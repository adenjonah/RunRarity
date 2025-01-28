import json

# Load the downloaded JSON file
input_file = "downloaded.json"
output_file = "filtered_downloaded.json"

try:
    with open(input_file, "r") as f:
        activities = json.load(f)
except FileNotFoundError:
    print(f"Error: {input_file} not found.")
    exit(1)

# Filter out activities where 'polyline' exists but is empty
filtered_activities = [
    {**activity, "label": 1} for activity in activities if activity.get("polyline", None)
]

# Save the cleaned JSON file
with open(output_file, "w") as f:
    json.dump(filtered_activities, f, indent=4)

print(f"Filtered activities saved to {output_file}")
