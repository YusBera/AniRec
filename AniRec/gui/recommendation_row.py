"""A compact horizontal row, for the list layout.

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

from .design_tokens import SPACE
from .recommendation_card import MEMORY_COVER_CACHE, open_mal_url
from .recommendation_view_model import RecommendationViewModel
from .resources import cover_placeholder_pixmap


# Square, so a row keeps one height whatever the poster's aspect ratio is.
THUMBNAIL_SIZE = 80

# Beyond this the reason is elided, keeping every row the same height.
REASON_CHARACTERS = 150


class RecommendationRow(QFrame):
    """One recommendation as a horizontal row."""

    selection_requested = Signal(object)
    details_requested = Signal(object)
    hide_requested = Signal(object)
    watch_later_requested = Signal(object)
    liked_requested = Signal(object)
    disliked_requested = Signal(object)
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
        layout.setContentsMargins(SPACE["md"], SPACE["sm"], SPACE["md"], SPACE["sm"])
        layout.setSpacing(SPACE["md"])

        self.cover_label = QLabel()
        self.cover_label.setObjectName("recommendationRowCover")
        self.cover_label.setFixedSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setAccessibleName(f"Cover for {model.display_title}")
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
        text_column.addWidget(self.title_label)
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
        tag_column.addWidget(self.match_tag)
        tag_column.addWidget(self.genre_tag)
        layout.addLayout(tag_column)

        self.like_button = QPushButton("Like")
        self.like_button.setObjectName("recommendationRowLikeButton")
        self.like_button.setProperty("feedback", "liked")
        self.like_button.setCheckable(True)
        self.like_button.clicked.connect(lambda: self.liked_requested.emit(self.model))
        self.dislike_button = QPushButton("Not for me")
        self.dislike_button.setObjectName("recommendationRowDislikeButton")
        self.dislike_button.setProperty("feedback", "disliked")
        self.dislike_button.setCheckable(True)
        self.dislike_button.clicked.connect(
            lambda: self.disliked_requested.emit(self.model)
        )
        self.details_button = QPushButton("Details")
        self.details_button.setProperty("buttonRole", "secondary")
        self.details_button.clicked.connect(
            lambda: self.details_requested.emit(self.model)
        )
        for button in (self.like_button, self.dislike_button, self.details_button):
            layout.addWidget(button)

    # -- cover ---------------------------------------------------------------

    def _show_placeholder(self) -> None:
        placeholder = cover_placeholder_pixmap()
        if placeholder.isNull():
            self.cover_label.setText("")
            return
        self.cover_label.setPixmap(
            placeholder.scaled(
                THUMBNAIL_SIZE,
                THUMBNAIL_SIZE,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

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
        self.cover_label.setPixmap(
            pixmap.scaled(
                THUMBNAIL_SIZE,
                THUMBNAIL_SIZE,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def set_cover_visible(self, visible: bool) -> None:
        self.cover_label.setVisible(bool(visible))

    # -- state ---------------------------------------------------------------

    def set_local_state(
        self,
        *,
        hidden: bool,
        watch_later: bool,
        actions_enabled: bool,
        liked: bool = False,
        disliked: bool = False,
    ) -> None:
        self.like_button.setChecked(liked)
        self.dislike_button.setChecked(disliked)
        self.like_button.setEnabled(actions_enabled)
        self.dislike_button.setEnabled(actions_enabled)
        self.setProperty(
            "tasteState", "liked" if liked else "disliked" if disliked else ""
        )
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


def _primary_tag(model: RecommendationViewModel) -> str:
    """The one genre or score worth showing beside a row."""
    if model.genres:
        return model.genres[0]
    return model.mal_score_text or ""
