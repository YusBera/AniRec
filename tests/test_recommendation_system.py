from __future__ import annotations

import pandas as pd
import pytest

from recommendation_system import recommend_animes_with_randomness


def _write_recommendation_inputs(directory, candidates, genre_weights):
    candidate_path = directory / "candidates.csv"
    genre_path = directory / "genres.csv"
    pd.DataFrame(candidates).to_csv(candidate_path, index=False)
    pd.DataFrame(genre_weights).to_csv(genre_path, index=False)
    return candidate_path, genre_path


def test_recommendations_sum_genre_weights_and_use_mean_score_as_tie_break(system_temp_dir):
    candidate_path, genre_path = _write_recommendation_inputs(
        system_temp_dir,
        [
            {"Title": "Action Lower", "Genres": ["Action"], "Mean Score": 7.0},
            {"Title": "Action Higher", "Genres": ["Action"], "Mean Score": 8.0},
            {"Title": "Comedy", "Genres": ["Comedy"], "Mean Score": 9.0},
        ],
        [
            {"Genre": "Action", "Importance_Score": 100.0},
            {"Genre": "Comedy", "Importance_Score": 20.0},
        ],
    )

    result = recommend_animes_with_randomness(
        candidate_path,
        genre_path,
        "fixture_user",
        num_recommendations=3,
        top_anime_count=3,
        randomness_factor=1,
        output_dir=system_temp_dir / "nested",
    )

    assert result == ["Action Higher", "Action Lower", "Comedy"]
    output = system_temp_dir / "nested" / "fixture_user_recommendations.csv"
    saved = pd.read_csv(output)
    scores = saved["Recommendation Score"].tolist()
    # The two Action titles match the profile equally, so they tie on the
    # genre signal and the higher community score breaks the tie. Comedy is
    # the weaker preference and ranks below both.
    assert scores[0] == pytest.approx(scores[1])
    assert scores[1] > scores[2]


@pytest.mark.parametrize("randomness_factor", [0, 1, 10, 20])
def test_randomness_is_clamped_and_returns_requested_invariants(
    system_temp_dir,
    randomness_factor,
):
    candidates = [
        {"Title": f"Show {index}", "Genres": ["Action"], "Mean Score": 10 - index / 10}
        for index in range(10)
    ]
    candidate_path, genre_path = _write_recommendation_inputs(
        system_temp_dir,
        candidates,
        [{"Genre": "Action", "Importance_Score": 100.0}],
    )

    result = recommend_animes_with_randomness(
        candidate_path,
        genre_path,
        f"fixture_{randomness_factor}",
        num_recommendations=2,
        top_anime_count=10,
        randomness_factor=randomness_factor,
        output_dir=system_temp_dir,
    )

    assert len(result) == 2
    assert len(set(result)) == 2
    assert set(result).issubset({row["Title"] for row in candidates})


def test_recommendation_input_columns_and_empty_frames_are_characterized(system_temp_dir):
    candidate_path, genre_path = _write_recommendation_inputs(
        system_temp_dir,
        [{"Genres": ["Action"]}],
        [{"Genre": "Action", "Importance_Score": 100.0}],
    )
    with pytest.raises(ValueError, match="missing columns: Title"):
        recommend_animes_with_randomness(
            candidate_path, genre_path, "fixture", 1, 1, 1, system_temp_dir
        )

    candidate_path, genre_path = _write_recommendation_inputs(
        system_temp_dir,
        [{"Title": "Show", "Genres": ["Action"]}],
        [{"Wrong": "Action", "Value": 100.0}],
    )
    with pytest.raises(ValueError, match="must include Genre and Importance_Score"):
        recommend_animes_with_randomness(
            candidate_path, genre_path, "fixture", 1, 1, 1, system_temp_dir
        )

    candidate_path, genre_path = _write_recommendation_inputs(
        system_temp_dir,
        [],
        [{"Genre": "Action", "Importance_Score": 100.0}],
    )
    pd.DataFrame(columns=["Title", "Genres"]).to_csv(candidate_path, index=False)
    assert recommend_animes_with_randomness(
        candidate_path, genre_path, "fixture", 1, 1, 1, system_temp_dir
    ) == []
