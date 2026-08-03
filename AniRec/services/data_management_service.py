"""Constrained local cache, cover, log, and application-data management."""

from __future__ import annotations

import shutil
import os
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

try:
    from ..errors import StorageError
    from ..infrastructure.paths import app_paths
except ImportError:  # Compatibility with legacy top-level imports.
    from errors import StorageError
    from infrastructure.paths import app_paths


class DataDeletionScope(str, Enum):
    CACHE = "cache"
    COVERS = "covers"
    ALL_LOCAL_DATA = "all-local-data"


@dataclass(frozen=True)
class DataDeletionPlan:
    scope: DataDeletionScope
    title: str
    target: Path
    description: str


@dataclass(frozen=True)
class DataDeletionReceipt:
    scope: DataDeletionScope
    target: Path
    removed_entries: int


class DataManagementService:
    def __init__(
        self,
        *,
        root_override: str | Path | None = None,
        path_opener: Callable[[Path], bool] | None = None,
    ) -> None:
        self.paths = app_paths(root_override)
        self._path_opener = path_opener or _default_open_path

    def plan(self, scope: DataDeletionScope | str) -> DataDeletionPlan:
        resolved = DataDeletionScope(scope)
        if resolved is DataDeletionScope.CACHE:
            return DataDeletionPlan(
                resolved,
                "Clear application cache?",
                self.paths.cache,
                "Deletes temporary cached data but preserves downloaded anime covers.",
            )
        if resolved is DataDeletionScope.COVERS:
            return DataDeletionPlan(
                resolved,
                "Clear downloaded covers?",
                self.paths.cache / "covers",
                "Deletes downloaded anime artwork. AniRec will use placeholders and may download covers again.",
            )
        return DataDeletionPlan(
            resolved,
            "Delete all local AniRec data?",
            self.paths.root,
            "Deletes settings, profiles, OAuth tokens, generated profile files, cache, covers, and logs.",
        )

    def delete(
        self,
        scope: DataDeletionScope | str,
        *,
        confirmed_target: str | Path,
    ) -> DataDeletionReceipt:
        plan = self.plan(scope)
        target = self._validated_target(plan)
        if Path(confirmed_target).resolve() != target:
            raise StorageError("Deletion confirmation target did not match the requested scope.")
        if plan.scope is DataDeletionScope.CACHE:
            removed = self._clear_directory(target, preserve_names={"covers"})
        elif plan.scope is DataDeletionScope.COVERS:
            removed = self._remove_target(target)
        else:
            removed = self._clear_directory(target)
        return DataDeletionReceipt(plan.scope, target, removed)

    def open_logs(self) -> Path:
        target = self.paths.logs.resolve()
        self._ensure_within_root(target)
        target.mkdir(parents=True, exist_ok=True)
        if not self._path_opener(target):
            raise StorageError("The log directory could not be opened.")
        return target

    def _validated_target(self, plan: DataDeletionPlan) -> Path:
        target = plan.target.resolve()
        root = self.paths.root.resolve()
        self._ensure_within_root(target)
        if root == Path(root.anchor) or root == Path.home().resolve():
            raise StorageError("The configured application data root is too broad to delete.")
        if plan.scope is DataDeletionScope.ALL_LOCAL_DATA and target != root:
            raise StorageError("All-data deletion target did not match the application data root.")
        return target

    def _ensure_within_root(self, target: Path) -> None:
        root = self.paths.root.resolve()
        if target != root and root not in target.parents:
            raise StorageError("Data management target escaped the AniRec application data root.")

    @classmethod
    def _clear_directory(
        cls, target: Path, *, preserve_names: set[str] | None = None
    ) -> int:
        if not target.exists():
            return 0
        preserve = preserve_names or set()
        removed = 0
        for child in tuple(target.iterdir()):
            if child.name in preserve:
                continue
            removed += cls._remove_target(child)
        return removed

    @staticmethod
    def _remove_target(target: Path) -> int:
        if not target.exists() and not target.is_symlink():
            return 0
        if target.is_symlink() or target.is_file():
            target.unlink()
        else:
            shutil.rmtree(target)
        return 1


def _default_open_path(path: Path) -> bool:
    if hasattr(os, "startfile"):
        os.startfile(str(path))
        return True
    return False
