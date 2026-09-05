"""The threat model for a local HTTP service, and the smallest fix for it.

A browser enforces same-origin policy for *reading* a cross-origin response,
but not for *sending* a cross-origin request. A page open in an unrelated
browser tab can already issue a POST to ``http://127.0.0.1:8770/api/...``
today; CORS blocks that page's JavaScript from reading what comes back, not
the server from acting on it. For a GET that only leaks data, CORS is most of
the fix. For a POST that starts a MyAnimeList sync, records a vote, or drives
an operation this process holds a live access token for, CORS alone leaves a
blind write open to any page the user happens to have loaded - the classic
"localhost is not a security boundary" finding, not a hypothetical one.

This is worth a real fix specifically *because* Tauri changes what this
process is. The development server on a fixed dev port is a tool one person
runs, understands, and closes; a packaged desktop application's sidecar is a
service that starts every time a consumer double-clicks an icon, on a machine
whose other tabs and processes the product has no say over.

The fix, sized to that model rather than to an enterprise one:

* bind to loopback only - enforced by the launcher, not by this module, and
  never overridable by an environment variable;
* a random per-launch port - so the address is not a fixed target;
* a random per-launch bearer token, known only to the process that spawned
  this one and to the frontend it hands the token to - so even a page that
  guesses the port cannot act without also knowing a value that exists
  nowhere on disk and was never sent to any other origin;
* constant-time comparison, because a timing side-channel on a bearer check
  is a real if narrow attack and costs nothing to close.

What this deliberately does not do: no session store, no login form, no
per-endpoint scopes, no refresh flow. One shared secret for one process's
lifetime is the right amount of ceremony for a service that dies with the
window that opened it.

Enforcement is opt-in via ``ANIREC_API_TOKEN`` so the existing plain
``python -m AniRec.api`` browser-development workflow - a developer running a
fixed local port they already understand the risk of - is unchanged. A
Tauri-launched process always sets it.
"""

from __future__ import annotations

import os
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

TOKEN_HEADER = "X-AniRec-Token"
TOKEN_ENV_VAR = "ANIREC_API_TOKEN"

# Never sent over the wire in the clear as a query parameter: that would land
# in access logs and browser history. Header only.
_UNAUTHORIZED = JSONResponse(
    status_code=401,
    content={
        "error": {
            "code": "unauthorized",
            "title": "AniRec could not verify this request",
            "description": "The local API requires its per-launch token.",
            "solution": "Restart AniRec. This should not happen through normal use.",
            "retryable": False,
        }
    },
)


def generate_token() -> str:
    """A fresh per-launch secret. 32 random bytes, URL-safe text."""
    return secrets.token_urlsafe(32)


class TokenAuthMiddleware(BaseHTTPMiddleware):
    """Reject any ``/api/*`` request that does not carry the current token.

    Every route under ``/api/`` is covered, ``/api/health`` included: a
    liveness probe leaks nothing sensitive on its own, but the frontend
    already has the token before it makes its first request - Rust hands it
    over at the same moment it hands over the port - so exempting health
    buys convenience nobody needs at the cost of one more rule to remember.

    ``/docs``, ``/redoc`` and ``/openapi.json`` are outside ``/api/`` and are
    intentionally left unauthenticated when a token is not required; when one
    is, ``create_app`` disables them outright rather than gating them here -
    see its docstring.
    """

    def __init__(self, app: ASGIApp, *, token: str) -> None:
        super().__init__(app)
        self._token = token

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/"):
            if not secrets.compare_digest(self._supplied(request), self._token):
                return _UNAUTHORIZED
        return await call_next(request)

    def _supplied(self, request: Request) -> str:
        """The token this request carries, from the header or - narrowly - a query.

        The header is the rule. The exception is the server-sent-events
        stream, because the browser's ``EventSource`` cannot set request
        headers at all; a client that could only authenticate by header would
        have to hand-roll SSE over ``fetch`` to use it.

        This is a deliberate, bounded narrowing rather than a general
        fallback, and it is confined to exactly one read-only GET route:

        * the URL never leaves the machine - the service is bound to
          loopback, so there is no proxy, gateway or CDN access log to leak
          into;
        * the route mutates nothing, so a leaked URL cannot be replayed into
          a state change;
        * the token dies with the process that issued it.

        Every other route, and every state-mutating request, still requires
        the header.
        """
        header = request.headers.get(TOKEN_HEADER, "")
        if header:
            return header
        if request.method == "GET" and request.url.path.endswith("/events"):
            return request.query_params.get("token", "")
        return ""


def token_from_environment() -> str | None:
    """The token this process should require, or ``None`` to require none."""
    value = os.environ.get(TOKEN_ENV_VAR, "").strip()
    return value or None
