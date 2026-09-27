"""The ``list-sync`` operation over HTTP.

It used to fail on every run: ``_build_handler`` never passed ``synced_at``
to ``MalSyncService.sync``, which requires it. The sync state must also land
in the reader's own data root, never the machine-wide one.
"""

from __future__ import annotations

import time
from dataclasses import replace
from datetime import datetime

from fastapi.testclient import TestClient

from AniRec.api.app import create_app

ORIGIN = {"Origin": "http://127.0.0.1:5173"}


class FakeMal:
    def get_json(self, url, params=None, **_kwargs):
        return {"data": []}


def _finished(client, operation_id: str) -> dict:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        snapshot = client.get(f"/api/operations/{operation_id}").json()
        if snapshot["state"] != "running":
            return snapshot
        time.sleep(0.05)
    raise AssertionError("the operation did not finish")


def test_list_sync_succeeds_and_records_when_it_ran(tmp_path):
    app = create_app(root_override=str(tmp_path))
    services = app.state.container
    services.settings.save(replace(services.settings.load(), client_id="installation-client-id"))
    services.profiles._mal_client = FakeMal()
    fetched = []

    def fetcher(username, access_token, **kwargs):
        fetched.append(username)
        return []

    services.mal_sync._fetcher = fetcher
    with TestClient(app) as client:
        profile = client.post("/api/onboarding/mal-profile", json={"username": "reader_01"}, headers=ORIGIN).json()["profile"]
        started = client.post("/api/operations/list-sync", json={}, headers=ORIGIN)
        assert started.status_code == 202
        snapshot = _finished(client, started.json()["id"])
    assert snapshot["state"] == "succeeded", snapshot.get("error")
    assert fetched == ["reader_01"]
    state_file = services.mal_sync.path(profile["profile_id"])
    assert tmp_path in state_file.parents
    synced_at = services.mal_sync.load(profile["profile_id"]).last_synced_at
    assert synced_at and datetime.fromisoformat(synced_at).tzinfo is not None
