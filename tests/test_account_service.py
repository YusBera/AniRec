"""AniRec accounts (D-021): passwords, sessions, guests, and ownership.

The rule under test: an account the server assigned owns every import; a
MyAnimeList name never selects one, and nothing reaches across accounts.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from AniRec.services.account_service import (
    AccountError,
    AccountService,
    FAILURE_LIMIT,
    RateWindow,
    SESSION_LIFETIME,
    hash_password,
    verify_password,
)


class Clock:
    def __init__(self):
        self.now = datetime(2026, 9, 24, 12, tzinfo=timezone.utc)

    def __call__(self):
        return self.now


def _service(tmp_path, clock=None):
    return AccountService(root_override=tmp_path, clock=clock or Clock())


def test_a_password_hash_verifies_only_the_same_password_and_never_contains_it():
    stored = hash_password("correct horse")
    assert stored.startswith("scrypt$15$8$1$")
    assert "correct horse" not in stored
    assert verify_password("correct horse", stored)
    assert not verify_password("correct horsE", stored)
    assert not verify_password("anything", "not-a-hash")


def test_registering_gives_a_fresh_session_and_stores_only_a_digest(tmp_path):
    accounts = _service(tmp_path)
    signed = accounts.register("Reader@Example.com ", "a long password")
    assert signed.account.registered and signed.account.email == "reader@example.com"
    assert accounts.account_for_session(signed.token) == signed.account
    raw = accounts.path.read_bytes()
    assert signed.token.encode() not in raw
    assert b"a long password" not in raw


@pytest.mark.parametrize(("email", "password", "reason"), [
    ("not-an-email", "a long password", "invalid-email"),
    ("reader@example.com", "short", "weak-password"),
    ("reader@example.com", "x" * 257, "password-too-long"),
])
def test_registration_refuses_bad_input_with_a_reason(tmp_path, email, password, reason):
    with pytest.raises(AccountError) as refused:
        _service(tmp_path).register(email, password)
    assert refused.value.reason == reason


def test_an_email_can_hold_only_one_account(tmp_path):
    accounts = _service(tmp_path)
    accounts.register("reader@example.com", "a long password")
    with pytest.raises(AccountError) as refused:
        accounts.register("READER@example.com", "another password")
    assert refused.value.reason == "email-taken"


def test_sign_in_checks_the_password_and_replaces_the_session(tmp_path):
    accounts = _service(tmp_path)
    first = accounts.register("reader@example.com", "a long password")
    with pytest.raises(AccountError) as refused:
        accounts.sign_in("reader@example.com", "wrong password")
    assert refused.value.reason == "wrong-credentials"
    with pytest.raises(AccountError) as unknown:
        accounts.sign_in("nobody@example.com", "a long password")
    assert unknown.value.reason == "wrong-credentials"   # the same words either way
    again = accounts.sign_in("reader@example.com", "a long password", current_token=first.token)
    assert again.account.account_id == first.account.account_id
    assert again.token != first.token
    assert accounts.account_for_session(first.token) is None   # rotated, not reused


def test_repeated_wrong_passwords_are_throttled_then_allowed_again(tmp_path):
    clock = Clock()
    accounts = _service(tmp_path, clock)
    accounts.register("reader@example.com", "a long password")
    for _ in range(FAILURE_LIMIT):
        with pytest.raises(AccountError):
            accounts.sign_in("reader@example.com", "wrong password")
    with pytest.raises(AccountError) as locked:
        accounts.sign_in("reader@example.com", "a long password")
    assert locked.value.reason == "too-many-attempts"
    clock.now += timedelta(minutes=16)
    assert accounts.sign_in("reader@example.com", "a long password").account.email == "reader@example.com"


def test_a_session_expires_and_signing_out_ends_it(tmp_path):
    clock = Clock()
    accounts = _service(tmp_path, clock)
    signed = accounts.register("reader@example.com", "a long password")
    clock.now += SESSION_LIFETIME + timedelta(seconds=1)
    assert accounts.account_for_session(signed.token) is None
    fresh = accounts.sign_in("reader@example.com", "a long password")
    accounts.sign_out(fresh.token)
    assert accounts.account_for_session(fresh.token) is None
    assert accounts.account_for_session("made-up") is None


def test_registering_as_a_guest_keeps_the_same_account_and_its_imports(tmp_path):
    accounts = _service(tmp_path)
    guest = accounts.create_guest()
    accounts.add_import(guest.account.account_id, "imp_one")
    registered = accounts.register("reader@example.com", "a long password", current_token=guest.token)
    assert registered.account.account_id == guest.account.account_id
    assert registered.account.active_profile_id == "imp_one"
    assert accounts.account_for_session(guest.token) is None


def test_a_guest_signing_in_brings_their_import_to_the_account(tmp_path):
    accounts = _service(tmp_path)
    reader = accounts.register("reader@example.com", "a long password")
    accounts.sign_out(reader.token)
    guest = accounts.create_guest()
    accounts.add_import(guest.account.account_id, "imp_guest")
    signed = accounts.sign_in("reader@example.com", "a long password", current_token=guest.token)
    assert signed.moved_profile_ids == ("imp_guest",)
    assert accounts.owns(reader.account.account_id, "imp_guest")
    assert signed.account.active_profile_id == "imp_guest"   # the account had none
    assert accounts.account_for_session(guest.token) is None


def test_a_guest_import_does_not_replace_an_accounts_active_one(tmp_path):
    accounts = _service(tmp_path)
    reader = accounts.register("reader@example.com", "a long password")
    accounts.add_import(reader.account.account_id, "imp_mine")
    guest = accounts.create_guest()
    accounts.add_import(guest.account.account_id, "imp_guest")
    signed = accounts.sign_in("reader@example.com", "a long password", current_token=guest.token)
    assert signed.account.active_profile_id == "imp_mine"
    assert set(accounts.owned_profile_ids(reader.account.account_id)) == {"imp_mine", "imp_guest"}


def test_an_account_cannot_activate_an_import_it_does_not_own(tmp_path):
    accounts = _service(tmp_path)
    one = accounts.register("one@example.com", "a long password")
    two = accounts.register("two@example.com", "a long password")
    accounts.add_import(one.account.account_id, "imp_one")
    with pytest.raises(AccountError) as refused:
        accounts.set_active(two.account.account_id, "imp_one")
    assert refused.value.reason == "not-owner"
    assert not accounts.owns(two.account.account_id, "imp_one")


def test_a_cookie_planted_before_registering_reaches_nothing_afterwards(tmp_path):
    accounts = _service(tmp_path)
    guest = accounts.create_guest()
    # Another page on this machine could plant the same guest cookie; model it
    # as a second session on the same guest account.
    with accounts._transaction() as conn:
        planted = accounts._new_session(conn, guest.account.account_id)
    registered = accounts.register("reader@example.com", "a long password", current_token=guest.token)
    assert accounts.account_for_session(planted) is None
    assert accounts.account_for_session(registered.token).registered


def test_registering_while_signed_in_is_refused(tmp_path):
    accounts = _service(tmp_path)
    signed = accounts.register("reader@example.com", "a long password")
    with pytest.raises(AccountError) as refused:
        accounts.register("other@example.com", "a long password", current_token=signed.token)
    assert refused.value.reason == "already-signed-in"


def test_an_unknown_email_is_throttled_like_a_known_one(tmp_path):
    accounts = _service(tmp_path)
    for _ in range(FAILURE_LIMIT):
        with pytest.raises(AccountError):
            accounts.sign_in("nobody@example.com", "wrong password")
    with pytest.raises(AccountError) as locked:
        accounts.sign_in("nobody@example.com", "wrong password")
    assert locked.value.reason == "too-many-attempts"


def test_new_accounts_are_capped_process_wide(tmp_path):
    accounts = AccountService(root_override=tmp_path, clock=Clock(), new_accounts=RateWindow(2, 3600))
    accounts.create_guest()
    accounts.create_guest()
    with pytest.raises(AccountError) as refused:
        accounts.create_guest()
    assert refused.value.reason == "busy"


def test_an_import_for_a_guest_that_signed_in_elsewhere_is_refused(tmp_path):
    accounts = _service(tmp_path)
    reader = accounts.register("reader@example.com", "a long password")
    guest = accounts.create_guest()
    accounts.sign_in("reader@example.com", "a long password", current_token=guest.token)
    with pytest.raises(AccountError) as refused:
        accounts.add_import(guest.account.account_id, "imp_late")
    assert refused.value.reason == "session-ended"
    assert not accounts.is_owned("imp_late")
    assert reader.account.account_id != guest.account.account_id


def test_the_console_names_the_owner_and_gives_them_every_unowned_import(tmp_path):
    accounts = _service(tmp_path)
    guest = accounts.create_guest()
    accounts.add_import(guest.account.account_id, "imp_guest")
    owner = accounts.register("owner@example.com", "a long password")
    assert accounts.owner_account_id() is None   # registering first makes no one owner
    account, claimed = accounts.set_owner("OWNER@example.com", ["mal-123", "reader_01", "imp_guest"])
    assert claimed == ("mal-123", "reader_01")   # never another account's import
    assert accounts.owner_account_id() == owner.account.account_id
    assert account.active_profile_id == "mal-123"
    assert accounts.owns(guest.account.account_id, "imp_guest")
    with pytest.raises(AccountError) as unknown:
        accounts.set_owner("nobody@example.com", [])
    assert unknown.value.reason == "no-such-account"


def test_a_busy_refusal_is_not_counted_as_a_failed_attempt(tmp_path, monkeypatch):
    import AniRec.services.account_service as module

    accounts = _service(tmp_path)
    accounts.register("reader@example.com", "a long password")

    class Full:
        def acquire(self, blocking=True):
            return False

        def release(self):
            raise AssertionError("released a slot never taken")

    real = module._HASH_SLOTS
    monkeypatch.setattr(module, "_HASH_SLOTS", Full())
    for _ in range(FAILURE_LIMIT + 2):
        with pytest.raises(AccountError) as busy:
            accounts.sign_in("reader@example.com", "a long password")
        assert busy.value.reason == "busy"
    monkeypatch.setattr(module, "_HASH_SLOTS", real)
    assert accounts.sign_in("reader@example.com", "a long password").account.registered


def test_an_unreadable_account_database_is_an_account_error_and_leaks_nothing(tmp_path):
    accounts = _service(tmp_path)
    accounts.path.parent.mkdir(parents=True, exist_ok=True)
    accounts.path.write_bytes(b"this is not a database" * 100)
    with pytest.raises(AccountError) as refused:
        accounts.register("reader@example.com", "a long password")
    assert refused.value.reason == "unavailable"
    assert accounts.account_for_session("anything") is None
