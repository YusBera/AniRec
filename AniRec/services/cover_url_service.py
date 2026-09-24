"""Cover addresses for picks whose catalogue has none.

The installed model catalogue (the collector snapshot) carries no picture
URLs, so a feed ranked from it had no artwork. After a feed is built, each
pick without a cover is looked up once through MyAnimeList's official API
(``/v2/anime/{id}?fields=main_picture``) with the installation's Client ID,
and the answer is kept in a cache shared by every account, because a cover
is public metadata.

A title MyAnimeList has no picture for stays without one (nothing is
invented) and is asked about again only after a month. A refused Client ID,
a rate limit or an unreachable service ends the run early and is not
remembered: the feed is saved as it was. At most ``max_lookups`` titles are
looked up per run, so a long feed fills in over several runs.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

from ..errors import AniRecError, NotFoundError
from ..infrastructure.json_storage import JsonStore
from ..infrastructure.mal_client import MALClient
from ..infrastructure.paths import cache_dir
from ..models.domain import PipelineResult

LOGGER = logging.getLogger("AniRec.covers")

MAX_LOOKUPS = 60
WORKERS = 4
# How long "MyAnimeList has no picture for this title" is believed.
NO_PICTURE_TTL_SECONDS = 30 * 24 * 3600
_ANIME_URL = "https://api.myanimelist.net/v2/anime/{}"


def _https(value) -> str | None:
    return value if isinstance(value, str) and value.startswith("https://") and len(value) <= 2048 else None


class CoverUrlService:
    def __init__(
        self,
        *,
        root_override: str | Path | None = None,
        client=None,
        store: JsonStore | None = None,
        clock: Callable[[], float] = time.time,
        max_lookups: int = MAX_LOOKUPS,
        workers: int = WORKERS,
    ) -> None:
        self._path = cache_dir(root_override) / "cover_urls.json"
        self._client = client or MALClient()
        self._store = store or JsonStore()
        self._clock = clock
        self._max_lookups = max_lookups
        self._workers = workers
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    def _read(self) -> dict[str, dict]:
        try:
            data = self._store.read(self._path) if self._path.exists() else {}
        except (AniRecError, OSError, ValueError):
            return {}   # a corrupt cache is only a cache
        return {str(k): v for k, v in data.items() if isinstance(v, dict)} if isinstance(data, dict) else {}

    def _known(self, entry: dict | None) -> bool:
        if not entry:
            return False
        if entry.get("medium") or entry.get("large"):
            return True
        return self._clock() - float(entry.get("checked_at") or 0) < NO_PICTURE_TTL_SECONDS

    def fill(self, result: PipelineResult, client_id: str | None) -> PipelineResult:
        """``result`` with every cover the cache or MyAnimeList can supply."""
        if not client_id:
            return result
        missing = [r.anime.mal_id for r in result.recommendations if r.anime.mal_id and not r.anime.cover_url]
        if not missing:
            return result
        with self._lock:
            cache = self._read()
            wanted = [i for i in dict.fromkeys(missing) if not self._known(cache.get(str(i)))]
            found = self._look_up(wanted[: self._max_lookups], client_id)
            if found:
                cache.update(found)
                try:
                    self._path.parent.mkdir(parents=True, exist_ok=True)
                    self._store.write(cache, self._path)
                except (AniRecError, OSError) as error:
                    LOGGER.warning("Cover cache could not be saved: %s", type(error).__name__)
        return self._applied(result, cache)

    def _look_up(self, ids: list[int], client_id: str) -> dict[str, dict]:
        stop = threading.Event()
        found: dict[str, dict] = {}

        def one(mal_id: int) -> None:
            if stop.is_set():
                return
            try:
                node = self._client.get_json(
                    _ANIME_URL.format(mal_id), params={"fields": "main_picture"}, client_id=client_id
                )
            except NotFoundError:
                node = {}
            except AniRecError as error:
                # Refused Client ID, rate limit, network: stop, remember nothing.
                if not stop.is_set():
                    LOGGER.warning("Cover lookups stopped: %s", type(error).__name__)
                stop.set()
                return
            picture = node.get("main_picture") if isinstance(node, dict) else None
            picture = picture if isinstance(picture, dict) else {}
            found[str(mal_id)] = {
                "medium": _https(picture.get("medium")),
                "large": _https(picture.get("large")),
                "checked_at": self._clock(),
            }

        if self._workers <= 1:
            for mal_id in ids:
                one(mal_id)
        else:
            with ThreadPoolExecutor(max_workers=self._workers, thread_name_prefix="anirec-covers") as pool:
                list(pool.map(one, ids))
        return found

    @staticmethod
    def _applied(result: PipelineResult, cache: dict[str, dict]) -> PipelineResult:
        changed = False
        recommendations = []
        for rec in result.recommendations:
            entry = cache.get(str(rec.anime.mal_id)) if rec.anime.mal_id and not rec.anime.cover_url else None
            medium = _https((entry or {}).get("medium"))
            large = _https((entry or {}).get("large"))
            if medium or large:
                rec = replace(rec, anime=replace(rec.anime, cover_url=medium or large, large_cover_url=large or medium))
                changed = True
            recommendations.append(rec)
        return replace(result, recommendations=tuple(recommendations)) if changed else result
