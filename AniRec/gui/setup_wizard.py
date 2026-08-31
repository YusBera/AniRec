"""Multi-step, restartable AniRec onboarding window."""

from __future__ import annotations

import time
from enum import IntEnum

from ..application.pipeline import FULL_PIPELINE_STEP_IDS, PipelineOrchestrator
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..errors import AniRecError, AuthError, ProfileError, UserFacingError
from ..models import (
    AppSettings,
    PipelineProgress,
    PipelineResult,
    PipelineSettings,
    TokenRecord,
    UserProfile,
)
from ..services import (
    ApiConnectionService,
    AuthService,
    OnboardingService,
    ResultService,
    SettingsService,
)
from .external_links import MAL_API_CONFIG_URL, open_external_url
from .instrument_widgets import Scanlines
from .texts import OAUTH_STATUS_TEXT, PROGRESS_STEP_TEXT, UI_TEXT, WIZARD_TEXT
from .workers import (
    OAuthWorker,
    OperationAlreadyRunningError,
    OperationKind,
    PublicProfileSetupResult,
    PublicProfileSetupWorker,
    RecommendationWorker,
    WorkerController,
    operation_key,
)


ONBOARDING_TOKEN_PROFILE_ID = "onboarding"

# How long closing the wizard waits for background work to unwind before
# closing anyway. Kept short: this blocks the GUI thread.
CLOSE_GRACE_SECONDS = 1.5

WIZARD_DEFAULT_SIZE = QSize(760, 520)
WIZARD_MINIMUM_SIZE = QSize(560, 360)
WIZARD_SCREEN_FRACTION = 0.75


class WizardStep(IntEnum):
    WELCOME = 0
    CONNECTION = 1
    API = 1
    PROFILE = 1
    OAUTH = 2
    ANALYSIS = 3


STEP_LABELS = {
    WizardStep.WELCOME: WIZARD_TEXT.welcome,
    WizardStep.CONNECTION: WIZARD_TEXT.connection,
    WizardStep.OAUTH: WIZARD_TEXT.oauth,
    WizardStep.ANALYSIS: WIZARD_TEXT.analysis,
}


def _hint_label(text: str) -> QLabel:
    """A quiet explanatory line sitting under a form field."""
    label = QLabel(text)
    label.setObjectName("wizardFieldHint")
    label.setWordWrap(True)
    return label


class WizardPage(QWidget):
    completion_changed = Signal(bool)

    def __init__(self, step: WizardStep, *, complete: bool = False) -> None:
        super().__init__()
        self.step = step
        self._complete = complete
        self.setObjectName(f"wizardPage-{step.name.casefold()}")
        self.content_layout = QVBoxLayout(self)
        self.title_label = QLabel(STEP_LABELS[step])
        self.title_label.setObjectName("pageTitle")
        self.hint_label = QLabel(WIZARD_TEXT.required_hint)
        self.hint_label.setObjectName("wizardRequiredHint")
        self.content_layout.addWidget(self.title_label)
        self.content_layout.addWidget(self.hint_label)
        self.content_layout.addStretch()

    @property
    def is_complete(self) -> bool:
        return self._complete

    def set_complete(self, complete: bool) -> None:
        complete = bool(complete)
        if self._complete != complete:
            self._complete = complete
            self.completion_changed.emit(complete)


class WelcomePage(WizardPage):
    demo_requested = Signal()

    def __init__(self) -> None:
        super().__init__(WizardStep.WELCOME, complete=True)
        self.hint_label.setText(WIZARD_TEXT.welcome_body)
        self.hint_label.setWordWrap(True)

        # A way in that costs nothing. Registering an API application before
        # seeing anything at all is a hard wall for someone still deciding
        # whether AniRec is worth their time.
        self.connect_hint = QLabel(WIZARD_TEXT.welcome_connect_hint)
        self.connect_hint.setObjectName("wizardFieldHint")
        self.connect_hint.setWordWrap(True)
        self.demo_button = QPushButton(WIZARD_TEXT.welcome_demo)
        self.demo_button.setObjectName("wizardDemoButton")
        # CHANGE [ACTIVATION]: this was a secondary button sitting underneath
        # the pitch for registering an API application. The cheapest path
        # through the product was styled like the way out of it, while the
        # footer's Next marched people at a Client ID field before they had
        # seen a single recommendation. The free path leads now.
        self.demo_button.setProperty("buttonRole", "primary")
        # CHANGE [ROW]: no height here. This asked for 40 and measured 36,
        # because the stylesheet's min-height wins - so the line claimed a
        # size the button never had, and 36 is the app's standard anyway.
        self.demo_button.setAccessibleName(WIZARD_TEXT.welcome_demo_accessible)
        self.demo_hint = QLabel(WIZARD_TEXT.welcome_demo_hint)
        self.demo_hint.setObjectName("wizardFieldHint")
        self.demo_hint.setWordWrap(True)
        self.demo_button.clicked.connect(self.demo_requested.emit)

        self.content_layout.insertWidget(2, self.demo_button)
        self.content_layout.insertWidget(3, self.demo_hint)
        self.content_layout.insertWidget(4, self.connect_hint)



def _configure_wizard_form(form: QFormLayout) -> None:
    """Give the wizard's forms the key column Settings already uses.

    The wizard was a stock Qt form on a dark background: labels left-aligned
    at Qt's default, sitting beside inputs that grew or did not depending on
    what was in them, on the first screen a new user sees. Settings had all of
    this settled; this is the same treatment, so the two surfaces read as the
    same machine.
    """
    form.setLabelAlignment(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
    )
    form.setFormAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
    form.setHorizontalSpacing(18)
    form.setVerticalSpacing(8)


def _name_field_keys(form: QFormLayout) -> None:
    """Tag the labels QFormLayout creates so they can be styled as keys.

    ``addRow("Client ID", widget)`` builds its own QLabel, which has no object
    name and therefore falls through to the reading face. Naming them after
    the fact is what lets the stylesheet treat them as panel keys rather than
    as prose.
    """
    for row in range(form.rowCount()):
        item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
        widget = item.widget() if item is not None else None
        if widget is not None and not widget.objectName() and widget.text().strip():
            widget.setObjectName("wizardFieldKey")

class ApiSettingsPage(WizardPage):
    test_requested = Signal(object, str)

    def __init__(self, initial_settings: AppSettings) -> None:
        super().__init__(WizardStep.API)
        self.initial_settings = initial_settings
        self._saved_secret = initial_settings.client_secret

        form = QFormLayout()
        _configure_wizard_form(form)
        self.client_id_input = QLineEdit(initial_settings.client_id or "")
        self.client_id_input.setObjectName("apiClientIdInput")
        self.profile_reference_input = QLineEdit()
        self.profile_reference_input.setObjectName("malProfileReferenceInput")
        self.profile_reference_input.setPlaceholderText(
            "https://myanimelist.net/profile/YourUsername"
        )
        self.client_secret_input = QLineEdit()
        self.client_secret_input.setObjectName("apiClientSecretInput")
        self.client_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        if self._saved_secret:
            self.client_secret_input.setPlaceholderText(WIZARD_TEXT.saved_secret)
        self.redirect_uri_input = QLineEdit(initial_settings.redirect_uri)
        self.redirect_uri_input.setObjectName("apiRedirectUriInput")
        self.redirect_uri_input.setReadOnly(True)

        self.intro_label = QLabel(WIZARD_TEXT.api_intro)
        self.intro_label.setObjectName("wizardIntro")
        self.intro_label.setWordWrap(True)
        self.steps_label = QLabel(WIZARD_TEXT.api_steps)
        self.steps_label.setObjectName("wizardSteps")
        self.steps_label.setWordWrap(True)
        self.api_link = QLabel(
            f'<a href="{MAL_API_CONFIG_URL}">{WIZARD_TEXT.api_link_label}</a>'
        )
        self.api_link.setObjectName("wizardApiLink")
        self.api_link.setOpenExternalLinks(False)
        self.api_link.setTextInteractionFlags(
            Qt.TextInteractionFlag.LinksAccessibleByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByKeyboard
        )
        self.api_link.linkActivated.connect(open_external_url)

        redirect_row = QHBoxLayout()
        redirect_row.setContentsMargins(0, 0, 0, 0)
        redirect_row.addWidget(self.redirect_uri_input)
        self.copy_redirect_button = QPushButton(WIZARD_TEXT.copy_redirect_uri)
        self.copy_redirect_button.setObjectName("apiCopyRedirectButton")
        self.copy_redirect_button.clicked.connect(self._copy_redirect_uri)
        redirect_row.addWidget(self.copy_redirect_button)
        redirect_container = QWidget()
        redirect_container.setLayout(redirect_row)

        form.addRow(WIZARD_TEXT.redirect_uri, redirect_container)
        form.addRow("", _hint_label(WIZARD_TEXT.redirect_uri_hint))
        form.addRow(WIZARD_TEXT.client_id, self.client_id_input)
        form.addRow("", _hint_label(WIZARD_TEXT.client_id_hint))
        form.addRow(WIZARD_TEXT.client_secret, self.client_secret_input)
        form.addRow("", _hint_label(WIZARD_TEXT.client_secret_hint))
        form.addRow(WIZARD_TEXT.profile_reference, self.profile_reference_input)
        self.content_layout.insertWidget(1, self.intro_label)
        self.content_layout.insertWidget(2, self.api_link)
        self.content_layout.insertWidget(3, self.steps_label)
        _name_field_keys(form)
        self.content_layout.insertLayout(4, form)

        self.test_button = QPushButton(WIZARD_TEXT.test_connection)
        self.test_button.setObjectName("apiTestConnectionButton")
        self.status_label = QLabel(WIZARD_TEXT.api_validation_hint)
        self.status_label.setObjectName("apiTestStatus")
        self.status_label.setWordWrap(True)
        self.content_layout.insertWidget(5, self.test_button)
        self.content_layout.insertWidget(6, self.status_label)

        for field in (
            self.client_id_input,
            self.client_secret_input,
            self.profile_reference_input,
        ):
            field.textChanged.connect(self._fields_changed)
        self.test_button.clicked.connect(self._request_test)
        self._fields_changed()

    def _copy_redirect_uri(self) -> None:
        application = QApplication.instance()
        if application is None:
            return
        application.clipboard().setText(self.redirect_uri_input.text())
        self.copy_redirect_button.setText(WIZARD_TEXT.copied_redirect_uri)

    def settings_value(self) -> AppSettings:
        entered_secret = self.client_secret_input.text()
        return AppSettings(
            client_id=self.client_id_input.text(),
            client_secret=entered_secret or self._saved_secret,
            redirect_uri=self.redirect_uri_input.text(),
            active_profile_id=self.initial_settings.active_profile_id,
            debug_logging=self.initial_settings.debug_logging,
            pipeline=self.initial_settings.pipeline,
            default_recommendation_sort=self.initial_settings.default_recommendation_sort,
            include_hidden_recommendations=self.initial_settings.include_hidden_recommendations,
            theme=self.initial_settings.theme,
            font_scale=self.initial_settings.font_scale,
            show_covers=self.initial_settings.show_covers,
        )

    def show_success(self, settings: AppSettings, profile: UserProfile) -> None:
        self.initial_settings = settings
        self._saved_secret = settings.client_secret
        self.client_secret_input.clear()
        if self._saved_secret:
            self.client_secret_input.setPlaceholderText(WIZARD_TEXT.saved_secret)
        self.status_label.setText(
            f"{WIZARD_TEXT.connection_success} Profile: {profile.username}"
        )
        self.set_complete(True)

    def show_failure(self, error: UserFacingError) -> None:
        self.status_label.setText(f"{error.title}. {error.solution}")
        self.set_complete(False)

    def finish_test(self) -> None:
        self._set_test_enabled_from_validation()

    def _request_test(self) -> None:
        try:
            settings = self.settings_value()
            SettingsService.validate(settings)
        except AniRecError as error:
            self.show_failure(error.to_user_error())
            return
        self.test_button.setEnabled(False)
        self.status_label.setText(WIZARD_TEXT.testing_connection)
        self.set_complete(False)
        self.test_requested.emit(settings, self.profile_reference_input.text().strip())

    def _fields_changed(self) -> None:
        self.set_complete(False)
        self.status_label.setText(WIZARD_TEXT.api_validation_hint)
        self._set_test_enabled_from_validation()

    def _set_test_enabled_from_validation(self) -> None:
        try:
            SettingsService.validate(self.settings_value())
        except AniRecError:
            self.test_button.setEnabled(False)
        else:
            self.test_button.setEnabled(bool(self.profile_reference_input.text().strip()))


class OAuthPage(WizardPage):
    connect_requested = Signal()
    cancel_requested = Signal()

    def __init__(self) -> None:
        super().__init__(WizardStep.OAUTH)
        self.status_label = QLabel(WIZARD_TEXT.oauth_ready)
        self.status_label.setObjectName("oauthStatusLabel")
        self.status_label.setWordWrap(True)
        self.connect_button = QPushButton(WIZARD_TEXT.connect_mal)
        self.connect_button.setObjectName("oauthConnectButton")
        self.cancel_connection_button = QPushButton(WIZARD_TEXT.cancel_connection)
        self.cancel_connection_button.setObjectName("oauthCancelButton")
        self.cancel_connection_button.setVisible(False)

        self.content_layout.insertWidget(1, self.status_label)
        self.content_layout.insertWidget(2, self.connect_button)
        self.content_layout.insertWidget(3, self.cancel_connection_button)
        self.connect_button.clicked.connect(self.connect_requested.emit)
        self.cancel_connection_button.clicked.connect(self.cancel_requested.emit)

    def begin_connection(self) -> None:
        self.set_complete(False)
        self.connect_button.setEnabled(False)
        self.cancel_connection_button.setVisible(True)
        self.cancel_connection_button.setEnabled(True)
        self.status_label.setText(WIZARD_TEXT.oauth_opening_browser)

    def show_status(self, status_id: str) -> None:
        if status_id in OAUTH_STATUS_TEXT:
            self.status_label.setText(OAUTH_STATUS_TEXT[status_id])

    def show_success(self) -> None:
        self.status_label.setText(WIZARD_TEXT.oauth_success)
        self.set_complete(True)

    def show_failure(self, error: UserFacingError, *, hint: str = "") -> None:
        message = f"{error.title}. {error.description} {error.solution}"
        if hint:
            message = f"{message} {hint}"
        self.status_label.setText(message)
        self.set_complete(False)

    def show_cancelled(self) -> None:
        self.status_label.setText(WIZARD_TEXT.oauth_cancelled)
        self.set_complete(False)

    def finish_connection(self) -> None:
        self.connect_button.setEnabled(True)
        self.cancel_connection_button.setVisible(False)


class AnalysisPage(WizardPage):
    start_requested = Signal(object)
    cancel_requested = Signal()

    def __init__(self) -> None:
        super().__init__(WizardStep.ANALYSIS)
        form = QFormLayout()
        _configure_wizard_form(form)
        self.top_limit_input = self._spinbox(1, 10_000, 500)
        self.recommendation_count_input = self._spinbox(1, 100, 10)
        self.candidate_pool_input = self._spinbox(1, 10_000, 150)
        self.randomness_input = self._spinbox(1, 10, 5)
        form.addRow(WIZARD_TEXT.top_anime_limit, self.top_limit_input)
        form.addRow(WIZARD_TEXT.recommendation_count, self.recommendation_count_input)
        form.addRow(WIZARD_TEXT.candidate_pool_size, self.candidate_pool_input)
        form.addRow(WIZARD_TEXT.randomness_factor, self.randomness_input)
        _name_field_keys(form)
        self.content_layout.insertLayout(1, form)

        self.status_label = QLabel(WIZARD_TEXT.analysis_ready)
        self.status_label.setObjectName("analysisStatusLabel")
        self.status_label.setWordWrap(True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("analysisProgressBar")
        self.progress_bar.setRange(0, len(FULL_PIPELINE_STEP_IDS))
        self.progress_bar.setValue(0)
        self.step_list = QListWidget()
        self.step_list.setObjectName("analysisStepList")
        self.step_list.addItems(
            [PROGRESS_STEP_TEXT[step_id] for step_id in FULL_PIPELINE_STEP_IDS]
        )
        self.step_list.setMaximumHeight(150)
        self.start_button = QPushButton(WIZARD_TEXT.start_analysis)
        self.start_button.setObjectName("analysisStartButton")
        self.cancel_analysis_button = QPushButton(WIZARD_TEXT.cancel_analysis)
        self.cancel_analysis_button.setObjectName("analysisCancelButton")
        self.cancel_analysis_button.setVisible(False)
        for index, widget in enumerate(
            (
                self.status_label,
                self.progress_bar,
                self.step_list,
                self.start_button,
                self.cancel_analysis_button,
            ),
            start=2,
        ):
            self.content_layout.insertWidget(index, widget)
        self.recommendation_count_input.valueChanged.connect(self._keep_pool_valid)
        self.start_button.clicked.connect(self._request_start)
        self.cancel_analysis_button.clicked.connect(self.cancel_requested.emit)

    @staticmethod
    def _spinbox(minimum: int, maximum: int, value: int) -> QSpinBox:
        field = QSpinBox()
        field.setRange(minimum, maximum)
        field.setValue(value)
        return field

    def settings_value(self) -> PipelineSettings:
        return PipelineSettings(
            top_anime_limit=self.top_limit_input.value(),
            recommendation_count=self.recommendation_count_input.value(),
            candidate_pool_size=self.candidate_pool_input.value(),
            randomness_factor=self.randomness_input.value(),
        )

    def begin_analysis(self) -> None:
        self.set_complete(False)
        self.status_label.setText(WIZARD_TEXT.analysis_running)
        self.progress_bar.setRange(0, len(FULL_PIPELINE_STEP_IDS))
        self.progress_bar.setValue(0)
        self.step_list.setCurrentRow(-1)
        self.start_button.setEnabled(False)
        self.cancel_analysis_button.setVisible(True)
        self.cancel_analysis_button.setEnabled(True)
        self._set_fields_enabled(False)

    def apply_progress(self, progress: PipelineProgress) -> None:
        if progress.stage_id in FULL_PIPELINE_STEP_IDS:
            row = FULL_PIPELINE_STEP_IDS.index(progress.stage_id)
            self.step_list.setCurrentRow(row)
            self.status_label.setText(PROGRESS_STEP_TEXT[progress.stage_id])
        if progress.total > 0:
            self.progress_bar.setRange(0, progress.total)
            self.progress_bar.setValue(progress.current)
        else:
            self.progress_bar.setRange(0, 0)

    def show_success(self) -> None:
        self.status_label.setText(WIZARD_TEXT.analysis_success)
        self.progress_bar.setRange(0, len(FULL_PIPELINE_STEP_IDS))
        self.progress_bar.setValue(len(FULL_PIPELINE_STEP_IDS))
        self.step_list.setCurrentRow(len(FULL_PIPELINE_STEP_IDS) - 1)
        self.start_button.setText(WIZARD_TEXT.start_analysis)
        self.set_complete(True)

    def show_failure(self, error: UserFacingError) -> None:
        current = self.step_list.currentItem()
        step = current.text() if current is not None else "initial setup"
        self.status_label.setText(
            f"Failed during {step}. {error.title}. {error.solution}"
        )
        self.set_complete(False)
        self.start_button.setText(WIZARD_TEXT.analysis_retry)

    def show_cancelled(self) -> None:
        self.status_label.setText(WIZARD_TEXT.analysis_cancelled)
        self.set_complete(False)
        self.start_button.setText(WIZARD_TEXT.analysis_retry)

    def finish_analysis(self) -> None:
        self.start_button.setEnabled(True)
        self.cancel_analysis_button.setVisible(False)
        self._set_fields_enabled(True)

    def _request_start(self) -> None:
        self.begin_analysis()
        self.start_requested.emit(self.settings_value())

    def _keep_pool_valid(self, recommendation_count: int) -> None:
        self.candidate_pool_input.setMinimum(recommendation_count)
        if self.candidate_pool_input.value() < recommendation_count:
            self.candidate_pool_input.setValue(recommendation_count)

    def _set_fields_enabled(self, enabled: bool) -> None:
        for field in (
            self.top_limit_input,
            self.recommendation_count_input,
            self.candidate_pool_input,
            self.randomness_input,
        ):
            field.setEnabled(enabled)


class SetupWizard(QDialog):
    demo_requested = Signal()
    def __init__(
        self,
        onboarding: OnboardingService,
        parent: QWidget | None = None,
        *,
        api_connection: ApiConnectionService | None = None,
        auth_service: AuthService | None = None,
        pipeline_orchestrator: PipelineOrchestrator | None = None,
        result_service: ResultService | None = None,
        worker_controller: WorkerController | None = None,
        available_screen_size: QSize | None = None,
    ) -> None:
        super().__init__(parent)
        self.onboarding = onboarding
        self.api_connection = api_connection or ApiConnectionService()
        self.auth_service = auth_service or AuthService(token_store=onboarding.tokens)
        self.pipeline_orchestrator = pipeline_orchestrator
        self.result_service = result_service
        self.worker_controller = worker_controller or WorkerController(self)
        self.connection_operation_key = operation_key(OperationKind.API_TEST, "setup")
        self.api_operation_key = self.connection_operation_key
        self.oauth_operation_key = operation_key(OperationKind.OAUTH, "setup")
        self.analysis_operation_key: str | None = None
        self.setObjectName("setupWizard")
        # CHANGE [CRT]: the raster, so onboarding is the same machine as
        # the application behind it. A dialog is its own top-level window
        # and gets none of the shell's treatment unless it asks.
        self.setWindowTitle(WIZARD_TEXT.title)
        self.setModal(True)
        screen_size = available_screen_size
        if screen_size is None:
            screen_size = self.screen().availableGeometry().size()
        initial_size = self._initial_size_for_screen(screen_size)
        self.setMinimumSize(
            min(WIZARD_MINIMUM_SIZE.width(), initial_size.width()),
            min(WIZARD_MINIMUM_SIZE.height(), initial_size.height()),
        )
        self.resize(initial_size)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(16)

        self.step_indicator = QLabel()
        self.step_indicator.setObjectName("wizardStepIndicator")
        outer.addWidget(self.step_indicator)

        self.stack = QStackedWidget()
        self.pages: dict[WizardStep, WizardPage] = {}
        for step in WizardStep:
            if step is WizardStep.WELCOME:
                page = WelcomePage()
                page.demo_requested.connect(self.demo_requested.emit)
            elif step is WizardStep.CONNECTION:
                page = ApiSettingsPage(onboarding.settings.load())
                page.test_requested.connect(self._start_connection_setup)
            elif step is WizardStep.OAUTH:
                page = OAuthPage()
                page.connect_requested.connect(self._start_oauth)
                page.cancel_requested.connect(self._cancel_oauth)
            elif step is WizardStep.ANALYSIS:
                page = AnalysisPage()
                page.start_requested.connect(self._start_analysis)
                page.cancel_requested.connect(self._cancel_analysis)
            else:
                page = WizardPage(step)
            page.completion_changed.connect(self._update_navigation)
            self.pages[step] = page
            self.stack.addWidget(page)
        self.content_scroll = QScrollArea()
        self.content_scroll.setObjectName("setupWizardScroll")
        self.content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.content_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.content_scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.content_scroll.setWidget(self.stack)
        outer.addWidget(self.content_scroll, 1)

        buttons = QHBoxLayout()
        self.cancel_button = QPushButton(WIZARD_TEXT.cancel)
        self.back_button = QPushButton(WIZARD_TEXT.back)
        self.next_button = QPushButton(WIZARD_TEXT.next)
        self.finish_button = QPushButton(WIZARD_TEXT.finish)
        buttons.addWidget(self.cancel_button)
        buttons.addStretch()
        buttons.addWidget(self.back_button)
        buttons.addWidget(self.next_button)
        buttons.addWidget(self.finish_button)
        outer.addLayout(buttons)

        self.cancel_button.clicked.connect(self.reject)
        self.back_button.clicked.connect(self.go_back)
        self.next_button.clicked.connect(self.go_next)
        self.finish_button.clicked.connect(self.finish_setup)
        self.stack.currentChanged.connect(lambda _index: self._update_navigation())
        self.scanlines = Scanlines(self)
        self.scanlines.raise_()
        self.worker_controller.result_ready.connect(self._worker_result)
        self.worker_controller.error_occurred.connect(self._worker_error)
        self.worker_controller.progress_changed.connect(self._worker_progress)
        self.worker_controller.step_changed.connect(self._worker_step)
        self.worker_controller.cancelled.connect(self._worker_cancelled)
        self.worker_controller.finished.connect(self._worker_finished)
        self.go_to(WizardStep.WELCOME)

    @staticmethod
    def _initial_size_for_screen(available_size: QSize) -> QSize:
        """Keep the dialog within 75 percent of the usable logical screen."""
        screen_width = max(1, available_size.width())
        screen_height = max(1, available_size.height())
        return QSize(
            min(
                WIZARD_DEFAULT_SIZE.width(),
                max(1, int(screen_width * WIZARD_SCREEN_FRACTION)),
            ),
            min(
                WIZARD_DEFAULT_SIZE.height(),
                max(1, int(screen_height * WIZARD_SCREEN_FRACTION)),
            ),
        )

    @property
    def connection_page(self) -> ApiSettingsPage:
        return self.pages[WizardStep.CONNECTION]

    @property
    def api_page(self) -> ApiSettingsPage:
        return self.connection_page

    @property
    def analysis_page(self) -> AnalysisPage:
        return self.pages[WizardStep.ANALYSIS]

    @property
    def oauth_page(self) -> OAuthPage:
        return self.pages[WizardStep.OAUTH]

    @property
    def current_step(self) -> WizardStep:
        return WizardStep(self.stack.currentIndex())

    def go_to(self, step: WizardStep) -> None:
        target = WizardStep(step)
        if target > self.current_step + 1:
            return
        if target > self.current_step and not self.pages[self.current_step].is_complete:
            return
        self.stack.setCurrentIndex(int(target))
        self._update_navigation()

    def go_next(self) -> None:
        if not self.pages[self.current_step].is_complete:
            return
        if self.current_step < WizardStep.ANALYSIS:
            self.stack.setCurrentIndex(int(self.current_step + 1))

    def go_back(self) -> None:
        if self.current_step > WizardStep.WELCOME:
            self.stack.setCurrentIndex(int(self.current_step - 1))

    def set_step_complete(self, step: WizardStep, complete: bool = True) -> None:
        self.pages[WizardStep(step)].set_complete(complete)

    def finish_setup(self) -> None:
        if self.current_step is not WizardStep.ANALYSIS:
            return
        if not all(page.is_complete for page in self.pages.values()):
            return
        self.onboarding.mark_complete()
        self.accept()

    def reject(self) -> None:
        keys = tuple(
            key
            for key in (
                self.connection_operation_key,
                self.oauth_operation_key,
                self.analysis_operation_key,
            )
            if key
        )
        for key in keys:
            self.worker_controller.cancel(key)
        # Give workers a brief chance to unwind, but always close. Returning
        # early here used to leave the dialog and its title-bar close button
        # dead whenever a worker was wedged, with no way out for the user.
        deadline = time.monotonic() + CLOSE_GRACE_SECONDS
        for key in keys:
            remaining_ms = max(0, int((deadline - time.monotonic()) * 1000))
            self.worker_controller.wait(key, remaining_ms)
        super().reject()

    def _start_connection_setup(self, settings: AppSettings, profile_reference: str) -> None:
        if self.worker_controller.is_running(self.connection_operation_key):
            return
        self.worker_controller.start(
            self.connection_operation_key,
            PublicProfileSetupWorker(
                self.api_connection,
                self.onboarding.profiles,
                settings,
                profile_reference,
            ),
        )

    def _start_api_test_from_current(self) -> bool:
        if self.worker_controller.is_running(self.connection_operation_key):
            return False
        self.connection_page._request_test()
        return self.worker_controller.is_running(self.connection_operation_key)

    def _start_oauth(self) -> None:
        if self.worker_controller.is_running(self.oauth_operation_key):
            return
        profile = self.onboarding.profiles.active_profile()
        if profile is None:
            self.oauth_page.show_failure(
                ProfileError("A validated profile is required before OAuth.").to_user_error()
            )
            return
        self.oauth_page.begin_connection()
        try:
            self.worker_controller.start(
                self.oauth_operation_key,
                OAuthWorker(
                    self.auth_service,
                    profile.profile_id,
                    self.onboarding.settings.load(),
                ),
            )
        except OperationAlreadyRunningError:
            # A previous run is still finalising. Restore the page instead of
            # letting the exception escape the click handler and leave the
            # Connect button permanently disabled.
            self.oauth_page.finish_connection()
            self.oauth_page.show_status("oauth_opening_browser")

    def _cancel_oauth(self) -> None:
        self.worker_controller.cancel(self.oauth_operation_key)

    def _retry_analysis(self) -> bool:
        if self.analysis_operation_key and self.worker_controller.is_running(
            self.analysis_operation_key
        ):
            return False
        self.analysis_page._request_start()
        return bool(
            self.analysis_operation_key
            and self.worker_controller.is_running(self.analysis_operation_key)
        )

    def _start_analysis(self, pipeline_settings: PipelineSettings) -> None:
        profile = self.onboarding.profiles.active_profile()
        if profile is None or self.pipeline_orchestrator is None:
            error = ProfileError("An active profile and pipeline are required.")
            self.analysis_page.show_failure(error.to_user_error())
            self.analysis_page.finish_analysis()
            return
        self.analysis_operation_key = operation_key(
            OperationKind.RECOMMENDATION,
            profile.profile_id,
        )
        if self.worker_controller.is_running(self.analysis_operation_key):
            return
        current = self.onboarding.settings.load()
        updated = AppSettings(
            client_id=current.client_id,
            client_secret=current.client_secret,
            redirect_uri=current.redirect_uri,
            active_profile_id=profile.profile_id,
            debug_logging=current.debug_logging,
            pipeline=pipeline_settings,
            default_recommendation_sort=current.default_recommendation_sort,
            include_hidden_recommendations=current.include_hidden_recommendations,
            theme=current.theme,
            font_scale=current.font_scale,
            show_covers=current.show_covers,
        )
        try:
            self.onboarding.settings.save(updated)
        except AniRecError as error:
            self.analysis_page.show_failure(error.to_user_error())
            self.analysis_page.finish_analysis()
            return
        try:
            self.worker_controller.start(
                self.analysis_operation_key,
                RecommendationWorker(
                    self.pipeline_orchestrator,
                    profile.username,
                    pipeline_settings,
                ),
            )
        except OperationAlreadyRunningError:
            self.analysis_page.finish_analysis()

    def _cancel_analysis(self) -> None:
        if self.analysis_operation_key is not None:
            self.worker_controller.cancel(self.analysis_operation_key)

    def _worker_result(self, operation_key_value: str, result: object) -> None:
        if operation_key_value == self.connection_operation_key and isinstance(
            result, PublicProfileSetupResult
        ):
            try:
                self.onboarding.settings.save(result.settings)
                self.onboarding.profiles.set_active(result.profile.profile_id)
                self.onboarding.tokens.delete(ONBOARDING_TOKEN_PROFILE_ID)
            except AniRecError as error:
                self.connection_page.show_failure(error.to_user_error())
                return
            self.connection_page.show_success(result.settings, result.profile)
            self.go_next()
            return
        if operation_key_value == self.oauth_operation_key:
            self.oauth_page.show_success()
            self.go_next()
            return
        if (
            self.analysis_operation_key is not None
            and operation_key_value == self.analysis_operation_key
            and isinstance(result, PipelineResult)
        ):
            profile = self.onboarding.profiles.active_profile()
            if profile is None or self.result_service is None:
                error = ProfileError("The analysis result could not be assigned to a profile.")
                self.analysis_page.show_failure(error.to_user_error())
                return
            try:
                self.result_service.save_merged(profile.profile_id, result)
            except AniRecError as error:
                self.analysis_page.show_failure(error.to_user_error())
                return
            self.analysis_page.show_success()

    def _oauth_failure_hint(self) -> str:
        """Point at the most likely cause when the token exchange is refused."""
        try:
            settings = self.onboarding.settings.load()
        except Exception:  # noqa: BLE001 - a hint must never mask the real error
            return ""
        return "" if settings.client_secret else WIZARD_TEXT.oauth_missing_secret_hint

    def owns_operation(self, operation_key_value: str) -> bool:
        """Whether this wizard is responsible for reporting an operation's outcome.

        The wizard shares MainWindow's worker controller, so both react to the
        same signals. The wizard is application-modal, and a non-modal dialog
        raised beside it would be input-blocked and impossible to dismiss, so
        the wizard reports its own errors inline and MainWindow stands down.
        """
        return operation_key_value in {
            self.connection_operation_key,
            self.oauth_operation_key,
            self.analysis_operation_key,
        }

    def _worker_error(self, operation_key_value: str, error: object) -> None:
        if operation_key_value == self.connection_operation_key and isinstance(
            error, UserFacingError
        ):
            self.connection_page.show_failure(error)
        elif operation_key_value == self.oauth_operation_key and isinstance(
            error, UserFacingError
        ):
            self.oauth_page.show_failure(error, hint=self._oauth_failure_hint())
        elif operation_key_value == self.analysis_operation_key and isinstance(
            error, UserFacingError
        ):
            self.analysis_page.show_failure(error)

    def _worker_progress(self, operation_key_value: str, progress: object) -> None:
        if operation_key_value == self.analysis_operation_key and isinstance(
            progress, PipelineProgress
        ):
            self.analysis_page.apply_progress(progress)

    def _worker_step(self, operation_key_value: str, step_id: str, _message: str) -> None:
        if operation_key_value == self.oauth_operation_key:
            self.oauth_page.show_status(step_id)

    def _worker_cancelled(self, operation_key_value: str) -> None:
        if operation_key_value == self.oauth_operation_key:
            self.oauth_page.show_cancelled()
        elif operation_key_value == self.analysis_operation_key:
            self.analysis_page.show_cancelled()

    def _worker_finished(self, operation_key_value: str) -> None:
        if operation_key_value == self.connection_operation_key:
            self.connection_page.finish_test()
        elif operation_key_value == self.oauth_operation_key:
            self.oauth_page.finish_connection()
        elif operation_key_value == self.analysis_operation_key:
            self.analysis_page.finish_analysis()

    @staticmethod
    def _set_primary(button, primary: bool) -> None:
        """Give or take the accent, repolishing so the change is visible.

        Qt reads a dynamic property when it polishes a widget, so setting one
        afterwards changes nothing on screen until the style is re-evaluated.
        """
        if bool(button.property("buttonRole") == "primary") == primary:
            return
        button.setProperty("buttonRole", "primary" if primary else None)
        button.style().unpolish(button)
        button.style().polish(button)

    def _update_navigation(self) -> None:
        step = self.current_step
        self.step_indicator.setText(
            f"Step {int(step) + 1} of {len(WizardStep)} | {STEP_LABELS[step]}"
        )
        self.back_button.setEnabled(step > WizardStep.WELCOME)
        # CHANGE [HIERARCHY]: the forward action carries the accent from the
        # second step onward, and never on the first.
        #
        # The welcome page deliberately gives its accent to "Look around with
        # sample data" and leaves Next quiet, so nobody is marched at a Client
        # ID field before seeing the product. That inversion is right, but it
        # was left in place for the whole wizard: on Connection, OAuth and
        # Analysis nothing at all was accented, so three consecutive screens
        # had no ranked action. Once someone has chosen to connect, Next is
        # the thing the screen wants.
        self._set_primary(self.next_button, step > WizardStep.WELCOME)
        self.next_button.setVisible(step < WizardStep.ANALYSIS)
        self.next_button.setEnabled(
            step < WizardStep.ANALYSIS and self.pages[step].is_complete
        )
        self.finish_button.setVisible(step is WizardStep.ANALYSIS)
        ready_to_finish = step is WizardStep.ANALYSIS and all(
            page.is_complete for page in self.pages.values()
        )
        self.finish_button.setEnabled(ready_to_finish)
        # CHANGE [HIERARCHY]: the last step has two forward controls - Start
        # analysis on the page and Finish in the footer - and carried the
        # accent on neither, so the one screen with a job to do looked like it
        # was waiting for nothing in particular. Which of the two is primary
        # depends on whether the run has happened, so it moves: Start until
        # the pipeline has completed, Finish afterwards. Never both.
        analysis = self.pages[WizardStep.ANALYSIS]
        self._set_primary(self.finish_button, ready_to_finish)
        self._set_primary(
            analysis.start_button, step is WizardStep.ANALYSIS and not ready_to_finish
        )
