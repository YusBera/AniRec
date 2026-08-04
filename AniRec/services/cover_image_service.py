"""Validated, bounded, atomically cached anime cover downloads."""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

try:
    from ..errors import DataError, NetworkError
    from ..infrastructure.paths import cache_dir
except ImportError:  # Compatibility with legacy top-level imports.
    from errors import DataError, NetworkError
    from infrastructure.paths import cache_dir


ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
DEFAULT_MAX_COVER_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class CoverImageResult:
    url: str
    data: bytes
    cache_path: Path
    cache_hit: bool


class CoverImageService:
    def __init__(
        self,
        *,
        root_override: str | Path | None = None,
        http_get=None,
        timeout_seconds: int = 15,
        max_bytes: int = DEFAULT_MAX_COVER_BYTES,
        replace_func=os.replace,
    ) -> None:
        self._directory = cache_dir(root_override) / "covers"
        self._http_get = http_get or requests.get
        self._timeout_seconds = timeout_seconds
        self._max_bytes = max_bytes
        self._replace = replace_func

    def fetch(self, url: str, *, cancellation=None) -> CoverImageResult:
        self._validate_url(url)
        path = self.cache_path(url)
        if path.is_file():
            data = path.read_bytes()
            if data:
                return CoverImageResult(url, data, path, True)
            path.unlink(missing_ok=True)

        _raise_if_cancelled(cancellation)
        try:
            response = self._http_get(
                url,
                timeout=self._timeout_seconds,
                stream=True,
            )
        except requests.Timeout as error:
            raise NetworkError("Anime cover request timed out.") from error
        except requests.RequestException as error:
            raise NetworkError("Anime cover request failed.") from error
        status = int(getattr(response, "status_code", 200))
        if status >= 400:
            raise NetworkError(f"Anime cover request returned HTTP {status}.")
        content_type = str(getattr(response, "headers", {}).get("Content-Type", ""))
        content_type = content_type.split(";", 1)[0].strip().casefold()
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise DataError("Anime cover response was not a supported image type.")
        length = getattr(response, "headers", {}).get("Content-Length")
        try:
            if length is not None and int(length) > self._max_bytes:
                raise DataError("Anime cover exceeded the download size limit.")
        except ValueError as error:
            raise DataError("Anime cover size header was invalid.") from error

        chunks: list[bytes] = []
        total = 0
        iterator = getattr(response, "iter_content", None)
        source = iterator(chunk_size=64 * 1024) if callable(iterator) else (response.content,)
        for chunk in source:
            _raise_if_cancelled(cancellation)
            if not chunk:
                continue
            total += len(chunk)
            if total > self._max_bytes:
                raise DataError("Anime cover exceeded the download size limit.")
            chunks.append(bytes(chunk))
        data = b"".join(chunks)
        if not data:
            raise DataError("Anime cover response was empty.")
        if not _matches_image_signature(data, content_type):
            raise DataError("Anime cover response contained invalid image data.")
        _raise_if_cancelled(cancellation)
        self._write_atomic(path, data)
        return CoverImageResult(url, data, path, False)

    def cache_path(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self._directory / f"{digest}.img"

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed = urlparse(url)
        if (
            parsed.scheme.casefold() != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise DataError("Anime cover URL must be a safe HTTPS URL.")

    def _write_atomic(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            self._replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def _raise_if_cancelled(cancellation) -> None:
    if cancellation is None:
        return
    checker = getattr(cancellation, "raise_if_cancelled", None)
    if callable(checker):
        checker()


def _matches_image_signature(data: bytes, content_type: str) -> bool:
    """Reject HTML/error bodies mislabeled as images before they reach Qt."""
    if content_type == "image/jpeg":
        return len(data) >= 3 and data.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/webp":
        return len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP"
    return False
