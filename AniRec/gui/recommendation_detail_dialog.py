"""Reusable, scrollable anime recommendation detail dialog."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .recommendation_card import open_mal_url
from .recommendation_view_model import RecommendationViewModel
from .resources import cover_placeholder_pixmap


DETAIL_COVER_WIDTH = 300
DETAIL_COVER_HEIGHT = 450
NO_ALTERNATIVE_TITLES = "No alternative titles are available."
NO_GENRE_CONTRIBUTIONS = "No genre contribution breakdown is available."


class RecommendationDetailDialog(QDialog):
    cover_requested = Signal(str)
    hide_requested = Signal(object)
    watch_later_requested = Signal(object)
    liked_requested = Signal(object)
    disliked_requested = Signal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        mal_opener: Callable[[QUrl], bool] = QDesktopServices.openUrl,
    ) -> None:
        super().__init__(parent)
        self.model: RecommendationViewModel | None = None
        self._mal_opener = mal_opener
        self.setObjectName("recommendationDetailDialog")
        self.setWindowTitle("Anime Details")
        self.setModal(False)
        self.resize(860, 700)
        self.setMinimumSize(660, 520)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("recommendationDetailScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("recommendationDetailContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(4, 4, 12, 4)
        content_layout.setSpacing(16)

        hero = QHBoxLayout()
        hero.setSpacing(20)
        self.cover_label = QLabel()
        self.cover_label.setObjectName("recommendationDetailCover")
        self.cover_label.setFixedSize(DETAIL_COVER_WIDTH, DETAIL_COVER_HEIGHT)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._show_placeholder()
        hero.addWidget(self.cover_label, 0, Qt.AlignmentFlag.AlignTop)

        facts = QVBoxLayout()
        facts.setSpacing(8)
        self.title_label = self._label("", "recommendationDetailTitle", word_wrap=True)
        self.secondary_title_label = self._label(
            "", "recommendationDetailSecondaryTitle", word_wrap=True
        )
        self.alternative_titles_label = self._label(
            "", "recommendationDetailAlternatives", word_wrap=True
        )
        self.personal_match_label = self._label("", "personalMatchLabel")
        self.mal_score_label = self._label("", "recommendationDetailMalScore")
        self.genres_label = self._label("", "recommendationDetailGenres", word_wrap=True)
        self.episodes_label = self._label("", "recommendationDetailEpisodes")
        self.status_label = self._label("", "recommendationDetailStatus")
        self.year_label = self._label("", "recommendationDetailYear")
        self.dates_label = self._label("", "recommendationDetailDates", word_wrap=True)
        self.mal_button = QPushButton("Open on MyAnimeList")
        self.mal_button.setObjectName("recommendationDetailMalButton")
        self.mal_button.clicked.connect(self._open_mal)
        self.watch_later_button = QPushButton("Watch Later")
        self.watch_later_button.setObjectName("recommendationDetailWatchLaterButton")
        self.watch_later_button.setCheckable(True)
        self.watch_later_button.clicked.connect(
            lambda: self.model is not None
            and self.watch_later_requested.emit(self.model)
        )
        self.like_button = QPushButton("Like")
        self.like_button.setObjectName("recommendationDetailLikeButton")
        self.like_button.setProperty("feedback", "liked")
        self.like_button.setCheckable(True)
        self.like_button.clicked.connect(
            lambda: self.model is not None and self.liked_requested.emit(self.model)
        )
        self.dislike_button = QPushButton("Not for me")
        self.dislike_button.setObjectName("recommendationDetailDislikeButton")
        self.dislike_button.setProperty("feedback", "disliked")
        self.dislike_button.setCheckable(True)
        self.dislike_button.clicked.connect(
            lambda: self.model is not None and self.disliked_requested.emit(self.model)
        )
        self.hide_button = QPushButton("Hide")
        self.hide_button.setObjectName("recommendationDetailHideButton")
        self.hide_button.clicked.connect(
            lambda: self.model is not None and self.hide_requested.emit(self.model)
        )
        for widget in (
            self.title_label,
            self.secondary_title_label,
            self.alternative_titles_label,
            self.personal_match_label,
            self.mal_score_label,
            self.genres_label,
            self.episodes_label,
            self.status_label,
            self.year_label,
            self.dates_label,
            self.like_button,
            self.dislike_button,
            self.watch_later_button,
            self.hide_button,
            self.mal_button,
        ):
            facts.addWidget(widget)
        facts.addStretch()
        hero.addLayout(facts, 1)
        content_layout.addLayout(hero)

        self.synopsis_label = self._section(
            content_layout, "Synopsis", "recommendationDetailSynopsis"
        )
        self.reason_label = self._section(
            content_layout, "Why this was recommended", "recommendationDetailReason"
        )
        self.contributions_label = self._section(
            content_layout, "Contributing genres", "recommendationDetailContributions"
        )
        content_layout.addStretch()
        self.scroll.setWidget(content)
        root.addWidget(self.scroll, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        root.addWidget(buttons)

    @staticmethod
    def _label(text: str, object_name: str, *, word_wrap: bool = False) -> QLabel:
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setWordWrap(word_wrap)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    @classmethod
    def _section(cls, layout: QVBoxLayout, title: str, object_name: str) -> QLabel:
        heading = QLabel(title)
        heading.setObjectName("recommendationDetailSectionTitle")
        body = cls._label("", object_name, word_wrap=True)
        layout.addWidget(heading)
        layout.addWidget(body)
        return body

    def set_model(self, model: RecommendationViewModel) -> None:
        self.model = model
        self.setWindowTitle(f"{model.display_title} — Anime Details")
        self.setAccessibleName(f"Details for {model.display_title}")
        self.title_label.setText(model.display_title)
        self.secondary_title_label.setText(model.secondary_title or "")
        self.secondary_title_label.setVisible(bool(model.secondary_title))
        self.alternative_titles_label.setText(
            "Alternative titles: " + " · ".join(model.alternative_titles)
            if model.alternative_titles
            else NO_ALTERNATIVE_TITLES
        )
        self.personal_match_label.setText(model.personal_match_text)
        self.mal_score_label.setText(model.mal_score_text)
        self.genres_label.setText(f"Genres: {model.genres_text}")
        self.episodes_label.setText(f"Episodes: {model.episodes_text}")
        self.status_label.setText(f"Status: {model.status}")
        self.year_label.setText(f"Airing year: {model.year_text}")
        self.dates_label.setText(
            f"Aired: {model.start_date} — {model.end_date}"
        )
        self.synopsis_label.setText(model.synopsis)
        self.reason_label.setText(model.reason)
        self.contributions_label.setText(self._contributions_text(model))
        self.mal_button.setEnabled(bool(model.mal_url))
        self._show_placeholder()
        cover_url = model.large_cover_url or model.cover_url
        if cover_url:
            self.cover_requested.emit(cover_url)

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
        self.hide_button.setEnabled(actions_enabled)
        self.watch_later_button.setEnabled(actions_enabled)
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
        self.like_button.setEnabled(actions_enabled)
        self.dislike_button.setEnabled(actions_enabled)

    def set_cover_visible(self, visible: bool) -> None:
        self.cover_label.setVisible(visible)

    @staticmethod
    def _contributions_text(model: RecommendationViewModel) -> str:
        if model.genre_contributions:
            return "\n".join(
                f"{genre}: {score:+.2f}" for genre, score in model.genre_contributions
            )
        if model.contributing_genres:
            return " · ".join(model.contributing_genres)
        return NO_GENRE_CONTRIBUTIONS

    def set_cover_data(self, data: bytes) -> bool:
        source = QPixmap()
        if not source.loadFromData(data):
            self._show_placeholder()
            return False
        self.cover_label.setPixmap(_fit_detail_cover(source))
        return True

    def _show_placeholder(self) -> None:
        source = cover_placeholder_pixmap()
        if source.isNull():
            source = QPixmap(DETAIL_COVER_WIDTH, DETAIL_COVER_HEIGHT)
            source.fill(Qt.GlobalColor.transparent)
        self.cover_label.setPixmap(_fit_detail_cover(source))

    def _open_mal(self) -> None:
        if self.model is not None:
            open_mal_url(self.model.mal_url, opener=self._mal_opener)


def _fit_detail_cover(source: QPixmap) -> QPixmap:
    scaled = source.scaled(
        DETAIL_COVER_WIDTH,
        DETAIL_COVER_HEIGHT,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    canvas = QPixmap(DETAIL_COVER_WIDTH, DETAIL_COVER_HEIGHT)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.drawPixmap(
        (DETAIL_COVER_WIDTH - scaled.width()) // 2,
        (DETAIL_COVER_HEIGHT - scaled.height()) // 2,
        scaled,
    )
    painter.end()
    return canvas
