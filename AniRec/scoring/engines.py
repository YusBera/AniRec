"""Ranking engine adapters and conservative fallback routing."""

from __future__ import annotations

from dataclasses import replace
from time import perf_counter

import pandas as pd

try:
    from ..recommendation_system import rank_recommendations
    from .contracts import (
        RANKING_INPUT_SCHEMA_VERSION,
        RankingEngine,
        RankingEngineMetadata,
        RankingRequest,
        RankingResult,
    )
except ImportError:  # Compatibility with the sibling import path used by tests.
    from recommendation_system import rank_recommendations
    from scoring.contracts import (
        RANKING_INPUT_SCHEMA_VERSION,
        RankingEngine,
        RankingEngineMetadata,
        RankingRequest,
        RankingResult,
    )


class RankingEngineUnavailable(RuntimeError):
    """The selected engine cannot perform inference in this environment."""


class IncompatibleRankingEngine(RankingEngineUnavailable):
    """The engine and request use incompatible contracts or feature schemas."""


class HeuristicRankingEngine:
    """Adapter that preserves AniRec's current explainable ranking behavior."""

    engine_id = "heuristic"
    engine_version = "1"
    feature_schema_version = "heuristic-v1"

    def rank(self, request: RankingRequest) -> RankingResult:
        if request.input_schema_version != RANKING_INPUT_SCHEMA_VERSION:
            raise IncompatibleRankingEngine(
                "The heuristic engine does not support ranking input schema "
                f"{request.input_schema_version!r}."
            )

        candidates = pd.DataFrame.from_records(
            request.candidates,
            columns=list(request.candidate_columns) or None,
        )
        profile = pd.DataFrame.from_records(
            request.taste_profile,
            columns=list(request.profile_columns) or None,
        )
        started = perf_counter()
        ranked = rank_recommendations(
            candidates,
            profile,
            num_recommendations=request.parameters.recommendation_count,
            top_anime_count=request.parameters.candidate_pool_size,
            randomness_factor=request.parameters.randomness_factor,
            random_state=request.parameters.random_seed,
            genre_adjustments=dict(request.taste_adjustments),
            excluded_mal_ids=set(request.excluded_mal_ids),
            excluded_titles=set(request.excluded_titles),
            minimum_mean_score=request.parameters.minimum_mean_score,
            collaborative_scores=dict(request.collaborative_scores),
        )
        elapsed_ms = (perf_counter() - started) * 1000.0
        return RankingResult(
            ranked_candidates=tuple(ranked.to_dict("records")),
            columns=tuple(str(column) for column in ranked.columns),
            metadata=RankingEngineMetadata(
                engine_id=self.engine_id,
                engine_version=self.engine_version,
                feature_schema_version=self.feature_schema_version,
                explanation_type="exact-additive",
                inference_ms=elapsed_ms,
            ),
        )


class FallbackRankingEngine:
    """Try a preferred engine and fall back only for availability failures.

    Programming and data errors are intentionally not swallowed. A future
    model adapter should translate missing artifacts, incompatible schemas,
    timeouts, and runtime startup failures into RankingEngineUnavailable.
    """

    engine_id = "fallback-router"

    def __init__(self, preferred: RankingEngine, fallback: RankingEngine) -> None:
        self._preferred = preferred
        self._fallback = fallback

    def rank(self, request: RankingRequest) -> RankingResult:
        try:
            return self._preferred.rank(request)
        except RankingEngineUnavailable as error:
            result = self._fallback.rank(request)
            return replace(
                result,
                metadata=replace(
                    result.metadata,
                    fallback_used=True,
                    requested_engine_id=self._preferred.engine_id,
                ),
                warnings=(*result.warnings, str(error)),
            )
