"""Pydantic response and request models: the API's actual OpenAPI contract.

Before this file, every route returned ``dict[str, Any]``. FastAPI still
served working JSON, but its generated ``/openapi.json`` described every
response as an empty, untyped object - there was nothing for a type generator
to read. These models exist so that document is complete, which is what lets
``frontend/src/api/generated/schema.d.ts`` be produced rather than typed by
hand a second time.

Each model's fields are a direct restatement of a presentation dataclass or a
service's return shape - see ``serialization.py`` for the functions that
actually build these payloads from ``AniRec.presentation`` and
``AniRec.services`` values. Nothing here computes anything; it only declares
what is already being sent, so that FastAPI can describe it.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    """Every response and request model shares strict, explicit field names."""

    model_config = ConfigDict(extra="forbid")


# -- errors -----------------------------------------------------------------


class ApiError(ApiModel):
    """``presentable_error``, restated. The desktop error dialog reads the same model."""

    code: str
    title: str
    description: str
    solution: str
    retryable: bool = False


class ErrorEnvelope(ApiModel):
    error: ApiError


# -- discover -----------------------------------------------------------------


class Contribution(ApiModel):
    label: str
    value: float


class RecommendationViewModelResponse(ApiModel):
    """``AniRec.presentation.RecommendationViewModel``, as JSON.

    Field-for-field with the dataclass; see ``serialization.view_model_to_dict``.
    The ``_text`` fields are pre-formatted for a QLabel and are carried rather
    than dropped so this stage changes no behaviour - a browser client should
    generally prefer the numeric field beside each one.
    """

    mal_id: int | None
    rank: int | None
    display_title: str
    secondary_title: str | None
    alternative_titles: tuple[str, ...]
    personal_match: float
    personal_match_text: str
    personal_match_available: bool
    mal_score: float | None
    mal_score_text: str
    genres: tuple[str, ...]
    genres_text: str
    studios: tuple[str, ...]
    studios_text: str
    episodes: int | None
    episodes_text: str
    status: str
    year: int | None
    year_text: str
    start_date: str
    end_date: str
    aired_text: str | None
    synopsis: str
    reason: str
    contributing_genres: tuple[str, ...]
    genre_contributions: tuple[Contribution, ...]
    cover_url: str | None
    large_cover_url: str | None
    mal_url: str | None
    media_type: str | None


class Catalogue(ApiModel):
    genres: tuple[str, ...]
    studios: tuple[str, ...]
    years: tuple[int, ...]
    statuses: tuple[str, ...]


class LocalState(ApiModel):
    hidden_mal_ids: tuple[int, ...]
    watch_later_mal_ids: tuple[int, ...]
    liked_mal_ids: tuple[int, ...]
    disliked_mal_ids: tuple[int, ...]
    show_hidden: bool


class ProfileSummary(ApiModel):
    profile_id: str
    username: str


FeedSource = Literal["profile", "sample", "empty"]


class FeedResponse(ApiModel):
    source: FeedSource
    ephemeral: bool
    profile: ProfileSummary | None
    state_profile_id: str | None
    recommendations: tuple[RecommendationViewModelResponse, ...]
    hidden_count: int
    catalogue: Catalogue
    state: LocalState
    user_stats: dict[str, Any]


FeedbackAction = Literal["hidden", "watch_later", "sentiment"]
Sentiment = Literal["liked", "disliked"]


class FeedbackRequest(ApiModel):
    profile_id: str
    mal_id: int
    action: FeedbackAction
    value: bool = True
    sentiment: Sentiment | None = None
    genres: tuple[str, ...] = ()
    title: str = ""


class FeedbackResponse(ApiModel):
    state: LocalState


# -- system -------------------------------------------------------------------


class OperationSnapshotResponse(ApiModel):
    """Mirrors ``operations.OperationRecord.snapshot()``.

    Named distinctly from ``operations.OperationState`` (the enum the
    ``state`` field below draws its literal values from) so the two are never
    confused where both are imported.
    """

    id: str
    kind: str
    profile_id: str
    state: Literal["running", "succeeded", "failed", "cancelled"]
    event_count: int


class SystemStateResponse(ApiModel):
    profile: ProfileSummary | None
    needs_setup: bool
    mal_client_id_present: bool
    active_operations: tuple[OperationSnapshotResponse, ...]


class HealthResponse(ApiModel):
    status: Literal["ok"]
    version: str


# -- operations -----------------------------------------------------------------


class OperationListResponse(ApiModel):
    operations: tuple[OperationSnapshotResponse, ...]


class OperationAcceptedResponse(OperationSnapshotResponse):
    """What starting an operation returns: a snapshot, at HTTP 202."""


class OperationStartRequest(ApiModel):
    """Every field any operation kind might read; each kind uses a subset.

    A single permissive model rather than one per kind, because the kind
    itself is a path parameter chosen at request time, not something Pydantic
    can discriminate on ahead of it.
    """

    profile_id: str | None = None
    username: str | None = None
    count: int | None = None
    target: str | None = None


class CancelResponse(ApiModel):
    cancelled: bool
    id: str


# -- progress events (SSE) -----------------------------------------------------
#
# Not part of the OpenAPI document: FastAPI does not describe the payloads of
# individual server-sent-event frames, only the streaming endpoint's overall
# response type. This model exists so the *shape* is declared once in Python
# and referenced from the streaming route's docstring - frontend/src/api/types.ts
# still hand-declares the equivalent TypeScript type for these three frames,
# and says why beside it.


class ProgressEvent(ApiModel):
    stage_id: str
    message: str
    current: int
    total: int
    cancellable: bool
