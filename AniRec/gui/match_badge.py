"""The technical match readout drawn across the bottom of a card portrait.

Addresses: FEAT2 (per-anime match), BUG2 (it scales with the GUI scale).

A square telemetry plate replaces the old circular/pill language. A calibrated
contribution rail carries the proportion and a mono readout carries the exact percentage, the
same pairing the scoring bench uses on the landing artifact.

The rail is a meter, not an icon: contributor blocks use their continuous
values, so 91%, 92% and 95% remain visibly different. Ten-percent hairlines
give it the same calibrated instrument language as the expanded score track.

The score is the one the ranker already produces, so nothing is stubbed: it is
a real, explainable figure whose parts are listed in the card's breakdown. When
a learned model is added it becomes another term in the same blend, and this
keeps working unchanged.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QRect, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QWidget

from .contribution_visuals import (
    SemanticContribution,
    contribution_colour,
    contribution_summary,
    proportional_segment_widths,
    semantic_contributions,
    snap_pixel,
    snapped_segment_edges,
)
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
READOUT_RATIO = 0.27

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

RAIL_HEIGHT = 8.0
RAIL_BOTTOM_GAP = 3.0
READOUT_RAIL_GAP = 1.0
# How much a hovered cell grows, and the share its neighbours take. The
# falloff is what makes dragging along the rail feel continuous instead
# of like stepping between separate buttons.
#
# CHANGE [RAIL-LIFT]: 2.0, not 7.0. On a 4px rail a 7px lift grew the hovered
# cell to 275% of its height with its neighbours trailing behind it, which is
# a magnifying dock - phone-app motion, and on the one widget in the product
# that is a measurement. A rail that deforms under the cursor is harder to
# read at exactly the moment the user is trying to read it. 2.0 still marks
# which contribution is under the pointer without restating its magnitude.
CELL_LIFT = 2.0
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

# How far a seam is pushed from the block on its left. Lower than a
# calibration mark: a boundary between two lit blocks needs to be seen,
# not announced.
SEAM_MIX = 0.55

# How much a hovered block brightens. Raised from 16: at that value the
# response was there in the buffer but below the threshold where a
# reader notices the bar answered them.
HOVER_LIFT = 24


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


class MatchBadge(QWidget):
    """A compact, square-ended match telemetry plate."""

    # The contributor under the pointer, or "" when the pointer is elsewhere.
    # The card uses it to light the matching tag, so the rail can be read as
    # "which of these tags produced this" rather than only "how much".
    contributor_hovered = Signal(str)

    def __init__(self, percentage: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("matchBadge")
        self._percentage = max(0.0, min(100.0, float(percentage)))
        self._track = QColor(0, 0, 0, 140)
        self._fill = QColor("#E0685A")
        self._signal = QColor("#6FC6C0")
        self._text = QColor("#FFFFFF")
        self._contributions: tuple[tuple[str, float], ...] = ()
        self._semantic_contributions: tuple[SemanticContribution, ...] = ()
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

    def set_contributions(self, contributions, *, genres=(), studios=()) -> None:
        """Colour the rail by what actually produced the score.

        Genre terms use the interface's blue signal family and studios use its
        brass/orange accent family, matching their filter tags.  The tooltip
        repeats those categories in words so colour is never the only cue.
        """
        self._semantic_contributions = tuple(
            item
            for item in semantic_contributions(
                contributions, genres=genres, studios=studios
            )
            if item.value > 0
        )
        self._contributions = tuple(
            (item.name, item.value) for item in self._semantic_contributions
        )
        summary = contribution_summary(self._semantic_contributions)
        self.setToolTip(f"Score contributors: {summary}")
        self.setAccessibleDescription(summary)
        self.update()

    # ---- hover -----------------------------------------------------------

    def _segment_bounds(self):
        """Pixel spans of each contributor, in draw order.

        Returned in the same coordinates the painter uses so hit-testing and
        drawing cannot drift apart.
        """
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        rail_left = snap_pixel(rect.left() + PLATE_PADDING)
        rail_width = max(
            1, snap_pixel(max(1.0, (rect.right() - PLATE_PADDING) - (rect.left() + PLATE_PADDING)))
        )
        filled = snap_pixel(
            rail_width * max(0.0, min(100.0, self._percentage)) / 100.0
        )
        visuals = self._semantic_contributions
        if not visuals:
            return []
        widths = proportional_segment_widths(visuals, filled)
        edges = snapped_segment_edges(widths, start=rail_left)
        return [
            (edges[i], edges[i + 1], visuals[i])
            for i in range(len(visuals))
            if edges[i + 1] > edges[i]
        ]

    def _segment_at(self, x: float) -> int:
        for index, (left, right, _item) in enumerate(self._segment_bounds()):
            if left <= x < right:
                return index
        return -1

    def contributor_name(self, index: int) -> str:
        bounds = self._segment_bounds()
        if 0 <= index < len(bounds):
            return bounds[index][2].name
        return ""

    def _on_hover_value(self, value) -> None:
        self._hover_strength = max(0.0, min(1.0, float(value)))
        self.update()

    def _animate_hover(self, target: float) -> None:
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_strength)
        self._hover_anim.setEndValue(float(target))
        self._hover_anim.start()

    def mouseMoveEvent(self, event) -> None:
        segment = self._segment_at(event.position().x())
        if segment != self._hover_cell:
            self._hover_cell = segment
            self.contributor_hovered.emit(self.contributor_name(segment))
            self.update()
        if segment >= 0 and self._hover_strength < 1.0:
            self._animate_hover(1.0)
        elif segment < 0 and self._hover_strength > 0.0:
            self._animate_hover(0.0)
        event.ignore()

    def leaveEvent(self, event) -> None:
        if self._hover_cell != -1:
            self.contributor_hovered.emit("")
        self._hover_cell = -1
        self._animate_hover(0.0)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        # The plate listens for hover only; clicks belong to the card.
        event.ignore()

    @property
    def percentage(self) -> float:
        return self._percentage

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

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
        readout_bottom = (
            rect.bottom() - RAIL_HEIGHT - RAIL_BOTTOM_GAP - READOUT_RAIL_GAP
        )
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

        # CHANGE [BLOOM]: the bloom is gone. The readout already carries an
        # eight-direction halo at alpha 205, and stacking a second glow on top
        # of it was more phosphor than a two-digit number needs - the kind of
        # decoration that reads as an effect rather than as a measurement.
        # It also drops a full-size QPixmap allocation and two bilinear scales
        # from every paint, though that measured as only 1.33ms -> 1.25ms: the
        # reason to remove it is that it was decoration, not that it was slow.

        painter.setPen(QPen(self._fill))
        painter.drawText(text_rect, alignment, label)

        # The cover uses the same continuous contribution channel as the
        # expanded score track. Category blocks are joined by one-pixel seams;
        # sparse quarter graduations sit over them. This reads like one
        # calibrated instrument instead of a row of decorative phone-style
        # cells, while preserving exact sub-percent fill width.
        rail_left = rect.left() + PLATE_PADDING
        rail_right = rect.right() - PLATE_PADDING
        rail_width = max(1.0, rail_right - rail_left)
        # CHANGE [SCRIM]: measured from the bottom edge as before, but the
        # plate is flush to the artwork now, so this is the rail's real
        # distance from the bottom of the picture rather than from the top of
        # a six-pixel margin.
        rail_y = rect.bottom() - RAIL_HEIGHT - RAIL_BOTTOM_GAP

        # The empty range is an opaque instrument well. A translucent pale
        # track inherited too much of the cover beneath it and could look
        # identical to neutral contributors on busy or dark artwork.
        inactive = QColor(self._track)
        inactive.setAlpha(max(210, inactive.alpha()))

        rail_left_px = snap_pixel(rail_left)
        rail_top_px = snap_pixel(rail_y)
        rail_width_px = max(1, snap_pixel(rail_width))
        rail_height_px = max(1, snap_pixel(RAIL_HEIGHT))
        filled_width_px = snap_pixel(
            rail_width_px * max(0.0, min(100.0, self._percentage)) / 100.0
        )
        rail_rect = QRect(
            rail_left_px, rail_top_px, rail_width_px, rail_height_px
        )
        painter.fillRect(rail_rect, inactive)

        visuals = self._semantic_contributions
        if not visuals and filled_width_px > 0:
            painter.fillRect(
                QRect(
                    rail_left_px,
                    rail_top_px,
                    filled_width_px,
                    rail_height_px,
                ),
                self._fill,
            )
        widths = proportional_segment_widths(visuals, filled_width_px)
        edges = snapped_segment_edges(widths, start=rail_left_px)

        def colour_at(x: int) -> QColor:
            """The contributor colour covering a rail pixel."""
            for i, entry in enumerate(visuals):
                if edges[i] <= x < edges[i + 1]:
                    return contribution_colour(
                        entry,
                        genre=self._signal,
                        studio=self._fill,
                        community=QColor(self._text).darker(118),
                        other=QColor(self._text).darker(145),
                    )
            return inactive
        for index, item in enumerate(visuals):
            segment_left = edges[index]
            segment_right = edges[index + 1]
            segment_width = segment_right - segment_left
            if segment_width <= 0:
                continue
            colour = contribution_colour(
                item,
                genre=self._signal,
                studio=self._fill,
                # Community is often the largest term. It must remain visibly
                # filled rather than disappearing into the empty black well.
                community=QColor(self._text).darker(118),
                other=QColor(self._text).darker(145),
            )
            hover_offset = self._hover_cell * float(scaled(CELL_PITCH))
            if (
                self._hover_cell >= 0
                and segment_left - rail_left_px
                <= hover_offset
                <= segment_right - rail_left_px
                and self._hover_strength > 0.0
            ):
                colour = colour.lighter(100 + round(HOVER_LIFT * self._hover_strength))
            painter.fillRect(
                QRect(
                    segment_left,
                    rail_top_px,
                    segment_width,
                    rail_height_px,
                ),
                colour,
            )

        # CHANGE [NO-GRID]: the quarter marks are gone. They encoded 25/50/75
        # on a rail that prints its own exact percentage two centimetres away,
        # so they measured nothing the reader did not already have, and three
        # abstract strokes crossing five coloured blocks read as clutter. The
        # contributors are now separated by a gap instead, which says the same
        # thing the marks were trying to say - where one term ends and the
        # next begins - without adding a second visual language to the rail.

        # CHANGE [SEAM]: the blocks are separated by a drawn division rather
        # than by an empty gap. A gap shows the well between contributors,
        # which breaks the bar into pieces and costs the reader the sense of
        # one continuous measurement; a seam marks the same boundary while the
        # rail stays whole.
        #
        # Exactly one seam per internal boundary, deduplicated by snapped x:
        # drawing both sides of a narrow contributor is what produced the
        # heavy 2-4px clusters this rail had before.
        seam_positions = sorted({
            edges[index] for index in range(1, len(visuals))
            if edges[index] > rail_left_px
            and edges[index] < rail_left_px + filled_width_px
        })
        for seam_x in seam_positions:
            under = colour_at(max(rail_left_px, seam_x - 1))
            painter.setPen(QPen(calibration_mark(under, SEAM_MIX), 1))
            painter.drawLine(
                seam_x,
                rail_top_px,
                seam_x,
                rail_top_px + rail_height_px - 1,
            )

        border = QColor(self._text)
        border.setAlpha(82)
        painter.setPen(QPen(border, 1))
        painter.drawRect(
            QRect(
                rail_left_px,
                rail_top_px,
                rail_width_px - 1,
                rail_height_px - 1,
            )
        )

        if filled_width_px > 0:
            marker = QColor(self._text)
            marker.setAlpha(220)
            marker_x = min(
                rail_left_px + rail_width_px - 1,
                rail_left_px + filled_width_px,
            )
            painter.setPen(QPen(marker, 1))
            painter.drawLine(
                marker_x,
                rail_top_px,
                marker_x,
                rail_top_px + rail_height_px - 1,
            )
        painter.end()


def should_show_badge(model) -> bool:
    """CHANGE [FEAT2]: no bar when there is no score to show.

    ``personal_match_available`` is False when the recommendation carried no
    match at all, which is different from a genuine score of zero.
    """
    if not getattr(model, "personal_match_available", False):
        return False
    return getattr(model, "personal_match", None) is not None
