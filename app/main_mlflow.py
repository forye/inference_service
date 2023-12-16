
from datetime import datetime
import json
from flask import Flask, request, jsonify
from pydantic import ValidationError
import xgboost as xgb
import pandas as pd
import redis
try:
    from app.data_models import OrderData,UpdateModelPrams
    from app.redis_populate import populate_redis_cache
    # from app.LRUCache import LRUCache
except:
    from data_models import OrderData, UpdateModelPrams
    from redis_populate import populate_redis_cache
    # from LRUCache import LRUCache

from datetime import datetime
import mlflow
import mlflow.xgboost


with open('config.json', 'r') as config_file:
    CONFIG = json.load(config_file)

app = Flask(__name__)
redis_client = redis.Redis(host=CONFIG['redis']["redis_host"], port=CONFIG['redis']["redis_port"],
                           db=CONFIG['redis']["db"], decode_responses=True)

class XgbMlflowSingletonInferer:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(XgbMlflowSingletonInferer, cls).__new__(cls)
            cls._instance.model = None
            cls._instance.load_xgb_model(CONFIG['base_model_artifact'])
        return cls._instance

    def load_xgb_model(self, new_model_path=None, new_model_dict=None):
        if not new_model_path:
            # if URI is not provided, assume the model json is provided and load model as bytarry
            if new_model_dict:
                new_model_path = bytearray(new_model_dict, 'utf-8')
        try:
            mlflow.start_run()
            self.model = mlflow.xgboost.load_model(new_model_path)
            mlflow.end_run()
            mlflow.xgboost.log_model(self.model, CONFIG["mlflow"]["model_name"])
        except Exception as e:
            print(f"Error loading model: {str(e)}")

    def predict(self, *kwargs):
        if self.model:
            return self.model.predict(**kwargs)
        else:
            print("No model loaded.")
            return []

@app.route('/update', methods=['POST'])
def update():
    try:
        model_params = UpdateModelPrams(**request.json)
    except ValidationError as e:
        return jsonify({"error": "Invalid order data", "details": str(e)}), 400

    try:
        XgbMlflowSingletonInferer().load_xgb_model(model_params['new_model_path'], model_params['new_model_dict'])
    except Exception as e:
        return jsonify({"error": "did not update model", "details": str(e)}), 400
    response = {
        "message": "mlflow update successful"
    }
    return jsonify(response)


#better just run: mlflow models serve -m model -p 5001
@app.route('/predict', methods=['POST'])
def predict():
    try:
        order_data = OrderData(**request.json)
    except ValidationError as e:
        return jsonify({"error": "Invalid order data", "details": str(e)}), 400

    model = XgbMlflowSingletonInferer()
    # Fetch avg_preparation_time from Redis
    avg_prep_time = redis_client.get(f"venue:{order_data.venue_id}:avg_preparation_time")
    found_in_cache = True
    if avg_prep_time is None:
        avg_prep_time = CONFIG["avg_prep_time_default"]
        found_in_cache = False
    # Prepare the data for prediction
    features = pd.DataFrame([{
        "is_retail": order_data.is_retail,
        "avg_preparation_time": float(avg_prep_time),
        "hour_of_day": pd.to_datetime(order_data.time_received).hour
    }])
    dmatrix = xgb.DMatrix(features)
    predictions = model.predict(dmatrix)
    response = {
        "timestamp": datetime.utcnow().isoformat(),
        "prediction": predictions.tolist(),
        "avg_preparation_time": avg_prep_time,
        "input_data": request.json,
        "found_in_cache": found_in_cache,
        "message": "Prediction successful"
    }
    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
