import json
import sqlite3
from contextlib import closing
import pytest

from AniRec.models import Anime, PipelineResult, Recommendation
from AniRec.services.result_service import ResultService
from AniRec.scoring.selection import select_complete_feed, select_feed
from AniRec.api.models import FeedQuery
from AniRec.services.feed_query import query_feed
from AniRec.errors import DataError


def test_complete_order_keeps_first_page_and_every_candidate_once():
    rows = [{"Anime ID": i, "Genres": ["Action" if i % 3 else "Comedy"]} for i in range(703)]
    order = select_complete_feed(rows, 10, 50)
    assert order[:50] == select_feed(rows, 50, 10)
    assert len(order) == len(rows)
    assert set(order) == set(range(len(rows)))
    assert select_complete_feed(rows, 1, 50) == tuple(range(len(rows)))


def test_complete_result_survives_restart_without_profile_metadata_copies(system_temp_dir):
    service = ResultService(root_override=system_temp_dir)
    result = PipelineResult(recommendations=tuple(
        Recommendation(Anime(f"Title {i}", mal_id=i, synopsis="Shared public synopsis" * 50),
                       raw_score=i / 1000, rank=i, model_rank=i, ranked_candidate_count=703)
        for i in range(1, 704)
    ), user_stats={"complete_ranking": True})
    path = service.save("reader-1", result)
    service.save("reader-2", result)
    assert ResultService(root_override=system_temp_dir).load("reader-1") == result
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["storage_format"] == "compact-ranking-v1"
    assert "Shared public synopsis" not in path.read_text(encoding="utf-8")
    assert path.stat().st_size < 100_000
    assert service.load("reader-3") is None


def test_legacy_inline_result_remains_readable(system_temp_dir):
    service = ResultService(root_override=system_temp_dir)
    result = PipelineResult(recommendations=(Recommendation(Anime("Legacy", mal_id=1), rank=1),))
    path = service.path("reader-1")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(result.to_dict()), encoding="utf-8")
    assert service.load("reader-1") == result


def test_shared_metadata_does_not_duplicate_weekly_score_updates(system_temp_dir):
    service = ResultService(root_override=system_temp_dir)
    for reader, score in (("reader-1", 7.1), ("reader-2", 7.2)):
        service.save(reader, PipelineResult(recommendations=(
            Recommendation(Anime("Public title", mal_id=1, mean_score=score,
                                 mean_score_source="offline-snapshot", scoring_users=100), rank=1),
        )))
    with closing(sqlite3.connect(service._metadata_path())) as db:
        assert db.execute("SELECT COUNT(*) FROM anime_metadata").fetchone()[0] == 1
    restarted = ResultService(root_override=system_temp_dir)
    assert restarted.load("reader-1").recommendations[0].anime.mean_score == 7.1
    assert restarted.load("reader-2").recommendations[0].anime.mean_score == 7.2


def test_filters_reach_beyond_500_and_require_every_selected_genre():
    rows = tuple(Recommendation(Anime(f"Title {i}", mal_id=i,
        genres=("Suspense", "Girls Love") if i == 601 else ("Suspense",),
        mean_score=8 if i == 601 else None), rank=i) for i in range(1, 704))
    page, total, number = query_feed(rows, FeedQuery(page=10), set())
    assert page[0].anime.mal_id == 501 and total == 703 and number == 10
    page, total, number = query_feed(rows, FeedQuery(genres=("Suspense", "Girls Love"), minimumMalScore=7), set())
    assert [r.anime.mal_id for r in page] == [601] and total == 1
    assert query_feed(rows, FeedQuery(genres=("Suspense", "Girls Love")), {601})[1] == 0


def test_corrupt_or_unknown_saved_ranking_fails_without_substitution(system_temp_dir):
    service = ResultService(root_override=system_temp_dir)
    result = PipelineResult(recommendations=(Recommendation(Anime("Public", mal_id=1), rank=1),))
    path = service.save("reader-1", result)
    with closing(sqlite3.connect(service._metadata_path())) as db, db:
        db.execute("UPDATE anime_metadata SET payload='{}'")
    with pytest.raises(DataError):
        service.load("reader-1")
    path.write_text(json.dumps({"storage_format": "future-format"}), encoding="utf-8")
    with pytest.raises(DataError):
        service.load("reader-1")
    path.write_text(json.dumps({"storage_format": "compact-ranking-v1", "ranking_data": "%%%"}), encoding="utf-8")
    with pytest.raises(DataError):
        service.load("reader-1")
