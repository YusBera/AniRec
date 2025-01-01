import os
import json
import requests
import base64
from urllib.parse import urlencode, urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
import time

CLIENT_ID = "712ff6e42fbd8756fd23bd5f7fd6a5c8"  # Replace with your client ID
CLIENT_SECRET = "d40ad01a4553cf313ba373783a121b794d773cf714ca30eec7a6607a2897847a"  # Replace with your client secret
REDIRECT_URI = "http://localhost:8080/auth_page.html"
AUTH_BASE_URL = "https://myanimelist.net/v1/oauth2"
API_BASE_URL = "https://api.myanimelist.net/v2"
TOKEN_FILE = "token.json"  # Token file location

def generate_code_challenge():
    random_bytes = os.urandom(32)
    code_verifier = base64.urlsafe_b64encode(random_bytes).decode("utf-8").rstrip("=")
    return code_verifier

class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)
        params = parse_qs(parsed_url.query)
        self.server.auth_code = params.get("code", [None])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Authorization code received. You can close this tab.")

def start_http_server():
    server = HTTPServer(("localhost", 8080), OAuthHandler)
    server.handle_request()
    return server.auth_code

def save_token_to_file(token_data):
    with open(TOKEN_FILE, "w") as file:
        json.dump(token_data, file)

def load_token_from_file():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as file:
            return json.load(file)
    return None

def get_access_token():
    """
    Get access token from the file or use refresh token if expired.
    If no token exists, initiate the OAuth flow.
    """
    token_data = load_token_from_file()

    if token_data and "access_token" in token_data:
        # Check if token is expired
        access_token = token_data["access_token"]
        expiration_time = token_data.get("expires_at", 0)
        current_time = int(time.time())

        if expiration_time > current_time:
            print("Using existing access token.")
            return access_token
        else:
            print("Access token expired. Refreshing token...")
            return refresh_access_token(token_data["refresh_token"])

    print("No valid access token found. Starting OAuth process.")
    return initiate_oauth_flow()

def initiate_oauth_flow():
    """
    Initiates the OAuth flow to get the access token.
    """
    code_challenge = generate_code_challenge()
    auth_url = (
        f"{AUTH_BASE_URL}/authorize?"
        f"{urlencode({'response_type': 'code', 'client_id': CLIENT_ID, 'redirect_uri': REDIRECT_URI, 'code_challenge': code_challenge, 'code_challenge_method': 'plain'})}"
    )
    print("Go to the following URL and authorize the application:")
    print(auth_url)

    print("\nWaiting for authorization code...")
    auth_code = start_http_server()

    if not auth_code:
        raise Exception("Failed to capture authorization code.")

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
        token_data = response.json()
        save_token_to_file(token_data)
        return token_data["access_token"]
    else:
        raise Exception(f"Failed to obtain access token: {response.status_code} {response.text}")

def refresh_access_token(refresh_token):
    """
    Refresh the access token using the refresh token.
    """
    print("Refreshing access token...")
    token_url = f"{AUTH_BASE_URL}/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }

    response = requests.post(token_url, data=data)

    if response.status_code == 200:
        print("Access token refreshed successfully!")
        token_data = response.json()
        save_token_to_file(token_data)
        return token_data["access_token"]
    else:
        raise Exception(f"Failed to refresh access token: {response.status_code} {response.text}")
