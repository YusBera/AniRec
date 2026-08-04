from __future__ import annotations

import pytest

from AniRec.gui.main_window import PAGE_DEFINITIONS
from AniRec.gui.texts import UI_TEXT
from AniRec.gui.theme import (
    MAXIMUM_FONT_SCALE,
    MINIMUM_FONT_SCALE,
    ThemeManager,
    ThemePreference,
)
from AniRec.gui_main import create_application


def test_resource_themes_apply_and_publish_active_state():
    application = create_application([])
    manager = ThemeManager(application)

    assert manager.apply(ThemePreference.DARK) is ThemePreference.DARK
    assert "AniRec dark theme" in application.styleSheet()
    assert application.property("activeTheme") == "dark"

    assert manager.apply("light") is ThemePreference.LIGHT
    assert "AniRec light theme" in application.styleSheet()
    assert application.property("themePreference") == "light"


def test_system_theme_resolves_to_a_concrete_theme():
    application = create_application([])
    manager = ThemeManager(application)

    resolved = manager.apply(ThemePreference.SYSTEM)

    assert resolved in {ThemePreference.LIGHT, ThemePreference.DARK}
    assert manager.requested_theme is ThemePreference.SYSTEM
    assert application.property("themePreference") == "system"


def test_missing_qss_uses_safe_accessible_fallback(system_temp_dir):
    application = create_application([])
    manager = ThemeManager(application, resource_root=system_temp_dir)

    manager.apply(ThemePreference.DARK)
    stylesheet = application.styleSheet()

    assert "AniRec fallback dark" in stylesheet
    assert "QPushButton:hover" in stylesheet
    assert "QPushButton:focus" in stylesheet
    assert "QPushButton:disabled" in stylesheet


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        (0.1, MINIMUM_FONT_SCALE),
        (1.1, 1.1),
        (5.0, MAXIMUM_FONT_SCALE),
    ],
)
def test_font_scale_is_bounded(requested, expected):
    application = create_application([])
    manager = ThemeManager(application)

    manager.apply(ThemePreference.LIGHT, font_scale=requested)

    assert manager.font_scale == expected
    assert application.property("fontScale") == expected
    assert application.font().pointSizeF() >= 8.0


def test_visible_page_copy_comes_from_central_english_catalog():
    assert [(page.label, page.description) for page in PAGE_DEFINITIONS] == [
        (page.label, page.description) for page in UI_TEXT.pages
    ]
    assert all(page.label.isascii() for page in UI_TEXT.pages)
