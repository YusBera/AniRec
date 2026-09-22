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
        "studios": [{"id": 14, "name": "Sunrise"}],
        "source": "original",
        "media_type": "tv",
        "num_scoring_users": 987654,
        # AniRec deliberately does not request or map MAL rank/popularity into
        # the heuristic scorer.
        "rank": 42,
        "popularity": 99,
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
    assert anime.studios == ("Sunrise",)
    assert anime.source == "original"
    assert anime.media_type == "tv"
    assert anime.scoring_users == 987654
    assert "rank" not in anime.to_dict()
    assert "popularity" not in anime.to_dict()


def test_missing_optional_fields_are_safe_and_missing_identity_is_skipped():
    anime = anime_from_node({"id": 10, "title": "Minimal"})
    assert anime.mean_score is None
    assert anime.genres == ()
    assert anime.display_score == "Not rated"
    assert anime_from_node({"title": "Missing ID"}) is None
    assert anime_from_node({"id": 10}) is None


def test_year_falls_back_to_start_season_when_start_date_is_missing():
    node = _rich_node()
    node.pop("start_date")

    anime = anime_from_node(node)

    assert anime.year == 1998


def test_anime_csv_row_schema_round_trip():
    anime = anime_from_node(_rich_node())
    row = anime_to_row(anime)
    assert list(row) == ANIME_CSV_COLUMNS
    assert anime_from_row(row) == anime
