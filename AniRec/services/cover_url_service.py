"""Public MAL artwork and community scores missing from the model catalogue.

The installed model catalogue (the collector snapshot) carries no picture
URLs or community scores, so a feed ranked from it had neither. After a feed
is built, missing values are looked up through MyAnimeList's official API
(``/v2/anime/{id}?fields=main_picture,mean``) with the installation's Client
ID and kept in a cache shared by every account. Existing catalogue values
always take precedence. API-enriched scores are marked in saved feeds and
refreshed after a month, including when a current feed is reused.

A title MyAnimeList has no picture for stays without one (nothing is
invented) and is asked about again only after a month. A refused Client ID,
a rate limit or an unreachable service ends the run early and is not
remembered: the feed is saved as it was. At most ``max_lookups`` titles are
looked up per run, so a long feed fills in over several runs.
"""

from __future__ import annotations

import csv
import logging
import math
import threading
import time
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

from ..errors import AniRecError, NotFoundError
from ..infrastructure.json_storage import JsonStore
from ..infrastructure.mal_client import MALClient
from ..infrastructure.paths import cache_dir
from ..models.domain import PipelineResult, Recommendation

LOGGER = logging.getLogger("AniRec.covers")

MAX_LOOKUPS = 60
WORKERS = 4
# How long "MyAnimeList has no picture for this title" is believed.
NO_PICTURE_TTL_SECONDS = 30 * 24 * 3600
_ANIME_URL = "https://api.myanimelist.net/v2/anime/{}"


def _https(value) -> str | None:
    return value if isinstance(value, str) and value.startswith("https://") and len(value) <= 2048 else None


def _score(value) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and 0 < number <= 10 else None


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

    def _recent(self, value) -> bool:
        try:
            checked_at = float(value)
        except (TypeError, ValueError, OverflowError):
            return False
        return math.isfinite(checked_at) and 0 <= self._clock() - checked_at < NO_PICTURE_TTL_SECONDS

    def _known(self, entry: dict | None, *, cover: bool, score: bool) -> bool:
        if not entry:
            return False
        cover_known = bool(_https(entry.get("medium")) or _https(entry.get("large"))) or self._recent(entry.get("checked_at"))
        score_known = self._recent(entry.get("score_checked_at"))
        return (not cover or cover_known) and (not score or score_known)

    def fill(self, result: PipelineResult, client_id: str | None) -> PipelineResult:
        """``result`` with public metadata the cache or MyAnimeList can supply."""
        def needs_score(rec: Recommendation) -> bool:
            return rec.anime.mean_score_source in (None, "mal-api") and (
                rec.anime.mean_score is None or rec.anime.mean_score_source == "mal-api"
            )

        missing = [
            (r.anime.mal_id, not r.anime.cover_url,
             needs_score(r))
            for r in result.recommendations
            if r.anime.mal_id and (not r.anime.cover_url or needs_score(r))
        ]
        if not missing:
            return result
        with self._lock:
            cache = self._read()
            wanted = [
                mal_id for mal_id, need_cover, need_score in dict.fromkeys(missing)
                if not self._known(cache.get(str(mal_id)), cover=need_cover, score=need_score)
            ]
        found = self._look_up(wanted[: self._max_lookups], client_id) if client_id else {}
        cache = self._merge_and_read(found)
        return self._applied(result, cache)

    def cached(self, result: PipelineResult) -> PipelineResult:
        """Apply previously fetched public metadata without another MAL request."""
        return self._applied(result, self._read())

    def evidence_posters(
        self, recommendation: Recommendation, client_id: str | None,
        *, profile_directory: Path | None = None,
    ) -> list[tuple[int, str | None]]:
        """Posters for at most three positive single-title effects of one saved pick.

        The IDs come only from that pick's recorded explanation. Looking them
        up when its inspector opens avoids fetching artwork for every saved
        explanation in a multi-reader feed.
        """
        explanation = recommendation.explanation
        if not isinstance(explanation, Mapping) or explanation.get("method") != "counterfactual-removal":
            return []
        influences = explanation.get("influences")
        if not isinstance(influences, (list, tuple)):
            return []
        strongest: dict[int, float] = {}
        for item in influences:
            if not isinstance(item, Mapping):
                continue
            mal_id, value = item.get("mal_id"), item.get("value")
            if not isinstance(mal_id, int) or isinstance(mal_id, bool) or mal_id <= 0:
                continue
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                continue
            strongest[mal_id] = max(strongest.get(mal_id, 0.0), float(value))
        ids = sorted(strongest, key=lambda mal_id: (-strongest[mal_id], mal_id))[:3]
        if not ids:
            return []
        with self._lock:
            cache = self._read()
        missing = [mal_id for mal_id in ids if not _https((cache.get(str(mal_id)) or {}).get("medium"))
                   and not _https((cache.get(str(mal_id)) or {}).get("large"))]
        imported = self._imported_covers(profile_directory, set(missing))
        wanted = [mal_id for mal_id in ids if str(mal_id) not in imported
                  and not self._known(cache.get(str(mal_id)), cover=True, score=False)]
        found = self._look_up(wanted[: self._max_lookups], client_id) if client_id else {}
        cache = self._merge_and_read({**imported, **found})
        return [
            (mal_id, _https((cache.get(str(mal_id)) or {}).get("medium"))
             or _https((cache.get(str(mal_id)) or {}).get("large")))
            for mal_id in ids
        ]

    def _merge_and_read(self, updates: dict[str, dict]) -> dict[str, dict]:
        """Serialize cache writes without holding the lock during MAL requests."""
        with self._lock:
            cache = self._read()
            if not updates:
                return cache
            for key, new in updates.items():
                old = cache.get(key, {})
                cache[key] = {
                    **old,
                    **new,
                    "medium": new.get("medium") or _https(old.get("medium")),
                    "large": new.get("large") or _https(old.get("large")),
                    "mean": new.get("mean", old.get("mean")),
                }
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                self._store.write(cache, self._path)
            except (AniRecError, OSError) as error:
                LOGGER.warning("Cover cache could not be saved: %s", type(error).__name__)
            return cache

    def _imported_covers(self, profile_directory: Path | None, ids: set[int]) -> dict[str, dict]:
        """Reuse public picture URLs already present in this reader's MAL import."""
        if profile_directory is None or not ids:
            return {}
        found: dict[str, dict] = {}
        try:
            with (profile_directory / "completed_anime.csv").open(newline="", encoding="utf-8-sig") as stream:
                for row in csv.DictReader(stream):
                    raw_id = row.get("Anime ID")
                    mal_id = raw_id.strip() if isinstance(raw_id, str) else ""
                    if not mal_id.isdecimal() or len(mal_id) > 12 or int(mal_id) not in ids:
                        continue
                    medium = _https(row.get("Picture URL"))
                    large = _https(row.get("Large Picture URL"))
                    if medium or large:
                        found[str(int(mal_id))] = {"medium": medium, "large": large, "checked_at": self._clock()}
                    if len(found) == len(ids):
                        break
        except (OSError, csv.Error, UnicodeError):
            return {}
        return found

    def _look_up(self, ids: list[int], client_id: str) -> dict[str, dict]:
        stop = threading.Event()
        found: dict[str, dict] = {}

        def one(mal_id: int) -> None:
            if stop.is_set():
                return
            try:
                node = self._client.get_json(
                    _ANIME_URL.format(mal_id), params={"fields": "main_picture,mean"}, client_id=client_id
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
                "mean": _score(node.get("mean")) if isinstance(node, dict) else None,
                "score_checked_at": self._clock(),
            }

        if self._workers <= 1:
            for mal_id in ids:
                one(mal_id)
        else:
            with ThreadPoolExecutor(max_workers=self._workers, thread_name_prefix="anirec-covers") as pool:
                list(pool.map(one, ids))
        return found

    def _applied(self, result: PipelineResult, cache: dict[str, dict]) -> PipelineResult:
        changed = False
        recommendations = []
        for rec in result.recommendations:
            entry = cache.get(str(rec.anime.mal_id)) if rec.anime.mal_id else None
            medium = _https((entry or {}).get("medium")) if not rec.anime.cover_url else None
            large = _https((entry or {}).get("large")) if not rec.anime.cover_url else None
            score_from_api = rec.anime.mean_score_source in (None, "mal-api") and (
                rec.anime.mean_score is None or rec.anime.mean_score_source == "mal-api"
            )
            score_recent = entry is not None and self._recent(entry.get("score_checked_at"))
            mean = _score(entry.get("mean")) if score_from_api and score_recent and entry else None
            replace_score = score_from_api and score_recent and mean != rec.anime.mean_score
            if medium or large or replace_score:
                rec = replace(rec, anime=replace(
                    rec.anime,
                    cover_url=rec.anime.cover_url or medium or large,
                    large_cover_url=rec.anime.large_cover_url or large or medium,
                    mean_score=mean if replace_score else rec.anime.mean_score,
                    mean_score_source="mal-api" if replace_score and mean is not None else rec.anime.mean_score_source,
                ))
                changed = True
            recommendations.append(rec)
        return replace(result, recommendations=tuple(recommendations)) if changed else result
