"""Task-local live baseline: isolated sample data, secondary monitor only."""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.capture_docs_screenshots import _isolated_window
from AniRec.gui.main_window import PageId
from AniRec.gui.theme import ThemeManager
from AniRec.gui_main import create_application
from AniRec.models import AppSettings
from PySide6.QtCore import QPoint, QTimer
from PySide6.QtWidgets import QWidget

app = create_application([])
screens = app.screens()
screen = next((s for s in screens if s != app.primaryScreen()), None)
if screen is None:
    raise SystemExit("No secondary monitor; did not open a window on the primary.")
out = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix="anirec-preservation-") as scratch:
    window = _isolated_window(ThemeManager(app), Path(scratch))
    window._apply_settings(AppSettings(theme="dark", font_scale=1.0))
    window.resize(1280, 900)
    window.move(screen.availableGeometry().topLeft() + QPoint(30, 30))
    window._enter_demo_mode()
    window.navigate_to(PageId.DISCOVER)
    window.show()

    def capture():
        window.grab().save(str(out / "pyside-baseline.png"))
        cards = [w for w in window.findChildren(QWidget) if w.objectName() == "recommendationCard" and w.isVisible()]
        def rect(widget):
            p = widget.mapTo(window, QPoint(0, 0))
            return dict(x=p.x(), y=p.y(), width=widget.width(), height=widget.height())
        data = {"screen": window.screen().name(), "window": rect(window), "cards": []}
        for card in cards[:8]:
            data["cards"].append({"title": card.model.display_title, "card": rect(card),
                **{key: rect(getattr(card, key)) for key in ("cover_label", "title_label", "secondary_title_label", "watch_later_button", "not_interested_button", "tag_strip", "meta_label", "reason_label")}})
        (out / "pyside-geometry.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(json.dumps(data, indent=2), flush=True)
        window.close()
        app.quit()

    QTimer.singleShot(3500, capture)
    app.exec()
