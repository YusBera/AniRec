from __future__ import annotations

import user_data
from core.mal_mapping import ANIME_FIELDS


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_completed_anime_follows_paging_next_and_maps_list_status(monkeypatch):
    calls = []
    responses = iter(
        [
            FakeResponse(
                {
                    "data": [
                        {
                                "node": {
                                    "id": 1,
                                    "title": "Alpha Show",
                                "genres": [{"name": "Action"}],
                            },
                            "list_status": {"score": 8},
                        }
                    ],
                    "paging": {"next": "https://fixture.invalid/page-2"},
                }
            ),
            FakeResponse(
                {
                    "data": [
                        {
                            "node": {"id": 2, "title": "Beta Show", "genres": []},
                            "list_status": {},
                        }
                    ],
                    "paging": {},
                }
            ),
        ]
    )

    def fake_get(url, headers, params, timeout):
        calls.append((url, headers, params, timeout))
        return next(responses)

    monkeypatch.setattr(user_data.requests, "get", fake_get)

    result = user_data.get_user_completed_animes("fixture-user", "fake-access-token")

    assert result[["Anime ID", "Title", "Genres", "Status", "User Score"]].to_dict(
        "records"
    ) == [
        {
            "Anime ID": 1,
            "Title": "Alpha Show",
            "Genres": ["Action"],
            "Status": "Completed",
            "User Score": 8,
        },
        {
            "Anime ID": 2,
            "Title": "Beta Show",
            "Genres": [],
            "Status": "Completed",
            "User Score": 0,
        },
    ]
    assert calls[0][2] == {
        "status": "completed",
        "fields": f"list_status,{ANIME_FIELDS}",
        "limit": 1000,
    }
    assert calls[1][0] == "https://fixture.invalid/page-2"
    assert calls[1][2] is None
    assert all(call[3] == 15 for call in calls)


def test_completed_anime_empty_response_returns_empty_frame(monkeypatch):
    monkeypatch.setattr(
        user_data.requests,
        "get",
        lambda *args, **kwargs: FakeResponse({"data": [], "paging": {}}),
    )
    assert user_data.get_user_completed_animes("fixture-user", "fake-token").empty


def test_include_nsfw_fetches_full_list_and_locally_keeps_completed_rewatches(
    monkeypatch,
):
    calls = []

    def fake_get(url, headers, params, timeout):
        calls.append(params)
        return FakeResponse(
            {
                "data": [
                    {
                        "node": {"id": 1, "title": "Completed", "genres": []},
                        "list_status": {
                            "status": "completed",
                            "is_rewatching": True,
                            "score": 8,
                        },
                    },
                    {
                        "node": {"id": 2, "title": "Watching", "genres": []},
                        "list_status": {"status": "watching", "score": 0},
                    },
                ],
                "paging": {},
            }
        )

    monkeypatch.setattr(user_data.requests, "get", fake_get)

    result = user_data.get_user_completed_animes(
        "fixture-user", "fake-token", include_nsfw=True
    )

    assert result["Title"].tolist() == ["Completed"]
    assert calls == [
        {
            "fields": f"list_status,{ANIME_FIELDS}",
            "limit": 1000,
            "nsfw": "true",
        }
    ]


def test_completed_anime_skips_malformed_records(monkeypatch):
    monkeypatch.setattr(
        user_data.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(
            {
                "data": [
                    {},
                    {"node": {}},
                    {"node": {"id": 10, "title": "Valid Fixture", "genres": []}},
                ],
                "paging": {},
            }
        ),
    )
    result = user_data.get_user_completed_animes("fixture-user", "fake-token")
    assert result["Title"].tolist() == ["Valid Fixture"]
