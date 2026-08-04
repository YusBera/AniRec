from __future__ import annotations

import requests
import pytest

import anime_data
from core.mal_mapping import ANIME_FIELDS
from errors import InvalidResponseError, NetworkError


class FakeResponse:
    def __init__(self, payload=None, error=None, json_error=None):
        self.payload = payload
        self.error = error
        self.json_error = json_error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.payload


def test_top_anime_uses_500_item_offset_pages(monkeypatch):
    calls = []

    def fake_get(url, params, headers, timeout):
        calls.append((url, params, headers, timeout))
        offset = params["offset"]
        return FakeResponse(
            {
                "data": [
                    {
                        "node": {
                            "id": offset + 1,
                            "title": f"Fixture {offset}",
                            "genres": [{"name": "Action"}],
                            "mean": 8.5,
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(anime_data.requests, "get", fake_get)

    result = anime_data.get_top_anime(limit=750, access_token="fake-access-token")

    assert result["Title"].tolist() == ["Fixture 0", "Fixture 500"]
    assert [call[1]["limit"] for call in calls] == [500, 250]
    assert [call[1]["offset"] for call in calls] == [0, 500]
    assert all(call[1]["fields"] == ANIME_FIELDS for call in calls)
    assert all(call[3] == 15 for call in calls)


def test_top_anime_empty_response_returns_empty_frame(monkeypatch):
    monkeypatch.setattr(
        anime_data.requests,
        "get",
        lambda *args, **kwargs: FakeResponse({"data": []}),
    )
    assert anime_data.get_top_anime(limit=1).empty


@pytest.mark.parametrize(
    "error",
    [
        requests.HTTPError("fixture http error"),
        requests.Timeout("fixture timeout"),
        requests.ConnectionError("fixture connection error"),
    ],
)
def test_top_anime_propagates_request_errors(monkeypatch, error):
    def failing_get(*args, **kwargs):
        raise error

    monkeypatch.setattr(anime_data.requests, "get", failing_get)
    with pytest.raises(NetworkError):
        anime_data.get_top_anime(limit=1)


def test_top_anime_propagates_invalid_json(monkeypatch):
    monkeypatch.setattr(
        anime_data.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(json_error=ValueError("invalid fixture json")),
    )
    with pytest.raises(InvalidResponseError, match="invalid JSON"):
        anime_data.get_top_anime(limit=1)


def test_top_anime_skips_malformed_records_without_losing_valid_rows(monkeypatch):
    monkeypatch.setattr(
        anime_data.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(
            {
                "data": [
                    {},
                    {"node": {}},
                        {
                            "node": {
                                "id": 10,
                                "title": "Valid Fixture",
                            "genres": [],
                            "mean": None,
                        }
                    },
                ]
            }
        ),
    )
    assert anime_data.get_top_anime(limit=1)["Title"].tolist() == ["Valid Fixture"]
