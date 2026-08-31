"""Capture the documentation screenshots deterministically.

Uses the bundled sample library rather than anyone's real account, so the
images contain no personal data and are reproducible on any machine.

CHANGE [NO-CREDENTIALS]: "uses the sample library" was true of the *feed* and
false of everything else. ``MainWindow`` builds its own services when it is
not given any, and those read the real application data root - so the
Settings page rendered the operator's live MyAnimeList Client ID straight
into ``anirec-settings.png``, which is committed and published. That is
exactly how a credential got into this repository's history.

Two defences, because one is not enough for a credential:

* every service is built against a throwaway data root, so there is nothing
  real for the window to read in the first place; and
* the API fields are blanked immediately before the grab, so a service added
  later that quietly reaches past the override still cannot print a secret.

A third catches what the other two miss: each image is scanned after it is
written, and the run fails rather than leaving a suspect file on disk.

Run on a desktop session. The offscreen Qt platform has no font database, so
it renders text as empty boxes:

    .\\.venv\\Scripts\\python.exe .\\scripts\\capture_docs_screenshots.py
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
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
from AniRec.services import (  # noqa: E402
    DataManagementService,
    RecommendationStateService,
    ResultService,
    SettingsService,
    TokenStore,
)


WINDOW_SIZE = (1280, 720)
WIZARD_SIZE = (760, 620)

# Shown in place of any API field, so nobody reading the docs goes looking
# for the real value.
REDACTED = "(redacted for screenshots)"

# What a leaked credential looks like as text: MyAnimeList issues 32-character
# client IDs and 64-character secrets, both lowercase hex. Deliberately
# broader than that.
CREDENTIAL_SHAPE = re.compile(rb"[0-9a-f]{24,}")


def _settle(application, widget) -> None:
    widget.show()
    for _pass in range(4):
        application.processEvents()


def _isolated_window(theme_manager, root):
    """A window whose every service points at an empty, throwaway data root.

    MainWindow constructs real services for anything it is not handed, and
    those default to the live application data directory. Passing all of them
    explicitly is what keeps a documentation build from reading - and then
    publishing - whatever account the operator happens to have configured.
    """
    return MainWindow(
        theme_manager=theme_manager,
        settings_service=SettingsService(root_override=root),
        result_service=ResultService(root_override=root),
        recommendation_state_service=RecommendationStateService(root_override=root),
        data_management_service=DataManagementService(root_override=root),
        token_store=TokenStore(root_override=root),
    )


def _blank_api_fields(window, application) -> None:
    """Clear the API inputs regardless of where their contents came from."""
    page = getattr(window, "settings_page", None)
    for name in ("client_id_input", "client_secret_input"):
        field = getattr(page, name, None)
        if field is not None:
            field.clear()
            field.setPlaceholderText(REDACTED)
    for _pass in range(2):
        application.processEvents()


def _assert_no_credentials(path: Path) -> None:
    """Refuse to leave an image on disk carrying a credential-shaped string.

    Text drawn into a PNG is pixels, not bytes, so this cannot read what the
    image *shows*. What it does catch is a credential reaching the file by a
    textual route - a tEXt/iTXt chunk, an embedded path, a stray metadata
    write - which is the failure a future edit is most likely to reintroduce.
    """
    match = CREDENTIAL_SHAPE.search(path.read_bytes())
    if match is not None:
        path.unlink(missing_ok=True)
        raise SystemExit(
            f"{path.name} contained a credential-shaped string "
            f"({match.group()[:8].decode('ascii', 'replace')}...); "
            "the file was deleted rather than published."
        )


def capture(output_dir: Path, theme: str) -> list[Path]:
    application = create_application([])
    theme_manager = ThemeManager(application)
    written: list[Path] = []

    # An empty root that goes away with the block. Nothing this window reads
    # belongs to whoever is running the script.
    with tempfile.TemporaryDirectory(prefix="anirec-docs-") as scratch:
        window = _isolated_window(theme_manager, Path(scratch))
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
            if page_id is PageId.SETTINGS:
                _blank_api_fields(window, application)
            path = output_dir / name
            window.grab().save(str(path))
            _assert_no_credentials(path)
            written.append(path)
        window.close()

    page = ApiSettingsPage(AppSettings())
    page.resize(*WIZARD_SIZE)
    _settle(application, page)
    path = output_dir / "anirec-first-run-wizard.png"
    page.grab().save(str(path))
    _assert_no_credentials(path)
    written.append(path)
    page.close()
    return written


def _display(path: Path) -> str:
    """Repository-relative where possible, absolute when the target is elsewhere."""
    try:
        return str(path.relative_to(REPOSITORY_ROOT))
    except ValueError:
        return str(path)


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
        print(f"wrote {_display(path)} ({size} bytes)")
        if size <= 0:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
