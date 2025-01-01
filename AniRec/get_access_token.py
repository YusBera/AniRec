#get_access_token.py

def get_access_token():
    """
    Get access token from the file or use refresh token if expired.
    If no token exists, initiate the OAuth flow.
    """
    token_data = load_token_from_file()

    if token_data and "access_token" in token_data:
        # If we have an access token, check if it has expired
        access_token = token_data["access_token"]
        expiration_time = token_data.get("expires_at", 0)
        current_time = int(time.time())  # Use time.time() to get current Unix timestamp

        if expiration_time > current_time:
            # Token is still valid
            print("Using existing access token.")
            return access_token
        else:
            # Token has expired, use the refresh token to get a new one
            print("Access token expired. Refreshing token...")
            refresh_token = token_data.get("refresh_token")
            if refresh_token:
                return refresh_access_token(refresh_token)
            else:
                print("No refresh token available. Please authenticate again.")
                raise Exception("No refresh token available.")
    else:
        # No valid access token found, go through the OAuth flow
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
        token_data = response.json()
        save_token_to_file(token_data)  # Save the token to a file
        return token_data["access_token"]
    else:
        raise Exception(f"Failed to obtain access token: {response.status_code} {response.text}")
