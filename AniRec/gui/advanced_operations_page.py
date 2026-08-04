"""Seven independently runnable AniRec pipeline operations with prerequisites."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..application.pipeline import PipelineOrchestrator
from ..errors import UserFacingError
from ..models import PipelineProgress, PipelineResult, UserProfile
from ..services import AuthService, ProfileService, SettingsService
from .workers import RecommendationWorker, TokenRefreshWorker, WorkerController


@dataclass(frozen=True)
class AdvancedOperationDefinition:
    step_id: str
    title: str
    description: str
    output_name: str | None


ADVANCED_OPERATIONS = (
    AdvancedOperationDefinition(
        "fetch_top",
        "Fetch popular anime data",
        "Download the current popular anime catalogue used to build the candidate pool.",
        "top_anime.csv",
    ),
    AdvancedOperationDefinition(
        "fetch_completed",
        "Fetch the user's anime list",
        "Download completed anime and personal scores from the active MyAnimeList profile.",
        "completed_anime.csv",
    ),
    AdvancedOperationDefinition(
        "oauth",
        "Refresh the OAuth connection",
        "Refresh an expired token when possible, or validate the current account connection.",
        None,
    ),
    AdvancedOperationDefinition(
        "impute_scores",
        "Handle missing scores",
        "Fill missing personal scores using the profile's genre-based medians.",
        "completed_anime_imputed.csv",
    ),
    AdvancedOperationDefinition(
        "genre_importance",
        "Calculate genre importance",
        "Calculate explainable preference weights from the completed anime data.",
        "genre_importance.csv",
    ),
    AdvancedOperationDefinition(
        "generate_candidates",
        "Generate recommendation candidates",
        "Exclude watched titles and combine the popular and completed anime datasets.",
        "recommendation_candidates.csv",
    ),
    AdvancedOperationDefinition(
        "generate_recommendations",
        "Generate personal recommendations",
        "Rank candidates using genre importance, personal settings, and explainable scoring.",
        "{profile_id}_recommendations.csv",
    ),
)


@dataclass
class AdvancedOperationWidgets:
    frame: QFrame
    prerequisite: QLabel
    last_run: QLabel
    status: QLabel
    run_button: QPushButton
    open_button: QPushButton


class AdvancedOperationsPage(QWidget):
    output_opened = Signal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        worker_controller: WorkerController | None = None,
        orchestrator: PipelineOrchestrator | None = None,
        profile_service: ProfileService | None = None,
        settings_service: SettingsService | None = None,
        auth_service: AuthService | None = None,
        path_opener: Callable[[Path], bool] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page-advanced-operations")
        self.setAccessibleName("Advanced Operations page")
        self.worker_controller = worker_controller or WorkerController(self)
        self.orchestrator = orchestrator
        self.profile_service = profile_service
        self.settings_service = settings_service or SettingsService()
        self.auth_service = auth_service
        self.path_opener = path_opener or self._default_path_opener
        self.profile: UserProfile | None = None
        self.widgets: dict[str, AdvancedOperationWidgets] = {}
        self._operation_steps: dict[str, str] = {}
        self._result_outputs: dict[str, Path] = {}
        self._last_runs: dict[str, str] = {}
        self._build_ui()
        self.worker_controller.started.connect(self._on_started)
        self.worker_controller.progress_changed.connect(self._on_progress)
        self.worker_controller.result_ready.connect(self._on_result)
        self.worker_controller.error_occurred.connect(self._on_error)
        self.worker_controller.cancelled.connect(self._on_cancelled)
        self.worker_controller.finished.connect(self._on_finished)
        self.set_profile(None)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)
        title = QLabel("Advanced Operations")
        title.setObjectName("pageTitle")
        description = QLabel(
            "Run one pipeline step at a time. Each operation explains the data it requires."
        )
        description.setObjectName("pageDescription")
        description.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(description)

        scroll = QScrollArea()
        scroll.setObjectName("advancedOperationsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 8, 8, 8)
        layout.setSpacing(12)
        for definition in ADVANCED_OPERATIONS:
            frame = QFrame()
            frame.setObjectName("advancedOperationCard")
            frame.setProperty("advancedOperation", True)
            grid = QGridLayout(frame)
            grid.setContentsMargins(14, 12, 14, 12)
            grid.setHorizontalSpacing(12)
            heading = QLabel(definition.title)
            heading.setObjectName("advancedOperationTitle")
            body = QLabel(definition.description)
            body.setObjectName("advancedOperationDescription")
            body.setWordWrap(True)
            prerequisite = QLabel()
            prerequisite.setObjectName("advancedOperationPrerequisite")
            prerequisite.setWordWrap(True)
            last_run = QLabel("Last run: Never")
            last_run.setObjectName("advancedOperationLastRun")
            status = QLabel("Ready")
            status.setObjectName("advancedOperationStatus")
            status.setWordWrap(True)
            run_button = QPushButton("Run")
            run_button.setObjectName(f"advancedRun-{definition.step_id}")
            open_button = QPushButton("Open output")
            open_button.setObjectName(f"advancedOpen-{definition.step_id}")
            run_button.clicked.connect(
                lambda _checked=False, step_id=definition.step_id: self.run_step(step_id)
            )
            open_button.clicked.connect(
                lambda _checked=False, step_id=definition.step_id: self.open_output(step_id)
            )
            grid.addWidget(heading, 0, 0, 1, 2)
            grid.addWidget(body, 1, 0, 1, 2)
            grid.addWidget(prerequisite, 2, 0, 1, 2)
            grid.addWidget(last_run, 3, 0)
            grid.addWidget(status, 4, 0)
            grid.addWidget(run_button, 3, 1)
            grid.addWidget(open_button, 4, 1)
            grid.setColumnStretch(0, 1)
            self.widgets[definition.step_id] = AdvancedOperationWidgets(
                frame, prerequisite, last_run, status, run_button, open_button
            )
            layout.addWidget(frame)
        layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

    def set_profile(self, profile: UserProfile | None) -> None:
        self.profile = profile
        self.refresh_prerequisites()

    def refresh_prerequisites(self) -> None:
        for definition in ADVANCED_OPERATIONS:
            available, reason = self.prerequisite(definition.step_id)
            widgets = self.widgets[definition.step_id]
            operation_key = self.operation_key(definition.step_id)
            running = bool(operation_key and self.worker_controller.is_running(operation_key))
            widgets.run_button.setEnabled(available and not running)
            widgets.run_button.setToolTip(reason if not available else "")
            widgets.prerequisite.setText(
                "Prerequisites: Ready" if available else f"Prerequisites: {reason}"
            )
            output = self.output_path(definition.step_id)
            widgets.open_button.setEnabled(bool(output and output.is_file()))
            last_run = self._last_runs.get(definition.step_id)
            if last_run is None and output is not None and output.is_file():
                last_run = datetime.fromtimestamp(output.stat().st_mtime).astimezone().isoformat(
                    timespec="seconds"
                )
            widgets.last_run.setText(f"Last run: {last_run or 'Never'}")

    def prerequisite(self, step_id: str) -> tuple[bool, str]:
        if self.profile is None:
            return False, "Select or connect a profile first."
        settings = self.settings_service.load()
        if step_id == "oauth":
            if self.auth_service is None:
                return False, "OAuth services are not configured."
            if not settings.client_id:
                return False, "Save a MyAnimeList Client ID in Settings first."
            return True, ""
        if self.orchestrator is None:
            return False, "Pipeline services are not configured."
        if step_id in {"fetch_top", "fetch_completed"}:
            if not settings.client_id:
                return False, "Save a MyAnimeList Client ID in Settings first."
            return True, ""
        directory = self.profile_directory()
        if directory is None:
            return False, "The active profile directory is unavailable."
        completed = (
            directory / "completed_anime_imputed.csv"
            if (directory / "completed_anime_imputed.csv").is_file()
            else directory / "completed_anime.csv"
        )
        if step_id in {"impute_scores", "genre_importance"}:
            if not (directory / "completed_anime.csv").is_file():
                return False, "Run 'Fetch the user's anime list' first."
            return True, ""
        if step_id == "generate_candidates":
            if not completed.is_file():
                return False, "Run 'Fetch the user's anime list' first."
            if not (directory / "top_anime.csv").is_file():
                return False, "Run 'Fetch popular anime data' first."
            return True, ""
        if step_id == "generate_recommendations":
            if not (directory / "recommendation_candidates.csv").is_file():
                return False, "Run 'Generate recommendation candidates' first."
            if not (directory / "genre_importance.csv").is_file():
                return False, "Run 'Calculate genre importance' first."
            return True, ""
        raise ValueError(f"Unknown advanced operation: {step_id}")

    def operation_key(self, step_id: str) -> str | None:
        if self.profile is None:
            return None
        return f"advanced-{step_id}:{self.profile.profile_id}"

    def run_step(self, step_id: str) -> bool:
        available, reason = self.prerequisite(step_id)
        widgets = self.widgets[step_id]
        if not available or self.profile is None:
            widgets.status.setText(reason)
            return False
        key = self.operation_key(step_id)
        if key is None or self.worker_controller.is_running(key):
            return False
        settings = self.settings_service.load()
        if step_id == "oauth":
            worker = TokenRefreshWorker(
                self.auth_service, self.profile.profile_id, settings
            )
        else:
            worker = RecommendationWorker(
                self.orchestrator,
                self.profile.username,
                settings.pipeline,
                step_id=step_id,
            )
        self._operation_steps[key] = step_id
        widgets.status.setText("Starting…")
        self.worker_controller.start(key, worker)
        return True

    def profile_directory(self) -> Path | None:
        if self.profile is None:
            return None
        if self.profile_service is not None:
            return self.profile_service.directory(self.profile.profile_id)
        return Path(self.profile.output_dir) if self.profile.output_dir else None

    def output_path(self, step_id: str) -> Path | None:
        result_path = self._result_outputs.get(step_id)
        if result_path is not None:
            return result_path
        directory = self.profile_directory()
        if directory is None:
            return None
        definition = next(item for item in ADVANCED_OPERATIONS if item.step_id == step_id)
        if definition.output_name is None:
            return None
        return directory / definition.output_name.format(profile_id=self.profile.profile_id)

    def open_output(self, step_id: str) -> bool:
        path = self.output_path(step_id)
        directory = self.profile_directory()
        if path is None or directory is None or not path.is_file():
            return False
        resolved_path = path.resolve()
        resolved_directory = directory.resolve()
        if resolved_path.parent != resolved_directory:
            return False
        opened = bool(self.path_opener(resolved_path))
        if opened:
            self.output_opened.emit(resolved_path)
        return opened

    @staticmethod
    def _default_path_opener(path: Path) -> bool:
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _step_for_key(self, operation_key: str) -> str | None:
        return self._operation_steps.get(operation_key)

    def _on_started(self, operation_key: str) -> None:
        step_id = self._step_for_key(operation_key)
        if step_id is not None:
            self.widgets[step_id].status.setText("Running…")
            self.refresh_prerequisites()

    def _on_progress(self, operation_key: str, progress: object) -> None:
        step_id = self._step_for_key(operation_key)
        if step_id is not None and isinstance(progress, PipelineProgress):
            self.widgets[step_id].status.setText(progress.message or "Running…")

    def _on_result(self, operation_key: str, result: object) -> None:
        step_id = self._step_for_key(operation_key)
        if step_id is None:
            return
        self.widgets[step_id].status.setText("Completed")
        if isinstance(result, PipelineResult):
            self._last_runs[step_id] = result.completed_at or datetime.now().astimezone().isoformat(
                timespec="seconds"
            )
            if result.generated_files:
                self._result_outputs[step_id] = Path(result.generated_files[-1])
        self.refresh_prerequisites()

    def _on_error(self, operation_key: str, error: object) -> None:
        step_id = self._step_for_key(operation_key)
        if step_id is None:
            return
        self.widgets[step_id].status.setText(
            f"{error.title}. {error.solution}"
            if isinstance(error, UserFacingError)
            else "The operation failed."
        )

    def _on_cancelled(self, operation_key: str) -> None:
        step_id = self._step_for_key(operation_key)
        if step_id is not None:
            self.widgets[step_id].status.setText("Cancelled")

    def _on_finished(self, operation_key: str) -> None:
        step_id = self._operation_steps.pop(operation_key, None)
        if step_id is not None:
            self.refresh_prerequisites()
