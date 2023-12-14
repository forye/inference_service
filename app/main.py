from flask import Flask, request, jsonify
import os
try:
    from app.data_models import OrderData,UpdateModelPrams
    from app.redis_populate import populate_redis_cache
    from app.LRUCache import LRUCache
except:
    from data_models import OrderData, UpdateModelPrams
    from redis_populate import populate_redis_cache
    from LRUCache import LRUCache
from pydantic import ValidationError
import xgboost as xgb
import pandas as pd
import redis
from datetime import datetime
import json



with open('config.json', 'r') as config_file:
    CONFIG = json.load(config_file)

DEBUG = CONFIG['debug']

app = Flask(__name__)
redis_client = redis.Redis(host=CONFIG['redis']["redis_host"], port=CONFIG['redis']["redis_port"], db=CONFIG['redis']["db"], decode_responses=True)
LOCAL_LRU = LRUCache(capacity=CONFIG['local_lru_cache_capacity'])


class XgbSingletonInferer:
    _instance = None

    def __new__(cls, new_model_path=None, new_model_dict=None, model_callable=xgb.Booster):
        if cls._instance is None:
            cls._instance = super(XgbSingletonInferer, cls).__new__(cls)
            cls._instance.model = None  # Initialize the model attribute
            if model_callable is None:
                raise Exception('No model to call')
            cls.model_callable = model_callable
            cls._instance.load_xgb_model(new_model_path=new_model_path, new_model_dict=new_model_dict)
        return cls._instance

    def load_xgb_model(self, new_model_path=None, new_model_dict=None):
        self._maybe_load_model_from_path(new_model_path)
        self._maybe_load_model_from_json(new_model_dict)
        return self

    def _maybe_load_model_from_path(self, new_model_path):
        if new_model_path:
            try:
                self.model = self.model_callable()
                self.model.load_model(new_model_path)
            except Exception as e:
                print(f"Error loading model from path: {str(e)}")

    def _maybe_load_model_from_json(self, new_model_dict):
        if new_model_dict:
            try:
                self.model = self.model_callable()
                self.model.load_model(bytearray(new_model_dict, 'utf-8'))
                # self.model.load_model(bytearray(json.loads(new_model_dict), 'utf-8'))
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
        XgbSingletonInferer(new_model_path="").load_xgb_model(new_model_dict=model_params.new_model_dict, new_model_path=model_params.new_model_path)
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
    # validate input
    try:
        order_data = OrderData(**request.json)
    except ValidationError as e:
        # if the request is a list
        return jsonify({"error": "Invalid order data", "details": str(e)}), 400

    # load model (singleton
    model = XgbSingletonInferer(new_model_path="model_artifact.json")

    # Fetch avg_preparation_time from Cach
    # first,  try to fetch value from local lru cache, to save a call to redis
    pred_time_key = f"venue:{order_data.venue_id}:avg_preparation_time"
    avg_prep_time = LOCAL_LRU.get(pred_time_key)
    # then,  try redis
    if avg_prep_time is None:
        avg_prep_time = redis_client.get(pred_time_key)
        LOCAL_LRU.put(pred_time_key, avg_prep_time)
    # not in cache, set to default value
    found_in_cache = avg_prep_time is not None
    if avg_prep_time is None:
        avg_prep_time = CONFIG['avg_prep_time_default']        

    # Prepare the data for prediction
    # features_mapping = {
    #     "is_retail": "order_data.is_retail",
    #     "avg_preparation_time": "float(avg_prep_time)",
    #     "hour_of_day": "pd.to_datetime(order_data.time_received).hour"
    # }
    # features = pd.DataFrame([{feature:eval(features_mapping[feature]) for feature in features_mapping.keys()}])
    features = pd.DataFrame([{
        "is_retail": order_data.is_retail,
        "avg_preparation_time": float(avg_prep_time),
        "hour_of_day": pd.to_datetime(order_data.time_received).hour
    }])
    dmatrix = xgb.DMatrix(features)
    predictions = model.model.predict(dmatrix)
    response = {
        "timestamp": datetime.utcnow().isoformat(),
        "prediction": predictions.tolist(),
        "avg_preparation_time":avg_prep_time,
        "input_data": request.json,
        "found_in_cache": found_in_cache,
        "message": "Prediction successful"
    }
    return jsonify(response)



if __name__ == '__main__':
    # Load the model
    print(populate_redis_cache(CONFIG['cached_data_csv'], CONFIG['redis']['redis_host'], CONFIG['redis']['redis_port']))

    app.run(debug=DEBUG, host='0.0.0.0')
