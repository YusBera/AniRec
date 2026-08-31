"""In-memory recommendation calculations with injectable randomness."""

from __future__ import annotations

import random
from collections.abc import Callable

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
    from ..scoring.engines import HeuristicRankingEngine
    from ..scoring.serialization import profile_to_frame
    from ..scoring.taste import build_taste_profile
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
    from scoring.engines import HeuristicRankingEngine
    from scoring.serialization import profile_to_frame
    from scoring.taste import build_taste_profile


class RecommendationService:
    def __init__(
        self,
        *,
        random_int: Callable[[int, int], int] = random.randint,
        ranker: RankingEngine | None = None,
    ) -> None:
        self._random_int = random_int
        self._ranker = ranker if ranker is not None else HeuristicRankingEngine()
        self._last_ranking_metadata: RankingEngineMetadata | None = None

    @property
    def last_ranking_metadata(self) -> RankingEngineMetadata | None:
        """Provenance from the latest completed ranking operation."""
        return self._last_ranking_metadata

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
    ) -> pd.DataFrame:
        random_state = (
            settings.seed
            if settings.seed is not None
            else self._random_int(1, 1_000_000)
        )
        request = RankingRequest(
            candidates=tuple(candidates.to_dict("records")),
            taste_profile=tuple(genre_importance.to_dict("records")),
            candidate_columns=tuple(str(column) for column in candidates.columns),
            profile_columns=tuple(str(column) for column in genre_importance.columns),
            parameters=RankingParameters(
                recommendation_count=settings.recommendation_count,
                candidate_pool_size=settings.candidate_pool_size,
                randomness_factor=settings.randomness_factor,
                random_seed=random_state,
                minimum_mean_score=settings.minimum_mean_score,
            ),
            taste_adjustments=genre_adjustments or {},
            excluded_mal_ids=frozenset(excluded_mal_ids),
            excluded_titles=frozenset(excluded_titles),
            collaborative_scores=collaborative_scores or {},
        )
        result = self._ranker.rank(request)
        self._last_ranking_metadata = result.metadata
        ranked = pd.DataFrame.from_records(
            result.ranked_candidates,
            columns=list(result.columns) or None,
        )
        ranked.attrs["ranking_engine"] = result.metadata
        ranked.attrs["ranking_warnings"] = result.warnings
        return ranked
