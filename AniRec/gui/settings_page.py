"""Validated recommendation, profile, API, and appearance settings UI."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..errors import AniRecError, ConfigError, UserFacingError
from ..models import AppSettings, PipelineSettings, UserProfile
from ..services import (
    ApiConnectionService,
    AuthService,
    DataDeletionPlan,
    DataDeletionScope,
    DataManagementService,
    ProfileService,
    SettingsService,
    TokenStore,
)
from ..infrastructure.logging_config import close_all_anirec_loggers
from .recommendation_card import MEMORY_COVER_CACHE
from .workers import ApiConnectionWorker, TokenRefreshWorker, WorkerController


class SettingsPage(QWidget):
    open_setup_requested = Signal()
    settings_saved = Signal(object)
    profile_changed = Signal(object)
    show_hidden_changed = Signal(bool)
    local_data_reset = Signal()

    API_TEST_KEY = "settings-api-test:global"

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        settings_service: SettingsService | None = None,
        profile_service: ProfileService | None = None,
        token_store: TokenStore | None = None,
        auth_service: AuthService | None = None,
        api_connection: ApiConnectionService | None = None,
        worker_controller: WorkerController | None = None,
        confirm_profile_delete: Callable[[UserProfile, Path], bool] | None = None,
        data_management: DataManagementService | None = None,
        confirm_data_delete: Callable[[DataDeletionPlan], bool] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page-settings")
        self.setAccessibleName("Settings page")
        self.settings_service = settings_service or SettingsService()
        self.profile_service = profile_service
        self.token_store = token_store or TokenStore()
        self.auth_service = auth_service
        self.api_connection = api_connection or ApiConnectionService()
        self.worker_controller = worker_controller or WorkerController(self)
        self.confirm_profile_delete = confirm_profile_delete or self._confirm_profile_delete
        self.data_management = data_management or DataManagementService()
        self.confirm_data_delete = confirm_data_delete or self._confirm_data_delete
        self.active_profile: UserProfile | None = None
        self._saved_secret: str | None = None
        self._refresh_key: str | None = None
        self._build_ui()
        self.worker_controller.result_ready.connect(self._on_worker_result)
        self.worker_controller.error_occurred.connect(self._on_worker_error)
        self.worker_controller.finished.connect(self._on_worker_finished)
        self.reload()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)
        title = QLabel("Settings")
        title.setObjectName("pageTitle")
        description = QLabel(
            "Manage recommendation behavior, local profiles, MyAnimeList API access, and appearance."
        )
        description.setObjectName("pageDescription")
        description.setWordWrap(True)
        self.status_label = QLabel()
        self.status_label.setObjectName("settingsStatus")
        self.status_label.setWordWrap(True)
        self.status_label.setVisible(False)
        root.addWidget(title)
        root.addWidget(description)
        root.addWidget(self.status_label)

        scroll = QScrollArea()
        scroll.setObjectName("settingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("settingsContent")
        content.setMaximumWidth(1180)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 8, 8, 8)
        layout.setSpacing(18)
        cards = QGridLayout()
        cards.setSpacing(16)
        cards.addWidget(self._build_recommendation_group(), 0, 0)
        cards.addWidget(self._build_appearance_group(), 0, 1)
        cards.addWidget(self._build_profile_group(), 1, 0)
        cards.addWidget(self._build_api_group(), 1, 1)
        cards.addWidget(self._build_data_group(), 2, 0, 1, 2)
        cards.setColumnStretch(0, 1)
        cards.setColumnStretch(1, 1)
        layout.addLayout(cards)

        action_row = QHBoxLayout()
        self.reload_button = QPushButton("Reload")
        self.save_button = QPushButton("Save settings")
        self.open_setup_button = QPushButton("Open Setup Wizard")
        self.save_button.setProperty("buttonRole", "primary")
        self.open_setup_button.setProperty("buttonRole", "secondary")
        self.reload_button.clicked.connect(self.reload)
        self.save_button.clicked.connect(self.save)
        self.open_setup_button.clicked.connect(self.open_setup_requested.emit)
        action_row.addWidget(self.reload_button)
        action_row.addStretch()
        action_row.addWidget(self.open_setup_button)
        action_row.addWidget(self.save_button)
        layout.addLayout(action_row)
        layout.addStretch()
        scroll.setWidget(content)
        scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        root.addWidget(scroll, 1)

    def _build_recommendation_group(self) -> QGroupBox:
        group = QGroupBox("Recommendation")
        group.setProperty("settingsCard", True)
        form = QFormLayout(group)
        self.top_limit_input = self._spinbox(1, 100_000)
        self.recommendation_count_input = self._spinbox(1, 1_000)
        self.candidate_pool_input = self._spinbox(1, 100_000)
        self.randomness_input = self._spinbox(1, 10)
        self.minimum_score_input = QDoubleSpinBox()
        self.minimum_score_input.setRange(0.0, 10.0)
        self.minimum_score_input.setDecimals(1)
        self.minimum_score_input.setSingleStep(0.5)
        self.minimum_score_input.setSpecialValueText("Any")
        self.seed_input = QSpinBox()
        self.seed_input.setRange(-1, 2_147_483_647)
        self.seed_input.setSpecialValueText("Random")
        self.default_sort_input = QComboBox()
        self.default_sort_input.addItem("Personal match", "personal-match")
        self.default_sort_input.addItem("MAL score", "mal-score")
        self.default_sort_input.addItem("Airing year", "year")
        self.default_sort_input.addItem("Alphabetical", "alphabetical")
        self.include_hidden_input = QCheckBox("Include hidden recommendations")
        self.include_nsfw_input = QCheckBox("Include NSFW anime")
        form.addRow("Popular anime pool", self.top_limit_input)
        form.addRow("Recommendation count", self.recommendation_count_input)
        form.addRow("Evaluated candidate count", self.candidate_pool_input)
        form.addRow("Randomness (1–10)", self.randomness_input)
        form.addRow("Minimum MAL score", self.minimum_score_input)
        form.addRow("Deterministic seed", self.seed_input)
        form.addRow("Default sort", self.default_sort_input)
        form.addRow("Hidden items", self.include_hidden_input)
        form.addRow("MAL content", self.include_nsfw_input)
        return group

    def _build_profile_group(self) -> QGroupBox:
        group = QGroupBox("Profiles")
        group.setProperty("settingsCard", True)
        layout = QVBoxLayout(group)
        self.profile_combo = QComboBox()
        self.profile_combo.setObjectName("settingsActiveProfile")
        buttons = QHBoxLayout()
        self.switch_profile_button = QPushButton("Switch")
        self.add_profile_button = QPushButton("Add profile")
        self.open_profile_folder_button = QPushButton("Open folder")
        self.delete_profile_button = QPushButton("Delete local profile")
        self.switch_profile_button.clicked.connect(self.switch_profile)
        self.add_profile_button.clicked.connect(self.open_setup_requested.emit)
        self.open_profile_folder_button.clicked.connect(self.open_profile_folder)
        self.delete_profile_button.clicked.connect(self.delete_profile)
        for button in (
            self.switch_profile_button,
            self.add_profile_button,
            self.open_profile_folder_button,
            self.delete_profile_button,
        ):
            buttons.addWidget(button)
        layout.addWidget(self.profile_combo)
        layout.addLayout(buttons)
        return group

    def _build_api_group(self) -> QGroupBox:
        group = QGroupBox("MyAnimeList Public API")
        group.setProperty("settingsCard", True)
        layout = QVBoxLayout(group)
        form = QFormLayout()
        self.client_id_input = QLineEdit()
        self.client_id_input.setObjectName("settingsClientId")
        self.client_secret_input = QLineEdit()
        self.client_secret_input.setObjectName("settingsClientSecret")
        self.client_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.redirect_uri_input = QLineEdit()
        self.redirect_uri_input.setObjectName("settingsRedirectUri")
        form.addRow("Client ID", self.client_id_input)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        self.test_api_button = QPushButton("Test connection")
        self.refresh_token_button = QPushButton("Refresh token")
        self.disconnect_button = QPushButton("Remove local connection")
        self.test_api_button.clicked.connect(self.test_api_connection)
        self.refresh_token_button.clicked.connect(self.refresh_token)
        self.disconnect_button.clicked.connect(self.disconnect_token)
        buttons.addWidget(self.test_api_button)
        self.refresh_token_button.setVisible(False)
        self.disconnect_button.setVisible(False)
        layout.addLayout(buttons)
        self.api_status_label = QLabel("Not tested")
        self.api_status_label.setObjectName("settingsApiStatus")
        self.api_status_label.setWordWrap(True)
        layout.addWidget(self.api_status_label)
        return group

    def _build_appearance_group(self) -> QGroupBox:
        group = QGroupBox("Appearance")
        group.setProperty("settingsCard", True)
        form = QFormLayout(group)
        self.theme_input = QComboBox()
        self.theme_input.addItem("System", "system")
        self.theme_input.addItem("Dark", "dark")
        self.theme_input.addItem("Light", "light")
        self.font_scale_input = QDoubleSpinBox()
        self.font_scale_input.setRange(0.80, 1.40)
        self.font_scale_input.setDecimals(2)
        self.font_scale_input.setSingleStep(0.05)
        self.font_scale_input.setSuffix("×")
        self.show_covers_input = QCheckBox("Show anime covers")
        form.addRow("Theme", self.theme_input)
        form.addRow("Font scale", self.font_scale_input)
        form.addRow("Recommendation artwork", self.show_covers_input)
        return group

    def _build_data_group(self) -> QGroupBox:
        group = QGroupBox("Local data")
        group.setProperty("settingsCard", True)
        layout = QVBoxLayout(group)
        buttons = QHBoxLayout()
        self.clear_cache_button = QPushButton("Clear cache")
        self.clear_covers_button = QPushButton("Clear downloaded covers")
        self.open_logs_button = QPushButton("Open log folder")
        self.delete_all_data_button = QPushButton("Delete all local data")
        self.delete_all_data_button.setProperty("buttonRole", "danger")
        self.clear_cache_button.clicked.connect(
            lambda: self.delete_data_scope(DataDeletionScope.CACHE)
        )
        self.clear_covers_button.clicked.connect(
            lambda: self.delete_data_scope(DataDeletionScope.COVERS)
        )
        self.open_logs_button.clicked.connect(self.open_logs)
        self.delete_all_data_button.clicked.connect(
            lambda: self.delete_data_scope(DataDeletionScope.ALL_LOCAL_DATA)
        )
        for button in (
            self.clear_cache_button,
            self.clear_covers_button,
            self.open_logs_button,
            self.delete_all_data_button,
        ):
            buttons.addWidget(button)
        scope = QLabel(
            "Destructive actions show their exact target and scope before changing local files."
        )
        scope.setObjectName("settingsDataScopeHint")
        scope.setWordWrap(True)
        layout.addWidget(scope)
        layout.addLayout(buttons)
        return group

    @staticmethod
    def _spinbox(minimum: int, maximum: int) -> QSpinBox:
        widget = QSpinBox()
        widget.setRange(minimum, maximum)
        return widget

    def set_context(self, active_profile: UserProfile | None) -> None:
        self.active_profile = active_profile
        self.refresh_profiles()
        self._sync_profile_buttons()

    def reload(self) -> None:
        settings = self.settings_service.load()
        self._saved_secret = settings.client_secret
        pipeline = settings.pipeline
        self.top_limit_input.setValue(pipeline.top_anime_limit)
        self.recommendation_count_input.setValue(pipeline.recommendation_count)
        self.candidate_pool_input.setValue(pipeline.candidate_pool_size)
        self.randomness_input.setValue(pipeline.randomness_factor)
        self.minimum_score_input.setValue(pipeline.minimum_mean_score or 0.0)
        self.seed_input.setValue(pipeline.seed if pipeline.seed is not None else -1)
        self.default_sort_input.setCurrentIndex(
            max(0, self.default_sort_input.findData(settings.default_recommendation_sort))
        )
        self.include_hidden_input.setChecked(settings.include_hidden_recommendations)
        self.include_nsfw_input.setChecked(pipeline.include_nsfw)
        self.client_id_input.setText(settings.client_id or "")
        self.client_secret_input.clear()
        self.client_secret_input.setPlaceholderText(
            "Saved securely — leave blank to keep" if self._saved_secret else ""
        )
        self.redirect_uri_input.setText(settings.redirect_uri)
        self.theme_input.setCurrentIndex(max(0, self.theme_input.findData(settings.theme)))
        self.font_scale_input.setValue(settings.font_scale)
        self.show_covers_input.setChecked(settings.show_covers)
        self.refresh_profiles()
        if self.settings_service.last_error is not None:
            self._set_status("Stored settings were invalid; safe defaults are shown.", error=True)
        else:
            self._set_status("", error=False)

    def settings_value(self) -> AppSettings:
        minimum_score = self.minimum_score_input.value()
        seed = self.seed_input.value()
        pipeline = PipelineSettings(
            top_anime_limit=self.top_limit_input.value(),
            recommendation_count=self.recommendation_count_input.value(),
            candidate_pool_size=self.candidate_pool_input.value(),
            randomness_factor=self.randomness_input.value(),
            minimum_mean_score=minimum_score if minimum_score > 0 else None,
            seed=seed if seed >= 0 else None,
            include_nsfw=self.include_nsfw_input.isChecked(),
        )
        secret = self.client_secret_input.text().strip() or self._saved_secret
        return AppSettings(
            client_id=self.client_id_input.text(),
            client_secret=secret,
            redirect_uri=self.redirect_uri_input.text(),
            active_profile_id=self.active_profile.profile_id if self.active_profile else None,
            pipeline=pipeline,
            default_recommendation_sort=self.default_sort_input.currentData(),
            include_hidden_recommendations=self.include_hidden_input.isChecked(),
            theme=self.theme_input.currentData(),
            font_scale=self.font_scale_input.value(),
            show_covers=self.show_covers_input.isChecked(),
        )

    def save(self) -> bool:
        try:
            settings = self.settings_value()
            self.settings_service.save(settings)
        except (AniRecError, TypeError, ValueError) as error:
            message = (
                str(error)
                if isinstance(error, ConfigError)
                else error.to_user_error().solution
                if isinstance(error, AniRecError)
                else str(error)
            )
            self._set_status(f"Settings were not saved. {message}", error=True)
            return False
        self._saved_secret = settings.client_secret
        self.client_secret_input.clear()
        self.client_secret_input.setPlaceholderText(
            "Saved securely — leave blank to keep" if self._saved_secret else ""
        )
        self._set_status("Settings saved and applied.", error=False)
        self.settings_saved.emit(settings)
        self.show_hidden_changed.emit(settings.include_hidden_recommendations)
        return True

    def refresh_profiles(self) -> None:
        profiles = self.profile_service.list_profiles() if self.profile_service else ()
        current_id = self.active_profile.profile_id if self.active_profile else None
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for profile in profiles:
            self.profile_combo.addItem(profile.username, profile.profile_id)
        index = self.profile_combo.findData(current_id)
        self.profile_combo.setCurrentIndex(index if index >= 0 else 0)
        self.profile_combo.blockSignals(False)
        self._sync_profile_buttons()

    def switch_profile(self) -> bool:
        if self.profile_service is None:
            return False
        profile_id = self.profile_combo.currentData()
        if not profile_id:
            return False
        try:
            profile = self.profile_service.set_active(profile_id)
        except AniRecError as error:
            self._set_status(error.to_user_error().solution, error=True)
            return False
        self.active_profile = profile
        self._sync_profile_buttons()
        self.profile_changed.emit(profile)
        self._set_status(f"Active profile changed to {profile.username}.", error=False)
        return True

    def open_profile_folder(self) -> bool:
        if self.profile_service is None or self.active_profile is None:
            return False
        try:
            self.profile_service.open_directory(self.active_profile.profile_id)
        except AniRecError as error:
            self._set_status(error.to_user_error().solution, error=True)
            return False
        return True

    def delete_profile(self) -> bool:
        if self.profile_service is None or self.active_profile is None:
            return False
        profile = self.active_profile
        try:
            target = self.profile_service.deletion_target(profile.profile_id)
            if not self.confirm_profile_delete(profile, target):
                return False
            if not self.worker_controller.shutdown():
                self._set_status(
                    "Local profile data was not deleted because a background operation is still running.",
                    error=True,
                )
                return False
            self.profile_service.delete_profile(profile.profile_id, confirmed_target=target)
        except AniRecError as error:
            self._set_status(error.to_user_error().solution, error=True)
            return False
        self.active_profile = self.profile_service.active_profile()
        self.refresh_profiles()
        self.profile_changed.emit(self.active_profile)
        self._set_status(f"Deleted local data for {profile.username}.", error=False)
        return True

    def open_logs(self) -> bool:
        try:
            target = self.data_management.open_logs()
        except AniRecError as error:
            self._set_status(error.to_user_error().solution, error=True)
            return False
        self._set_status(f"Opened log folder: {target}", error=False)
        return True

    def delete_data_scope(self, scope: DataDeletionScope | str) -> bool:
        plan = self.data_management.plan(scope)
        if not self.confirm_data_delete(plan):
            return False
        if not self.worker_controller.shutdown():
            self._set_status(
                "Local data was not changed because a background operation is still running.",
                error=True,
            )
            return False
        if plan.scope is DataDeletionScope.ALL_LOCAL_DATA:
            close_all_anirec_loggers()
        try:
            receipt = self.data_management.delete(
                plan.scope, confirmed_target=plan.target
            )
        except (AniRecError, OSError) as error:
            message = (
                error.to_user_error().solution
                if isinstance(error, AniRecError)
                else "Check folder permissions and try again."
            )
            self._set_status(f"Local data was not changed. {message}", error=True)
            return False
        if plan.scope in {DataDeletionScope.COVERS, DataDeletionScope.ALL_LOCAL_DATA}:
            MEMORY_COVER_CACHE.clear()
        if plan.scope is DataDeletionScope.ALL_LOCAL_DATA:
            self.active_profile = None
            self._saved_secret = None
            self.reload()
            self.set_context(None)
            self.profile_changed.emit(None)
            self.local_data_reset.emit()
        self._set_status(
            f"{plan.title.rstrip('?')} completed ({receipt.removed_entries} entries removed).",
            error=False,
        )
        return True

    def test_api_connection(self) -> bool:
        try:
            settings = self.settings_value()
            self.settings_service.validate(settings)
        except (AniRecError, TypeError, ValueError) as error:
            self.api_status_label.setText(f"Invalid settings: {error}")
            return False
        if self.worker_controller.is_running(self.API_TEST_KEY):
            return False
        self.api_status_label.setText("Testing connection…")
        self.test_api_button.setEnabled(False)
        self.worker_controller.start(
            self.API_TEST_KEY, ApiConnectionWorker(self.api_connection, settings)
        )
        return True

    def refresh_token(self) -> bool:
        if self.active_profile is None or self.auth_service is None:
            self.api_status_label.setText("Select a connected profile first.")
            return False
        try:
            settings = self.settings_value()
            self.settings_service.validate(settings)
        except (AniRecError, TypeError, ValueError) as error:
            self.api_status_label.setText(f"Invalid settings: {error}")
            return False
        self._refresh_key = f"settings-token-refresh:{self.active_profile.profile_id}"
        if self.worker_controller.is_running(self._refresh_key):
            return False
        self.api_status_label.setText("Refreshing token…")
        self.refresh_token_button.setEnabled(False)
        self.worker_controller.start(
            self._refresh_key,
            TokenRefreshWorker(
                self.auth_service, self.active_profile.profile_id, settings
            ),
        )
        return True

    def disconnect_token(self) -> bool:
        if self.active_profile is None:
            return False
        self.token_store.delete(self.active_profile.profile_id)
        self.api_status_label.setText("The local MyAnimeList connection was removed.")
        return True

    def set_show_hidden(self, show_hidden: bool, *, enabled: bool) -> None:
        self.include_hidden_input.blockSignals(True)
        self.include_hidden_input.setChecked(show_hidden)
        self.include_hidden_input.setEnabled(enabled)
        self.include_hidden_input.blockSignals(False)

    def _sync_profile_buttons(self) -> None:
        has_profile = self.active_profile is not None
        has_choices = self.profile_combo.count() > 0
        self.switch_profile_button.setEnabled(has_choices)
        self.open_profile_folder_button.setEnabled(has_profile)
        self.delete_profile_button.setEnabled(has_profile)
        self.refresh_token_button.setEnabled(has_profile and self.auth_service is not None)
        self.disconnect_button.setEnabled(has_profile)

    def _on_worker_result(self, operation_key: str, _result: object) -> None:
        if operation_key == self.API_TEST_KEY:
            self.api_status_label.setText("Client ID connection succeeded.")
        elif operation_key == self._refresh_key:
            self.api_status_label.setText("OAuth token is valid and refreshed if required.")

    def _on_worker_error(self, operation_key: str, error: object) -> None:
        if operation_key not in {self.API_TEST_KEY, self._refresh_key}:
            return
        self.api_status_label.setText(
            f"{error.title}. {error.solution}"
            if isinstance(error, UserFacingError)
            else "The connection operation failed."
        )

    def _on_worker_finished(self, operation_key: str) -> None:
        if operation_key == self.API_TEST_KEY:
            self.test_api_button.setEnabled(True)
        elif operation_key == self._refresh_key:
            self.refresh_token_button.setEnabled(self.active_profile is not None)

    def _set_status(self, text: str, *, error: bool) -> None:
        self.status_label.setText(text)
        self.status_label.setProperty("error", error)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.status_label.setVisible(bool(text))

    def _confirm_profile_delete(self, profile: UserProfile, target: Path) -> bool:
        result = QMessageBox.warning(
            self,
            "Delete local profile data?",
            f"This deletes AniRec's local data for {profile.username}:\n{target}\n\n"
            "It does not change the MyAnimeList account.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return result == QMessageBox.StandardButton.Yes

    def _confirm_data_delete(self, plan: DataDeletionPlan) -> bool:
        result = QMessageBox.warning(
            self,
            plan.title,
            f"{plan.description}\n\nExact target:\n{plan.target}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return result == QMessageBox.StandardButton.Yes
