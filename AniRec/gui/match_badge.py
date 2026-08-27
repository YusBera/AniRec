"""The technical match readout drawn across the bottom of a card portrait.

Addresses: FEAT2 (per-anime match), BUG2 (it scales with the GUI scale).

A square telemetry plate replaces the old circular/pill language. A cell rail
carries the proportion and a mono readout carries the exact percentage, the
same pairing the scoring bench uses on the landing artifact.

The rail is a meter, not an icon: cells are lit from a continuous value, so
the final cell is partially lit and 91%, 92% and 95% are visibly different.
The previous ten-cell version rounded to the nearest tenth and drew all
three identically.

The score is the one the ranker already produces, so nothing is stubbed: it is
a real, explainable figure whose parts are listed in the card's breakdown. When
a learned model is added it becomes another term in the same blend, and this
keeps working unchanged.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QWidget

from .design_tokens import FONT_STACK_MONO
from .scaling import scaled


# Plate height at 100% GUI scale.
#
# CHANGE [VIGNETTE]: 38. It went to 44 to give an opaque black band room to
# fade over, and an opaque band is exactly what this should not be - it read
# as a slab laid across the bottom of every poster. The band is a vignette
# now and the readout carries its own ground, so the plate only has to be
# tall enough to hold the number and the rail.
BAR_HEIGHT = 38

# Inner padding, rail geometry and the cell rhythm of the proportion bar.
PLATE_PADDING = 7.0
# The readout's point size as a share of the plate height, so the number
# grows with the GUI scale without a second constant to keep in step.
READOUT_RATIO = 0.36

# The vignette's alpha ramp, top of the plate to bottom.
# CHANGE [VIGNETTE]: the old ramp reached full black at 34% of the plate and
# stayed there, which is a rectangle with a soft top edge - on a bright poster
# it read as a black bar taped across the artwork. This only reaches 60% black
# at the very bottom edge and is gone by a third of the way up.
SCRIM_RAMP = (
    (0.0, 0),
    (0.38, 18),
    (0.66, 70),
    (0.88, 128),
    (1.0, 153),
)

# How dark the ring immediately around each stroke goes, and how far it is
# thrown. The halo is what makes the vignette optional.
READOUT_HALO_ALPHA = 205
READOUT_HALO_SPREAD = 2

# The bloom is a blurred copy of the glyphs, not offset copies of them. Four
# translated draws at low alpha produced four legible ghosts rather than a
# glow - visible on the render as a doubled "93%". The blur is the same cheap
# scale-down-scale-up used for the cover backdrop.
READOUT_BLOOM_ALPHA = 132
READOUT_BLOOM_DIVISOR = 3
RAIL_HEIGHT = 4.0
# How much a hovered cell grows, and the share its neighbours take. The
# falloff is what makes dragging along the rail feel continuous instead
# of like stepping between separate buttons.
CELL_LIFT = 7.0
NEIGHBOUR_SHARE = 0.5
RAIL_GAP = 3.0
CELL_PITCH = 7
CELL_GAP = 2

# Resolved once so the plate follows the same stack as every other number
# in the interface instead of naming one family that may not be installed.
MONO_FAMILIES = [
    part.strip().strip('\"')
    for part in FONT_STACK_MONO.split(",")
]

# CHANGE [SCRIM]: both insets are gone. Six pixels of artwork showed under
# the plate and down each side of it, so the readout floated on a rectangle
# with a margin rather than sitting on the picture. The plate is the bottom
# edge of the portrait now; the cover's corner radius is 1px, so nothing
# meaningful overhangs.
BADGE_BOTTOM_INSET = 0

BAR_SIDE_INSET = 0

# Kept for callers that still import the old name.
BADGE_DIAMETER = BAR_HEIGHT


class MatchBadge(QWidget):
    """A compact, square-ended match telemetry plate."""

    def __init__(self, percentage: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("matchBadge")
        self._percentage = max(0.0, min(100.0, float(percentage)))
        self._track = QColor(0, 0, 0, 140)
        self._fill = QColor("#E0685A")
        self._signal = QColor("#6FC6C0")
        self._text = QColor("#FFFFFF")
        self._contributions: tuple[tuple[str, float], ...] = ()
        self._hover_cell = -1
        self._hover_strength = 0.0
        # Where the readout landed on the last paint, so a probe can check it
        # against the scrim ramp without reimplementing the arithmetic.
        self._readout_rect = QRectF()
        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(140)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover_value)
        self.setMouseTracking(True)
        self.setAccessibleName(
            f"{round(self._percentage)} percent match with your interests"
        )
        self.apply_scale()

    def apply_scale(self) -> None:
        """CHANGE [BUG2]: resize with the GUI scale, like everything else."""
        self.setFixedHeight(scaled(BAR_HEIGHT))
        self.update()

    def set_colours(
        self,
        track: QColor,
        fill: QColor,
        text: QColor,
        signal: QColor | None = None,
    ) -> None:
        """Follow the active theme rather than assuming one backdrop."""
        self._track = QColor(track)
        self._fill = QColor(fill)
        self._text = QColor(text)
        if signal is not None:
            self._signal = QColor(signal)
        self.update()

    def set_contributions(self, contributions) -> None:
        """Colour the rail by what actually produced the score.

        The detail view already splits a match into its parts; the rail on the
        card was a single flat colour saying only "this much". Given the same
        terms it can say which of them, in the same language: warm bands for
        the genres you rate highly, the signal colour for the community term
        that came from other people rather than from you.
        """
        cleaned = []
        for name, value in contributions or ():
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if number == number and number > 0:  # finite and positive
                cleaned.append((str(name), number))
        self._contributions = tuple(cleaned)
        self.update()

    # ---- hover -----------------------------------------------------------

    def _cell_geometry(self):
        """Left edge, width and count of the rail's cells."""
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        left = rect.left() + PLATE_PADDING
        width = max(1.0, (rect.right() - PLATE_PADDING) - left)
        step = float(scaled(CELL_PITCH))
        gap = float(max(1, scaled(CELL_GAP)))
        return left, width, step, max(1.0, step - gap)

    def _cell_at(self, x: float) -> int:
        left, width, step, _ = self._cell_geometry()
        if x < left or x > left + width:
            return -1
        return int((x - left) // step)

    def _on_hover_value(self, value) -> None:
        self._hover_strength = max(0.0, min(1.0, float(value)))
        self.update()

    def _animate_hover(self, target: float) -> None:
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_strength)
        self._hover_anim.setEndValue(float(target))
        self._hover_anim.start()

    def mouseMoveEvent(self, event) -> None:
        cell = self._cell_at(event.position().x())
        if cell != self._hover_cell:
            self._hover_cell = cell
            self.update()
        if cell >= 0 and self._hover_strength < 1.0:
            self._animate_hover(1.0)
        event.ignore()

    def leaveEvent(self, event) -> None:
        self._hover_cell = -1
        self._animate_hover(0.0)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        # The plate listens for hover only; clicks belong to the card.
        event.ignore()

    def _cell_colour(self, offset: float, width: float) -> QColor:
        """Which contribution owns the rail position at ``offset``."""
        if not self._contributions:
            return QColor(self._fill)
        position = offset / width * 100.0
        running = 0.0
        for index, (name, value) in enumerate(self._contributions):
            running += value
            if position <= running:
                lowered = name.casefold()
                if "community" in lowered or "viewer" in lowered:
                    return QColor(self._signal)
                shade = QColor(self._fill)
                return shade.darker(100 + min(index, 3) * 14)
        return QColor(self._fill)

    @property
    def percentage(self) -> float:
        return self._percentage

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        on_track = QColor(self._text)

        # CHANGE [SCRIM]: the fade now covers the whole plate, and it runs to
        # a vignette weighted to the bottom edge, and nothing more.
        #
        # This has been through both extremes. It began as a translucent slab
        # over the whole plate, became a scrim that reached full black across
        # the bottom two thirds - which fixed legibility by covering the
        # artwork with a bar - and is now a fade that tops out at 60% at the
        # very bottom edge. Legibility moved to where it belongs: onto the
        # digits, which carry their own halo, so this only has to seat the
        # plate against the bottom of the picture.
        # Filled over the full widget rect, not the half-pixel-inset rect
        # the rail strokes against: now that the plate is flush to the
        # artwork, insetting the fill left an unpainted seam of poster down
        # the left edge and along the top, which is exactly the empty space
        # the flush plate was meant to remove.
        plate = QRectF(self.rect())
        scrim = QLinearGradient(0.0, plate.top(), 0.0, plate.bottom())
        for stop, alpha in SCRIM_RAMP:
            colour = QColor(0, 0, 0)
            colour.setAlpha(alpha)
            scrim.setColorAt(stop, colour)
        painter.fillRect(plate, scrim)

        # CHANGE [READOUT]: the caption is gone. It spent more than half the
        # plate's width spelling out what the "%" beside it already says, on
        # a card that shows no other number.
        label = f"{round(self._percentage)}%"
        font = QFont(self.font())
        font.setFamilies(MONO_FAMILIES)
        font.setPointSizeF(max(6.0, rect.height() * READOUT_RATIO))
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        # CHANGE [SCRIM]: the readout was centred in everything above the
        # rail, which on the taller plate would float it up into the part of
        # the fade that is still transparent. It hangs off the rail instead,
        # so it stays inside the opaque band whatever the plate's height is.
        metrics = painter.fontMetrics()
        readout_height = metrics.height()
        # CHANGE [VIGNETTE]: sits down on the rail, the way a value sits on
        # its scale. Shortening the plate alone did not do this - it moved the
        # number relative to the plate and left it in the same place relative
        # to the artwork, 14px up from the bottom either way. The gap above
        # the rail is what actually held it there, so that is what went.
        readout_bottom = rect.bottom() - RAIL_HEIGHT - 1.0
        text_rect = QRectF(
            rect.left() + PLATE_PADDING,
            readout_bottom - readout_height,
            rect.width() - PLATE_PADDING * 2,
            readout_height,
        )
        # What the digits actually cover, not what the font box reserves. A
        # mono font's box is roughly twice the height of the glyphs in it, so
        # measuring legibility against the box would test a band of empty
        # space above the number as well as the number.
        ink = metrics.tightBoundingRect(label)
        baseline = text_rect.bottom() - metrics.descent()
        self._readout_rect = QRectF(
            text_rect.left(),
            baseline - ink.height(),
            text_rect.width(),
            float(ink.height()),
        )
        # CHANGE [VIGNETTE]: aligned to the bottom of its box, not centred in
        # it. A mono font's box carries roughly its own height again in
        # ascent and descent, so centring the box left the digits sitting in
        # the middle of the plate however far down the box was moved.
        alignment = int(
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight
        )
        # CHANGE [VIGNETTE]: the digits carry their own ground and their own
        # bloom, which is what lets the plate behind them stay a vignette.
        #
        # The halo is drawn first, offset in eight directions, so whatever the
        # artwork is doing there is a dark ring immediately around every
        # stroke. The bloom is the same glyph in the accent at low alpha,
        # thrown slightly wider - a phosphor dot spreading into the mask
        # rather than a drop shadow. The crisp glyph goes on last.
        halo = QColor(0, 0, 0)
        halo.setAlpha(READOUT_HALO_ALPHA)
        painter.setPen(QPen(halo))
        spread = max(1, scaled(READOUT_HALO_SPREAD))
        for dx, dy in (
            (-spread, 0), (spread, 0), (0, -spread), (0, spread),
            (-spread, -spread), (spread, -spread),
            (-spread, spread), (spread, spread),
        ):
            painter.drawText(text_rect.translated(dx, dy), alignment, label)

        # The bloom: the glyphs drawn once into a transparent layer, scaled
        # down and back up so they smear, then composited under the crisp
        # text. One bilinear pass each way, no convolution, and it reads as
        # light spreading in the mask rather than as a second number.
        layer = QPixmap(self.size())
        layer.fill(Qt.GlobalColor.transparent)
        scratch = QPainter(layer)
        scratch.setFont(font)
        scratch.setPen(QPen(self._fill))
        scratch.drawText(text_rect, alignment, label)
        scratch.end()
        divisor = max(2, READOUT_BLOOM_DIVISOR)
        smeared = layer.scaled(
            max(1, layer.width() // divisor),
            max(1, layer.height() // divisor),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ).scaled(
            layer.size(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.setOpacity(READOUT_BLOOM_ALPHA / 255.0)
        painter.drawPixmap(0, 0, smeared)
        painter.setOpacity(1.0)

        painter.setPen(QPen(self._fill))
        painter.drawText(text_rect, alignment, label)

        # CHANGE [RESOLUTION]: the rail used ten cells and lit
        # ``round(percentage / 10)`` of them, so 91%, 92% and 95% drew exactly
        # the same picture - a proportion display that could not show the
        # differences it existed to show.
        #
        # It is drawn the way the landing artifact draws it instead: one solid
        # fill at the true width, with a uniform grid of gaps punched across
        # the whole rail afterwards. The cells line up because they come from
        # one rhythm rather than being divided per segment, and the fill keeps
        # sub-cell precision.
        rail_left = rect.left() + PLATE_PADDING
        rail_right = rect.right() - PLATE_PADDING
        rail_width = max(1.0, rail_right - rail_left)
        # CHANGE [SCRIM]: measured from the bottom edge as before, but the
        # plate is flush to the artwork now, so this is the rail's real
        # distance from the bottom of the picture rather than from the top of
        # a six-pixel margin.
        rail_y = rect.bottom() - RAIL_HEIGHT - 4

        inactive = QColor(on_track)
        inactive.setAlpha(60)

        filled = rail_width * max(0.0, min(100.0, self._percentage)) / 100.0
        step = float(scaled(CELL_PITCH))
        gap = float(max(1, scaled(CELL_GAP)))
        cell_width = max(1.0, step - gap)

        # Each cell is drawn once, and the last lit one is lit only as far as
        # the value reaches into it. Overpainting gaps on top of a solid fill
        # was the obvious alternative, but the plate's track is deliberately
        # translucent so the artwork shows through, which would have left the
        # gaps tinted instead of clear.
        #
        # A hovered cell lifts, and its immediate neighbours lift by half, so
        # running the pointer along the rail reads as one continuous movement
        # rather than a row of separate switches.
        index = 0
        offset = 0.0
        while offset < rail_width - 0.5:
            width = min(cell_width, rail_width - offset)
            lift = 0.0
            if self._hover_cell >= 0 and self._hover_strength > 0.0:
                distance = abs(index - self._hover_cell)
                if distance == 0:
                    lift = CELL_LIFT
                elif distance == 1:
                    lift = CELL_LIFT * NEIGHBOUR_SHARE
                elif distance == 2:
                    lift = CELL_LIFT * NEIGHBOUR_SHARE * 0.4
                lift *= self._hover_strength

            height = RAIL_HEIGHT + lift
            top = rail_y + RAIL_HEIGHT - height  # grows upward from the baseline
            painter.fillRect(QRectF(rail_left + offset, top, width, height), inactive)

            lit = max(0.0, min(width, filled - offset))
            if lit > 0.0:
                colour = self._cell_colour(offset + lit / 2.0, rail_width)
                if lift > 0.0:
                    colour = colour.lighter(100 + int(28 * lift / CELL_LIFT))
                painter.fillRect(
                    QRectF(rail_left + offset, top, lit, height), colour
                )
            offset += step
            index += 1
        painter.end()


def should_show_badge(model) -> bool:
    """CHANGE [FEAT2]: no bar when there is no score to show.

    ``personal_match_available`` is False when the recommendation carried no
    match at all, which is different from a genuine score of zero.
    """
    if not getattr(model, "personal_match_available", False):
        return False
    return getattr(model, "personal_match", None) is not None
