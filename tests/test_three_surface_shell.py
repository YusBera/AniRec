"""The restructured shell: three surfaces, hidden tooling, and demo mode."""

from __future__ import annotations

import pytest

from AniRec.gui.main_window import DISCOVER_STATES, LIBRARY_STATES, MainWindow, PageId
from PySide6.QtWidgets import QApplication

from AniRec.gui_main import create_application
from AniRec.services import SampleDataService


@pytest.fixture
def window():
    create_application([])
    shell = MainWindow()
    yield shell
    shell.close()


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------


def test_navigation_offers_only_three_destinations(window):
    assert set(window.navigation_buttons) == {
        PageId.DISCOVER,
        PageId.LIBRARY,
        PageId.SETTINGS,
    }


def test_discover_shows_the_feed_and_library_shows_what_was_saved(window):
    """The two surfaces divide one library rather than duplicating it."""
    discover_states = set(window.recommendations_page._visible_states)
    library_states = set(window.library_page._visible_states)

    assert discover_states == set(DISCOVER_STATES)
    assert library_states == set(LIBRARY_STATES)
    # Nothing appears on both, so neither surface repeats the other.
    assert not discover_states & library_states
    # Between them they still reach every collection.
    assert discover_states | library_states == set(
        window.recommendations_page.library_tabs
    )


def test_a_single_collection_needs_no_tab_bar(window):
    assert not window.recommendations_page.library_bar.isVisibleTo(
        window.recommendations_page
    )
    assert window.library_page.library_bar.isVisibleTo(window.library_page)


def test_pipeline_steps_are_hidden_until_developer_tools_are_enabled(window):
    advanced = window.advanced_operations_page

    assert not advanced.isVisibleTo(window.settings_page)

    window.settings_page.developer_tools_checkbox.setChecked(True)
    assert advanced.isVisibleTo(window.settings_page)

    window.settings_page.developer_tools_checkbox.setChecked(False)
    assert not advanced.isVisibleTo(window.settings_page)


def test_one_action_replaces_the_seven_step_pipeline_view(window):
    requested = []
    window.recommendations_requested.connect(lambda: requested.append(True))

    window.discover_page.refresh_button.click()

    assert requested == [True]


def test_progress_is_reported_where_the_user_is_looking(window):
    """Status must land on a visible surface.

    HomePage still holds the dashboard state, but it is composed into Discover
    rather than being a page of its own, so anything written only to its own
    activity line would never be seen.
    """
    window._report_activity("Your recommendation feed has been refreshed.")

    assert "refreshed" in window.discover_page.status_label.text()


def test_the_refresh_button_shows_that_work_is_under_way(window):
    window.discover_page.set_refreshing(True)
    assert not window.discover_page.refresh_button.isEnabled()
    busy_text = window.discover_page.refresh_button.text()

    window.discover_page.set_refreshing(False)
    assert window.discover_page.refresh_button.isEnabled()
    assert window.discover_page.refresh_button.text() != busy_text


# ---------------------------------------------------------------------------
# Adventurousness
# ---------------------------------------------------------------------------


def test_adventurousness_replaces_the_sampler_internals(window):
    settings_page = window.settings_page

    for widget in (
        settings_page.candidate_pool_input,
        settings_page.randomness_input,
        settings_page.seed_input,
        settings_page.top_limit_input,
    ):
        assert not widget.isVisibleTo(settings_page)

    settings_page.adventurousness_input.setValue(9)
    assert settings_page.randomness_input.value() == 9

    settings_page.adventurousness_input.setValue(2)
    assert settings_page.randomness_input.value() == 2


# ---------------------------------------------------------------------------
# Demo mode
# ---------------------------------------------------------------------------


def test_sample_library_loads_through_the_real_models():
    result = SampleDataService().load()

    assert result is not None
    assert result.recommendations
    assert result.genre_stats
    # The sample must obey the same explanation rule as generated output.
    for recommendation in result.recommendations:
        if not recommendation.genre_contributions:
            continue
        total = sum(value for _label, value in recommendation.genre_contributions)
        assert total == pytest.approx(recommendation.match_score, abs=0.05)


def test_demo_mode_fills_every_surface_and_says_that_it_is_a_sample(window):
    assert not window.demo_banner.isVisibleTo(window)

    window._enter_demo_mode()

    assert window.demo_mode
    assert window.demo_banner.isVisibleTo(window)
    assert window.current_page_id is PageId.DISCOVER
    assert window.recommendations_page.visible_models
    # Sample data is read only, so it is deliberately bound to no profile
    # and cannot write likes or hidden items to anyone's stored state.
    assert window.library_page.profile_id is None


def test_the_card_is_short_enough_for_the_review_loop_to_fit(window):
    """The whole review loop has to fit the default window.

    Measured against the card's own height rather than against screen
    positions, because realised geometry varies with the Qt platform and with
    whatever ran before. Roughly 390px of feed is visible at 1280x720 once the
    surrounding chrome is accounted for, and everything up to and including the
    feedback buttons has to sit inside that.
    """
    window._enter_demo_mode()
    card = next(iter(window.recommendations_page._cards_by_key.values()))

    hint = card.sizeHint()
    below_actions = sum(
        widget.sizeHint().height()
        for widget in (card.mal_score_label, card.meta_label, card.genres_label,
                       card.reason_label, card.details_button, card.mal_button)
    )
    through_actions = hint.height() - below_actions

    assert through_actions <= 390, (
        f"cover through feedback buttons needs {through_actions}px, "
        "which pushes the review actions below the fold"
    )


def test_the_sample_can_actually_be_reviewed(window):
    """Looking around must demonstrate the product, not a dead feed.

    Reviewing a pick is the whole loop, so disabling Like and Not for me when
    there is no profile left the one mode meant to sell AniRec unable to show
    anything working.
    """
    window._enter_demo_mode()
    feed = window.recommendations_page
    before = len(feed.visible_models)
    card = next(iter(feed._cards_by_key.values()))

    assert card.like_button.isEnabled()
    assert card.dislike_button.isEnabled()

    card.like_button.click()

    assert card.model.mal_id in feed.local_state.liked_mal_ids
    # A reviewed pick leaves the queue, exactly as it would with an account.
    assert len(feed.visible_models) == before - 1


def test_reviewing_the_sample_writes_nothing(window, tmp_path):
    """No profile means no directory, and none is created."""
    window._enter_demo_mode()
    feed = window.recommendations_page
    card = next(iter(feed._cards_by_key.values()))

    card.like_button.click()
    card_two = next(iter(feed._cards_by_key.values()))
    card_two.dislike_button.click()

    assert feed.profile_id is None
    assert feed.local_state.liked_mal_ids or feed.local_state.disliked_mal_ids
    # The isolated app-data root for this test stays empty of profile state.
    assert not list(tmp_path.rglob("recommendation_state.json"))


def test_the_sample_summary_does_not_claim_the_result_is_saved(window):
    window._enter_demo_mode()
    feed = window.recommendations_page
    next(iter(feed._cards_by_key.values())).like_button.click()

    summary = feed.feedback_summary_label.text().casefold()

    assert "1 liked" in summary
    assert "connect" in summary


def test_a_refresh_cannot_quietly_empty_the_sample(window):
    window._enter_demo_mode()
    shown = len(window.recommendations_page.visible_models)

    window.refresh_dashboard()

    assert len(window.recommendations_page.visible_models) == shown
    assert window.demo_mode
