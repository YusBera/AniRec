from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from AniRec.application.pipeline import PipelineOrchestrator
from AniRec.gui.workers import (
    OAuthWorker,
    OperationKind,
    RecommendationWorker,
    SyncWorker,
    WorkerController,
    operation_key,
)
from AniRec.gui_main import create_application
from AniRec.infrastructure.csv_storage import CsvStorage
from AniRec.models import AppSettings, PipelineProgress, PipelineResult, PipelineSettings, TokenRecord
from AniRec.services import AnimeDataService, ProfileService, RecommendationService


def wait_until(application, predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        application.processEvents()
        time.sleep(0.002)
    application.processEvents()
    assert predicate()


def test_operation_key_is_stable_per_kind_and_profile():
    assert operation_key(OperationKind.SYNC, " profile-1 ") == "sync:profile-1"
    assert operation_key("recommendation", "profile-1") == "recommendation:profile-1"
    assert operation_key(OperationKind.OAUTH, "profile-1") == "oauth:profile-1"


def test_sync_worker_binds_real_orchestrator_and_persists_source_data(
    system_temp_dir,
    top_anime_df,
    completed_anime_df,
):
    application = create_application([])
    instant = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)
    profiles = ProfileService(root_override=system_temp_dir, clock=lambda: instant)
    orchestrator = PipelineOrchestrator(
        anime_data=AnimeDataService(
            top_fetcher=lambda **_kwargs: top_anime_df,
            completed_fetcher=lambda *_args, **_kwargs: completed_anime_df,
        ),
        profiles=profiles,
        recommendations=RecommendationService(),
        storage=CsvStorage(),
        access_token_provider=lambda: "fake-token",
        clock=lambda: instant,
    )
    controller = WorkerController()
    progress = []
    results = []
    controller.progress_changed.connect(lambda _key, value: progress.append(value))
    controller.result_ready.connect(lambda _key, value: results.append(value))

    key = operation_key(OperationKind.SYNC, "fixture-profile")
    controller.start(key, SyncWorker(orchestrator, "fixture-user", PipelineSettings()))
    wait_until(application, lambda: not controller.active_keys)

    assert [item.stage_id for item in progress] == ["fetch_top", "fetch_completed"]
    assert [item.total for item in progress] == [2, 2]
    assert len(results) == 1
    assert isinstance(results[0], PipelineResult)
    assert results[0].user_stats["completed_count"] == len(completed_anime_df)
    assert all(Path(path).is_file() for path in results[0].generated_files)
    saved_profile = profiles.get_profile(profiles.create_profile("fixture-user").profile_id)
    assert saved_profile.last_sync == instant.isoformat()


class FakeOrchestrator:
    def __init__(self):
        self.calls = []

    def run_full(self, username, settings, *, progress_callback, cancellation_token):
        self.calls.append(("full", username, settings, cancellation_token))
        progress_callback(PipelineProgress("genre_importance", "Calculate genres", 4, 6, True))
        return PipelineResult(user_stats={"mode": "full"})

    def run_step(self, step_id, username, settings, *, progress_callback, cancellation_token):
        self.calls.append((step_id, username, settings, cancellation_token))
        progress_callback(PipelineProgress(step_id, "One step", 1, 1, True))
        return PipelineResult(user_stats={"mode": "step"})


def test_recommendation_worker_supports_full_and_single_step_pipeline():
    application = create_application([])
    orchestrator = FakeOrchestrator()
    controller = WorkerController()
    results = []
    controller.result_ready.connect(lambda key, value: results.append((key, value)))

    controller.start(
        "recommendation:p1",
        RecommendationWorker(orchestrator, "user", PipelineSettings()),
    )
    wait_until(application, lambda: not controller.active_keys)
    controller.start(
        "recommendation-step:p1",
        RecommendationWorker(
            orchestrator,
            "user",
            PipelineSettings(),
            step_id="genre_importance",
        ),
    )
    wait_until(application, lambda: not controller.active_keys)

    assert [call[0] for call in orchestrator.calls] == ["full", "genre_importance"]
    assert [result.user_stats["mode"] for _key, result in results] == ["full", "step"]
    assert all(call[3] is not None for call in orchestrator.calls)


class FakeAuthService:
    def __init__(self):
        self.calls = []

    def authorize(
        self,
        profile_id,
        settings,
        *,
        callback_timeout_seconds,
        cancellation,
        status_callback,
    ):
        self.calls.append(
            (profile_id, settings, callback_timeout_seconds, cancellation, status_callback)
        )
        status_callback("oauth_success")
        return TokenRecord("fake-access-token", expires_at=10_000)


def test_oauth_worker_passes_timeout_and_cancellation_without_exposing_token():
    application = create_application([])
    auth = FakeAuthService()
    controller = WorkerController()
    progress = []
    results = []
    controller.progress_changed.connect(lambda _key, value: progress.append(value))
    controller.result_ready.connect(lambda _key, value: results.append(value))
    settings = AppSettings(client_id="fake-client")

    controller.start(
        "oauth:p1",
        OAuthWorker(auth, "p1", settings, callback_timeout_seconds=45),
    )
    wait_until(application, lambda: not controller.active_keys)

    assert len(auth.calls) == 1
    assert auth.calls[0][:3] == ("p1", settings, 45)
    assert auth.calls[0][3] is not None
    assert progress == [PipelineProgress("oauth", "Connect MyAnimeList account", 0, 0, True)]
    assert len(results) == 1
    assert "fake-access-token" not in repr(results[0])
