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
    from ..recommendation_system import rank_recommendations
except ImportError:  # Compatibility with the S01 top-level test import path.
    from candidate_generation import filter_recommendation_candidates
    from genre_importance import calculate_genre_importance
    from handle_missing_scores import (
        calculate_genre_medians,
        handle_missing_scores_with_genre_medians,
    )
    from models import PipelineSettings
    from recommendation_system import rank_recommendations


class RecommendationService:
    def __init__(
        self,
        *,
        random_int: Callable[[int, int], int] = random.randint,
    ) -> None:
        self._random_int = random_int

    def impute_missing_scores(self, completed: pd.DataFrame) -> pd.DataFrame:
        medians = calculate_genre_medians(completed)
        return handle_missing_scores_with_genre_medians(completed, medians)

    def calculate_genre_importance(self, completed: pd.DataFrame) -> pd.DataFrame:
        medians = calculate_genre_medians(completed)
        importance = calculate_genre_importance(completed, medians)
        return pd.DataFrame(
            sorted(importance.items(), key=lambda item: item[1], reverse=True),
            columns=["Genre", "Importance_Score"],
        )

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
    ) -> pd.DataFrame:
        random_state = (
            settings.seed
            if settings.seed is not None
            else self._random_int(1, 1_000_000)
        )
        return rank_recommendations(
            candidates,
            genre_importance,
            num_recommendations=settings.recommendation_count,
            top_anime_count=settings.candidate_pool_size,
            randomness_factor=settings.randomness_factor,
            random_state=random_state,
            genre_adjustments=genre_adjustments,
            excluded_mal_ids=excluded_mal_ids,
            excluded_titles=excluded_titles,
        )
