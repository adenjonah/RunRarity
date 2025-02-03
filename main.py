from flask import Flask, request, jsonify, redirect, send_file
import os
import time
import json
import requests
import threading
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
CALLBACK_URL = os.getenv("CALLBACK_URL")
DATABASE_URL = os.getenv("DATABASE_URL")

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


@app.route("/")
def index():
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
        return jsonify({"error": "Missing Strava config"}), 500

    url = (f"https://www.strava.com/oauth/authorize"
           f"?client_id={CLIENT_ID}"
           f"&response_type=code"
           f"&redirect_uri={CALLBACK_URL}"
           f"&scope=activity:read_all"
           f"&approval_prompt=auto")
    return redirect(url)


@app.route("/auth/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "No code returned from Strava"}), 400

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

    # Initialize fetch status
    fetch_status[user_id] = {"file_path": "",
                             "in_progress": False, "done": False}

    # Redirect user to a page with two buttons
    return redirect(f"/post-auth?user_id={user_id}")


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
    if tokens["expires_at"] < time.time():
        r = requests.post("https://www.strava.com/api/v3/oauth/token", data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"]
        })
        if r.status_code == 200:
            new_tokens = r.json()
            store_tokens(user_id,
                         new_tokens["access_token"],
                         new_tokens["refresh_token"],
                         new_tokens["expires_at"])
            return True
        return False
    return True


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=True)
