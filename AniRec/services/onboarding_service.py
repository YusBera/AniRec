"""First-run completion state and setup readiness checks."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Callable

try:
    from ..errors import AniRecError, ConfigError
    from ..infrastructure.json_storage import JsonStore
    from ..infrastructure.paths import config_dir
    from .profile_service import ProfileService
    from .settings_service import SettingsService
    from .token_store import TokenStore
except ImportError:  # Compatibility with the legacy top-level import path.
    from errors import AniRecError, ConfigError
    from infrastructure.json_storage import JsonStore
    from infrastructure.paths import config_dir
    from services.profile_service import ProfileService
    from services.settings_service import SettingsService
    from services.token_store import TokenStore


ONBOARDING_SCHEMA_VERSION = 1


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OnboardingService:
    def __init__(
        self,
        *,
        settings: SettingsService,
        profiles: ProfileService,
        tokens: TokenStore,
        root_override: str | Path | None = None,
        store: JsonStore | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.settings = settings
        self.profiles = profiles
        self.tokens = tokens
        self._path = config_dir(root_override) / "onboarding.json"
        self._store = store or JsonStore()
        self._clock = clock

    @property
    def path(self) -> Path:
        return self._path

    def completion_flag(self) -> bool:
        if not self._path.exists():
            return False
        try:
            payload = self._store.read(self._path)
        except (OSError, TypeError, ValueError):
            return False
        return (
            payload.get("schema_version") == ONBOARDING_SCHEMA_VERSION
            and payload.get("completed") is True
        )

    def needs_setup(self) -> bool:
        if not self.completion_flag():
            return True
        settings = self.settings.load()
        try:
            self.settings.validate(settings)
            profile = self.profiles.active_profile()
            return profile is None
        except (AniRecError, ConfigError, OSError, TypeError, ValueError):
            return True

    def mark_complete(self) -> Path:
        payload = {
            "schema_version": ONBOARDING_SCHEMA_VERSION,
            "completed": True,
            "completed_at": self._clock().astimezone(timezone.utc).isoformat(),
        }
        return self._store.write(payload, self._path)
