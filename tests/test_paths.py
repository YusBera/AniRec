from __future__ import annotations

import sys

import pytest

from infrastructure.paths import (
    app_paths,
    profile_dir,
    resource_path,
)


def test_app_paths_use_injected_root_and_create_expected_directories(system_temp_dir):
    root = system_temp_dir / "isolated-app-data"
    paths = app_paths(root).ensure_exists()

    assert paths.root == root.resolve()
    assert paths.config == paths.root / "config"
    assert paths.profiles == paths.root / "profiles"
    assert paths.cache == paths.root / "cache"
    assert paths.logs == paths.root / "logs"
    assert paths.tokens == paths.root / "tokens"
    assert all(
        directory.is_dir()
        for directory in (
            paths.root,
            paths.config,
            paths.profiles,
            paths.cache,
            paths.logs,
            paths.tokens,
        )
    )


@pytest.mark.parametrize(
    "unsafe_id",
    ["", ".", "..", "../escape", "..\\escape", "nested/profile", "C:\\escape"],
)
def test_profile_dir_rejects_traversal_and_nested_paths(system_temp_dir, unsafe_id):
    with pytest.raises(ValueError, match="Profile"):
        profile_dir(unsafe_id, root_override=system_temp_dir / "app-data")


def test_profile_dir_returns_direct_child(system_temp_dir):
    root = system_temp_dir / "app-data"
    result = profile_dir("fixture-profile_1", root_override=root)
    assert result == root.resolve() / "profiles" / "fixture-profile_1"


def test_resource_path_supports_source_override_and_rejects_escape(system_temp_dir):
    base = system_temp_dir / "resources"
    expected = base.resolve() / "icons" / "app.png"
    assert resource_path("icons/app.png", base_override=base) == expected

    with pytest.raises(ValueError, match="resource root"):
        resource_path("../secret.txt", base_override=base)
    with pytest.raises(ValueError, match="relative"):
        resource_path(system_temp_dir / "absolute.txt", base_override=base)


def test_resource_path_uses_pyinstaller_meipass(monkeypatch, system_temp_dir):
    bundle_root = system_temp_dir / "bundle"
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle_root), raising=False)
    assert resource_path("resources/theme.qss") == (
        bundle_root.resolve() / "resources" / "theme.qss"
    )
