from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from models import AppSettings, TokenRecord
from services import AuthService, TokenStore


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeCallback:
    def __init__(self, code="fake-authorization-code"):
        self.code = code
        self.calls = []

    def wait_for_code(self, redirect_uri, expected_state, **kwargs):
        self.calls.append((redirect_uri, expected_state, kwargs))
        return self.code


def _settings():
    return AppSettings(
        client_id="fixture-client-id",
        client_secret="fixture-client-secret",
        redirect_uri="http://localhost:8080/callback",
    )


def test_authorization_session_uses_random_state_and_mal_compatible_plain_pkce(
    system_temp_dir,
):
    values = iter(["fixture-state", "fixture-code-verifier"])
    service = AuthService(
        token_store=TokenStore(root_override=system_temp_dir),
        random_token=lambda _length: next(values),
    )
    session = service.create_session(_settings())
    query = parse_qs(urlparse(session.authorization_url).query)
    assert query["state"] == ["fixture-state"]
    assert query["code_challenge"] == ["fixture-code-verifier"]
    assert query["code_challenge_method"] == ["plain"]
    assert "fixture-code-verifier" not in repr(session)


def test_authorize_opens_browser_exchanges_code_and_saves_token(system_temp_dir):
    callback = FakeCallback()
    browser_urls = []
    post_calls = []

    def fake_post(url, data, timeout):
        post_calls.append((url, data, timeout))
        return FakeResponse(
            {
                "access_token": "fake-access-token",
                "refresh_token": "fake-refresh-token",
                "expires_in": 3600,
                "token_type": "Bearer",
            }
        )

    values = iter(["fixture-state", "fixture-verifier"])
    token_store = TokenStore(root_override=system_temp_dir / "app-data")
    service = AuthService(
        token_store=token_store,
        callback_server=callback,
        http_post=fake_post,
        browser_open=lambda url: browser_urls.append(url) or True,
        clock=lambda: 1000,
        random_token=lambda _length: next(values),
    )
    token = service.authorize("fixture-profile", _settings())
    assert token.expires_at == 4540
    assert token_store.load("fixture-profile") == token
    assert len(browser_urls) == 1
    assert callback.calls[0][0] == "http://localhost:8080/callback"
    assert post_calls[0][1]["code"] == "fake-authorization-code"
    assert post_calls[0][1]["code_verifier"] == "fixture-verifier"


def test_authorize_reports_browser_callback_and_token_statuses_in_order(system_temp_dir):
    callback = FakeCallback()
    values = iter(["fixture-state", "fixture-verifier"])
    statuses = []
    service = AuthService(
        token_store=TokenStore(root_override=system_temp_dir),
        callback_server=callback,
        http_post=lambda *_args, **_kwargs: FakeResponse(
            {"access_token": "fake-access", "expires_in": 3600}
        ),
        browser_open=lambda _url: True,
        random_token=lambda _length: next(values),
    )

    service.authorize("profile", _settings(), status_callback=statuses.append)

    assert statuses == [
        "oauth_opening_browser",
        "oauth_waiting_approval",
        "oauth_authorization_complete",
        "oauth_validating_token",
        "oauth_success",
    ]


def test_cached_token_reuse_and_expired_refresh(system_temp_dir):
    store = TokenStore(root_override=system_temp_dir / "app-data")
    store.save("valid", TokenRecord("valid-access", "valid-refresh", expires_at=2000))
    post_calls = []

    def fake_post(url, data, timeout):
        post_calls.append(data)
        return FakeResponse(
            {"access_token": "refreshed-access", "expires_in": 3600}
        )

    service = AuthService(token_store=store, http_post=fake_post, clock=lambda: 1000)
    assert service.get_access_token("valid", _settings()) == "valid-access"
    assert post_calls == []

    store.save("expired", TokenRecord("old", "refresh-me", expires_at=500))
    assert service.get_access_token("expired", _settings()) == "refreshed-access"
    assert post_calls[0]["grant_type"] == "refresh_token"
    assert store.load("expired").refresh_token == "refresh-me"


def test_interactive_access_token_starts_oauth_when_no_token_exists(system_temp_dir):
    callback = FakeCallback()
    statuses = []
    iter_values = iter(["state", "verifier"])
    token_store = TokenStore(root_override=system_temp_dir / "app-data")
    service = AuthService(
        token_store=token_store,
        callback_server=callback,
        http_post=lambda *_args, **_kwargs: FakeResponse(
            {"access_token": "interactive-access", "expires_in": 3600}
        ),
        browser_open=lambda _url: True,
        random_token=lambda _length: next(iter_values),
    )

    token = service.get_access_token(
        "profile",
        _settings(),
        interactive=True,
        status_callback=statuses.append,
    )

    assert token == "interactive-access"
    assert token_store.load("profile").access_token == "interactive-access"
    assert statuses == [
        "oauth_opening_browser",
        "oauth_waiting_approval",
        "oauth_authorization_complete",
        "oauth_validating_token",
        "oauth_success",
    ]
