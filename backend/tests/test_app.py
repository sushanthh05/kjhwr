from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("status") == "ok"
    assert payload.get("name") == "Wind Forecast Intelligence API"
    assert payload.get("version") == "0.1.0"


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload == {"status": "healthy"}
