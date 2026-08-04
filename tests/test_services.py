from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from infrastructure.csv_storage import CsvStorage
from models import PipelineSettings
from services import AnimeDataService, ProfileService, RecommendationService


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_anime_data_service_injects_http_client():
    calls = []

    def fake_get(url, params, headers, timeout):
        calls.append((url, params, headers, timeout))
        return FakeResponse(
            {
                "data": [
                    {
                            "node": {
                                "id": 1,
                                "title": "Fixture",
                            "genres": [{"name": "Action"}],
                            "mean": 8.0,
                        }
                    }
                ]
            }
        )

    service = AnimeDataService(http_get=fake_get)
    result = service.fetch_top_anime(limit=1, access_token="fake-token")

    assert result["Title"].tolist() == ["Fixture"]
    assert len(calls) == 1


def test_anime_data_service_supports_public_client_id_auth():
    calls = []

    def fake_get(url, params, headers, timeout):
        calls.append(headers)
        return FakeResponse({"data": []})

    service = AnimeDataService(http_get=fake_get)
    result = service.fetch_top_anime(limit=1, client_id="fixture-client")

    assert result.empty
    assert calls == [{"X-MAL-CLIENT-ID": "fixture-client"}]


def test_profile_service_injects_root_and_clock(system_temp_dir):
    instant = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)
    service = ProfileService(
        root_override=system_temp_dir / "app-data",
        clock=lambda: instant,
    )

    profile = service.create_profile("Kullanıcı Çığ")
    directory = service.directory(profile.profile_id, create=True)
    synced = service.mark_synced(profile)

    assert directory.is_dir()
    assert directory.parent == (system_temp_dir / "app-data").resolve() / "profiles"
    assert synced.last_sync == "2026-08-03T12:00:00+00:00"


def test_recommendation_service_is_in_memory_and_randomness_is_injected(
    completed_anime_df,
    top_anime_df,
):
    service = RecommendationService(random_int=lambda _start, _end: 42)
    imputed = service.impute_missing_scores(completed_anime_df)
    genre = service.calculate_genre_importance(imputed)
    candidates = service.create_candidates(imputed, top_anime_df)
    recommendations = service.recommend(
        candidates,
        genre,
        PipelineSettings(recommendation_count=2, candidate_pool_size=2),
    )

    assert imputed["User Score"].isna().sum() == 0
    assert list(genre.columns) == ["Genre", "Importance_Score"]
    assert candidates["Title"].tolist() == ["Gamma Show", "Delta Show"]
    assert len(recommendations) == 2


def test_csv_storage_is_the_dataframe_persistence_boundary(system_temp_dir):
    storage = CsvStorage()
    source = pd.DataFrame([{"Title": "Fixture", "Genres": "['Action']"}])
    path = storage.write(source, system_temp_dir / "nested" / "fixture.csv")
    result = storage.read(path, required_columns=["Title", "Genres"])
    assert result.to_dict("records") == source.to_dict("records")


def test_service_modules_do_not_import_qt(repo_root):
    service_root = repo_root / "AniRec" / "services"
    imported_modules = []
    for path in service_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.append(node.module)
    assert not any(name.startswith(("PySide6", "PyQt")) for name in imported_modules)
