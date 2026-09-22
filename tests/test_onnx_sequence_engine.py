from __future__ import annotations

import hashlib
import json
from datetime import date
from dataclasses import replace

import numpy as np
import pandas as pd

from models import PipelineSettings
from scoring.contracts import RankingParameters, RankingRequest
from scoring.engines import (
    FallbackRankingEngine,
    HeuristicRankingEngine,
    OnnxSequenceRankingEngine,
)
from services import RecommendationService


class FakeSession:
    def __init__(self, logits):
        self.logits = np.asarray([logits], dtype=np.float32)
        self.feeds = []

    def run(self, outputs, feeds):
        assert outputs == ["logits"]
        self.feeds.append(feeds)
        return [self.logits]


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bundle(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    np.save(bundle / "items.npy", np.asarray([1, 2, 3, 4], dtype=np.int32))
    np.save(bundle / "candidate_mask.npy", np.asarray([1, 1, 1, 1], dtype=bool))
    (bundle / "catalog.json").write_text(
        json.dumps(
            [
                {
                    "anime_id": 1,
                    "title": "Already watched",
                    "start_date": "2020-01-01",
                    "airing_status": "Finished Airing",
                    "content_rating": "PG-13 - Teens 13 or older",
                    "genres": ["Action"],
                },
                {
                    "anime_id": 2,
                    "title": "Future title",
                    "start_date": "2030-01-01",
                    "airing_status": "Not yet aired",
                    "content_rating": "PG-13 - Teens 13 or older",
                    "genres": ["Action"],
                },
                {
                    "anime_id": 3,
                    "title": "Adult title",
                    "start_date": "2021-01-01",
                    "airing_status": "Finished Airing",
                    "content_rating": "Rx - Hentai",
                    "genres": ["Action"],
                },
                {
                    "anime_id": 4,
                    "title": "Released title",
                    "start_date": "2022-01-01",
                    "airing_status": "Finished Airing",
                    "content_rating": "PG-13 - Teens 13 or older",
                    "genres": ["Action"],
                },
            ]
        ),
        encoding="utf-8",
    )
    np.savez(
        bundle / "prerequisites.npz",
        candidate=np.asarray([3], dtype=np.int32),
        prequel=np.asarray([0], dtype=np.int32),
    )
    (bundle / "model.onnx").write_bytes(b"fixture graph")
    files = {
        name: {"sha256": _sha256(bundle / name)}
        for name in (
            "items.npy",
            "candidate_mask.npy",
            "catalog.json",
            "prerequisites.npz",
            "model.onnx",
        )
    }
    (bundle / "manifest.json").write_text(
        json.dumps(
            {
                "bundle_version": 3,
                "format": "onnx",
                "checkpoint": {"sha256": "abcdef1234567890"},
                "data": {"n_items": 4},
                "model": {"maxlen": 4},
                "contract": {"sequence_length": 4},
                "parity": {"parity_pass": True},
                "files": files,
            }
        ),
        encoding="utf-8",
    )
    return bundle


def _request(history):
    candidates = tuple(
        {
            "Anime ID": mal_id,
            "Title": title,
            "Genres": ["Action"],
            "Mean Score": mean,
        }
        for mal_id, title, mean in (
            (1, "Already watched", 9.9),
            (2, "Best model candidate", 7.0),
            (3, "Second model candidate", 9.0),
            (4, "Lowest model candidate", 10.0),
        )
    )
    return RankingRequest(
        candidates=candidates,
        taste_profile=({"Genre": "Action", "Importance_Score": 80.0},),
        user_history=tuple(history),
        candidate_columns=tuple(candidates[0]),
        parameters=RankingParameters(
            recommendation_count=2,
            candidate_pool_size=4,
            randomness_factor=5,
            random_seed=7,
        ),
    )


def test_onnx_engine_uses_typed_chronology_and_excludes_known_items(tmp_path):
    session = FakeSession([0.2, 0.9, 0.7, 0.1])
    engine = OnnxSequenceRankingEngine(
        _bundle(tmp_path), session_factory=lambda _path: session
    )
    history = [
        {
            "Anime ID": 1,
            "Status": "completed",
            "User Score": 8,
            "Episodes Watched": 12,
            "Is Rewatching": False,
            "Updated At": "2026-09-01T10:00:00+00:00",
        }
    ]

    result = engine.rank(_request(history))

    # The engine returns its whole ordered pool; the service selects the feed.
    assert [row["Anime ID"] for row in result.ranked_candidates] == [2, 3, 4]
    assert result.metadata.engine_id == "sasrec-onnx"
    assert result.metadata.explanation_type == "sequence-score"
    feed = session.feeds[0]
    assert feed["items"].tolist() == [[0, 0, 0, 1]]
    assert feed["types"].tolist() == [[0, 0, 0, 1]]
    assert feed["scores"].tolist() == [[0, 0, 0, 8]]
    assert result.ranked_candidates[0]["Match Score Available"] is False


def test_missing_chronology_falls_back_and_reports_requested_engine(tmp_path):
    engine = FallbackRankingEngine(
        OnnxSequenceRankingEngine(
            _bundle(tmp_path),
            session_factory=lambda _path: FakeSession([0.2, 0.9, 0.7, 0.1]),
        ),
        HeuristicRankingEngine(),
    )
    request = _request(
        [
            {
                "Anime ID": 1,
                "Status": "completed",
                "User Score": 8,
                "Episodes Watched": 12,
                "Is Rewatching": False,
                "Updated At": "",
            }
        ]
    )

    result = engine.rank(request)

    assert result.metadata.engine_id == "heuristic"
    assert result.metadata.requested_engine_id == "sasrec-onnx"
    assert result.metadata.fallback_used
    assert "missing update timestamps" in result.warnings[0]


def test_neural_failure_limits_heuristic_fallback_to_live_candidates(tmp_path):
    engine = FallbackRankingEngine(
        OnnxSequenceRankingEngine(
            _bundle(tmp_path),
            session_factory=lambda _path: FakeSession([0.2, 0.9, 0.7, 0.1]),
        ),
        HeuristicRankingEngine(),
    )
    request = _request(
        [
            {
                "Anime ID": 1,
                "Status": "completed",
                "User Score": 8,
                "Episodes Watched": 12,
                "Is Rewatching": False,
                "Updated At": "",
            }
        ]
    )
    live = (dict(request.candidates[1]),)
    request = replace(
        request,
        context={
            "fallback_candidates": live,
            "fallback_candidate_columns": tuple(live[0]),
        },
    )

    result = engine.rank(request)

    assert [row["Anime ID"] for row in result.ranked_candidates] == [2]
    assert result.metadata.fallback_used


def test_later_entry_requires_a_consumed_direct_prequel(tmp_path):
    session = FakeSession([0.2, 0.1, 0.7, 0.95])
    engine = OnnxSequenceRankingEngine(
        _bundle(tmp_path), session_factory=lambda _path: session
    )
    request = _request(
        [
            {
                "Anime ID": 1,
                "Status": "plan_to_watch",
                "User Score": 0,
                "Episodes Watched": 0,
                "Is Rewatching": False,
                "Updated At": "2026-09-01T10:00:00+00:00",
            }
        ]
    )

    result = engine.rank(request)

    assert [row["Anime ID"] for row in result.ranked_candidates] == [3, 2]
    assert all(row["Anime ID"] != 4 for row in result.ranked_candidates)


def test_serving_catalog_filters_release_and_nsfw_without_guessing(tmp_path):
    engine = OnnxSequenceRankingEngine(
        _bundle(tmp_path), session_factory=lambda _path: FakeSession([0, 0, 0, 0])
    )

    safe = engine.candidate_catalog(as_of=date(2026, 9, 20))
    with_nsfw = engine.candidate_catalog(
        include_nsfw=True, as_of=date(2026, 9, 20)
    )

    assert [row["Anime ID"] for row in safe] == [1, 4]
    assert [row["Anime ID"] for row in with_nsfw] == [1, 3, 4]
    assert safe[1]["Mean Score"] is None
    assert safe[1]["MAL URL"] == "https://myanimelist.net/anime/4"


def test_recommendation_service_passes_history_to_sequence_boundary(tmp_path):
    session = FakeSession([0.2, 0.9, 0.7, 0.1])
    service = RecommendationService(
        ranker=OnnxSequenceRankingEngine(
            _bundle(tmp_path), session_factory=lambda _path: session
        )
    )
    request = _request(
        [
            {
                "Anime ID": 1,
                "Status": "watching",
                "User Score": 0,
                "Episodes Watched": 0,
                "Is Rewatching": True,
                "Updated At": "2026-09-01T10:00:00+00:00",
            }
        ]
    )

    result = service.recommend(
        pd.DataFrame(request.candidates),
        pd.DataFrame(request.taste_profile),
        PipelineSettings(
            top_anime_limit=4,
            recommendation_count=2,
            candidate_pool_size=4,
            seed=7,
        ),
        user_history=pd.DataFrame(request.user_history),
        as_of=date(2026, 9, 20),
    )

    # The shared final policy removes the future and restricted rows after the
    # catalogue merge; the consumed prequel makes the released sequel eligible.
    assert result["Anime ID"].tolist() == [4]
    assert service.requires_user_history
    assert session.feeds[0]["types"].tolist() == [[0, 0, 0, 2]]
    assert service.last_eligibility_audit.excluded_by_reason == {
        "already_in_history": 1,
        "not_released": 1,
        "restricted_content": 1,
    }


def test_model_startup_failure_keeps_bundle_eligibility_on_fallback(tmp_path):
    def unavailable_session(_path):
        raise RuntimeError("runtime unavailable")

    engine = FallbackRankingEngine(
        OnnxSequenceRankingEngine(
            _bundle(tmp_path), session_factory=unavailable_session
        ),
        HeuristicRankingEngine(),
    )
    service = RecommendationService(ranker=engine)
    candidates = pd.DataFrame(
        [
            {
                "Anime ID": 2,
                "Title": "Future title",
                "Genres": ["Action"],
                "Mean Score": 9.0,
            },
            {
                "Anime ID": 4,
                "Title": "Released title",
                "Genres": ["Action"],
                "Mean Score": 8.0,
            },
        ]
    )
    history = pd.DataFrame(
        [
            {
                "Anime ID": 1,
                "Status": "completed",
                "User Score": 8,
                "Episodes Watched": 12,
                "Is Rewatching": False,
                "Updated At": "2026-09-01T10:00:00+00:00",
            }
        ]
    )

    result = service.recommend(
        candidates,
        pd.DataFrame([{"Genre": "Action", "Importance_Score": 80.0}]),
        PipelineSettings(recommendation_count=1, candidate_pool_size=2, seed=7),
        user_history=history,
        fallback_candidates=candidates,
        as_of=date(2026, 9, 20),
    )

    assert result["Anime ID"].tolist() == [4]
    assert service.last_ranking_metadata.fallback_used
    assert service.last_eligibility_audit.excluded_by_reason == {"not_released": 1}
