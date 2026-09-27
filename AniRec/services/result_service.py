"""Profile-scoped persistence for the latest successful pipeline result."""

from __future__ import annotations

from pathlib import Path
import base64
import binascii
import hashlib
import json
import sqlite3
import zlib
from contextlib import closing
from collections import OrderedDict
from threading import RLock

try:
    from ..errors import DataError
    from ..infrastructure.json_storage import JsonStore
    from ..infrastructure.paths import profile_dir, app_data_dir
    from ..models import PipelineResult
except ImportError:  # Compatibility with the legacy top-level import path.
    from errors import DataError
    from infrastructure.json_storage import JsonStore
    from infrastructure.paths import profile_dir, app_data_dir
    from models import PipelineResult


LATEST_RESULT_FILENAME = "latest_result.json"
_LOADED_RESULTS_LIMIT = 2
_SNAPSHOT_ANIME_FIELDS = ("mean_score", "mean_score_source", "scoring_users")


class ResultService:
    def __init__(
        self,
        *,
        root_override: str | Path | None = None,
        store: JsonStore | None = None,
    ) -> None:
        self._root_override = root_override
        self._store = store or JsonStore()
        self._loaded: OrderedDict[str, tuple[tuple, PipelineResult]] = OrderedDict()
        self._loaded_lock = RLock()

    def path(self, profile_id: str) -> Path:
        return profile_dir(profile_id, self._root_override) / LATEST_RESULT_FILENAME

    def load(self, profile_id: str) -> PipelineResult | None:
        path = self.path(profile_id)
        if not path.exists():
            return None
        try:
            revision = self._revision(path)
            with self._loaded_lock:
                cached = self._loaded.get(profile_id)
                if cached is not None and cached[0] == revision:
                    self._loaded.move_to_end(profile_id)
                    return cached[1]
            payload = dict(self._store.read(path))
            if "storage_format" in payload:
                if payload["storage_format"] != "compact-ranking-v1":
                    raise ValueError("Unsupported saved ranking format.")
                packed = base64.b64decode(payload.pop("ranking_data"), validate=True)
                decoder = zlib.decompressobj()
                raw = decoder.decompress(packed, 64 * 1024 * 1024)
                if not decoder.eof or decoder.unused_data:
                    raise ValueError("Invalid or oversized saved ranking.")
                rows = json.loads(raw)
                refs = {row["anime_ref"] for row in rows}
                metadata = self._read_metadata(refs)
                for row in rows:
                    anime = dict(metadata[row.pop("anime_ref")])
                    anime.update(row.pop("anime_snapshot_values", {}))
                    row["anime"] = anime
                payload["recommendations"] = rows
            result = PipelineResult.from_dict(payload)
            if revision == self._revision(path):
                self._remember(profile_id, revision, result)
            return result
        except (OSError, TypeError, ValueError, KeyError, AttributeError, binascii.Error, sqlite3.Error, zlib.error) as error:
            raise DataError("The saved pipeline result is invalid.") from error

    def save(self, profile_id: str, result: PipelineResult) -> Path:
        destination = self.path(profile_id)  # Validate profile scope before writes.
        payload = result.to_dict()
        records = {}
        rows = payload.pop("recommendations")
        for row in rows:
            anime = row.pop("anime")
            row["anime_snapshot_values"] = {
                field: anime.pop(field) for field in _SNAPSHOT_ANIME_FIELDS
            }
            encoded = json.dumps(anime, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            ref = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
            records[ref] = encoded
            row["anime_ref"] = ref
        # Public immutable metadata commits first; the existing atomic pointer
        # write then exposes the new personal ranking in one replacement.
        self._write_metadata(records)
        packed = zlib.compress(json.dumps(rows, separators=(",", ":")).encode("utf-8"))
        payload.update(storage_format="compact-ranking-v1", ranking_data=base64.b64encode(packed).decode("ascii"))
        written = self._store.write(payload, destination)
        self._remember(profile_id, self._revision(written), result)
        return written

    def _metadata_path(self):
        return app_data_dir(self._root_override) / "catalogue" / "anime_metadata.sqlite"

    def _revision(self, path):
        source = path.stat()
        metadata_path = self._metadata_path()
        metadata = metadata_path.stat() if metadata_path.exists() else None
        return (source.st_mtime_ns, source.st_size,
                metadata.st_mtime_ns if metadata else None,
                metadata.st_size if metadata else None)

    def _remember(self, profile_id, revision, result):
        with self._loaded_lock:
            self._loaded[profile_id] = (revision, result)
            self._loaded.move_to_end(profile_id)
            while len(self._loaded) > _LOADED_RESULTS_LIMIT:
                self._loaded.popitem(last=False)

    def _write_metadata(self, records):
        if not records:
            return
        path = self._metadata_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path, timeout=30)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS anime_metadata (ref TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            db.executemany("INSERT OR IGNORE INTO anime_metadata VALUES (?, ?)", records.items())

    def _read_metadata(self, refs):
        if not refs:
            return {}
        path = self._metadata_path()
        metadata = {}
        with closing(sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)) as db:
            ordered = sorted(refs)
            for start in range(0, len(ordered), 500):
                batch = ordered[start:start + 500]
                for ref, encoded in db.execute(
                    f"SELECT ref,payload FROM anime_metadata WHERE ref IN ({','.join('?' for _ in batch)})", batch
                ):
                    if hashlib.sha256(encoded.encode("utf-8")).hexdigest() != ref:
                        raise ValueError("Corrupt anime metadata reference.")
                    metadata[ref] = json.loads(encoded)
        if metadata.keys() != refs:
            raise ValueError("Missing anime metadata reference.")
        return metadata

    def save_merged(self, profile_id: str, result: PipelineResult) -> PipelineResult:
        previous = self.load(profile_id)
        if previous is None:
            self.save(profile_id, result)
            return result

        user_stats = dict(previous.user_stats)
        user_stats.update(result.user_stats)
        generated_files = tuple(
            dict.fromkeys((*previous.generated_files, *result.generated_files))
        )
        merged = PipelineResult(
            recommendations=result.recommendations or previous.recommendations,
            genre_stats=result.genre_stats or previous.genre_stats,
            user_stats=user_stats,
            generated_files=generated_files,
            started_at=result.started_at or previous.started_at,
            completed_at=result.completed_at or previous.completed_at,
        )
        if not result.recommendations:
            # A sync or unchanged refresh only updates small profile stats.
            # Keep the validated ranking blob and shared metadata untouched.
            path = self.path(profile_id)
            payload = dict(self._store.read(path))
            if payload.get("storage_format") == "compact-ranking-v1":
                payload["user_stats"] = dict(merged.user_stats)
                payload["generated_files"] = list(merged.generated_files)
                payload["started_at"] = merged.started_at
                payload["completed_at"] = merged.completed_at
                self._store.write(payload, path)
                self._remember(profile_id, self._revision(path), merged)
                return merged
        self.save(profile_id, merged)
        return merged
