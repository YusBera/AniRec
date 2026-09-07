"""Read source anime metadata and compare completed-list evidence, without affinity scoring."""
from dataclasses import replace
import math
from urllib.parse import urlparse

from ..core.mal_mapping import anime_from_row
from ..models import Recommendation
from ..errors import InvalidResponseError
from ..infrastructure.mal_client import MALClient
from ..presentation import recommendation_view_models
from ..presentation.compatibility import (
    CompatibilityReport, ComparisonEntry, ComparisonScores, ComparisonSection, FriendSummary,
)


class ComparisonClient(MALClient):
    """Refuse partial/malformed lists and untrusted pagination destinations."""

    def get_json(self, url, **kwargs):
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.netloc != "api.myanimelist.net" or not parsed.path.startswith("/v2/users/") or not parsed.path.endswith("/animelist"):
            raise InvalidResponseError("Invalid comparison pagination URL.")
        page = super().get_json(url, **kwargs)
        if not isinstance(page.get("data"), list):
            raise InvalidResponseError("MyAnimeList did not return an anime list.")
        for item in page["data"]:
            if not isinstance(item, dict) or not isinstance(item.get("node"), dict) or not isinstance(item.get("list_status"), dict):
                raise InvalidResponseError("MyAnimeList returned an incomplete list entry.")
            from ..core.mal_mapping import anime_from_node
            if anime_from_node(item["node"]) is None:
                raise InvalidResponseError("MyAnimeList returned an invalid anime.")
        return page


def metadata_model(anime):
    model = recommendation_view_models((Recommendation(anime=anime, match_score=0),))[0]
    return replace(model, personal_match_available=False, personal_match_text="N/A")


def compare_completed(username, yours, theirs):
    """Join on MAL ID. Zero is unrated; no aggregate compatibility is inferred."""
    def records(frame):
        result = {}
        for _, row in frame.iterrows():
            anime = anime_from_row(row)
            if anime.mal_id:
                raw = row.get("User Score")
                try:
                    score = float(raw)
                except (ValueError, TypeError):
                    score = None
                if score is not None and (not math.isfinite(score) or not 1 <= score <= 10):
                    score = None
                result[anime.mal_id] = (anime, score)
        return result

    left, right = records(yours), records(theirs)
    shared = left.keys() & right.keys()
    entries = []
    for mal_id in shared:
        anime, other = right[mal_id]
        own = left[mal_id][1]
        entries.append(ComparisonEntry(metadata_model(anime), ComparisonScores(
            your_score=own, friend_score=other,
            difference=None if own is None or other is None else abs(own - other),
            mal_score=anime.mean_score,
        )))
    rated = [entry for entry in entries if entry.scores.difference is not None]
    rated.sort(key=lambda entry: (-entry.scores.difference, entry.model.mal_id))
    unrated = sorted((entry for entry in entries if entry.scores.difference is None),
                     key=lambda entry: entry.model.display_title.casefold())
    return CompatibilityReport(
        friend=FriendSummary(username=username, total_anime=len(right), shared_anime=len(shared),
                             both_rated=len(rated), match_label="Completed-list evidence; compatibility is not calculated."),
        sections=(
            ComparisonSection("rated", "Shared ratings", "Largest absolute score differences first; ties use MAL ID.", tuple(rated), "No shared titles rated by both readers."),
            ComparisonSection("unrated", "Shared, awaiting a rating", "At least one reader has not rated these completed titles.", tuple(unrated), "No unrated shared titles."),
        ),
    )
