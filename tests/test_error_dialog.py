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


def test_non_retryable_dialog_hides_try_again_and_main_window_deduplicates_by_operation():
    create_application([])
    window = MainWindow()
    error = UserFacingError(
        "config_error",
        "Settings problem",
        "Settings are invalid.",
        "Review and save Settings.",
        retryable=False,
        technical_details="ConfigError (config_error)",
    )
    window._on_operation_error("settings-api-test:global", error)
    first = window.error_dialogs["settings-api-test:global"]
    window._on_operation_error("settings-api-test:global", error)

    assert window.error_dialogs["settings-api-test:global"] is first
    assert not first.retry_button.isVisible()
    assert "Traceback" not in first.technical_details.toPlainText()
    first.close()
    window.close()
