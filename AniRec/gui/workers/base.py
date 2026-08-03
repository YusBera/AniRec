"""Reusable QObject worker contract for long-running AniRec operations."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal, Slot

from ...application.pipeline import CancellationToken
from ...errors import AniRecError, CancelledError, presentable_error
from ...models import PipelineProgress


class BaseWorker(QObject):
    """Execute one operation once and emit a stable terminal signal sequence."""

    started = Signal()
    progress_changed = Signal(object)
    step_changed = Signal(str, str)
    result_ready = Signal(object)
    error_occurred = Signal(object)
    cancelled = Signal()
    finished = Signal()

    def __init__(
        self,
        *,
        cancellation_token: CancellationToken | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__()
        self.cancellation_token = cancellation_token or CancellationToken()
        self._logger = logger
        self._has_run = False
        self._operation_key: str | None = None

    @property
    def operation_key(self) -> str | None:
        return self._operation_key

    def bind_operation_key(self, operation_key: str) -> None:
        if self._operation_key is not None:
            raise RuntimeError("A worker can only be assigned to one operation.")
        self._operation_key = operation_key

    def request_cancel(self) -> None:
        """Thread-safe cooperative cancellation callable from the GUI thread."""
        self.cancellation_token.cancel()

    def report_progress(self, progress: PipelineProgress) -> None:
        self.progress_changed.emit(progress)
        self.step_changed.emit(progress.stage_id, progress.message)

    @Slot()
    def run(self) -> None:
        if self._has_run:
            return
        self._has_run = True
        self.started.emit()
        try:
            self.cancellation_token.raise_if_cancelled()
            result = self.execute()
            self.cancellation_token.raise_if_cancelled()
        except CancelledError:
            self.cancelled.emit()
        except AniRecError as error:
            self._log_failure(error)
            self.error_occurred.emit(presentable_error(error))
        except Exception as error:
            self._log_failure(error)
            self.error_occurred.emit(presentable_error(error))
        else:
            self.result_ready.emit(result)
        finally:
            self.finished.emit()

    def execute(self) -> object:
        """Perform work without reading or mutating GUI widgets."""
        raise NotImplementedError

    def _log_failure(self, error: Exception) -> None:
        if self._logger is not None:
            self._logger.exception(
                "Worker operation %s failed.",
                self._operation_key or "unbound",
                exc_info=error,
            )
