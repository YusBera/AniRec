from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from AniRec.application.pipeline import (
    CANDIDATE_CATALOGUE_FILENAME,
    CATALOGUE_SOURCE_COLUMN,
    FULL_PIPELINE_STEP_IDS,
    LEGACY_MAL_CATALOGUE_SOURCE,
    OWNED_CATALOGUE_SOURCE,
    SINGLE_STEP_IDS,
    CancellationToken,
    PipelineOrchestrator,
)
from AniRec.errors import CancelledError, DataError
from AniRec.infrastructure.csv_storage import CsvStorage
from AniRec.models import PipelineSettings, UserProfile
from AniRec.scoring.engines import HeuristicRankingEngine
from AniRec.scoring.contracts import RankingEngineMetadata
from AniRec.scoring.eligibility import EligibilityAudit
from AniRec.services import AnimeDataService, ProfileService, RecommendationService


def _orchestrator(
    system_temp_dir,
    top_anime_df,
    completed_anime_df,
    *,
    anime_data=None,
    recommendations=None,
):
    instant = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)
    data_service = anime_data or AnimeDataService(
        top_fetcher=lambda **_kwargs: top_anime_df,
        completed_fetcher=lambda *_args, **_kwargs: completed_anime_df,
    )
    return PipelineOrchestrator(
        anime_data=data_service,
        profiles=ProfileService(root_override=system_temp_dir / "app-data", clock=lambda: instant),
        recommendations=(
            recommendations
            or RecommendationService(random_int=lambda _start, _end: 42)
        ),
        storage=CsvStorage(),
        access_token_provider=lambda: "fake-access-token",
        clock=lambda: instant,
    )


def test_sync_uses_bound_profile_and_credentials_after_active_switch(
    system_temp_dir, top_anime_df, completed_anime_df,
):
    seen_credentials = []
    def completed_fetcher(_username, access_token=None, **kwargs):
        seen_credentials.append({"access_token": access_token, **kwargs})
        return completed_anime_df

    anime_data = AnimeDataService(
        top_fetcher=lambda **kwargs: seen_credentials.append(kwargs) or top_anime_df,
        completed_fetcher=completed_fetcher,
    )
    orchestrator = _orchestrator(
        system_temp_dir, top_anime_df, completed_anime_df, anime_data=anime_data,
    )
    bound = UserProfile(profile_id="bound", username="fixture-user")
    other = UserProfile(profile_id="other", username="fixture-user")
    profiles = orchestrator._profiles
    directory = profiles.directory(other.profile_id, create=True)
    (directory / "profile.json").write_text(json.dumps(other.to_dict()), encoding="utf-8")
    profiles.set_active(other.profile_id)

    result = orchestrator.run_sync(
        bound.username, PipelineSettings(), profile_override=bound,
        access_token_provider=lambda: "bound-token",
    )

    assert result.generated_files
    assert all(Path(path).parent.name == "bound" for path in result.generated_files)
    assert not (directory / "completed_anime.csv").exists()
    assert seen_credentials
    assert all(kwargs.get("access_token") == "bound-token" for kwargs in seen_credentials)


def test_full_and_more_keep_bound_profile_after_active_switch(
    system_temp_dir, top_anime_df, completed_anime_df,
):
    orchestrator = _orchestrator(system_temp_dir, top_anime_df, completed_anime_df)
    orchestrator._access_token_provider = lambda: pytest.fail("unbound token used")
    bound = UserProfile(profile_id="bound", username="fixture-user")
    other = UserProfile(profile_id="other", username="fixture-user")
    profiles = orchestrator._profiles
    other_directory = profiles.directory(other.profile_id, create=True)
    (other_directory / "profile.json").write_text(json.dumps(other.to_dict()), encoding="utf-8")
    profiles.set_active(other.profile_id)
    settings = PipelineSettings(
        top_anime_limit=3, recommendation_count=1,
        candidate_pool_size=2, randomness_factor=1,
    )

    initial = orchestrator.run_full(
        bound.username, settings, profile_override=bound,
        access_token_provider=lambda: "bound-token",
    )
    expanded = orchestrator.run_more(
        bound.username, settings, profile_override=bound,
        existing_recommendations=initial.recommendations, count=1,
    )

    assert all(Path(path).parent.name == "bound" for path in initial.generated_files)
    assert len(expanded.recommendations) == 2
    assert not (other_directory / "completed_anime.csv").exists()
    assert not (other_directory / "ranking_signals.csv").exists()


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
    assert result.user_stats["eligibility_policy_version"] == "anirec-final-eligibility-v1"
    assert result.user_stats["eligibility_input_count"] == 2
    assert result.user_stats["eligibility_eligible_count"] == 2
    assert result.user_stats["candidate_catalogue_source"] == LEGACY_MAL_CATALOGUE_SOURCE
    # Six pipeline outputs plus the ranking signals "more" reuses.
    assert len(result.generated_files) == 7
    assert any(path.endswith("ranking_signals.csv") for path in result.generated_files)
    assert all(pd.io.common.file_exists(path) for path in result.generated_files)
    catalogue_path = next(
        Path(path)
        for path in result.generated_files
        if path.endswith(CANDIDATE_CATALOGUE_FILENAME)
    )
    persisted_catalogue = pd.read_csv(catalogue_path)
    assert set(persisted_catalogue[CATALOGUE_SOURCE_COLUMN]) == {
        LEGACY_MAL_CATALOGUE_SOURCE
    }


def test_sequence_pipeline_fetches_persists_and_passes_full_history(
    system_temp_dir,
    top_anime_df,
    completed_anime_df,
):
    history = pd.DataFrame(
        [
            {
                "Anime ID": 101,
                "Title": "Chronology source",
                "Status": "completed",
                "User Score": 8,
                "Episodes Watched": 12,
                "Is Rewatching": False,
                "Updated At": "2026-08-01T12:00:00+00:00",
            }
        ]
    )
    history_calls = []

    class CapturingRanker:
        requires_user_history = True

        def __init__(self):
            self.requests = []
            self.delegate = HeuristicRankingEngine()

        def rank(self, request):
            self.requests.append(request)
            return self.delegate.rank(request)

        def candidate_catalog(self, *, include_nsfw, as_of):
            assert include_nsfw is False
            assert as_of.isoformat() == "2026-08-03"
            return (
                {
                    "Anime ID": 200,
                    "Title": "Frozen catalogue one",
                    "Genres": ["Action"],
                    "Mean Score": None,
                },
                {
                    "Anime ID": 201,
                    "Title": "Frozen catalogue two",
                    "Genres": ["Drama"],
                    "Mean Score": None,
                },
            )

    ranker = CapturingRanker()
    data_service = AnimeDataService(
        top_fetcher=lambda **_kwargs: pytest.fail(
            "installed catalogue must bypass the MAL ranking endpoint"
        ),
        completed_fetcher=lambda *_args, **_kwargs: completed_anime_df,
        history_fetcher=lambda *_args, **_kwargs: (
            history_calls.append("fetch") or history.copy()
        ),
    )
    orchestrator = PipelineOrchestrator(
        anime_data=data_service,
        profiles=ProfileService(root_override=system_temp_dir / "app-data"),
        recommendations=RecommendationService(ranker=ranker),
        storage=CsvStorage(),
        access_token_provider=lambda: "fake-access-token",
        clock=lambda: datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc),
    )

    result = orchestrator.run_full(
        "fixture-user",
        PipelineSettings(
            top_anime_limit=3,
            recommendation_count=2,
            candidate_pool_size=2,
        ),
    )

    assert history_calls == ["fetch"]
    assert ranker.requests[0].user_history == tuple(history.to_dict("records"))
    assert {row.get("Anime ID") for row in ranker.requests[0].candidates} == {200, 201}
    assert {
        row.get("Anime ID")
        for row in ranker.requests[0].context["fallback_candidates"]
    } == {200, 201}
    assert result.user_stats["ranking_engine_id"] == "heuristic"
    assert result.user_stats["ranking_engine_version"] == "1"
    assert result.user_stats["candidate_count"] == 2
    assert result.user_stats["candidate_catalogue_count"] == 2
    assert result.user_stats["candidate_catalogue_source"] == OWNED_CATALOGUE_SOURCE
    catalogue_paths = [
        Path(path)
        for path in result.generated_files
        if path.endswith(CANDIDATE_CATALOGUE_FILENAME)
    ]
    assert len(catalogue_paths) == 1
    saved_catalogue = pd.read_csv(catalogue_paths[0])
    assert set(saved_catalogue[CATALOGUE_SOURCE_COLUMN]) == {OWNED_CATALOGUE_SOURCE}
    history_paths = [Path(path) for path in result.generated_files if path.endswith("user_history.csv")]
    assert len(history_paths) == 1
    saved = pd.read_csv(history_paths[0])
    assert saved["Anime ID"].tolist() == [101]


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
    # "More" continues the feed's ranking, so it must see the same feedback
    # the feed was ranked with.
    initial = orchestrator.run_full(
        "fixture-user", settings, genre_adjustments={"Action": 6.0}
    )
    expanded = orchestrator.run_more(
        "fixture-user",
        settings,
        existing_recommendations=initial.recommendations,
        genre_adjustments={"Action": 6.0},
        count=1,
    )

    assert len(expanded.recommendations) == 2
    assert expanded.user_stats["added_recommendation_count"] == 1
    assert expanded.user_stats["candidate_catalogue_source"] == (
        LEGACY_MAL_CATALOGUE_SOURCE
    )
    assert expanded.user_stats["candidate_catalogue_count"] == initial.user_stats[
        "candidate_catalogue_count"
    ]
    assert expanded.user_stats["candidate_snapshot_count"] == initial.user_stats[
        "candidate_count"
    ]
    assert (
        expanded.recommendations[0].anime.title
        != expanded.recommendations[1].anime.title
    )

    regenerated = orchestrator.run_step(
        "generate_recommendations", "fixture-user", settings
    )
    assert regenerated.user_stats["candidate_catalogue_source"] == (
        LEGACY_MAL_CATALOGUE_SOURCE
    )
    assert regenerated.user_stats["candidate_catalogue_count"] == (
        initial.user_stats["candidate_catalogue_count"]
    )
    assert regenerated.user_stats["candidate_snapshot_count"] == (
        initial.user_stats["candidate_count"]
    )


def test_run_more_refuses_when_persisted_candidates_changed_since_the_feed(
    system_temp_dir,
    top_anime_df,
    completed_anime_df,
):
    orchestrator = _orchestrator(system_temp_dir, top_anime_df, completed_anime_df)
    settings = PipelineSettings(
        top_anime_limit=3,
        recommendation_count=1,
        candidate_pool_size=3,
        randomness_factor=1,
    )
    initial = orchestrator.run_full("fixture-user", settings)
    profile = orchestrator._profiles.resolve_profile("fixture-user")
    directory = orchestrator._profiles.directory(profile.profile_id)
    candidate_path = directory / "recommendation_candidates.csv"
    persisted = pd.read_csv(candidate_path)
    future = {column: None for column in persisted.columns}
    future.update({
        "Anime ID": 999999,
        "Title": "Future injected candidate",
        "Genres": "['Action']",
        "Mean Score": 10.0,
        "Start Date": "2030-01-01",
        "Anime Status": "not_yet_aired",
    })
    pd.concat([persisted, pd.DataFrame([future])], ignore_index=True).to_csv(
        candidate_path, index=False
    )

    # Continuing a ranking over a changed population would mix two rankings
    # in one feed; the tampered snapshot is refused instead of trusted.
    with pytest.raises(DataError, match="Generate a new feed"):
        orchestrator.run_more(
            "fixture-user",
            settings,
            existing_recommendations=initial.recommendations,
            count=1,
        )


def test_pipeline_uses_result_owned_provenance_instead_of_shared_last_state(
    system_temp_dir,
    top_anime_df,
    completed_anime_df,
):
    class MisleadingLastStateService(RecommendationService):
        def recommend(self, *args, **kwargs):
            ranked = super().recommend(*args, **kwargs)
            self._last_ranking_metadata = RankingEngineMetadata(
                engine_id="raced-engine",
                engine_version="wrong",
                feature_schema_version="wrong",
                explanation_type="wrong",
            )
            self._last_eligibility_audit = EligibilityAudit(
                policy_version="raced-policy",
                catalog_version="wrong",
                input_candidates=999,
                eligible_candidates=0,
                excluded_by_reason={"wrong": 999},
            )
            return ranked

    service = MisleadingLastStateService(random_int=lambda _start, _end: 42)
    orchestrator = _orchestrator(
        system_temp_dir,
        top_anime_df,
        completed_anime_df,
        recommendations=service,
    )

    result = orchestrator.run_full(
        "fixture-user",
        PipelineSettings(recommendation_count=1, candidate_pool_size=2),
    )

    assert service.last_ranking_metadata.engine_id == "raced-engine"
    assert result.user_stats["ranking_engine_id"] == "heuristic"
    assert result.user_stats["eligibility_policy_version"] == "anirec-final-eligibility-v1"
    assert result.user_stats["eligibility_input_count"] == 2


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


def test_installed_catalogue_bypasses_ranking_for_sync_and_single_step(
    system_temp_dir,
    completed_anime_df,
):
    class InstalledCatalogue:
        requires_user_history = False

        def candidate_catalog(self, **_kwargs):
            return (
                {
                    "Anime ID": 200,
                    "Title": "Owned catalogue title",
                    "Genres": ["Action"],
                },
            )

    data = AnimeDataService(
        top_fetcher=lambda **_kwargs: pytest.fail(
            "installed catalogue must bypass MAL ranking"
        ),
        completed_fetcher=lambda *_args, **_kwargs: completed_anime_df,
    )
    orchestrator = PipelineOrchestrator(
        anime_data=data,
        profiles=ProfileService(root_override=system_temp_dir / "owned-app-data"),
        recommendations=RecommendationService(ranker=InstalledCatalogue()),
        storage=CsvStorage(),
        access_token_provider=lambda: pytest.fail(
            "catalogue-only single step must not request OAuth"
        ),
        client_id_provider=lambda: "fixture-client-id",
    )

    synced = orchestrator.run_sync("fixture-user", PipelineSettings())
    loaded = orchestrator.run_step("fetch_top", "fixture-user", PipelineSettings())

    assert synced.user_stats["candidate_catalogue_source"] == OWNED_CATALOGUE_SOURCE
    assert loaded.user_stats["candidate_catalogue_source"] == OWNED_CATALOGUE_SOURCE
    saved = pd.read_csv(loaded.generated_files[0])
    assert set(saved[CATALOGUE_SOURCE_COLUMN]) == {OWNED_CATALOGUE_SOURCE}


def test_empty_installed_catalogue_fails_without_calling_mal_ranking(
    system_temp_dir,
    completed_anime_df,
):
    class EmptyInstalledCatalogue:
        requires_user_history = False

        def candidate_catalog(self, **_kwargs):
            return ()

    orchestrator = PipelineOrchestrator(
        anime_data=AnimeDataService(
            top_fetcher=lambda **_kwargs: pytest.fail(
                "empty installed catalogue must not switch to MAL ranking"
            ),
            completed_fetcher=lambda *_args, **_kwargs: completed_anime_df,
        ),
        profiles=ProfileService(root_override=system_temp_dir / "empty-app-data"),
        recommendations=RecommendationService(ranker=EmptyInstalledCatalogue()),
        storage=CsvStorage(),
        client_id_provider=lambda: "fixture-client-id",
    )

    with pytest.raises(DataError, match="installed candidate catalogue has no eligible"):
        orchestrator.run_full("fixture-user", PipelineSettings())


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
    assert Path(result.generated_files[0]).name == CANDIDATE_CATALOGUE_FILENAME
    assert result.user_stats["candidate_catalogue_source"] == LEGACY_MAL_CATALOGUE_SOURCE
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
    assert not (profile_dir / CANDIDATE_CATALOGUE_FILENAME).exists()
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
    top_path = directory / CANDIDATE_CATALOGUE_FILENAME
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


def test_full_more_and_single_step_share_one_deterministic_selection(
    system_temp_dir,
    completed_anime_df,
    monkeypatch,
):
    import AniRec.services.recommendation_service as service_module

    studios = ["Madhouse", "Bones", "MAPPA"]
    catalogue = pd.DataFrame(
        [
            {
                "Anime ID": 500 + index,
                "Title": f"Catalogue {index:02d}",
                "Genres": ["Action", ["Drama", "Comedy", "Mystery", "Romance"][index % 4]],
                "Studios": [studios[index % 3]],
                "Source": ["Manga", "Original"][index % 2],
                "Media Type": "tv",
                "Mean Score": 9.0 - index * 0.05,
            }
            for index in range(20)
        ]
    )
    calls = []
    real = service_module.select_feed

    def counting(rows, count, adventurousness):
        calls.append((count, adventurousness))
        return real(rows, count, adventurousness)

    monkeypatch.setattr(service_module, "select_feed", counting)
    settings = PipelineSettings(
        top_anime_limit=20,
        recommendation_count=5,
        candidate_pool_size=20,
        randomness_factor=10,
    )

    def orchestrator():
        # Production construction: no injected seed source.
        return _orchestrator(
            system_temp_dir,
            catalogue,
            completed_anime_df,
            recommendations=RecommendationService(),
        )

    initial = orchestrator().run_full("fixture-user", settings)
    initial_ids = [item.anime.mal_id for item in initial.recommendations]
    assert calls == [(5, 10)]

    # Single-step reads the persisted CSV candidates and must serve the same feed.
    step = orchestrator().run_step("generate_recommendations", "fixture-user", settings)
    assert [item.anime.mal_id for item in step.recommendations] == initial_ids
    assert calls == [(5, 10), (5, 10)]

    # "More" no longer draws a fresh random seed: repeated requests agree.
    more = [
        orchestrator().run_more(
            "fixture-user",
            settings,
            existing_recommendations=initial.recommendations,
            count=3,
        )
        for _ in range(2)
    ]
    added = [
        [item.anime.mal_id for item in result.recommendations[len(initial_ids):]]
        for result in more
    ]
    assert added[0] == added[1]
    assert len(added[0]) == 3
    assert not set(added[0]) & set(initial_ids)
    assert calls[2:] == [(3, 10), (3, 10)]
