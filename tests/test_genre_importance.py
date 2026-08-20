from __future__ import annotations

import pandas as pd

from genre_importance import calculate_genre_importance
from main import calculate_and_save_genre_importance


def test_importance_follows_rating_quality_not_frequency():
    """A genre rated above the user's own average outranks one rated below it.

    The original formula could not express this. It multiplied a frequency
    share by a genre's mean divided by its own median, which is a ratio taken
    from the same sample and therefore equal to one whenever a genre is rated
    consistently. Frequency alone decided the outcome, so a genre watched often
    and disliked outranked one watched rarely and loved.
    """
    frame = pd.DataFrame(
        [{"Genres": ["Adored"], "User Score": 9} for _ in range(5)]
        + [{"Genres": ["Endured"], "User Score": 4} for _ in range(5)]
    )

    importance = calculate_genre_importance(frame)

    assert importance["Adored"] > 0
    assert importance["Endured"] < 0
    assert importance["Adored"] > importance["Endured"]


def test_evidence_tempers_a_single_strong_rating():
    frame = pd.DataFrame(
        [{"Genres": ["Rare"], "User Score": 10}]
        + [{"Genres": ["Staple"], "User Score": 9} for _ in range(20)]
        + [{"Genres": ["Filler"], "User Score": 4} for _ in range(20)]
    )

    importance = calculate_genre_importance(frame)

    assert importance["Staple"] > importance["Rare"] > 0


def test_unrated_entries_contribute_nothing():
    no_scores = pd.DataFrame(
        [
            {"Genres": ["Action"], "User Score": 0},
            {"Genres": ["Drama"], "User Score": float("nan")},
        ]
    )

    assert calculate_genre_importance(no_scores) == {}


def test_legacy_medians_argument_is_still_accepted():
    frame = pd.DataFrame(
        [
            {"Genres": ["Action", "Drama"], "User Score": 8},
            {"Genres": ["Action"], "User Score": 6},
        ]
    )

    assert calculate_genre_importance(
        frame, {"Action": 7.0, "Drama": 8.0}
    ) == calculate_genre_importance(frame)


def test_saved_genre_importance_is_sorted_descending(system_temp_dir):
    completed = pd.DataFrame(
        [{"Genres": ["Adored"], "User Score": 9} for _ in range(5)]
        + [{"Genres": ["Endured"], "User Score": 4} for _ in range(5)]
    )
    completed.to_csv(system_temp_dir / "completed_anime.csv", index=False)

    output = calculate_and_save_genre_importance(system_temp_dir)
    result = pd.read_csv(output)

    assert result["Genre"].tolist() == ["Adored", "Endured"]
    assert result["Importance_Score"].is_monotonic_decreasing
