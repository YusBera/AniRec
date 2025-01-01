import requests
import pandas as pd
from oauth_handler import get_access_token  # Ensure you have access to the token function

API_BASE_URL = "https://api.myanimelist.net/v2"

def get_top_anime(limit=100, access_token=None):
    """
    Fetch a list of top anime and return as a pandas DataFrame with relevant fields like title, genres, rank, and average_score.
    """
    url = f"{API_BASE_URL}/anime/ranking"
    params = {
        "limit": limit,
        "fields": "title,genres,ranking,average_score",  # Ensure all relevant fields are requested
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
            rank = anime["ranking"]["rank"]
            average_score = anime["node"].get("average_score", None)  # Default to None if not available
            genres = [genre["name"] for genre in anime["node"]["genres"]]

            anime_data.append({
                "Title": title,
                "Genres": genres,
                "Rank": rank,
                "Average Score": average_score
            })

        # Create a DataFrame
        df = pd.DataFrame(anime_data)
        return df
    else:
        raise Exception(f"Error: {response.status_code} - {response.text}")
