from flask import send_file, Flask, request, jsonify, redirect, render_template
import json
import requests
import os
import time
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

app = Flask(__name__)

# If you don't have a fixed client ID, you can let the user supply it.
DEFAULT_CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "my_secure_token")
CALLBACK_URL = os.getenv("CALLBACK_URL")
DATABASE_URL = os.getenv("DATABASE_URL")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

print(f"CALLBACK_URL: {CALLBACK_URL}")

try:
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor(cursor_factory=RealDictCursor)
except Exception as e:
    print(f"Error connecting to the database: {e}")
    raise

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at BIGINT NOT NULL,
    add_integration BOOLEAN DEFAULT FALSE,
    give_data BOOLEAN DEFAULT FALSE
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS user_activities (
    user_id BIGINT,
    activity_id BIGINT,
    name TEXT,
    distance DOUBLE PRECISION,
    start_date TIMESTAMP,
    PRIMARY KEY(user_id, activity_id)
)
''')
conn.commit()


@app.route("/")
def home():
    # Pass along the default (if any) so the template can allow editing
    return render_template("home.html", client_id=DEFAULT_CLIENT_ID)


@app.route("/auth")
def authorize():
    # Allow client_id to be supplied in the URL (e.g. /auth?client_id=123456)
    client_id = request.args.get("client_id", DEFAULT_CLIENT_ID)
    if not client_id or not CALLBACK_URL:
        return jsonify({"error": "Missing OAuth configuration"}), 500

    url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri={CALLBACK_URL}/auth/callback"
        f"&scope=activity:read_all,activity:write"
        f"&approval_prompt=auto"
    )
    return redirect(url)


@app.route("/auth/callback")
def callback():
    code = request.args.get("code")
    r = requests.post("https://www.strava.com/api/v3/oauth/token", data={
        "client_id": DEFAULT_CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
    })
    if r.status_code != 200:
        return jsonify({"error": "Exchange failed", "details": r.json()}), 400

    tokens = r.json()
    user_id = tokens["athlete"]["id"]
    store_tokens(user_id, tokens["access_token"],
                 tokens["refresh_token"], tokens["expires_at"])
    register_webhook_internal()
    return redirect("/success")


@app.route("/success")
def success():
    return render_template("success.html")


def store_tokens(user_id, access_token, refresh_token, expires_at):
    cursor.execute('''
        INSERT INTO users (user_id, access_token, refresh_token, expires_at)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE
        SET access_token=EXCLUDED.access_token,
            refresh_token=EXCLUDED.refresh_token,
            expires_at=EXCLUDED.expires_at
    ''', (user_id, access_token, refresh_token, expires_at))
    conn.commit()


def get_tokens(user_id):
    cursor.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
    return cursor.fetchone()


def refresh_token_if_needed(user_id, tokens):
    if tokens["expires_at"] < time.time():
        r = requests.post("https://www.strava.com/api/v3/oauth/token", data={
            "client_id": DEFAULT_CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"]
        })
        if r.status_code == 200:
            new_tokens = r.json()
            store_tokens(user_id, new_tokens["access_token"],
                         new_tokens["refresh_token"], new_tokens["expires_at"])
            return True
        else:
            return False
    return True


@app.route("/preferences", methods=["POST"])
def set_preferences():
    user_id = request.form.get("user_id")
    add_integration = request.form.get("add_integration") == "true"
    give_data = request.form.get("give_data") == "true"
    cursor.execute('''
        UPDATE users
        SET add_integration=%s, give_data=%s
        WHERE user_id=%s
    ''', (add_integration, give_data, user_id))
    conn.commit()
    return jsonify({"message": "Preferences updated"})


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return jsonify({"hub.challenge": request.args.get("hub.challenge")}), 200
        return "Mismatch", 403
    event = request.json
    if event.get("aspect_type") == "create" and event.get("object_type") == "activity":
        owner_id = event.get("owner_id")
        activity_id = event.get("object_id")
        user_tokens = get_tokens(owner_id)
        if user_tokens and refresh_token_if_needed(owner_id, user_tokens):
            act_req = requests.get(f"https://www.strava.com/api/v3/activities/{activity_id}",
                                   headers={"Authorization": f"Bearer {user_tokens['access_token']}"})
            if act_req.status_code == 200:
                act_data = act_req.json()
                if user_tokens["add_integration"]:
                    desc = act_data.get("description", "")
                    new_desc = desc + ("\n" if desc else "") + \
                        "Data managed by runnershigh.io"
                    requests.put(f"https://www.strava.com/api/v3/activities/{activity_id}",
                                 headers={"Authorization": f"Bearer {
                                     user_tokens['access_token']}"},
                                 json={"description": new_desc})
                if user_tokens["give_data"]:
                    cursor.execute('''
                        INSERT INTO user_activities (user_id, activity_id, name, distance, start_date)
                        VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING
                    ''', (owner_id, activity_id, act_data.get("name", ""),
                          act_data.get("distance", 0), act_data.get("start_date")))
                    conn.commit()
    return "OK", 200


@app.route("/register-webhook", methods=["POST"])
def register_webhook():
    return register_webhook_internal()


def register_webhook_internal():
    payload = {
        "client_id": DEFAULT_CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "callback_url": f"{CALLBACK_URL}/webhook",
        "verify_token": VERIFY_TOKEN
    }
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    r = requests.post(
        "https://www.strava.com/api/v3/push_subscriptions", headers=headers, data=payload)
    if r.status_code == 201:
        return jsonify(r.json())
    else:
        return jsonify({"error": r.json()}), r.status_code


@app.route("/grab-activities", methods=["GET"])
def grab_activities():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "User ID required"}), 400
    user_tokens = get_tokens(user_id)
    if not user_tokens:
        return jsonify({"error": "Not authenticated"}), 401
    if not refresh_token_if_needed(user_id, user_tokens):
        return jsonify({"error": "Refresh token failed"}), 500
    access_token = user_tokens["access_token"]
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"per_page": 100, "page": 1}

    activities = []
    start_time = time.time()
    while time.time() - start_time < 30:
        resp = requests.get(url, headers=headers, params=params, timeout=5)
        if resp.status_code != 200:
            break
        data = resp.json()
        if not data:
            break
        activities.extend(data)
        params["page"] += 1

    run_activities = [{
        "name": x["name"],
        "link": f"https://www.strava.com/activities/{x['id']}",
        "polyline": x.get("map", {}).get("summary_polyline", "")
    } for x in activities if x.get("type") == "Run" and x.get("map", {}).get("summary_polyline")]

    fname = f"strava_runs_{user_id}.json"
    path = os.path.join("/tmp", fname)
    with open(path, "w") as f:
        json.dump(run_activities, f, indent=4)
    return jsonify({
        "message": "Activities fetched",
        "activities_count": len(run_activities),
        "file_url": f"/download-json?user_id={user_id}"
    })


@app.route("/download-json", methods=["GET"])
def download_json():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "User ID required"}), 400
    fname = f"strava_runs_{user_id}.json"
    path = os.path.join("/tmp", fname)
    if not os.path.exists(path):
        return jsonify({"error": "File not found"}), 404
    return send_file(path, as_attachment=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=True)
