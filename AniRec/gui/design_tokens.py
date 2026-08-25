"""The single source of truth for AniRec's visual design.

Both stylesheets are generated from the maps below, so light and dark cannot
drift apart: a rule written once is emitted for both, and a role that exists in
one mode necessarily exists in the other.

The direction is cinematic. Chrome recedes to near neutral warm greys so that
cover artwork carries the visual weight, one accent does all the signalling,
and depth comes from tone rather than from drawing a line around everything.

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

RADIUS = MappingProxyType(
    {
        "sm": 6,
        "md": 10,
        "lg": 14,
        "xl": 20,
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

FONT_STACK = '"Segoe UI", "Inter", "Noto Sans", "DejaVu Sans", sans-serif'


DARK = MappingProxyType(
    {
        # Surfaces, from furthest back to closest.
        "bg": "#0B0B0F",
        "bg_alt": "#0E0E13",
        "sidebar": "#101015",
        "surface": "#16161C",
        "surface_raised": "#1E1E26",
        "surface_sunken": "#0F0F14",
        "well": "#08080B",
        # Text.
        "text": "#F2F0ED",
        "text_strong": "#FFFFFF",
        "text_muted": "#9A968F",
        "text_subtle": "#6B6862",
        "text_disabled": "#55524D",
        # Lines. Deliberately quiet: depth is carried by tone.
        "border": "#26262E",
        "border_strong": "#3A3A44",
        "border_subtle": "#1C1C23",
        # The single accent.
        "accent": "#E0685A",
        "accent_hover": "#EC7A6C",
        "accent_soft": "#F0958A",
        "accent_muted": "#3A211E",
        "accent_contrast": "#FFFFFF",
        "focus": "#E0685A",
        "selection": "#3A211E",
        # Status. Warm enough to sit beside the accent without clashing.
        "success_bg": "#14251C",
        "success_border": "#2A5240",
        "success_text": "#7BD5A6",
        "danger_bg": "#2B1518",
        "danger_border": "#5E2C31",
        "danger_text": "#F09A96",
        "warning_bg": "#2A2113",
        "warning_border": "#5C4A25",
        "warning_text": "#E5C27E",
        "busy_bg": "#1E1E2E",
        "busy_border": "#43436B",
        "busy_text": "#B9B9E0",
        "saved_bg": "#13202B",
        "saved_border": "#2F5670",
        "saved_text": "#91C4E0",
        # Depth, used sparingly in place of borders.
        "gradient_card": (
            "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            "stop:0 #1A1A21, stop:1 #131318)"
        ),
        "gradient_page": (
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            "stop:0 #0B0B0F, stop:1 #101015)"
        ),
        "gradient_hero": (
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            "stop:0 #1B1A20, stop:0.55 #211B1D, stop:1 #2A1D1B)"
        ),
    }
)


LIGHT = MappingProxyType(
    {
        "bg": "#FAF9F7",
        "bg_alt": "#F5F4F1",
        "sidebar": "#F3F2EF",
        "surface": "#FFFFFF",
        "surface_raised": "#FFFFFF",
        "surface_sunken": "#F2F1EE",
        "well": "#EDEBE7",
        "text": "#1A1A1F",
        "text_strong": "#0E0E12",
        "text_muted": "#6E6A64",
        "text_subtle": "#918C85",
        "text_disabled": "#AFAAA3",
        "border": "#E2E0DB",
        "border_strong": "#C9C6BF",
        "border_subtle": "#EDEBE7",
        "accent": "#C4503F",
        "accent_hover": "#AC4433",
        "accent_soft": "#A8402F",
        "accent_muted": "#F7E9E5",
        "accent_contrast": "#FFFFFF",
        "focus": "#C4503F",
        "selection": "#F7DFDA",
        "success_bg": "#E9F5EE",
        "success_border": "#A8D4BC",
        "success_text": "#1C6742",
        "danger_bg": "#FCECEA",
        "danger_border": "#E8B3AC",
        "danger_text": "#A03327",
        "warning_bg": "#FBF3E2",
        "warning_border": "#DFC894",
        "warning_text": "#6B5216",
        "busy_bg": "#EEEDF7",
        "busy_border": "#C3C1E0",
        "busy_text": "#4A4780",
        "saved_bg": "#E8F2F8",
        "saved_border": "#A9C9DD",
        "saved_text": "#245A78",
        "gradient_card": (
            "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            "stop:0 #FFFFFF, stop:1 #FAF9F7)"
        ),
        "gradient_page": (
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            "stop:0 #FAF9F7, stop:1 #F4F2EF)"
        ),
        "gradient_hero": (
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            "stop:0 #FFFFFF, stop:0.55 #FBF5F3, stop:1 #F8EEEB)"
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
        "surface": "#0A0A0D",
        "surface_raised": "#141418",
        "surface_sunken": "#050506",
        "well": "#000000",
        "border": "#232329",
        "border_strong": "#3E3E48",
        "border_subtle": "#141418",
        "gradient_card": (
            "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            "stop:0 #101014, stop:1 #050506)"
        ),
        "gradient_page": "#000000",
        "gradient_hero": (
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            "stop:0 #0C0C0F, stop:0.55 #14100F, stop:1 #1C1210)"
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
