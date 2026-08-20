"""A bundled sample library so AniRec can be explored without an account.

Registering a MyAnimeList API application before seeing anything at all is a
hard wall for someone deciding whether the app is worth their time. This loads
a small, honest set of well known titles through the same models the real
pipeline produces, so every surface behaves normally with nothing connected.

The sample is read only. It never touches a profile directory and is never
written back, so it cannot be mistaken for real data or overwrite any.
"""

from __future__ import annotations

import json
from pathlib import Path

try:
    from ..infrastructure.paths import resource_path
    from ..models import Anime, GenreStat, PipelineResult, Recommendation
except ImportError:  # Compatibility with the S01 top-level test import path.
    from infrastructure.paths import resource_path
    from models import Anime, GenreStat, PipelineResult, Recommendation


SAMPLE_PROFILE_ID = "__sample__"
SAMPLE_USERNAME = "Sample library"
SAMPLE_RESOURCE = "gui/resources/sample/sample_library.json"


class SampleDataService:
    """Load the bundled demonstration library."""

    def __init__(self, *, resource_root: str | Path | None = None) -> None:
        self._resource_root = resource_root

    @property
    def profile_id(self) -> str:
        return SAMPLE_PROFILE_ID

    def is_sample_profile(self, profile_id: object) -> bool:
        return str(profile_id) == SAMPLE_PROFILE_ID

    def load(self) -> PipelineResult | None:
        """Return the sample result, or None when it is unavailable.

        Demonstration data is a convenience. If it cannot be read the caller
        continues without it rather than failing to start.
        """
        try:
            path = resource_path(SAMPLE_RESOURCE, base_override=self._resource_root)
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        if not isinstance(payload, dict):
            return None

        recommendations = []
        for rank, entry in enumerate(payload.get("recommendations") or (), start=1):
            if not isinstance(entry, dict):
                continue
            try:
                anime = Anime(
                    title=entry["title"],
                    mal_id=entry.get("mal_id"),
                    english_title=entry.get("english_title"),
                    genres=tuple(entry.get("genres") or ()),
                    mean_score=entry.get("mean_score"),
                    episodes=entry.get("episodes"),
                    year=entry.get("year"),
                    status=entry.get("status"),
                    synopsis=entry.get("synopsis"),
                    studios=tuple(entry.get("studios") or ()),
                    source=entry.get("source"),
                    media_type=entry.get("media_type"),
                    scoring_users=entry.get("scoring_users"),
                    mal_url=(
                        f"https://myanimelist.net/anime/{entry['mal_id']}"
                        if entry.get("mal_id")
                        else None
                    ),
                )
            except (KeyError, TypeError, ValueError):
                continue
            recommendations.append(
                Recommendation(
                    anime=anime,
                    match_score=float(entry.get("match_score") or 0.0),
                    reason=entry.get("reason"),
                    genre_contributions=tuple(
                        (str(name), float(value))
                        for name, value in (entry.get("contributions") or ())
                    ),
                    rank=rank,
                )
            )

        genre_stats = []
        for entry in payload.get("genres") or ():
            if not isinstance(entry, dict):
                continue
            try:
                genre_stats.append(
                    GenreStat(
                        genre=entry["genre"],
                        importance_score=float(entry.get("importance_score") or 0.0),
                        completed_count=int(entry.get("completed_count") or 0),
                        average_user_score=entry.get("average_user_score"),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue

        if not recommendations:
            return None

        return PipelineResult(
            recommendations=tuple(recommendations),
            genre_stats=tuple(genre_stats),
            user_stats={
                "username": SAMPLE_USERNAME,
                "completed_count": int(payload.get("completed_count") or 0),
                "rated_count": int(payload.get("rated_count") or 0),
                "recommendation_count": len(recommendations),
            },
        )
