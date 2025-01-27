import requests

url = "https://www.strava.com/api/v3/oauth/token"
data = {
    "client_id": "123765",
    "client_secret": "64ed64764a17c172fbd3feb8d3cce4835da0f9a4",
    "code": "8e3dddd701dec29dc0833152a96ba69824889115",
    "grant_type": "authorization_code"
}

response = requests.post(url, data=data)

if response.status_code == 200:
    print("Access Token:", response.json())
else:
    print(f"Error: {response.status_code}, {response.text}")
