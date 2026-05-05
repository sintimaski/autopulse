from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from db_reset import truncate_ingest_core_tables as _truncate_tables
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from autopulse_backend.app import create_app
from autopulse_backend.auth import generate_api_key
from autopulse_backend.metrics import service_metrics
from autopulse_backend.models import ApiKey, Project


def _seed_project_and_key(database_url: str) -> tuple[str, str]:
    async def run() -> tuple[str, str]:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                project = Project(id=uuid4(), name="Test Project")
                key_value, key_id, key_salt, key_hash = generate_api_key()
                api_key = ApiKey(
                    project_id=project.id,
                    key_id=key_id,
                    key_salt=key_salt,
                    key_hash=key_hash,
                )
                session.add(project)
                session.add(api_key)
                await session.commit()
                return (key_value, str(project.id))
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _query_event_rows(database_url: str) -> list[dict[str, object]]:
    async def run() -> list[dict[str, object]]:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                result = await session.execute(
                    text(
                        "SELECT CAST(project_id AS TEXT), sdk_version, type, status_code, "
                        "request_id FROM events ORDER BY id"
                    )
                )
                return [dict(row) for row in result.mappings().all()]
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _query_latest_payload(database_url: str) -> dict[str, object] | None:
    async def run() -> dict[str, object] | None:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                result = await session.execute(
                    text("SELECT payload FROM events ORDER BY id DESC LIMIT 1")
                )
                payload = result.scalar_one_or_none()
                return payload if isinstance(payload, dict) else None
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _count_events(database_url: str) -> int:
    async def run() -> int:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                result = await session.execute(text("SELECT COUNT(*) FROM events"))
                return int(result.scalar_one())
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _list_indexes(database_url: str) -> list[str]:
    async def run() -> list[str]:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                result = await session.execute(
                    text(
                        """
                        SELECT indexname
                        FROM pg_indexes
                        WHERE schemaname = 'public'
                        ORDER BY indexname
                        """
                    )
                )
                return [str(name) for name in result.scalars().all()]
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_migration_creates_tables_and_indexes(backend_test_database_url: str) -> None:
    indexes = _list_indexes(backend_test_database_url)
    assert "ix_api_keys_key_id" in indexes
    assert "ix_events_project_timestamp_desc" in indexes
    assert "ix_events_project_type_timestamp_desc" in indexes
    assert "ix_events_project_path_timestamp_desc" in indexes
    assert "ix_alert_dispatches_project_triggered_at" in indexes
    assert "ix_alert_dispatches_project_type_triggered_at" in indexes
    assert "ix_metric_buckets_project_minute" in indexes
    assert "ix_error_group_aggregates_project_last_seen" in indexes


def test_ingest_rejects_missing_auth_header(backend_test_database_url: str) -> None:
    _truncate_tables(backend_test_database_url)
    app = create_app()
    payload = {
        "events": [
            {
                "type": "request",
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/health",
                "status_code": 200,
                "latency_ms": 12.5,
            }
        ]
    }
    with TestClient(app) as client:
        response = client.post("/ingest", json=payload)
    assert response.status_code == 401
    assert _count_events(backend_test_database_url) == 0


def test_ingest_persists_batch_with_metadata(backend_test_database_url: str) -> None:
    _truncate_tables(backend_test_database_url)
    key, project_id = _seed_project_and_key(backend_test_database_url)
    app = create_app()
    payload = {
        "sdk_version": "0.1.0",
        "events": [
            {
                "type": "request",
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/users/{id}",
                "status_code": 200,
                "latency_ms": 42.3,
                "request_id": "req-1",
            }
        ],
    }
    with TestClient(app) as client:
        response = client.post("/ingest", json=payload, headers={"Authorization": f"Bearer {key}"})
    assert response.status_code == 200
    assert response.json() == {"accepted": 1}
    rows = _query_event_rows(backend_test_database_url)
    assert len(rows) == 1
    assert rows[0]["project_id"] == project_id
    assert rows[0]["sdk_version"] == "0.1.0"
    assert rows[0]["type"] == "request"
    assert rows[0]["status_code"] == 200
    assert rows[0]["request_id"] == "req-1"


def test_ingest_rejects_invalid_batch_all_or_nothing(backend_test_database_url: str) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url)
    app = create_app()
    payload = {
        "events": [
            {
                "type": "request",
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/ok",
                "status_code": 200,
                "latency_ms": 10.1,
            },
            {
                "type": "request",
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/broken",
                "status_code": "bad",
                "latency_ms": 11.1,
            },
        ]
    }
    with TestClient(app) as client:
        response = client.post("/ingest", json=payload, headers={"Authorization": f"Bearer {key}"})
    assert response.status_code == 422
    assert _count_events(backend_test_database_url) == 0


def test_ingest_rejects_payload_larger_than_configured_limit(
    backend_test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("INGEST_MAX_REQUEST_BYTES", "64")
    app = create_app()
    payload = {
        "sdk_version": "0.1.0",
        "events": [
            {
                "type": "request",
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/users/{id}",
                "status_code": 200,
                "latency_ms": 42.3,
                "request_id": "req-too-large",
            }
        ],
    }
    with TestClient(app) as client:
        response = client.post("/ingest", json=payload, headers={"Authorization": f"Bearer {key}"})
    assert response.status_code == 413
    assert response.json() == {"detail": "Ingest payload exceeds max request size (64 bytes)."}
    assert _count_events(backend_test_database_url) == 0


def test_ingest_rejects_batch_larger_than_configured_event_limit(
    backend_test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("INGEST_MAX_EVENTS_PER_BATCH", "2")
    app = create_app()
    now = datetime.now(tz=UTC).isoformat()
    payload = {
        "events": [
            {
                "type": "request",
                "timestamp": now,
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/batch-limit/1",
                "status_code": 200,
                "latency_ms": 8.0,
            },
            {
                "type": "request",
                "timestamp": now,
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/batch-limit/2",
                "status_code": 200,
                "latency_ms": 9.0,
            },
            {
                "type": "request",
                "timestamp": now,
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/batch-limit/3",
                "status_code": 200,
                "latency_ms": 10.0,
            },
        ]
    }
    with TestClient(app) as client:
        response = client.post("/ingest", json=payload, headers={"Authorization": f"Bearer {key}"})
    assert response.status_code == 413
    assert response.json() == {"detail": "Ingest batch exceeds max event count (2 events)."}
    assert _count_events(backend_test_database_url) == 0


def test_ingest_rate_limit_returns_429_with_retry_after(
    backend_test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("INGEST_RATE_LIMIT_REQUESTS_PER_WINDOW", "2")
    monkeypatch.setenv("INGEST_RATE_LIMIT_WINDOW_SECONDS", "60")
    app = create_app()
    payload = {
        "events": [
            {
                "type": "request",
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/rate-limit",
                "status_code": 200,
                "latency_ms": 12.5,
            }
        ]
    }
    headers = {"Authorization": f"Bearer {key}"}
    with TestClient(app) as client:
        first = client.post("/ingest", json=payload, headers=headers)
        second = client.post("/ingest", json=payload, headers=headers)
        third = client.post("/ingest", json=payload, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.headers.get("retry-after") == "60"
    assert third.json() == {"detail": "Ingest rate limit exceeded. Try again in 60 seconds."}
    assert _count_events(backend_test_database_url) == 2


def test_ingest_rejects_non_https_when_required(
    backend_test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("INGEST_REQUIRE_HTTPS", "true")
    monkeypatch.setenv("INGEST_TRUST_FORWARDED_PROTO", "false")
    app = create_app()
    payload = {
        "events": [
            {
                "type": "request",
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/secure-ingest",
                "status_code": 200,
                "latency_ms": 10.0,
            }
        ]
    }
    with TestClient(app) as client:
        response = client.post("/ingest", json=payload, headers={"Authorization": f"Bearer {key}"})
    assert response.status_code == 400
    assert response.json() == {"detail": "HTTPS is required for ingest requests."}
    assert _count_events(backend_test_database_url) == 0


def test_ingest_accepts_forwarded_https_when_required(
    backend_test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("INGEST_REQUIRE_HTTPS", "true")
    monkeypatch.setenv("INGEST_TRUST_FORWARDED_PROTO", "true")
    app = create_app()
    payload = {
        "events": [
            {
                "type": "request",
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/secure-ingest",
                "status_code": 200,
                "latency_ms": 10.0,
            }
        ]
    }
    headers = {"Authorization": f"Bearer {key}", "x-forwarded-proto": "https"}
    with TestClient(app) as client:
        response = client.post("/ingest", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"accepted": 1}
    assert _count_events(backend_test_database_url) == 1


def test_ingest_rate_limit_isolated_per_project(
    backend_test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _truncate_tables(backend_test_database_url)
    key_one, _ = _seed_project_and_key(backend_test_database_url)
    key_two, _ = _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("INGEST_RATE_LIMIT_REQUESTS_PER_WINDOW", "2")
    monkeypatch.setenv("INGEST_RATE_LIMIT_WINDOW_SECONDS", "60")
    app = create_app()
    payload = {
        "events": [
            {
                "type": "request",
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/rate-limit",
                "status_code": 200,
                "latency_ms": 12.5,
            }
        ]
    }
    with TestClient(app) as client:
        first = client.post(
            "/ingest",
            json=payload,
            headers={"Authorization": f"Bearer {key_one}"},
        )
        second = client.post(
            "/ingest",
            json=payload,
            headers={"Authorization": f"Bearer {key_one}"},
        )
        blocked = client.post(
            "/ingest",
            json=payload,
            headers={"Authorization": f"Bearer {key_one}"},
        )
        allowed_other_project = client.post(
            "/ingest", json=payload, headers={"Authorization": f"Bearer {key_two}"}
        )
    assert first.status_code == 200
    assert second.status_code == 200
    assert blocked.status_code == 429
    assert allowed_other_project.status_code == 200


def test_internal_metrics_tracks_ingest_counters(
    backend_test_database_url: str,
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url)
    app = create_app()
    payload = {
        "events": [
            {
                "type": "request",
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/metrics",
                "status_code": 200,
                "latency_ms": 8.5,
            }
        ]
    }
    with TestClient(app) as client:
        accepted = client.post("/ingest", json=payload, headers={"Authorization": f"Bearer {key}"})
        metrics = client.get(
            "/internal/metrics",
            headers={"Authorization": "Bearer test-internal-metrics-token"},
        )
    assert accepted.status_code == 200
    assert metrics.status_code == 200
    counters = metrics.json()["counters"]
    assert counters["ingest.accepted.batches"] >= 1
    assert counters["ingest.accepted.events"] >= 1


def test_prometheus_metrics_endpoint_exposes_ingest_counters(
    backend_test_database_url: str,
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url)
    app = create_app()
    payload = {
        "events": [
            {
                "type": "request",
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/metrics",
                "status_code": 200,
                "latency_ms": 6.0,
            }
        ]
    }
    with TestClient(app) as client:
        ingest = client.post("/ingest", json=payload, headers={"Authorization": f"Bearer {key}"})
        metrics = client.get(
            "/metrics",
            headers={"Authorization": "Bearer test-internal-metrics-token"},
        )
    assert ingest.status_code == 200
    assert metrics.status_code == 200
    assert "autopulse_ingest_accepted_batches" in metrics.text


def test_internal_metrics_requires_bearer_token(backend_test_database_url: str) -> None:
    _truncate_tables(backend_test_database_url)
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/internal/metrics")
    assert response.status_code == 401


def test_ingest_accepts_optional_unknown_event_fields(
    backend_test_database_url: str,
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url)
    app = create_app()
    payload = {
        "sdk_version": "sdk-contract-test",
        "events": [
            {
                "type": "request",
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/contract",
                "status_code": 200,
                "latency_ms": 12.0,
                "extra_client_field": "ignored",
            }
        ],
    }
    with TestClient(app) as client:
        response = client.post("/ingest", json=payload, headers={"Authorization": f"Bearer {key}"})
    assert response.status_code == 200
    assert response.json()["accepted"] == 1


def test_ingest_can_drop_autopulse_internal_traffic_before_db_write(
    backend_test_database_url: str,
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url)
    app = create_app()
    now = datetime.now(tz=UTC).isoformat()
    payload = {
        "events": [
            {
                "type": "request",
                "timestamp": now,
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/autopulse/dashboard/overview",
                "status_code": 200,
                "latency_ms": 10.0,
                "request_id": "internal-1",
            },
            {
                "type": "request",
                "timestamp": now,
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/dashboard/overview",
                "status_code": 200,
                "latency_ms": 10.0,
                "request_id": "internal-2",
            },
            {
                "type": "request",
                "timestamp": now,
                "service_name": "api",
                "environment": "test",
                "method": "POST",
                "path": "/ingest",
                "status_code": 200,
                "latency_ms": 10.0,
                "request_id": "internal-3",
            },
            {
                "type": "request",
                "timestamp": now,
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/orders",
                "status_code": 200,
                "latency_ms": 11.0,
                "request_id": "app-1",
            },
        ]
    }
    with TestClient(app) as client:
        response = client.post("/ingest", json=payload, headers={"Authorization": f"Bearer {key}"})
    assert response.status_code == 200
    assert response.json() == {"accepted": 1}
    assert _count_events(backend_test_database_url) == 1


def test_ingest_idempotency_key_replays_accepted_without_duplicate_events(
    backend_test_database_url: str,
) -> None:
    if "sqlite" in backend_test_database_url.lower():
        pytest.skip(
            "Idempotency completion uses a second DB session while the request session is "
            "still open; SQLite file locking can raise OperationalError in this integration path."
        )
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url)
    app = create_app()
    payload = {
        "events": [
            {
                "type": "request",
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/idem",
                "status_code": 200,
                "latency_ms": 1.0,
            }
        ]
    }
    headers = {"Authorization": f"Bearer {key}", "Idempotency-Key": "idem-integration-1"}
    with TestClient(app) as client:
        first = client.post("/ingest", json=payload, headers=headers)
        second = client.post("/ingest", json=payload, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json() == {"accepted": 1}
    assert _count_events(backend_test_database_url) == 1


def test_ingest_second_error_batch_updates_error_group_aggregates_without_datetime_mismatch(
    backend_test_database_url: str,
) -> None:
    """SQLite can return naive datetimes for TZ columns; deltas from ingest are UTC-aware."""
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url)
    app = create_app()
    base_ts = datetime.now(tz=UTC).replace(microsecond=0)

    def error_batch(ts: datetime) -> dict[str, object]:
        return {
            "events": [
                {
                    "type": "error",
                    "timestamp": ts.isoformat(),
                    "service_name": "api",
                    "environment": "test",
                    "method": "GET",
                    "path": "/boom",
                    "status_code": 500,
                    "latency_ms": 1.0,
                    "exception_type": "RuntimeError",
                    "exception_message": "x",
                }
            ],
        }

    headers = {"Authorization": f"Bearer {key}"}
    with TestClient(app) as client:
        first = client.post("/ingest", json=error_batch(base_ts), headers=headers)
        second = client.post(
            "/ingest", json=error_batch(base_ts + timedelta(seconds=1)), headers=headers
        )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json() == {"accepted": 1}


def test_ingest_distributed_rate_limit_db_error_fails_open_and_increments_metric(
    backend_test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("INGEST_DISTRIBUTED_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("INGEST_RATE_LIMIT_REQUESTS_PER_WINDOW", "50")
    monkeypatch.setenv("INGEST_RATE_LIMIT_WINDOW_SECONDS", "60")
    app = create_app()
    payload = {
        "events": [
            {
                "type": "request",
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/dist-limit-fallback",
                "status_code": 200,
                "latency_ms": 2.0,
            }
        ]
    }
    headers = {"Authorization": f"Bearer {key}"}
    baseline = service_metrics.snapshot().get("ingest.rate_limit.distributed_fallback", 0)
    with (
        patch(
            "autopulse_backend.routes.ingest.allow_distributed_ingest_request",
            side_effect=RuntimeError("simulated db limiter failure"),
        ),
        TestClient(app) as client,
    ):
        response = client.post("/ingest", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"accepted": 1}
    after = service_metrics.snapshot().get("ingest.rate_limit.distributed_fallback", 0)
    assert after == baseline + 1


def test_ingest_accepts_job_event(backend_test_database_url: str) -> None:
    _truncate_tables(backend_test_database_url)
    key, project_id = _seed_project_and_key(backend_test_database_url)
    app = create_app()
    payload = {
        "sdk_version": "0.1.0",
        "events": [
            {
                "type": "job",
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "service_name": "api",
                "environment": "test",
                "method": "JOB",
                "path": "digest_send",
                "status_code": 500,
                "latency_ms": 120.0,
                "request_id": "http-req-xyz",
                "exception_message": "SMTP down",
            }
        ],
    }
    with TestClient(app) as client:
        response = client.post("/ingest", json=payload, headers={"Authorization": f"Bearer {key}"})
    assert response.status_code == 200
    rows = _query_event_rows(backend_test_database_url)
    assert len(rows) == 1
    assert rows[0]["type"] == "job"
    assert rows[0]["project_id"] == project_id
    assert rows[0]["status_code"] == 500


def test_ingest_rejects_job_with_invalid_method(backend_test_database_url: str) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url)
    app = create_app()
    payload = {
        "events": [
            {
                "type": "job",
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "bad_job",
                "status_code": 500,
                "latency_ms": 1.0,
            }
        ]
    }
    with TestClient(app) as client:
        response = client.post("/ingest", json=payload, headers={"Authorization": f"Bearer {key}"})
    assert response.status_code == 422
    assert _count_events(backend_test_database_url) == 0


def test_ingest_otlp_traces_maps_span_context_to_events(backend_test_database_url: str) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url)
    app = create_app()
    otlp_payload = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "checkout-api"}},
                        {"key": "deployment.environment", "value": {"stringValue": "prod"}},
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "fastapi"},
                        "spans": [
                            {
                                "traceId": "0123456789abcdef0123456789abcdef",
                                "spanId": "1111111111111111",
                                "parentSpanId": "0000000000000000",
                                "name": "GET /checkout",
                                "kind": 2,
                                "startTimeUnixNano": "1715000000000000000",
                                "endTimeUnixNano": "1715000000500000000",
                                "attributes": [
                                    {"key": "http.method", "value": {"stringValue": "GET"}},
                                    {"key": "http.route", "value": {"stringValue": "/checkout"}},
                                    {"key": "http.status_code", "value": {"intValue": "503"}},
                                ],
                                "status": {"code": 2, "message": "upstream timeout"},
                            }
                        ],
                    }
                ],
            }
        ]
    }
    with TestClient(app) as client:
        response = client.post(
            "/otlp/v1/traces",
            json=otlp_payload,
            headers={"Authorization": f"Bearer {key}"},
        )
    assert response.status_code == 200
    assert response.json() == {"accepted": 1}
    latest = _query_latest_payload(backend_test_database_url)
    assert latest is not None
    assert latest.get("trace_id") == "0123456789abcdef0123456789abcdef"
    assert latest.get("span_id") == "1111111111111111"
    assert latest.get("span_name") == "GET /checkout"
