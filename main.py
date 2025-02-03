from flask import Flask, request, jsonify, redirect, render_template, send_file
import os
import time
import json
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

CLIENT_ID = os.getenv("CLIENT_ID")        # Your Strava client ID
CLIENT_SECRET = os.getenv("CLIENT_SECRET")  # Your Strava client secret
# e.g. "https://yourapp.com/auth/callback"
CALLBACK_URL = os.getenv("CALLBACK_URL")
DATABASE_URL = os.getenv("DATABASE_URL")  # e.g. "postgres://..."

# Init database
try:
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor(cursor_factory=RealDictCursor)
except Exception as e:
    raise RuntimeError("Database connection failed: " + str(e))

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at BIGINT NOT NULL
)
''')
conn.commit()


@app.route("/")
def index():
    # A simple page with one button
    return '''
<html>
  <head><title>Donate Activities</title></head>
  <body>
    <h1>Donate Activities</h1>
    <form action="/auth" method="get">
      <button type="submit">Donate Activities</button>
    </form>
  </body>
</html>
'''


@app.route("/auth")
def authorize():
    # Redirect to Strava OAuth
    if not CLIENT_ID or not CALLBACK_URL:
        return jsonify({"error": "Missing Strava config"}), 500
    url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={CALLBACK_URL}"
        f"&scope=activity:read_all"
        f"&approval_prompt=auto"
    )
    return redirect(url)


@app.route("/auth/callback")
def callback():
    # Strava sends us ?code=...
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "No code returned"}), 400

    # Exchange code for tokens
    r = requests.post("https://www.strava.com/api/v3/oauth/token", data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code"
    })
    if r.status_code != 200:
        return jsonify({"error": "Token exchange failed", "details": r.json()}), 400

    tokens = r.json()
    user_id = tokens["athlete"]["id"]
    store_tokens(user_id, tokens["access_token"],
                 tokens["refresh_token"], tokens["expires_at"])

    # Fetch runs that have a summary polyline (map)
    activities = fetch_activities(user_id)
    fname = f"strava_runs_{user_id}.json"
    path = os.path.join("/tmp", fname)
    with open(path, "w") as f:
        json.dump(activities, f, indent=4)

    # Send file directly as an attachment
    return send_file(path, as_attachment=True, download_name=fname)


def fetch_activities(user_id):
    tokens = get_tokens(user_id)
    if not tokens:
        return []

    if not refresh_token_if_needed(user_id, tokens):
        return []

    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    url = "https://www.strava.com/api/v3/athlete/activities"
    params = {"per_page": 100, "page": 1}
    activities = []

    start_time = time.time()
    while (time.time() - start_time) < 29:  # 29-second limit
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            break
        data = resp.json()
        if not data:
            break
        activities.extend(data)
        params["page"] += 1

    # Filter to runs with summary_polyline
    run_activities = []
    for act in activities:
        if act.get("type") == "Run" and act.get("map", {}).get("summary_polyline"):
            run_activities.append({
                "name": act["name"],
                "link": f"https://www.strava.com/activities/{act['id']}",
                "polyline": act["map"]["summary_polyline"]
            })
    return run_activities


def store_tokens(user_id, access_token, refresh_token, expires_at):
    cursor.execute('''
        INSERT INTO users (user_id, access_token, refresh_token, expires_at)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE
        SET access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            expires_at = EXCLUDED.expires_at
    ''', (user_id, access_token, refresh_token, expires_at))
    conn.commit()


def get_tokens(user_id):
    cursor.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
    return cursor.fetchone()


def refresh_token_if_needed(user_id, tokens):
    now = time.time()
    if tokens["expires_at"] < now:
        # Refresh
        r = requests.post("https://www.strava.com/api/v3/oauth/token", data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"]
        })
        if r.status_code == 200:
            new_tokens = r.json()
            store_tokens(
                user_id,
                new_tokens["access_token"],
                new_tokens["refresh_token"],
                new_tokens["expires_at"]
            )
            return True
        else:
            return False
    return True


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=True)
