"""Derive a taste-profile payload from profile-scoped synchronized MAL data.

This service reads the CSV snapshots the existing sync already writes. It is
deliberately independent of candidate generation, recommendation ranking,
collaborative signals, and future neural-network work.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import pandas as pd

try:
    from ..errors import AniRecError
    from ..genre_utils import parse_genres
    from ..infrastructure.csv_storage import CsvStorage
except ImportError:  # Compatibility with the legacy top-level import path.
    from errors import AniRecError
    from genre_utils import parse_genres
    from infrastructure.csv_storage import CsvStorage

from .profile_service import ProfileService


COMPLETED_ANIME_FILENAME = "completed_anime.csv"
TOP_ANIME_FILENAME = "top_anime.csv"
MINIMUM_GROUP_SIZE = 3
VISIBLE_GROUP_LIMIT = 8
VISIBLE_TITLE_LIMIT = 8


class ProfileStatisticsUnavailableReason(str, Enum):
    NOT_CONNECTED = "not-connected"
    NO_DATA = "no-data"
    INVALID_DATA = "invalid-data"


class ProfileStatisticsUnavailable(Exception):
    """A local profile snapshot cannot be converted into statistics."""

    def __init__(
        self,
        reason: ProfileStatisticsUnavailableReason,
        message: str = "",
    ) -> None:
        super().__init__(message or reason.value)
        self.reason = reason
        self.message = message


@dataclass(frozen=True)
class _TitleRecord:
    title: str
    mal_id: int | None
    user_score: float | None
    community_score: float | None
    episodes: int | None
    year: int | None
    start_date: str
    genres: tuple[str, ...]
    studios: tuple[str, ...]
    cover_url: str | None
    scoring_users: int | None

    @property
    def delta(self) -> float | None:
        if self.user_score is None or self.community_score is None:
            return None
        return self.user_score - self.community_score


class ProfileStatisticsService:
    """Build the documented Profile payload from the active local snapshot."""

    def __init__(
        self,
        profile_service: ProfileService,
        *,
        storage: CsvStorage | None = None,
    ) -> None:
        self._profiles = profile_service
        self._storage = storage or CsvStorage()

    def profile_payload(self) -> dict:
        try:
            profile = self._profiles.active_profile()
        except (AniRecError, OSError, TypeError, ValueError) as error:
            raise ProfileStatisticsUnavailable(
                ProfileStatisticsUnavailableReason.INVALID_DATA,
                "The active local profile could not be read.",
            ) from error
        if profile is None:
            raise ProfileStatisticsUnavailable(
                ProfileStatisticsUnavailableReason.NOT_CONNECTED
            )

        directory = self._profiles.directory(profile.profile_id)
        completed_path = directory / COMPLETED_ANIME_FILENAME
        try:
            completed = self._storage.read(
                completed_path,
                required_columns=("Title", "User Score"),
            )
        except FileNotFoundError as error:
            raise ProfileStatisticsUnavailable(
                ProfileStatisticsUnavailableReason.NO_DATA,
                "Sync your MyAnimeList library before opening your taste profile.",
            ) from error
        except (OSError, TypeError, ValueError, pd.errors.ParserError) as error:
            raise ProfileStatisticsUnavailable(
                ProfileStatisticsUnavailableReason.INVALID_DATA,
                "The synchronized anime-list snapshot could not be read.",
            ) from error
        if completed.empty:
            raise ProfileStatisticsUnavailable(
                ProfileStatisticsUnavailableReason.NO_DATA,
                "No completed anime are available in the synchronized library.",
            )

        records = tuple(
            record
            for _, row in completed.iterrows()
            if (record := _record_from_row(row)) is not None
        )
        if not records:
            raise ProfileStatisticsUnavailable(
                ProfileStatisticsUnavailableReason.NO_DATA,
                "No readable completed anime are available in the synchronized library.",
            )

        payload = {
            "identity": _identity_payload(profile.username, records),
            "fingerprint": _fingerprint_payload(records),
            "rating_distribution": _distribution_payload(records),
            "hot_takes": _hot_takes_payload(records),
            "genres": _genre_payload(records),
            "studios": _studio_payload(records),
            "eras": _era_payload(records),
        }
        hype = self._hype_killers(directory / TOP_ANIME_FILENAME, records)
        if hype:
            payload["hype_killers"] = hype
        return payload

    def _hype_killers(
        self, top_path: Path, records: tuple[_TitleRecord, ...]
    ) -> dict:
        if not top_path.is_file():
            return {}
        try:
            top = self._storage.read(top_path, required_columns=("Title",))
        except (OSError, TypeError, ValueError, pd.errors.ParserError):
            return {}

        ranks_by_id: dict[int, int] = {}
        ranks_by_title: dict[str, int] = {}
        for offset, (_, row) in enumerate(top.iterrows(), start=1):
            mal_id = _optional_int(row.get("Anime ID"))
            title = _clean_text(row.get("Title"))
            if mal_id is not None:
                ranks_by_id.setdefault(mal_id, offset)
            if title:
                ranks_by_title.setdefault(title.casefold(), offset)

        candidates = []
        for record in records:
            rank = (
                ranks_by_id.get(record.mal_id)
                if record.mal_id is not None
                else None
            ) or ranks_by_title.get(record.title.casefold())
            if (
                rank is None
                or record.user_score is None
                or record.community_score is None
                or record.user_score > 5
                or record.community_score < 7.5
                or (record.delta or 0.0) > -2.0
            ):
                continue
            candidates.append(_verdict_payload(record, ranked_position=rank))
        if not candidates:
            return {}

        candidates.sort(key=lambda item: (item["delta"], item["ranked_position"]))
        biggest = candidates[0]
        entries = sorted(
            candidates[1:], key=lambda item: item["ranked_position"]
        )[:5]
        return {
            "count": len(candidates),
            "biggest": biggest,
            "entries": entries,
        }


def _record_from_row(row: pd.Series) -> _TitleRecord | None:
    title = _clean_text(row.get("Title"))
    if not title:
        return None
    user_score = _optional_float(row.get("User Score"))
    if user_score is not None and not 1 <= user_score <= 10:
        user_score = None
    community_score = _optional_float(row.get("Mean Score"))
    if community_score is not None and not 0 <= community_score <= 10:
        community_score = None
    return _TitleRecord(
        title=title,
        mal_id=_optional_int(row.get("Anime ID")),
        user_score=user_score,
        community_score=community_score,
        episodes=_positive_int(row.get("Episodes")),
        year=_positive_int(row.get("Year")),
        start_date=_clean_text(row.get("Start Date")),
        genres=tuple(parse_genres(row.get("Genres"))),
        studios=tuple(parse_genres(row.get("Studios"))),
        cover_url=(
            _clean_text(row.get("Large Picture URL"))
            or _clean_text(row.get("Picture URL"))
            or None
        ),
        scoring_users=_optional_int(row.get("Scoring Users")),
    )


def _identity_payload(username: str, records: tuple[_TitleRecord, ...]) -> dict:
    scored = [record.user_score for record in records if record.user_score is not None]
    episodes = sum(record.episodes or 0 for record in records)
    return {
        "username": username,
        "profile_url": f"https://myanimelist.net/profile/{username}",
        "completed": len(records),
        "episodes": episodes,
        # MAL's synchronized title rows do not include runtime. Twenty-four
        # minutes per episode is intentionally presented as an approximation.
        "days_watched": episodes * 24 / 1440 if episodes else None,
        "mean_score": _mean(scored),
    }


def _fingerprint_payload(records: tuple[_TitleRecord, ...]) -> list[dict]:
    compared = [record for record in records if record.delta is not None]
    if not compared:
        return []

    sync = sum(abs(record.delta or 0.0) <= 1.0 for record in compared) / len(compared)
    bias = _mean([record.delta for record in compared if record.delta is not None]) or 0.0
    contrarian = (
        sum(abs(record.delta or 0.0) >= 2.0 for record in compared) / len(compared)
    )
    if bias < 0:
        bias_detail = (
            f"Your scores average {abs(bias):.2f} points below the community score."
        )
    elif bias > 0:
        bias_detail = (
            f"Your scores average {abs(bias):.2f} points above the community score."
        )
    else:
        bias_detail = "Your scores match the community average."
    return [
        {
            "id": "community-sync",
            "caption": "COMMUNITY SYNC",
            "value_text": f"{sync:.0%}",
            "label": (
                "HIGH ALIGNMENT"
                if sync >= 0.75
                else "MOSTLY ALIGNED"
                if sync >= 0.5
                else "LOW ALIGNMENT"
            ),
            "detail": (
                f"Your score is within one point of the community on "
                f"{round(sync * len(compared))} of {len(compared)} rated titles."
            ),
            "position": sync,
            "readout": "cells",
        },
        {
            "id": "rating-bias",
            "caption": "RATING BIAS",
            "value_text": f"{bias:+.2f}",
            "label": _bias_label(bias),
            "detail": bias_detail,
            "position": max(0.0, min(1.0, (bias + 2.0) / 4.0)),
            "scale_low": "HARSH",
            "scale_high": "GENEROUS",
            "readout": "scale",
            "tone": "you",
        },
        {
            "id": "contrarian",
            "caption": "CONTRARIAN",
            "value_text": f"{contrarian:.0%}",
            "label": (
                "OFTEN APART"
                if contrarian >= 0.4
                else "INDEPENDENT"
                if contrarian >= 0.2
                else "CONSENSUS-LEANING"
            ),
            "detail": (
                f"You differ from the community by at least two points on "
                f"{round(contrarian * len(compared))} of {len(compared)} rated titles."
            ),
            "position": contrarian,
            "readout": "cells",
        },
    ]


def _bias_label(bias: float) -> str:
    if bias <= -0.75:
        return "HARSH"
    if bias <= -0.2:
        return "SLIGHTLY HARSH"
    if bias >= 0.75:
        return "GENEROUS"
    if bias >= 0.2:
        return "SLIGHTLY GENEROUS"
    return "BALANCED"


def _distribution_payload(records: tuple[_TitleRecord, ...]) -> dict:
    counts = {score: 0 for score in range(1, 11)}
    for record in records:
        if record.user_score is None:
            continue
        rounded = int(round(record.user_score))
        if 1 <= rounded <= 10:
            counts[rounded] += 1
    return {
        "buckets": [
            {"score": score, "count": counts[score]}
            for score in range(10, 0, -1)
        ]
    }


def _hot_takes_payload(records: tuple[_TitleRecord, ...]) -> dict:
    comparable = [record for record in records if record.delta is not None]
    higher = sorted(
        (record for record in comparable if (record.delta or 0.0) > 0),
        key=lambda record: record.delta or 0.0,
        reverse=True,
    )[:5]
    lower = sorted(
        (record for record in comparable if (record.delta or 0.0) < 0),
        key=lambda record: record.delta or 0.0,
    )[:5]
    return {
        "higher": [_verdict_payload(record) for record in higher],
        "lower": [_verdict_payload(record) for record in lower],
    }


def _verdict_payload(
    record: _TitleRecord, *, ranked_position: int | None = None
) -> dict:
    return {
        "title": record.title,
        "mal_id": record.mal_id,
        "cover_url": record.cover_url,
        "your_score": record.user_score,
        "community_score": record.community_score,
        "delta": record.delta,
        "ranked_position": ranked_position,
        "year": record.year,
    }


def _genre_payload(records: tuple[_TitleRecord, ...]) -> dict:
    groups: dict[str, list[_TitleRecord]] = defaultdict(list)
    for record in records:
        for genre in dict.fromkeys(record.genres):
            groups[genre].append(record)
    readings = _group_readings(groups, total=len(records), include_titles=True)
    return {
        "readings": readings[:VISIBLE_GROUP_LIMIT],
        "best_match": _best_group(readings),
        "weakness": _weak_group(readings),
        "divisive": _divisive_group(readings),
    }


def _studio_payload(records: tuple[_TitleRecord, ...]) -> dict:
    groups: dict[str, list[_TitleRecord]] = defaultdict(list)
    for record in records:
        for studio in dict.fromkeys(record.studios):
            groups[studio].append(record)
    # CHANGE [EVIDENCE]: studios carry their titles too. "Your nemesis studio
    # is Tezuka Productions" is not a fact a reader can check - most people
    # cannot name a single thing that studio made, so the card reads as the
    # application asserting something about them rather than showing them
    # something about themselves. The titles are what turn it back into
    # evidence, and they were already in hand here.
    readings = _group_readings(groups, total=len(records), include_titles=True)
    visible = readings[:VISIBLE_GROUP_LIMIT]
    return {
        "readings": visible,
        "most_watched": visible[0] if visible else None,
        "most_trusted": _best_group(readings),
        "nemesis": _weak_group(readings),
    }


def _group_readings(
    groups: dict[str, list[_TitleRecord]],
    *,
    total: int,
    include_titles: bool,
) -> list[dict]:
    readings = []
    for name, members in groups.items():
        scores = [record.user_score for record in members if record.user_score is not None]
        reading = {
            "name": name,
            "watched": len(members),
            "share": len(members) / total if total else 0.0,
            "average": _mean(scores),
            "spread": _standard_deviation(scores),
        }
        if include_titles:
            ordered = sorted(
                members,
                key=lambda record: (
                    record.user_score is not None,
                    record.user_score or 0.0,
                    record.title.casefold(),
                ),
                reverse=True,
            )[:VISIBLE_TITLE_LIMIT]
            reading["titles"] = [
                {"title": record.title, "your_score": record.user_score}
                for record in ordered
            ]
            # The other end of the same list. A divisive genre is only
            # divisive because of its extremes, so showing the top alone
            # states the claim and hides the half that proves it.
            scored = [
                record for record in members if record.user_score is not None
            ]
            lowest = sorted(
                scored,
                key=lambda record: (record.user_score, record.title.casefold()),
            )[:VISIBLE_TITLE_LIMIT]
            reading["lowest"] = [
                {"title": record.title, "your_score": record.user_score}
                for record in lowest
            ]
        readings.append(reading)
    readings.sort(key=lambda item: (-item["watched"], item["name"].casefold()))
    return readings


def _eligible_groups(readings: list[dict]) -> list[dict]:
    return [
        reading
        for reading in readings
        if reading["watched"] >= MINIMUM_GROUP_SIZE
        and reading.get("average") is not None
    ]


def _best_group(readings: list[dict]) -> dict | None:
    eligible = _eligible_groups(readings)
    return max(
        eligible,
        key=lambda item: (item["average"], item["watched"]),
        default=None,
    )


def _weak_group(readings: list[dict]) -> dict | None:
    eligible = _eligible_groups(readings)
    if not eligible:
        return None
    watched_floor = sorted(item["watched"] for item in eligible)[len(eligible) // 2]
    frequent = [item for item in eligible if item["watched"] >= watched_floor]
    return min(frequent, key=lambda item: (item["average"], -item["watched"]))


def _divisive_group(readings: list[dict]) -> dict | None:
    eligible = [
        reading
        for reading in _eligible_groups(readings)
        if reading.get("spread") is not None
    ]
    if not eligible:
        return None
    result = dict(max(eligible, key=lambda item: item["spread"]))
    result["detail"] = "WIDE SCORE RANGE"
    return result


def _era_payload(records: tuple[_TitleRecord, ...]) -> dict:
    era_groups: dict[int, list[_TitleRecord]] = defaultdict(list)
    season_groups: dict[str, list[_TitleRecord]] = defaultdict(list)
    for record in records:
        if record.year is not None:
            era_groups[(record.year // 5) * 5].append(record)
        season = _season_from_date(record.start_date)
        if season:
            season_groups[season].append(record)

    buckets = []
    for start, members in sorted(era_groups.items()):
        scores = [record.user_score for record in members if record.user_score is not None]
        buckets.append(
            {
                "label": f"{start}-{start + 4}",
                "watched": len(members),
                "average": _mean(scores),
            }
        )
    golden_candidates = [
        bucket
        for bucket in buckets
        if bucket["watched"] >= MINIMUM_GROUP_SIZE
        and bucket["average"] is not None
    ]
    golden = max(
        golden_candidates,
        key=lambda item: (item["average"], item["watched"]),
        default=None,
    )

    seasons = []
    for name in ("WINTER", "SPRING", "SUMMER", "FALL"):
        members = season_groups.get(name, [])
        scores = [record.user_score for record in members if record.user_score is not None]
        if members:
            seasons.append(
                {"name": name, "watched": len(members), "average": _mean(scores)}
            )
    rated_seasons = [season for season in seasons if season["average"] is not None]
    season_of_choice = (
        max(rated_seasons, key=lambda item: (item["average"], item["watched"]))[
            "name"
        ]
        if rated_seasons
        else ""
    )
    return {
        "buckets": buckets,
        "golden": golden,
        "seasons": seasons,
        "season_of_choice": season_of_choice,
    }


def _season_from_date(value: str) -> str:
    parts = value.split("-", 2)
    if len(parts) < 2 or not parts[1].isdigit():
        return ""
    month = int(parts[1])
    if month in (1, 2, 3):
        return "WINTER"
    if month in (4, 5, 6):
        return "SPRING"
    if month in (7, 8, 9):
        return "SUMMER"
    if month in (10, 11, 12):
        return "FALL"
    return ""


def _mean(values) -> float | None:
    cleaned = [float(value) for value in values if value is not None]
    return sum(cleaned) / len(cleaned) if cleaned else None


def _standard_deviation(values) -> float | None:
    cleaned = [float(value) for value in values if value is not None]
    if len(cleaned) < 2:
        return None
    mean = sum(cleaned) / len(cleaned)
    return math.sqrt(sum((value - mean) ** 2 for value in cleaned) / len(cleaned))


def _clean_text(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value).strip()


def _optional_float(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _optional_int(value) -> int | None:
    number = _optional_float(value)
    return int(number) if number is not None else None


def _positive_int(value) -> int | None:
    number = _optional_int(value)
    return number if number is not None and number > 0 else None
