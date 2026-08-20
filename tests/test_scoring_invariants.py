"""Properties the recommendation engine must satisfy, independent of formula.

These were written as the executable specification for the 2.0 scoring
rebuild. Each one began as a strict expected failure describing a defect in
the 1.2.2 engine, so that fixing the underlying bug failed the suite until the
marker was removed. They all pass now, and they are kept as the statement of
what must stay true: a formula may change, these may not.

Assertions are deliberately about behaviour rather than about particular
numbers. Pinning exact values is what made the previous suite agree with a
model that had stopped measuring preference at all.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

from genre_importance import calculate_genre_importance
from handle_missing_scores import calculate_genre_medians
from recommendation_system import rank_recommendations


def _rank(candidates, weights, **kwargs):
    options = {
        "num_recommendations": len(candidates),
        "top_anime_count": len(candidates),
        "randomness_factor": 1,
        "random_state": 7,
    }
    options.update(kwargs)
    return rank_recommendations(candidates, weights, **options)


def _candidate(anime_id, title, genres, mean_score=8.0):
    return {
        "Anime ID": anime_id,
        "Title": title,
        "Genres": list(genres),
        "Mean Score": mean_score,
    }


def _weights(pairs):
    return pd.DataFrame(
        [{"Genre": genre, "Importance_Score": score} for genre, score in pairs]
    )


def _match_by_id(frame):
    return dict(zip(frame["Anime ID"], frame["Match Score"]))


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------


def test_match_score_is_independent_of_the_rest_of_the_batch():
    weights = _weights([("Action", 120.0), ("Comedy", 60.0)])
    full = pd.DataFrame(
        [
            _candidate(1, "Both", ["Action", "Comedy"]),
            _candidate(2, "Action Only", ["Action"]),
            _candidate(3, "Comedy Only", ["Comedy"]),
        ]
    )
    # The second page of results, after the strongest title was already shown.
    second_page = full[full["Anime ID"] != 1].reset_index(drop=True)

    first_scores = _match_by_id(_rank(full, weights))
    second_scores = _match_by_id(_rank(second_page, weights))

    assert second_scores[2] == pytest.approx(first_scores[2])
    assert second_scores[3] == pytest.approx(first_scores[3])


def test_match_score_is_deterministic_for_identical_input():
    weights = _weights([("Action", 120.0)])
    candidates = pd.DataFrame(
        [_candidate(1, "A", ["Action"]), _candidate(2, "B", ["Action"])]
    )
    assert _match_by_id(_rank(candidates, weights)) == _match_by_id(
        _rank(candidates, weights)
    )


def test_match_score_never_leaves_the_zero_to_hundred_range():
    weights = _weights([("Action", 20.0), ("Comedy", 60.0)])
    candidates = pd.DataFrame(
        [
            _candidate(1, "Disliked Action", ["Action"]),
            _candidate(2, "Liked Comedy", ["Comedy"]),
        ]
    )
    result = _rank(candidates, weights, genre_adjustments={"Action": -30.0})

    assert result["Match Score"].min() >= 0.0
    assert result["Match Score"].max() <= 100.0


# ---------------------------------------------------------------------------
# Explanation integrity
# ---------------------------------------------------------------------------


def test_displayed_contributions_reconcile_with_the_displayed_score():
    weights = _weights([("Action", 120.0), ("Comedy", 60.0)])
    candidates = pd.DataFrame([_candidate(1, "Both", ["Action", "Comedy"])])
    row = _rank(candidates, weights).iloc[0]

    contribution_total = sum(score for _genre, score in row["Genre Contributions"])
    assert contribution_total == pytest.approx(row["Match Score"], rel=1e-6)


def test_a_disliked_genre_is_never_shown_as_helping():
    """Signs in the breakdown must match reality, even for a poor match.

    Attributing shares by dividing the match percentage by the blended score
    inverts every sign when that score is negative, which presents the very
    genres that sank a title as the reasons to watch it.
    """
    taste = pytest.importorskip("scoring.taste")
    ranking = pytest.importorskip("scoring.ranking")

    completed = pd.DataFrame(
        [{"Title": f"Chore {i}", "Genres": ["Tedious"], "User Score": 3} for i in range(8)]
        + [{"Title": f"Gem {i}", "Genres": ["Beloved"], "User Score": 10} for i in range(8)]
    )
    profile = taste.build_taste_profile(completed)
    scored = ranking.score_candidate(
        {"Genres": ["Tedious"], "Mean Score": 8.0, "Scoring Users": 100000}, profile
    )

    assert profile.affinity("genre:Tedious") < 0
    contributions = dict(scored.contributions)
    assert contributions["genre:Tedious"] < 0, "a disliked genre must read as a penalty"
    assert scored.quality_contribution > 0


def test_penalised_titles_explain_why_they_were_penalised():
    weights = _weights([("Action", 20.0)])
    candidates = pd.DataFrame([_candidate(1, "Disliked", ["Action"])])
    row = _rank(candidates, weights, genre_adjustments={"Action": -30.0}).iloc[0]

    assert row["Genre Contributions"], "a penalised title must show its penalty"


# ---------------------------------------------------------------------------
# Ranking shape
# ---------------------------------------------------------------------------


def test_repeating_a_tag_does_not_raise_a_title():
    weights = _weights([("Action", 100.0)])
    candidates = pd.DataFrame(
        [
            _candidate(1, "Single Tag", ["Action"]),
            _candidate(2, "Repeated Tag", ["Action", "Action"]),
        ]
    )
    scores = dict(zip(*_rank(candidates, weights)[["Anime ID", "Recommendation Score"]].values.T))
    assert scores[2] == pytest.approx(scores[1])


def test_raising_a_weight_never_lowers_a_title_carrying_it():
    candidates = pd.DataFrame([_candidate(1, "Action Show", ["Action"])])
    low = _rank(candidates, _weights([("Action", 10.0)])).iloc[0]
    high = _rank(candidates, _weights([("Action", 50.0)])).iloc[0]

    assert high["Recommendation Score"] >= low["Recommendation Score"]


def test_excluded_ids_never_appear_in_results():
    weights = _weights([("Action", 100.0)])
    candidates = pd.DataFrame(
        [_candidate(index, f"Show {index}", ["Action"]) for index in range(1, 6)]
    )
    result = _rank(candidates, weights, excluded_mal_ids={2, 4})

    assert 2 not in set(result["Anime ID"])
    assert 4 not in set(result["Anime ID"])


# ---------------------------------------------------------------------------
# Taste profile
# ---------------------------------------------------------------------------


def test_a_well_rated_genre_outranks_a_badly_rated_one_at_equal_frequency():
    completed = pd.DataFrame(
        [
            {"Title": f"Loved {index}", "Genres": ["Adored"], "User Score": 10}
            for index in range(5)
        ]
        + [
            {"Title": f"Endured {index}", "Genres": ["Endured"], "User Score": 4}
            for index in range(5)
        ]
    )
    importance = calculate_genre_importance(
        completed, calculate_genre_medians(completed)
    )

    assert importance["Adored"] > importance["Endured"]


def test_a_single_observation_cannot_outweigh_a_well_supported_genre():
    """Confidence must temper strength: one rave review loses to twenty steady ones.

    This cannot be expressed against the 1.2.2 model, which has no notion of
    sample confidence at all -- its ranking is decided by raw frequency share,
    so any comparison here would pass for the wrong reason. The test targets the
    Phase 3 API and starts running by itself once that module exists.
    """
    taste = pytest.importorskip(
        "scoring.taste", reason="shrinkage arrives with the Phase 3 scoring engine"
    )
    completed = pd.DataFrame(
        [{"Title": "One Off", "Genres": ["Rare"], "User Score": 10}]
        + [
            {"Title": f"Staple {index}", "Genres": ["Staple"], "User Score": 9}
            for index in range(20)
        ]
        + [
            {"Title": f"Filler {index}", "Genres": ["Filler"], "User Score": 5}
            for index in range(20)
        ]
    )
    profile = taste.build_taste_profile(completed)

    # "Rare" has the higher raw mean, "Staple" the stronger evidence.
    assert profile.affinity("genre:Staple") > profile.affinity("genre:Rare")


def test_genres_the_user_never_rated_are_absent_from_the_profile():
    completed = pd.DataFrame(
        [
            {"Title": "Rated", "Genres": ["Action"], "User Score": 8},
            {"Title": "Unrated", "Genres": ["Horror"], "User Score": 0},
        ]
    )
    importance = calculate_genre_importance(
        completed, calculate_genre_medians(completed)
    )

    assert "Horror" not in importance


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------


def test_feedback_reaches_genres_absent_from_the_taste_profile():
    weights = _weights([("Action", 100.0)])
    candidates = pd.DataFrame(
        [
            _candidate(1, "Known", ["Action"]),
            _candidate(2, "Discovered", ["Psychological"]),
        ]
    )
    result = _rank(candidates, weights, genre_adjustments={"Psychological": 60.0})
    scores = dict(
        zip(*result[["Anime ID", "Recommendation Score"]].values.T)
    )

    assert scores[2] > 0.0


def test_feedback_on_a_known_genre_changes_the_ranking():
    weights = _weights([("Action", 20.0), ("Fantasy", 18.0)])
    candidates = pd.DataFrame(
        [_candidate(1, "Action", ["Action"]), _candidate(2, "Fantasy", ["Fantasy"])]
    )
    baseline = _rank(candidates, weights)["Anime ID"].tolist()
    boosted = _rank(candidates, weights, genre_adjustments={"Fantasy": 25.0})[
        "Anime ID"
    ].tolist()

    assert baseline[0] == 1
    assert boosted[0] == 2


def test_accumulated_feedback_does_not_depend_on_replay_order():
    """Five likes then a dislike must equal a dislike then five likes."""
    from services.recommendation_state_service import (
        RecommendationFeedback,
        RecommendationLocalState,
    )
    from services.taste_feedback_service import TasteFeedbackService

    def record(mal_id, sentiment):
        return RecommendationFeedback(
            mal_id=mal_id, sentiment=sentiment, genres=("Fantasy",), title=f"T{mal_id}"
        )

    liked = [record(index, "liked") for index in range(1, 6)]
    disliked = [record(99, "disliked")]
    service = TasteFeedbackService()

    forward = service.genre_adjustments(
        RecommendationLocalState(feedback=tuple(liked + disliked))
    )
    reverse = service.genre_adjustments(
        RecommendationLocalState(feedback=tuple(disliked + liked))
    )

    assert forward == reverse


def test_minimum_mean_score_filters_low_rated_candidates():
    weights = _weights([("Action", 100.0)])
    candidates = pd.DataFrame(
        [
            _candidate(1, "Acclaimed", ["Action"], mean_score=8.5),
            _candidate(2, "Mediocre", ["Action"], mean_score=5.5),
            _candidate(3, "Unrated", ["Action"], mean_score=None),
        ]
    )
    result = _rank(candidates, weights, minimum_mean_score=7.0)

    assert set(result["Anime ID"]) == {1}


def test_untitled_rows_do_not_exclude_one_another():
    from candidate_generation import filter_recommendation_candidates

    completed = pd.DataFrame([{"Anime ID": None, "Title": float("nan")}])
    top = pd.DataFrame(
        [
            {"Anime ID": 10, "Title": "Real Show"},
            {"Anime ID": 11, "Title": float("nan")},
        ]
    )
    result = filter_recommendation_candidates(completed, top)

    # A missing title carries no identity, so it must not filter anything out.
    assert 10 in set(result["Anime ID"])


# ---------------------------------------------------------------------------
# Theme parity
# ---------------------------------------------------------------------------


_SELECTOR_PATTERN = re.compile(r"([^{}]+)\{[^{}]*\}", re.MULTILINE)


def _selectors(path: Path) -> set[str]:
    text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
    found: set[str] = set()
    for block in _SELECTOR_PATTERN.findall(text):
        for selector in block.split(","):
            cleaned = " ".join(selector.split())
            if cleaned:
                found.add(cleaned)
    return found


def test_light_and_dark_themes_style_the_same_selectors(repo_root: Path):
    styles = repo_root / "AniRec" / "gui" / "resources" / "styles"
    dark = _selectors(styles / "dark.qss")
    light = _selectors(styles / "light.qss")

    assert dark - light == set(), f"missing from light.qss: {sorted(dark - light)}"
    assert light - dark == set(), f"missing from dark.qss: {sorted(light - dark)}"
