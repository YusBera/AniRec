"""The collaborative signal, its request budget, and its fallback behaviour."""

from __future__ import annotations

import pandas as pd
import pytest

from recommendation_system import rank_recommendations
from scoring.collaborative import (
    collaborative_scores,
    franchise_exclusions,
    select_seeds,
)
from services.anime_graph_service import AnimeGraphService


def _node(mal_id, recommendations=(), related=()):
    return {
        "id": mal_id,
        "recommendations": [
            {"node": {"id": target}, "num_recommendations": votes}
            for target, votes in recommendations
        ],
        "related_anime": [
            {"node": {"id": target}, "relation_type": relation}
            for target, relation in related
        ],
    }


class _RecordingClient:
    """Stands in for MALClient and counts what the service asks for."""

    def __init__(self, payloads):
        self.payloads = payloads
        self.requested: list[str] = []

    def get_json(self, url, *, params=None, access_token=None, client_id=None, cancellation=None):
        self.requested.append(url)
        mal_id = int(url.rsplit("/", 1)[-1])
        return self.payloads.get(mal_id, {"id": mal_id})


# ---------------------------------------------------------------------------
# Seed selection
# ---------------------------------------------------------------------------


def test_only_above_average_titles_seed_the_walk():
    seeds = select_seeds([(1, 1.4), (2, -0.9), (3, 0.2), (4, 0.0)])

    assert [mal_id for mal_id, _weight in seeds] == [1, 3]


def test_seeds_are_capped_so_the_request_budget_stays_bounded():
    rated = [(index, float(index)) for index in range(1, 200)]

    seeds = select_seeds(rated, limit=40)

    assert len(seeds) == 40
    # The strongest ratings are the ones worth spending requests on.
    assert seeds[0][0] == 199


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def test_votes_are_normalised_per_seed():
    """A seed with many edges must not outvote one with few."""
    graph = {
        1: {"recommendations": [{"mal_id": 10, "votes": 5}]},
        2: {
            "recommendations": [
                {"mal_id": 20, "votes": 500},
                {"mal_id": 21, "votes": 500},
            ]
        },
    }

    scores = collaborative_scores([(1, 1.0), (2, 1.0)], graph)

    # Seed 1 points all of its weight at one title; seed 2 splits its weight.
    assert scores[10] > scores[20]
    assert scores[20] == pytest.approx(scores[21])


def test_seeds_never_recommend_themselves():
    graph = {1: {"recommendations": [{"mal_id": 2, "votes": 10}, {"mal_id": 1, "votes": 90}]}}

    scores = collaborative_scores([(1, 1.0)], graph)

    assert 1 not in scores
    assert 2 in scores


def test_scores_stay_bounded_by_the_evidence_behind_them():
    graph = {index: {"recommendations": [{"mal_id": 99, "votes": 10}]} for index in range(1, 11)}
    seeds = [(index, 1.0) for index in range(1, 11)]

    scores = collaborative_scores(seeds, graph)

    assert 0.0 < scores[99] <= 1.0


def test_no_seeds_yields_no_scores():
    assert collaborative_scores([], {1: {"recommendations": []}}) == {}


# ---------------------------------------------------------------------------
# Franchise handling
# ---------------------------------------------------------------------------


def test_sequels_are_withheld_rather_than_recommended():
    graph = {
        1: {
            "related": [
                {"mal_id": 2, "relation": "sequel"},
                {"mal_id": 3, "relation": "prequel"},
                {"mal_id": 4, "relation": "other"},
            ]
        }
    }

    excluded = franchise_exclusions(graph)

    assert excluded == {2, 3}


# ---------------------------------------------------------------------------
# Request budget and caching
# ---------------------------------------------------------------------------


def test_one_request_per_seed_and_none_for_cached_entries(system_temp_dir):
    client = _RecordingClient({1: _node(1, [(10, 5)]), 2: _node(2, [(20, 7)])})
    service = AnimeGraphService(client=client, sleep=lambda _seconds: None)

    first = service.build_graph([1, 2], system_temp_dir)
    assert len(client.requested) == 2
    assert set(first) == {1, 2}

    # A second run reuses the cache and asks for nothing further.
    reused = AnimeGraphService(client=client, sleep=lambda _seconds: None)
    second = reused.build_graph([1, 2], system_temp_dir)

    assert len(client.requested) == 2
    assert set(second) == {1, 2}


def test_a_cancelled_walk_keeps_what_it_already_fetched(system_temp_dir):
    class _Cancels:
        def __init__(self):
            self.calls = 0

        @property
        def is_cancelled(self):
            self.calls += 1
            return self.calls > 2

    client = _RecordingClient({index: _node(index, [(100 + index, 5)]) for index in range(1, 6)})
    service = AnimeGraphService(client=client, sleep=lambda _seconds: None)

    service.build_graph([1, 2, 3, 4, 5], system_temp_dir, cancellation=_Cancels())

    # Whatever was gathered before cancelling is persisted, so resuming does
    # not start from the beginning.
    assert service.load_cache(system_temp_dir)


def test_a_damaged_cache_is_discarded_rather_than_raising(system_temp_dir):
    service = AnimeGraphService()
    service.cache_path(system_temp_dir).write_text("{ not json", encoding="utf-8")

    assert service.load_cache(system_temp_dir) == {}


def test_stale_entries_are_ignored(system_temp_dir):
    now = [1_000_000.0]
    service = AnimeGraphService(clock=lambda: now[0])
    service.save_cache(
        system_temp_dir, {1: {"fetched_at": now[0], "recommendations": [], "related": []}}
    )

    assert service.load_cache(system_temp_dir)

    now[0] += 400 * 24 * 60 * 60
    assert service.load_cache(system_temp_dir) == {}


# ---------------------------------------------------------------------------
# Integration with ranking
# ---------------------------------------------------------------------------


def _candidates():
    return pd.DataFrame(
        [
            {"Anime ID": 10, "Title": "Endorsed", "Genres": ["Action"], "Mean Score": 8.0},
            {"Anime ID": 11, "Title": "Ignored", "Genres": ["Action"], "Mean Score": 8.0},
        ]
    )


def _weights():
    return pd.DataFrame([{"Genre": "Action", "Importance_Score": 50.0}])


def test_collaborative_support_raises_a_candidate():
    options = dict(
        num_recommendations=2, top_anime_count=2, randomness_factor=1, random_state=3
    )
    baseline = rank_recommendations(_candidates(), _weights(), **options)
    boosted = rank_recommendations(
        _candidates(), _weights(), collaborative_scores={10: 0.9}, **options
    )

    baseline_scores = dict(zip(baseline["Anime ID"], baseline["Match Score"]))
    boosted_scores = dict(zip(boosted["Anime ID"], boosted["Match Score"]))

    assert baseline_scores[10] == pytest.approx(baseline_scores[11])
    assert boosted_scores[10] > boosted_scores[11]


def test_every_title_in_a_batch_is_scored_on_the_same_blend():
    """Carrying an extra signal must never cost a title its ranking.

    Choosing the blend per title rather than per batch reweights the terms
    differently for each row, so a title with collaborative support could be
    scored with a smaller content weight than one without, and lose on the
    signal it was strongest on.
    """
    result = rank_recommendations(
        _candidates(),
        _weights(),
        collaborative_scores={10: 0.9},
        num_recommendations=2,
        top_anime_count=2,
        randomness_factor=1,
        random_state=3,
    )
    scores = dict(zip(result["Anime ID"], result["Match Score"]))

    assert scores[10] > scores[11]


def test_ranking_works_unchanged_when_the_graph_is_unavailable():
    options = dict(
        num_recommendations=2, top_anime_count=2, randomness_factor=1, random_state=3
    )
    without = rank_recommendations(_candidates(), _weights(), **options)
    empty = rank_recommendations(
        _candidates(), _weights(), collaborative_scores={}, **options
    )

    assert without["Match Score"].tolist() == empty["Match Score"].tolist()


def test_the_collaborative_share_is_named_in_the_breakdown():
    result = rank_recommendations(
        _candidates(),
        _weights(),
        collaborative_scores={10: 0.9},
        num_recommendations=2,
        top_anime_count=2,
        randomness_factor=1,
        random_state=3,
    )
    row = result[result["Anime ID"] == 10].iloc[0]
    breakdown = dict(row["Genre Contributions"])

    assert "Similar viewers" in breakdown
    assert sum(row["Genre Contributions"][i][1] for i in range(len(row["Genre Contributions"]))) == pytest.approx(
        row["Match Score"], abs=0.01
    )
