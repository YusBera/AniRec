#user_data.py

import requests
import pandas as pd

API_BASE_URL = "https://api.myanimelist.net/v2"

def get_user_completed_animes(username, access_token):
    """
    Fetch the list of completed animes for a specific user and return it as a pandas DataFrame.
    """
    url = f"{API_BASE_URL}/users/{username}/animelist"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    params = {
        "status": "completed",
        "fields": "list_status,title,genres",
        "limit": 1000  # Adjust as needed
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()
        animes = []

        for anime in data.get("data", []):
            title = anime["node"]["title"]
            genres = anime["node"]["genres"]
            genres_list = [genre["name"] for genre in genres]  # Extract genre names
            # Add status as "Completed"
            animes.append({
                "Title": title,
                "Genres": genres_list,
                "Status": "Completed"
            })

        # Convert the list of completed animes to a pandas DataFrame
        df = pd.DataFrame(animes)
        return df
    else:
        raise Exception(f"Failed to fetch user animelist: {response.status_code} {response.text}")
