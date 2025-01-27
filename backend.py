from flask import Flask, request, redirect, jsonify
import requests
import time

app = Flask(__name__)

# Strava API credentials
CLIENT_ID = "123765"
CLIENT_SECRET = "64ed64764a17c172fbd3feb8d3cce4835da0f9a4"
REDIRECT_URI = "http://10.207.60.94:5050/auth/callback"

# In-memory database for user tokens
users = {}


@app.route("/auth")
def authorize():
    # Redirect user to Strava's OAuth page
    url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}"
        f"&scope=activity:read_all,activity:write&approval_prompt=auto"
    )
    return redirect(url)


@app.route("/auth/callback")
def callback():
    # Exchange authorization code for tokens
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
    """Refreshes the user's access token if expired."""
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
            timeout=10
        )
        if response.status_code == 200:
            refreshed_tokens = response.json()
            tokens.update({
                "access_token": refreshed_tokens["access_token"],
                "refresh_token": refreshed_tokens["refresh_token"],
                "expires_at": refreshed_tokens["expires_at"],
            })
            print(f"Token refreshed successfully for user {user_id}.")
        else:
            print(
                f"Failed to refresh token for user {user_id}: {response.json()}")
            return False
    return True


@app.route("/add-jokes")
def add_jokes():
    for user_id, tokens in users.items():
        print(f"Processing user {user_id}...")

        # Refresh token if expired
        if not refresh_user_token(user_id, tokens):
            continue

        # Fetch user activities
        print("Fetching activities...")
        activities_response = requests.get(
            "https://www.strava.com/api/v3/athlete/activities?per_page=5",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            timeout=10
        )
        if activities_response.status_code != 200:
            print(
                f"Failed to fetch activities for user {user_id}: {activities_response.json()}")
            continue

        activities = activities_response.json()
        print(f"Fetched {len(activities)} activities for user {user_id}.")

        # Update activity descriptions with jokes
        num = 1
        for activity in activities:
            if num == 0:
                break

            activity_id = activity["id"]
            current_description = activity.get("description", "")
            joke = "Why don’t skeletons fight each other? They don’t have the guts!"
            updated_description = f"{current_description}\nJoke: {joke}"
            print(f"Updating activity {activity_id} for user {user_id}...")

            update_response = requests.put(
                f"https://www.strava.com/api/v3/activities/{activity_id}",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
                json={"description": updated_description},
                timeout=10
            )
            if update_response.status_code != 200:
                print(
                    f"Failed to update activity {activity_id}: {update_response.json()}")
                continue

            print(
                f"Activity {activity_id} updated successfully for user {user_id}.")
            num -= 1

    print("Finished adding jokes.")
    return jsonify({"message": "Jokes added to activities!"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
