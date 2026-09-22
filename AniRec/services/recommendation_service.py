"""In-memory recommendation calculations: eligibility, ranking and selection."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import date

import pandas as pd

try:
    from ..candidate_generation import filter_recommendation_candidates
    from ..genre_importance import calculate_genre_importance
    from ..handle_missing_scores import (
        calculate_genre_medians,
        handle_missing_scores_with_genre_medians,
    )
    from ..models import PipelineSettings
    from ..scoring.contracts import (
        RankingEngine,
        RankingEngineMetadata,
        RankingParameters,
        RankingRequest,
    )
    from ..scoring.engines import (
        FallbackRankingEngine,
        HeuristicRankingEngine,
        OnnxSequenceRankingEngine,
    )
    from ..scoring.eligibility import (
        EligibilityAudit,
        EligibilityContext,
        FinalEligibilityPolicy,
    )
    from ..scoring.explanation import (
        EXPLANATION_COLUMN,
        METHOD_EXACT_ADDITIVE,
        SCORE_PARTS_COLUMN,
        explain_additive,
        unavailable_explanation,
    )
    from ..scoring.selection import select_feed
    from ..scoring.serialization import profile_to_frame
    from ..scoring.taste import build_taste_profile
    from ..title_utils import normalize_title_key
except ImportError:  # Compatibility with the S01 top-level test import path.
    from candidate_generation import filter_recommendation_candidates
    from genre_importance import calculate_genre_importance
    from handle_missing_scores import (
        calculate_genre_medians,
        handle_missing_scores_with_genre_medians,
    )
    from models import PipelineSettings
    from scoring.contracts import (
        RankingEngine,
        RankingEngineMetadata,
        RankingParameters,
        RankingRequest,
    )
    from scoring.engines import (
        FallbackRankingEngine,
        HeuristicRankingEngine,
        OnnxSequenceRankingEngine,
    )
    from scoring.eligibility import (
        EligibilityAudit,
        EligibilityContext,
        FinalEligibilityPolicy,
    )
    from scoring.explanation import (
        EXPLANATION_COLUMN,
        METHOD_EXACT_ADDITIVE,
        SCORE_PARTS_COLUMN,
        explain_additive,
        unavailable_explanation,
    )
    from scoring.selection import select_feed
    from scoring.serialization import profile_to_frame
    from scoring.taste import build_taste_profile
    from title_utils import normalize_title_key


class RecommendationService:
    def __init__(
        self,
        *,
        random_int: Callable[[int, int], int] | None = None,
        ranker: RankingEngine | None = None,
        eligibility_policy: FinalEligibilityPolicy | None = None,
    ) -> None:
        # ``random_int`` is accepted for older callers only. Feed selection is
        # deterministic and never draws from a random source.
        del random_int
        self._ranker = ranker if ranker is not None else HeuristicRankingEngine()
        self._eligibility_policy = eligibility_policy or FinalEligibilityPolicy()
        self._last_ranking_metadata: RankingEngineMetadata | None = None
        self._last_eligibility_audit: EligibilityAudit | None = None

    @property
    def last_ranking_metadata(self) -> RankingEngineMetadata | None:
        """Provenance from the latest completed ranking operation."""
        return self._last_ranking_metadata

    @property
    def last_eligibility_audit(self) -> EligibilityAudit | None:
        """Aggregate policy provenance from the candidates actually scored."""
        return self._last_eligibility_audit

    @property
    def requires_user_history(self) -> bool:
        return bool(getattr(self._ranker, "requires_user_history", False))

    def impute_missing_scores(self, completed: pd.DataFrame) -> pd.DataFrame:
        medians = calculate_genre_medians(completed)
        return handle_missing_scores_with_genre_medians(completed, medians)

    def calculate_genre_importance(
        self,
        completed: pd.DataFrame,
        catalog: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """Learn the user's taste profile from their rated history.

        ``catalog`` is the wider candidate pool, used to judge how common each
        feature is. Without it the user's own list stands in, which is less
        discriminating but still correct.
        """
        return profile_to_frame(build_taste_profile(completed, catalog=catalog))

    def create_candidates(
        self,
        completed: pd.DataFrame,
        top_anime: pd.DataFrame,
    ) -> pd.DataFrame:
        return filter_recommendation_candidates(completed, top_anime)

    def candidate_catalog(
        self,
        *,
        include_nsfw: bool = False,
        as_of: date | None = None,
    ) -> pd.DataFrame | None:
        provider = getattr(self._ranker, "candidate_catalog", None)
        if not callable(provider):
            return None
        rows = provider(include_nsfw=include_nsfw, as_of=as_of)
        if rows is None:
            return None
        return pd.DataFrame.from_records(rows)

    def recommend(
        self,
        candidates: pd.DataFrame,
        genre_importance: pd.DataFrame,
        settings: PipelineSettings,
        *,
        genre_adjustments: dict[str, float] | None = None,
        excluded_mal_ids: set[int] | frozenset[int] = frozenset(),
        excluded_titles: set[str] | frozenset[str] = frozenset(),
        collaborative_scores: dict[int, float] | None = None,
        user_history: pd.DataFrame | None = None,
        fallback_candidates: pd.DataFrame | None = None,
        consumed_mal_ids: set[int] | frozenset[int] = frozenset(),
        include_nsfw: bool = False,
        as_of: date | None = None,
        rated_history: pd.DataFrame | None = None,
        already_shown_mal_ids: set[int] | frozenset[int] = frozenset(),
        already_shown_titles: set[str] | frozenset[str] = frozenset(),
    ) -> pd.DataFrame:
        """Rank, select and explain a feed.

        ``rated_history`` is the reader's real rated list (never the imputed
        frame); it supplies the "you rated this" evidence in explanations.

        ``already_shown_*`` are titles that must not be selected but must stay
        in the ranking (already in the feed being extended, or hidden since it
        was generated), so fit ranks keep one population across a feed and its
        "more" batches.
        """
        history_records = (
            tuple(user_history.to_dict("records"))
            if user_history is not None
            else ()
        )
        provider = getattr(self._ranker, "eligibility_context", None)
        context = provider() if callable(provider) else EligibilityContext()
        candidate_records, candidate_audit = self._eligibility_policy.apply(
            tuple(candidates.to_dict("records")),
            context=context,
            user_history=history_records,
            consumed_mal_ids=consumed_mal_ids,
            excluded_mal_ids=excluded_mal_ids,
            excluded_titles=excluded_titles,
            include_nsfw=include_nsfw,
            as_of=as_of,
        )
        fallback_records = None
        fallback_audit = None
        if fallback_candidates is not None:
            fallback_records, fallback_audit = self._eligibility_policy.apply(
                tuple(fallback_candidates.to_dict("records")),
                context=context,
                user_history=history_records,
                consumed_mal_ids=consumed_mal_ids,
                excluded_mal_ids=excluded_mal_ids,
                excluded_titles=excluded_titles,
                include_nsfw=include_nsfw,
                as_of=as_of,
            )
        request_context: dict[str, object] = {
            "eligibility": candidate_audit.as_dict(),
        }
        if fallback_records is not None:
            request_context.update(
                {
                    "fallback_candidates": fallback_records,
                    "fallback_candidate_columns": tuple(
                        str(column) for column in fallback_candidates.columns
                    ),
                    "fallback_eligibility": fallback_audit.as_dict(),
                }
            )
        request = RankingRequest(
            candidates=candidate_records,
            taste_profile=tuple(genre_importance.to_dict("records")),
            candidate_columns=tuple(str(column) for column in candidates.columns),
            profile_columns=tuple(str(column) for column in genre_importance.columns),
            user_history=history_records,
            history_columns=(
                tuple(str(column) for column in user_history.columns)
                if user_history is not None
                else ()
            ),
            context=request_context,
            parameters=RankingParameters(
                recommendation_count=settings.recommendation_count,
                candidate_pool_size=settings.candidate_pool_size,
                randomness_factor=settings.randomness_factor,
                # Retained in the contract for compatibility; no engine or
                # selection step reads it.
                random_seed=settings.seed if settings.seed is not None else 0,
                minimum_mean_score=settings.minimum_mean_score,
            ),
            taste_adjustments=genre_adjustments or {},
            excluded_mal_ids=frozenset(excluded_mal_ids),
            excluded_titles=frozenset(excluded_titles),
            collaborative_scores=collaborative_scores or {},
        )
        result = self._ranker.rank(request)
        shown_titles = {
            key for value in already_shown_titles if (key := normalize_title_key(value))
        }
        selectable = [
            row
            for row in result.ranked_candidates
            if not self._already_shown(row, already_shown_mal_ids, shown_titles)
        ]
        # Engines return their ordered, final-eligible pool. The feed is chosen
        # here, once, by the one shared policy, whichever engine answered.
        positions = select_feed(
            selectable,
            settings.recommendation_count,
            settings.randomness_factor,
        )
        selected_rows = [dict(selectable[position]) for position in positions]
        self._explain(
            selected_rows,
            result.metadata,
            request,
            rated_history=rated_history,
            taste_adjustments=genre_adjustments,
        )
        columns = [
            column for column in result.columns if column != SCORE_PARTS_COLUMN
        ]
        if columns:
            columns.append(EXPLANATION_COLUMN)
        self._last_ranking_metadata = result.metadata
        eligibility_audit = (
            fallback_audit
            if result.metadata.fallback_used and fallback_audit is not None
            else candidate_audit
        )
        self._last_eligibility_audit = eligibility_audit
        ranked = pd.DataFrame.from_records(
            selected_rows,
            columns=columns or None,
        )
        ranked.attrs["ranking_engine"] = result.metadata
        ranked.attrs["ranking_warnings"] = result.warnings
        ranked.attrs["eligibility_audit"] = eligibility_audit
        return ranked

    @staticmethod
    def _already_shown(row, shown_ids, shown_titles) -> bool:
        try:
            mal_id = int(row.get("Anime ID"))
        except (TypeError, ValueError):
            mal_id = None
        if mal_id is not None and mal_id in shown_ids:
            return True
        return bool(shown_titles) and normalize_title_key(row.get("Title")) in shown_titles

    def _explain(self, rows, metadata, request, *, rated_history, taste_adjustments):
        """Attach the answering engine's own explanation to each served row.

        Heuristic rows (including a fallback) are explained from their recorded
        score parts. Sequence-model rows are explained by the model engine
        itself; nothing is borrowed from another engine.
        """
        explain = getattr(self._ranker, "explain", None)
        if metadata.explanation_type == METHOD_EXACT_ADDITIVE:
            explanations = explain_additive(
                rows,
                rated_history=(
                    rated_history.to_dict("records")
                    if rated_history is not None
                    else None
                ),
                taste_adjustments=taste_adjustments,
            )
        elif (
            metadata.explanation_type == SEQUENCE_EXPLANATION_TYPE
            and not metadata.fallback_used
            and callable(explain)
        ):
            explanations = explain(request, rows)
        else:
            explanations = [
                unavailable_explanation("engine-cannot-explain") for _row in rows
            ]
        for row, explanation in zip(rows, explanations):
            row.pop(SCORE_PARTS_COLUMN, None)
            row[EXPLANATION_COLUMN] = explanation


# ``explanation_type`` the sequence engine reports in its ranking metadata.
SEQUENCE_EXPLANATION_TYPE = "sequence-score"

MODEL_BUNDLE_ENV = "ANIREC_MODEL_BUNDLE"


def build_recommendation_service(
    *,
    model_bundle: str | None = None,
    random_int: Callable[[int, int], int] | None = None,
) -> RecommendationService:
    """Use the verified ONNX model when configured, with honest fallback."""
    bundle = model_bundle or os.environ.get(MODEL_BUNDLE_ENV)
    if not bundle:
        return RecommendationService(random_int=random_int)
    return RecommendationService(
        random_int=random_int,
        ranker=FallbackRankingEngine(
            OnnxSequenceRankingEngine(bundle),
            HeuristicRankingEngine(),
        ),
    )
