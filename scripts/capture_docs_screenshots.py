"""Capture the documentation screenshots deterministically.

Uses the bundled sample library rather than anyone's real account, so the
images contain no personal data and are reproducible on any machine.

Run on a desktop session. The offscreen Qt platform has no font database, so
it renders text as empty boxes:

    .\\.venv\\Scripts\\python.exe .\\scripts\\capture_docs_screenshots.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

# Must be chosen before Qt loads.
os.environ.setdefault("QT_QPA_PLATFORM", "windows")

from AniRec.gui.main_window import MainWindow, PageId  # noqa: E402
from AniRec.gui.setup_wizard import ApiSettingsPage  # noqa: E402
from AniRec.gui.theme import ThemeManager  # noqa: E402
from AniRec.gui_main import create_application  # noqa: E402
from AniRec.models import AppSettings  # noqa: E402


WINDOW_SIZE = (1280, 720)
WIZARD_SIZE = (760, 620)


def _settle(application, widget) -> None:
    widget.show()
    for _pass in range(4):
        application.processEvents()


def capture(output_dir: Path, theme: str) -> list[Path]:
    application = create_application([])
    theme_manager = ThemeManager(application)
    written: list[Path] = []

    window = MainWindow(theme_manager=theme_manager)
    window._apply_settings(AppSettings(theme=theme, font_scale=1.0))
    window.resize(*WINDOW_SIZE)
    # The sample library keeps these images free of personal data.
    window._enter_demo_mode()
    _settle(application, window)

    for page_id, name in (
        (PageId.DISCOVER, "anirec-home.png"),
        (PageId.LIBRARY, "anirec-recommendations.png"),
        (PageId.SETTINGS, "anirec-settings.png"),
    ):
        window.navigate_to(page_id)
        for _pass in range(4):
            application.processEvents()
        path = output_dir / name
        window.grab().save(str(path))
        written.append(path)
    window.close()

    page = ApiSettingsPage(AppSettings())
    page.resize(*WIZARD_SIZE)
    _settle(application, page)
    path = output_dir / "anirec-first-run-wizard.png"
    page.grab().save(str(path))
    written.append(path)
    page.close()
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPOSITORY_ROOT / "docs" / "images",
        help="Directory to write the images into.",
    )
    parser.add_argument("--theme", default="dark", choices=("dark", "light"))
    arguments = parser.parse_args()
    arguments.output.mkdir(parents=True, exist_ok=True)

    for path in capture(arguments.output, arguments.theme):
        size = path.stat().st_size if path.is_file() else 0
        print(f"wrote {path.relative_to(REPOSITORY_ROOT)} ({size} bytes)")
        if size <= 0:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
