"""Widget-independent presentation model for anime recommendations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from urllib.parse import urlparse

from ..models import Recommendation


NOT_AVAILABLE = "Not available"
NOT_RATED = "Not rated"
NO_GENRES = "Genres not available"
NO_SYNOPSIS = "No synopsis is available."
NO_REASON = "No recommendation explanation is available."


@dataclass(frozen=True)
class RecommendationViewModel:
    mal_id: int | None
    rank: int | None
    display_title: str
    secondary_title: str | None
    alternative_titles: tuple[str, ...]
    personal_match: float
    personal_match_text: str
    mal_score: float | None
    mal_score_text: str
    genres: tuple[str, ...]
    genres_text: str
    episodes: int | None
    episodes_text: str
    status: str
    year: int | None
    year_text: str
    start_date: str
    end_date: str
    synopsis: str
    reason: str
    contributing_genres: tuple[str, ...]
    cover_url: str | None
    large_cover_url: str | None
    mal_url: str | None
    personal_match_available: bool = True
    genre_contributions: tuple[tuple[str, float], ...] = ()

    @classmethod
    def from_recommendation(cls, recommendation: Recommendation) -> "RecommendationViewModel":
        anime = recommendation.anime
        raw_personal_match = _finite_number(recommendation.match_score)
        personal_match = raw_personal_match or 0.0
        mal_score = _finite_number(anime.mean_score)
        genres = tuple(text for item in anime.genres if (text := _clean_text(item)))
        alternatives = tuple(
            text for item in anime.alternative_titles if (text := _clean_text(item))
        )
        raw_status = _clean_text(anime.status)
        status = raw_status.replace("_", " ").title() if raw_status else NOT_AVAILABLE
        synopsis = _clean_text(anime.synopsis) or NO_SYNOPSIS
        reason = _clean_text(recommendation.reason) or NO_REASON
        contributing = tuple(
            text
            for item in recommendation.contributing_genres
            if (text := _clean_text(item))
        )

        return cls(
            mal_id=anime.mal_id,
            rank=recommendation.rank,
            display_title=anime.display_title,
            secondary_title=anime.secondary_title,
            alternative_titles=alternatives,
            personal_match=personal_match,
            personal_match_text=f"Personal match: {personal_match:.1f}%",
            mal_score=mal_score,
            mal_score_text=(
                f"MAL score: {mal_score:.2f} / 10" if mal_score is not None else f"MAL score: {NOT_RATED}"
            ),
            genres=genres,
            genres_text=" · ".join(genres) if genres else NO_GENRES,
            episodes=anime.episodes,
            episodes_text=(
                f"{anime.episodes} episode" if anime.episodes == 1 else f"{anime.episodes} episodes"
            )
            if anime.episodes is not None
            else "Episodes not available",
            status=status,
            year=anime.year,
            year_text=str(anime.year) if anime.year is not None else "Year not available",
            start_date=_clean_text(anime.start_date) or NOT_AVAILABLE,
            end_date=_clean_text(anime.end_date) or NOT_AVAILABLE,
            synopsis=synopsis,
            reason=reason,
            contributing_genres=contributing,
            cover_url=_safe_https_url(anime.cover_url),
            large_cover_url=_safe_https_url(anime.large_cover_url),
            mal_url=_safe_mal_url(anime.mal_url, anime.mal_id),
            personal_match_available=raw_personal_match is not None,
            genre_contributions=tuple(recommendation.genre_contributions),
        )


def recommendation_view_models(
    recommendations: tuple[Recommendation, ...] | list[Recommendation],
) -> tuple[RecommendationViewModel, ...]:
    return tuple(RecommendationViewModel.from_recommendation(item) for item in recommendations)


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.casefold() in {"none", "nan", "null"}:
        return None
    return text


def _finite_number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _safe_https_url(value: object) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    parsed = urlparse(text)
    if parsed.scheme.casefold() != "https" or not parsed.hostname or parsed.username or parsed.password:
        return None
    return text


def _safe_mal_url(value: object, mal_id: int | None) -> str | None:
    text = _safe_https_url(value)
    if text is None:
        return None
    parsed = urlparse(text)
    if parsed.hostname.casefold() not in {"myanimelist.net", "www.myanimelist.net"}:
        return None
    if mal_id is not None:
        segments = [segment for segment in parsed.path.split("/") if segment]
        if len(segments) < 2 or segments[0].casefold() != "anime" or segments[1] != str(mal_id):
            return None
    return text
