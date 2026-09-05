"""Render the design tokens as CSS custom properties.

The sibling of ``qss_builder``. Both read ``design_tokens`` and neither owns a
value: a colour role, a spacing step or a type ratio is written once, in one
file, and emitted twice. That is the whole point of adding this - two
frontends will exist side by side for the length of the migration, and a
palette maintained in two places is a palette that drifts. The QSS builder's
own docstring records that exact failure happening once already, when light
and dark were hand-written and context menus were styled in only one of them.

Three things need translating rather than copying:

* ``qlineargradient(x1:.. y1:.. x2:.. y2:.. stop:N #hex ..)`` is Qt's spelling.
  CSS wants ``linear-gradient(<angle>, #hex <pct>, ..)``, and the angle has to
  be derived from the vector rather than guessed.
* ``RADIUS`` and ``SPACE`` are unitless integers in Python because Qt wants
  pixels. CSS gets them as ``px``.
* ``TYPE_SCALE`` is a set of ratios against a base size, which is what lets the
  font-scale setting move the hierarchy together. In CSS that is ``em``
  against a root size, so the ratios are emitted unitless and the stylesheet
  multiplies - the same arithmetic, done by the engine instead of by Python.

Emitting is one-way on purpose. Nothing reads CSS back into Python.
"""

from __future__ import annotations

import math
import re

try:
    from .design_tokens import (
        FONT_STACK,
        FONT_STACK_DISPLAY,
        FONT_STACK_MONO,
        RADIUS,
        SPACE,
        TYPE_SCALE,
        WEIGHT,
        palette,
    )
except ImportError:  # Compatibility with the sibling import path used by tests.
    from design_tokens import (  # type: ignore[no-redef]
        FONT_STACK,
        FONT_STACK_DISPLAY,
        FONT_STACK_MONO,
        RADIUS,
        SPACE,
        TYPE_SCALE,
        WEIGHT,
        palette,
    )


# The themes that get a selector in the emitted sheet. "gradient" is excluded
# deliberately: it is generated from two colours a user picks at runtime, so it
# has no fixed value to write into a static file. A client that wants it asks
# the API for a generated palette and sets the properties itself.
CSS_THEMES = ("dark", "light", "oled")

_GRADIENT_PATTERN = re.compile(
    r"qlineargradient\(\s*x1:\s*([\d.]+)\s*,\s*y1:\s*([\d.]+)\s*,"
    r"\s*x2:\s*([\d.]+)\s*,\s*y2:\s*([\d.]+)\s*,\s*(.+?)\s*\)\s*$",
    re.IGNORECASE | re.DOTALL,
)
_STOP_PATTERN = re.compile(r"stop:\s*([\d.]+)\s+([^,)]+)")


def css_variable_name(role: str) -> str:
    """``surface_raised`` -> ``--surface-raised``. One rule, no exceptions."""
    return f"--{role.replace('_', '-')}"


def qt_gradient_to_css(value: str) -> str:
    """Translate one ``qlineargradient`` into a CSS ``linear-gradient``.

    Qt states a direction as a vector between two corners of the painted box
    in normalised coordinates; CSS states it as an angle measured clockwise
    from "to top". Converting rather than hard-coding matters because the
    palette uses three different vectors - vertical for cards, diagonal for
    the page, and a three-stop diagonal for the hero - and eyeballing an angle
    for each would put the light source in a different place on each surface.
    """
    match = _GRADIENT_PATTERN.match(value.strip())
    if match is None:
        return value
    x1, y1, x2, y2 = (float(match.group(index)) for index in range(1, 5))
    stops = [
        f"{colour.strip()} {float(position) * 100:g}%"
        for position, colour in _STOP_PATTERN.findall(match.group(5))
    ]
    if not stops:
        return value
    # CSS y grows downward on screen but its angle is measured from "to top",
    # so the y component is negated before the angle is taken.
    angle = (math.degrees(math.atan2(x2 - x1, -(y2 - y1))) + 360.0) % 360.0
    return f"linear-gradient({angle:g}deg, {', '.join(stops)})"


def _colour_value(value: object) -> str:
    text = str(value)
    return qt_gradient_to_css(text) if "qlineargradient" in text else text


def palette_variables(theme: str, **kwargs) -> dict[str, str]:
    """Every colour role of one theme, as CSS custom properties."""
    return {
        css_variable_name(role): _colour_value(value)
        for role, value in palette(theme, **kwargs).items()
    }


def structural_variables() -> dict[str, str]:
    """Spacing, radius, type ratios, weights and families.

    Theme-independent by construction: the palette changes between light and
    dark, the geometry does not. Emitting them once keeps a theme block to the
    thing that actually varies.
    """
    variables: dict[str, str] = {}
    for name, value in SPACE.items():
        variables[f"--space-{name}"] = f"{int(value)}px"
    for name, value in RADIUS.items():
        variables[f"--radius-{name}"] = f"{int(value)}px"
    for name, value in TYPE_SCALE.items():
        # Unitless: the stylesheet multiplies by its own root size, which is
        # what reproduces the font-scale setting the desktop applies in points.
        variables[f"--type-{name}"] = f"{float(value):g}"
    for name, value in WEIGHT.items():
        variables[f"--weight-{name}"] = str(int(value))
    variables["--font-sans"] = FONT_STACK
    variables["--font-display"] = FONT_STACK_DISPLAY
    variables["--font-mono"] = FONT_STACK_MONO
    return variables


def _block(selector: str, variables: dict[str, str], *, comment: str = "") -> str:
    lines = [f"{selector} {{"]
    if comment:
        lines.insert(0, f"/* {comment} */")
    width = max((len(name) for name in variables), default=0)
    for name, value in variables.items():
        lines.append(f"  {name + ':':<{width + 1}} {value};")
    lines.append("}")
    return "\n".join(lines)


def build_tokens_css(themes: tuple[str, ...] = CSS_THEMES) -> str:
    """The complete token sheet: structure once, then one block per theme.

    ``:root`` carries the default theme so a page renders correctly before any
    theme attribute is set, and ``[data-theme="..."]`` overrides it. The dark
    palette is the default because AniRec's is a dark product - the light mode
    is described in the tokens as "the technical drawing the panel was printed
    from", which is the alternative rather than the baseline.
    """
    default = themes[0]
    sections = [
        "/* AniRec design tokens. Generated from AniRec/gui/design_tokens.py.",
        "   Do not edit by hand: run scripts/build_theme.py. */",
        "",
        _block(
            ":root",
            {**structural_variables(), **palette_variables(default)},
            comment=f"Structure, and the {default} palette as the default.",
        ),
    ]
    for theme in themes:
        sections.append("")
        sections.append(
            _block(f':root[data-theme="{theme}"]', palette_variables(theme))
        )
    # The viewer's own setting, honoured when no explicit theme is stamped.
    # Guarded so an explicit light choice is not overridden by a dark OS.
    if "light" in themes:
        sections.append("")
        sections.append("@media (prefers-color-scheme: light) {")
        sections.append(
            "\n".join(
                f"  {line}"
                for line in _block(
                    ':root:not([data-theme])', palette_variables("light")
                ).splitlines()
            )
        )
        sections.append("}")
    return "\n".join(sections) + "\n"
