"""Sign a test reader in, the way the web client is (D-021).

The API scopes every reader route to the session's account and the import it
owns; it never reads the machine-wide active profile. Tests that need a
reader's data therefore sign one in and give the account the import, rather
than calling ``ProfileService.set_active``.
"""

from __future__ import annotations

import secrets

from AniRec.services.account_service import SESSION_COOKIE


def sign_in_reader(client, profile_id: str | None = None, *, services=None, email: str | None = None) -> str:
    """Register an account, give it ``profile_id``, and put its cookie on ``client``.

    Returns the account ID. ``services`` defaults to the client's app container.
    """
    services = services or client.app.state.container
    signed = services.accounts.register(email or f"reader-{secrets.token_hex(4)}@example.com", "a long password")
    if profile_id is not None:
        services.accounts.add_import(signed.account.account_id, profile_id)
    client.cookies.set(SESSION_COOKIE, signed.token)
    return signed.account.account_id
