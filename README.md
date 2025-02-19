# Strava Integration and Activity Rarity Analysis

## Overview

This project demonstrates the integration of Strava's API to authenticate users and fetch their activity data. It also includes a machine learning component to analyze the rarity of these activities based on various features. The project showcases skills in web development, API integration, database management, and machine learning.

## Features

- **Strava Authentication**: Users can authenticate with Strava to allow the application to access their activity data.
- **Activity Fetching**: The application fetches user activities from Strava, focusing on runs with map data.
- **Data Processing**: Activities are processed and stored in a PostgreSQL database.
- **Rarity Analysis**: A machine learning model predicts the rarity of activities based on features like time of day, location, and pace.

## Technologies Used

- **Flask**: Used for building the web application and handling HTTP requests.
- **PostgreSQL**: Database for storing user and activity data.
- **Gunicorn**: WSGI HTTP server for running the Flask application.
- **Python**: Core programming language used throughout the project.
- **Requests**: For making HTTP requests to the Strava API.
- **Pandas**: Data manipulation and analysis library used in the machine learning pipeline.
- **Scikit-learn**: Machine learning library used to train the rarity prediction model.
- **Joblib**: For saving and loading the trained machine learning model.
- **dotenv**: For managing environment variables securely.

## Project Structure

- **Web Application**: The Flask application handles user authentication, data fetching, and serves HTML templates.
  - Code reference: 
    
```1:425:main.py
from flask import Flask, request, jsonify, redirect, send_file
import os
import time
import json
import requests
import threading
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import logging

load_dotenv()
app = Flask(__name__)

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
CALLBACK_URL = os.getenv("CALLBACK_URL")
DATABASE_URL = os.getenv("DATABASE_URL")

# Configure logging
logging.basicConfig(level=logging.INFO)

# Track fetch progress: { user_id: {"file_path": "", "in_progress": bool, "done": bool} }
fetch_status = {}

# Init database
try:
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor(cursor_factory=RealDictCursor)
except Exception as e:
    raise RuntimeError("DB connection failed: " + str(e))

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at BIGINT NOT NULL
)
''')
conn.commit()

cursor.execute('''
CREATE TABLE IF NOT EXISTS activities (
    user_id BIGINT REFERENCES users(user_id),
    activity_id BIGINT PRIMARY KEY,
    name TEXT,
    distance FLOAT,
    moving_time INT,
    elapsed_time INT,
    total_elevation_gain FLOAT,
    type TEXT,
    start_date TIMESTAMP,
    start_latitude FLOAT,
    start_longitude FLOAT,
    end_latitude FLOAT,
    end_longitude FLOAT,
    polyline TEXT,
    average_speed FLOAT,
    max_speed FLOAT,
    average_heartrate FLOAT,
    max_heartrate FLOAT,
    calories FLOAT,
    UNIQUE(user_id, activity_id)
)
''')
conn.commit()


@app.route("/")
def index():
    code = request.args.get("code")
    if code:
        # If there's a code, handle the callback
        return handle_callback(code)
    else:
        # Otherwise, show the index page
        return """
<html>
  <head><title>Donate Activities</title></head>
  <body>
    <h1>Donate Activities</h1>
    <p>Click below to authenticate with Strava.</p>
    <form action="/auth" method="get">
      <button type="submit">Donate Activities</button>
    </form>
  </body>
</html>
"""


@app.route("/auth")
def authorize():
    if not CLIENT_ID or not CALLBACK_URL:
        logging.error("Missing Strava config")
        return jsonify({"error": "Missing Strava config"}), 500

    logging.info("Redirecting to Strava OAuth URL")
    url = (f"https://www.strava.com/oauth/authorize"
           f"?client_id={CLIENT_ID}"
           f"&response_type=code"
           f"&redirect_uri={CALLBACK_URL}/auth/callback"
           f"&scope=activity:read_all"
           f"&approval_prompt=auto")
    return redirect(url)


@app.route("/auth/callback")
def callback():
    code = request.args.get("code")
    if not code:
        logging.error("No code returned from Strava")
        return jsonify({"error": "No code returned from Strava"}), 400

    logging.info("Exchanging code for tokens")
    r = requests.post("https://www.strava.com/api/v3/oauth/token", data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code"
    })
    if r.status_code != 200:
        logging.error("Token exchange failed")
        return jsonify({"error": "Token exchange failed", "details": r.json()}), 400

    tokens = r.json()
    user_id = tokens["athlete"]["id"]
    store_tokens(user_id, tokens["access_token"],
                 tokens["refresh_token"], tokens["expires_at"])

    # Initialize fetch status
    fetch_status[user_id] = {"file_path": "",
                             "in_progress": False, "done": False}

    logging.info(f"User {user_id} authenticated successfully")
    return redirect(f"/post-auth?user_id={user_id}")
...
@app.route("/post-auth")
def post_auth():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400

    return f"""
<html>
  <head>
    <title>Donate Activities</title>
    <script>
      let userId = '{user_id}';
      let pollTimer = null;

      function startFetch() {{
        fetch(`/start-fetch?user_id=${{userId}}`)
          .then(r => r.json())
          .then(() => {{
            console.log("Fetch started");
            pollTimer = setInterval(checkStatus, 1000);
          }});
      }}

      function checkStatus() {{
        fetch(`/fetch-status?user_id=${{userId}}`)
          .then(r => r.json())
          .then(data => {{
            if(data.done) {{
              clearInterval(pollTimer);
              document.getElementById('downloadBtn').disabled = false;
            }}
          }});
      }}

      function downloadFile() {{
        window.location = `/download-file?user_id=${{userId}}`;
      }}
    </script>
  </head>
  <body>
    <h1>Donate Activities (Runs with Maps)</h1>
    <p>Click "Start Fetch" to begin retrieving your activities.</p>
    <button onclick="startFetch()">Start Fetch</button>
    <button id="downloadBtn" onclick="downloadFile()" disabled>Download JSON</button>
  </body>
</html>
"""
...
@app.route("/start-fetch")
def start_fetch():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "No user_id"}), 400

    if user_id not in fetch_status:
        fetch_status[user_id] = {"file_path": "",
                                 "in_progress": False, "done": False}

    # Only start if not already in progress/done
    if (not fetch_status[user_id]["in_progress"]) and (not fetch_status[user_id]["done"]):
        fetch_status[user_id]["in_progress"] = True
        t = threading.Thread(target=do_fetch, args=(user_id,))
        t.start()

    return jsonify({"message": "Fetch initiated"})


@app.route("/fetch-status")
def fetch_status_endpoint():
    user_id = request.args.get("user_id")
    if not user_id or user_id not in fetch_status:
        return jsonify({"done": False})
    return jsonify({"done": fetch_status[user_id]["done"]})


@app.route("/download-file")
def download_file():
    user_id = request.args.get("user_id")
    if not user_id or user_id not in fetch_status:
        return jsonify({"error": "No file"}), 400

    path = fetch_status[user_id]["file_path"]
    if not path or not os.path.exists(path):
        return jsonify({"error": "File not found"}), 404

    return send_file(path, as_attachment=True, download_name=os.path.basename(path))
...
def do_fetch(user_id):
    """
    Background thread: fetch runs (with map) for up to 29 seconds.
    Write them to /tmp. Mark status done.
    """
    try:
        acts = fetch_activities(user_id)
        fname = f"strava_runs_{user_id}.json"
        path = os.path.join("/tmp", fname)
        with open(path, "w") as f:
            json.dump(acts, f, indent=4)
        fetch_status[user_id]["file_path"] = path
    except Exception as e:
        print(f"Error fetching for user {user_id}:", e)
    finally:
        fetch_status[user_id]["in_progress"] = False
        fetch_status[user_id]["done"] = True


def fetch_activities(user_id):
    tokens = get_tokens(user_id)
    if not tokens:
        return []

    if not refresh_token_if_needed(user_id, tokens):
        return []

    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    url = "https://www.strava.com/api/v3/athlete/activities"
    params = {"per_page": 100, "page": 1}
    results = []
    start_time = time.time()

    while time.time() - start_time < 29:  # stop after ~29s
        resp = requests.get(url, headers=headers, params=params, timeout=5)
        if resp.status_code != 200:
            break
        chunk = resp.json()
        if not chunk:
            break
        results.extend(chunk)
        params["page"] += 1

    # Only runs with summary_polyline
    run_data = []
    for r in results:
        if r.get("type") == "Run" and r.get("map", {}).get("summary_polyline"):
            run_data.append({
                "name": r["name"],
                "link": f"https://www.strava.com/activities/{r['id']}",
                "polyline": r["map"]["summary_polyline"]
            })
    return run_data
...
@app.route("/api/process-data")
def process_data():
    user_id = request.args.get("user_id")
    if not user_id:
        logging.error("Missing user_id")
        return jsonify({"error": "Missing user_id"}), 400

    logging.info(f"Processing data for user {user_id}")
    tokens = get_tokens(user_id)
    if not tokens:
        logging.error("User not authenticated")
        return jsonify({"error": "User not authenticated"}), 401

    if not refresh_token_if_needed(user_id, tokens):
        logging.error("Token refresh failed")
        return jsonify({"error": "Token refresh failed"}), 401

    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    url = "https://www.strava.com/api/v3/athlete/activities"
    params = {"per_page": 100, "page": 1}
    activities = []

    while len(activities) < 1000:
        logging.info(f"Fetching page {params['page']} for user {user_id}")
        resp = requests.get(url, headers=headers, params=params, timeout=5)
        if resp.status_code != 200:
            logging.error("Failed to fetch activities")
            break
        chunk = resp.json()
        if not chunk:
            break
        activities.extend(chunk)
        params["page"] += 1

    # Filter and store activities
    for activity in activities:
        if activity.get("type") == "Run" and activity.get("map", {}).get("summary_polyline"):
            store_activity(user_id, activity)

    logging.info(f"Data processing complete for user {user_id}")
    return jsonify({"message": "Data processing complete"})
...
def store_activity(user_id, activity):
    try:
        cursor.execute('''
            INSERT INTO activities (user_id, activity_id, name, distance, moving_time, elapsed_time, 
                                   total_elevation_gain, type, start_date, start_latitude, start_longitude, 
                                   end_latitude, end_longitude, polyline, average_speed, max_speed, 
                                   average_heartrate, max_heartrate, calories)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, activity_id) DO NOTHING
        ''', (
            user_id,
            activity["id"],
            activity["name"],
            activity["distance"],
            activity["moving_time"],
            activity["elapsed_time"],
            activity["total_elevation_gain"],
            activity["type"],
            activity["start_date"],
            activity.get("start_latlng", [None, None])[0],
            activity.get("start_latlng", [None, None])[1],
            activity.get("end_latlng", [None, None])[0],
            activity.get("end_latlng", [None, None])[1],
            activity["map"]["summary_polyline"],
            activity["average_speed"],
            activity["max_speed"],
            activity.get("average_heartrate"),
            activity.get("max_heartrate"),
            activity.get("calories")
        ))
        conn.commit()
        logging.info(f"Activity {activity['id']} for user {user_id} stored successfully.")
    except Exception as e:
        logging.error(f"Failed to store activity {activity['id']} for user {user_id}: {e}")
...
def handle_callback(code):
    logging.info("Exchanging code for tokens")
    r = requests.post("https://www.strava.com/api/v3/oauth/token", data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code"
    })
    if r.status_code != 200:
        logging.error("Token exchange failed")
        return jsonify({"error": "Token exchange failed", "details": r.json()}), 400

    tokens = r.json()
    user_id = tokens["athlete"]["id"]
    store_tokens(user_id, tokens["access_token"],
                 tokens["refresh_token"], tokens["expires_at"])

    # Initialize fetch status
    fetch_status[user_id] = {"file_path": "",
                             "in_progress": False, "done": False}

    logging.info(f"User {user_id} authenticated successfully")
    return redirect(f"/post-auth?user_id={user_id}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=True)
```


- **HTML Templates**: Used for rendering web pages for user interaction.
  - Code reference:
    
```1:8:templates/home.html
<!-- home.html -->
<html>
  <body>
    <h1>Strava Integration Demo</h1>
    <a href="/auth?client_id={{client_id}}">Authenticate with Strava</a>
  </body>
</html>

```

    
```1:12:templates/success.html
<!-- success.html -->
<html>
  <body>
    <h2>Success!</h2>
    <p>Your user ID is {{ user_id }}</p>
    <p>
      <a href="/donate-data?user_id={{ user_id }}">Donate Data</a> |
      <a href="/setup-integration?user_id={{ user_id }}">Setup Integration</a>
    </p>
  </body>
</html>

```


- **Machine Learning**: A pipeline for processing activity data, extracting features, and training a model to predict activity rarity.
  - Code reference:
    
```1:25:polyline-ranking/main.py
import json
import pandas as pd
from feature_extraction import calculate_features  # Assuming Script 1 is saved as feature_extraction.py

def process_training_data(input_file, output_file):
    """Extract features from training data and save them as a CSV."""
    with open(input_file, "r") as f:
        training_data = json.load(f)

    dataset = []
    for entry in training_data:
        polyline = entry["polyline"]
        label = entry["label"]
        features = calculate_features(polyline)
        if features:
            features["label"] = label
            dataset.append(features)

    # Save dataset to CSV
    df = pd.DataFrame(dataset)
    df.to_csv(output_file, index=False)
    print(f"Features saved to {output_file}")

# Run feature extraction
process_training_data("data/training_data.json", "data/polyline_dataset.csv")
```

    
```1:37:polyline-ranking/model_training.py
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import pandas as pd


def train_model(dataset_path):
    """
    Train a machine learning model to predict rarity scores.
    :param dataset_path: Path to the dataset CSV file.
    """
    # Load dataset
    df = pd.read_csv(dataset_path)
    X = df.drop(columns=["label"])
    y = df["label"]

    # Split into train and test sets
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42)

    # Train Random Forest model
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # Test model
    y_pred = model.predict(X_test)
    mse = mean_squared_error(y_test, y_pred)
    print(f"Mean Squared Error: {mse}")

    # Save the trained model
    import joblib
    joblib.dump(model, "polyline_model.pkl")
    print("Model saved as polyline_model.pkl")


# Example usage
train_model("data/polyline_dataset.csv")
```


## Setup and Installation

1. **Clone the Repository**: 
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Install Dependencies**: 
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Variables**: Create a `.env` file and add your Strava API credentials and database URL.

4. **Run the Application**: 
   ```bash
   gunicorn main:app
   ```

5. **Access the Application**: Open your browser and go to `http://localhost:8000`.

## Skills Demonstrated

- **API Integration**: Learned how to integrate with third-party APIs, handle OAuth authentication, and manage API requests.
- **Database Management**: Gained experience in setting up and interacting with a PostgreSQL database using Python.
- **Web Development**: Developed a web application using Flask, handling routes, and rendering HTML templates.
- **Machine Learning**: Built a machine learning model to analyze and predict the rarity of activities, including data preprocessing and model evaluation.

## Future Improvements

- **Enhanced Feature Extraction**: Improve the feature extraction process to include more detailed activity metrics.
- **User Interface**: Develop a more interactive and user-friendly interface.
- **Scalability**: Optimize the application for handling a larger number of users and activities.

## Conclusion

This project serves as a comprehensive demonstration of integrating web technologies with machine learning to provide valuable insights into user activities. It highlights the ability to work with APIs, manage databases, and apply machine learning techniques effectively.
