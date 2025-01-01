import requests
import base64
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs

# Constants
CLIENT_ID = "712ff6e42fbd8756fd23bd5f7fd6a5c8"
CLIENT_SECRET = "d40ad01a4553cf313ba373783a121b794d773cf714ca30eec7a6607a2897847a"
REDIRECT_URI = "http://localhost:8080/auth_page.html"
AUTH_BASE_URL = "https://myanimelist.net/v1/oauth2"
API_BASE_URL = "https://api.myanimelist.net/v2"

def generate_code_challenge():
    """
    Generate a secure code challenge for PKCE.
    """
    random_bytes = os.urandom(32)
    code_verifier = base64.urlsafe_b64encode(random_bytes).decode("utf-8").rstrip("=")
    return code_verifier

class OAuthHandler(BaseHTTPRequestHandler):
    """
    HTTP server handler to capture the authorization code.
    """
    def do_GET(self):
        parsed_url = urlparse(self.path)
        params = parse_qs(parsed_url.query)
        self.server.auth_code = params.get("code", [None])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Authorization code received. You can close this tab.")

def start_http_server():
    """
    Start an HTTP server to listen for the authorization code.
    """
    server = HTTPServer(("localhost", 8080), OAuthHandler)
    server.handle_request()  # Only handle one request
    return server.auth_code

def get_access_token():
    """
    Retrieve an access token using MyAnimeList's OAuth2 API.
    """
    code_challenge = generate_code_challenge()

    # Generate the authorization URL
    auth_url = (
        f"{AUTH_BASE_URL}/authorize?"
        f"{urlencode({'response_type': 'code', 'client_id': CLIENT_ID, 'redirect_uri': REDIRECT_URI, 'code_challenge': code_challenge, 'code_challenge_method': 'plain'})}"
    )
    print("Go to the following URL and authorize the application:")
    print(auth_url)

    # Start the local server to capture the authorization code
    print("\nWaiting for authorization code...")
    auth_code = start_http_server()

    if not auth_code:
        raise Exception("Failed to capture authorization code.")

    # Exchange the authorization code for an access token
    token_url = f"{AUTH_BASE_URL}/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": code_challenge,
    }

    response = requests.post(token_url, data=data)

    if response.status_code == 200:
        print("Access token obtained successfully!")
        return response.json()["access_token"]
    else:
        raise Exception(f"Failed to obtain access token: {response.status_code} {response.text}")

def get_user_completed_animes(username, access_token):
    """
    Fetch the list of completed animes for a specific user.
    """
    url = f"{API_BASE_URL}/users/{username}/animelist"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    params = {
        "status": "completed",
        "fields": "list_status,title",
        "limit": 1000
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()
        return [anime["node"]["title"] for anime in data.get("data", [])]
    else:
        raise Exception(f"Failed to fetch user animelist: {response.status_code} {response.text}")

def main():
    """
    Main function to handle the program flow.
    """
    try:
        print("Welcome to the MyAnimeList Completed Anime Fetcher!")
        username = input("Enter the MyAnimeList username: ").strip()

        # Obtain access token
        access_token = get_access_token()

        # Fetch user's completed animes
        completed_animes = get_user_completed_animes(username, access_token)

        if completed_animes:
            print(f"\nCompleted animes for user {username}:")
            for i, anime in enumerate(completed_animes, start=1):
                print(f"{i}. {anime}")
        else:
            print(f"\nNo completed animes found for user {username}.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
