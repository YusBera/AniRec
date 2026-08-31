"""Operation progress UI bound to the shared worker controller."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .instrument_widgets import Scanlines
from ..errors import UserFacingError
from ..models import PipelineProgress
from .texts import PROGRESS_STEP_TEXT, UI_TEXT
from .workers import WorkerController


class OperationProgressDialog(QDialog):
    """Show determinate/indeterminate progress for one operation key."""

    SUCCESS_CLOSE_DELAY_MS = 900

    def __init__(
        self,
        operation_key: str,
        controller: WorkerController,
        parent: QWidget | None = None,
        *,
        success_close_delay_ms: int = SUCCESS_CLOSE_DELAY_MS,
    ) -> None:
        super().__init__(parent)
        self.operation_key = operation_key
        self.controller = controller
        self.is_terminal = False
        self._completed_successfully = False
        self._success_close_delay_ms = max(0, int(success_close_delay_ms))
        self.setObjectName("operationProgressDialog")
        # CHANGE [CRT]: the raster, so this reads as part of the same
        # machine. Installed last in __init__ so it sits above the
        # dialog's own children; it re-raises itself when more arrive.
        self.setWindowTitle(UI_TEXT.progress_dialog_title)
        self.setModal(False)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(12)

        self.step_label = QLabel(UI_TEXT.progress_waiting)
        self.step_label.setObjectName("progressStepLabel")
        self.step_label.setWordWrap(True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("operationProgressBar")
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setAccessibleName("Operation progress")
        self.counter_label = QLabel(UI_TEXT.progress_working)
        self.counter_label.setObjectName("progressCounterLabel")
        self.cancel_button = QPushButton(UI_TEXT.progress_cancel)
        self.cancel_button.setObjectName("progressCancelButton")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel_or_close)

        layout.addWidget(self.step_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.counter_label)
        layout.addWidget(self.cancel_button)

        controller.progress_changed.connect(self._on_progress)
        controller.result_ready.connect(self._on_result)
        controller.error_occurred.connect(self._on_error)
        controller.cancelled.connect(self._on_cancelled)
        controller.finished.connect(self._on_finished)
        self.scanlines = Scanlines(self)
        self.scanlines.raise_()

    def apply_progress(self, progress: PipelineProgress) -> None:
        self.step_label.setText(
            PROGRESS_STEP_TEXT.get(progress.stage_id, progress.message or UI_TEXT.progress_working)
        )
        if progress.total > 0:
            self.progress_bar.setRange(0, progress.total)
            self.progress_bar.setValue(min(progress.current, progress.total))
            self.counter_label.setText(
                UI_TEXT.progress_counter_template.format(
                    current=progress.current,
                    total=progress.total,
                )
            )
        else:
            self.progress_bar.setRange(0, 0)
            self.counter_label.setText(UI_TEXT.progress_working)
        self.cancel_button.setEnabled(progress.cancellable and not self.is_terminal)

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self.is_terminal and self.controller.is_running(self.operation_key):
            self._request_cancel()
            event.ignore()
            return
        event.accept()

    def _matches(self, operation_key: str) -> bool:
        return operation_key == self.operation_key

    def _on_progress(self, operation_key: str, progress: object) -> None:
        if self._matches(operation_key) and isinstance(progress, PipelineProgress):
            self.apply_progress(progress)

    def _on_result(self, operation_key: str, _result: object) -> None:
        if self._matches(operation_key):
            self._completed_successfully = True
            self.step_label.setText(UI_TEXT.progress_completed)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.counter_label.setText("Completed successfully")
            self.setProperty("operationState", "success")
            self.style().unpolish(self)
            self.style().polish(self)

    def _on_error(self, operation_key: str, error: object) -> None:
        if self._matches(operation_key):
            self._completed_successfully = False
            self.step_label.setText(
                error.title if isinstance(error, UserFacingError) else UI_TEXT.progress_working
            )

    def _on_cancelled(self, operation_key: str) -> None:
        if self._matches(operation_key):
            self._completed_successfully = False
            self.step_label.setText(UI_TEXT.progress_cancelled)

    def _on_finished(self, operation_key: str) -> None:
        if not self._matches(operation_key):
            return
        self.is_terminal = True
        if self._completed_successfully:
            self.cancel_button.setText("Closing automatically…")
            self.cancel_button.setEnabled(False)
            QTimer.singleShot(self._success_close_delay_ms, self._close_after_success)
        else:
            self.cancel_button.setText(UI_TEXT.progress_close)
            self.cancel_button.setEnabled(True)

    def _close_after_success(self) -> None:
        if self.is_terminal and self._completed_successfully:
            self.accept()

    def _cancel_or_close(self) -> None:
        if self.is_terminal:
            self.close()
        else:
            self._request_cancel()

    def _request_cancel(self) -> None:
        if self.controller.cancel(self.operation_key):
            self.cancel_button.setText(UI_TEXT.progress_cancelling)
            self.cancel_button.setEnabled(False)
            self.step_label.setText(UI_TEXT.progress_cancelling)
