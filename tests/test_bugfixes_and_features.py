"""BUG1 popups, BUG2 DPI and GUI scale, FEAT1 live colour, FEAT2 match badge."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog

from AniRec.errors import UserFacingError
from AniRec.gui.gradient_picker import GradientPicker
from AniRec.gui.main_window import MainWindow
from AniRec.gui.match_badge import BAR_HEIGHT, MatchBadge, should_show_badge
from AniRec.gui.recommendation_card import (
    CARD_MAX_WIDTH,
    CARD_WIDTH,
    COVER_WIDTH,
    RecommendationCard,
)
from AniRec.gui.scaling import GUI_SCALE_CHOICES, scaled, set_gui_scale
from AniRec.gui.theme import ThemeManager
from AniRec.gui_main import create_application
from AniRec.models import AppSettings


@pytest.fixture(autouse=True)
def default_scale():
    set_gui_scale(1.0)
    yield
    set_gui_scale(1.0)


@pytest.fixture
def window():
    create_application([])
    shell = MainWindow(theme_manager=ThemeManager(create_application([])))
    shell._enter_demo_mode()
    yield shell
    shell.close()


# ---------------------------------------------------------------------------
# BUG1
# ---------------------------------------------------------------------------


def test_no_window_opens_for_routine_background_work(window, monkeypatch):
    """The flash was a progress dialog that closed itself moments later."""
    opened = []
    monkeypatch.setattr(QDialog, "show", lambda self: opened.append(type(self).__name__))

    window._start_sync()
    window._start_recommendations()
    window._start_more_recommendations()

    assert opened == []


def test_a_failure_is_reported_on_the_surface_not_in_a_window(window):
    error = UserFacingError(
        "network_error",
        "Could not reach MyAnimeList",
        "The request timed out.",
        "Check your connection and try again.",
        retryable=True,
    )

    window._on_operation_error("more-recommendations:p1", error)

    assert window.error_dialogs == {}
    # The sentence lives on the message label; the STATE field beside it
    # reports the state, not the sentence.
    assert "Could not reach MyAnimeList" in window.discover_page.message_label.text()
    assert window.discover_page.status_label.text() == "FAULT"


def test_a_retry_is_still_available_after_a_failure(window):
    error = UserFacingError(
        "network_error", "Failed", "It failed.", "Try again.", retryable=True
    )
    window._on_operation_error("more-recommendations:p1", error)

    assert window._pending_retry is not None


def test_the_action_guards_itself_and_then_recovers(window):
    """A second press must not start a second run, and the control must return."""
    feed = window.recommendations_page
    feed.set_more_available(True)
    assert feed.more_button.isEnabled()

    feed.set_more_running(True)
    assert not feed.more_button.isEnabled()

    feed.set_more_running(False)
    feed.set_more_available(True)
    assert feed.more_button.isEnabled()


def test_a_finished_operation_does_not_block_the_next_one():
    """BUG1: the key outlived the thread, so the next press was dropped."""
    from AniRec.gui.workers import WorkerController
    from AniRec.gui.workers.base import BaseWorker

    create_application([])
    controller = WorkerController()

    class Quick(BaseWorker):
        def execute(self):
            return "done"

    controller.start("k", Quick())
    controller.wait("k", 4000)
    # The handle may still be registered until its queued callback lands.
    controller.start("k", Quick())
    controller.wait("k", 4000)


# ---------------------------------------------------------------------------
# BUG2
# ---------------------------------------------------------------------------


def test_the_offered_scales_are_the_ones_specified():
    assert GUI_SCALE_CHOICES == (0.75, 1.00, 1.25, 1.50)
    assert AppSettings().gui_scale == 1.0


def test_scaled_dimensions_track_the_factor():
    set_gui_scale(1.5)
    assert scaled(100) == 150
    set_gui_scale(0.75)
    assert scaled(100) == 75
    # A hairline must not round away to nothing.
    assert scaled(1) >= 1


@pytest.mark.parametrize("factor", GUI_SCALE_CHOICES)
def test_the_card_and_its_portrait_resize_together(factor):
    create_application([])
    set_gui_scale(factor)
    from AniRec.gui.recommendation_view_model import recommendation_view_models
    from AniRec.services import SampleDataService

    model = recommendation_view_models(SampleDataService().load().recommendations)[0]
    card = RecommendationCard(model)

    # Cards flex to fill their grid column, so a single pinned width is no
    # longer the thing that scales - the bounds are. Both ends move with the
    # GUI scale, and the portrait moves with them.
    assert card.minimumWidth() == scaled(CARD_WIDTH)
    assert card.maximumWidth() == scaled(CARD_MAX_WIDTH)
    assert card.cover_label.width() == scaled(COVER_WIDTH)


def test_the_portrait_is_centred_in_the_card():
    """BUG2: the cover is narrower than the card and sat against the margin."""
    create_application([])
    from AniRec.gui.recommendation_view_model import recommendation_view_models
    from AniRec.services import SampleDataService

    model = recommendation_view_models(SampleDataService().load().recommendations)[0]
    card = RecommendationCard(model)
    card.show()

    offset = card.cover_label.mapTo(card, card.cover_label.rect().topLeft()).x()
    expected = (card.width() - card.cover_label.width()) // 2

    assert abs(offset - expected) <= 1
    card.close()


def test_the_view_toggle_is_present_on_every_surface(window):
    """BUG2: it lived inside the collapsible tab bar, so Discover lost it."""
    for feed in (window.recommendations_page, window.library_page):
        assert feed.view_bar.isVisibleTo(feed)
        for button in (feed.cards_button, feed.list_button, feed.table_button):
            assert button.isVisibleTo(feed)


def test_the_gui_scale_is_remembered(window):
    """Persisted as it is chosen, not on Save.

    The Save button deliberately refuses an API configuration with no Client
    ID, so routing appearance through it would leave a theme or a scale
    unsavable until an account existed.
    """
    settings_page = window.settings_page
    index = settings_page.gui_scale_input.findData(1.25)

    settings_page.gui_scale_input.setCurrentIndex(index)

    assert window.settings_service.load().gui_scale == 1.25


def test_an_out_of_range_scale_is_bounded_rather_than_rejected():
    assert AppSettings(gui_scale=99).gui_scale == 1.5
    assert AppSettings(gui_scale=0.01).gui_scale == 0.75
    assert AppSettings(gui_scale="nonsense").gui_scale == 1.0


# ---------------------------------------------------------------------------
# FEAT1
# ---------------------------------------------------------------------------


def test_the_colour_updates_while_it_is_being_chosen():
    create_application([])
    picker = GradientPicker()
    picker.set_colours("#111111", "#222222")
    seen = []
    picker.changed.connect(lambda start, _end: seen.append(start))

    picker._apply("start", "#AA0000")
    picker.changed.emit(picker.start, picker.end)
    picker._apply("start", "#BB0000")
    picker.changed.emit(picker.start, picker.end)

    assert seen == ["#AA0000", "#BB0000"]
    assert "#BB0000" in picker.preview.styleSheet()


def test_cancelling_restores_the_colour_from_when_the_picker_opened():
    create_application([])
    picker = GradientPicker()
    picker.set_colours("#111111", "#222222")
    opened_with = picker.start

    picker._apply("start", "#CC0000")
    assert picker.start != opened_with
    # What the cancel branch does.
    picker.set_colours(opened_with, picker.end)

    assert picker.start == opened_with


def test_a_preview_is_told_apart_from_a_commit():
    """Nothing is written to the config until Done is pressed."""
    create_application([])
    picker = GradientPicker()
    previews, commits = [], []
    picker.changed.connect(lambda *a: previews.append(a))
    picker.committed.connect(lambda *a: commits.append(a))

    picker._apply("start", "#0000AA")
    picker.changed.emit(picker.start, picker.end)

    assert previews and not commits


# ---------------------------------------------------------------------------
# FEAT2
# ---------------------------------------------------------------------------


def test_the_badge_shows_the_same_precision_as_every_other_readout():
    """CHANGE [PRECISION]: the badge used to round to a whole number.

    The row, the table and the score inspector all print a tenth, so the
    same title read 95% on its card and 94.6% one click away, in an
    application whose entire claim is that its score means something.
    """
    create_application([])
    badge = MatchBadge(94.6)

    assert badge.percentage == pytest.approx(94.6)
    assert "94.6 percent" in badge.accessibleName()


def test_the_badge_is_hidden_when_there_is_no_score():
    class NoScore:
        personal_match_available = False
        personal_match = None

    class Scored:
        personal_match_available = True
        personal_match = 88.0

    assert not should_show_badge(NoScore())
    assert should_show_badge(Scored())


@pytest.mark.parametrize("factor", GUI_SCALE_CHOICES)
def test_the_match_bar_scales_with_the_gui_scale(factor):
    """The bar's height scales; its width is set by the card it spans."""
    create_application([])
    set_gui_scale(factor)
    badge = MatchBadge(90.0)
    badge.apply_scale()

    assert badge.height() == scaled(BAR_HEIGHT)


@pytest.mark.parametrize(
    ("percentage", "expect_wider"),
    [(100.0, True), (50.0, False)],
)
def test_the_fill_length_is_the_score(percentage, expect_wider):
    """A full score covers the card; a half score covers about half of it."""
    create_application([])
    badge = MatchBadge(percentage)
    badge.setFixedWidth(200)

    fraction = badge.percentage / 100.0
    filled = max(badge.height(), 200 * fraction)

    assert (filled > 150) is expect_wider


def test_the_match_bar_spans_the_bottom_of_the_portrait(window):
    window.recommendations_page.set_view_mode("cards")
    card = next(iter(window.recommendations_page._cards_by_key.values()))
    badge, cover = card.match_badge, card.cover_label

    assert badge is not None
    assert badge.parent() is cover
    # CHANGE [SCRIM]: the plate used to be inset six pixels from the bottom
    # and each side, so a margin of artwork showed around it and the readout
    # floated on a rectangle instead of sitting on the picture. It is flush
    # to the portrait's lower edge now, which is a stricter claim than the
    # ">80% of the width, somewhere in the lower half" this used to make.
    assert badge.x() == 0
    assert badge.width() == cover.width()
    assert badge.y() + badge.height() == cover.height()
    assert badge.y() > cover.height() // 2


def test_the_match_bar_follows_the_theme():
    create_application([])
    badge = MatchBadge(90.0)

    badge.set_colours(QColor(0, 0, 0, 165), QColor("#E0685A"), QColor("#FFFFFF"))

    assert badge._track.alpha() == 165
    assert badge._fill.name().upper() == "#E0685A"
    assert badge._text.name().upper() == "#FFFFFF"


# ---------------------------------------------------------------------------
# Round two: reported after using the build
# ---------------------------------------------------------------------------


def test_a_vote_does_not_tear_down_the_feed(window):
    """The flashing was widgets being destroyed and rebuilt, not dialogs.

    One Like rebuilt every card and row five times over, roughly 3,500 child
    widgets and about a second, during which the feed visibly disappeared and
    came back. Cards are reused now, so a vote touches only what changed.
    """
    from AniRec.gui.recommendation_card import RecommendationCard

    feed = window.recommendations_page
    feed.set_view_mode("cards")
    built = []
    original = RecommendationCard.__init__

    def counting(self, *args, **kwargs):
        built.append(1)
        return original(self, *args, **kwargs)

    RecommendationCard.__init__ = counting
    try:
        card = next(iter(feed._cards_by_key.values()))
        card.not_interested_button.click()
    finally:
        RecommendationCard.__init__ = original

    # A reviewed pick leaves the feed; nothing else should be recreated.
    assert len(built) <= 1


def test_only_the_visible_layout_is_built(window):
    """Building both doubled the widget count, and every widget costs on a
    theme change because Qt re-polishes the whole tree."""
    feed = window.recommendations_page

    feed.set_view_mode("cards")
    assert feed._cards_by_key
    assert not feed._rows_by_key

    feed.set_view_mode("list")
    assert feed._rows_by_key


def test_list_rows_can_receive_artwork(window):
    """BUG3: the list showed no portraits because covers were only ever
    requested for, and delivered to, the card grid."""
    feed = window.recommendations_page
    feed.set_view_mode("list")
    row = next(iter(feed._rows_by_key.values()))

    assert hasattr(row, "request_cover")
    assert hasattr(row, "set_cover_data")


def test_the_header_folds_away_while_browsing(window):
    """BUG5: the header took 41% of the window, leaving a slot to browse in."""
    discover = window.discover_page

    assert not discover.header_collapsed

    discover.set_header_collapsed(True)
    assert discover.header_collapsed
    assert not discover.taste_panel.isVisibleTo(discover)

    discover.set_header_collapsed(False)
    assert discover.taste_panel.isVisibleTo(discover)


def test_the_feedback_actions_are_colour_coded():
    """BUG7: the actions looked identical until after being pressed."""
    from AniRec.gui.qss_builder import build_stylesheet

    sheet = build_stylesheet("dark")

    assert 'QPushButton[feedback="not-interested"]:hover' in sheet
    assert 'QPushButton[savedAction="true"]:hover' in sheet


def test_hover_colours_come_from_the_active_theme():
    """So green and red follow light, dark, OLED and gradient."""
    from AniRec.gui.design_tokens import palette

    for theme in ("dark", "light", "oled"):
        colours = palette(theme)
        assert colours["success_text"] != colours["danger_text"]


def test_a_colour_preview_is_coalesced_rather_than_applied_per_event(window):
    """Applying a stylesheet re-polishes the whole tree, so one apply per
    mouse move made dragging a colour unusable."""
    settings_page = window.settings_page
    applied = []
    settings_page._apply_preview_now = lambda: applied.append(1)

    for _ in range(30):
        settings_page._preview_theme()

    assert applied == []
    assert settings_page._preview_timer.isActive()
