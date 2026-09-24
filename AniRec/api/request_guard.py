"""Host and Origin checks for every ``/api/`` request (D-021).

A session cookie is sent by the browser on its own, so a page on another
origin could make a signed-in reader's browser act, and ``SameSite`` does not
separate two ports on one host. Two checks close that:

* **Host**, on every request: its name must be loopback or explicitly allowed.
  That stops DNS rebinding, where a page on ``evil.test`` re-resolves to
  ``127.0.0.1`` and becomes same-origin with this API.
* **Origin**, on every write: when present it must be one of the configured
  origins, never derived from ``Host``; ``null`` is refused. A write with no
  ``Origin`` is accepted only when ``Sec-Fetch-Site`` does not call it
  cross-origin: browsers send ``Origin`` on every cross-origin write, and a
  non-browser client cannot hold a reader's cookie.

Reads stay governed by CORS, as before. See ``docs/ACCOUNTS.md``.
"""

from __future__ import annotations

import os

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

HOSTS_ENV_VAR = "ANIREC_ALLOWED_HOSTS"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})
_WRITES = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def allowed_hosts_from_environment() -> frozenset[str]:
    extra = os.environ.get(HOSTS_ENV_VAR, "")
    return LOOPBACK_HOSTS | {name.strip().lower() for name in extra.split(",") if name.strip()}


def _host_name(value: str) -> str:
    value = value.strip().lower()
    if value.startswith("["):   # [::1]:8770
        return value.split("]")[0] + "]"
    return value.rsplit(":", 1)[0] if value.count(":") == 1 else value


def _refusal(title: str) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"error": {
            "code": "forbidden_origin",
            "title": title,
            "description": "AniRec only accepts requests from its own pages.",
            "solution": "Open AniRec from its usual address and try again.",
            "retryable": False,
        }},
    )


class RequestGuardMiddleware:
    def __init__(self, app: ASGIApp, *, origins: tuple[str, ...], hosts: frozenset[str]) -> None:
        self.app = app
        self._origins = frozenset(origin.rstrip("/").lower() for origin in origins)
        self._hosts = hosts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            await self.app(scope, receive, send)
            return
        headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope["headers"]}
        if _host_name(headers.get("host", "")) not in self._hosts:
            await _refusal("AniRec did not recognise the address this request used")(scope, receive, send)
            return
        if scope["method"] in _WRITES:
            origin = headers.get("origin")
            if origin is not None:
                if origin.rstrip("/").lower() not in self._origins:
                    await _refusal("AniRec refused a request from another site")(scope, receive, send)
                    return
            elif headers.get("sec-fetch-site", "same-origin") not in ("same-origin", "none"):
                await _refusal("AniRec refused a request from another site")(scope, receive, send)
                return
        await self.app(scope, receive, send)
