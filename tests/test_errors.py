from __future__ import annotations

import pytest

from errors import (
    AniRecError,
    AuthError,
    CancelledError,
    ConfigError,
    DataError,
    NetworkError,
    ProfileError,
    StorageError,
)


@pytest.mark.parametrize(
    "error_type",
    [
        AniRecError,
        NetworkError,
        AuthError,
        ProfileError,
        DataError,
        StorageError,
        ConfigError,
        CancelledError,
    ],
)
def test_application_errors_have_complete_safe_user_models(error_type):
    technical_secret = "client_secret=must-not-reach-user-model"
    model = error_type(technical_secret).to_user_error()

    assert model.code
    assert model.title
    assert model.description
    assert model.solution
    assert "must-not-reach-user-model" not in repr(model)


def test_retryable_error_families_are_explicit():
    assert NetworkError().to_user_error().retryable is True
    assert AuthError().to_user_error().retryable is True
    assert DataError().to_user_error().retryable is True
    assert StorageError().to_user_error().retryable is True
    assert ConfigError().to_user_error().retryable is False
    assert CancelledError().to_user_error().retryable is False
