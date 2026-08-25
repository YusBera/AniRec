"""Reference-aligned recommendation card with safe cover and MAL actions."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFocusEvent, QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .design_tokens import SPACE
from .recommendation_view_model import RecommendationViewModel
from .resources import cover_placeholder_pixmap


CARD_WIDTH = 224
# A 2:3 poster, the standard shape for anime cover art. Sized so that a whole
# card, including the review actions, fits the default window without
# scrolling; at the previous size the buttons sat below the fold.
COVER_WIDTH = 176
COVER_HEIGHT = 264


class CoverMemoryCache:
    def __init__(self, maximum_items: int = 64) -> None:
        self.maximum_items = maximum_items
        self._items: OrderedDict[str, QPixmap] = OrderedDict()

    def get(self, url: str) -> QPixmap | None:
        pixmap = self._items.get(url)
        if pixmap is not None:
            self._items.move_to_end(url)
        return pixmap

    def put(self, url: str, pixmap: QPixmap) -> None:
        self._items[url] = pixmap
        self._items.move_to_end(url)
        while len(self._items) > self.maximum_items:
            self._items.popitem(last=False)

    def clear(self) -> None:
        self._items.clear()


MEMORY_COVER_CACHE = CoverMemoryCache()


def open_mal_url(url: str | None, *, opener: Callable[[QUrl], bool] = QDesktopServices.openUrl) -> bool:
    if not url:
        return False
    parsed = QUrl(url)
    if (
        not parsed.isValid()
        or parsed.scheme().casefold() != "https"
        or parsed.host().casefold() not in {"myanimelist.net", "www.myanimelist.net"}
        or not parsed.path().startswith("/anime/")
    ):
        return False
    segments = [segment for segment in parsed.path().split("/") if segment]
    if len(segments) < 2 or segments[0].casefold() != "anime" or not segments[1].isdigit():
        return False
    return opener(parsed)


class RecommendationCard(QFrame):
    cover_requested = Signal(str)
    details_requested = Signal(object)
    selection_requested = Signal(object)
    hide_requested = Signal(object)
    watch_later_requested = Signal(object)
    liked_requested = Signal(object)
    disliked_requested = Signal(object)

    def __init__(
        self,
        model: RecommendationViewModel,
        parent: QWidget | None = None,
        *,
        mal_opener: Callable[[QUrl], bool] = QDesktopServices.openUrl,
    ) -> None:
        super().__init__(parent)
        self.model = model
        self._mal_opener = mal_opener
        self.setObjectName("recommendationCard")
        self.setProperty("recommendationCard", True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(f"Anime recommendation: {model.display_title}")
        self.setFixedWidth(CARD_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Maximum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE['md'], SPACE['sm'], SPACE['md'], SPACE['sm'])
        # Ten stacked items, so the gap between them dominates the card height.
        layout.setSpacing(SPACE['xs'])
        self.cover_label = QLabel()
        self.cover_label.setObjectName("recommendationCover")
        self.cover_label.setFixedSize(COVER_WIDTH, COVER_HEIGHT)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setAccessibleName(f"Cover for {model.display_title}")
        self.cover_label.setToolTip(f"Cover for {model.display_title}")
        self._show_placeholder()

        self.match_label = self._label(model.personal_match_text, "personalMatchLabel")
        self.title_label = self._label(model.display_title, "recommendationTitle")
        self.title_label.setWordWrap(True)
        self.secondary_title_label = self._label(
            model.secondary_title or "", "recommendationSecondaryTitle"
        )
        self.secondary_title_label.setVisible(bool(model.secondary_title))
        self.mal_score_label = self._label(model.mal_score_text, "malScoreLabel")
        self.meta_label = self._label(
            f"{model.year_text} · {model.status} · {model.episodes_text}",
            "recommendationMeta",
        )
        self.meta_label.setWordWrap(True)
        self.genres_label = self._label(model.genres_text, "recommendationGenres")
        self.genres_label.setWordWrap(True)
        self.reason_label = self._label(model.reason, "recommendationReason")
        self.reason_label.setWordWrap(True)
        self.like_button = QPushButton("Like")
        self.like_button.setObjectName("recommendationLikeButton")
        self.like_button.setProperty("feedback", "liked")
        self.like_button.setCheckable(True)
        self.like_button.clicked.connect(lambda: self.liked_requested.emit(self.model))
        self.dislike_button = QPushButton("Not for me")
        self.dislike_button.setObjectName("recommendationDislikeButton")
        self.dislike_button.setProperty("feedback", "disliked")
        self.dislike_button.setCheckable(True)
        self.dislike_button.clicked.connect(
            lambda: self.disliked_requested.emit(self.model)
        )
        self.details_button = QPushButton("View Details")
        self.details_button.setProperty("buttonRole", "secondary")
        self.details_button.clicked.connect(lambda: self.details_requested.emit(self.model))
        self.hide_button = QPushButton("Hide")
        self.hide_button.setObjectName("recommendationHideButton")
        self.hide_button.clicked.connect(lambda: self.hide_requested.emit(self.model))
        self.watch_later_button = QPushButton("Watch Later")
        self.watch_later_button.setObjectName("recommendationWatchLaterButton")
        self.watch_later_button.setProperty("savedAction", True)
        self.watch_later_button.setCheckable(True)
        self.watch_later_button.clicked.connect(
            lambda: self.watch_later_requested.emit(self.model)
        )
        self.mal_button = QPushButton("Open on MyAnimeList")
        self.mal_button.setProperty("buttonRole", "link")
        self.mal_button.setEnabled(bool(model.mal_url))
        self.mal_button.clicked.connect(
            lambda: open_mal_url(self.model.mal_url, opener=self._mal_opener)
        )
        # Identity first, then the decision, then the supporting detail.
        #
        # A 2:3 poster plus six buttons cannot fit the default window: a whole
        # card measures around 565px against roughly 448px of visible feed, and
        # shrinking the cover far enough to close that gap would leave artwork
        # too small to recognise. So the ordering decides what falls below the
        # fold. Reviewing a pick is the core loop, so Like and Not for me sit
        # directly under the title where the eye already is, and the metadata
        # a user reads only when undecided moves beneath them.
        for widget in (
            self.cover_label,
            self.match_label,
            self.title_label,
            self.secondary_title_label,
        ):
            layout.addWidget(widget)
        feedback_row = QHBoxLayout()
        feedback_row.setSpacing(8)
        feedback_row.addWidget(self.like_button, 1)
        feedback_row.addWidget(self.dislike_button, 1)
        layout.addLayout(feedback_row)
        for widget in (
            self.mal_score_label,
            self.meta_label,
            self.genres_label,
            self.reason_label,
        ):
            layout.addWidget(widget)
        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        action_row.addWidget(self.details_button, 1)
        action_row.addWidget(self.watch_later_button, 1)
        layout.addLayout(action_row)
        utility_row = QHBoxLayout()
        utility_row.setSpacing(4)
        utility_row.addWidget(self.mal_button, 1)
        utility_row.addWidget(self.hide_button)
        layout.addLayout(utility_row)

    @staticmethod
    def _label(text: str, object_name: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName(object_name)
        return label

    def request_cover(self) -> None:
        if not self.model.cover_url:
            return
        cached = MEMORY_COVER_CACHE.get(self.model.cover_url)
        if cached is not None:
            self.cover_label.setPixmap(cached)
            return
        self.cover_requested.emit(self.model.cover_url)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_local_state(
        self,
        *,
        hidden: bool,
        watch_later: bool,
        actions_enabled: bool,
        liked: bool = False,
        disliked: bool = False,
    ) -> None:
        self.hide_button.setText("Unhide" if hidden else "Hide")
        self.watch_later_button.setText(
            "Remove saved" if watch_later else "Watch Later"
        )
        self.watch_later_button.setChecked(watch_later)
        self.like_button.setChecked(liked)
        self.dislike_button.setChecked(disliked)
        self.like_button.setText(
            "Remove like" if liked else "Move to Liked" if disliked else "Like"
        )
        self.dislike_button.setText(
            "Remove dislike"
            if disliked
            else "Move to Disliked"
            if liked
            else "Not for me"
        )
        taste_state = "liked" if liked else "disliked" if disliked else "unreviewed"
        self.setProperty("tasteState", taste_state)
        self.style().unpolish(self)
        self.style().polish(self)
        self.hide_button.setEnabled(actions_enabled)
        self.watch_later_button.setEnabled(actions_enabled)
        self.like_button.setEnabled(actions_enabled)
        self.dislike_button.setEnabled(actions_enabled)
        reason = "Connect or select a profile to manage local recommendation lists."
        self.hide_button.setToolTip("" if actions_enabled else reason)
        self.watch_later_button.setToolTip("" if actions_enabled else reason)
        self.like_button.setToolTip(
            (
                "Remove this like and return the anime to For You."
                if liked
                else "Move this anime to Liked and update the taste model."
            )
            if actions_enabled
            else reason
        )
        self.dislike_button.setToolTip(
            (
                "Remove this dislike and return the anime to For You."
                if disliked
                else "Move this anime to Disliked and update the taste model."
            )
            if actions_enabled
            else reason
        )

    def set_cover_visible(self, visible: bool) -> None:
        self.cover_label.setVisible(visible)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.selection_requested.emit(self.model)
        super().mousePressEvent(event)

    def focusInEvent(self, event: QFocusEvent) -> None:
        self.selection_requested.emit(self.model)
        super().focusInEvent(event)

    def set_cover_data(self, data: bytes) -> bool:
        source = QPixmap()
        if not source.loadFromData(data):
            self._show_placeholder()
            return False
        fitted = _fit_cover(source)
        self.cover_label.setPixmap(fitted)
        if self.model.cover_url:
            MEMORY_COVER_CACHE.put(self.model.cover_url, fitted)
        return True

    def _show_placeholder(self) -> None:
        source = cover_placeholder_pixmap()
        if source.isNull():
            source = QPixmap(COVER_WIDTH, COVER_HEIGHT)
            source.fill(Qt.GlobalColor.transparent)
        self.cover_label.setPixmap(_fit_cover(source))


def _fit_cover(source: QPixmap) -> QPixmap:
    scaled = source.scaled(
        COVER_WIDTH,
        COVER_HEIGHT,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    canvas = QPixmap(COVER_WIDTH, COVER_HEIGHT)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.drawPixmap(
        (COVER_WIDTH - scaled.width()) // 2,
        (COVER_HEIGHT - scaled.height()) // 2,
        scaled,
    )
    painter.end()
    return canvas
