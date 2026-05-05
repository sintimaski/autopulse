from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from autopulse_backend.app import create_app


def _payload() -> dict[str, object]:
    return {
        "type": "runtime_error",
        "path": "/dashboard",
        "session_id": "rum-session-123",
        "ts": datetime.now(tz=UTC).isoformat(),
        "data": {"message": "boom", "load_event_ms": 120.5},
    }


def test_rum_endpoint_accepts_valid_payload(backend_test_database_url: str, monkeypatch) -> None:
    monkeypatch.setenv("DASHBOARD_RUM_MAX_REQUEST_BYTES", "8192")
    app = create_app()
    with TestClient(app) as client:
        response = client.post("/autopulse/rum", json=_payload())
    assert response.status_code == 202
    assert response.json() == {"accepted": True}


def test_rum_endpoint_rejects_oversized_payload(
    backend_test_database_url: str, monkeypatch
) -> None:
    monkeypatch.setenv("DASHBOARD_RUM_MAX_REQUEST_BYTES", "64")
    app = create_app()
    payload = _payload()
    payload["path"] = "/" + ("a" * 120)
    payload["data"] = {f"k{i}": "1234567890" for i in range(10)}
    with TestClient(app) as client:
        response = client.post("/autopulse/rum", json=payload)
    assert response.status_code == 413
    assert response.json() == {"detail": "RUM payload exceeds max request size (256 bytes)."}


def test_rum_endpoint_rejects_unbounded_data_shape(
    backend_test_database_url: str, monkeypatch
) -> None:
    monkeypatch.setenv("DASHBOARD_RUM_MAX_REQUEST_BYTES", "8192")
    app = create_app()
    payload = _payload()
    payload["data"] = {f"k{i}": i for i in range(25)}
    with TestClient(app) as client:
        response = client.post("/autopulse/rum", json=payload)
    assert response.status_code == 422
