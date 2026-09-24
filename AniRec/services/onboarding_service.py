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

    def import_public_mal_profile(self, reference: str, *, cancellation=None):
        """Start with a public MyAnimeList list, read by username (D-020).

        The Client ID is this installation's own setting; the visitor never
        supplies one. The list is validated before anything is written, the
        profile becomes the active one, and setup is marked complete. A
        failure to read the list leaves no profile and no completion flag.
        """
        client_id = (self.settings.load().client_id or "").strip()
        if not client_id:
            raise ConfigError("MyAnimeList import is not set up for this installation.")
        profile = self.profiles.validate_public_profile(reference, client_id, cancellation=cancellation)
        # A reader AniRec already knows keeps their saved profile, whether
        # the desktop connected it (mal-<id>) or an earlier import made it:
        # nothing is rewritten and no second profile is created.
        known = next(
            (saved for saved in self.profiles.list_profiles()
             if saved.username.casefold() == profile.username.casefold()),
            None,
        )
        # The flag first: if it cannot be written, no profile is left behind;
        # if the profile then cannot be written, no profile is active, so
        # setup is still needed.
        self.mark_complete()
        if known is not None:
            return self.profiles.set_active(known.profile_id)
        return self.profiles.save_and_activate(profile)

    def mark_complete(self) -> Path:
        payload = {
            "schema_version": ONBOARDING_SCHEMA_VERSION,
            "completed": True,
            "completed_at": self._clock().astimezone(timezone.utc).isoformat(),
        }
        return self._store.write(payload, self._path)
