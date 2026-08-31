"""Settings surface.

Addresses: BUG2 (GUI Scale setting), FEAT1 (live colour preview with Cancel).

Configuration keys owned by this surface
----------------------------------------
``theme``            one of system, light, dark, oled, gradient. Default "system".
``gradient_start``   hex colour, the gradient's first stop. Default "#1B1A20".
``gradient_end``     hex colour, the gradient's second stop. Default "#2A1D1B".
``gui_scale``        float, one of 0.75, 1.0, 1.25, 1.5. Default 1.0. Multiplies
                     every hand-chosen dimension in the interface, so cards,
                     portraits, badges, spacing, buttons and text all resize
                     together. Stored in the same settings.json as everything
                     else and applied at startup.
``font_scale``       float 0.80 to 1.40. Default 1.0. Text only, independent of
                     gui_scale and multiplied with it.
``recommendation_view_mode``  one of cards, list, table. Default "cards".
Validated recommendation, profile, API, and appearance settings UI.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QTimer
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
from ..infrastructure.logging_config import close_all_anirec_loggers
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
from .gradient_picker import GradientPicker
from .design_tokens import SPACE
from .instrument_widgets import SteppedSlider
from .recommendation_card import MEMORY_COVER_CACHE
from .scaling import GUI_SCALE_CHOICES, clamp_gui_scale, set_gui_scale
from .texts import SETTINGS_TEXT


# Long enough to skip the intermediate frames of a drag, short enough that the
# preview still tracks the pointer.
PREVIEW_COALESCE_MS = 90
from .workers import ApiConnectionWorker, TokenRefreshWorker, WorkerController


class SettingsPage(QWidget):
    open_setup_requested = Signal()
    # CHANGE [BUG2]: announced so the shell can rebuild everything it sizes.
    gui_scale_changed = Signal(float)
    settings_saved = Signal(object)
    profile_changed = Signal(object)
    show_hidden_changed = Signal(bool)
    show_covers_changed = Signal(bool)
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
        advanced_page: QWidget | None = None,
        about_page: QWidget | None = None,
        theme_manager=None,
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
        self.advanced_page = advanced_page
        self.about_page = about_page
        self.theme_manager = theme_manager
        # CHANGE [FEAT1]: one pending preview at a time.
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._apply_preview_now)
        # CHANGE [BUG-PREVIEW]: true while controls are being populated.
        #
        # CHANGE [SAVE-MODEL]: and true through construction, not just through
        # reload. Building the Appearance panel fires currentIndexChanged on
        # every combo as its items are added, which now persists appearance -
        # so the theme combo firing while the GUI scale combo was still empty
        # wrote that combo's first entry, 0.75, over whatever scale the user
        # had. Constructing the page silently reset it. The first reload()
        # clears this in its finally block.
        self._loading = True
        self._saved_secret: str | None = None
        self._refresh_key: str | None = None
        self._build_ui()
        self.worker_controller.result_ready.connect(self._on_worker_result)
        self.worker_controller.error_occurred.connect(self._on_worker_error)
        self.worker_controller.finished.connect(self._on_worker_finished)
        self.reload()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        # CHANGE [PAGE]: the shared page inset and rhythm.
        root.setContentsMargins(
            SPACE["sm"], SPACE["sm"], SPACE["sm"], SPACE["sm"]
        )
        root.setSpacing(SPACE["md"])
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
        # CHANGE [VOID]: a grid stretches every cell to the tallest in its
        # row, so APPEARANCE beside the much taller RECOMMENDATION was drawn
        # as a panel two thirds full of nothing. Panels size to their contents
        # and sit at the top of their cell instead.
        top = Qt.AlignmentFlag.AlignTop
        cards.addWidget(self._build_recommendation_group(), 0, 0, top)
        cards.addWidget(self._build_appearance_group(), 0, 1, top)
        cards.addWidget(self._build_profile_group(), 1, 0, top)
        cards.addWidget(self._build_api_group(), 1, 1, top)
        cards.addWidget(self._build_data_group(), 2, 0, 1, 2)
        cards.setColumnStretch(0, 1)
        cards.setColumnStretch(1, 1)
        layout.addLayout(cards)

        layout.addWidget(self._build_developer_group())
        if self.about_page is not None:
            layout.addWidget(self.about_page)

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

    @staticmethod
    def _configure_form(form: QFormLayout) -> None:
        """Give every panel the same key column and field behaviour.

        The forms were left at Qt's defaults, so each panel's label column
        found its own width and its own alignment and the fields grew or did
        not depending on what happened to be in them. Right-aligning the keys
        against a consistent gutter is what turns three unrelated forms into
        one spec sheet.
        """
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.setHorizontalSpacing(SPACE["lg"])
        form.setVerticalSpacing(SPACE["sm"])

    def _build_developer_group(self) -> QGroupBox:
        """The individual pipeline steps, off by default.

        A first time user has no reason to run data steps by hand, and showing
        a seven node dependency chain as a flat list of buttons was the single
        most confusing thing in the old interface. The steps remain available
        for anyone who wants them.
        """
        group = QGroupBox(SETTINGS_TEXT.developer_tools)
        group.setProperty("settingsCard", True)
        layout = QVBoxLayout(group)
        self.developer_tools_checkbox = QCheckBox(SETTINGS_TEXT.developer_tools)
        self.developer_tools_checkbox.setObjectName("settingsDeveloperTools")
        hint = QLabel(SETTINGS_TEXT.developer_tools_hint)
        hint.setObjectName("settingsDataScopeHint")
        hint.setWordWrap(True)
        layout.addWidget(self.developer_tools_checkbox)
        layout.addWidget(hint)
        if self.advanced_page is not None:
            self.advanced_page.setVisible(False)
            layout.addWidget(self.advanced_page)
            self.developer_tools_checkbox.toggled.connect(
                self.advanced_page.setVisible
            )
        return group

    def _build_recommendation_group(self) -> QGroupBox:
        group = QGroupBox("RECOMMENDATION")
        group.setProperty("settingsCard", True)
        form = QFormLayout(group)
        self._configure_form(form)
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
        # One control replaces the candidate pool size, the randomness factor
        # and the deterministic seed. Those are properties of the sampler, not
        # decisions a person can reason about, so they are derived from this
        # instead. The originals stay as hidden widgets so stored settings
        # round trip unchanged.
        self.adventurousness_input = SteppedSlider(Qt.Orientation.Horizontal)
        self.adventurousness_input.setObjectName("settingsAdventurousness")
        self.adventurousness_input.setRange(1, 10)
        self.adventurousness_input.setPageStep(1)
        self.adventurousness_input.setAccessibleName(
            "How far AniRec reaches beyond your usual taste"
        )
        adventurousness_row = QWidget()
        adventurousness_layout = QHBoxLayout(adventurousness_row)
        adventurousness_layout.setContentsMargins(0, 0, 0, 0)
        low = QLabel(SETTINGS_TEXT.adventurousness_low)
        high = QLabel(SETTINGS_TEXT.adventurousness_high)
        low.setObjectName("settingsDataScopeHint")
        high.setObjectName("settingsDataScopeHint")
        adventurousness_layout.addWidget(low)
        adventurousness_layout.addWidget(self.adventurousness_input, 1)
        adventurousness_layout.addWidget(high)

        adventurousness_hint = QLabel(SETTINGS_TEXT.adventurousness_hint)
        adventurousness_hint.setObjectName("settingsDataScopeHint")
        adventurousness_hint.setWordWrap(True)

        form.addRow(SETTINGS_TEXT.adventurousness, adventurousness_row)
        form.addRow("", adventurousness_hint)
        form.addRow("BATCH SIZE", self.recommendation_count_input)
        form.addRow("MIN MAL SCORE", self.minimum_score_input)
        form.addRow("DEFAULT SORT", self.default_sort_input)
        form.addRow("HIDDEN ITEMS", self.include_hidden_input)
        form.addRow("MAL CONTENT", self.include_nsfw_input)

        # Kept for round tripping and for the developer tools view; they are no
        # longer surfaced as separate questions to answer.
        for widget in (
            self.top_limit_input,
            self.candidate_pool_input,
            self.randomness_input,
            self.seed_input,
        ):
            widget.setVisible(False)
        self.adventurousness_input.valueChanged.connect(self._sync_adventurousness)
        return group

    def _sync_adventurousness(self, value: int) -> None:
        """Derive the sampler settings from the single visible control."""
        self.randomness_input.setValue(max(1, min(10, int(value))))

    def _adventurousness_from(self, pipeline) -> int:
        return max(1, min(10, int(getattr(pipeline, "randomness_factor", 5) or 5)))

    def _build_profile_group(self) -> QGroupBox:
        group = QGroupBox("PROFILES")
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
        group = QGroupBox("MYANIMELIST API")
        group.setProperty("settingsCard", True)
        layout = QVBoxLayout(group)
        form = QFormLayout()
        self._configure_form(form)
        self.client_id_input = QLineEdit()
        self.client_id_input.setObjectName("settingsClientId")
        self.client_secret_input = QLineEdit()
        self.client_secret_input.setObjectName("settingsClientSecret")
        self.client_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.redirect_uri_input = QLineEdit()
        self.redirect_uri_input.setObjectName("settingsRedirectUri")
        form.addRow("CLIENT ID", self.client_id_input)
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
        group = QGroupBox("APPEARANCE")
        group.setProperty("settingsCard", True)
        form = QFormLayout(group)
        self._configure_form(form)
        self.theme_input = QComboBox()
        self.theme_input.addItem("System", "system")
        self.theme_input.addItem("Dark", "dark")
        self.theme_input.addItem("Light", "light")
        self.theme_input.addItem("OLED black", "oled")
        self.theme_input.addItem("Gradient", "gradient")
        self.theme_input.currentIndexChanged.connect(self._on_theme_changed)
        self.font_scale_input = QDoubleSpinBox()
        self.font_scale_input.setRange(0.80, 1.40)
        self.font_scale_input.setDecimals(2)
        self.font_scale_input.setSingleStep(0.05)
        self.font_scale_input.setSuffix("×")
        self.show_covers_input = QCheckBox("Show anime covers")
        # CHANGE [BUG2]: GUI Scale. Qt stylesheets have no relative units, so the
        # equivalent is one factor that every hand-sized dimension is routed
        # through, applied here and consumed by gui/scaling.py.
        self.gui_scale_input = QComboBox()
        self.gui_scale_input.setObjectName("settingsGuiScale")
        self.gui_scale_input.setAccessibleName("Overall size of the interface")
        for factor in GUI_SCALE_CHOICES:
            self.gui_scale_input.addItem(f"{round(factor * 100)}%", factor)
        self.gui_scale_input.currentIndexChanged.connect(self._on_gui_scale_changed)
        self.gui_scale_hint = QLabel(
            "Resizes everything together: cards, portraits, badges, spacing and "
            "text. Separate from the Windows display scaling."
        )
        self.gui_scale_hint.setObjectName("settingsDataScopeHint")
        self.gui_scale_hint.setWordWrap(True)

        self.oled_hint = QLabel(
            "OLED black uses true black, which switches pixels off entirely on "
            "OLED panels."
        )
        self.oled_hint.setObjectName("settingsDataScopeHint")
        self.oled_hint.setWordWrap(True)

        self.gradient_picker = GradientPicker()
        # CHANGE [SAVE-MODEL]: these two had no change signal at all, so a
        # font scale or an artwork preference did nothing whatsoever until the
        # Save button was found - in a panel where the control directly above
        # them applied itself instantly. The font scale goes through the same
        # coalesced preview as the theme, because applying a stylesheet
        # re-polishes the whole tree and a spin box emits on every click.
        self.font_scale_input.valueChanged.connect(self._on_font_scale_changed)
        self.show_covers_input.toggled.connect(self._on_show_covers_changed)
        self.gradient_picker.changed.connect(lambda *_args: self._preview_theme())
        # CHANGE [FEAT1]: only a committed colour is written to the config.
        self.gradient_picker.committed.connect(
            lambda *_args: self._persist_appearance()
        )

        form.addRow("THEME", self.theme_input)
        form.addRow("", self.oled_hint)
        self.gradient_row_label = QLabel("Gradient colours")
        form.addRow(self.gradient_row_label, self.gradient_picker)
        form.addRow("GUI SCALE", self.gui_scale_input)
        form.addRow("", self.gui_scale_hint)
        form.addRow("FONT SCALE", self.font_scale_input)
        form.addRow("ARTWORK", self.show_covers_input)
        self._on_theme_changed()
        return group

    def _on_gui_scale_changed(self, *_args) -> None:
        """CHANGE [BUG2]: apply the scale immediately and rebuild what it sizes."""
        factor = self.gui_scale_input.currentData()
        if factor is None:
            return
        set_gui_scale(factor)
        self._preview_theme()
        # CHANGE [BUG2]: persist immediately through the preferences path, which
        # does not require credentials. The Save button keeps its existing
        # contract of refusing an API configuration with no Client ID, so
        # appearance would otherwise be unsavable until an account existed.
        self._persist_appearance()
        self.gui_scale_changed.emit(float(factor))

    def _on_font_scale_changed(self, *_args) -> None:
        """Apply the new size and keep it, the way the scale beside it does."""
        if self._loading:
            return
        self._preview_theme()
        self._persist_appearance()

    def _on_show_covers_changed(self, checked: bool) -> None:
        """Keep the preference and tell the feeds, without a full re-apply.

        A narrow signal rather than reusing the settings-saved path: that one
        re-applies the stylesheet, which re-polishes every widget in the tree
        and costs about a second. Turning artwork off should not.
        """
        if self._loading:
            return
        self._persist_appearance()
        self.show_covers_changed.emit(bool(checked))

    def _persist_appearance(self) -> None:
        """Store appearance choices without demanding an API configuration.

        CHANGE [SAVE-MODEL]: this now covers every control in the Appearance
        panel, and every one of them calls it.

        Three of the five used to be missing. Gradient colours and GUI scale
        kept themselves the moment they changed; theme, font scale and Show
        anime covers did not, and waited for the Save button - which validates
        an API configuration and refuses without a Client ID. So a visitor
        looking around with sample data could pick a theme, watch it take
        effect, and lose it on the next launch, while the GUI scale they set
        in the same panel survived. Worse for the theme than for the others:
        it previews live, so the interface positively asserted that the choice
        had been taken.

        The line the page draws now is a real one - preferences apply and are
        kept the moment you touch them; the API configuration and the pipeline
        are configuration, and those are what Save owns.
        """
        if self._loading:
            return
        try:
            current = self.settings_service.load()
            self.settings_service.save_preferences(
                replace(
                    current,
                    theme=self.theme_input.currentData() or current.theme,
                    gradient_start=self.gradient_picker.start,
                    gradient_end=self.gradient_picker.end,
                    gui_scale=float(self.gui_scale_input.currentData() or 1.0),
                    font_scale=float(self.font_scale_input.value()),
                    show_covers=self.show_covers_input.isChecked(),
                )
            )
        except (AniRecError, OSError, TypeError, ValueError):
            # A preference is never worth interrupting the session over.
            return

    def _on_theme_changed(self, *_args) -> None:
        """Show only the controls the selected theme actually uses."""
        theme = self.theme_input.currentData()
        for widget in (self.gradient_row_label, self.gradient_picker):
            widget.setVisible(theme == "gradient")
        self.oled_hint.setVisible(theme == "oled")
        self._preview_theme()
        self._persist_appearance()

    def _preview_theme(self) -> None:
        """Apply the selection immediately, so the choice can be seen.

        CHANGE [BUG-PREVIEW]: only when the user changed something. Populating
        these controls from stored settings also fires their change signals, so
        a preview was being queued during every reload and then applied a
        moment later, overwriting whatever theme had just been applied
        elsewhere. A theme chosen anywhere reverted to whatever this page
        happened to be showing.

        A theme is judged by looking at it. Requiring Save first would mean
        picking two gradient colours blind.

        CHANGE [FEAT1]: coalesced. Applying a stylesheet makes Qt re-polish
        every widget in the tree, which costs about a second here, and the
        colour picker emits a change on every mouse move. Applying each one
        made dragging unusable. The latest request wins after a short pause,
        so the preview keeps up with the drag instead of queueing behind it.
        """
        if self.theme_manager is None or self._loading:
            return
        self._preview_timer.start(PREVIEW_COALESCE_MS)

    def _apply_preview_now(self) -> None:
        if self.theme_manager is None or self._loading:
            return
        self.theme_manager.apply(
            self.theme_input.currentData() or "system",
            font_scale=float(self.font_scale_input.value()),
            gui_scale=float(self.gui_scale_input.currentData() or 1.0),
            gradient_start=self.gradient_picker.start,
            gradient_end=self.gradient_picker.end,
        )

    def _build_data_group(self) -> QGroupBox:
        # Qt has no text-transform, so the case lives in the string - and every
        # other section legend on this page is set in caps.
        group = QGroupBox("LOCAL DATA")
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
        # CHANGE [BLAST-RADIUS]: the irreversible one used to sit in the same
        # evenly-spaced run as three benign ones, so "Clear cache" and "Delete
        # all local data" were adjacent, identically sized, and one slip
        # apart. Red carried the entire warning. It is now separated from the
        # reversible group and pushed to the far end, so reaching it is a
        # deliberate movement rather than an adjacent one.
        for button in (
            self.clear_cache_button,
            self.clear_covers_button,
            self.open_logs_button,
        ):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addSpacing(SPACE["xl"])
        buttons.addWidget(self.delete_all_data_button)
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
        # CHANGE [BUG-PREVIEW]: populating these controls fires their change
        # signals, which used to queue a theme preview that then overwrote the
        # theme the application had just applied.
        self._loading = True
        try:
            self._reload_controls()
        finally:
            self._loading = False
            # CHANGE [BUG-PREVIEW]: discard anything queued while populating,
            # including a preview armed while the page was being constructed.
            # Otherwise it fires afterwards and reverts the applied theme.
            self._preview_timer.stop()

    def _reload_controls(self) -> None:
        settings = self.settings_service.load()
        self._saved_secret = settings.client_secret
        pipeline = settings.pipeline
        self.top_limit_input.setValue(pipeline.top_anime_limit)
        self.recommendation_count_input.setValue(pipeline.recommendation_count)
        self.candidate_pool_input.setValue(pipeline.candidate_pool_size)
        self.randomness_input.setValue(pipeline.randomness_factor)
        self.adventurousness_input.setValue(self._adventurousness_from(pipeline))
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
            "Saved securely. Leave blank to keep." if self._saved_secret else ""
        )
        self.redirect_uri_input.setText(settings.redirect_uri)
        # CHANGE [BUG2]: restore the saved GUI scale before anything is sized.
        set_gui_scale(settings.gui_scale)
        index = self.gui_scale_input.findData(clamp_gui_scale(settings.gui_scale))
        self.gui_scale_input.setCurrentIndex(max(0, index))
        self.gradient_picker.set_colours(settings.gradient_start, settings.gradient_end)
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
            gradient_start=self.gradient_picker.start,
            gradient_end=self.gradient_picker.end,
            # CHANGE [BUG2]: persist the GUI scale with everything else.
            gui_scale=float(self.gui_scale_input.currentData() or 1.0),
            font_scale=self.font_scale_input.value(),
            show_covers=self.show_covers_input.isChecked(),
        )

    def _is_configuring_api(self, settings: AppSettings) -> bool:
        """Whether this save is an attempt to set up MyAnimeList access.

        The distinction decides which validation applies, so it has to be
        wider than "is the Client ID box empty". Someone who typed a secret
        and forgot the ID, or who already had a working configuration and has
        just cleared a field, is configuring the API and must be told which
        field is missing. Someone who has never entered any of it is not, and
        should not be blocked from changing a content filter.
        """
        if (settings.client_id or "").strip():
            return True
        if self.client_secret_input.text().strip() or self._saved_secret:
            return True
        try:
            return bool((self.settings_service.load().client_id or "").strip())
        except (AniRecError, OSError, TypeError, ValueError):
            return False

    def save(self) -> bool:
        """Persist the form.

        CHANGE [DEMO-SAVE]: a blank Client ID means the API is not being
        configured, not that the rest of the page is unsavable.

        ``settings_service.save`` validates an API configuration and refuses
        one with no Client ID. Every field on this page went through it, so
        somebody looking around with sample data who ticked "Include NSFW
        anime" and pressed Save was told *"MAL client ID is required"* - a
        message about credentials, in answer to a content filter - and nothing
        was written. The whole recommendation panel was unreachable on the one
        path the product most wants people to take.

        With no Client ID there is no API configuration to check, so the form
        is written through the preference path, which validates everything
        that is not a credential. The moment a Client ID is present the strict
        validation applies again, so a malformed redirect URI is still caught.
        """
        try:
            settings = self.settings_value()
            configuring_api = self._is_configuring_api(settings)
            if configuring_api:
                self.settings_service.save(settings)
            else:
                self.settings_service.save_preferences(settings)
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
            "Saved securely. Leave blank to keep." if self._saved_secret else ""
        )
        self._set_status(
            "Settings saved and applied."
            if configuring_api
            else "Settings saved. MyAnimeList is not connected yet.",
            error=False,
        )
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
