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


def test_a_missing_qss_file_still_yields_a_fully_themed_application(system_temp_dir):
    """Styling no longer depends on the packaged file being present.

    The stylesheet is generated from the design tokens so that font sizes can
    follow the user's scale setting. A missing or unreadable resource therefore
    costs nothing, where it previously dropped the application onto a stripped
    back fallback palette that shared almost no colours with the real theme.
    """
    application = create_application([])
    manager = ThemeManager(application, resource_root=system_temp_dir)

    manager.apply(ThemePreference.DARK)
    stylesheet = application.styleSheet()

    assert "AniRec dark theme" in stylesheet
    for state in ("QPushButton:hover", "QPushButton:focus", "QPushButton:disabled"):
        assert state in stylesheet
    # The full theme, not a reduced stand-in.
    assert "QFrame#sidebar" in stylesheet
    assert "QMenu::item:selected" in stylesheet


def test_both_themes_style_exactly_the_same_selectors():
    """Generation is what makes drift impossible.

    The two stylesheets were previously maintained by hand and had diverged:
    context menus and the operation progress dialog were styled only in dark,
    and rendered with unthemed platform defaults in light.
    """
    from AniRec.gui.qss_builder import build_stylesheet, selectors

    dark = selectors(build_stylesheet("dark"))
    light = selectors(build_stylesheet("light"))

    assert dark == light
    assert len(dark) > 100


def test_font_scale_moves_the_whole_type_hierarchy_together():
    """Headings must grow with body text, not stay pinned.

    Sizes were previously fixed pixel values in the stylesheet, which the font
    scale setting could not reach. Body text grew while headings did not, so
    the hierarchy flattened and eventually inverted at larger scales.
    """
    import re

    from AniRec.gui.qss_builder import build_stylesheet

    def sizes(scale: float) -> tuple[float, float]:
        sheet = build_stylesheet("dark", base_point_size=9.0, font_scale=scale)
        body = float(re.search(r"font-size: ([\d.]+)pt;", sheet).group(1))
        heading = float(
            re.search(r"HeroTitle \{ color: [^;]+; font-size: ([\d.]+)pt", sheet).group(1)
        )
        return body, heading

    small_body, small_heading = sizes(MINIMUM_FONT_SCALE)
    large_body, large_heading = sizes(MAXIMUM_FONT_SCALE)

    assert large_body > small_body
    assert large_heading > small_heading
    assert small_heading / small_body == pytest.approx(
        large_heading / large_body, rel=0.02
    )


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
