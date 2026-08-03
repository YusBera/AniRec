import pandas as pd
import requests

try:
    from .core.mal_mapping import ANIME_CSV_COLUMNS, ANIME_FIELDS, anime_from_node, anime_to_row
    from .infrastructure.mal_client import MALClient
except ImportError:  # Backward compatibility for direct script-style imports.
    from core.mal_mapping import ANIME_CSV_COLUMNS, ANIME_FIELDS, anime_from_node, anime_to_row
    from infrastructure.mal_client import MALClient

API_BASE_URL = "https://api.myanimelist.net/v2"
REQUEST_TIMEOUT_SECONDS = 15


def get_top_anime(
    limit=100,
    access_token=None,
    *,
    client_id=None,
    http_get=None,
    client=None,
    cancellation=None,
):
    """Fetch top anime from MyAnimeList and return title, genres, and mean score."""
    api_client = client or MALClient(http_get=http_get or requests.get)
    anime_rows = []

    for offset in range(0, limit, 500):
        page_limit = min(500, limit - offset)
        params = {
            "ranking_type": "all",
            "limit": page_limit,
            "offset": offset,
            "fields": ANIME_FIELDS,
        }

        data = api_client.get_json(
            f"{API_BASE_URL}/anime/ranking",
            params=params,
            access_token=access_token,
            client_id=client_id,
            cancellation=cancellation,
        )

        for anime in data.get("data", []):
            if not isinstance(anime, dict) or not isinstance(anime.get("node"), dict):
                continue
            model = anime_from_node(anime["node"])
            if model is None:
                continue
            anime_rows.append(anime_to_row(model))

    return pd.DataFrame(anime_rows, columns=ANIME_CSV_COLUMNS)
