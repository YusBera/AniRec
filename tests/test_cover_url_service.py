"""Cover addresses for picks whose catalogue has none.

The installed model catalogue carries no picture URLs, so a feed built from it
showed no artwork. Covers are looked up through MyAnimeList's official API
with the installation's Client ID, once per title, into a shared cache. A
title MyAnimeList has no picture for stays without one: nothing is invented.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from fastapi.testclient import TestClient

from AniRec.api.app import create_app
from AniRec.infrastructure.json_storage import JsonStore
from AniRec.errors import ClientIdRejectedError, NotFoundError
from AniRec.models.domain import Anime, PipelineResult, Recommendation
from AniRec.services.cover_url_service import CoverUrlService

from account_helpers import sign_in_reader


def _feed(*ids, covered=(), scored=()):
    return PipelineResult(recommendations=tuple(
        Recommendation(anime=Anime(
            title=f"Title {i}", mal_id=i,
            cover_url=f"https://known/{i}.jpg" if i in covered else None,
            large_cover_url=f"https://known/{i}l.jpg" if i in covered else None,
            mean_score=8.0 if i in scored else None,
        ), rank=n + 1)
        for n, i in enumerate(ids)
    ))


class FakeMal:
    def __init__(self, pictures=None, fail=None, means=None):
        self.pictures = pictures or {}
        self.fail = fail or {}
        self.means = means or {}
        self.calls: list[tuple[str, dict, str | None]] = []
        self.lock = threading.Lock()

    def get_json(self, url, *, params=None, client_id=None, **_kwargs):
        mal_id = int(url.rstrip("/").rsplit("/", 1)[1])
        with self.lock:
            self.calls.append((url, dict(params or {}), client_id))
        if mal_id in self.fail:
            raise self.fail[mal_id]
        picture = self.pictures.get(mal_id)
        return {
            "id": mal_id,
            **({"main_picture": picture} if picture else {}),
            **({"mean": self.means[mal_id]} if mal_id in self.means else {}),
        }


def _covers(result):
    return [(r.anime.cover_url, r.anime.large_cover_url) for r in result.recommendations]


def test_missing_covers_are_looked_up_once_and_cached(tmp_path):
    mal = FakeMal({1: {"medium": "https://cdn/1.jpg", "large": "https://cdn/1l.jpg"},
                   2: {"medium": "https://cdn/2.jpg", "large": "https://cdn/2l.jpg"}})
    service = CoverUrlService(root_override=tmp_path, client=mal)
    filled = service.fill(_feed(1, 2), "installation-id")
    assert _covers(filled) == [("https://cdn/1.jpg", "https://cdn/1l.jpg"), ("https://cdn/2.jpg", "https://cdn/2l.jpg")]
    assert {c[2] for c in mal.calls} == {"installation-id"}
    assert all(c[1] == {"fields": "main_picture,mean"} for c in mal.calls)
    # Everything else about the pick is untouched.
    assert [r.rank for r in filled.recommendations] == [1, 2]
    again = CoverUrlService(root_override=tmp_path, client=mal).fill(_feed(1, 2), "installation-id")
    assert _covers(again) == _covers(filled)
    assert len(mal.calls) == 2


def test_a_pick_that_has_a_cover_and_score_is_neither_looked_up_nor_changed(tmp_path):
    mal = FakeMal({2: {"medium": "https://cdn/2.jpg"}})
    filled = CoverUrlService(root_override=tmp_path, client=mal).fill(_feed(1, 2, covered={1}, scored={1}), "id")
    assert filled.recommendations[0].anime.cover_url == "https://known/1.jpg"
    assert [c[0] for c in mal.calls] == ["https://api.myanimelist.net/v2/anime/2"]


def test_missing_mal_score_is_filled_even_when_cover_is_already_present(tmp_path):
    mal = FakeMal(means={1: 7.42})
    service = CoverUrlService(root_override=tmp_path, client=mal)
    feed = _feed(1, covered={1})
    filled = service.fill(feed, "id")
    assert filled.recommendations[0].anime.mean_score == 7.42
    assert filled.recommendations[0].anime.cover_url == feed.recommendations[0].anime.cover_url
    assert mal.calls[0][1] == {"fields": "main_picture,mean"}
    assert service.fill(feed, "id").recommendations[0].anime.mean_score == 7.42
    assert len(mal.calls) == 1


def test_enriched_score_is_refetched_after_a_month_even_on_a_saved_feed(tmp_path):
    now = [1_000_000.0]
    mal = FakeMal(means={1: 7.42})
    service = CoverUrlService(root_override=tmp_path, client=mal, clock=lambda: now[0])
    first = service.fill(_feed(1, covered={1}), "id")
    saved = PipelineResult.from_dict(first.to_dict())
    assert saved.recommendations[0].anime.mean_score == 7.42
    assert service.fill(saved, "id").recommendations[0].anime.mean_score == 7.42
    assert len(mal.calls) == 1

    now[0] += 31 * 24 * 3600
    mal.means[1] = 7.8
    updated = service.fill(saved, "id")
    assert updated.recommendations[0].anime.mean_score == 7.8
    assert len(mal.calls) == 2


def test_catalogue_score_keeps_precedence_after_cache_score_expires(tmp_path):
    now = [1_000_000.0]
    mal = FakeMal(means={1: 7.42})
    service = CoverUrlService(root_override=tmp_path, client=mal, clock=lambda: now[0])
    feed = _feed(1, covered={1}, scored={1})
    assert service.fill(feed, "id").recommendations[0].anime.mean_score == 8.0
    now[0] += 31 * 24 * 3600
    assert service.fill(feed, "id").recommendations[0].anime.mean_score == 8.0
    assert mal.calls == []


def test_existing_cover_cache_gets_missing_score_without_reasking_again(tmp_path):
    mal = FakeMal(means={2: 8.1})
    service = CoverUrlService(root_override=tmp_path, client=mal)
    service.path.parent.mkdir(parents=True, exist_ok=True)
    JsonStore().write({"2": {"medium": "https://cdn/2.jpg", "large": None, "checked_at": 1_000_000}}, service.path)
    filled = service.fill(_feed(2), "id")
    assert filled.recommendations[0].anime.cover_url == "https://cdn/2.jpg"
    assert filled.recommendations[0].anime.mean_score == 8.1
    assert len(mal.calls) == 1
    assert service.fill(_feed(2), "id").recommendations[0].anime.mean_score == 8.1
    assert len(mal.calls) == 1


def test_cached_artwork_remains_available_without_a_client_id(tmp_path):
    mal = FakeMal({})
    service = CoverUrlService(root_override=tmp_path, client=mal)
    service.path.parent.mkdir(parents=True, exist_ok=True)
    JsonStore().write({"1": {"medium": "https://cdn/1.jpg", "checked_at": time.time()}}, service.path)
    assert service.fill(_feed(1), None).recommendations[0].anime.cover_url == "https://cdn/1.jpg"
    assert mal.calls == []


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


def test_invalid_community_score_is_not_shown_or_cached_as_a_rating(tmp_path):
    mal = FakeMal(means={1: 0, 2: 11, 3: "NaN"})
    service = CoverUrlService(root_override=tmp_path, client=mal)
    filled = service.fill(_feed(1, 2, 3), "id")
    assert [r.anime.mean_score for r in filled.recommendations] == [None, None, None]
    assert len(mal.calls) == 3
    service.fill(_feed(1, 2, 3), "id")
    assert len(mal.calls) == 3


def test_a_corrupt_cache_is_treated_as_empty(tmp_path):
    service = CoverUrlService(root_override=tmp_path, client=FakeMal({1: {"medium": "https://cdn/1.jpg"}}))
    service.path.parent.mkdir(parents=True, exist_ok=True)
    service.path.write_text("{not json", encoding="utf-8")
    assert service.fill(_feed(1), "id").recommendations[0].anime.cover_url == "https://cdn/1.jpg"


def test_corrupt_cached_timestamps_do_not_prevent_metadata_recovery(tmp_path):
    mal = FakeMal(means={1: 7.1})
    service = CoverUrlService(root_override=tmp_path, client=mal)
    service.path.parent.mkdir(parents=True, exist_ok=True)
    JsonStore().write({"1": {"checked_at": "broken", "score_checked_at": []}}, service.path)
    assert service.fill(_feed(1), "id").recommendations[0].anime.mean_score == 7.1


def test_oversized_cached_numbers_are_treated_as_unavailable(tmp_path):
    mal = FakeMal(means={1: 7.1})
    service = CoverUrlService(root_override=tmp_path, client=mal)
    service.path.parent.mkdir(parents=True, exist_ok=True)
    JsonStore().write({"1": {"checked_at": 10**400, "score_checked_at": 10**400}}, service.path)
    assert service.fill(_feed(1), "id").recommendations[0].anime.mean_score == 7.1
    JsonStore().write({"1": {"mean": 10**400, "score_checked_at": time.time()}}, service.path)
    assert service.cached(_feed(1)).recommendations[0].anime.mean_score is None


def test_untimestamped_cached_score_is_not_used_after_a_fresh_lookup(tmp_path):
    mal = FakeMal({1: {"medium": "https://cdn/1.jpg"}})
    service = CoverUrlService(root_override=tmp_path, client=mal)
    service.path.parent.mkdir(parents=True, exist_ok=True)
    JsonStore().write({"1": {"medium": "javascript:bad()", "mean": 8.2}}, service.path)
    anime = service.fill(_feed(1), "id").recommendations[0].anime
    assert anime.cover_url == "https://cdn/1.jpg"
    assert anime.mean_score is None


def test_a_refresh_saves_the_feed_with_its_covers(tmp_path, monkeypatch):
    app = create_app(root_override=str(tmp_path))
    services = app.state.container
    services.settings.save(replace(services.settings.load(), client_id="installation-id"))
    profile = services.profiles.create_profile("reader_01")
    JsonStore().write(profile.to_dict(), services.profiles.directory(profile.profile_id, create=True) / "profile.json")
    services.cover_urls._client = FakeMal(
        {7: {"medium": "https://cdn/7.jpg", "large": "https://cdn/7l.jpg"}}, means={7: 7.42}
    )
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
    assert saved.recommendations[0].anime.mean_score == 7.42


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


def test_visible_page_metadata_uses_saved_picks_and_reappears_on_feed_reload(tmp_path):
    app = create_app(root_override=str(tmp_path))
    services = app.state.container
    services.settings.save(replace(services.settings.load(), client_id="installation-id"))
    profile = services.profiles.create_profile("reader_01")
    JsonStore().write(profile.to_dict(), services.profiles.directory(profile.profile_id, create=True) / "profile.json")
    services.results.save(profile.profile_id, _feed(1, 2, 3))
    mal = FakeMal({2: {"medium": "https://cdn/2.jpg"}}, means={2: 7.42})
    services.cover_urls._client = mal

    with TestClient(app) as client:
        sign_in_reader(client, profile.profile_id)
        response = client.post(
            "/api/discover/page-metadata",
            json={"mal_ids": [2, 999]},
            headers={"Origin": "http://127.0.0.1:5173"},
        )
        assert response.status_code == 200, response.text
        assert [item["mal_id"] for item in response.json()] == [2]
        assert response.json()[0]["mal_score"] == 7.42
        reloaded = client.get("/api/discover/feed").json()
        assert reloaded["recommendations"][1]["cover_url"] == "https://cdn/2.jpg"
        assert reloaded["recommendations"][1]["mal_score"] == 7.42

    assert [int(call[0].rsplit("/", 1)[1]) for call in mal.calls] == [2]


def test_evidence_posters_fetch_only_three_strongest_positive_titles_and_reuse_cache(tmp_path):
    mal = FakeMal({
        21: {"medium": "https://cdn/21.jpg"},
        22: {"medium": "https://cdn/22.jpg"},
        23: {"medium": "https://cdn/23.jpg"},
    })
    service = CoverUrlService(root_override=tmp_path, client=mal)
    rec = replace(_feed(7).recommendations[0], explanation={
        "method": "counterfactual-removal",
        "influences": [
            {"mal_id": 24, "value": -9.0},
            {"mal_id": 23, "value": 0.3},
            {"mal_id": 22, "value": 0.8},
            {"mal_id": 25, "value": 0.1},
            {"mal_id": 21, "value": 1.2},
        ],
    })
    assert service.evidence_posters(rec, "installation-id") == [
        (21, "https://cdn/21.jpg"),
        (22, "https://cdn/22.jpg"),
        (23, "https://cdn/23.jpg"),
    ]
    assert [int(call[0].rsplit("/", 1)[1]) for call in mal.calls] == [21, 22, 23]
    assert service.evidence_posters(rec, "installation-id")[0] == (21, "https://cdn/21.jpg")
    assert len(mal.calls) == 3


def test_evidence_posters_ignore_malformed_saved_influences(tmp_path):
    mal = FakeMal({})
    service = CoverUrlService(root_override=tmp_path, client=mal)
    rec = replace(_feed(7).recommendations[0], explanation={
        "method": "counterfactual-removal", "influences": 42,
    })
    assert service.evidence_posters(rec, "installation-id") == []
    assert mal.calls == []


def test_imported_evidence_posters_do_not_wait_for_page_metadata_lookups(tmp_path):
    entered, release = threading.Event(), threading.Event()

    class BlockingMal(FakeMal):
        def get_json(self, url, *, params=None, client_id=None, **kwargs):
            entered.set()
            assert release.wait(5)
            return super().get_json(url, params=params, client_id=client_id, **kwargs)

    service = CoverUrlService(root_override=tmp_path, client=BlockingMal({7: {"medium": "https://cdn/7.jpg"}}))
    profile_directory = tmp_path / "reader"
    profile_directory.mkdir()
    (profile_directory / "completed_anime.csv").write_text(
        "Anime ID,Picture URL\n21,https://cdn/21-imported.jpg\n", encoding="utf-8",
    )
    rec = replace(_feed(8).recommendations[0], explanation={
        "method": "counterfactual-removal", "influences": [{"mal_id": 21, "value": 0.8}],
    })
    with ThreadPoolExecutor(max_workers=2) as pool:
        slow = pool.submit(service.fill, _feed(7), "installation-id")
        assert entered.wait(2)
        fast = pool.submit(service.evidence_posters, rec, "installation-id", profile_directory=profile_directory)
        try:
            assert fast.result(timeout=0.75) == [(21, "https://cdn/21-imported.jpg")]
        finally:
            release.set()
        assert slow.result(timeout=5).recommendations[0].anime.cover_url == "https://cdn/7.jpg"


def test_evidence_artwork_is_scoped_to_saved_pick_and_ranking(tmp_path):
    app = create_app(root_override=str(tmp_path))
    services = app.state.container
    services.settings.save(replace(services.settings.load(), client_id="installation-id"))
    profile_a = services.profiles.create_profile("reader_a")
    profile_b = services.profiles.create_profile("reader_b")
    for profile in (profile_a, profile_b):
        JsonStore().write(profile.to_dict(), services.profiles.directory(profile.profile_id, create=True) / "profile.json")
    rec = replace(_feed(7).recommendations[0], ranking_id="ranking-a", explanation={
        "method": "counterfactual-removal",
        "influences": [{"mal_id": 21, "value": 0.8}],
    })
    services.results.save(profile_a.profile_id, PipelineResult(recommendations=(rec,)))
    services.results.save(profile_b.profile_id, _feed(8))
    (services.profiles.directory(profile_a.profile_id) / "completed_anime.csv").write_text(
        "Anime ID,Picture URL,Large Picture URL\n"
        "21,https://cdn/21-imported.jpg,https://cdn/21-large.jpg\n",
        encoding="utf-8",
    )
    mal = FakeMal({21: {"medium": "https://cdn/21.jpg"}})
    services.cover_urls._client = mal
    origin = {"Origin": "http://127.0.0.1:5173"}

    with TestClient(app) as client:
        sign_in_reader(client, profile_a.profile_id)
        stale = client.post("/api/discover/evidence-artwork", json={"pick_mal_id": 7, "ranking_id": "old"}, headers=origin)
        assert stale.status_code == 409
        found = client.post("/api/discover/evidence-artwork", json={"pick_mal_id": 7, "ranking_id": "ranking-a"}, headers=origin)
        assert found.status_code == 200, found.text
        assert found.json()["posters"] == [{"mal_id": 21, "cover_url": "https://cdn/21-imported.jpg"}]
        sign_in_reader(client, profile_b.profile_id)
        other_reader = client.post("/api/discover/evidence-artwork", json={"pick_mal_id": 7, "ranking_id": "ranking-a"}, headers=origin)
        assert other_reader.status_code == 409
    assert mal.calls == []
