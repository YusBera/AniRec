from __future__ import annotations

import ast

import pytest

from errors import AuthError, InvalidResponseError
from models import AppSettings, TokenRecord
from services import AuthService, TokenStore


class Response:
    def __init__(self, *, status=200, payload=None, json_error=None):
        self.status_code = status
        self._payload = payload
        self._json_error = json_error

    def raise_for_status(self):
        return None

    def json(self):
        if self._json_error:
            raise self._json_error
        return self._payload


class Callback:
    def wait_for_code(self, *args, **kwargs):
        return "fake-new-code"


def _settings():
    return AppSettings(
        client_id="fixture-client",
        redirect_uri="http://localhost:8080/callback",
    )


def test_failed_refresh_can_fall_back_to_interactive_authorization(system_temp_dir):
    store = TokenStore(root_override=system_temp_dir / "app-data")
    store.save("profile", TokenRecord("expired", "refresh", expires_at=1))
    responses = iter(
        [
            Response(status=401),
            Response(
                payload={
                    "access_token": "new-access",
                    "refresh_token": "new-refresh",
                    "expires_in": 3600,
                }
            ),
        ]
    )
    random_values = iter(["state", "verifier"])
    service = AuthService(
        token_store=store,
        callback_server=Callback(),
        http_post=lambda *args, **kwargs: next(responses),
        browser_open=lambda _url: True,
        clock=lambda: 1000,
        random_token=lambda _length: next(random_values),
    )
    assert service.get_access_token(
        "profile",
        _settings(),
        interactive=True,
    ) == "new-access"
    assert store.load("profile").refresh_token == "new-refresh"


@pytest.mark.parametrize(
    "response",
    [
        Response(payload=None, json_error=ValueError("broken fixture json")),
        Response(payload=[]),
        Response(payload={"refresh_token": "missing access"}),
        Response(payload={"access_token": "token", "expires_in": "invalid"}),
    ],
)
def test_invalid_token_responses_are_controlled_data_errors(system_temp_dir, response):
    service = AuthService(
        token_store=TokenStore(root_override=system_temp_dir),
        http_post=lambda *args, **kwargs: response,
    )
    with pytest.raises(InvalidResponseError):
        service.refresh("profile", _settings(), "fake-refresh")


def test_noninteractive_missing_or_failed_token_is_explicit(system_temp_dir):
    store = TokenStore(root_override=system_temp_dir)
    service = AuthService(token_store=store, clock=lambda: 1000)
    with pytest.raises(AuthError):
        service.get_access_token("missing", _settings(), interactive=False)

    store.save("expired", TokenRecord("expired", "refresh", expires_at=1))
    failing = AuthService(
        token_store=store,
        clock=lambda: 1000,
        http_post=lambda *args, **kwargs: Response(status=401),
    )
    with pytest.raises(AuthError):
        failing.get_access_token("expired", _settings(), interactive=False)


def test_auth_and_profile_services_have_no_terminal_or_qt_calls(repo_root):
    service_root = repo_root / "AniRec" / "services"
    forbidden_calls = []
    forbidden_imports = []
    for path in service_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"input", "print"}
            ):
                forbidden_calls.append((path.name, node.func.id))
            if isinstance(node, ast.Import):
                forbidden_imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                forbidden_imports.append(node.module)
    assert forbidden_calls == []
    assert not any(name.startswith(("PySide6", "PyQt")) for name in forbidden_imports)


def test_secret_models_do_not_leak_values_in_repr():
    settings = AppSettings(
        client_id="client",
        client_secret="fixture-client-secret-never-repr",
    )
    token = TokenRecord(
        "fixture-access-never-repr",
        "fixture-refresh-never-repr",
    )
    representation = f"{settings!r} {token!r}"
    assert "fixture-client-secret-never-repr" not in representation
    assert "fixture-access-never-repr" not in representation
    assert "fixture-refresh-never-repr" not in representation
