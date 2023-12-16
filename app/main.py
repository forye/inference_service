
from datetime import datetime
import json

import numpy as np
from flask import Flask, request, jsonify
from pydantic import ValidationError
import xgboost as xgb
import pandas as pd
import redis

try:
    from app.data_models import OrderData,UpdateModelPrams
    from app.redis_populate import populate_redis_cache
    from app.LRUCache import LRUCache
except:
    from data_models import OrderData, UpdateModelPrams
    from redis_populate import populate_redis_cache
    from LRUCache import LRUCache


with open('config.json', 'r') as config_file:
    CONFIG = json.load(config_file)

DEBUG = CONFIG['debug']

app = Flask(__name__)

REDIS_CLIENT = redis.Redis(host=CONFIG['redis']["redis_host"],
                           port=CONFIG['redis']["redis_port"],
                           db=CONFIG['redis']["db"], decode_responses=True)
LOCAL_LRU = LRUCache(capacity=CONFIG['local_lru_cache_capacity'])


class XgbSingletonInferer:
    _instance = None
    features_names=[]
    features_types=[]

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

    def _load_model_metadata(self, model_dict):
        self.features_names = model_dict['learner']['attributes']['feature_names']
        self.features_types = model_dict['learner']['attributes']['feature_types']

    def _maybe_load_model_from_path(self, new_model_path):
        if new_model_path:
            try:
                self.model = self.model_callable()
                self.model.load_model(new_model_path)
                try:
                    with open(new_model_path, 'r') as f:
                        model_dict = json.load(f)
                        self._load_model_metadata(self, model_dict)
                except:
                    # something went wrong with the hack of reading that json
                    pass
            except Exception as e:
                print(f"Error loading model from path: {str(e)}")

    def _maybe_load_model_from_json(self, new_model_dict):
        if new_model_dict:
            try:
                self.model = self.model_callable()
                self.model.load_model(bytearray(new_model_dict, 'utf-8'))
                self._load_model_metadata(self, new_model_dict)
            except Exception as e:
                print(f"Error loading model from JSON: {str(e)}")

    def predict(self, x):
        if self.model:
            return self.model.predict(x)
        else:
            print("No model loaded.")
            return None

    def validate_input(self, request_data):
        if not self.features_names:
            return True, "Cant validate"
        for iftr, ftr in enumerate(self.features_names):
            if ftr not in request_data:
                return False, f"validation error, {ftr} not in request"
            if str(type(request_data[ftr]))!=self.features_types[iftr]:
                return False, f"validation error, missmatch between {ftr} feature data type"
        return True, "Input Data Validated"

    def validate_output(self, predctions):
        return np.max(predctions) < 99999999 and np.min(predctions)>=0, "Output data validation"



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

        response = {
            "new_model_dict": model_params.new_model_dict,
            "new_model_path": model_params.new_model_path,
            "message": "update successful"
        }
        return jsonify(response)
    except Exception as e:
        return jsonify({"error": "did not update model", "details": str(e)}), 400

"""
{
    "is_retail": false,
    "time_received": "2006-10-20 09:50:01.897036",
    "venue_id": "8a61bb7"
  }
"""

def get_value_from_cache(key,subkey="avg_preparation_time",namespace="venue"):
    global LOCAL_LRU
    # Fetch avg_preparation_time from Cach
    pred_time_key = f"{namespace}:{key}:{subkey}"
    # first, try to fetch value from local lru cache, to save a call to redis
    avg_prep_time = LOCAL_LRU.get(pred_time_key)
    # then,  try redis
    if avg_prep_time is None:
        avg_prep_time = REDIS_CLIENT.get(pred_time_key)
        LOCAL_LRU.put(pred_time_key, avg_prep_time)
    # not in cache, set to default value
    found_in_cache = avg_prep_time is not None
    if avg_prep_time is None:
        avg_prep_time = CONFIG['avg_preparation_time_default']
    return avg_prep_time, found_in_cache


def get_cached_bached(ven_ids, namespace='venue',subkey='avg_preparation_time',default_val=None):
    global LOCAL_LRU
    keys_to_query = [f"{namespace}:{ven_id}:{subkey}" for ven_id in ven_ids]
    avg_prep_time = np.ones(len(ven_ids))*-1.0
    key_to_redis = []
    for ik, k in enumerate(keys_to_query):
        avg_prep_time[ik] = LOCAL_LRU.get(k)
        if avg_prep_time[ik] is None:
            key_to_redis.append(k)
    redis_values = REDIS_CLIENT.mget(key_to_redis)
    p = 0
    for ik, k in enumerate(keys_to_query):
        if avg_prep_time[ik] is None:
            avg_prep_time[ik] = redis_values[p]
            p += 1
            if avg_prep_time[ik] is None:
                avg_prep_time = default_val
            else:
                LOCAL_LRU.put(k, redis_values[p])
    return avg_prep_time


@app.route('/predict', methods=['POST'])
def predict():
    request_data = request.json
    try:
        _ = OrderData(**request_data)  # This line can be removed if you don't use the variable _
    except ValidationError as e:
        return jsonify({"error": "Invalid order data in request", "details": str(e)}), 400

    # Load model (singleton)
    try:
        model = XgbSingletonInferer(new_model_path=CONFIG['base_model_artifact'])

        avg_prep_time, found_in_cache = get_value_from_cache(request_data['venue_id'],
                                                             subkey="avg_preparation_time",
                                                             namespace="venue")
        request_data.update({'avg_preparation_time': avg_prep_time})
        features = pd.DataFrame([{
            "is_retail": request_data["is_retail"],
            "avg_preparation_time": float(request_data['avg_preparation_time']),
            "hour_of_day": pd.to_datetime(request_data["time_received"]).hour
        }])


        is_validated, validation_message = model.validate_input(features.iloc[0].to_dict())
        if not is_validated:
            return jsonify({"error": "features" + validation_message}), 400

        dmatrix = xgb.DMatrix(features)
        prediction = model.predict(dmatrix)
        is_validated, validation_message = model.validate_output(prediction)

        if not is_validated:
            return jsonify({"error": validation_message}), 400
        response = {
            "timestamp": datetime.utcnow().isoformat(),
            "prediction": prediction.tolist(),
            "avg_preparation_time": avg_prep_time,
            "input_data": request.json,
            "found_in_cache": found_in_cache,
            "message": "Prediction successful"
        }
        return jsonify(response)
    except Exception as ex:
        return jsonify({"error": str(ex)}), 400


@app.route('/predict_generic', methods=['POST'])
def predict_generic():
    try:

        request_data = request.json

        # Load model (singleton)
        model = XgbSingletonInferer(new_model_path=CONFIG['base_model_artifact'])

        for f_name, f_params in CONFIG['features'].items():
            if not f_params['cache']:
                continue
            val, found_in_cache = get_value_from_cache(request_data[f_params['cache']['cached_key']],
                                                       subkey=f_params['source_feature'],
                                                       namespace=f_params['cache']['cached_namespace'])
            request_data.update({f_name: val})

        features_df = pd.DataFrame(
            [{k: eval(v["def"])(request_data[v['source_feature']]) for k, v in CONFIG["features"].items()}])

        is_validated, validation_message = model.validate_input(features_df.iloc[0].to_dict())
        if not is_validated:
            return jsonify({"error": "features dict" + validation_message}), 400

        dmatrix = xgb.DMatrix(features_df)
        prediction = model.predict(dmatrix)

        is_validated, validation_message = model.validate_output(prediction)

        if not is_validated:
            return jsonify({"error": validation_message}), 400

        response = {
            "timestamp": datetime.utcnow().isoformat(),
            "prediction": prediction.tolist(),
            "input_data": request.json,
            "found_in_cache": found_in_cache,
            "message": "Prediction successful"
        }
        return jsonify(response)
    except Exception as ex:
        return jsonify({"error": str(ex)}), 400

def validate_input_many(features_data):
    # Validate input

    if not isinstance(features_data, dict) or isinstance(list(features_data.values())[0], list):
        return jsonify({"error": "Invalid input format. Expected a JSON object with feature names as keys and arrays as values."}), 400

    # Check if all arrays have the same length
    data_lengths = {feature_name: len(data) for feature_name, data in features_data.items()}
    if len(set(data_lengths.values())) > 1:
        return jsonify({"error": "Input arrays must have the same length."}), 400


@app.route('/predict_many', methods=['POST'])
def predict_many():
    features_data = request.json
    try:
        validate_input_many(features_data)

        # Load model (singleton)
        model = XgbSingletonInferer(new_model_path=CONFIG['base_model_artifact'])

        avg_prep_time = get_cached_bached(features_data['venue_id'], namespace='venue',
                                          subkey='avg_preparation_time',
                                          default_val=CONFIG['features']['avg_preparation_time'].get("default_val", None))
        # data frame now is 2d!
        features = pd.DataFrame({
            "is_retail": features_data['is_retail'],
            "avg_preparation_time": avg_prep_time,
            "hour_of_day": pd.to_datetime(features_data['time_received']).hour
        })

        # validating the model input features match and the cant validate vectorised yet, tbd.
        is_validated, validation_message = model.validate_input(features.iloc[0].to_dict())
        if not is_validated:
            return jsonify({"error": validation_message}), 400

        dmatrix = xgb.DMatrix(features)
        predictions = model.predict(dmatrix)

        response = {
            "timestamp": datetime.utcnow().isoformat(),
            "predictions": predictions.tolist(),
            "avg_preparation_time": avg_prep_time.mean(),
            "input_data": features_data,
            "message": "Prediction successful"
        }
        return jsonify(response)
    except Exception as e:
        return jsonify({"error": "did not update model", "details": str(e)}), 400



if __name__ == '__main__':
    # Load the model
    print(populate_redis_cache(CONFIG['cached_data_csv'], CONFIG['redis']['redis_host'], CONFIG['redis']['redis_port']))

    app.run(debug=DEBUG, host='0.0.0.0')
