from __future__ import annotations

import pytest

from AniRec.errors import (
    AccessDeniedError,
    AniRecError,
    AuthError,
    AuthTimeoutError,
    CancelledError,
    ConfigError,
    DataError,
    InvalidResponseError,
    NetworkError,
    NotFoundError,
    ProfileError,
    RateLimitError,
    ServerError,
    StorageError,
    UserFacingError,
    presentable_error,
)
from AniRec.gui.error_dialog import ErrorDialog
from AniRec.gui.main_window import MainWindow
from AniRec.gui_main import create_application


ERROR_TYPES = (
    AniRecError,
    NetworkError,
    AuthError,
    AuthTimeoutError,
    AccessDeniedError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ProfileError,
    DataError,
    InvalidResponseError,
    StorageError,
    ConfigError,
    CancelledError,
)


@pytest.mark.parametrize("error_type", ERROR_TYPES)
def test_every_application_error_has_complete_safe_presentation(error_type):
    error = error_type("access_token=fixture-secret")
    model = presentable_error(error)
    rendered = " ".join(
        (model.title, model.description, model.solution, model.technical_details or "")
    )
    assert model.code
    assert model.title
    assert model.description
    assert model.solution
    assert "fixture-secret" not in rendered
    assert "[REDACTED]" in (model.technical_details or "")
    assert "Traceback" not in rendered


def test_unexpected_exception_never_exposes_arbitrary_message():
    model = presentable_error(RuntimeError("private-user-path-and-secret"))
    assert model.code == "application_error"
    assert "private-user-path-and-secret" not in repr(model)
    assert "RuntimeError" in (model.technical_details or "")


def test_dialog_shows_complete_matrix_and_retry_is_guarded_against_duplicates():
    create_application([])
    calls = []
    logs = []
    error = UserFacingError(
        code="network_error",
        title="Connection problem",
        description="AniRec could not reach MyAnimeList.",
        solution="Check your internet connection and try again.",
        retryable=True,
        technical_details="NetworkError: connection refused",
    )
    dialog = ErrorDialog(
        error,
        retry=lambda: not calls.append(True),
        open_logs=lambda: logs.append(True),
    )
    dialog.show()

    assert dialog.title_label.text() == error.title
    assert dialog.description_label.text() == error.description
    assert dialog.solution_label.text() == error.solution
    assert dialog.retry_button.isVisibleTo(dialog)
    dialog.technical_button.setChecked(True)
    assert dialog.technical_details.isVisibleTo(dialog)
    assert "connection refused" in dialog.technical_details.toPlainText()
    dialog.log_button.click()
    assert logs == [True]
    dialog._retry()
    dialog._retry()
    assert calls == [True]
    dialog.close()


def test_a_non_retryable_error_hides_try_again():
    """The dialog itself still behaves correctly when one is opened explicitly."""
    create_application([])
    error = UserFacingError(
        "config_error",
        "Settings problem",
        "Settings are invalid.",
        "Review and save Settings.",
        retryable=False,
        technical_details="ConfigError (config_error)",
    )
    dialog = ErrorDialog(error)

    assert not dialog.retry_button.isVisible()
    assert "Traceback" not in dialog.technical_details.toPlainText()
    dialog.close()


def test_a_failed_operation_reports_inline_rather_than_opening_a_window():
    """BUG1: routine failures must not raise windows.

    An error box appearing on top of a progress box that was already closing
    itself is what produced the reported flashing. The message and the offer to
    retry now land on the surface the user is looking at.
    """
    create_application([])
    window = MainWindow()
    error = UserFacingError(
        "network_error",
        "Could not reach MyAnimeList",
        "The request timed out.",
        "Check your connection and try again.",
        retryable=True,
    )

    window._on_operation_error("sync:p1", error)
    window._on_operation_error("sync:p1", error)

    assert window.error_dialogs == {}
    status = window.discover_page.status_label.text()
    assert "Could not reach MyAnimeList" in status
    assert "Check your connection" in status
    window.close()
