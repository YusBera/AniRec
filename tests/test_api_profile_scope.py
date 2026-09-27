"""Request fields cannot select a different local profile at the HTTP boundary."""

import json

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from AniRec.api import create_app  # noqa: E402
from AniRec.services import RecommendationStateService  # noqa: E402
from account_helpers import sign_in_reader  # noqa: E402


def _local_profile(app, username):
    profiles = app.state.container.profiles
    profile = profiles.create_profile(username)
    directory = profiles.directory(profile.profile_id, create=True)
    (directory / "profile.json").write_text(json.dumps(profile.to_dict()), encoding="utf-8")
    return profile


@pytest.mark.parametrize("action", ["hidden", "watch_later", "sentiment"])
def test_feedback_cannot_write_another_profile(tmp_path, action):
    app = create_app(root_override=str(tmp_path))
    active = _local_profile(app, "active")
    other = _local_profile(app, "other")
    state = RecommendationStateService(root_override=tmp_path)
    payload = {"profile_id": other.profile_id, "mal_id": 42, "action": action}
    if action == "sentiment":
        payload["sentiment"] = "liked"
    with TestClient(app) as client:
        sign_in_reader(client, active.profile_id)
        response = client.post("/api/discover/feedback", json=payload)
    assert response.status_code == 409
    assert not state.path(other.profile_id).exists()


def test_feedback_cannot_create_state_without_an_active_profile(tmp_path):
    app = create_app(root_override=str(tmp_path))
    with TestClient(app) as client:
        response = client.post("/api/discover/feedback", json={
            "profile_id": "invented", "mal_id": 42, "action": "hidden",
        })
    assert response.status_code == 409
    assert not (tmp_path / "profiles" / "invented").exists()


@pytest.mark.parametrize("override", [
    {"profile_id": "other"},
    {"username": "other"},
    {"profile_id": "other", "username": "active"},
])
def test_operation_rejects_request_scope_that_differs_from_active(tmp_path, override):
    app = create_app(root_override=str(tmp_path))
    active = _local_profile(app, "active")
    other = _local_profile(app, "other")
    payload = {**override}
    if payload.get("profile_id") == "other":
        payload["profile_id"] = other.profile_id
    with TestClient(app) as client:
        sign_in_reader(client, active.profile_id)
        response = client.post("/api/operations/recommendation", json=payload)
        operations = client.get("/api/operations").json()["operations"]
    assert response.status_code == 409
    assert operations == []


def test_operation_cannot_use_request_fields_when_no_profile_is_active(tmp_path):
    app = create_app(root_override=str(tmp_path))
    with TestClient(app) as client:
        response = client.post("/api/operations/recommendation", json={
            "profile_id": "invented", "username": "someone",
        })
    assert response.status_code == 409
    assert not (tmp_path / "profiles" / "invented").exists()


def test_matching_hints_allow_operation_and_lookup_target_stays_independent(tmp_path, monkeypatch):
    app = create_app(root_override=str(tmp_path))
    active = _local_profile(app, "active")
    seen = []
    monkeypatch.setattr(
        app.state.container.profiles, "validate_public_profile",
        lambda target, _client_id, **_kwargs: seen.append(target) or active,
    )
    with TestClient(app) as client:
        sign_in_reader(client, active.profile_id)
        response = client.post("/api/operations/profile-lookup", json={
            "profile_id": active.profile_id,
            "username": active.username,
            "target": "unrelated-mal-user",
        })
        assert response.status_code == 202
        app.state.operations.shutdown()
    assert seen == ["unrelated-mal-user"]


def test_operation_handler_keeps_captured_profile_and_token_after_switch(tmp_path, monkeypatch):
    from AniRec.api.app import _build_handler
    from AniRec.api.models import OperationStartRequest
    from AniRec.application.pipeline import CancellationToken
    from AniRec.models import PipelineResult

    app = create_app(root_override=str(tmp_path))
    services = app.state.container
    original = _local_profile(app, "original")
    other = _local_profile(app, "other")
    handler = _build_handler(
        services, "sync", OperationStartRequest(), original.username,
        original.profile_id, profile=original,
    )
    monkeypatch.setattr(
        services.auth, "get_access_token", lambda profile_id, _settings: profile_id,
    )
    captured = []

    def fake_sync(username, _settings, **kwargs):
        captured.append((username, kwargs["profile_override"], kwargs["access_token_provider"]()))
        return PipelineResult()

    monkeypatch.setattr(services.orchestrator, "run_sync", fake_sync)
    handler(CancellationToken(), lambda _progress: None)
    assert captured == [(original.username, original, original.profile_id)]
    assert services.results.path(original.profile_id).exists()
    assert not services.results.path(other.profile_id).exists()
