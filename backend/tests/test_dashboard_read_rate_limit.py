from __future__ import annotations

import asyncio
from uuid import uuid4

from db_reset import truncate_ingest_core_tables as _truncate_tables
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from lumonox_backend.app import create_app
from lumonox_backend.auth import generate_api_key
from lumonox_backend.models import ApiKey, Project


def _seed_project_and_key(database_url: str) -> str:
    async def run() -> str:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                project = Project(id=uuid4(), name="Dashboard Project")
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
                return key_value
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_dashboard_query_bundle_rate_limit_returns_429_with_retry_after(
    backend_test_database_url: str, monkeypatch
) -> None:
    _truncate_tables(backend_test_database_url)
    key = _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK", "true")
    monkeypatch.setenv("DASHBOARD_READ_RATE_LIMIT_REQUESTS_PER_WINDOW", "2")
    monkeypatch.setenv("DASHBOARD_READ_RATE_LIMIT_WINDOW_SECONDS", "60")
    app = create_app()
    headers = {"Authorization": f"Bearer {key}"}
    payload = {"scope": {}}
    with TestClient(app) as client:
        first = client.post("/dashboard/query", json=payload, headers=headers)
        second = client.post("/dashboard/query", json=payload, headers=headers)
        third = client.post("/dashboard/query", json=payload, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.headers.get("retry-after") == "60"


def test_dashboard_query_explorer_rate_limit_returns_429_with_retry_after(
    backend_test_database_url: str, monkeypatch
) -> None:
    _truncate_tables(backend_test_database_url)
    key = _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK", "true")
    monkeypatch.setenv("DASHBOARD_READ_RATE_LIMIT_REQUESTS_PER_WINDOW", "2")
    monkeypatch.setenv("DASHBOARD_READ_RATE_LIMIT_WINDOW_SECONDS", "60")
    app = create_app()
    headers = {"Authorization": f"Bearer {key}"}
    payload = {"query": "SELECT path FROM scoped_events LIMIT 1", "row_limit": 10}
    with TestClient(app) as client:
        first = client.post("/dashboard/query-explorer/execute", json=payload, headers=headers)
        second = client.post("/dashboard/query-explorer/execute", json=payload, headers=headers)
        third = client.post("/dashboard/query-explorer/execute", json=payload, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.headers.get("retry-after") == "60"
