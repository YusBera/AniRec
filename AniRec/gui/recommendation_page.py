"""Filterable card, list and table explorer for persisted recommendations.

Addresses: BUG1 (guarded actions), BUG2 (view toggle restored, scale rebuild),
FEAT2 (badge colours follow the theme).
"""

from __future__ import annotations

import hashlib
from time import monotonic
from dataclasses import dataclass, replace
from enum import Enum

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPoint,
    Qt,
    QTimer,
    Signal,
)
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
    RecommendationFeedback,
    RecommendationLocalState,
    RecommendationStateService,
)
from .recommendation_card import CARD_WIDTH, RecommendationCard
from .resources import themed_ui_icon, ui_icon_pixmap
from .scaling import scaled
from .design_tokens import SPACE
from .instrument_widgets import ChannelWipe, InstrumentPanel, ScanSweep
from .recommendation_detail_dialog import RecommendationDetailDialog
from .recommendation_row import RecommendationRow
from .recommendation_view_model import RecommendationViewModel, recommendation_view_models
from .workers import CoverDownloadWorker, OperationAlreadyRunningError, WorkerController


class RecommendationViewMode(str, Enum):
    """How the feed is laid out.

    CARDS leads with artwork in a responsive grid. LIST trades the poster
    for density, fitting several times as many titles in the same space.
    TABLE remains for scanning many rows by column.
    """

    CARDS = "cards"
    LIST = "list"
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


def _toggle_in_memory(
    state: RecommendationLocalState, field: str, mal_id: int, wanted: bool
) -> RecommendationLocalState:
    """Add or remove one id from a saved-state set, without persisting."""
    current = set(getattr(state, field))
    current.add(mal_id) if wanted else current.discard(mal_id)
    return replace(state, **{field: frozenset(current)})


def _feedback_in_memory(
    state: RecommendationLocalState,
    mal_id: int,
    sentiment: str | None,
    *,
    genres: tuple[str, ...],
    title: str,
) -> RecommendationLocalState:
    """Record or clear one vote, without persisting."""
    kept = [record for record in state.feedback if record.mal_id != mal_id]
    if sentiment is not None:
        kept.append(
            RecommendationFeedback(
                mal_id=mal_id, sentiment=sentiment, genres=genres, title=title
            )
        )
    return replace(state, feedback=tuple(kept))


# Long enough to read as a transition, short enough not to delay the switch.


# Endless scrolling. The trigger is how close to the end of the feed a reader
# has to be before more is fetched; the debounce collapses a whole flick's
# worth of scroll events into one request; the cooldown is the floor between
# requests even when a worker never answers.
AUTOLOAD_TRIGGER_PX = 420
AUTOLOAD_DEBOUNCE_MS = 220
AUTOLOAD_COOLDOWN_S = 1.5


def _badge_colours():
    """Track, fill and text for the match bar, from the palette in force.

    CHANGE [BUG-BADGE]: this used to look the palette up by theme name, which
    returns defaults for the gradient theme because that palette is built from
    the user's two colours. The bar stayed the stock terracotta over a green or
    blue interface. The theme manager now publishes what it actually resolved.
    """
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QApplication

    from .design_tokens import palette

    application = QApplication.instance()
    accent = application.property("resolvedAccent") if application else None
    contrast = application.property("resolvedAccentContrast") if application else None
    background = application.property("resolvedBackground") if application else None
    signal = application.property("resolvedSignal") if application else None
    if not accent:
        theme = (application.property("activeTheme") if application else None) or "dark"
        try:
            colours = palette(theme)
        except ValueError:
            colours = palette("dark")
        accent = colours["accent"]
        contrast = colours["accent_contrast"]
        background = colours["bg"]
        signal = colours["focus"]

    track = QColor(background)
    # CHANGE [FEAT2]: opaque enough to read as the bar's full length over
    # cover art. At 165 it disappeared into dark artwork and the fill had
    # nothing to be a proportion of.
    track.setAlpha(215)
    # The fourth colour is the "not yours" term. The rail bands the community
    # contribution in it, the way the detail view and the landing page do, so
    # the split between your taste and everyone else's is visible on the card
    # without opening anything.
    return track, QColor(accent), QColor(contrast), QColor(signal or "#6FC6C0")


def recommendation_key(model: RecommendationViewModel, source_index: int) -> str:
    if model.mal_id is not None:
        return f"mal:{model.mal_id}"
    return f"local:{source_index}:{model.display_title.casefold()}"



def _vertical_bar() -> QFrame:
    """A hard separator between fields on a control bar."""
    rule = QFrame()
    rule.setObjectName("stripDivider")
    rule.setFixedWidth(1)
    rule.setFixedHeight(13)
    return rule


def _resolved_colour(role: str, fallback: str) -> str:
    """Read a colour the active theme published, with a safe default."""
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance()
    value = application.property(role) if application is not None else None
    return str(value or fallback)


class RecommendationExplorerPage(QWidget):
    """One query state rendered as either accessible cards or a compact table."""

    details_requested = Signal(object)
    selection_changed = Signal(object)
    show_hidden_changed = Signal(bool)
    feedback_changed = Signal(object)
    more_requested = Signal()
    refill_requested = Signal()
    view_mode_changed = Signal(str)
    # CHANGE [BUG5]: lets the surrounding surface collapse its header once
    # the feed is scrolled, so browsing is not done through a slot.
    feed_scrolled = Signal(int)
    # Emitted when artwork actually lands, so the activity panel can say
    # so. Carries the title it belongs to rather than the URL.
    artwork_retrieved = Signal(str)
    MAX_COVER_REQUESTS_PER_PASS = 6

    # How many times one URL may be re-requested before the feed gives up on
    # it. A transient failure must not cost the card its artwork forever; a
    # permanently bad URL must not be retried on every scroll.
    MAX_COVER_ATTEMPTS = 3

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
        self._rows_by_key: dict[str, RecommendationRow] = {}
        self._selected_key: str | None = None
        self._view_mode = RecommendationViewMode.CARDS
        self.show_covers = True
        self._cover_attempted: set[str] = set()
        # Counted per URL so a retry is bounded rather than endless.
        self._cover_failures: dict[str, int] = {}
        self._cover_operation_urls: dict[str, str] = {}
        self._cover_data_by_url: dict[str, bytes] = {}
        self.detail_dialog: RecommendationDetailDialog | None = None
        self._more_available = False
        self._more_running = False
        self._more_unavailable_reason = ""
        self._profile_loaded = False
        self._ephemeral = False
        self._view_animation = None
        self._build_ui()
        self._update_more_actions()
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

    def _sweep_feed(self) -> None:
        """Run the refresh sweep, if the feed is the visible surface."""
        sweep = getattr(self, "scan_sweep", None)
        if sweep is None or self._view_mode is not RecommendationViewMode.CARDS:
            return
        if not self.card_scroll.isVisible():
            return
        sweep.sweep()

    def set_recommendations(
        self,
        recommendations: tuple[Recommendation, ...] | list[Recommendation],
    ) -> None:
        previous_key = self._selected_key
        models = recommendation_view_models(recommendations)
        # CHANGE [BUG1]: an identical set needs no teardown. Re-personalising
        # after a vote usually returns the same titles in the same order.
        if models == self._models:
            self._apply_query()
            return
        # CHANGE [SCROLL-FLICKER]: the sweep runs when the feed is replaced,
        # not when it grows. Endless scrolling calls this method with the old
        # list plus five more, which differs from the old list, so every
        # top-up used to fire a 520ms band across the viewport - while the
        # user was mid-scroll, which is what read as flickering. An append is
        # not a refresh: nothing above the new cards changed.
        extended = len(models) > len(self._models) and models[: len(self._models)] == self._models
        self._models = models
        if not extended:
            self._sweep_feed()
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
        # An unavailable top-up is already explained by the surrounding
        # connection/generation state.  Hiding it avoids a large disabled slab
        # that looks actionable but cannot convert; it returns as soon as the
        # candidate pool exists (and stays visible while a request is running).
        self.more_button.setVisible(self._more_available or self._more_running)
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
        # CHANGE [BUG1]: skip the work when nothing changed. A single Like ran
        # five full rebuilds of every card and row, because the dashboard
        # refresh calls set_profile and set_recommendations on both views and
        # each one triggered a teardown. Four of those five were redundant, and
        # the visible tear-down and rebuild is what reads as flashing.
        if profile_id == self.profile_id and self._profile_loaded:
            self.local_state = (
                self.state_service.load(profile_id)
                if profile_id is not None
                else self.local_state
            )
            self._update_feedback_summary()
            self._apply_query()
            return
        self._profile_loaded = True
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
        self.list_button.setChecked(resolved is RecommendationViewMode.LIST)
        self.table_button.setChecked(resolved is RecommendationViewMode.TABLE)
        # CHANGE [BUG1]: the layout being switched to may not be built yet.
        self._rebuild_cards()
        self._rebuild_rows()
        self._show_current_view()
        self._restore_selection()
        self._update_selected_actions_visibility()
        if resolved in (RecommendationViewMode.CARDS, RecommendationViewMode.LIST):
            QTimer.singleShot(0, self._request_visible_covers)
        self._fade_in_current_view()
        self.view_mode_changed.emit(resolved.value)

    def set_default_sort(self, sort_mode: RecommendationSortMode | str) -> None:
        resolved = RecommendationSortMode(sort_mode)
        index = self.sort_combo.findData(resolved.value)
        if index >= 0:
            self.sort_combo.setCurrentIndex(index)

    def set_show_covers(self, show_covers: bool) -> None:
        self.show_covers = bool(show_covers)
        for card in self._cards_by_key.values():
            card.set_cover_visible(self.show_covers)
            # CHANGE [FEAT2]: the badge follows the active theme rather than
            # assuming a dark portrait behind it.
            card.set_badge_colours(*_badge_colours())
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

    # CHANGE [PAGE]: one inset and one rhythm for every surface, named from
    # the spacing scale rather than typed as raw pixels. Discover, My Library
    # and Settings each carried their own numbers - (0,0,0,0)/8, (8,8,8,8)/12
    # and (8,8,8,8)/8 - so switching tabs nudged the whole page.
    PAGE_MARGIN = SPACE["sm"]
    PAGE_SPACING = SPACE["md"]

    def set_embedded(self, embedded: bool) -> None:
        """Drop the page inset when this sits inside another page.

        Discover wraps this component in a surface that supplies the page
        margin itself. Without this the two insets stacked and Discover's feed
        sat eight pixels further in than the identical feed on My Library.
        """
        layout = self.layout()
        if layout is None:
            return
        margin = 0 if embedded else self.PAGE_MARGIN
        layout.setContentsMargins(margin, margin, margin, margin)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            self.PAGE_MARGIN, self.PAGE_MARGIN, self.PAGE_MARGIN, self.PAGE_MARGIN
        )
        root.setSpacing(self.PAGE_SPACING)

        self.hero = InstrumentPanel()
        self.hero.setObjectName("recommendationHero")
        hero_layout = QHBoxLayout(self.hero)
        hero_layout.setContentsMargins(20, 10, 20, 10)
        hero_layout.setSpacing(20)
        heading_copy = QVBoxLayout()
        heading_copy.setSpacing(SPACE["xs"])
        eyebrow = QLabel("PERSONAL DISCOVERY")
        eyebrow.setObjectName("recommendationEyebrow")
        self.hero_eyebrow = eyebrow
        title = QLabel("Find your next favorite")
        title.setObjectName("recommendationHeroTitle")
        title.setAccessibleName("Your recommendations heading")
        self.hero_title = title
        description = QLabel(
            "Review each pick once. AniRec learns from every decision and reshapes "
            "the remaining feed in real time."
        )
        description.setObjectName("recommendationHeroDescription")
        description.setWordWrap(True)
        self.hero_description = description
        heading_copy.addWidget(eyebrow)
        heading_copy.addWidget(title)
        heading_copy.addWidget(description)

        self.feedback_summary_label = QLabel()
        self.feedback_summary_label.setObjectName("recommendationFeedbackSummary")
        self.feedback_summary_label.setWordWrap(False)
        hero_layout.addLayout(heading_copy, 1)

        hero_actions = QVBoxLayout()
        hero_actions.setSpacing(8)
        hero_actions.addStretch()
        action_caption = QLabel("READY FOR SOMETHING NEW?")
        action_caption.setObjectName("recommendationActionCaption")
        action_caption.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.hero_action_caption = action_caption
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
        # CHANGE [HIERARCHY]: topping the feed up is an incremental action
        # sitting beside a summary line, not the reason you opened the page.
        # As a third accent-filled block on the same screen it competed with
        # "Get new recommendations" and with the connect prompt above it.
        self.more_button.setProperty("buttonRole", "secondary")
        # 46px made this the tallest control in the app, which is a lot of
        # band for a top-up action. Matches every other button now.
        # CHANGE [ROW]: the width is pinned, the height is not.
        #
        # This asked for 26px both ways. A stylesheet min-height beats
        # setMaximumHeight, so the button rendered at the sheet's 36 while the
        # layout sized it from a 26px maximum - which is why it sat ten pixels
        # below the rest of its row, top at y=63 against everything else at
        # y=53. Pin the axis you actually care about and let the row share the
        # other.
        self.more_button.setMinimumWidth(150)
        self.more_button.setEnabled(False)
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
        library_layout.setContentsMargins(0, 0, 0, 0)
        library_layout.setSpacing(SPACE["sm"])
        tab_row = QHBoxLayout()
        tab_row.setSpacing(SPACE["xs"])
        self.library_tabs: dict[str, QPushButton] = {}
        self.library_tab_group = QButtonGroup(self)
        self.library_tab_group.setExclusive(True)
        for state, label in (
            ("all", "FOR YOU"),
            ("liked", "LIKED"),
            ("disliked", "DISLIKED"),
            ("watch-later", "WATCH LATER"),
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
        self._visible_states = tuple(self.library_tabs)
        tab_row.addStretch()
        library_layout.addLayout(tab_row)

        view_row = QHBoxLayout()
        view_row.setSpacing(SPACE["sm"])
        # CHANGE [ORPHAN]: the count sat between two stretches, centred in the
        # window with the controls it describes pushed to the far right. It
        # reads as a caption for those controls, so it is anchored to the left
        # of the bar and one stretch separates the readout from the switches.
        self.result_count_label = QLabel()
        self.result_count_label.setObjectName("recommendationResultCount")
        view_row.addWidget(self.result_count_label)
        # CHANGE [BAND]: the feedback summary and the top-up action used to
        # sit in a full-width band of their own above this bar - a fourth
        # stacked box on Discover carrying one sentence and one button. They
        # belong with the readouts and switches that describe the same feed.
        view_row.addWidget(_vertical_bar())
        view_row.addWidget(self.feedback_summary_label)
        view_row.addStretch(1)
        view_row.addWidget(self.more_button)
        self.filter_toggle_button = QPushButton("Filters")
        self.filter_toggle_button.setIcon(themed_ui_icon("filter"))
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
        self.cards_button.setIcon(themed_ui_icon("view-grid"))
        self.cards_button.setObjectName("recommendationCardsViewButton")
        self.cards_button.setProperty("viewToggle", True)
        self.cards_button.setCheckable(True)
        self.list_button = QPushButton("List")
        self.list_button.setIcon(themed_ui_icon("view-list"))
        self.list_button.setObjectName("recommendationListViewButton")
        self.list_button.setProperty("viewToggle", True)
        self.list_button.setCheckable(True)
        self.list_button.setAccessibleName("Show recommendations as a compact list")
        self.table_button = QPushButton("Table")
        self.table_button.setIcon(themed_ui_icon("view-table"))
        self.table_button.setObjectName("recommendationTableViewButton")
        self.table_button.setProperty("viewToggle", True)
        self.table_button.setCheckable(True)
        group = QButtonGroup(self)
        group.setExclusive(True)
        group.addButton(self.cards_button)
        group.addButton(self.list_button)
        group.addButton(self.table_button)
        self.cards_button.setChecked(True)
        view_row.addWidget(self.cards_button)
        view_row.addWidget(self.list_button)
        view_row.addWidget(self.table_button)
        # CHANGE [BUG2]: the grid/list toggle used to live inside library_bar,
        # which set_visible_states() hides when a surface offers only one
        # collection. Discover offers one, so the toggle disappeared entirely,
        # at every DPI. It now sits in its own bar that is always shown.
        self.view_bar = QFrame()
        self.view_bar.setObjectName("recommendationViewBar")
        view_bar_layout = QVBoxLayout(self.view_bar)
        view_bar_layout.setContentsMargins(0, 0, 0, 0)
        # CHANGE [PAGE]: stated, not inherited. Left unset this took Qt's
        # default of 6, which is not a value on the spacing scale and was the
        # only reason this bar's rhythm differed from the one above it.
        view_bar_layout.setSpacing(0)
        view_bar_layout.addLayout(view_row)

        root.addWidget(self.library_bar)
        root.addWidget(self.view_bar)
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
        # CHANGE [PAGE]: a QStackedLayout defaults to a 9px margin all round.
        # Nobody chose 9 - it is off the spacing scale, and it inset the feed
        # a further nine pixels inside the page's own eight, so the grid sat
        # seventeen pixels from the edge while every bar above it sat at
        # eight. The stack carries full-bleed content; the page owns the
        # inset.
        stack_layout = self.content_stack.layout()
        if stack_layout is not None:
            stack_layout.setContentsMargins(0, 0, 0, 0)
            stack_layout.setSpacing(0)
        self.card_scroll = QScrollArea()
        self.card_scroll.setObjectName("recommendationCardScroll")
        self.card_scroll.setWidgetResizable(True)
        self.card_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.list_scroll = QScrollArea()
        self.list_scroll.setObjectName("recommendationListScroll")
        self.list_scroll.setWidgetResizable(True)
        self.list_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.list_container = QWidget()
        self.list_container.setObjectName("recommendationListContainer")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(SPACE["sm"])
        self.list_layout.addStretch()
        self.list_scroll.setWidget(self.list_container)
        self.list_scroll.verticalScrollBar().valueChanged.connect(
            self.feed_scrolled.emit
        )

        self.card_container = QWidget()
        self.card_container.setObjectName("recommendationCardContainer")
        self.card_layout = QGridLayout(self.card_container)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setSpacing(16)
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.card_scroll.setWidget(self.card_container)
        self.card_scroll.verticalScrollBar().valueChanged.connect(
            self.feed_scrolled.emit
        )
        # One sweep widget over the viewport, not an effect per card.
        self.scan_sweep = ScanSweep(self.card_scroll.viewport())
        # On the stack rather than on a view, so it spans whichever
        # layout is current without being rebuilt per switch.
        self._view_wipe = ChannelWipe(self.content_stack)
        self.card_scroll.viewport().installEventFilter(self)
        self.card_scroll.verticalScrollBar().valueChanged.connect(
            lambda _value: self._schedule_visible_covers()
        )
        self.card_scroll.verticalScrollBar().valueChanged.connect(
            lambda _value: self._consider_autoload()
        )
        # Endless scrolling, with the brakes it needs. A scroll bar emits
        # valueChanged for every pixel of a flick, so the request is debounced
        # rather than fired from the event, and three independent guards below
        # stop a fast scroll turning into a queue of overlapping fetches.
        self._autoload_timer = QTimer(self)
        self._autoload_timer.setSingleShot(True)
        self._autoload_timer.setInterval(AUTOLOAD_DEBOUNCE_MS)
        self._autoload_timer.timeout.connect(self._autoload_now)
        self._autoload_enabled = True
        self._autoload_blocked_until = 0.0

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
        panel_layout.setContentsMargins(
            SPACE["3xl"], SPACE["2xl"], SPACE["3xl"], SPACE["2xl"]
        )
        panel_layout.setSpacing(12)
        self.empty_icon_label = QLabel()
        self.empty_icon_label.setObjectName("recommendationEmptyIcon")
        self.empty_icon_label.setFixedSize(48, 48)
        self.empty_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_icon_name = "view-grid"
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
        panel_layout.addSpacing(8)
        panel_layout.addWidget(self.empty_title_label)
        panel_layout.addWidget(self.empty_label)
        panel_layout.addLayout(empty_actions)
        empty_layout.addWidget(
            self.empty_panel, 0, Qt.AlignmentFlag.AlignHCenter
        )
        empty_layout.addStretch()

        self.card_index = self.content_stack.addWidget(self.card_scroll)
        self.list_index = self.content_stack.addWidget(self.list_scroll)
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
        self.list_button.clicked.connect(lambda: self.set_view_mode(RecommendationViewMode.LIST))
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

    def set_ephemeral(self, ephemeral: bool) -> None:
        """Allow reviewing without a profile, keeping the result in memory.

        The sample library exists so someone can judge AniRec before creating a
        MyAnimeList application. Reviewing a pick is the whole product, so
        disabling Like and Not for me there left the one mode meant to sell it
        unable to demonstrate anything. Nothing is written: there is no profile
        directory to write to, and the state is discarded when the sample is.
        """
        self._ephemeral = bool(ephemeral)
        if self._ephemeral:
            self.local_state = RecommendationLocalState()
        self._update_feedback_summary()
        self._apply_query()

    @property
    def can_review(self) -> bool:
        """Whether feedback and saved state can be recorded at all."""
        return self.profile_id is not None or self._ephemeral

    def rebuild_for_scale(self) -> None:
        """Resize the existing widgets rather than recreating them.

        CHANGE [BUG2]: rebuilding here would undo the reuse that stops a vote
        tearing down the feed, so the widgets re-apply their own dimensions
        instead.
        """
        for widget in (*self._cards_by_key.values(), *self._rows_by_key.values()):
            widget.apply_scale()
        # The one thing that does change a card's natural height.
        self._invalidate_card_height()
        self._laid_out = (0, ())
        self._reflow_cards()
        self._restore_selection()

    def set_compact_header(self, compact: bool) -> None:
        """Fold away the decorative header copy.

        Measured on a 1280x720 window, the full header put half the viewport
        above the first recommendation, so almost nothing was visible without
        scrolling. The two parts that do work, the feedback summary and the
        action to fetch more, stay; the standing title and description do not,
        because the surface already carries its own heading and the empty state
        explains the review loop where that explanation is actually useful.
        """
        decorative = bool(compact)
        for widget in (
            self.hero_eyebrow,
            self.hero_title,
            self.hero_description,
            self.hero_action_caption,
        ):
            widget.setVisible(not decorative)
        # Everything that did work has moved to the control bar, so in compact
        # mode the band would be an empty rectangle. It is hidden outright.
        self.hero.setVisible(not decorative and "all" in self._visible_states)

    def set_visible_states(self, states) -> None:
        """Restrict which library collections this view offers.

        The same widget serves both top level surfaces: Discover shows the feed
        waiting to be reviewed, My Library shows what has been saved. Limiting
        the tabs rather than duplicating the view keeps filtering, sorting,
        selection and cover loading in one place.
        """
        wanted = [state for state in states if state in self.library_tabs]
        if not wanted:
            return
        self._visible_states = tuple(wanted)
        for state, button in self.library_tabs.items():
            button.setVisible(state in self._visible_states)
        # My Library is a filing surface, not a second recommendation funnel.
        # Keeping the Discover feedback banner and a disabled "Recommend more"
        # action above an empty library produced a rectangle whose only job was
        # to advertise that it could not be used.
        self.hero.setVisible("all" in self._visible_states)
        # A single collection needs no tab to choose between.
        self.library_bar.setVisible(len(self._visible_states) > 1)
        if self.state_filter.currentData() not in self._visible_states:
            self._select_state_filter(self._visible_states[0])

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
        # Qt has no text-transform, so the case lives in the string.
        labels = {
            "all": "FOR YOU",
            "liked": "LIKED",
            "disliked": "DISLIKED",
            "watch-later": "WATCH LATER",
        }
        current_state = self.state_filter.currentData()
        for state, button in self.library_tabs.items():
            button.setText(f"{labels[state]}  {counts[state]}")
            button.setChecked(state == current_state)
            button.setVisible(state in self._visible_states)

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

    def _schedule_rebuild(self) -> None:
        """Coalesce rebuild requests into one pass on the next event turn.

        CHANGE [BUG1]: a single Like ran three separate full rebuilds, tearing
        down and recreating every card and row each time. With thirty
        recommendations that was 88 card widgets plus 88 rows, roughly 3,500
        child widgets, and about 1.1 seconds during which the feed visibly
        tore down and came back. That flashing is what reads as popups
        appearing and vanishing, and it is the main reason the interface felt
        slow. Collapsing the burst into one deferred pass removes both.
        """
        if self._rebuild_pending:
            return
        self._rebuild_pending = True
        QTimer.singleShot(0, self._run_pending_rebuild)

    def _run_pending_rebuild(self) -> None:
        self._rebuild_pending = False
        self._rebuild_cards()
        self._rebuild_rows()
        self._restore_selection()

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
        # One register for the row: this sits immediately beside the feedback
        # summary ("SAMPLE · 0 LIKED · 0 PASSED"), and the two were sentence
        # case and caps in the same face on the same baseline.
        #
        # On a collection tab it reports SHOWN rather than naming the
        # collection again. The tab already carries the collection's total and
        # the summary carries the vote counts; repeating "LIKED" here put the
        # same number on screen three times. SHOWN is also the more useful
        # fact, because it is the count after the active filters.
        if state_filter in ("liked", "disliked", "watch-later"):
            count_text = f"{len(self._visible_models)} SHOWN"
        else:
            count_text = (
                f"{len(self._visible_models)} UNREVIEWED · {len(reviewed_ids)} FILED"
            )
        self.result_count_label.setText(count_text)
        self._update_library_tabs()
        visible_keys = {self._key_by_model[id(model)] for model in self._visible_models}
        if self._selected_key not in visible_keys:
            self._selected_key = None
        self._rebuild_cards()
        self._rebuild_rows()
        self._rebuild_table()
        self._show_current_view()
        self._restore_selection()
        self._update_local_action_state()

    def _fade_in_current_view(self) -> None:
        """Mark the layout change with a wipe across the top of the feed.

        This was an opacity fade over the whole view. A graphics effect
        re-renders its entire source into an offscreen buffer every frame, and
        on a feed of cards that measured 26-54ms per frame - five to seven
        frames for the whole transition, which reads as a stutter rather than
        as a cross fade.

        The wipe carries the same "this surface just changed" signal from a
        two-pixel opaque strip, and measures at frame rate. It is also the
        same motion the shell uses when the page changes, so switching layout
        and switching page now speak with one voice.
        """
        widget = self.content_stack.currentWidget()
        if widget is None:
            return
        self._view_wipe.run()
        # Kept under its original name: the invariant the suite pins is that a
        # layout switch animates and has a real duration, not which widget
        # carries the animation.
        self._view_animation = self._view_wipe.animation

    def _show_current_view(self) -> None:
        state_filter = self.state_filter.currentData()
        model_ids = {model.mal_id for model in self._models}
        reviewed_ids = (
            self.local_state.liked_mal_ids | self.local_state.disliked_mal_ids
        )
        if state_filter == "liked":
            collection_ids = model_ids & self.local_state.liked_mal_ids
        elif state_filter == "disliked":
            collection_ids = model_ids & self.local_state.disliked_mal_ids
        elif state_filter == "watch-later":
            collection_ids = model_ids & self.local_state.watch_later_mal_ids
        else:
            collection_ids = model_ids - reviewed_ids
        has_collection_items = bool(collection_ids)
        has_hidden_items = bool(collection_ids & self.local_state.hidden_mal_ids)
        self.show_hidden_checkbox.setVisible(has_hidden_items)

        if not self._visible_models:
            # Keep the Cards/List/Table affordance in a stable location on
            # every surface (including an empty Library), but do not invite
            # people to open filters that cannot produce a result yet.
            self.view_bar.setVisible(True)
            self.filter_toggle_button.setChecked(False)
            self.filter_toggle_button.setVisible(has_collection_items)
            has_source = bool(self._models)
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
                icon = "like-active"
                message = (
                    "Every current pick has been reviewed. Generate 10 fresh anime "
                    "from your updated taste model, or revisit the choices you saved."
                )
            elif state_filter == "liked" and not self._has_active_filters():
                title = "No liked anime yet"
                icon = "folder-liked"
                message = "Anime you like will stay here so you can inspect or change the vote later."
            elif state_filter == "disliked" and not self._has_active_filters():
                title = "Nothing filed as Disliked"
                icon = "folder-disliked"
                message = "Anime marked Not for me will stay here and can be moved back at any time."
            elif state_filter == "watch-later" and not self._has_active_filters():
                title = "Your Watch Later list is empty"
                icon = "folder-watch-later"
                message = "Save an anime from any card and it will appear in this collection."
            elif has_source:
                title = "No matches found"
                icon = "search"
                message = "Try clearing or widening the active filters to bring more anime back."
            else:
                title = "Build your first feed"
                icon = "view-grid"
                message = (
                    "Generate recommendations from Home to create a personal anime feed."
                )
            self.empty_title_label.setText(title)
            self._set_empty_icon(icon)
            self.empty_label.setText(message)
            self.refill_button.setVisible(exhausted)
            self.clear_filters_button.setVisible(has_source and self._has_active_filters())
            self.browse_liked_button.setVisible(
                exhausted and bool(self.local_state.liked_mal_ids)
            )
            self.content_stack.setCurrentIndex(self.empty_index)
            return
        self.view_bar.setVisible(True)
        self.filter_toggle_button.setVisible(True)
        self.refill_button.setVisible(False)
        self.clear_filters_button.setVisible(False)
        self.browse_liked_button.setVisible(False)
        self.content_stack.setCurrentIndex(
            {
                RecommendationViewMode.CARDS: self.card_index,
                RecommendationViewMode.LIST: self.list_index,
                RecommendationViewMode.TABLE: self.table_index,
            }[self._view_mode]
        )

    def _rebuild_rows(self) -> None:
        """Bring the compact list in line with the visible models.

        CHANGE [BUG1]: reuses rows for the same reason cards are reused. Both
        views are kept in step, so a rebuild of one was a rebuild of both.
        """
        # CHANGE [BUG1]: see _rebuild_cards. Only the visible layout is built.
        if self._view_mode is not RecommendationViewMode.LIST:
            return
        wanted = [
            (self._key_by_model[id(model)], model) for model in self._visible_models
        ]
        wanted_keys = {key for key, _model in wanted}

        for key in [key for key in self._rows_by_key if key not in wanted_keys]:
            row = self._rows_by_key.pop(key)
            # CHANGE [BUG1]: hide before detaching, as in _rebuild_cards.
            row.hide()
            self.list_layout.removeWidget(row)
            row.setParent(None)
            row.deleteLater()

        # Detach the trailing stretch so order can be reapplied cheaply.
        while self.list_layout.count():
            item = self.list_layout.takeAt(self.list_layout.count() - 1)
            if item.widget() is not None:
                item.widget().setParent(self.list_container)

        for key, model in wanted:
            row = self._rows_by_key.get(key)
            if row is None:
                row = self._build_row(key, model)
                self._rows_by_key[key] = row
            row.set_local_state(
                hidden=model.mal_id in self.local_state.hidden_mal_ids,
                watch_later=model.mal_id in self.local_state.watch_later_mal_ids,
                actions_enabled=self.can_review and model.mal_id is not None,
                liked=model.mal_id in self.local_state.liked_mal_ids,
                disliked=model.mal_id in self.local_state.disliked_mal_ids,
            )
            row.set_cover_visible(self.show_covers)
            row.show()
            self.list_layout.addWidget(row)
        self.list_layout.addStretch()

    def _build_row(self, key: str, model: RecommendationViewModel):
        row = RecommendationRow(model, self.list_container)
        row.selection_requested.connect(
            lambda _model, selected_key=key: self.select_key(selected_key)
        )
        row.details_requested.connect(self._open_details)
        row.hide_requested.connect(self._toggle_hidden)
        row.watch_later_requested.connect(self._toggle_watch_later)
        row.liked_requested.connect(lambda model: self._toggle_feedback(model, "liked"))
        row.disliked_requested.connect(
            lambda model: self._toggle_feedback(model, "disliked")
        )
        row.cover_requested.connect(
            lambda url, selected_key=key: self._request_cover(selected_key, url)
        )
        return row

    def _rebuild_cards(self) -> None:
        """Bring the card grid in line with the visible models.

        CHANGE [BUG1]: this used to delete every card and build them all again
        on any change. A single Like did that five times over, roughly 3,500
        child widgets, taking about a second, and the feed visibly tore down
        and came back each time. That is what reads as things flashing open and
        shut, and it is the main reason the interface felt slow.

        Cards are now reused. Only titles that actually entered or left the
        view are created or destroyed, and the rest are updated in place, so
        nothing is torn down for a state change that does not need it.
        """
        # CHANGE [BUG1]: only build the layout that is on screen. Both the card
        # grid and the list rows were being built every time regardless of which
        # one was visible, which doubled the widget count for nothing. With a
        # global stylesheet, every extra widget is re-polished on a theme
        # change, and that repolish is what a theme switch actually costs.
        if self._view_mode is not RecommendationViewMode.CARDS:
            return
        wanted = [
            (self._key_by_model[id(model)], model) for model in self._visible_models
        ]
        wanted_keys = {key for key, _model in wanted}

        for key in [key for key in self._cards_by_key if key not in wanted_keys]:
            card = self._cards_by_key.pop(key)
            # CHANGE [BUG1]: hide before detaching. setParent(None) makes a
            # widget a top-level window, and a widget that was visible keeps
            # its "explicitly shown" state, so Qt re-shows it as a real window
            # on the next event loop turn: a blank frame with a title bar that
            # vanishes when deleteLater finally runs. That is the flashing seen
            # on Like, Watch Later and anything else that refilters the feed.
            card.hide()
            self.card_layout.removeWidget(card)
            card.setParent(None)
            card.deleteLater()

        for key, model in wanted:
            card = self._cards_by_key.get(key)
            if card is None:
                card = self._build_card(key, model)
                self._cards_by_key[key] = card
            card.set_local_state(
                hidden=model.mal_id in self.local_state.hidden_mal_ids,
                watch_later=model.mal_id in self.local_state.watch_later_mal_ids,
                actions_enabled=self.can_review and model.mal_id is not None,
                liked=model.mal_id in self.local_state.liked_mal_ids,
                disliked=model.mal_id in self.local_state.disliked_mal_ids,
            )
            card.set_cover_visible(self.show_covers)
            card.set_badge_colours(*_badge_colours())
        self._reflow_cards()
        self._schedule_visible_covers()

    def _build_card(self, key: str, model: RecommendationViewModel):
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
        return card

    def _set_empty_icon(self, name: str) -> None:
        """Paint the empty-state mark from the interface icon set.

        CHANGE [DEFECT-ICON]: the glyph was tinted ``resolvedAccent`` and the
        stylesheet paints this label's background ``$accent`` - a brass mark
        on a brass plate, which rendered as a solid brass square with no icon
        in it on every empty state. The stylesheet already declares the right
        answer next to the background it sets (``color: $accent_contrast``);
        a QLabel pixmap does not read that property, so the contrast colour
        has to be handed to the renderer here.
        """
        self._empty_icon_name = name
        pixmap = ui_icon_pixmap(
            name, _resolved_colour("resolvedAccentContrast", "#0A120E"), 32
        )
        if pixmap.isNull():
            self.empty_icon_label.clear()
        else:
            self.empty_icon_label.setPixmap(pixmap)

    def retint_icons(self) -> None:
        """Re-render the view selectors after a theme change.

        A QIcon holds rendered pixmaps, not a colour reference, so switching
        themes re-styles every widget but leaves the glyphs painted in the
        previous theme's colour until they are rebuilt.
        """
        self._set_empty_icon(getattr(self, "_empty_icon_name", "view-grid"))
        for button, name in (
            (self.filter_toggle_button, "filter"),
            (self.cards_button, "view-grid"),
            (self.list_button, "view-list"),
            (self.table_button, "view-table"),
        ):
            button.setIcon(themed_ui_icon(name))

    def _reflow_cards(self) -> None:
        cards = list(self._cards_by_key.values())
        self._equalise_card_heights(cards)
        # CHANGE [SCROLL-FLICKER]: emptying the layout and re-adding every
        # widget is what a column-count change needs; it is not what a
        # scroll-triggered top-up needs. Appending five cards used to take
        # all forty out of the grid and put them back, which relaid the whole
        # feed under the pointer. When the column count and the order of the
        # existing cards are both unchanged, only the new cards are placed.
        gap = self.card_layout.horizontalSpacing()
        minimum = scaled(CARD_WIDTH)
        available = max(self.card_scroll.viewport().width(), minimum)
        columns = max(1, (available + gap) // (minimum + gap))
        keys = tuple(self._cards_by_key)
        previous_columns, previous_keys = getattr(self, "_laid_out", (0, ()))
        appended = (
            previous_columns == columns
            and len(keys) > len(previous_keys)
            and keys[: len(previous_keys)] == previous_keys
        )
        if appended:
            for index in range(len(previous_keys), len(keys)):
                self.card_layout.addWidget(
                    cards[index],
                    index // columns,
                    index % columns,
                    Qt.AlignmentFlag.AlignTop,
                )
            self._laid_out = (columns, keys)
            for column in range(max(columns, self.card_layout.columnCount())):
                self.card_layout.setColumnStretch(column, 1 if column < columns else 0)
            return
        while self.card_layout.count():
            self.card_layout.takeAt(0)
        # CHANGE [SCALE]: the cards are laid out at scaled(CARD_WIDTH), so
        # measuring the stride with the unscaled constant counted one
        # column too many at any GUI scale above 100% and pushed the last
        # one off the right edge. scaling.py says as much in its own
        # docstring: hand-chosen pixel sizes go through scaled().
        # CHANGE [SCALE]: the cards are laid out at scaled(CARD_WIDTH), so
        # measuring the stride with the unscaled constant counted one column
        # too many at any GUI scale above 100%.
        #
        # CHANGE [MARGIN]: n columns need n widths and n-1 gaps, not n of
        # each. Counting a trailing gap that is never drawn understated how
        # many cards fit, and the layout's AlignLeft then piled every leftover
        # pixel - measured at 108 to 111 of them - against the right edge as a
        # margin nobody asked for. The columns share the row now.
        gap = self.card_layout.horizontalSpacing()
        minimum = scaled(CARD_WIDTH)
        available = max(self.card_scroll.viewport().width(), minimum)
        columns = max(1, (available + gap) // (minimum + gap))
        for index, card in enumerate(cards):
            self.card_layout.addWidget(
                card,
                index // columns,
                index % columns,
                Qt.AlignmentFlag.AlignTop,
            )
        self._laid_out = (columns, tuple(self._cards_by_key))
        # Every column that holds a card takes an equal share of the width;
        # any column left over from a previous, wider layout takes none.
        for column in range(max(columns, self.card_layout.columnCount())):
            self.card_layout.setColumnStretch(column, 1 if column < columns else 0)

    # Qt's "no maximum". Not exported by PySide6, so it is spelled out.
    _UNCONSTRAINED_HEIGHT = 16777215

    def _invalidate_card_height(self) -> None:
        """Forget the measured card height so the next reflow measures again.

        CHANGE [SCROLL-FLICKER]: only a change of GUI scale or font scale can
        change it. Width cannot: every wrapped label on the card reserves a
        fixed number of lines, so a card's natural height is 511px at a 700px
        viewport and 511px at a 1042px one.
        """
        self._card_height = 0

    def _equalise_card_heights(self, cards) -> None:
        """CHANGE [BUG7]: give every card in the grid the same height.

        Cards sized themselves to their own content, and content varies: a
        title that wraps to two lines, a missing English title, a longer genre
        list. In a QGridLayout each row is then as tall as its tallest card and
        the shorter ones leave a ragged gap beneath them, which is what reads
        as the grid not lining up.

        The height is measured, not assumed, so it follows the GUI scale and
        the font scale without a second set of constants to keep in step. The
        constraint is lifted before measuring, or the previous height would be
        all sizeHint could report and the cards could only ever grow.

        CHANGE [SCROLL-FLICKER]: the measurement is cached. Re-measuring
        means lifting the height constraint on every card first, and a grid
        of forty briefly-unconstrained cards re-lays out to a different
        height before being pinned back - visible as the feed jumping while
        a top-up lands. Measured across a top-up and four resizes, every one
        of those passes recomputed the same 511px it already had.
        """
        if not cards:
            return
        tallest = getattr(self, "_card_height", 0)
        if tallest <= 0:
            for card in cards:
                card.setMinimumHeight(0)
                card.setMaximumHeight(self._UNCONSTRAINED_HEIGHT)
            tallest = max(card.sizeHint().height() for card in cards)
            if tallest <= 0:
                return
            self._card_height = tallest
        for card in cards:
            if card.minimumHeight() != tallest or card.maximumHeight() != tallest:
                card.setFixedHeight(tallest)

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
        if not self.can_review or model is None or model.mal_id is None:
            return
        wanted = model.mal_id not in self.local_state.hidden_mal_ids
        if self.profile_id is None:
            self.local_state = _toggle_in_memory(
                self.local_state, "hidden_mal_ids", model.mal_id, wanted
            )
        else:
            self.local_state = self.state_service.set_hidden(
                self.profile_id,
                model.mal_id,
                wanted,
            )
        self._apply_query()
        self._sync_detail_local_state()

    def _toggle_watch_later(self, model: RecommendationViewModel | None) -> None:
        if not self.can_review or model is None or model.mal_id is None:
            return
        wanted = model.mal_id not in self.local_state.watch_later_mal_ids
        if self.profile_id is None:
            self.local_state = _toggle_in_memory(
                self.local_state, "watch_later_mal_ids", model.mal_id, wanted
            )
        else:
            self.local_state = self.state_service.set_watch_later(
                self.profile_id,
                model.mal_id,
                wanted,
            )
        self._apply_query()
        self._sync_detail_local_state()

    def _toggle_feedback(
        self, model: RecommendationViewModel | None, sentiment: str
    ) -> None:
        if not self.can_review or model is None or model.mal_id is None:
            return
        active_ids = (
            self.local_state.liked_mal_ids
            if sentiment == "liked"
            else self.local_state.disliked_mal_ids
        )
        next_sentiment = None if model.mal_id in active_ids else sentiment
        if self.profile_id is None:
            self.local_state = _feedback_in_memory(
                self.local_state,
                model.mal_id,
                next_sentiment,
                genres=model.genres,
                title=model.display_title,
            )
        else:
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
        # CHANGE [READOUT]: these were paragraph-length sentences written for
        # a full-width band. On the control bar that band collapsed into, the
        # longest of them ran off the end mid-word. They are status readouts
        # now: same facts, told the way the rest of the bar tells them.
        if not self.can_review:
            text = "NO PROFILE · REVIEWING DISABLED"
        elif self.profile_id is None:
            # Sample data. Reviewing works and reshapes the feed, but the
            # result is not kept, so say so rather than implying it is saved.
            text = (
                f"SAMPLE · {likes} LIKED · {dislikes} PASSED "
                "· CONNECT TO KEEP"
            )
        elif not likes and not dislikes:
            # Named for what is actually tested - a saved profile - rather
            # than for a "model" this application does not have.
            text = "PROFILE READY · VOTE TO SHAPE THE FEED"
        else:
            text = f"VOTES SAVED · {likes} LIKED · {dislikes} PASSED"
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
            self.detail_dialog.previous_requested.connect(
                lambda: self._step_detail(-1)
            )
            self.detail_dialog.next_requested.connect(
                lambda: self._step_detail(1)
            )
            self.detail_dialog.liked_requested.connect(
                lambda model: self._toggle_feedback(model, "liked")
            )
            self.detail_dialog.disliked_requested.connect(
                lambda model: self._toggle_feedback(model, "disliked")
            )
        self._set_detail_model(model)
        self.detail_dialog.show()
        self.detail_dialog.raise_()
        self.detail_dialog.activateWindow()

    def _set_detail_model(self, model: RecommendationViewModel) -> None:
        if self.detail_dialog is None:
            return
        self.detail_dialog.set_model(model)
        self.detail_dialog.set_cover_visible(self.show_covers)
        # CHANGE [DETAIL-COVER]: show the artwork the feed already has while
        # the larger one is fetched.
        #
        # The dialog asks for `large_cover_url`, which is a different URL from
        # the card's, so opening the breakdown always started a fresh download
        # and sat on the placeholder for as long as it took. The feed has
        # usually already downloaded the smaller image for the very card that
        # was clicked; showing it costs nothing and is replaced the moment the
        # large one lands.
        if self.show_covers and model.cover_url:
            cached = self._cover_data_by_url.get(model.cover_url)
            if cached is not None:
                self.detail_dialog.set_cover_data(cached)
        models = self._models or (model,)
        try:
            index = models.index(model)
        except ValueError:
            index = 0
        self.detail_dialog.set_navigation(index + 1, len(models))
        self._sync_detail_local_state()

    def _step_detail(self, offset: int) -> None:
        if self.detail_dialog is None or self.detail_dialog.model is None:
            return
        models = self._models
        if len(models) < 2:
            return
        try:
            current_index = models.index(self.detail_dialog.model)
        except ValueError:
            current_index = 0
        self._set_detail_model(models[(current_index + offset) % len(models)])

    def _sync_detail_local_state(self) -> None:
        if self.detail_dialog is None or self.detail_dialog.model is None:
            return
        mal_id = self.detail_dialog.model.mal_id
        self.detail_dialog.set_local_state(
            hidden=mal_id in self.local_state.hidden_mal_ids,
            watch_later=mal_id in self.local_state.watch_later_mal_ids,
            actions_enabled=self.can_review and mal_id is not None,
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
            sweep = getattr(self, "scan_sweep", None)
            if sweep is not None:
                sweep.setGeometry(self.card_scroll.viewport().rect())
        return super().eventFilter(watched, event)

    def set_autoload_enabled(self, enabled: bool) -> None:
        """Turn endless scrolling on or off for this surface."""
        self._autoload_enabled = bool(enabled)

    def _consider_autoload(self) -> None:
        """Debounce a scroll gesture into at most one fetch request."""
        if not self._autoload_enabled:
            return
        if self._view_mode is not RecommendationViewMode.CARDS:
            return
        if self._more_running or not self._more_available:
            return
        bar = self.card_scroll.verticalScrollBar()
        # A feed that does not scroll cannot be scrolled to the bottom of, and
        # would otherwise satisfy the threshold permanently and fetch forever.
        if bar.maximum() <= 0:
            return
        if bar.maximum() - bar.value() > AUTOLOAD_TRIGGER_PX:
            return
        self._autoload_timer.start()

    def _autoload_now(self) -> None:
        """Fire one top-up, if every guard still agrees."""
        if not self._autoload_enabled or self._more_running or not self._more_available:
            return
        now = monotonic()
        if now < self._autoload_blocked_until:
            return
        bar = self.card_scroll.verticalScrollBar()
        if bar.maximum() <= 0 or bar.maximum() - bar.value() > AUTOLOAD_TRIGGER_PX:
            return
        # Hold the gate until the worker reports back, and in any case for a
        # minimum interval, so a stalled or failed fetch cannot be retried on
        # every subsequent scroll event.
        self._autoload_blocked_until = now + AUTOLOAD_COOLDOWN_S
        self.set_more_running(True)
        self.more_requested.emit()

    def _schedule_visible_covers(self) -> None:
        if self._view_mode is RecommendationViewMode.CARDS:
            QTimer.singleShot(0, self._request_visible_covers)

    def _request_visible_covers(self) -> None:
        """Fetch artwork for whatever is on screen, in either layout.

        CHANGE [BUG3]: the list layout showed no portraits at all, because this
        only ever considered the card grid. Rows have a thumbnail and were
        never asking for one, so they sat on the placeholder forever.
        """
        if not self.show_covers:
            return
        if self.content_stack.currentIndex() == self.card_index:
            container, scroll = self.card_container, self.card_scroll
            widgets = self._cards_by_key.values()
        elif self.content_stack.currentIndex() == self.list_index:
            container, scroll = self.list_container, self.list_scroll
            widgets = self._rows_by_key.values()
        else:
            return

        origin = container.mapFrom(scroll.viewport(), QPoint(0, 0))
        visible_rect = scroll.viewport().rect().translated(origin)
        requested = 0
        for widget in widgets:
            if requested >= self.MAX_COVER_REQUESTS_PER_PASS:
                break
            if widget.geometry().intersects(visible_rect):
                before = len(self._cover_attempted)
                widget.request_cover()
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
        self._cover_failures.pop(url, None)
        # CHANGE [COVER-RETRY]: a finished download frees a slot in the
        # per-pass budget, so ask again for whatever is still on screen
        # without artwork. Otherwise anything past the sixth visible card
        # waited for a scroll that a reader with a full window never makes.
        self._schedule_visible_covers()
        # CHANGE [BUG3]: deliver to rows as well, not only cards.
        landed = ""
        for card in self._cards_by_key.values():
            if card.model.cover_url == url:
                card.set_cover_data(result.data)
                landed = card.model.display_title
        if landed:
            self.artwork_retrieved.emit(landed)
        for row in self._rows_by_key.values():
            if row.model.cover_url == url:
                row.set_cover_data(result.data)
        if self.detail_dialog is not None and self.detail_dialog.model is not None:
            detail_url = (
                self.detail_dialog.model.large_cover_url
                or self.detail_dialog.model.cover_url
            )
            if detail_url == url:
                self.detail_dialog.set_cover_data(result.data)

    def _on_worker_error(self, operation_key: str, _error: object) -> None:
        """Let a cover that failed be asked for again.

        CHANGE [COVER-RETRY]: this used to drop only the operation mapping and
        leave the URL in ``_cover_attempted``, which is the set
        ``_request_cover`` checks before doing anything. So one failed
        download - a dropped connection, a timeout, anything transient - meant
        that card kept its placeholder for the rest of the session no matter
        how long anyone waited, and no scroll or resize could recover it.

        The reason this looked survivable is that the detail dialog asks for
        ``large_cover_url``, a different URL that was never marked attempted.
        Opening the breakdown therefore fetched the artwork and made the feed
        look like the slow one rather than the broken one.

        Retries are bounded: a URL that has failed MAX_COVER_ATTEMPTS times
        stays attempted, so a genuinely dead link is not re-requested on every
        pass.
        """
        url = self._cover_operation_urls.pop(operation_key, None)
        if url is None:
            return
        failures = self._cover_failures.get(url, 0) + 1
        self._cover_failures[url] = failures
        if failures < self.MAX_COVER_ATTEMPTS:
            self._cover_attempted.discard(url)
            self._schedule_visible_covers()
