from __future__ import annotations

import os

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


def test_internal_metrics_includes_ingest_pressure_view(
    backend_test_database_url: str,
) -> None:
    """Operators need backpressure signals surfaced; snapshot contract check."""
    token = os.environ.get("INTERNAL_METRICS_BEARER_TOKEN") or "test-internal-metrics-token"
    os.environ["INTERNAL_METRICS_BEARER_TOKEN"] = token
    app = create_app()
    with TestClient(app) as client:
        response = client.get(
            "/internal/metrics",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    body = response.json()
    assert "ingest_pressure" in body
    pressure = body["ingest_pressure"]
    for field in (
        "accepted_events_total",
        "rate_limited_total",
        "payload_too_large_total",
        "payload_too_large_header_total",
        "payload_too_large_stream_total",
        "aggregate_worker_enqueue_failed_total",
        "aggregate_worker_queue_full_total",
        "aggregate_worker_sync_fallback_total",
        "aggregate_worker_failed_total",
    ):
        assert field in pressure, f"missing pressure field: {field}"
    assert "ingest_aggregate_queue" in body
    assert "enabled" in body["ingest_aggregate_queue"]
