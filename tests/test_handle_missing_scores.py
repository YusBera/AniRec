from __future__ import annotations

import pandas as pd

from handle_missing_scores import (
    calculate_genre_medians,
    handle_missing_scores_with_genre_medians,
)


def test_calculate_genre_medians_ignores_zero_nan_and_invalid_scores():
    frame = pd.DataFrame(
        [
            {"Genres": ["Action", "Drama"], "User Score": 8},
            {"Genres": ["Action"], "User Score": 6},
            {"Genres": ["Comedy"], "User Score": 0},
            {"Genres": ["Comedy"], "User Score": float("nan")},
            {"Genres": ["Comedy"], "User Score": "invalid"},
        ]
    )

    assert calculate_genre_medians(frame) == {"Action": 7.0, "Drama": 8.0}


def test_imputation_uses_matching_genre_mean_then_global_median():
    frame = pd.DataFrame(
        [
            {"Title": "Kept", "Genres": ["Action"], "User Score": 9},
            {"Title": "Mixed", "Genres": ["Action", "Drama"], "User Score": 0},
            {"Title": "Unknown", "Genres": ["Mystery"], "User Score": None},
            {"Title": "Invalid", "Genres": [], "User Score": "invalid"},
        ]
    )
    genre_medians = {"Action": 8.0, "Drama": 6.0, "Comedy": 7.0}

    result = handle_missing_scores_with_genre_medians(frame, genre_medians)

    assert result["User Score"].tolist() == [9.0, 7.0, 7.0, 7.0]


def test_imputation_without_any_genre_median_keeps_fallback_at_zero():
    frame = pd.DataFrame([{"Genres": ["Action"], "User Score": None}])

    result = handle_missing_scores_with_genre_medians(frame, {})

    assert result.at[0, "User Score"] == 0.0
