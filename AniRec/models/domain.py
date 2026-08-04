"""Immutable, JSON-friendly models for the AniRec application boundary."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping


MODEL_SCHEMA_VERSION = 1
SETTINGS_SCHEMA_VERSION = 1
TOKEN_SCHEMA_VERSION = 1
APP_THEME_VALUES = {"light", "dark", "system"}
RECOMMENDATION_SORT_VALUES = {"personal-match", "mal-score", "year", "alphabetical"}
UNKNOWN_TITLE = "Unknown title"
NOT_AVAILABLE = "Not available"
NOT_RATED = "Not rated"


def _require_schema(data: Mapping[str, Any]) -> None:
    version = data.get("schema_version")
    if version != MODEL_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported model schema version: {version!r}; expected {MODEL_SCHEMA_VERSION}."
        )


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number


def _text_tuple(values: object) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        values = [values]
    return tuple(text for item in values if (text := _optional_text(item)) is not None)


@dataclass(frozen=True)
class Anime:
    title: str
    mal_id: int | None = None
    english_title: str | None = None
    alternative_titles: tuple[str, ...] = ()
    genres: tuple[str, ...] = ()
    mean_score: float | None = None
    cover_url: str | None = None
    large_cover_url: str | None = None
    episodes: int | None = None
    status: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    year: int | None = None
    synopsis: str | None = None
    mal_url: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", _optional_text(self.title) or UNKNOWN_TITLE)
        for name in (
            "english_title",
            "cover_url",
            "large_cover_url",
            "status",
            "start_date",
            "end_date",
            "synopsis",
            "mal_url",
        ):
            object.__setattr__(self, name, _optional_text(getattr(self, name)))
        object.__setattr__(self, "alternative_titles", _text_tuple(self.alternative_titles))
        object.__setattr__(self, "genres", _text_tuple(self.genres))
        object.__setattr__(self, "mean_score", _optional_float(self.mean_score))

        for name in ("mal_id", "episodes", "year"):
            value = getattr(self, name)
            if value is not None:
                value = int(value)
                if value <= 0:
                    raise ValueError(f"{name} must be a positive integer when provided.")
                object.__setattr__(self, name, value)

    @property
    def display_title(self) -> str:
        return self.english_title or self.title

    @property
    def secondary_title(self) -> str | None:
        if self.english_title and self.english_title.casefold() != self.title.casefold():
            return self.title
        return None

    @property
    def display_score(self) -> str:
        return NOT_RATED if self.mean_score is None else f"{self.mean_score:.2f}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": MODEL_SCHEMA_VERSION,
            "title": self.title,
            "mal_id": self.mal_id,
            "english_title": self.english_title,
            "alternative_titles": list(self.alternative_titles),
            "genres": list(self.genres),
            "mean_score": self.mean_score,
            "cover_url": self.cover_url,
            "large_cover_url": self.large_cover_url,
            "episodes": self.episodes,
            "status": self.status,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "year": self.year,
            "synopsis": self.synopsis,
            "mal_url": self.mal_url,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Anime":
        _require_schema(data)
        values = dict(data)
        values.pop("schema_version", None)
        return cls(**values)


@dataclass(frozen=True)
class Recommendation:
    anime: Anime
    match_score: float = 0.0
    raw_score: float = 0.0
    contributing_genres: tuple[str, ...] = ()
    genre_contributions: tuple[tuple[str, float], ...] = ()
    reason: str | None = None
    rank: int | None = None

    def __post_init__(self) -> None:
        score = _optional_float(self.match_score)
        object.__setattr__(self, "match_score", score if score is not None else 0.0)
        raw_score = _optional_float(self.raw_score)
        object.__setattr__(self, "raw_score", raw_score if raw_score is not None else 0.0)
        contributions = []
        for item in self.genre_contributions:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                continue
            genre = _optional_text(item[0])
            contribution = _optional_float(item[1])
            if genre is not None and contribution is not None:
                contributions.append((genre, contribution))
        object.__setattr__(self, "genre_contributions", tuple(contributions))
        contributing_genres = _text_tuple(self.contributing_genres)
        if not contributing_genres and contributions:
            contributing_genres = tuple(genre for genre, _score in contributions)
        object.__setattr__(self, "contributing_genres", contributing_genres)
        object.__setattr__(self, "reason", _optional_text(self.reason))
        if self.rank is not None and int(self.rank) <= 0:
            raise ValueError("rank must be positive when provided.")
        if self.rank is not None:
            object.__setattr__(self, "rank", int(self.rank))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": MODEL_SCHEMA_VERSION,
            "anime": self.anime.to_dict(),
            "match_score": self.match_score,
            "raw_score": self.raw_score,
            "contributing_genres": list(self.contributing_genres),
            "genre_contributions": [
                {"genre": genre, "score": score}
                for genre, score in self.genre_contributions
            ],
            "reason": self.reason,
            "rank": self.rank,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Recommendation":
        _require_schema(data)
        contribution_values = []
        for item in data.get("genre_contributions") or ():
            if isinstance(item, Mapping):
                contribution_values.append((item.get("genre"), item.get("score")))
            else:
                contribution_values.append(item)
        return cls(
            anime=Anime.from_dict(data["anime"]),
            match_score=data.get("match_score", 0.0),
            raw_score=data.get("raw_score", 0.0),
            contributing_genres=tuple(data.get("contributing_genres") or ()),
            genre_contributions=tuple(contribution_values),
            reason=data.get("reason"),
            rank=data.get("rank"),
        )


@dataclass(frozen=True)
class GenreStat:
    genre: str
    importance_score: float = 0.0
    completed_count: int = 0
    average_user_score: float | None = None
    missing_score_count: int = 0
    example_titles: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "genre", _optional_text(self.genre) or NOT_AVAILABLE)
        object.__setattr__(self, "importance_score", _optional_float(self.importance_score) or 0.0)
        object.__setattr__(self, "average_user_score", _optional_float(self.average_user_score))
        object.__setattr__(self, "example_titles", _text_tuple(self.example_titles))
        if self.completed_count < 0 or self.missing_score_count < 0:
            raise ValueError("Genre counts cannot be negative.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": MODEL_SCHEMA_VERSION,
            "genre": self.genre,
            "importance_score": self.importance_score,
            "completed_count": self.completed_count,
            "average_user_score": self.average_user_score,
            "missing_score_count": self.missing_score_count,
            "example_titles": list(self.example_titles),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GenreStat":
        _require_schema(data)
        values = dict(data)
        values.pop("schema_version", None)
        return cls(**values)


@dataclass(frozen=True)
class UserProfile:
    profile_id: str
    username: str
    mal_user_id: int | None = None
    last_sync: str | None = None
    output_dir: str | None = None

    def __post_init__(self) -> None:
        if not _optional_text(self.profile_id):
            raise ValueError("profile_id is required.")
        if not _optional_text(self.username):
            raise ValueError("username is required.")
        object.__setattr__(self, "profile_id", self.profile_id.strip())
        object.__setattr__(self, "username", self.username.strip())
        if self.mal_user_id is not None:
            mal_user_id = int(self.mal_user_id)
            if mal_user_id <= 0:
                raise ValueError("mal_user_id must be positive when provided.")
            object.__setattr__(self, "mal_user_id", mal_user_id)
        object.__setattr__(self, "last_sync", _optional_text(self.last_sync))
        object.__setattr__(self, "output_dir", _optional_text(self.output_dir))

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": MODEL_SCHEMA_VERSION, **self.__dict__}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "UserProfile":
        _require_schema(data)
        values = dict(data)
        values.pop("schema_version", None)
        return cls(**values)


@dataclass(frozen=True)
class PipelineSettings:
    top_anime_limit: int = 500
    recommendation_count: int = 10
    candidate_pool_size: int = 150
    randomness_factor: int = 5
    minimum_mean_score: float | None = None
    seed: int | None = None

    def __post_init__(self) -> None:
        if self.top_anime_limit <= 0:
            raise ValueError("top_anime_limit must be positive.")
        if self.recommendation_count <= 0:
            raise ValueError("recommendation_count must be positive.")
        if self.candidate_pool_size < self.recommendation_count:
            raise ValueError("candidate_pool_size cannot be smaller than recommendation_count.")
        if self.top_anime_limit < self.candidate_pool_size:
            raise ValueError("top_anime_limit cannot be smaller than candidate_pool_size.")
        if not 1 <= self.randomness_factor <= 10:
            raise ValueError("randomness_factor must be between 1 and 10.")
        object.__setattr__(self, "minimum_mean_score", _optional_float(self.minimum_mean_score))
        if self.minimum_mean_score is not None and not 0 <= self.minimum_mean_score <= 10:
            raise ValueError("minimum_mean_score must be between 0 and 10.")

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": MODEL_SCHEMA_VERSION, **self.__dict__}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PipelineSettings":
        _require_schema(data)
        values = dict(data)
        values.pop("schema_version", None)
        return cls(**values)


@dataclass(frozen=True)
class AppSettings:
    client_id: str | None = None
    redirect_uri: str = "http://localhost:8080/callback"
    client_secret: str | None = field(default=None, repr=False)
    active_profile_id: str | None = None
    debug_logging: bool = False
    pipeline: PipelineSettings = field(default_factory=PipelineSettings)
    default_recommendation_sort: str = "personal-match"
    include_hidden_recommendations: bool = False
    theme: str = "system"
    font_scale: float = 1.0
    show_covers: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "client_id", _optional_text(self.client_id))
        object.__setattr__(self, "redirect_uri", _optional_text(self.redirect_uri) or "")
        object.__setattr__(self, "client_secret", _optional_text(self.client_secret))
        object.__setattr__(self, "active_profile_id", _optional_text(self.active_profile_id))
        object.__setattr__(
            self,
            "default_recommendation_sort",
            (_optional_text(self.default_recommendation_sort) or "personal-match").casefold(),
        )
        object.__setattr__(
            self, "include_hidden_recommendations", bool(self.include_hidden_recommendations)
        )
        object.__setattr__(self, "theme", (_optional_text(self.theme) or "system").casefold())
        object.__setattr__(self, "font_scale", float(self.font_scale))
        object.__setattr__(self, "show_covers", bool(self.show_covers))

    @property
    def masked_client_secret(self) -> str:
        return "••••••" if self.client_secret else ""

    def to_storage_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SETTINGS_SCHEMA_VERSION,
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "client_secret": self.client_secret,
            "active_profile_id": self.active_profile_id,
            "debug_logging": self.debug_logging,
            "pipeline": self.pipeline.to_dict(),
            "default_recommendation_sort": self.default_recommendation_sort,
            "include_hidden_recommendations": self.include_hidden_recommendations,
            "theme": self.theme,
            "font_scale": self.font_scale,
            "show_covers": self.show_covers,
        }

    def to_diagnostic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SETTINGS_SCHEMA_VERSION,
            "client_id_configured": bool(self.client_id),
            "redirect_uri": self.redirect_uri,
            "client_secret_configured": bool(self.client_secret),
            "active_profile_id": self.active_profile_id,
            "debug_logging": self.debug_logging,
            "pipeline": self.pipeline.to_dict(),
            "default_recommendation_sort": self.default_recommendation_sort,
            "include_hidden_recommendations": self.include_hidden_recommendations,
            "theme": self.theme,
            "font_scale": self.font_scale,
            "show_covers": self.show_covers,
        }

    @classmethod
    def from_storage_dict(cls, data: Mapping[str, Any]) -> "AppSettings":
        if data.get("schema_version") != SETTINGS_SCHEMA_VERSION:
            raise ValueError("Unsupported settings schema version.")
        pipeline_data = data.get("pipeline")
        pipeline = (
            PipelineSettings.from_dict(pipeline_data)
            if isinstance(pipeline_data, Mapping)
            else PipelineSettings()
        )
        return cls(
            client_id=data.get("client_id"),
            redirect_uri=data.get("redirect_uri") or "",
            client_secret=data.get("client_secret"),
            active_profile_id=data.get("active_profile_id"),
            debug_logging=bool(data.get("debug_logging", False)),
            pipeline=pipeline,
            default_recommendation_sort=data.get("default_recommendation_sort") or "personal-match",
            include_hidden_recommendations=bool(
                data.get("include_hidden_recommendations", False)
            ),
            theme=data.get("theme") or "system",
            font_scale=data.get("font_scale", 1.0),
            show_covers=bool(data.get("show_covers", True)),
        )


@dataclass(frozen=True)
class TokenRecord:
    access_token: str = field(repr=False)
    refresh_token: str | None = field(default=None, repr=False)
    expires_at: int = 0
    token_type: str = "Bearer"
    scope: str | None = None

    def __post_init__(self) -> None:
        access_token = _optional_text(self.access_token)
        if not access_token:
            raise ValueError("access_token is required.")
        object.__setattr__(self, "access_token", access_token)
        object.__setattr__(self, "refresh_token", _optional_text(self.refresh_token))
        object.__setattr__(self, "token_type", _optional_text(self.token_type) or "Bearer")
        object.__setattr__(self, "scope", _optional_text(self.scope))
        object.__setattr__(self, "expires_at", max(int(self.expires_at), 0))

    def to_storage_dict(self) -> dict[str, Any]:
        return {
            "schema_version": TOKEN_SCHEMA_VERSION,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "token_type": self.token_type,
            "scope": self.scope,
        }

    @classmethod
    def from_storage_dict(cls, data: Mapping[str, Any]) -> "TokenRecord":
        if data.get("schema_version") != TOKEN_SCHEMA_VERSION:
            raise ValueError("Unsupported token schema version.")
        return cls(
            access_token=data.get("access_token"),
            refresh_token=data.get("refresh_token"),
            expires_at=data.get("expires_at", 0),
            token_type=data.get("token_type") or "Bearer",
            scope=data.get("scope"),
        )


@dataclass(frozen=True)
class PipelineProgress:
    stage_id: str
    message: str
    current: int = 0
    total: int = 0
    cancellable: bool = False

    def __post_init__(self) -> None:
        if self.current < 0 or self.total < 0:
            raise ValueError("Progress values cannot be negative.")
        if self.total and self.current > self.total:
            raise ValueError("Progress current cannot exceed total.")
        object.__setattr__(self, "stage_id", _optional_text(self.stage_id) or "unknown")
        object.__setattr__(self, "message", _optional_text(self.message) or "")

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": MODEL_SCHEMA_VERSION, **self.__dict__}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PipelineProgress":
        _require_schema(data)
        values = dict(data)
        values.pop("schema_version", None)
        return cls(**values)


@dataclass(frozen=True)
class PipelineResult:
    recommendations: tuple[Recommendation, ...] = ()
    genre_stats: tuple[GenreStat, ...] = ()
    user_stats: Mapping[str, int | float | str] = field(default_factory=dict)
    generated_files: tuple[str, ...] = ()
    started_at: str | None = None
    completed_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "recommendations", tuple(self.recommendations))
        object.__setattr__(self, "genre_stats", tuple(self.genre_stats))
        object.__setattr__(self, "user_stats", dict(self.user_stats))
        object.__setattr__(self, "generated_files", _text_tuple(self.generated_files))
        object.__setattr__(self, "started_at", _optional_text(self.started_at))
        object.__setattr__(self, "completed_at", _optional_text(self.completed_at))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": MODEL_SCHEMA_VERSION,
            "recommendations": [item.to_dict() for item in self.recommendations],
            "genre_stats": [item.to_dict() for item in self.genre_stats],
            "user_stats": dict(self.user_stats),
            "generated_files": list(self.generated_files),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PipelineResult":
        _require_schema(data)
        return cls(
            recommendations=tuple(
                Recommendation.from_dict(item) for item in data.get("recommendations", ())
            ),
            genre_stats=tuple(GenreStat.from_dict(item) for item in data.get("genre_stats", ())),
            user_stats=dict(data.get("user_stats") or {}),
            generated_files=tuple(data.get("generated_files") or ()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
        )
