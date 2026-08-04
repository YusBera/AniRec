from __future__ import annotations

import time

from PySide6.QtCore import QTimer

from AniRec.errors import ConfigError
from AniRec.gui.setup_wizard import SetupWizard, WizardStep
from AniRec.gui_main import create_application
from AniRec.services import OnboardingService, ProfileService, SettingsService, TokenStore


class PublicProfileClient:
    def __init__(self, *, delay: float = 0.0):
        self.calls = []
        self.delay = delay

    def get_json(self, url, **kwargs):
        if self.delay:
            time.sleep(self.delay)
        self.calls.append((url, kwargs))
        return {"data": []}


def onboarding_service(system_temp_dir, client=None):
    settings = SettingsService(root_override=system_temp_dir)
    tokens = TokenStore(root_override=system_temp_dir)
    return OnboardingService(
        settings=settings,
        profiles=ProfileService(
            root_override=system_temp_dir,
            mal_client=client or PublicProfileClient(),
            token_store=tokens,
        ),
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


class SuccessfulApiConnection:
    def __init__(self, *, delay: float = 0.0):
        self.calls = []
        self.delay = delay

    def test(self, settings):
        if self.delay:
            time.sleep(self.delay)
        self.calls.append(settings)
        return True


def test_welcome_explains_local_explainable_and_unofficial_behavior(system_temp_dir):
    create_application([])
    wizard = SetupWizard(onboarding_service(system_temp_dir))
    text = wizard.pages[WizardStep.WELCOME].hint_label.text()

    assert "genre-based, explainable" in text
    assert "local AniRec application-data folder" in text
    assert "unofficial application" in text
    assert "not affiliated with or endorsed by MyAnimeList" in text


def test_client_id_and_profile_url_validate_together_without_oauth(system_temp_dir):
    application = create_application([])
    profile_client = PublicProfileClient()
    onboarding = onboarding_service(system_temp_dir, profile_client)
    connection = SuccessfulApiConnection()
    wizard = SetupWizard(onboarding, api_connection=connection)
    wizard.go_next()
    page = wizard.connection_page

    assert len(WizardStep) == 3
    assert not page.test_button.isEnabled()
    page.client_id_input.setText("fixture-client")
    page.profile_reference_input.setText(
        "https://myanimelist.net/profile/AniRecFixtureUser"
    )
    assert page.test_button.isEnabled()

    page.test_button.click()
    wait_until(application, lambda: wizard.current_step is WizardStep.ANALYSIS)

    assert page.is_complete
    assert onboarding.settings.load().client_id == "fixture-client"
    assert onboarding.profiles.active_profile().username == "AniRecFixtureUser"
    assert onboarding.tokens.load(onboarding.profiles.active_profile().profile_id) is None
    assert connection.calls
    assert profile_client.calls[0][0].endswith("/users/AniRecFixtureUser/animelist")
    assert profile_client.calls[0][1]["client_id"] == "fixture-client"


class RetryApiConnection:
    def __init__(self):
        self.should_fail = True
        self.calls = 0

    def test(self, _settings):
        self.calls += 1
        if self.should_fail:
            raise ConfigError("rejected fixture")
        return True


def test_combined_connection_failure_is_retryable_and_saves_only_after_success(
    system_temp_dir,
):
    application = create_application([])
    onboarding = onboarding_service(system_temp_dir)
    connection = RetryApiConnection()
    wizard = SetupWizard(onboarding, api_connection=connection)
    wizard.go_next()
    page = wizard.connection_page
    page.client_id_input.setText("fixture-client")
    page.profile_reference_input.setText("AniRecFixtureUser")

    page.test_button.click()
    wait_until(application, lambda: connection.calls == 1 and page.test_button.isEnabled())
    assert not page.is_complete
    assert not onboarding.settings.path.exists()
    assert "Settings problem" in page.status_label.text()

    connection.should_fail = False
    page.test_button.click()
    wait_until(application, lambda: wizard.current_step is WizardStep.ANALYSIS)
    assert onboarding.settings.path.is_file()


def test_combined_connection_worker_keeps_gui_event_loop_responsive(system_temp_dir):
    application = create_application([])
    wizard = SetupWizard(
        onboarding_service(system_temp_dir, PublicProfileClient(delay=0.05)),
        api_connection=SuccessfulApiConnection(delay=0.05),
    )
    wizard.go_next()
    page = wizard.connection_page
    timer_fired = []
    page.client_id_input.setText("fixture-client")
    page.profile_reference_input.setText("AniRecFixtureUser")
    QTimer.singleShot(10, lambda: timer_fired.append(True))

    page.test_button.click()
    wait_until(application, lambda: bool(timer_fired))

    assert not page.test_button.isEnabled()
    wait_until(application, lambda: wizard.current_step is WizardStep.ANALYSIS)
