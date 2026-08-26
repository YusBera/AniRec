"""The single source of truth for AniRec's visual design.

Both stylesheets are generated from the maps below, so light and dark cannot
drift apart: a rule written once is emitted for both, and a role that exists in
one mode necessarily exists in the other.

The direction is an instrument panel. Chrome recedes into a lacquer green-black
that is barely a colour at all, so cover artwork carries the visual weight.
Depth comes from tone rather than from drawing a line around everything.

Two accents, and they mean different things. Brass is *you*: your match score,
your taste, the one action a screen wants you to take. Aqua is *everyone else*
and *the system*: focus rings, saved items, community ratings. Keeping them
apart is what stops the interface shouting in one colour from eight places at
once, which is what the single terracotta accent used to do.

The same two accents carry the AniRec landing page, so the app a visitor
downloads looks like the page that sold it to them.

Colour roles rather than colour names. A rule asks for ``surface`` or
``text_muted``, never for a particular hex value, which is what lets the same
rule mean the right thing in either mode.
"""

from __future__ import annotations

from types import MappingProxyType


# Spacing, in pixels. Layout code names these instead of repeating magic
# numbers, so vertical rhythm stays consistent across pages.
SPACE = MappingProxyType(
    {
        "none": 0,
        "hair": 2,
        "xs": 4,
        "sm": 8,
        "md": 12,
        "lg": 16,
        "xl": 24,
        "2xl": 32,
        "3xl": 40,
    }
)

# Tightened from 6/10/14/20. Everything being generously rounded made every
# element read as the same kind of object: a nav item, a warning banner and a
# recommendation card were all equally soft, so nothing looked more important
# than anything else. Small radii on controls, larger only on the things that
# genuinely are cards.
RADIUS = MappingProxyType(
    {
        "sm": 4,
        "md": 6,
        "lg": 9,
        "xl": 13,
        "pill": 999,
    }
)

# Type sizes as multiples of the application's base font. Expressing them
# relatively is what lets the font scale setting move every level together;
# the absolute pixel sizes used previously left headings fixed while body text
# grew, which inverted the hierarchy at larger scales.
TYPE_SCALE = MappingProxyType(
    {
        "xs": 0.82,
        "sm": 0.92,
        "md": 1.00,
        "lg": 1.14,
        "xl": 1.30,
        "2xl": 1.60,
        "3xl": 1.95,
        "4xl": 2.35,
    }
)

WEIGHT = MappingProxyType({"normal": 400, "medium": 600, "bold": 700, "heavy": 800})

# Three roles, not one. The interface used to set a single family for
# everything, which meant a match percentage, a section heading and a sentence
# of body copy were all rendered by the same neutral face and the hierarchy had
# to be carried entirely by size and weight.
#
# Every family named here ships with Windows 10 and 11, so there is nothing to
# bundle and nothing to fall back from on the platform the app targets.
FONT_STACK = '"Segoe UI Variable Text", "Segoe UI", "Noto Sans", "DejaVu Sans", sans-serif'

# Bahnschrift is Microsoft's DIN: technical, slightly condensed, and nothing
# like the default UI face, which is what makes a heading read as a heading.
FONT_STACK_DISPLAY = (
    '"Bahnschrift", "Segoe UI Variable Display", "Segoe UI Semibold", '
    '"DejaVu Sans", sans-serif'
)

# Numbers that belong in a column - match scores, MAL ratings, counters - get a
# monospaced face so digits line up instead of jittering between rows.
FONT_STACK_MONO = '"Cascadia Mono", "Consolas", "DejaVu Sans Mono", monospace'


DARK = MappingProxyType(
    {
        # Surfaces, from furthest back to closest. Green-black rather than
        # neutral black: a hue bias this slight is not read as "green", it is
        # read as considered, and it keeps warm cover artwork from looking
        # tinted the way a pure grey chrome does.
        "bg": "#0A120E",
        "bg_alt": "#0C1611",
        "sidebar": "#070E0B",
        "surface": "#12201A",
        "surface_raised": "#182A21",
        "surface_sunken": "#0C1712",
        "well": "#06100C",
        # Text. Bone rather than white; pure white on a near-black panel is
        # harsher than anything a long session wants.
        "text": "#E9E5D6",
        "text_strong": "#F7F4EA",
        "text_muted": "#9BA99E",
        "text_subtle": "#7C8C80",
        "text_disabled": "#5A6960",
        # Lines. Deliberately quiet: depth is carried by tone.
        "border": "#23372C",
        "border_strong": "#35513F",
        "border_subtle": "#182A21",
        # Brass. This means "yours": your match, your taste, the one action
        # the screen is asking for.
        "accent": "#C6A15B",
        "accent_hover": "#D8B570",
        "accent_soft": "#E2C489",
        "accent_muted": "#2A2417",
        # Brass is a light colour, so anything sitting on it must be dark.
        "accent_contrast": "#0A120E",
        # Aqua. This means "the system": focus, selection, saved. Focus rings
        # in a second colour are unmistakable against brass controls.
        "focus": "#6FC6C0",
        "selection": "#22403C",
        # Status. Vivid enough to signal against a ground that is itself
        # faintly green.
        "success_bg": "#102A1E",
        "success_border": "#2E6B4A",
        "success_text": "#74D6A0",
        "danger_bg": "#2C1417",
        "danger_border": "#6B2F34",
        "danger_text": "#F0989A",
        "warning_bg": "#2A2213",
        "warning_border": "#5E4C26",
        "warning_text": "#E5C27E",
        "busy_bg": "#16262B",
        "busy_border": "#35606B",
        "busy_text": "#9FCBD4",
        "saved_bg": "#142A28",
        "saved_border": "#2F6460",
        "saved_text": "#8FD3CD",
        # Depth, used sparingly in place of borders.
        "gradient_card": (
            "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            "stop:0 #16261E, stop:1 #101B15)"
        ),
        "gradient_page": (
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            "stop:0 #0A120E, stop:1 #0D1813)"
        ),
        "gradient_hero": (
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            "stop:0 #14231B, stop:0.55 #1A2A20, stop:1 #24291B)"
        ),
    }
)


# Sage paper. The light mode is not the dark mode inverted, it is the
# technical drawing the panel was printed from: a paper stock with the same
# faint green in it, bronze where the dark mode has brass.
LIGHT = MappingProxyType(
    {
        "bg": "#E9ECE4",
        "bg_alt": "#E3E7DD",
        "sidebar": "#DDE2D6",
        "surface": "#F4F6EF",
        "surface_raised": "#FAFBF5",
        "surface_sunken": "#E3E7DD",
        "well": "#D8DED0",
        "text": "#16241F",
        "text_strong": "#0C1613",
        "text_muted": "#4C5B50",
        "text_subtle": "#5C6858",
        "text_disabled": "#97A294",
        "border": "#C6CFBE",
        "border_strong": "#A8B4A0",
        "border_subtle": "#D5DCCC",
        "accent": "#7A5D1C",
        "accent_hover": "#634B14",
        # accent_soft is used as a *text* colour, so on paper it has to be the
        # darker end of the brass range, not the lighter one.
        "accent_soft": "#5E4813",
        "accent_muted": "#EDE7D5",
        "accent_contrast": "#FBFCF7",
        "focus": "#2C7C74",
        "selection": "#CFE3DF",
        "success_bg": "#E3F1E8",
        "success_border": "#A5CDB4",
        "success_text": "#1B6340",
        "danger_bg": "#FAEAE8",
        "danger_border": "#E0AFA9",
        "danger_text": "#96301F",
        "warning_bg": "#F7F0DC",
        "warning_border": "#D9C48F",
        "warning_text": "#6A5115",
        "busy_bg": "#E6EFF0",
        "busy_border": "#AEC9CC",
        "busy_text": "#2A5A62",
        "saved_bg": "#DFEEEC",
        "saved_border": "#A6CBC6",
        "saved_text": "#235C56",
        "gradient_card": (
            "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            "stop:0 #FAFBF5, stop:1 #F1F4EB)"
        ),
        "gradient_page": (
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            "stop:0 #E9ECE4, stop:1 #E2E7DC)"
        ),
        "gradient_hero": (
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            "stop:0 #FAFBF5, stop:0.55 #F4F5EA, stop:1 #F2EFDF)"
        ),
    }
)


# True black for OLED panels, where an unlit pixel emits no light and draws no
# power. Derived from DARK rather than written out again, so the two cannot
# drift: only the surfaces that should reach black are overridden, and the
# borders lift slightly because separators disappear entirely against #000000.
OLED = MappingProxyType(
    {
        **DARK,
        "bg": "#000000",
        "bg_alt": "#000000",
        "sidebar": "#000000",
        "surface": "#08120D",
        "surface_raised": "#0F1C15",
        "surface_sunken": "#040807",
        "well": "#000000",
        "border": "#1C2E24",
        "border_strong": "#33503E",
        "border_subtle": "#0F1C15",
        "gradient_card": (
            "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            "stop:0 #0C1912, stop:1 #040807)"
        ),
        "gradient_page": "#000000",
        "gradient_hero": (
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            "stop:0 #08120D, stop:0.55 #0E1811, stop:1 #17190E)"
        ),
    }
)


PALETTES = MappingProxyType({"dark": DARK, "light": LIGHT, "oled": OLED})


def _luminance(colour: str) -> float:
    """Perceived brightness of a hex colour, 0 for black and 1 for white."""
    body = colour.lstrip("#")
    if len(body) == 3:
        body = "".join(character * 2 for character in body)
    red, green, blue = (int(body[index : index + 2], 16) / 255 for index in (0, 2, 4))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _mix(first: str, second: str, weight: float = 0.5) -> str:
    """Blend two hex colours."""
    parts = []
    for colour in (first, second):
        body = colour.lstrip("#")
        if len(body) == 3:
            body = "".join(character * 2 for character in body)
        parts.append([int(body[index : index + 2], 16) for index in (0, 2, 4)])
    blended = [
        round(one * (1 - weight) + two * weight) for one, two in zip(parts[0], parts[1])
    ]
    return "#" + "".join(f"{value:02X}" for value in blended)


def _saturation(colour: str) -> float:
    """How colourful a value is, 0 for grey and 1 for a pure hue."""
    body = colour.lstrip("#")
    if len(body) == 3:
        body = "".join(character * 2 for character in body)
    channels = [int(body[index : index + 2], 16) / 255 for index in (0, 2, 4)]
    high, low = max(channels), min(channels)
    return 0.0 if high == 0 else (high - low) / high


def _shift(colour: str, amount: float, base) -> str:
    """Move a colour toward white on a dark base, toward black on a light one."""
    target = "#FFFFFF" if _luminance(base["bg"]) < 0.5 else "#000000"
    return _mix(colour, target, amount)


def _accent_for(start: str, end: str, base) -> str:
    """Pick a highlight from the user's colours that stays readable.

    The more saturated end is the one that reads as "their" colour. It is then
    lifted away from the background until there is real contrast, because a
    gradient of two dark blues would otherwise give a dark blue accent that
    disappeared into it.
    """
    candidate = start if _saturation(start) >= _saturation(end) else end
    background = _luminance(base["bg"])
    for _attempt in range(6):
        if abs(_luminance(candidate) - background) >= 0.28:
            return candidate
        candidate = _shift(candidate, 0.18, base)
    return candidate


def gradient_palette(start: str, end: str):
    """Build a full palette around two colours the user chose.

    Only the page background is actually theirs. Everything else is derived so
    the result stays legible whatever they pick: the base palette is chosen by
    the brightness of their colours, surfaces are mixed toward it so cards
    still read as raised, and text keeps the contrast of that base rather than
    being tinted into illegibility.
    """
    base = LIGHT if (_luminance(start) + _luminance(end)) / 2 > 0.5 else DARK
    midpoint = _mix(start, end)
    # CHANGE [BUG-ACCENT]: derive the accent from the chosen colours. It used to
    # stay the default terracotta whatever the user picked, so buttons, the
    # match bar and every highlight ignored their gradient entirely. The more
    # colourful of the two ends is taken and pushed away from the background
    # until it is clearly readable against it.
    accent = _accent_for(start, end, base)
    return MappingProxyType(
        {
            **base,
            "accent": accent,
            "accent_hover": _shift(accent, 0.14, base),
            "accent_soft": _shift(accent, 0.28, base),
            "accent_muted": _mix(accent, midpoint, 0.78),
            "accent_contrast": "#FFFFFF" if _luminance(accent) < 0.55 else "#101014",
            "focus": accent,
            "selection": _mix(accent, midpoint, 0.62),
            "bg": midpoint,
            "bg_alt": _mix(midpoint, base["surface"], 0.35),
            "sidebar": _mix(start, base["sidebar"], 0.55),
            "surface": _mix(midpoint, base["surface"], 0.72),
            "surface_raised": _mix(midpoint, base["surface_raised"], 0.80),
            "surface_sunken": _mix(midpoint, base["surface_sunken"], 0.60),
            "gradient_page": (
                f"qlineargradient(x1:0, y1:0, x2:1, y2:1, "
                f"stop:0 {start}, stop:1 {end})"
            ),
            "gradient_hero": (
                f"qlineargradient(x1:0, y1:0, x2:1, y2:1, "
                f"stop:0 {_mix(start, base['surface'], 0.5)}, "
                f"stop:1 {_mix(end, base['surface'], 0.5)})"
            ),
        }
    )


def palette(theme: str, *, gradient_start: str | None = None, gradient_end: str | None = None):
    """Return the colour map for a theme name."""
    name = str(theme).strip().casefold()
    if name == "gradient":
        return gradient_palette(
            gradient_start or "#1B1A20", gradient_end or "#2A1D1B"
        )
    try:
        return PALETTES[name]
    except KeyError as error:
        raise ValueError(f"Unknown theme: {theme!r}") from error
