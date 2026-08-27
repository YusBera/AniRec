"""Generate the AniRec interface icon set.

    .\\.venv\\Scripts\\python.exe .\\scripts\\build_ui_icons.py

Writes ``AniRec/gui/resources/icons/ui/*.svg``. Pure text output: no Qt, no
rasteriser, so unlike ``build_icon.py`` this runs anywhere, including CI.

Why a generator rather than 40 hand-written files
-------------------------------------------------
The set only works if the shapes agree with each other. A folder drawn at one
weight beside a frame drawn at another reads as two icon sets sharing a folder.
Declaring the geometry in one place makes the shared rules - stroke weight, cap
and join style, the safe area - impossible to apply inconsistently, and makes a
change to any of them a one-line edit rather than forty.

Geometry rules, from docs/ICON_HANDOFF.md
-----------------------------------------
* 24x24 viewBox, transparent, safe area 3..21.
* stroke 2, ``butt`` caps, ``miter`` joins. Nothing in this interface is round
  ended, and round caps are the clearest tell of a generic icon set.
* ``currentColor`` throughout: the frontend tints per theme and state.
* Orthogonal and 45 degrees, except where a form genuinely needs a curve - the
  dial, the refresh arc, the crescent, the lens ring.
* Active variants are one ``fill-rule="evenodd"`` path so the glyph is knocked
  out of the solid. A filled shape with the mark drawn on top in a second
  colour would not survive being tinted.
"""

from __future__ import annotations

import argparse
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPOSITORY_ROOT / "AniRec" / "gui" / "resources" / "icons" / "ui"

LICENCE_NOTE = "Original AniRec interface icon, created for this GPL-3.0 project."

_STROKE_SHELL = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
    'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="butt" stroke-linejoin="miter">\n'
    "  <metadata>{note}</metadata>\n"
    "{body}\n"
    "</svg>\n"
)

_FILL_SHELL = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
    'viewBox="0 0 24 24" fill="currentColor" stroke="none">\n'
    "  <metadata>{note}</metadata>\n"
    "{body}\n"
    "</svg>\n"
)


def stroke_icon(body: str) -> str:
    return _STROKE_SHELL.format(note=LICENCE_NOTE, body=_indent(body))


def fill_icon(body: str) -> str:
    return _FILL_SHELL.format(note=LICENCE_NOTE, body=_indent(body))


def _indent(body: str) -> str:
    return "\n".join(f"  {line}" for line in body.strip().splitlines())


# A folder, mitred rather than radiused, reused by four icons.
FOLDER = '<path d="M3 6h7l2 3h9v11H3z"/>'


# --------------------------------------------------------------------------
# Priority 0
# --------------------------------------------------------------------------

ICONS: dict[str, str] = {}

# Like / Not for me. Sample marks in a frame, not hearts or thumbs: this is an
# instrument recording a positive or negative observation, and the pair reads
# as one control when they sit side by side.
ICONS["like"] = stroke_icon(
    '<rect x="4" y="4" width="16" height="16"/>\n'
    '<path d="M12 9v6M9 12h6"/>'
)
ICONS["like-active"] = fill_icon(
    '<path fill-rule="evenodd" d="M3 3h18v18H3z '
    'M11 8h2v3h3v2h-3v3h-2v-3H8v-2h3z"/>'
)
ICONS["dislike"] = stroke_icon(
    '<rect x="4" y="4" width="16" height="16"/>\n'
    '<path d="M9 12h6"/>'
)
ICONS["dislike-active"] = fill_icon(
    '<path fill-rule="evenodd" d="M3 3h18v18H3z M8 11h8v2H8z"/>'
)

# View modes, drawn as window-manager frames rather than document metaphors.
ICONS["view-grid"] = stroke_icon(
    '<rect x="4" y="4" width="6" height="6"/>\n'
    '<rect x="14" y="4" width="6" height="6"/>\n'
    '<rect x="4" y="14" width="6" height="6"/>\n'
    '<rect x="14" y="14" width="6" height="6"/>'
)
ICONS["view-grid-active"] = fill_icon(
    '<path d="M3 3h8v8H3zM13 3h8v8h-8zM3 13h8v8H3zM13 13h8v8h-8z"/>'
)
ICONS["view-list"] = stroke_icon('<path d="M4 6h3M10 6h10M4 12h3M10 12h10M4 18h3M10 18h10"/>')
ICONS["view-list-active"] = fill_icon(
    '<path d="M3 4h6v4H3zM11 4h10v4H11zM3 10h6v4H3zM11 10h10v4H11z'
    'M3 16h6v4H3zM11 16h10v4H11z"/>'
)
ICONS["view-table"] = stroke_icon(
    '<rect x="4" y="4" width="16" height="16"/>\n'
    '<path d="M4 9h16M9 9v11M15 9v11"/>'
)
ICONS["view-table-active"] = stroke_icon(
    '<rect x="4" y="4" width="16" height="16"/>\n'
    '<path d="M4 9h16M9 9v11M15 9v11"/>\n'
    '<path d="M4 4h16v5H4z" fill="currentColor" stroke="none"/>'
)

# A dial, because a queue of things to watch later is a matter of time. Ticks
# omitted deliberately: at 16px they silt up the face.
ICONS["watch-later"] = stroke_icon(
    '<circle cx="12" cy="12" r="8"/>\n'
    '<path d="M12 7v5h4"/>'
)
ICONS["watch-later-active"] = fill_icon(
    '<path fill-rule="evenodd" d="M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z '
    'M11 6h2v5h4v2h-6z"/>'
)

# The inspector is the application's own panel: header strip, then readout.
ICONS["details-inspector"] = stroke_icon(
    '<rect x="3" y="4" width="18" height="16"/>\n'
    '<path d="M3 9h18M7 13h10M7 17h6"/>'
)
ICONS["external-mal"] = stroke_icon(
    '<path d="M13 4h7v7"/>\n'
    '<path d="M20 4l-9 9"/>\n'
    '<path d="M18 14v6H4V6h6"/>'
)


# --------------------------------------------------------------------------
# Priority 1
# --------------------------------------------------------------------------

# Horizontal faders. A funnel is the convention, but this interface is built
# out of instrument controls and a filter is one. Settings uses the same form
# rotated, which keeps the two distinguishable at 16px.
ICONS["filter"] = stroke_icon(
    '<path d="M3 7h18M3 12h18M3 17h18"/>\n'
    '<path d="M7 5h3v4H7zM14 10h3v4h-3zM9 15h3v4H9z" fill="currentColor" stroke="none"/>'
)
ICONS["hide"] = stroke_icon(
    '<path d="M3 12l5-5h8l5 5-5 5H8z"/>\n'
    '<rect x="10" y="10" width="4" height="4"/>\n'
    '<path d="M4 4l16 16"/>'
)
ICONS["show-hidden"] = stroke_icon(
    '<path d="M3 12l5-5h8l5 5-5 5H8z"/>\n'
    '<rect x="10" y="10" width="4" height="4"/>'
)
ICONS["folder-liked"] = stroke_icon(FOLDER + '\n<path d="M12 12v6M9 15h6"/>')
ICONS["folder-disliked"] = stroke_icon(FOLDER + '\n<path d="M9 15h6"/>')
ICONS["folder-watch-later"] = stroke_icon(
    FOLDER + '\n<circle cx="12" cy="15" r="3"/>\n<path d="M12 13v2h2"/>'
)
ICONS["chevron-left"] = stroke_icon('<path d="M15 5l-7 7 7 7"/>')
ICONS["chevron-right"] = stroke_icon('<path d="M9 5l7 7-7 7"/>')
ICONS["close"] = stroke_icon('<path d="M5 5l14 14M19 5L5 19"/>')
# A square-cased lens. Still unmistakably a lens, but it belongs to the panels.
ICONS["search"] = stroke_icon(
    '<rect x="4" y="4" width="12" height="12"/>\n'
    '<path d="M16 16l5 5"/>'
)


# --------------------------------------------------------------------------
# Priority 2
# --------------------------------------------------------------------------

ICONS["nav-dashboard"] = stroke_icon(
    '<rect x="3" y="4" width="18" height="16"/>\n'
    '<path d="M12 4v16M12 12h9"/>'
)
ICONS["nav-discover"] = stroke_icon(
    '<rect x="3" y="4" width="18" height="16"/>\n'
    '<circle cx="12" cy="12" r="3"/>\n'
    '<path d="M12 4v3M12 17v3M3 12h3M18 12h3"/>'
)
ICONS["nav-library"] = stroke_icon(
    '<rect x="3" y="4" width="18" height="16"/>\n'
    '<path d="M8 8v9M12 8v9M16 8v9"/>'
)
# Vertical faders: the same control family as the filter, on the other axis.
ICONS["nav-settings"] = stroke_icon(
    '<path d="M7 3v18M12 3v18M17 3v18"/>\n'
    '<path d="M5 8h4v3H5zM10 13h4v3h-4zM15 6h4v3h-4z" fill="currentColor" stroke="none"/>'
)
ICONS["refresh"] = stroke_icon(
    '<path d="M21 12a9 9 0 1 1-2.64-6.36"/>\n'
    '<path d="M21 4v5h-5"/>'
)
ICONS["sync"] = stroke_icon(
    '<path d="M3 9h14M14 6l3 3-3 3"/>\n'
    '<path d="M21 15H7M10 12l-3 3 3 3"/>'
)
# The working state is a segmented ring the shell can rotate in steps, which
# suits the rest of the motion in this direction better than a smooth spinner.
ICONS["sync-working"] = stroke_icon(
    '<path d="M12 3v3M12 18v3M3 12h3M18 12h3'
    'M5.64 5.64l2.12 2.12M16.24 16.24l2.12 2.12'
    'M18.36 5.64l-2.12 2.12M7.76 16.24l-2.12 2.12"/>'
)
ICONS["connect"] = stroke_icon(
    '<path d="M9 6H5v12h4M15 6h4v12h-4"/>\n'
    '<path d="M8 12h8"/>'
)
# A profile here is a stored local record, not an avatar.
ICONS["profile"] = stroke_icon(
    '<rect x="3" y="5" width="18" height="14"/>\n'
    '<rect x="6" y="8" width="5" height="5"/>\n'
    '<path d="M14 9h4M14 12h4M6 16h12"/>'
)
ICONS["open-folder"] = stroke_icon(FOLDER + '\n<path d="M12 18v-6M9 15l3-3 3 3"/>')
ICONS["copy"] = stroke_icon(
    '<rect x="9" y="3" width="12" height="12"/>\n'
    '<rect x="3" y="9" width="12" height="12"/>'
)
ICONS["trash"] = stroke_icon(
    '<path d="M3 6h18M8 6V3h8v3M6 6v15h12V6M11 10v7M14 10v7"/>'
)
ICONS["theme-system"] = stroke_icon(
    '<rect x="3" y="4" width="18" height="16"/>\n'
    '<path d="M4 5h8v14H4z" fill="currentColor" stroke="none"/>'
)
ICONS["theme-light"] = stroke_icon(
    '<circle cx="12" cy="12" r="4"/>\n'
    '<path d="M12 2v3M12 19v3M2 12h3M19 12h3'
    'M5.64 5.64l2.12 2.12M16.24 16.24l2.12 2.12'
    'M18.36 5.64l-2.12 2.12M7.76 16.24l-2.12 2.12"/>'
)
ICONS["theme-dark"] = stroke_icon(
    '<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z"/>'
)
# A stepped ramp rather than a smooth swatch: the gradient theme is built from
# two chosen ends, and a segmented readout is how everything else here shows a
# quantity.
ICONS["theme-gradient"] = stroke_icon(
    '<rect x="3" y="4" width="18" height="16"/>\n'
    '<path d="M6 15h2v3H6zM9 13h2v5H9zM12 11h2v7h-2zM15 9h2v9h-2zM18 7h1v11h-1z" '
    'fill="currentColor" stroke="none"/>'
)


def write_set(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, markup in sorted(ICONS.items()):
        path = output_dir / f"{name}.svg"
        path.write_text(markup, encoding="utf-8")
        written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()

    written = write_set(arguments.output)
    for path in written:
        try:
            shown = path.relative_to(REPOSITORY_ROOT)
        except ValueError:
            shown = path
        print(f"wrote {shown}")
    print(f"\n{len(written)} icons")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
