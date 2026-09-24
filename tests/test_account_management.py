"""Account management (D-021, docs/ACCOUNTS.md "Account management").

Change password, delete account, export, per-reader preferences, sessions
that renew while used, and pruning of guests nobody can reach any more.
The invariants: nothing reaches another account's data, a deleted reader's
lists are never handed to anyone, and the desktop tool's data survives.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from AniRec.api.app import create_app
from AniRec.api.operations import ProfileClosedError
from AniRec.models import PipelineResult
from AniRec.services.account_service import SESSION_COOKIE

ORIGIN = {"Origin": "http://127.0.0.1:5173"}
CREDENTIALS = {"email": "reader@example.com", "password": "a long password"}


class FakeMal:
    def get_json(self, url, params=None, **_kwargs):
        return {"data": []}


class Clock:
    def __init__(self):
        self.now = datetime.now(timezone.utc)

    def __call__(self):
        return self.now


def _app(tmp_path):
    app = create_app(root_override=str(tmp_path))
    services = app.state.container
    services.settings.save(replace(services.settings.load(), client_id="installation-client-id"))
    services.profiles._mal_client = FakeMal()
    return app, services


def _post(client, path, body=None):
    return client.post(path, json=body, headers=ORIGIN)


def _register_with_list(client, username="reader_01", credentials=CREDENTIALS):
    imported = _post(client, "/api/onboarding/mal-profile", {"username": username}).json()["profile"]
    assert _post(client, "/api/account/register", credentials).json()["account"]["kind"] == "registered"
    return imported


# -- change password ---------------------------------------------------------------------

def test_changing_the_password_ends_every_other_session_but_keeps_this_one(tmp_path):
    app, _services = _app(tmp_path)
    with TestClient(app) as here, TestClient(app) as elsewhere:
        _register_with_list(here)
        _post(elsewhere, "/api/account/sign-in", CREDENTIALS)
        wrong = _post(here, "/api/account/password", {"current_password": "not it at all", "new_password": "a new long password"})
        assert wrong.json()["reason"] == "wrong-credentials"
        changed = _post(here, "/api/account/password", {"current_password": CREDENTIALS["password"], "new_password": "a new long password"})
        assert changed.json()["account"]["kind"] == "registered"
        assert "a new long password" not in changed.text
        assert here.get("/api/account").json()["account"]["email"] == CREDENTIALS["email"]
        assert elsewhere.get("/api/account").json()["account"] is None
        assert _post(elsewhere, "/api/account/sign-in", CREDENTIALS).json()["reason"] == "wrong-credentials"
        assert _post(elsewhere, "/api/account/sign-in", {**CREDENTIALS, "password": "a new long password"}).json()["account"]


def test_a_guest_has_no_password_to_change(tmp_path):
    app, _services = _app(tmp_path)
    with TestClient(app) as guest:
        _post(guest, "/api/onboarding/mal-profile", {"username": "reader_01"})
        refused = _post(guest, "/api/account/password", {"current_password": "whatever1", "new_password": "a long password"})
    assert refused.json()["reason"] == "not-registered"


# -- delete account -------------------------------------------------------------------------

def test_deleting_an_account_removes_its_lists_and_nobody_elses(tmp_path):
    app, services = _app(tmp_path)
    with TestClient(app) as reader, TestClient(app) as other:
        mine = _register_with_list(reader)
        theirs = _post(other, "/api/onboarding/mal-profile", {"username": "reader_01"}).json()["profile"]
        services.tokens.path_for(mine["profile_id"]).parent.mkdir(parents=True, exist_ok=True)
        services.tokens.path_for(mine["profile_id"]).write_text("{}", encoding="utf-8")
        assert _post(reader, "/api/account/delete", {"password": "not the password"}).json()["reason"] == "wrong-credentials"
        assert services.profiles.directory(mine["profile_id"]).exists()
        response = _post(reader, "/api/account/delete", {"password": CREDENTIALS["password"]})
        assert response.json() == {"account": None, "reason": None, "moved_imports": 0}
        assert SESSION_COOKIE in response.headers["set-cookie"]   # cleared
        assert reader.get("/api/account").json()["account"] is None
        assert _post(reader, "/api/account/sign-in", CREDENTIALS).json()["reason"] == "wrong-credentials"
        assert other.get("/api/system/state").json()["profile"]["profile_id"] == theirs["profile_id"]
    assert not services.profiles.directory(mine["profile_id"]).exists()
    assert not services.tokens.path_for(mine["profile_id"]).exists()
    assert services.profiles.directory(theirs["profile_id"]).exists()
    assert services.accounts.pending_deletions() == ()


def test_a_guest_deletes_their_data_without_a_password(tmp_path):
    app, services = _app(tmp_path)
    with TestClient(app) as guest:
        imported = _post(guest, "/api/onboarding/mal-profile", {"username": "reader_01"}).json()["profile"]
        assert _post(guest, "/api/account/delete", {}).json()["reason"] is None
    assert not services.profiles.directory(imported["profile_id"]).exists()


def test_deleting_is_refused_while_a_list_is_busy_and_then_nothing_changes(tmp_path):
    app, services = _app(tmp_path)
    release = threading.Event()
    with TestClient(app) as reader:
        mine = _register_with_list(reader)
        app.state.operations.start("busy", "api-test", mine["profile_id"], lambda _t, _r: release.wait(5))
        refused = _post(reader, "/api/account/delete", {"password": CREDENTIALS["password"]})
        assert refused.json()["reason"] == "operation-running"
        assert reader.get("/api/account").json()["account"]["email"] == CREDENTIALS["email"]
        release.set()
        app.state.operations.shutdown()
        # Not left closed: the reader's next operation may start.
        app.state.operations.start("next", "api-test", mine["profile_id"], lambda _t, _r: None)
    assert services.profiles.directory(mine["profile_id"]).exists()


def test_no_operation_can_start_on_a_deleted_list(tmp_path):
    app, _services = _app(tmp_path)
    with TestClient(app) as reader:
        mine = _register_with_list(reader)
        _post(reader, "/api/account/delete", {"password": CREDENTIALS["password"]})
    with pytest.raises(ProfileClosedError):
        app.state.operations.start("late", "sync", mine["profile_id"], lambda _t, _r: None)


def test_deleting_the_owner_releases_the_desktop_tools_profiles(tmp_path):
    app, services = _app(tmp_path)
    legacy = services.profiles.create_profile("desktop_reader", mal_user_id=123)
    services.profiles.save_profile(legacy)
    with TestClient(app) as owner:
        web = _register_with_list(owner)
        second = _post(owner, "/api/onboarding/mal-profile", {"username": "desktop_active"}).json()["profile"]
        services.accounts.set_owner(CREDENTIALS["email"], ["mal-123"])
        # The desktop tool has one of the owner's web lists active.
        services.profiles.set_active(second["profile_id"])
        assert _post(owner, "/api/account/delete", {"password": CREDENTIALS["password"]}).json()["reason"] is None
    assert services.profiles.directory("mal-123").exists()
    assert services.profiles.directory(second["profile_id"]).exists()
    assert not services.profiles.directory(web["profile_id"]).exists()
    assert not services.accounts.is_owned("mal-123")
    assert services.accounts.owner_account_id() is None


def test_files_that_cannot_be_removed_stay_pending_and_are_never_claimed(tmp_path, monkeypatch):
    import AniRec.api.account_maintenance as maintenance_module

    app, services = _app(tmp_path)
    real = maintenance_module.shutil.rmtree
    monkeypatch.setattr(maintenance_module.shutil, "rmtree", lambda *_a, **_k: (_ for _ in ()).throw(OSError("locked")))
    with TestClient(app) as reader:
        mine = _register_with_list(reader)
        # Final for the reader even though the files are still there.
        assert _post(reader, "/api/account/delete", {"password": CREDENTIALS["password"]}).json()["reason"] is None
        assert reader.get("/api/account").json()["account"] is None
    assert services.accounts.pending_deletions() == (mine["profile_id"],)
    _post_owner = services.accounts.register("owner@example.com", "a long password")
    _account, claimed = services.accounts.set_owner("owner@example.com", [mine["profile_id"]])
    assert claimed == ()
    monkeypatch.setattr(maintenance_module.shutil, "rmtree", real)
    app.state.maintenance.sweep()
    assert not services.profiles.directory(mine["profile_id"]).exists()
    assert services.accounts.pending_deletions() == ()
    assert _post_owner.account.registered


def test_the_sweep_removes_only_stale_unowned_web_lists(tmp_path):
    app, services = _app(tmp_path)
    stale = services.profiles.directory("imp_" + "a" * 32, create=True)
    (stale / "recommendation_state.json").write_text("{}", encoding="utf-8")
    fresh = services.profiles.directory("imp_" + "b" * 32, create=True)
    legacy = services.profiles.directory("mal-123", create=True)
    old = time.time() - 7200
    for path in (stale, stale / "recommendation_state.json", legacy):
        os.utime(path, (old, old))
    with TestClient(app) as reader:
        owned = _register_with_list(reader)
    owned_dir = services.profiles.directory(owned["profile_id"])
    os.utime(owned_dir, (old, old))
    app.state.maintenance.sweep()
    assert not stale.exists()
    assert fresh.exists() and legacy.exists() and owned_dir.exists()


# -- guest pruning -------------------------------------------------------------------------------

def _guest_with_list(app, username):
    # Not entered as a context manager: the lifespan (and its startup sweep)
    # stays off, so each test decides when the sweep runs.
    guest = TestClient(app)
    return _post(guest, "/api/onboarding/mal-profile", {"username": username}).json()["profile"]


def test_a_guest_nobody_has_used_for_37_days_is_pruned_with_their_list(tmp_path):
    app, services = _app(tmp_path)
    clock = Clock()
    services.accounts._clock = clock
    abandoned = _guest_with_list(app, "abandoned")
    clock.now += timedelta(days=38)
    recent = _guest_with_list(app, "recent")   # someone is using AniRec now
    app.state.maintenance.sweep()
    assert not services.profiles.directory(abandoned["profile_id"]).exists()
    assert services.profiles.directory(recent["profile_id"]).exists()


def test_nothing_is_pruned_when_the_clock_looks_wrong(tmp_path):
    app, services = _app(tmp_path)
    clock = Clock()
    services.accounts._clock = clock
    abandoned = _guest_with_list(app, "abandoned")
    clock.now += timedelta(days=90)   # a forward jump: nobody "seen" in a day
    app.state.maintenance.sweep()
    assert services.profiles.directory(abandoned["profile_id"]).exists()


def test_a_guest_in_use_is_never_pruned_because_sessions_renew(tmp_path):
    app, services = _app(tmp_path)
    clock = Clock()
    services.accounts._clock = clock
    guest = TestClient(app)
    profile = _post(guest, "/api/onboarding/mal-profile", {"username": "daily"}).json()["profile"]
    for _ in range(40):   # used every day for 40 days
        clock.now += timedelta(days=1)
        response = guest.get("/api/system/state")
        assert response.json()["profile"]["profile_id"] == profile["profile_id"]
    assert SESSION_COOKIE in response.headers.get("set-cookie", "")   # renewed in the browser too
    app.state.maintenance.sweep()
    assert services.profiles.directory(profile["profile_id"]).exists()


# -- export ------------------------------------------------------------------------------------------

def test_the_export_holds_the_readers_own_data_and_no_secrets(tmp_path):
    app, services = _app(tmp_path)
    with TestClient(app) as reader, TestClient(app) as other:
        mine = _register_with_list(reader)
        theirs = _post(other, "/api/onboarding/mal-profile", {"username": "someone_else"}).json()["profile"]
        _post(reader, "/api/discover/feedback", {"profile_id": mine["profile_id"], "mal_id": 7, "action": "watch_later", "value": True})
        _post(other, "/api/discover/feedback", {"profile_id": theirs["profile_id"], "mal_id": 9, "action": "watch_later", "value": True})
        response = reader.get("/api/account/export")
        assert other.get("/api/account/export").status_code == 200
        with TestClient(app) as anonymous:
            assert anonymous.get("/api/account/export").status_code == 401
    assert response.headers["cache-control"] == "no-store"
    assert "attachment" in response.headers["content-disposition"]
    body = response.json()
    assert body["account"]["email"] == CREDENTIALS["email"]
    assert [item["username"] for item in body["lists"]] == ["reader_01"]
    assert body["lists"][0]["saved"]["watch_later_mal_ids"] == [7]
    text = response.text
    for secret in ("scrypt$", CREDENTIALS["password"], "someone_else", theirs["profile_id"], "installation-client-id"):
        assert secret not in text


# -- per-reader preferences -------------------------------------------------------------------------------

def test_each_reader_ranks_with_their_own_preferences_and_nsfw_is_never_inherited(tmp_path, monkeypatch):
    app, services = _app(tmp_path)
    settings = services.settings.load()
    services.settings.save(replace(settings, pipeline=replace(settings.pipeline, include_nsfw=True, randomness_factor=2)))
    seen = []

    def run_full(username, pipeline, **_kwargs):
        seen.append((username, pipeline.randomness_factor, pipeline.include_nsfw, pipeline.minimum_mean_score))
        return PipelineResult()

    monkeypatch.setattr(services.orchestrator, "run_full", run_full)
    with TestClient(app) as reader, TestClient(app) as other:
        _register_with_list(reader)
        _post(other, "/api/onboarding/mal-profile", {"username": "other_reader"})
        read = reader.get("/api/workspace/settings").json()
        assert read["can_edit_preferences"] is True and read["can_edit"] is False
        assert read["include_nsfw"] is False and read["adventurousness"] == 2
        saved = _post(reader, "/api/workspace/preferences", {"adventurousness": 9, "minimum_mal_score": 7.5, "include_nsfw": False})
        assert saved.json()["adventurousness"] == 9
        assert _post(reader, "/api/operations/recommendation", {}).status_code == 202
        app.state.operations.shutdown()
        assert _post(other, "/api/operations/recommendation", {}).status_code == 202
        app.state.operations.shutdown()
    assert seen == [("reader_01", 9, False, 7.5), ("other_reader", 2, False, None)]
    assert services.settings.load().pipeline.randomness_factor == 2   # the installation's are untouched


def test_the_owners_preferences_are_the_installation_settings(tmp_path):
    app, services = _app(tmp_path)
    with TestClient(app) as owner:
        _register_with_list(owner)
        services.accounts.set_owner(CREDENTIALS["email"], [])
        _post(owner, "/api/workspace/preferences", {"adventurousness": 8, "minimum_mal_score": None, "include_nsfw": True})
    pipeline = services.settings.load().pipeline
    assert (pipeline.randomness_factor, pipeline.include_nsfw) == (8, True)


def test_preferences_need_an_account(tmp_path):
    app, _services = _app(tmp_path)
    with TestClient(app) as visitor:
        assert visitor.get("/api/workspace/settings").json()["can_edit_preferences"] is False
        refused = _post(visitor, "/api/workspace/preferences", {"adventurousness": 8, "minimum_mal_score": None, "include_nsfw": True})
    assert refused.status_code == 409
