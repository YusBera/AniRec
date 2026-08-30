"""Top-level AniRec desktop window and navigation shell.

Addresses: BUG1 (flashing popups), BUG2 (DPI and GUI scale), FEAT2 (match badge).

BUG1 root cause and fix strategy
--------------------------------
Reported as "multiple popups flash open and closed" when pressing Recommend 5
More. Measured rather than assumed, and it is none of the three usual suspects:

* not listener duplication. ``more_requested`` has exactly one receiver.
* not re-instantiation from a re-render. Qt widgets here are built once.
* not a missing event guard on the click itself.

What actually happens is that every operation start called
``show_operation_progress``, which opens a modal progress dialog, and that
dialog closes itself a moment after the work succeeds. Fetching more
recommendations reads an already generated candidate pool from disk, so it
finishes almost immediately. The dialog therefore appears and vanishes, which
is exactly the reported flash. Several can overlap because the button stays
enabled until the worker thread actually starts, because the automatic refill
prompt starts a second operation of its own, and because a failure adds a
non modal ErrorDialog on top.

Fix strategy: stop reporting routine background work through windows at all.
These operations already have two inline affordances, the button text and the
Discover status line, so progress and failure are now reported there. The
dialog classes and ``show_operation_progress`` remain for explicit callers,
but nothing opens them automatically. A guard also disables the action the
moment it is pressed, and the existing finished handler re-enables it, so a
second press cannot start a second run and the control always comes back.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..application.pipeline import PipelineOrchestrator
from ..errors import AniRecError, UserFacingError
from ..metadata import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    MINIMUM_WINDOW_HEIGHT,
    MINIMUM_WINDOW_WIDTH,
)
from ..models import AppSettings, PipelineResult, UserProfile
from ..services import (
    AuthService,
    DataManagementService,
    OnboardingService,
    ProfileService,
    ProfileStatisticsService,
    RecommendationStateService,
    ResultService,
    BundleContextService,
    SampleDataService,
    SettingsService,
    TasteFeedbackService,
    TokenStore,
)
from .advanced_operations_page import AdvancedOperationsPage
from .about_page import AboutPage
from .compare_page import ComparePage
from .compatibility import (
    CompatibilityUnavailable,
    SampleCompatibilityProvider,
    UnavailableCompatibilityProvider,
    UnavailableReason,
)
from .discover_page import DiscoverPage
from .profile_lookup import ProfileLookupService
from .profile_page import ProfilePage
from .taste_profile import (
    LocalTasteProfileProvider,
    SampleTasteProfileProvider,
    TasteProfileProvider,
    TasteProfileUnavailable,
    UnavailableTasteProfileProvider,
)
from .home_page import ACTION_GENERATE, ACTION_SYNC, HomePage
from .genre_analysis_page import GenreAnalysisPage
from .instrument_widgets import (
    ChannelWipe,
    InstrumentPanel,
    NavMarker,
    Scanlines,
    StatusLight,
)
from .error_dialog import ErrorDialog
from .progress_dialog import OperationProgressDialog
from .recommendation_page import RecommendationExplorerPage
from .resources import (
    app_icon,
    clear_cover_placeholder_cache,
    clear_ui_icon_cache,
    placeholder_pixmap,
    themed_ui_icon,
)
from .design_tokens import SPACE
from .scaling import set_gui_scale
from .settings_page import SettingsPage
from .system_log import SystemLog
from .setup_wizard import SetupWizard
from .texts import COMPARE_TEXT, FILTER_TEXT, UI_TEXT, WIZARD_TEXT
from .theme import ThemeManager
from .workers import (
    MoreRecommendationsWorker,
    OperationAlreadyRunningError,
    RecommendationWorker,
    SyncWorker,
    WorkerController,
    operation_key,
)


class PageId(str, Enum):
    DISCOVER = "discover"
    LIBRARY = "library"
    # CHANGE [PROFILE]: a surface about the reader rather than about the
    # catalogue. It sits between the library it is derived from and the
    # comparison it makes sense of: you read your own taste, then you read
    # somebody else's against it.
    PROFILE = "profile"
    # CHANGE [COMPARE]: a fourth surface, and the first one that is about
    # somebody else. It sits after the two that are about the user's own
    # library and before Settings, which is where the rail already puts the
    # things you configure rather than the things you read.
    COMPARE = "compare"
    SETTINGS = "settings"


@dataclass(frozen=True)
class PageDefinition:
    page_id: PageId
    label: str
    description: str


# Three surfaces. What used to be a dashboard, a genre analysis page and a
# seven step pipeline view now live inside Discover, or behind the developer
# tools switch in Settings for anyone who wants the individual steps.
PAGE_DEFINITIONS = (
    PageDefinition(PageId.DISCOVER, UI_TEXT.pages[0].label, UI_TEXT.pages[0].description),
    PageDefinition(PageId.LIBRARY, UI_TEXT.pages[1].label, UI_TEXT.pages[1].description),
    PageDefinition(PageId.PROFILE, UI_TEXT.pages[2].label, UI_TEXT.pages[2].description),
    PageDefinition(PageId.COMPARE, UI_TEXT.pages[3].label, UI_TEXT.pages[3].description),
    PageDefinition(PageId.SETTINGS, UI_TEXT.pages[4].label, UI_TEXT.pages[4].description),
)

# TODO [ICON]: temporary. Every rail row is drawn from ``nav-<page>.svg`` and
# there is no ``nav-profile.svg`` yet - the icon set is being drawn separately.
# Until it lands the row borrows the existing profile mark, which is the right
# subject at the wrong weight; delete this map when the asset arrives.
NAV_ICON_OVERRIDES = {PageId.PROFILE: "profile"}


def nav_icon_name(page_id: PageId) -> str:
    return NAV_ICON_OVERRIDES.get(page_id, f"nav-{page_id.value}")

# Collections shown on each surface.
DISCOVER_STATES = ("all",)
LIBRARY_STATES = ("liked", "watch-later", "disliked")


class SystemReadout(QFrame):
    """A fixed set of key/value rows reporting live application state.

    Deliberately fixed: the rows are declared once and only their values
    change, so the rail never reflows and the eye can learn where each fact
    lives. Values are short enough to be read without being read.
    """

    ROWS = ("ENGINE", "SOURCE", "PROFILE", "MAL")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("systemReadout")
        self.setAccessibleName("System state")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 12)
        layout.setSpacing(3)

        caption = QLabel("SYSTEM")
        caption.setObjectName("railCaption")
        layout.addWidget(caption)
        layout.addSpacing(3)

        self._values: dict[str, QLabel] = {}
        self._lamps: dict[str, StatusLight] = {}
        for key in self.ROWS:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(SPACE["xs"])
            lamp = StatusLight("off")
            name = QLabel(key)
            name.setObjectName("readoutKey")
            value = QLabel("--")
            value.setObjectName("readoutValue")
            value.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            row.addWidget(lamp)
            row.addWidget(name)
            row.addStretch()
            row.addWidget(value)
            layout.addLayout(row)
            self._values[key] = value
            self._lamps[key] = lamp

    # How each readout tone maps onto a lamp.
    _LAMP_FOR_TONE = {
        "ok": "ok",
        "warn": "warn",
        "busy": "busy",
        "idle": "off",
        "error": "error",
    }

    def set_value(self, key: str, text: str, *, tone: str = "idle") -> None:
        label = self._values.get(key)
        if label is None:
            return
        changed = label.text() != str(text)
        label.setText(str(text))
        label.setProperty("tone", tone)
        label.setAccessibleName(f"{key} {text}")
        label.style().unpolish(label)
        label.style().polish(label)

        lamp = self._lamps.get(key)
        if lamp is not None:
            lamp.set_state(self._LAMP_FOR_TONE.get(tone, "off"))
            if changed:
                # A changed reading swells its lamp and settles. This used to
                # invert the text's background for three hard frames, which
                # strobed rather than drew the eye.
                lamp.flash()


class ConnectionStatusBar(InstrumentPanel):
    """Reusable display for the active profile and MAL connection state."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("connectionStatusBar")
        self.setAccessibleName("Profile and MyAnimeList connection status")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(14)

        self.profile_label = QLabel()
        self.profile_label.setObjectName("activeProfileLabel")
        self.mal_status_label = QLabel()
        self.mal_status_label.setObjectName("malConnectionLabel")

        # CHANGE [DUPLICATE]: these two are NOT added to the strip. The rail's
        # system readout reports PROFILE and MAL permanently, so repeating them
        # here put the same two facts on screen twice at all times. They stay
        # as live widgets - the text is still set and still queried - they just
        # no longer occupy a second place on the glass.
        self.profile_label.setVisible(False)
        self.mal_status_label.setVisible(False)
        layout.addStretch()
        self._layout = layout
        self.set_status()

    def attach_notice(self, widget: QWidget) -> None:
        """Park a transient notice on the right of the strip.

        Sample mode used to add a second full-width banner underneath this
        one. Two stacked bars pushed the first recommendation more than
        halfway down the window, on every page, which is an expensive way to
        say something a single line can say.
        """
        self._layout.addWidget(widget)

    def set_status(self, profile_name: str | None = None, *, mal_connected: bool = False) -> None:
        safe_name = profile_name.strip() if profile_name and profile_name.strip() else None
        self.profile_label.setText(
            UI_TEXT.active_profile_template.format(profile_name=safe_name)
            if safe_name
            else UI_TEXT.no_active_profile
        )
        self.mal_status_label.setText(
            UI_TEXT.mal_connected if mal_connected else UI_TEXT.mal_disconnected
        )
        self.mal_status_label.setProperty("connected", mal_connected)
        self.mal_status_label.style().unpolish(self.mal_status_label)
        self.mal_status_label.style().polish(self.mal_status_label)


class MainWindow(QMainWindow):
    """Main application window with a usable first-run shell."""

    sync_requested = Signal()
    recommendations_requested = Signal()
    output_folder_opened = Signal(object)

    def __init__(
        self,
        *,
        profile_service: ProfileService | None = None,
        result_service: ResultService | None = None,
        onboarding_service: OnboardingService | None = None,
        auth_service: AuthService | None = None,
        pipeline_orchestrator: PipelineOrchestrator | None = None,
        recommendation_state_service: RecommendationStateService | None = None,
        settings_service: SettingsService | None = None,
        token_store: TokenStore | None = None,
        data_management_service: DataManagementService | None = None,
        theme_manager: ThemeManager | None = None,
        taste_profile_provider: TasteProfileProvider | None = None,
    ) -> None:
        super().__init__()
        self.profile_service = profile_service
        self.result_service = result_service
        self.onboarding_service = onboarding_service
        self.auth_service = auth_service
        self.pipeline_orchestrator = pipeline_orchestrator
        self.recommendation_state_service = (
            recommendation_state_service or RecommendationStateService()
        )
        self.taste_feedback_service = TasteFeedbackService()
        self.settings_service = settings_service or SettingsService()
        self.token_store = token_store or TokenStore()
        self.data_management_service = data_management_service or DataManagementService()
        self.active_profile: UserProfile | None = None
        self.setup_wizard: SetupWizard | None = None
        self.sample_data_service = SampleDataService()
        # CHANGE [BUNDLE-WIRING]: what the feed needs to fold a franchise.
        # Read from the profile directory, best effort: no graph means the
        # feed reads exactly as it always has.
        self.bundle_context_service = BundleContextService()
        self.demo_mode = False
        # CHANGE [COMPARE]: what ships wired up is the provider that refuses,
        # with a reason. Nothing on the Compare surface invents a match score,
        # and the surface says so rather than showing an empty page that looks
        # like a fault. The recorded sample is offered from that state, and is
        # stamped when it is shown.
        self.compatibility_provider = UnavailableCompatibilityProvider()
        self.sample_compatibility_provider = SampleCompatibilityProvider()
        # The local provider reads only the synchronized MAL snapshots. It has
        # no dependency on candidate generation or recommendation ranking.
        # A bare test shell still gets the explicit refusing provider.
        self.taste_profile_provider = taste_profile_provider or (
            LocalTasteProfileProvider(ProfileStatisticsService(profile_service))
            if profile_service is not None
            else UnavailableTasteProfileProvider()
        )
        self.sample_taste_profile_provider = SampleTasteProfileProvider()
        # Mirrored state for the rail's system readout. Kept here rather
        # than interrogated from widgets so the panel cannot disagree
        # with what the window believes.
        self._engine_busy = False
        self._mal_connected = False
        self._profile_name: str | None = None
        self.theme_manager = theme_manager
        self.setObjectName("mainWindow")
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        self.setMinimumSize(MINIMUM_WINDOW_WIDTH, MINIMUM_WINDOW_HEIGHT)
        self.navigation_buttons: dict[PageId, QPushButton] = {}
        self.page_indexes: dict[PageId, int] = {}
        self.page_widgets: dict[PageId, QWidget] = {}
        self.worker_controller = WorkerController(self)
        # One lookup for both surfaces, with one session cache in front of it,
        # so the same username typed on Discover and on Compare costs one
        # request and cannot produce two different verdicts.
        self.profile_lookup = ProfileLookupService(
            worker_controller=self.worker_controller,
            profile_service=profile_service,
            settings_service=self.settings_service,
            parent=self,
        )
        self.profile_lookup.resolved.connect(self._on_profile_lookup_resolved)
        self.operation_dialogs: dict[str, OperationProgressDialog] = {}
        self.error_dialogs: dict[str, ErrorDialog] = {}
        self._last_more_count = 5
        # CHANGE [BUG1]: retry state for the last failure, offered inline.
        self._pending_retry = None
        self.setCentralWidget(self._build_shell())
        self._connect_dashboard_actions()
        self.sync_requested.connect(self._start_sync)
        self.recommendations_requested.connect(self._start_recommendations)
        self.worker_controller.started.connect(self._on_operation_started)
        self.worker_controller.finished.connect(self._on_operation_finished)
        self.worker_controller.result_ready.connect(self._on_operation_result)
        self.worker_controller.error_occurred.connect(self._on_operation_error)
        self.refresh_dashboard()
        self._apply_settings(self.settings_service.load())
        self.navigate_to(PageId.DISCOVER)
        if self.onboarding_service is not None and self.onboarding_service.needs_setup():
            QTimer.singleShot(0, lambda: self.open_setup_wizard(force=False))

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.worker_controller.shutdown():
            event.accept()
        else:
            event.ignore()

    def show_operation_progress(self, operation_key: str) -> OperationProgressDialog:
        dialog = self.operation_dialogs.get(operation_key)
        if dialog is None:
            dialog = OperationProgressDialog(operation_key, self.worker_controller, self)
            dialog.finished.connect(
                lambda _result, key=operation_key: self.operation_dialogs.pop(key, None)
            )
            self.operation_dialogs[operation_key] = dialog
        dialog.show()
        dialog.raise_()
        return dialog

    def open_setup_wizard(self, *, force: bool = True) -> SetupWizard | None:
        if self.onboarding_service is None:
            return None
        if not force and not self.onboarding_service.needs_setup():
            return None
        if self.setup_wizard is not None and self.setup_wizard.isVisible():
            self.setup_wizard.raise_()
            self.setup_wizard.activateWindow()
            return self.setup_wizard
        wizard = SetupWizard(
            self.onboarding_service,
            self,
            auth_service=self.auth_service,
            pipeline_orchestrator=self.pipeline_orchestrator,
            result_service=self.result_service,
            worker_controller=self.worker_controller,
        )
        wizard.finished.connect(self._on_setup_finished)
        wizard.demo_requested.connect(self._enter_demo_mode)
        self.setup_wizard = wizard
        wizard.show()
        return wizard

    def _enter_demo_mode(self) -> None:
        """Show the bundled sample library so AniRec can be judged before setup."""
        result = self.sample_data_service.load()
        if result is None:
            return
        self.demo_mode = True
        if self.setup_wizard is not None:
            self.setup_wizard.reject()
        for view in self._recommendation_views():
            # No profile, so nothing is written to disk, but the review
            # loop still works in memory. Being able to press Like and
            # watch the feed respond is the point of looking around.
            view.set_profile(None)
            view.set_ephemeral(True)
            view.set_recommendations(result.recommendations)
        self.discover_page.set_genre_stats(result.genre_stats)
        self._publish_studio_names()
        self._publish_bundle_context()
        self.genre_analysis_page.set_genre_stats(result.genre_stats)
        self.home_page.set_state(None, result)
        self.demo_banner.setVisible(True)
        self._refresh_system_readout()
        self._log(
            "source",
            f"sample vault mounted · {len(result.recommendations)} records",
        )
        self.navigate_to(PageId.DISCOVER)

    def _leave_demo_mode(self) -> None:
        self.demo_mode = False
        for view in self._recommendation_views():
            view.set_ephemeral(False)
        self.demo_banner.setVisible(False)
        self._refresh_system_readout()
        self._log("source", "sample vault released · awaiting uplink")
        self.open_setup_wizard()

    def _on_setup_finished(self, result: int) -> None:
        if result == int(QDialog.DialogCode.Accepted):
            settings = self.settings_service.load()
            self.settings_page.reload()
            self._apply_settings(settings)
        self.refresh_dashboard()
        if result == int(QDialog.DialogCode.Accepted):
            self.navigate_to(PageId.DISCOVER)

    def refresh_dashboard(self) -> None:
        # Sample data stands in for a library that does not exist yet, so a
        # refresh would only replace it with nothing.
        if self.demo_mode:
            return
        profile = None
        result = None
        if self.profile_service is not None:
            try:
                profile = self.profile_service.active_profile()
            except (AniRecError, OSError, TypeError, ValueError):
                profile = None
        if profile is not None and self.result_service is not None:
            try:
                result = self.result_service.load(profile.profile_id)
            except (AniRecError, OSError, TypeError, ValueError):
                result = None
        self.active_profile = profile
        display_result = result
        local_state = None
        if profile is not None:
            local_state = self.recommendation_state_service.load(profile.profile_id)
        if result is not None and local_state is not None:
            display_result = replace(
                result,
                recommendations=self.taste_feedback_service.personalize(
                    result.recommendations, local_state
                ),
            )
        self.home_page.set_state(profile, display_result)
        stats = result.genre_stats if result else ()
        # Discover and My Library are two views of one library, so both are
        # given the same profile and the same recommendations.
        for view in self._recommendation_views():
            view.set_profile(profile.profile_id if profile else None)
            view.set_recommendations(
                display_result.recommendations if display_result else ()
            )
        self.genre_analysis_page.set_genre_stats(stats)
        self.discover_page.set_genre_stats(stats)
        self._publish_studio_names()
        self._publish_bundle_context()
        # The two lines that used to be asserted at construction, reported
        # here instead - each only when the thing it names actually happened,
        # and each carrying the count that proves it.
        if result is not None:
            self._log(
                "source",
                f"local vault mounted · {len(result.recommendations)} records",
            )
        if stats:
            self._log("engine", f"taste vector restored · {len(stats)} genres")
        self.advanced_operations_page.set_profile(profile)
        self._refresh_compare_context()
        self.settings_page.set_context(profile)
        settings = self.settings_service.load()
        mal_connected = bool(profile and settings.client_id)
        self._profile_name = profile.username if profile else None
        self._mal_connected = mal_connected
        self.connection_status.set_status(
            self._profile_name,
            mal_connected=mal_connected,
        )
        self._refresh_system_readout()
        more_available = bool(
            profile
            and result
            and result.recommendations
            and self.profile_service is not None
            and (self.profile_service.directory(profile.profile_id) / "recommendation_candidates.csv").is_file()
            and (self.profile_service.directory(profile.profile_id) / "genre_importance.csv").is_file()
        )
        self.recommendations_page.set_more_available(
            more_available,
            "Generate recommendations once to create the candidate pool."
            if profile
            else "Connect a MyAnimeList profile first.",
        )

    # ---- group recommendation profiles -----------------------------------

    def _resolve_group_profile(self, username: str) -> None:
        """Look one added username up, and answer the pill when it lands.

        Every profile is its own request. Five added at once become five
        operations that start together and finish independently, so a slow
        list never holds up the others and a failure is scoped to its own
        pill.
        """
        result = self.profile_lookup.lookup(username)
        if result is not None:
            self._apply_profile_result(result)

    def _retry_group_profile(self, username: str) -> None:
        # Without forgetting the previous answer a retry would be served the
        # failure that is already on screen, which is not a retry.
        self.profile_lookup.forget(username)
        self._resolve_group_profile(username)

    def _on_profile_lookup_resolved(self, result) -> None:
        self._apply_profile_result(result)

    def _apply_profile_result(self, result) -> None:
        page = getattr(self, "recommendations_page", None)
        if page is None:
            return
        if result.ok:
            page.set_profile_resolved(result.username, result.username)
            self._log("uplink", f"profile resolved · {result.username}")
        else:
            page.set_profile_failed(result.username, result.message)
            self._log("uplink", f"profile refused · {result.username}")
        compare = getattr(self, "compare_page", None)
        if compare is not None and compare.is_loading:
            self._continue_comparison(result)

    def _on_discover_filters_changed(self, parameters) -> None:
        """Report what the feed is being asked for, and what cannot be honoured.

        The genre, studio, year and score filters are applied to the records
        already loaded, which is what the feed has always done. Ranking for
        several profiles at once is not something the frontend can do or
        should: it needs the scoring engine to blend several taste vectors,
        and that does not exist. So the profiles are collected, reported, and
        the surface says plainly that the results below are still the user's
        own until a backend answers.
        """
        profiles = parameters.get("profile") or []
        page = self.recommendations_page
        if not profiles:
            page.set_group_notice("")
            return
        page.set_group_notice(FILTER_TEXT.group_pending)

    # ---- compare ---------------------------------------------------------

    def _start_comparison(self, username: str) -> None:
        """Ask the provider for one comparison and draw whatever comes back."""
        page = self.compare_page
        page.show_loading(username)
        try:
            report = self.compatibility_provider.compare(username)
        except CompatibilityUnavailable as error:
            page.show_unavailable(error, offer_sample=True)
            return
        page.show_report(report)
        page.request_visible_covers()

    def _show_sample_comparison(self) -> None:
        """Draw the bundled example, stamped as one.

        Offered from the "not built yet" state so the surface can be judged
        before the capability exists - the same bargain the sample library
        already makes for the feed, and marked the same way.
        """
        page = self.compare_page
        username = page.username_input.text().strip()
        if not username:
            friends = ()
            try:
                friends = self.sample_compatibility_provider.friends()
            except CompatibilityUnavailable:
                pass
            if not friends:
                return
            page.set_friends(friends)
            username = friends[0].username
        try:
            report = self.sample_compatibility_provider.compare(username)
        except CompatibilityUnavailable as error:
            page.show_unavailable(error)
            return
        page.show_report(report)
        page.request_visible_covers()

    # ---- profile ---------------------------------------------------------

    def _load_taste_profile(self) -> None:
        """Ask the provider for this reader's profile and draw what comes back."""
        page = self.profile_page
        page.show_loading()
        try:
            profile = self.taste_profile_provider.taste_profile()
        except TasteProfileUnavailable as error:
            page.show_unavailable(error, offer_sample=True)
            return
        page.show_profile(profile)
        page.request_visible_covers()

    def _show_sample_taste_profile(self) -> None:
        """Draw the bundled example, stamped as one.

        Offered from the "not built yet" state, exactly as Compare offers its
        sample comparison, so the surface can be judged before the capability
        exists without any figure on it claiming to be the reader's own.
        """
        page = self.profile_page
        try:
            profile = self.sample_taste_profile_provider.taste_profile()
        except TasteProfileUnavailable as error:
            page.show_unavailable(error)
            return
        page.show_profile(profile)
        page.request_visible_covers()

    def _filter_discover_by_metadata(self, kind, value: str) -> None:
        """A genre or studio pressed on the Profile page.

        Goes to the same filter state a card's tag goes to, and then to the
        surface that state belongs to: pressing "Isekai" on a panel that has
        just told you it is your weakest genre is a request to go and look at
        the ones you have not watched.
        """
        self.recommendations_page.filter_state.add_value(kind, str(value))
        self.navigate_to(PageId.DISCOVER)

    def _continue_comparison(self, _result) -> None:
        """Placeholder for the live path once a provider exists.

        The lookup resolving is what would let a real provider start work. It
        is not wired to one today because there is nothing to start, and
        pretending otherwise would leave the surface spinning forever.
        """
        return

    def _refresh_compare_context(self) -> None:
        """Tell Compare who "you" are, and what its friends list can be.

        Both facts move with the active profile: the friends list is that
        account's, and comparing a list with itself is only refusable once the
        surface knows which list is yours.
        """
        page = getattr(self, "compare_page", None)
        if page is None:
            return
        page.set_own_username(self.active_profile.username if self.active_profile else None)
        try:
            page.set_friends(self.compatibility_provider.friends())
        except CompatibilityUnavailable as error:
            page.set_friends_unavailable(error.reason)

    def _build_shell(self) -> QWidget:
        shell = QWidget()
        shell.setObjectName("applicationShell")

        layout = QHBoxLayout(shell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_sidebar())
        layout.addWidget(self._build_content_area(), 1)
        # CHANGE [CRT]: the raster goes on last and stays on top. Built after
        # the layout so it is the final child, and it re-raises itself when
        # anything else is added.
        self.scanlines = Scanlines(shell)
        self.scanlines.raise_()
        return shell

    def _build_sidebar(self) -> QFrame:
        """The navigation rail, built as a workstation front panel.

        Three destinations do not need three large pill buttons. They need an
        index, a selection mark, and the space that buys back for telling you
        what the machine is currently doing.
        """
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(214)
        sidebar.setMaximumWidth(238)
        sidebar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        plate = QWidget()
        plate.setObjectName("sidebarPlate")
        plate_layout = QVBoxLayout(plate)
        plate_layout.setContentsMargins(14, 14, 14, 12)
        plate_layout.setSpacing(1)
        title = QLabel(APP_NAME.upper())
        title.setObjectName("sidebarTitle")
        title.setAccessibleName("AniRec application title")
        subtitle = QLabel("アニレク")
        subtitle.setObjectName("sidebarKana")
        plate_layout.addWidget(title)
        plate_layout.addWidget(subtitle)
        layout.addWidget(plate)
        layout.addWidget(self._hairline())

        for index, definition in enumerate(PAGE_DEFINITIONS, start=1):
            # The index is part of the label rather than a separate widget so
            # the whole row stays one focusable, clickable control.
            button = QPushButton(f"{index:02d}   {definition.label.upper()}")
            button.setObjectName(f"navigationButton-{definition.page_id.value}")
            button.setProperty("navItem", True)
            button.setCheckable(True)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            button.setMinimumHeight(34)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            # CHANGE [NUMBERED-NAV]: the 01-05 prefixes read as a sequence -
            # a wizard you work through - on what is flat navigation you can
            # enter at any point. Rather than drop them, they are made true:
            # each number is now the key that reaches its page. The label
            # stops being decoration and starts being documentation.
            button.setShortcut(QKeySequence(f"Alt+{index}"))
            button.setAccessibleName(f"Open {definition.label} page, Alt+{index}")
            button.setToolTip(f"{definition.description}  (Alt+{index})")
            button.setIcon(themed_ui_icon(nav_icon_name(definition.page_id)))
            button.clicked.connect(
                lambda checked=False, page_id=definition.page_id: self.navigate_to(page_id)
            )
            self.navigation_buttons[definition.page_id] = button
            layout.addWidget(button)

        # One mark that travels between the rows, rather than a border colour
        # that teleports. Parented to the rail so it can be positioned across
        # button boundaries.
        self.nav_marker = NavMarker(sidebar)

        layout.addWidget(self._hairline())
        self.system_readout = SystemReadout()
        layout.addWidget(self.system_readout)
        layout.addWidget(self._hairline())
        # The console sits at the foot of the rail, under the spare height:
        # it is ambient, and pinning it below the readout put a scrolling
        # panel in the middle of the navigation.
        layout.addStretch(1)
        layout.addWidget(self._hairline())
        self.system_log = SystemLog()
        layout.addWidget(self.system_log)
        layout.addWidget(self._hairline())

        version_note = QLabel(f"BUILD {APP_VERSION}")
        version_note.setObjectName("sidebarFooter")
        version_note.setContentsMargins(14, 8, 14, 12)
        layout.addWidget(version_note)
        self._refresh_system_readout()
        # CHANGE [TELEMETRY]: three of the four lines that used to be here
        # were literals fired unconditionally at construction, before any
        # profile, vault or settings had loaded. "taste vector restored" was
        # the worst of them - it asserted a restore in the same frame the rail
        # above it truthfully reported PROFILE --, in the one panel whose job
        # is to show that this application does not invent state.
        #
        # "local vault mounted" and "taste vector restored" now come from
        # refresh_dashboard, where the load actually happens and there is a
        # real count to print. "scoring engine armed" is gone rather than
        # relocated: nothing is armed at any particular moment, and the
        # ENGINE row already reports readiness.
        # Appended, not paced through ``boot()``. The boot gate holds
        # ``_booting`` until its sequence finishes and queues every real event
        # that arrives meanwhile; with a single line there is nothing to pace,
        # and the gate only risks swallowing the genuine startup traffic that
        # follows it. ``boot()`` stays for any caller with a real sequence.
        self.system_log.append("boot", f"core {APP_VERSION} online")
        return sidebar

    @staticmethod
    def _hairline() -> QFrame:
        line = QFrame()
        line.setObjectName("railRule")
        line.setFixedHeight(1)
        return line

    def _refresh_system_readout(self) -> None:
        """Publish real machine state onto the rail.

        Every row here corresponds to something the application actually
        knows. Nothing is invented to fill the panel out.
        """
        readout = getattr(self, "system_readout", None)
        if readout is None:
            return
        busy = self._engine_busy
        readout.set_value("ENGINE", "BUSY" if busy else "READY", tone="busy" if busy else "ok")
        # CHANGE [READOUT-HONESTY]: this said LIVE for anything that was not
        # sample mode, including "you left the sample vault and connected
        # nothing" - so the rail could read SOURCE LIVE directly above
        # PROFILE -- and MAL OFFLINE, three rows apparently disagreeing about
        # whether there was any data at all. LIVE now means what a reader
        # takes it to mean: a real library is loaded.
        profile_name = self._profile_name
        if self.demo_mode:
            source, source_tone = "SAMPLE", "warn"
        elif profile_name:
            source, source_tone = "LIVE", "ok"
        else:
            source, source_tone = "NONE", "idle"
        readout.set_value("SOURCE", source, tone=source_tone)
        readout.set_value("PROFILE", profile_name or "--", tone="ok" if profile_name else "idle")
        connected = self._mal_connected
        # "warn", not "idle". Offline is a state the user can act on; an
        # absent profile is simply nothing yet. Both rendered identically
        # before, so the cluster could not tell "not connected" from "not
        # applicable" - and colour was the only thing distinguishing them.
        readout.set_value(
            "MAL", "ONLINE" if connected else "OFFLINE",
            tone="ok" if connected else "warn",
        )

    def _build_content_area(self) -> QWidget:
        content = QWidget()
        content.setObjectName("contentArea")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(26, 14, 26, 14)
        layout.setSpacing(14)

        self.connection_status = ConnectionStatusBar()
        layout.addWidget(self.connection_status)

        # Stays visible for as long as sample data is on screen, so the state
        # can never be mistaken for the user's own library. It rides on the
        # status strip rather than claiming a row of its own.
        self.demo_banner = QFrame()
        self.demo_banner.setObjectName("demoBanner")
        banner_layout = QHBoxLayout(self.demo_banner)
        banner_layout.setContentsMargins(0, 0, 0, 0)
        banner_layout.setSpacing(10)
        banner_label = QLabel(WIZARD_TEXT.demo_banner)
        banner_label.setObjectName("demoBannerText")
        banner_button = QPushButton(WIZARD_TEXT.demo_banner_action)
        # Secondary, not primary: this is a standing notice, not the action
        # the screen is asking for. Two solid amber buttons in the top 180px
        # meant neither of them read as the primary one.
        banner_button.setProperty("buttonRole", "secondary")
        banner_button.clicked.connect(self._leave_demo_mode)
        banner_layout.addWidget(banner_label)
        banner_layout.addWidget(banner_button)
        self.demo_banner.setVisible(False)
        self.connection_status.attach_notice(self.demo_banner)

        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("pageStack")
        # The dashboard and genre analysis still exist as widgets; they are now
        # composed into Discover rather than being destinations of their own.
        self.home_page = HomePage(worker_controller=self.worker_controller)
        self.genre_analysis_page = GenreAnalysisPage()
        self.advanced_operations_page = AdvancedOperationsPage(
            worker_controller=self.worker_controller,
            orchestrator=self.pipeline_orchestrator,
            profile_service=self.profile_service,
            settings_service=self.settings_service,
            auth_service=self.auth_service,
        )
        self.about_page = AboutPage()

        for definition in PAGE_DEFINITIONS:
            if definition.page_id is PageId.DISCOVER:
                self.recommendations_page = RecommendationExplorerPage(
                    worker_controller=self.worker_controller,
                    state_service=self.recommendation_state_service,
                )
                self.recommendations_page.set_visible_states(DISCOVER_STATES)
                self.recommendations_page.set_compact_header(True)
                # Only Discover. My Library files what has already been
                # decided, and another person's taste has no bearing on it.
                self.recommendations_page.set_group_profiles_enabled(True)
                self.recommendations_page.profile_requested.connect(
                    self._resolve_group_profile
                )
                self.recommendations_page.profile_retry_requested.connect(
                    self._retry_group_profile
                )
                self.recommendations_page.filters_changed.connect(
                    self._on_discover_filters_changed
                )
                page = DiscoverPage(self.recommendations_page)
                page.refresh_requested.connect(self.recommendations_requested.emit)
                self.discover_page = page
            elif definition.page_id is PageId.LIBRARY:
                self.library_page = RecommendationExplorerPage(
                    worker_controller=self.worker_controller,
                    state_service=self.recommendation_state_service,
                )
                self.library_page.set_visible_states(LIBRARY_STATES)
                self.library_page.set_compact_header(True)
                page = self.library_page
            elif definition.page_id is PageId.PROFILE:
                page = ProfilePage()
                page.retry_requested.connect(self._load_taste_profile)
                page.sample_requested.connect(self._show_sample_taste_profile)
                page.metadata_filter_requested.connect(
                    self._filter_discover_by_metadata
                )
                self.profile_page = page
            elif definition.page_id is PageId.COMPARE:
                page = ComparePage()
                page.compare_requested.connect(self._start_comparison)
                page.sample_requested.connect(self._show_sample_comparison)
                self.compare_page = page
            elif definition.page_id is PageId.SETTINGS:
                page = SettingsPage(
                    settings_service=self.settings_service,
                    profile_service=self.profile_service,
                    token_store=self.token_store,
                    auth_service=self.auth_service,
                    worker_controller=self.worker_controller,
                    data_management=self.data_management_service,
                    advanced_page=self.advanced_operations_page,
                    about_page=self.about_page,
                    theme_manager=self.theme_manager,
                )
                self.settings_page = page
            else:
                page = self._build_placeholder_page(definition)
            index = self.page_stack.addWidget(page)
            self.page_indexes[definition.page_id] = index
            self.page_widgets[definition.page_id] = page
        layout.addWidget(self.page_stack, 1)
        # The page-change wipe rides on the stack itself, so it spans the
        # page and nothing else. Bounded and opaque, unlike the whole-page
        # fade it replaced.
        self.page_wipe = ChannelWipe(self.page_stack)
        return content

    @staticmethod
    def _build_placeholder_page(definition: PageDefinition) -> QWidget:
        page = QWidget()
        page.setObjectName(f"page-{definition.page_id.value}")
        page.setAccessibleName(f"{definition.label} page")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        title = QLabel(definition.label)
        title.setObjectName("pageTitle")
        title.setAccessibleName(f"{definition.label} heading")
        description = QLabel(definition.description)
        description.setObjectName("pageDescription")
        description.setWordWrap(True)

        artwork = QLabel()
        artwork.setObjectName("placeholderArtwork")
        artwork.setAccessibleName("AniRec placeholder artwork")
        pixmap = placeholder_pixmap()
        if not pixmap.isNull():
            artwork.setPixmap(
                pixmap.scaled(
                    360,
                    220,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(16)
        layout.addWidget(artwork, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        return page

    def _connect_dashboard_actions(self) -> None:
        self.home_page.generate_requested.connect(self.recommendations_requested.emit)
        self.home_page.sync_requested.connect(self.sync_requested.emit)
        self.home_page.open_recommendations_requested.connect(
            lambda: self.navigate_to(PageId.DISCOVER)
        )
        self.home_page.view_genres_requested.connect(
            lambda: self.navigate_to(PageId.DISCOVER)
        )
        self.home_page.open_folder_requested.connect(self._open_active_output_folder)
        self.settings_page.open_setup_requested.connect(
            lambda: self.open_setup_wizard(force=True)
        )
        self.settings_page.show_hidden_changed.connect(
            self.recommendations_page.set_show_hidden_preference
        )
        self.settings_page.settings_saved.connect(self._apply_settings)
        self.settings_page.profile_changed.connect(lambda _profile: self.refresh_dashboard())
        self.settings_page.local_data_reset.connect(
            lambda: self._apply_settings(AppSettings())
        )
        self.recommendations_page.show_hidden_changed.connect(
            lambda value: self.settings_page.set_show_hidden(
                value, enabled=self.active_profile is not None
            )
        )
        self.recommendations_page.feedback_changed.connect(
            lambda _state: self.refresh_dashboard()
        )
        for view in (self.recommendations_page, self.library_page):
            view.view_mode_changed.connect(self._persist_view_mode)
        # CHANGE [BUG2]: rebuild the sized widgets when the GUI scale changes.
        self.settings_page.gui_scale_changed.connect(self._on_gui_scale_changed)
        self.settings_page.show_covers_changed.connect(self._on_show_covers_changed)
        for view in self._recommendation_views():
            view.artwork_retrieved.connect(
                lambda title: self._log("retriev", f"artwork acquired · {title}")
            )
        self.recommendations_page.more_requested.connect(
            lambda: self._start_more_recommendations(5)
        )
        self.recommendations_page.refill_requested.connect(
            lambda: self._start_more_recommendations(10)
        )

    def _start_sync(self) -> bool:
        if self.active_profile is None or self.pipeline_orchestrator is None:
            return False
        key = operation_key("sync", self.active_profile.profile_id)
        # CHANGE [BUG1]: report progress inline instead of opening a window.
        if self.worker_controller.is_running(key):
            return False
        worker = SyncWorker(
            self.pipeline_orchestrator,
            self.active_profile.username,
            self.settings_service.load().pipeline,
        )
        try:
            self.worker_controller.start(key, worker)
        except OperationAlreadyRunningError:
            return False
        # CHANGE [BUG1]: no progress window; the button and status line report it.
        return True

    def _start_recommendations(self) -> bool:
        if self.active_profile is None or self.pipeline_orchestrator is None:
            return False
        key = operation_key("recommendation", self.active_profile.profile_id)
        # CHANGE [BUG1]: report progress inline instead of opening a window.
        if self.worker_controller.is_running(key):
            return False
        state = self.recommendation_state_service.load(self.active_profile.profile_id)
        # Generation stays feedback-neutral on purpose. TasteFeedbackService
        # applies votes once, on the display path, so that a like is not counted
        # both in the stored score and again when the feed is rendered.
        worker = RecommendationWorker(
            self.pipeline_orchestrator,
            self.active_profile.username,
            self.settings_service.load().pipeline,
            excluded_mal_ids=state.disliked_mal_ids | state.hidden_mal_ids,
        )
        try:
            self.worker_controller.start(key, worker)
        except OperationAlreadyRunningError:
            return False
        # CHANGE [BUG1]: no progress window; the button and status line report it.
        return True

    def _start_more_recommendations(self, count: int = 5) -> bool:
        if (
            self.active_profile is None
            or self.pipeline_orchestrator is None
            or self.result_service is None
        ):
            return False
        existing = self.result_service.load(self.active_profile.profile_id)
        if existing is None or not existing.recommendations:
            return False
        key = operation_key("more-recommendations", self.active_profile.profile_id)
        # CHANGE [BUG1]: a second press must not start a second run.
        if self.worker_controller.is_running(key):
            return False
        # CHANGE [BUG1]: guard immediately, before the worker thread starts, and
        # let _on_operation_finished clear it so later presses still work.
        for view in self._recommendation_views():
            view.set_more_running(True)
        self._more_guard_engaged = True
        self._last_more_count = max(1, int(count))
        state = self.recommendation_state_service.load(self.active_profile.profile_id)
        worker = MoreRecommendationsWorker(
            self.pipeline_orchestrator,
            self.active_profile.username,
            self.settings_service.load().pipeline,
            existing_recommendations=existing.recommendations,
            excluded_mal_ids=state.disliked_mal_ids | state.hidden_mal_ids,
            count=self._last_more_count,
        )
        try:
            self.worker_controller.start(key, worker)
        except OperationAlreadyRunningError:
            # CHANGE [BUG1]: clear the guard on every path that gives up after
            # setting it, or the control stays disabled for good.
            for view in self._recommendation_views():
                view.set_more_running(False)
            return False
        # CHANGE [BUG1]: no progress window; the button and status line report it.
        return True

    def _on_show_covers_changed(self, show_covers: bool) -> None:
        """Artwork on or off, applied without re-running the whole settings."""
        for view in self._recommendation_views():
            view.set_show_covers(bool(show_covers))

    def _on_gui_scale_changed(self, factor: float) -> None:
        """CHANGE [BUG2]: cards and rows are built with fixed sizes, so a scale
        change has to rebuild them rather than just restyle."""
        set_gui_scale(factor)
        for view in self._recommendation_views():
            view.rebuild_for_scale()

    def _persist_view_mode(self, mode: str) -> None:
        """Remember the layout choice, so it survives a restart."""
        try:
            settings = self.settings_service.load()
            if settings.recommendation_view_mode == mode:
                return
            self.settings_service.save_preferences(
                replace(settings, recommendation_view_mode=mode)
            )
        except (AniRecError, OSError, TypeError, ValueError):
            # A preference is not worth interrupting the session over.
            return

    def _publish_bundle_context(self) -> None:
        """Give Discover what it needs to fold franchises, and only Discover.

        My Library is a record of decisions the reader has already made about
        individual titles. Collapsing three of them into "1 series" there
        would hide the very thing that surface exists to show, so the library
        explorer is handed the same context with bundling switched off.
        """
        directory = None
        profile = self.active_profile
        if profile is not None and self.profile_service is not None:
            try:
                directory = self.profile_service.directory(profile.profile_id)
            except (AniRecError, OSError, TypeError, ValueError):
                directory = None
        context = self.bundle_context_service.load(directory)

        feed = getattr(self, "recommendations_page", None)
        if feed is not None:
            feed.set_bundle_context(
                context.graph, context.watched_mal_ids, enabled=True
            )
        library = getattr(self, "library_page", None)
        if library is not None:
            library.set_bundle_context({}, (), enabled=False)

    def _publish_studio_names(self) -> None:
        """Tell the taste sentence which of its ranked terms are studios.

        The importance ranking mixes genres and studios in one list, which is
        correct for scoring and wrong for a sentence: "You tend to enjoy
        Samurai, Bandai Namco Pictures, Parody, Shaft" reads like a bug. The
        explorer already keeps a catalogue of every studio it has actually
        seen, so the split needs no new source of truth - only for the two
        halves of the application to be introduced to each other.
        """
        names: set[str] = set()
        for view in self._recommendation_views():
            catalog = getattr(view, "metadata_catalog", None)
            if catalog is not None:
                names.update(catalog.studios)
        self.discover_page.set_studio_names(names)

    def _recommendation_views(self):
        """Every explorer instance that should reflect the same library."""
        return tuple(
            view
            for view in (
                getattr(self, "recommendations_page", None),
                getattr(self, "library_page", None),
            )
            if view is not None
        )

    def _apply_settings(self, settings: AppSettings) -> None:
        manager = self.theme_manager
        if manager is None:
            application = QApplication.instance()
            if isinstance(application, QApplication):
                manager = ThemeManager(application)
                self.theme_manager = manager
        if manager is not None:
            # CHANGE [BUG2]: text scales with the GUI scale as well, so the
            # whole interface grows together rather than geometry alone.
            set_gui_scale(settings.gui_scale)
            manager.apply(
                settings.theme,
                font_scale=settings.font_scale,
                gui_scale=settings.gui_scale,
                gradient_start=settings.gradient_start,
                gradient_end=settings.gradient_end,
            )
        self._retint_icons()
        profile_page = getattr(self, "profile_page", None)
        if profile_page is not None:
            profile_page.apply_scale()
        self._log(
            "render",
            f"{settings.theme} palette bound · x{settings.gui_scale:.2f}",
        )
        for view in self._recommendation_views():
            view.set_default_sort(settings.default_recommendation_sort)
            view.set_show_covers(settings.show_covers)
            view.set_view_mode(settings.recommendation_view_mode)
        if self.active_profile is not None:
            for view in self._recommendation_views():
                view.set_show_hidden_preference(
                    settings.include_hidden_recommendations
                )
        self.advanced_operations_page.refresh_prerequisites()

    # Human-readable names for the worker keys the controller emits.
    _OPERATION_NAMES = {
        "sync": "library uplink",
        "recommendations": "scoring pass",
        "more": "feed extension",
    }

    @staticmethod
    def _operation_name(operation_key: str) -> str:
        text = str(operation_key or "operation")
        for token, name in MainWindow._OPERATION_NAMES.items():
            if token in text:
                return name
        return text

    def _log(self, tag: str, message: str) -> None:
        """Write one line to the activity console, if it exists yet."""
        console = getattr(self, "system_log", None)
        if console is not None:
            console.append(tag, message)

    def _log_progress(self, tag: str, percent: float, message: str = "") -> None:
        console = getattr(self, "system_log", None)
        if console is not None:
            console.progress(tag, percent, message)

    def _retint_icons(self) -> None:
        """Rebuild every themed glyph after the palette changes.

        The rendered pixmaps are cached by colour, so the cache is dropped
        first; otherwise the next request returns the previous theme's tint.
        The cover placeholder is rendered the same way and goes with them.
        """
        clear_ui_icon_cache()
        clear_cover_placeholder_cache()
        console = getattr(self, "system_log", None)
        if console is not None:
            console.retint()
        for definition in PAGE_DEFINITIONS:
            button = self.navigation_buttons.get(definition.page_id)
            if button is not None:
                button.setIcon(themed_ui_icon(nav_icon_name(definition.page_id)))
        # CHANGE [PROFILE]: Compare and Profile both paint state marks from
        # the icon set, and Compare was not in this list, so its empty-state
        # glyph kept the previous palette's tint until the page was rebuilt.
        for page in (
            self.discover_page,
            self.compare_page,
            self.profile_page,
            *self._recommendation_views(),
        ):
            retint = getattr(page, "retint_icons", None)
            if callable(retint):
                retint()

    def _open_active_output_folder(self) -> None:
        if self.profile_service is None or self.active_profile is None:
            return
        path = self.profile_service.open_directory(self.active_profile.profile_id)
        self.output_folder_opened.emit(path)

    def _report_activity(self, message: str, *, tone: str = "success") -> None:
        """Show progress where the user can see it.

        HomePage keeps the dashboard state, but it is composed into Discover
        rather than being a page of its own, so its own activity line is no
        longer on screen. Discover carries the visible one.
        """
        self.home_page.show_activity(message, tone=tone)
        self.discover_page.set_status(message, tone=tone)
        self._log("error" if tone == "error" else "status", message)

    def _on_operation_started(self, operation_key: str) -> None:
        self._engine_busy = True
        self._refresh_system_readout()
        self._log("engine", f"{self._operation_name(operation_key)} engaged")
        if operation_key.startswith("sync:"):
            self.home_page.set_operation_running(ACTION_SYNC, True)
            self.discover_page.set_refreshing(True)
        elif operation_key.startswith("recommendation:"):
            self.home_page.set_operation_running(ACTION_GENERATE, True)
            self.discover_page.set_refreshing(True)
        elif operation_key.startswith("more-recommendations:"):
            self.recommendations_page.set_more_running(True)

    def _on_operation_finished(self, operation_key: str) -> None:
        self._engine_busy = False
        self._refresh_system_readout()
        self._log("engine", f"{self._operation_name(operation_key)} resolved")
        if operation_key.startswith("sync:"):
            self.home_page.set_operation_running(ACTION_SYNC, False)
            self.discover_page.set_refreshing(False)
        elif operation_key.startswith("recommendation:"):
            self.home_page.set_operation_running(ACTION_GENERATE, False)
            self.discover_page.set_refreshing(False)
        elif operation_key.startswith("more-recommendations:"):
            self.recommendations_page.set_more_running(False)

    def _on_operation_result(self, operation_key: str, result: object) -> None:
        if not isinstance(result, PipelineResult):
            return
        if self.active_profile is None or self.result_service is None:
            return
        operation_profile_id = operation_key.partition(":")[2]
        if operation_profile_id != self.active_profile.profile_id:
            return
        self.result_service.save_merged(self.active_profile.profile_id, result)
        if operation_key.startswith("sync:"):
            completed = result.user_stats.get("completed_count", 0)
            self._report_activity(
                f"MAL data updated: {completed} completed titles synced.",
                tone="success",
            )
        elif operation_key.startswith("more-recommendations:"):
            added = result.user_stats.get("added_recommendation_count", 0)
            self._report_activity(
                f"Added {added} new feedback-aware recommendations.",
                tone="success",
            )
        elif operation_key.startswith("recommendation:"):
            self._report_activity(
                "Your recommendation feed has been refreshed.", tone="success"
            )
        self.refresh_dashboard()

    def _on_operation_error(self, operation_key: str, error: object) -> None:
        if operation_key.startswith("cover") or not isinstance(error, UserFacingError):
            return
        # An open modal wizard reports its own failures inline. Raising a second,
        # non-modal dialog here would be blocked by the wizard's modality and
        # leave the user with an error box they cannot close.
        wizard = self.setup_wizard
        if (
            wizard is not None
            and wizard.isVisible()
            and wizard.owns_operation(operation_key)
        ):
            return
        # CHANGE [BUG1]: report failures inline rather than opening a window.
        # An error box that appears on top of a progress box that is already
        # closing itself is what produced the reported flashing. The message,
        # what to do about it, and a retry all live on the surface the user is
        # already looking at. Technical detail stays reachable from the log
        # folder button in Settings.
        self._report_activity(f"{error.title} {error.solution}".strip(), tone="error")
        if error.retryable:
            retry = self._retry_callback(operation_key)
            if retry is not None:
                self._offer_retry(operation_key, retry)

    def _offer_retry(self, operation_key: str, retry) -> None:
        """Expose a retry for a failed operation without opening a window."""
        # CHANGE [BUG1]: retry is offered through the surface, not a dialog.
        self._pending_retry = (operation_key, retry)

    def retry_last_failure(self) -> bool:
        """Run the retry recorded by the last failure, if there is one."""
        # CHANGE [BUG1]: replaces the retry button that lived on the error dialog.
        pending = getattr(self, "_pending_retry", None)
        if pending is None:
            return False
        _key, retry = pending
        self._pending_retry = None
        return bool(retry())

    def _retry_callback(self, operation_key: str):
        if operation_key.startswith("advanced-"):
            step_id = operation_key.partition(":")[0].removeprefix("advanced-")
            return lambda: self.advanced_operations_page.run_step(step_id)
        if operation_key == self.settings_page.API_TEST_KEY:
            return self.settings_page.test_api_connection
        if operation_key.startswith("settings-token-refresh:"):
            return self.settings_page.refresh_token
        if operation_key.startswith("sync:"):
            return self._retry_sync
        if operation_key.startswith("recommendation:"):
            return self._retry_recommendations
        if operation_key.startswith("more-recommendations:"):
            return lambda: self._start_more_recommendations(self._last_more_count)
        if self.setup_wizard is not None:
            if operation_key == self.setup_wizard.connection_operation_key:
                return self.setup_wizard._start_api_test_from_current
            if operation_key == self.setup_wizard.analysis_operation_key:
                return self.setup_wizard._retry_analysis
        return None

    def _retry_sync(self) -> bool:
        self.sync_requested.emit()
        return True

    def _retry_recommendations(self) -> bool:
        self.recommendations_requested.emit()
        return True

    def navigate_to(self, page_id: PageId | str) -> None:
        """Select a page and keep visual/navigation state synchronized."""
        resolved_page_id = PageId(page_id)
        changed = self.page_stack.currentIndex() != self.page_indexes[resolved_page_id]
        self.page_stack.setCurrentIndex(self.page_indexes[resolved_page_id])
        for page_id, button in self.navigation_buttons.items():
            button.setChecked(page_id is resolved_page_id)
        self._move_nav_marker(resolved_page_id)
        if resolved_page_id is PageId.PROFILE and changed:
            self._load_taste_profile()
        if changed:
            self._mark_page_change()

    def _move_nav_marker(self, page_id: PageId) -> None:
        """Send the rail's selection mark to the row that is now current."""
        marker = getattr(self, "nav_marker", None)
        button = self.navigation_buttons.get(page_id)
        if marker is None or button is None:
            return
        # No guard on the target's geometry here. Before the rail is laid out
        # a nav button reports the rail's full height rather than its own, so
        # there is nothing to test for - the mark takes whatever it is given
        # and NavMarker re-syncs itself when the rail lays out.
        marker.move_to(button)

    def _mark_page_change(self) -> None:
        """Run the wipe across the top of the page that just came up.

        Deliberately not an opacity fade over the page: that buffers the whole
        surface every frame and measured at five to seven frames on the card
        feed, which reads as a stutter. This is a two-pixel opaque strip and
        costs nothing underneath it.
        """
        wipe = getattr(self, "page_wipe", None)
        if wipe is None:
            return
        wipe.run()

    @property
    def current_page_id(self) -> PageId:
        current_index = self.page_stack.currentIndex()
        return next(
            page_id for page_id, index in self.page_indexes.items() if index == current_index
        )
