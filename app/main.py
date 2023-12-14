from flask import Flask, request, jsonify
import os
from app.data_models import OrderData,UpdateModelPrams
from app.redis_populate import populate_redis_cache

from pydantic import ValidationError
import xgboost as xgb
import pandas as pd
import redis
from datetime import datetime

DEBUG = True
app = Flask(__name__)
redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

INFERER=None

class XgbInferer:
    _instance = None
    avg_prep_time_default = 15.0

    def __new__(cls, new_model_path=None, new_model_dict=None):
        if cls._instance is None:
            cls._instance = super(XgbInferer, cls).__new__(cls)
            cls._instance.model = None  # Initialize the model attribute
            cls._instance.load_xgb_model(new_model_path=new_model_path, new_model_dict=new_model_dict)
        return cls._instance

    def load_xgb_model(self, new_model_path=None, new_model_dict=None):
        self.maybe_load_model_from_path(new_model_path)
        self.maybe_load_model_from_json(new_model_dict)
        return self

    def maybe_load_model_from_path(self, new_model_path):
        if new_model_path:
            try:
                self.model = xgb.Booster()
                self.model.load_model(new_model_path)
            except Exception as e:
                print(f"Error loading model from path: {str(e)}")

    def maybe_load_model_from_json(self, new_model_dict):
        if new_model_dict:
            try:
                self.model = xgb.Booster()
                self.model.load_model(bytearray(new_model_dict, 'utf-8'))
            except Exception as e:
                print(f"Error loading model from JSON: {str(e)}")

    def predict(self, *kwargs):
        if self.model:
            return self.model.predict(**kwargs)
        else:
            print("No model loaded.")
            return []


"""
{ "new_model_path":"model_artifact.json", "new_model_dict":"" }
"""
@app.route('/update', methods=['POST'])
def update():
    try:
        model_params = UpdateModelPrams(**request.json)
    except ValidationError as e:
        return jsonify({"error": "Invalid order data", "details": str(e)}), 400
    try:
        INFERER = XgbInferer(new_model_path="").load_xgb_model(new_model_dict=model_params.new_model_dict, new_model_path=model_params.new_model_path)
    except Exception as e:
        return jsonify({"error": "did not update model", "details": str(e)}), 400
    response = {
        "new_model_dict": model_params.new_model_dict,
        "new_model_path": model_params.new_model_path,
        "message": "update successful"
    }
    return jsonify(response)

"""
{
    "is_retail": false,
    "time_received": "2006-10-20 09:50:01.897036",
    "venue_id": "8a61bb7"
  }
"""

@app.route('/predict', methods=['POST'])
def predict():
    try:
        order_data = OrderData(**request.json)
    except ValidationError as e:
        return jsonify({"error": "Invalid order data", "details": str(e)}), 400

    INFERER = XgbInferer(new_model_path="model_artifact.json")
    # Fetch avg_preparation_time from Redis
    avg_prep_time = redis_client.get(f"venue:{order_data.venue_id}:avg_preparation_time")
    found_in_cach = True
    if avg_prep_time is None:
        avg_prep_time = INFERER.avg_prep_time_default
        found_in_cach = False
    # Prepare the data for prediction
    features = pd.DataFrame([{
        "is_retail": order_data.is_retail,
        "avg_preparation_time": float(avg_prep_time),
        "hour_of_day": pd.to_datetime(order_data.time_received).hour
    }])
    dmatrix = xgb.DMatrix(features)
    predictions = INFERER.model.predict(dmatrix)
    response = {
        "timestamp": datetime.utcnow().isoformat(),
        "prediction": predictions.tolist(),
        "avg_preparation_time":avg_prep_time,
        "input_data": request.json,
        "found_in_cach": found_in_cach,
        "message": "Prediction successful"
    }
    return jsonify(response)






if __name__ == '__main__':
    # Load the model

    print(populate_redis_cache('venue_preparation.csv', 'redis', 6379))

    app.run(debug=DEBUG, host='0.0.0.0')
