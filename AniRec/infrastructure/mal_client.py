"""Single MyAnimeList API HTTP boundary with safe application error mapping."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from typing import Any

import requests

try:
    from ..errors import (
        AccessDeniedError,
        AuthError,
        CancelledError,
        InvalidResponseError,
        NetworkError,
        NotFoundError,
        RateLimitError,
        ServerError,
    )
except ImportError:  # Compatibility with the S01 top-level import path.
    from errors import (
        AccessDeniedError,
        AuthError,
        CancelledError,
        InvalidResponseError,
        NetworkError,
        NotFoundError,
        RateLimitError,
        ServerError,
    )


class MALClient:
    def __init__(
        self,
        *,
        http_get: Callable | None = None,
        timeout_seconds: int = 15,
    ) -> None:
        self._http_get = http_get or requests.get
        self._timeout_seconds = timeout_seconds

    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        access_token: str | None = None,
        client_id: str | None = None,
        cancellation=None,
    ) -> Mapping[str, Any]:
        _raise_if_cancelled(cancellation)
        headers = {}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        elif client_id:
            headers["X-MAL-CLIENT-ID"] = client_id
        try:
            response = self._http_get(
                url,
                params=params,
                headers=headers,
                timeout=self._timeout_seconds,
            )
        except requests.Timeout as error:
            raise NetworkError("MyAnimeList request timed out.") from error
        except requests.ConnectionError as error:
            raise NetworkError("Could not connect to MyAnimeList.") from error
        except requests.RequestException as error:
            raise NetworkError("MyAnimeList request failed.") from error

        _raise_if_cancelled(cancellation)

        status = int(getattr(response, "status_code", 200))
        if status >= 400:
            self._raise_status_error(status, getattr(response, "headers", {}))

        try:
            response.raise_for_status()
        except requests.RequestException as error:
            raise NetworkError("MyAnimeList request failed.") from error

        try:
            payload = response.json()
        except (ValueError, TypeError) as error:
            raise InvalidResponseError("MyAnimeList returned invalid JSON.") from error
        if not isinstance(payload, Mapping):
            raise InvalidResponseError("MyAnimeList JSON root must be an object.")
        _raise_if_cancelled(cancellation)
        return payload

    def iter_pages(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        access_token: str | None = None,
        client_id: str | None = None,
        max_pages: int = 100,
        cancellation=None,
    ) -> Iterator[Mapping[str, Any]]:
        next_url: str | None = url
        next_params = params
        visited: set[str] = set()
        page_count = 0
        while next_url:
            _raise_if_cancelled(cancellation)
            if next_url in visited or page_count >= max_pages:
                raise InvalidResponseError("MyAnimeList pagination did not terminate safely.")
            visited.add(next_url)
            page = self.get_json(
                next_url,
                params=next_params,
                access_token=access_token,
                client_id=client_id,
                cancellation=cancellation,
            )
            yield page
            page_count += 1
            paging = page.get("paging")
            next_value = paging.get("next") if isinstance(paging, Mapping) else None
            next_url = next_value if isinstance(next_value, str) and next_value else None
            next_params = None

    @staticmethod
    def _raise_status_error(status: int, headers: Mapping[str, Any]) -> None:
        if status == 401:
            raise AuthError("MyAnimeList returned HTTP 401.")
        if status == 403:
            raise AccessDeniedError("MyAnimeList returned HTTP 403.")
        if status == 404:
            raise NotFoundError("MyAnimeList returned HTTP 404.")
        if status == 429:
            raise RateLimitError(
                "MyAnimeList returned HTTP 429.",
                retry_after_seconds=_safe_retry_after(headers.get("Retry-After")),
            )
        if status >= 500:
            raise ServerError(f"MyAnimeList returned HTTP {status}.")
        raise NetworkError(f"MyAnimeList returned HTTP {status}.")


def _safe_retry_after(value: object) -> int | None:
    try:
        seconds = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return seconds if 0 <= seconds <= 86_400 else None


def _raise_if_cancelled(cancellation) -> None:
    if cancellation is None:
        return
    checker = getattr(cancellation, "raise_if_cancelled", None)
    if callable(checker):
        checker()
        return
    value = getattr(cancellation, "is_cancelled", cancellation)
    if callable(value):
        value = value()
    if value:
        raise CancelledError("MyAnimeList request cancellation requested.")
