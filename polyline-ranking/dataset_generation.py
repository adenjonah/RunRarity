import json
import pandas as pd
# Assuming the feature_extraction module is available
from feature_extraction import calculate_features


def process_training_data(input_file, output_file):
    """
    Extract polylines and rankings from a JSON file, calculate features, and save as a CSV.
    :param input_file: Path to the training data JSON file.
    :param output_file: Path to save the generated dataset CSV.
    """
    # Load training data
    with open(input_file, "r") as f:
        training_data = json.load(f)

    data = []
    for entry in training_data:
        polyline = entry.get("polyline")
        label = entry.get("label")

        # Validate the input
        if not polyline or label is None:
            print(f"Skipping invalid entry: {entry}")
            continue

        # Calculate features
        features = calculate_features(polyline)
        if features:
            features["label"] = label  # Add the ranking to the feature set
            data.append(features)

    # Convert to a Pandas DataFrame
    df = pd.DataFrame(data)

    # Save to CSV
    df.to_csv(output_file, index=False)
    print(f"Dataset saved to {output_file}")


# Example usage
input_file = "data/training_data.json"  # Path to your training data JSON
output_file = "data/polyline_dataset.csv"  # Path to save the dataset CSV
process_training_data(input_file, output_file)
