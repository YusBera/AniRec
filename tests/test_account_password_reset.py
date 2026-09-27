"""Password reset by email (D-021, phase 5; docs/ACCOUNTS.md).

The rules under test: the request answers the same whether or not an account
uses the email; a token is single-use, short-lived and stored only as a
digest; a reset ends every session of the account; neither the SMTP password
nor a token reaches a response or a log.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from AniRec.api.app import create_app
from AniRec.api.container import build_container
from AniRec.infrastructure.logging_config import redact_secrets
from AniRec.infrastructure.mailer import MailOutbox, MailSettings, SmtpMailer
import AniRec.services.account_service as account_service
from AniRec.services.account_service import (
    RESET_LIFETIME,
    RESETS_PER_ACCOUNT_HOUR,
    AccountError,
    AccountService,
)
from AniRec.services.password_reset_service import public_url_from_environment, reset_link

ORIGIN = {"Origin": "http://127.0.0.1:5173"}
EMAIL = "reader@example.com"
PASSWORD = "a long password"


class Clock:
    def __init__(self):
        self.now = datetime(2026, 9, 24, 12, tzinfo=timezone.utc)

    def __call__(self):
        return self.now


class FakeMailer:
    def __init__(self, available: bool = True) -> None:
        self.available = available
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))


@pytest.fixture(autouse=True)
def _no_public_url(monkeypatch):
    monkeypatch.delenv("ANIREC_PUBLIC_URL", raising=False)


def _token_from(body: str) -> str:
    return body.split("#/reset-password?token=", 1)[1].split()[0]


# -- the token store ------------------------------------------------------------

def _registered(tmp_path, clock=None):
    accounts = AccountService(root_override=tmp_path, clock=clock or Clock())
    signed = accounts.register(EMAIL, PASSWORD)
    return accounts, signed


def test_a_token_is_issued_only_for_a_registered_email_and_stored_as_a_digest(tmp_path):
    accounts, _signed = _registered(tmp_path)
    guest = accounts.create_guest()
    assert accounts.issue_reset_token("nobody@example.com") is None
    assert guest.account.email is None
    issued = accounts.issue_reset_token(" Reader@Example.com")
    assert issued is not None
    token, email = issued
    assert email == EMAIL and len(token) >= 40
    assert token.encode() not in accounts.path.read_bytes()


def test_a_reset_replaces_the_password_ends_every_session_and_the_token_works_once(tmp_path):
    accounts, signed = _registered(tmp_path)
    other = accounts.sign_in(EMAIL, PASSWORD)
    token, _ = accounts.issue_reset_token(EMAIL)
    accounts.reset_password(token, "a brand new password")
    assert accounts.account_for_session(signed.token) is None
    assert accounts.account_for_session(other.token) is None
    with pytest.raises(AccountError) as refused:
        accounts.sign_in(EMAIL, PASSWORD)
    assert refused.value.reason == "wrong-credentials"
    assert accounts.sign_in(EMAIL, "a brand new password").account.email == EMAIL
    with pytest.raises(AccountError) as reused:
        accounts.reset_password(token, "yet another password")
    assert reused.value.reason == "invalid-token"


def test_a_reset_spends_every_outstanding_token_of_the_account(tmp_path):
    accounts, _ = _registered(tmp_path)
    first, _ = accounts.issue_reset_token(EMAIL)
    second, _ = accounts.issue_reset_token(EMAIL)
    accounts.reset_password(second, "a brand new password")
    with pytest.raises(AccountError) as refused:
        accounts.reset_password(first, "another new password")
    assert refused.value.reason == "invalid-token"


def test_a_token_expires_after_thirty_minutes(tmp_path):
    clock = Clock()
    accounts, _ = _registered(tmp_path, clock)
    token, _ = accounts.issue_reset_token(EMAIL)
    assert RESET_LIFETIME == timedelta(minutes=30)
    clock.now += RESET_LIFETIME
    with pytest.raises(AccountError) as refused:
        accounts.reset_password(token, "a brand new password")
    assert refused.value.reason == "invalid-token"


def test_a_weak_new_password_is_refused_without_spending_the_token(tmp_path):
    accounts, _ = _registered(tmp_path)
    token, _ = accounts.issue_reset_token(EMAIL)
    with pytest.raises(AccountError) as refused:
        accounts.reset_password(token, "short")
    assert refused.value.reason == "weak-password"
    accounts.reset_password(token, "a brand new password")


def test_unknown_and_malformed_tokens_are_refused_alike(tmp_path):
    accounts, _ = _registered(tmp_path)
    for token in ("", "x" * 500, "not-a-token"):
        with pytest.raises(AccountError) as refused:
            accounts.reset_password(token, "a brand new password")
        assert refused.value.reason == "invalid-token"


def test_at_most_three_tokens_an_hour_per_account(tmp_path):
    clock = Clock()
    accounts, _ = _registered(tmp_path, clock)
    issued = [accounts.issue_reset_token(EMAIL) for _ in range(RESETS_PER_ACCOUNT_HOUR + 1)]
    assert all(issued[:RESETS_PER_ACCOUNT_HOUR]) and issued[-1] is None
    clock.now += timedelta(hours=1, seconds=1)
    assert accounts.issue_reset_token(EMAIL) is not None


def test_the_whole_installation_sends_at_most_so_many_an_hour_and_a_day(tmp_path, monkeypatch):
    monkeypatch.setattr(account_service, "INSTALLATION_RESETS_PER_HOUR", 2)
    monkeypatch.setattr(account_service, "INSTALLATION_RESETS_PER_DAY", 3)
    clock = Clock()
    accounts = AccountService(root_override=tmp_path, clock=clock)
    emails = [f"reader{i}@example.com" for i in range(4)]
    for email in emails:
        accounts.register(email, PASSWORD)
    assert accounts.issue_reset_token(emails[0]) and accounts.issue_reset_token(emails[1])
    assert accounts.issue_reset_token(emails[2]) is None           # the hour is full
    clock.now += timedelta(hours=1, seconds=1)
    assert accounts.issue_reset_token(emails[2]) is not None
    assert accounts.issue_reset_token(emails[3]) is None           # the day is full
    clock.now += timedelta(days=1)
    assert accounts.issue_reset_token(emails[3]) is not None


def test_changing_the_password_spends_outstanding_reset_tokens(tmp_path):
    accounts, signed = _registered(tmp_path)
    token, _ = accounts.issue_reset_token(EMAIL)
    accounts.change_password(signed.account.account_id, PASSWORD, "a changed password")
    with pytest.raises(AccountError) as refused:
        accounts.reset_password(token, "a brand new password")
    assert refused.value.reason == "invalid-token"


def test_a_reset_ends_a_sign_in_lockout(tmp_path):
    accounts, _ = _registered(tmp_path)
    for _ in range(5):
        with pytest.raises(AccountError):
            accounts.sign_in(EMAIL, "wrong password", client="1.2.3.4")
    with pytest.raises(AccountError) as locked:
        accounts.sign_in(EMAIL, "wrong password", client="1.2.3.4")
    assert locked.value.reason == "too-many-attempts"
    token, _ = accounts.issue_reset_token(EMAIL)
    accounts.reset_password(token, "a brand new password")
    assert accounts.sign_in(EMAIL, "a brand new password", client="1.2.3.4").account.email == EMAIL


def test_a_deleted_account_takes_its_tokens_with_it(tmp_path):
    accounts, signed = _registered(tmp_path)
    token, _ = accounts.issue_reset_token(EMAIL)
    accounts.delete_account(signed.account.account_id)
    with pytest.raises(AccountError) as refused:
        accounts.reset_password(token, "a brand new password")
    assert refused.value.reason == "invalid-token"


# -- the mailer -------------------------------------------------------------------

def test_mail_is_available_only_with_a_host_and_a_sender():
    assert not MailSettings.from_environment({}).available
    assert not MailSettings.from_environment({"ANIREC_SMTP_HOST": "smtp.example.com"}).available
    assert MailSettings.from_environment({
        "ANIREC_SMTP_HOST": "smtp.example.com", "ANIREC_SMTP_SENDER": "AniRec <no-reply@example.com>",
    }).available
    # A user without a password (or the reverse) is a mistake, not anonymous mail.
    assert not MailSettings.from_environment({
        "ANIREC_SMTP_HOST": "smtp.example.com", "ANIREC_SMTP_SENDER": "no-reply@example.com",
        "ANIREC_SMTP_USER": "mailer",
    }).available
    assert not MailSettings.from_environment({
        "ANIREC_SMTP_HOST": "smtp.example.com", "ANIREC_SMTP_SENDER": "no-reply@example.com",
        "ANIREC_SMTP_PORT": "not a port",
    }).available


def test_the_smtp_password_never_appears_in_the_settings_repr():
    settings = MailSettings.from_environment({
        "ANIREC_SMTP_HOST": "smtp.example.com", "ANIREC_SMTP_SENDER": "no-reply@example.com",
        "ANIREC_SMTP_USER": "mailer", "ANIREC_SMTP_PASSWORD": "smtp-secret-value",
    })
    assert settings.available
    assert "smtp-secret-value" not in repr(settings)


class FakeSmtp:
    instances: list["FakeSmtp"] = []
    offers_starttls = True

    def __init__(self, host, port, timeout=None, **kwargs):
        self.host, self.port, self.calls = host, port, []
        FakeSmtp.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def ehlo(self):
        self.calls.append("ehlo")

    def has_extn(self, name):
        return name == "starttls" and self.offers_starttls

    def starttls(self, context=None):
        assert context is not None
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(("login", user))

    def send_message(self, message, from_addr=None, to_addrs=None):
        self.calls.append(("send", message["To"], message["From"]))


def _smtp_settings(**extra):
    return MailSettings.from_environment({
        "ANIREC_SMTP_HOST": "smtp.example.com", "ANIREC_SMTP_SENDER": "no-reply@example.com",
        "ANIREC_SMTP_USER": "mailer", "ANIREC_SMTP_PASSWORD": "smtp-secret-value", **extra,
    })


def test_smtp_always_encrypts_before_signing_in(monkeypatch):
    import AniRec.infrastructure.mailer as mailer_module

    FakeSmtp.instances = []
    FakeSmtp.offers_starttls = True
    monkeypatch.setattr(mailer_module.smtplib, "SMTP", FakeSmtp)
    SmtpMailer(_smtp_settings()).send(EMAIL, "Subject", "Body")
    calls = FakeSmtp.instances[0].calls
    assert calls.index("starttls") < calls.index(("login", "mailer"))
    assert ("send", EMAIL, "no-reply@example.com") in calls


def test_smtp_refuses_to_send_in_the_clear_to_a_remote_server(monkeypatch):
    import AniRec.infrastructure.mailer as mailer_module

    FakeSmtp.instances = []
    FakeSmtp.offers_starttls = False
    monkeypatch.setattr(mailer_module.smtplib, "SMTP", FakeSmtp)
    with pytest.raises(Exception):
        SmtpMailer(_smtp_settings()).send(EMAIL, "Subject", "Body")
    assert not any(isinstance(call, tuple) for call in FakeSmtp.instances[0].calls)


def test_port_465_uses_tls_from_the_first_byte(monkeypatch):
    import AniRec.infrastructure.mailer as mailer_module

    FakeSmtp.instances = []
    monkeypatch.setattr(mailer_module.smtplib, "SMTP_SSL", FakeSmtp)
    monkeypatch.setattr(mailer_module.smtplib, "SMTP", None)
    SmtpMailer(_smtp_settings(ANIREC_SMTP_PORT="465")).send(EMAIL, "Subject", "Body")
    assert FakeSmtp.instances[0].port == 465


def test_the_outbox_runs_jobs_off_the_request_path_and_logs_a_failure_by_class_only(caplog):
    release = threading.Event()

    def job():
        release.wait(5)
        raise RuntimeError("smtp-secret-value reader@example.com token=abcdef")

    outbox = MailOutbox()
    mail_log = logging.getLogger("AniRec.mail")
    mail_log.addHandler(caplog.handler)   # AniRec loggers may not propagate
    try:
        assert outbox.submit(job)   # returns while the job is blocked
        release.set()
        outbox.join()
    finally:
        mail_log.removeHandler(caplog.handler)
    assert "RuntimeError" in caplog.text
    for secret in ("smtp-secret-value", "reader@example.com", "abcdef"):
        assert secret not in caplog.text


def test_the_outbox_refuses_jobs_when_full():
    release = threading.Event()
    outbox = MailOutbox(maxsize=1)
    results = [outbox.submit(lambda: release.wait(5)) for _ in range(4)]
    release.set()
    outbox.join()
    assert results[0] and not results[-1]


def test_tokens_are_redacted_from_logs():
    assert "abc123" not in redact_secrets("token=abc123")
    assert "abc123" not in redact_secrets('{"token": "abc123"}')
    assert "abc123" not in redact_secrets("http://127.0.0.1:5173/#/reset-password?token=abc123")
    assert "s3cret" not in redact_secrets('{"new_password": "s3cret"}')


def test_the_link_carries_the_token_in_the_fragment():
    assert reset_link("http://127.0.0.1:5173/", "tok_en") == "http://127.0.0.1:5173/#/reset-password?token=tok_en"
    assert reset_link("https://anirec.example/app", "t") == "https://anirec.example/app/#/reset-password?token=t"


@pytest.mark.parametrize("value, expected", [
    ("https://anirec.example", "https://anirec.example"),
    ("https://anirec.example/app/", "https://anirec.example/app"),
    ("http://127.0.0.1:5173", "http://127.0.0.1:5173"),
    ("http://localhost:8770/", "http://localhost:8770"),
    ("http://anirec.example", None),            # plain http off loopback
    ("https://anirec.example/?next=x", None),   # a query
    ("https://anirec.example/#x", None),        # a fragment
    ("https://user@anirec.example", None),      # a user
    ("ftp://anirec.example", None),
    ("anirec.example", None),
    ("", None),
])
def test_the_public_address_is_checked(value, expected):
    assert public_url_from_environment({"ANIREC_PUBLIC_URL": value}) == expected


# -- the routes -------------------------------------------------------------------

PUBLIC = "http://127.0.0.1:5173"


def _app(tmp_path, monkeypatch, mailer=None, public_url=PUBLIC, **kwargs):
    if public_url is not None:
        monkeypatch.setenv("ANIREC_PUBLIC_URL", public_url)
    mailer = mailer or FakeMailer()
    app = create_app(container=build_container(str(tmp_path), mailer=mailer), **kwargs)
    return app, app.state.container, mailer


def _post(client, path, body=None, headers=None):
    return client.post(path, json=body, headers={**ORIGIN, **(headers or {})})


def _register(client, email=EMAIL):
    assert _post(client, "/api/account/register", {"email": email, "password": PASSWORD}).json()["account"]


def test_the_request_answers_alike_for_a_known_an_unknown_and_a_guest_email(tmp_path, monkeypatch):
    app, services, mailer = _app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        _register(client)
        known = _post(client, "/api/account/password-reset", {"email": EMAIL})
        unknown = _post(client, "/api/account/password-reset", {"email": "nobody@example.com"})
        services.password_resets.join()
        assert known.status_code == unknown.status_code == 200
        assert known.content == unknown.content
        assert known.json() == {"reason": None}
        assert "set-cookie" not in known.headers
        assert [to for to, _s, _b in mailer.sent] == [EMAIL]
        _subject, body = mailer.sent[0][1:]
        assert "30 minutes" in body
        assert body.count(f"{PUBLIC}/#/reset-password?token=") == 1
        assert _token_from(body) not in known.text


def test_the_request_does_no_account_work_on_the_request_path(tmp_path, monkeypatch):
    app, services, _mailer = _app(tmp_path, monkeypatch)
    calls = []

    def fails(email):
        calls.append(threading.current_thread().name)
        raise AccountError("unavailable")

    monkeypatch.setattr(services.accounts, "issue_reset_token", fails)
    with TestClient(app) as client:
        response = _post(client, "/api/account/password-reset", {"email": EMAIL})
        services.password_resets.join()
    assert response.json() == {"reason": None}
    assert calls and calls[0] != threading.main_thread().name


def test_the_link_ignores_the_request_origin(tmp_path, monkeypatch):
    app, services, mailer = _app(tmp_path, monkeypatch, public_url="https://anirec.example")
    with TestClient(app) as client:
        _register(client)
        # An allowed Origin the attacker chose, and none at all: the link is the configured one.
        _post(client, "/api/account/password-reset", {"email": EMAIL}, {"Origin": "http://localhost:5173"})
        client.post("/api/account/password-reset", json={"email": EMAIL})
        services.password_resets.join()
    assert len(mailer.sent) == 2
    for _to, _subject, body in mailer.sent:
        assert "https://anirec.example/#/reset-password?token=" in body
        assert "5173" not in body


@pytest.mark.parametrize("mail_ready, public_url", [(False, PUBLIC), (True, None), (True, "http://anirec.example")])
def test_reset_says_it_is_unavailable_without_a_mailer_or_a_public_address(tmp_path, monkeypatch, mail_ready, public_url):
    app, services, mailer = _app(tmp_path, monkeypatch, FakeMailer(available=mail_ready), public_url=public_url)
    with TestClient(app) as client:
        _register(client)
        assert client.get("/api/system/state").json()["password_reset_available"] is False
        assert _post(client, "/api/account/password-reset", {"email": EMAIL}).json() == {"reason": "reset-unavailable"}
        services.password_resets.join()
    assert mailer.sent == []


def test_reset_is_available_with_a_mailer_and_a_public_address(tmp_path, monkeypatch):
    app, _services, _mailer = _app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        assert client.get("/api/system/state").json()["password_reset_available"] is True


def test_the_request_is_limited_per_visitor(tmp_path, monkeypatch):
    app, services, _mailer = _app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        answers = [
            _post(client, "/api/account/password-reset", {"email": f"n{i}@example.com"}).json()["reason"]
            for i in range(6)
        ]
        services.password_resets.join()
    assert answers == [None] * 5 + ["too-many-attempts"]


def test_a_malformed_email_is_refused_as_such(tmp_path, monkeypatch):
    app, _services, mailer = _app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        assert _post(client, "/api/account/password-reset", {"email": "not an email"}).json() == {"reason": "invalid-email"}
    assert mailer.sent == []


def test_confirming_resets_the_password_and_signs_every_device_out(tmp_path, monkeypatch):
    app, services, mailer = _app(tmp_path, monkeypatch)
    with TestClient(app) as client, TestClient(app) as other:
        _register(client)
        assert _post(other, "/api/account/sign-in", {"email": EMAIL, "password": PASSWORD}).json()["account"]
        _post(client, "/api/account/password-reset", {"email": EMAIL})
        services.password_resets.join()
        token = _token_from(mailer.sent[0][2])
        done = _post(client, "/api/account/password-reset/confirm", {"token": token, "new_password": "a brand new password"})
        assert done.json() == {"reason": None}
        assert "a brand new password" not in done.text and token not in done.text
        assert client.get("/api/account").json()["account"] is None
        assert other.get("/api/account").json()["account"] is None
        again = _post(client, "/api/account/password-reset/confirm", {"token": token, "new_password": "another password"})
        assert again.json()["reason"] == "invalid-token"
        signed = _post(client, "/api/account/sign-in", {"email": EMAIL, "password": "a brand new password"})
        assert signed.json()["account"]["email"] == EMAIL


def test_wrong_tokens_count_as_sign_in_failures(tmp_path, monkeypatch):
    app, _services, _mailer = _app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        reasons = [
            _post(client, "/api/account/password-reset/confirm",
                  {"token": f"guess-{i}", "new_password": "a brand new password"}).json()["reason"]
            for i in range(21)
        ]
    assert reasons[:20] == ["invalid-token"] * 20
    assert reasons[20] == "too-many-attempts"


def test_a_busy_hashing_slot_neither_spends_the_token_nor_counts(tmp_path, monkeypatch):
    app, services, mailer = _app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        _register(client)
        _post(client, "/api/account/password-reset", {"email": EMAIL})
        services.password_resets.join()
        token = _token_from(mailer.sent[0][2])
        assert account_service._HASH_SLOTS.acquire(blocking=False)
        assert account_service._HASH_SLOTS.acquire(blocking=False)
        try:
            busy = _post(client, "/api/account/password-reset/confirm", {"token": token, "new_password": "a brand new password"})
        finally:
            account_service._HASH_SLOTS.release()
            account_service._HASH_SLOTS.release()
        assert busy.json()["reason"] == "busy"
        assert not app.state.limits.sign_in_failures.full("testclient")
        done = _post(client, "/api/account/password-reset/confirm", {"token": token, "new_password": "a brand new password"})
        assert done.json() == {"reason": None}


@pytest.mark.parametrize("path, body", [
    ("/api/account/password-reset", {"email": EMAIL}),
    ("/api/account/password-reset/confirm", {"token": "t", "new_password": "a brand new password"}),
])
def test_both_routes_pass_the_request_guard(tmp_path, monkeypatch, path, body):
    app, services, mailer = _app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        assert client.post(path, json=body, headers={"Origin": "https://evil.test"}).status_code == 403
        assert client.post(path, json=body, headers={**ORIGIN, "Host": "evil.test"}).status_code == 403
        assert client.post(path, json=body, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
        services.password_resets.join()
    assert mailer.sent == []


def test_an_overlong_new_password_is_refused_before_any_hashing(tmp_path, monkeypatch):
    app, _services, _mailer = _app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        response = _post(client, "/api/account/password-reset/confirm", {"token": "t", "new_password": "x" * 257})
    assert response.status_code == 422


# -- final review --------------------------------------------------------------------

def test_a_sign_in_checked_before_a_reset_does_not_survive_it(tmp_path):
    accounts, _ = _registered(tmp_path)
    token, _ = accounts.issue_reset_token(EMAIL)
    checked = accounts._checked_credentials_with_hash

    def reset_in_between(*args, **kwargs):
        result = checked(*args, **kwargs)
        accounts.reset_password(token, "a brand new password")   # the owner recovers
        return result

    accounts._checked_credentials_with_hash = reset_in_between
    with pytest.raises(AccountError) as refused:
        accounts.sign_in(EMAIL, PASSWORD)
    assert refused.value.reason == "wrong-credentials"


def test_changing_the_password_does_not_reset_the_mail_limit(tmp_path):
    accounts, signed = _registered(tmp_path)
    for _ in range(RESETS_PER_ACCOUNT_HOUR):
        assert accounts.issue_reset_token(EMAIL)
    accounts.change_password(signed.account.account_id, PASSWORD, "a changed password")
    assert accounts.issue_reset_token(EMAIL) is None


def test_deleting_and_registering_again_does_not_reset_the_mail_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(account_service, "INSTALLATION_RESETS_PER_HOUR", RESETS_PER_ACCOUNT_HOUR + 1)
    accounts, signed = _registered(tmp_path)
    for _ in range(RESETS_PER_ACCOUNT_HOUR):
        assert accounts.issue_reset_token(EMAIL)
    accounts.delete_account(signed.account.account_id)
    accounts.register(EMAIL, PASSWORD)
    assert accounts.issue_reset_token(EMAIL) is None
    # The installation's count did not drop either.
    accounts.register("other@example.com", PASSWORD)
    assert accounts.issue_reset_token("other@example.com")
    assert accounts.issue_reset_token("other@example.com") is None


def test_a_spent_token_still_counts_and_still_cannot_be_used(tmp_path):
    accounts, _ = _registered(tmp_path)
    token, _ = accounts.issue_reset_token(EMAIL)
    accounts.reset_password(token, "a brand new password")
    for _ in range(RESETS_PER_ACCOUNT_HOUR - 1):
        assert accounts.issue_reset_token(EMAIL)
    assert accounts.issue_reset_token(EMAIL) is None
    with pytest.raises(AccountError):
        accounts.reset_password(token, "another new password")


@pytest.mark.parametrize("address", [
    "me@evil.com,root", "me@evil.com;root", "<me@evil.com>", '"me"@evil.com', "me(x)@evil.com",
])
def test_an_address_that_could_name_a_second_recipient_is_refused(tmp_path, address):
    accounts = AccountService(root_override=tmp_path, clock=Clock())
    with pytest.raises(AccountError) as refused:
        accounts.register(address, PASSWORD)
    assert refused.value.reason == "invalid-email"


def test_smtp_sends_only_to_the_one_address(monkeypatch):
    import AniRec.infrastructure.mailer as mailer_module

    sent = []

    class Recording(FakeSmtp):
        def send_message(self, message, from_addr=None, to_addrs=None):
            sent.append(to_addrs)

    FakeSmtp.offers_starttls = True
    monkeypatch.setattr(mailer_module.smtplib, "SMTP", Recording)
    SmtpMailer(_smtp_settings()).send(EMAIL, "Subject", "Body")
    assert sent == [[EMAIL]]
