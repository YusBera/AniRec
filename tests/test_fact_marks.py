"""The Profile board's marks: they exist, they obey the set, and they draw.

A fact card is a legend, a figure and a mark. The first two come from the
profile and fail loudly when they are missing; the mark is loaded by name from
disk and fails *silently* - ``ui_icon_pixmap`` answers a missing file with a
null pixmap and an unparseable one with a transparent pixmap of the right
size. Either way the card renders with a hole where its glyph should be and
nothing raises.

So these tests do not check that a file is present. They check that every name
the board can ask for resolves, that the file obeys the rules the other sixty
icons follow, and that rendering it actually puts ink on the plate - at 16px as
well as 22px, because 16px is what the 75% GUI-scale setting produces and it is
where a mark that is too busy stops resolving.
"""

from __future__ import annotations

import pathlib
import re

from PySide6.QtGui import QColor

from AniRec.gui.profile_page import (
    _READING_ICONS,
    _SEASON_ICONS,
    board_facts,
)
from AniRec.gui.resources import ui_icon_pixmap
from AniRec.presentation.taste_profile import (
    EraBucket,
    EraPreferences,
    FingerprintReading,
    GenreDNA,
    GenreVerdict,
    HiddenGems,
    HypeKillers,
    RewatchNote,
    StudioDNA,
    StudioReading,
    TasteProfile,
    TitleVerdict,
    WatchingHabits,
)
from AniRec.gui_main import create_application

ICON_DIR = (
    pathlib.Path(__file__).resolve().parents[1]
    / "AniRec"
    / "gui"
    / "resources"
    / "icons"
    / "ui"
)

# The rendered sizes a fact mark is actually asked for: 22px at the default
# GUI scale, 16px at the smallest one the settings offer.
RENDER_SIZES = (16, 22)

# Past roughly this many direction changes a 22px mark stops being a glyph and
# becomes texture. Measured as path commands inside d="" plus a fixed cost per
# primitive - counting command letters across raw markup also matches letters
# inside <rect>, <circle> and attribute names such as stroke-linecap.
NODE_BUDGET = 14

# What every stroked icon in this set declares. The five filled ``-active``
# variants and the heavier ``check`` are the documented exceptions, and no
# fact mark is either of those.
HOUSE_RULE = (
    'viewBox="0 0 24 24"',
    'stroke="currentColor"',
    'fill="none"',
    'stroke-width="2"',
    'stroke-linecap="butt"',
    'stroke-linejoin="miter"',
)


def _fact_marks():
    return sorted(ICON_DIR.glob("fact-*.svg"))


def _nodes(body: str) -> int:
    count = sum(
        len(re.findall(r"[MmLlHhVvCcSsQqTtAaZz]", d))
        for d in re.findall(r'\bd="([^"]*)"', body)
    )
    count += 4 * len(re.findall(r"<rect\b", body))
    count += 2 * len(re.findall(r"<circle\b", body))
    return count


def _ink(pixmap) -> int:
    """How many pixels the mark actually painted."""
    image = pixmap.toImage()
    return sum(
        1
        for y in range(image.height())
        for x in range(image.width())
        if QColor(image.pixelColor(x, y)).alpha() > 0
    )


def _maximal_profile() -> TasteProfile:
    """A profile that produces one of every fact the board can show."""
    return TasteProfile(
        fingerprint=tuple(
            FingerprintReading(reading_id, reading_id.upper(), "50%",
                               position=0.5, detail="A sentence.")
            for reading_id in _READING_ICONS
        ),
        hype_killers=HypeKillers(
            count=3,
            biggest=TitleVerdict("A", your_score=3, community_score=8.7, delta=-5.7),
        ),
        hidden_gems=HiddenGems(
            rate_text="14%",
            deepest=TitleVerdict("B", your_score=9, community_score=5.9),
        ),
        habits=WatchingHabits(most_rewatched=RewatchNote("C", watches=6)),
        studios=StudioDNA(
            nemesis=StudioReading("D", 14, 5.1),
            most_trusted=StudioReading("E", 12, 8.4),
        ),
        genres=GenreDNA(divisive=GenreVerdict("F")),
        eras=EraPreferences(golden=EraBucket("2010-2014", 40, 8.1),
                            season_of_choice="FALL"),
    )


def test_every_mark_the_board_can_ask_for_resolves_to_a_file():
    """Including the ones only reachable through a lookup table."""
    create_application([])
    wanted = set(_READING_ICONS.values()) | set(_SEASON_ICONS.values())
    wanted |= {fact.icon for fact in board_facts(_maximal_profile())}

    missing = sorted(n for n in wanted if not (ICON_DIR / f"{n}.svg").is_file())

    assert missing == [], f"the board names marks that do not exist: {missing}"
    # The maximal profile must genuinely exercise the board, or this proves
    # nothing about the names hidden inside board_facts().
    assert len(wanted) >= 12


def test_every_fact_mark_obeys_the_house_rule():
    """One deviation and the mark reads as pasted in from another set."""
    offenders = {}
    for path in _fact_marks():
        head = path.read_text(encoding="utf-8").split(">")[0]
        broken = [rule for rule in HOUSE_RULE if rule not in head]
        if broken:
            offenders[path.name] = broken

    assert offenders == {}, offenders


def test_every_fact_mark_stays_within_the_legibility_budget():
    over = {}
    for path in _fact_marks():
        body = path.read_text(encoding="utf-8").split("</metadata>")[-1]
        count = _nodes(body)
        if count > NODE_BUDGET:
            over[path.name] = count

    assert over == {}, f"too busy for 22px, budget {NODE_BUDGET}: {over}"


def test_every_fact_mark_actually_paints_something():
    """The failure this whole file exists for.

    A missing file gives a null pixmap and an unparseable one gives a
    transparent pixmap of the right size, so neither raises and neither is
    caught by checking the file is on disk. Only the rendered result tells you
    whether the card has a glyph or a hole.
    """
    create_application([])
    blank = []
    for path in _fact_marks():
        for size in RENDER_SIZES:
            pixmap = ui_icon_pixmap(path.stem, "#D9A441", size)
            if pixmap.isNull() or _ink(pixmap) == 0:
                blank.append(f"{path.stem} @ {size}px")

    assert blank == [], f"marks that render as nothing: {blank}"


def test_a_mark_keeps_enough_ink_to_read_at_the_smallest_scale():
    """A glyph that survives 22px can still silt up at 16px.

    Not a sharpness test - a floor. A mark covering almost none of its box has
    dropped out; one covering almost all of it has filled in. Both are the same
    failure seen from opposite ends.
    """
    create_application([])
    bad = {}
    for path in _fact_marks():
        pixmap = ui_icon_pixmap(path.stem, "#D9A441", 16)
        coverage = _ink(pixmap) / (16 * 16)
        if not 0.06 <= coverage <= 0.72:
            bad[path.stem] = round(coverage, 3)

    assert bad == {}, f"coverage outside the readable band at 16px: {bad}"


def test_an_unrecognised_reading_or_season_falls_back_to_the_empty_plate():
    """Never substitute a mark that asserts a meaning the tile may not have.

    Both lookups used to fall back to a real glyph - an unknown reading was
    given the community-sync trace and an unknown season a calendar - so the
    card stated something specific and possibly false. fact-unknown is a plate
    with a dash in it and claims nothing.
    """
    create_application([])
    profile = TasteProfile(
        fingerprint=(
            FingerprintReading("a-metric-added-later", "NEW", "42%",
                               position=0.4, detail="A sentence."),
        ),
        eras=EraPreferences(season_of_choice="MONSOON"),
    )

    icons = [fact.icon for fact in board_facts(profile)]

    assert icons == ["fact-unknown", "fact-unknown"]
    assert (ICON_DIR / "fact-unknown.svg").is_file()
