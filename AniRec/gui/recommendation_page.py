"""Filterable card/table explorer for persisted anime recommendations."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import QEvent, QPoint, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models import Recommendation
from ..services import (
    CoverImageResult,
    CoverImageService,
    RecommendationLocalState,
    RecommendationStateService,
)
from .recommendation_card import CARD_WIDTH, RecommendationCard
from .recommendation_detail_dialog import RecommendationDetailDialog
from .recommendation_view_model import RecommendationViewModel, recommendation_view_models
from .workers import CoverDownloadWorker, OperationAlreadyRunningError, WorkerController


class RecommendationViewMode(str, Enum):
    CARDS = "cards"
    TABLE = "table"


class RecommendationSortMode(str, Enum):
    PERSONAL_MATCH = "personal-match"
    MAL_SCORE = "mal-score"
    YEAR = "year"
    ALPHABETICAL = "alphabetical"


@dataclass(frozen=True)
class RecommendationFilters:
    genre: str | None = None
    minimum_mal_score: float | None = None
    status: str | None = None
    minimum_episodes: int | None = None
    maximum_episodes: int | None = None


def filter_and_sort_recommendations(
    models: tuple[RecommendationViewModel, ...] | list[RecommendationViewModel],
    filters: RecommendationFilters = RecommendationFilters(),
    sort_mode: RecommendationSortMode = RecommendationSortMode.PERSONAL_MATCH,
) -> tuple[RecommendationViewModel, ...]:
    """Return a stable, missing-last projection shared by cards and the table."""

    genre = filters.genre.casefold() if filters.genre else None
    status = filters.status.casefold() if filters.status else None
    filtered = []
    for model in models:
        if genre is not None and genre not in {item.casefold() for item in model.genres}:
            continue
        if filters.minimum_mal_score is not None and (
            model.mal_score is None or model.mal_score < filters.minimum_mal_score
        ):
            continue
        if status is not None and model.status.casefold() != status:
            continue
        if filters.minimum_episodes is not None and (
            model.episodes is None or model.episodes < filters.minimum_episodes
        ):
            continue
        if filters.maximum_episodes is not None and (
            model.episodes is None or model.episodes > filters.maximum_episodes
        ):
            continue
        filtered.append(model)

    if sort_mode is RecommendationSortMode.PERSONAL_MATCH:
        key = lambda item: (not item.personal_match_available, -item.personal_match)
    elif sort_mode is RecommendationSortMode.MAL_SCORE:
        key = lambda item: (item.mal_score is None, -(item.mal_score or 0.0))
    elif sort_mode is RecommendationSortMode.YEAR:
        key = lambda item: (item.year is None, -(item.year or 0))
    else:
        key = lambda item: item.display_title.casefold()
    return tuple(sorted(filtered, key=key))


def recommendation_key(model: RecommendationViewModel, source_index: int) -> str:
    if model.mal_id is not None:
        return f"mal:{model.mal_id}"
    return f"local:{source_index}:{model.display_title.casefold()}"


class RecommendationExplorerPage(QWidget):
    """One query state rendered as either accessible cards or a compact table."""

    details_requested = Signal(object)
    selection_changed = Signal(object)
    show_hidden_changed = Signal(bool)
    feedback_changed = Signal(object)
    more_requested = Signal()
    refill_requested = Signal()
    MAX_COVER_REQUESTS_PER_PASS = 6

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        worker_controller: WorkerController | None = None,
        cover_service: CoverImageService | None = None,
        state_service: RecommendationStateService | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page-recommendations")
        self.setAccessibleName("Recommendations page")
        self.worker_controller = worker_controller
        self.cover_service = cover_service or CoverImageService()
        self.state_service = state_service or RecommendationStateService()
        self.profile_id: str | None = None
        self.local_state = RecommendationLocalState()
        self._models: tuple[RecommendationViewModel, ...] = ()
        self._visible_models: tuple[RecommendationViewModel, ...] = ()
        self._key_by_model: dict[int, str] = {}
        self._model_by_key: dict[str, RecommendationViewModel] = {}
        self._cards_by_key: dict[str, RecommendationCard] = {}
        self._selected_key: str | None = None
        self._view_mode = RecommendationViewMode.CARDS
        self.show_covers = True
        self._cover_attempted: set[str] = set()
        self._cover_operation_urls: dict[str, str] = {}
        self._cover_data_by_url: dict[str, bytes] = {}
        self.detail_dialog: RecommendationDetailDialog | None = None
        self._more_available = False
        self._more_running = False
        self._more_unavailable_reason = ""
        self._build_ui()
        self._update_feedback_summary()
        if self.worker_controller is not None:
            self.worker_controller.result_ready.connect(self._on_worker_result)
            self.worker_controller.error_occurred.connect(self._on_worker_error)
        self.set_recommendations(())

    @property
    def visible_models(self) -> tuple[RecommendationViewModel, ...]:
        return self._visible_models

    @property
    def selected_key(self) -> str | None:
        return self._selected_key

    @property
    def view_mode(self) -> RecommendationViewMode:
        return self._view_mode

    def set_recommendations(
        self,
        recommendations: tuple[Recommendation, ...] | list[Recommendation],
    ) -> None:
        previous_key = self._selected_key
        self._models = recommendation_view_models(recommendations)
        self._key_by_model = {
            id(model): recommendation_key(model, index)
            for index, model in enumerate(self._models)
        }
        self._model_by_key = {
            self._key_by_model[id(model)]: model for model in self._models
        }
        self._selected_key = previous_key if previous_key in self._model_by_key else None
        self._populate_filter_options()
        self._apply_query()

    def set_more_available(self, available: bool, reason: str = "") -> None:
        self._more_available = bool(available)
        self._more_unavailable_reason = reason
        self._update_more_actions()

    def set_more_running(self, running: bool) -> None:
        self._more_running = bool(running)
        self._update_more_actions()
        self.more_button.setText("Finding new anime…" if running else "Recommend 5 more")
        self.refill_button.setText(
            "Finding 10 new anime…" if running else "Recommend 10 new anime"
        )

    def _update_more_actions(self) -> None:
        enabled = self._more_available and not self._more_running
        self.more_button.setEnabled(enabled)
        self.refill_button.setEnabled(enabled)
        unavailable = self._more_unavailable_reason or "Generate recommendations first."
        self.more_button.setToolTip(
            "Generate five unseen picks using your latest feedback."
            if self._more_available
            else unavailable
        )
        self.refill_button.setToolTip(
            "Generate ten unseen picks using your latest feedback."
            if self._more_available
            else unavailable
        )

    def set_profile(self, profile_id: str | None) -> None:
        self.profile_id = profile_id
        self.local_state = (
            self.state_service.load(profile_id)
            if profile_id is not None
            else RecommendationLocalState()
        )
        self.show_hidden_checkbox.blockSignals(True)
        self.show_hidden_checkbox.setChecked(self.local_state.show_hidden)
        self.show_hidden_checkbox.setEnabled(profile_id is not None)
        self.show_hidden_checkbox.blockSignals(False)
        self._update_feedback_summary()
        self._apply_query()

    def set_show_hidden_preference(self, show_hidden: bool) -> None:
        if self.profile_id is None:
            return
        self.local_state = self.state_service.set_show_hidden(
            self.profile_id, show_hidden
        )
        self.show_hidden_checkbox.blockSignals(True)
        self.show_hidden_checkbox.setChecked(self.local_state.show_hidden)
        self.show_hidden_checkbox.blockSignals(False)
        self.show_hidden_changed.emit(self.local_state.show_hidden)
        self._apply_query()

    def set_view_mode(self, mode: RecommendationViewMode | str) -> None:
        resolved = RecommendationViewMode(mode)
        self._view_mode = resolved
        self.cards_button.setChecked(resolved is RecommendationViewMode.CARDS)
        self.table_button.setChecked(resolved is RecommendationViewMode.TABLE)
        self._show_current_view()
        self._restore_selection()
        self._update_selected_actions_visibility()
        if resolved is RecommendationViewMode.CARDS:
            QTimer.singleShot(0, self._request_visible_covers)

    def set_default_sort(self, sort_mode: RecommendationSortMode | str) -> None:
        resolved = RecommendationSortMode(sort_mode)
        index = self.sort_combo.findData(resolved.value)
        if index >= 0:
            self.sort_combo.setCurrentIndex(index)

    def set_show_covers(self, show_covers: bool) -> None:
        self.show_covers = bool(show_covers)
        for card in self._cards_by_key.values():
            card.set_cover_visible(self.show_covers)
        if self.detail_dialog is not None:
            self.detail_dialog.set_cover_visible(self.show_covers)
        if self.show_covers:
            self._schedule_visible_covers()

    def clear_filters(self) -> None:
        for widget in (
            self.genre_filter,
            self.mal_score_filter,
            self.status_filter,
            self.minimum_episodes_filter,
            self.maximum_episodes_filter,
        ):
            widget.blockSignals(True)
        self.genre_filter.setCurrentIndex(0)
        self.mal_score_filter.setValue(0.0)
        self.status_filter.setCurrentIndex(0)
        self.minimum_episodes_filter.setValue(0)
        self.maximum_episodes_filter.setValue(0)
        for widget in (
            self.genre_filter,
            self.mal_score_filter,
            self.status_filter,
            self.minimum_episodes_filter,
            self.maximum_episodes_filter,
        ):
            widget.blockSignals(False)
        self._apply_query()

    def select_key(self, key: str | None) -> None:
        if key is not None and key not in self._model_by_key:
            return
        self._selected_key = key
        self._restore_selection()
        self._update_local_action_state()
        self.selection_changed.emit(self.selected_model())

    def selected_model(self) -> RecommendationViewModel | None:
        return self._model_by_key.get(self._selected_key or "")

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(12)

        self.hero = QFrame()
        self.hero.setObjectName("recommendationHero")
        hero_layout = QHBoxLayout(self.hero)
        hero_layout.setContentsMargins(24, 22, 24, 22)
        hero_layout.setSpacing(24)
        heading_copy = QVBoxLayout()
        heading_copy.setSpacing(6)
        eyebrow = QLabel("PERSONAL DISCOVERY")
        eyebrow.setObjectName("recommendationEyebrow")
        title = QLabel("Find your next favorite")
        title.setObjectName("recommendationHeroTitle")
        title.setAccessibleName("Your recommendations heading")
        description = QLabel(
            "Review each pick once. AniRec learns from every decision and reshapes "
            "the remaining feed in real time."
        )
        description.setObjectName("recommendationHeroDescription")
        description.setWordWrap(True)
        heading_copy.addWidget(eyebrow)
        heading_copy.addWidget(title)
        heading_copy.addWidget(description)

        self.feedback_summary_label = QLabel()
        self.feedback_summary_label.setObjectName("recommendationFeedbackSummary")
        self.feedback_summary_label.setWordWrap(True)
        heading_copy.addWidget(self.feedback_summary_label)
        hero_layout.addLayout(heading_copy, 1)

        hero_actions = QVBoxLayout()
        hero_actions.setSpacing(8)
        hero_actions.addStretch()
        action_caption = QLabel("READY FOR SOMETHING NEW?")
        action_caption.setObjectName("recommendationActionCaption")
        action_caption.setAlignment(Qt.AlignmentFlag.AlignRight)
        hero_actions.addWidget(action_caption)

        # Kept as a compatibility hook for earlier local state tests; visible
        # navigation is provided by the library tabs below.
        self.taste_folders_button = QPushButton("Taste folders · 0 liked · 0 disliked")
        self.taste_folders_button.setObjectName("recommendationTasteFoldersButton")
        self.taste_folders_button.setVisible(False)
        self.taste_folders_menu = QMenu(self.taste_folders_button)
        self.recommendations_folder_action = self.taste_folders_menu.addAction(
            "Recommendations"
        )
        self.liked_folder_action = self.taste_folders_menu.addAction("Liked (0)")
        self.disliked_folder_action = self.taste_folders_menu.addAction("Disliked (0)")
        self.taste_folders_button.setMenu(self.taste_folders_menu)
        self.more_button = QPushButton("Recommend 5 more")
        self.more_button.setObjectName("recommendationMoreButton")
        self.more_button.setProperty("buttonRole", "primary")
        self.more_button.setMinimumSize(190, 46)
        self.more_button.setEnabled(False)
        hero_actions.addWidget(self.more_button)
        hero_layout.addLayout(hero_actions)
        root.addWidget(self.hero)

        self.filter_controls = QFrame()
        self.filter_controls.setObjectName("recommendationControls")
        controls_layout = QGridLayout(self.filter_controls)
        controls_layout.setContentsMargins(12, 12, 12, 12)
        controls_layout.setHorizontalSpacing(10)
        controls_layout.setVerticalSpacing(7)

        self.genre_filter = QComboBox()
        self.genre_filter.setObjectName("recommendationGenreFilter")
        self.mal_score_filter = QDoubleSpinBox()
        self.mal_score_filter.setObjectName("recommendationMalScoreFilter")
        self.mal_score_filter.setRange(0.0, 10.0)
        self.mal_score_filter.setDecimals(1)
        self.mal_score_filter.setSingleStep(0.5)
        self.mal_score_filter.setSpecialValueText("Any")
        self.status_filter = QComboBox()
        self.status_filter.setObjectName("recommendationStatusFilter")
        self.minimum_episodes_filter = self._episode_spinbox("recommendationMinimumEpisodesFilter")
        self.maximum_episodes_filter = self._episode_spinbox("recommendationMaximumEpisodesFilter")
        self.sort_combo = QComboBox()
        self.sort_combo.setObjectName("recommendationSort")
        self.sort_combo.addItem("Personal match", RecommendationSortMode.PERSONAL_MATCH.value)
        self.sort_combo.addItem("MAL score", RecommendationSortMode.MAL_SCORE.value)
        self.sort_combo.addItem("Airing year", RecommendationSortMode.YEAR.value)
        self.sort_combo.addItem("Alphabetical", RecommendationSortMode.ALPHABETICAL.value)

        widgets = (
            ("Genre", self.genre_filter),
            ("Minimum MAL score", self.mal_score_filter),
            ("Airing status", self.status_filter),
            ("Minimum episodes", self.minimum_episodes_filter),
            ("Maximum episodes", self.maximum_episodes_filter),
            ("Sort by", self.sort_combo),
        )
        for index, (label_text, widget) in enumerate(widgets):
            row = (index // 3) * 2
            column = index % 3
            label = QLabel(label_text)
            label.setObjectName("recommendationFilterLabel")
            controls_layout.addWidget(label, row, column)
            controls_layout.addWidget(widget, row + 1, column)
        self.filter_controls.setVisible(False)

        self.library_bar = QFrame()
        self.library_bar.setObjectName("recommendationLibraryBar")
        library_layout = QVBoxLayout(self.library_bar)
        library_layout.setContentsMargins(8, 8, 8, 8)
        library_layout.setSpacing(6)
        tab_row = QHBoxLayout()
        tab_row.setSpacing(6)
        self.library_tabs: dict[str, QPushButton] = {}
        self.library_tab_group = QButtonGroup(self)
        self.library_tab_group.setExclusive(True)
        for state, label in (
            ("all", "For You"),
            ("liked", "Liked"),
            ("disliked", "Disliked"),
            ("watch-later", "Watch Later"),
        ):
            button = QPushButton(f"{label}  0")
            button.setObjectName(f"recommendationLibraryTab-{state}")
            button.setProperty("libraryTab", True)
            button.setCheckable(True)
            button.setAccessibleName(f"Open {label} recommendation collection")
            button.clicked.connect(
                lambda _checked=False, selected_state=state: self._select_state_filter(
                    selected_state
                )
            )
            self.library_tab_group.addButton(button)
            self.library_tabs[state] = button
            tab_row.addWidget(button)
        self.library_tabs["all"].setChecked(True)
        tab_row.addStretch()
        library_layout.addLayout(tab_row)

        view_row = QHBoxLayout()
        view_row.setSpacing(6)
        view_row.addStretch()
        self.result_count_label = QLabel()
        self.result_count_label.setObjectName("recommendationResultCount")
        view_row.addWidget(self.result_count_label)
        view_row.addStretch()
        self.filter_toggle_button = QPushButton("Filters")
        self.filter_toggle_button.setObjectName("recommendationFilterToggle")
        self.filter_toggle_button.setProperty("buttonRole", "ghost")
        self.filter_toggle_button.setCheckable(True)
        view_row.addWidget(self.filter_toggle_button)
        self.state_filter = QComboBox()
        self.state_filter.setObjectName("recommendationStateFilter")
        self.state_filter.addItem("Recommendations", "all")
        self.state_filter.addItem("Watch Later", "watch-later")
        self.state_filter.addItem("Liked folder", "liked")
        self.state_filter.addItem("Disliked folder", "disliked")
        self.state_filter.setVisible(False)
        self.show_hidden_checkbox = QCheckBox("Show hidden")
        self.show_hidden_checkbox.setObjectName("recommendationShowHidden")
        self.show_hidden_checkbox.setEnabled(False)
        view_row.addWidget(self.show_hidden_checkbox)
        self.cards_button = QPushButton("Cards")
        self.cards_button.setObjectName("recommendationCardsViewButton")
        self.cards_button.setProperty("viewToggle", True)
        self.cards_button.setCheckable(True)
        self.table_button = QPushButton("Table")
        self.table_button.setObjectName("recommendationTableViewButton")
        self.table_button.setProperty("viewToggle", True)
        self.table_button.setCheckable(True)
        group = QButtonGroup(self)
        group.setExclusive(True)
        group.addButton(self.cards_button)
        group.addButton(self.table_button)
        self.cards_button.setChecked(True)
        view_row.addWidget(self.cards_button)
        view_row.addWidget(self.table_button)
        library_layout.addLayout(view_row)
        root.addWidget(self.library_bar)
        root.addWidget(self.filter_controls)

        self.selected_actions_frame = QFrame()
        self.selected_actions_frame.setObjectName("recommendationSelectedActions")
        selected_actions = QHBoxLayout(self.selected_actions_frame)
        selected_actions.setContentsMargins(12, 8, 12, 8)
        selected_actions.setSpacing(8)
        selected_label = QLabel("Selected anime")
        selected_label.setObjectName("recommendationSelectedLabel")
        selected_actions.addWidget(selected_label)
        selected_actions.addStretch()
        self.watch_later_selected_button = QPushButton("Watch Later")
        self.watch_later_selected_button.setObjectName("recommendationWatchLaterSelected")
        self.hide_selected_button = QPushButton("Hide")
        self.hide_selected_button.setObjectName("recommendationHideSelected")
        self.like_selected_button = QPushButton("Like")
        self.like_selected_button.setObjectName("recommendationLikeSelected")
        self.like_selected_button.setProperty("feedback", "liked")
        self.like_selected_button.setCheckable(True)
        self.dislike_selected_button = QPushButton("Not for me")
        self.dislike_selected_button.setObjectName("recommendationDislikeSelected")
        self.dislike_selected_button.setProperty("feedback", "disliked")
        self.dislike_selected_button.setCheckable(True)
        selected_actions.addWidget(self.like_selected_button)
        selected_actions.addWidget(self.dislike_selected_button)
        selected_actions.addWidget(self.watch_later_selected_button)
        selected_actions.addWidget(self.hide_selected_button)
        self.selected_actions_frame.setVisible(False)
        root.addWidget(self.selected_actions_frame)

        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("recommendationContentStack")
        self.card_scroll = QScrollArea()
        self.card_scroll.setObjectName("recommendationCardScroll")
        self.card_scroll.setWidgetResizable(True)
        self.card_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.card_container = QWidget()
        self.card_container.setObjectName("recommendationCardContainer")
        self.card_layout = QGridLayout(self.card_container)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setSpacing(16)
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.card_scroll.setWidget(self.card_container)
        self.card_scroll.viewport().installEventFilter(self)
        self.card_scroll.verticalScrollBar().valueChanged.connect(
            lambda _value: self._schedule_visible_covers()
        )

        self.table = QTableWidget(0, 8)
        self.table.setObjectName("recommendationTable")
        self.table.setHorizontalHeaderLabels(
            ("Rank", "Title", "Personal match", "MAL score", "Genres", "Year", "Status", "Episodes")
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.table.itemDoubleClicked.connect(lambda _item: self._open_selected_details())

        self.empty_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.addStretch()
        self.empty_panel = QFrame()
        self.empty_panel.setObjectName("recommendationEmptyPanel")
        self.empty_panel.setMaximumWidth(680)
        panel_layout = QVBoxLayout(self.empty_panel)
        panel_layout.setContentsMargins(40, 34, 40, 34)
        panel_layout.setSpacing(12)
        self.empty_icon_label = QLabel("✦")
        self.empty_icon_label.setObjectName("recommendationEmptyIcon")
        self.empty_icon_label.setFixedSize(56, 56)
        self.empty_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_title_label = QLabel("Your feed is waiting")
        self.empty_title_label.setObjectName("recommendationEmptyTitle")
        self.empty_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label = QLabel()
        self.empty_label.setObjectName("recommendationEmptyState")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.clear_filters_button = QPushButton("Clear filters")
        self.clear_filters_button.setObjectName("recommendationClearFiltersButton")
        self.clear_filters_button.setMaximumWidth(180)
        self.refill_button = QPushButton("Recommend 10 new anime")
        self.refill_button.setObjectName("recommendationRefillButton")
        self.refill_button.setProperty("buttonRole", "primary")
        self.refill_button.setMaximumWidth(240)
        self.refill_button.setVisible(False)
        self.refill_button.setEnabled(False)
        self.browse_liked_button = QPushButton("Review liked anime")
        self.browse_liked_button.setObjectName("recommendationBrowseLikedButton")
        self.browse_liked_button.setProperty("buttonRole", "secondary")
        self.browse_liked_button.setMaximumWidth(220)
        self.browse_liked_button.setVisible(False)
        empty_actions = QHBoxLayout()
        empty_actions.setSpacing(8)
        empty_actions.addStretch()
        empty_actions.addWidget(self.clear_filters_button)
        empty_actions.addWidget(self.browse_liked_button)
        empty_actions.addWidget(self.refill_button)
        empty_actions.addStretch()
        panel_layout.addWidget(
            self.empty_icon_label, 0, Qt.AlignmentFlag.AlignHCenter
        )
        panel_layout.addWidget(self.empty_title_label)
        panel_layout.addWidget(self.empty_label)
        panel_layout.addLayout(empty_actions)
        empty_layout.addWidget(
            self.empty_panel, 0, Qt.AlignmentFlag.AlignHCenter
        )
        empty_layout.addStretch()

        self.card_index = self.content_stack.addWidget(self.card_scroll)
        self.table_index = self.content_stack.addWidget(self.table)
        self.empty_index = self.content_stack.addWidget(self.empty_widget)
        root.addWidget(self.content_stack, 1)

        for widget in (
            self.genre_filter,
            self.mal_score_filter,
            self.status_filter,
            self.minimum_episodes_filter,
            self.maximum_episodes_filter,
            self.sort_combo,
        ):
            if isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(lambda _index: self._apply_query())
            else:
                widget.valueChanged.connect(lambda _value: self._apply_query())
        self.cards_button.clicked.connect(lambda: self.set_view_mode(RecommendationViewMode.CARDS))
        self.table_button.clicked.connect(lambda: self.set_view_mode(RecommendationViewMode.TABLE))
        self.clear_filters_button.clicked.connect(self.clear_filters)
        self.state_filter.currentIndexChanged.connect(lambda _index: self._apply_query())
        self.show_hidden_checkbox.toggled.connect(self.set_show_hidden_preference)
        self.watch_later_selected_button.clicked.connect(
            lambda: self._toggle_watch_later(self.selected_model())
        )
        self.hide_selected_button.clicked.connect(
            lambda: self._toggle_hidden(self.selected_model())
        )
        self.like_selected_button.clicked.connect(
            lambda: self._toggle_feedback(self.selected_model(), "liked")
        )
        self.dislike_selected_button.clicked.connect(
            lambda: self._toggle_feedback(self.selected_model(), "disliked")
        )
        self.more_button.clicked.connect(self.more_requested.emit)
        self.refill_button.clicked.connect(self.refill_requested.emit)
        self.browse_liked_button.clicked.connect(
            lambda: self._select_state_filter("liked")
        )
        self.recommendations_folder_action.triggered.connect(
            lambda: self._select_state_filter("all")
        )
        self.liked_folder_action.triggered.connect(
            lambda: self._select_state_filter("liked")
        )
        self.disliked_folder_action.triggered.connect(
            lambda: self._select_state_filter("disliked")
        )
        self.filter_toggle_button.toggled.connect(self._set_filters_visible)

    @staticmethod
    def _episode_spinbox(object_name: str) -> QSpinBox:
        widget = QSpinBox()
        widget.setObjectName(object_name)
        widget.setRange(0, 100_000)
        widget.setSpecialValueText("Any")
        return widget

    def _set_filters_visible(self, visible: bool) -> None:
        self.filter_controls.setVisible(bool(visible))
        self.filter_toggle_button.setText("Hide filters" if visible else "Filters")

    def _select_state_filter(self, state: str) -> None:
        index = self.state_filter.findData(state)
        if index < 0:
            return
        tab = self.library_tabs.get(state)
        if tab is not None:
            tab.setChecked(True)
        if index == self.state_filter.currentIndex():
            self._apply_query()
        else:
            self.state_filter.setCurrentIndex(index)

    def _update_library_tabs(self) -> None:
        reviewed = self.local_state.liked_mal_ids | self.local_state.disliked_mal_ids
        for_you = sum(
            1
            for model in self._models
            if model.mal_id not in reviewed
            and (
                self.local_state.show_hidden
                or model.mal_id not in self.local_state.hidden_mal_ids
            )
        )
        counts = {
            "all": for_you,
            "liked": len(self.local_state.liked_mal_ids),
            "disliked": len(self.local_state.disliked_mal_ids),
            "watch-later": len(self.local_state.watch_later_mal_ids),
        }
        labels = {
            "all": "For You",
            "liked": "Liked",
            "disliked": "Disliked",
            "watch-later": "Watch Later",
        }
        current_state = self.state_filter.currentData()
        for state, button in self.library_tabs.items():
            button.setText(f"{labels[state]}  {counts[state]}")
            button.setChecked(state == current_state)

    def _populate_filter_options(self) -> None:
        current_genre = self.genre_filter.currentData()
        current_status = self.status_filter.currentData()
        genres = sorted({genre for model in self._models for genre in model.genres}, key=str.casefold)
        statuses = sorted(
            {model.status for model in self._models if model.status != "Not available"},
            key=str.casefold,
        )
        for combo, first_label, values, previous in (
            (self.genre_filter, "Any genre", genres, current_genre),
            (self.status_filter, "Any status", statuses, current_status),
        ):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(first_label, None)
            for value in values:
                combo.addItem(value, value)
            index = combo.findData(previous)
            combo.setCurrentIndex(max(0, index))
            combo.blockSignals(False)

    def _filters(self) -> RecommendationFilters:
        minimum_mal = self.mal_score_filter.value()
        minimum_episodes = self.minimum_episodes_filter.value()
        maximum_episodes = self.maximum_episodes_filter.value()
        return RecommendationFilters(
            genre=self.genre_filter.currentData(),
            minimum_mal_score=minimum_mal if minimum_mal > 0 else None,
            status=self.status_filter.currentData(),
            minimum_episodes=minimum_episodes if minimum_episodes > 0 else None,
            maximum_episodes=maximum_episodes if maximum_episodes > 0 else None,
        )

    def _sort_mode(self) -> RecommendationSortMode:
        return RecommendationSortMode(self.sort_combo.currentData())

    def _has_active_filters(self) -> bool:
        filters = self._filters()
        return any(
            value is not None
            for value in (
                filters.genre,
                filters.minimum_mal_score,
                filters.status,
                filters.minimum_episodes,
                filters.maximum_episodes,
            )
        )

    def _apply_query(self) -> None:
        state_filter = self.state_filter.currentData()
        reviewed_ids = (
            self.local_state.liked_mal_ids | self.local_state.disliked_mal_ids
        )
        state_filtered = tuple(
            model
            for model in self._models
            if (
                self.local_state.show_hidden
                or model.mal_id not in self.local_state.hidden_mal_ids
            )
            and (
                state_filter != "all"
                or model.mal_id not in reviewed_ids
            )
            and (
                state_filter != "watch-later"
                or model.mal_id in self.local_state.watch_later_mal_ids
            )
            and (state_filter != "liked" or model.mal_id in self.local_state.liked_mal_ids)
            and (
                state_filter != "disliked"
                or model.mal_id in self.local_state.disliked_mal_ids
            )
        )
        self._visible_models = filter_and_sort_recommendations(
            state_filtered, self._filters(), self._sort_mode()
        )
        if state_filter == "liked":
            count_text = f"{len(self._visible_models)} liked anime"
        elif state_filter == "disliked":
            count_text = f"{len(self._visible_models)} disliked anime"
        elif state_filter == "watch-later":
            count_text = f"{len(self._visible_models)} saved for later"
        else:
            count_text = (
                f"{len(self._visible_models)} unreviewed · {len(reviewed_ids)} filed"
            )
        self.result_count_label.setText(count_text)
        self._update_library_tabs()
        visible_keys = {self._key_by_model[id(model)] for model in self._visible_models}
        if self._selected_key not in visible_keys:
            self._selected_key = None
        self._rebuild_cards()
        self._rebuild_table()
        self._show_current_view()
        self._restore_selection()
        self._update_local_action_state()

    def _show_current_view(self) -> None:
        if not self._visible_models:
            has_source = bool(self._models)
            state_filter = self.state_filter.currentData()
            exhausted = (
                has_source
                and state_filter == "all"
                and not self._has_active_filters()
                and bool(
                    self.local_state.liked_mal_ids
                    | self.local_state.disliked_mal_ids
                )
            )
            if exhausted:
                title = "You’re all caught up"
                icon = "✓"
                message = (
                    "Every current pick has been reviewed. Generate 10 fresh anime "
                    "from your updated taste model, or revisit the choices you saved."
                )
            elif state_filter == "liked" and not self._has_active_filters():
                title = "No liked anime yet"
                icon = "♥"
                message = "Anime you like will stay here so you can inspect or change the vote later."
            elif state_filter == "disliked" and not self._has_active_filters():
                title = "Nothing filed as Disliked"
                icon = "–"
                message = "Anime marked Not for me will stay here and can be moved back at any time."
            elif state_filter == "watch-later" and not self._has_active_filters():
                title = "Your Watch Later list is empty"
                icon = "☆"
                message = "Save an anime from any card and it will appear in this collection."
            elif has_source:
                title = "No matches found"
                icon = "⌕"
                message = "Try clearing or widening the active filters to bring more anime back."
            else:
                title = "Build your first feed"
                icon = "✦"
                message = (
                    "Generate recommendations from Home to create a personal anime feed."
                )
            self.empty_title_label.setText(title)
            self.empty_icon_label.setText(icon)
            self.empty_label.setText(message)
            self.refill_button.setVisible(exhausted)
            self.clear_filters_button.setVisible(has_source and self._has_active_filters())
            self.browse_liked_button.setVisible(
                exhausted and bool(self.local_state.liked_mal_ids)
            )
            self.content_stack.setCurrentIndex(self.empty_index)
            return
        self.refill_button.setVisible(False)
        self.clear_filters_button.setVisible(False)
        self.browse_liked_button.setVisible(False)
        self.content_stack.setCurrentIndex(
            self.card_index if self._view_mode is RecommendationViewMode.CARDS else self.table_index
        )

    def _rebuild_cards(self) -> None:
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self._cards_by_key.clear()
        for model in self._visible_models:
            key = self._key_by_model[id(model)]
            card = RecommendationCard(model, self.card_container)
            card.selection_requested.connect(
                lambda _model, selected_key=key: self.select_key(selected_key)
            )
            card.details_requested.connect(self._open_details)
            card.hide_requested.connect(self._toggle_hidden)
            card.watch_later_requested.connect(self._toggle_watch_later)
            card.liked_requested.connect(lambda model: self._toggle_feedback(model, "liked"))
            card.disliked_requested.connect(
                lambda model: self._toggle_feedback(model, "disliked")
            )
            card.cover_requested.connect(
                lambda url, selected_key=key: self._request_cover(selected_key, url)
            )
            self._cards_by_key[key] = card
            card.set_local_state(
                hidden=model.mal_id in self.local_state.hidden_mal_ids,
                watch_later=model.mal_id in self.local_state.watch_later_mal_ids,
                actions_enabled=self.profile_id is not None and model.mal_id is not None,
                liked=model.mal_id in self.local_state.liked_mal_ids,
                disliked=model.mal_id in self.local_state.disliked_mal_ids,
            )
            card.set_cover_visible(self.show_covers)
        self._reflow_cards()
        self._schedule_visible_covers()

    def _reflow_cards(self) -> None:
        cards = list(self._cards_by_key.values())
        while self.card_layout.count():
            self.card_layout.takeAt(0)
        grid_stride = CARD_WIDTH + self.card_layout.horizontalSpacing()
        available = max(self.card_scroll.viewport().width(), grid_stride)
        columns = max(1, available // grid_stride)
        for index, card in enumerate(cards):
            self.card_layout.addWidget(
                card,
                index // columns,
                index % columns,
                Qt.AlignmentFlag.AlignTop,
            )

    def _rebuild_table(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._visible_models))
        for row, model in enumerate(self._visible_models):
            key = self._key_by_model[id(model)]
            values = (
                str(model.rank) if model.rank is not None else "—",
                model.display_title,
                f"{model.personal_match:.1f}%" if model.personal_match_available else "Not available",
                f"{model.mal_score:.2f}" if model.mal_score is not None else "Not rated",
                model.genres_text,
                str(model.year) if model.year is not None else "Not available",
                model.status,
                str(model.episodes) if model.episodes is not None else "Not available",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, key)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        self.table.blockSignals(False)

    def _restore_selection(self) -> None:
        for key, card in self._cards_by_key.items():
            card.set_selected(key == self._selected_key)
        self.table.blockSignals(True)
        self.table.clearSelection()
        if self._selected_key is not None:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item and item.data(Qt.ItemDataRole.UserRole) == self._selected_key:
                    self.table.selectRow(row)
                    break
        self.table.blockSignals(False)

    def _on_table_selection_changed(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        item = self.table.item(rows[0].row(), 0)
        if item is not None:
            self.select_key(item.data(Qt.ItemDataRole.UserRole))

    def _update_local_action_state(self) -> None:
        model = self.selected_model()
        enabled = self.profile_id is not None and model is not None and model.mal_id is not None
        self.hide_selected_button.setEnabled(enabled)
        self.watch_later_selected_button.setEnabled(enabled)
        self.like_selected_button.setEnabled(enabled)
        self.dislike_selected_button.setEnabled(enabled)
        self._update_selected_actions_visibility()
        if model is None:
            self.hide_selected_button.setText("Hide")
            self.watch_later_selected_button.setText("Watch Later")
            self.like_selected_button.setText("Like")
            self.dislike_selected_button.setText("Not for me")
            self.like_selected_button.setChecked(False)
            self.dislike_selected_button.setChecked(False)
            return
        self.hide_selected_button.setText(
            "Unhide" if model.mal_id in self.local_state.hidden_mal_ids else "Hide"
        )
        self.watch_later_selected_button.setText(
            "Remove from Watch Later"
            if model.mal_id in self.local_state.watch_later_mal_ids
            else "Watch Later"
        )
        liked = model.mal_id in self.local_state.liked_mal_ids
        disliked = model.mal_id in self.local_state.disliked_mal_ids
        self.like_selected_button.setChecked(liked)
        self.dislike_selected_button.setChecked(disliked)
        self.like_selected_button.setText(
            "Remove like" if liked else "Move to Liked" if disliked else "Like"
        )
        self.dislike_selected_button.setText(
            "Remove dislike"
            if disliked
            else "Move to Disliked"
            if liked
            else "Not for me"
        )

    def _update_selected_actions_visibility(self) -> None:
        self.selected_actions_frame.setVisible(
            self._view_mode is RecommendationViewMode.TABLE
            and self.selected_model() is not None
        )

    def _toggle_hidden(self, model: RecommendationViewModel | None) -> None:
        if self.profile_id is None or model is None or model.mal_id is None:
            return
        self.local_state = self.state_service.set_hidden(
            self.profile_id,
            model.mal_id,
            model.mal_id not in self.local_state.hidden_mal_ids,
        )
        self._apply_query()
        self._sync_detail_local_state()

    def _toggle_watch_later(self, model: RecommendationViewModel | None) -> None:
        if self.profile_id is None or model is None or model.mal_id is None:
            return
        self.local_state = self.state_service.set_watch_later(
            self.profile_id,
            model.mal_id,
            model.mal_id not in self.local_state.watch_later_mal_ids,
        )
        self._apply_query()
        self._sync_detail_local_state()

    def _toggle_feedback(
        self, model: RecommendationViewModel | None, sentiment: str
    ) -> None:
        if self.profile_id is None or model is None or model.mal_id is None:
            return
        active_ids = (
            self.local_state.liked_mal_ids
            if sentiment == "liked"
            else self.local_state.disliked_mal_ids
        )
        next_sentiment = None if model.mal_id in active_ids else sentiment
        self.local_state = self.state_service.set_feedback(
            self.profile_id,
            model.mal_id,
            next_sentiment,
            genres=model.genres,
            title=model.display_title,
        )
        self._update_feedback_summary()
        self._apply_query()
        self._sync_detail_local_state()
        self.feedback_changed.emit(self.local_state)

    def _update_feedback_summary(self) -> None:
        likes = len(self.local_state.liked_mal_ids)
        dislikes = len(self.local_state.disliked_mal_ids)
        if self.profile_id is None:
            text = "Connect a profile to teach AniRec what fits your taste."
        elif not likes and not dislikes:
            text = "Taste learning is ready — like or dislike any card to shape future picks."
        else:
            text = (
                f"Live taste model: {likes} liked · {dislikes} disliked. "
                "The remaining feed and every future pick update after each vote."
            )
        self.feedback_summary_label.setText(text)
        self.taste_folders_button.setText(
            f"Taste folders · {likes} liked · {dislikes} disliked"
        )
        self.liked_folder_action.setText(f"Liked ({likes})")
        self.disliked_folder_action.setText(f"Disliked ({dislikes})")
        self._update_library_tabs()

    def _open_selected_details(self) -> None:
        model = self.selected_model()
        if model is not None:
            self._open_details(model)

    def _open_details(self, model: RecommendationViewModel) -> None:
        self.details_requested.emit(model)
        if self.detail_dialog is None:
            self.detail_dialog = RecommendationDetailDialog(self)
            self.detail_dialog.cover_requested.connect(self._request_detail_cover)
            self.detail_dialog.hide_requested.connect(self._toggle_hidden)
            self.detail_dialog.watch_later_requested.connect(self._toggle_watch_later)
            self.detail_dialog.liked_requested.connect(
                lambda model: self._toggle_feedback(model, "liked")
            )
            self.detail_dialog.disliked_requested.connect(
                lambda model: self._toggle_feedback(model, "disliked")
            )
        self.detail_dialog.set_model(model)
        self.detail_dialog.set_cover_visible(self.show_covers)
        self._sync_detail_local_state()
        self.detail_dialog.show()
        self.detail_dialog.raise_()
        self.detail_dialog.activateWindow()

    def _sync_detail_local_state(self) -> None:
        if self.detail_dialog is None or self.detail_dialog.model is None:
            return
        mal_id = self.detail_dialog.model.mal_id
        self.detail_dialog.set_local_state(
            hidden=mal_id in self.local_state.hidden_mal_ids,
            watch_later=mal_id in self.local_state.watch_later_mal_ids,
            actions_enabled=self.profile_id is not None and mal_id is not None,
            liked=mal_id in self.local_state.liked_mal_ids,
            disliked=mal_id in self.local_state.disliked_mal_ids,
        )

    def _request_detail_cover(self, url: str) -> None:
        if not self.show_covers or self.detail_dialog is None:
            return
        data = self._cover_data_by_url.get(url)
        if data is not None:
            self.detail_dialog.set_cover_data(data)
            return
        self._request_cover("detail", url)

    def eventFilter(self, watched, event) -> bool:
        if watched is self.card_scroll.viewport() and event.type() == QEvent.Type.Resize:
            self._reflow_cards()
            self._schedule_visible_covers()
        return super().eventFilter(watched, event)

    def _schedule_visible_covers(self) -> None:
        if self._view_mode is RecommendationViewMode.CARDS:
            QTimer.singleShot(0, self._request_visible_covers)

    def _request_visible_covers(self) -> None:
        if not self.show_covers or self.content_stack.currentIndex() != self.card_index:
            return
        origin = self.card_container.mapFrom(self.card_scroll.viewport(), QPoint(0, 0))
        visible_rect = self.card_scroll.viewport().rect().translated(origin)
        requested = 0
        for card in self._cards_by_key.values():
            if requested >= self.MAX_COVER_REQUESTS_PER_PASS:
                break
            if card.geometry().intersects(visible_rect):
                before = len(self._cover_attempted)
                card.request_cover()
                if len(self._cover_attempted) > before:
                    requested += 1

    def _request_cover(self, _key: str, url: str) -> None:
        if url in self._cover_attempted:
            return
        self._cover_attempted.add(url)
        if self.worker_controller is None:
            return
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
        operation_key = f"cover:{digest}"
        self._cover_operation_urls[operation_key] = url
        try:
            self.worker_controller.start(
                operation_key, CoverDownloadWorker(self.cover_service, url)
            )
        except OperationAlreadyRunningError:
            pass

    def _on_worker_result(self, operation_key: str, result: object) -> None:
        url = self._cover_operation_urls.pop(operation_key, None)
        if url is None or not isinstance(result, CoverImageResult):
            return
        self._cover_data_by_url[url] = result.data
        for card in self._cards_by_key.values():
            if card.model.cover_url == url:
                card.set_cover_data(result.data)
        if self.detail_dialog is not None and self.detail_dialog.model is not None:
            detail_url = (
                self.detail_dialog.model.large_cover_url
                or self.detail_dialog.model.cover_url
            )
            if detail_url == url:
                self.detail_dialog.set_cover_data(result.data)

    def _on_worker_error(self, operation_key: str, _error: object) -> None:
        self._cover_operation_urls.pop(operation_key, None)
