"""Sending email: a small seam over SMTP (D-021, phase 5; docs/ACCOUNTS.md).

Settings come from the environment only and are never written to disk or
returned by the API. The connection is always encrypted (STARTTLS, or TLS
from the first byte on port 465), except to a loopback server such as a local
test catcher. Nothing here logs an address, a message body or the SMTP
password: a failure is logged by its exception class alone, because SMTP
errors quote addresses and server replies.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import queue
import smtplib
import ssl
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Protocol

LOGGER = logging.getLogger("AniRec.mail")

SMTP_TIMEOUT_SECONDS = 15
IMPLICIT_TLS_PORT = 465
OUTBOX_SIZE = 50


class Mailer(Protocol):
    @property
    def available(self) -> bool: ...

    def send(self, to: str, subject: str, body: str) -> None: ...


def is_loopback_host(host: str) -> bool:
    if host.strip().lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class MailSettings:
    host: str = ""
    port: int = 587
    user: str = ""
    password: str = field(default="", repr=False)
    sender: str = ""
    valid: bool = False

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "MailSettings":
        env = os.environ if environ is None else environ
        host = env.get("ANIREC_SMTP_HOST", "").strip()
        sender = env.get("ANIREC_SMTP_SENDER", "").strip()
        user = env.get("ANIREC_SMTP_USER", "")
        password = env.get("ANIREC_SMTP_PASSWORD", "")
        try:
            port = int(env.get("ANIREC_SMTP_PORT", "").strip() or 587)
        except ValueError:
            port = 0
        valid = (
            bool(host) and bool(sender) and 0 < port < 65536
            # Both or neither: a user without a password is a mistake.
            and bool(user) == bool(password)
            # Header injection: the sender goes into a header as it is.
            and "\r" not in sender and "\n" not in sender
        )
        return cls(host=host, port=port, user=user, password=password, sender=sender, valid=valid)

    @property
    def available(self) -> bool:
        return self.valid


class SmtpMailer:
    def __init__(self, settings: MailSettings) -> None:
        self._settings = settings

    @classmethod
    def from_environment(cls) -> "SmtpMailer":
        return cls(MailSettings.from_environment())

    @property
    def available(self) -> bool:
        return self._settings.available

    def send(self, to: str, subject: str, body: str) -> None:
        settings = self._settings
        if not settings.available:
            raise RuntimeError("Mail is not configured.")
        message = EmailMessage()
        message["From"] = settings.sender
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        context = ssl.create_default_context()
        if settings.port == IMPLICIT_TLS_PORT:
            with smtplib.SMTP_SSL(settings.host, settings.port, timeout=SMTP_TIMEOUT_SECONDS, context=context) as smtp:
                self._deliver(smtp, message)
            return
        with smtplib.SMTP(settings.host, settings.port, timeout=SMTP_TIMEOUT_SECONDS) as smtp:
            smtp.ehlo()
            if smtp.has_extn("starttls"):
                smtp.starttls(context=context)
                smtp.ehlo()
            elif not is_loopback_host(settings.host):
                # Never a password or a reset link in the clear.
                raise smtplib.SMTPNotSupportedError("The mail server does not offer STARTTLS.")
            self._deliver(smtp, message)

    def _deliver(self, smtp, message: EmailMessage) -> None:
        if self._settings.user:
            smtp.login(self._settings.user, self._settings.password)
        # Exactly one recipient, never whatever the To header parses into.
        smtp.send_message(message, to_addrs=[message["To"]])


class MailOutbox:
    """One background worker behind a bounded queue.

    A request hands its mail work here and answers at once, so what the work
    finds (an account, or none) never shows in the response time.
    """

    def __init__(self, *, maxsize: int = OUTBOX_SIZE) -> None:
        self._jobs: queue.Queue[Callable[[], None]] = queue.Queue(maxsize=maxsize)
        self._worker: threading.Thread | None = None
        self._lock = threading.Lock()

    def submit(self, job: Callable[[], None]) -> bool:
        """Queue ``job``; ``False`` when the queue is full (nothing queued)."""
        try:
            self._jobs.put_nowait(job)
        except queue.Full:
            LOGGER.warning("Mail queue is full; a message was dropped.")
            return False
        self._start()
        return True

    def join(self) -> None:
        """Wait until every queued job has run (tests, orderly shutdown)."""
        self._jobs.join()

    def _start(self) -> None:
        with self._lock:
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._run, name="anirec-mail", daemon=True)
                self._worker.start()

    def _run(self) -> None:
        while True:
            job = self._jobs.get()
            try:
                job()
            except Exception as error:  # noqa: BLE001 - the worker must survive any job
                LOGGER.warning("Mail job failed: %s", type(error).__name__)
            finally:
                self._jobs.task_done()
