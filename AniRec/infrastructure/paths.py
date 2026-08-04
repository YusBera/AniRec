"""Central, testable filesystem path resolution for AniRec."""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path


APP_DIRECTORY_NAME = "AniRec"
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_PROFILE_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")


@dataclass(frozen=True)
class AppPaths:
    root: Path
    config: Path
    profiles: Path
    cache: Path
    logs: Path
    tokens: Path

    def ensure_exists(self) -> "AppPaths":
        for directory in (
            self.root,
            self.config,
            self.profiles,
            self.cache,
            self.logs,
            self.tokens,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        return self


def app_data_dir(root_override: str | Path | None = None) -> Path:
    """Return the AniRec application data root without creating it."""
    if root_override is not None:
        return Path(root_override).expanduser().resolve()

    roaming_root = os.environ.get("APPDATA")
    if roaming_root:
        return (Path(roaming_root).expanduser() / APP_DIRECTORY_NAME).resolve()

    return (Path.home() / "AppData" / "Roaming" / APP_DIRECTORY_NAME).resolve()


def app_paths(root_override: str | Path | None = None) -> AppPaths:
    root = app_data_dir(root_override)
    return AppPaths(
        root=root,
        config=root / "config",
        profiles=root / "profiles",
        cache=root / "cache",
        logs=root / "logs",
        tokens=root / "tokens",
    )


def config_dir(root_override: str | Path | None = None) -> Path:
    return app_paths(root_override).config


def profiles_dir(root_override: str | Path | None = None) -> Path:
    return app_paths(root_override).profiles


def cache_dir(root_override: str | Path | None = None) -> Path:
    return app_paths(root_override).cache


def logs_dir(root_override: str | Path | None = None) -> Path:
    return app_paths(root_override).logs


def tokens_dir(root_override: str | Path | None = None) -> Path:
    return app_paths(root_override).tokens


def profile_dir(profile_id: str, root_override: str | Path | None = None) -> Path:
    """Return one direct profile child and reject traversal or nested paths."""
    return _validated_direct_child(profiles_dir(root_override), profile_id, "Profile")


def token_file(profile_id: str, root_override: str | Path | None = None) -> Path:
    """Return a profile-scoped token file below the application token root."""
    return _validated_direct_child(tokens_dir(root_override), profile_id, "Token").with_suffix(
        ".json"
    )


def _validated_direct_child(parent: Path, child_id: str, label: str) -> Path:
    if not _PROFILE_ID_PATTERN.fullmatch(child_id) or child_id in {".", ".."}:
        raise ValueError(f"{label} ID contains unsupported or unsafe characters.")
    resolved_parent = parent.resolve()
    candidate = (resolved_parent / child_id).resolve()
    if candidate.parent != resolved_parent:
        raise ValueError(f"{label} path must stay inside the AniRec data directory.")
    return candidate


def resource_path(
    relative_path: str | Path,
    base_override: str | Path | None = None,
) -> Path:
    """Resolve a packaged/source resource while preventing path traversal."""
    relative = Path(relative_path)
    if relative.is_absolute():
        raise ValueError("Resource path must be relative.")

    if base_override is not None:
        base = Path(base_override).expanduser().resolve()
    elif getattr(sys, "_MEIPASS", None):
        base = Path(sys._MEIPASS).resolve()
    else:
        base = PACKAGE_ROOT

    candidate = (base / relative).resolve()
    if candidate != base and base not in candidate.parents:
        raise ValueError("Resource path must stay inside the application resource root.")
    return candidate
