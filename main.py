import requests
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get environment variables
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

# Base Strava API URL
BASE_API_URL = "https://www.strava.com/api/v3"

# Headers with authorization token
HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}"
}


def get_authenticated_athlete():
    """Get authenticated athlete details."""
    try:
        response = requests.get(f"{BASE_API_URL}/athlete", headers=HEADERS)
        if response.status_code == 200:
            return response.json()
        else:
            print(
                f"Failed to fetch athlete details. HTTP {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def get_athlete_stats(athlete_id):
    """Get athlete stats for the given athlete ID."""
    try:
        response = requests.get(
            f"{BASE_API_URL}/athletes/{athlete_id}/stats", headers=HEADERS)
        if response.status_code == 200:
            return response.json()
        else:
            print(
                f"Failed to fetch stats. HTTP {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


if __name__ == "__main__":
    # Step 1: Get authenticated athlete details
    athlete = get_authenticated_athlete()
    if athlete:
        athlete_id = athlete.get("id")
        print(f"Authenticated Athlete ID: {athlete_id}")

        # Step 2: Fetch athlete stats using the athlete ID
        stats = get_athlete_stats(athlete_id)
        if stats:
            print("Athlete Stats:")
            print(stats)
