from flask import Flask, request, jsonify
import requests
import os
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Strava API credentials
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
VERIFY_TOKEN = "my_secure_token"  # Your chosen verify token
CALLBACK_URL = os.getenv("CALLBACK_URL")  # Publicly accessible URL of your app
users = {}  # In-memory database for storing user tokens


@app.route("/auth")
def authorize():
    """Redirect user to Strava OAuth authorization."""
    url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={CLIENT_ID}&response_type=code&redirect_uri={CALLBACK_URL}/auth/callback"
        f"&scope=activity:read_all,activity:write&approval_prompt=auto"
    )
    return jsonify({"redirect_url": url})


@app.route("/auth/callback")
def callback():
    """Handle OAuth callback and exchange code for tokens."""
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
    users[user_id] = {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "expires_at": tokens["expires_at"],
    }
    return jsonify({"message": "Authentication successful!", "user_id": user_id})


def refresh_user_token(user_id, tokens):
    """Refresh the user's access token if expired."""
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
            tokens.update({
                "access_token": refreshed_tokens["access_token"],
                "refresh_token": refreshed_tokens["refresh_token"],
                "expires_at": refreshed_tokens["expires_at"],
            })
            print(f"Token refreshed successfully for user {user_id}.")
            return True
        else:
            print(
                f"Failed to refresh token for user {user_id}: {response.json()}")
            return False
    return True


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    """Handle webhook verification and events."""
    if request.method == "GET":
        # Webhook verification challenge
        verify_token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if verify_token == VERIFY_TOKEN:
            return jsonify({"hub.challenge": challenge}), 200
        return "Verification token mismatch", 403

    if request.method == "POST":
        # Process webhook events
        event = request.json
        print(f"Webhook event received: {event}")

        if event.get("aspect_type") == "create" and event.get("object_type") == "activity":
            owner_id = event.get("owner_id")
            activity_id = event.get("object_id")

            if owner_id in users:
                tokens = users[owner_id]
                if refresh_user_token(owner_id, tokens):
                    joke = "Why don’t skeletons fight each other? They don’t have the guts!"
                    response = requests.put(
                        f"https://www.strava.com/api/v3/activities/{activity_id}",
                        headers={
                            "Authorization": f"Bearer {tokens['access_token']}"},
                        json={"description": joke},
                    )
                    if response.status_code == 200:
                        print(f"Added joke to activity {activity_id}")
                    else:
                        print(
                            f"Failed to add joke to activity {activity_id}: {response.json()}")
        return "Event processed", 200


@app.route("/register-webhook", methods=["POST"])
def register_webhook():
    """Register webhook with Strava."""
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "callback_url": f"{CALLBACK_URL}/webhook",
        "verify_token": VERIFY_TOKEN,
    }
    headers = {
        "Authorization": f"Bearer {os.getenv('ACCESS_TOKEN')}"
    }
    response = requests.post(
        "https://www.strava.com/api/v3/push_subscriptions", headers=headers, data=payload)
    if response.status_code == 201:
        return jsonify(response.json())
    return jsonify({"error": response.json()}), response.status_code


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=True)
