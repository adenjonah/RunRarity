import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve variables
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")
# Replace with your actual public webhook URL
CALLBACK_URL = "https://imagine-image-190266ff1663.herokuapp.com/webhook"
VERIFY_TOKEN = "my_secure_token"  # Replace with your chosen verify token

# API endpoint
SUBSCRIPTION_URL = "https://www.strava.com/api/v3/push_subscriptions"

# Register webhook subscription
payload = {
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "callback_url": CALLBACK_URL,
    "verify_token": VERIFY_TOKEN,
}

headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}"
}

response = requests.post(SUBSCRIPTION_URL, headers=headers, data=payload)

# Handle response
if response.status_code == 201:
    print("Webhook subscription created successfully:")
    print(response.json())
elif response.status_code == 400:
    print("Bad Request - Check your callback URL or verify token:")
    print(response.json())
else:
    print(
        f"Failed to create webhook subscription (HTTP {response.status_code}):")
    print(response.json())
