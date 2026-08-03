from __future__ import annotations

from core.mal_mapping import (
    ANIME_CSV_COLUMNS,
    anime_from_node,
    anime_from_row,
    anime_to_row,
)


def _rich_node():
    return {
        "id": 1,
        "title": "Cowboy Bebop",
        "alternative_titles": {
            "en": "Cowboy Bebop",
            "ja": "カウボーイビバップ",
            "synonyms": ["COWBOY BEBOP"],
        },
        "main_picture": {
            "medium": "https://cdn.myanimelist.net/medium.jpg",
            "large": "https://cdn.myanimelist.net/large.jpg",
        },
        "genres": [{"id": 1, "name": "Action"}, {"id": 24, "name": "Sci-Fi"}],
        "mean": 8.75,
        "num_episodes": 26,
        "status": "finished_airing",
        "start_date": "1998-04-03",
        "end_date": "1999-04-24",
        "start_season": {"year": 1998, "season": "spring"},
        "synopsis": "A fixture synopsis.",
    }


def test_rich_mal_node_maps_to_complete_anime_and_safe_url():
    anime = anime_from_node(_rich_node())

    assert anime.mal_id == 1
    assert anime.title == "Cowboy Bebop"
    assert anime.english_title == "Cowboy Bebop"
    assert anime.alternative_titles == (
        "Cowboy Bebop",
        "カウボーイビバップ",
        "COWBOY BEBOP",
    )
    assert anime.genres == ("Action", "Sci-Fi")
    assert anime.mean_score == 8.75
    assert anime.episodes == 26
    assert anime.year == 1998
    assert anime.mal_url == "https://myanimelist.net/anime/1"


def test_missing_optional_fields_are_safe_and_missing_identity_is_skipped():
    anime = anime_from_node({"id": 10, "title": "Minimal"})
    assert anime.mean_score is None
    assert anime.genres == ()
    assert anime.display_score == "Not rated"
    assert anime_from_node({"title": "Missing ID"}) is None
    assert anime_from_node({"id": 10}) is None


def test_anime_csv_row_schema_round_trip():
    anime = anime_from_node(_rich_node())
    row = anime_to_row(anime)
    assert list(row) == ANIME_CSV_COLUMNS
    assert anime_from_row(row) == anime
