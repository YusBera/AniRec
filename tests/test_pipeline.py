from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from AniRec.application.pipeline import (
    FULL_PIPELINE_STEP_IDS,
    SINGLE_STEP_IDS,
    CancellationToken,
    PipelineOrchestrator,
)
from AniRec.errors import CancelledError
from AniRec.infrastructure.csv_storage import CsvStorage
from AniRec.models import PipelineSettings
from AniRec.services import AnimeDataService, ProfileService, RecommendationService


def _orchestrator(
    system_temp_dir,
    top_anime_df,
    completed_anime_df,
    *,
    anime_data=None,
):
    instant = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)
    data_service = anime_data or AnimeDataService(
        top_fetcher=lambda **_kwargs: top_anime_df,
        completed_fetcher=lambda *_args, **_kwargs: completed_anime_df,
    )
    return PipelineOrchestrator(
        anime_data=data_service,
        profiles=ProfileService(root_override=system_temp_dir / "app-data", clock=lambda: instant),
        recommendations=RecommendationService(random_int=lambda _start, _end: 42),
        storage=CsvStorage(),
        access_token_provider=lambda: "fake-access-token",
        clock=lambda: instant,
    )


def test_full_pipeline_runs_six_steps_in_order_and_returns_typed_result(
    system_temp_dir,
    top_anime_df,
    completed_anime_df,
):
    progress = []
    orchestrator = _orchestrator(system_temp_dir, top_anime_df, completed_anime_df)

    result = orchestrator.run_full(
        "fixture-user",
        PipelineSettings(
            top_anime_limit=3,
            recommendation_count=2,
            candidate_pool_size=2,
            randomness_factor=5,
        ),
        progress_callback=progress.append,
    )

    assert tuple(item.stage_id for item in progress) == FULL_PIPELINE_STEP_IDS
    assert [item.current for item in progress] == [1, 2, 3, 4, 5, 6]
    assert all(item.total == 6 for item in progress)
    assert len(result.recommendations) == 2
    assert len(result.genre_stats) >= 1
    assert result.user_stats["completed_count"] == 3
    assert len(result.generated_files) == 6
    assert all(pd.io.common.file_exists(path) for path in result.generated_files)


def test_run_more_appends_unseen_feedback_aware_recommendations_from_saved_candidates(
    system_temp_dir,
    top_anime_df,
    completed_anime_df,
):
    orchestrator = _orchestrator(system_temp_dir, top_anime_df, completed_anime_df)
    settings = PipelineSettings(
        top_anime_limit=3,
        recommendation_count=1,
        candidate_pool_size=2,
        randomness_factor=1,
    )
    initial = orchestrator.run_full("fixture-user", settings)
    expanded = orchestrator.run_more(
        "fixture-user",
        settings,
        existing_recommendations=initial.recommendations,
        genre_adjustments={"Action": 6.0},
        count=1,
    )

    assert len(expanded.recommendations) == 2
    assert expanded.user_stats["added_recommendation_count"] == 1
    assert (
        expanded.recommendations[0].anime.title
        != expanded.recommendations[1].anime.title
    )


def test_sync_prefers_client_id_and_does_not_require_oauth_token(
    system_temp_dir,
    top_anime_df,
    completed_anime_df,
):
    calls = []

    class PublicData:
        def fetch_top_anime(self, **kwargs):
            calls.append(kwargs)
            return top_anime_df

        def fetch_completed_anime(self, _username, **kwargs):
            calls.append(kwargs)
            return completed_anime_df

    orchestrator = PipelineOrchestrator(
        anime_data=PublicData(),
        profiles=ProfileService(root_override=system_temp_dir / "app-data"),
        recommendations=RecommendationService(),
        storage=CsvStorage(),
        access_token_provider=lambda: pytest.fail("OAuth token must not be requested"),
        client_id_provider=lambda: "fixture-client-id",
    )

    orchestrator.run_sync(
        "AniRecFixtureUser",
        PipelineSettings(
            top_anime_limit=3,
            recommendation_count=2,
            candidate_pool_size=3,
        ),
    )

    assert len(calls) == 2
    assert all(call["client_id"] == "fixture-client-id" for call in calls)
    assert all("access_token" not in call for call in calls)


def test_single_step_contract_contains_oauth_and_six_pipeline_actions(
    system_temp_dir,
    top_anime_df,
    completed_anime_df,
):
    assert SINGLE_STEP_IDS == ("oauth", *FULL_PIPELINE_STEP_IDS)
    progress = []
    result = _orchestrator(
        system_temp_dir,
        top_anime_df,
        completed_anime_df,
    ).run_step(
        "oauth",
        "fixture-user",
        PipelineSettings(),
        progress_callback=progress.append,
    )
    assert result.user_stats == {"oauth_connected": 1}
    assert [item.stage_id for item in progress] == ["oauth"]


def test_pipeline_resolves_persisted_mal_id_profile_for_single_step_outputs(
    system_temp_dir,
    top_anime_df,
    completed_anime_df,
):
    orchestrator = _orchestrator(system_temp_dir, top_anime_df, completed_anime_df)
    profile = orchestrator._profiles.create_profile("fixture-user", mal_user_id=42)
    directory = orchestrator._profiles.directory(profile.profile_id, create=True)
    orchestrator._profiles._store.write(profile.to_dict(), directory / "profile.json")
    orchestrator._profiles.set_active(profile.profile_id)

    result = orchestrator.run_step("fetch_top", "fixture-user", PipelineSettings())

    assert Path(result.generated_files[0]).parent == directory
    assert not any(
        path.name.startswith("user-fixture-user-")
        for path in directory.parent.iterdir()
    )


def test_cancellation_stops_before_next_step_and_leaves_no_partial_csv(
    system_temp_dir,
    top_anime_df,
    completed_anime_df,
):
    cancellation = CancellationToken()
    calls = []

    class CancellingDataService:
        def fetch_top_anime(self, **_kwargs):
            calls.append("fetch_top")
            cancellation.cancel()
            return top_anime_df

        def fetch_completed_anime(self, *_args, **_kwargs):
            calls.append("fetch_completed")
            return completed_anime_df

    orchestrator = _orchestrator(
        system_temp_dir,
        top_anime_df,
        completed_anime_df,
        anime_data=CancellingDataService(),
    )

    with pytest.raises(CancelledError):
        orchestrator.run_full(
            "fixture-user",
            PipelineSettings(),
            cancellation_token=cancellation,
        )

    profile_roots = list((system_temp_dir / "app-data" / "profiles").iterdir())
    assert len(profile_roots) == 1
    profile_dir = profile_roots[0]
    assert calls == ["fetch_top"]
    assert not (profile_dir / "top_anime.csv").exists()
    assert list(profile_dir.glob("*.tmp")) == []


def test_atomic_csv_write_preserves_old_file_and_cleans_temp_on_replace_failure(
    system_temp_dir,
):
    destination = system_temp_dir / "result.csv"
    destination.write_text("old-content", encoding="utf-8")

    def fail_replace(_source, _destination):
        raise OSError("fixture replace failure")

    storage = CsvStorage(replace_func=fail_replace)
    with pytest.raises(OSError, match="fixture replace failure"):
        storage.write(pd.DataFrame([{"Title": "New"}]), destination)

    assert destination.read_text(encoding="utf-8") == "old-content"
    assert list(system_temp_dir.glob("*.tmp")) == []


def test_sync_cancellation_preserves_both_previous_valid_files(
    system_temp_dir,
    top_anime_df,
    completed_anime_df,
):
    cancellation = CancellationToken()

    class CancellingSyncData:
        def fetch_top_anime(self, **_kwargs):
            return top_anime_df

        def fetch_completed_anime(self, *_args, **_kwargs):
            cancellation.cancel()
            return completed_anime_df

    orchestrator = _orchestrator(
        system_temp_dir,
        top_anime_df,
        completed_anime_df,
        anime_data=CancellingSyncData(),
    )
    profile = orchestrator._profiles.create_profile("fixture-user")
    directory = orchestrator._profiles.directory(profile.profile_id, create=True)
    top_path = directory / "top_anime.csv"
    completed_path = directory / "completed_anime.csv"
    top_path.write_text("old-top", encoding="utf-8")
    completed_path.write_text("old-completed", encoding="utf-8")

    with pytest.raises(CancelledError):
        orchestrator.run_sync(
            "fixture-user",
            PipelineSettings(),
            cancellation_token=cancellation,
        )

    assert top_path.read_text(encoding="utf-8") == "old-top"
    assert completed_path.read_text(encoding="utf-8") == "old-completed"
    assert list(directory.glob("*.tmp")) == []
    assert list(directory.glob("*.bak")) == []


def test_csv_batch_rolls_back_every_destination_when_second_commit_fails(system_temp_dir):
    import os

    first = system_temp_dir / "first.csv"
    second = system_temp_dir / "second.csv"
    first.write_text("old-first", encoding="utf-8")
    second.write_text("old-second", encoding="utf-8")

    def fail_second_staged_replace(source, destination):
        if Path(source).suffix == ".tmp" and Path(destination) == second:
            raise OSError("fixture second commit failure")
        os.replace(source, destination)

    storage = CsvStorage(replace_func=fail_second_staged_replace)
    with pytest.raises(OSError, match="second commit failure"):
        storage.write_batch(
            (
                (pd.DataFrame([{"Title": "New first"}]), first),
                (pd.DataFrame([{"Title": "New second"}]), second),
            )
        )

    assert first.read_text(encoding="utf-8") == "old-first"
    assert second.read_text(encoding="utf-8") == "old-second"
    assert list(system_temp_dir.glob("*.tmp")) == []
    assert list(system_temp_dir.glob("*.bak")) == []
