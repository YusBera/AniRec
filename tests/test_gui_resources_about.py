from __future__ import annotations

from AniRec.gui.about_page import AboutPage, PROJECT_GITHUB_URL, is_safe_project_url
from AniRec.gui.main_window import MainWindow, PAGE_DEFINITIONS, PageId
from AniRec.gui.resources import app_icon, placeholder_pixmap
from AniRec.gui.theme import ThemeManager, ThemePreference
from AniRec.gui_main import create_application


def test_original_icon_and_placeholder_resources_load():
    create_application([])

    assert not app_icon().isNull()
    assert not placeholder_pixmap().isNull()


def test_about_page_contains_required_attribution_and_notice():
    create_application([])
    page = AboutPage()
    text = page.complete_text()

    assert "AniRec" in text
    assert "Original project owner: YusBera" in text
    assert "Desktop GUI contribution" in text
    assert "GPL-3.0" in text
    assert "Python, PySide6, pandas, and requests" in text
    assert "unofficial application" in text
    assert "not affiliated with or endorsed by MyAnimeList" in text


def test_about_project_link_allows_only_the_verified_https_url():
    assert is_safe_project_url(PROJECT_GITHUB_URL)
    assert not is_safe_project_url("http://github.com/YusBera/AniRec")
    assert not is_safe_project_url("https://github.com/YusBera/Other")
    assert not is_safe_project_url("https://example.com/YusBera/AniRec")
    assert not is_safe_project_url("javascript:alert(1)")


def test_about_link_uses_injected_opener_for_the_verified_url_only():
    create_application([])
    opened: list[str] = []
    page = AboutPage(url_opener=lambda url: not opened.append(url))

    page.github_link.linkActivated.emit(PROJECT_GITHUB_URL)
    page.github_link.linkActivated.emit("https://example.com/unsafe")

    assert opened == [PROJECT_GITHUB_URL]


def test_offscreen_shell_smoke_navigates_themes_about_and_closes():
    application = create_application([])
    manager = ThemeManager(application)
    window = MainWindow()
    window.show()
    application.processEvents()

    assert not application.windowIcon().isNull()
    assert not window.windowIcon().isNull()
    for definition in PAGE_DEFINITIONS:
        window.navigate_to(definition.page_id)
        application.processEvents()
        assert window.current_page_id is definition.page_id

    for theme in ThemePreference:
        assert manager.apply(theme) in {ThemePreference.LIGHT, ThemePreference.DARK}

    # About is now a section within Settings, not a destination of its own.
    about_page = window.about_page
    assert isinstance(about_page, AboutPage)
    assert "GPL-3.0" in about_page.complete_text()
    assert "unofficial application" in about_page.complete_text()

    window.close()
    application.processEvents()
    assert not window.isVisible()
