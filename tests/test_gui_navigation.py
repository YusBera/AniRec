from __future__ import annotations

from PySide6.QtGui import QKeySequence
from PySide6.QtCore import QAbstractAnimation, Qt
from PySide6.QtWidgets import QWidget

from AniRec.gui.main_window import MainWindow, PAGE_DEFINITIONS, PageId
from AniRec.gui.instrument_widgets import ChannelWipe, ScanSweep
from AniRec.gui import profile_widgets
from AniRec.gui_main import create_application
from AniRec.metadata import MINIMUM_WINDOW_HEIGHT, MINIMUM_WINDOW_WIDTH


def test_main_window_exposes_the_product_surfaces():
    """The shell exposes the focused product surfaces, in reading order.

    A first time user was previously shown six navigation entries, one of which
    rendered a seven step dependency chain as a flat list of buttons. Those
    views still exist: the first two are composed into Discover, and the steps
    sit behind the developer tools switch in Settings. Profile and Compare are
    deliberate destinations rather than a return to the old utility-page
    sprawl, and they are ordered by whose taste they are about - yours, then
    somebody else's.
    """
    create_application([])
    window = MainWindow()

    assert [definition.label for definition in PAGE_DEFINITIONS] == [
        "Discover",
        "My Library",
        "Profile",
        "Compare",
        "Settings",
    ]
    assert window.page_stack.count() == len(PAGE_DEFINITIONS)
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
        # CHANGE [NUMBERED-NAV]: the rail's 01-05 prefixes are real
        # shortcuts now, and the accessible name says so - a keyboard user
        # should not have to discover Alt+1 by trying it.
        index = PAGE_DEFINITIONS.index(definition) + 1
        assert button.accessibleName() == f"Open {definition.label} page, Alt+{index}"
        assert button.shortcut() == QKeySequence(f"Alt+{index}")
        assert button.focusPolicy() & Qt.FocusPolicy.TabFocus
        assert sum(candidate.isChecked() for candidate in window.navigation_buttons.values()) == 1

    window.close()


def test_connection_status_bar_handles_signed_out_and_connected_states():
    create_application([])
    window = MainWindow()

    # The strip no longer carries its own lamp: the navigation rail's system
    # readout reports PROFILE and MAL permanently, and repeating them here put
    # the same two facts on screen twice. The strip still tracks the state, so
    # that is what is asserted; the rail's own lamps are covered below.
    assert window.connection_status.profile_label.text() == "No active profile"
    assert window.connection_status.mal_status_label.text() == "MAL: Disconnected"
    assert window.connection_status.mal_status_label.property("connected") is False

    window.connection_status.set_status("  yusuf  ", mal_connected=True)

    assert window.connection_status.profile_label.text() == "Active profile: yusuf"
    assert window.connection_status.mal_status_label.text() == "MAL: Connected"
    assert window.connection_status.mal_status_label.property("connected") is True
    window.close()


def test_the_rail_reports_connection_state_with_a_lamp():
    """The state the strip used to duplicate is still reported, on the rail."""
    create_application([])
    window = MainWindow()

    assert window.system_readout._values["MAL"].text() == "OFFLINE"
    assert window.system_readout._lamps["MAL"].state == "warn"

    window._profile_name = "yusuf"
    window._mal_connected = True
    window._refresh_system_readout()

    assert window.system_readout._values["MAL"].text() == "ONLINE"
    assert window.system_readout._lamps["MAL"].state == "ok"
    assert window.system_readout._values["PROFILE"].text() == "yusuf"
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


def test_shared_transition_effects_honor_reduced_motion(monkeypatch):
    application = create_application([])
    monkeypatch.setattr(profile_widgets, "_ANIMATIONS_ALLOWED", False)
    host = QWidget()
    host.resize(900, 600)
    host.show()
    application.processEvents()

    sweep = ScanSweep(host)
    sweep.sweep()
    wipe = ChannelWipe(host)
    wipe.run()

    assert sweep._animation.state() == QAbstractAnimation.State.Stopped
    assert wipe.animation.state() == QAbstractAnimation.State.Stopped
    assert not sweep.isVisible()
    assert not wipe.isVisible()
    host.close()
