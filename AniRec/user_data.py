import pandas as pd
import requests

API_BASE_URL = "https://api.myanimelist.net/v2"
REQUEST_TIMEOUT_SECONDS = 15


def get_user_completed_animes(username, access_token):
    """Fetch a user's completed anime list from MyAnimeList."""
    url = f"{API_BASE_URL}/users/{username}/animelist"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "status": "completed",
        "fields": "list_status,title,genres,score",
        "limit": 1000,
    }
    anime_rows = []

    while url:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()

        for anime in data.get("data", []):
            node = anime["node"]
            list_status = anime.get("list_status", {})
            anime_rows.append(
                {
                    "Title": node["title"],
                    "Genres": [genre["name"] for genre in node.get("genres", [])],
                    "Status": "Completed",
                    "User Score": list_status.get("score", 0),
                }
            )

        url = data.get("paging", {}).get("next")
        params = None

    return pd.DataFrame(anime_rows)
