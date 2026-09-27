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


def test_stats_only_merge_reuses_compact_ranking_blob(system_temp_dir):
    service = ResultService(root_override=system_temp_dir)
    original = PipelineResult(recommendations=(
        Recommendation(Anime("Shared", mal_id=1), rank=1),
    ), user_stats={"complete_ranking": True})
    path = service.save("profile-1", original)
    before = __import__("json").loads(path.read_text(encoding="utf-8"))
    updated = service.save_merged("profile-1", PipelineResult(user_stats={"feed_refresh": "current"}))
    after = __import__("json").loads(path.read_text(encoding="utf-8"))
    assert after["ranking_data"] == before["ranking_data"]
    assert updated.user_stats["feed_refresh"] == "current"
    assert service.load("profile-1") == updated


def test_loaded_ranking_cache_is_bounded_and_not_shared_across_profiles(system_temp_dir):
    service = ResultService(root_override=system_temp_dir)
    for index in range(3):
        service.save(f"profile-{index}", PipelineResult(recommendations=(
            Recommendation(Anime(f"Title {index}", mal_id=index + 1), rank=1),
        )))
    newest = service.load("profile-2")
    assert service.load("profile-2") is newest
    assert len(service._loaded) == 2
    assert service.load("profile-0").recommendations[0].anime.title == "Title 0"
