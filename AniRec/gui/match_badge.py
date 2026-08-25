"""The match indicator drawn across the bottom of a card's portrait.

Addresses: FEAT2 (per-anime match), BUG2 (it scales with the GUI scale).

A horizontal bar rather than a bubble. The filled length *is* the score, so the
value is readable at a glance and comparable between two cards side by side
without reading either number. At 100% the fill spans the card; at 60% it
covers a little over half. The number sits inside the fill.

The score is the one the ranker already produces, so nothing is stubbed: it is
a real, explainable figure whose parts are listed in the card's breakdown. When
a learned model is added it becomes another term in the same blend, and this
keeps working unchanged.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from .scaling import scaled


# Bar height at 100% GUI scale.
BAR_HEIGHT = 26

# How far the bar sits above the bottom edge of the portrait.
BADGE_BOTTOM_INSET = 6

# Side inset, so the bar does not run into the portrait's rounded corners.
BAR_SIDE_INSET = 6

# Kept for callers that still import the old name.
BADGE_DIAMETER = BAR_HEIGHT


class MatchBadge(QWidget):
    """A proportional match bar, drawn over the bottom of a portrait."""

    def __init__(self, percentage: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("matchBadge")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._percentage = max(0.0, min(100.0, float(percentage)))
        self._track = QColor(0, 0, 0, 140)
        self._fill = QColor("#E0685A")
        self._text = QColor("#FFFFFF")
        self.setAccessibleName(
            f"{round(self._percentage)} percent match with your interests"
        )
        self.apply_scale()

    def apply_scale(self) -> None:
        """CHANGE [BUG2]: resize with the GUI scale, like everything else."""
        self.setFixedHeight(scaled(BAR_HEIGHT))
        self.update()

    def set_colours(self, track: QColor, fill: QColor, text: QColor) -> None:
        """Follow the active theme rather than assuming one backdrop."""
        self._track = QColor(track)
        self._fill = QColor(fill)
        self._text = QColor(text)
        self.update()

    @property
    def percentage(self) -> float:
        return self._percentage

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = QRectF(self.rect())
        radius = rect.height() / 2

        # CHANGE [FEAT2]: the track carries the meaning. The fill only reads as
        # a proportion if the whole length it is measured against is visible,
        # and at alpha 165 over dark cover art it was not, so a low score drew
        # a small rounded fill on an invisible track: exactly the bubble this
        # replaced. It is now opaque enough to see, with a hairline edge.
        track_path = QPainterPath()
        track_path.addRoundedRect(rect, radius, radius)
        painter.fillPath(track_path, self._track)
        edge = QColor(self._text)
        edge.setAlpha(60)
        painter.setPen(QPen(edge, 1))
        painter.drawPath(track_path)

        fraction = self._percentage / 100.0
        fill_width = max(rect.height(), rect.width() * fraction)
        fill_rect = QRectF(rect.left(), rect.top(), fill_width, rect.height())
        fill_path = QPainterPath()
        fill_path.addRoundedRect(fill_rect, radius, radius)
        painter.fillPath(fill_path, self._fill)

        label = f"{round(self._percentage)}%"
        font = QFont(self.font())
        font.setPointSizeF(max(6.0, rect.height() * 0.46))
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)

        # CHANGE [FEAT2]: the number stays inside the bar at every score.
        # It used to be pushed outside whenever the fill was too short to hold
        # it, which is what made a low match look like a bubble with a number
        # sitting next to it. Anchored to the right of the track it also keeps
        # one position down a column of cards, so the numbers can be compared
        # without the eye chasing them.
        text_width = painter.fontMetrics().horizontalAdvance(label)
        padding = rect.height() * 0.42
        text_rect = QRectF(
            rect.right() - text_width - padding,
            rect.top(),
            text_width,
            rect.height(),
        )
        covered = fill_rect.right() >= text_rect.left()
        if covered:
            painter.setPen(QPen(self._text))
        else:
            # Readable against the track, whatever the theme made it.
            on_track = QColor("#FFFFFF") if self._track.lightness() < 128 else QColor("#101014")
            painter.setPen(QPen(on_track))
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            label,
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
