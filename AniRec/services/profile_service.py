"""Profile model/path service with injectable application root and clock."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import unicodedata
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

try:
    from ..errors import InvalidResponseError, ProfileError
    from ..infrastructure.json_storage import JsonStore
    from ..infrastructure.mal_client import MALClient
    from ..infrastructure.paths import config_dir, profile_dir, profiles_dir
    from ..models import UserProfile
    from .token_store import TokenStore
except ImportError:  # Compatibility with the S01 top-level test import path.
    from errors import InvalidResponseError, ProfileError
    from infrastructure.json_storage import JsonStore
    from infrastructure.mal_client import MALClient
    from infrastructure.paths import config_dir, profile_dir, profiles_dir
    from models import UserProfile
    from services.token_store import TokenStore


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def safe_profile_id(username: str) -> str:
    normalized = unicodedata.normalize("NFKD", username)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_value).strip("-").lower()
    slug = slug[:32] or "profile"
    digest = hashlib.sha256(username.casefold().encode("utf-8")).hexdigest()[:12]
    return f"user-{slug}-{digest}"


def username_from_profile_reference(reference: str) -> str:
    """Return a MAL username from either plain text or an exact profile URL."""
    value = str(reference or "").strip()
    if not value:
        raise ProfileError("A MyAnimeList username or profile URL is required.")

    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme.casefold() != "https" or (parsed.hostname or "").casefold() not in {
            "myanimelist.net",
            "www.myanimelist.net",
        }:
            raise ProfileError("Use an https://myanimelist.net/profile/... URL.")
        parts = [unquote(part) for part in parsed.path.split("/") if part]
        if len(parts) != 2 or parts[0].casefold() != "profile":
            raise ProfileError("The MyAnimeList profile URL is invalid.")
        value = parts[1]

    if not re.fullmatch(r"[A-Za-z0-9_]{2,64}", value):
        raise ProfileError("The MyAnimeList username contains unsupported characters.")
    return value


def _default_open_path(path: Path) -> bool:
    if hasattr(os, "startfile"):
        os.startfile(str(path))
        return True
    return False


class ProfileService:
    def __init__(
        self,
        *,
        root_override: str | Path | None = None,
        clock: Callable[[], datetime] = _default_clock,
        mal_client: MALClient | None = None,
        store: JsonStore | None = None,
        token_store: TokenStore | None = None,
        open_path: Callable[[Path], bool] = _default_open_path,
    ) -> None:
        self._root_override = root_override
        self._clock = clock
        self._mal_client = mal_client
        self._store = store or JsonStore()
        self._tokens = token_store or TokenStore(root_override=root_override)
        self._open_path = open_path
        self._state_path = config_dir(root_override) / "profile_state.json"

    def create_profile(self, username: str, *, mal_user_id: int | None = None) -> UserProfile:
        username = username.strip()
        if not username:
            raise ValueError("A MyAnimeList username is required.")
        profile_id = f"mal-{int(mal_user_id)}" if mal_user_id is not None else safe_profile_id(username)
        directory = profile_dir(profile_id, self._root_override)
        return UserProfile(
            profile_id,
            username,
            mal_user_id=mal_user_id,
            output_dir=str(directory),
        )

    def validate_username(
        self,
        username: str,
        access_token: str,
        *,
        cancellation=None,
    ) -> UserProfile:
        username = username.strip()
        if not username:
            raise ProfileError("A MyAnimeList username is required.")
        if self._mal_client is None:
            raise ProfileError("MyAnimeList profile validation is not configured.")
        _raise_if_cancelled(cancellation)
        payload = self._mal_client.get_json(
            "https://api.myanimelist.net/v2/users/@me",
            params={"fields": "id,name"},
            access_token=access_token,
        )
        _raise_if_cancelled(cancellation)
        try:
            mal_user_id = int(payload["id"])
            normalized_username = str(payload["name"]).strip()
        except (KeyError, TypeError, ValueError) as error:
            raise InvalidResponseError("MyAnimeList profile response is invalid.") from error
        if mal_user_id <= 0 or not normalized_username:
            raise InvalidResponseError("MyAnimeList profile identity is invalid.")
        return self.create_profile(normalized_username, mal_user_id=mal_user_id)

    def validate_public_profile(
        self,
        reference: str,
        client_id: str,
        *,
        cancellation=None,
    ) -> UserProfile:
        """Validate a public MAL anime list without requiring account OAuth."""
        username = username_from_profile_reference(reference)
        if not str(client_id or "").strip():
            raise ProfileError("A MyAnimeList Client ID is required.")
        if self._mal_client is None:
            raise ProfileError("MyAnimeList profile validation is not configured.")
        _raise_if_cancelled(cancellation)
        payload = self._mal_client.get_json(
            f"https://api.myanimelist.net/v2/users/{quote(username, safe='')}/animelist",
            params={"status": "completed", "limit": 1},
            client_id=client_id,
            cancellation=cancellation,
        )
        if not isinstance(payload.get("data"), list):
            raise InvalidResponseError("MyAnimeList anime-list response is invalid.")
        _raise_if_cancelled(cancellation)
        return self.create_profile(username)

    def add_public_profile(
        self,
        reference: str,
        client_id: str,
        *,
        cancellation=None,
    ) -> UserProfile:
        profile = self.validate_public_profile(
            reference,
            client_id,
            cancellation=cancellation,
        )
        directory = self.directory(profile.profile_id, create=True)
        self._store.write(profile.to_dict(), directory / "profile.json")
        self.set_active(profile.profile_id)
        return profile

    def add_profile(
        self,
        username: str,
        access_token: str,
        *,
        cancellation=None,
    ) -> UserProfile:
        profile = self.validate_username(
            username,
            access_token,
            cancellation=cancellation,
        )
        _raise_if_cancelled(cancellation)
        self._validate_list_access(profile.username, access_token)
        _raise_if_cancelled(cancellation)
        directory = self.directory(profile.profile_id, create=True)
        self._store.write(profile.to_dict(), directory / "profile.json")
        if self.active_profile_id() is None:
            self.set_active(profile.profile_id)
        return profile

    def _validate_list_access(self, username: str, access_token: str) -> None:
        self._mal_client.get_json(
            f"https://api.myanimelist.net/v2/users/{quote(username, safe='')}/animelist",
            params={"status": "completed", "limit": 1},
            access_token=access_token,
        )

    def directory(self, profile_id: str, *, create: bool = False) -> Path:
        directory = profile_dir(profile_id, self._root_override)
        if create:
            directory.mkdir(parents=True, exist_ok=True)
        return directory

    def mark_synced(self, profile: UserProfile) -> UserProfile:
        timestamp = self._clock().astimezone(timezone.utc).isoformat()
        updated = replace(profile, last_sync=timestamp)
        directory = self.directory(profile.profile_id, create=True)
        self._store.write(updated.to_dict(), directory / "profile.json")
        return updated

    def get_profile(self, profile_id: str) -> UserProfile:
        path = self.directory(profile_id) / "profile.json"
        if not path.exists():
            raise ProfileError("The selected local profile does not exist.")
        try:
            return UserProfile.from_dict(self._store.read(path))
        except (OSError, TypeError, ValueError) as error:
            raise ProfileError("The selected local profile is invalid.") from error

    def list_profiles(self) -> tuple[UserProfile, ...]:
        root = profiles_dir(self._root_override)
        if not root.exists():
            return ()
        profiles = []
        for directory in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
            if not directory.is_dir():
                continue
            try:
                profiles.append(self.get_profile(directory.name))
            except ProfileError:
                continue
        return tuple(profiles)

    def set_active(self, profile_id: str) -> UserProfile:
        profile = self.get_profile(profile_id)
        self._store.write(
            {"schema_version": 1, "active_profile_id": profile_id},
            self._state_path,
        )
        return profile

    def active_profile_id(self) -> str | None:
        if not self._state_path.exists():
            return None
        try:
            payload = self._store.read(self._state_path)
        except (OSError, TypeError, ValueError):
            return None
        if payload.get("schema_version") != 1:
            return None
        value = payload.get("active_profile_id")
        try:
            self.directory(value)
        except (TypeError, ValueError):
            return None
        return value if (self.directory(value) / "profile.json").exists() else None

    def active_profile(self) -> UserProfile | None:
        profile_id = self.active_profile_id()
        return self.get_profile(profile_id) if profile_id else None

    def resolve_profile(self, username: str) -> UserProfile:
        """Prefer a persisted MAL-ID profile before creating a legacy username profile."""
        normalized = username.strip().casefold()
        active = self.active_profile()
        if active is not None and active.username.casefold() == normalized:
            return active
        for profile in self.list_profiles():
            if profile.username.casefold() == normalized:
                return profile
        return self.create_profile(username)

    def open_directory(self, profile_id: str) -> Path:
        directory = self.directory(profile_id)
        if not directory.is_dir():
            raise ProfileError("The selected local profile folder does not exist.")
        if not self._open_path(directory):
            raise ProfileError("The profile folder could not be opened.")
        return directory

    def deletion_target(self, profile_id: str) -> Path:
        directory = self.directory(profile_id)
        if not directory.is_dir():
            raise ProfileError("The selected local profile does not exist.")
        return directory

    def delete_profile(self, profile_id: str, *, confirmed_target: str | Path) -> Path:
        target = self.deletion_target(profile_id).resolve()
        if Path(confirmed_target).resolve() != target:
            raise ProfileError("Profile deletion confirmation target did not match.")
        root = profiles_dir(self._root_override).resolve()
        if target.parent != root:
            raise ProfileError("Profile deletion target escaped the application data root.")
        was_active = self.active_profile_id() == profile_id
        shutil.rmtree(target)
        self._tokens.delete(profile_id)
        if was_active:
            self._state_path.unlink(missing_ok=True)
        return target


def _raise_if_cancelled(cancellation) -> None:
    if cancellation is None:
        return
    checker = getattr(cancellation, "raise_if_cancelled", None)
    if callable(checker):
        checker()
