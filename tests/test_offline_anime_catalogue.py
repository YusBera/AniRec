"""Public anime metadata may enrich a model feed without changing its scores."""

from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from AniRec.api.models import RecommendationViewModelResponse
from AniRec.api.serialization import view_model_to_dict
from AniRec.core.mal_mapping import anime_from_row
from AniRec.models.domain import Anime, PipelineResult, PipelineSettings, Recommendation
from AniRec.presentation.recommendation_view_model import RecommendationViewModel
from AniRec.scoring.engines import HeuristicRankingEngine
from AniRec.services.cover_url_service import CoverUrlService
from AniRec.services.offline_anime_catalogue import OfflineAnimeCatalogue
from AniRec.services.recommendation_service import RecommendationService


@pytest.fixture
def reference_db(tmp_path):
    path = tmp_path / "anime-reference.sqlite"
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE anime_metadata (
                anime_id INTEGER PRIMARY KEY, canonical_url TEXT, title TEXT,
                title_english TEXT, title_japanese TEXT, synonyms_json TEXT,
                media_type TEXT, episodes INTEGER, airing_status TEXT,
                content_rating TEXT, score REAL, scored_by INTEGER, rank INTEGER,
                popularity INTEGER, members INTEGER, start_date TEXT,
                end_date TEXT, genres_json TEXT, themes_json TEXT,
                demographics_json TEXT, studios_json TEXT, synopsis TEXT,
                image_url_medium TEXT, image_url_large TEXT, trailer_url TEXT,
                related_anime_json TEXT, source_html_scraped_at TEXT,
                baseline_scraped_at TEXT, parse_status TEXT NOT NULL
            );
            CREATE TABLE field_observation (
                anime_id INTEGER NOT NULL, field_name TEXT NOT NULL,
                state TEXT NOT NULL, source_name TEXT NOT NULL,
                checked_at TEXT, issue TEXT, PRIMARY KEY (anime_id, field_name)
            );
            CREATE TABLE snapshot_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO snapshot_meta VALUES ('format_version', 'offline-staging-1');
            INSERT INTO anime_metadata (
                anime_id, title, score, scored_by, popularity, members,
                synopsis, image_url_medium, image_url_large, trailer_url,
                parse_status
            ) VALUES
                (1, 'Known', 8.4, 100, 400, 5000, 'Real synopsis',
                 'https://cdn.myanimelist.net/images/anime/1.jpg',
                 'https://cdn.myanimelist.net/images/anime/1.jpg',
                 'https://www.youtube.com/watch?v=abc123', 'parsed'),
                (2, 'Unscored', NULL, NULL, 1200, 100, 'Second synopsis',
                 'https://cdn.myanimelist.net/images/anime/2.jpg',
                 'https://cdn.myanimelist.net/images/anime/2.jpg', NULL, 'parsed');
            INSERT INTO field_observation VALUES
                (1, 'score', 'present', 'stored_mal_html', '2026-09-20', NULL),
                (1, 'scored_by', 'present', 'stored_mal_html', '2026-09-20', NULL),
                (1, 'popularity', 'present', 'stored_mal_html', '2026-09-20', NULL),
                (1, 'members', 'present', 'stored_mal_html', '2026-09-20', NULL),
                (1, 'synopsis', 'present', 'stored_mal_html', '2026-09-20', NULL),
                (1, 'image_url_medium', 'present', 'stored_mal_html', '2026-09-20', NULL),
                (1, 'image_url_large', 'present', 'stored_mal_html', '2026-09-20', NULL),
                (1, 'trailer_url', 'present', 'stored_mal_html', '2026-09-20', NULL),
                (2, 'score', 'confirmed_absent', 'stored_mal_html', '2026-09-20', NULL),
                (2, 'popularity', 'present', 'stored_mal_html', '2026-09-20', NULL),
                (2, 'members', 'present', 'stored_mal_html', '2026-09-20', NULL),
                (2, 'synopsis', 'present', 'stored_mal_html', '2026-09-20', NULL),
                (2, 'image_url_medium', 'present', 'stored_mal_html', '2026-09-20', NULL),
                (2, 'image_url_large', 'present', 'stored_mal_html', '2026-09-20', NULL);
        """)
    return path


def test_candidate_values_are_sourced_and_unrated_is_not_zero(reference_db):
    catalogue = OfflineAnimeCatalogue(reference_db)
    rows = catalogue.enrich_candidates([
        {"Anime ID": 1, "Title": "Known", "Mean Score": None},
        {"Anime ID": 2, "Title": "Unscored", "Mean Score": None},
        {"Anime ID": 3, "Title": "Not in snapshot", "Mean Score": None},
    ])
    assert rows[0]["Mean Score"] == 8.4
    assert rows[0]["Scoring Users"] == 100
    assert rows[0]["Catalog Members"] == 5000
    assert rows[0]["Catalog Popularity"] == 400
    assert rows[0]["Mean Score Source"] == "offline-snapshot"
    assert rows[1]["Mean Score"] is None
    assert rows[1]["Mean Score Source"] == "offline-absent"
    assert rows[2]["Mean Score"] is None


def test_selected_metadata_reaches_card_and_unsafe_links_are_rejected(reference_db):
    catalogue = OfflineAnimeCatalogue(reference_db)
    row = catalogue.enrich_selected([{
        "Anime ID": 1, "Title": "Known", "Mean Score": 8.4,
        "Mean Score Source": "offline-snapshot",
    }])[0]
    anime = anime_from_row(row)
    model = RecommendationViewModel.from_recommendation(Recommendation(anime))
    assert model.synopsis == "Real synopsis"
    assert model.cover_url == "https://cdn.myanimelist.net/images/anime/1.jpg"
    assert model.pv_youtube_url == "https://www.youtube.com/watch?v=abc123"
    with sqlite3.connect(reference_db) as db:
        db.execute("UPDATE anime_metadata SET trailer_url='https://evil.example/watch?v=1' WHERE anime_id=1")
    bad = catalogue.enrich_selected([{"Anime ID": 1, "Title": "Known"}])[0]
    assert anime_from_row(bad).pv_youtube_url is None
    with sqlite3.connect(reference_db) as db:
        db.execute("UPDATE anime_metadata SET image_url_medium='https://[invalid' WHERE anime_id=1")
    malformed = catalogue.enrich_selected([{"Anime ID": 1, "Title": "Known"}])[0]
    assert malformed.get("Picture URL") is None


def test_saved_feed_gets_display_metadata_without_changing_its_rank_inputs(reference_db, tmp_path):
    catalogue = OfflineAnimeCatalogue(reference_db)
    original = PipelineResult(recommendations=(
        Recommendation(Anime("Known", mal_id=1, mean_score=7.0, scoring_users=80),
                       model_rank=17, raw_score=2.3),
        Recommendation(Anime("Unscored", mal_id=2, mean_score=None,
                             mean_score_source="offline-absent"),
                       model_rank=44, raw_score=1.2),
    ))
    result = catalogue.enrich_result(original)
    assert [(r.model_rank, r.raw_score) for r in result.recommendations] == [(17, 2.3), (44, 1.2)]
    assert result.recommendations[0].anime.mean_score == 7.0
    assert result.recommendations[0].anime.scoring_users == 80
    assert result.recommendations[0].anime.synopsis == "Real synopsis"
    assert result.recommendations[1].anime.mean_score is None
    assert result.recommendations[1].anime.mean_score_source == "offline-absent"
    # A confirmed absence and a supplied poster must not cause another MAL request.
    class NoRequests:
        def get_json(self, *_args, **_kwargs):
            raise AssertionError("The offline reference already checked this title")

    assert CoverUrlService(root_override=tmp_path, client=NoRequests()).fill(result, "configured-id") == result


def test_saved_newer_api_score_is_not_replaced_by_old_absence(reference_db):
    result = PipelineResult(recommendations=(Recommendation(Anime(
        "Unscored", mal_id=2, mean_score=7.1, mean_score_source="mal-api"
    )),))
    updated = OfflineAnimeCatalogue(reference_db).enrich_result(result)
    assert updated.recommendations[0].anime.mean_score == 7.1
    assert updated.recommendations[0].anime.mean_score_source == "mal-api"


def test_owned_catalogue_ranking_and_api_receive_offline_fields(reference_db):
    class OwnedHeuristic(HeuristicRankingEngine):
        def candidate_catalog(self, **_kwargs):
            return (
                {"Anime ID": 1, "Title": "Known", "Genres": ["Action"],
                 "Mean Score": None, "Scoring Users": None},
                {"Anime ID": 2, "Title": "Unscored", "Genres": ["Drama"],
                 "Mean Score": None, "Scoring Users": None},
            )

    service = RecommendationService(
        ranker=OwnedHeuristic(), anime_reference=OfflineAnimeCatalogue(reference_db)
    )
    candidates = service.candidate_catalog()
    assert candidates.loc[0, "Mean Score"] == 8.4
    assert pd.isna(candidates.loc[1, "Mean Score"])
    ranked = service.recommend(
        candidates, pd.DataFrame([{"Genre": "Action", "Importance_Score": 100.0}]),
        PipelineSettings(recommendation_count=2, candidate_pool_size=2, randomness_factor=1),
    )
    known = next(row for row in ranked.to_dict("records") if row["Anime ID"] == 1)
    assert known["Picture URL"] == "https://cdn.myanimelist.net/images/anime/1.jpg"
    assert known["Synopsis"] == "Real synopsis"
    anime = anime_from_row(known)
    response = RecommendationViewModelResponse.model_validate(view_model_to_dict(
        RecommendationViewModel.from_recommendation(Recommendation(anime))
    ))
    assert response.mal_score == 8.4
    assert response.pv_youtube_url == "https://www.youtube.com/watch?v=abc123"


def test_configured_invalid_snapshot_fails_closed(tmp_path):
    path = tmp_path / "wrong.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE unrelated (value TEXT)")
    with pytest.raises(ValueError, match="anime reference"):
        OfflineAnimeCatalogue(path)
