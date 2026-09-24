"""Cover addresses for picks whose catalogue has none.

The installed model catalogue carries no picture URLs, so a feed built from it
showed no artwork. Covers are looked up through MyAnimeList's official API
with the installation's Client ID, once per title, into a shared cache. A
title MyAnimeList has no picture for stays without one: nothing is invented.
"""

from __future__ import annotations

import threading
import time
from dataclasses import replace

from fastapi.testclient import TestClient

from AniRec.api.app import create_app
from AniRec.infrastructure.json_storage import JsonStore
from AniRec.errors import ClientIdRejectedError, NotFoundError
from AniRec.models.domain import Anime, PipelineResult, Recommendation
from AniRec.services.cover_url_service import CoverUrlService

from account_helpers import sign_in_reader


def _feed(*ids, covered=()):
    return PipelineResult(recommendations=tuple(
        Recommendation(anime=Anime(
            title=f"Title {i}", mal_id=i,
            cover_url=f"https://known/{i}.jpg" if i in covered else None,
            large_cover_url=f"https://known/{i}l.jpg" if i in covered else None,
        ), rank=n + 1)
        for n, i in enumerate(ids)
    ))


class FakeMal:
    def __init__(self, pictures=None, fail=None):
        self.pictures = pictures or {}
        self.fail = fail or {}
        self.calls: list[tuple[str, dict, str | None]] = []
        self.lock = threading.Lock()

    def get_json(self, url, *, params=None, client_id=None, **_kwargs):
        mal_id = int(url.rstrip("/").rsplit("/", 1)[1])
        with self.lock:
            self.calls.append((url, dict(params or {}), client_id))
        if mal_id in self.fail:
            raise self.fail[mal_id]
        picture = self.pictures.get(mal_id)
        return {"id": mal_id, **({"main_picture": picture} if picture else {})}


def _covers(result):
    return [(r.anime.cover_url, r.anime.large_cover_url) for r in result.recommendations]


def test_missing_covers_are_looked_up_once_and_cached(tmp_path):
    mal = FakeMal({1: {"medium": "https://cdn/1.jpg", "large": "https://cdn/1l.jpg"},
                   2: {"medium": "https://cdn/2.jpg", "large": "https://cdn/2l.jpg"}})
    service = CoverUrlService(root_override=tmp_path, client=mal)
    filled = service.fill(_feed(1, 2), "installation-id")
    assert _covers(filled) == [("https://cdn/1.jpg", "https://cdn/1l.jpg"), ("https://cdn/2.jpg", "https://cdn/2l.jpg")]
    assert {c[2] for c in mal.calls} == {"installation-id"}
    assert all(c[1] == {"fields": "main_picture"} for c in mal.calls)
    # Everything else about the pick is untouched.
    assert [r.rank for r in filled.recommendations] == [1, 2]
    again = CoverUrlService(root_override=tmp_path, client=mal).fill(_feed(1, 2), "installation-id")
    assert _covers(again) == _covers(filled)
    assert len(mal.calls) == 2


def test_a_pick_that_has_a_cover_is_neither_looked_up_nor_changed(tmp_path):
    mal = FakeMal({2: {"medium": "https://cdn/2.jpg"}})
    filled = CoverUrlService(root_override=tmp_path, client=mal).fill(_feed(1, 2, covered={1}), "id")
    assert filled.recommendations[0].anime.cover_url == "https://known/1.jpg"
    assert [c[0] for c in mal.calls] == ["https://api.myanimelist.net/v2/anime/2"]


def test_a_title_without_a_picture_stays_without_one_and_is_not_asked_again_soon(tmp_path):
    now = [1_000_000.0]
    mal = FakeMal(fail={3: NotFoundError("gone")})
    service = CoverUrlService(root_override=tmp_path, client=mal, clock=lambda: now[0])
    filled = service.fill(_feed(2, 3), "id")
    assert _covers(filled) == [(None, None), (None, None)]
    assert len(mal.calls) == 2
    service.fill(_feed(2, 3), "id")
    assert len(mal.calls) == 2
    now[0] += 31 * 24 * 3600   # a month later MyAnimeList may have one
    service.fill(_feed(2, 3), "id")
    assert len(mal.calls) == 4


def test_a_refused_client_id_stops_the_lookups_and_keeps_the_feed(tmp_path):
    mal = FakeMal(fail={i: ClientIdRejectedError("refused") for i in range(1, 6)})
    service = CoverUrlService(root_override=tmp_path, client=mal, workers=1)
    feed = _feed(1, 2, 3, 4, 5)
    assert service.fill(feed, "bad-id") == feed
    assert len(mal.calls) == 1
    # A refusal is not remembered as "no picture".
    service._client = FakeMal({1: {"medium": "https://cdn/1.jpg"}})
    assert service.fill(_feed(1), "good-id").recommendations[0].anime.cover_url == "https://cdn/1.jpg"


def test_lookups_are_bounded_per_run(tmp_path):
    mal = FakeMal({i: {"medium": f"https://cdn/{i}.jpg"} for i in range(1, 101)})
    service = CoverUrlService(root_override=tmp_path, client=mal, max_lookups=5)
    filled = service.fill(_feed(*range(1, 101)), "id")
    assert len(mal.calls) == 5
    assert sum(1 for c in _covers(filled) if c[0]) == 5
    assert sum(1 for c in _covers(service.fill(_feed(*range(1, 101)), "id")) if c[0]) == 10


def test_without_a_client_id_nothing_is_looked_up(tmp_path):
    mal = FakeMal({1: {"medium": "https://cdn/1.jpg"}})
    feed = _feed(1)
    assert CoverUrlService(root_override=tmp_path, client=mal).fill(feed, "") == feed
    assert mal.calls == []


def test_only_https_picture_addresses_are_kept(tmp_path):
    mal = FakeMal({1: {"medium": "javascript:alert(1)", "large": "http://cdn/1l.jpg"}})
    filled = CoverUrlService(root_override=tmp_path, client=mal).fill(_feed(1), "id")
    assert _covers(filled) == [(None, None)]


def test_a_corrupt_cache_is_treated_as_empty(tmp_path):
    service = CoverUrlService(root_override=tmp_path, client=FakeMal({1: {"medium": "https://cdn/1.jpg"}}))
    service.path.parent.mkdir(parents=True, exist_ok=True)
    service.path.write_text("{not json", encoding="utf-8")
    assert service.fill(_feed(1), "id").recommendations[0].anime.cover_url == "https://cdn/1.jpg"


def test_a_refresh_saves_the_feed_with_its_covers(tmp_path, monkeypatch):
    app = create_app(root_override=str(tmp_path))
    services = app.state.container
    services.settings.save(replace(services.settings.load(), client_id="installation-id"))
    profile = services.profiles.create_profile("reader_01")
    JsonStore().write(profile.to_dict(), services.profiles.directory(profile.profile_id, create=True) / "profile.json")
    services.cover_urls._client = FakeMal({7: {"medium": "https://cdn/7.jpg", "large": "https://cdn/7l.jpg"}})
    monkeypatch.setattr(services.orchestrator, "run_refresh", lambda *a, **k: _feed(7))
    with TestClient(app) as client:
        sign_in_reader(client, profile.profile_id)
        started = client.post("/api/operations/refresh", json={}, headers={"Origin": "http://127.0.0.1:5173"})
        assert started.status_code == 202, started.text
        deadline = time.monotonic() + 10
        while client.get(f"/api/operations/{started.json()['id']}").json()["state"] == "running":
            assert time.monotonic() < deadline
            time.sleep(0.05)
    saved = services.results.load(profile.profile_id)
    assert saved.recommendations[0].anime.cover_url == "https://cdn/7.jpg"


def test_a_refresh_that_finds_the_feed_current_still_fills_its_covers(tmp_path, monkeypatch):
    app = create_app(root_override=str(tmp_path))
    services = app.state.container
    services.settings.save(replace(services.settings.load(), client_id="installation-id"))
    profile = services.profiles.create_profile("reader_01")
    JsonStore().write(profile.to_dict(), services.profiles.directory(profile.profile_id, create=True) / "profile.json")
    services.results.save(profile.profile_id, _feed(8))   # built before covers were looked up
    services.cover_urls._client = FakeMal({8: {"medium": "https://cdn/8.jpg"}})
    monkeypatch.setattr(services.orchestrator, "run_refresh",
                        lambda *a, **k: PipelineResult(user_stats={"feed_refresh": "current"}))
    with TestClient(app) as client:
        sign_in_reader(client, profile.profile_id)
        started = client.post("/api/operations/refresh", json={}, headers={"Origin": "http://127.0.0.1:5173"})
        deadline = time.monotonic() + 10
        while client.get(f"/api/operations/{started.json()['id']}").json()["state"] == "running":
            assert time.monotonic() < deadline
            time.sleep(0.05)
    assert services.results.load(profile.profile_id).recommendations[0].anime.cover_url == "https://cdn/8.jpg"
