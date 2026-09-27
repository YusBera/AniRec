"""First-run completion state and setup readiness checks."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Callable

try:
    from ..errors import AniRecError, ConfigError
    from ..infrastructure.json_storage import JsonStore
    from ..infrastructure.paths import config_dir
    from ..models import UserProfile
    from .profile_service import ProfileService
    from .settings_service import SettingsService
    from .token_store import TokenStore
except ImportError:  # Compatibility with the legacy top-level import path.
    from errors import AniRecError, ConfigError
    from infrastructure.json_storage import JsonStore
    from infrastructure.paths import config_dir
    from models import UserProfile
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

    def read_public_mal_list(self, reference: str, *, cancellation=None) -> str:
        """Check that a public MyAnimeList list can be read; return its username.

        Nothing is written. The Client ID is this installation's own setting;
        the visitor never supplies one (D-020).
        """
        client_id = (self.settings.load().client_id or "").strip()
        if not client_id:
            raise ConfigError("MyAnimeList import is not set up for this installation.")
        return self.profiles.validate_public_profile(reference, client_id, cancellation=cancellation).username

    def import_for_account(self, accounts, account_id: str, username: str) -> UserProfile:
        """Make ``username``'s list an import of this account, and its active one.

        An account that already imported this username keeps that import and
        its saved decisions. Nothing is looked up across accounts: another
        reader's import of the same list is theirs alone (D-021). The import
        directory is named by the server, never after the MyAnimeList user.
        """
        from .account_service import new_import_id

        for profile_id in accounts.owned_profile_ids(account_id):
            try:
                saved = self.profiles.get_profile(profile_id)
            except (AniRecError, OSError, TypeError, ValueError):
                continue
            if saved.username.casefold() == username.casefold():
                accounts.set_active(account_id, profile_id)
                return saved
        profile_id = new_import_id()
        directory = self.profiles.directory(profile_id, create=True)
        profile = UserProfile(profile_id, username, output_dir=str(directory))
        try:
            self.profiles.save_profile(profile)
            accounts.add_import(account_id, profile_id)
        except BaseException:
            # Never leave an import directory that no account owns.
            shutil.rmtree(directory, ignore_errors=True)
            raise
        return profile

    def mark_complete(self) -> Path:
        payload = {
            "schema_version": ONBOARDING_SCHEMA_VERSION,
            "completed": True,
            "completed_at": self._clock().astimezone(timezone.utc).isoformat(),
        }
        return self._store.write(payload, self._path)
