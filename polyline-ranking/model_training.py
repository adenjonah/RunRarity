from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import pandas as pd


def train_model(dataset_path):
    """
    Train a machine learning model to predict rarity scores.
    :param dataset_path: Path to the dataset CSV file.
    """
    # Load dataset
    df = pd.read_csv(dataset_path)
    X = df.drop(columns=["label"])
    y = df["label"]

    # Split into train and test sets
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42)

    # Train Random Forest model
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # Test model
    y_pred = model.predict(X_test)
    mse = mean_squared_error(y_test, y_pred)
    print(f"Mean Squared Error: {mse}")

    # Save the trained model
    import joblib
    joblib.dump(model, "polyline_model.pkl")
    print("Model saved as polyline_model.pkl")


# Example usage
train_model("data/polyline_dataset.csv")
