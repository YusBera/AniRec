from __future__ import annotations

from datetime import datetime, timezone

from AniRec.models import AppSettings, TokenRecord
from AniRec.services import (
    OnboardingService,
    ProfileService,
    SettingsService,
    TokenStore,
)


def build_services(system_temp_dir):
    settings = SettingsService(root_override=system_temp_dir)
    profiles = ProfileService(root_override=system_temp_dir)
    tokens = TokenStore(root_override=system_temp_dir)
    onboarding = OnboardingService(
        settings=settings,
        profiles=profiles,
        tokens=tokens,
        root_override=system_temp_dir,
        clock=lambda: datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc),
    )
    return settings, profiles, tokens, onboarding


def make_valid_setup(settings, profiles, tokens):
    settings.save(AppSettings(client_id="fake-client"))
    profile = profiles.create_profile("fixture-user")
    profiles.directory(profile.profile_id, create=True)
    profiles.mark_synced(profile)
    profiles.set_active(profile.profile_id)
    tokens.save(profile.profile_id, TokenRecord("fake-token", expires_at=1))
    return profile


def test_clean_root_needs_setup_and_completion_flag_is_atomic(system_temp_dir):
    settings, profiles, tokens, onboarding = build_services(system_temp_dir)

    assert onboarding.needs_setup()
    assert not onboarding.completion_flag()
    make_valid_setup(settings, profiles, tokens)
    assert onboarding.needs_setup()

    path = onboarding.mark_complete()

    assert path.is_file()
    assert onboarding.completion_flag()
    assert not onboarding.needs_setup()
    assert list(path.parent.glob("*.tmp")) == []


def test_completion_flag_requires_settings_and_profile_but_not_oauth_token(system_temp_dir):
    settings, profiles, tokens, onboarding = build_services(system_temp_dir)
    profile = make_valid_setup(settings, profiles, tokens)
    onboarding.mark_complete()
    assert not onboarding.needs_setup()

    tokens.delete(profile.profile_id)
    assert not onboarding.needs_setup()

    settings.path.unlink()
    assert onboarding.needs_setup()
