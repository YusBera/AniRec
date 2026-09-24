"""Personal fit as a rank, and "why was this recommended to me?" (Goal 2).

Every test runs the shipped path: the pipeline or ``RecommendationService`` with
the real engines, then persistence, the shared view model and the strict API
model. Nothing in the ranking, selection or explanation path is mocked.
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import pytest

from AniRec.services.cover_url_service import CoverUrlService
from AniRec.api.models import Explanation, RecommendationViewModelResponse
from AniRec.api.serialization import view_model_to_dict
from AniRec.application.pipeline import PipelineOrchestrator
from AniRec.infrastructure.csv_storage import CsvStorage
from AniRec.models import PipelineResult, PipelineSettings
from AniRec.presentation import recommendation_view_models
from AniRec.scoring.engines import (
    FallbackRankingEngine,
    HeuristicRankingEngine,
    OnnxSequenceRankingEngine,
)
from AniRec.services import (
    AnimeDataService,
    ProfileService,
    RecommendationService,
    ResultService,
)


AS_OF = date(2026, 9, 20)
NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
GENRE_POOL = ["Drama", "Comedy", "Mystery", "Romance", "Sports", "Horror"]


def _catalogue():
    rows = []
    for index in range(24):
        rows.append(
            {
                "Anime ID": 500 + index,
                "Title": f"Catalogue {index:02d}",
                "Genres": ["Action", GENRE_POOL[index % 6]]
                if index % 4
                else [GENRE_POOL[index % 6]],
                "Studios": [["Madhouse", "Bones", "MAPPA"][index % 3]],
                "Source": ["Manga", "Original"][index % 2],
                "Media Type": "tv",
                # One title has no community score, to exercise the stand-in.
                "Mean Score": None if index == 7 else 8.9 - index * 0.05,
                "Scoring Users": None if index == 7 else 50_000 + index,
                "Year": 2010 + index % 10,
            }
        )
    return pd.DataFrame(rows)


def _completed():
    rows = [
        (101, "Loved Action Drama", ["Action", "Drama"], "Madhouse", 10),
        (102, "Liked Action", ["Action"], "Bones", 9),
        (103, "Fine Mystery", ["Mystery"], "MAPPA", 7),
        (104, "Disliked Comedy", ["Comedy"], "Bones", 3),
        (105, "Hated Comedy Romance", ["Comedy", "Romance"], "MAPPA", 2),
        (106, "Unrated Action", ["Action"], "Madhouse", 0),
        (107, "Unscored Drama", ["Drama"], "Madhouse", float("nan")),
    ]
    return pd.DataFrame(
        [
            {
                "Anime ID": mal_id,
                "Title": title,
                "Genres": genres,
                "Studios": [studio],
                "Source": "Manga",
                "Media Type": "tv",
                "Status": "Completed",
                "User Score": score,
                "Year": 2015,
            }
            for mal_id, title, genres, studio, score in rows
        ]
    )


REAL_SCORES = {"Loved Action Drama": 10, "Liked Action": 9, "Fine Mystery": 7,
               "Disliked Comedy": 3, "Hated Comedy Romance": 2}


def _orchestrator(root, recommendations=None):
    return PipelineOrchestrator(
        anime_data=AnimeDataService(
            top_fetcher=lambda **_kwargs: _catalogue(),
            completed_fetcher=lambda *_args, **_kwargs: _completed(),
        ),
        profiles=ProfileService(root_override=root / "app-data", clock=lambda: NOW),
        recommendations=recommendations or RecommendationService(),
        storage=CsvStorage(),
        access_token_provider=lambda: "fake-access-token",
        clock=lambda: NOW,
    )


SETTINGS = PipelineSettings(
    top_anime_limit=24, recommendation_count=6, candidate_pool_size=24,
    randomness_factor=10,
)


def _segment_sum(why):
    return math.fsum(segment["value"] for segment in why["segments"])


# --- heuristic: exact, evidence-backed breakdown ------------------------------


def test_heuristic_why_sums_exactly_to_the_ranking_score(system_temp_dir):
    result = _orchestrator(system_temp_dir).run_full("fixture-user", SETTINGS)

    assert result.recommendations
    for item in result.recommendations:
        why = item.explanation
        assert why["method"] == "exact-additive"
        assert why["unit"] == "ranking-score"
        assert _segment_sum(why) == pytest.approx(why["total"], abs=1e-12)
        # The stored ranking score is rounded to six places.
        assert why["total"] == pytest.approx(item.raw_score, abs=5e-7)
        kinds = [segment["kind"] for segment in why["segments"]]
        assert kinds.count("community") == 1
        assert set(kinds) <= {"taste", "community", "similar-viewers"}


def test_taste_evidence_quotes_only_real_ratings_in_the_part_direction(system_temp_dir):
    orchestrator = _orchestrator(system_temp_dir)
    initial = orchestrator.run_full("fixture-user", SETTINGS)
    more = orchestrator.run_more(
        "fixture-user", SETTINGS,
        existing_recommendations=initial.recommendations, count=4,
    )
    step = orchestrator.run_step("generate_recommendations", "fixture-user", SETTINGS)

    seen_negative = seen_positive = False
    for result in (initial, more, step):
        for item in result.recommendations:
            for segment in item.explanation["segments"]:
                if segment["kind"] != "taste":
                    continue
                scores = [entry["user_score"] for entry in segment["evidence"]]
                for entry in segment["evidence"]:
                    # Only genuinely rated titles, with their real score:
                    # never the imputed copy, never an unrated entry.
                    assert REAL_SCORES[entry["title"]] == entry["user_score"]
                if segment["value"] > 0:
                    seen_positive = seen_positive or bool(scores)
                    assert scores == sorted(scores, reverse=True)
                elif segment["value"] < 0:
                    seen_negative = seen_negative or bool(scores)
                    assert scores == sorted(scores)
                taste = segment["taste"]
                assert taste["rated_count"] >= len(segment["evidence"])
                assert taste["overall_mean_user_score"] == pytest.approx(6.2)
    assert seen_positive and seen_negative


def test_community_part_is_separate_and_flags_a_missing_score():
    catalogue = _catalogue()
    feed = RecommendationService().recommend(
        catalogue,
        _profile_frame(),
        PipelineSettings(recommendation_count=24, candidate_pool_size=24,
                         top_anime_limit=24, randomness_factor=1),
        rated_history=_completed(),
    )
    by_id = {int(row["Anime ID"]): row["Explanation"] for _i, row in feed.iterrows()}
    community = {
        mal_id: next(s for s in why["segments"] if s["kind"] == "community")
        for mal_id, why in by_id.items()
    }
    assert community[507]["signal_available"] is False
    assert community[507]["community"]["mean_score"] is None
    assert community[500]["signal_available"] is True
    assert community[500]["community"]["mean_score"] == pytest.approx(8.9)
    assert all(s["taste"] is None for s in community.values())


def test_feedback_adjustment_is_recorded_on_the_genre_part():
    feed = RecommendationService().recommend(
        _catalogue(),
        _profile_frame(),
        PipelineSettings(recommendation_count=24, candidate_pool_size=24,
                         top_anime_limit=24, randomness_factor=1),
        genre_adjustments={"Comedy": 12.0},
        rated_history=_completed(),
    )
    comedy = [
        segment
        for why in feed["Explanation"]
        for segment in why["segments"]
        if segment["facet"] == "genre" and segment["label"] == "Comedy"
    ]
    others = [
        segment
        for why in feed["Explanation"]
        for segment in why["segments"]
        if segment["facet"] == "genre" and segment["label"] != "Comedy"
    ]
    assert comedy and all(s["feedback_adjustment"] == 12.0 for s in comedy)
    assert others and all(s["feedback_adjustment"] is None for s in others)


def _profile_frame():
    return RecommendationService().calculate_genre_importance(_completed(), _catalogue())


# --- personal fit is the engine's own rank, before selection -------------------


def test_fit_rank_is_the_engine_rank_before_selection():
    catalogue = _catalogue()
    settings = PipelineSettings(recommendation_count=6, candidate_pool_size=24,
                                top_anime_limit=24, randomness_factor=10)
    feed = RecommendationService().recommend(
        catalogue, _profile_frame(), settings, rated_history=_completed()
    )
    full = RecommendationService().recommend(
        catalogue, _profile_frame(),
        PipelineSettings(recommendation_count=24, candidate_pool_size=24,
                         top_anime_limit=24, randomness_factor=1),
        rated_history=_completed(),
    )
    order = [int(value) for value in full["Anime ID"]]
    ranks = [int(value) for value in feed["Model Rank"]]

    assert [order.index(int(mal_id)) + 1 for mal_id in feed["Anime ID"]] == ranks
    assert set(feed["Ranked Candidate Count"]) == {24}
    # Diversity selection skipped at least one title, so feed position and
    # engine rank differ somewhere; the fit rank reports the engine's.
    assert ranks != list(range(1, len(ranks) + 1))


# --- ONNX: honest "cannot explain" -------------------------------------------


def _bundle(tmp_path, size):
    import hashlib

    bundle = tmp_path / "bundle"
    bundle.mkdir(parents=True)
    catalog = [
        {
            "anime_id": anime_id,
            "title": f"Title {anime_id:03d}",
            "start_date": "2020-01-01",
            "airing_status": "Finished Airing",
            "content_rating": "PG-13 - Teens 13 or older",
            "genres": ["Action", GENRE_POOL[anime_id % 6]],
            "studios": ["Studio A"],
            "source": "Manga",
            "media_type": "tv",
        }
        for anime_id in range(1, size + 1)
    ]
    np.save(bundle / "items.npy", np.arange(1, size + 1, dtype=np.int32))
    np.save(bundle / "candidate_mask.npy", np.ones(size, dtype=bool))
    (bundle / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    np.savez(bundle / "prerequisites.npz", candidate=np.zeros(0, np.int32),
             prequel=np.zeros(0, np.int32))
    (bundle / "model.onnx").write_bytes(b"fixture graph")
    names = ("items.npy", "candidate_mask.npy", "catalog.json",
             "prerequisites.npz", "model.onnx")
    (bundle / "manifest.json").write_text(json.dumps({
        "bundle_version": 3, "format": "onnx",
        "checkpoint": {"sha256": "abcdef1234567890"},
        "data": {"n_items": size}, "model": {"maxlen": 4},
        "contract": {"sequence_length": 4}, "parity": {"parity_pass": True},
        "files": {n: {"sha256": hashlib.sha256((bundle / n).read_bytes()).hexdigest()}
                  for n in names},
    }), encoding="utf-8")
    return bundle


class _AdditiveSession:
    """A fake sequence model whose score is additive in the history.

    ``logits[j] = bias[j] + sum(weight[item][j] for item in history)``, plus an
    optional pairwise interaction. Without the interaction, removing one
    history title drops the score by exactly that title's weight, and removing
    a genre group drops it by the sum of its titles' weights, so removal
    effects can be checked against known truth.
    """

    def __init__(self, size, weights, interaction=None):
        self.size = size
        self.bias = np.linspace(1.0, 0.0, size)
        self.weights = weights            # {model item (dense + 1): np.array(size)}
        self.interaction = interaction    # (item_a, item_b, np.array(size)) or None
        self.calls = 0

    def run(self, _outputs, feeds):
        self.calls += 1
        items = feeds["items"]
        out = np.tile(self.bias, (items.shape[0], 1))
        for row in range(items.shape[0]):
            present = set(int(value) for value in items[row] if value)
            for item in present:
                out[row] += self.weights.get(item, 0.0)
            if self.interaction and {self.interaction[0], self.interaction[1]} <= present:
                out[row] += self.interaction[2]
        return [out.astype(np.float32)]


def _history(ids):
    return pd.DataFrame([
        {
            "Anime ID": anime_id, "Title": f"Title {anime_id:03d}",
            "Status": ["completed", "dropped", "plan_to_watch", "completed"][index % 4],
            "User Score": [9, 3, 0, 7][index % 4], "Episodes Watched": 12,
            "Is Rewatching": False,
            "Updated At": f"2026-09-0{index + 1}T10:00:00+00:00",
        }
        for index, anime_id in enumerate(ids)
    ])


def _weights(size):
    # History items 1-4 (model items 1-4). Distinct, signed effects per target.
    return {
        1: np.linspace(2.0, 1.0, size),
        2: np.linspace(-1.0, -0.5, size),
        3: np.full(size, 0.25),
        4: np.zeros(size),
    }


def _onnx_service(tmp_path, session):
    return RecommendationService(ranker=OnnxSequenceRankingEngine(
        _bundle(tmp_path, 12), session_factory=lambda _path: session
    ))


def _serve(service, history, count=4):
    return service.recommend(
        service.candidate_catalog(as_of=AS_OF), _profile_frame(),
        PipelineSettings(recommendation_count=count, candidate_pool_size=8,
                         top_anime_limit=12, randomness_factor=1),
        user_history=history, consumed_mal_ids={1, 4}, as_of=AS_OF,
        rated_history=history,
    )


def _brute_force_rank(session, history_items, target, eligible):
    """Rank ``target`` among ``eligible`` model items by re-sorting from scratch.

    Mirrors the engine's key: model score, then community mean (unavailable in
    this fixture, so equal), then MAL ID (equal to the model item here).
    """
    items = np.zeros((1, 4), dtype=np.int64)
    for offset, item in enumerate(history_items, start=4 - len(history_items)):
        items[0, offset] = item
    logits = session.run(["logits"], {"items": items})[0][0]
    order = sorted(eligible, key=lambda item: (-np.float32(logits[item - 1]), item))
    return order.index(target) + 1


def test_onnx_removal_effects_match_the_model_exactly(tmp_path):
    session = _AdditiveSession(12, _weights(12))
    feed = _serve(_onnx_service(tmp_path, session), _history([1, 2, 3, 4]))
    weights = _weights(12)
    genres = {item: ["Action", GENRE_POOL[item % 6]] for item in (1, 2, 3, 4)}
    eligible = list(range(5, 13))

    assert set(feed["Ranked Candidate Count"]) == {8}
    assert not feed["Match Score Available"].any()
    for _index, row in feed.iterrows():
        why = row["Explanation"]
        target = int(row["Anime ID"])
        column = target - 1
        assert why["method"] == "counterfactual-removal"
        assert why["unit"] == "model-score"
        # Removal effects overlap: no total, no baseline, no sum claim.
        assert why["total"] is None and why["baseline"] is None
        # The full-history run reproduces the ranking exactly.
        assert why["full_score"] == row["Recommendation Score"]
        assert why["full_rank"] == row["Model Rank"]
        assert why["ranked_candidate_count"] == 8
        assert why["history_window"] == 4
        # The strict API model accepts the shape unchanged.
        assert json.loads(Explanation.model_validate(why).model_dump_json()) == (
            json.loads(json.dumps(why))
        )

        # One title removed: the score drops by exactly that title's weight,
        # and the rank matches a from-scratch re-sort without it.
        for entry in why["influences"]:
            mal_id = entry["mal_id"]
            assert entry["value"] == pytest.approx(float(weights[mal_id][column]), abs=1e-5)
            remaining = [item for item in (1, 2, 3, 4) if item != mal_id]
            assert entry["rank_without"] == _brute_force_rank(
                session, remaining, target, eligible
            )
        assert {entry["mal_id"] for entry in why["influences"]} == {1, 2, 3, 4}

        # One genre removed: every history title in that genre goes at once.
        for segment in why["segments"]:
            assert segment["kind"] == "history-group"
            assert segment["facet"] == "genre"
            members = [item for item in (1, 2, 3, 4) if segment["label"] in genres[item]]
            assert segment["member_count"] == len(members)
            assert segment["value"] == pytest.approx(
                sum(float(weights[item][column]) for item in members), abs=1e-5
            )
            remaining = [item for item in (1, 2, 3, 4) if item not in members]
            assert segment["rank_without"] == _brute_force_rank(
                session, remaining, target, eligible
            )
            assert segment["taste"] is None

        statuses = {entry["mal_id"]: entry["list_status"] for entry in why["influences"]}
        assert statuses[2] == "dropped" and statuses[3] == "plan_to_watch"
        unrated = [entry for entry in why["influences"] if entry["mal_id"] == 3]
        assert unrated[0]["user_score"] is None


def test_onnx_removal_explanation_is_deterministic_under_interactions(tmp_path):
    def serve(root):
        session = _AdditiveSession(
            12, _weights(12), interaction=(1, 2, np.full(12, 3.0))
        )
        return _serve(_onnx_service(root, session), _history([1, 2, 3, 4]))

    first, again = serve(tmp_path / "a"), serve(tmp_path / "b")
    assert list(first["Explanation"]) == list(again["Explanation"])
    for why in first["Explanation"]:
        by_id = {entry["mal_id"]: entry["value"] for entry in why["influences"]}
        # With an interaction the single-title effects include it: removing
        # title 1 also removes the 1x2 bonus. Effects are not forced to add up.
        assert by_id[1] > 0


def test_onnx_explanation_failure_keeps_the_feed_and_says_unavailable(tmp_path):
    class BreaksOnShorterHistory(_AdditiveSession):
        def run(self, outputs, feeds):
            if int((feeds["items"] > 0).sum()) < 4:
                raise RuntimeError("counterfactual inference unavailable")
            return super().run(outputs, feeds)

    feed = _serve(
        _onnx_service(tmp_path, BreaksOnShorterHistory(12, _weights(12))),
        _history([1, 2, 3, 4]),
    )
    assert len(feed) == 4
    for why in feed["Explanation"]:
        assert why["method"] == "unavailable"
        assert why["unavailable_reason"] == "explanation-failed"
        assert why["segments"] == []


def test_fallback_rows_carry_the_answering_engines_explanation(tmp_path):
    def unavailable(_path):
        raise RuntimeError("runtime unavailable")

    service = RecommendationService(ranker=FallbackRankingEngine(
        OnnxSequenceRankingEngine(_bundle(tmp_path, 12), session_factory=unavailable),
        HeuristicRankingEngine(),
    ))
    candidates = service.candidate_catalog(as_of=AS_OF)
    feed = service.recommend(
        candidates, _profile_frame(),
        PipelineSettings(recommendation_count=4, candidate_pool_size=11,
                         top_anime_limit=12, randomness_factor=1),
        user_history=_history([1]), fallback_candidates=candidates,
        consumed_mal_ids={1}, as_of=AS_OF, rated_history=_completed(),
    )

    assert feed.attrs["ranking_engine"].fallback_used
    for why in feed["Explanation"]:
        assert why["method"] == "exact-additive"
        assert _segment_sum(why) == pytest.approx(why["total"], abs=1e-12)


# --- persistence and the strict API contract -------------------------------


def test_fit_and_why_survive_persistence_and_the_strict_api_model(system_temp_dir):
    result = _orchestrator(system_temp_dir).run_full("fixture-user", SETTINGS)
    store = ResultService(root_override=system_temp_dir / "results")
    store.save("fixture-user", result)
    loaded = store.load("fixture-user")

    assert loaded.recommendations == result.recommendations
    for model, original in zip(
        recommendation_view_models(loaded.recommendations), result.recommendations
    ):
        payload = view_model_to_dict(model)
        response = RecommendationViewModelResponse.model_validate(payload)
        assert response.fit_rank == original.model_rank
        assert response.fit_pool_size == original.ranked_candidate_count
        assert response.fit_top_percent == pytest.approx(
            100.0 * original.model_rank / original.ranked_candidate_count
        )
        assert response.personal_match_available is False
        assert response.why.method == "exact-additive"
        assert math.fsum(s.value for s in response.why.segments) == pytest.approx(
            response.why.total, abs=1e-12
        )
        assert json.loads(response.model_dump_json())["why"]["total"] == (
            pytest.approx(original.explanation["total"])
        )


def test_results_saved_before_this_change_still_load():
    legacy = {
        "schema_version": 1,
        "recommendations": [],
    }
    assert PipelineResult.from_dict(legacy).recommendations == ()


# --- review regressions -------------------------------------------------------


class _StubGraph:
    """A fixed MAL recommendation graph: similar viewers plus one sequel."""

    def build_graph(self, _seeds, _directory, **_kwargs):
        return {
            101: {
                "recommendations": [
                    {"mal_id": 505, "votes": 40},
                    {"mal_id": 519, "votes": 25},
                ],
                "related": [{"relation": "sequel", "mal_id": 511}],
            }
        }


def _graph_orchestrator(root):
    orchestrator = _orchestrator(root)
    orchestrator._anime_graph = _StubGraph()
    return orchestrator


def test_more_ranks_one_population_with_the_same_signals(system_temp_dir):
    orchestrator = _graph_orchestrator(system_temp_dir / "feed")
    initial = orchestrator.run_full("fixture-user", SETTINGS)
    more = orchestrator.run_more(
        "fixture-user", SETTINGS, existing_recommendations=initial.recommendations,
        count=6,
    )
    reference = _graph_orchestrator(system_temp_dir / "reference").run_full(
        "fixture-user",
        PipelineSettings(top_anime_limit=24, recommendation_count=24,
                         candidate_pool_size=24, randomness_factor=1),
    )
    order = {item.anime.mal_id: item for item in reference.recommendations}

    combined = more.recommendations
    ranks = [item.model_rank for item in combined]
    assert len(set(ranks)) == len(ranks), "two titles claim the same fit rank"
    assert {item.ranked_candidate_count for item in combined} == {len(order)}
    for item in combined:
        # Same population, same signals: each title's rank and score equal
        # the single full ordering of every eligible candidate.
        assert item.model_rank == order[item.anime.mal_id].model_rank
        assert item.raw_score == order[item.anime.mal_id].raw_score
        kinds = [segment["kind"] for segment in item.explanation["segments"]]
        assert "similar-viewers" in kinds
    # The franchise exclusion the first feed applied still holds in "more".
    assert 511 not in {item.anime.mal_id for item in combined}
    assert 511 not in order


def test_a_genre_vote_never_moves_a_same_named_source_or_type():
    completed = pd.DataFrame([
        {"Anime ID": 1, "Title": "Rated music-source drama", "Genres": ["Drama"],
         "Source": "music", "Media Type": "tv", "User Score": 9},
        {"Anime ID": 2, "Title": "Rated action", "Genres": ["Action"],
         "Source": "manga", "Media Type": "tv", "User Score": 4},
    ])
    candidates = pd.DataFrame([
        {"Anime ID": 10, "Title": "Cand MV", "Genres": ["Drama"], "Source": "music",
         "Media Type": "tv", "Mean Score": 8.0},
        {"Anime ID": 11, "Title": "Music genre title", "Genres": ["Music"],
         "Source": "manga", "Media Type": "tv", "Mean Score": 8.0},
    ])
    service = RecommendationService()
    profile = service.calculate_genre_importance(completed, candidates)
    settings = PipelineSettings(recommendation_count=2, candidate_pool_size=2,
                                top_anime_limit=2)

    def parts(adjustments):
        feed = service.recommend(candidates, profile, settings,
                                 genre_adjustments=adjustments, rated_history=completed)
        return {
            (int(row["Anime ID"]), segment["facet"], segment["label"]): segment
            for _i, row in feed.iterrows()
            for segment in row["Explanation"]["segments"]
            if segment["kind"] == "taste"
        }

    before, voted = parts(None), parts({"Music": 24.0})
    source_before = before[(10, "source", "music")]
    source_after = voted[(10, "source", "music")]
    assert source_after["taste"]["affinity"] == source_before["taste"]["affinity"]
    assert source_after["feedback_adjustment"] is None
    genre_part = voted[(11, "genre", "Music")]
    assert genre_part["feedback_adjustment"] == 24.0
    assert genre_part["value"] > 0


def test_onnx_ranks_resolve_exact_ties_like_the_engine(tmp_path):
    class TiedSession(_AdditiveSession):
        def __init__(self):
            super().__init__(12, {item: np.full(12, 0.5 * item) for item in (1, 2, 3, 4)})
            self.bias = np.ones(12)          # every candidate ties on score

    session = TiedSession()
    feed = _serve(_onnx_service(tmp_path, session), _history([1, 2, 3, 4]))
    eligible = list(range(5, 13))
    # Equal scores and unavailable community means fall back to MAL ID.
    assert [int(v) for v in feed["Anime ID"]] == [5, 6, 7, 8]
    for _index, row in feed.iterrows():
        why = row["Explanation"]
        target = int(row["Anime ID"])
        assert why["full_rank"] == row["Model Rank"] == eligible.index(target) + 1
        for entry in why["influences"]:
            remaining = [item for item in (1, 2, 3, 4) if item != entry["mal_id"]]
            assert entry["rank_without"] == _brute_force_rank(
                session, remaining, target, eligible
            )


def test_results_saved_before_personal_fit_still_load_and_serve():
    from AniRec.models import Recommendation

    legacy = {
        "schema_version": 1,
        "anime": {"schema_version": 1, "title": "Old pick", "mal_id": 9},
        "match_score": 73.25,
        "match_score_available": True,
        "raw_score": 0.41,
        "contributing_genres": ["Action"],
        "genre_contributions": [{"genre": "Action", "score": 73.25}],
        "reason": "Matches your interest in Action.",
        "rank": 1,
    }
    item = Recommendation.from_dict(legacy)
    assert item.model_rank is None and item.explanation is None
    payload = view_model_to_dict(recommendation_view_models((item,))[0])
    response = RecommendationViewModelResponse.model_validate(payload)
    assert response.fit_rank is None and response.why is None
    assert response.personal_match == 0.0 and response.personal_match_available is False
    assert response.genre_contributions == ()


def test_unknown_rated_history_is_reported_as_unknown_not_zero():
    feed = RecommendationService().recommend(
        _catalogue(), _profile_frame(),
        PipelineSettings(recommendation_count=4, candidate_pool_size=24,
                         top_anime_limit=24, randomness_factor=1),
    )
    taste = [
        segment["taste"]
        for why in feed["Explanation"]
        for segment in why["segments"]
        if segment["kind"] == "taste"
    ]
    assert taste
    assert all(t["rated_count"] is None and t["mean_user_score"] is None for t in taste)


# --- a feed and its "more" batches share one ranking, or "more" refuses -------


def _assert_one_ranking(recommendations):
    ranks = [item.model_rank for item in recommendations]
    assert len(set(ranks)) == len(ranks), "two titles claim the same fit rank"
    assert len({item.ranked_candidate_count for item in recommendations}) == 1


def _more(orchestrator, initial, **options):
    return orchestrator.run_more(
        "fixture-user", SETTINGS, existing_recommendations=initial.recommendations,
        count=6, **options,
    )


def test_restoring_a_hidden_title_does_not_split_the_ranking(system_temp_dir):
    orchestrator = _orchestrator(system_temp_dir)
    reference = _orchestrator(system_temp_dir / "reference").run_full(
        "fixture-user",
        PipelineSettings(top_anime_limit=24, recommendation_count=1,
                         candidate_pool_size=24, randomness_factor=1),
    )
    top = reference.recommendations[0].anime.mal_id
    initial = orchestrator.run_full("fixture-user", SETTINGS, excluded_mal_ids={top})
    more = _more(orchestrator, initial, excluded_mal_ids=set())   # "Show again"

    _assert_one_ranking(more.recommendations)
    # Hidden at generation, so absent from this ranking until the next full run.
    assert top not in {item.anime.mal_id for item in more.recommendations}


def test_hiding_a_title_after_the_feed_skips_it_without_reranking(system_temp_dir):
    orchestrator = _orchestrator(system_temp_dir)
    initial = orchestrator.run_full("fixture-user", SETTINGS)
    shown = {item.anime.mal_id for item in initial.recommendations}
    hidden_later = next(
        mal_id for mal_id in range(500, 524) if mal_id not in shown
    )
    more = _more(orchestrator, initial, excluded_mal_ids={hidden_later})

    _assert_one_ranking(more.recommendations)
    assert hidden_later not in {item.anime.mal_id for item in more.recommendations}


def test_more_refuses_after_a_sync_changed_the_list(system_temp_dir):
    completed = {"frame": _completed()}
    orchestrator = PipelineOrchestrator(
        anime_data=AnimeDataService(
            top_fetcher=lambda **_kwargs: _catalogue(),
            completed_fetcher=lambda *_args, **_kwargs: completed["frame"],
        ),
        profiles=ProfileService(root_override=system_temp_dir / "app-data", clock=lambda: NOW),
        recommendations=RecommendationService(),
        storage=CsvStorage(),
        access_token_provider=lambda: "fake-access-token",
        clock=lambda: NOW,
    )
    initial = orchestrator.run_full("fixture-user", SETTINGS)
    newly_completed = _completed().iloc[[0]].assign(
        **{"Anime ID": 509, "Title": "Catalogue 09", "User Score": 8}
    )
    completed["frame"] = pd.concat([_completed(), newly_completed], ignore_index=True)
    orchestrator.run_sync("fixture-user", SETTINGS)

    from AniRec.errors import DataError

    with pytest.raises(DataError, match="Generate a new feed"):
        _more(orchestrator, initial)


def test_more_refuses_when_feedback_changed_since_the_feed(system_temp_dir):
    from AniRec.errors import DataError

    orchestrator = _orchestrator(system_temp_dir)
    initial = orchestrator.run_full("fixture-user", SETTINGS)
    with pytest.raises(DataError, match="Generate a new feed"):
        _more(orchestrator, initial, genre_adjustments={"Comedy": 6.0})


def test_more_refuses_when_the_ranking_engine_changed(system_temp_dir):
    from AniRec.errors import DataError

    class NewerHeuristic(HeuristicRankingEngine):
        engine_version = "2"

    initial = _orchestrator(system_temp_dir).run_full("fixture-user", SETTINGS)
    upgraded = _orchestrator(
        system_temp_dir, RecommendationService(ranker=NewerHeuristic())
    )
    with pytest.raises(DataError, match="ranking engine changed"):
        _more(upgraded, initial)


def test_single_step_regeneration_starts_a_ranking_more_can_continue(system_temp_dir):
    orchestrator = _orchestrator(system_temp_dir)
    orchestrator.run_full("fixture-user", SETTINGS)
    step = orchestrator.run_step("generate_recommendations", "fixture-user", SETTINGS)
    more = _more(orchestrator, step)

    _assert_one_ranking(more.recommendations)


def test_more_refuses_a_feed_that_is_not_the_snapshots(system_temp_dir):
    """An older feed next to a newer snapshot (a feed generated but never saved,
    or a stale client) must not be extended with the newer ranking."""
    from AniRec.errors import DataError

    orchestrator = _orchestrator(system_temp_dir)
    older = orchestrator.run_full("fixture-user", SETTINGS)
    newer = orchestrator.run_full(
        "fixture-user", SETTINGS, excluded_mal_ids={older.recommendations[0].anime.mal_id}
    )
    assert older.recommendations[0].ranking_id != newer.recommendations[0].ranking_id

    with pytest.raises(DataError, match="Generate a new feed"):
        _more(orchestrator, older)
    more = _more(orchestrator, newer)
    assert {item.ranking_id for item in more.recommendations} == {
        newer.recommendations[0].ranking_id
    }
    payload = view_model_to_dict(recommendation_view_models(more.recommendations)[0])
    assert RecommendationViewModelResponse.model_validate(payload).ranking_id == (
        newer.recommendations[0].ranking_id
    )


@pytest.mark.parametrize(
    "changed",
    [
        {"include_nsfw": True},
        {"minimum_mean_score": 8.5},
    ],
    ids=["nsfw-toggled", "minimum-score-raised"],
)
def test_more_refuses_when_eligibility_filters_changed(system_temp_dir, changed):
    """The Settings page can change which titles may be ranked at all; "more"
    must not continue the old ranking under different filters (and must never
    serve NSFW titles the reader just switched off)."""
    from dataclasses import replace

    from AniRec.errors import DataError

    orchestrator = _orchestrator(system_temp_dir)
    initial = orchestrator.run_full("fixture-user", SETTINGS)
    with pytest.raises(DataError, match="Generate a new feed"):
        orchestrator.run_more(
            "fixture-user", replace(SETTINGS, **changed),
            existing_recommendations=initial.recommendations, count=6,
        )


def test_web_generate_and_more_are_saved_for_the_feed_to_show(system_temp_dir):
    """The web client reloads the saved feed when an operation finishes; the
    API must persist each result or "Recommend 5 more" silently shows nothing."""
    from types import SimpleNamespace

    from AniRec.api.app import _build_handler
    from AniRec.api.models import OperationStartRequest
    from AniRec.application.pipeline import CancellationToken
    from AniRec.services import RecommendationStateService

    orchestrator = _orchestrator(system_temp_dir)
    profile_id = orchestrator._profiles.resolve_profile("fixture-user").profile_id
    root = system_temp_dir / "app-data"
    services = SimpleNamespace(
        settings=SimpleNamespace(
            load=lambda: SimpleNamespace(pipeline=SETTINGS, client_id=None)
        ),
        orchestrator=orchestrator,
        results=ResultService(root_override=root),
        recommendation_state=RecommendationStateService(root_override=root),
        cover_urls=CoverUrlService(root_override=root),
    )

    def run(kind, **payload):
        handler = _build_handler(
            services, kind, OperationStartRequest(**payload), "fixture-user", profile_id
        )
        return handler(CancellationToken(), lambda _progress: None)

    run("recommendation")
    saved = services.results.load(profile_id)
    assert len(saved.recommendations) == SETTINGS.recommendation_count

    run("more-recommendations", count=4)
    extended = services.results.load(profile_id)
    assert len(extended.recommendations) == SETTINGS.recommendation_count + 4
    _assert_one_ranking(extended.recommendations)


def test_each_row_records_the_selection_it_was_chosen_under(system_temp_dir):
    from dataclasses import replace

    from AniRec.scoring.selection import SELECTION_POLICY_VERSION

    orchestrator = _orchestrator(system_temp_dir)
    initial = orchestrator.run_full("fixture-user", SETTINGS)          # adventurousness 10
    more = orchestrator.run_more(
        "fixture-user", replace(SETTINGS, randomness_factor=3),
        existing_recommendations=initial.recommendations, count=4,
    )
    first, added = more.recommendations[:6], more.recommendations[6:]
    assert {(item.selection_policy, item.adventurousness) for item in first} == {
        (SELECTION_POLICY_VERSION, 10)
    }
    assert {(item.selection_policy, item.adventurousness) for item in added} == {
        (SELECTION_POLICY_VERSION, 3)
    }
    # Adventurousness shapes selection, not ranking: one ranking throughout.
    _assert_one_ranking(more.recommendations)


def test_single_step_generation_honours_hidden_titles(system_temp_dir):
    orchestrator = _orchestrator(system_temp_dir)
    initial = orchestrator.run_full("fixture-user", SETTINGS)
    hidden = initial.recommendations[0].anime.mal_id

    step = orchestrator.run_step(
        "generate_recommendations", "fixture-user", SETTINGS, excluded_mal_ids={hidden}
    )
    assert hidden not in {item.anime.mal_id for item in step.recommendations}

    more = orchestrator.run_more(
        "fixture-user", SETTINGS, existing_recommendations=step.recommendations,
        excluded_mal_ids={hidden}, count=4,
    )
    assert hidden not in {item.anime.mal_id for item in more.recommendations}
    _assert_one_ranking(more.recommendations)


def test_generation_honours_saved_hidden_titles_without_the_caller_passing_them(system_temp_dir):
    """The CLI calls run_step/run_full with no hidden set; the pipeline must
    read the profile's own saved state rather than serve a hidden title."""
    from AniRec.services import RecommendationStateService

    orchestrator = _orchestrator(system_temp_dir)
    profile_id = orchestrator._profiles.resolve_profile("fixture-user").profile_id
    first = orchestrator.run_full("fixture-user", SETTINGS)
    hidden = first.recommendations[0].anime.mal_id
    RecommendationStateService(root_override=system_temp_dir / "app-data").set_hidden(
        profile_id, hidden, True
    )

    step = orchestrator.run_step("generate_recommendations", "fixture-user", SETTINGS)
    full = orchestrator.run_full("fixture-user", SETTINGS)
    assert hidden not in {item.anime.mal_id for item in step.recommendations}
    assert hidden not in {item.anime.mal_id for item in full.recommendations}
    # And "more" with no hidden set passed continues the ranking unchanged.
    more = orchestrator.run_more(
        "fixture-user", SETTINGS, existing_recommendations=full.recommendations, count=4
    )
    assert hidden not in {item.anime.mal_id for item in more.recommendations}
    _assert_one_ranking(more.recommendations)


def test_an_older_feeds_ranking_stays_resolvable_after_regeneration(system_temp_dir):
    orchestrator = _orchestrator(system_temp_dir)
    older = orchestrator.run_full("fixture-user", SETTINGS)
    older_id = older.recommendations[0].ranking_id
    newer = orchestrator.run_full(
        "fixture-user", SETTINGS, excluded_mal_ids={older.recommendations[0].anime.mal_id}
    )
    assert newer.recommendations[0].ranking_id != older_id

    resolved = orchestrator.ranking_snapshot("fixture-user", older_id)
    assert resolved is not None
    assert resolved["ranking_id"] == older_id
    assert resolved["hidden"] == set()
    assert resolved["engine"].startswith("heuristic:1:primary:")
    assert json.loads(resolved["filters"]) == {
        "include_nsfw": SETTINGS.include_nsfw,
        "minimum_mean_score": SETTINGS.minimum_mean_score,
    }
    assert orchestrator.ranking_snapshot("fixture-user", "0" * 24) is None


def test_a_snapshot_referenced_by_an_event_outlives_the_archive_window(system_temp_dir):
    import os
    from uuid import uuid4

    from AniRec.services.recommendation_event_service import RecommendationEventService

    orchestrator = _orchestrator(system_temp_dir)
    profile_id = orchestrator._profiles.resolve_profile("fixture-user").profile_id
    older = orchestrator.run_full("fixture-user", SETTINGS)
    ranking_id = older.recommendations[0].ranking_id
    archive = (
        orchestrator._profiles.directory(profile_id) / "ranking_snapshots" / f"{ranking_id}.csv"
    )
    # Generated 100 days before the pipeline clock: past the 90-day window.
    long_ago = NOW.timestamp() - 100 * 86400
    os.utime(archive, (long_ago, long_ago))

    events = RecommendationEventService(system_temp_dir / "app-data")
    events.set_enabled(profile_id, True)
    assert events.record(
        profile_id, request_id=str(uuid4()), feed_id="a" * 64, action="impression",
        mal_id=older.recommendations[0].anime.mal_id, position=1, model_rank=1,
        surface="web_cards", ranking_id=ranking_id,
    )
    # A later generation prunes expired archives, but not one an event references.
    orchestrator.run_full(
        "fixture-user", SETTINGS, excluded_mal_ids={older.recommendations[0].anime.mal_id}
    )
    assert archive.exists()
    assert orchestrator.ranking_snapshot("fixture-user", ranking_id)["ranking_id"] == ranking_id


def test_votes_are_collected_but_never_change_what_is_recommended(system_temp_dir):
    """D-013: until feeding is decided, likes and dislikes must not move the
    ranking, the selection or the explanations of any generated feed."""
    from types import SimpleNamespace

    from AniRec.api.app import _build_handler
    from AniRec.api.models import OperationStartRequest
    from AniRec.application.pipeline import CancellationToken
    from AniRec.services import RecommendationStateService

    def generate(root, votes):
        orchestrator = _orchestrator(root)
        profile_id = orchestrator._profiles.resolve_profile("fixture-user").profile_id
        state = RecommendationStateService(root_override=root / "app-data")
        for mal_id, sentiment in votes:
            state.set_feedback(profile_id, mal_id, sentiment, genres=("Comedy",))
        services = SimpleNamespace(
            settings=SimpleNamespace(load=lambda: SimpleNamespace(pipeline=SETTINGS, client_id=None)),
            orchestrator=orchestrator,
            results=ResultService(root_override=root / "app-data"),
            recommendation_state=state,
            cover_urls=CoverUrlService(root_override=root / "app-data"),
        )
        for kind, payload in (("recommendation", {}), ("more-recommendations", {"count": 4})):
            _build_handler(
                services, kind, OperationStartRequest(**payload), "fixture-user", profile_id
            )(CancellationToken(), lambda _progress: None)
        return services.results.load(profile_id).recommendations

    plain = generate(system_temp_dir / "plain", [])
    voted = generate(system_temp_dir / "voted", [(503, "liked"), (507, "disliked"), (512, "liked")])

    def essence(items):
        return [(item.anime.mal_id, item.model_rank, item.raw_score, item.explanation)
                for item in items]

    assert essence(voted) == essence(plain)


# -- automatic refresh (D-018) ---------------------------------------------


def _refresh(orchestrator, existing, count=6):
    return orchestrator.run_refresh(
        "fixture-user", SETTINGS, existing=existing, count=count
    )


def test_refresh_without_a_feed_generates_one_that_more_can_continue(system_temp_dir):
    orchestrator = _orchestrator(system_temp_dir)
    refreshed = _refresh(orchestrator, None, count=5)

    assert refreshed.user_stats["feed_refresh"] == "missing"
    assert len(refreshed.recommendations) == 5
    more = _more(orchestrator, refreshed)
    _assert_one_ranking(more.recommendations)


def test_refresh_keeps_a_current_feed_untouched(system_temp_dir):
    orchestrator = _orchestrator(system_temp_dir)
    initial = _refresh(orchestrator, None)
    again = _refresh(orchestrator, initial)

    assert again.user_stats["feed_refresh"] == "current"
    # No recommendations: saving it keeps the feed and its ranking as they were.
    assert again.recommendations == ()
    saved = ResultService(root_override=system_temp_dir / "app-data")
    profile_id = orchestrator._profiles.resolve_profile("fixture-user").profile_id
    saved.save(profile_id, initial)
    merged = saved.save_merged(profile_id, again)
    assert [item.ranking_id for item in merged.recommendations] == [
        item.ranking_id for item in initial.recommendations
    ]
    _more(orchestrator, merged)   # still continuable


def test_refresh_rebuilds_when_the_synced_list_changed(system_temp_dir):
    completed = {"frame": _completed()}
    orchestrator = PipelineOrchestrator(
        anime_data=AnimeDataService(
            top_fetcher=lambda **_kwargs: _catalogue(),
            completed_fetcher=lambda *_args, **_kwargs: completed["frame"],
        ),
        profiles=ProfileService(root_override=system_temp_dir / "app-data", clock=lambda: NOW),
        recommendations=RecommendationService(),
        storage=CsvStorage(),
        access_token_provider=lambda: "fake-access-token",
        clock=lambda: NOW,
    )
    initial = _refresh(orchestrator, None)
    newly_completed = _completed().iloc[[0]].assign(
        **{"Anime ID": 509, "Title": "Catalogue 09", "User Score": 8}
    )
    completed["frame"] = pd.concat([_completed(), newly_completed], ignore_index=True)

    refreshed = _refresh(orchestrator, initial)
    assert refreshed.user_stats["feed_refresh"] == "inputs-changed"
    assert refreshed.recommendations[0].ranking_id != initial.recommendations[0].ranking_id
    assert 509 not in {item.anime.mal_id for item in refreshed.recommendations}


def test_refresh_rebuilds_when_a_different_engine_would_rank(system_temp_dir):
    class NewerHeuristic(HeuristicRankingEngine):
        engine_version = "2"

    initial = _refresh(_orchestrator(system_temp_dir), None)
    upgraded = _orchestrator(system_temp_dir, RecommendationService(ranker=NewerHeuristic()))
    refreshed = _refresh(upgraded, initial)

    assert refreshed.user_stats["feed_refresh"] == "engine-changed"
    _more(upgraded, refreshed)   # the rebuilt feed is the new engine's ranking


def test_refresh_rebuilds_a_feed_that_predates_ranking_snapshots(system_temp_dir):
    from dataclasses import replace

    orchestrator = _orchestrator(system_temp_dir)
    current = _refresh(orchestrator, None)
    legacy = replace(current, recommendations=tuple(
        replace(item, ranking_id=None) for item in current.recommendations
    ))
    assert _refresh(orchestrator, legacy).user_stats["feed_refresh"] == "inputs-changed"


def test_the_api_accepts_refresh_as_a_feed_writing_operation(tmp_path):
    from fastapi.testclient import TestClient

    from AniRec.api.app import FEED_WRITING_KINDS, SUPPORTED_KINDS, WEB_FEED_BATCH, create_app

    assert "refresh" in SUPPORTED_KINDS and "refresh" in FEED_WRITING_KINDS
    assert WEB_FEED_BATCH == 50
    with TestClient(create_app(root_override=str(tmp_path))) as client:
        # No active profile: refused as a state conflict, not as an unknown kind.
        response = client.post("/api/operations/refresh", json={}, headers={"Origin": "http://127.0.0.1:5173"})
    assert response.status_code == 409


def _mutable_orchestrator(root, completed, recommendations=None):
    return PipelineOrchestrator(
        anime_data=AnimeDataService(
            top_fetcher=lambda **_kwargs: _catalogue(),
            completed_fetcher=lambda *_args, **_kwargs: completed["frame"],
        ),
        profiles=ProfileService(root_override=root / "app-data", clock=lambda: NOW),
        recommendations=recommendations or RecommendationService(),
        storage=CsvStorage(),
        access_token_provider=lambda: "fake-access-token",
        clock=lambda: NOW,
    )


def _with_community_columns(frame, drift=0):
    # Real MAL rows carry community fields that move every day.
    return frame.assign(
        **{
            "Mean Score": [7.1 + (index % 5) / 10 + drift / 100 for index in range(len(frame))],
            "Scoring Users": [100_000 + index * 7 + drift for index in range(len(frame))],
        }
    )


def test_refresh_ignores_daily_community_drift_in_the_list(system_temp_dir):
    completed = {"frame": _with_community_columns(_completed())}
    orchestrator = _mutable_orchestrator(system_temp_dir, completed)
    initial = _refresh(orchestrator, None)

    completed["frame"] = _with_community_columns(_completed(), drift=3)
    again = _refresh(orchestrator, initial)

    assert again.user_stats["feed_refresh"] == "current"
    assert again.recommendations == () and again.started_at is None


def test_refresh_rebuilds_when_the_reader_rescored_a_title(system_temp_dir):
    completed = {"frame": _with_community_columns(_completed())}
    orchestrator = _mutable_orchestrator(system_temp_dir, completed)
    initial = _refresh(orchestrator, None)

    rescored = _with_community_columns(_completed())
    rescored.loc[0, "User Score"] = 1 if rescored.loc[0, "User Score"] != 1 else 10
    completed["frame"] = rescored
    assert _refresh(orchestrator, initial).user_stats["feed_refresh"] == "inputs-changed"


def test_a_refresh_rebuild_ranks_exactly_as_a_full_run(system_temp_dir):
    """Taste from real ratings, fresh similar-viewer and franchise signals."""
    rebuilt = _refresh(_graph_orchestrator(system_temp_dir / "refresh"), None, count=6)
    full = _graph_orchestrator(system_temp_dir / "full").run_full("fixture-user", SETTINGS)

    def ranking(result):
        return [(item.anime.mal_id, item.model_rank, item.ranked_candidate_count)
                for item in result.recommendations]

    assert ranking(rebuilt) == ranking(full)
    assert [(stat.genre, stat.importance_score) for stat in rebuilt.genre_stats] == [
        (stat.genre, stat.importance_score) for stat in full.genre_stats
    ]


def test_engine_identity_names_the_model_before_it_has_ranked(system_temp_dir):
    """A restart must not look like a model change (the version was "unloaded")."""
    engine = OnnxSequenceRankingEngine(_bundle(system_temp_dir, 12), session_factory=lambda _path: None)
    service = RecommendationService(ranker=FallbackRankingEngine(engine, HeuristicRankingEngine()))

    assert service.engine_identity() == ("sasrec-onnx", "abcdef123456")


# -- refresh review (D-018): engine identity and unavailable history --------

class _DecliningPreferred:
    """A preferred engine that loads, then declines this reader, so the
    fallback ranks. Mirrors a sequence model with no usable history."""

    engine_id = "declining-model"
    feature_schema_version = "test"

    def __init__(self, version="v1", requires_history=False):
        self.engine_version = version
        self.requires_user_history = requires_history

    def eligibility_context(self):
        from AniRec.scoring.eligibility import EligibilityContext
        return EligibilityContext()

    def rank(self, _request):
        from AniRec.scoring.engines import RankingEngineUnavailable
        raise RankingEngineUnavailable("This reader has no usable history.")


def _declining_service(version="v1", requires_history=False):
    return RecommendationService(ranker=FallbackRankingEngine(
        _DecliningPreferred(version, requires_history), HeuristicRankingEngine()
    ))


def test_a_fallback_feed_is_current_while_the_same_preferred_engine_declines(system_temp_dir):
    """A per-reader fallback must not read as an engine change on every refresh."""
    orchestrator = _orchestrator(system_temp_dir, _declining_service())
    initial = _refresh(orchestrator, None)
    assert initial.user_stats["ranking_fallback_used"] == 1

    again = _refresh(orchestrator, initial)
    assert again.user_stats["feed_refresh"] == "current"
    assert again.recommendations == ()


def test_a_fallback_feed_rebuilds_when_the_preferred_engine_changes(system_temp_dir):
    initial = _refresh(_orchestrator(system_temp_dir, _declining_service("v1")), None)
    upgraded = _orchestrator(system_temp_dir, _declining_service("v2"))
    assert _refresh(upgraded, initial).user_stats["feed_refresh"] == "engine-changed"


def test_a_fallback_feed_rebuilds_once_the_preferred_engine_can_load(system_temp_dir):
    """D-018: a feed the fallback ranked because the model could not load is
    rebuilt when it can."""
    from AniRec.scoring.engines import RankingEngineUnavailable

    class Unloadable(_DecliningPreferred):
        def eligibility_context(self):
            raise RankingEngineUnavailable("No bundle installed.")

    unloadable = RecommendationService(ranker=FallbackRankingEngine(Unloadable(), HeuristicRankingEngine()))
    initial = _refresh(_orchestrator(system_temp_dir, unloadable), None)
    assert _refresh(_orchestrator(system_temp_dir, unloadable), initial).user_stats["feed_refresh"] == "current"
    loadable = _orchestrator(system_temp_dir, _declining_service())
    assert _refresh(loadable, initial).user_stats["feed_refresh"] == "engine-changed"


def _refresh_history():
    return pd.DataFrame([
        {"Anime ID": mal_id, "Status": "completed", "User Score": score,
         "Episodes Watched": 12, "Is Rewatching": False,
         "Updated At": f"2026-09-{day:02d}T10:00:00+00:00"}
        for day, (mal_id, score) in enumerate([(101, 10), (102, 9), (103, 7)], start=1)
    ])


def test_a_failed_history_fetch_keeps_the_feed_instead_of_rebuilding_without_history(system_temp_dir):
    """A transient failure is not a changed list: it must not swap the feed
    for one ranked without the reader's history."""
    from AniRec.errors import NetworkError

    history = {"fetch": _refresh_history}
    def fetch_history(*_args, **_kwargs):
        return history["fetch"]()

    orchestrator = PipelineOrchestrator(
        anime_data=AnimeDataService(
            top_fetcher=lambda **_kwargs: _catalogue(),
            completed_fetcher=lambda *_args, **_kwargs: _completed(),
            history_fetcher=fetch_history,
        ),
        profiles=ProfileService(root_override=system_temp_dir / "app-data", clock=lambda: NOW),
        recommendations=_declining_service(requires_history=True),
        storage=CsvStorage(),
        access_token_provider=lambda: "fake-access-token",
        clock=lambda: NOW,
    )
    initial = _refresh(orchestrator, None)
    directory = orchestrator._profiles.directory(orchestrator._profiles.resolve_profile("fixture-user").profile_id)
    saved_history = (directory / "user_history.csv").read_bytes()

    def fail():
        raise NetworkError("offline")
    history["fetch"] = fail
    again = _refresh(orchestrator, initial)

    assert again.user_stats["feed_refresh"] == "current"
    assert again.recommendations == ()
    assert (directory / "user_history.csv").read_bytes() == saved_history


def test_the_refresh_digest_survives_a_csv_round_trip_of_missing_values(system_temp_dir):
    """Fetched frames and the same frames read back from CSV digest alike,
    including missing timestamps (NaT) and nullable integers (<NA>)."""
    directory = system_temp_dir / "digest"
    directory.mkdir()
    for name in ("genre_importance.csv", "recommendation_candidates.csv"):
        (directory / name).write_text("a\n1\n", encoding="utf-8")
    history = pd.DataFrame({
        "Anime ID": pd.array([1, 2], dtype="Int64"),
        "Status": ["completed", None],
        "User Score": pd.array([8, pd.NA], dtype="Int64"),
        "Episodes Watched": [12.0, float("nan")],
        "Is Rewatching": [False, True],
        "Updated At": pd.to_datetime(["2026-09-01T10:00:00+00:00", None], utc=True),
    })
    completed = history[["Anime ID", "Status", "User Score"]]
    frames = {"completed_anime.csv": completed, "user_history.csv": history}
    CsvStorage().write_batch((
        (completed, directory / "completed_anime.csv"),
        (history, directory / "user_history.csv"),
    ))
    orchestrator = _orchestrator(system_temp_dir)

    assert orchestrator._user_inputs_digest(directory, frames, None) == orchestrator._ranking_inputs_digest(directory, None)
