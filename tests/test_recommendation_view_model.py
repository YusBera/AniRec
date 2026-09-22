from __future__ import annotations

from AniRec.presentation.recommendation_view_model import (
    NO_GENRES,
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
    # The uncalibrated percentage is retired (D-008); without a recorded
    # ranking position there is no personal-fit claim to make.
    assert model.personal_match_text == "Personal match unavailable"
    assert model.personal_match_available is False


def test_same_english_and_mal_title_is_not_repeated():
    model = RecommendationViewModel.from_recommendation(
        Recommendation(Anime("Frieren", english_title="Frieren"))
    )
    assert model.display_title == "Frieren"
    assert model.secondary_title is None


def test_personal_fit_is_a_rank_and_mal_score_stays_separate():
    explanation = {"method": "exact-additive", "total": 0.4, "segments": []}
    model = RecommendationViewModel.from_recommendation(
        Recommendation(
            Anime("Fixture", mean_score=8.456),
            match_score=73.25,
            model_rank=4,
            ranked_candidate_count=22210,
            explanation=explanation,
        )
    )
    assert model.personal_match_text == "Ranked #4 of 22,210 for you"
    assert model.personal_match_available is False
    assert model.fit_rank == 4
    assert model.fit_pool_size == 22210
    assert model.fit_top_percent == 100.0 * 4 / 22210
    assert model.why == explanation
    assert model.mal_score_text == "MAL score: 8.46 / 10"
    assert model.mal_score == 8.456


def test_inconsistent_fit_rank_is_dropped_rather_than_shown():
    for rank, count in ((5, 3), (0, 10), (2.5, 10), (3, None)):
        model = RecommendationViewModel.from_recommendation(
            Recommendation(Anime("Fixture"), model_rank=rank, ranked_candidate_count=count)
        )
        assert model.fit_rank is None
        assert model.fit_pool_size is None
        assert model.fit_top_percent is None


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

    assert model.personal_match_text == "Personal match unavailable"
    assert "Not rated" in model.mal_score_text
    assert model.genres_text == NO_GENRES
    assert model.status == "Not available"
    assert model.synopsis == NO_SYNOPSIS
    # CHANGE [DEFECT-REASON]: this used to pin the fallback to the sentence
    # "No recommendation explanation is available.", which is what the card
    # then spent both of its reserved reason lines rendering. The invariant
    # worth protecting is the one this test is named for - nothing leaks a
    # Python literal or a placeholder - so it now checks the stronger thing:
    # with no explanation and nothing that contributed, the reason is empty
    # and the card prints nothing rather than a non-statement.
    assert model.reason == ""
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


def test_a_missing_explanation_reports_the_genres_that_carried_the_score():
    """The card's reason line has to say something true or say nothing.

    CHANGE [DEFECT-REASON]: covers the fallback that replaced the old
    "No recommendation explanation is available." sentence.
    """
    model = RecommendationViewModel.from_recommendation(
        Recommendation(
            Anime("Fixture", genres=("Drama", "Mystery")),
            match_score=90.0,
            genre_contributions=(
                ("Mystery", 18.0),
                ("Community rating", 30.0),
                ("Drama", 22.5),
            ),
        )
    )
    # Weight order, and the community term is not one of the user's genres.
    assert model.reason == "Matched on Drama and Mystery."
    assert "community" not in model.reason.casefold()


def test_a_written_explanation_is_never_replaced_by_the_fallback():
    model = RecommendationViewModel.from_recommendation(
        Recommendation(
            Anime("Fixture", genres=("Drama",)),
            match_score=90.0,
            reason="Because you rated Death Note highly.",
            genre_contributions=(("Drama", 22.5),),
        )
    )
    assert model.reason == "Because you rated Death Note highly."
