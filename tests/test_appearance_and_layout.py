"""Theme modes and the grid/list layout toggle."""

from __future__ import annotations

import pytest

from AniRec.gui.design_tokens import gradient_palette, palette
from AniRec.gui.gradient_picker import GradientPicker
from AniRec.gui.main_window import MainWindow
from AniRec.gui.qss_builder import build_stylesheet, selectors
from AniRec.gui.recommendation_page import RecommendationViewMode
from AniRec.gui.recommendation_row import COVER_ROW_HEIGHT, THUMBNAIL_SIZE
from AniRec.gui.theme import ThemeManager, ThemePreference
from AniRec.gui_main import create_application
from AniRec.models import AppSettings
from AniRec.services import SettingsService


@pytest.fixture
def window():
    create_application([])
    shell = MainWindow(theme_manager=ThemeManager(create_application([])))
    yield shell
    shell.close()


# ---------------------------------------------------------------------------
# Themes
# ---------------------------------------------------------------------------


def test_every_theme_styles_the_same_surfaces():
    """Adding modes must not reintroduce the drift generation exists to stop."""
    reference = selectors(build_stylesheet("dark"))
    for theme in ("light", "oled"):
        assert selectors(build_stylesheet(theme)) == reference
    gradient = build_stylesheet("gradient", gradient_start="#123456", gradient_end="#654321")
    assert selectors(gradient) == reference


def test_oled_uses_true_black_where_it_matters():
    """On an OLED panel a black pixel is switched off, so it must be exact."""
    oled = palette("oled")

    assert oled["bg"] == "#000000"
    assert oled["sidebar"] == "#000000"
    # Cards still have to lift off that black, or the layout disappears.
    assert oled["surface"] != "#000000"
    assert oled["border"] != "#000000"


def test_oled_keeps_the_dark_palette_roles():
    """Derived from dark rather than rewritten, so the two cannot drift."""
    dark, oled = palette("dark"), palette("oled")

    assert oled["accent"] == dark["accent"]
    assert oled["text"] == dark["text"]


@pytest.mark.parametrize(
    ("start", "end", "expect_light_text"),
    [
        ("#101018", "#201020", True),
        ("#FFF4E8", "#E8F0FF", False),
    ],
)
def test_gradient_text_follows_the_brightness_of_the_chosen_colours(
    start, end, expect_light_text
):
    """A user can pick anything, and the result still has to be readable."""
    colours = gradient_palette(start, end)
    text_is_light = colours["text"] == palette("dark")["text"]

    assert text_is_light is expect_light_text


def test_gradient_paints_the_whole_shell():
    sheet = build_stylesheet(
        "gradient", gradient_start="#1B3A6B", gradient_end="#6B1B4A"
    )

    assert "#1B3A6B" in sheet and "#6B1B4A" in sheet
    assert "QWidget#contentArea" in sheet


def test_every_theme_applies(window):
    manager = window.theme_manager
    for theme in ("light", "dark", "oled"):
        assert manager.apply(theme) is ThemePreference(theme)
    assert manager.apply("gradient", gradient_start="#112233", gradient_end="#445566")
    assert "#112233" in manager.application.styleSheet()


def test_gradient_colours_survive_a_save_and_load():
    settings = AppSettings(
        theme="gradient", gradient_start="#AABBCC", gradient_end="#112233"
    )
    restored = AppSettings.from_storage_dict(settings.to_storage_dict())

    assert restored.gradient_start == "#AABBCC"
    assert restored.gradient_end == "#112233"


def test_a_malformed_colour_falls_back_rather_than_failing_to_load():
    """A cosmetic value must never stop settings from loading."""
    assert AppSettings(gradient_start="not-a-colour").gradient_start.startswith("#")


def test_the_picker_preview_uses_the_same_colours_it_will_apply():
    create_application([])
    picker = GradientPicker()

    picker.set_colours("#1B3A6B", "#6B1B4A")

    assert picker.start == "#1B3A6B"
    assert picker.end == "#6B1B4A"
    style = picker.preview.styleSheet()
    assert "#1B3A6B" in style and "#6B1B4A" in style


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


def test_the_toggle_offers_grid_and_list(window):
    feed = window.recommendations_page

    assert feed.cards_button.isCheckable()
    assert feed.list_button.isCheckable()

    feed.list_button.click()
    assert feed.view_mode is RecommendationViewMode.LIST

    feed.cards_button.click()
    assert feed.view_mode is RecommendationViewMode.CARDS


def test_a_list_row_leads_with_a_small_thumbnail_and_then_text(window):
    window._enter_demo_mode()
    feed = window.recommendations_page
    feed.set_view_mode("list")
    row = next(iter(feed._rows_by_key.values()))

    # The thumbnail is a 2:3 poster, not a square. Cover art is 2:3, so a
    # square crop cut the top and bottom off every image in the list and made
    # the same title look different depending on which view it was in.
    assert row.cover_label.width() == THUMBNAIL_SIZE
    assert row.cover_label.height() == COVER_ROW_HEIGHT
    assert THUMBNAIL_SIZE * 3 == COVER_ROW_HEIGHT * 2
    assert row.title_label.text()
    assert row.reason_label.text()
    assert row.match_tag.text()


def test_a_long_description_is_truncated_so_rows_keep_one_height():
    from AniRec.gui.recommendation_row import _truncate

    assert _truncate("short text") == "short text"
    long_text = "word " * 200
    assert len(_truncate(long_text)) <= 150
    assert _truncate(long_text).endswith("…")


def test_the_grid_adds_columns_as_the_window_widens(window):
    window._enter_demo_mode()
    feed = window.recommendations_page
    feed.set_view_mode("cards")

    def columns_at(width: int) -> int:
        window.resize(width, 720)
        feed.card_scroll.viewport().resize(width - 320, 600)
        feed._reflow_cards()
        return max(
            (feed.card_layout.getItemPosition(i)[1] for i in range(feed.card_layout.count())),
            default=-1,
        ) + 1

    narrow = columns_at(900)
    wide = columns_at(1920)

    assert narrow >= 1
    assert wide > narrow


def test_switching_layout_is_animated_rather_than_a_jump_cut(window):
    window._enter_demo_mode()
    feed = window.recommendations_page

    feed.set_view_mode("list")

    assert feed._view_animation is not None
    assert feed._view_animation.duration() > 0


def test_the_layout_choice_is_remembered(window):
    """Read through the window's own service.

    The suite already isolates APPDATA per test, so constructing a second
    service here would read a different root than the one the window wrote to.
    """
    feed = window.recommendations_page

    feed.list_button.click()

    assert window.settings_service.load().recommendation_view_mode == "list"

    feed.cards_button.click()
    assert window.settings_service.load().recommendation_view_mode == "cards"


def test_a_preference_saves_without_requiring_an_account(tmp_path, monkeypatch):
    """Appearance is not an API configuration.

    Requiring a Client ID to store a theme meant nothing a user chose while
    looking around could be kept.
    """
    monkeypatch.setenv("APPDATA", str(tmp_path))
    service = SettingsService()
    settings = AppSettings(theme="oled", recommendation_view_mode="list")

    service.save_preferences(settings)

    restored = service.load()
    assert restored.theme == "oled"
    assert restored.recommendation_view_mode == "list"


def test_credentials_are_still_validated_on_a_full_save(tmp_path, monkeypatch):
    """The relaxed path must not weaken the real one."""
    from AniRec.errors import ConfigError

    monkeypatch.setenv("APPDATA", str(tmp_path))
    service = SettingsService()

    with pytest.raises(ConfigError):
        service.save(AppSettings(client_id=None))
