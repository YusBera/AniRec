"""Top-level AniRec desktop window and navigation shell."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QCloseEvent
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
    RecommendationStateService,
    ResultService,
    SettingsService,
    TasteFeedbackService,
    TokenStore,
)
from .advanced_operations_page import AdvancedOperationsPage
from .about_page import AboutPage
from .home_page import ACTION_GENERATE, ACTION_SYNC, HomePage
from .genre_analysis_page import GenreAnalysisPage
from .error_dialog import ErrorDialog
from .progress_dialog import OperationProgressDialog
from .recommendation_page import RecommendationExplorerPage
from .resources import app_icon, placeholder_pixmap
from .settings_page import SettingsPage
from .setup_wizard import SetupWizard
from .texts import UI_TEXT
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
    HOME = "home"
    RECOMMENDATIONS = "recommendations"
    GENRE_ANALYSIS = "genre-analysis"
    ADVANCED_OPERATIONS = "advanced-operations"
    SETTINGS = "settings"
    ABOUT = "about"


@dataclass(frozen=True)
class PageDefinition:
    page_id: PageId
    label: str
    description: str


PAGE_DEFINITIONS = (
    PageDefinition(PageId.HOME, UI_TEXT.pages[0].label, UI_TEXT.pages[0].description),
    PageDefinition(
        PageId.RECOMMENDATIONS,
        UI_TEXT.pages[1].label,
        UI_TEXT.pages[1].description,
    ),
    PageDefinition(
        PageId.GENRE_ANALYSIS,
        UI_TEXT.pages[2].label,
        UI_TEXT.pages[2].description,
    ),
    PageDefinition(
        PageId.ADVANCED_OPERATIONS,
        UI_TEXT.pages[3].label,
        UI_TEXT.pages[3].description,
    ),
    PageDefinition(PageId.SETTINGS, UI_TEXT.pages[4].label, UI_TEXT.pages[4].description),
    PageDefinition(PageId.ABOUT, UI_TEXT.pages[5].label, UI_TEXT.pages[5].description),
)


class ConnectionStatusBar(QFrame):
    """Reusable display for the active profile and MAL connection state."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("connectionStatusBar")
        self.setAccessibleName("Profile and MyAnimeList connection status")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(16)

        self.profile_label = QLabel()
        self.profile_label.setObjectName("activeProfileLabel")
        self.mal_status_label = QLabel()
        self.mal_status_label.setObjectName("malConnectionLabel")

        layout.addWidget(self.profile_label)
        layout.addStretch()
        layout.addWidget(self.mal_status_label)
        self.set_status()

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
        self.setObjectName("mainWindow")
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        self.setMinimumSize(MINIMUM_WINDOW_WIDTH, MINIMUM_WINDOW_HEIGHT)
        self.navigation_buttons: dict[PageId, QPushButton] = {}
        self.page_indexes: dict[PageId, int] = {}
        self.page_widgets: dict[PageId, QWidget] = {}
        self.worker_controller = WorkerController(self)
        self.operation_dialogs: dict[str, OperationProgressDialog] = {}
        self.error_dialogs: dict[str, ErrorDialog] = {}
        self._last_more_count = 5
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
        self.navigate_to(PageId.HOME)
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
        self.setup_wizard = wizard
        wizard.show()
        return wizard

    def _on_setup_finished(self, result: int) -> None:
        if result == int(QDialog.DialogCode.Accepted):
            settings = self.settings_service.load()
            self.settings_page.reload()
            self._apply_settings(settings)
        self.refresh_dashboard()
        if result == int(QDialog.DialogCode.Accepted):
            self.navigate_to(PageId.HOME)

    def refresh_dashboard(self) -> None:
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
        self.recommendations_page.set_profile(profile.profile_id if profile else None)
        self.recommendations_page.set_recommendations(
            display_result.recommendations if display_result else ()
        )
        self.genre_analysis_page.set_genre_stats(result.genre_stats if result else ())
        self.advanced_operations_page.set_profile(profile)
        self.settings_page.set_context(profile)
        settings = self.settings_service.load()
        mal_connected = bool(profile and settings.client_id)
        self.connection_status.set_status(
            profile.username if profile else None,
            mal_connected=mal_connected,
        )
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

    def _build_shell(self) -> QWidget:
        shell = QWidget()
        shell.setObjectName("applicationShell")

        layout = QHBoxLayout(shell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_sidebar())
        layout.addWidget(self._build_content_area(), 1)
        return shell

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(208)
        sidebar.setMaximumWidth(248)
        sidebar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 24, 16, 20)
        layout.setSpacing(8)

        title = QLabel(APP_NAME)
        title.setObjectName("sidebarTitle")
        title.setAccessibleName("AniRec application title")
        layout.addWidget(title)
        layout.addSpacing(24)

        for definition in PAGE_DEFINITIONS:
            button = QPushButton(definition.label)
            button.setObjectName(f"navigationButton-{definition.page_id.value}")
            button.setCheckable(True)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            button.setMinimumHeight(42)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setAccessibleName(f"Open {definition.label} page")
            button.clicked.connect(
                lambda checked=False, page_id=definition.page_id: self.navigate_to(page_id)
            )
            self.navigation_buttons[definition.page_id] = button
            layout.addWidget(button)

        layout.addStretch()
        version_note = QLabel(UI_TEXT.sidebar_footer)
        version_note.setObjectName("sidebarFooter")
        layout.addWidget(version_note)
        return sidebar

    def _build_content_area(self) -> QWidget:
        content = QWidget()
        content.setObjectName("contentArea")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(20)

        self.connection_status = ConnectionStatusBar()
        layout.addWidget(self.connection_status)

        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("pageStack")
        for definition in PAGE_DEFINITIONS:
            if definition.page_id is PageId.HOME:
                page = HomePage(worker_controller=self.worker_controller)
                self.home_page = page
            elif definition.page_id is PageId.RECOMMENDATIONS:
                page = RecommendationExplorerPage(
                    worker_controller=self.worker_controller,
                    state_service=self.recommendation_state_service,
                )
                self.recommendations_page = page
            elif definition.page_id is PageId.GENRE_ANALYSIS:
                page = GenreAnalysisPage()
                self.genre_analysis_page = page
            elif definition.page_id is PageId.ADVANCED_OPERATIONS:
                page = AdvancedOperationsPage(
                    worker_controller=self.worker_controller,
                    orchestrator=self.pipeline_orchestrator,
                    profile_service=self.profile_service,
                    settings_service=self.settings_service,
                    auth_service=self.auth_service,
                )
                self.advanced_operations_page = page
            elif definition.page_id is PageId.ABOUT:
                page = AboutPage()
            elif definition.page_id is PageId.SETTINGS:
                page = SettingsPage(
                    settings_service=self.settings_service,
                    profile_service=self.profile_service,
                    token_store=self.token_store,
                    auth_service=self.auth_service,
                    worker_controller=self.worker_controller,
                    data_management=self.data_management_service,
                )
                self.settings_page = page
            else:
                page = self._build_placeholder_page(definition)
            index = self.page_stack.addWidget(page)
            self.page_indexes[definition.page_id] = index
            self.page_widgets[definition.page_id] = page
        layout.addWidget(self.page_stack, 1)
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
            lambda: self.navigate_to(PageId.RECOMMENDATIONS)
        )
        self.home_page.view_genres_requested.connect(
            lambda: self.navigate_to(PageId.GENRE_ANALYSIS)
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
        if self.worker_controller.is_running(key):
            self.show_operation_progress(key)
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
        self.show_operation_progress(key)
        return True

    def _start_recommendations(self) -> bool:
        if self.active_profile is None or self.pipeline_orchestrator is None:
            return False
        key = operation_key("recommendation", self.active_profile.profile_id)
        if self.worker_controller.is_running(key):
            self.show_operation_progress(key)
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
        self.show_operation_progress(key)
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
        if self.worker_controller.is_running(key):
            self.show_operation_progress(key)
            return False
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
            return False
        self.show_operation_progress(key)
        return True

    def _apply_settings(self, settings: AppSettings) -> None:
        application = QApplication.instance()
        if isinstance(application, QApplication):
            manager = getattr(application, "_anirec_theme_manager", None)
            if not isinstance(manager, ThemeManager):
                manager = ThemeManager(application)
                application._anirec_theme_manager = manager
            manager.apply(settings.theme, font_scale=settings.font_scale)
        self.recommendations_page.set_default_sort(settings.default_recommendation_sort)
        self.recommendations_page.set_show_covers(settings.show_covers)
        if self.active_profile is not None:
            self.recommendations_page.set_show_hidden_preference(
                settings.include_hidden_recommendations
            )
        self.advanced_operations_page.refresh_prerequisites()

    def _open_active_output_folder(self) -> None:
        if self.profile_service is None or self.active_profile is None:
            return
        path = self.profile_service.open_directory(self.active_profile.profile_id)
        self.output_folder_opened.emit(path)

    def _on_operation_started(self, operation_key: str) -> None:
        if operation_key.startswith("sync:"):
            self.home_page.set_operation_running(ACTION_SYNC, True)
        elif operation_key.startswith("recommendation:"):
            self.home_page.set_operation_running(ACTION_GENERATE, True)
        elif operation_key.startswith("more-recommendations:"):
            self.recommendations_page.set_more_running(True)

    def _on_operation_finished(self, operation_key: str) -> None:
        if operation_key.startswith("sync:"):
            self.home_page.set_operation_running(ACTION_SYNC, False)
        elif operation_key.startswith("recommendation:"):
            self.home_page.set_operation_running(ACTION_GENERATE, False)
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
            self.home_page.show_activity(
                f"MAL data updated — {completed} completed titles synced.",
                tone="success",
            )
        elif operation_key.startswith("more-recommendations:"):
            added = result.user_stats.get("added_recommendation_count", 0)
            self.home_page.show_activity(
                f"Added {added} new feedback-aware recommendations.",
                tone="success",
            )
        elif operation_key.startswith("recommendation:"):
            self.home_page.show_activity(
                "Your recommendation feed has been refreshed.", tone="success"
            )
        self.refresh_dashboard()

    def _on_operation_error(self, operation_key: str, error: object) -> None:
        if operation_key.startswith("cover") or not isinstance(error, UserFacingError):
            return
        if operation_key.startswith(("sync:", "recommendation:", "more-recommendations:")):
            self.home_page.show_activity(error.title, tone="error")
        existing = self.error_dialogs.get(operation_key)
        if existing is not None and existing.isVisible():
            existing.raise_()
            return
        retry = self._retry_callback(operation_key) if error.retryable else None
        dialog = ErrorDialog(
            error,
            self,
            retry=retry,
            open_logs=self.data_management_service.open_logs,
        )
        dialog.finished.connect(
            lambda _result, key=operation_key: self.error_dialogs.pop(key, None)
        )
        self.error_dialogs[operation_key] = dialog
        dialog.show()

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
        self.page_stack.setCurrentIndex(self.page_indexes[resolved_page_id])
        for page_id, button in self.navigation_buttons.items():
            button.setChecked(page_id is resolved_page_id)

    @property
    def current_page_id(self) -> PageId:
        current_index = self.page_stack.currentIndex()
        return next(
            page_id for page_id, index in self.page_indexes.items() if index == current_index
        )
