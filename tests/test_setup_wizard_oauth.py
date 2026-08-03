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


def test_default_setup_has_three_steps_and_no_required_oauth_page(system_temp_dir):
    create_application([])
    wizard = SetupWizard(onboarding_service(system_temp_dir))

    assert list(WizardStep) == [
        WizardStep.WELCOME,
        WizardStep.CONNECTION,
        WizardStep.ANALYSIS,
    ]
    assert wizard.stack.count() == 3
    assert not hasattr(wizard, "oauth_page")
    assert not hasattr(wizard, "profile_page")


class ExplodingAuthService:
    def authorize(self, *_args, **_kwargs):
        raise AssertionError("Public setup must not start OAuth")


def test_public_setup_never_calls_oauth_and_removes_stale_temporary_token(
    system_temp_dir,
):
    application = create_application([])
    onboarding = onboarding_service(system_temp_dir)
    onboarding.tokens.save(
        ONBOARDING_TOKEN_PROFILE_ID,
        TokenRecord("stale-fixture-token", expires_at=100),
    )
    wizard = SetupWizard(
        onboarding,
        api_connection=SuccessfulApiConnection(),
        auth_service=ExplodingAuthService(),
    )
    page = fill_connection_page(wizard)

    page.test_button.click()
    wait_until(application, lambda: wizard.current_step is WizardStep.ANALYSIS)

    assert onboarding.tokens.load(ONBOARDING_TOKEN_PROFILE_ID) is None
    assert onboarding.profiles.active_profile().username == "AniRecFixtureUser"


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
