"""Rotating application logging with defense-in-depth secret redaction."""

from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .paths import logs_dir


REDACTION_MARKER = "[REDACTED]"
_REDACTION_PATTERNS = (
    (
        re.compile(r"(?i)\b(Bearer)\s+[A-Za-z0-9._~+/=-]+"),
        rf"\1 {REDACTION_MARKER}",
    ),
    (
        re.compile(
            r"(?i)([\"']?(?:access_token|refresh_token|client_secret|authorization_code|id_token)"
            r"[\"']?\s*[:=]\s*[\"']?)([^&,\s\"'}]+)"
        ),
        rf"\1{REDACTION_MARKER}",
    ),
    (
        re.compile(
            r"(?i)([?&](?:code|state|access_token|refresh_token|client_secret|token)=)[^&\s]+"
        ),
        rf"\1{REDACTION_MARKER}",
    ),
)


def redact_secrets(value: object) -> str:
    redacted = str(value)
    for pattern, replacement in _REDACTION_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_secrets(record.getMessage())
        record.args = ()
        return True


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact_secrets(super().format(record))


def configure_logging(
    *,
    debug: bool = False,
    root_override: str | Path | None = None,
    logger_name: str = "AniRec",
    max_bytes: int = 1_000_000,
    backup_count: int = 3,
) -> logging.Logger:
    """Configure one isolated AniRec logger and return it."""
    directory = logs_dir(root_override)
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / "anirec.log"

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False

    close_logger(logger)

    handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(logging.DEBUG if debug else logging.INFO)
    handler.addFilter(SecretRedactionFilter())
    handler.setFormatter(
        RedactingFormatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    logger.addHandler(handler)
    return logger


def close_logger(logger: logging.Logger) -> None:
    """Flush, detach, and close all handlers owned by an AniRec logger."""
    for handler in list(logger.handlers):
        handler.flush()
        logger.removeHandler(handler)
        handler.close()


def close_all_anirec_loggers() -> None:
    """Release every AniRec-owned file handler before local-data deletion."""
    for name, candidate in tuple(logging.Logger.manager.loggerDict.items()):
        if isinstance(candidate, logging.Logger) and (
            name == "AniRec" or name.startswith("AniRec.")
        ):
            close_logger(candidate)
