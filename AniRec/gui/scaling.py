"""GUI scale, applied to every hand-sized dimension in the interface.

Addresses: BUG2 (layout and scaling at non-100% Windows DPI).

Qt already scales for the display's DPI, so a widget asking for 224 pixels gets
224 *logical* pixels and is drawn larger on a 120% display. What that does not
do is change the proportion: the window's logical size shrinks as the DPI
factor rises, so a fixed-size card takes a larger share of a smaller canvas and
fewer of them fit. That is the "cards look oversized at 120%" report.

Qt stylesheets have no relative units. There is no em, rem, or vw to reach for,
so the equivalent is to route every hand-chosen dimension through one factor
and recompute when it changes. That is what this module is.

Anything sized in pixels by hand should be written ``scaled(N)`` rather than
``N``. Fonts are handled separately by ThemeManager, which multiplies its type
scale by the same factor, so text and geometry move together.
"""

from __future__ import annotations


# CHANGE [BUG2]: the choices offered in Settings, and the default.
GUI_SCALE_CHOICES = (0.75, 1.00, 1.25, 1.50)
DEFAULT_GUI_SCALE = 1.00

_MINIMUM = min(GUI_SCALE_CHOICES)
_MAXIMUM = max(GUI_SCALE_CHOICES)

_current_scale = DEFAULT_GUI_SCALE


def clamp_gui_scale(value: object) -> float:
    """Bound a scale to the supported range, falling back to the default."""
    try:
        scale = float(value)
    except (TypeError, ValueError):
        return DEFAULT_GUI_SCALE
    if scale <= 0:
        return DEFAULT_GUI_SCALE
    return max(_MINIMUM, min(_MAXIMUM, scale))


def set_gui_scale(value: object) -> float:
    """Set the factor every scaled dimension is multiplied by."""
    global _current_scale
    _current_scale = clamp_gui_scale(value)
    return _current_scale


def gui_scale() -> float:
    return _current_scale


def scaled(value: float) -> int:
    """A hand-chosen pixel dimension, adjusted for the current GUI scale.

    Rounded to whole pixels because Qt geometry is integral, and floored at 1
    so a scaled-down border or divider never disappears entirely.
    """
    result = round(float(value) * _current_scale)
    if value > 0 and result < 1:
        return 1
    return int(result)


def scaled_spacing(space: dict, name: str) -> int:
    """Convenience for the token spacing scale."""
    return scaled(space[name])
