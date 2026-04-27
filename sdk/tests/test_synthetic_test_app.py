from fastapi.testclient import TestClient

from autopulse.fixtures.synthetic_test_app import create_app


def test_synthetic_app_health_endpoint_starts_cleanly() -> None:
    app = create_app(enable_monitor=False)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["service"] == "synthetic-test-api"
    assert response.headers.get("x-request-id")


def test_synthetic_app_boom_endpoint_returns_500() -> None:
    app = create_app(enable_monitor=True)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom", headers={"x-auth-token": "demo:admin:test-admin"})
    assert response.status_code == 500
