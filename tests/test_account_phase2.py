"""Accounts, phase 2 hosted-launch gates (D-021, docs/ACCOUNTS.md).

- Limits are per visitor: one visitor exhausting theirs blocks nobody else.
- Behind a trusted proxy the visitor is the forwarded address, and HTTPS is
  what the proxy reports; from anyone else those headers are ignored.
- Only the launcher (per-launch token) or the installation owner can stop the
  service.
- Everything that spends the installation's MyAnimeList Client ID shares a
  per-visitor budget.
- An account with several lists can switch between them, and only between
  its own.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from AniRec.api.app import create_app
from AniRec.api.limits import ClientLimits, KeyedRateWindow
from AniRec.api.security import TOKEN_HEADER, generate_token
from AniRec.services.account_service import SESSION_COOKIE

ORIGIN = {"Origin": "http://127.0.0.1:5173"}
CREDENTIALS = {"email": "reader@example.com", "password": "a long password"}


class FakeMal:
    def __init__(self):
        self.calls = 0

    def get_json(self, url, params=None, **_kwargs):
        self.calls += 1
        return {"data": []}


def _app(tmp_path, limits=None, **kwargs):
    app = create_app(root_override=str(tmp_path), limits=limits, **kwargs)
    services = app.state.container
    services.settings.save(replace(services.settings.load(), client_id="installation-client-id"))
    mal = FakeMal()
    services.profiles._mal_client = mal
    return app, services, mal


def _post(client, path, body=None, headers=None):
    return client.post(path, json=body, headers={**ORIGIN, **(headers or {})})


def _visitor(app, address):
    return TestClient(app, client=(address, 40000))


# -- per-visitor limits -------------------------------------------------------------

def test_one_visitors_wrong_passwords_do_not_lock_out_anyone_else(tmp_path):
    limits = ClientLimits(sign_in_failures=KeyedRateWindow(3, 60))
    app, _services, _mal = _app(tmp_path, limits)
    with _visitor(app, "203.0.113.5") as owner, _visitor(app, "198.51.100.9") as attacker:
        _post(owner, "/api/account/register", CREDENTIALS)
        _post(owner, "/api/account/sign-out")
        for index in range(3):
            wrong = {"email": f"victim{index}@example.com", "password": "not the password"}
            assert _post(attacker, "/api/account/sign-in", wrong).json()["reason"] == "wrong-credentials"
        assert _post(attacker, "/api/account/sign-in", CREDENTIALS).json()["reason"] == "too-many-attempts"
        assert _post(owner, "/api/account/sign-in", CREDENTIALS).json()["account"]["kind"] == "registered"


def test_new_accounts_are_limited_per_visitor(tmp_path):
    limits = ClientLimits(new_accounts=KeyedRateWindow(2, 3600))
    app, _services, _mal = _app(tmp_path, limits)
    with _visitor(app, "198.51.100.9") as flood, _visitor(app, "203.0.113.5") as reader:
        for index in range(2):
            assert _post(flood, "/api/account/register", {**CREDENTIALS, "email": f"junk{index}@example.com"}).json()["account"]
            _post(flood, "/api/account/sign-out")
        assert _post(flood, "/api/account/register", {**CREDENTIALS, "email": "junk9@example.com"}).json()["reason"] == "busy"
        assert _post(flood, "/api/onboarding/mal-profile", {"username": "someone"}).json()["reason"] == "busy"
        assert _post(reader, "/api/account/register", CREDENTIALS).json()["account"]["kind"] == "registered"


def test_upgrading_a_guest_is_not_a_new_account(tmp_path):
    limits = ClientLimits(new_accounts=KeyedRateWindow(1, 3600))
    app, _services, _mal = _app(tmp_path, limits)
    with _visitor(app, "203.0.113.5") as reader:
        assert _post(reader, "/api/onboarding/mal-profile", {"username": "reader_01"}).json()["profile"]
        assert _post(reader, "/api/account/register", CREDENTIALS).json()["account"]["kind"] == "registered"


def test_every_myanimelist_lookup_shares_one_budget_per_visitor(tmp_path):
    limits = ClientLimits(mal_calls=KeyedRateWindow(2, 3600))
    app, services, mal = _app(tmp_path, limits)
    with _visitor(app, "198.51.100.9") as heavy, _visitor(app, "203.0.113.5") as other:
        imported = _post(heavy, "/api/onboarding/mal-profile", {"username": "reader_01"}).json()["profile"]
        assert _post(heavy, "/api/operations/profile-lookup", {"target": "friend"}).status_code == 202
        app.state.operations.shutdown()
        snapshot = services.profiles.directory(imported["profile_id"]) / "completed_anime.csv"
        snapshot.write_text("Anime ID,Title,User Score\n1,Cowboy Bebop,9\n", encoding="utf-8")
        # The budget is spent: lookup, Compare, title details and imports refuse.
        assert _post(heavy, "/api/operations/profile-lookup", {"target": "friend"}).status_code == 429
        assert heavy.get("/api/workspace/compare", params={"username": "friend"}).json()["reason"] == "busy"
        services.recommendation_state.set_watch_later(imported["profile_id"], 5, True)
        resolved = _post(heavy, "/api/workspace/library/resolve", {"profile_id": imported["profile_id"], "mal_id": 5})
        assert resolved.status_code == 429
        assert _post(heavy, "/api/onboarding/mal-profile", {"username": "reader_02"}).json()["reason"] == "busy"
        # Someone else's budget is untouched.
        assert _post(other, "/api/onboarding/mal-profile", {"username": "reader_03"}).json()["profile"]


# -- trusted proxies ---------------------------------------------------------------------

def test_forwarded_headers_count_only_from_a_trusted_proxy(tmp_path):
    limits = ClientLimits(trusted_proxies=frozenset({"10.0.0.2"}), sign_in_failures=KeyedRateWindow(1, 60))
    app, _services, _mal = _app(tmp_path, limits)
    wrong = {"email": "nobody@example.com", "password": "not the password"}
    with _visitor(app, "10.0.0.2") as proxy:
        # Two visitors behind the proxy are two clients.
        _post(proxy, "/api/account/sign-in", wrong, {"X-Forwarded-For": "203.0.113.5"})
        assert _post(proxy, "/api/account/sign-in", wrong, {"X-Forwarded-For": "203.0.113.5"}).json()["reason"] == "too-many-attempts"
        assert _post(proxy, "/api/account/sign-in", wrong, {"X-Forwarded-For": "198.51.100.9"}).json()["reason"] == "wrong-credentials"
        # A client cannot forge its place in the chain: the right-most
        # untrusted address is the one that counts.
        spoofed = _post(proxy, "/api/account/sign-in", wrong, {"X-Forwarded-For": "1.2.3.4, 203.0.113.5"})
        assert spoofed.json()["reason"] == "too-many-attempts"
    with _visitor(app, "192.0.2.77") as direct:
        # Not a trusted proxy: its forwarded header is ignored.
        _post(direct, "/api/account/sign-in", wrong, {"X-Forwarded-For": "198.51.100.200"})
        assert _post(direct, "/api/account/sign-in", wrong, {"X-Forwarded-For": "198.51.100.201"}).json()["reason"] == "too-many-attempts"


def test_the_cookie_is_secure_when_a_trusted_proxy_says_https(tmp_path):
    limits = ClientLimits(trusted_proxies=frozenset({"10.0.0.2"}))
    app, _services, _mal = _app(tmp_path, limits)
    with _visitor(app, "10.0.0.2") as proxy:
        response = _post(proxy, "/api/account/register", CREDENTIALS, {"X-Forwarded-Proto": "https", "X-Forwarded-For": "203.0.113.5"})
        assert "Secure" in response.headers["set-cookie"]
    with _visitor(app, "192.0.2.77") as direct:
        response = _post(direct, "/api/account/register", {**CREDENTIALS, "email": "b@example.com"}, {"X-Forwarded-Proto": "https"})
        assert "Secure" not in response.headers["set-cookie"]


# -- shutdown ----------------------------------------------------------------------------

def test_only_the_owner_can_stop_a_service_launched_without_a_token(tmp_path):
    stopped: list[bool] = []
    app, services, _mal = _app(tmp_path, on_shutdown_requested=lambda: stopped.append(True))
    with TestClient(app) as visitor, TestClient(app) as reader, TestClient(app) as owner:
        assert _post(visitor, "/api/system/shutdown").status_code == 403
        _post(reader, "/api/account/register", {**CREDENTIALS, "email": "reader2@example.com"})
        assert _post(reader, "/api/system/shutdown").status_code == 403
        _post(owner, "/api/account/register", CREDENTIALS)
        services.accounts.set_owner(CREDENTIALS["email"], [])
        assert stopped == []
        assert _post(owner, "/api/system/shutdown").status_code == 202
    assert stopped == [True]


def test_the_launcher_stops_the_service_with_its_token(tmp_path):
    token = generate_token()
    stopped: list[bool] = []
    app, _services, _mal = _app(tmp_path, token=token, on_shutdown_requested=lambda: stopped.append(True))
    with TestClient(app) as launcher:
        assert _post(launcher, "/api/system/shutdown", headers={TOKEN_HEADER: token}).status_code == 202
    assert stopped == [True]


# -- switching between an account's lists ---------------------------------------------------

def test_an_account_switches_between_its_own_lists_only(tmp_path):
    app, _services, _mal = _app(tmp_path)
    with TestClient(app) as reader, TestClient(app) as other:
        first = _post(reader, "/api/onboarding/mal-profile", {"username": "reader_01"}).json()["profile"]
        second = _post(reader, "/api/onboarding/mal-profile", {"username": "reader_02"}).json()["profile"]
        theirs = _post(other, "/api/onboarding/mal-profile", {"username": "reader_01"}).json()["profile"]
        listed = reader.get("/api/account/imports").json()
        assert [item["username"] for item in listed["imports"]] == ["reader_01", "reader_02"]
        assert listed["active_profile_id"] == second["profile_id"]
        switched = _post(reader, "/api/account/imports/active", {"profile_id": first["profile_id"]}).json()
        assert switched["active_profile_id"] == first["profile_id"] and switched["reason"] is None
        assert reader.get("/api/system/state").json()["profile"]["profile_id"] == first["profile_id"]
        refused = _post(reader, "/api/account/imports/active", {"profile_id": theirs["profile_id"]}).json()
        assert refused["reason"] == "not-owner"
        assert reader.get("/api/system/state").json()["profile"]["profile_id"] == first["profile_id"]
        assert theirs["profile_id"] not in [item["profile_id"] for item in listed["imports"]]
    with TestClient(app) as anonymous:
        assert anonymous.get("/api/account/imports").json() == {"imports": [], "active_profile_id": None, "reason": None}
        assert _post(anonymous, "/api/account/imports/active", {"profile_id": first["profile_id"]}).json()["reason"] == "signed-out"


def test_a_guest_list_moved_into_an_account_can_be_switched_to(tmp_path):
    app, _services, _mal = _app(tmp_path)
    with TestClient(app) as reader:
        _post(reader, "/api/account/register", CREDENTIALS)
        mine = _post(reader, "/api/onboarding/mal-profile", {"username": "reader_01"}).json()["profile"]
        _post(reader, "/api/account/sign-out")
        guest = _post(reader, "/api/onboarding/mal-profile", {"username": "guest_list"}).json()["profile"]
        _post(reader, "/api/account/sign-in", CREDENTIALS)
        assert reader.get("/api/system/state").json()["profile"]["profile_id"] == mine["profile_id"]
        assert _post(reader, "/api/account/imports/active", {"profile_id": guest["profile_id"]}).json()["reason"] is None
        assert reader.get("/api/system/state").json()["profile"]["username"] == "guest_list"
