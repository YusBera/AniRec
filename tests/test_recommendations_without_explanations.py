"""Discover rebuilds rank and persist picks without generating explanations."""

from test_recommendation_explanation import (
    SETTINGS, _AdditiveSession, _history, _onnx_service, _orchestrator, _serve, _weights,
)
from AniRec.api.models import RecommendationViewModelResponse
from AniRec.api.serialization import view_model_to_dict
from AniRec.presentation import recommendation_view_models
from AniRec.services import ResultService


def test_sequence_generation_uses_only_the_ranking_inference(tmp_path, monkeypatch):
    session = _AdditiveSession(12, _weights(12))
    service = _onnx_service(tmp_path, session)

    def forbidden(*args, **kwargs):
        raise AssertionError("Discover must not generate removal explanations")

    monkeypatch.setattr(service._ranker, "explain", forbidden)
    feed = _serve(service, _history([1, 2, 3, 4]))
    assert len(feed) == 4
    assert session.calls == 1
    assert "Explanation" not in feed.columns
    assert "Score Parts" not in feed.columns
    assert set(feed["Ranked Candidate Count"]) == {8}
    assert feed.attrs["ranking_engine"].engine_id == "sasrec-onnx"


def test_heuristic_lifecycle_persists_null_why_with_personal_ranks(system_temp_dir):
    orchestrator = _orchestrator(system_temp_dir)
    initial = orchestrator.run_full("fixture-user", SETTINGS)
    more = orchestrator.run_more(
        "fixture-user", SETTINGS, existing_recommendations=initial.recommendations, count=4,
    )
    step = orchestrator.run_step("generate_recommendations", "fixture-user", SETTINGS)
    store = ResultService(root_override=system_temp_dir / "results")
    for result in (initial, more, step):
        assert result.recommendations
        assert all(item.explanation is None for item in result.recommendations)
        store.save("fixture-user", result)
        loaded = store.load("fixture-user")
        assert loaded.recommendations == result.recommendations
        for model in recommendation_view_models(loaded.recommendations):
            response = RecommendationViewModelResponse.model_validate(view_model_to_dict(model))
            assert response.why is None
            assert response.fit_rank > 0
            assert response.fit_pool_size >= response.fit_rank
