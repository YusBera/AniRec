from __future__ import annotations

import time

from AniRec.gui.setup_wizard import ONBOARDING_TOKEN_PROFILE_ID, SetupWizard, WizardStep
from AniRec.gui_main import create_application
from AniRec.models import TokenRecord
from AniRec.services import OnboardingService, ProfileService, SettingsService, TokenStore


class SuccessfulApiConnection:
    def test(self, _settings):
        return True


class PublicProfileClient:
    def get_json(self, _url, **_kwargs):
        return {"data": []}


def onboarding_service(system_temp_dir, client=None):
    settings = SettingsService(root_override=system_temp_dir)
    tokens = TokenStore(root_override=system_temp_dir)
    profiles = ProfileService(
        root_override=system_temp_dir,
        mal_client=client or PublicProfileClient(),
        token_store=tokens,
    )
    return OnboardingService(
        settings=settings,
        profiles=profiles,
        tokens=tokens,
        root_override=system_temp_dir,
    )


def wait_until(application, predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        application.processEvents()
        time.sleep(0.002)
    application.processEvents()
    assert predicate()


def fill_connection_page(wizard):
    wizard.go_next()
    page = wizard.connection_page
    page.client_id_input.setText("fixture-client")
    page.profile_reference_input.setText("AniRecFixtureUser")
    return page


def test_default_setup_has_required_oauth_page_between_connection_and_analysis(
    system_temp_dir,
):
    create_application([])
    wizard = SetupWizard(onboarding_service(system_temp_dir))

    assert list(WizardStep) == [
        WizardStep.WELCOME,
        WizardStep.CONNECTION,
        WizardStep.OAUTH,
        WizardStep.ANALYSIS,
    ]
    assert wizard.stack.count() == 4
    assert wizard.oauth_page.connect_button.isEnabled()
    assert not hasattr(wizard, "profile_page")


class SuccessfulAuthService:
    def __init__(self, tokens):
        self.tokens = tokens
        self.calls = []

    def authorize(self, profile_id, settings, **kwargs):
        self.calls.append((profile_id, settings))
        kwargs["status_callback"]("oauth_waiting_approval")
        token = TokenRecord("oauth-fixture-token", expires_at=9999999999)
        self.tokens.save(profile_id, token)
        kwargs["status_callback"]("oauth_success")
        return token


def test_setup_validates_public_profile_then_requires_oauth_for_real_profile(
    system_temp_dir,
):
    application = create_application([])
    onboarding = onboarding_service(system_temp_dir)
    onboarding.tokens.save(
        ONBOARDING_TOKEN_PROFILE_ID,
        TokenRecord("stale-fixture-token", expires_at=100),
    )
    auth = SuccessfulAuthService(onboarding.tokens)
    wizard = SetupWizard(
        onboarding,
        api_connection=SuccessfulApiConnection(),
        auth_service=auth,
    )
    page = fill_connection_page(wizard)

    page.test_button.click()
    wait_until(application, lambda: wizard.current_step is WizardStep.OAUTH)

    assert onboarding.tokens.load(ONBOARDING_TOKEN_PROFILE_ID) is None
    profile = onboarding.profiles.active_profile()
    assert profile.username == "AniRecFixtureUser"

    wizard.oauth_page.connect_button.click()
    wait_until(application, lambda: wizard.current_step is WizardStep.ANALYSIS)

    assert auth.calls[0][0] == profile.profile_id
    assert onboarding.tokens.load(profile.profile_id) is not None
    assert wizard.oauth_page.is_complete


class CancellableProfileClient:
    def get_json(self, _url, **kwargs):
        cancellation = kwargs["cancellation"]
        for _ in range(200):
            time.sleep(0.002)
            cancellation.raise_if_cancelled()
        return {"data": []}


def test_reject_cancels_public_profile_validation_worker(system_temp_dir):
    application = create_application([])
    wizard = SetupWizard(
        onboarding_service(system_temp_dir, CancellableProfileClient()),
        api_connection=SuccessfulApiConnection(),
    )
    wizard.show()
    page = fill_connection_page(wizard)
    page.test_button.click()
    wait_until(
        application,
        lambda: wizard.worker_controller.is_running(wizard.connection_operation_key),
    )

    wizard.reject()
    application.processEvents()

    assert not wizard.worker_controller.is_running(wizard.connection_operation_key)
    assert not wizard.isVisible()
