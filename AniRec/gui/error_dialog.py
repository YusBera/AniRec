"""Shared user-safe error presentation with guarded retry and log access."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .instrument_widgets import Scanlines
from ..errors import UserFacingError


class ErrorDialog(QDialog):
    def __init__(
        self,
        error: UserFacingError,
        parent: QWidget | None = None,
        *,
        retry: Callable[[], bool] | None = None,
        open_logs: Callable[[], object] | None = None,
    ) -> None:
        super().__init__(parent)
        self.error = error
        self.retry_callback = retry
        self.open_logs_callback = open_logs
        self.retry_requested = False
        self.setObjectName("errorDialog")
        # CHANGE [CRT]: the raster, so this reads as part of the same
        # machine. Installed last in __init__ so it sits above the
        # dialog's own children; it re-raises itself when more arrive.
        self.setWindowTitle(error.title)
        self.setModal(False)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(12)
        self.title_label = QLabel(error.title)
        self.title_label.setObjectName("errorDialogTitle")
        self.title_label.setWordWrap(True)
        self.description_label = QLabel(error.description)
        self.description_label.setObjectName("errorDialogDescription")
        self.description_label.setWordWrap(True)
        solution_heading = QLabel("What you can do")
        solution_heading.setObjectName("errorDialogSectionTitle")
        self.solution_label = QLabel(error.solution)
        self.solution_label.setObjectName("errorDialogSolution")
        self.solution_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        layout.addWidget(self.description_label)
        layout.addWidget(solution_heading)
        layout.addWidget(self.solution_label)

        self.technical_button = QPushButton("Show technical details")
        self.technical_button.setCheckable(True)
        self.technical_button.setObjectName("errorDialogTechnicalToggle")
        self.technical_details = QPlainTextEdit()
        self.technical_details.setObjectName("errorDialogTechnicalDetails")
        self.technical_details.setReadOnly(True)
        self.technical_details.setPlainText(
            error.technical_details or f"Error code: {error.code}"
        )
        self.technical_details.setMaximumHeight(130)
        self.technical_details.setVisible(False)
        self.technical_button.toggled.connect(self._toggle_technical_details)
        layout.addWidget(self.technical_button)
        layout.addWidget(self.technical_details)

        self.action_status = QLabel()
        self.action_status.setObjectName("errorDialogActionStatus")
        self.action_status.setWordWrap(True)
        self.action_status.setVisible(False)
        layout.addWidget(self.action_status)

        buttons = QDialogButtonBox()
        self.retry_button = buttons.addButton(
            "Try Again", QDialogButtonBox.ButtonRole.ActionRole
        )
        self.retry_button.setObjectName("errorDialogRetryButton")
        self.retry_button.setVisible(error.retryable and retry is not None)
        self.log_button = buttons.addButton(
            "Open Log Folder", QDialogButtonBox.ButtonRole.ActionRole
        )
        self.log_button.setObjectName("errorDialogOpenLogsButton")
        self.log_button.setVisible(open_logs is not None)
        close_button = buttons.addButton(QDialogButtonBox.StandardButton.Close)
        close_button.setObjectName("errorDialogCloseButton")
        buttons.rejected.connect(self.close)
        self.retry_button.clicked.connect(self._retry)
        self.log_button.clicked.connect(self._open_logs)
        layout.addWidget(buttons)
        self.scanlines = Scanlines(self)
        self.scanlines.raise_()

    def _toggle_technical_details(self, visible: bool) -> None:
        self.technical_details.setVisible(visible)
        self.technical_button.setText(
            "Hide technical details" if visible else "Show technical details"
        )

    def _retry(self) -> None:
        if self.retry_requested or self.retry_callback is None:
            return
        self.retry_requested = True
        self.retry_button.setEnabled(False)
        if self.retry_callback():
            self.accept()
            return
        self.retry_requested = False
        self.retry_button.setEnabled(True)
        self.action_status.setText(
            "Retry could not start because the operation is still finishing. Try again shortly."
        )
        self.action_status.setVisible(True)

    def _open_logs(self) -> None:
        if self.open_logs_callback is None:
            return
        try:
            self.open_logs_callback()
        except Exception:
            self.action_status.setText(
                "The log folder could not be opened. Check folder permissions in Settings."
            )
            self.action_status.setVisible(True)
