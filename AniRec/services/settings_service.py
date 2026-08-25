"""Schema-versioned AniRec settings with validation and safe fallback."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

try:
    from ..errors import ConfigError
    from ..infrastructure.json_storage import JsonStore
    from ..infrastructure.paths import config_dir
    from ..models import (
        APP_THEME_VALUES,
        RECOMMENDATION_SORT_VALUES,
        RECOMMENDATION_VIEW_MODES,
        AppSettings,
    )
except ImportError:  # Compatibility with the S01 top-level import path.
    from errors import ConfigError
    from infrastructure.json_storage import JsonStore
    from infrastructure.paths import config_dir
    from models import (
        APP_THEME_VALUES,
        RECOMMENDATION_SORT_VALUES,
        RECOMMENDATION_VIEW_MODES,
        AppSettings,
    )


class SettingsService:
    def __init__(
        self,
        *,
        root_override: str | Path | None = None,
        store: JsonStore | None = None,
    ) -> None:
        self._path = config_dir(root_override) / "settings.json"
        self._store = store or JsonStore()
        self.last_error: ConfigError | None = None

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> AppSettings:
        self.last_error = None
        if not self._path.exists():
            return AppSettings()
        try:
            return AppSettings.from_storage_dict(self._store.read(self._path))
        except (OSError, TypeError, ValueError) as error:
            self.last_error = ConfigError("Settings could not be loaded safely.")
            self.last_error.__cause__ = error
            return AppSettings()

    def save(self, settings: AppSettings) -> Path:
        self.validate(settings)
        return self._store.write(settings.to_storage_dict(), self._path)

    def save_preferences(self, settings: AppSettings) -> Path:
        """Persist appearance and layout choices without demanding credentials.

        ``validate`` refuses settings that carry no Client ID, which is right
        for an API configuration and wrong for a preference: it meant a theme
        or a layout could not be remembered until an account existed, so
        someone still looking around lost every choice they made.
        """
        self.validate_preferences(settings)
        return self._store.write(settings.to_storage_dict(), self._path)

    @staticmethod
    def validate(settings: AppSettings) -> None:
        if not settings.client_id:
            raise ConfigError("MAL client ID is required.")
        SettingsService.validate_preferences(settings)
        parsed = urlparse(settings.redirect_uri)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"localhost", "127.0.0.1"}
            or parsed.path != "/callback"
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ConfigError("Redirect URI must be a local HTTP /callback URL.")

    @staticmethod
    def validate_preferences(settings: AppSettings) -> None:
        """Check the parts of the settings that are not credentials."""
        if settings.default_recommendation_sort not in RECOMMENDATION_SORT_VALUES:
            raise ConfigError("Default recommendation sort is invalid.")
        if settings.theme not in APP_THEME_VALUES:
            raise ConfigError("Theme preference is invalid.")
        if settings.recommendation_view_mode not in RECOMMENDATION_VIEW_MODES:
            raise ConfigError("Recommendation view mode is invalid.")
        if not 0.80 <= settings.font_scale <= 1.40:
            raise ConfigError("Font scale must be between 0.80 and 1.40.")
