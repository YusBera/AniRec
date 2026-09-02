from __future__ import annotations

from datetime import datetime, timezone
import time

from AniRec.application.pipeline import PipelineOrchestrator
from AniRec.gui.home_page import (
    ACTION_GENERATE,
    ACTION_OPEN_FOLDER,
    ACTION_OPEN_RECOMMENDATIONS,
    ACTION_SYNC,
    ACTION_VIEW_GENRES,
)
from AniRec.gui.main_window import MainWindow, PageId
from AniRec.gui.taste_profile import SampleTasteProfileProvider
from AniRec.gui.texts import DASHBOARD_TEXT
from AniRec.gui_main import create_application
from AniRec.infrastructure.csv_storage import CsvStorage
from AniRec.models import AppSettings, Anime, GenreStat, PipelineResult, Recommendation
from AniRec.services import (
    AnimeDataService,
    ProfileService,
    RecommendationStateService,
    RecommendationService,
    ResultService,
    SettingsService,
)


def create_dashboard_state(system_temp_dir, *, open_path=lambda _path: True):
    instant = datetime(2026, 8, 3, 14, 30, tzinfo=timezone.utc)
    profiles = ProfileService(
        root_override=system_temp_dir,
        clock=lambda: instant,
        open_path=open_path,
    )
    profile = profiles.create_profile("fixture-user")
    profiles.directory(profile.profile_id, create=True)
    profile = profiles.mark_synced(profile)
    profiles.set_active(profile.profile_id)
    results = ResultService(root_override=system_temp_dir)
    result = PipelineResult(
        recommendations=tuple(
            Recommendation(
                Anime(f"Romaji {index}", english_title=f"English {index}"),
                rank=index,
            )
            for index in range(1, 7)
        ),
        genre_stats=tuple(
            GenreStat(name, importance_score=score)
            for name, score in (
                ("Drama", 20),
                ("Action", 50),
                ("Comedy", 30),
                ("Fantasy", 10),
                ("Mystery", 40),
                ("Sci-Fi", 5),
            )
        ),
        user_stats={"completed_count": 42, "rated_count": 38},
        completed_at=instant.isoformat(),
    )
    results.save(profile.profile_id, result)
    return profiles, results, profile, result


def test_empty_dashboard_explains_every_missing_prerequisite():
    create_application([])
    window = MainWindow()
    home = window.home_page

    assert home.empty_state_label.text() == DASHBOARD_TEXT.empty_state
    assert home.metric_values["username"].text() == DASHBOARD_TEXT.not_connected
    assert all(not button.isEnabled() for button in home.action_buttons.values())
    assert home.action_reasons[ACTION_SYNC].text() == DASHBOARD_TEXT.profile_required
    assert home.action_reasons[ACTION_OPEN_FOLDER].text() == DASHBOARD_TEXT.folder_required
    window.close()


def test_dashboard_loads_profile_metrics_top_genres_and_recent_english_titles(
    system_temp_dir,
):
    create_application([])
    profiles, results, profile, _result = create_dashboard_state(system_temp_dir)

    window = MainWindow(profile_service=profiles, result_service=results)
    home = window.home_page

    assert home.metric_values["username"].text() == "fixture-user"
    assert home.metric_values["completed"].text() == "42"
    assert home.metric_values["rated"].text() == "38"
    assert home.metric_values["genres"].text() == "6"
    assert home.metric_values["last_sync"].text() == "03 Aug 2026 · 17:30"
    assert home.metric_values["recommendations"].text() == "6"
    assert [home.genre_list.item(index).text() for index in range(5)] == [
        "Action: 50.0",
        "Mystery: 40.0",
        "Comedy: 30.0",
        "Drama: 20.0",
        "Fantasy: 10.0",
    ]
    assert [home.recommendation_list.item(index).text() for index in range(5)] == [
        "English 1",
        "English 2",
        "English 3",
        "English 4",
        "English 5",
    ]
    assert all(button.isEnabled() for button in home.action_buttons.values())
    assert [model.genre for model in window.genre_analysis_page.models[:3]] == [
        "Action",
        "Mystery",
        "Comedy",
    ]
    window.close()


def test_dashboard_actions_route_to_requests_pages_and_safe_profile_folder(system_temp_dir):
    application = create_application([])
    opened_paths = []
    profiles, results, profile, _result = create_dashboard_state(
        system_temp_dir,
        open_path=lambda path: not opened_paths.append(path),
    )
    window = MainWindow(profile_service=profiles, result_service=results)
    requested_sync = []
    requested_recommendations = []
    emitted_folders = []
    window.sync_requested.connect(lambda: requested_sync.append(True))
    window.recommendations_requested.connect(lambda: requested_recommendations.append(True))
    window.output_folder_opened.connect(emitted_folders.append)
    home = window.home_page

    home.action_buttons[ACTION_SYNC].click()
    home.action_buttons[ACTION_GENERATE].click()
    home.action_buttons[ACTION_OPEN_RECOMMENDATIONS].click()
    application.processEvents()
    # Recommendations and the taste summary both live on Discover now.
    assert window.current_page_id is PageId.DISCOVER
    window.navigate_to(PageId.SETTINGS)
    home.action_buttons[ACTION_VIEW_GENRES].click()
    application.processEvents()
    assert window.current_page_id is PageId.DISCOVER
    home.action_buttons[ACTION_OPEN_FOLDER].click()

    assert requested_sync == [True]
    assert requested_recommendations == [True]
    assert opened_paths == [profiles.directory(profile.profile_id)]
    assert emitted_folders == opened_paths
    window.close()


def test_running_operation_disables_only_its_start_action(system_temp_dir):
    create_application([])
    profiles, results, profile, _result = create_dashboard_state(system_temp_dir)
    window = MainWindow(profile_service=profiles, result_service=results)

    window._on_operation_started(f"sync:{profile.profile_id}")
    assert not window.home_page.action_buttons[ACTION_SYNC].isEnabled()
    assert (
        window.home_page.action_reasons[ACTION_SYNC].text()
        == DASHBOARD_TEXT.operation_running
    )
    assert window.home_page.action_buttons[ACTION_GENERATE].isEnabled()

    window._on_operation_finished(f"sync:{profile.profile_id}")
    assert window.home_page.action_buttons[ACTION_SYNC].isEnabled()
    window.close()


def test_cover_work_does_not_flash_engine_busy_and_parallel_work_stays_busy():
    create_application([])
    window = MainWindow()

    window._on_operation_started("cover:poster")
    assert not window._engine_busy

    window._on_operation_started("sync:profile-a")
    window._on_operation_started("recommendation:profile-a")
    window._on_operation_finished("sync:profile-a")
    assert window._engine_busy

    window._on_operation_finished("recommendation:profile-a")
    assert not window._engine_busy
    window.close()


def test_returning_to_profile_reuses_the_rendered_taste_profile(system_temp_dir):
    create_application([])
    profiles, results, _profile, _result = create_dashboard_state(system_temp_dir)

    class CountingTasteProvider:
        def __init__(self):
            self.calls = 0

        def taste_profile(self):
            self.calls += 1
            return SampleTasteProfileProvider().taste_profile()

    provider = CountingTasteProvider()
    window = MainWindow(
        profile_service=profiles,
        result_service=results,
        taste_profile_provider=provider,
    )

    window.navigate_to(PageId.PROFILE)
    window.navigate_to(PageId.SETTINGS)
    window.navigate_to(PageId.PROFILE)

    assert provider.calls == 1
    window.close()


def test_successful_worker_result_is_merged_and_visible_after_window_reopens(system_temp_dir):
    create_application([])
    profiles, results, profile, _result = create_dashboard_state(system_temp_dir)
    first = MainWindow(profile_service=profiles, result_service=results)
    update = PipelineResult(user_stats={"completed_count": 99, "rated_count": 90})

    first.worker_controller.result_ready.emit(f"sync:{profile.profile_id}", update)
    assert first.home_page.metric_values["completed"].text() == "99"
    first.close()

    reopened = MainWindow(profile_service=profiles, result_service=results)
    assert reopened.home_page.metric_values["completed"].text() == "99"
    assert reopened.home_page.metric_values["recommendations"].text() == "6"
    reopened.close()


def test_public_client_id_marks_mal_connected_and_update_button_runs_real_sync_worker(
    system_temp_dir,
    top_anime_df,
    completed_anime_df,
):
    application = create_application([])
    settings = SettingsService(root_override=system_temp_dir)
    settings.save(AppSettings(client_id="fixture-client"))
    profiles = ProfileService(root_override=system_temp_dir)
    profile = profiles.create_profile("fixture-user")
    profiles.directory(profile.profile_id, create=True)
    profile = profiles.mark_synced(profile)
    profiles.set_active(profile.profile_id)
    results = ResultService(root_override=system_temp_dir)
    orchestrator = PipelineOrchestrator(
        anime_data=AnimeDataService(
            top_fetcher=lambda **_kwargs: top_anime_df,
            completed_fetcher=lambda *_args, **_kwargs: completed_anime_df,
        ),
        profiles=profiles,
        recommendations=RecommendationService(),
        storage=CsvStorage(),
        client_id_provider=lambda: settings.load().client_id or "",
    )
    window = MainWindow(
        profile_service=profiles,
        result_service=results,
        pipeline_orchestrator=orchestrator,
        settings_service=settings,
    )
    assert window.connection_status.mal_status_label.text() == "MAL: Connected"

    window.home_page.action_buttons[ACTION_SYNC].click()
    deadline = time.monotonic() + 3
    while window.worker_controller.active_keys and time.monotonic() < deadline:
        application.processEvents()
        time.sleep(0.002)
    application.processEvents()

    assert not window.worker_controller.active_keys
    saved = results.load(profile.profile_id)
    assert saved is not None
    assert saved.user_stats["completed_count"] == len(completed_anime_df)
    assert window.home_page.activity_label.text().startswith("MAL data updated")
    window.close()


def test_setting_aside_files_the_anime_without_reranking_what_is_left(
    system_temp_dir,
):
    """A filter must not pretend to be a rating.

    This test used to assert the opposite: liking "Fantasy signal" boosted the
    Fantasy genre, which lifted "Fantasy candidate" (75) above "Drama leader"
    (80), and the reordering was the point. That behaviour is gone with the
    like button. Setting a title aside says nothing about genre, so the two
    that remain must still be in plain score order - which is the guarantee
    worth pinning, because silently reranking on a filter is the exact
    mistake the old vote made.
    """
    application = create_application([])
    profiles = ProfileService(root_override=system_temp_dir)
    profile = profiles.create_profile("fixture-user")
    profiles.directory(profile.profile_id, create=True)
    profile = profiles.mark_synced(profile)
    profiles.set_active(profile.profile_id)
    results = ResultService(root_override=system_temp_dir)
    results.save(
        profile.profile_id,
        PipelineResult(
            recommendations=(
                Recommendation(
                    Anime("Fantasy signal", mal_id=1, genres=("Fantasy",)),
                    match_score=70,
                ),
                Recommendation(
                    Anime("Drama leader", mal_id=2, genres=("Drama",)),
                    match_score=80,
                ),
                Recommendation(
                    Anime("Fantasy candidate", mal_id=3, genres=("Fantasy",)),
                    match_score=75,
                ),
            )
        ),
    )
    state = RecommendationStateService(root_override=system_temp_dir)
    window = MainWindow(
        profile_service=profiles,
        result_service=results,
        recommendation_state_service=state,
    )

    window.recommendations_page._cards_by_key["mal:1"].not_interested_button.click()
    application.processEvents()

    titles = [
        model.display_title for model in window.recommendations_page.visible_models
    ]
    assert titles == ["Drama leader", "Fantasy candidate"]
    assert "mal:1" not in window.recommendations_page._cards_by_key
    assert (
        window.recommendations_page.not_interested_folder_action.text()
        == "Not interested (1)"
    )
    window.close()


def test_ten_pick_refill_reaches_more_worker_with_requested_count(
    system_temp_dir,
    monkeypatch,
):
    create_application([])
    profiles, results, _profile, _result = create_dashboard_state(system_temp_dir)
    window = MainWindow(
        profile_service=profiles,
        result_service=results,
        pipeline_orchestrator=object(),
    )
    captured = {}
    monkeypatch.setattr(
        window.worker_controller,
        "start",
        lambda key, worker: captured.update(key=key, worker=worker),
    )
    monkeypatch.setattr(window, "show_operation_progress", lambda _key: None)

    assert window._start_more_recommendations(10)
    assert captured["worker"].count == 10
    assert window._last_more_count == 10
    window.close()
