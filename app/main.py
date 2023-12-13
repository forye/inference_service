from flask import Flask, request, jsonify
import os
from app.data_models import OrderData
from pydantic import ValidationError
import xgboost as xgb
import pandas as pd
import redis
from datetime import datetime

DEBUG = True
app = Flask(__name__)
redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

model = xgb.Booster()
model.load_model("model_artifact.json")  # Adjust the path as needed


@app.route('/predict', methods=['POST'])
def predict():
    try:
        order_data = OrderData(**request.json)
    except ValidationError as e:
        return jsonify({"error": "Invalid order data", "details": str(e)}), 400

    # Fetch avg_preparation_time from Redis
    avg_prep_time = redis_client.get(f"venue:{order_data.venue_id}:avg_preparation_time")
    if avg_prep_time is None:
        return jsonify({"error": "venue_id's avg_preparation_time not found in cache"}), 404
    # Prepare the data for prediction
    features = pd.DataFrame([{
        "is_retail": order_data.is_retail,
        "avg_preparation_time": float(avg_prep_time),
        "hour_of_day": pd.to_datetime(order_data.time_received).hour
    }])
    # Convert to DMatrix (if required by the model)
    dmatrix = xgb.DMatrix(features)
    predictions = model.predict(dmatrix)
    # predictions = model.predict(features)

    response = {
        "timestamp": datetime.utcnow().isoformat(),
        "prediction": predictions.tolist(),
        "input data": order_data.dict(),
        "avg_preparation_time":avg_prep_time,
        # Include any other relevant information here
        "input_data": request.json,
        "message": "Prediction successful"
    }
    return jsonify(response)

    # Placeholder for prediction logic
    # data = request.json
    # return jsonify({"message": "Validated data, Prediction made",
    #                 "input data": order_data.dict(), "prediction": predictions.tolist()})

def populate_redis_cache(csv_file_path, redis_host, redis_port):
    try:
        # Read data from the CSV file into a DataFrame
        df = pd.read_csv(csv_file_path)

        # Initialize a Redis client
        redis_client = redis.StrictRedis(host=redis_host, port=redis_port, db=0)

        # Iterate through each row in the DataFrame and populate the cache
        for index, row in df.iterrows():
            venue_id = row['venue_id']
            avg_preparation_time = row['avg_preparation_time']

            # Store the data in the Redis cache with a specific key format
            cache_key = f"venue:{venue_id}:avg_preparation_time"
            redis_client.set(cache_key, avg_preparation_time)

        return True, "Cache population successful"
    except Exception as e:
        return False, f"Cache population failed: {str(e)}"


if __name__ == '__main__':
    # Load the model

    print(populate_redis_cache('venue_preparation.csv','localhost',6379))

    app.run(debug=DEBUG, host='0.0.0.0')
