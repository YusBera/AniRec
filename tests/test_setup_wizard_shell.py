from __future__ import annotations

from datetime import datetime, timezone

from AniRec.gui.main_window import MainWindow, PageId
from AniRec.gui.setup_wizard import SetupWizard, WizardStep
from AniRec.gui_main import create_application
from AniRec.models import AppSettings, TokenRecord
from AniRec.services import (
    OnboardingService,
    ProfileService,
    ResultService,
    SettingsService,
    TokenStore,
)


def services(system_temp_dir, *, valid=False, complete=False):
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
    if valid:
        settings.save(AppSettings(client_id="fake-client"))
        profile = profiles.create_profile("fixture-user")
        profiles.directory(profile.profile_id, create=True)
        profiles.mark_synced(profile)
        profiles.set_active(profile.profile_id)
        tokens.save(profile.profile_id, TokenRecord("fake-token", expires_at=1))
    if complete:
        onboarding.mark_complete()
    return profiles, onboarding


def test_wizard_prevents_skipping_required_steps_and_preserves_page_instances(system_temp_dir):
    create_application([])
    _profiles, onboarding = services(system_temp_dir)
    wizard = SetupWizard(onboarding)
    api_page = wizard.pages[WizardStep.API]

    assert wizard.current_step is WizardStep.WELCOME
    assert wizard.next_button.isEnabled()
    wizard.go_next()
    assert wizard.current_step is WizardStep.API
    assert not wizard.next_button.isEnabled()

    api_page.setProperty("safeDraft", "preserved-client-id")
    wizard.go_next()
    assert wizard.current_step is WizardStep.API
    wizard.go_to(WizardStep.OAUTH)
    assert wizard.current_step is WizardStep.API

    wizard.set_step_complete(WizardStep.API)
    wizard.go_next()
    wizard.go_back()
    assert wizard.current_step is WizardStep.API
    assert wizard.pages[WizardStep.API] is api_page
    assert api_page.property("safeDraft") == "preserved-client-id"


def test_cancel_does_not_mark_partial_setup_complete(system_temp_dir):
    create_application([])
    _profiles, onboarding = services(system_temp_dir)
    wizard = SetupWizard(onboarding)

    wizard.reject()

    assert not onboarding.completion_flag()


def test_finish_requires_every_step_and_then_marks_completion(system_temp_dir):
    create_application([])
    _profiles, onboarding = services(system_temp_dir)
    wizard = SetupWizard(onboarding)
    accepted = []
    wizard.accepted.connect(lambda: accepted.append(True))

    for step in WizardStep:
        wizard.set_step_complete(step)
    wizard.go_to(WizardStep.API)
    wizard.go_to(WizardStep.OAUTH)
    wizard.go_to(WizardStep.PROFILE)
    wizard.go_to(WizardStep.ANALYSIS)
    wizard.finish_button.click()

    assert accepted == [True]
    assert onboarding.completion_flag()


def test_clean_app_data_auto_opens_modal_wizard_without_marking_completion(system_temp_dir):
    application = create_application([])
    profiles, onboarding = services(system_temp_dir)
    window = MainWindow(
        profile_service=profiles,
        result_service=ResultService(root_override=system_temp_dir),
        onboarding_service=onboarding,
    )
    window.show()
    application.processEvents()

    assert window.setup_wizard is not None
    assert window.setup_wizard.isVisible()
    assert window.setup_wizard.isModal()
    window.setup_wizard.reject()
    assert not onboarding.completion_flag()
    window.close()


def test_completed_setup_does_not_auto_open_but_settings_can_reopen_wizard(system_temp_dir):
    application = create_application([])
    profiles, onboarding = services(system_temp_dir, valid=True, complete=True)
    window = MainWindow(
        profile_service=profiles,
        result_service=ResultService(root_override=system_temp_dir),
        onboarding_service=onboarding,
    )
    window.show()
    application.processEvents()

    assert window.setup_wizard is None
    window.navigate_to(PageId.SETTINGS)
    window.settings_page.open_setup_button.click()
    application.processEvents()

    assert window.setup_wizard is not None
    assert window.setup_wizard.isVisible()
    window.setup_wizard.reject()
    assert onboarding.completion_flag()
    window.close()
