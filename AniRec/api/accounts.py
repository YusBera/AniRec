"""Accounts over HTTP, and the scope every reader-owned route runs in (D-021).

``reader_scope`` is the only way a route learns whose data it may touch: the
session cookie names an account, the account names its active import, and the
import counts only if the account owns it. A ``profile_id`` or username in a
request is never authority; routes compare it against the scope.

Run as a module, this is also the operator's console command that names the
installation owner (``docs/ACCOUNTS.md``, "The installation owner"):

    python -m AniRec.api.accounts owner reader@example.com [--root DIR]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from fastapi import APIRouter, Request, Response
from pydantic import Field

from ..errors import AniRecError
from ..models import UserProfile
from ..services.account_service import (
    PASSWORD_MAX,
    SESSION_COOKIE,
    SESSION_LIFETIME,
    Account,
    AccountError,
    AccountService,
    SignedIn,
)
from .container import ApiContainer
from .models import AccountSummary, ApiModel


@dataclass(frozen=True)
class ReaderScope:
    """Who is asking, and the import they may act on."""

    account: Account | None
    profile: UserProfile | None
    token: str | None

    @property
    def profile_id(self) -> str | None:
        return None if self.profile is None else self.profile.profile_id


def session_token(request: Request) -> str | None:
    return request.cookies.get(SESSION_COOKIE) or None


def resolve_scope(services: ApiContainer, request: Request) -> ReaderScope:
    token = session_token(request)
    account = services.accounts.account_for_session(token)
    if account is None:
        return ReaderScope(None, None, None)
    profile = None
    profile_id = account.active_profile_id
    if profile_id and services.accounts.owns(account.account_id, profile_id):
        try:
            profile = services.profiles.get_profile(profile_id)
        except (AniRecError, OSError, TypeError, ValueError):  # missing or unreadable: no import
            profile = None
    return ReaderScope(account, profile, token)


def set_session_cookie(request: Request, response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        path="/",
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
    )


def clear_session_cookie(request: Request, response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE, path="/", httponly=True, samesite="lax",
        secure=request.url.scheme == "https",
    )


class AccountResponse(ApiModel):
    account: AccountSummary | None = None
    reason: str | None = Field(
        default=None,
        description=(
            "invalid-email, weak-password, password-too-long, email-taken, wrong-credentials, "
            "too-many-attempts, already-signed-in, busy or unavailable."
        ),
    )


class Credentials(ApiModel):
    email: str = Field(max_length=254)
    # Capped here, before any hashing happens (docs/ACCOUNTS.md, "Passwords").
    password: str = Field(max_length=PASSWORD_MAX)


def account_summary(services: ApiContainer, scope: ReaderScope) -> AccountSummary | None:
    account = scope.account
    if account is None:
        return None
    return AccountSummary(
        kind=account.kind,
        email=account.email if account.registered else None,
        has_import=scope.profile is not None,
        installation_owner=account.registered and services.accounts.owner_account_id() == account.account_id,
    )


def accounts_router(services: ApiContainer) -> APIRouter:
    router = APIRouter(prefix="/api/account")

    def signed_in(request: Request, response: Response, signed: SignedIn) -> AccountResponse:
        set_session_cookie(request, response, signed.token)
        # A fresh scope from the new token, not the request's old cookie.
        profile = None
        if signed.account.active_profile_id:
            try:
                profile = services.profiles.get_profile(signed.account.active_profile_id)
            except (AniRecError, OSError, TypeError, ValueError):
                profile = None
        return AccountResponse(account=account_summary(services, ReaderScope(signed.account, profile, signed.token)))

    @router.get("", response_model=AccountResponse)
    def read_account(request: Request) -> AccountResponse:
        return AccountResponse(account=account_summary(services, resolve_scope(services, request)))

    @router.post("/register", response_model=AccountResponse)
    def register(payload: Credentials, request: Request, response: Response) -> AccountResponse:
        try:
            signed = services.accounts.register(payload.email, payload.password, current_token=session_token(request))
        except AccountError as error:
            return AccountResponse(reason=error.reason)
        except OSError:
            return AccountResponse(reason="unavailable")
        return signed_in(request, response, signed)

    @router.post("/sign-in", response_model=AccountResponse)
    def sign_in(payload: Credentials, request: Request, response: Response) -> AccountResponse:
        try:
            signed = services.accounts.sign_in(payload.email, payload.password, current_token=session_token(request))
        except AccountError as error:
            return AccountResponse(reason=error.reason)
        except OSError:
            return AccountResponse(reason="unavailable")
        return signed_in(request, response, signed)

    @router.post("/sign-out", response_model=AccountResponse)
    def sign_out(request: Request, response: Response) -> AccountResponse:
        services.accounts.sign_out(session_token(request))
        clear_session_cookie(request, response)
        return AccountResponse()

    return router


def unowned_profile_ids(services_accounts: AccountService, profiles) -> tuple[str, ...]:
    return tuple(p.profile_id for p in profiles.list_profiles() if not services_accounts.is_owned(p.profile_id))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m AniRec.api.accounts", description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", default=None, help="AniRec data directory (defaults to the normal one).")
    commands = parser.add_subparsers(dest="command", required=True)
    owner = commands.add_parser("owner", help="Name the installation owner and give them every unowned import.")
    owner.add_argument("email")
    args = parser.parse_args(argv)

    from ..services.profile_service import ProfileService

    accounts = AccountService(root_override=args.root)
    profiles = ProfileService(root_override=args.root)
    try:
        account, claimed = accounts.set_owner(args.email, unowned_profile_ids(accounts, profiles))
    except AccountError as error:
        if error.reason == "no-such-account":
            print("No registered account uses that email. Create the account in AniRec first.", file=sys.stderr)
        else:
            print("That is not a valid email address.", file=sys.stderr)
        return 1
    print(f"{account.email} now owns this AniRec installation.")
    if claimed:
        print("Imports added to that account: " + ", ".join(claimed))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
