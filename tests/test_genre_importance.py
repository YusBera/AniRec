from __future__ import annotations

import pandas as pd

from genre_importance import calculate_genre_importance
from main import calculate_and_save_genre_importance


def test_genre_importance_formula_and_empty_score_behavior():
    frame = pd.DataFrame(
        [
            {"Genres": ["Action", "Drama"], "User Score": 8},
            {"Genres": ["Action"], "User Score": 6},
        ]
    )

    assert calculate_genre_importance(frame, {"Action": 7.0, "Drama": 8.0}) == {
        "Action": 100.0,
        "Drama": 50.0,
    }

    no_scores = pd.DataFrame(
        [
            {"Genres": ["Action"], "User Score": 0},
            {"Genres": ["Drama"], "User Score": float("nan")},
        ]
    )
    assert calculate_genre_importance(no_scores, {}) == {}


def test_saved_genre_importance_is_sorted_descending(system_temp_dir):
    completed = pd.DataFrame(
        [
            {"Genres": ["Action", "Drama"], "User Score": 8},
            {"Genres": ["Action"], "User Score": 6},
        ]
    )
    completed.to_csv(system_temp_dir / "completed_anime.csv", index=False)

    output = calculate_and_save_genre_importance(system_temp_dir)
    result = pd.read_csv(output)

    assert result["Genre"].tolist() == ["Action", "Drama"]
    assert result["Importance_Score"].tolist() == [100.0, 50.0]
