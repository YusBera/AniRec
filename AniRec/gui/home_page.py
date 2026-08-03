"""Modern, visual dashboard backed by the latest persisted AniRec result."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..models import PipelineResult, Recommendation, UserProfile
from ..services import CoverImageResult, CoverImageService
from .resources import cover_placeholder_pixmap
from .texts import DASHBOARD_TEXT
from .workers import (
    CoverDownloadWorker,
    OperationAlreadyRunningError,
    WorkerController,
)


ACTION_GENERATE = "generate"
ACTION_SYNC = "sync"
ACTION_OPEN_RECOMMENDATIONS = "open-recommendations"
ACTION_VIEW_GENRES = "view-genres"
ACTION_OPEN_FOLDER = "open-folder"
HOME_COVER_WIDTH = 88
HOME_COVER_HEIGHT = 126


class RecentRecommendationCard(QFrame):
    opened = Signal()

    def __init__(self, recommendation: Recommendation, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.recommendation = recommendation
        self.setObjectName("homeRecommendationCard")
        self.setProperty("homeRecommendationCard", True)
        self.setMinimumWidth(250)
        self.setMaximumWidth(360)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        self.cover_label = QLabel()
        self.cover_label.setObjectName("homeRecommendationCover")
        self.cover_label.setFixedSize(HOME_COVER_WIDTH, HOME_COVER_HEIGHT)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._show_placeholder()
        layout.addWidget(self.cover_label)
        copy = QVBoxLayout()
        copy.setSpacing(5)
        title = QLabel(recommendation.anime.display_title)
        title.setObjectName("homeRecommendationTitle")
        title.setWordWrap(True)
        score = QLabel(f"{recommendation.match_score:.0f}% match")
        score.setObjectName("homeRecommendationScore")
        genres = QLabel(" · ".join(recommendation.anime.genres[:3]) or "Discover something new")
        genres.setObjectName("homeRecommendationMeta")
        genres.setWordWrap(True)
        open_button = QPushButton("View recommendation")
        open_button.setObjectName("homeRecommendationOpen")
        open_button.setProperty("buttonRole", "link")
        open_button.clicked.connect(self.opened.emit)
        copy.addWidget(score)
        copy.addWidget(title)
        copy.addWidget(genres)
        copy.addStretch()
        copy.addWidget(open_button)
        layout.addLayout(copy, 1)

    def set_cover_data(self, data: bytes) -> bool:
        source = QPixmap()
        if not source.loadFromData(data):
            return False
        self.cover_label.setPixmap(_fit_home_cover(source))
        return True

    def _show_placeholder(self) -> None:
        source = cover_placeholder_pixmap()
        if source.isNull():
            source = QPixmap(HOME_COVER_WIDTH, HOME_COVER_HEIGHT)
            source.fill(Qt.GlobalColor.transparent)
        self.cover_label.setPixmap(_fit_home_cover(source))


class HomePage(QWidget):
    generate_requested = Signal()
    sync_requested = Signal()
    open_recommendations_requested = Signal()
    view_genres_requested = Signal()
    open_folder_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        worker_controller: WorkerController | None = None,
        cover_service: CoverImageService | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page-home")
        self.setAccessibleName("Home page")
        self.worker_controller = worker_controller
        self.cover_service = cover_service or CoverImageService()
        self.profile: UserProfile | None = None
        self.result: PipelineResult | None = None
        self.running_operations = {ACTION_GENERATE: False, ACTION_SYNC: False}
        self.metric_values: dict[str, QLabel] = {}
        self.action_buttons: dict[str, QPushButton] = {}
        self.action_reasons: dict[str, QLabel] = {}
        self.genre_rows: list[tuple[QLabel, QProgressBar, QLabel]] = []
        self.recommendation_cards: list[RecentRecommendationCard] = []
        self._cover_urls: dict[str, str] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(12)

        header = QHBoxLayout()
        copy = QVBoxLayout()
        copy.setSpacing(4)
        title = QLabel("Welcome back")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Your anime taste, recommendations, and MAL library at a glance.")
        subtitle.setObjectName("pageDescription")
        copy.addWidget(title)
        copy.addWidget(subtitle)
        header.addLayout(copy, 1)
        self.activity_label = QLabel("Ready")
        self.activity_label.setObjectName("dashboardActivity")
        self.activity_label.setProperty("tone", "neutral")
        header.addWidget(self.activity_label, 0, Qt.AlignmentFlag.AlignBottom)
        outer.addLayout(header)

        self.empty_state_label = QLabel(DASHBOARD_TEXT.empty_state)
        self.empty_state_label.setObjectName("dashboardEmptyState")
        self.empty_state_label.setWordWrap(True)
        outer.addWidget(self.empty_state_label)

        scroll = QScrollArea()
        scroll.setObjectName("dashboardScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body.setObjectName("dashboardBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 4, 4, 4)
        body_layout.setSpacing(18)
        body_layout.addLayout(self._build_actions())
        body_layout.addLayout(self._build_metrics())
        body_layout.addLayout(self._build_insights())
        body_layout.addStretch()
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        # Compatibility projections kept off-layout for automation and accessibility APIs.
        self.genre_list = QListWidget(self)
        self.genre_list.hide()
        self.recommendation_list = QListWidget(self)
        self.recommendation_list.hide()

        self._connect_actions()
        if self.worker_controller is not None:
            self.worker_controller.result_ready.connect(self._on_worker_result)
            self.worker_controller.error_occurred.connect(self._on_worker_error)
        self.set_state(None, None)

    def _build_actions(self) -> QGridLayout:
        layout = QGridLayout()
        layout.setSpacing(10)
        actions = (
            (ACTION_GENERATE, "Refresh recommendations", "primary"),
            (ACTION_SYNC, "Update MAL data", "secondary"),
            (ACTION_OPEN_RECOMMENDATIONS, "Explore all", "secondary"),
            (ACTION_VIEW_GENRES, "Taste profile", "secondary"),
            (ACTION_OPEN_FOLDER, "Data folder", "ghost"),
        )
        for index, (action_id, text, role) in enumerate(actions):
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(3)
            button = QPushButton(text)
            button.setObjectName(f"dashboardAction-{action_id}")
            button.setProperty("dashboardAction", True)
            button.setProperty("buttonRole", role)
            button.setMinimumHeight(42)
            button.setAccessibleName(text)
            reason = QLabel()
            reason.setObjectName("dashboardActionReason")
            reason.setWordWrap(True)
            self.action_buttons[action_id] = button
            self.action_reasons[action_id] = reason
            container_layout.addWidget(button)
            container_layout.addWidget(reason)
            layout.addWidget(container, index // 3, index % 3)
        for column in range(3):
            layout.setColumnStretch(column, 1)
        return layout

    def _build_metrics(self) -> QGridLayout:
        layout = QGridLayout()
        layout.setSpacing(12)
        metrics = (
            ("username", "MAL profile"),
            ("completed", "Completed"),
            ("rated", "Rated"),
            ("genres", "Taste signals"),
            ("last_sync", "Last MAL update"),
            ("recommendations", "Recommendations"),
        )
        for index, (metric_id, label_text) in enumerate(metrics):
            card = QFrame()
            card.setObjectName("dashboardMetricCard")
            card.setProperty("metricCard", True)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 14, 16, 14)
            card_layout.setSpacing(5)
            label = QLabel(label_text)
            label.setObjectName("dashboardMetricLabel")
            value = QLabel("0")
            value.setObjectName("dashboardMetricValue")
            value.setAccessibleName(label_text)
            value.setWordWrap(True)
            card_layout.addWidget(label)
            card_layout.addWidget(value)
            self.metric_values[metric_id] = value
            layout.addWidget(card, index // 3, index % 3)
        for column in range(3):
            layout.setColumnStretch(column, 1)
        return layout

    def _build_insights(self) -> QGridLayout:
        layout = QGridLayout()
        layout.setSpacing(14)
        genre_panel = QFrame()
        genre_panel.setObjectName("dashboardPanel")
        genre_layout = QVBoxLayout(genre_panel)
        genre_layout.setContentsMargins(18, 18, 18, 18)
        genre_layout.setSpacing(10)
        genre_title = QLabel("Your strongest genres")
        genre_title.setObjectName("dashboardSectionTitle")
        genre_layout.addWidget(genre_title)
        for _index in range(5):
            row = QHBoxLayout()
            name = QLabel()
            name.setObjectName("dashboardGenreName")
            name.setMinimumWidth(82)
            bar = QProgressBar()
            bar.setObjectName("dashboardGenreBar")
            bar.setRange(0, 1000)
            bar.setTextVisible(False)
            score = QLabel()
            score.setObjectName("dashboardGenreScore")
            score.setMinimumWidth(44)
            row.addWidget(name)
            row.addWidget(bar, 1)
            row.addWidget(score)
            genre_layout.addLayout(row)
            self.genre_rows.append((name, bar, score))
        genre_layout.addStretch()

        recommendation_panel = QFrame()
        recommendation_panel.setObjectName("dashboardPanel")
        recommendation_layout = QVBoxLayout(recommendation_panel)
        recommendation_layout.setContentsMargins(18, 18, 18, 18)
        recommendation_layout.setSpacing(12)
        recommendation_header = QHBoxLayout()
        recommendation_title = QLabel("Recent recommendations")
        recommendation_title.setObjectName("dashboardSectionTitle")
        view_all = QPushButton("View all")
        view_all.setProperty("buttonRole", "link")
        view_all.clicked.connect(self.open_recommendations_requested.emit)
        recommendation_header.addWidget(recommendation_title)
        recommendation_header.addStretch()
        recommendation_header.addWidget(view_all)
        recommendation_layout.addLayout(recommendation_header)
        self.recommendation_grid = QGridLayout()
        self.recommendation_grid.setSpacing(10)
        recommendation_layout.addLayout(self.recommendation_grid)
        self.no_recommendations_label = QLabel(DASHBOARD_TEXT.no_recommendations)
        self.no_recommendations_label.setObjectName("dashboardNoRecommendations")
        recommendation_layout.addWidget(self.no_recommendations_label)
        recommendation_layout.addStretch()

        layout.addWidget(genre_panel, 0, 0)
        layout.addWidget(recommendation_panel, 0, 1)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 2)
        return layout

    def _connect_actions(self) -> None:
        self.action_buttons[ACTION_GENERATE].clicked.connect(self.generate_requested.emit)
        self.action_buttons[ACTION_SYNC].clicked.connect(self.sync_requested.emit)
        self.action_buttons[ACTION_OPEN_RECOMMENDATIONS].clicked.connect(
            self.open_recommendations_requested.emit
        )
        self.action_buttons[ACTION_VIEW_GENRES].clicked.connect(self.view_genres_requested.emit)
        self.action_buttons[ACTION_OPEN_FOLDER].clicked.connect(self.open_folder_requested.emit)

    def set_state(
        self,
        profile: UserProfile | None,
        result: PipelineResult | None,
    ) -> None:
        self.profile = profile
        self.result = result
        stats = dict(result.user_stats) if result else {}
        recommendations = result.recommendations if result else ()
        genres = result.genre_stats if result else ()

        self.empty_state_label.setVisible(profile is None)
        self.metric_values["username"].setText(
            profile.username if profile else DASHBOARD_TEXT.not_connected
        )
        self.metric_values["completed"].setText(str(stats.get("completed_count", 0)))
        self.metric_values["rated"].setText(str(stats.get("rated_count", 0)))
        self.metric_values["genres"].setText(str(len(genres)))
        self.metric_values["last_sync"].setText(_friendly_timestamp(profile.last_sync) if profile else DASHBOARD_TEXT.never)
        self.metric_values["recommendations"].setText(str(len(recommendations)))

        strongest = sorted(genres, key=lambda item: item.importance_score, reverse=True)[:5]
        self.genre_list.clear()
        self.genre_list.addItems(
            [f"{item.genre} — {item.importance_score:.1f}" for item in strongest]
            or [DASHBOARD_TEXT.no_genres]
        )
        maximum = max((item.importance_score for item in strongest), default=1.0)
        for index, (name, bar, score) in enumerate(self.genre_rows):
            visible = index < len(strongest)
            name.setVisible(visible)
            bar.setVisible(visible)
            score.setVisible(visible)
            if visible:
                item = strongest[index]
                name.setText(item.genre)
                bar.setValue(round(max(0.0, item.importance_score) / max(maximum, 0.01) * 1000))
                score.setText(f"{item.importance_score:.1f}")

        self.recommendation_list.clear()
        self.recommendation_list.addItems(
            [item.anime.display_title for item in recommendations[:5]]
            or [DASHBOARD_TEXT.no_recommendations]
        )
        self._set_recent_recommendations(recommendations[:4])
        self._update_actions()

    def _set_recent_recommendations(
        self, recommendations: tuple[Recommendation, ...] | list[Recommendation]
    ) -> None:
        while self.recommendation_grid.count():
            item = self.recommendation_grid.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.recommendation_cards.clear()
        self._cover_urls.clear()
        self.no_recommendations_label.setVisible(not recommendations)
        for index, recommendation in enumerate(recommendations):
            card = RecentRecommendationCard(recommendation)
            card.opened.connect(self.open_recommendations_requested.emit)
            self.recommendation_grid.addWidget(card, index // 2, index % 2)
            self.recommendation_cards.append(card)
            url = recommendation.anime.cover_url
            if url:
                digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
                key = f"cover-home:{digest}"
                self._cover_urls[key] = url
                if self.worker_controller is not None:
                    try:
                        self.worker_controller.start(
                            key, CoverDownloadWorker(self.cover_service, url)
                        )
                    except OperationAlreadyRunningError:
                        pass

    def set_operation_running(self, action_id: str, is_running: bool) -> None:
        if action_id in self.running_operations:
            self.running_operations[action_id] = is_running
            if action_id == ACTION_SYNC and is_running:
                self.show_activity(
                    "Updating your MAL library…",
                    tone="busy",
                )
            elif action_id == ACTION_GENERATE and is_running:
                self.show_activity(
                    "Building a fresh recommendation feed…",
                    tone="busy",
                )
            elif not is_running and self.activity_label.property("tone") == "busy":
                self.show_activity("Operation finished", tone="neutral")
            self._update_actions()

    def show_activity(self, message: str, *, tone: str = "neutral") -> None:
        self.activity_label.setText(message)
        self.activity_label.setProperty("tone", tone)
        self.activity_label.style().unpolish(self.activity_label)
        self.activity_label.style().polish(self.activity_label)

    def _update_actions(self) -> None:
        profile = self.profile
        result = self.result
        has_profile = profile is not None
        has_sync = bool(profile and profile.last_sync)
        has_recommendations = bool(result and result.recommendations)
        has_genres = bool(result and result.genre_stats)
        has_folder = bool(profile and profile.output_dir and Path(profile.output_dir).is_dir())
        self._set_action(
            ACTION_GENERATE,
            has_sync,
            DASHBOARD_TEXT.sync_required if has_profile else DASHBOARD_TEXT.profile_required,
        )
        self._set_action(ACTION_SYNC, has_profile, DASHBOARD_TEXT.profile_required)
        self._set_action(ACTION_OPEN_RECOMMENDATIONS, has_recommendations, DASHBOARD_TEXT.recommendations_required)
        self._set_action(ACTION_VIEW_GENRES, has_genres, DASHBOARD_TEXT.genres_required)
        self._set_action(ACTION_OPEN_FOLDER, has_folder, DASHBOARD_TEXT.folder_required)

    def _set_action(self, action_id: str, available: bool, unavailable_reason: str) -> None:
        running = self.running_operations.get(action_id, False)
        reason = DASHBOARD_TEXT.operation_running if running else ("" if available else unavailable_reason)
        button = self.action_buttons[action_id]
        button.setEnabled(available and not running)
        button.setToolTip(reason)
        if action_id == ACTION_SYNC:
            button.setText("Updating MAL…" if running else "Update MAL data")
        elif action_id == ACTION_GENERATE:
            button.setText("Generating…" if running else "Refresh recommendations")
        self.action_reasons[action_id].setText(reason)
        self.action_reasons[action_id].setVisible(bool(reason))

    def _on_worker_result(self, operation_key: str, result: object) -> None:
        url = self._cover_urls.pop(operation_key, None)
        if url is None or not isinstance(result, CoverImageResult):
            return
        for card in self.recommendation_cards:
            if card.recommendation.anime.cover_url == url:
                card.set_cover_data(result.data)

    def _on_worker_error(self, operation_key: str, _error: object) -> None:
        self._cover_urls.pop(operation_key, None)


def _fit_home_cover(source: QPixmap) -> QPixmap:
    scaled = source.scaled(
        HOME_COVER_WIDTH,
        HOME_COVER_HEIGHT,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    canvas = QPixmap(HOME_COVER_WIDTH, HOME_COVER_HEIGHT)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.drawPixmap(
        (HOME_COVER_WIDTH - scaled.width()) // 2,
        (HOME_COVER_HEIGHT - scaled.height()) // 2,
        scaled,
    )
    painter.end()
    return canvas


def _friendly_timestamp(value: str | None) -> str:
    if not value:
        return DASHBOARD_TEXT.never
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    return parsed.astimezone().strftime("%d %b %Y · %H:%M")
