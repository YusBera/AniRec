"""What the window does when a MyAnimeList walk comes back."""

from __future__ import annotations

from AniRec.gui.main_window import MainWindow
from AniRec.gui.workers import OperationKind, operation_key
from AniRec.gui_main import create_application
from AniRec.models import Anime, AppSettings, PipelineResult, Recommendation
from AniRec.services import (
    MalSyncService,
    ProfileService,
    RecommendationStateService,
    ResultService,
    SettingsService,
)
from AniRec.services.mal_sync_service import MalSyncState, SyncedCompletion


def build_window(system_temp_dir, *, client_id="fixture-client-id"):
    """A window with a real profile, results and settings on a scratch root.

    ``client_id=None`` leaves settings unwritten, which is what a profile that
    has never been configured looks like - the service refuses to save an
    empty one, so the absence has to be genuine.
    """
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
                Recommendation(Anime("Alpha", mal_id=1), match_score=80),
                Recommendation(Anime("Beta", mal_id=2), match_score=70),
            )
        ),
    )
    settings = SettingsService(root_override=system_temp_dir)
    if client_id:
        settings.save(AppSettings(client_id=client_id))

    state_service = RecommendationStateService(root_override=system_temp_dir)
    sync_service = MalSyncService(root_override=system_temp_dir)
    window = MainWindow(
        profile_service=profiles,
        result_service=results,
        recommendation_state_service=state_service,
        mal_sync_service=sync_service,
        settings_service=settings,
    )
    return window, profile, state_service, sync_service


def completion(mal_id, title, score, *, credited=True):
    return SyncedCompletion(
        mal_id=mal_id,
        title=title,
        score=score,
        completed_at="2026-09-01T10:00:00+00:00",
        from_watch_later=credited,
    )


def test_a_watched_title_leaves_watch_later_without_being_asked(system_temp_dir):
    """Watch Later means "I still intend to watch this".

    A title that has been finished no longer qualifies, so clearing it is
    agreeing with the reader's own list rather than deciding anything for
    them. A prompt here would have exactly one sensible answer.
    """
    create_application([])
    window, profile, state_service, _sync = build_window(system_temp_dir)
    state_service.set_watch_later(profile.profile_id, 1, True)
    state_service.set_watch_later(profile.profile_id, 2, True)

    window._apply_sync_result(
        profile.profile_id,
        (MalSyncState(completions=(completion(1, "Alpha", 9),)), frozenset({1})),
    )

    remaining = state_service.load(profile.profile_id).watch_later_mal_ids
    assert remaining == frozenset({2})
    window.close()


def test_the_strip_reports_what_the_walk_found(system_temp_dir):
    create_application([])
    window, profile, _state, _sync = build_window(system_temp_dir)

    window._apply_sync_result(
        profile.profile_id,
        (MalSyncState(completions=(completion(1, "Alpha", 0),)), frozenset()),
    )

    assert not window.sync_notice.isHidden()
    assert "no score" in window.sync_notice.message_label.text()
    window.close()


def test_dismissing_the_notice_stops_it_returning_on_the_next_launch(
    system_temp_dir,
):
    """Acknowledgement is persisted, not just hidden on the widget."""
    create_application([])
    window, profile, _state, sync_service = build_window(system_temp_dir)
    sync_service.save(
        profile.profile_id,
        MalSyncState(completions=(completion(1, "Alpha", 0),)),
    )
    window.sync_notice.set_state(sync_service.load(profile.profile_id))
    assert not window.sync_notice.isHidden()

    window.sync_notice.dismiss_button.click()

    assert window.sync_notice.isHidden()
    assert sync_service.load(profile.profile_id).unacknowledged == ()
    window.close()


def test_a_walk_for_another_profile_is_ignored(system_temp_dir):
    """A result that arrives after a profile switch is not this profile's."""
    create_application([])
    window, profile, state_service, _sync = build_window(system_temp_dir)
    state_service.set_watch_later(profile.profile_id, 1, True)

    window._on_operation_result(
        operation_key(OperationKind.LIST_SYNC, "some-other-profile"),
        (MalSyncState(completions=(completion(1, "Alpha", 9),)), frozenset({1})),
    )

    assert state_service.load(profile.profile_id).watch_later_mal_ids == frozenset({1})
    window.close()


def test_a_sync_result_never_reaches_the_recommendation_result_path(
    system_temp_dir,
):
    """The tuple a walk returns is not a PipelineResult and must not be saved.

    The dispatch returns early on the list-sync key. Without that, the tuple
    would fall through to the guard below it and be silently dropped - which
    would look identical to a sync that found nothing.
    """
    create_application([])
    window, profile, state_service, _sync = build_window(system_temp_dir)
    state_service.set_watch_later(profile.profile_id, 1, True)

    window._on_operation_result(
        operation_key(OperationKind.LIST_SYNC, profile.profile_id),
        (MalSyncState(completions=(completion(1, "Alpha", 9),)), frozenset({1})),
    )

    assert state_service.load(profile.profile_id).watch_later_mal_ids == frozenset()
    assert not window.sync_notice.isHidden()
    window.close()


def test_no_credentials_means_no_walk_rather_than_an_error(system_temp_dir):
    """A sync nobody asked for reports what it finds, not why it did not run."""
    create_application([])
    window, _profile, _state, _sync = build_window(system_temp_dir, client_id=None)

    assert window._start_list_sync() is False
    window.close()


def test_demo_mode_never_reaches_myanimelist(system_temp_dir):
    create_application([])
    window, _profile, _state, _sync = build_window(system_temp_dir)
    window.demo_mode = True

    assert window._start_list_sync() is False
    window.close()
