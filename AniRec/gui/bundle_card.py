"""The series bundle: a stacked card, and the panel it opens into.

A franchise the user has not started is one decision, not five. Collapsed it
occupies exactly one cell of the feed; opened it becomes a full-width row
directly beneath its own row, holding its entries and one place to decide
about them.

Geometry that is load-bearing, and why:

- **The stack sits inside a cover's footprint.** Single covers float 108-176px
  wide with their artwork, but a bundle pins the canonical 132x198 frame: a
  2x2 tile block is only poster-shaped at 132 (tiles measure 61x92, aspect
  0.66) and overflows the frame by 63px at 176. A bundle is a container, not
  a poster.
- **The shingles are painted into the artwork**, not added as margin above it.
  Ten pixels of extra top margin pushed the bundle's title ten pixels below
  every other title on its row.
- **Three covers and a count, or four covers at exactly four.** Three plus a
  "+1" is worse than showing all four, so the count starts at five.

See ``docs/design/BUNDLE_HANDOFF.md`` for the parts of this that are still blocked on
data rather than on layout.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .bundle_view_model import BundleViewModel
from .cover_art import rounded_cover
from .design_tokens import FONT_STACK_DISPLAY, RADIUS, SPACE
from .instrument_widgets import ScoreTrack, keep_crisp
from .recommendation_card import (
    CARD_MAX_WIDTH,
    CARD_WIDTH,
    COVER_HEIGHT,
    COVER_RADIUS,
    COVER_WIDTH,
    RecommendationCard,
)
from .scaling import scaled


# The plates that peek out from behind the front of the stack.
SHINGLE_HEIGHT = 11
SHINGLE_PLATE = 9
TILE_GAP = 3

# Derived so the tiles stay 2:3, the shape real cover art ships in.
TILE_HEIGHT = (COVER_HEIGHT - SHINGLE_HEIGHT - TILE_GAP) // 2
TILE_WIDTH = round(TILE_HEIGHT * 2 / 3)
TILE_BLOCK_WIDTH = TILE_WIDTH * 2 + TILE_GAP

# Below five entries every cover fits, so the count would be replacing a
# picture with an apology for not showing it.
COUNT_FROM = 5


def _resolved(role: str, fallback: str) -> QColor:
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance()
    value = application.property(role) if application is not None else None
    return QColor(str(value or fallback))


class BundleCard(QFrame):
    """The collapsed stack: one grid cell, the same height as a card."""

    toggled = Signal(object)

    def __init__(self, bundle: BundleViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.bundle = bundle
        self._expanded = False
        self.setObjectName("bundleCard")
        self.setProperty("bundleCard", True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(
            "Series bundle: %s, %d entries" % (bundle.title, bundle.size)
        )
        self.setMinimumWidth(scaled(CARD_WIDTH))
        self.setMaximumWidth(scaled(CARD_MAX_WIDTH))
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            scaled(SPACE["md"]), scaled(SPACE["sm"]),
            scaled(SPACE["md"]), scaled(SPACE["md"]),
        )
        layout.setSpacing(scaled(SPACE["sm"]))

        self.stack_label = QLabel()
        self.stack_label.setObjectName("bundleStack")
        self.stack_label.setFixedSize(scaled(COVER_WIDTH), scaled(COVER_HEIGHT))
        self.stack_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        keep_crisp(self.stack_label)
        layout.addWidget(self.stack_label, 0, Qt.AlignmentFlag.AlignHCenter)

        self.title_label = QLabel(bundle.title)
        self.title_label.setObjectName("bundleTitle")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.count_label = QLabel("%d ENTRIES" % bundle.size)
        self.count_label.setObjectName("bundleCount")
        layout.addWidget(self.count_label)

        # The mean, never the best of the members: a best-of number would rank
        # every bundle by its strongest entry and make bundles outscore the
        # single cards beside them in the same grid.
        self.match_label = QLabel("AVG MATCH %d%%" % round(bundle.average_match))
        self.match_label.setObjectName("bundleMatch")
        layout.addWidget(self.match_label)
        layout.addStretch(1)

        self.open_button = QPushButton("Open")
        self.open_button.setObjectName("bundleOpenButton")
        self.open_button.setAccessibleName("Open this series bundle")
        self.open_button.clicked.connect(lambda: self.toggled.emit(self))
        self.hide_button = QPushButton("Hide all")
        self.hide_button.setObjectName("bundleHideButton")
        self.hide_button.setProperty("buttonRole", "ghost")
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(scaled(SPACE["sm"]))
        row.addWidget(self.open_button, 1)
        row.addWidget(self.hide_button, 0)
        layout.addLayout(row)

        self._covers: dict[int, QPixmap] = {}
        self.refresh_stack()

    # ---------------------------------------------------------------- state

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = bool(expanded)
        self.open_button.setText("Close" if self._expanded else "Open")
        self.setProperty("expanded", self._expanded)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_cover(self, mal_id: int, pixmap: QPixmap) -> None:
        """Supply one member's artwork; the stack redraws with what it has."""
        if pixmap.isNull():
            return
        self._covers[int(mal_id)] = pixmap
        self.refresh_stack()

    def apply_scale(self) -> None:
        self.setMinimumWidth(scaled(CARD_WIDTH))
        self.setMaximumWidth(scaled(CARD_MAX_WIDTH))
        self.stack_label.setFixedSize(scaled(COVER_WIDTH), scaled(COVER_HEIGHT))
        self.refresh_stack()

    # --------------------------------------------------------------- paint

    def refresh_stack(self) -> None:
        self.stack_label.setPixmap(self._render_stack())

    def _render_stack(self) -> QPixmap:
        width = scaled(COVER_WIDTH)
        height = scaled(COVER_HEIGHT)
        shingle = scaled(SHINGLE_HEIGHT)
        tile_height = (height - shingle - scaled(TILE_GAP)) // 2
        tile_width = max(1, round(tile_height * 2 / 3))
        gap = scaled(TILE_GAP)
        block = tile_width * 2 + gap

        canvas = QPixmap(width, height)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        raised = _resolved("resolvedSurface", "#101A14")
        painter.setPen(Qt.PenStyle.NoPen)
        for index, inset in enumerate((scaled(16), scaled(8))):
            shade = QColor(raised)
            shade.setAlpha(150 + index * 55)
            painter.setBrush(shade)
            painter.drawRoundedRect(
                QRectF(inset, index * scaled(4), width - inset * 2, scaled(SHINGLE_PLATE)),
                scaled(RADIUS["md"]),
                scaled(RADIUS["md"]),
            )

        entries = self.bundle.entries
        shown = entries[:4] if len(entries) < COUNT_FROM else entries[:3]
        left = (width - block) // 2
        for index, entry in enumerate(shown):
            column, row = index % 2, index // 2
            tile = self._tile(entry, tile_width, tile_height)
            painter.drawPixmap(
                left + column * (tile_width + gap),
                shingle + row * (tile_height + gap),
                tile,
            )

        if len(entries) >= COUNT_FROM:
            spot = QRectF(
                left + tile_width + gap,
                shingle + tile_height + gap,
                tile_width,
                tile_height,
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(_resolved("resolvedWell", "#040806"))
            painter.drawRoundedRect(spot, scaled(RADIUS["md"]), scaled(RADIUS["md"]))
            painter.setPen(_resolved("resolvedAccent", "#D9A441"))
            font = QFont(self.font())
            font.setFamilies([part.strip().strip('"') for part in FONT_STACK_DISPLAY.split(",")])
            font.setPointSizeF(max(7.0, tile_height * 0.24))
            font.setWeight(QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(
                spot,
                int(Qt.AlignmentFlag.AlignCenter),
                "+%d" % (len(entries) - 3),
            )
        painter.end()
        return canvas

    def _tile(self, entry, width: int, height: int) -> QPixmap:
        source = self._covers.get(entry.mal_id) if entry.mal_id is not None else None
        if source is None or source.isNull():
            placeholder = QPixmap(width, height)
            placeholder.fill(_resolved("resolvedWell", "#040806"))
            return rounded_cover(placeholder, width, height, scaled(COVER_RADIUS))
        return rounded_cover(source, width, height, scaled(COVER_RADIUS))

    # --------------------------------------------------------------- input

    def mouseReleaseEvent(self, event) -> None:
        self.toggled.emit(self)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.toggled.emit(self)
            return
        super().keyPressEvent(event)


class BundleInfoBlock(QFrame):
    """Two cells wide, one cell tall: the score, the rail, the why, the actions.

    Everything true of the franchise rather than of one entry lives here,
    which is what lets the entry cards go back to being posters.
    """

    liked = Signal(object)
    disliked = Signal(object)
    watch_later = Signal(object)
    hidden = Signal(object)

    def __init__(self, bundle: BundleViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.bundle = bundle
        self.setObjectName("bundleInfo")
        self.setFixedWidth(scaled(CARD_WIDTH) * 2 + scaled(SPACE["lg"]))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            scaled(SPACE["md"]), scaled(SPACE["md"]),
            scaled(SPACE["md"]), scaled(SPACE["md"]),
        )
        layout.setSpacing(scaled(SPACE["sm"]))

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(scaled(SPACE["sm"]))
        caption = QLabel("BUNDLE MATCH")
        caption.setObjectName("bundleInfoCaption")
        head.addWidget(caption)
        head.addStretch(1)
        mean_of = QLabel("MEAN OF %d ENTRIES" % bundle.size)
        mean_of.setObjectName("bundleInfoMeta")
        head.addWidget(mean_of)
        layout.addLayout(head)

        readout = QHBoxLayout()
        readout.setContentsMargins(0, 0, 0, 0)
        readout.setSpacing(scaled(SPACE["xs"]))
        self.value_label = QLabel("%d" % round(bundle.average_match))
        self.value_label.setObjectName("bundleInfoValue")
        self.percent_label = QLabel("%")
        self.percent_label.setObjectName("bundleInfoPercent")
        readout.addWidget(self.value_label, 0, Qt.AlignmentFlag.AlignBottom)
        readout.addWidget(self.percent_label, 0, Qt.AlignmentFlag.AlignBottom)
        readout.addStretch(1)
        # A mean alone hides that the members disagree; the spread says so.
        self.range_label = QLabel(
            "RANGE %d–%d%%"
            % (round(bundle.lowest_match), round(bundle.highest_match))
        )
        self.range_label.setObjectName("bundleInfoMeta")
        readout.addWidget(self.range_label, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(readout)

        self.track = ScoreTrack(self)
        self.track.set_data(bundle.contributions, bundle.average_match)
        layout.addWidget(self.track)

        self.reason_label = QLabel(bundle.reason)
        self.reason_label.setObjectName("bundleInfoReason")
        self.reason_label.setWordWrap(True)
        layout.addWidget(self.reason_label)
        layout.addStretch(1)

        # The same four decisions a single card offers, at franchise scale.
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(scaled(SPACE["sm"]))
        self.dislike_button = QPushButton("Not for me")
        self.dislike_button.setObjectName("bundleDislikeButton")
        self.dislike_button.setProperty("feedback", "disliked")
        self.later_button = QPushButton("Later")
        self.later_button.setObjectName("bundleLaterButton")
        self.later_button.setProperty("savedAction", True)
        self.hide_button = QPushButton("Hide")
        self.hide_button.setObjectName("bundleInfoHideButton")
        self.hide_button.setProperty("buttonRole", "ghost")
        self.like_button = QPushButton("Like the franchise")
        self.like_button.setObjectName("bundleLikeButton")
        self.like_button.setProperty("buttonRole", "primary")
        for button, stretch in (
            (self.dislike_button, 3),
            (self.later_button, 2),
            (self.hide_button, 2),
            (self.like_button, 4),
        ):
            button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            actions.addWidget(button, stretch)
        layout.addLayout(actions)

        self.like_button.clicked.connect(lambda: self.liked.emit(self.bundle))
        self.dislike_button.clicked.connect(lambda: self.disliked.emit(self.bundle))
        self.later_button.clicked.connect(lambda: self.watch_later.emit(self.bundle))
        self.hide_button.clicked.connect(lambda: self.hidden.emit(self.bundle))

    def refresh_track(self) -> None:
        """Re-read the palette after a theme change.

        ScoreTrack paints itself from the resolved palette the theme
        publishes, so it only needs telling that the data is still the
        same and the colours are not.
        """
        self.track.set_data(self.bundle.contributions, self.bundle.average_match)
