from __future__ import annotations

import time
from pathlib import Path

from AniRec.gui.advanced_operations_page import ADVANCED_OPERATIONS, AdvancedOperationsPage
from AniRec.gui.workers import WorkerController
from AniRec.gui_main import create_application
from AniRec.models import AppSettings, PipelineProgress, PipelineResult
from AniRec.services import ProfileService, SettingsService


def wait_until(application, predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        application.processEvents()
        time.sleep(0.002)
    application.processEvents()
    assert predicate()


class FakeOrchestrator:
    def __init__(self):
        self.calls = []

    def run_step(self, step_id, username, settings, *, progress_callback, cancellation_token):
        self.calls.append((step_id, username, settings, cancellation_token))
        progress_callback(PipelineProgress(step_id, f"Running {step_id}", 1, 1, True))
        return PipelineResult(completed_at="2026-08-03T12:00:00+00:00")


class FakeAuthService:
    def __init__(self):
        self.calls = []

    def get_access_token(self, profile_id, settings):
        self.calls.append((profile_id, settings))
        return "secret-token-never-returned-to-ui"


def state(system_temp_dir):
    profiles = ProfileService(root_override=system_temp_dir)
    profile = profiles.create_profile("fixture-user", mal_user_id=42)
    profiles.directory(profile.profile_id, create=True)
    profile = profiles.mark_synced(profile)
    profiles.set_active(profile.profile_id)
    settings = SettingsService(root_override=system_temp_dir)
    settings.save(AppSettings(client_id="fixture-client-id"))
    return profiles, profile, settings


def test_exactly_seven_operations_have_descriptions_status_and_named_prerequisites(
    system_temp_dir,
):
    create_application([])
    profiles, profile, settings = state(system_temp_dir)
    page = AdvancedOperationsPage(
        orchestrator=FakeOrchestrator(),
        profile_service=profiles,
        settings_service=settings,
        auth_service=FakeAuthService(),
    )
    page.set_profile(profile)

    assert [item.step_id for item in ADVANCED_OPERATIONS] == [
        "fetch_top",
        "fetch_completed",
        "oauth",
        "impute_scores",
        "genre_importance",
        "generate_candidates",
        "generate_recommendations",
    ]
    assert len(page.widgets) == 7
    assert page.widgets["fetch_top"].run_button.isEnabled()
    assert page.widgets["fetch_completed"].run_button.isEnabled()
    assert page.widgets["oauth"].run_button.isEnabled()
    assert not page.widgets["impute_scores"].run_button.isEnabled()
    assert "Fetch the user's anime list" in page.widgets["impute_scores"].prerequisite.text()
    assert "Fetch the user's anime list" in page.widgets[
        "generate_candidates"
    ].prerequisite.text()
    assert "Generate recommendation candidates" in page.widgets[
        "generate_recommendations"
    ].prerequisite.text()
    page.close()


def test_file_prerequisites_unlock_in_dependency_order(system_temp_dir):
    create_application([])
    profiles, profile, settings = state(system_temp_dir)
    directory = profiles.directory(profile.profile_id)
    page = AdvancedOperationsPage(
        orchestrator=FakeOrchestrator(),
        profile_service=profiles,
        settings_service=settings,
        auth_service=FakeAuthService(),
    )
    page.set_profile(profile)

    (directory / "completed_anime.csv").write_text("Title,Genres,User Score\n", encoding="utf-8")
    page.refresh_prerequisites()
    assert page.widgets["impute_scores"].run_button.isEnabled()
    assert page.widgets["genre_importance"].run_button.isEnabled()
    assert not page.widgets["generate_candidates"].run_button.isEnabled()

    (directory / "top_anime.csv").write_text("Title,Genres\n", encoding="utf-8")
    page.refresh_prerequisites()
    assert page.widgets["generate_candidates"].run_button.isEnabled()
    assert not page.widgets["generate_recommendations"].run_button.isEnabled()

    (directory / "recommendation_candidates.csv").write_text("Title,Genres\n", encoding="utf-8")
    (directory / "genre_importance.csv").write_text("Genre,Importance_Score\n", encoding="utf-8")
    page.refresh_prerequisites()
    assert page.widgets["generate_recommendations"].run_button.isEnabled()
    page.close()


def test_each_action_uses_the_expected_worker_and_reaches_terminal_status(system_temp_dir):
    application = create_application([])
    profiles, profile, settings = state(system_temp_dir)
    directory = profiles.directory(profile.profile_id)
    for name in (
        "completed_anime.csv",
        "top_anime.csv",
        "recommendation_candidates.csv",
        "genre_importance.csv",
    ):
        (directory / name).write_text("fixture\n", encoding="utf-8")
    orchestrator = FakeOrchestrator()
    auth = FakeAuthService()
    controller = WorkerController()
    page = AdvancedOperationsPage(
        worker_controller=controller,
        orchestrator=orchestrator,
        profile_service=profiles,
        settings_service=settings,
        auth_service=auth,
    )
    page.set_profile(profile)

    for definition in ADVANCED_OPERATIONS:
        assert page.run_step(definition.step_id)
        wait_until(application, lambda: not controller.active_keys)
        assert page.widgets[definition.step_id].status.text() == "Completed"
        assert "Never" not in page.widgets[definition.step_id].last_run.text()

    assert [call[0] for call in orchestrator.calls] == [
        "fetch_top",
        "fetch_completed",
        "impute_scores",
        "genre_importance",
        "generate_candidates",
        "generate_recommendations",
    ]
    assert len(auth.calls) == 1
    assert auth.calls[0][0] == profile.profile_id
    assert "secret-token-never-returned-to-ui" not in " ".join(
        widgets.status.text() for widgets in page.widgets.values()
    )
    page.close()


def test_output_open_rejects_paths_outside_profile_and_opens_verified_file(
    system_temp_dir,
):
    create_application([])
    opened = []
    profiles, profile, settings = state(system_temp_dir)
    directory = profiles.directory(profile.profile_id)
    output = directory / "top_anime.csv"
    output.write_text("fixture", encoding="utf-8")
    page = AdvancedOperationsPage(
        orchestrator=FakeOrchestrator(),
        profile_service=profiles,
        settings_service=settings,
        auth_service=FakeAuthService(),
        path_opener=lambda path: not opened.append(path),
    )
    page.set_profile(profile)
    assert page.open_output("fetch_top")
    assert opened == [output.resolve()]

    sentinel = system_temp_dir.parent / "outside-sentinel.csv"
    sentinel.write_text("do not touch", encoding="utf-8")
    page._result_outputs["fetch_top"] = sentinel
    assert not page.open_output("fetch_top")
    assert sentinel.read_text(encoding="utf-8") == "do not touch"
    page.close()
