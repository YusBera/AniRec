"""Capture deterministic, privacy-safe main-window screenshots for documentation."""

from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from AniRec.gui.main_window import MainWindow, PageId
from AniRec.gui.theme import ThemeManager, ThemePreference
from AniRec.gui_main import create_application
from AniRec.models import AppSettings, Anime, GenreStat, PipelineResult, Recommendation
from AniRec.services import (
    DataManagementService,
    ProfileService,
    RecommendationStateService,
    ResultService,
    SettingsService,
    TokenStore,
)


def sample_result() -> PipelineResult:
    instant = datetime(2026, 8, 3, 14, 30, tzinfo=timezone.utc)
    titles = (
        ("Skyward Echo", ("Fantasy", "Adventure"), 94.2),
        ("Neon Ronin", ("Action", "Sci-Fi"), 91.8),
        ("Quiet Orbit", ("Drama", "Sci-Fi"), 89.4),
        ("Paper Moons", ("Mystery", "Drama"), 87.9),
        ("Glass Horizon", ("Comedy", "School"), 85.1),
        ("The Last Stargazer", ("Fantasy", "Adventure"), 82.7),
    )
    recommendations = tuple(
        Recommendation(
            Anime(
                title,
                mal_id=index,
                genres=genres,
                mean_score=8.9 - (index * 0.08),
                status="finished_airing",
                episodes=11 + index,
                year=2026 - (index % 3),
            ),
            match_score=match,
            reason=f"Matches your interests in {', '.join(genres)}.",
            rank=index,
        )
        for index, (title, genres, match) in enumerate(titles, start=1)
    )
    genre_stats = tuple(
        GenreStat(name, importance_score=score)
        for name, score in (
            ("Fantasy", 48.0),
            ("Action", 42.0),
            ("Sci-Fi", 37.0),
            ("Adventure", 31.0),
            ("Drama", 27.0),
        )
    )
    return PipelineResult(
        recommendations=recommendations,
        genre_stats=genre_stats,
        user_stats={"completed_count": 42, "rated_count": 38},
        completed_at=instant.isoformat(),
    )


def capture(window: MainWindow, path: Path, application) -> None:
    application.processEvents()
    if not window.grab().save(str(path)):
        raise RuntimeError(f"Could not save visual QA capture: {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("docs/images"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    application = create_application([])
    ThemeManager(application).apply(ThemePreference.DARK)
    with tempfile.TemporaryDirectory(prefix="anirec-main-window-qa-") as temporary_root:
        profiles = ProfileService(root_override=temporary_root)
        profile = profiles.create_profile("SampleAnimeFan")
        profiles.directory(profile.profile_id, create=True)
        profile = profiles.mark_synced(profile)
        profiles.set_active(profile.profile_id)

        results = ResultService(root_override=temporary_root)
        results.save(profile.profile_id, sample_result())
        states = RecommendationStateService(root_override=temporary_root)
        settings = SettingsService(root_override=temporary_root)
        settings.save(
            AppSettings(
                client_id="fixture-client-id",
                active_profile_id=profile.profile_id,
                theme="dark",
            )
        )
        tokens = TokenStore(root_override=temporary_root)
        data = DataManagementService(root_override=temporary_root)
        window = MainWindow(
            profile_service=profiles,
            result_service=results,
            recommendation_state_service=states,
            settings_service=settings,
            token_store=tokens,
            data_management_service=data,
        )
        window.resize(1440, 900)
        window.show()

        window.navigate_to(PageId.HOME)
        capture(window, args.output_dir / "anirec-modern-home.png", application)
        window.navigate_to(PageId.RECOMMENDATIONS)
        capture(
            window,
            args.output_dir / "anirec-modern-recommendations.png",
            application,
        )
        window.navigate_to(PageId.SETTINGS)
        capture(window, args.output_dir / "anirec-modern-settings.png", application)
        window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
