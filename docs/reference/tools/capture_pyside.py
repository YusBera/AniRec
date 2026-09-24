"""Capture AniRec's LATEST (HEAD, post-e4710a1) PySide6 UI states, offscreen,
sample data only.

Isolation: APPDATA / LOCALAPPDATA are expected to already be set (by the
caller's environment) to a scratch folder before this script imports
anything from AniRec. QT_QPA_PLATFORM must be "offscreen". This script
never passes a MyAnimeList Client ID, secret or token anywhere, and never
touches a real profile directory - only the bundled sample library and the
sample compatibility / taste profile providers are used.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

assert os.environ.get("QT_QPA_PLATFORM") == "offscreen", "must run offscreen"
assert "pyside-latest-appdata" in os.environ.get("APPDATA", ""), "APPDATA not isolated"

REPO_ROOT = Path(r"C:\Users\yusuf\AppData\Local\Temp\claude\C--Users-yusuf-OneDrive-Desktop-projects-AniRec\37023a8e-ae93-47aa-8e64-3328fece458e\scratchpad\compare\anirec-pyside-latest")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

OUT = Path(r"C:\Users\yusuf\AppData\Local\Temp\claude\C--Users-yusuf-OneDrive-Desktop-projects-AniRec\37023a8e-ae93-47aa-8e64-3328fece458e\scratchpad\pyside-latest")
OUT.mkdir(parents=True, exist_ok=True)

from PySide6.QtCore import Qt, QEvent, QPoint
from PySide6.QtGui import QEnterEvent

from AniRec.gui.main_window import MainWindow, PageId
from AniRec.gui.setup_wizard import WelcomePage, ApiSettingsPage
from AniRec.gui.recommendation_page import RecommendationViewMode
from AniRec.gui.theme import ThemeManager
from AniRec.gui_main import create_application
from AniRec.models import AppSettings
from AniRec.infrastructure.paths import app_data_dir

print(f"resolved app data root: {app_data_dir()}")
assert "pyside-latest-appdata" in str(app_data_dir()), "app_data_dir is not isolated!"

written = []


def settle(app, widget, passes=6):
    widget.show()
    for _ in range(passes):
        app.processEvents()


def save(widget, name):
    path = OUT / name
    ok = widget.grab().save(str(path))
    size = path.stat().st_size if path.is_file() else 0
    print(f"{'OK ' if ok and size else 'FAIL'} {name} ({size} bytes)")
    written.append((name, ok and size > 0))


def main():
    app = create_application([])
    theme_manager = ThemeManager(app)
    theme_manager.apply("dark", font_scale=1.0)

    # ---- first-run: welcome page ----
    welcome = WelcomePage()
    welcome.resize(760, 620)
    settle(app, welcome)
    save(welcome, "01-first-run-welcome.png")
    welcome.close()

    # ---- first-run: API settings page ----
    api_page = ApiSettingsPage(AppSettings())
    api_page.resize(760, 620)
    settle(app, api_page)
    save(api_page, "02-first-run-api-settings.png")
    api_page.close()

    # ---- main window, sample/demo data ----
    window = MainWindow(theme_manager=theme_manager)
    window._apply_settings(AppSettings(theme="dark", font_scale=1.0))
    window.resize(1440, 900)
    window._enter_demo_mode()
    settle(app, window)

    window.navigate_to(PageId.DISCOVER)
    settle(app, window)
    save(window, "03-discover-cards-1440x900.png")

    explorer = window.recommendations_page

    # List view
    explorer.set_view_mode(RecommendationViewMode.LIST)
    settle(app, window)
    save(window, "04-discover-list-1440x900.png")

    # Table view
    explorer.set_view_mode(RecommendationViewMode.TABLE)
    settle(app, window)
    save(window, "05-discover-table-1440x900.png")

    # Back to cards for the rest
    explorer.set_view_mode(RecommendationViewMode.CARDS)
    settle(app, window)

    # Filters panel open
    explorer.filter_toggle_button.setChecked(True)
    settle(app, window)
    save(window, "06-discover-filters-open.png")
    explorer.filter_toggle_button.setChecked(False)
    settle(app, window)

    # Taste vector panel expanded (closest analogue to "why these?")
    window.discover_page.taste_panel.toggle_button.setChecked(True)
    settle(app, window)
    save(window, "07-discover-taste-vector-expanded.png")
    window.discover_page.taste_panel.toggle_button.setChecked(False)
    settle(app, window)

    # A filter that yields nothing -> empty/no-matches state
    from AniRec.gui.discover_filters import FilterKind
    explorer.filter_state.add_value(FilterKind.GENRE, "Zzz-No-Such-Genre-Zzz")
    settle(app, window)
    save(window, "08-discover-no-matches-empty-state.png")
    explorer.clear_all_filters()
    settle(app, window)

    # One card grabbed alone, plus a "selected" pseudo-state
    first_key = next(iter(explorer._cards_by_key))
    card = explorer._cards_by_key[first_key]
    save(card, "09-recommendation-card-alone.png")

    card.set_selected(True)
    settle(app, window)
    save(card, "10-recommendation-card-selected.png")
    card.set_selected(False)

    # Attempted hover pseudo-state (offscreen platform may not honour :hover)
    try:
        enter = QEnterEvent(
            card.rect().center().toPointF(),
            card.rect().center().toPointF(),
            card.mapToGlobal(card.rect().center()).toPointF(),
        )
        app.sendEvent(card, enter)
        settle(app, window)
        save(card, "11-recommendation-card-hover-attempt.png")
        app.sendEvent(card, QEvent(QEvent.Type.Leave))
    except Exception as exc:  # noqa: BLE001
        print(f"hover attempt failed: {exc}")

    # "Not interested" pressed state, so the checked verdict icon is visible
    card.not_interested_button.setChecked(True)
    card._refresh_verdict_icons()
    settle(app, window)
    save(card, "11b-recommendation-card-not-interested-checked.png")
    card.not_interested_button.setChecked(False)
    card._refresh_verdict_icons()

    # Score inspector / detail dialog, opened from that same card's model
    explorer._open_details(card.model)
    settle(app, window)
    save(explorer.detail_dialog, "12-score-inspector-detail-dialog.png")
    explorer.detail_dialog.close()

    # My Library (default view: first entry of the current LIBRARY_STATES tuple)
    window.navigate_to(PageId.LIBRARY)
    settle(app, window)
    save(window, "13-my-library-default.png")

    # My Library, Watch Later tab (empty in a fresh demo session -> empty state)
    window.library_page._select_state_filter("watch-later")
    settle(app, window)
    save(window, "14-my-library-watch-later-empty-state.png")

    # My Library, Not interested tab (also empty)
    window.library_page._select_state_filter("not-interested")
    settle(app, window)
    save(window, "15-my-library-not-interested-empty-state.png")

    # Profile page: default state (no profile/statistics backend => refusal)
    window.navigate_to(PageId.PROFILE)
    settle(app, window)
    save(window, "16-profile-backend-missing.png")

    # Profile page: sample data offered from that refusal state
    window._show_sample_taste_profile()
    settle(app, window)
    save(window, "17-profile-sample-data.png")

    # Compare page: idle state
    window.navigate_to(PageId.COMPARE)
    settle(app, window)
    save(window, "18-compare-idle.png")

    # Compare page: sample comparison
    window._show_sample_comparison()
    settle(app, window)
    save(window, "19-compare-sample-data.png")

    # Settings page: default state
    window.navigate_to(PageId.SETTINGS)
    settle(app, window)
    save(window, "20-settings-default.png")

    window.close()

    # ---- Discover at 1024x768 ----
    window2 = MainWindow(theme_manager=theme_manager)
    window2._apply_settings(AppSettings(theme="dark", font_scale=1.0))
    window2.resize(1024, 768)
    window2._enter_demo_mode()
    settle(app, window2)
    window2.navigate_to(PageId.DISCOVER)
    settle(app, window2)
    save(window2, "21-discover-cards-1024x768.png")
    window2.recommendations_page.set_view_mode(RecommendationViewMode.LIST)
    settle(app, window2)
    save(window2, "22-discover-list-1024x768.png")
    window2.close()

    failures = [name for name, ok in written if not ok]
    print(f"\n{len(written)} screenshots attempted, {len(failures)} failed")
    if failures:
        print("FAILED:", failures)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
