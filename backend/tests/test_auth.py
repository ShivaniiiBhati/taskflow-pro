from fastapi.testclient import TestClient
from app.main import app


def test_request_without_token_is_rejected():
    unauthenticated = TestClient(app)
    resp = unauthenticated.get("/tasks")
    assert resp.status_code == 401


def test_request_with_wrong_token_is_rejected():
    unauthenticated = TestClient(app)
    unauthenticated.headers.update({"Authorization": "Bearer wrong-token"})
    resp = unauthenticated.get("/tasks")
    assert resp.status_code == 401


def test_health_endpoint_does_not_require_auth():
    """/health is intentionally excluded from the auth guard -- it's
    used for liveness checks/monitoring, not board data."""
    unauthenticated = TestClient(app)
    resp = unauthenticated.get("/health")
    assert resp.status_code == 200


def test_request_with_correct_token_succeeds(client):
    # `client` fixture is pre-authenticated via conftest.
    resp = client.get("/tasks")
    assert resp.status_code == 200
