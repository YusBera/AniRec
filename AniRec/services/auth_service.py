"""Terminal-independent MyAnimeList OAuth lifecycle service."""

from __future__ import annotations

import secrets
import time
import webbrowser
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import urlencode

import requests

try:
    from ..errors import AuthError, InvalidResponseError, NetworkError
    from ..infrastructure.oauth_callback import OAuthCallbackServer
    from ..models import AppSettings, TokenRecord
    from .settings_service import SettingsService
    from .token_store import TokenStore
except ImportError:  # Compatibility with the S01 top-level import path.
    from errors import AuthError, InvalidResponseError, NetworkError
    from infrastructure.oauth_callback import OAuthCallbackServer
    from models import AppSettings, TokenRecord
    from services.settings_service import SettingsService
    from services.token_store import TokenStore


AUTH_BASE_URL = "https://myanimelist.net/v1/oauth2"
OAUTH_STATUS_OPENING_BROWSER = "oauth_opening_browser"
OAUTH_STATUS_WAITING_APPROVAL = "oauth_waiting_approval"
OAUTH_STATUS_AUTHORIZATION_COMPLETE = "oauth_authorization_complete"
OAUTH_STATUS_VALIDATING_TOKEN = "oauth_validating_token"
OAUTH_STATUS_SUCCESS = "oauth_success"


@dataclass(frozen=True)
class OAuthSession:
    authorization_url: str = field(repr=False)
    state: str = field(repr=False)
    code_verifier: str = field(repr=False)
    code_challenge: str = field(repr=False)


class AuthService:
    def __init__(
        self,
        *,
        token_store: TokenStore,
        callback_server: OAuthCallbackServer | None = None,
        http_post: Callable | None = None,
        browser_open: Callable[[str], bool] = webbrowser.open,
        clock: Callable[[], float] = time.time,
        random_token: Callable[[int], str] = secrets.token_urlsafe,
        timeout_seconds: int = 15,
    ) -> None:
        self._tokens = token_store
        self._callback = callback_server or OAuthCallbackServer()
        self._http_post = http_post or requests.post
        self._browser_open = browser_open
        self._clock = clock
        self._random_token = random_token
        self._timeout_seconds = timeout_seconds

    def create_session(self, settings: AppSettings) -> OAuthSession:
        SettingsService.validate(settings)
        state = self._random_token(32)
        code_verifier = self._random_token(64)
        # MyAnimeList currently supports only the ``plain`` PKCE method.  The
        # verifier is still generated independently for every authorization
        # attempt and is checked again when the code is exchanged for a token.
        code_challenge = code_verifier
        authorization_params = {
            "response_type": "code",
            "client_id": settings.client_id,
            "redirect_uri": settings.redirect_uri,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "plain",
        }
        authorization_url = (
            f"{AUTH_BASE_URL}/authorize?{urlencode(authorization_params)}"
        )
        return OAuthSession(authorization_url, state, code_verifier, code_challenge)

    def authorize(
        self,
        profile_id: str,
        settings: AppSettings,
        *,
        callback_timeout_seconds: float = 180,
        cancellation=None,
        status_callback: Callable[[str], None] | None = None,
    ) -> TokenRecord:
        session = self.create_session(settings)
        _emit_status(status_callback, OAUTH_STATUS_OPENING_BROWSER)
        if not self._browser_open(session.authorization_url):
            raise AuthError("The system browser could not be opened.")
        _emit_status(status_callback, OAUTH_STATUS_WAITING_APPROVAL)
        code = self._callback.wait_for_code(
            settings.redirect_uri,
            session.state,
            timeout_seconds=callback_timeout_seconds,
            cancellation=cancellation,
        )
        _emit_status(status_callback, OAUTH_STATUS_AUTHORIZATION_COMPLETE)
        _emit_status(status_callback, OAUTH_STATUS_VALIDATING_TOKEN)
        token = self._exchange_code(code, session.code_verifier, settings)
        self._tokens.save(profile_id, token)
        _emit_status(status_callback, OAUTH_STATUS_SUCCESS)
        return token

    def get_access_token(
        self,
        profile_id: str,
        settings: AppSettings,
        *,
        interactive: bool = False,
        callback_timeout_seconds: float = 180,
        cancellation=None,
    ) -> str:
        token = self._tokens.load(profile_id)
        if token and token.expires_at > int(self._clock()):
            return token.access_token
        if token and token.refresh_token:
            try:
                refreshed = self.refresh(profile_id, settings, token.refresh_token)
                return refreshed.access_token
            except AuthError:
                if not interactive:
                    raise
        if interactive:
            return self.authorize(
                profile_id,
                settings,
                callback_timeout_seconds=callback_timeout_seconds,
                cancellation=cancellation,
            ).access_token
        raise AuthError("No valid OAuth token is available.")

    def refresh(
        self,
        profile_id: str,
        settings: AppSettings,
        refresh_token: str,
    ) -> TokenRecord:
        SettingsService.validate(settings)
        data = {
            "client_id": settings.client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        if settings.client_secret:
            data["client_secret"] = settings.client_secret
        token = self._request_token(data, fallback_refresh_token=refresh_token)
        self._tokens.save(profile_id, token)
        return token

    def _exchange_code(
        self,
        code: str,
        code_verifier: str,
        settings: AppSettings,
    ) -> TokenRecord:
        data = {
            "client_id": settings.client_id,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.redirect_uri,
            "code_verifier": code_verifier,
        }
        if settings.client_secret:
            data["client_secret"] = settings.client_secret
        return self._request_token(data)

    def _request_token(
        self,
        data: dict,
        *,
        fallback_refresh_token: str | None = None,
    ) -> TokenRecord:
        try:
            response = self._http_post(
                f"{AUTH_BASE_URL}/token",
                data=data,
                timeout=self._timeout_seconds,
            )
        except requests.Timeout as error:
            raise NetworkError("OAuth token request timed out.") from error
        except requests.ConnectionError as error:
            raise NetworkError("OAuth token endpoint could not be reached.") from error
        except requests.RequestException as error:
            raise NetworkError("OAuth token request failed.") from error
        status = int(getattr(response, "status_code", 200))
        if status in {400, 401, 403}:
            raise AuthError("MyAnimeList rejected the OAuth token request.")
        if status >= 500:
            raise NetworkError("MyAnimeList OAuth service is temporarily unavailable.")
        try:
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as error:
            raise AuthError("OAuth token request was rejected.") from error
        except (TypeError, ValueError) as error:
            raise InvalidResponseError("OAuth token response was invalid.") from error
        if not isinstance(payload, dict) or not payload.get("access_token"):
            raise InvalidResponseError("OAuth token response did not contain an access token.")
        try:
            expires_in = max(int(payload.get("expires_in", 0)), 0)
        except (TypeError, ValueError) as error:
            raise InvalidResponseError("OAuth token expiration was invalid.") from error
        return TokenRecord(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token") or fallback_refresh_token,
            expires_at=int(self._clock()) + max(expires_in - 60, 0),
            token_type=payload.get("token_type") or "Bearer",
            scope=payload.get("scope"),
        )

def _emit_status(callback: Callable[[str], None] | None, status: str) -> None:
    if callback is not None:
        callback(status)
