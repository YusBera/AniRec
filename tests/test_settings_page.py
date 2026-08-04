from __future__ import annotations

import time

from AniRec.gui.main_window import MainWindow
from AniRec.gui.settings_page import SettingsPage
from AniRec.gui.workers import WorkerController
from AniRec.gui_main import create_application
from AniRec.models import AppSettings, PipelineSettings, TokenRecord
from AniRec.services import (
    DataDeletionScope,
    DataManagementService,
    ProfileService,
    RecommendationStateService,
    SettingsService,
    TokenStore,
)


def wait_until(application, predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        application.processEvents()
        time.sleep(0.002)
    application.processEvents()
    assert predicate()


def saved_settings():
    return AppSettings(
        client_id="fixture-client-id",
        client_secret="fixture-secret",
        redirect_uri="http://localhost:8080/callback",
        pipeline=PipelineSettings(
            top_anime_limit=800,
            recommendation_count=20,
            candidate_pool_size=250,
            randomness_factor=7,
            minimum_mean_score=6.5,
            seed=42,
        ),
        default_recommendation_sort="year",
        include_hidden_recommendations=True,
        theme="dark",
        font_scale=1.15,
        show_covers=False,
    )


def create_profiles(root, *, open_path=lambda _path: True):
    profiles = ProfileService(root_override=root, open_path=open_path)
    first = profiles.create_profile("first-user", mal_user_id=1)
    profiles.directory(first.profile_id, create=True)
    first = profiles.mark_synced(first)
    second = profiles.create_profile("second-user", mal_user_id=2)
    profiles.directory(second.profile_id, create=True)
    second = profiles.mark_synced(second)
    profiles.set_active(first.profile_id)
    return profiles, first, second


class FakeApiConnection:
    def __init__(self):
        self.calls = []

    def test(self, settings):
        self.calls.append(settings)
        return True


class FakeAuthService:
    def __init__(self):
        self.calls = []

    def get_access_token(self, profile_id, settings):
        self.calls.append((profile_id, settings))
        return "secret-token"


def test_all_recommendation_api_and_appearance_fields_round_trip_after_restart(
    system_temp_dir,
):
    create_application([])
    service = SettingsService(root_override=system_temp_dir)
    service.save(saved_settings())
    page = SettingsPage(settings_service=service)

    assert page.top_limit_input.value() == 800
    assert page.recommendation_count_input.value() == 20
    assert page.candidate_pool_input.value() == 250
    assert page.randomness_input.value() == 7
    assert page.minimum_score_input.value() == 6.5
    assert page.seed_input.value() == 42
    assert page.default_sort_input.currentData() == "year"
    assert page.include_hidden_input.isChecked()
    assert page.client_id_input.text() == "fixture-client-id"
    assert page.client_secret_input.text() == ""
    assert page.client_secret_input.echoMode().name == "Password"
    assert page.theme_input.currentData() == "dark"
    assert page.font_scale_input.value() == 1.15
    assert not page.show_covers_input.isChecked()

    page.recommendation_count_input.setValue(25)
    page.default_sort_input.setCurrentIndex(page.default_sort_input.findData("alphabetical"))
    assert page.save()
    reopened = SettingsService(root_override=system_temp_dir).load()
    assert reopened.pipeline.recommendation_count == 25
    assert reopened.default_recommendation_sort == "alphabetical"
    assert reopened.client_secret == "fixture-secret"
    page.close()


def test_cross_field_validation_prevents_invalid_candidate_pool_save(system_temp_dir):
    create_application([])
    service = SettingsService(root_override=system_temp_dir)
    service.save(AppSettings(client_id="fixture-client-id"))
    page = SettingsPage(settings_service=service)
    page.top_limit_input.setValue(20)
    page.recommendation_count_input.setValue(10)
    page.candidate_pool_input.setValue(30)

    assert not page.save()
    assert "not saved" in page.status_label.text()
    assert service.load().pipeline == PipelineSettings()
    page.close()


def test_profile_switch_open_add_and_confirmed_local_delete_are_wired(system_temp_dir):
    create_application([])
    opened = []
    profiles, first, second = create_profiles(
        system_temp_dir, open_path=lambda path: not opened.append(path)
    )
    requested_setup = []
    changed = []
    page = SettingsPage(
        settings_service=SettingsService(root_override=system_temp_dir),
        profile_service=profiles,
        token_store=TokenStore(root_override=system_temp_dir),
        confirm_profile_delete=lambda _profile, _target: True,
    )
    page.open_setup_requested.connect(lambda: requested_setup.append(True))
    page.profile_changed.connect(changed.append)
    page.set_context(first)

    page.profile_combo.setCurrentIndex(page.profile_combo.findData(second.profile_id))
    assert page.switch_profile()
    assert profiles.active_profile().profile_id == second.profile_id
    assert page.open_profile_folder()
    assert opened == [profiles.directory(second.profile_id)]
    page.add_profile_button.click()
    assert requested_setup == [True]
    assert page.delete_profile()
    assert not profiles.directory(second.profile_id).exists()
    assert changed[0].profile_id == second.profile_id
    assert changed[-1] is None
    page.close()


def test_api_test_refresh_and_disconnect_run_without_exposing_token(system_temp_dir):
    application = create_application([])
    settings = SettingsService(root_override=system_temp_dir)
    settings.save(AppSettings(client_id="fixture-client-id"))
    profiles, first, _second = create_profiles(system_temp_dir)
    tokens = TokenStore(root_override=system_temp_dir)
    tokens.save(first.profile_id, TokenRecord("local-secret-token", expires_at=100))
    api = FakeApiConnection()
    auth = FakeAuthService()
    controller = WorkerController()
    page = SettingsPage(
        settings_service=settings,
        profile_service=profiles,
        token_store=tokens,
        auth_service=auth,
        api_connection=api,
        worker_controller=controller,
    )
    page.set_context(first)

    assert page.test_api_connection()
    wait_until(application, lambda: not controller.active_keys)
    assert page.api_status_label.text() == "Client ID connection succeeded."
    assert len(api.calls) == 1

    assert page.refresh_token()
    wait_until(application, lambda: not controller.active_keys)
    assert "valid" in page.api_status_label.text()
    assert auth.calls[0][0] == first.profile_id
    assert "secret-token" not in page.api_status_label.text()

    assert page.disconnect_token()
    assert tokens.load(first.profile_id) is None
    page.close()


def test_main_window_applies_saved_sort_hidden_cover_theme_and_scale_live(system_temp_dir):
    application = create_application([])
    profiles, first, _second = create_profiles(system_temp_dir)
    settings = SettingsService(root_override=system_temp_dir)
    settings.save(AppSettings(client_id="fixture-client-id"))
    state = RecommendationStateService(root_override=system_temp_dir)
    window = MainWindow(
        profile_service=profiles,
        settings_service=settings,
        recommendation_state_service=state,
        token_store=TokenStore(root_override=system_temp_dir),
    )
    page = window.settings_page
    page.default_sort_input.setCurrentIndex(page.default_sort_input.findData("alphabetical"))
    page.include_hidden_input.setChecked(True)
    page.theme_input.setCurrentIndex(page.theme_input.findData("light"))
    page.font_scale_input.setValue(1.20)
    page.show_covers_input.setChecked(False)
    assert page.save()
    application.processEvents()

    assert window.recommendations_page.sort_combo.currentData() == "alphabetical"
    assert window.recommendations_page.local_state.show_hidden
    assert not window.recommendations_page.show_covers
    assert application.property("themePreference") == "light"
    assert application.property("fontScale") == 1.20
    window.close()


def test_data_actions_confirm_exact_scope_reset_ui_and_preserve_outside_sentinel(
    system_temp_dir,
):
    create_application([])
    profiles, first, _second = create_profiles(system_temp_dir)
    settings = SettingsService(root_override=system_temp_dir)
    settings.save(AppSettings(client_id="fixture-client-id"))
    cache = system_temp_dir / "cache"
    covers = cache / "covers"
    covers.mkdir(parents=True)
    (cache / "general.bin").write_text("cache", encoding="utf-8")
    (covers / "cover.img").write_text("cover", encoding="utf-8")
    sentinel = system_temp_dir.parent / "settings-page-outside-sentinel.txt"
    sentinel.write_text("safe", encoding="utf-8")
    confirmed = []
    data = DataManagementService(
        root_override=system_temp_dir,
        path_opener=lambda _path: True,
    )
    page = SettingsPage(
        settings_service=settings,
        profile_service=profiles,
        token_store=TokenStore(root_override=system_temp_dir),
        data_management=data,
        confirm_data_delete=lambda plan: not confirmed.append(plan),
    )
    page.set_context(first)

    assert page.delete_data_scope(DataDeletionScope.CACHE)
    assert not (cache / "general.bin").exists()
    assert (covers / "cover.img").exists()
    assert confirmed[-1].target == cache
    assert page.delete_data_scope(DataDeletionScope.COVERS)
    assert not covers.exists()

    resets = []
    page.local_data_reset.connect(lambda: resets.append(True))
    assert page.delete_data_scope(DataDeletionScope.ALL_LOCAL_DATA)
    assert resets == [True]
    assert page.active_profile is None
    assert page.client_id_input.text() == ""
    assert sentinel.read_text(encoding="utf-8") == "safe"
    page.close()
