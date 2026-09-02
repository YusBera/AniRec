"""A compact horizontal row, for the list layout.

Addresses: BUG2 (GUI scale), FEAT2 (match badge is shown on cards, not rows).

Where a card leads with artwork, a row leads with text: a small fixed
thumbnail, then the title, a truncated reason, and a tag carrying the match or
community score. It trades the poster for density, so several times as many
titles fit the same space.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFocusEvent, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from .design_tokens import RADIUS, SPACE
from .cover_art import rounded_cover
from .instrument_widgets import keep_crisp
from .scaling import scaled
from .recommendation_card import MEMORY_COVER_CACHE, open_mal_url
from .recommendation_view_model import RecommendationViewModel
from .resources import cover_placeholder_pixmap, title_placeholder_pixmap


# CHANGE [BUG7]: a 2:3 poster, matching the card and the source artwork.
# Cropping the thumbnail square was never intended and cut the artwork off.
THUMBNAIL_SIZE = 56
COVER_ROW_HEIGHT = 84
# Smaller than the card's, in proportion to the smaller thumbnail.
ROW_COVER_RADIUS = RADIUS["sm"]

# Beyond this the reason is elided, keeping every row the same height.
REASON_CHARACTERS = 150


class RecommendationRow(QFrame):
    """One recommendation as a horizontal row."""

    selection_requested = Signal(object)
    details_requested = Signal(object)
    not_interested_requested = Signal(object)
    watch_later_requested = Signal(object)
    cover_requested = Signal(str)

    def __init__(
        self,
        model: RecommendationViewModel,
        parent=None,
        *,
        mal_opener: Callable[[str], bool] | None = None,
    ) -> None:
        super().__init__(parent)
        self.model = model
        self._mal_opener = mal_opener
        self.setObjectName("recommendationRow")
        self.setProperty("recommendationRow", True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(f"Anime recommendation: {model.display_title}")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        layout = QHBoxLayout(self)
        # CHANGE [BUG2]: spacing scales with the rest of the row.
        layout.setContentsMargins(
            scaled(SPACE["md"]), scaled(SPACE["sm"]),
            scaled(SPACE["md"]), scaled(SPACE["sm"]),
        )
        layout.setSpacing(scaled(SPACE["md"]))

        self.cover_label = QLabel()
        self.cover_label.setObjectName("recommendationRowCover")
        # Artwork is never rastered; see keep_crisp.
        keep_crisp(self.cover_label)
        # CHANGE [BUG2]: the thumbnail scales with the GUI Scale setting.
        self.cover_label.setFixedSize(scaled(THUMBNAIL_SIZE), scaled(COVER_ROW_HEIGHT))
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setAccessibleName(f"Cover for {model.display_title}")
        self._source_cover = None
        self._show_placeholder()
        layout.addWidget(self.cover_label)

        text_column = QVBoxLayout()
        text_column.setSpacing(SPACE["hair"])
        self.title_label = QLabel(model.display_title)
        self.title_label.setObjectName("recommendationRowTitle")
        self.title_label.setWordWrap(False)
        self.title_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.reason_label = QLabel(_truncate(model.reason or model.genres_text))
        self.reason_label.setObjectName("recommendationRowReason")
        self.reason_label.setWordWrap(True)
        # CHANGE [ROW-DENSITY]: the row carried a title, one sentence and a
        # single orphaned genre chip, then several centimetres of nothing.
        # The card states the year, the run length, the studio and the MAL
        # score; the list view is supposed to be the denser way to read the
        # same feed and was showing strictly less. The facts go in the empty
        # space that was already there.
        self.facts_label = QLabel(_facts_line(model))
        self.facts_label.setObjectName("recommendationRowFacts")
        self.facts_label.setWordWrap(False)
        # CHANGE [BUILD-QUIET]: only hidden when there is nothing to show.
        # setVisible() on a child of a live parent forces a layout pass, and
        # measured 24.7ms a call - the single most expensive line in this
        # constructor. A label is visible by default, so the common path now
        # makes no call at all.
        if not self.facts_label.text():
            self.facts_label.setVisible(False)
        text_column.addWidget(self.title_label)
        text_column.addWidget(self.facts_label)
        text_column.addWidget(self.reason_label)
        layout.addLayout(text_column, 1)

        tag_column = QVBoxLayout()
        tag_column.setSpacing(SPACE["xs"])
        tag_column.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.match_tag = QLabel(model.personal_match_text)
        self.match_tag.setObjectName("recommendationRowMatchTag")
        self.match_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.genre_tag = QLabel(_primary_tag(model))
        self.genre_tag.setObjectName("recommendationRowGenreTag")
        self.genre_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # CHANGE [BUG-SIZES]: each tag hugs its own text. Stacked in a column
        # they were both stretched to the width of the wider one, so a short
        # genre sat in a pill several times longer than its label.
        for tag in (self.match_tag, self.genre_tag):
            tag.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        tag_column.addWidget(self.match_tag, 0, Qt.AlignmentFlag.AlignRight)
        tag_column.addWidget(self.genre_tag, 0, Qt.AlignmentFlag.AlignRight)
        layout.addLayout(tag_column)

        # CHANGE [NO-VERDICTS]: the row carried Like and Dislike and no way
        # to save anything, which left the list view able to express only the
        # opinion a reader cannot yet hold and not the one action they can.
        # The signal for it was already declared here and already wired on the
        # page; only the button was missing.
        self.watch_later_button = QPushButton("Watch Later")
        self.watch_later_button.setObjectName("recommendationRowWatchLaterButton")
        self.watch_later_button.setProperty("savedAction", True)
        self.watch_later_button.setCheckable(True)
        self.watch_later_button.clicked.connect(
            lambda: self.watch_later_requested.emit(self.model)
        )
        self.not_interested_button = QPushButton("Not interested")
        self.not_interested_button.setObjectName(
            "recommendationRowNotInterestedButton"
        )
        self.not_interested_button.setProperty("feedback", "not-interested")
        self.not_interested_button.setCheckable(True)
        self.not_interested_button.clicked.connect(
            lambda: self.not_interested_requested.emit(self.model)
        )
        self.details_button = QPushButton("Details")
        self.details_button.setProperty("buttonRole", "secondary")
        self.details_button.clicked.connect(
            lambda: self.details_requested.emit(self.model)
        )
        for button in (
            self.watch_later_button,
            self.not_interested_button,
            self.details_button,
        ):
            layout.addWidget(button)

    # -- cover ---------------------------------------------------------------

    def _show_placeholder(self) -> None:
        # CHANGE [PLATE-SIZE]: at the size it is drawn, not at the source
        # artwork's. Called without one this renders 440x660 and then scales
        # the result down to a 56x84 thumbnail - measured at 20ms of drawText
        # per row, a third of the entire cost of building a list row, to
        # produce pixels that are immediately thrown away.
        placeholder = title_placeholder_pixmap(
            self.model.display_title,
            (scaled(THUMBNAIL_SIZE), scaled(COVER_ROW_HEIGHT)),
        )
        if placeholder.isNull():
            placeholder = cover_placeholder_pixmap()
        if placeholder.isNull():
            self.cover_label.setText("")
            return
        self._source_cover = placeholder
        # CHANGE [BUG7]: rounded, like the card portraits.
        self.cover_label.setPixmap(_fit_row_cover(placeholder))

    def request_cover(self) -> None:
        if not self.model.cover_url:
            return
        cached = MEMORY_COVER_CACHE.get(self.model.cover_url)
        if cached is not None:
            self.set_cover(cached)
            return
        self.cover_requested.emit(self.model.cover_url)

    def set_cover(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            self._show_placeholder()
            return
        self._source_cover = pixmap
        self.cover_label.setPixmap(_fit_row_cover(pixmap))

    def apply_scale(self) -> None:
        """CHANGE [BUG2]: rows are reused too, so re-apply their fixed sizes."""
        self.cover_label.setFixedSize(scaled(THUMBNAIL_SIZE), scaled(COVER_ROW_HEIGHT))
        layout = self.layout()
        if layout is not None:
            layout.setContentsMargins(
                scaled(SPACE["md"]), scaled(SPACE["sm"]),
                scaled(SPACE["md"]), scaled(SPACE["sm"]),
            )
            layout.setSpacing(scaled(SPACE["md"]))
        self._rescale_cover()

    def set_cover_data(self, data: bytes) -> None:
        """CHANGE [BUG3]: accept downloaded bytes, as the card does."""
        pixmap = QPixmap()
        if not data or not pixmap.loadFromData(data):
            self._show_placeholder()
            return
        # CHANGE [BUG6]: cache the original, not a downscaled copy.
        if self.model.cover_url:
            MEMORY_COVER_CACHE.put(self.model.cover_url, pixmap)
        self.set_cover(pixmap)

    def _rescale_cover(self) -> None:
        """CHANGE [BUG6]: re-fit from the original after a scale change."""
        source = getattr(self, "_source_cover", None)
        if source is None or source.isNull():
            self._show_placeholder()
            return
        self.set_cover(source)

    def set_cover_visible(self, visible: bool) -> None:
        self.cover_label.setVisible(bool(visible))

    # -- state ---------------------------------------------------------------

    def set_local_state(
        self,
        *,
        hidden: bool,
        watch_later: bool,
        actions_enabled: bool,
    ) -> None:
        self.watch_later_button.setChecked(bool(watch_later))
        self.not_interested_button.setChecked(bool(hidden))
        self.watch_later_button.setEnabled(actions_enabled)
        self.not_interested_button.setEnabled(actions_enabled)
        # CHANGE [NO-VERDICTS]: the label no longer grows when the state
        # changes. "Remove from Watch Later" is twice the width of "Watch
        # Later", so a saved row pushed the whole action column left and the
        # list stopped lining up down the page. The button is checkable: the
        # checked state says it is saved, and the accessible name says what
        # pressing it does.
        self.watch_later_button.setAccessibleName(
            "Remove from Watch Later" if watch_later else "Save to Watch Later"
        )
        self.not_interested_button.setAccessibleName(
            "Show this recommendation again" if hidden else "Not interested"
        )
        for button in (self.watch_later_button, self.not_interested_button):
            button.setToolTip(button.accessibleName())
        self.setProperty("tasteState", "not-interested" if hidden else "")
        self.setProperty("hiddenItem", bool(hidden))
        self.setProperty("watchLater", bool(watch_later))
        self.style().unpolish(self)
        self.style().polish(self)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def open_mal(self) -> bool:
        return open_mal_url(self.model.mal_url, opener=self._mal_opener)

    # -- interaction ---------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.selection_requested.emit(self.model)
        super().mousePressEvent(event)

    def focusInEvent(self, event: QFocusEvent) -> None:
        self.selection_requested.emit(self.model)
        super().focusInEvent(event)


def _truncate(text: str | None, limit: int = REASON_CHARACTERS) -> str:
    """Elide to keep every row the same height."""
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _facts_line(model: RecommendationViewModel) -> str:
    """The metadata band the card shows and the row was missing.

    Only parts that actually exist are joined, so a title with no year and no
    studio produces a shorter line rather than a row of "Not available".
    """
    parts: list[str] = []
    if model.studios:
        parts.append(model.studios[0])
    if model.year is not None:
        parts.append(str(model.year))
    if model.episodes is not None:
        parts.append(model.episodes_text)
    if model.mal_score is not None:
        parts.append(f"MAL {model.mal_score:.2f}")
    return "  ·  ".join(parts)


def _primary_tag(model: RecommendationViewModel) -> str:
    """The one genre or score worth showing beside a row."""
    if model.genres:
        return model.genres[0]
    return model.mal_score_text or ""


def _fit_row_cover(source: QPixmap) -> QPixmap:
    """CHANGE [BUG7]: one rounded, centre-cropped thumbnail for every row."""
    return rounded_cover(
        source,
        scaled(THUMBNAIL_SIZE),
        scaled(COVER_ROW_HEIGHT),
        scaled(ROW_COVER_RADIUS),
    )
