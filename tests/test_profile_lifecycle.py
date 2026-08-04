from __future__ import annotations

import re

import pytest

from errors import AccessDeniedError, NotFoundError, ProfileError
from models import TokenRecord
from services import ProfileService, TokenStore


class FakeMALClient:
    def __init__(self):
        self.calls = []

    def get_json(self, url, params, access_token):
        self.calls.append((url, params, access_token))
        return {"id": 123, "name": "Kullanıcı Çığ"}


def test_profile_validation_normalizes_api_identity_and_persists_metadata(system_temp_dir):
    client = FakeMALClient()
    service = ProfileService(
        root_override=system_temp_dir / "app-data",
        mal_client=client,
    )
    profile = service.add_profile("Kullanıcı/Çığ", "fake-access-token")
    assert profile.profile_id == "mal-123"
    assert profile.username == "Kullanıcı Çığ"
    assert profile.mal_user_id == 123
    assert service.get_profile("mal-123") == profile
    assert service.active_profile() == profile
    assert client.calls[0][0].endswith("/users/@me")
    assert "%C3%87" in client.calls[1][0]
    assert "/" not in client.calls[0][0].split("/users/", 1)[1]
    assert client.calls[1][0].endswith("/animelist")


def test_private_anime_list_is_checked_separately_after_identity(system_temp_dir):
    class PrivateListClient:
        def get_json(self, url, **_kwargs):
            if url.endswith("/animelist"):
                raise AccessDeniedError("private fixture list")
            return {"id": 123, "name": "Fixture User"}

    service = ProfileService(
        root_override=system_temp_dir,
        mal_client=PrivateListClient(),
    )
    with pytest.raises(AccessDeniedError):
        service.add_profile("Fixture User", "fake-token")


@pytest.mark.parametrize("username", ["Çığ", ".", "..", "CON", "a/b", "a\\b"])
def test_unverified_local_ids_are_safe_for_unicode_reserved_and_separators(
    system_temp_dir,
    username,
):
    profile = ProfileService(root_override=system_temp_dir).create_profile(username)
    assert re.fullmatch(r"user-[a-z0-9-]+-[a-f0-9]{12}", profile.profile_id)
    assert profile.profile_id.split("-", 1)[0].casefold() not in {"con", "prn", "aux", "nul"}


def test_multiple_profiles_switch_open_and_delete_only_confirmed_target(system_temp_dir):
    root = system_temp_dir / "app-data"
    opened = []
    tokens = TokenStore(root_override=root)
    service = ProfileService(
        root_override=root,
        mal_client=FakeMALClient(),
        token_store=tokens,
        open_path=lambda path: opened.append(path) or True,
    )
    first = service.add_profile("first", "fake-token")

    class SecondClient:
        def get_json(self, *args, **kwargs):
            return {"id": 456, "name": "Second User"}

    service._mal_client = SecondClient()
    second = service.add_profile("second", "fake-token")
    tokens.save(first.profile_id, TokenRecord("first-token"))
    tokens.save(second.profile_id, TokenRecord("second-token"))

    assert {item.profile_id for item in service.list_profiles()} == {"mal-123", "mal-456"}
    service.set_active(second.profile_id)
    assert service.active_profile() == second
    assert service.open_directory(first.profile_id) == opened[0]

    target = service.deletion_target(first.profile_id)
    with pytest.raises(ProfileError):
        service.delete_profile(first.profile_id, confirmed_target=target.parent)
    assert target.exists()
    service.delete_profile(first.profile_id, confirmed_target=target)
    assert not target.exists()
    assert tokens.load(first.profile_id) is None
    assert tokens.load(second.profile_id).access_token == "second-token"
    assert service.active_profile() == second


@pytest.mark.parametrize("error_type", [NotFoundError, AccessDeniedError])
def test_user_not_found_and_inaccessible_profile_errors_remain_distinct(
    system_temp_dir,
    error_type,
):
    class FailingClient:
        def get_json(self, *args, **kwargs):
            raise error_type("fixture")

    service = ProfileService(root_override=system_temp_dir, mal_client=FailingClient())
    with pytest.raises(error_type):
        service.validate_username("fixture", "fake-token")
