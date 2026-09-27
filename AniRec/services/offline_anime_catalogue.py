"""Read a separately prepared, anime-only reference snapshot for serving.

The reference database is an explicit local input, never a collector operational
database. Model membership, eligibility metadata and model scores remain owned
by the installed ONNX bundle. This adapter supplies observed public metadata.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import replace
from math import isfinite
from pathlib import Path
from urllib.parse import urlparse

try:
    from ..models.domain import PipelineResult
except ImportError:  # S01 top-level compatibility import path.
    from models.domain import PipelineResult


ANIME_REFERENCE_ENV = "ANIREC_ANIME_REFERENCE_DB"
_TABLES = frozenset({"anime_metadata", "field_observation", "snapshot_meta"})
_CANDIDATE_FIELDS = ("score", "scored_by", "popularity", "members")
_DISPLAY_FIELDS = ("synopsis", "image_url_medium", "image_url_large", "trailer_url")
_CHUNK_SIZE = 500


def _observed_number(value: object, *, minimum: float = 0, maximum: float | None = None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not (isfinite(number) and number >= minimum and (maximum is None or number <= maximum)):
        return None
    return value


def _https_on_host(value: object, hosts: frozenset[str]) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = urlparse(value.strip())
        if parsed.scheme != "https" or parsed.hostname not in hosts or parsed.username or parsed.password:
            return None
    except ValueError:
        return None
    return value.strip()


class OfflineAnimeCatalogue:
    """Join observed anime fields by MAL ID without reading personal data."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve(strict=True)
        with self._connect() as db:
            tables = {name for (name,) in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )}
            if tables != _TABLES:
                raise ValueError("The anime reference must contain only the three anime-only tables.")
            version = db.execute(
                "SELECT value FROM snapshot_meta WHERE key='format_version'"
            ).fetchone()
            if version is None or version[0] != "offline-staging-1":
                raise ValueError("The anime reference format is unsupported.")
            expected = {
                "anime_metadata": {"anime_id", *_CANDIDATE_FIELDS, *_DISPLAY_FIELDS},
                "field_observation": {"anime_id", "field_name", "state"},
            }
            for table, required in expected.items():
                columns = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
                if not required <= columns:
                    raise ValueError(f"The anime reference {table} columns are incomplete.")

    @classmethod
    def from_environment(cls) -> "OfflineAnimeCatalogue | None":
        path = os.environ.get(ANIME_REFERENCE_ENV)
        return cls(path) if path else None

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        return db

    def _records(self, ids: set[int], fields: tuple[str, ...]):
        if not ids:
            return {}
        found = {}
        ordered = sorted(ids)
        with self._connect() as db:
            for start in range(0, len(ordered), _CHUNK_SIZE):
                batch = ordered[start:start + _CHUNK_SIZE]
                slots = ",".join("?" for _ in batch)
                values = {
                    row["anime_id"]: dict(row) for row in db.execute(
                        f"SELECT anime_id,{','.join(fields)} FROM anime_metadata "
                        f"WHERE anime_id IN ({slots})", batch
                    )
                }
                if not values:
                    continue
                states: dict[int, dict[str, str]] = {anime_id: {} for anime_id in values}
                for row in db.execute(
                    "SELECT anime_id,field_name,state FROM field_observation "
                    f"WHERE anime_id IN ({slots}) AND field_name IN "
                    f"({','.join('?' for _ in fields)})", (*batch, *fields)
                ):
                    if row["field_name"] in fields and row["anime_id"] in states:
                        states[row["anime_id"]][row["field_name"]] = row["state"]
                found.update((anime_id, (value, states[anime_id])) for anime_id, value in values.items())
        return found

    @staticmethod
    def _ids(rows):
        ids = set()
        for row in rows:
            try:
                anime_id = int(row.get("Anime ID"))
            except (TypeError, ValueError):
                continue
            if anime_id > 0:
                ids.add(anime_id)
        return ids

    def enrich_candidates(self, rows: list[dict]) -> list[dict]:
        records = self._records(self._ids(rows), _CANDIDATE_FIELDS)
        result = []
        for source in rows:
            row = dict(source)
            try:
                anime_id = int(row.get("Anime ID"))
            except (TypeError, ValueError):
                anime_id = None
            entry = records.get(anime_id)
            if entry is not None:
                values, states = entry
                if states.get("score") == "confirmed_absent":
                    row["Mean Score"] = None
                    row["Mean Score Source"] = "offline-absent"
                elif states.get("score") == "present":
                    score = _observed_number(values["score"], maximum=10)
                    if score is not None:
                        row["Mean Score"] = score
                        row["Mean Score Source"] = "offline-snapshot"
                for field, column in (
                    ("scored_by", "Scoring Users"),
                    ("popularity", "Catalog Popularity"),
                    ("members", "Catalog Members"),
                ):
                    value = _observed_number(values[field])
                    if states.get(field) == "present" and value is not None and float(value).is_integer():
                        row[column] = int(value)
            result.append(row)
        return result

    def enrich_selected(self, rows: list[dict]) -> list[dict]:
        records = self._records(self._ids(rows), _DISPLAY_FIELDS)
        result = []
        for source in rows:
            row = dict(source)
            try:
                anime_id = int(row.get("Anime ID"))
            except (TypeError, ValueError):
                anime_id = None
            entry = records.get(anime_id)
            if entry is not None:
                values, states = entry
                for field, column in (
                    ("image_url_medium", "Picture URL"),
                    ("image_url_large", "Large Picture URL"),
                ):
                    url = _https_on_host(values[field], frozenset({"cdn.myanimelist.net"}))
                    if states.get(field) == "present" and url:
                        row[column] = url
                if states.get("synopsis") == "present" and isinstance(values["synopsis"], str):
                    row["Synopsis"] = values["synopsis"].strip() or row.get("Synopsis")
                url = _https_on_host(
                    values["trailer_url"], frozenset({"youtube.com", "www.youtube.com", "youtu.be"})
                )
                if states.get("trailer_url") == "present" and url:
                    row["PV YouTube URL"] = url
            result.append(row)
        return result

    def enrich_result(self, result: PipelineResult) -> PipelineResult:
        """Refresh display fields; saved rank inputs and evidence stay immutable."""
        rows = [
            {
                "Anime ID": rec.anime.mal_id,
                "Picture URL": rec.anime.cover_url,
                "Large Picture URL": rec.anime.large_cover_url,
                "Synopsis": rec.anime.synopsis,
                "PV YouTube URL": rec.anime.pv_youtube_url,
            }
            for rec in result.recommendations
        ]
        enriched = self.enrich_selected(rows)
        recommendations = tuple(
            replace(rec, anime=replace(
                rec.anime,
                cover_url=row.get("Picture URL"),
                large_cover_url=row.get("Large Picture URL"),
                synopsis=row.get("Synopsis"),
                pv_youtube_url=row.get("PV YouTube URL"),
            ))
            for rec, row in zip(result.recommendations, enriched)
        )
        return replace(result, recommendations=recommendations)
