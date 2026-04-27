from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from autopulse_backend.app import create_app
from autopulse_backend.auth import generate_api_key
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
                        "SELECT project_id::text, sdk_version, type, status_code, request_id "
                        "FROM events ORDER BY id"
                    )
                )
                return [dict(row) for row in result.mappings().all()]
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


def _truncate_tables(database_url: str) -> None:
    async def run() -> None:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                await session.execute(
                    text("TRUNCATE TABLE events, api_keys, projects RESTART IDENTITY CASCADE")
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(run())


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
