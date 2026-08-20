from __future__ import annotations

from PySide6.QtCore import Qt

from AniRec.gui.main_window import MainWindow, PAGE_DEFINITIONS, PageId
from AniRec.gui_main import create_application
from AniRec.metadata import MINIMUM_WINDOW_HEIGHT, MINIMUM_WINDOW_WIDTH


def test_main_window_exposes_three_surfaces():
    """The dashboard, genre analysis and pipeline pages are no longer destinations.

    A first time user was previously shown six navigation entries, one of which
    rendered a seven step dependency chain as a flat list of buttons. Those
    views still exist: the first two are composed into Discover, and the steps
    sit behind the developer tools switch in Settings.
    """
    create_application([])
    window = MainWindow()

    assert [definition.label for definition in PAGE_DEFINITIONS] == [
        "Discover",
        "My Library",
        "Settings",
    ]
    assert window.page_stack.count() == 3
    assert window.current_page_id is PageId.DISCOVER
    assert window.navigation_buttons[PageId.DISCOVER].isChecked()
    window.close()


def test_sidebar_buttons_navigate_and_expose_accessible_state():
    application = create_application([])
    window = MainWindow()
    window.show()

    for definition in PAGE_DEFINITIONS:
        button = window.navigation_buttons[definition.page_id]
        button.click()
        application.processEvents()

        assert window.current_page_id is definition.page_id
        assert window.page_stack.currentWidget() is window.page_widgets[definition.page_id]
        assert button.isChecked()
        assert button.accessibleName() == f"Open {definition.label} page"
        assert button.focusPolicy() & Qt.FocusPolicy.TabFocus
        assert sum(candidate.isChecked() for candidate in window.navigation_buttons.values()) == 1

    window.close()


def test_connection_status_bar_handles_signed_out_and_connected_states():
    create_application([])
    window = MainWindow()

    assert window.connection_status.profile_label.text() == "No active profile"
    assert window.connection_status.mal_status_label.text() == "MAL: Disconnected"

    window.connection_status.set_status("  yusuf  ", mal_connected=True)

    assert window.connection_status.profile_label.text() == "Active profile: yusuf"
    assert window.connection_status.mal_status_label.text() == "MAL: Connected"
    assert window.connection_status.mal_status_label.property("connected") is True
    window.close()


def test_navigation_shell_remains_usable_at_minimum_window_size():
    application = create_application([])
    window = MainWindow()
    window.resize(MINIMUM_WINDOW_WIDTH, MINIMUM_WINDOW_HEIGHT)
    window.show()
    application.processEvents()

    assert window.centralWidget().width() > 0
    assert window.page_stack.width() > 0
    assert window.page_stack.height() > 0
    assert all(button.isVisible() for button in window.navigation_buttons.values())
    assert window.connection_status.isVisible()

    window.close()
