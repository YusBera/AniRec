"""Capture the current tabs with isolated sample data on the secondary screen."""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.capture_docs_screenshots import _isolated_window, _blank_api_fields
from AniRec.gui.main_window import PageId
from AniRec.gui.theme import ThemeManager
from AniRec.gui_main import create_application
from AniRec.models import AppSettings
from PySide6.QtCore import QPoint, QTimer

app = create_application([])
screen = next((s for s in app.screens() if s != app.primaryScreen()), None)
if screen is None:
    raise SystemExit("No secondary screen; no window opened.")
out = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix="anirec-tab-concepts-") as scratch:
    window = _isolated_window(ThemeManager(app), Path(scratch))
    window._apply_settings(AppSettings(theme="dark", font_scale=1.0))
    window.resize(1440, 1000)
    window.move(screen.availableGeometry().topLeft() + QPoint(20, 20))
    window._enter_demo_mode()
    window.show()
    pages = iter([(PageId.LIBRARY, "library"), (PageId.PROFILE, "profile"), (PageId.COMPARE, "compare"), (PageId.SETTINGS, "settings")])

    def next_page():
        item = next(pages, None)
        if item is None:
            window.close()
            app.quit()
            return
        page_id, name = item
        window.navigate_to(page_id)
        if page_id == PageId.PROFILE:
            window.profile_page.show_profile(window.sample_taste_profile_provider.taste_profile())
        if page_id == PageId.COMPARE:
            window._show_sample_comparison()
        if page_id == PageId.SETTINGS:
            _blank_api_fields(window, app)
        def grab():
            window.grab().save(str(out / f"pyside-{name}.png"))
            print(f"Captured {name} on {window.screen().name()}", flush=True)
            next_page()
        QTimer.singleShot(650, grab)
    QTimer.singleShot(1200, next_page)
    app.exec()
