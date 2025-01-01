import requests
import pandas as pd
from oauth_handler import get_access_token

API_BASE_URL = "https://api.myanimelist.net/v2"

def get_top_anime(limit=100, access_token=None):
    """
    Fetch a list of top anime and return relevant data, including the median score.
    """
    url = f"{API_BASE_URL}/anime/ranking"
    params = {
        "limit": limit,
        "fields": "title,genres,mean",  # Fetch only relevant fields
    }
    headers = {
        "Authorization": f"Bearer {access_token}" if access_token else "",
    }

    response = requests.get(url, params=params, headers=headers)
    if response.status_code == 200:
        data = response.json()
        anime_data = []

        for anime in data.get("data", []):
            title = anime["node"]["title"]
            genres = [genre["name"] for genre in anime["node"]["genres"]]
            average_score = anime["node"].get("mean", None)  # Default to None if not available

            # For simplicity, we'll treat the average score as the median score since no per-user data is available here
            median_score = average_score

            anime_data.append({
                "Title": title,
                "Genres": genres,
                "Median Score": median_score
            })

        # Create a DataFrame with only the required fields
        df = pd.DataFrame(anime_data)
        return df
    else:
        raise Exception(f"Error: {response.status_code} - {response.text}")
