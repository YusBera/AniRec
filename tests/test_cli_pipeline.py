from __future__ import annotations

import builtins

from errors import AuthError
from main import run_full_pipeline
from models import Anime, PipelineResult, Recommendation


class RecordingLogger:
    def __init__(self):
        self.calls = []

    def exception(self, message, *args):
        self.calls.append((message, args))


class SuccessfulOrchestrator:
    def __init__(self, output_path):
        self.output_path = output_path
        self.calls = []

    def run_full(self, username, settings, progress_callback):
        self.calls.append((username, settings))
        return PipelineResult(
            recommendations=(Recommendation(Anime("Fixture Recommendation"), 100.0),),
            generated_files=(str(self.output_path),),
        )


def test_cli_full_pipeline_uses_service_defaults(monkeypatch, system_temp_dir, capsys):
    answers = iter(["fixture-user", "", "", "", ""])
    monkeypatch.setattr(builtins, "input", lambda _prompt: next(answers))
    orchestrator = SuccessfulOrchestrator(system_temp_dir / "fixture.csv")
    logger = RecordingLogger()

    result = run_full_pipeline(orchestrator=orchestrator, logger=logger)

    username, settings = orchestrator.calls[0]
    assert username == "fixture-user"
    assert settings.top_anime_limit == 500
    assert settings.recommendation_count == 10
    assert settings.candidate_pool_size == 150
    assert settings.randomness_factor == 5
    assert result.recommendations[0].anime.title == "Fixture Recommendation"
    assert "Fixture Recommendation" in capsys.readouterr().out
    assert logger.calls == []


def test_cli_logs_technical_error_but_only_prints_safe_model(monkeypatch, capsys):
    answers = iter(["fixture-user", "", "", "", ""])
    monkeypatch.setattr(builtins, "input", lambda _prompt: next(answers))
    logger = RecordingLogger()

    class FailingOrchestrator:
        def run_full(self, username, settings, progress_callback):
            raise AuthError("access_token=fixture-secret-must-not-print")

    assert run_full_pipeline(orchestrator=FailingOrchestrator(), logger=logger) is None
    output = capsys.readouterr().out
    assert "fixture-secret-must-not-print" not in output
    assert "Account connection problem" in output
    assert logger.calls[0][0] == "Full recommendation pipeline failed"
