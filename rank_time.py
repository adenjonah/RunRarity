from datetime import datetime

# Initialize an array for all minutes in a day (24 hours * 60 minutes = 1440 minutes)
rankings = [0] * 1440

# Define rankings for ranges in minutes since midnight
time_ranges = [
    (0, 240, 5),     # 12:00 am - 4:00 am
    (240, 330, 4),   # 4:00 am - 5:30 am
    (330, 390, 3),   # 5:30 am - 6:30 am
    (390, 450, 2),   # 6:30 am - 7:30 am
    (450, 540, 1),   # 7:30 am - 9:00 am
    (540, 720, 2),   # 9:00 am - 12:00 pm
    (720, 780, 1),   # 12:00 pm - 1:00 pm
    (780, 990, 2),   # 1:00 pm - 4:30 pm
    (990, 1080, 1),  # 4:30 pm - 6:00 pm
    (1080, 1200, 2),  # 6:00 pm - 8:00 pm
    (1200, 1320, 3),  # 8:00 pm - 10:00 pm
    (1320, 1440, 4)  # 10:00 pm - 12:00 am
]

# Populate the rankings array
for start, end, rank in time_ranges:
    for minute in range(start, end):
        rankings[minute] = rank

# Function to convert ISO 8601 time to "minutes since midnight"


def get_minutes_since_midnight(iso_time):
    # Parse the ISO 8601 datetime string
    dt = datetime.strptime(iso_time, "%Y-%m-%dT%H:%M:%SZ")
    # Calculate minutes since midnight
    return dt.hour * 60 + dt.minute

# Function to get the rank based on event time


def get_rank(startdate):
    minutes_since_midnight = get_minutes_since_midnight(startdate)
    return rankings[minutes_since_midnight]


# Example usage
startdate = "2025-01-27T12:02:57Z"  # ISO 8601 format
rank = get_rank(startdate)
print(f"The rank for the event time is {rank}.")
