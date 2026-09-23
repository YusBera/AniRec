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

from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID


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


class ExplanationEvidence(ApiModel):
    """A title from the reader's own list that backs one part of a "why".

    For counterfactual removal, ``value`` is how much the pick's model score
    drops without this one title (positive: the title raised the pick) and
    ``rank_without`` the pick's rank without it, among the same candidates;
    ``list_status`` is the reader's MAL list status. All three are null for a
    heuristic taste part, whose evidence is the reader's rated titles.
    """

    mal_id: int | None
    title: str
    user_score: float | None
    list_status: str | None
    value: float | None
    rank_without: int | None


class TasteDetail(ApiModel):
    """How the reader's ratings shaped one taste part.

    ``affinity`` is the value the ranking used: the shrunk mean of the reader's
    centred ratings of titles carrying the feature, then moved by any explicit
    feedback (see the segment's ``feedback_adjustment``). ``rarity`` is its
    catalogue IDF. ``rated_count`` and ``mean_user_score`` describe the
    reader's rated titles with the feature; both are null when the rated list
    was unavailable.
    """

    affinity: float
    rarity: float
    rated_count: int | None
    mean_user_score: float | None
    overall_mean_user_score: float | None


class CommunityDetail(ApiModel):
    mean_score: float | None
    scoring_users: float | None


class ExplanationSegment(ApiModel):
    """One part of a recommendation's score, in the explanation's ``unit``.

    ``taste`` parts come from the reader's own ratings. ``community`` and
    ``similar-viewers`` parts are not about the reader's taste.
    ``history-group`` parts are the reader's history titles in one genre (the
    genre of *their* titles; the sequence model never sees genres), and
    ``history-other`` their titles without genres. For these, ``value`` is the
    model-score drop when all ``member_count`` titles are removed and
    ``rank_without`` the pick's rank then; removal effects overlap, so they do
    not sum to the score.
    ``signal_available`` false means a neutral stand-in filled a missing signal.
    """

    kind: Literal[
        "taste", "community", "similar-viewers", "history-group", "history-other"
    ]
    facet: Literal["genre", "studio", "source", "media-type", "era"] | None
    label: str
    value: float
    rank_without: int | None
    member_count: int | None
    taste: TasteDetail | None
    feedback_adjustment: float | None
    signal_available: bool
    community: CommunityDetail | None
    evidence: tuple[ExplanationEvidence, ...]


class Explanation(ApiModel):
    """Why the ranking engine placed a title where it did.

    * ``exact-additive`` (heuristic): segment values sum exactly to ``total``,
      the ranking score (``baseline`` 0, ``full_score`` = ``total``). Render
      as an additive bar.
    * ``counterfactual-removal`` (sequence model): ``full_score`` and
      ``full_rank`` are the pick's model score and rank with the reader's full
      history among ``ranked_candidate_count`` candidates. Each segment and
      ``influences`` entry says how far the pick falls without those history
      titles. Effects overlap, so ``total`` and ``baseline`` are null: render
      relative impacts, never shares of a whole.
    * ``unavailable``: the engine cannot explain itself;
      ``unavailable_reason`` says why, and nothing is borrowed.
    """

    schema_version: int
    method: Literal["exact-additive", "counterfactual-removal", "unavailable"]
    unit: Literal["ranking-score", "model-score"] | None
    total: float | None
    baseline: float | None
    full_score: float | None
    full_rank: int | None
    ranked_candidate_count: int | None
    history_window: int | None = Field(
        default=None,
        description=(
            "counterfactual-removal only: how many of the reader's most recent "
            "list entries the model reads. Segments and influences cover only "
            "these titles, never the whole list."
        ),
    )
    segments: tuple[ExplanationSegment, ...]
    influences: tuple[ExplanationEvidence, ...]
    unavailable_reason: str | None


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
    personal_match: float = Field(
        description=(
            "Retired (D-008). Always 0.0 and personal_match_available is always "
            "false; use fit_rank. Kept only so existing clients still parse."
        )
    )
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
    genre_contributions: tuple[Contribution, ...] = Field(
        description=(
            "Retired with personal_match (it was in its percentage points). "
            "Always empty; the breakdown is why.segments."
        )
    )
    cover_url: str | None
    large_cover_url: str | None
    mal_url: str | None
    media_type: str | None
    fit_rank: int | None = Field(
        default=None,
        description=(
            "Position in the ranking engine's ordering of every eligible "
            "candidate, before feed selection. Replaces personal_match."
        ),
    )
    fit_pool_size: int | None = Field(
        default=None, description="How many eligible candidates that ordering held."
    )
    fit_top_percent: float | None = Field(
        default=None, description="100 * fit_rank / fit_pool_size."
    )
    why: Explanation | None = Field(
        default=None,
        description="Why the ranking engine placed this title where it did.",
    )
    ranking_id: str | None = Field(
        default=None,
        description=(
            "Identity of the ranking fit_rank comes from. Compare fit_rank only "
            "between rows with the same ranking_id."
        ),
    )
    selection_policy: str | None = Field(
        default=None,
        description="Version of the shared selection policy that chose this row.",
    )
    adventurousness: int | None = Field(
        default=None,
        description="Adventurousness (1-10) in force when this row was selected.",
    )


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
    activity_feed_id: str = ""


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
    feed_id: str | None = Field(
        default=None,
        pattern="^[a-f0-9]{64}$",
        description=(
            "The activity_feed_id of the feed the vote was cast on. A vote is "
            "attributed to what was shown only when this matches the served feed."
        ),
    )


class ActivityStatus(ApiModel):
    enabled: bool
    local_only: bool = True
    retention_days: int = 90


class ActivitySetting(ApiModel):
    enabled: bool


class ActivityEvent(ApiModel):
    profile_id: str = Field(min_length=1, max_length=200)
    event_id: UUID
    request_id: UUID
    feed_id: str = Field(pattern="^[a-f0-9]{64}$")
    action: Literal["impression", "detail_open", "external_open", "watch_later_add", "watch_later_remove", "dismiss", "restore"]
    mal_id: int = Field(gt=0)
    position: int = Field(gt=0, le=100000)
    model_rank: int | None = Field(default=None, gt=0)
    surface: Literal["web_cards"]


class ActivityReceipt(ApiModel):
    recorded: bool


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
