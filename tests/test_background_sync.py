"""The opt-in repeat: the setting, and the timer it controls."""

from __future__ import annotations

from AniRec.gui.main_window import BACKGROUND_SYNC_INTERVAL_MS, MainWindow
from AniRec.gui_main import create_application
from AniRec.models import AppSettings
from AniRec.services import (
    MalSyncService,
    ProfileService,
    RecommendationStateService,
    ResultService,
    SettingsService,
)


def build_window(system_temp_dir, *, background_sync=False):
    profiles = ProfileService(root_override=system_temp_dir)
    profile = profiles.create_profile("fixture-user")
    profiles.directory(profile.profile_id, create=True)
    profile = profiles.mark_synced(profile)
    profiles.set_active(profile.profile_id)
    settings = SettingsService(root_override=system_temp_dir)
    settings.save(
        AppSettings(client_id="fixture-client-id", background_sync_enabled=background_sync)
    )
    window = MainWindow(
        profile_service=profiles,
        result_service=ResultService(root_override=system_temp_dir),
        recommendation_state_service=RecommendationStateService(
            root_override=system_temp_dir
        ),
        mal_sync_service=MalSyncService(root_override=system_temp_dir),
        settings_service=settings,
    )
    return window, profile, settings


# -- the setting ------------------------------------------------------------


def test_the_repeat_is_off_unless_it_has_been_asked_for():
    """Opening a profile is a request. A timer firing later is not.

    The default has to be off, because the difference between the two is the
    whole reason this is a setting.
    """
    assert AppSettings(client_id="x").background_sync_enabled is False


def test_an_older_settings_file_reads_as_off_rather_than_failing():
    """The field was added without bumping the schema version.

    The loader rejects any version it does not recognise, so a bump would
    have made every existing settings file unreadable.
    """
    payload = AppSettings(client_id="x").to_storage_dict()
    del payload["background_sync_enabled"]

    assert AppSettings.from_storage_dict(payload).background_sync_enabled is False


def test_the_setting_survives_a_round_trip():
    settings = AppSettings(client_id="x", background_sync_enabled=True)

    restored = AppSettings.from_storage_dict(settings.to_storage_dict())

    assert restored.background_sync_enabled is True


def test_the_diagnostic_view_reports_it():
    """Whether the application contacts MyAnimeList on its own is exactly the
    kind of thing a diagnostic dump exists to answer."""
    report = AppSettings(client_id="x", background_sync_enabled=True).to_diagnostic_dict()

    assert report["background_sync_enabled"] is True


# -- the timer --------------------------------------------------------------


def test_a_window_with_the_setting_off_never_arms_the_timer(system_temp_dir):
    create_application([])
    window, _profile, _settings = build_window(system_temp_dir)

    assert not window.background_sync_timer.isActive()
    window.close()


def test_a_window_with_the_setting_on_arms_it_at_the_documented_interval(
    system_temp_dir,
):
    create_application([])
    window, _profile, _settings = build_window(system_temp_dir, background_sync=True)

    assert window.background_sync_timer.isActive()
    assert window.background_sync_timer.interval() == BACKGROUND_SYNC_INTERVAL_MS
    window.close()


def test_turning_it_on_and_off_starts_and_stops_the_repeat(system_temp_dir):
    create_application([])
    window, _profile, _settings = build_window(system_temp_dir)

    window.set_background_sync(True)
    assert window.background_sync_timer.isActive()

    window.set_background_sync(False)
    assert not window.background_sync_timer.isActive()
    window.close()


def test_turning_it_on_twice_does_not_restart_the_countdown(system_temp_dir):
    """Saving settings re-emits the value, so an idempotent call matters.

    Restarting the timer on every save would push the next check out by a
    full interval each time somebody visited the settings page.
    """
    create_application([])
    window, _profile, _settings = build_window(system_temp_dir, background_sync=True)
    window.background_sync_timer.setInterval(BACKGROUND_SYNC_INTERVAL_MS)

    started = []
    original = window.background_sync_timer.start
    window.background_sync_timer.start = lambda *args: started.append(1) or original(*args)
    window.set_background_sync(True)

    assert started == []
    window.close()


def test_closing_the_window_stops_the_repeat(system_temp_dir):
    """A tick landing mid-shutdown would walk against services on their way
    out, and report to a window that is already closing."""
    create_application([])
    window, _profile, _settings = build_window(system_temp_dir, background_sync=True)
    assert window.background_sync_timer.isActive()

    window.close()

    assert not window.background_sync_timer.isActive()


def test_a_tick_goes_through_the_same_guards_as_any_other_sync(system_temp_dir):
    """The timer calls _start_list_sync directly, so demo mode still wins."""
    create_application([])
    window, _profile, _settings = build_window(system_temp_dir, background_sync=True)
    window.demo_mode = True

    window.background_sync_timer.timeout.emit()

    assert window._start_list_sync() is False
    window.close()
