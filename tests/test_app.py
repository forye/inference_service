import pytest
from app.main import app
from locust import HttpUser, task, between
import unittest

MOCK_REQUEST_DATA = {
        "venue_id": "8a61bb7",
        "time_received": "2021-01-01T12:00:00",
        "is_retail": True
    }

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

class TestYourAPI(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.app = app.test_client()

    def tearDown(self):
        pass


    def test_predict_endpoint(self):
        # Send a POST request to the /predict endpoint
        response = self.app.post('/predict', json=MOCK_REQUEST_DATA)

        # Check if the response is as expected
        assert response.status_code == 200
        assert "prediction" in response.json

    def test_predict_generic_endpoint(self):
        # Send a POST request to the /predict endpoint
        response = self.app.post('/predict_generic', json=MOCK_REQUEST_DATA)

        # Check if the response is as expected
        assert response.status_code == 200
        assert "prediction" in response.json
        # tbd add more test according to label distribution and business logic


# integration test
@pytest.fixtures
def client():
    with app.test_client() as client:
        yield client

def test_complete_prediction_flow(client):
    # Assuming Redis is running and has necessary data

    # Send a POST request to the /predict endpoint
    response = client.post('/predict', json=MOCK_REQUEST_DATA)

    # Check if the entire flow is completed successfully
    assert response.status_code == 200
    assert "prediction" in response.json
    # Further assertions can be made based on the expected response
    assert response.json['prediction'] >= 0
    assert response.json['prediction'] is not None


# performance test
class QuickstartUser(HttpUser):
    wait_time = between(1, 2)

    @task
    def predict_endpoint(self):
        self.client.post("/predict", json=MOCK_REQUEST_DATA)
