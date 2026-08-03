from __future__ import annotations

import pytest
import requests

from AniRec.errors import ConfigError, InvalidResponseError, NetworkError
from AniRec.models import AppSettings
from AniRec.services import ApiConnectionService


class Response:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self.payload = {"data": []} if payload is None else payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_api_connection_uses_client_id_header_and_small_ranking_request():
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    assert ApiConnectionService(http_get=fake_get).test(
        AppSettings(client_id="fixture-client")
    )
    assert calls[0][1]["headers"] == {"X-MAL-CLIENT-ID": "fixture-client"}
    assert calls[0][1]["params"] == {"ranking_type": "all", "limit": 1}


@pytest.mark.parametrize("status", [400, 401, 403])
def test_api_connection_rejected_client_id_maps_to_config_error(status):
    service = ApiConnectionService(http_get=lambda *_args, **_kwargs: Response(status))
    with pytest.raises(ConfigError):
        service.test(AppSettings(client_id="rejected"))


def test_api_connection_network_and_payload_failures_are_safe():
    def timeout(*_args, **_kwargs):
        raise requests.Timeout("fixture")

    with pytest.raises(NetworkError):
        ApiConnectionService(http_get=timeout).test(AppSettings(client_id="fixture"))
    with pytest.raises(InvalidResponseError):
        ApiConnectionService(
            http_get=lambda *_args, **_kwargs: Response(payload={"wrong": []})
        ).test(AppSettings(client_id="fixture"))
