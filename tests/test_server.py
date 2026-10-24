from fastapi.testclient import TestClient

from server import api

client = TestClient(api)


def test_hello():
    response = client.get("/v1")
    assert response.status_code == 200
    assert "Judy" in response.text
