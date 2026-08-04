from __future__ import annotations

import requests
import pytest

from errors import (
    AccessDeniedError,
    AuthError,
    InvalidResponseError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    ServerError,
    CancelledError,
)
from application.pipeline import CancellationToken
from infrastructure.mal_client import MALClient


class FakeResponse:
    def __init__(self, *, status=200, payload=None, headers=None, json_error=None):
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        self._json_error = json_error

    def raise_for_status(self):
        return None

    def json(self):
        if self._json_error:
            raise self._json_error
        return self._payload


@pytest.mark.parametrize(
    ("status", "error_type"),
    [
        (401, AuthError),
        (403, AccessDeniedError),
        (404, NotFoundError),
        (429, RateLimitError),
        (500, ServerError),
        (503, ServerError),
    ],
)
def test_http_statuses_map_to_application_errors(status, error_type):
    client = MALClient(
        http_get=lambda *args, **kwargs: FakeResponse(
            status=status,
            headers={"Retry-After": "30"},
        )
    )
    with pytest.raises(error_type) as captured:
        client.get_json("https://fixture.invalid", access_token="fake-token")
    if status == 429:
        assert captured.value.retry_after_seconds == 30


@pytest.mark.parametrize("retry_after", ["unsafe-date", "-1", "999999", None])
def test_rate_limit_only_carries_safe_retry_after_seconds(retry_after):
    client = MALClient(
        http_get=lambda *args, **kwargs: FakeResponse(
            status=429,
            headers={"Retry-After": retry_after},
        )
    )
    with pytest.raises(RateLimitError) as captured:
        client.get_json("https://fixture.invalid")
    assert captured.value.retry_after_seconds is None


@pytest.mark.parametrize(
    "network_error",
    [requests.Timeout("fixture"), requests.ConnectionError("fixture")],
)
def test_network_failures_map_to_network_error(network_error):
    def fail(*args, **kwargs):
        raise network_error

    with pytest.raises(NetworkError):
        MALClient(http_get=fail).get_json("https://fixture.invalid")


@pytest.mark.parametrize(
    "response",
    [
        FakeResponse(json_error=ValueError("invalid json")),
        FakeResponse(payload=[]),
    ],
)
def test_invalid_json_maps_to_data_error(response):
    with pytest.raises(InvalidResponseError):
        MALClient(http_get=lambda *args, **kwargs: response).get_json(
            "https://fixture.invalid"
        )


def test_iter_pages_follows_next_once_and_drops_initial_params():
    calls = []
    responses = iter(
        [
            FakeResponse(payload={"data": [1], "paging": {"next": "https://next"}}),
            FakeResponse(payload={"data": [2], "paging": {}}),
        ]
    )

    def fake_get(url, params, headers, timeout):
        calls.append((url, params))
        return next(responses)

    pages = list(
        MALClient(http_get=fake_get).iter_pages(
            "https://first",
            params={"limit": 100},
            access_token="fake-token",
        )
    )
    assert [page["data"] for page in pages] == [[1], [2]]
    assert calls == [
        ("https://first", {"limit": 100}),
        ("https://next", None),
    ]


def test_iter_pages_checks_cancellation_before_requesting_the_next_page():
    calls = []
    responses = iter(
        [
            FakeResponse(payload={"data": [1], "paging": {"next": "https://next"}}),
            FakeResponse(payload={"data": [2], "paging": {}}),
        ]
    )

    def fake_get(url, params, headers, timeout):
        calls.append(url)
        return next(responses)

    cancellation = CancellationToken()
    pages = MALClient(http_get=fake_get).iter_pages(
        "https://first",
        cancellation=cancellation,
    )
    assert next(pages)["data"] == [1]
    cancellation.cancel()

    with pytest.raises(CancelledError):
        next(pages)
    assert calls == ["https://first"]


def test_client_id_auth_uses_x_mal_header_without_bearer_token():
    captured = {}

    def fake_get(url, params, headers, timeout):
        captured.update(headers)
        return FakeResponse(payload={"data": []})

    MALClient(http_get=fake_get).get_json(
        "https://fixture.invalid",
        client_id="fixture-client-id",
    )

    assert captured == {"X-MAL-CLIENT-ID": "fixture-client-id"}


def test_bearer_token_takes_precedence_when_both_credentials_are_supplied():
    captured = {}

    def fake_get(url, params, headers, timeout):
        captured.update(headers)
        return FakeResponse(payload={"data": []})

    MALClient(http_get=fake_get).get_json(
        "https://fixture.invalid",
        access_token="fixture-token",
        client_id="fixture-client-id",
    )

    assert captured == {"Authorization": "Bearer fixture-token"}
