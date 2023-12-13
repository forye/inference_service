import pytest
from app.main import app

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_predict_endpoint(client):
    # Mock request data
    mock_request_data = {
        "venue_id": 123,
        "time_received": "2021-01-01T12:00:00",
        "is_retail": True
    }

    # Send a POST request to the /predict endpoint
    response = client.post('/predict', json=mock_request_data)

    # Check if the response is as expected
    assert response.status_code == 200
    assert "prediction" in response.json


# ntegration test

import pytest
from app.main import app

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_complete_prediction_flow(client):
    # Assuming Redis is running and has necessary data

    # Mock request data
    mock_request_data = {
        "venue_id": 123,
        "time_received": "2021-01-01T12:00:00",
        "is_retail": True
    }

    # Send a POST request to the /predict endpoint
    response = client.post('/predict', json=mock_request_data)

    # Check if the entire flow is completed successfully
    assert response.status_code == 200
    assert "prediction" in response.json
    # Further assertions can be made based on the expected response


# performance test
# from locust import HttpUser, task, between
#
# class QuickstartUser(HttpUser):
#     wait_time = between(1, 2)
#
#     @task
#     def predict_endpoint(self):
#         self.client.post("/predict", json={
#             "venue_id": 123,
#             "time_received": "2021-01-01T12:00:00",
#             "is_retail": True
#         })
