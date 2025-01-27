from flask import Flask, request, jsonify, redirect
import requests
import os
import time
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Strava API credentials
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
# from .env, fallback if not set
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "my_secure_token")
CALLBACK_URL = os.getenv("CALLBACK_URL")  # Publicly accessible URL of your app
DATABASE_URL = os.getenv("DATABASE_URL")  # Heroku provides this automatically
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")  # Token for webhook registration

print(f"CALLBACK_URL: {CALLBACK_URL}")  # For debugging

# Connect to Postgres DB
try:
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor(cursor_factory=RealDictCursor)
except Exception as e:
    print(f"Error connecting to the database: {e}")
    raise

# Create table if not exists
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
    return "Welcome to the Strava Integration App!", 200


@app.route("/auth")
def authorize():
    """Redirect user to Strava OAuth authorization."""
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
    store_user_tokens(
        user_id=user_id,
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        expires_at=tokens["expires_at"]
    )
    # Automatically register the webhook once user has authenticated
    # This ensures the webhook is always set up.
    register_webhook_internal()

    return jsonify({"message": "Authentication successful! Webhook registered.", "user_id": user_id})


def store_user_tokens(user_id, access_token, refresh_token, expires_at):
    """Store or update user tokens in the database."""
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
    """Retrieve user tokens from the database."""
    cursor.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
    return cursor.fetchone()


def delete_user_tokens(user_id):
    """Delete user tokens from the database."""
    cursor.execute('DELETE FROM users WHERE user_id = %s', (user_id,))
    conn.commit()


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
        # Verify webhook registration
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

            user_tokens = get_user_tokens(owner_id)
            if user_tokens:
                if refresh_user_token(owner_id, user_tokens):
                    joke = "Why don’t skeletons fight each other? They don’t have the guts!"
                    response = requests.put(
                        f"https://www.strava.com/api/v3/activities/{activity_id}",
                        headers={
                            "Authorization": f"Bearer {user_tokens['access_token']}"
                        },
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
    """Manually register webhook with Strava."""
    return register_webhook_internal()


def register_webhook_internal():
    """Helper function to register webhook silently."""
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=True)
