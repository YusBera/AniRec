from __future__ import annotations

import json

import pytest

from errors import AuthError, ConfigError
from infrastructure.json_storage import JsonStore
from models import AppSettings, PipelineSettings, TokenRecord
from services import SettingsService, TokenStore


def _valid_settings(secret="fixture-client-secret"):
    return AppSettings(
        client_id="fixture-client-id",
        redirect_uri="http://localhost:8080/callback",
        client_secret=secret,
        active_profile_id="fixture-profile",
        pipeline=PipelineSettings(seed=42),
    )


def test_settings_round_trip_is_schema_versioned_and_outside_repo(system_temp_dir):
    service = SettingsService(root_override=system_temp_dir / "app-data")
    settings = _valid_settings()
    path = service.save(settings)
    loaded = service.load()
    assert path == (system_temp_dir / "app-data").resolve() / "config" / "settings.json"
    assert loaded == settings
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["pipeline"]["schema_version"] == 1


def test_extended_preferences_round_trip_and_diagnostics_exclude_secret(system_temp_dir):
    service = SettingsService(root_override=system_temp_dir)
    settings = AppSettings(
        client_id="fixture-client-id",
        client_secret="must-not-appear-in-diagnostics",
        pipeline=PipelineSettings(
            top_anime_limit=900,
            recommendation_count=25,
            candidate_pool_size=300,
            minimum_mean_score=7.0,
            seed=99,
        ),
        default_recommendation_sort="alphabetical",
        include_hidden_recommendations=True,
        theme="dark",
        font_scale=1.25,
        show_covers=False,
    )
    service.save(settings)
    assert service.load() == settings
    diagnostic = repr(settings.to_diagnostic_dict())
    assert "must-not-appear-in-diagnostics" not in diagnostic
    assert "alphabetical" in diagnostic


def test_missing_corrupt_and_old_settings_fall_back_without_crashing(system_temp_dir):
    service = SettingsService(root_override=system_temp_dir / "app-data")
    assert service.load() == AppSettings()
    assert service.last_error is None
    service.path.parent.mkdir(parents=True, exist_ok=True)
    service.path.write_text("{broken", encoding="utf-8")
    assert service.load() == AppSettings()
    assert isinstance(service.last_error, ConfigError)
    service.path.write_text('{"schema_version": 0}', encoding="utf-8")
    assert service.load() == AppSettings()
    assert isinstance(service.last_error, ConfigError)


@pytest.mark.parametrize(
    "settings",
    [
        AppSettings(client_id=""),
        AppSettings(client_id="fixture", redirect_uri="https://localhost:8080/callback"),
        AppSettings(client_id="fixture", redirect_uri="http://example.com/callback"),
        AppSettings(client_id="fixture", redirect_uri="http://localhost:8080/wrong"),
        AppSettings(client_id="fixture", redirect_uri="http://localhost:8080/callback?code=x"),
    ],
)
def test_settings_validation_rejects_missing_or_unsafe_api_values(system_temp_dir, settings):
    with pytest.raises(ConfigError):
        SettingsService(root_override=system_temp_dir).save(settings)


def test_client_secret_is_masked_and_absent_from_diagnostics():
    settings = _valid_settings(secret="fixture-secret-must-not-export")
    diagnostic = settings.to_diagnostic_dict()
    assert settings.masked_client_secret == "••••••"
    assert "fixture-secret-must-not-export" not in repr(settings)
    assert "fixture-secret-must-not-export" not in repr(diagnostic)
    assert diagnostic["client_secret_configured"] is True


def test_settings_atomic_write_preserves_previous_file_on_replace_failure(system_temp_dir):
    root = system_temp_dir / "app-data"
    valid_service = SettingsService(root_override=root)
    valid_service.save(_valid_settings(secret="old-secret"))
    before = valid_service.path.read_text(encoding="utf-8")

    def fail_replace(_source, _destination):
        raise OSError("fixture replace failure")

    failing_service = SettingsService(root_override=root, store=JsonStore(replace_func=fail_replace))
    with pytest.raises(OSError, match="fixture replace failure"):
        failing_service.save(_valid_settings(secret="new-secret"))
    assert valid_service.path.read_text(encoding="utf-8") == before
    assert list(valid_service.path.parent.glob("*.tmp")) == []


def test_token_store_is_profile_isolated_and_schema_versioned(system_temp_dir):
    store = TokenStore(root_override=system_temp_dir / "app-data")
    first = TokenRecord("fake-access-one", "fake-refresh-one", expires_at=1000)
    second = TokenRecord("fake-access-two", expires_at=2000)
    first_path = store.save("profile-one", first)
    second_path = store.save("profile-two", second)
    assert first_path.parent.name == "tokens"
    assert first_path != second_path
    assert store.load("profile-one") == first
    assert store.load("profile-two") == second
    store.delete("profile-one")
    assert store.load("profile-one") is None
    assert store.load("profile-two") == second


def test_token_store_rejects_traversal_and_corrupt_json(system_temp_dir):
    store = TokenStore(root_override=system_temp_dir / "app-data")
    with pytest.raises(ValueError):
        store.path_for("../escape")
    path = store.path_for("fixture-profile")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(AuthError):
        store.load("fixture-profile")
