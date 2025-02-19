# Strava Integration and Activity Rarity Analysis

## Overview

This project demonstrates the integration of Strava's API to authenticate users and fetch their activity data. It also includes a machine learning component to analyze the rarity of these activities based on various features. The project showcases skills in web development, API integration, database management, and machine learning.

## Features

- **Strava Authentication**: Users can authenticate with Strava to allow the application to access their activity data.
- **Activity Fetching**: The application fetches user activities from Strava, focusing on runs with map data.
- **Data Processing**: Activities are processed and stored in a PostgreSQL database.
- **Rarity Analysis**: A machine learning model predicts the rarity of activities based on features like time of day, location, and pace.

## Technologies Used

- **Flask**: Used for building the web application and handling HTTP requests.
- **PostgreSQL**: Database for storing user and activity data.
- **Gunicorn**: WSGI HTTP server for running the Flask application.
- **Python**: Core programming language used throughout the project.
- **Requests**: For making HTTP requests to the Strava API.
- **Pandas**: Data manipulation and analysis library used in the machine learning pipeline.
- **Scikit-learn**: Machine learning library used to train the rarity prediction model.
- **Joblib**: For saving and loading the trained machine learning model.
- **dotenv**: For managing environment variables securely.

## Project Structure

- **Web Application**: The Flask application handles user authentication, data fetching, and serves HTML templates.
  - Code reference: `main.py`
    ```python
    @app.route("/auth")
    def authorize():
        if not CLIENT_ID or not CALLBACK_URL:
            logging.error("Missing Strava config")
            return jsonify({"error": "Missing Strava config"}), 500

        logging.info("Redirecting to Strava OAuth URL")
        url = (f"https://www.strava.com/oauth/authorize"
               f"?client_id={CLIENT_ID}"
               f"&response_type=code"
               f"&redirect_uri={CALLBACK_URL}/auth/callback"
               f"&scope=activity:read_all"
               f"&approval_prompt=auto")
        return redirect(url)
    ```

- **HTML Templates**: Used for rendering web pages for user interaction.
  - Code reference: `templates/home.html`
    ```html
    <!-- home.html -->
    <html>
      <body>
        <h1>Strava Integration Demo</h1>
        <a href="/auth?client_id={{client_id}}">Authenticate with Strava</a>
      </body>
    </html>
    ```

- **Machine Learning**: A pipeline for processing activity data, extracting features, and training a model to predict activity rarity.
  - Code reference: `polyline-ranking/main.py`
    ```python
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
    ```

## Setup and Installation

1. **Clone the Repository**: 
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Install Dependencies**: 
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Variables**: Create a `.env` file and add your Strava API credentials and database URL.

4. **Run the Application**: 
   ```bash
   gunicorn main:app
   ```

5. **Access the Application**: Open your browser and go to `http://localhost:8000`.

## Skills Demonstrated

- **API Integration**: Learned how to integrate with third-party APIs, handle OAuth authentication, and manage API requests.
- **Database Management**: Gained experience in setting up and interacting with a PostgreSQL database using Python.
- **Web Development**: Developed a web application using Flask, handling routes, and rendering HTML templates.
- **Machine Learning**: Built a machine learning model to analyze and predict the rarity of activities, including data preprocessing and model evaluation.

## Future Improvements

- **Enhanced Feature Extraction**: Improve the feature extraction process to include more detailed activity metrics.
- **User Interface**: Develop a more interactive and user-friendly interface.
- **Scalability**: Optimize the application for handling a larger number of users and activities.

## Conclusion

This project serves as a comprehensive demonstration of integrating web technologies with machine learning to provide valuable insights into user activities. It highlights the ability to work with APIs, manage databases, and apply machine learning techniques effectively.
