from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from autopulse_backend.app import create_app
from autopulse_backend.auth import generate_api_key
from autopulse_backend.models import ApiKey, Project


def _seed_project_and_key(database_url: str, project_name: str) -> tuple[str, str]:
    async def run() -> tuple[str, str]:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                project = Project(id=uuid4(), name=project_name)
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


def _ingest(
    client: TestClient, key: str, timestamp: datetime, status_code: int, method: str, path: str
) -> None:
    payload = {
        "sdk_version": "0.1.0",
        "events": [
            {
                "type": "error" if status_code >= 500 else "request",
                "timestamp": timestamp.isoformat(),
                "service_name": "api",
                "environment": "test",
                "method": method,
                "path": path,
                "status_code": status_code,
                "latency_ms": 20.0 + status_code / 100.0,
                "request_id": f"req-{status_code}-{path}",
            }
        ],
    }
    response = client.post("/ingest", json=payload, headers={"Authorization": f"Bearer {key}"})
    assert response.status_code == 200


def test_dashboard_reads_require_auth(backend_test_database_url: str) -> None:
    _truncate_tables(backend_test_database_url)
    app = create_app()
    with TestClient(app) as client:
        overview_response = client.get("/dashboard/overview")
        requests_response = client.get("/dashboard/requests")
    assert overview_response.status_code == 401
    assert requests_response.status_code == 401


def test_dashboard_overview_returns_project_scoped_metrics(backend_test_database_url: str) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Project One")
    other_key, _ = _seed_project_and_key(backend_test_database_url, "Project Two")
    base_time = datetime.now(tz=UTC) - timedelta(minutes=10)

    app = create_app()
    with TestClient(app) as client:
        _ingest(client, key, base_time, 200, "GET", "/ok")
        _ingest(client, key, base_time + timedelta(minutes=1), 500, "GET", "/boom")
        _ingest(client, other_key, base_time + timedelta(minutes=2), 500, "GET", "/other-project")

        response = client.get(
            "/dashboard/overview",
            params={
                "from_timestamp": (base_time - timedelta(minutes=1)).isoformat(),
                "to_timestamp": (base_time + timedelta(minutes=5)).isoformat(),
            },
            headers={"Authorization": f"Bearer {key}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["request_count"] == 2
    assert payload["error_count"] == 1
    assert payload["error_rate"] == 0.5
    assert payload["avg_latency_ms"] > 0
    assert payload["requests_per_minute"] > 0
    assert len(payload["series"]) >= 2


def test_dashboard_requests_support_filters_and_pagination(backend_test_database_url: str) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Project Filters")
    base_time = datetime.now(tz=UTC) - timedelta(minutes=20)
    app = create_app()

    with TestClient(app) as client:
        _ingest(client, key, base_time, 200, "GET", "/a")
        _ingest(client, key, base_time + timedelta(minutes=1), 502, "POST", "/b")
        _ingest(client, key, base_time + timedelta(minutes=2), 503, "POST", "/c")

        filtered = client.get(
            "/dashboard/requests",
            params={
                "from_timestamp": (base_time - timedelta(minutes=1)).isoformat(),
                "to_timestamp": (base_time + timedelta(minutes=10)).isoformat(),
                "method": "POST",
                "status_class": 5,
                "limit": 1,
                "offset": 0,
            },
            headers={"Authorization": f"Bearer {key}"},
        )

    assert filtered.status_code == 200
    payload = filtered.json()
    assert payload["total"] == 2
    assert payload["limit"] == 1
    assert payload["offset"] == 0
    assert len(payload["items"]) == 1
    assert payload["items"][0]["method"] == "POST"
    assert payload["items"][0]["status_code"] >= 500
