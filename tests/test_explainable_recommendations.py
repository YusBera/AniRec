from __future__ import annotations

import pandas as pd
import pytest

from models import PipelineSettings
from recommendation_system import rank_recommendations
from services import RecommendationService


def test_raw_display_score_contributions_and_reason_templates():
    candidates = pd.DataFrame(
        [
            {
                "Anime ID": 1,
                "Title": "Two Genres",
                "Genres": ["Action", "Comedy"],
                "Mean Score": 8.0,
            },
            {
                "Anime ID": 2,
                "Title": "One Genre",
                "Genres": ["Action"],
                "Mean Score": 9.0,
            },
            {
                "Anime ID": 3,
                "Title": "No Match",
                "Genres": ["Mystery"],
                "Mean Score": 10.0,
            },
        ]
    )
    weights = pd.DataFrame(
        [
            {"Genre": "Action", "Importance_Score": 120.0},
            {"Genre": "Comedy", "Importance_Score": 60.0},
        ]
    )

    result = rank_recommendations(
        candidates,
        weights,
        num_recommendations=3,
        top_anime_count=3,
        randomness_factor=1,
        random_state=42,
    )

    titles = result["Title"].tolist()
    assert titles == ["Two Genres", "One Genre", "No Match"]

    # Carrying an extra matching tag still helps, but only slightly. Scoring by
    # cosine rather than by a sum of weights means a precise two-tag match is no
    # longer beaten simply because another title carries more tags.
    scores = dict(zip(titles, result["Match Score"]))
    assert scores["Two Genres"] > scores["One Genre"] > scores["No Match"]
    assert scores["One Genre"] > scores["Two Genres"] * 0.8

    # Every displayed part adds up to the percentage shown beside it.
    for _index, row in result.iterrows():
        breakdown = sum(value for _label, value in row["Genre Contributions"])
        assert breakdown == pytest.approx(row["Match Score"], abs=0.01)

    assert result["Recommendation Reason"].tolist() == [
        "Matches your interests in Action and Comedy.",
        "Matches your interest in Action.",
        "Broadens your recommendations beyond your strongest genres.",
    ]


def test_same_seed_repeats_ids_and_different_seed_changes_selection():
    candidates = pd.DataFrame(
        [
            {
                "Anime ID": index,
                "Title": f"Fixture {index:02d}",
                "Genres": ["Action"],
                "Mean Score": 8.0,
            }
            for index in range(1, 21)
        ]
    )
    weights = pd.DataFrame([{"Genre": "Action", "Importance_Score": 100.0}])
    service = RecommendationService(
        random_int=lambda _start, _end: (_ for _ in ()).throw(
            AssertionError("seeded recommendation must not use random source")
        )
    )

    first = service.recommend(
        candidates,
        weights,
        PipelineSettings(
            recommendation_count=5,
            candidate_pool_size=20,
            randomness_factor=10,
            seed=42,
        ),
    )
    repeated = service.recommend(
        candidates,
        weights,
        PipelineSettings(
            recommendation_count=5,
            candidate_pool_size=20,
            randomness_factor=10,
            seed=42,
        ),
    )
    different = service.recommend(
        candidates,
        weights,
        PipelineSettings(
            recommendation_count=5,
            candidate_pool_size=20,
            randomness_factor=10,
            seed=43,
        ),
    )

    assert first["Anime ID"].tolist() == repeated["Anime ID"].tolist()
    assert first["Anime ID"].tolist() != different["Anime ID"].tolist()


def test_stable_tie_break_is_score_mean_id_then_title():
    candidates = pd.DataFrame(
        [
            {"Anime ID": 3, "Title": "C", "Genres": ["Action"], "Mean Score": 8.0},
            {"Anime ID": 1, "Title": "A", "Genres": ["Action"], "Mean Score": 8.0},
            {"Anime ID": 2, "Title": "B", "Genres": ["Action"], "Mean Score": 9.0},
        ]
    )
    weights = pd.DataFrame([{"Genre": "Action", "Importance_Score": 100.0}])
    result = rank_recommendations(
        candidates,
        weights,
        num_recommendations=3,
        top_anime_count=3,
        randomness_factor=1,
    )
    assert result["Anime ID"].tolist() == [2, 1, 3]


def test_feedback_adjustments_change_selection_and_excluded_ids_never_return():
    candidates = pd.DataFrame(
        [
            {"Anime ID": 1, "Title": "Action", "Genres": ["Action"], "Mean Score": 8.0},
            {"Anime ID": 2, "Title": "Fantasy", "Genres": ["Fantasy"], "Mean Score": 8.0},
            {"Anime ID": 3, "Title": "More Fantasy", "Genres": ["Fantasy"], "Mean Score": 7.9},
        ]
    )
    weights = pd.DataFrame(
        [
            {"Genre": "Action", "Importance_Score": 20.0},
            {"Genre": "Fantasy", "Importance_Score": 18.0},
        ]
    )
    result = rank_recommendations(
        candidates,
        weights,
        num_recommendations=2,
        top_anime_count=3,
        randomness_factor=1,
        genre_adjustments={"Fantasy": 8.0, "Action": -8.0},
        excluded_mal_ids={2},
    )
    assert result["Anime ID"].tolist() == [3, 1]
    assert result.iloc[0]["Recommendation Reason"].startswith("Adapted to your likes")
