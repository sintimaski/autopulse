from __future__ import annotations

from fastapi.testclient import TestClient

from autopulse_backend.app import create_app


def test_health_endpoint_returns_ok(backend_test_database_url: str) -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_endpoint_returns_ready_when_database_is_available(
    backend_test_database_url: str,
) -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
