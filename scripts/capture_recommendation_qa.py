"""Capture deterministic recommendation-page screenshots for native Qt visual QA."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from AniRec.gui.recommendation_page import RecommendationExplorerPage
from AniRec.gui.theme import ThemeManager, ThemePreference
from AniRec.gui_main import create_application
from AniRec.models import Anime, Recommendation
from AniRec.services import RecommendationStateService


def sample_recommendations() -> tuple[Recommendation, ...]:
    titles = (
        "Skyward Echo",
        "Neon Ronin",
        "Quiet Orbit",
        "Paper Moons",
        "Glass Horizon",
        "The Last Stargazer",
        "Violet Circuit",
        "Cloud Atlas Academy",
        "Moonlit Archive",
        "Afterimage City",
    )
    genres = (
        ("Fantasy", "Adventure"),
        ("Action", "Sci-Fi"),
        ("Drama", "Sci-Fi"),
        ("Mystery", "Drama"),
        ("Comedy", "School"),
    )
    return tuple(
        Recommendation(
            Anime(
                title,
                mal_id=index,
                genres=genres[(index - 1) % len(genres)],
                mean_score=9.0 - (index * 0.07),
                status="finished_airing",
                episodes=11 + index,
                year=2026 - (index % 4),
            ),
            match_score=96.6 - (index * 2.4),
            rank=index,
        )
        for index, title in enumerate(titles, start=1)
    )


def capture(page: RecommendationExplorerPage, path: Path, application) -> None:
    application.processEvents()
    image = page.grab()
    if not image.save(str(path)):
        raise RuntimeError(f"Could not save visual QA capture: {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/images"),
        help="Destination directory for PNG screenshots.",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    application = create_application([])
    ThemeManager(application).apply(ThemePreference.DARK)
    models = sample_recommendations()
    with tempfile.TemporaryDirectory(prefix="anirec-visual-qa-") as temporary_root:
        service = RecommendationStateService(root_override=temporary_root)
        service.set_feedback(
            "visual-qa", 1, "liked", genres=models[0].anime.genres, title=models[0].anime.title
        )
        service.set_feedback(
            "visual-qa", 2, "disliked", genres=models[1].anime.genres, title=models[1].anime.title
        )
        service.set_watch_later("visual-qa", 3, True)

        page = RecommendationExplorerPage(state_service=service)
        page.set_profile("visual-qa")
        page.set_recommendations(models)
        page.set_more_available(True)
        page.resize(1440, 900)
        page.show()
        capture(page, args.output_dir / "anirec-s15-modern-for-you.png", application)

        page.library_tabs["liked"].click()
        capture(page, args.output_dir / "anirec-s15-editable-liked.png", application)

        for recommendation in models[2:]:
            service.set_feedback(
                "visual-qa",
                recommendation.anime.mal_id,
                "liked",
                genres=recommendation.anime.genres,
                title=recommendation.anime.title,
            )
        page.set_profile("visual-qa")
        page.library_tabs["all"].click()
        capture(page, args.output_dir / "anirec-s15-modern-empty.png", application)
        page.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
