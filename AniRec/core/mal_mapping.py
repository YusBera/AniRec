"""Safe mapping between MyAnimeList payloads, models, and CSV rows."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

try:
    from ..genre_utils import parse_genres
    from ..models import Anime
except ImportError:  # Compatibility with the S01 top-level import path.
    from genre_utils import parse_genres
    from models import Anime


ANIME_FIELDS = (
    "id,title,alternative_titles,main_picture,genres,mean,num_episodes,status,"
    "start_date,end_date,start_season,synopsis"
)
ANIME_CSV_COLUMNS = [
    "Anime ID",
    "Title",
    "English Title",
    "Alternative Titles",
    "Genres",
    "Mean Score",
    "Picture URL",
    "Large Picture URL",
    "Episodes",
    "Anime Status",
    "Start Date",
    "End Date",
    "Year",
    "Synopsis",
    "MAL URL",
]
COMPLETED_ANIME_CSV_COLUMNS = [*ANIME_CSV_COLUMNS, "Status", "User Score"]


def anime_from_node(node: object) -> Anime | None:
    if not isinstance(node, Mapping):
        return None
    mal_id = _positive_int(node.get("id"))
    title = _text(node.get("title"))
    if mal_id is None or title is None:
        return None

    alternative_data = node.get("alternative_titles")
    if not isinstance(alternative_data, Mapping):
        alternative_data = {}
    english_title = _text(alternative_data.get("en"))
    alternatives = _alternative_titles(alternative_data)

    picture = node.get("main_picture")
    if not isinstance(picture, Mapping):
        picture = {}
    genres = tuple(
        name
        for item in node.get("genres") or ()
        if isinstance(item, Mapping) and (name := _text(item.get("name")))
    )
    start_date = _text(node.get("start_date"))
    start_season = node.get("start_season")
    season_year = start_season.get("year") if isinstance(start_season, Mapping) else None
    year = _year_from_date(start_date) or _positive_int(season_year)

    return Anime(
        mal_id=mal_id,
        title=title,
        english_title=english_title,
        alternative_titles=alternatives,
        genres=genres,
        mean_score=node.get("mean"),
        cover_url=_text(picture.get("medium")),
        large_cover_url=_text(picture.get("large")),
        episodes=_positive_int(node.get("num_episodes")),
        status=_text(node.get("status")),
        start_date=start_date,
        end_date=_text(node.get("end_date")),
        year=year,
        synopsis=_text(node.get("synopsis")),
        mal_url=f"https://myanimelist.net/anime/{mal_id}",
    )


def anime_to_row(anime: Anime) -> dict[str, Any]:
    return {
        "Anime ID": anime.mal_id,
        "Title": anime.title,
        "English Title": anime.english_title,
        "Alternative Titles": list(anime.alternative_titles),
        "Genres": list(anime.genres),
        "Mean Score": anime.mean_score,
        "Picture URL": anime.cover_url,
        "Large Picture URL": anime.large_cover_url,
        "Episodes": anime.episodes,
        "Anime Status": anime.status,
        "Start Date": anime.start_date,
        "End Date": anime.end_date,
        "Year": anime.year,
        "Synopsis": anime.synopsis,
        "MAL URL": anime.mal_url,
    }


def anime_from_row(row: Mapping[str, Any]) -> Anime:
    mal_id = _positive_int(row.get("Anime ID"))
    title = _text(row.get("Title")) or "Unknown title"
    return Anime(
        mal_id=mal_id,
        title=title,
        english_title=_text(row.get("English Title")),
        alternative_titles=tuple(parse_genres(row.get("Alternative Titles"))),
        genres=tuple(parse_genres(row.get("Genres"))),
        mean_score=row.get("Mean Score"),
        cover_url=_text(row.get("Picture URL")),
        large_cover_url=_text(row.get("Large Picture URL")),
        episodes=_positive_int(row.get("Episodes")),
        status=_text(row.get("Anime Status")),
        start_date=_text(row.get("Start Date")),
        end_date=_text(row.get("End Date")),
        year=_positive_int(row.get("Year")),
        synopsis=_text(row.get("Synopsis")),
        mal_url=(
            f"https://myanimelist.net/anime/{mal_id}"
            if mal_id is not None
            else None
        ),
    )


def _alternative_titles(data: Mapping[str, Any]) -> tuple[str, ...]:
    values = []
    for key in ("en", "ja"):
        if text := _text(data.get(key)):
            values.append(text)
    for value in data.get("synonyms") or ():
        if text := _text(value):
            values.append(text)
    return tuple(dict.fromkeys(values))


def _text(value: object) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip()
    return text or None


def _positive_int(value: object) -> int | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _year_from_date(value: str | None) -> int | None:
    if value and len(value) >= 4 and value[:4].isdigit():
        return _positive_int(value[:4])
    return None
