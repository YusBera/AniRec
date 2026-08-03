"""Small injectable MAL request used to verify Client ID configuration."""

from __future__ import annotations

from collections.abc import Callable, Mapping

import requests

try:
    from ..errors import ConfigError, InvalidResponseError, NetworkError
    from ..models import AppSettings
    from .settings_service import SettingsService
except ImportError:  # Compatibility with the legacy top-level import path.
    from errors import ConfigError, InvalidResponseError, NetworkError
    from models import AppSettings
    from services.settings_service import SettingsService


API_TEST_URL = "https://api.myanimelist.net/v2/anime/ranking"


class ApiConnectionService:
    def __init__(
        self,
        *,
        http_get: Callable | None = None,
        timeout_seconds: int = 15,
    ) -> None:
        self._http_get = http_get or requests.get
        self._timeout_seconds = timeout_seconds

    def test(self, settings: AppSettings) -> bool:
        SettingsService.validate(settings)
        try:
            response = self._http_get(
                API_TEST_URL,
                params={"ranking_type": "all", "limit": 1},
                headers={"X-MAL-CLIENT-ID": settings.client_id},
                timeout=self._timeout_seconds,
            )
        except requests.Timeout as error:
            raise NetworkError("MAL Client ID test timed out.") from error
        except requests.RequestException as error:
            raise NetworkError("MAL Client ID test request failed.") from error

        status = int(getattr(response, "status_code", 200))
        if status in {400, 401, 403}:
            raise ConfigError("MyAnimeList rejected the Client ID.")
        if status >= 400:
            raise NetworkError(f"MyAnimeList Client ID test returned HTTP {status}.")
        try:
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as error:
            raise NetworkError("MAL Client ID test failed.") from error
        except (TypeError, ValueError) as error:
            raise InvalidResponseError("MAL Client ID test returned invalid JSON.") from error
        if not isinstance(payload, Mapping) or not isinstance(payload.get("data"), list):
            raise InvalidResponseError("MAL Client ID test response was incomplete.")
        return True
