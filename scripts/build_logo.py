"""Generate the AniRec logo marks.

    .\\.venv\\Scripts\\python.exe .\\scripts\\build_logo.py

Writes the square marks into ``AniRec/gui/resources/icons/``. Pure text output,
no Qt. Run ``build_icon.py`` afterwards to refresh the packaged ``.ico``.

Two marks, one system
---------------------
``anirec.svg``       AR monogram + readout. The full mark, for 32px and above.
``anirec-mark-a.svg`` A monogram + readout. Same construction with one letter,
                      because two letterforms inside 16px is four pixels each
                      and turns to mush.

Both are drawn as filled paths rather than set in a typeface: nothing can be
guaranteed installed on a user's machine, and a logo that silently falls back
to Arial is not a logo.

The readout
-----------
The segmented bar is the one element unique to this product - the score that
decomposes into parts that sum. It now carries a warm-to-cool sweep drawn from
the palette's own accents rather than a single brass, so it reads as a
calibration strip: brass through gold, a chartreuse bridge, mint, aqua, steel,
then two unlit cells for the headroom. Nine lit of eleven is the point: the
score is high, and it is not 100.
"""

from __future__ import annotations

import argparse
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPOSITORY_ROOT / "AniRec" / "gui" / "resources" / "icons"

NOTE = "Original AniRec logo mark, created for this GPL-3.0 project."

GROUND = "#070C09"
FRAME = "#1E2E24"
FRAME_TICK = "#2E4636"
LETTER = "#E2C489"

# Warm through cool, all of it inside the product's accent range. The two
# closing cells are unlit: headroom, not decoration.
# Six lit steps, not nine. Eleven narrow cells turned to a smear the moment
# the mark was rendered at 16px; six wide ones survive the downscale and the
# sweep still reads warm-to-cool. The two closing cells are unlit headroom.
RAMP = (
    "#C6A15B",
    "#D8B570",
    "#E2C489",
    "#BFCB8A",
    "#8FD3A2",
    "#6FC6C0",
    "#23372C",
    "#182A21",
)

# A, drawn with a low crossbar. Outer contour plus a triangular counter, cut
# with evenodd so the letter stays one shape at any size.
# The first attempt put the counter's base on the same line as the top of the
# legs gap, which left no crossbar between them at all and made the letter read
# as a lambda. The crossbar is the band from y=126 to y=146; the counter sits
# above it, the legs gap below.
GLYPH_A = (
    "M30 170 L74 52 H88 L132 170 H108 L99 146 H63 L54 170 Z"
    " M70 126 H92 L81 98 Z"
)

# R, assembled from four orthogonal blocks and one parallelogram leg. The
# counter is the gap the blocks leave, so no second contour is needed.
# The bowl is deliberately narrower than the letter's full width. The first
# version ran it out to x=222, which left the leg nowhere to splay into: it
# descended flush with the bowl's right edge and the R read as a P with a
# block under it. The bowl now stops at 206 so the leg can finish past it.
GLYPH_R_BLOCKS = (
    (142, 52, 22, 118),   # stem
    (164, 52, 42, 22),    # bowl, top arm
    (184, 52, 22, 62),    # bowl, right side
    (164, 92, 42, 22),    # bowl, bottom arm
)
GLYPH_R_LEG = "M170 114 H192 L222 170 H200 Z"


def _bar(x0: int, y: int, width: int, cells: int, height: int) -> str:
    """A segmented readout: equal cells, equal gaps, exact total width."""
    gap = 3
    cell = (width - gap * (cells - 1)) // cells
    rects = []
    for index in range(cells):
        left = x0 + index * (cell + gap)
        rects.append(
            f'    <rect x="{left}" y="{y}" width="{cell}" height="{height}" '
            f'fill="{RAMP[index]}"/>'
        )
    return "\n".join(rects)


def _chassis() -> str:
    return (
        f'  <rect width="256" height="256" fill="{GROUND}"/>\n'
        f'  <rect x="11" y="11" width="234" height="234" fill="none" '
        f'stroke="{FRAME}" stroke-width="3"/>\n'
        f'  <path d="M11 30V11h19M226 11h19v19M245 226v19h-19M30 245H11v-19" '
        f'fill="none" stroke="{FRAME_TICK}" stroke-width="3"/>'
    )


def mark_ar() -> str:
    blocks = "\n".join(
        f'    <rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{LETTER}"/>'
        for x, y, w, h in GLYPH_R_BLOCKS
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <metadata>{NOTE}</metadata>
{_chassis()}
  <g shape-rendering="geometricPrecision">
    <path fill-rule="evenodd" fill="{LETTER}" d="{GLYPH_A}"/>
{blocks}
    <path fill="{LETTER}" d="{GLYPH_R_LEG}"/>
  </g>
  <g shape-rendering="crispEdges">
{_bar(30, 190, 192, 8, 20)}
  </g>
</svg>
"""


def mark_a() -> str:
    """One letter, centred, at the weight the AR mark uses.

    The A is shifted and scaled to sit on the same optical centre as the pair,
    so switching marks between sizes does not look like switching logos.
    """
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <metadata>{NOTE}</metadata>
{_chassis()}
  <g transform="translate(128 111) scale(1.22) translate(-81 -111)">
    <path fill-rule="evenodd" fill="{LETTER}" d="{GLYPH_A}"/>
  </g>
  <g shape-rendering="crispEdges">
{_bar(58, 196, 140, 6, 22)}
  </g>
</svg>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    arguments.output.mkdir(parents=True, exist_ok=True)

    for name, markup in (("anirec.svg", mark_ar()), ("anirec-mark-a.svg", mark_a())):
        path = arguments.output / name
        path.write_text(markup, encoding="utf-8")
        print(f"wrote {path.relative_to(REPOSITORY_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
