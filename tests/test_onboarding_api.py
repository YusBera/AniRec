"""First-time setup: import a public MyAnimeList list by username (D-020).

The visitor types only a username. The Client ID belongs to this AniRec
installation and is never asked for or returned; a list that cannot be read
comes back as a plain reason, never as a server error.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from AniRec.api.app import create_app
from AniRec.api.security import TOKEN_HEADER, generate_token
from AniRec.errors import AccessDeniedError, NetworkError, NotFoundError

ORIGIN = {"Origin": "http://127.0.0.1:5173"}


class FakeMal:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls: list[tuple[str, str | None]] = []

    def get_json(self, url, params=None, *, client_id=None, cancellation=None, **_kwargs):
        self.calls.append((url, client_id))
        if self.error is not None:
            raise self.error
        return {"data": []}


def _client(tmp_path, *, client_id="installation-client-id", error=None, token=None):
    app = create_app(root_override=str(tmp_path), token=token)
    services = app.state.container
    if client_id:
        services.settings.save(replace(services.settings.load(), client_id=client_id))
    mal = FakeMal(error)
    services.profiles._mal_client = mal
    return app, services, mal


def _import(client, username, headers=None):
    return client.post("/api/onboarding/mal-profile", json={"username": username}, headers={**ORIGIN, **(headers or {})})


def test_a_public_list_becomes_the_active_profile_and_ends_setup(tmp_path):
    app, services, mal = _client(tmp_path)
    with TestClient(app) as client:
        assert client.get("/api/system/state").json()["needs_setup"] is True
        response = _import(client, "reader_01")
        assert response.status_code == 200
        body = response.json()
        assert body["reason"] is None
        assert body["profile"]["username"] == "reader_01"
        state = client.get("/api/system/state").json()
    assert state["profile"]["username"] == "reader_01"
    assert state["needs_setup"] is False
    # The installation's Client ID was used; the response never carries it.
    assert mal.calls and mal.calls[0][1] == "installation-client-id"
    assert "installation-client-id" not in response.text


def test_a_profile_url_is_accepted_as_well(tmp_path):
    app, _services, _mal = _client(tmp_path)
    with TestClient(app) as client:
        body = _import(client, "https://myanimelist.net/profile/reader_01").json()
    assert body["profile"]["username"] == "reader_01"


def test_without_a_client_id_nothing_is_created_and_the_reason_is_given(tmp_path):
    app, services, mal = _client(tmp_path, client_id=None)
    with TestClient(app) as client:
        body = _import(client, "reader_01").json()
        state = client.get("/api/system/state").json()
    assert body == {"profile": None, "reason": "client-id-required"}
    assert mal.calls == []
    assert state["profile"] is None and state["needs_setup"] is True


@pytest.mark.parametrize("username", ["", "a", "no spaces", "semi;colon", "x" * 65, "http://myanimelist.net/profile/reader"])
def test_an_invalid_username_is_refused_before_anything_is_fetched(tmp_path, username):
    app, _services, mal = _client(tmp_path)
    with TestClient(app) as client:
        body = _import(client, username).json()
    assert body == {"profile": None, "reason": "invalid-username"}
    assert mal.calls == []


@pytest.mark.parametrize(("error", "reason"), [
    (NotFoundError("MyAnimeList returned HTTP 404."), "user-not-found"),
    (AccessDeniedError("MyAnimeList returned HTTP 403."), "private-list"),
    (NetworkError("Could not connect to MyAnimeList."), "network"),
])
def test_a_list_that_cannot_be_read_is_a_plain_reason_not_a_server_error(tmp_path, error, reason):
    app, _services, _mal = _client(tmp_path, error=error)
    with TestClient(app) as client:
        response = _import(client, "reader_01")
        state = client.get("/api/system/state").json()
    assert response.status_code == 200
    assert response.json() == {"profile": None, "reason": reason}
    assert state["profile"] is None and state["needs_setup"] is True


def test_the_import_route_needs_the_token_like_every_other_write(tmp_path):
    token = generate_token()
    app, _services, mal = _client(tmp_path, token=token)
    with TestClient(app) as client:
        assert _import(client, "reader_01").status_code == 401
        assert _import(client, "reader_01", {TOKEN_HEADER: token}).status_code == 200
    assert len(mal.calls) == 1


# -- review fixes: the real status mapping, and existing profiles ---------------

class _Response:
    def __init__(self, status, payload=None, bad_json=False):
        self.status_code = status
        self.headers = {}
        self._payload = payload if payload is not None else {"data": []}
        self._bad_json = bad_json

    def raise_for_status(self):
        return None

    def json(self):
        if self._bad_json:
            raise ValueError("not json")
        return self._payload


def _real_client(tmp_path, response):
    from AniRec.infrastructure.mal_client import MALClient

    app = create_app(root_override=str(tmp_path))
    services = app.state.container
    services.settings.save(replace(services.settings.load(), client_id="installation-client-id"))
    services.profiles._mal_client = MALClient(http_get=lambda *_args, **_kwargs: response)
    return app, services


@pytest.mark.parametrize(("response", "reason"), [
    (_Response(401), "installation-refused"),
    (_Response(403), "private-list"),
    (_Response(404), "user-not-found"),
    (_Response(429), "rate-limited"),
    (_Response(500), "unavailable"),
    (_Response(503), "unavailable"),
    (_Response(400), "unavailable"),
    (_Response(200, bad_json=True), "unavailable"),
])
def test_every_myanimelist_answer_maps_to_a_reason_through_the_real_client(tmp_path, response, reason):
    app, _services = _real_client(tmp_path, response)
    with TestClient(app) as client:
        result = _import(client, "reader_01")
        state = client.get("/api/system/state").json()
    assert result.status_code == 200
    assert result.json() == {"profile": None, "reason": reason}
    assert state["profile"] is None and state["needs_setup"] is True


def test_an_unreachable_myanimelist_is_the_readers_connection(tmp_path):
    import requests

    from AniRec.infrastructure.mal_client import MALClient

    app = create_app(root_override=str(tmp_path))
    services = app.state.container
    services.settings.save(replace(services.settings.load(), client_id="installation-client-id"))
    def refuse(*_args, **_kwargs):
        raise requests.ConnectionError("offline")
    services.profiles._mal_client = MALClient(http_get=refuse)
    with TestClient(app) as client:
        assert _import(client, "reader_01").json() == {"profile": None, "reason": "network"}


def test_importing_a_known_reader_again_keeps_their_saved_profile(tmp_path):
    app, services, _mal = _client(tmp_path)
    with TestClient(app) as client:
        first = _import(client, "reader_01").json()["profile"]
        path = services.profiles.directory(first["profile_id"]) / "profile.json"
        services.profiles.mark_synced(services.profiles.get_profile(first["profile_id"]))
        saved = path.read_bytes()
        again = _import(client, "READER_01").json()["profile"]
    assert again["profile_id"] == first["profile_id"]
    assert path.read_bytes() == saved   # last sync and anything else kept


def test_a_desktop_profile_that_no_account_owns_is_never_handed_to_an_import(tmp_path):
    # D-021: a MyAnimeList name never selects saved data. Only the operator's
    # console can give pre-account profiles to an account.
    app, services, _mal = _client(tmp_path)
    existing = services.profiles.create_profile("reader_01", mal_user_id=123)
    directory = services.profiles.directory(existing.profile_id, create=True)
    services.profiles._store.write(existing.to_dict(), directory / "profile.json")
    with TestClient(app) as client:
        body = _import(client, "reader_01").json()
    assert body["profile"]["profile_id"].startswith("imp_")
    assert not services.accounts.is_owned("mal-123")


def test_a_disk_failure_is_a_reason_and_leaves_no_import_behind(tmp_path, monkeypatch):
    app, services, _mal = _client(tmp_path)
    def fail(*_args, **_kwargs):
        raise OSError("disk full")
    monkeypatch.setattr(services.profiles, "save_profile", fail)
    with TestClient(app) as client:
        body = _import(client, "reader_01").json()
        state = client.get("/api/system/state").json()
    assert body == {"profile": None, "reason": "unavailable"}
    assert state["profile"] is None and state["needs_setup"] is True
    profiles = tmp_path / "profiles"
    assert not profiles.exists() or not any(profiles.iterdir())


def test_a_failed_read_creates_no_guest_account(tmp_path):
    app, services, _mal = _client(tmp_path, error=NotFoundError("MyAnimeList returned HTTP 404."))
    with TestClient(app) as client:
        response = _import(client, "reader_01")
    assert "anirec_session" not in response.cookies
    assert client.cookies.get("anirec_session") is None


def test_imports_are_capped_process_wide(tmp_path, monkeypatch):
    import AniRec.api.onboarding as onboarding

    monkeypatch.setattr(onboarding, "IMPORTS_PER_HOUR", 1)
    app, _services, mal = _client(tmp_path)
    with TestClient(app) as client:
        assert _import(client, "reader_01").json()["reason"] is None
        assert _import(client, "reader_02").json() == {"profile": None, "reason": "busy"}
    assert len(mal.calls) == 1
