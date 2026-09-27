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
        RankingEngineUnavailable,
    )
    from ..scoring.eligibility import (
        EligibilityAudit,
        EligibilityContext,
        FinalEligibilityPolicy,
    )
    from ..scoring.explanation import (
        EXPLANATION_COLUMN,
        SCORE_PARTS_COLUMN,
    )
    from ..scoring.selection import select_feed, select_feed_pages, select_complete_feed
    from ..scoring.serialization import profile_to_frame
    from ..scoring.taste import build_taste_profile
    from ..title_utils import normalize_title_key
    from .offline_anime_catalogue import OfflineAnimeCatalogue
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
        RankingEngineUnavailable,
    )
    from scoring.eligibility import (
        EligibilityAudit,
        EligibilityContext,
        FinalEligibilityPolicy,
    )
    from scoring.explanation import (
        EXPLANATION_COLUMN,
        SCORE_PARTS_COLUMN,
    )
    from scoring.selection import select_feed, select_feed_pages, select_complete_feed
    from scoring.serialization import profile_to_frame
    from scoring.taste import build_taste_profile
    from title_utils import normalize_title_key
    from services.offline_anime_catalogue import OfflineAnimeCatalogue


class RecommendationService:
    def __init__(
        self,
        *,
        random_int: Callable[[int, int], int] | None = None,
        ranker: RankingEngine | None = None,
        eligibility_policy: FinalEligibilityPolicy | None = None,
        anime_reference: OfflineAnimeCatalogue | None = None,
    ) -> None:
        # ``random_int`` is accepted for older callers only. Feed selection is
        # deterministic and never draws from a random source.
        del random_int
        self._ranker = ranker if ranker is not None else HeuristicRankingEngine()
        self._eligibility_policy = eligibility_policy or FinalEligibilityPolicy()
        self._anime_reference = anime_reference
        self._last_ranking_metadata: RankingEngineMetadata | None = None
        self._last_eligibility_audit: EligibilityAudit | None = None

    def engine_identity(self) -> tuple[str, str]:
        """The engine and version that would rank a feed now.

        With a fallback router that is the preferred engine when it can load,
        and the fallback when it cannot. It is compared against the engine a
        saved feed records, so a feed ranked by a fallback is rebuilt once the
        preferred engine is available again, and a model swap is noticed
        before anything is ranked.
        """
        preferred = self.preferred_identity()
        if preferred is not None:
            return preferred
        return self.fallback_identity() or self._identity(self._preferred_engine())

    def preferred_identity(self) -> tuple[str, str] | None:
        """The preferred engine and version, or None when it cannot load.

        Loading is not ranking: a loadable model can still decline one reader
        (no usable history, nothing it covers), and then the fallback ranks.
        """
        preferred = self._preferred_engine()
        load = getattr(preferred, "eligibility_context", None)
        try:
            if callable(load):
                load()
        except RankingEngineUnavailable:
            return None
        return self._identity(preferred)

    def fallback_identity(self) -> tuple[str, str] | None:
        """The engine a router falls back to, or None without a router."""
        fallback = getattr(self._ranker, "fallback_engine", None)
        return None if fallback is None else self._identity(fallback)

    def _preferred_engine(self):
        return getattr(self._ranker, "preferred_engine", self._ranker)

    @staticmethod
    def _identity(engine) -> tuple[str, str]:
        return str(engine.engine_id), str(engine.engine_version)

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
        if self._anime_reference is not None:
            rows = self._anime_reference.enrich_candidates(list(rows))
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
        known_mal_ids: set[int] | frozenset[int] = frozenset(),
        include_nsfw: bool = False,
        as_of: date | None = None,
        rated_history: pd.DataFrame | None = None,
        already_shown_mal_ids: set[int] | frozenset[int] = frozenset(),
        already_shown_titles: set[str] | frozenset[str] = frozenset(),
        selection_page_size: int | None = None,
        full_ranking: bool = False,
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
            known_mal_ids=known_mal_ids,
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
                known_mal_ids=known_mal_ids,
                excluded_mal_ids=excluded_mal_ids,
                excluded_titles=excluded_titles,
                include_nsfw=include_nsfw,
                as_of=as_of,
            )
        request_context: dict[str, object] = {
            "eligibility": candidate_audit.as_dict(),
            "full_ranking": full_ranking,
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
        positions = (
            select_complete_feed(selectable, settings.randomness_factor)
            if full_ranking else
            select_feed_pages(
                selectable, settings.recommendation_count,
                settings.randomness_factor, selection_page_size,
            )
            if selection_page_size is not None
            else select_feed(
                selectable, settings.recommendation_count,
                settings.randomness_factor,
            )
        )
        selected_rows = [dict(selectable[position]) for position in positions]
        # Discover serves ranks, without explanation work or removal inferences.
        # Drop internal score parts and any legacy explanation carried by a row.
        for row in selected_rows:
            row.pop(SCORE_PARTS_COLUMN, None)
            row.pop(EXPLANATION_COLUMN, None)
        if self._anime_reference is not None:
            if full_ranking:
                selected_rows[:50] = self._anime_reference.enrich_selected(selected_rows[:50])
            else:
                selected_rows = self._anime_reference.enrich_selected(selected_rows)
        columns = [
            column for column in result.columns
            if column not in (SCORE_PARTS_COLUMN, EXPLANATION_COLUMN)
        ]
        if columns:
            if self._anime_reference is not None:
                columns = list(dict.fromkeys((
                    *columns, "Picture URL", "Large Picture URL", "Synopsis", "PV YouTube URL"
                )))
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
        ranked.attrs["complete_ranking"] = full_ranking
        ranked.attrs["ranking_engine"] = result.metadata
        ranked.attrs["ranking_warnings"] = result.warnings
        ranked.attrs["eligibility_audit"] = eligibility_audit
        return ranked

    def complete_ranking_identity(self):
        provider = getattr(self._ranker, "eligibility_context", None)
        context = provider() if callable(provider) else EligibilityContext()
        reference = None
        if self._anime_reference is not None:
            stat = self._anime_reference.path.stat()
            reference = (stat.st_size, stat.st_mtime_ns)
        return {"catalogue": context.catalog_version, "reference": reference,
                "selection": "complete-carry-v1"}

    @staticmethod
    def _already_shown(row, shown_ids, shown_titles) -> bool:
        try:
            mal_id = int(row.get("Anime ID"))
        except (TypeError, ValueError):
            mal_id = None
        if mal_id is not None and mal_id in shown_ids:
            return True
        return bool(shown_titles) and normalize_title_key(row.get("Title")) in shown_titles


MODEL_BUNDLE_ENV = "ANIREC_MODEL_BUNDLE"


def build_recommendation_service(
    *,
    model_bundle: str | None = None,
    random_int: Callable[[int, int], int] | None = None,
    anime_reference: OfflineAnimeCatalogue | None = None,
) -> RecommendationService:
    """Use the verified ONNX model when configured, with honest fallback."""
    bundle = model_bundle or os.environ.get(MODEL_BUNDLE_ENV)
    reference = anime_reference if anime_reference is not None else OfflineAnimeCatalogue.from_environment()
    if not bundle:
        return RecommendationService(random_int=random_int, anime_reference=reference)
    return RecommendationService(
        random_int=random_int,
        anime_reference=reference,
        ranker=FallbackRankingEngine(
            OnnxSequenceRankingEngine(bundle),
            HeuristicRankingEngine(),
        ),
    )
