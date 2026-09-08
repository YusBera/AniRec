from __future__ import annotations

import ast

import pandas as pd
import pytest

from models import PipelineSettings
from recommendation_system import rank_recommendations
from scoring.contracts import (
    RankingEngineMetadata,
    RankingParameters,
    RankingRequest,
    RankingResult,
)
from scoring.engines import (
    FallbackRankingEngine,
    HeuristicRankingEngine,
    RankingEngineUnavailable,
)
from services import RecommendationService


def _request() -> RankingRequest:
    return RankingRequest(
        candidates=(
            {
                "Anime ID": 1,
                "Title": "Fixture",
                "Genres": ["Action"],
                "Mean Score": 8.0,
            },
        ),
        taste_profile=(
            {"Genre": "Action", "Importance_Score": 80.0},
        ),
        candidate_columns=("Anime ID", "Title", "Genres", "Mean Score"),
        profile_columns=("Genre", "Importance_Score"),
        parameters=RankingParameters(
            recommendation_count=1,
            candidate_pool_size=1,
            randomness_factor=1,
            random_seed=7,
        ),
    )


def test_contract_module_has_no_dataframe_or_model_runtime_dependency(repo_root):
    path = repo_root / "AniRec" / "scoring" / "contracts.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    assert not any(
        name.startswith(("pandas", "numpy", "torch", "tensorflow", "onnx"))
        for name in imported
    )


def test_recommendation_service_routes_portable_records_to_an_injected_engine():
    captured = []

    class FixtureEngine:
        engine_id = "fixture"

        def rank(self, request):
            captured.append(request)
            row = {
                **request.candidates[0],
                "Recommendation Score": 0.5,
                "Match Score": 62.0,
                "Genre Contributions": [("Action", 62.0)],
                "Contributing Genres": ["Action"],
                "Recommendation Reason": "Fixture reason.",
            }
            return RankingResult(
                ranked_candidates=(row,),
                columns=tuple(row),
                metadata=RankingEngineMetadata(
                    engine_id=self.engine_id,
                    engine_version="test",
                    feature_schema_version="fixture-features-v1",
                    explanation_type="fixture",
                ),
            )

    service = RecommendationService(ranker=FixtureEngine())
    result = service.recommend(
        pd.DataFrame(_request().candidates),
        pd.DataFrame(_request().taste_profile),
        PipelineSettings(recommendation_count=1, candidate_pool_size=1, seed=7),
    )

    assert len(captured) == 1
    assert isinstance(captured[0], RankingRequest)
    assert captured[0].candidates[0]["Title"] == "Fixture"
    assert result.iloc[0]["Match Score"] == 62.0
    assert service.last_ranking_metadata.engine_id == "fixture"
    assert result.attrs["ranking_engine"].engine_id == "fixture"


def test_heuristic_adapter_preserves_the_existing_ranked_rows():
    candidates = pd.DataFrame(
        [
            {"Anime ID": 1, "Title": "Alpha", "Genres": ["Action"], "Mean Score": 8.0},
            {"Anime ID": 2, "Title": "Beta", "Genres": ["Comedy"], "Mean Score": 7.0},
            {"Anime ID": 3, "Title": "Gamma", "Genres": ["Action"], "Mean Score": 9.0},
        ]
    )
    profile = pd.DataFrame(
        [
            {"Genre": "Action", "Importance_Score": 80.0},
            {"Genre": "Comedy", "Importance_Score": 20.0},
        ]
    )
    settings = PipelineSettings(
        recommendation_count=2,
        candidate_pool_size=3,
        randomness_factor=7,
        seed=13,
    )

    expected = rank_recommendations(
        candidates,
        profile,
        num_recommendations=2,
        top_anime_count=3,
        randomness_factor=7,
        random_state=13,
        minimum_mean_score=settings.minimum_mean_score,
    )
    actual = RecommendationService().recommend(candidates, profile, settings)

    assert actual.columns.tolist() == expected.columns.tolist()
    assert actual.to_dict("records") == expected.to_dict("records")
    assert actual.attrs["ranking_engine"].engine_id == "heuristic"
    assert actual.attrs["ranking_engine"].explanation_type == "exact-additive"


def test_fallback_router_records_why_the_preferred_engine_was_not_used():
    class UnavailableEngine:
        engine_id = "future-model"

        def rank(self, _request):
            raise RankingEngineUnavailable("Model artifact is not installed.")

    result = FallbackRankingEngine(
        UnavailableEngine(),
        HeuristicRankingEngine(),
    ).rank(_request())

    assert result.metadata.engine_id == "heuristic"
    assert result.metadata.requested_engine_id == "future-model"
    assert result.metadata.fallback_used is True
    assert result.warnings == ("Model artifact is not installed.",)


def test_fallback_router_does_not_hide_engine_programming_errors():
    class BrokenEngine:
        engine_id = "broken"

        def rank(self, _request):
            raise ValueError("Bad model output")

    with pytest.raises(ValueError, match="Bad model output"):
        FallbackRankingEngine(BrokenEngine(), HeuristicRankingEngine()).rank(_request())
