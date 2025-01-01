import requests
import pandas as pd

API_BASE_URL = "https://api.myanimelist.net/v2"

def get_user_completed_animes(username, access_token):
    """
    Fetch the list of completed animes for a user and return relevant data, including the user score.
    """
    url = f"{API_BASE_URL}/users/{username}/animelist"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    params = {
        "status": "completed",  # Focus on completed anime
        "fields": "list_status,title,genres,score",  # Fetch only relevant fields
        "limit": 1000  # You can adjust this limit if needed
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()
        animes = []

        for anime in data.get("data", []):
            title = anime["node"]["title"]
            genres = anime["node"]["genres"]
            genres_list = [genre["name"] for genre in genres]  # Extract genre names
            user_score = anime["list_status"].get("score", None)  # Get the user score if available
            # Add status as "Completed"
            animes.append({
                "Title": title,
                "Genres": genres_list,
                "Status": "Completed",
                "User Score": user_score
            })

        # Convert the list of completed animes to a pandas DataFrame
        df = pd.DataFrame(animes)
        return df
    else:
        raise Exception(f"Failed to fetch user animelist: {response.status_code} {response.text}")
