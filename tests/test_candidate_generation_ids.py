from __future__ import annotations

import pandas as pd

from candidate_generation import (
    filter_recommendation_candidates,
    generate_recommendation_candidates,
)


def test_mal_id_is_primary_and_duplicate_ids_are_removed():
    completed = pd.DataFrame(
        [
            {"Anime ID": 1, "Title": "Old Localized Title"},
            {"Anime ID": None, "Title": "Legacy Watched"},
        ]
    )
    top = pd.DataFrame(
        [
            {"Anime ID": 1, "Title": "Completely New Title", "Genres": ["Action"]},
            {"Anime ID": 2, "Title": "Old Localized Title", "Genres": ["Drama"]},
            {"Anime ID": 3, "Title": "First ID Three", "Genres": ["Comedy"]},
            {"Anime ID": 3, "Title": "Duplicate ID Three", "Genres": ["Comedy"]},
            {"Anime ID": None, "Title": "Legacy Watched", "Genres": ["Mystery"]},
            {"Anime ID": None, "Title": "Legacy New", "Genres": ["Sci-Fi"]},
            {"Anime ID": None, "Title": "LEGACY NEW", "Genres": ["Sci-Fi"]},
        ]
    )

    result = filter_recommendation_candidates(completed, top)

    assert result["Title"].tolist() == [
        "Old Localized Title",
        "First ID Three",
        "Legacy New",
    ]
    assert result["Anime ID"].dropna().astype(int).tolist() == [2, 3]


def test_legacy_csv_without_ids_keeps_casefold_title_fallback():
    completed = pd.DataFrame([{"Title": "Watched Show"}])
    top = pd.DataFrame(
        [
            {"Title": "WATCHED SHOW", "Genres": ["Action"]},
            {"Title": "New Show", "Genres": ["Drama"]},
        ]
    )
    result = filter_recommendation_candidates(completed, top)
    assert result["Title"].tolist() == ["New Show"]


def test_file_adapter_persists_id_filtered_schema(system_temp_dir):
    completed_path = system_temp_dir / "completed.csv"
    top_path = system_temp_dir / "top.csv"
    output_path = system_temp_dir / "nested" / "candidates.csv"
    pd.DataFrame([{"Anime ID": 1, "Title": "Watched"}]).to_csv(
        completed_path, index=False
    )
    pd.DataFrame(
        [
            {"Anime ID": 1, "Title": "Renamed", "Genres": ["Action"]},
            {"Anime ID": 2, "Title": "New", "Genres": ["Drama"]},
        ]
    ).to_csv(top_path, index=False)

    result = generate_recommendation_candidates(completed_path, top_path, output_path)

    assert result["Anime ID"].astype(int).tolist() == [2]
    assert pd.read_csv(output_path)["Anime ID"].astype(int).tolist() == [2]
