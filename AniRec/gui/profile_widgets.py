"""The instruments the Profile surface reads its figures out on.

Presentation only, in the same way ``instrument_widgets`` is: everything here
takes a number that has already been decided and draws it. Nothing computes a
statistic, and nothing reinterprets one.

Four instruments cover the whole page, which is the point. A histogram bar, a
genre share, an era count and a season average are all "this much of that", so
they are all ``BarRail``; a proportion of a whole is a ``CellBank``; a position
between two named extremes is a ``PolarityScale``; a run of yearly averages is
a ``TimelinePlot``. Nine differently-shaped charts would have made the page a
dashboard, which is the one thing it must not be.

They are drawn the way the rest of the application draws: aliasing off, whole
pixels, wells and rails from the palette, calibration marks derived from
whatever pixel sits under them. No gradients on data, no drop shadows, no
rounded caps. The colour argument is the application's - brass is the reader,
aqua is everyone else - and no instrument here leans on colour alone: every
one of them is legible in monochrome from its length, its position or the
text beside it.
"""

from __future__ import annotations

import ctypes

from PySide6.QtCore import QEasingCurve, QEvent, QRect, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from .contribution_visuals import snap_pixel
from .design_tokens import SPACE
from .instrument_widgets import calibration_mark
from .scaling import scaled


def _application_colour(property_name: str, fallback: str) -> QColor:
    application = QApplication.instance()
    value = application.property(property_name) if application is not None else None
    colour = QColor(str(value or fallback))
    return colour if colour.isValid() else QColor(fallback)


# ---------------------------------------------------------------------------
# Motion
# ---------------------------------------------------------------------------

_ANIMATIONS_ALLOWED: bool | None = None

# SPI_GETCLIENTAREAANIMATION. Windows' "show animations in Windows" switch,
# which is what "prefers reduced motion" means on the platform this ships on.
_SPI_GETCLIENTAREAANIMATION = 0x1042


def motion_enabled() -> bool:
    """Whether this machine wants interface animation at all.

    Qt publishes no reduced-motion hint, so the platform switch is read
    directly, once, and cached. Anything that cannot be read is treated as
    "animation is fine": a reveal that plays when it should not is a smaller
    failure than a bar that never fills because a system call was refused.
    """
    global _ANIMATIONS_ALLOWED
    if _ANIMATIONS_ALLOWED is None:
        allowed = True
        try:
            enabled = ctypes.c_int(1)
            ok = ctypes.windll.user32.SystemParametersInfoW(  # type: ignore[attr-defined]
                _SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(enabled), 0
            )
            if ok:
                allowed = bool(enabled.value)
        except (AttributeError, OSError, ValueError):
            allowed = True
        _ANIMATIONS_ALLOWED = allowed
    return _ANIMATIONS_ALLOWED


# The reveal every instrument on the page shares, so nothing arrives out of
# step with the panel beside it. Matches ScoreTrack's curve; a little shorter,
# because several of these play at once when the page opens.
REVEAL_MILLISECONDS = 480

# CHANGE [NEVER-EMPTY]: the reveal used to start at exactly zero, so the first
# painted frame of the Rating Distribution was a grid with no bars in it -
# an entire chart that reads as broken, for as long as it takes anyone to
# glance at it or take a screenshot. It now starts a quarter of the way in.
# Nothing is misreported by this: the reveal scales each bar's own final
# length, so a count of zero still draws nothing and a count of 68 is simply
# short for a moment rather than absent.
REVEAL_FLOOR = 0.25


class _RevealingWidget(QWidget):
    """A painted widget whose value grows in from nothing once, on mount.

    Subclasses read ``self._reveal`` (0 to 1) and multiply their fill by it.
    On a machine that has asked for less motion the reveal is simply never
    below 1, so the same paint code draws the finished state immediately.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._reveal = 1.0
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(REVEAL_MILLISECONDS)
        self._animation.setStartValue(REVEAL_FLOOR)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._on_reveal)

    def _on_reveal(self, value) -> None:
        self._reveal = max(0.0, min(1.0, float(value)))
        self.update()

    def animate(self) -> None:
        # A reveal nobody can see is not a reveal, it is a clock running
        # against a hidden widget - which is how these landed on screen
        # already part-way through, or worse, at zero. Off-screen, the
        # finished state is the only honest thing to draw.
        if not motion_enabled() or not self.isVisible():
            self._reveal = 1.0
            self.update()
            return
        self._animation.stop()
        self._reveal = REVEAL_FLOOR
        self._animation.start()

    def event(self, event: QEvent) -> bool:
        if event.type() in {
            QEvent.Type.ApplicationPaletteChange,
            QEvent.Type.StyleChange,
        }:
            self.update()
        return super().event(event)


# ---------------------------------------------------------------------------
# Instruments
# ---------------------------------------------------------------------------

# A rail is this tall unless something asks otherwise. Deliberately short: the
# figure is the length, not the mass.
RAIL_HEIGHT = 10

# Ten graduations, the same grid ScoreTrack rules its rail with, so a bar on
# this page and the score bar on a card are read against the same scale.
GRADUATIONS = 10


class BarRail(_RevealingWidget):
    """One proportional bar in a well, ruled at tenths.

    Used for the rating histogram, genre share, era counts and season
    averages. The caller supplies a fraction of the row's own maximum; this
    does not know what the number means and does not label it - the value
    always sits in a mono label beside the rail, so the bar is a comparison
    aid and never the only place a figure appears.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        tone: str = "you",
        height: int = RAIL_HEIGHT,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("profileBarRail")
        self._fraction = 0.0
        self._tone = tone
        self._height = height
        self.setFixedHeight(scaled(height))
        self.setMinimumWidth(scaled(60))

    def set_fraction(self, fraction: float, *, tone: str | None = None) -> None:
        try:
            value = float(fraction)
        except (TypeError, ValueError):
            value = 0.0
        self._fraction = max(0.0, min(1.0, value))
        if tone is not None:
            self._tone = tone
        self.update()

    def apply_scale(self) -> None:
        self.setFixedHeight(scaled(self._height))

    def _fill_colour(self) -> QColor:
        if self._tone == "community":
            return _application_colour("resolvedSignal", "#5FBFB5")
        if self._tone == "quiet":
            return _application_colour("resolvedTextSubtle", "#748676")
        return _application_colour("resolvedAccent", "#D9A441")

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        rect = QRectF(self.rect())
        left = snap_pixel(rect.left())
        top = snap_pixel(rect.top())
        width = max(1, snap_pixel(rect.width()))
        height = max(1, snap_pixel(rect.height()))

        well = _application_colour("resolvedWell", "#040806")
        border = _application_colour("resolvedBorder", "#1E2E24")
        painter.fillRect(QRect(left, top, width, height), well)

        filled = snap_pixel(width * self._fraction * self._reveal)
        if filled > 0:
            painter.fillRect(
                QRect(left, top, filled, height), self._fill_colour()
            )

        # Marks derived from the pixel under them, for the reason ScoreTrack
        # gives: a fixed mid-tone vanishes on one theme or another.
        fill_colour = self._fill_colour()
        for index in range(1, GRADUATIONS):
            x_tick = left + snap_pixel(width * index / GRADUATIONS)
            under = fill_colour if x_tick < left + filled else well
            painter.setPen(QPen(calibration_mark(under), 1))
            painter.drawLine(x_tick, top, x_tick, top + height - 1)

        painter.setPen(QPen(border, 1))
        painter.drawRect(QRect(left, top, width - 1, height - 1))
        painter.end()


# A cell and the gap after it, matching the match badge's contribution rail so
# a segmented readout looks like the same machine wherever it appears.
CELL_PITCH = 7
CELL_GAP = 2
CELL_HEIGHT = 14


class CellBank(_RevealingWidget):
    """A proportion drawn as a bank of discrete cells, lit from the left.

    A percentage on this page is never a smooth ring. A ring is a dashboard
    borrowing from another product; a stepped bank is what an instrument does,
    and it also stops a reader over-reading a figure that is only accurate to
    a couple of points - you can count lit cells, and there are twenty of
    them, so the resolution the widget claims is the resolution it has.
    """

    CELLS = 20

    def __init__(self, parent: QWidget | None = None, *, tone: str = "you") -> None:
        super().__init__(parent)
        self.setObjectName("profileCellBank")
        self._fraction = 0.0
        self._tone = tone
        self.setFixedHeight(scaled(CELL_HEIGHT))
        self.setMinimumWidth(scaled(self.CELLS * CELL_PITCH))

    def set_fraction(self, fraction: float) -> None:
        try:
            value = float(fraction)
        except (TypeError, ValueError):
            value = 0.0
        self._fraction = max(0.0, min(1.0, value))
        self.update()

    def apply_scale(self) -> None:
        self.setFixedHeight(scaled(CELL_HEIGHT))
        self.setMinimumWidth(scaled(self.CELLS * CELL_PITCH))

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        lit = (
            _application_colour("resolvedSignal", "#5FBFB5")
            if self._tone == "community"
            else _application_colour("resolvedAccent", "#D9A441")
        )
        # An unlit cell has to be visibly a cell. The plain border colour sits
        # within a few points of the well on the paper theme, which left the
        # unused end of every bank as a blank strip rather than as twenty
        # cells waiting to light; the stronger line reads on both grounds.
        unlit = _application_colour("resolvedCoverMark", "#2E4636")
        well = _application_colour("resolvedWell", "#040806")

        width = max(1, self.width())
        height = max(1, self.height())
        pitch = max(2, width // self.CELLS)
        gap = max(1, scaled(CELL_GAP))
        cell_width = max(1, pitch - gap)

        # A reading of 3% must not render as an unlit bank. Nothing lit reads
        # as "no signal", which is a different statement from "a very small
        # one", and this widget is used for both drop rates and completion
        # rates where the small end is the interesting end.
        shown = self._fraction * self._reveal
        cells = 0 if shown <= 0 else max(1, int(round(shown * self.CELLS)))

        painter.fillRect(QRect(0, 0, width, height), well)
        for index in range(self.CELLS):
            left = index * pitch
            if left + cell_width > width:
                break
            painter.fillRect(
                QRect(left, 0, cell_width, height),
                lit if index < cells else unlit,
            )
        painter.end()


# How far the marker overhangs the rail it sits on, each side.
MARKER_OVERHANG = 3


class PolarityScale(_RevealingWidget):
    """A position between two named extremes, marked on a graduated rail.

    This is the widget for a figure that has no good end and no bad end -
    harsh against generous, obscure against mainstream. A bar would imply that
    more is better, which for these two is not a claim the application is in a
    position to make. The two names are drawn by the caller as labels at
    either end, so the meaning survives with the colour turned off.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("profilePolarityScale")
        self._position = 0.5
        self.setFixedHeight(scaled(CELL_HEIGHT))
        self.setMinimumWidth(scaled(80))

    def set_position(self, position: float) -> None:
        try:
            value = float(position)
        except (TypeError, ValueError):
            value = 0.5
        self._position = max(0.0, min(1.0, value))
        self.update()

    def apply_scale(self) -> None:
        self.setFixedHeight(scaled(CELL_HEIGHT))

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        width = max(2, self.width())
        height = max(2, self.height())
        well = _application_colour("resolvedWell", "#040806")
        border = _application_colour("resolvedBorder", "#1E2E24")
        accent = _application_colour("resolvedAccent", "#D9A441")

        rail_height = max(2, scaled(4))
        rail_top = (height - rail_height) // 2
        painter.fillRect(QRect(0, rail_top, width, rail_height), well)
        painter.setPen(QPen(border, 1))
        painter.drawRect(QRect(0, rail_top, width - 1, rail_height - 1))

        for index in range(1, GRADUATIONS):
            x_tick = snap_pixel(width * index / GRADUATIONS)
            painter.setPen(QPen(calibration_mark(well), 1))
            painter.drawLine(x_tick, rail_top, x_tick, rail_top + rail_height - 1)

        # The marker travels in from the middle rather than from zero: on a
        # two-ended scale the centre is the neutral reading, so growing out of
        # it is the only reveal that does not briefly assert one extreme.
        travelled = 0.5 + (self._position - 0.5) * self._reveal
        marker_x = snap_pixel(width * travelled)
        marker_width = max(2, scaled(3))
        marker_x = max(0, min(width - marker_width, marker_x - marker_width // 2))
        overhang = scaled(MARKER_OVERHANG)
        painter.fillRect(
            QRect(
                marker_x,
                max(0, rail_top - overhang),
                marker_width,
                min(height, rail_height + overhang * 2),
            ),
            accent,
        )
        painter.end()


class TimelinePlot(_RevealingWidget):
    """Mean score per year, drawn as a stepped trace on a ruled well.

    Stepped rather than curved: each year is one figure that held for that
    year, and a spline between them would draw scores that were never given.
    The axis labels are the caller's - they belong to the layout, so they
    scale with the rest of the type instead of being painted into the plot.
    """

    PLOT_HEIGHT = 96

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("profileTimelinePlot")
        self._points: tuple[tuple[int, float], ...] = ()
        self._bounds = (1.0, 10.0)
        self.setMinimumHeight(scaled(self.PLOT_HEIGHT))
        self.setMinimumWidth(scaled(220))

    def set_points(self, points, bounds) -> None:
        """``points`` is (year, average) pairs; years with no average drop out."""
        self._points = tuple(
            (int(year), float(average))
            for year, average in points
            if average is not None
        )
        low, high = bounds
        self._bounds = (float(low), float(high) if high > low else float(low) + 1.0)
        self.update()

    def apply_scale(self) -> None:
        self.setMinimumHeight(scaled(self.PLOT_HEIGHT))

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        width = max(2, self.width())
        height = max(2, self.height())
        well = _application_colour("resolvedWell", "#040806")
        border = _application_colour("resolvedBorder", "#1E2E24")
        accent = _application_colour("resolvedAccent", "#D9A441")
        painter.fillRect(QRect(0, 0, width, height), well)

        low, high = self._bounds
        span = max(0.001, high - low)

        # Four horizontal rules, so a rise of a tenth of a point is readable
        # as a rise of a tenth of a point rather than as a cliff.
        for index in range(1, 4):
            y_rule = snap_pixel(height * index / 4)
            painter.setPen(QPen(calibration_mark(well), 1))
            painter.drawLine(0, y_rule, width - 1, y_rule)

        if len(self._points) < 2:
            painter.setPen(QPen(border, 1))
            painter.drawRect(QRect(0, 0, width - 1, height - 1))
            painter.end()
            return

        columns = len(self._points)
        column_width = width / columns
        shown = max(1, int(round(columns * self._reveal)))

        painter.setPen(QPen(accent, max(1, scaled(2))))
        previous: tuple[int, int] | None = None
        for index, (_year, average) in enumerate(self._points[:shown]):
            centre = snap_pixel(column_width * (index + 0.5))
            y_value = snap_pixel(
                height - 1 - (max(0.0, min(1.0, (average - low) / span)) * (height - 2))
            )
            if previous is not None:
                # Step across, then step to the new level: the value held all
                # year, and only changed between years.
                painter.drawLine(previous[0], previous[1], centre, previous[1])
                painter.drawLine(centre, previous[1], centre, y_value)
            previous = (centre, y_value)
            marker = max(2, scaled(3))
            painter.fillRect(
                QRect(centre - marker // 2, y_value - marker // 2, marker, marker),
                accent,
            )
        if previous is not None:
            painter.drawLine(previous[0], previous[1], width - 1, previous[1])

        painter.setPen(QPen(border, 1))
        painter.drawRect(QRect(0, 0, width - 1, height - 1))
        painter.end()


class SkeletonBlock(QWidget):
    """An unlit stand-in, the size of the content that has not arrived.

    Not a shimmer. A shimmering grey pill is a web loading convention and it
    would be the only animated decoration in the application; an instrument
    that has no signal yet shows its wells empty, which is both quieter and
    honest about what it is. Rows are drawn at the pitch the real section uses
    so the panel does not resize when the figures land.
    """

    def __init__(
        self, rows: int = 3, parent: QWidget | None = None, *, row_height: int = 18
    ) -> None:
        super().__init__(parent)
        self.setObjectName("profileSkeleton")
        self._rows = max(1, int(rows))
        self._row_height = int(row_height)
        self.setAccessibleName("Loading")
        self.setMinimumHeight(scaled(self._rows * (self._row_height + SPACE["sm"])))

    def apply_scale(self) -> None:
        self.setMinimumHeight(scaled(self._rows * (self._row_height + SPACE["sm"])))

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        well = _application_colour("resolvedWell", "#040806")
        border = _application_colour("resolvedBorder", "#1E2E24")
        row_height = scaled(self._row_height)
        pitch = row_height + scaled(SPACE["sm"])
        width = max(2, self.width())
        for index in range(self._rows):
            top = index * pitch
            if top + row_height > self.height():
                break
            # Rows step in from the right so the block reads as a list waiting
            # to be filled rather than as a solid slab.
            row_width = max(scaled(40), int(width * (1.0 - 0.08 * (index % 3))))
            painter.fillRect(QRect(0, top, row_width, row_height), well)
            painter.setPen(QPen(border, 1))
            painter.drawRect(QRect(0, top, row_width - 1, row_height - 1))
        painter.end()


class ReadoutPair(QWidget):
    """A caption over a value, the pairing the navigation rail already uses.

    The whole page is built from these. Keeping them one widget means the
    caption and the figure cannot drift apart in spacing from section to
    section, and it gives every figure on the page one accessible name that
    carries its caption with it.
    """

    def __init__(
        self,
        caption: str,
        value: str = "N/A",
        parent: QWidget | None = None,
        *,
        tone: str = "",
        size: str = "md",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("profileReadout")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.caption_label = QLabel(caption)
        self.caption_label.setObjectName("profileReadoutKey")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("profileReadoutValue")
        self.value_label.setProperty("readoutSize", size)
        if tone:
            self.value_label.setProperty("tone", tone)
        layout.addWidget(self.caption_label)
        layout.addWidget(self.value_label)
        self._caption = caption
        self._apply_accessible(value)

    def set_value(self, value: str, *, tone: str | None = None) -> None:
        self.value_label.setText(value)
        if tone is not None:
            self.value_label.setProperty("tone", tone)
            self.value_label.style().unpolish(self.value_label)
            self.value_label.style().polish(self.value_label)
        self._apply_accessible(value)

    def _apply_accessible(self, value: str) -> None:
        # One string, not two labels a screen reader has to associate itself.
        self.setAccessibleName(f"{self._caption.title()}: {value}")
