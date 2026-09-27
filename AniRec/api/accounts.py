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
import json
import sys
from dataclasses import dataclass, replace
from datetime import datetime, timezone

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
    is_web_import,
)
from .container import ApiContainer
from .limits import ClientLimits
from .models import AccountSummary, ApiModel


@dataclass(frozen=True)
class ReaderScope:
    """Who is asking, and the import they may act on."""

    account: Account | None
    profile: UserProfile | None
    token: str | None
    # The session's lifetime was just extended: re-send the cookie.
    renewed: bool = False

    @property
    def profile_id(self) -> str | None:
        return None if self.profile is None else self.profile.profile_id


def session_token(request: Request) -> str | None:
    return request.cookies.get(SESSION_COOKIE) or None


def resolve_scope(services: ApiContainer, request: Request) -> ReaderScope:
    token = session_token(request)
    account, renewed = services.accounts.session(token)
    if account is None:
        return ReaderScope(None, None, None)
    profile = None
    profile_id = account.active_profile_id
    try:
        owned = bool(profile_id) and services.accounts.owns(account.account_id, profile_id)
    except AccountError:
        # The account database became unreadable mid-request: act anonymous.
        return ReaderScope(None, None, None)
    if owned:
        try:
            profile = services.profiles.get_profile(profile_id)
        except (AniRecError, OSError, TypeError, ValueError):  # missing or unreadable: no import
            profile = None
    return ReaderScope(account, profile, token, renewed)


def renew_cookie(request: Request, response: Response, scope: ReaderScope, limits: "ClientLimits") -> None:
    """A session in use lives on: send its cookie again with a full lifetime."""
    if scope.renewed and scope.token:
        set_session_cookie(request, response, scope.token, limits)


def reader_pipeline(services: ApiContainer, scope: ReaderScope):
    """The pipeline settings this reader's operations rank with.

    The installation owner's preferences are the installation settings; any
    other account's saved ones replace them. NSFW is never inherited: an
    account that never chose it gets it off (docs/ACCOUNTS.md).
    """
    installation = services.settings.load().pipeline
    account = scope.account
    if account is None or is_installation_owner(services, scope):
        return installation
    try:
        saved = services.accounts.preferences(account.account_id)
    except AccountError:
        saved = {}
    return replace(
        installation,
        randomness_factor=int(saved.get("adventurousness", installation.randomness_factor)),
        minimum_mean_score=saved.get("minimum_mal_score", installation.minimum_mean_score),
        include_nsfw=bool(saved.get("include_nsfw", False)),
    )


def set_session_cookie(request: Request, response: Response, token: str, limits: ClientLimits) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        path="/",
        httponly=True,
        samesite="lax",
        # Behind a trusted proxy, HTTPS is what the proxy reports (limits.py).
        secure=limits.is_https(request),
    )


def clear_session_cookie(request: Request, response: Response, limits: ClientLimits) -> None:
    response.delete_cookie(
        SESSION_COOKIE, path="/", httponly=True, samesite="lax",
        secure=limits.is_https(request),
    )


def is_installation_owner(services: ApiContainer, scope: ReaderScope) -> bool:
    """Whether this reader is the owner the operator named from the console."""
    account = scope.account
    if account is None or not account.registered:
        return False
    try:
        return services.accounts.owner_account_id() == account.account_id
    except AccountError:
        return False


class AccountResponse(ApiModel):
    account: AccountSummary | None = None
    moved_imports: int = Field(
        default=0, description="Lists a guest brought along when signing in to this account."
    )
    reason: str | None = Field(
        default=None,
        description=(
            "invalid-email, weak-password, password-too-long, email-taken, wrong-credentials, "
            "too-many-attempts, already-signed-in, busy or unavailable."
        ),
    )


class ImportSummary(ApiModel):
    profile_id: str
    username: str
    kept_on_delete: bool = Field(
        default=False,
        description="Deleting the account keeps this list for the desktop tool rather than deleting it.",
    )


class ImportsResponse(ApiModel):
    """The lists this account has imported, and which one is shown."""

    imports: tuple[ImportSummary, ...] = ()
    active_profile_id: str | None = None
    reason: str | None = Field(default=None, description="signed-out, not-owner or unavailable.")


class ActiveImportRequest(ApiModel):
    profile_id: str = Field(max_length=128)


class PasswordChange(ApiModel):
    current_password: str = Field(max_length=PASSWORD_MAX)
    new_password: str = Field(max_length=PASSWORD_MAX)


class PasswordResetRequest(ApiModel):
    email: str = Field(max_length=254)


class PasswordResetConfirm(ApiModel):
    token: str = Field(max_length=512)
    # Capped here, before any hashing happens (docs/ACCOUNTS.md, "Passwords").
    new_password: str = Field(max_length=PASSWORD_MAX)


class PasswordResetResponse(ApiModel):
    reason: str | None = Field(
        default=None,
        description=(
            "Never depends on whether an account uses the email. Asking: reset-unavailable, invalid-email, "
            "too-many-attempts or busy. Confirming: invalid-token, weak-password, password-too-long, "
            "too-many-attempts, busy or unavailable."
        ),
    )


class DeleteRequest(ApiModel):
    # Registered accounts only; a guest has no password.
    password: str | None = Field(default=None, max_length=PASSWORD_MAX)


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
        installation_owner=is_installation_owner(services, scope),
    )


NO_STORE = {"Cache-Control": "no-store"}


def accounts_router(services: ApiContainer, limits: ClientLimits, maintenance) -> APIRouter:
    router = APIRouter(prefix="/api/account")

    def signed_in(request: Request, response: Response, signed: SignedIn) -> AccountResponse:
        set_session_cookie(request, response, signed.token, limits)
        # A fresh scope from the new token, not the request's old cookie.
        profile = None
        if signed.account.active_profile_id:
            try:
                profile = services.profiles.get_profile(signed.account.active_profile_id)
            except (AniRecError, OSError, TypeError, ValueError):
                profile = None
        return AccountResponse(
            account=account_summary(services, ReaderScope(signed.account, profile, signed.token)),
            moved_imports=len(signed.moved_profile_ids),
        )

    @router.get("", response_model=AccountResponse)
    def read_account(request: Request, response: Response) -> AccountResponse:
        response.headers.update(NO_STORE)
        scope = resolve_scope(services, request)
        renew_cookie(request, response, scope, limits)
        return AccountResponse(account=account_summary(services, scope))

    @router.post("/register", response_model=AccountResponse)
    def register(payload: Credentials, request: Request, response: Response) -> AccountResponse:
        # Upgrading this visitor's guest account is not a new account; any
        # other registration counts against this visitor's hourly limit, but
        # only once it succeeds: a mistyped attempt spends nothing.
        client = limits.client(request)
        new_account = scope_of(request, response).account is None
        if new_account and limits.new_accounts.full(client):
            return AccountResponse(reason="busy")
        try:
            signed = services.accounts.register(payload.email, payload.password, current_token=session_token(request))
        except AccountError as error:
            return AccountResponse(reason=error.reason)
        except OSError:
            return AccountResponse(reason="unavailable")
        if new_account:
            limits.new_accounts.take(client)
        return signed_in(request, response, signed)

    @router.post("/sign-in", response_model=AccountResponse)
    def sign_in(payload: Credentials, request: Request, response: Response) -> AccountResponse:
        # Per visitor, across every email (password spraying). The service
        # also counts per email and visitor, with a higher ceiling per email
        # from everyone, so no single visitor can lock a reader out.
        client = limits.client(request)
        if limits.sign_in_failures.full(client):
            return AccountResponse(reason="too-many-attempts")
        try:
            signed = services.accounts.sign_in(
                payload.email, payload.password, current_token=session_token(request), client=client
            )
        except AccountError as error:
            if error.reason == "wrong-credentials":
                limits.sign_in_failures.take(client)
            return AccountResponse(reason=error.reason)
        except OSError:
            return AccountResponse(reason="unavailable")
        return signed_in(request, response, signed)

    @router.post("/sign-out", response_model=AccountResponse)
    def sign_out(request: Request, response: Response) -> AccountResponse:
        services.accounts.sign_out(session_token(request))
        clear_session_cookie(request, response, limits)
        return AccountResponse()

    def scope_of(request: Request, response: Response) -> ReaderScope:
        """The scope, re-sending the cookie when using it renewed the session."""
        scope = resolve_scope(services, request)
        renew_cookie(request, response, scope, limits)
        return scope

    def counted(request: Request, check) -> None:
        """A password check counted as a sign-in for this visitor."""
        client = limits.client(request)
        if limits.sign_in_failures.full(client):
            raise AccountError("too-many-attempts")
        try:
            check(client)
        except AccountError as error:
            if error.reason == "wrong-credentials":
                limits.sign_in_failures.take(client)
            raise

    @router.post("/password", response_model=AccountResponse)
    def change_password(payload: PasswordChange, request: Request, response: Response) -> AccountResponse:
        scope = scope_of(request, response)
        if scope.account is None:
            return AccountResponse(reason="signed-out")
        if not scope.account.registered:
            return AccountResponse(reason="not-registered")
        result: list[SignedIn] = []
        try:
            counted(request, lambda client: result.append(services.accounts.change_password(
                scope.account.account_id, payload.current_password, payload.new_password, client=client)))
        except AccountError as error:
            return AccountResponse(reason=error.reason)
        return signed_in(request, response, result[0])

    @router.post("/password-reset", response_model=PasswordResetResponse)
    def request_password_reset(payload: PasswordResetRequest, request: Request) -> PasswordResetResponse:
        """Queue a reset link for the email; the same answer whether or not an
        account uses it (docs/ACCOUNTS.md, "Password reset by email")."""
        resets = services.password_resets
        if not resets.available:
            return PasswordResetResponse(reason="reset-unavailable")
        if not limits.password_resets.take(limits.client(request)):
            return PasswordResetResponse(reason="too-many-attempts")
        try:
            resets.request(payload.email)
        except AccountError as error:
            return PasswordResetResponse(reason=error.reason)
        return PasswordResetResponse()

    @router.post("/password-reset/confirm", response_model=PasswordResetResponse)
    def confirm_password_reset(payload: PasswordResetConfirm, request: Request) -> PasswordResetResponse:
        """Set a new password from an emailed token. Every session of the
        account ends; this browser is not signed in."""
        client = limits.client(request)
        if limits.sign_in_failures.full(client):
            return PasswordResetResponse(reason="too-many-attempts")
        try:
            services.password_resets.confirm(payload.token, payload.new_password)
        except AccountError as error:
            if error.reason == "invalid-token":
                limits.sign_in_failures.take(client)
            return PasswordResetResponse(reason=error.reason)
        return PasswordResetResponse()

    @router.post("/delete", response_model=AccountResponse)
    def delete_account(payload: DeleteRequest, request: Request, response: Response) -> AccountResponse:
        """Delete the account and every list it owns (docs/ACCOUNTS.md)."""
        scope = scope_of(request, response)
        account = scope.account
        if account is None:
            return AccountResponse(reason="signed-out")
        try:
            if account.registered:
                counted(request, lambda client: services.accounts.confirm_password(
                    account.account_id, payload.password or "", client=client))
            maintenance.delete_account(account.account_id)
        except AccountError as error:
            return AccountResponse(reason=error.reason)
        clear_session_cookie(request, response, limits)
        return AccountResponse()

    @router.get("/export")
    def export(request: Request) -> Response:
        """Everything this account holds, as one JSON file for its reader."""
        scope = resolve_scope(services, request)
        account = scope.account
        if account is None:
            return Response(status_code=401, headers=NO_STORE)
        if not limits.exports.take(limits.client(request)):
            return Response(status_code=429, headers=NO_STORE)
        try:
            details = services.accounts.account_details(account.account_id) or {}
            preferences = services.accounts.preferences(account.account_id)
            owned = services.accounts.owned_profile_ids(account.account_id)
        except AccountError:
            return Response(status_code=503, headers=NO_STORE)
        from ..services.recommendation_event_service import RecommendationEventService

        activity = RecommendationEventService(services.profiles.root_override)
        lists = []
        for profile_id in owned:
            try:
                profile = services.profiles.get_profile(profile_id)
            except (AniRecError, OSError, TypeError, ValueError):
                continue
            state = services.recommendation_state.load(profile_id).to_storage_dict()
            lists.append({
                "username": profile.username,
                "saved": state,
                "activity": {**activity.status(profile_id), "events": activity.export(profile_id)},
            })
        body = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "account": details,
            "preferences": preferences,
            "lists": lists,
        }
        download = Response(
            content=json.dumps(body, indent=2, sort_keys=True, default=str),
            media_type="application/json",
            headers={**NO_STORE, "Content-Disposition": 'attachment; filename="anirec-export.json"'},
        )
        renew_cookie(request, download, scope, limits)
        return download

    def imports_of(scope: ReaderScope, reason: str | None = None) -> ImportsResponse:
        account = scope.account
        if account is None:
            return ImportsResponse(reason=reason)
        items = []
        try:
            owned = services.accounts.owned_profile_ids(account.account_id)
            current = services.accounts.account_for_session(scope.token)
        except AccountError:
            return ImportsResponse(reason="unavailable")
        desktop = services.profiles.desktop_active_profile_id()
        for profile_id in owned:
            try:
                items.append(ImportSummary(
                    profile_id=profile_id,
                    username=services.profiles.get_profile(profile_id).username,
                    kept_on_delete=not is_web_import(profile_id) or profile_id == desktop,
                ))
            except (AniRecError, OSError, TypeError, ValueError):
                continue   # an unreadable import is not offered
        active = None if current is None else current.active_profile_id
        return ImportsResponse(imports=tuple(items), active_profile_id=active, reason=reason)

    @router.get("/imports", response_model=ImportsResponse)
    def list_imports(request: Request, response: Response) -> ImportsResponse:
        return imports_of(scope_of(request, response))

    @router.post("/imports/active", response_model=ImportsResponse)
    def choose_import(payload: ActiveImportRequest, request: Request, response: Response) -> ImportsResponse:
        """Show another of this account's lists. Only its own (D-021)."""
        scope = scope_of(request, response)
        if scope.account is None:
            return ImportsResponse(reason="signed-out")
        try:
            services.accounts.set_active(scope.account.account_id, payload.profile_id)
        except AccountError as error:
            return imports_of(scope, error.reason)
        return imports_of(scope)

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
