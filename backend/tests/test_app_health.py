from __future__ import annotations

import asyncio
import os

import pytest
from fastapi.testclient import TestClient

from autopulse_backend.api.routes.health import _topology_guardrail_status
from autopulse_backend.app import create_app
from autopulse_backend.jobs import SchedulerHandle


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
    body = response.json()
    assert body["status"] == "ready"
    assert "autopulse_env" in body
    assert "event_plane_mode" in body
    assert "dashboard_auth_enabled" in body
    assert "jobs_enable_scheduler" in body
    assert "jobs_external_cron_ownership" in body
    assert "scheduler_running" in body
    assert "database_run_migrations_on_startup" in body
    assert "topology_guardrails" in body


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
    assert "topology_profile" in body
    topology = body["topology_profile"]
    for field in (
        "event_store",
        "event_plane_mode",
        "duckdb_single_writer_profile",
        "jobs_enable_scheduler",
        "jobs_external_cron_ownership",
        "dashboard_auth_enabled",
        "dashboard_realtime_bus_backend",
    ):
        assert field in topology, f"missing topology field: {field}"
    assert "topology_guardrails" in body
    assert "scheduler_required" in body["topology_guardrails"]
    assert "reasons" in body["topology_guardrails"]
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
        "persist_sql_tail_failed_total",
        "sql_tail_repair_queued_total",
        "sql_tail_repair_enqueue_failed_total",
        "sql_tail_repair_succeeded_total",
        "sql_tail_repair_failed_total",
        "sql_tail_repair_dead_lettered_total",
    ):
        assert field in pressure, f"missing pressure field: {field}"
    assert "ingest_aggregate_queue" in body
    assert "enabled" in body["ingest_aggregate_queue"]
    assert "parquet_export" in body
    assert "enabled" in body["parquet_export"]
    assert "query_enabled" in body["parquet_export"]
    assert "hot_window_hours" in body["parquet_export"]
    assert "lifecycle_enabled" in body["parquet_export"]
    assert "lifecycle_interval_seconds" in body["parquet_export"]
    assert "lifecycle_retention_days" in body["parquet_export"]
    assert "lifecycle_dry_run" in body["parquet_export"]
    assert "object_storage_enabled" in body["parquet_export"]
    assert "object_storage_interval_seconds" in body["parquet_export"]
    assert "object_storage_uri" in body["parquet_export"]
    assert "object_storage_prefix" in body["parquet_export"]
    assert "object_storage_verify_upload" in body["parquet_export"]
    assert "object_storage_restore_root" in body["parquet_export"]


def test_topology_guardrail_status_degraded_when_scheduler_required_but_not_running() -> None:
    status = _topology_guardrail_status(
        autopulse_env="production",
        database_url="sqlite+aiosqlite:///./.autopulse/autopulse.db",
        database_run_migrations_on_startup=True,
        scheduler_running=False,
        jobs_enable_scheduler=True,
        scheduler_required=True,
        dashboard_realtime_bus_backend="postgres_notify",
    )
    assert status["status"] == "degraded"
    assert "risky:scheduler-required-env-scheduler-not-running" in status["reasons"]
    assert status["risky_count"] >= 1


def test_topology_guardrail_status_degraded_when_scheduler_required_but_disabled() -> None:
    status = _topology_guardrail_status(
        autopulse_env="staging",
        database_url="sqlite+aiosqlite:///./.autopulse/autopulse.db",
        database_run_migrations_on_startup=True,
        scheduler_running=False,
        jobs_enable_scheduler=False,
        scheduler_required=True,
        dashboard_realtime_bus_backend="postgres_notify",
    )
    assert status["status"] == "degraded"
    assert any(
        r == "unsafe:scheduler-required-env-without-in-process-scheduler" for r in status["reasons"]
    )
    assert status["unsafe_count"] >= 1


def test_topology_guardrail_status_flags_realtime_risk_for_staging_without_shared_bus() -> None:
    status = _topology_guardrail_status(
        autopulse_env="staging",
        database_url="sqlite+aiosqlite:///./.autopulse/autopulse.db",
        database_run_migrations_on_startup=True,
        scheduler_running=True,
        jobs_enable_scheduler=True,
        scheduler_required=True,
        dashboard_realtime_bus_backend="none",
    )
    assert status["status"] == "degraded"
    assert "risky:realtime-bus-none" in status["reasons"]
    assert status["risky_count"] >= 1


def test_topology_guardrail_status_reports_non_ideal_external_cron_mix_without_degrading() -> None:
    status = _topology_guardrail_status(
        autopulse_env="production",
        database_url="sqlite+aiosqlite:///./.autopulse/autopulse.db",
        database_run_migrations_on_startup=True,
        scheduler_running=True,
        jobs_enable_scheduler=True,
        scheduler_required=False,
        jobs_external_cron_ownership=True,
        dashboard_realtime_bus_backend="postgres_notify",
    )
    assert status["status"] == "healthy"
    assert (
        "non-ideal:external-cron-ownership-with-in-process-scheduler-enabled" in status["reasons"]
    )
    assert status["non_ideal_count"] >= 1
    assert status["unsafe_count"] == 0
    assert status["risky_count"] == 0


def test_topology_guardrail_status_is_healthy_for_dev_with_scheduler_optional() -> None:
    status = _topology_guardrail_status(
        autopulse_env="development",
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/autopulse",
        database_run_migrations_on_startup=True,
        scheduler_running=False,
        jobs_enable_scheduler=False,
        scheduler_required=False,
        dashboard_realtime_bus_backend="none",
    )
    assert status["status"] == "healthy"
    assert status["unsafe_count"] == 0
    assert status["risky_count"] == 0
    assert status["non_ideal_count"] == 0


def test_topology_guardrail_status_flags_risky_non_sql_startup_migrations() -> None:
    status = _topology_guardrail_status(
        autopulse_env="production",
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/autopulse",
        database_run_migrations_on_startup=True,
        scheduler_running=True,
        jobs_enable_scheduler=True,
        scheduler_required=True,
        jobs_external_cron_ownership=False,
        dashboard_realtime_bus_backend="postgres_notify",
    )
    assert status["status"] == "degraded"
    assert "risky:non-sql-startup-migrations-enabled" in status["reasons"]
    assert status["risky_count"] >= 1


def test_startup_hard_fails_when_required_scheduler_does_not_start(
    backend_test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AUTOPULSE_ENV", "staging")
    monkeypatch.setenv("JOBS_ENABLE_SCHEDULER", "true")
    monkeypatch.setenv("JOBS_EXTERNAL_CRON_OWNERSHIP", "false")
    monkeypatch.setattr(
        "autopulse_backend.lifespan.start_scheduler",
        lambda settings: SchedulerHandle(stop_event=asyncio.Event(), tasks=[]),
    )
    app = create_app()
    with (
        pytest.raises(RuntimeError, match="Unsafe topology: scheduler is required"),
        TestClient(app),
    ):
        pass


def test_ready_stays_ready_with_non_ideal_scheduler_ownership_mix(
    backend_test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AUTOPULSE_ENV", "staging")
    monkeypatch.setenv("JOBS_ENABLE_SCHEDULER", "true")
    monkeypatch.setenv("JOBS_EXTERNAL_CRON_OWNERSHIP", "true")
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    guardrails = body["topology_guardrails"]
    assert guardrails["status"] == "healthy"
    assert guardrails["non_ideal_count"] >= 1
    assert (
        "non-ideal:external-cron-ownership-with-in-process-scheduler-enabled"
        in guardrails["reasons"]
    )
