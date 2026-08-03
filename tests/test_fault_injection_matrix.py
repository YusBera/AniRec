from __future__ import annotations

import errno
import time

import pytest
import requests

from AniRec.errors import (
    AccessDeniedError,
    AuthError,
    ConfigError,
    DataError,
    InvalidResponseError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    UserFacingError,
)
from AniRec.gui.workers import BaseWorker, WorkerController
from AniRec.gui_main import create_application
from AniRec.infrastructure.csv_storage import CsvStorage
from AniRec.infrastructure.mal_client import MALClient
from AniRec.infrastructure.oauth_callback import OAuthCallbackServer
from AniRec.models import AppSettings, TokenRecord
from AniRec.services import (
    ApiConnectionService,
    AuthService,
    CoverImageService,
    ProfileService,
    SettingsService,
    TokenStore,
)


class Response:
    def __init__(self, *, status=200, payload=None, headers=None):
        self.status_code = status
        self._payload = {} if payload is None else payload
        self.headers = headers or {}

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class CallableWorker(BaseWorker):
    def __init__(self, action):
        super().__init__()
        self.action = action

    def execute(self):
        return self.action()


def _wait_until(application, predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        application.processEvents()
        time.sleep(0.002)
    application.processEvents()
    assert predicate()


@pytest.mark.parametrize(
    ("transport_error", "label"),
    [
        (requests.ConnectionError("offline fixture"), "offline"),
        (requests.Timeout("timeout fixture"), "timeout"),
    ],
)
def test_offline_and_api_timeout_are_controlled_and_client_can_retry(
    transport_error, label
):
    calls = 0

    def request(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise transport_error
        return Response(payload={"data": []})

    client = MALClient(http_get=request)
    with pytest.raises(NetworkError):
        client.get_json(f"https://fixture.invalid/{label}")

    assert client.get_json("https://fixture.invalid/retry") == {"data": []}


def test_rate_limit_is_retryable_without_leaking_headers():
    client = MALClient(
        http_get=lambda *_args, **_kwargs: Response(
            status=429,
            headers={"Retry-After": "45", "Authorization": "fixture-secret"},
        )
    )
    with pytest.raises(RateLimitError) as captured:
        client.get_json("https://fixture.invalid/rate-limit")

    assert captured.value.retry_after_seconds == 45
    model = captured.value.to_user_error()
    assert model.retryable
    assert "fixture-secret" not in repr(model)


def test_invalid_client_id_is_a_settings_error_and_a_valid_retry_succeeds():
    responses = iter(
        [Response(status=401), Response(payload={"data": []})]
    )
    service = ApiConnectionService(http_get=lambda *_args, **_kwargs: next(responses))
    settings = AppSettings(client_id="fixture-client")

    with pytest.raises(ConfigError):
        service.test(settings)
    assert service.test(settings)


def test_invalid_client_secret_or_refresh_rejection_preserves_expired_token(
    system_temp_dir,
):
    store = TokenStore(root_override=system_temp_dir)
    expired = TokenRecord("expired-access", "existing-refresh", expires_at=1)
    store.save("profile", expired)
    service = AuthService(
        token_store=store,
        clock=lambda: 1000,
        http_post=lambda *_args, **_kwargs: Response(status=401),
    )
    settings = AppSettings(
        client_id="fixture-client",
        client_secret="invalid-fixture-secret",
    )

    with pytest.raises(AuthError):
        service.get_access_token("profile", settings, interactive=False)

    assert store.load("profile") == expired


def test_callback_port_in_use_fails_before_waiting_and_does_not_leave_server():
    calls = []

    def occupied(_address, _handler):
        calls.append(True)
        raise OSError(errno.EADDRINUSE, "fixture port occupied")

    server = OAuthCallbackServer(server_factory=occupied)
    with pytest.raises(AuthError, match="port"):
        server.wait_for_code(
            "http://127.0.0.1:8080/callback",
            "fixture-state",
            timeout_seconds=0.05,
        )
    assert calls == [True]


@pytest.mark.parametrize(
    ("status", "expected"),
    [(404, NotFoundError), (403, AccessDeniedError)],
)
def test_missing_user_and_private_list_remain_distinct_without_partial_profile(
    system_temp_dir, status, expected
):
    responses = (
        [Response(status=404)]
        if status == 404
        else [
            Response(payload={"id": 77, "name": "Fixture User"}),
            Response(status=403),
        ]
    )
    service = ProfileService(
        root_override=system_temp_dir,
        mal_client=MALClient(http_get=lambda *_args, **_kwargs: responses.pop(0)),
    )

    with pytest.raises(expected):
        service.add_profile("Fixture User", "fixture-token")

    assert service.list_profiles() == ()


def test_corrupt_csv_worker_is_safe_and_controller_remains_reusable(system_temp_dir):
    application = create_application([])
    corrupt = system_temp_dir / "corrupt.csv"
    corrupt.write_text('Title,Score\n"unterminated,8', encoding="utf-8")
    controller = WorkerController()
    errors: list[UserFacingError] = []
    results = []
    controller.error_occurred.connect(lambda _key, error: errors.append(error))
    controller.result_ready.connect(lambda _key, result: results.append(result))

    controller.start("corrupt-csv", CallableWorker(lambda: CsvStorage().read(corrupt)))
    _wait_until(application, lambda: not controller.active_keys)
    controller.start("after-csv-fault", CallableWorker(lambda: "usable"))
    _wait_until(application, lambda: not controller.active_keys)

    assert errors[0].code == "application_error"
    assert "Traceback" not in repr(errors[0])
    assert results == ["usable"]


def test_corrupt_json_falls_back_and_can_be_replaced(system_temp_dir):
    service = SettingsService(root_override=system_temp_dir)
    service.path.parent.mkdir(parents=True, exist_ok=True)
    service.path.write_text("{broken", encoding="utf-8")

    assert service.load() == AppSettings()
    assert isinstance(service.last_error, ConfigError)
    valid = AppSettings(client_id="fixture-client")
    service.save(valid)
    assert service.load() == valid


@pytest.mark.parametrize(
    "storage_error",
    [
        PermissionError(errno.EACCES, "fixture permission denied"),
        OSError(errno.ENOSPC, "fixture disk full"),
    ],
    ids=["permission-denied", "disk-full"],
)
def test_storage_fault_worker_is_safe_and_controller_remains_reusable(storage_error):
    application = create_application([])
    controller = WorkerController()
    errors: list[UserFacingError] = []
    results = []
    controller.error_occurred.connect(lambda _key, error: errors.append(error))
    controller.result_ready.connect(lambda _key, result: results.append(result))

    controller.start(
        "storage-fault",
        CallableWorker(lambda: (_ for _ in ()).throw(storage_error)),
    )
    _wait_until(application, lambda: not controller.active_keys)
    controller.start("after-storage-fault", CallableWorker(lambda: "usable"))
    _wait_until(application, lambda: not controller.active_keys)

    rendered = repr(errors[0])
    assert errors[0].code == "application_error"
    assert "fixture permission denied" not in rendered
    assert "fixture disk full" not in rendered
    assert results == ["usable"]


def test_missing_profile_api_fields_do_not_create_local_data(system_temp_dir):
    service = ProfileService(
        root_override=system_temp_dir,
        mal_client=MALClient(
            http_get=lambda *_args, **_kwargs: Response(payload={"id": 77})
        ),
    )

    with pytest.raises(InvalidResponseError):
        service.add_profile("Fixture User", "fixture-token")

    assert service.list_profiles() == ()


@pytest.mark.parametrize(
    ("response_or_error", "expected"),
    [
        (requests.Timeout("fixture cover timeout"), NetworkError),
        (
            Response(
                payload=None,
                headers={"Content-Type": "image/jpeg"},
            ),
            DataError,
        ),
    ],
    ids=["cover-timeout", "cover-corrupt-content"],
)
def test_cover_faults_do_not_leave_partial_cache(
    system_temp_dir, response_or_error, expected
):
    url = "https://fixture.invalid/cover.jpg"

    if isinstance(response_or_error, Exception):
        def fetch(*_args, **_kwargs):
            raise response_or_error
    else:
        response_or_error.iter_content = lambda chunk_size: iter((b"not-an-image",))

        def fetch(*_args, **_kwargs):
            return response_or_error

    service = CoverImageService(root_override=system_temp_dir, http_get=fetch)
    with pytest.raises(expected):
        service.fetch(url)

    assert not service.cache_path(url).exists()
