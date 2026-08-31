"""The single source of truth for AniRec's visual design.

Both stylesheets are generated from the maps below, so light and dark cannot
drift apart: a rule written once is emitted for both, and a role that exists in
one mode necessarily exists in the other.

The direction is an instrument panel. Chrome recedes into a lacquer green-black
that is barely a colour at all, so cover artwork carries the visual weight.
Depth comes from tone rather than from drawing a line around everything.

Two accents, and they mean different things. Amber is *you*: your match score,
your taste, the one action a screen wants you to take. Cyan is *everyone else*
and *the system*: focus rings, saved items, community ratings. Keeping them
apart is what stops the interface shouting in one colour from eight places at
once, which is what the single terracotta accent used to do.

CHANGE [CRT]: the dark palette is the workstation artifact's, imported value
for value - a phosphor readout on a lab bench, not gold leaf on lacquer. Text
is a green-grey rather than bone, because a CRT's white was never white. Two
roles could not be imported as they stand: the artifact sets its faintest
label for 9px type on a single ground, and at body size on this app's darkest
panel it measures 3.21:1. It and the negative colour are walked toward the
text colour until they pass AA, and nothing else moved.

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

# The landing artifact is built like a rack-mounted instrument: square chassis,
# hairline divisions, and only the tiniest easing on large physical panels.
# Standard radio buttons remain circular because their shape communicates the
# control; everything else uses this near-square scale.
RADIUS = MappingProxyType(
    {
        "sm": 0,
        "md": 1,
        "lg": 2,
        "xl": 3,
        "pill": 2,
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
FONT_STACK = (
    '"Yu Gothic UI", "Meiryo UI", "Segoe UI Variable Text", "Segoe UI", '
    '"Noto Sans CJK JP", "DejaVu Sans", sans-serif'
)

# CHANGE [CRT]: Martian Mono, the face the workstation artifact sets its
# headings in. A wide monospace rather than a condensed grotesque, which is
# what makes a legend read as something stencilled onto a panel instead of
# as bold body copy. Bahnschrift stays behind it: the app must still look
# right before the bundled file loads, and on a machine where it cannot.
#
# Both bundled faces are SIL OFL 1.1, which is compatible with this project's
# GPL-3 licence. The licence texts ship beside them in resources/fonts.
FONT_STACK_DISPLAY = (
    '"Martian Mono", "Bahnschrift Condensed", "Bahnschrift", '
    '"Yu Gothic UI Semibold", "Segoe UI Variable Display", sans-serif'
)

# Numbers that belong in a column - match scores, MAL ratings, counters - get a
# monospaced face so digits line up instead of jittering between rows.
#
# CHANGE [CRT]: IBM Plex Mono, again from the artifact. Cascadia stays as the
# fallback; it is the closest face Windows ships.
FONT_STACK_MONO = (
    '"IBM Plex Mono", "Cascadia Mono", "Consolas", "DejaVu Sans Mono", monospace'
)


DARK = MappingProxyType(
    {
        # Surfaces, from furthest back to closest. Green-black rather than
        # neutral black: a hue bias this slight is not read as "green", it is
        # read as considered, and it keeps warm cover artwork from looking
        # tinted the way a pure grey chrome does.
        "bg": "#070C09",
        "bg_alt": "#0A100C",
        "sidebar": "#050907",
        "surface": "#0C1410",
        "surface_raised": "#101A14",
        "surface_sunken": "#0A120E",
        "well": "#040806",
        # Text. Bone rather than white; pure white on a near-black panel is
        # harsher than anything a long session wants.
        "text": "#C6D4C2",
        "text_strong": "#DCE8D8",
        "text_muted": "#849686",
        "text_subtle": "#748676",
        "text_disabled": "#47564A",
        # Lines. Deliberately quiet: depth is carried by tone.
        "border": "#1E2E24",
        "border_strong": "#2E4636",
        "border_subtle": "#16221B",
        # Brass. This means "yours": your match, your taste, the one action
        # the screen is asking for.
        "accent": "#D9A441",
        "accent_hover": "#E8B85C",
        "accent_soft": "#E9C275",
        "accent_muted": "#241B0C",
        # Brass is a light colour, so anything sitting on it must be dark.
        "accent_contrast": "#0A0F0B",
        # Aqua. This means "the system": focus, selection, saved. Focus rings
        # in a second colour are unmistakable against brass controls.
        "focus": "#5FBFB5",
        "selection": "#17332F",
        # Status. Vivid enough to signal against a ground that is itself
        # faintly green.
        "success_bg": "#0C2016",
        "success_border": "#2A6244",
        "success_text": "#6FCF99",
        "danger_bg": "#241110",
        "danger_border": "#7A3E28",
        "danger_text": "#D98363",
        # CHANGE [WARN-VS-YOU]: this was #D9A441 - byte for byte the accent
        # above. The palette's own rule is that amber means "yours": your
        # match, your taste, the one action a screen is asking for. A
        # caution wearing the identical value breaks that rule at the worst
        # moment, so a SAMPLE DATA stamp and a RUN ANALYSIS button read as
        # the same kind of thing. Warning moves toward orange: still
        # unmistakably a caution, no longer the brand accent.
        "warning_bg": "#241609",
        "warning_border": "#7A4E1E",
        "warning_text": "#E08A43",
        "busy_bg": "#0E1F21",
        "busy_border": "#2F6B66",
        "busy_text": "#8FCFC7",
        "saved_bg": "#0F2523",
        "saved_border": "#2F6B66",
        "saved_text": "#5FBFB5",
        # Depth, used sparingly in place of borders.
        "gradient_card": (
            "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            "stop:0 #101A14, stop:1 #0A120E)"
        ),
        "gradient_page": (
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            "stop:0 #070C09, stop:1 #0A120E)"
        ),
        "gradient_hero": (
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            "stop:0 #0C1410, stop:0.55 #101A14, stop:1 #16221B)"
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


def _channels(colour: str) -> tuple[float, float, float]:
    body = colour.lstrip("#")
    if len(body) == 3:
        body = "".join(character * 2 for character in body)
    return tuple(int(body[index : index + 2], 16) / 255 for index in (0, 2, 4))  # type: ignore[return-value]


def _relative_luminance(colour: str) -> float:
    """WCAG 2.1 relative luminance: sRGB channels linearised, then weighted.

    Distinct from ``_luminance`` above, which weights the gamma-encoded values
    directly. That one is a fine cheap answer to "is this backdrop light or
    dark", which is all it is still used for. It is not the quantity the
    contrast formula is defined over, and using it there was the bug.
    """
    linear = [
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in _channels(colour)
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(first: str, second: str) -> float:
    """The WCAG 2.1 contrast ratio between two colours, from 1 to 21."""
    lighter, darker = sorted(
        (_relative_luminance(first), _relative_luminance(second)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


# WCAG 2.1 AA: 4.5:1 for body text, 3:1 for large text, UI components and
# graphical objects. Borders and focus rings are the latter.
CONTRAST_TEXT = 4.5
CONTRAST_UI = 3.0


def _readable(colour: str, background: str, minimum: float = CONTRAST_TEXT) -> str:
    """Push a colour away from a background until it actually passes WCAG.

    CHANGE [WCAG]: this used to compare gamma-encoded luminances and accept
    any pair whose difference cleared an arbitrary 0.28-0.34. That is not the
    contrast formula and does not correlate with it: the check passes colours
    that fail 4.5:1 and rejects ones that pass, and every derived role in the
    palette - the tinted text, the five status chips, focus, accent_soft -
    was built through it. It now measures the ratio the standard defines, so
    the theme is accessible by construction rather than by hope.
    """
    target = "#FFFFFF" if _luminance(background) < 0.5 else "#000000"
    candidate = colour
    # Sixteen steps of 0.10 traverse the full distance to the target, so a
    # colour that starts on top of its background can still reach compliance.
    for _attempt in range(16):
        if contrast_ratio(candidate, background) >= minimum:
            return candidate
        candidate = _mix(candidate, target, 0.10)
    return candidate


def gradient_palette(start: str, end: str):
    """Build a full palette around two colours the user chose.

    Every surface and line role is derived, not inherited. The previous
    version tinted fifteen roles and left the rest at the dark theme's values,
    so in a red gradient the navigation rail, the wells, every border and all
    five status colours stayed green: whole regions of the interface simply
    refused to follow the theme.

    Semantic hues survive because they carry meaning - success must still read
    as success - but they are blended into the chosen world so they belong to
    it, and each one is then checked for contrast against the surface it
    actually sits on.
    """
    base = LIGHT if (_luminance(start) + _luminance(end)) / 2 > 0.5 else DARK
    midpoint = _mix(start, end)
    accent = _accent_for(start, end, base)

    surface = _mix(midpoint, base["surface"], 0.72)
    surface_raised = _mix(midpoint, base["surface_raised"], 0.80)
    surface_sunken = _mix(midpoint, base["surface_sunken"], 0.60)
    well = _mix(midpoint, base["well"], 0.45)
    page_bg = midpoint

    # Lines take the chosen hue so they read as part of the same object.
    border = _mix(surface, base["border"], 0.55)
    border_strong = _mix(surface, base["border_strong"], 0.50)
    border_subtle = _mix(surface, base["border_subtle"], 0.70)

    # Text keeps the base's contrast and only a trace of the hue: bias it any
    # further and long passages start to lose legibility.
    def _tinted_text(role: str, amount: float = 0.08) -> str:
        return _readable(_mix(base[role], midpoint, amount), page_bg, CONTRAST_TEXT)

    def _status(role_bg: str, role_border: str, role_text: str):
        """Keep the hue, join the world, stay readable on its own chip."""
        chip = _mix(base[role_bg], midpoint, 0.45)
        return (
            chip,
            _mix(base[role_border], midpoint, 0.30),
            _readable(_mix(base[role_text], midpoint, 0.12), chip, CONTRAST_TEXT),
        )

    success = _status("success_bg", "success_border", "success_text")
    danger = _status("danger_bg", "danger_border", "danger_text")
    warning = _status("warning_bg", "warning_border", "warning_text")
    busy = _status("busy_bg", "busy_border", "busy_text")
    saved = _status("saved_bg", "saved_border", "saved_text")

    # The second accent stays a second accent. Collapsing focus onto the
    # user's colour cost the interface its "yours" / "the system" split, so
    # the base signal hue is kept and only lifted until it reads.
    focus = _readable(_mix(base["focus"], midpoint, 0.18), surface, CONTRAST_UI)

    return MappingProxyType(
        {
            **base,
            "accent": accent,
            "accent_hover": _shift(accent, 0.14, base),
            "accent_soft": _readable(_shift(accent, 0.28, base), surface, CONTRAST_TEXT),
            "accent_muted": _mix(accent, midpoint, 0.78),
            "accent_contrast": "#FFFFFF" if _luminance(accent) < 0.55 else "#101014",
            "focus": focus,
            "selection": _mix(accent, midpoint, 0.62),
            "bg": page_bg,
            "bg_alt": _mix(midpoint, base["surface"], 0.35),
            "sidebar": _mix(start, base["sidebar"], 0.30),
            "surface": surface,
            "surface_raised": surface_raised,
            "surface_sunken": surface_sunken,
            "well": well,
            "border": border,
            "border_strong": border_strong,
            "border_subtle": border_subtle,
            # Primary copy is NOT tinted. It is the one thing on screen that
            # must stay maximally legible whatever two colours are chosen, and
            # the hue bias that helps chrome belong to the theme buys nothing
            # on a paragraph. Only the recessive text roles take the tint.
            "text": base["text"],
            "text_strong": base["text_strong"],
            "text_muted": _tinted_text("text_muted", 0.10),
            "text_subtle": _tinted_text("text_subtle", 0.12),
            "text_disabled": _mix(base["text_disabled"], midpoint, 0.16),
            "success_bg": success[0], "success_border": success[1], "success_text": success[2],
            "danger_bg": danger[0], "danger_border": danger[1], "danger_text": danger[2],
            "warning_bg": warning[0], "warning_border": warning[1], "warning_text": warning[2],
            "busy_bg": busy[0], "busy_border": busy[1], "busy_text": busy[2],
            "saved_bg": saved[0], "saved_border": saved[1], "saved_text": saved[2],
            "gradient_card": (
                f"qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                f"stop:0 {surface_raised}, stop:1 {surface})"
            ),
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
