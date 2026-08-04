from __future__ import annotations

from PySide6.QtCore import QTimer

from AniRec.gui.main_window import MainWindow
from AniRec.gui_main import SAFE_STARTUP_ERROR, create_application, main
from AniRec.metadata import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    MINIMUM_WINDOW_HEIGHT,
    MINIMUM_WINDOW_WIDTH,
    ORGANIZATION_NAME,
)


def test_create_application_is_singleton_with_central_metadata():
    first = create_application([])
    second = create_application(["ignored-after-first-creation"])

    assert first is second
    assert first.applicationName() == APP_NAME
    assert first.applicationVersion() == APP_VERSION
    assert first.organizationName() == ORGANIZATION_NAME


def test_main_window_has_expected_initial_and_minimum_size():
    create_application([])
    window = MainWindow()

    assert window.width() == DEFAULT_WINDOW_WIDTH
    assert window.height() == DEFAULT_WINDOW_HEIGHT
    assert window.minimumWidth() == MINIMUM_WINDOW_WIDTH
    assert window.minimumHeight() == MINIMUM_WINDOW_HEIGHT
    assert window.centralWidget() is not None
    assert window.windowTitle() == APP_NAME

    window.close()


def test_main_runs_the_qt_event_loop_and_exits_cleanly(system_temp_dir):
    application = create_application([])
    QTimer.singleShot(0, application.quit)

    assert main([], root_override=system_temp_dir / "app-data") == 0


def test_startup_failure_shows_only_safe_message_and_redacts_log(system_temp_dir):
    presented_messages: list[str] = []

    def fail_to_create_window():
        raise RuntimeError("client_secret=highly-sensitive-value")

    exit_code = main(
        [],
        root_override=system_temp_dir,
        window_factory=fail_to_create_window,
        error_presenter=presented_messages.append,
    )

    log_text = (system_temp_dir / "logs" / "anirec.log").read_text(encoding="utf-8")
    assert exit_code == 1
    assert presented_messages == [SAFE_STARTUP_ERROR]
    assert "highly-sensitive-value" not in presented_messages[0]
    assert "highly-sensitive-value" not in log_text
    assert "client_secret=[REDACTED]" in log_text
