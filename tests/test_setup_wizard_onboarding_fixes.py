"""Regression tests for the first-run defects reported against 1.2.2."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLayout, QLineEdit

from AniRec.gui.external_links import (
    MAL_API_CONFIG_URL,
    is_safe_external_url,
)
from AniRec.gui.setup_wizard import ApiSettingsPage
from AniRec.gui_main import create_application
from AniRec.models import AppSettings


@pytest.fixture(scope="module")
def application():
    return create_application([])


@pytest.fixture
def api_page(application):
    page = ApiSettingsPage(AppSettings())
    yield page
    page.deleteLater()


def _widgets_in_layout(widget) -> set:
    """Every widget actually reachable from a page's layout tree."""
    found = set()

    def walk(layout: QLayout | None) -> None:
        if layout is None:
            return
        for index in range(layout.count()):
            item = layout.itemAt(index)
            child = item.widget()
            if child is not None:
                found.add(child)
                walk(child.layout())
            walk(item.layout())

    walk(widget.layout())
    return found


def test_client_secret_and_redirect_uri_are_actually_rendered(api_page):
    """Both fields existed but were never added to a layout.

    MyAnimeList issues a client secret and the token exchange only sends one
    when it is set, so an unreachable field made the connection step fail with
    no way to correct it from the interface.
    """
    rendered = _widgets_in_layout(api_page)

    assert api_page.client_secret_input in rendered
    assert api_page.redirect_uri_input in rendered
    assert api_page.client_id_input in rendered


def test_redirect_uri_is_shown_read_only_with_a_copy_action(api_page):
    assert api_page.redirect_uri_input.isReadOnly()
    assert api_page.redirect_uri_input.text() == "http://localhost:8080/callback"

    api_page.copy_redirect_button.click()
    from PySide6.QtWidgets import QApplication

    assert QApplication.instance().clipboard().text() == (
        "http://localhost:8080/callback"
    )


def test_client_secret_is_masked(api_page):
    assert api_page.client_secret_input.echoMode() is QLineEdit.EchoMode.Password


def test_setup_page_links_to_the_mal_api_page(api_page):
    assert MAL_API_CONFIG_URL in api_page.api_link.text()
    assert not api_page.api_link.openExternalLinks()


def test_setup_page_explains_the_terms_it_asks_for(api_page):
    guidance = " ".join(
        [api_page.intro_label.text(), api_page.steps_label.text()]
    ).casefold()

    assert "client id" in guidance
    assert "redirect" in guidance


@pytest.mark.parametrize(
    "url",
    [
        "https://myanimelist.net/apiconfig",
        "https://myanimelist.net/apiconfig/",
    ],
)
def test_allowed_urls_are_accepted(url):
    assert is_safe_external_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://myanimelist.net/apiconfig",
        "https://myanimelist.net.evil.test/apiconfig",
        "https://myanimelist.net/apiconfig?next=https://evil.test",
        "https://myanimelist.net/profile/someone",
        "javascript:alert(1)",
        "",
    ],
)
def test_unexpected_urls_are_refused(url):
    assert not is_safe_external_url(url)
