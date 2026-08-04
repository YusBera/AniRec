from __future__ import annotations

import logging

from infrastructure.logging_config import close_logger, configure_logging, redact_secrets


SECRET_EXAMPLES = (
    "bearer-fixture-secret",
    "access-fixture-secret",
    "refresh-fixture-secret",
    "client-fixture-secret",
    "authorization-fixture-secret",
    "query-code-fixture-secret",
    "query-state-fixture-secret",
    "trace-fixture-secret",
)


def _flush(logger):
    for handler in logger.handlers:
        handler.flush()


def test_redact_secrets_covers_headers_key_values_json_and_query_parameters():
    message = (
        "Authorization: Bearer bearer-fixture-secret "
        "access_token=access-fixture-secret "
        "refresh_token: refresh-fixture-secret "
        '\"client_secret\": \"client-fixture-secret\" '
        "authorization_code=authorization-fixture-secret "
        "https://localhost/callback?code=query-code-fixture-secret&state=query-state-fixture-secret"
    )

    redacted = redact_secrets(message)

    assert "[REDACTED]" in redacted
    assert all(secret not in redacted for secret in SECRET_EXAMPLES[:-1])


def test_rotating_file_logging_redacts_message_and_traceback(system_temp_dir):
    logger = configure_logging(
        debug=True,
        root_override=system_temp_dir / "app-data",
        logger_name="AniRec.fixture.redaction",
        max_bytes=2_000,
        backup_count=1,
    )
    try:
        logger.info(
            "Authorization: Bearer bearer-fixture-secret access_token=%s",
            "access-fixture-secret",
        )
        logger.info(
            "refresh_token=refresh-fixture-secret client_secret=client-fixture-secret "
            "authorization_code=authorization-fixture-secret"
        )
        logger.info(
            "callback?code=query-code-fixture-secret&state=query-state-fixture-secret"
        )
        try:
            raise RuntimeError("client_secret=trace-fixture-secret")
        except RuntimeError:
            logger.exception("Fixture failure")
        _flush(logger)

        log_path = system_temp_dir / "app-data" / "logs" / "anirec.log"
        content = log_path.read_text(encoding="utf-8")
        assert "[REDACTED]" in content
        assert "Fixture failure" in content
        assert all(secret not in content for secret in SECRET_EXAMPLES)
        assert isinstance(logger.handlers[0], logging.handlers.RotatingFileHandler)
    finally:
        close_logger(logger)


def test_non_debug_logger_filters_debug_records(system_temp_dir):
    logger = configure_logging(
        debug=False,
        root_override=system_temp_dir / "app-data",
        logger_name="AniRec.fixture.level",
    )
    try:
        logger.debug("hidden debug message")
        logger.info("visible info message")
        _flush(logger)

        content = (system_temp_dir / "app-data" / "logs" / "anirec.log").read_text(
            encoding="utf-8"
        )
        assert "hidden debug message" not in content
        assert "visible info message" in content
    finally:
        close_logger(logger)
