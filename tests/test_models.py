from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from models import (
    MODEL_SCHEMA_VERSION,
    Anime,
    GenreStat,
    PipelineProgress,
    PipelineResult,
    PipelineSettings,
    Recommendation,
    UserProfile,
)


def test_anime_normalizes_missing_values_and_preserves_unicode():
    anime = Anime(
        title="  進撃の巨人  ",
        english_title="Attack on Titan",
        alternative_titles=("Shingeki no Kyojin", " "),
        genres=(" Action ", "Dram Çığ"),
        mean_score=float("nan"),
    )

    assert anime.title == "進撃の巨人"
    assert anime.display_title == "Attack on Titan"
    assert anime.secondary_title == "進撃の巨人"
    assert anime.genres == ("Action", "Dram Çığ")
    assert anime.mean_score is None
    assert anime.display_score == "Not rated"


def test_anime_and_recommendation_schema_round_trip():
    anime = Anime(
        title="Cowboy Bebop",
        mal_id=1,
        genres=("Action", "Sci-Fi"),
        mean_score=8.75,
        episodes=26,
        year=1998,
    )
    recommendation = Recommendation(
        anime=anime,
        match_score=180.5,
        raw_score=240.0,
        contributing_genres=("Sci-Fi", "Action"),
        genre_contributions=(("Sci-Fi", 140.0), ("Action", 100.0)),
        reason="Matches strong genres.",
        rank=1,
    )

    payload = recommendation.to_dict()
    assert payload["schema_version"] == MODEL_SCHEMA_VERSION
    assert Recommendation.from_dict(payload) == recommendation


def test_model_schema_version_is_required():
    with pytest.raises(ValueError, match="schema version"):
        Anime.from_dict({"schema_version": 999, "title": "Fixture"})


def test_models_are_frozen():
    anime = Anime(title="Fixture")
    with pytest.raises(FrozenInstanceError):
        anime.title = "Changed"


@pytest.mark.parametrize(
    "settings",
    [
        PipelineSettings(),
        PipelineSettings(
            top_anime_limit=250,
            recommendation_count=5,
            candidate_pool_size=50,
            randomness_factor=1,
            minimum_mean_score=float("nan"),
            seed=42,
        ),
    ],
)
def test_pipeline_settings_round_trip(settings):
    assert PipelineSettings.from_dict(settings.to_dict()) == settings


@pytest.mark.parametrize(
    "kwargs",
    [
        {"top_anime_limit": 0},
        {"recommendation_count": 0},
        {"recommendation_count": 10, "candidate_pool_size": 5},
        {"randomness_factor": 0},
        {"randomness_factor": 11},
    ],
)
def test_pipeline_settings_reject_invalid_ranges(kwargs):
    with pytest.raises(ValueError):
        PipelineSettings(**kwargs)


def test_profile_progress_and_result_round_trip():
    profile = UserProfile("fixture-1", "Kullanıcı Çığ", last_sync="2026-08-03T12:00:00Z")
    assert UserProfile.from_dict(profile.to_dict()) == profile

    progress = PipelineProgress("fetch", "Fetching fixtures", current=1, total=2, cancellable=True)
    assert PipelineProgress.from_dict(progress.to_dict()) == progress

    stat = GenreStat(
        "Bilim Kurgu",
        importance_score=120.5,
        completed_count=3,
        average_user_score=8.25,
        missing_score_count=1,
        example_titles=("Örnek",),
    )
    result = PipelineResult(
        recommendations=(Recommendation(Anime("Öneri", mal_id=10), 50.0),),
        genre_stats=(stat,),
        user_stats={"completed_count": 3},
        generated_files=("fixture.csv",),
        started_at="2026-08-03T12:00:00Z",
        completed_at="2026-08-03T12:01:00Z",
    )
    assert PipelineResult.from_dict(result.to_dict()) == result


def test_progress_rejects_invalid_values():
    with pytest.raises(ValueError):
        PipelineProgress("stage", "message", current=-1)
    with pytest.raises(ValueError):
        PipelineProgress("stage", "message", current=2, total=1)
