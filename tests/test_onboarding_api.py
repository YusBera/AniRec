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
