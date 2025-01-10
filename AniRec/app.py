from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import requests

# Initialize Flask app
app = Flask(__name__)

API_BASE_URL = "https://api.myanimelist.net/v2"


# Function to fetch completed animes (as per your earlier code)
def get_user_completed_animes(username, access_token):
    url = f"{API_BASE_URL}/users/{username}/animelist"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    params = {
        "status": "completed",
        "fields": "list_status,title,genres,score",
        "limit": 1000
    }
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            animes = []
            for anime in data.get("data", []):
                title = anime["node"]["title"]
                genres = anime["node"]["genres"]
                genres_list = [genre["name"] for genre in genres]
                user_score = anime["list_status"].get("score", None)
                animes.append({
                    "Title": title,
                    "Genres": genres_list,
                    "Status": "Completed",
                    "User Score": user_score
                })
            return pd.DataFrame(animes)
        else:
            return pd.DataFrame()
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return pd.DataFrame()


# Route to handle dashboard
@app.route('/dashboard', methods=['GET'])
def dashboard():
    username = request.args.get('username', 'default_user')  # Default username or from URL
    # Replace with actual access token handling
    access_token = 'your_access_token_here'
    completed_animes = get_user_completed_animes(username, access_token)

    # Return the dashboard template with completed animes
    return render_template('dashboard.html', username=username, completed_animes=completed_animes)


# Route for generating recommendations (this is where you want to generate anime recommendations)
@app.route('/generate_recommendations', methods=['GET'])
def generate_recommendations():
    # Logic to generate anime recommendations
    # For simplicity, I am just using a placeholder list. Replace this with actual recommendation logic.
    recommendations = [
        {"Title": "One Piece", "Genres": ["Adventure", "Fantasy"], "Score": 8.7},
        {"Title": "Naruto", "Genres": ["Action", "Adventure"], "Score": 8.5},
        {"Title": "Attack on Titan", "Genres": ["Action", "Drama"], "Score": 9.0}
    ]
    return render_template('generate_recommendations.html', recommendations=recommendations)


# Route for user login (if needed)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        return redirect(url_for('dashboard', username=username))
    return render_template('login.html')


# Route for recommendations page (where we can see all recommendations)
@app.route('/recommendations', methods=['GET'])
def recommendations():
    # Placeholder recommendations, you should replace this with dynamic data
    recommendations = [
        {"Title": "Fullmetal Alchemist", "Genres": ["Action", "Adventure"], "Score": 9.1},
        {"Title": "One Punch Man", "Genres": ["Action", "Comedy"], "Score": 8.8},
        {"Title": "Demon Slayer", "Genres": ["Action", "Fantasy"], "Score": 8.9}
    ]
    return render_template('recommendations.html', recommendations=recommendations)


# Home route
@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True)
