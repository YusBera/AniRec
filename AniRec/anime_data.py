import pandas as pd
import requests

API_BASE_URL = "https://api.myanimelist.net/v2"
REQUEST_TIMEOUT_SECONDS = 15


def get_top_anime(limit=100, access_token=None):
    """Fetch top anime from MyAnimeList and return title, genres, and mean score."""
    headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
    anime_rows = []

    for offset in range(0, limit, 500):
        page_limit = min(500, limit - offset)
        params = {
            "ranking_type": "all",
            "limit": page_limit,
            "offset": offset,
            "fields": "title,genres,mean",
        }

        response = requests.get(
            f"{API_BASE_URL}/anime/ranking",
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()

        for anime in data.get("data", []):
            node = anime["node"]
            anime_rows.append(
                {
                    "Title": node["title"],
                    "Genres": [genre["name"] for genre in node.get("genres", [])],
                    "Mean Score": node.get("mean"),
                }
            )

    return pd.DataFrame(anime_rows)
