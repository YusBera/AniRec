from __future__ import annotations

import pandas as pd
import pytest

from candidate_generation import generate_recommendation_candidates, load_anime_data


def test_load_anime_data_validates_file_and_required_columns(system_temp_dir):
    missing_path = system_temp_dir / "missing.csv"
    with pytest.raises(FileNotFoundError, match="File not found"):
        load_anime_data(missing_path)

    invalid_path = system_temp_dir / "invalid.csv"
    pd.DataFrame([{"Genres": ["Action"]}]).to_csv(invalid_path, index=False)
    with pytest.raises(ValueError, match="missing required columns: Title"):
        load_anime_data(invalid_path, required_columns=["Title"])


def test_candidate_generation_filters_titles_case_insensitively_and_creates_output(
    csv_fixture_dir,
):
    output = csv_fixture_dir / "nested" / "recommendation_candidates.csv"

    result = generate_recommendation_candidates(
        csv_fixture_dir / "completed_anime.csv",
        csv_fixture_dir / "top_anime.csv",
        output,
    )

    assert result["Title"].tolist() == ["Gamma Show", "Delta Show"]
    assert list(result.columns) == ["Title", "Genres", "Mean Score"]
    assert output.is_file()
