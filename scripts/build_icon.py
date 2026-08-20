"""Regenerate the packaged Windows icon from the tracked SVG.

Run after changing ``AniRec/gui/resources/icons/anirec.svg`` so the .ico stays
a faithful rendering of it:

    .\\.venv\\Scripts\\python.exe .\\scripts\\build_icon.py

Must run on a desktop session. Qt's offscreen platform has no font or raster
backend here and rasterising vectors under it crashes the process.

Deliberately avoids QSvgRenderer and QBuffer, both of which fault in this
environment. QIcon renders each size natively, and each frame round trips
through a temporary PNG file.
"""

from __future__ import annotations

import argparse
import os
import struct
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "windows")

from AniRec.gui_main import create_application  # noqa: E402

# The sizes Windows picks between for the taskbar, alt-tab, and file listings.
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
SOURCE = REPOSITORY_ROOT / "AniRec" / "gui" / "resources" / "icons" / "anirec.svg"
TARGET = REPOSITORY_ROOT / "AniRec" / "gui" / "resources" / "icons" / "anirec.ico"


def render(source: Path) -> list[tuple[int, bytes]]:
    from PySide6.QtCore import QSize, Qt
    from PySide6.QtGui import QIcon

    icon = QIcon(str(source))
    frames: list[tuple[int, bytes]] = []
    with tempfile.TemporaryDirectory(prefix="anirec-icon-") as work:
        for size in ICON_SIZES:
            pixmap = icon.pixmap(QSize(size, size))
            if pixmap.isNull():
                raise SystemExit(f"could not render {source} at {size}px")
            if pixmap.width() != size:
                pixmap = pixmap.scaled(
                    size,
                    size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            frame = Path(work) / f"{size}.png"
            if not pixmap.save(str(frame), "PNG"):
                raise SystemExit(f"could not encode {size}px frame")
            frames.append((size, frame.read_bytes()))
    return frames


def build_ico(frames: list[tuple[int, bytes]]) -> bytes:
    header = struct.pack("<HHH", 0, 1, len(frames))
    offset = len(header) + 16 * len(frames)
    directory, payload = b"", b""
    for size, data in frames:
        # A 256px frame is recorded as 0, which is how the format spells it.
        dimension = 0 if size >= 256 else size
        directory += struct.pack(
            "<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(data), offset
        )
        payload += data
        offset += len(data)
    return header + directory + payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=TARGET)
    arguments = parser.parse_args()

    create_application([])
    frames = render(arguments.source)
    payload = build_ico(frames)
    arguments.output.write_bytes(payload)
    print(
        f"wrote {arguments.output.relative_to(REPOSITORY_ROOT)}: "
        f"{len(frames)} sizes, {len(payload)} bytes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
