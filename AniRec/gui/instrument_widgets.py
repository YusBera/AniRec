"""Small painted widgets that give AniRec's panels physical instrument character.

These are deliberately presentation-only.  They consume colours published by
``ThemeManager`` and values already present in the recommendation view model;
they do not calculate or reinterpret recommendation scores.
"""

from __future__ import annotations

import math
import random
import weakref

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPoint,
    QPointF,
    QRectF,
    Qt,
    QTimer,
    QVariantAnimation,
)
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPaintEvent,
    QPen,
    QRadialGradient,
    QRegion,
)
from PySide6.QtWidgets import QApplication, QFrame, QSlider, QWidget

from .scaling import scaled


def _application_colour(property_name: str, fallback: str) -> QColor:
    application = QApplication.instance()
    value = application.property(property_name) if application is not None else None
    colour = QColor(str(value or fallback))
    return colour if colour.isValid() else QColor(fallback)


class InstrumentPanel(QFrame):
    """A normal styled frame with restrained scanlines and calibration ticks."""

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        scanline = _application_colour("resolvedTextSubtle", "#7C8C80")
        scanline.setAlpha(11)
        painter.setPen(QPen(scanline, 1))
        for y in range(3, self.height(), 4):
            painter.drawLine(1, y, max(1, self.width() - 2), y)

        tick = _application_colour("resolvedBorder", "#23372C")
        tick.setAlpha(150)
        painter.setPen(QPen(tick, 1))
        for x in range(12, self.width() - 8, 18):
            painter.drawLine(x, 0, x, 3)
        painter.end()


class SteppedSlider(QSlider):
    """A discrete brass calibration rail with visible one-step graduations."""

    def __init__(
        self,
        orientation: Qt.Orientation = Qt.Orientation.Horizontal,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(orientation, parent)
        self.setProperty("technicalSlider", True)
        self.setSingleStep(1)
        self.setPageStep(1)
        self.setTickInterval(1)
        self.setTickPosition(QSlider.TickPosition.NoTicks)
        self.setMinimumHeight(30)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        super().paintEvent(event)
        if self.orientation() is not Qt.Orientation.Horizontal:
            return

        steps = self.maximum() - self.minimum()
        if steps <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        accent = _application_colour("resolvedAccent", "#C6A15B")
        border = _application_colour("resolvedBorder", "#23372C")
        left = 8
        right = max(left + 1, self.width() - 8)
        centre = self.height() // 2
        for offset in range(steps + 1):
            x = round(left + (right - left) * offset / steps)
            step_value = self.minimum() + offset
            colour = accent if step_value <= self.value() else border
            painter.setPen(QPen(colour, 1))
            tick_height = 12 if offset in {0, steps} else 8
            painter.drawLine(x, centre - tick_height // 2, x, centre + tick_height // 2)
        painter.end()


class ScoreTrack(QWidget):
    """Paint a score as the sum of its supplied contribution values.

    Segment widths use the values exactly as supplied: ``16.5`` occupies 16.5%
    of the available 0-100 rail.  Negative values remain visible in the text
    rows but do not pretend to be positive width on this one-direction track.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("recommendationScoreTrack")
        self.setAccessibleName("Score contribution bar")
        self.setMinimumHeight(30)
        self.setMaximumHeight(34)
        self._contributions: tuple[tuple[str, float], ...] = ()
        self._score = 0.0
        self._reveal = 1.0
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(620)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._set_reveal)

    @property
    def contributions(self) -> tuple[tuple[str, float], ...]:
        return self._contributions

    def set_data(self, contributions, score: float) -> None:
        cleaned = []
        for name, value in contributions or ():
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(number):
                cleaned.append((str(name), number))
        self._contributions = tuple(cleaned)
        try:
            candidate = float(score)
        except (TypeError, ValueError):
            candidate = 0.0
        self._score = candidate if math.isfinite(candidate) else 0.0
        self._reveal = 1.0
        self.update()

    def animate(self) -> None:
        self._animation.stop()
        self._reveal = 0.0
        self._animation.start()

    def _set_reveal(self, value) -> None:
        self._reveal = max(0.0, min(1.0, float(value)))
        self.update()

    def event(self, event: QEvent) -> bool:
        if event.type() in {QEvent.Type.ApplicationPaletteChange, QEvent.Type.StyleChange}:
            self.update()
        return super().event(event)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)

        well = _application_colour("resolvedWell", "#06100C")
        border = _application_colour("resolvedBorder", "#23372C")
        accent = _application_colour("resolvedAccent", "#C6A15B")
        signal = _application_colour("resolvedSignal", "#6FC6C0")
        painter.fillRect(rect, well)

        contributions = self._contributions
        if not contributions and self._score > 0:
            contributions = (("Personal match", self._score),)

        x = rect.left()
        available = rect.width()
        for index, (name, value) in enumerate(contributions):
            if value <= 0 or x >= rect.right():
                continue
            width = available * min(value, 100.0) / 100.0 * self._reveal
            width = min(width, rect.right() - x)
            lowered = name.casefold()
            if "community" in lowered or "viewer" in lowered:
                colour = QColor(signal)
            else:
                colour = QColor(accent).darker(100 + min(index, 3) * 12)
            painter.fillRect(QRectF(x, rect.top(), width, rect.height()), colour)
            x += width

        tick = QColor(border)
        tick.setAlpha(185)
        painter.setPen(QPen(tick, 1))
        for index in range(11):
            x_tick = rect.left() + rect.width() * index / 10
            painter.drawLine(int(x_tick), int(rect.top()), int(x_tick), int(rect.bottom()))

        # The rail is a contribution sum; this hairline is the final displayed
        # score.  They normally coincide.  If the service sends a calibrated
        # score that does not reconcile with the raw contributors, the UI is
        # honest about that difference instead of stretching a segment.
        score_x = rect.left() + rect.width() * max(0.0, min(self._score, 100.0)) / 100.0
        score_marker = QColor(signal).lighter(118)
        painter.fillRect(QRectF(score_x - 1, rect.top(), 2, rect.height()), score_marker)
        painter.drawRect(rect)
        painter.end()


# Lamp geometry: the lit core, and the box that holds it plus its halo.
LAMP_CORE = 8
LAMP_BOX = 16

# Halo rings, from outermost to innermost. Alphas fall steeply so the
# bloom reads as light rather than as a coloured border.
GLOW_RINGS = (16, 30, 58)


class StatusLight(QWidget):
    """A small round indicator lamp reporting one piece of real state.

    CHANGE [GLASS]: round, and built like a lens rather than drawn like a
    swatch. The argument for a square was that the panel is made of
    rectangles and a round LED is the modern dashboard idiom - but the
    equipment this is imitating had physical indicator lamps pressed into the
    fascia, and those were turned, not milled. A circle here is the same
    reasoning the radio indicators and the slider knob already use: the shape
    says what the part is.

    Four passes make the glass. An outer bloom of falling alpha for the halo
    the phosphor throws; a dark bezel ring, which is the hole in the fascia; a
    radial body lit from the same offset every time, so the lamps on a panel
    all catch the light from one direction; and a small specular highlight up
    and left of centre, which is the only thing that actually reads as glass.

    Every lit lamp flickers - a shallow, irregular wander in brightness, not a
    blink. Mains ripple on an incandescent indicator, and the thing that makes
    a panel look powered rather than painted. ``busy`` still swings much
    further, so activity stays distinguishable from merely being on.
    """

    STATES = ("off", "ok", "warn", "busy", "error")

    # One breath per cycle. Slow enough to be calm in peripheral vision
    # during a long session, quick enough to read as activity.
    PULSE_MS = 900

    # The idle flicker. Shallow enough that you notice it only when you stop
    # looking at it, and stepped at a rate that does not read as an animation.
    FLICKER_MS = 120
    FLICKER_DEPTH = 0.07

    # Where the lamp is lit from, as a fraction of its radius, and how big the
    # specular dot is. One direction for every lamp on the panel.
    LIGHT_FROM = (-0.32, -0.36)
    SPECULAR = 0.26

    def __init__(self, state: str = "off", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statusLight")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._state = "off"
        # Brightness is continuous, not a two-frame toggle. A lamp warming and
        # dimming reads as alive; snapping between two states reads as a
        # blinking error indicator, which is the opposite of what a healthy
        # channel should look like.
        self._level = 1.0
        self._pulse = QVariantAnimation(self)
        self._pulse.setDuration(self.PULSE_MS)
        self._pulse.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._pulse.setStartValue(1.0)
        self._pulse.setEndValue(0.35)
        self._pulse.valueChanged.connect(self._on_level)
        self._pulse.finished.connect(self._reverse_pulse)
        # The widget is larger than the lamp so the bloom has somewhere to
        # go. The artifact draws this with `box-shadow: 0 0 4px`; QPainter has
        # no blur, so it is built from concentric rings of falling alpha,
        # which is also closer to how a real lamp haloes on a CRT.
        self.setFixedSize(scaled(LAMP_BOX), scaled(LAMP_BOX))
        # The idle flicker runs off its own timer rather than an animation:
        # it is a random walk, not a curve between two values, and a timer
        # that only ticks while the lamp is lit costs nothing when it is not.
        self._flicker = 1.0
        self._flicker_timer = QTimer(self)
        self._flicker_timer.setInterval(self.FLICKER_MS)
        self._flicker_timer.timeout.connect(self._on_flicker)
        self.set_state(state)

    def _on_flicker(self) -> None:
        """Wander the brightness a little, without ever going dark."""
        self._flicker = 1.0 - random.random() * self.FLICKER_DEPTH
        self.update()

    def set_state(self, state: str) -> None:
        state = str(state).casefold()
        if state not in self.STATES:
            state = "off"
        if state == self._state:
            return
        self._state = state
        if state == "busy":
            self._start_pulse()
        else:
            self._pulse.stop()
            self._level = 1.0
        if state == "off":
            self._flicker_timer.stop()
            self._flicker = 1.0
        elif not self._flicker_timer.isActive():
            self._flicker_timer.start()
        self.setAccessibleName(f"status {state}")
        self.update()

    @property
    def state(self) -> str:
        return self._state

    def apply_scale(self) -> None:
        self.setFixedSize(scaled(LAMP_BOX), scaled(LAMP_BOX))
        self.update()

    def _on_level(self, value) -> None:
        self._level = max(0.0, min(1.0, float(value)))
        self.update()

    def _start_pulse(self) -> None:
        self._pulse.stop()
        self._pulse.setStartValue(1.0)
        self._pulse.setEndValue(0.35)
        self._pulse.start()

    def _reverse_pulse(self) -> None:
        """Swing back the other way, so the lamp breathes continuously."""
        if self._state != "busy":
            return
        start = self._pulse.startValue()
        end = self._pulse.endValue()
        self._pulse.setStartValue(end)
        self._pulse.setEndValue(start)
        self._pulse.start()

    def flash(self) -> None:
        """A single bright swell, used when the value beside it changes."""
        if self._state == "busy":
            return
        self._pulse.stop()
        self._pulse.setStartValue(1.9)
        self._pulse.setEndValue(1.0)
        self._pulse.start()

    def _lamp_colour(self) -> QColor:
        if self._state == "ok":
            return _application_colour("resolvedSignal", "#6FC6C0")
        if self._state == "warn":
            return _application_colour("resolvedAccent", "#C6A15B")
        if self._state == "busy":
            return _application_colour("resolvedAccent", "#C6A15B")
        if self._state == "error":
            return QColor("#F0989A")
        return _application_colour("resolvedBorder", "#23372C")

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        # The one place antialiasing is wanted: a stair-stepped 8px circle
        # reads as a bug, not as period detail.
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)

        full = QRectF(self.rect())
        side = float(scaled(LAMP_CORE))
        lamp_rect = QRectF(
            full.center().x() - side / 2.0,
            full.center().y() - side / 2.0,
            side,
            side,
        )

        colour = self._lamp_colour()
        lit = self._state != "off"
        level = (self._level * self._flicker) if lit else 0.0

        if lit:
            # The bloom. Concentric discs of falling alpha rather than a blur,
            # which QPainter has no primitive for - and which is closer to how
            # a lamp haloes on a phosphor screen anyway.
            for ring, alpha in enumerate(GLOW_RINGS, start=1):
                halo = QColor(colour)
                halo.setAlpha(max(0, min(255, int(alpha * level))))
                spread = float(scaled(ring))
                painter.setBrush(halo)
                painter.drawEllipse(
                    lamp_rect.adjusted(-spread, -spread, spread, spread)
                )

        # The bezel: the lamp is seated in the fascia, not printed on it.
        bezel = _application_colour("resolvedWell", "#040806")
        painter.setBrush(bezel)
        painter.drawEllipse(lamp_rect)

        body = QColor(colour)
        if lit:
            body.setAlpha(max(70, min(255, int(255 * min(1.0, level)))))
        else:
            body.setAlpha(64)

        # Lit from one corner, falling to a darker rim: a sphere, not a disc.
        inner = lamp_rect.adjusted(0.8, 0.8, -0.8, -0.8)
        radius = inner.width() / 2.0
        focus = QPointF(
            inner.center().x() + radius * self.LIGHT_FROM[0],
            inner.center().y() + radius * self.LIGHT_FROM[1],
        )
        lens = QRadialGradient(inner.center(), radius, focus)
        hot = QColor(body)
        hot.setAlpha(min(255, int(body.alpha() * 1.0)))
        rim = QColor(body)
        rim.setAlpha(int(body.alpha() * 0.42))
        edge = QColor(body)
        edge.setAlpha(int(body.alpha() * 0.16))
        lens.setColorAt(0.0, hot)
        lens.setColorAt(0.62, rim)
        lens.setColorAt(1.0, edge)
        painter.setBrush(lens)
        painter.drawEllipse(inner)

        # The specular dot. Small, offset, and the same white every lamp gets,
        # because it is a reflection of the room and not of the lamp.
        if lit:
            gleam = QColor(255, 255, 255)
            gleam.setAlpha(int(150 * min(1.0, level)))
            dot = radius * self.SPECULAR
            painter.setBrush(gleam)
            painter.drawEllipse(
                QPointF(
                    inner.center().x() + radius * self.LIGHT_FROM[0],
                    inner.center().y() + radius * self.LIGHT_FROM[1],
                ),
                dot,
                dot,
            )

        # A hairline rim, so the glass has an edge against a dark panel.
        ring_colour = QColor(colour)
        ring_colour.setAlpha(int(190 * min(1.0, level)) if lit else 80)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(ring_colour, 1))
        painter.drawEllipse(lamp_rect.adjusted(0.5, 0.5, -0.5, -0.5))
        painter.end()


# Widgets the raster must not cross. A weak set, so a card being torn down
# takes its cover out of here with it and nothing has to remember to
# deregister.
_CRISP_WIDGETS: "weakref.WeakSet[QWidget]" = weakref.WeakSet()


def keep_crisp(widget: QWidget) -> None:
    """Exempt a widget from the scanline raster.

    Atmosphere is worth having over chrome and worth nothing over a
    photograph. Cover artwork is the one thing on the page the user is
    actually trying to look at, and laying a 1-in-3 dark line over it is
    subtracting detail from the content to decorate the frame around it.
    """
    _CRISP_WIDGETS.add(widget)


class Scanlines(QWidget):
    """A fixed raster laid over the whole shell.

    The one thing that says CRT before anything else is read. The artifact
    draws it as a repeating 1px line every 3px at 22% black with the whole
    layer at 55% opacity - about 10% effective. Anything heavier stops being
    a texture and starts being a filter over the artwork, which on a page
    that is mostly cover art is the difference between atmosphere and
    damage.

    Two things make this safe to lay over an entire application. It never
    takes input: ``WA_TransparentForMouseEvents`` is set, and there is a test
    for it, because an overlay that eats clicks would break every control
    underneath. And it never paints a background, only lines, so the widgets
    below are composited through it rather than being covered.

    It is a child of the shell rather than of the window, so it does not
    extend over native menus or dialogs - a dialog is a separate window and
    gets its own, if it wants one.
    """

    # Line every PITCH pixels, LINE of them dark.
    PITCH = 3
    LINE = 1

    # CHANGE [RASTER]: 26, not 56. The artifact stacks two opacities - a line
    # at 22% black inside a layer drawn at 55% - and 56 is the first of those
    # without the second, so the raster shipped at roughly twice the intended
    # weight and cover artwork went grey behind it. The arithmetic gives 31;
    # this sits a little under, because the app puts the raster over
    # photographic artwork where the page only ever put it over flat panels.
    INK_ALPHA = 26

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("scanlines")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        if parent is not None:
            parent.installEventFilter(self)
            self.setGeometry(parent.rect())
            self.raise_()

    def eventFilter(self, watched, event) -> bool:
        if watched is self.parentWidget():
            if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
                self.setGeometry(self.parentWidget().rect())
                self.raise_()
            elif event.type() == QEvent.Type.ChildAdded:
                # A page added after us would otherwise stack above the
                # raster and the effect would vanish on that surface only.
                self.raise_()
        return super().eventFilter(watched, event)

    def _scanned_region(self) -> QRegion:
        """Everything this overlay covers, less the widgets that opted out.

        ``visibleRegion`` rather than ``geometry``: a cover scrolled half out
        of the feed viewport is clipped by it, and subtracting the whole
        widget rectangle would punch a hole through the chrome above the
        viewport where nothing is showing.
        """
        region = QRegion(self.rect())
        parent = self.parentWidget()
        if parent is None:
            return region
        for widget in list(_CRISP_WIDGETS):
            try:
                if not widget.isVisible() or not parent.isAncestorOf(widget):
                    continue
                visible = widget.visibleRegion()
                if visible.isEmpty():
                    continue
                offset = widget.mapTo(parent, QPoint(0, 0))
                region -= visible.translated(offset)
            except RuntimeError:
                # The widget went away between the weak set and here.
                continue
        return region

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setClipRegion(self._scanned_region())
        ink = QColor(0, 0, 0, self.INK_ALPHA)

        # CHANGE [MOIRE]: the raster is laid out in device pixels, not logical
        # ones.
        #
        # At a 1.5x device pixel ratio a 3px logical pitch is 4.5 device
        # pixels, which cannot be drawn - so the lines landed with gaps of
        # 4, 1, 4, 4, 1 device rows, occasionally two of them adjacent. That
        # beat against the pixel grid and read as a coarse diagonal weave
        # rather than a fine scanline, which is most of why the effect looked
        # heavier than its alpha suggests. Rounding the pitch to a whole
        # number of device pixels makes every gap identical.
        ratio = self.devicePixelRatioF() or 1.0
        pitch = max(2, int(round(scaled(self.PITCH) * ratio)))
        # One device pixel, not one logical pixel scaled up: rounding 1x1.5
        # to 2 would darken half of every cycle instead of a quarter.
        thickness = max(1, scaled(self.LINE))
        painter.scale(1.0 / ratio, 1.0 / ratio)
        width = int(self.width() * ratio) + 1
        height = int(self.height() * ratio) + 1
        for y in range(0, height, pitch):
            painter.fillRect(0, y, width, thickness, ink)
        painter.end()


class ScanSweep(QWidget):
    """A single bright band that crosses the feed once when it reloads.

    A phosphor display refreshing, not a glitch effect. It runs once per load
    rather than looping, it is one widget painting one band rather than an
    effect applied per card, and it is transparent to the mouse throughout so
    it can never swallow a click on a recommendation underneath it.

    Timing is linear and short. Easing would read as modern motion design;
    a constant-rate sweep reads as a machine drawing a frame.
    """

    DURATION_MS = 520

    # Band height as a fraction of the swept area.
    BAND = 0.28

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("scanSweep")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.hide()

        self._position = 0.0
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(self.DURATION_MS)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QEasingCurve.Type.Linear)
        self._animation.valueChanged.connect(self._on_value)
        self._animation.finished.connect(self.hide)

    def sweep(self) -> None:
        """Run one pass. A second request restarts rather than stacking."""
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self._animation.stop()
        self._position = 0.0
        self.show()
        self.raise_()
        self._animation.start()

    def _on_value(self, value) -> None:
        self._position = max(0.0, min(1.0, float(value)))
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        if self.height() <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        band = max(6.0, self.height() * self.BAND)
        travel = self.height() + band
        bottom = self._position * travel
        top = bottom - band

        tint = _application_colour("resolvedAccent", "#C6A15B")
        # A continuous falloff rather than three hard steps. The stepped
        # version read as three stacked rectangles sliding down the feed
        # instead of one pass of light.
        wash = QLinearGradient(0.0, top, 0.0, bottom)
        for stop, alpha in ((0.0, 0), (0.45, 20), (0.82, 46), (1.0, 0)):
            colour = QColor(tint)
            colour.setAlpha(alpha)
            wash.setColorAt(stop, colour)
        painter.fillRect(QRectF(0, top, self.width(), band), wash)

        edge = QColor(tint)
        edge.setAlpha(90)
        painter.setPen(QPen(edge, 1))
        painter.drawLine(0, int(bottom), self.width(), int(bottom))
        painter.end()
