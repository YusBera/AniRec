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
    QRect,
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

from .contribution_visuals import (
    SemanticContribution,
    contribution_colour,
    contribution_summary,
    proportional_segment_widths,
    semantic_contributions,
    snap_pixel,
    snapped_segment_edges,
)
from .scaling import scaled


def _application_colour(property_name: str, fallback: str) -> QColor:
    application = QApplication.instance()
    value = application.property(property_name) if application is not None else None
    colour = QColor(str(value or fallback))
    return colour if colour.isValid() else QColor(fallback)


# How far a calibration mark is pushed away from whatever sits under it.
GRADUATION_MIX = 0.42


def relative_luminance(colour: QColor) -> float:
    return (
        0.2126 * colour.redF()
        + 0.7152 * colour.greenF()
        + 0.0722 * colour.blueF()
    )


def blend_opaque(base: QColor, toward: QColor, amount: float) -> QColor:
    """An opaque mix of two colours."""
    ratio = max(0.0, min(1.0, float(amount)))
    return QColor(
        round(base.red() + (toward.red() - base.red()) * ratio),
        round(base.green() + (toward.green() - base.green()) * ratio),
        round(base.blue() + (toward.blue() - base.blue()) * ratio),
    )


def calibration_mark(under: QColor, amount: float = GRADUATION_MIX) -> QColor:
    """A mark guaranteed to separate from the colour it is drawn on.

    A single fixed mark colour cannot work here. The rail is painted from a
    derived palette, so a contributor can land at any luminance, and a fixed
    mid-tone will sooner or later coincide with one - measured at 0.003
    contrast on the gradient theme, which is a mark that exists in the buffer
    and not on the glass. Pushing away from the local background instead
    keeps every mark legible whatever the palette does.
    """
    target = QColor(0, 0, 0) if relative_luminance(under) > 0.45 else QColor(255, 255, 255)
    return blend_opaque(under, target, amount)


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
    """Paint a score-length rail divided by its supplied contributors.

    The calibrated match determines total filled length. Positive raw terms
    divide that length proportionally; their exact values remain in the text
    rows and accessible description. Negative terms do not pretend to be
    positive width on this one-direction track.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("recommendationScoreTrack")
        self.setAccessibleName("Score contribution bar")
        self.setMinimumHeight(30)
        self.setMaximumHeight(34)
        self._contributions: tuple[tuple[str, float], ...] = ()
        self._semantic_contributions: tuple[SemanticContribution, ...] = ()
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

    def set_data(self, contributions, score: float, *, genres=(), studios=()) -> None:
        self._semantic_contributions = semantic_contributions(
            contributions, genres=genres, studios=studios
        )
        self._contributions = tuple(
            (item.name, item.value) for item in self._semantic_contributions
        )
        try:
            candidate = float(score)
        except (TypeError, ValueError):
            candidate = 0.0
        self._score = candidate if math.isfinite(candidate) else 0.0
        summary = contribution_summary(self._semantic_contributions)
        self.setToolTip(f"Score contributors: {summary}")
        self.setAccessibleDescription(summary)
        self._reveal = 1.0
        self.update()

    def animate(self) -> None:
        # CHANGE [NEVER-EMPTY]: this both ignored the machine's reduced-motion
        # setting - which every other reveal in the application honours - and
        # started from a literal zero, so the score bar in the inspector was
        # empty on its first painted frame. Same floor, same visibility guard,
        # same rule: an instrument nobody can see draws its finished value.
        from .profile_widgets import REVEAL_FLOOR, motion_enabled

        if not motion_enabled() or not self.isVisible():
            self._reveal = 1.0
            self.update()
            return
        self._animation.stop()
        self._animation.setStartValue(REVEAL_FLOOR)
        self._reveal = REVEAL_FLOOR
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
        rail_left = snap_pixel(rect.left())
        rail_top = snap_pixel(rect.top())
        rail_width = max(1, snap_pixel(rect.width()))
        rail_height = max(1, snap_pixel(rect.height()))
        rail_rect = QRect(rail_left, rail_top, rail_width, rail_height)

        well = _application_colour("resolvedWell", "#06100C")
        border = _application_colour("resolvedBorder", "#23372C")
        accent = _application_colour("resolvedAccent", "#C6A15B")
        signal = _application_colour("resolvedSignal", "#6FC6C0")
        text = _application_colour("resolvedText", "#E9E5D6")
        neutral = _application_colour("resolvedTextSubtle", "#7C8C80")
        painter.fillRect(rail_rect, well)

        available = rail_width
        positive = tuple(
            item for item in self._semantic_contributions if item.value > 0
        )
        filled = snap_pixel(
            available
            * max(0.0, min(self._score, 100.0))
            / 100.0
            * self._reveal
        )
        if not positive and self._score > 0:
            painter.fillRect(
                QRect(rail_left, rail_top, filled, rail_height), accent
            )

        widths = proportional_segment_widths(positive, filled)
        edges = snapped_segment_edges(widths, start=rail_left)
        for index, item in enumerate(positive):
            segment_left = edges[index]
            segment_right = edges[index + 1]
            width = segment_right - segment_left
            if width <= 0:
                continue
            colour = contribution_colour(
                item,
                genre=signal,
                studio=accent,
                community=neutral,
                other=neutral.darker(112),
            )
            painter.fillRect(
                QRect(segment_left, rail_top, width, rail_height), colour
            )

        # CHANGE [GRID]: the mark was the border colour at alpha 185, which
        # gave it no guaranteed relationship to whatever it lands on. Measured
        # across the four themes at a 63% fill, marks past the fill point fell
        # to 0.045 contrast in light and 0.028 in gradient - present in the
        # buffer, invisible on the glass, so the scale appeared to stop
        # partway along the rail. A fixed mid-tone was no better: it collided
        # with a derived contributor colour on the gradient theme at 0.003.
        #
        # Each mark is therefore derived from the pixel under it.
        def colour_under(x: int) -> QColor:
            if x >= rail_left + filled:
                return well
            for index, item in enumerate(positive):
                if edges[index] <= x < edges[index + 1]:
                    return contribution_colour(
                        item,
                        genre=signal,
                        studio=accent,
                        community=neutral,
                        other=neutral.darker(112),
                    )
            return accent

        # Contributor edges are already visible as colour transitions. Keep
        # all actual strokes on the one regular ten-percent calibration grid.
        divider_positions = {
            rail_left + snap_pixel(rail_width * index / 10)
            for index in range(1, 10)
        }
        for x_tick in sorted(divider_positions):
            painter.setPen(QPen(calibration_mark(colour_under(x_tick)), 1))
            painter.drawLine(
                x_tick,
                rail_top,
                x_tick,
                rail_top + rail_height - 1,
            )

        # The bright one-pixel hairline marks the final displayed score. Raw
        # contributor values remain exact in the adjacent text breakdown.
        score_x = min(
            rail_left + rail_width - 1,
            rail_left
            + snap_pixel(
                rail_width * max(0.0, min(self._score, 100.0)) / 100.0
            ),
        )
        score_marker = QColor(text)
        painter.setPen(QPen(score_marker, 1))
        painter.drawLine(
            score_x,
            rail_top,
            score_x,
            rail_top + rail_height - 1,
        )
        painter.setPen(QPen(border, 1))
        painter.drawRect(
            QRect(rail_left, rail_top, rail_width - 1, rail_height - 1)
        )
        painter.end()


# Lamp geometry: the lit core, and the box that holds it plus its halo.
LAMP_CORE = 8
LAMP_BOX = 16

# Halo rings, from outermost to innermost. Alphas fall steeply so the
# bloom reads as light rather than as a coloured border.
#
# CHANGE [BLOOM]: the outer ring was 58 on a 16px box - a halo wider than the
# lamp's own widget, clipped square by it, and the loudest thing in a 238px
# rail. A status light reporting a healthy channel should not look like an
# alarm. Halved, so the bloom sits inside the box it is drawn in.
GLOW_RINGS = (16, 30, 28)


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
        # The lamp fills its own box with the colour behind it and declares
        # itself opaque.  A translucent widget makes Qt repaint every ancestor
        # underneath it, so the 120ms flicker on two lit lamps measured as 8
        # full-window repaints a second at idle, and a busy pulse as 62.  The
        # box is 16px and the halo is clipped to it either way, so filling it
        # costs nothing visually and takes the ancestor repaints to zero.
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self._flicker = 1.0
        self.set_state(state)

    # ---- shared flicker driver -------------------------------------------
    #
    # The flicker is a random walk rather than a curve, so it is a timer and
    # not an animation.  It used to be a timer *per lamp*: four lamps meant
    # four wakeups delivering four independent repaints.  One driver ticks
    # every lit lamp together, and skips lamps nobody can see - a backgrounded
    # window now costs nothing at all rather than 8 repaints a second.

    _flicker_driver: QTimer | None = None
    _flicker_members: "weakref.WeakSet[StatusLight]" = weakref.WeakSet()

    @classmethod
    def _driver(cls) -> QTimer:
        if cls._flicker_driver is None:
            timer = QTimer()
            timer.setInterval(cls.FLICKER_MS)
            # Coarse: the tick is a brightness wander, not a deadline, and a
            # precise timer would keep the CPU out of its idle states.
            timer.setTimerType(Qt.TimerType.CoarseTimer)
            timer.timeout.connect(cls._tick_flicker)
            cls._flicker_driver = timer
        return cls._flicker_driver

    @classmethod
    def _tick_flicker(cls) -> None:
        live = 0
        for lamp in list(cls._flicker_members):
            try:
                if lamp.state == "off":
                    continue
                live += 1
                # Off-screen, on an inactive page, or in a window the user is
                # not looking at: still lit, just not worth a repaint.
                if not lamp.isVisible() or not lamp.window().isActiveWindow():
                    continue
                lamp._flicker = 1.0 - random.random() * cls.FLICKER_DEPTH
                lamp.update()
            except RuntimeError:
                # The C++ side went away between ticks.
                cls._flicker_members.discard(lamp)
        if live == 0:
            cls._driver().stop()

    def _join_flicker(self) -> None:
        StatusLight._flicker_members.add(self)
        driver = StatusLight._driver()
        if not driver.isActive():
            driver.start()

    def _leave_flicker(self) -> None:
        StatusLight._flicker_members.discard(self)
        self._flicker = 1.0

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
            self._leave_flicker()
        else:
            self._join_flicker()
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
        # Declared opaque in __init__, so this fill is now the widget's own
        # ground rather than something the ancestors have to supply.
        painter.fillRect(full, _application_colour("resolvedSidebar", "#050907"))
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

    def _scanned_region(self, damaged: QRect | None = None) -> QRegion:
        """Everything this overlay covers, less the widgets that opted out.

        ``visibleRegion`` rather than ``geometry``: a cover scrolled half out
        of the feed viewport is clipped by it, and subtracting the whole
        widget rectangle would punch a hole through the chrome above the
        viewport where nothing is showing.

        ``damaged`` is the rectangle Qt actually asked for.  Scoping to it
        matters because this walks every exempted cover on the page: a 16px
        lamp repainting in the rail used to cost a full pass over the feed's
        artwork, sixty times a second while a lamp pulsed.
        """
        region = QRegion(self.rect() if damaged is None else damaged)
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
                translated = visible.translated(offset)
                # Nothing to subtract if the exempted widget is nowhere near
                # the damage.
                if damaged is not None and not translated.intersects(damaged):
                    continue
                region -= translated
            except RuntimeError:
                # The widget went away between the weak set and here.
                continue
        return region

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        damaged = event.rect()
        painter.setClipRegion(self._scanned_region(damaged))
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
        # Only the damaged band, in device rows. The raster is absolute - row
        # zero is always a line - so the start is floored onto the pitch grid
        # rather than onto the damage, and a partial repaint lands on exactly
        # the same lines a full one would.
        left = int(damaged.left() * ratio)
        width = int(damaged.width() * ratio) + 2
        first = int(damaged.top() * ratio) // pitch * pitch
        last = int(damaged.bottom() * ratio) + 1
        for y in range(first, last, pitch):
            painter.fillRect(left, y, width, thickness, ink)
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

    def _band_rect(self, position: float) -> QRect:
        """The rows the band occupies at ``position``."""
        band = max(6.0, self.height() * self.BAND)
        travel = self.height() + band
        bottom = position * travel
        top = bottom - band
        # A row of slack each side for the leading edge line and rounding.
        return QRect(0, int(top) - 2, self.width(), int(band) + 5)

    def _on_value(self, value) -> None:
        previous = self._position
        self._position = max(0.0, min(1.0, float(value)))
        # Only the rows the band just left and the rows it just entered.
        #
        # This used to be a bare ``update()``, which invalidates the whole
        # widget - and the widget is the whole viewport, so every frame
        # recomposited the entire feed behind it. That measured at 31-38ms a
        # frame no matter how tall the band was, which is the tell: the cost
        # was never the band, it was the invalidation.
        self.update(self._band_rect(previous).united(self._band_rect(self._position)))

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


class NavMarker(QWidget):
    """The rail's selection mark, as one object that travels between rows.

    The mark used to be ``border-left-color`` on whichever nav button was
    checked, so selection teleported: the old row lost its rail and the new
    one gained it in the same frame, with nothing connecting them.  Moving one
    mark between the rows says the same thing and also says which way you
    went, which is the part a jump cut throws away.

    Timing is linear and short, like ``ScanSweep``.  A carriage travelling to
    a stop runs at a constant rate; easing would read as phone-app motion, and
    this is chrome on an instrument.

    The widget is opaque and exactly the width of the mark, so travelling it
    never forces a repaint of anything except the narrow column it moves in.
    """

    DURATION_MS = 150
    WIDTH = 3

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("navMarker")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._top = 0.0
        self._height = 0.0
        self._from = (0.0, 0.0)
        self._to = (0.0, 0.0)
        self._placed = False
        self._target: "weakref.ReferenceType[QWidget] | None" = None
        # A single scalar, lerped in the handler.  QVariantAnimation cannot
        # interpolate a Python tuple - it emits the start value and then the
        # end value, and the mark does not move at all.
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(self.DURATION_MS)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QEasingCurve.Type.Linear)
        self._animation.valueChanged.connect(self._on_value)
        if parent is not None:
            parent.installEventFilter(self)
        self.hide()

    def eventFilter(self, watched, event) -> bool:
        # The rail lays out after the mark is built, so the first target
        # geometry is a placeholder.  Re-sync whenever the rail changes shape
        # - that also covers a font-scale change moving every row.
        if watched is self.parentWidget() and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.LayoutRequest,
        ):
            self._resync()
        return super().eventFilter(watched, event)

    def _resync(self) -> None:
        target = self._target() if self._target is not None else None
        if target is None:
            return
        try:
            self._settle(target)
        except RuntimeError:
            self._target = None

    def _settle(self, target: QWidget) -> None:
        """Place the mark on ``target`` with no travel."""
        parent = self.parentWidget()
        if parent is None:
            return
        top = float(target.mapTo(parent, QPoint(0, 0)).y())
        height = float(target.height())
        if (top, height) == (self._top, self._height):
            return
        self._animation.stop()
        self._apply(top, height)

    def _on_value(self, value) -> None:
        try:
            progress = float(value)
        except (TypeError, ValueError):
            return
        top = self._from[0] + (self._to[0] - self._from[0]) * progress
        height = self._from[1] + (self._to[1] - self._from[1]) * progress
        self._apply(top, height)

    def _apply(self, top: float, height: float) -> None:
        self._top = top
        self._height = height
        self.setGeometry(
            0, int(round(top)), scaled(self.WIDTH), max(1, int(round(height)))
        )
        self.update()

    def move_to(self, target: QWidget, animate: bool = True) -> None:
        """Travel to sit against ``target``'s left edge.

        The first placement of a session is not a movement - there is no
        previous selection for the mark to have come from - so it is placed
        without animating.
        """
        parent = self.parentWidget()
        if parent is None or target is None:
            return
        self._target = weakref.ref(target)
        top = float(target.mapTo(parent, QPoint(0, 0)).y())
        height = float(target.height())
        self._animation.stop()
        if not animate or not self._placed:
            self._apply(top, height)
            self._placed = True
            self.show()
            self.raise_()
            return
        if (top, height) == (self._top, self._height):
            return
        self._from = (self._top, self._height)
        self._to = (top, height)
        self.show()
        self.raise_()
        self._animation.start()

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        # Opaque: the rail's ground first, then the mark, so the widget owes
        # its ancestors nothing on repaint.
        painter.fillRect(self.rect(), _application_colour("resolvedSidebar", "#050907"))
        painter.fillRect(self.rect(), _application_colour("resolvedAccent", "#C6A15B"))
        painter.end()


class ChannelWipe(QWidget):
    """A short bright segment that runs the width of the page once, on change.

    The page transition this replaces was an opacity fade over the whole
    surface.  It measured at five to seven frames - the effect re-renders the
    entire page into an offscreen buffer every frame, and on the card feed
    that costs 26-54ms each - so the fade read as a stutter rather than as a
    transition, which is worse than the jump cut it was meant to soften.

    This is the same information carried by a bounded, opaque strip: two
    device pixels tall, its own ground painted, so nothing underneath it is
    ever recomposited.  It measures at roughly 60fps for the same reason the
    rail mark does.

    A tuning head crossing a channel, and it stops when it gets there.
    """

    DURATION_MS = 190
    THICKNESS = 2

    # Segment width as a fraction of the strip.
    SEGMENT = 0.22

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("channelWipe")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._position = 0.0
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(self.DURATION_MS)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QEasingCurve.Type.Linear)
        self._animation.valueChanged.connect(self._on_value)
        self._animation.finished.connect(self.hide)
        self.hide()

    @property
    def animation(self) -> QVariantAnimation:
        """The travel itself, for callers that need to observe or await it."""
        return self._animation

    def _on_value(self, value) -> None:
        try:
            self._position = max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return
        self.update()

    def run(self) -> None:
        """One pass. A second request restarts rather than stacking."""
        parent = self.parentWidget()
        if parent is None or parent.width() <= 0:
            return
        self.setGeometry(0, 0, parent.width(), max(1, scaled(self.THICKNESS)))
        self._animation.stop()
        self._position = 0.0
        self.show()
        self.raise_()
        self._animation.start()

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        if self.width() <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        # Opaque ground first: this strip owes its ancestors no repaint.
        painter.fillRect(self.rect(), _application_colour("resolvedBackground", "#070C09"))

        segment = max(24.0, self.width() * self.SEGMENT)
        travel = self.width() + segment
        right = self._position * travel
        left = right - segment

        tint = _application_colour("resolvedAccent", "#C6A15B")
        # Bright at the leading edge, falling off behind it, so the segment
        # reads as travelling rather than as a block sliding.
        wash = QLinearGradient(left, 0.0, right, 0.0)
        for stop, alpha in ((0.0, 0), (0.55, 70), (1.0, 235)):
            colour = QColor(tint)
            colour.setAlpha(alpha)
            wash.setColorAt(stop, colour)
        painter.fillRect(QRectF(left, 0.0, segment, float(self.height())), wash)
        painter.end()
