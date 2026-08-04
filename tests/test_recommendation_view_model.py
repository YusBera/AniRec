from __future__ import annotations

from AniRec.gui.recommendation_view_model import (
    NO_GENRES,
    NO_REASON,
    NO_SYNOPSIS,
    RecommendationViewModel,
)
from AniRec.models import Anime, Recommendation


def test_english_title_is_primary_and_distinct_romaji_is_secondary():
    model = RecommendationViewModel.from_recommendation(
        Recommendation(
            Anime(
                "Shingeki no Kyojin",
                english_title="Attack on Titan",
                mal_id=16498,
            ),
            match_score=91.25,
        )
    )

    assert model.display_title == "Attack on Titan"
    assert model.secondary_title == "Shingeki no Kyojin"
    assert model.personal_match_text == "Personal match: 91.2%"


def test_same_english_and_mal_title_is_not_repeated():
    model = RecommendationViewModel.from_recommendation(
        Recommendation(Anime("Frieren", english_title="Frieren"))
    )
    assert model.display_title == "Frieren"
    assert model.secondary_title is None


def test_personal_match_and_mal_score_have_distinct_explicit_labels():
    model = RecommendationViewModel.from_recommendation(
        Recommendation(Anime("Fixture", mean_score=8.456), match_score=73.25)
    )
    assert model.personal_match_text == "Personal match: 73.2%"
    assert model.mal_score_text == "MAL score: 8.46 / 10"
    assert model.personal_match == 73.25
    assert model.mal_score == 8.456


def test_missing_values_never_render_python_literals_or_nan():
    model = RecommendationViewModel.from_recommendation(
        Recommendation(
            Anime(
                "Fixture",
                mean_score=float("nan"),
                genres=(),
                episodes=None,
                status=" ",
                year=None,
                synopsis="None",
            ),
            match_score=float("nan"),
            reason="nan",
        )
    )
    rendered = " ".join(
        (
            model.personal_match_text,
            model.mal_score_text,
            model.genres_text,
            model.episodes_text,
            model.status,
            model.year_text,
            model.synopsis,
            model.reason,
        )
    )

    assert model.personal_match_text == "Personal match: 0.0%"
    assert "Not rated" in model.mal_score_text
    assert model.genres_text == NO_GENRES
    assert model.status == "Not available"
    assert model.synopsis == NO_SYNOPSIS
    assert model.reason == NO_REASON
    assert "None" not in rendered
    assert "nan" not in rendered.casefold()
    assert "[]" not in rendered


def test_episode_year_status_genres_reason_and_dates_are_formatted():
    model = RecommendationViewModel.from_recommendation(
        Recommendation(
            Anime(
                "Fixture",
                genres=("Action", "Drama"),
                episodes=1,
                status="finished_airing",
                year=2024,
                start_date="2024-01-01",
                end_date="2024-03-01",
                synopsis="A fixture synopsis.",
            ),
            reason="Matches your interests.",
            contributing_genres=("Action",),
        )
    )
    assert model.genres_text == "Action · Drama"
    assert model.episodes_text == "1 episode"
    assert model.year_text == "2024"
    assert model.start_date == "2024-01-01"
    assert model.end_date == "2024-03-01"
    assert model.contributing_genres == ("Action",)


def test_only_https_cover_and_matching_mal_urls_survive():
    valid = RecommendationViewModel.from_recommendation(
        Recommendation(
            Anime(
                "Fixture",
                mal_id=42,
                cover_url="https://cdn.example.test/cover.jpg",
                mal_url="https://myanimelist.net/anime/42/Fixture",
            )
        )
    )
    invalid = RecommendationViewModel.from_recommendation(
        Recommendation(
            Anime(
                "Unsafe",
                mal_id=42,
                cover_url="http://cdn.example.test/cover.jpg",
                mal_url="https://example.test/anime/42",
            )
        )
    )
    assert valid.cover_url == "https://cdn.example.test/cover.jpg"
    assert valid.mal_url == "https://myanimelist.net/anime/42/Fixture"
    assert invalid.cover_url is None
    assert invalid.mal_url is None
