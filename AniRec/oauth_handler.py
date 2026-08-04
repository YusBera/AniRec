import base64
import json
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

try:
    from .infrastructure.paths import tokens_dir
except ImportError:  # Backward compatibility for direct script-style imports.
    from infrastructure.paths import tokens_dir

AUTH_BASE_URL = "https://myanimelist.net/v1/oauth2"
REQUEST_TIMEOUT_SECONDS = 15


def get_access_token():
    """Get a cached access token, refresh it, or start OAuth if needed."""
    token_data = load_token_from_file()

    if token_data and "access_token" in token_data:
        if token_data.get("expires_at", 0) > int(time.time()):
            print("Using existing access token.")
            return token_data["access_token"]

        if token_data.get("refresh_token"):
            print("Access token expired. Refreshing...")
            return refresh_access_token(token_data["refresh_token"])

    print("No valid access token found. Starting OAuth.")
    return initiate_oauth_flow()


def initiate_oauth_flow():
    """Start the MyAnimeList OAuth flow and cache the returned token."""
    client_id = _get_client_id()
    client_secret = _get_client_secret()
    redirect_uri = _get_redirect_uri()
    code_verifier = generate_code_challenge()
    auth_url = (
        f"{AUTH_BASE_URL}/authorize?"
        f"{urlencode({'response_type': 'code', 'client_id': client_id, 'redirect_uri': redirect_uri, 'code_challenge': code_verifier, 'code_challenge_method': 'plain'})}"
    )
    print("Go to the following URL and authorize the application:")
    print(auth_url)

    print("\nWaiting for authorization code...")
    auth_code = start_http_server(redirect_uri)

    if not auth_code:
        raise RuntimeError("Failed to capture authorization code.")

    data = {
        "client_id": client_id,
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }
    if client_secret:
        data["client_secret"] = client_secret

    response = requests.post(
        f"{AUTH_BASE_URL}/token",
        data=data,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    print("Access token obtained successfully.")
    token_data = _add_expiration(response.json())
    save_token_to_file(token_data)
    return token_data["access_token"]


def refresh_access_token(refresh_token):
    """Refresh the access token using the cached refresh token."""
    client_id = _get_client_id()
    client_secret = _get_client_secret()
    data = {
        "client_id": client_id,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    if client_secret:
        data["client_secret"] = client_secret

    response = requests.post(
        f"{AUTH_BASE_URL}/token",
        data=data,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    print("Access token refreshed successfully.")
    token_data = _add_expiration(response.json())
    save_token_to_file(token_data)
    return token_data["access_token"]


def generate_code_challenge():
    random_bytes = os.urandom(32)
    return base64.urlsafe_b64encode(random_bytes).decode("utf-8").rstrip("=")


def start_http_server(redirect_uri):
    parsed_redirect_uri = urlparse(redirect_uri)
    host = parsed_redirect_uri.hostname or "localhost"
    port = parsed_redirect_uri.port or 8080
    server = HTTPServer((host, port), OAuthHandler)
    server.handle_request()
    return getattr(server, "auth_code", None)


def save_token_to_file(token_data):
    token_file = _get_token_file()
    token_file.parent.mkdir(parents=True, exist_ok=True)
    with token_file.open("w", encoding="utf-8") as file:
        json.dump(token_data, file)


def load_token_from_file():
    token_file = _get_token_file()
    if token_file.exists():
        with token_file.open("r", encoding="utf-8") as file:
            return json.load(file)
    return None


class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)
        params = parse_qs(parsed_url.query)
        self.server.auth_code = params.get("code", [None])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Authorization code received. You can close this tab.")

    def log_message(self, format, *args):
        return


def _get_client_id():
    client_id = os.environ.get("MAL_CLIENT_ID")
    if not client_id:
        raise RuntimeError("MAL_CLIENT_ID is required. Set it before starting OAuth.")
    return client_id


def _get_client_secret():
    return os.environ.get("MAL_CLIENT_SECRET")


def _get_redirect_uri():
    return os.environ.get("MAL_REDIRECT_URI", "http://localhost:8080/callback")


def _get_token_file():
    configured_path = os.environ.get("MAL_TOKEN_FILE")
    return Path(configured_path) if configured_path else tokens_dir() / "token.json"


def _add_expiration(token_data):
    expires_in = int(token_data.get("expires_in", 0))
    token_data["expires_at"] = int(time.time()) + max(expires_in - 60, 0)
    return token_data
