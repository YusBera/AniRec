from __future__ import annotations

import time

from AniRec.application.pipeline import FULL_PIPELINE_STEP_IDS
from AniRec.errors import DataError
from AniRec.gui.main_window import MainWindow, PageId
from AniRec.gui.setup_wizard import SetupWizard, WizardStep
from AniRec.gui.texts import PROGRESS_STEP_TEXT, WIZARD_TEXT
from AniRec.gui_main import create_application
from AniRec.models import (
    Anime,
    AppSettings,
    GenreStat,
    PipelineProgress,
    PipelineResult,
    Recommendation,
    TokenRecord,
)
from AniRec.services import (
    OnboardingService,
    ProfileService,
    ResultService,
    SettingsService,
    TokenStore,
)


def setup_state(system_temp_dir):
    settings = SettingsService(root_override=system_temp_dir)
    settings.save(AppSettings(client_id="fixture-client"))
    tokens = TokenStore(root_override=system_temp_dir)
    profiles = ProfileService(root_override=system_temp_dir, token_store=tokens)
    profile = profiles.create_profile("fixture-user", mal_user_id=123)
    profiles.directory(profile.profile_id, create=True)
    profiles.mark_synced(profile)
    profiles.set_active(profile.profile_id)
    tokens.save(profile.profile_id, TokenRecord("fixture-access", expires_at=100))
    onboarding = OnboardingService(
        settings=settings,
        profiles=profiles,
        tokens=tokens,
        root_override=system_temp_dir,
    )
    return onboarding, ResultService(root_override=system_temp_dir), profile


def wait_until(application, predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        application.processEvents()
        time.sleep(0.002)
    application.processEvents()
    assert predicate()


def result_fixture():
    return PipelineResult(
        recommendations=(Recommendation(Anime("Fixture Anime"), rank=1),),
        genre_stats=(GenreStat("Action", importance_score=10),),
        user_stats={"completed_count": 12, "rated_count": 10},
        completed_at="2026-08-03T12:00:00+00:00",
    )


class SuccessfulPipeline:
    def __init__(self):
        self.calls = []

    def run_full(self, username, settings, *, progress_callback, cancellation_token):
        self.calls.append((username, settings, cancellation_token))
        for current, step_id in enumerate(FULL_PIPELINE_STEP_IDS, start=1):
            progress_callback(
                PipelineProgress(
                    step_id,
                    PROGRESS_STEP_TEXT[step_id],
                    current,
                    len(FULL_PIPELINE_STEP_IDS),
                    True,
                )
            )
        return result_fixture()


def move_to_analysis(wizard):
    for step in (WizardStep.API, WizardStep.OAUTH, WizardStep.PROFILE):
        wizard.set_step_complete(step)
    wizard.go_to(WizardStep.API)
    wizard.go_to(WizardStep.OAUTH)
    wizard.go_to(WizardStep.PROFILE)
    wizard.go_to(WizardStep.ANALYSIS)


def test_analysis_page_uses_documented_defaults_and_six_steps(system_temp_dir):
    create_application([])
    onboarding, results, _profile = setup_state(system_temp_dir)
    wizard = SetupWizard(
        onboarding,
        pipeline_orchestrator=SuccessfulPipeline(),
        result_service=results,
    )
    page = wizard.analysis_page

    assert page.top_limit_input.value() == 500
    assert page.recommendation_count_input.value() == 10
    assert page.candidate_pool_input.value() == 150
    assert page.randomness_input.value() == 5
    assert page.step_list.count() == 6
    assert [page.step_list.item(index).text() for index in range(6)] == [
        PROGRESS_STEP_TEXT[step_id] for step_id in FULL_PIPELINE_STEP_IDS
    ]


def test_mock_end_to_end_analysis_persists_result_marks_complete_and_opens_home(
    system_temp_dir,
):
    application = create_application([])
    onboarding, results, profile = setup_state(system_temp_dir)
    pipeline = SuccessfulPipeline()
    window = MainWindow(
        profile_service=onboarding.profiles,
        result_service=results,
        onboarding_service=onboarding,
        pipeline_orchestrator=pipeline,
    )
    window.show()
    application.processEvents()
    wizard = window.setup_wizard
    assert wizard is not None
    move_to_analysis(wizard)

    wizard.analysis_page.start_button.click()
    wait_until(application, lambda: wizard.analysis_page.is_complete)

    assert wizard.analysis_page.progress_bar.value() == 6
    assert wizard.analysis_page.step_list.currentRow() == 5
    assert results.load(profile.profile_id) == result_fixture()
    assert not onboarding.completion_flag()
    wizard.finish_button.click()
    application.processEvents()

    assert onboarding.completion_flag()
    assert window.current_page_id is PageId.HOME
    assert window.home_page.metric_values["completed"].text() == "12"
    assert window.home_page.metric_values["recommendations"].text() == "1"
    window.close()


class RetryPipeline(SuccessfulPipeline):
    def __init__(self):
        super().__init__()
        self.fail = True

    def run_full(self, username, settings, *, progress_callback, cancellation_token):
        progress_callback(
            PipelineProgress("fetch_top", "Fetch top anime", 1, 6, True)
        )
        if self.fail:
            raise DataError("fixture pipeline failure")
        return super().run_full(
            username,
            settings,
            progress_callback=progress_callback,
            cancellation_token=cancellation_token,
        )


def test_analysis_failure_names_step_and_allows_retry(system_temp_dir):
    application = create_application([])
    onboarding, results, _profile = setup_state(system_temp_dir)
    pipeline = RetryPipeline()
    wizard = SetupWizard(
        onboarding,
        pipeline_orchestrator=pipeline,
        result_service=results,
    )
    page = wizard.analysis_page

    page.start_button.click()
    wait_until(application, lambda: page.start_button.isEnabled())
    assert not page.is_complete
    assert "Failed during Fetch top anime" in page.status_label.text()
    assert page.start_button.text() == WIZARD_TEXT.analysis_retry

    pipeline.fail = False
    page.start_button.click()
    wait_until(application, lambda: page.is_complete)
    assert page.status_label.text() == WIZARD_TEXT.analysis_success


class CancellablePipeline:
    def run_full(self, _username, _settings, *, progress_callback, cancellation_token):
        progress_callback(
            PipelineProgress("fetch_top", "Fetch top anime", 1, 6, True)
        )
        for _ in range(100):
            time.sleep(0.003)
            cancellation_token.raise_if_cancelled()
        return result_fixture()


def test_analysis_cancel_saves_no_result_or_completion_flag(system_temp_dir):
    application = create_application([])
    onboarding, results, profile = setup_state(system_temp_dir)
    wizard = SetupWizard(
        onboarding,
        pipeline_orchestrator=CancellablePipeline(),
        result_service=results,
    )
    page = wizard.analysis_page

    page.start_button.click()
    wait_until(application, lambda: not page.cancel_analysis_button.isHidden())
    page.cancel_analysis_button.click()
    wait_until(application, lambda: page.start_button.isEnabled())

    assert page.status_label.text() == WIZARD_TEXT.analysis_cancelled
    assert results.load(profile.profile_id) is None
    assert not onboarding.completion_flag()
    assert not page.is_complete
