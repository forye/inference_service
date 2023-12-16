# Inference Service README

## Description

The Inference Service is a Python-based application that serves as an API for making predictions using a given XGBoost model.

This service is designed for real-time prediction requests and includes features such as caching, model updates, 
and various deployment options, relying to a config.json for simplicity. 

It provides multiple API endpoints for making predictions and updating the machine learning model.


## Table of Contents

1. [How to Execute](#how-to-execute)
   - [Docker Compose]
   - [Standalone Execution]   
   - [MLflow]
   - [Kubernetes (K8s)]
2. [API Endpoints](#api-endpoints)
   - [`/predict`]
   - [`/predict_many`]
   - [`/update`]
   - [`/update_generic`]
3. [Configuration (config.json)](#configuration-configjson)
4. [Optimizations](#optimizations)
   - [Redis Cache]
   - [Internal LRU Cache]
   - [Online Model Change]
   - [Input Data Validation]
   - [Testing]
   - [Predict vs. Predict Many]
   - [Kubernetes and Load Balancing (Bonus)]
   - [MLflow Integration]
   - [Features and Feature Manipulation]
 5. [Optimizations](#optimizations)
 
##How to Execute
<a id="how-to-execute"></a>

#### notes:

a. The server first populates the redis with the given CSV data in the config.

b. On production some configuration should be taken as env var (the code should be modified accordingly)

c. In order to use predict generic ( for a generic xgb model) the features in the config should be in the 
same order as entered to the model

d. On start, the app loads the content of the venue_prepratation.csv file locally. On production this should be 
shared cache between all services, and the resources should be downloaded (the model and data) from a cloud storage.  


### Docker Compose Execution

To run the Inference Service using Docker Compose, follow these steps:

1. Install Docker and Docker Compose if you haven't already.

2. Build the Docker images and start the Docker containers:

   ```bash
   docker-compose up --build
    ```
  
   The service will be accessible at http://localhost:5000.

### Standalone Execution

To run the Inference Service standalone, follow these steps:

1. Ensure you have Python 3.8 or higher installed.

2. Install the required Python packages by running:

   ```bash
   pip install -r requirements.txt
   ```
   
 3. Start the service:
 
   ```bash
   python app/main.py
   ```
  
The service will be accessible at http://localhost:5000.

Note that it depends on a redis server

### MLflow Execution (bonus- not testsed)

option 1:
The MLflow (toy) version of the service can be executed by running the following command:

```shell script
   CMD ["python", "-m", "app.main_mlflow"]
   ```
option 2:
after the model has been named
one can call using mlflow serve...
    ```bash
    mlflow models serve -m <your_model_name_config> -p 5000
    ```

### Kubernetes (K8s) Execution (bonus- not testsed)

Deploy the application to Kubernetes using the provided Kubernetes configurations:

1. Make sure you have kubectl and a Kubernetes cluster set up.

2. Build your Docker image and push it to a container registry of your choice. Replace your-docker-image:latest in the deployment.yaml file with the image name and tag.

3. Deploy your application to Kubernetes:
    ```bash
   kubectl apply -f k8s/deployment.yaml
    ```
 
This will create a deployment and expose the service using a LoadBalancer. You can adjust the number of replicas and other settings in the deployment.yaml file.


## API Endpoints
<a id="api-endpoints"></a>

### /predict Endpoint
This endpoint is used for making predictions based on input data.

#### POST /predict
Example Request:
    Copy code
    ```json
    {
        "venue_id": "8a61bb7",
        "time_received": "2021-01-01T12:00:00",
        "is_retail": true
    }
    ```
    
Example Response:

    ```json    
    {
        "timestamp": "2023-12-15T12:00:00",
        "prediction": [0.85],
        "avg_preparation_time": 10.5,
        "input_data": {
            "venue_id": "8a61bb7",
            "time_received": "2021-01-01T12:00:00",
            "is_retail": true
        },
        "found_in_cache": true,
        "message": "Prediction successful"
    }
    ```
### /predict_many Endpoint
This endpoint allows batch predictions based on input data for multiple orders.

#### POST /predict_many

Example Request:

    ```json
    {
    "is_retail": [false,false,false,true,false,false],
    "time_received": ["2006-09-20 08:50:01.897036","2006-10-20 11:50:01.897036","2006-10-20 19:50:01.897036","2006-11-20 05:50:01.897036","2006-12-21 09:50:01.897036","2006-12-01 09:50:01.897036"],
    "venue_id": ["8a61bb7","8a61bb7","8a61bb7","1111bb7","8a61bb7","1111bb7"]
    }
    ```
    
Example Response:

    ```json
    {
    "timestamp": "2023-12-15T12:00:00",
    "predictions": [0.85, 0.72, 0.93],
    "avg_preparation_time": 10.5,
    "input_data": {
        "venue_id": ["8a61bb7", "8a61bc8", "8a61bd9"],
        "time_received": ["2021-01-01T12:00:00", "2021-01-02T14:30:00", "2021-01-03T10:15:00"],
        "is_retail": [true, false, true]
    },
    "message": "Prediction successful"
    }
    ```
    
 ### /update Endpoint
 
This endpoint is used to update the machine learning model.

Example Request:

#### POST /update

    ```jsonPOST /update
    {
        "new_model_path": "model_artifact.json",
        "new_model_dict": ""
    }
    ```

Example Response:

    
    ```json
    {
    "message": "update successful",
    "new_model_dict": "",
    "new_model_path": "model_artifact.json"
    }
    ```
    


#### POST /predict_generic

Note: Because its generic, this endpoint do not validate the input

Example Request:
    Copy code
    ```json
    {
        "venue_id": "8a61bb7",
        "time_received": "2021-01-01T12:00:00",
        "is_retail": true
    }
    ```
    
Example Response:

    ```json    
    {
        "timestamp": "2023-12-15T12:00:00",
        "prediction": [0.85],
        "input_data": {
            "venue_id": "8a61bb7",
            "time_received": "2021-01-01T12:00:00",
            "is_retail": true
        },
        "found_in_cache": true,
        "message": "Prediction successful"
    }
    ```

## Configuration (config.json)
<a id="configuration-configjson"></a>


The config.json file defines the configuration parameters for the entire project. Here's an explanation of some key configuration options:

* redis: Configuration for the Redis cache, including host, port, and database.

* mlflow: Configuration for MLflow integration, including the model name.

* features: Configuration for feature extraction, including feature definitions and source features.

* base_model_artifact: Path to the base model artifact.

* avg_prep_time_default: Default value for average preparation time.

* debug: Debug mode flag.

* local_lru_cache_capacity: Capacity of the internal LRU cache.

* cached_data_csv: Path to the CSV file used to populate the Redis cache.


## Optimizations
<a id="optimizations"></a>

### Redis Cache Implementation

The Redis cache is used to store and retrieve frequently used data, such as average preparation times for venues. It reduces the computational load on the application by fetching data from cache whenever possible, improving response times.

### Internal LRU Cache

An internal Least Recently Used (LRU) cache is used to store a small subset of repeating keys. This cache minimizes the need for Redis calls, further improving response times for frequently accessed keys.

### Online Model Change

The /update endpoint allows for dynamic model updates, enabling you to change the machine learning model without restarting the service. You can provide a new model artifact file or a dictionary containing the new model parameters.

### Input Data Validation

Input data is validated to ensure it meets the required format and constraints. This helps prevent errors and ensures the correct usage of the API endpoints.

### Testing

The project includes unit tests, integration tests, and performance tests using Locust. These tests help verify the correctness and performance of the application.

### Predict vs. Predict Many

The /predict and /predict_many endpoints cater to both single and batch prediction requests, allowing for flexibility and efficient use of the service.

###  Kubernetes and Load Balancing (Bonus - not tested)

The Kubernetes deployment configuration (k8s/deployment.yaml) provides scalability and load balancing capabilities. It allows you to scale the application horizontally as needed to handle increased traffic.

### MLflow Integration (Bonus - not tested)

The project offers an (toy) alternative implementation using MLflow for model management. MLflow makes it easy to track, manage, and deploy machine learning models.

### Features and Feature Manipulation
The config.json file defines feature extraction configurations, including transformations using lambda functions. This enables you to customize feature engineering to suit your specific needs.

The features can be boolean or continuous, not categorical

* The feature should be defined in the same order of columns as fed to the model

* Each feature is composed from a single source feature

* The manipulation of a feature is defined using a lambda function under "def"

* Each applicable feature as a default value configured

* Each feature is configured if sould be taken from the request or from the Cache

## Future Improvements

1. Implement predict_multy using gRPC

2. Implement inference using kafka

3. Implement a version that runs MLFlow from cli

4. Add periodic models update

5. Add more tests

6. allow generation of feature from multiple sources

7. Validate the input in predict_generic

8. Add tests according to label distribution and business logic for the endpoints