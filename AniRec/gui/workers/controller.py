"""Single owner for AniRec worker threads and their cleanup."""

from __future__ import annotations

import time
from dataclasses import dataclass

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot

from .base import BaseWorker


class OperationAlreadyRunningError(RuntimeError):
    pass


@dataclass(frozen=True)
class _OperationHandle:
    key: str
    worker: BaseWorker
    thread: QThread
    relay: "_WorkerSignalRelay"


class _WorkerSignalRelay(QObject):
    """Keep the operation key available after the worker schedules deletion."""

    def __init__(self, key: str, controller: "WorkerController") -> None:
        super().__init__(controller)
        self.key = key
        self.controller = controller

    @Slot()
    def started(self) -> None:
        self.controller.started.emit(self.key)

    @Slot(object)
    def progress_changed(self, progress: object) -> None:
        self.controller.progress_changed.emit(self.key, progress)

    @Slot(str, str)
    def step_changed(self, step_id: str, message: str) -> None:
        self.controller.step_changed.emit(self.key, step_id, message)

    @Slot(object)
    def result_ready(self, result: object) -> None:
        self.controller.result_ready.emit(self.key, result)

    @Slot(object)
    def error_occurred(self, error: object) -> None:
        self.controller.error_occurred.emit(self.key, error)

    @Slot()
    def cancelled(self) -> None:
        self.controller.cancelled.emit(self.key)

    @Slot()
    def finished(self) -> None:
        self.controller.finished.emit(self.key)

    @Slot()
    def thread_finished(self) -> None:
        self.controller._finalize_operation(self.key)


class WorkerController(QObject):
    """Create, relay, cancel, wait for, and clean up all GUI workers."""

    started = Signal(str)
    progress_changed = Signal(str, object)
    step_changed = Signal(str, str, str)
    result_ready = Signal(str, object)
    error_occurred = Signal(str, object)
    cancelled = Signal(str)
    finished = Signal(str)
    thread_cleaned = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._operations: dict[str, _OperationHandle] = {}

    @property
    def active_keys(self) -> tuple[str, ...]:
        return tuple(self._operations)

    def is_running(self, operation_key: str) -> bool:
        handle = self._operations.get(operation_key)
        return bool(handle and handle.thread.isRunning())

    def start(self, operation_key: str, worker: BaseWorker) -> None:
        key = operation_key.strip()
        if not key:
            raise ValueError("operation_key is required.")
        if key in self._operations:
            raise OperationAlreadyRunningError(f"Operation is already running: {key}")
        if worker.parent() is not None:
            raise ValueError("A worker must not have a parent before moveToThread().")

        worker.bind_operation_key(key)
        thread = QThread(self)
        thread.setObjectName(f"AniRecWorkerThread-{key}")
        relay = _WorkerSignalRelay(key, self)
        worker.moveToThread(thread)

        worker.started.connect(relay.started)
        worker.progress_changed.connect(relay.progress_changed)
        worker.step_changed.connect(relay.step_changed)
        worker.result_ready.connect(relay.result_ready)
        worker.error_occurred.connect(relay.error_occurred)
        worker.cancelled.connect(relay.cancelled)
        worker.finished.connect(relay.finished)
        worker.finished.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        worker.finished.connect(worker.deleteLater)
        thread.started.connect(worker.run)
        thread.finished.connect(relay.thread_finished)
        thread.finished.connect(thread.deleteLater)

        self._operations[key] = _OperationHandle(key, worker, thread, relay)
        thread.start()

    def cancel(self, operation_key: str) -> bool:
        handle = self._operations.get(operation_key)
        if handle is None:
            return False
        handle.worker.request_cancel()
        return True

    def wait(self, operation_key: str, timeout_ms: int = 5_000) -> bool:
        handle = self._operations.get(operation_key)
        return True if handle is None else handle.thread.wait(max(0, timeout_ms))

    def shutdown(self, timeout_ms: int = 5_000) -> bool:
        """Cooperatively cancel every worker and wait without forced termination."""
        handles = tuple(self._operations.values())
        for handle in handles:
            handle.worker.request_cancel()

        deadline = time.monotonic() + max(0, timeout_ms) / 1000
        all_stopped = True
        for handle in handles:
            remaining_ms = max(0, int((deadline - time.monotonic()) * 1000))
            if handle.thread.isRunning() and not handle.thread.wait(remaining_ms):
                all_stopped = False
        return all_stopped

    def _finalize_operation(self, operation_key: str) -> None:
        if self._operations.pop(operation_key, None) is not None:
            self.thread_cleaned.emit(operation_key)
