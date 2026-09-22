import json
import sqlite3
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest

from AniRec.services.recommendation_event_service import (
    RecommendationEventService,
    ExposureTracker,
    activity_model_version,
    feed_fingerprint,
)


def event(**overrides):
    return dict(request_id=str(uuid4()), feed_id="a" * 64, action="impression",
                mal_id=1, position=1, model_rank=3, surface="web_cards", **overrides)


def test_opt_in_idempotence_and_clear(tmp_path):
    service = RecommendationEventService(tmp_path)
    payload = event()
    assert not service.record("profile", **payload)
    assert not (tmp_path / "profiles").exists()
    service.set_enabled("profile", True)
    assert service.record("profile", **payload)
    assert not service.record("profile", **payload)
    payload["action"] = "detail_open"
    payload["event_id"] = str(uuid4())
    assert service.record("profile", **payload)
    assert not service.record("profile", **payload)
    service.set_enabled("profile", False)
    payload["event_id"] = str(uuid4())
    assert not service.record("profile", **payload)
    service.clear("profile")
    with sqlite3.connect(tmp_path / "profiles/profile/recommendation_events.sqlite") as conn:
        assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0


def test_event_allowlist_and_privacy(tmp_path):
    service = RecommendationEventService(tmp_path)
    service.set_enabled("profile", True)
    p = event()
    p["action"] = "PRIVACY_BAIT"
    with pytest.raises(ValueError):
        service.record("profile", **p)
    p["action"] = "watch_later_add"
    assert service.record("profile", **p)
    db = tmp_path / "profiles/profile/recommendation_events.sqlite"
    with sqlite3.connect(db) as conn:
        names = {row[1] for row in conn.execute("PRAGMA table_info(events)")}
        assert not names & {"username", "profile_id", "title", "url", "notes"}
    assert b"PRIVACY_BAIT" not in db.read_bytes()


def test_feed_and_event_are_attributed_to_the_actual_ranking_engine(tmp_path):
    service = RecommendationEventService(tmp_path)
    service.set_enabled("profile", True)
    version = activity_model_version(
        {"ranking_engine_id": "sasrec-onnx", "ranking_engine_version": "65e485aa95f9"}
    )
    models = [SimpleNamespace(mal_id=1, rank=1, personal_match=0.0)]
    assert feed_fingerprint(models, version) != feed_fingerprint(models, "heuristic:1")
    assert service.record("profile", model_version=version, **event())
    with sqlite3.connect(tmp_path / "profiles/profile/recommendation_events.sqlite") as conn:
        assert conn.execute("SELECT model_version FROM events").fetchone()[0] == version


def test_visibility_requires_continuous_dwell_and_acknowledgement():
    tracker = ExposureTracker()
    assert tracker.update([1], 0) == []
    assert tracker.update([], .8) == []
    assert tracker.update([1], 1) == []
    assert tracker.update([1], 1.9) == []
    assert tracker.update([1], 2.1) == [1]
    tracker.acknowledge(1)
    assert tracker.update([1], 8) == []
    tracker.reset()
    assert tracker.update([1], 9) == []


def test_logging_failure_does_not_fail_action(tmp_path, monkeypatch):
    service = RecommendationEventService(tmp_path)
    service.set_enabled("profile", True)
    def fail(*a):
        raise sqlite3.OperationalError("locked")
    monkeypatch.setattr(service, "_connect", fail)
    assert not service.record("profile", **event())


def test_native_demo_is_never_logged(tmp_path):
    from AniRec.gui_main import create_application
    from AniRec.gui.recommendation_page import RecommendationExplorerPage
    from AniRec.services import RecommendationStateService
    from AniRec.models import Anime, Recommendation
    app = create_application([])
    page = RecommendationExplorerPage(state_service=RecommendationStateService(root_override=tmp_path))
    page.set_recommendations([Recommendation(Anime("Example", mal_id=1), match_score=80, rank=1)])
    page.set_ephemeral(True)
    assert not page._record_activity(page.visible_models[0], "detail_open")
    page.close()
    page.deleteLater()
    app.processEvents()


def test_retention_is_bounded(tmp_path, monkeypatch):
    from AniRec.services import recommendation_event_service as module
    monkeypatch.setattr(module, "MAX_EVENTS", 3)
    service = RecommendationEventService(tmp_path)
    service.set_enabled("profile", True)
    for _ in range(5):
        assert service.record("profile", **event())
    with sqlite3.connect(tmp_path / "profiles/profile/recommendation_events.sqlite") as conn:
        assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 3


def test_api_activity_is_opt_in_and_rejects_stale_or_unknown_items(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from AniRec.api import create_app
    from AniRec.api.container import build_container
    services = build_container(tmp_path)
    profile = SimpleNamespace(profile_id="profile", username="PRIVACY_BAIT")
    monkeypatch.setattr(services.profiles, "active_profile", lambda: profile)
    sample = services.samples.load()
    services.results.save(
        "profile",
        replace(
            sample,
            user_stats={
                **sample.user_stats,
                "ranking_engine_id": "sasrec-onnx",
                "ranking_engine_version": "65e485aa95f9",
            },
        ),
    )
    with TestClient(create_app(container=services)) as client:
        feed = client.get("/api/discover/feed").json()
        first = feed["recommendations"][0]
        payload = event()
        payload.update(profile_id="profile", event_id=str(uuid4()), feed_id=feed["activity_feed_id"], mal_id=first["mal_id"])
        assert client.post("/api/discover/activity", json=payload).json() == {"recorded": False}
        assert client.post("/api/discover/activity/settings", json={"enabled": True}).json()["enabled"]
        assert client.post("/api/discover/activity", json=payload).json()["recorded"]
        database = tmp_path / "profiles/profile/recommendation_events.sqlite"
        with sqlite3.connect(database) as conn:
            assert conn.execute("SELECT model_version FROM events").fetchone()[0] == "sasrec-onnx:65e485aa95f9"
        assert not client.post("/api/discover/activity", json=payload).json()["recorded"]
        payload["event_id"] = str(uuid4())
        payload["profile_id"] = "previous-profile"
        assert not client.post("/api/discover/activity", json=payload).json()["recorded"]
        payload["profile_id"] = "profile"
        payload["mal_id"] = 999999999
        assert not client.post("/api/discover/activity", json=payload).json()["recorded"]
        payload["mal_id"] = first["mal_id"]
        payload["feed_id"] = "b" * 64
        assert not client.post("/api/discover/activity", json=payload).json()["recorded"]
        payload["username"] = "PRIVACY_BAIT"
        assert client.post("/api/discover/activity", json=payload).status_code == 422
        assert client.delete("/api/discover/activity").status_code == 200


def test_native_visible_impressions_and_saved_actions(tmp_path, monkeypatch):
    from AniRec.gui_main import create_application
    from AniRec.gui import recommendation_page as module
    from AniRec.services import RecommendationStateService
    from AniRec.models import Anime, Recommendation
    app = create_application([])
    page = module.RecommendationExplorerPage(state_service=RecommendationStateService(root_override=tmp_path))
    page.set_profile("profile")
    page.set_recommendations([Recommendation(Anime(f"Example {i}", mal_id=i), match_score=80, rank=i) for i in range(1, 31)])
    page.resize(1200, 800)
    page.show()
    page.activateWindow()
    app.processEvents()
    page._activity_timer.stop()
    page.set_activity_model_version("sasrec-onnx:65e485aa95f9")
    page.activity.set_enabled("profile", True)
    now = [0.]
    monkeypatch.setattr(module, "monotonic", lambda: now[0])
    monkeypatch.setattr(page, "isActiveWindow", lambda: True)
    page._poll_activity()
    now[0] = 1.2
    page._poll_activity()
    db = tmp_path / "profiles/profile/recommendation_events.sqlite"
    with sqlite3.connect(db) as conn:
        n = conn.execute("SELECT COUNT(*) FROM events WHERE action='impression'").fetchone()[0]
        assert 0 < n < 30, "only viewport-visible cards may generate impressions"
    page._poll_activity()
    page._toggle_watch_later(page.visible_models[0])
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM events WHERE action='impression'").fetchone()[0] == n
        assert conn.execute("SELECT COUNT(*) FROM events WHERE action='watch_later_add'").fetchone()[0] == 1
        assert {row[0] for row in conn.execute("SELECT DISTINCT model_version FROM events")} == {"sasrec-onnx:65e485aa95f9"}
    page.hide()
    now[0] = 9.
    page._poll_activity()
    page.close()
    page.deleteLater()
    app.processEvents()



def test_malformed_setting_fails_closed_and_disabled_history_expires(tmp_path):
    service = RecommendationEventService(tmp_path)
    service.set_enabled("profile", True)
    assert service.record("profile", **event())
    root = tmp_path / "profiles/profile"
    (root / "recommendation_activity.json").write_text("[]", encoding="utf-8")
    with sqlite3.connect(root / "recommendation_events.sqlite") as conn:
        conn.execute("UPDATE events SET recorded_at=1")
    # A fresh client expires stale rows even when collection is disabled.
    assert not RecommendationEventService(tmp_path).status("profile")["enabled"]
    with sqlite3.connect(root / "recommendation_events.sqlite") as conn:
        assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0


# --- Goal 3: attribution to the exact ranking, rank and selection -------------


def _attributed_result(sample):
    """The sample feed, stamped the way a generated feed is: rows 1-3 were
    selected from engine ranks 1, 4 and 2 of ranking ``ab12…`` at
    adventurousness 7."""
    from AniRec.models import Recommendation

    stamped = []
    for index, item in enumerate(sample.recommendations[:3]):
        stamped.append(
            replace(
                item,
                rank=index + 1,
                model_rank=(1, 4, 2)[index],
                ranked_candidate_count=500,
                ranking_id="ab12" * 6,
                selection_policy="rank-diversity-v1",
                adventurousness=7,
            )
        )
    assert all(isinstance(item, Recommendation) for item in stamped)
    return replace(
        sample,
        recommendations=tuple(stamped),
        user_stats={
            **sample.user_stats,
            "ranking_engine_id": "heuristic",
            "ranking_engine_version": "1",
            "eligibility_catalog_version": "onnx-v3:aaa:bbb:ccc",
        },
    )


def test_api_event_is_attributed_to_engine_rank_feed_position_and_selection(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from AniRec.api import create_app
    from AniRec.api.container import build_container

    services = build_container(tmp_path)
    monkeypatch.setattr(
        services.profiles, "active_profile",
        lambda: SimpleNamespace(profile_id="profile", username="someone"),
    )
    services.results.save("profile", _attributed_result(services.samples.load()))
    with TestClient(create_app(container=services)) as client:
        client.post("/api/discover/activity/settings", json={"enabled": True})
        feed = client.get("/api/discover/feed").json()
        second = feed["recommendations"][1]
        payload = event()
        payload.update(
            profile_id="profile", event_id=str(uuid4()), feed_id=feed["activity_feed_id"],
            mal_id=second["mal_id"], action="detail_open", position=2,
            # A client cannot choose the rank recorded against its event.
            model_rank=99,
        )
        assert client.post("/api/discover/activity", json=payload).json()["recorded"]

    database = tmp_path / "profiles/profile/recommendation_events.sqlite"
    with sqlite3.connect(database) as conn:
        row = conn.execute(
            """SELECT model_rank, feed_rank, position, ranking_id, selection_policy,
                      adventurousness, schema_version, model_version, catalog_version
               FROM events"""
        ).fetchone()
    assert row == (
        4, 2, 2, "ab12" * 6, "rank-diversity-v1", 7, 2, "heuristic:1", "onnx-v3:aaa:bbb:ccc"
    )


def test_version_one_activity_store_is_migrated_in_place(tmp_path):
    root = tmp_path / "profiles" / "profile"
    root.mkdir(parents=True)
    with sqlite3.connect(root / "recommendation_events.sqlite") as conn:
        conn.execute("""CREATE TABLE events (
            event_id TEXT PRIMARY KEY, recorded_at INTEGER NOT NULL,
            request_id TEXT NOT NULL, feed_id TEXT NOT NULL, model_version TEXT NOT NULL,
            action TEXT NOT NULL, mal_id INTEGER NOT NULL, position INTEGER NOT NULL,
            model_rank INTEGER, surface TEXT NOT NULL, schema_version INTEGER NOT NULL DEFAULT 1
        )""")
        conn.execute(
            "INSERT INTO events VALUES (?, strftime('%s','now'), ?, ?, 'legacy', 'impression', 5, 1, 1, 'web_cards', 1)",
            (str(uuid4()), str(uuid4()), "c" * 64),
        )
    service = RecommendationEventService(tmp_path)
    service.set_enabled("profile", True)
    assert service.record(
        "profile", ranking_id="ab12" * 6, feed_rank=1, selection_policy="rank-diversity-v1",
        adventurousness=5, **event(),
    )
    with sqlite3.connect(root / "recommendation_events.sqlite") as conn:
        rows = conn.execute(
            "SELECT model_version, schema_version, ranking_id, feed_rank FROM events ORDER BY schema_version"
        ).fetchall()
    # The version 1 row keeps its data with NULL attribution; the new row is v2.
    assert rows[0] == ("legacy", 1, None, None)
    assert rows[1][1:] == (2, "ab12" * 6, 1)


def test_invalid_attribution_values_are_rejected(tmp_path):
    service = RecommendationEventService(tmp_path)
    service.set_enabled("profile", True)
    for bad in (
        {"ranking_id": "NOT-HEX"},
        {"feed_rank": 0},
        {"adventurousness": 11},
        {"selection_policy": ""},
    ):
        with pytest.raises(ValueError):
            service.record("profile", **event(), **bad)


def test_feed_fingerprint_tracks_ranking_and_selection_not_the_retired_percentage():
    base = dict(mal_id=1, rank=1, fit_rank=4, ranking_id="ab" * 12,
                selection_policy="rank-diversity-v1", adventurousness=5)
    reference = feed_fingerprint([SimpleNamespace(**base, personal_match=10.0)])
    assert feed_fingerprint([SimpleNamespace(**base, personal_match=90.0)]) == reference
    for change in ({"ranking_id": "cd" * 12}, {"fit_rank": 5}, {"adventurousness": 6}):
        assert feed_fingerprint([SimpleNamespace(**{**base, **change})]) != reference
