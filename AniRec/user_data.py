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
    http_get=None,
    client=None,
    cancellation=None,
):
    """Fetch a user's completed anime list from MyAnimeList."""
    url = f"{API_BASE_URL}/users/{quote(str(username), safe='')}/animelist"
    params = {
        "status": "completed",
        "fields": f"list_status,{ANIME_FIELDS}",
        "limit": 1000,
    }
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
            row = anime_to_row(model)
            row.update(
                {
                    "Status": str(list_status.get("status") or "completed").title(),
                    "User Score": list_status.get("score", 0),
                }
            )
            anime_rows.append(row)
    return pd.DataFrame(anime_rows, columns=COMPLETED_ANIME_CSV_COLUMNS)
