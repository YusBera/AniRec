from __future__ import annotations

import time

from PySide6.QtCore import QThread, QTimer

from AniRec.errors import DataError, UserFacingError
from AniRec.gui.main_window import MainWindow
from AniRec.gui.workers import BaseWorker, OperationAlreadyRunningError, WorkerController
from AniRec.gui_main import create_application
from AniRec.models import PipelineProgress


class SuccessfulWorker(BaseWorker):
    def __init__(self, result="complete"):
        super().__init__()
        self.result = result
        self.execution_thread = None

    def execute(self):
        self.execution_thread = QThread.currentThread()
        self.report_progress(PipelineProgress("fetch_top", "Fetch top anime", 1, 2, True))
        return self.result


class FailingWorker(BaseWorker):
    def execute(self):
        raise DataError("technical path and record details")


class UnexpectedFailingWorker(BaseWorker):
    def execute(self):
        raise RuntimeError("client_secret=must-not-reach-the-GUI")


class CooperativeSlowWorker(BaseWorker):
    def execute(self):
        for _ in range(100):
            time.sleep(0.005)
            self.cancellation_token.raise_if_cancelled()
        return "too late"


def wait_until(application, predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        application.processEvents()
        time.sleep(0.002)
    application.processEvents()
    assert predicate()


def test_worker_success_relays_typed_signals_and_cleans_thread_once():
    application = create_application([])
    controller = WorkerController()
    worker = SuccessfulWorker({"status": "ok"})
    started = []
    progress = []
    steps = []
    results = []
    finished = []
    cleaned = []
    controller.started.connect(started.append)
    controller.progress_changed.connect(lambda key, value: progress.append((key, value)))
    controller.step_changed.connect(lambda *values: steps.append(values))
    controller.result_ready.connect(lambda key, value: results.append((key, value)))
    controller.finished.connect(finished.append)
    controller.thread_cleaned.connect(cleaned.append)

    controller.start("sync:profile-1", worker)
    wait_until(application, lambda: not controller.active_keys)

    assert started == ["sync:profile-1"]
    assert progress[0][0] == "sync:profile-1"
    assert isinstance(progress[0][1], PipelineProgress)
    assert steps == [("sync:profile-1", "fetch_top", "Fetch top anime")]
    assert results == [("sync:profile-1", {"status": "ok"})]
    assert finished == ["sync:profile-1"]
    assert cleaned == ["sync:profile-1"]
    assert worker.execution_thread is not application.thread()


def test_known_and_unexpected_errors_emit_only_safe_user_errors():
    application = create_application([])
    controller = WorkerController()
    errors = []
    finished = []
    controller.error_occurred.connect(lambda key, error: errors.append((key, error)))
    controller.finished.connect(finished.append)

    controller.start("known", FailingWorker())
    wait_until(application, lambda: "known" not in controller.active_keys)
    controller.start("unexpected", UnexpectedFailingWorker())
    wait_until(application, lambda: not controller.active_keys)

    assert [key for key, _error in errors] == ["known", "unexpected"]
    assert all(isinstance(error, UserFacingError) for _key, error in errors)
    assert errors[0][1].code == "data_error"
    assert errors[1][1].code == "application_error"
    assert "must-not-reach-the-GUI" not in repr(errors)
    assert finished == ["known", "unexpected"]


def test_cancellation_is_cooperative_and_finished_is_emitted_once():
    application = create_application([])
    controller = WorkerController()
    cancelled = []
    results = []
    finished = []
    controller.cancelled.connect(cancelled.append)
    controller.result_ready.connect(lambda *values: results.append(values))
    controller.finished.connect(finished.append)

    controller.start("slow", CooperativeSlowWorker())
    wait_until(application, lambda: controller.is_running("slow"))
    assert controller.cancel("slow")
    wait_until(application, lambda: not controller.active_keys)

    assert cancelled == ["slow"]
    assert results == []
    assert finished == ["slow"]
    assert not controller.cancel("missing")


def test_duplicate_operation_key_is_rejected_while_running():
    application = create_application([])
    controller = WorkerController()
    controller.start("sync:profile-1", CooperativeSlowWorker())
    wait_until(application, lambda: controller.is_running("sync:profile-1"))

    try:
        controller.start("sync:profile-1", SuccessfulWorker())
    except OperationAlreadyRunningError as error:
        assert "sync:profile-1" in str(error)
    else:
        raise AssertionError("Duplicate operation start should fail.")
    finally:
        controller.cancel("sync:profile-1")
        wait_until(application, lambda: not controller.active_keys)


def test_slow_worker_does_not_block_gui_event_loop_and_shutdown_cleans_it():
    application = create_application([])
    controller = WorkerController()
    timer_fired = []
    QTimer.singleShot(10, lambda: timer_fired.append(True))

    controller.start("responsive", CooperativeSlowWorker())
    wait_until(application, lambda: bool(timer_fired))

    assert controller.is_running("responsive")
    assert controller.shutdown(timeout_ms=2_000)
    wait_until(application, lambda: not controller.active_keys)


def test_main_window_close_cancels_owned_workers_without_orphans():
    application = create_application([])
    window = MainWindow()
    window.show()
    window.worker_controller.start("window-owned", CooperativeSlowWorker())
    wait_until(application, lambda: window.worker_controller.is_running("window-owned"))

    assert window.close()
    wait_until(application, lambda: not window.worker_controller.active_keys)

    assert not window.isVisible()
