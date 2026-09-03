import pandas as pd
import requests
from urllib.parse import quote

try:
    from .core.mal_mapping import (
        ANIME_FIELDS,
        COMPLETED_ANIME_CSV_COLUMNS,
        anime_from_node,
        anime_to_row,
    )
    from .infrastructure.mal_client import MALClient
except ImportError:  # Backward compatibility for direct script-style imports.
    from core.mal_mapping import (
        ANIME_FIELDS,
        COMPLETED_ANIME_CSV_COLUMNS,
        anime_from_node,
        anime_to_row,
    )
    from infrastructure.mal_client import MALClient

API_BASE_URL = "https://api.myanimelist.net/v2"
REQUEST_TIMEOUT_SECONDS = 15


def get_user_completed_animes(
    username,
    access_token=None,
    *,
    client_id=None,
    include_nsfw=False,
    http_get=None,
    client=None,
    cancellation=None,
):
    """Fetch a user's completed anime list from MyAnimeList."""
    url = f"{API_BASE_URL}/users/{quote(str(username), safe='')}/animelist"
    params = {
        "fields": f"list_status,{ANIME_FIELDS}",
        "limit": 1000,
    }
    if include_nsfw:
        # MAL omits NSFW entries unless explicitly requested. Fetching the full
        # list also preserves completed entries currently marked as rewatching.
        params["nsfw"] = "true"
    else:
        params["status"] = "completed"
    anime_rows = []
    api_client = client or MALClient(http_get=http_get or requests.get)

    for data in api_client.iter_pages(
        url,
        params=params,
        access_token=access_token,
        client_id=client_id,
        cancellation=cancellation,
    ):

        for anime in data.get("data", []):
            if not isinstance(anime, dict) or not isinstance(anime.get("node"), dict):
                continue
            model = anime_from_node(anime["node"])
            if model is None:
                continue
            list_status = anime.get("list_status", {})
            if not isinstance(list_status, dict):
                list_status = {}
            if include_nsfw and list_status.get("status") != "completed":
                continue
            row = anime_to_row(model)
            row.update(
                {
                    "Status": str(list_status.get("status") or "completed").title(),
                    "User Score": list_status.get("score", 0),
                }
            )
            anime_rows.append(row)
    return pd.DataFrame(anime_rows, columns=COMPLETED_ANIME_CSV_COLUMNS)


# Sorting by list_updated_at is what makes a routine sync cheap: MyAnimeList
# returns the most recently touched entries first, so a watermark from the last
# run lets the walk stop at the first entry it has already seen instead of
# paging the whole list. A list of 800 titles that gained one completion costs
# one request rather than one per thousand.
LIST_SYNC_FIELDS = "list_status"
LIST_SYNC_SORT = "list_updated_at"
LIST_SYNC_PAGE_SIZE = 100


def fetch_recent_list_entries(
    username,
    access_token=None,
    *,
    client_id=None,
    since=None,
    include_nsfw=False,
    max_entries=1000,
    http_get=None,
    client=None,
    cancellation=None,
):
    """Yield list entries touched since ``since``, newest first.

    ``since`` is an ISO 8601 timestamp as MyAnimeList writes it. Comparison is
    lexicographic, which is only sound because MAL emits these in a fixed
    UTC-offset format; the value is stored and returned verbatim rather than
    parsed and re-rendered, so nothing here can drift it into another shape.

    An entry equal to the watermark stops the walk. Equality means it was the
    newest thing the previous run saw, so it and everything behind it are
    already accounted for.
    """
    url = f"{API_BASE_URL}/users/{quote(str(username), safe='')}/animelist"
    params = {
        "fields": LIST_SYNC_FIELDS,
        "limit": LIST_SYNC_PAGE_SIZE,
        "sort": LIST_SYNC_SORT,
    }
    if include_nsfw:
        params["nsfw"] = "true"
    api_client = client or MALClient(http_get=http_get or requests.get)

    seen = 0
    for page in api_client.iter_pages(
        url,
        params=params,
        access_token=access_token,
        client_id=client_id,
        cancellation=cancellation,
    ):
        for item in page.get("data", []):
            if not isinstance(item, dict):
                continue
            node = item.get("node")
            list_status = item.get("list_status")
            if not isinstance(node, dict) or not isinstance(list_status, dict):
                continue
            mal_id = node.get("id")
            updated_at = list_status.get("updated_at")
            if not isinstance(mal_id, int) or not isinstance(updated_at, str):
                continue
            if since is not None and updated_at <= since:
                return
            yield {
                "mal_id": mal_id,
                "title": str(node.get("title") or ""),
                "status": str(list_status.get("status") or ""),
                "score": list_status.get("score") or 0,
                "episodes_watched": list_status.get("num_episodes_watched") or 0,
                "updated_at": updated_at,
            }
            seen += 1
            if seen >= max_entries:
                return
