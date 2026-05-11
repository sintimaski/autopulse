"""Runtime checks for CI reliability-matrix topology (scheduler + async aggregate).

The default integration profile forces ``JOBS_ENABLE_SCHEDULER=false`` and
``INGEST_ASYNC_AGGREGATE_ENABLED=false`` in ``conftest.py`` when
``BACKEND_TEST_DATABASE_URL`` is unset. The dedicated CI job sets
``BACKEND_TEST_DATABASE_URL`` and enables scheduler + aggregate worker; these tests
assert that topology is healthy and observable via ``/internal/metrics``.
"""

from __future__ import annotations

import os
import time

import pytest
from db_reset import truncate_full_schema
from fastapi.testclient import TestClient

from lumonox_backend.app import create_app


def _poll_scheduler_ready(client: TestClient, *, timeout_s: float = 3.0) -> dict:
    deadline = time.monotonic() + timeout_s
    last: dict = {}
    while time.monotonic() < deadline:
        response = client.get("/ready")
        last = response.json()
        if response.status_code == 200 and last.get("scheduler_running") is True:
            return last
        time.sleep(0.05)
    return last


def test_internal_metrics_reports_scheduler_and_aggregate_queue_when_enabled(
    backend_test_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    truncate_full_schema(backend_test_database_url)
    monkeypatch.setenv("JOBS_ENABLE_SCHEDULER", "true")
    monkeypatch.setenv("INGEST_ASYNC_AGGREGATE_ENABLED", "true")
    monkeypatch.setenv("JOBS_ALERT_INTERVAL_SECONDS", "3600")
    monkeypatch.setenv("JOBS_RETENTION_INTERVAL_SECONDS", "3600")
    token = os.environ.get("INTERNAL_METRICS_BEARER_TOKEN") or "test-internal-metrics-token"
    monkeypatch.setenv("INTERNAL_METRICS_BEARER_TOKEN", token)

    app = create_app()
    with TestClient(app) as client:
        ready_body = _poll_scheduler_ready(client)
        assert ready_body.get("status") == "ready", ready_body
        assert ready_body.get("jobs_enable_scheduler") is True
        assert ready_body.get("scheduler_running") is True

        metrics = client.get(
            "/internal/metrics",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert metrics.status_code == 200
    body = metrics.json()
    topology = body["topology_profile"]
    assert topology["jobs_enable_scheduler"] is True
    agg = body["ingest_aggregate_queue"]
    assert agg["enabled"] is True
    assert isinstance(agg.get("max_size"), int)
    assert agg["max_size"] > 0
