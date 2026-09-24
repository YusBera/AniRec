"""Accounts at the HTTP boundary (D-021).

The rule: the session's account owns every import it acts on. Two readers who
import the same MyAnimeList username never see or change each other's saved
decisions, operations or settings, and no request field can select another
account's data.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from AniRec.api.app import create_app
from AniRec.services.account_service import SESSION_COOKIE
from AniRec.services.profile_service import ProfileService

ORIGIN = {"Origin": "http://127.0.0.1:5173"}
CREDENTIALS = {"email": "reader@example.com", "password": "a long password"}


class FakeMal:
    def get_json(self, url, params=None, **_kwargs):
        return {"data": []}


def _app(tmp_path):
    app = create_app(root_override=str(tmp_path))
    services = app.state.container
    services.settings.save(replace(services.settings.load(), client_id="installation-client-id"))
    services.profiles._mal_client = FakeMal()
    return app, services


def _post(client, path, body=None, headers=None):
    return client.post(path, json=body, headers={**ORIGIN, **(headers or {})})


# -- registration, sign-in and the cookie --------------------------------------

def test_registering_sets_a_protected_cookie_and_never_returns_the_token(tmp_path):
    app, _services = _app(tmp_path)
    with TestClient(app) as client:
        response = _post(client, "/api/account/register", CREDENTIALS)
        body = response.json()
        cookie = response.headers["set-cookie"]
        assert body["account"] == {"kind": "registered", "email": "reader@example.com",
                                   "has_import": False, "installation_owner": False}
        assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/" in cookie
        assert "Secure" not in cookie   # plain http on loopback
        assert client.cookies[SESSION_COOKIE] not in response.text
        assert "a long password" not in response.text
        assert client.get("/api/account").json()["account"]["email"] == "reader@example.com"
        assert client.get("/api/system/state").json()["account"]["kind"] == "registered"


def test_signing_in_and_out(tmp_path):
    app, _services = _app(tmp_path)
    with TestClient(app) as client:
        _post(client, "/api/account/register", CREDENTIALS)
        _post(client, "/api/account/sign-out")
        assert client.get("/api/account").json() == {"account": None, "reason": None, "moved_imports": 0}
        wrong = _post(client, "/api/account/sign-in", {**CREDENTIALS, "password": "not the password"})
        assert wrong.json() == {"account": None, "reason": "wrong-credentials", "moved_imports": 0}
        assert _post(client, "/api/account/sign-in", CREDENTIALS).json()["account"]["kind"] == "registered"


def test_an_overlong_password_is_refused_before_any_hashing(tmp_path, monkeypatch):
    import AniRec.services.account_service as accounts

    app, _services = _app(tmp_path)
    monkeypatch.setattr(accounts, "_scrypt", lambda *_a, **_k: pytest.fail("hashed an overlong password"))
    with TestClient(app) as client:
        response = _post(client, "/api/account/sign-in", {"email": "a@b.co", "password": "x" * 10_000})
    assert response.status_code == 422


# -- the request guard -----------------------------------------------------------

@pytest.mark.parametrize("headers", [
    {"Origin": "http://evil.test"},
    {"Origin": "null"},
    {"Sec-Fetch-Site": "cross-site"},
])
def test_a_write_from_another_site_is_refused(tmp_path, headers):
    app, services = _app(tmp_path)
    with TestClient(app) as client:
        response = client.post("/api/account/register", json=CREDENTIALS, headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden_origin"
    from AniRec.services.account_service import AccountError
    with pytest.raises(AccountError) as refused:
        services.accounts.sign_in(CREDENTIALS["email"], CREDENTIALS["password"])
    assert refused.value.reason == "wrong-credentials"   # no account was created


def test_an_unknown_host_is_refused_even_for_reads(tmp_path, monkeypatch):
    monkeypatch.delenv("ANIREC_ALLOWED_HOSTS")
    app, _services = _app(tmp_path)
    with TestClient(app, base_url="http://evil.test:8770") as client:
        assert client.get("/api/health").status_code == 403
    with TestClient(app, base_url="http://127.0.0.1:8770") as client:
        assert client.get("/api/health").status_code == 200
    with TestClient(app, base_url="http://localhost:8770") as client:
        assert client.get("/api/health").status_code == 200


def test_a_same_origin_write_without_an_origin_header_is_accepted(tmp_path):
    app, _services = _app(tmp_path)
    with TestClient(app) as client:
        response = client.post("/api/account/register", json=CREDENTIALS, headers={"Sec-Fetch-Site": "same-origin"})
    assert response.json()["account"]["kind"] == "registered"


# -- guests ------------------------------------------------------------------------

def test_a_guest_import_survives_registering(tmp_path):
    app, _services = _app(tmp_path)
    with TestClient(app) as client:
        imported = _post(client, "/api/onboarding/mal-profile", {"username": "reader_01"}).json()["profile"]
        assert client.get("/api/account").json()["account"]["kind"] == "guest"
        _post(client, "/api/discover/feedback", {"profile_id": imported["profile_id"], "mal_id": 1, "action": "watch_later", "value": True})
        _post(client, "/api/account/register", CREDENTIALS)
        state = client.get("/api/system/state").json()
    assert state["account"]["kind"] == "registered"
    assert state["profile"]["profile_id"] == imported["profile_id"]
    assert app.state.container.recommendation_state.load(imported["profile_id"]).watch_later_mal_ids == frozenset({1})


def test_a_guest_signing_in_keeps_their_import_and_its_operations(tmp_path):
    app, services = _app(tmp_path)
    with TestClient(app) as reader:
        _post(reader, "/api/account/register", CREDENTIALS)
        _post(reader, "/api/account/sign-out")
        imported = _post(reader, "/api/onboarding/mal-profile", {"username": "reader_01"}).json()["profile"]
        key = f"api-test:{imported['profile_id']}"
        app.state.operations.start(key, "api-test", imported["profile_id"], lambda _t, _r: {"ok": True})
        app.state.operations.shutdown()
        assert _post(reader, "/api/account/sign-in", CREDENTIALS).json()["moved_imports"] == 1
        assert reader.get("/api/system/state").json()["profile"]["profile_id"] == imported["profile_id"]
        assert reader.get(f"/api/operations/{key}").status_code == 200


# -- isolation between accounts ------------------------------------------------------

def _two_readers_of_one_list(app):
    one, two = TestClient(app), TestClient(app)
    first = _post(one, "/api/onboarding/mal-profile", {"username": "shared_name"}).json()["profile"]
    second = _post(two, "/api/onboarding/mal-profile", {"username": "Shared_Name"}).json()["profile"]
    return one, two, first, second


def test_two_readers_of_one_list_get_separate_imports_and_decisions(tmp_path):
    app, services = _app(tmp_path)
    one, two, first, second = _two_readers_of_one_list(app)
    assert first["profile_id"] != second["profile_id"]
    assert first["profile_id"].startswith("imp_") and second["profile_id"].startswith("imp_")
    _post(one, "/api/discover/feedback", {"profile_id": first["profile_id"], "mal_id": 7, "action": "watch_later", "value": True})
    # The second reader cannot name the first's import, in any route.
    assert _post(two, "/api/discover/feedback", {"profile_id": first["profile_id"], "mal_id": 7, "action": "hidden", "value": True}).status_code == 409
    assert two.get("/api/workspace/library", params={"profile_id": first["profile_id"]}).status_code == 409
    assert _post(two, "/api/workspace/library/resolve", {"profile_id": first["profile_id"], "mal_id": 7}).status_code == 409
    for kind in ("recommendation", "refresh", "sync", "more-recommendations", "list-sync", "profile-lookup", "api-test"):
        refused = _post(two, f"/api/operations/{kind}", {"profile_id": first["profile_id"]})
        assert refused.status_code == 409, kind
    assert services.recommendation_state.load(first["profile_id"]).hidden_mal_ids == frozenset()
    assert services.recommendation_state.load(second["profile_id"]).watch_later_mal_ids == frozenset()


def test_a_readers_operations_are_invisible_to_everyone_else(tmp_path):
    app, _services = _app(tmp_path)
    one, two, first, _second = _two_readers_of_one_list(app)
    key = f"api-test:{first['profile_id']}"
    app.state.operations.start(key, "api-test", first["profile_id"], lambda _t, _r: {"ok": True})
    app.state.operations.shutdown()
    assert [op["id"] for op in one.get("/api/operations").json()["operations"]] == [key]
    assert two.get("/api/operations").json()["operations"] == []
    assert two.get(f"/api/operations/{key}").status_code == 404
    assert two.get(f"/api/operations/{key}/events").status_code == 404
    assert two.delete(f"/api/operations/{key}", headers=ORIGIN).status_code == 404
    anonymous = TestClient(app)
    assert anonymous.get("/api/operations").json()["operations"] == []


def test_the_api_never_reads_or_writes_the_machine_wide_active_profile(tmp_path, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("the API used profile_state.json")

    for name in ("active_profile", "active_profile_id", "set_active", "save_and_activate", "resolve_profile"):
        monkeypatch.setattr(ProfileService, name, forbidden)
    app, _services = _app(tmp_path)
    one, _two, first, _second = _two_readers_of_one_list(app)
    for path in ("/api/system/state", "/api/discover/feed", "/api/discover/activity", "/api/operations",
                 "/api/workspace/profile", "/api/workspace/settings", "/api/account",
                 f"/api/workspace/library?profile_id={first['profile_id']}"):
        assert one.get(path).status_code == 200, path
    assert not (tmp_path / "config" / "profile_state.json").exists()


# -- installation settings -------------------------------------------------------------

def _settings_payload(client):
    payload = client.get("/api/workspace/settings").json()
    for key in ("username", "client_id_present", "using_defaults", "can_edit", "can_edit_preferences"):
        payload.pop(key)
    return payload


def test_only_the_installation_owner_can_change_installation_settings(tmp_path):
    app, services = _app(tmp_path)
    guest, _other, _first, _second = _two_readers_of_one_list(app)
    with TestClient(app) as stranger, TestClient(app) as owner:
        _post(stranger, "/api/account/register", {**CREDENTIALS, "email": "stranger@example.com"})
        _post(owner, "/api/account/register", {**CREDENTIALS, "email": "owner@example.com"})
        services.accounts.set_owner("owner@example.com", [])
        for client in (guest, stranger):
            assert client.get("/api/workspace/settings").json()["can_edit"] is False
            refused = _post(client, "/api/workspace/settings", {**_settings_payload(owner), "adventurousness": 9})
            assert refused.status_code == 403
        assert services.settings.load().pipeline.randomness_factor != 9
        assert owner.get("/api/workspace/settings").json()["can_edit"] is True
        assert owner.get("/api/account").json()["account"]["installation_owner"] is True
        saved = _post(owner, "/api/workspace/settings", {**_settings_payload(owner), "adventurousness": 9})
        assert saved.status_code == 200
    assert services.settings.load().pipeline.randomness_factor == 9


def test_the_console_names_the_owner_and_hands_over_pre_account_profiles(tmp_path, capsys):
    from AniRec.api.accounts import main

    app, services = _app(tmp_path)
    existing = services.profiles.create_profile("desktop_reader", mal_user_id=123)
    services.profiles.save_profile(existing)
    with TestClient(app) as client:
        _post(client, "/api/account/register", CREDENTIALS)
        assert client.get("/api/system/state").json()["profile"] is None
        assert main(["--root", str(tmp_path), "owner", "reader@example.com"]) == 0
        state = client.get("/api/system/state").json()
    assert state["profile"]["profile_id"] == "mal-123"
    assert state["account"]["installation_owner"] is True
    assert "mal-123" in capsys.readouterr().out
    assert main(["--root", str(tmp_path), "owner", "nobody@example.com"]) == 1


def test_an_unreadable_account_database_never_becomes_a_server_error(tmp_path):
    app, services = _app(tmp_path)
    services.accounts.path.parent.mkdir(parents=True, exist_ok=True)
    services.accounts.path.write_bytes(b"this is not a database" * 100)
    with TestClient(app) as client:
        client.cookies.set(SESSION_COOKIE, "some-token")
        assert client.get("/api/discover/feed").json()["source"] == "sample"
        assert client.get("/api/system/state").json()["account"] is None
        assert _post(client, "/api/account/register", CREDENTIALS).json() == {"account": None, "reason": "unavailable", "moved_imports": 0}
        assert _post(client, "/api/account/sign-in", CREDENTIALS).json() == {"account": None, "reason": "unavailable", "moved_imports": 0}
