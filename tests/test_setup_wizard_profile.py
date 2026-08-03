from __future__ import annotations

import pytest

from AniRec.errors import AccessDeniedError, NotFoundError, ProfileError
from AniRec.services import ProfileService
from AniRec.services.profile_service import username_from_profile_reference


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        ("AniRecFixtureUser", "AniRecFixtureUser"),
        ("  AniRecFixtureUser  ", "AniRecFixtureUser"),
        ("https://myanimelist.net/profile/AniRecFixtureUser", "AniRecFixtureUser"),
        ("https://www.myanimelist.net/profile/AniRecFixtureUser/", "AniRecFixtureUser"),
    ],
)
def test_profile_reference_accepts_username_or_exact_mal_url(reference, expected):
    assert username_from_profile_reference(reference) == expected


@pytest.mark.parametrize(
    "reference",
    [
        "",
        "https://example.com/profile/AniRecFixtureUser",
        "http://myanimelist.net/profile/AniRecFixtureUser",
        "https://myanimelist.net/anime/1",
        "Neo/Balls",
        "Neo Balls",
    ],
)
def test_profile_reference_rejects_non_mal_or_unsafe_values(reference):
    with pytest.raises(ProfileError):
        username_from_profile_reference(reference)


class PublicListClient:
    def __init__(self, *, error=None):
        self.error = error
        self.calls = []

    def get_json(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error:
            raise self.error
        return {"data": []}


def test_public_profile_validation_uses_client_id_and_persists_without_token(
    system_temp_dir,
):
    client = PublicListClient()
    service = ProfileService(root_override=system_temp_dir, mal_client=client)

    profile = service.add_public_profile(
        "https://myanimelist.net/profile/AniRecFixtureUser",
        "fixture-client-id",
    )

    assert profile.username == "AniRecFixtureUser"
    assert profile.profile_id.startswith("user-anirecfixtureuser-")
    assert service.active_profile() == profile
    assert client.calls[0][0].endswith("/users/AniRecFixtureUser/animelist")
    assert client.calls[0][1]["client_id"] == "fixture-client-id"
    assert "access_token" not in client.calls[0][1]


@pytest.mark.parametrize(
    ("error", "error_type"),
    [
        (NotFoundError("missing fixture"), NotFoundError),
        (AccessDeniedError("private fixture"), AccessDeniedError),
    ],
)
def test_public_profile_preserves_not_found_and_private_list_errors(
    system_temp_dir,
    error,
    error_type,
):
    service = ProfileService(
        root_override=system_temp_dir,
        mal_client=PublicListClient(error=error),
    )
    with pytest.raises(error_type):
        service.add_public_profile("AniRecFixtureUser", "fixture-client-id")


def test_empty_completed_list_is_still_a_valid_public_profile(system_temp_dir):
    service = ProfileService(
        root_override=system_temp_dir,
        mal_client=PublicListClient(),
    )
    profile = service.validate_public_profile("AniRecFixtureUser", "fixture-client-id")
    assert profile.username == "AniRecFixtureUser"
