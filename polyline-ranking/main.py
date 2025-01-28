import json
import pandas as pd
from feature_extraction import calculate_features  # Assuming Script 1 is saved as feature_extraction.py

def process_training_data(input_file, output_file):
    """Extract features from training data and save them as a CSV."""
    with open(input_file, "r") as f:
        training_data = json.load(f)

    dataset = []
    for entry in training_data:
        polyline = entry["polyline"]
        label = entry["label"]
        features = calculate_features(polyline)
        if features:
            features["label"] = label
            dataset.append(features)

    # Save dataset to CSV
    df = pd.DataFrame(dataset)
    df.to_csv(output_file, index=False)
    print(f"Features saved to {output_file}")

# Run feature extraction
process_training_data("data/training_data.json", "data/polyline_dataset.csv")