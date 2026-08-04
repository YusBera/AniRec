from __future__ import annotations

from pathlib import Path

import pytest

from AniRec.errors import StorageError
from AniRec.services import DataDeletionScope, DataManagementService


def populate(root: Path):
    cache = root / "cache"
    covers = cache / "covers"
    logs = root / "logs"
    profiles = root / "profiles" / "profile-a"
    tokens = root / "tokens"
    config = root / "config"
    for directory in (covers, logs, profiles, tokens, config):
        directory.mkdir(parents=True, exist_ok=True)
    (cache / "general.cache").write_text("cache", encoding="utf-8")
    (cache / "nested").mkdir()
    (cache / "nested" / "entry.bin").write_text("cache", encoding="utf-8")
    (covers / "cover.img").write_text("cover", encoding="utf-8")
    (logs / "anirec.log").write_text("log", encoding="utf-8")
    (profiles / "profile.json").write_text("{}", encoding="utf-8")
    (tokens / "profile-a.json").write_text("{}", encoding="utf-8")
    (config / "settings.json").write_text("{}", encoding="utf-8")


def test_plans_describe_exact_in_root_targets_and_scopes(system_temp_dir):
    service = DataManagementService(root_override=system_temp_dir)
    cache = service.plan(DataDeletionScope.CACHE)
    covers = service.plan(DataDeletionScope.COVERS)
    all_data = service.plan(DataDeletionScope.ALL_LOCAL_DATA)

    assert cache.target == system_temp_dir.resolve() / "cache"
    assert "preserves downloaded anime covers" in cache.description
    assert covers.target == system_temp_dir.resolve() / "cache" / "covers"
    assert "artwork" in covers.description
    assert all_data.target == system_temp_dir.resolve()
    assert "OAuth tokens" in all_data.description


def test_cache_and_cover_deletion_are_separate_and_require_exact_confirmation(
    system_temp_dir,
):
    populate(system_temp_dir)
    service = DataManagementService(root_override=system_temp_dir)
    cache_plan = service.plan(DataDeletionScope.CACHE)

    with pytest.raises(StorageError):
        service.delete(DataDeletionScope.CACHE, confirmed_target=system_temp_dir)
    assert (system_temp_dir / "cache" / "general.cache").exists()

    receipt = service.delete(DataDeletionScope.CACHE, confirmed_target=cache_plan.target)
    assert receipt.removed_entries == 2
    assert not (system_temp_dir / "cache" / "general.cache").exists()
    assert (system_temp_dir / "cache" / "covers" / "cover.img").exists()

    cover_plan = service.plan(DataDeletionScope.COVERS)
    service.delete(DataDeletionScope.COVERS, confirmed_target=cover_plan.target)
    assert not cover_plan.target.exists()


def test_all_local_data_deletion_preserves_outside_sentinel(system_temp_dir):
    populate(system_temp_dir)
    sentinel = system_temp_dir.parent / "anirec-outside-sentinel.txt"
    sentinel.write_text("must survive", encoding="utf-8")
    service = DataManagementService(root_override=system_temp_dir)
    plan = service.plan(DataDeletionScope.ALL_LOCAL_DATA)

    receipt = service.delete(plan.scope, confirmed_target=plan.target)

    assert receipt.removed_entries == 5
    assert system_temp_dir.exists()
    assert list(system_temp_dir.iterdir()) == []
    assert sentinel.read_text(encoding="utf-8") == "must survive"


def test_broad_root_and_outside_targets_are_rejected_without_mutation(system_temp_dir):
    broad = DataManagementService(root_override=Path(system_temp_dir.anchor))
    plan = broad.plan(DataDeletionScope.ALL_LOCAL_DATA)
    with pytest.raises(StorageError):
        broad.delete(plan.scope, confirmed_target=plan.target)

    service = DataManagementService(root_override=system_temp_dir)
    outside = system_temp_dir.parent / "outside"
    with pytest.raises(StorageError):
        service._ensure_within_root(outside.resolve())


def test_log_folder_is_created_and_opened_through_injected_boundary(system_temp_dir):
    opened = []
    service = DataManagementService(
        root_override=system_temp_dir,
        path_opener=lambda path: not opened.append(path),
    )
    target = service.open_logs()
    assert target == system_temp_dir.resolve() / "logs"
    assert target.is_dir()
    assert opened == [target]
