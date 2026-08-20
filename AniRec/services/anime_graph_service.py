"""Fetch and cache the MyAnimeList recommendation graph for a profile.

Only the detail endpoint carries ``recommendations`` and ``related_anime``, so
each seed costs one request. The cache exists to keep that cost off every run:
entries are reused until they age out, and a run that is cancelled or fails
part way keeps whatever it managed to gather.

This service is entirely optional. If it returns nothing, scoring proceeds on
content and community rating alone with the weights renormalised.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path

try:
    from ..errors import AniRecError
    from ..infrastructure.json_storage import JsonStore
    from ..infrastructure.mal_client import MALClient
except ImportError:  # Compatibility with the S01 top-level test import path.
    from errors import AniRecError
    from infrastructure.json_storage import JsonStore
    from infrastructure.mal_client import MALClient


API_BASE_URL = "https://api.myanimelist.net/v2"
GRAPH_FIELDS = "id,recommendations,related_anime"
CACHE_FILENAME = "anime_graph.json"
CACHE_SCHEMA_VERSION = 1

# Recommendation edges change slowly, so a month-old entry is still useful and
# saves a request.
CACHE_TTL_SECONDS = 30 * 24 * 60 * 60

# Paced well inside MyAnimeList's limits. The graph is a background nicety, not
# something worth pushing the API for.
REQUESTS_PER_SECOND = 4.0


class AnimeGraphService:
    def __init__(
        self,
        *,
        client: MALClient | None = None,
        store: JsonStore | None = None,
        http_get: Callable | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client or MALClient(http_get=http_get)
        self._store = store or JsonStore()
        self._clock = clock
        self._sleep = sleep

    def cache_path(self, directory: str | Path) -> Path:
        return Path(directory) / CACHE_FILENAME

    def load_cache(self, directory: str | Path) -> dict[int, dict]:
        path = self.cache_path(directory)
        if not path.is_file():
            return {}
        try:
            payload = self._store.read(path)
        except (OSError, ValueError):
            # A damaged cache is a performance problem, never a correctness
            # one. Discard it and let the next run rebuild what it needs.
            return {}
        if payload.get("schema_version") != CACHE_SCHEMA_VERSION:
            return {}
        entries = payload.get("entries")
        if not isinstance(entries, Mapping):
            return {}

        now = self._clock()
        fresh: dict[int, dict] = {}
        for key, entry in entries.items():
            if not isinstance(entry, Mapping):
                continue
            try:
                mal_id = int(key)
                fetched_at = float(entry.get("fetched_at") or 0)
            except (TypeError, ValueError):
                continue
            if now - fetched_at <= CACHE_TTL_SECONDS:
                fresh[mal_id] = dict(entry)
        return fresh

    def save_cache(self, directory: str | Path, graph: Mapping[int, Mapping]) -> Path:
        payload = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "entries": {str(key): dict(value) for key, value in graph.items()},
        }
        return self._store.write(payload, self.cache_path(directory))

    def build_graph(
        self,
        seed_ids: Iterable[int],
        directory: str | Path,
        *,
        access_token: str | None = None,
        client_id: str | None = None,
        cancellation=None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[int, dict]:
        """Return graph entries for the seeds, fetching only what is missing."""
        graph = self.load_cache(directory)
        wanted = [int(value) for value in seed_ids if value is not None]
        missing = [mal_id for mal_id in wanted if mal_id not in graph]
        if not missing:
            return {mal_id: graph[mal_id] for mal_id in wanted if mal_id in graph}

        interval = 1.0 / REQUESTS_PER_SECOND if REQUESTS_PER_SECOND > 0 else 0.0
        fetched_any = False
        try:
            for position, mal_id in enumerate(missing, start=1):
                if _is_cancelled(cancellation):
                    break
                if progress_callback is not None:
                    progress_callback(position, len(missing))
                entry = self._fetch_entry(
                    mal_id,
                    access_token=access_token,
                    client_id=client_id,
                    cancellation=cancellation,
                )
                if entry is not None:
                    graph[mal_id] = entry
                    fetched_any = True
                if interval and position < len(missing):
                    self._sleep(interval)
        finally:
            # Persist partial progress so an interrupted run is never repeated
            # from the beginning.
            if fetched_any:
                try:
                    self.save_cache(directory, graph)
                except (OSError, ValueError):
                    pass
        return {mal_id: graph[mal_id] for mal_id in wanted if mal_id in graph}

    def _fetch_entry(
        self,
        mal_id: int,
        *,
        access_token: str | None,
        client_id: str | None,
        cancellation,
    ) -> dict | None:
        try:
            payload = self._client.get_json(
                f"{API_BASE_URL}/anime/{int(mal_id)}",
                params={"fields": GRAPH_FIELDS},
                access_token=access_token,
                client_id=client_id,
                cancellation=cancellation,
            )
        except AniRecError:
            # One unavailable title must not abandon the whole walk.
            return None

        recommendations = []
        for item in payload.get("recommendations") or ():
            if not isinstance(item, Mapping):
                continue
            node = item.get("node")
            if not isinstance(node, Mapping):
                continue
            target = node.get("id")
            if target is None:
                continue
            recommendations.append(
                {
                    "mal_id": int(target),
                    "votes": int(item.get("num_recommendations") or 0),
                }
            )

        related = []
        for item in payload.get("related_anime") or ():
            if not isinstance(item, Mapping):
                continue
            node = item.get("node")
            if not isinstance(node, Mapping):
                continue
            target = node.get("id")
            if target is None:
                continue
            related.append(
                {
                    "mal_id": int(target),
                    "relation": str(item.get("relation_type") or "").strip().casefold(),
                }
            )

        return {
            "fetched_at": self._clock(),
            "recommendations": recommendations,
            "related": related,
        }


def _is_cancelled(cancellation) -> bool:
    if cancellation is None:
        return False
    value = getattr(cancellation, "is_cancelled", cancellation)
    return bool(value() if callable(value) else value)
