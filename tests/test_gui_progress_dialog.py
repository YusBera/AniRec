from __future__ import annotations

import time

from AniRec.gui.main_window import MainWindow
from AniRec.gui.progress_dialog import OperationProgressDialog
from AniRec.gui.texts import UI_TEXT
from AniRec.gui.workers import BaseWorker, WorkerController
from AniRec.gui_main import create_application
from AniRec.models import PipelineProgress


class ProgressSlowWorker(BaseWorker):
    def execute(self):
        self.report_progress(PipelineProgress("fetch_top", "internal copy", 1, 3, True))
        for _ in range(100):
            time.sleep(0.003)
            self.cancellation_token.raise_if_cancelled()
        return "done"


def wait_until(application, predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        application.processEvents()
        time.sleep(0.002)
    application.processEvents()
    assert predicate()


def test_progress_dialog_maps_step_and_determinate_values():
    create_application([])
    controller = WorkerController()
    dialog = OperationProgressDialog("sync:p1", controller)

    dialog.apply_progress(PipelineProgress("fetch_top", "ignored", 2, 5, True))

    assert dialog.step_label.text() == "Fetch top anime"
    assert dialog.progress_bar.minimum() == 0
    assert dialog.progress_bar.maximum() == 5
    assert dialog.progress_bar.value() == 2
    assert dialog.counter_label.text() == "2 of 5"
    assert dialog.cancel_button.isEnabled()


def test_progress_dialog_uses_indeterminate_mode_for_unknown_total():
    create_application([])
    controller = WorkerController()
    dialog = OperationProgressDialog("oauth:p1", controller)

    dialog.apply_progress(PipelineProgress("oauth", "ignored", 0, 0, True))

    assert dialog.step_label.text() == "Connect MyAnimeList account"
    assert dialog.progress_bar.minimum() == 0
    assert dialog.progress_bar.maximum() == 0
    assert dialog.counter_label.text() == UI_TEXT.progress_working


def test_progress_dialog_filters_operations_and_cancel_button_stops_worker():
    application = create_application([])
    controller = WorkerController()
    dialog = OperationProgressDialog("sync:p1", controller)
    dialog.show()
    controller.progress_changed.emit(
        "sync:other",
        PipelineProgress("fetch_completed", "Other", 2, 2, True),
    )
    assert dialog.step_label.text() == UI_TEXT.progress_waiting

    controller.start("sync:p1", ProgressSlowWorker())
    wait_until(application, lambda: dialog.cancel_button.isEnabled())
    assert dialog.step_label.text() == "Fetch top anime"

    dialog.cancel_button.click()
    assert dialog.cancel_button.text() == UI_TEXT.progress_cancelling
    assert not dialog.cancel_button.isEnabled()
    wait_until(application, lambda: dialog.is_terminal)
    wait_until(application, lambda: not controller.active_keys)

    assert dialog.step_label.text() == UI_TEXT.progress_cancelled
    assert dialog.cancel_button.text() == UI_TEXT.progress_close
    dialog.close()


def test_main_window_reuses_one_progress_dialog_per_operation_key():
    create_application([])
    window = MainWindow()

    first = window.show_operation_progress("sync:p1")
    second = window.show_operation_progress("sync:p1")

    assert first is second
    first.is_terminal = True
    first.close()
    window.close()


def test_successful_progress_dialog_closes_automatically_after_brief_success_state():
    application = create_application([])
    controller = WorkerController()
    dialog = OperationProgressDialog(
        "sync:p1", controller, success_close_delay_ms=10
    )
    dialog.show()

    controller.result_ready.emit("sync:p1", "done")
    controller.finished.emit("sync:p1")
    assert dialog.is_terminal
    assert dialog.progress_bar.value() == 100
    assert dialog.counter_label.text() == "Completed successfully"
    assert dialog.cancel_button.text() == "Closing automatically…"
    assert not dialog.cancel_button.isEnabled()
    wait_until(application, lambda: not dialog.isVisible())
