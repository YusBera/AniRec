"""Password reset by email (D-021, phase 5; docs/ACCOUNTS.md).

A request only checks the email's form and queues it. The mail worker looks
the account up, issues the token and sends the link, so whether an account
uses the email never shows in the answer or in its timing. The link's address
comes only from ``ANIREC_PUBLIC_URL``, never from the request: anyone can
send an allowed ``Origin`` from a plain HTTP client.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from urllib.parse import urlsplit

from ..infrastructure.mailer import Mailer, MailOutbox, is_loopback_host
from .account_service import RESET_LIFETIME, AccountError, AccountService, normalize_email

PUBLIC_URL_ENV_VAR = "ANIREC_PUBLIC_URL"
SUBJECT = "Reset your AniRec password"


def public_url_from_environment(environ: Mapping[str, str] | None = None) -> str | None:
    """The web client's address for links, or ``None`` when unset or unsafe.

    ``https``, or ``http`` for a loopback host only; no user, query or
    fragment. A trailing slash is dropped.
    """
    raw = (os.environ if environ is None else environ).get(PUBLIC_URL_ENV_VAR, "").strip()
    if not raw:
        return None
    try:
        parts = urlsplit(raw)
        host = parts.hostname or ""
        parts.port   # raises on a malformed port
    except ValueError:
        return None
    if not host or parts.username or parts.password or parts.query or parts.fragment or "#" in raw or "?" in raw:
        return None
    if parts.scheme != "https" and not (parts.scheme == "http" and is_loopback_host(host)):
        return None
    return raw.rstrip("/")


def reset_link(base: str, token: str) -> str:
    # In the fragment: browsers never send it to a server or in a Referer.
    return f"{base.rstrip('/')}/#/reset-password?token={token}"


def _body(link: str) -> str:
    minutes = int(RESET_LIFETIME.total_seconds() // 60)
    return (
        "Someone asked to reset the password of the AniRec account that uses this email address.\n\n"
        f"To choose a new password, open this link within {minutes} minutes:\n\n"
        f"{link}\n\n"
        "The link works once. If you didn't ask for this, ignore this email: your password stays the same.\n"
    )


class PasswordResetService:
    def __init__(self, accounts: AccountService, mailer: Mailer, public_url: str | None,
                 outbox: MailOutbox | None = None) -> None:
        self._accounts = accounts
        self._mailer = mailer
        self._public_url = public_url
        self._outbox = outbox or MailOutbox()

    @property
    def available(self) -> bool:
        return bool(self._mailer.available and self._public_url)

    def request(self, email: str) -> None:
        """Queue a reset for ``email``. Raises only for reasons that do not
        depend on whether an account uses it."""
        if not self.available:
            raise AccountError("reset-unavailable")
        email = normalize_email(email)
        if not self._outbox.submit(lambda: self._send(email)):
            raise AccountError("busy")

    def _send(self, email: str) -> None:
        issued = self._accounts.issue_reset_token(email)
        if issued is None:
            return
        token, address = issued
        self._mailer.send(address, SUBJECT, _body(reset_link(self._public_url, token)))

    def confirm(self, token: str, new_password: str) -> None:
        self._accounts.reset_password(token, new_password)

    def join(self) -> None:
        """Wait for queued mail work (tests)."""
        self._outbox.join()
