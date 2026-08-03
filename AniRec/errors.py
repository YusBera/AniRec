"""Application error families and their safe presentation model."""

from __future__ import annotations

from dataclasses import dataclass

try:
    from .infrastructure.logging_config import redact_secrets
except ImportError:  # Compatibility with legacy top-level imports.
    from infrastructure.logging_config import redact_secrets


@dataclass(frozen=True)
class UserFacingError:
    code: str
    title: str
    description: str
    solution: str
    retryable: bool = False
    technical_details: str | None = None


class AniRecError(Exception):
    code = "application_error"
    user_title = "AniRec could not complete the operation"
    safe_description = "An unexpected application error occurred."
    suggested_solution = "Try again. If the problem continues, review the application log."
    retryable = False

    def to_user_error(self) -> UserFacingError:
        return UserFacingError(
            code=self.code,
            title=self.user_title,
            description=self.safe_description,
            solution=self.suggested_solution,
            retryable=self.retryable,
        )


class NetworkError(AniRecError):
    code = "network_error"
    user_title = "Connection problem"
    safe_description = "AniRec could not reach MyAnimeList."
    suggested_solution = "Check your internet connection and try again."
    retryable = True


class AuthError(AniRecError):
    code = "auth_error"
    user_title = "Account connection problem"
    safe_description = "The MyAnimeList connection is unavailable or no longer valid."
    suggested_solution = "Reconnect your MyAnimeList account and retry the operation."
    retryable = True


class AuthTimeoutError(AuthError):
    code = "auth_timeout"
    user_title = "Account connection timed out"
    safe_description = "MyAnimeList authorization was not completed in time."
    suggested_solution = "Start the connection again and finish authorization in the browser."


class AccessDeniedError(AuthError):
    code = "access_denied"
    user_title = "MyAnimeList access denied"
    safe_description = "AniRec is not allowed to access the requested MyAnimeList data."
    suggested_solution = "Check account permissions and whether the anime list is private."
    retryable = False


class NotFoundError(AniRecError):
    code = "not_found"
    user_title = "MyAnimeList data not found"
    safe_description = "The requested MyAnimeList user or anime data could not be found."
    suggested_solution = "Check the username or requested item and try again."


class RateLimitError(NetworkError):
    code = "rate_limited"
    user_title = "MyAnimeList request limit reached"
    safe_description = "MyAnimeList temporarily limited AniRec requests."
    suggested_solution = "Wait briefly before trying again."

    def __init__(self, technical_message: str = "", *, retry_after_seconds: int | None = None):
        super().__init__(technical_message)
        self.retry_after_seconds = retry_after_seconds


class ServerError(NetworkError):
    code = "server_error"
    user_title = "MyAnimeList service problem"
    safe_description = "MyAnimeList is temporarily unable to complete the request."
    suggested_solution = "Try again later."


class ProfileError(AniRecError):
    code = "profile_error"
    user_title = "Profile problem"
    safe_description = "AniRec could not use the selected profile."
    suggested_solution = "Check the profile and MyAnimeList username, then try again."


class DataError(AniRecError):
    code = "data_error"
    user_title = "Anime data problem"
    safe_description = "AniRec could not read or process the required anime data."
    suggested_solution = "Synchronize the profile again or restore the affected data file."
    retryable = True


class InvalidResponseError(DataError):
    code = "invalid_response"
    user_title = "Invalid MyAnimeList response"
    safe_description = "MyAnimeList returned data that AniRec could not safely process."
    suggested_solution = "Try again. If the problem continues, update AniRec or review the log."


class StorageError(AniRecError):
    code = "storage_error"
    user_title = "File storage problem"
    safe_description = "AniRec could not safely read or save local application data."
    suggested_solution = "Check available disk space and folder permissions, then try again."
    retryable = True


class ConfigError(AniRecError):
    code = "config_error"
    user_title = "Settings problem"
    safe_description = "One or more AniRec settings are missing or invalid."
    suggested_solution = "Review the application settings and save them again."


class CancelledError(AniRecError):
    code = "cancelled"
    user_title = "Operation cancelled"
    safe_description = "The operation was cancelled before it finished."
    suggested_solution = "Start the operation again when you are ready."


def presentable_error(error: Exception) -> UserFacingError:
    """Map any exception to a secret-redacted, traceback-free presentation model."""
    if isinstance(error, AniRecError):
        model = error.to_user_error()
        message = redact_secrets(str(error).strip())
        details = f"Error type: {error.__class__.__name__}\nCode: {model.code}"
        if message:
            details += f"\nMessage: {message[:500]}"
        return UserFacingError(
            code=model.code,
            title=model.title,
            description=model.description,
            solution=model.solution,
            retryable=model.retryable,
            technical_details=details,
        )
    model = AniRecError().to_user_error()
    return UserFacingError(
        code=model.code,
        title=model.title,
        description=model.description,
        solution=model.solution,
        retryable=model.retryable,
        technical_details=(
            f"Error type: {error.__class__.__name__}\n"
            "Unexpected details were written to the redacted application log."
        ),
    )
