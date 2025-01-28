from flask import send_file
import json
from flask import Flask, request, jsonify, redirect, render_template
import requests
import os
import time
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

app = Flask(__name__)

CLIENT_ID = os.getenv("CLIENT_ID")
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
        expires_at BIGINT NOT NULL
    )
''')
conn.commit()


@app.route("/")
def home():
    return render_template("home.html"), 200


@app.route("/auth")
def authorize():
    if not CALLBACK_URL:
        return jsonify({"error": "CALLBACK_URL is not set"}), 500

    url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={CLIENT_ID}&response_type=code&redirect_uri={CALLBACK_URL}/auth/callback"
        f"&scope=activity:read_all,activity:write&approval_prompt=auto"
    )
    return redirect(url)


@app.route("/auth/callback")
def callback():
    code = request.args.get("code")
    response = requests.post(
        "https://www.strava.com/api/v3/oauth/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
        },
    )
    if response.status_code != 200:
        return jsonify({"error": "Failed to exchange code", "details": response.json()}), 400

    tokens = response.json()
    user_id = tokens["athlete"]["id"]
    store_user_tokens(
        user_id=user_id,
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        expires_at=tokens["expires_at"]
    )

    # Automatically register the webhook once user has authenticated
    register_webhook_internal()

    # Redirect the user to a success page
    return redirect("/success")


@app.route("/success")
def success():
    return render_template("success.html"), 200


def store_user_tokens(user_id, access_token, refresh_token, expires_at):
    cursor.execute('''
        INSERT INTO users (user_id, access_token, refresh_token, expires_at)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE
        SET access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            expires_at = EXCLUDED.expires_at
    ''', (user_id, access_token, refresh_token, expires_at))
    conn.commit()


def get_user_tokens(user_id):
    cursor.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
    return cursor.fetchone()


def delete_user_tokens(user_id):
    cursor.execute('DELETE FROM users WHERE user_id = %s', (user_id,))
    conn.commit()


def refresh_user_token(user_id, tokens):
    if tokens["expires_at"] < time.time():
        print(f"Refreshing token for user {user_id}...")
        response = requests.post(
            "https://www.strava.com/api/v3/oauth/token",
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"],
            },
        )
        if response.status_code == 200:
            refreshed_tokens = response.json()
            store_user_tokens(
                user_id=user_id,
                access_token=refreshed_tokens["access_token"],
                refresh_token=refreshed_tokens["refresh_token"],
                expires_at=refreshed_tokens["expires_at"]
            )
            print(f"Token refreshed successfully for user {user_id}.")
            return True
        else:
            print(
                f"Failed to refresh token for user {user_id}: {response.json()}")
            return False
    return True


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        verify_token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if verify_token == VERIFY_TOKEN:
            return jsonify({"hub.challenge": challenge}), 200
        return "Verification token mismatch", 403

    if request.method == "POST":
        event = request.json
        print(f"Webhook event received: {event}")

        if event.get("aspect_type") == "create" and event.get("object_type") == "activity":
            owner_id = event.get("owner_id")
            activity_id = event.get("object_id")

            user_tokens = get_user_tokens(owner_id)
            if user_tokens:

                if refresh_user_token(owner_id, user_tokens):
                    joke = "Data managed by runnershigh . io"

                    # Get the existing activity details
                    activity_response = requests.get(
                        f"https://www.strava.com/api/v3/activities/{activity_id}",
                        headers={
                            "Authorization": f"Bearer {user_tokens['access_token']}"
                        },
                    )

                    if activity_response.status_code == 200:
                        existing_activity = activity_response.json()
                        existing_description = existing_activity.get(
                            "description", "")

                        # Append the joke to the existing description
                        new_description = existing_description + "\n" + \
                            joke if existing_description else joke

                        # Update the activity with the new description
                        response = requests.put(
                            f"https://www.strava.com/api/v3/activities/{activity_id}",
                            headers={
                                "Authorization": f"Bearer {user_tokens['access_token']}"
                            },
                            json={"description": new_description},
                        )

                        if response.status_code == 200:
                            print(f"Added joke to activity {activity_id}")

                            # Upload an image to the activity
                            try:

                                with open("./image.png", "rb") as image_file:
                                    upload_response = requests.post(
                                        "https://www.strava.com/api/v3/uploads",
                                        headers={
                                            "Authorization": f"Bearer {user_tokens['access_token']}"
                                        },
                                        files={"file": image_file},
                                        data={
                                            "activity_id": activity_id,
                                            "data_type": "photo",  # Required field to specify the type of upload
                                        },
                                    )

                                    if upload_response.status_code == 201:
                                        print(
                                            f"Successfully added image to activity {activity_id}")
                                    else:
                                        print(
                                            f"Failed to upload image to activity {activity_id}: {upload_response.json()}")
                            except FileNotFoundError:
                                print("Image file not found: ./image.png")
                        else:
                            print(
                                f"Failed to add joke to activity {activity_id}: {response.json()}")
                    else:
                        print(
                            f"Failed to fetch activity details for {activity_id}: {activity_response.json()}")
        return "Event processed", 200


@app.route("/register-webhook", methods=["POST"])
def register_webhook():
    return register_webhook_internal()


def register_webhook_internal():
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "callback_url": f"{CALLBACK_URL}/webhook",
        "verify_token": VERIFY_TOKEN,
    }
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }
    response = requests.post(
        "https://www.strava.com/api/v3/push_subscriptions", headers=headers, data=payload)
    print(f"Webhook registration response: {response.json()}")
    if response.status_code == 201:
        return jsonify(response.json())
    return jsonify({"error": response.json()}), response.status_code


@app.route("/grab-activities", methods=["GET"])
def grab_activities():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "User ID required"}), 400

    user_tokens = get_user_tokens(user_id)
    if not user_tokens:
        return jsonify({"error": "User not authenticated"}), 401

    if not refresh_user_token(user_id, user_tokens):
        return jsonify({"error": "Failed to refresh access token"}), 500

    access_token = user_tokens["access_token"]
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"per_page": 100, "page": 1}

    activities = []
    while True:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            return jsonify({"error": "Failed to fetch activities", "details": response.json()}), 500

        page_data = response.json()
        if not page_data:
            break
        activities.extend(page_data)
        params["page"] += 1

    run_activities = [
        {
            "name": act["name"],
            "link": f"https://www.strava.com/activities/{act['id']}",
            "polyline": act.get("map", {}).get("summary_polyline", ""),
        }
        for act in activities if act.get("type") == "Run" and act.get("map", {}).get("summary_polyline")
    ]

    # Save JSON file in a temporary location
    json_filename = f"strava_runs_{user_id}.json"
    json_path = os.path.join("/tmp", json_filename)
    with open(json_path, "w") as f:
        json.dump(run_activities, f, indent=4)

    return jsonify({
        "message": "Activities saved",
        "file_url": f"/download-json?user_id={user_id}"
    })


@app.route("/download-json", methods=["GET"])
def download_json():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "User ID required"}), 400

    json_filename = f"strava_runs_{user_id}.json"
    json_path = os.path.join("/tmp", json_filename)

    if not os.path.exists(json_path):
        return jsonify({"error": "File not found"}), 404

    return send_file(json_path, as_attachment=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=True)
