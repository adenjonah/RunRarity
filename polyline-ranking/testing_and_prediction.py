import joblib


def predict_rarity(polyline_str, model_path="polyline_model.pkl"):
    """
    Predict the rarity score for a given polyline using the trained model.
    :param polyline_str: Polyline string.
    :param model_path: Path to the trained model file.
    :return: Predicted rarity score.
    """
    # Load the trained model
    model = joblib.load(model_path)

    # Extract features from the polyline
    features = calculate_features(polyline_str)
    if features:
        feature_values = list(features.values())
        rarity_score = model.predict([feature_values])[0]
        return rarity_score
    else:
        return "Invalid polyline"


# Example usage
polyline = "snaxFfrlbMHJBRI`AG^..."  # Replace with a real polyline string
predicted_score = predict_rarity(polyline)
print(f"Predicted Rarity Score: {predicted_score}")
