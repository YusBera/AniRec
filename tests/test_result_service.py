from __future__ import annotations

from AniRec.models import Anime, GenreStat, PipelineResult, Recommendation
from AniRec.services import ResultService


def test_result_service_round_trips_profile_scoped_latest_result(system_temp_dir):
    service = ResultService(root_override=system_temp_dir)
    result = PipelineResult(
        recommendations=(Recommendation(Anime("Fixture"), rank=1),),
        genre_stats=(GenreStat("Action", importance_score=12.5),),
        user_stats={"completed_count": 7},
        generated_files=("recommendations.csv",),
        completed_at="2026-08-03T12:00:00+00:00",
    )

    path = service.save("profile-1", result)

    assert path.is_file()
    assert service.load("profile-1") == result
    assert service.load("profile-2") is None


def test_result_service_merge_preserves_rich_results_during_sync_update(system_temp_dir):
    service = ResultService(root_override=system_temp_dir)
    previous = PipelineResult(
        recommendations=(Recommendation(Anime("Existing"), rank=1),),
        genre_stats=(GenreStat("Drama", importance_score=9.0),),
        user_stats={"recommendation_count": 1, "completed_count": 4},
        generated_files=("recommendations.csv",),
        completed_at="old",
    )
    service.save("profile-1", previous)

    merged = service.save_merged(
        "profile-1",
        PipelineResult(
            user_stats={"completed_count": 8, "rated_count": 6},
            generated_files=("completed.csv",),
            completed_at="new",
        ),
    )

    assert merged.recommendations == previous.recommendations
    assert merged.genre_stats == previous.genre_stats
    assert merged.user_stats == {
        "recommendation_count": 1,
        "completed_count": 8,
        "rated_count": 6,
    }
    assert merged.generated_files == ("recommendations.csv", "completed.csv")
    assert service.load("profile-1") == merged
