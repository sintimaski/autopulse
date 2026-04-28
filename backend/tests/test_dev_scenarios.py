from __future__ import annotations

import asyncio
from uuid import uuid4

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
                project = Project(id=uuid4(), name="Scenario Test Project")
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
                return key_value, str(project.id)
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
                    text(
                        "TRUNCATE TABLE error_group_aggregates, metric_buckets, events, "
                        "api_keys, projects RESTART IDENTITY CASCADE"
                    )
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_dev_scenarios_router_is_disabled_by_default(backend_test_database_url: str) -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/dev/scenarios/ok")
    assert response.status_code == 404


def test_dev_scenarios_status_endpoints_when_enabled(
    backend_test_database_url: str,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DEV_SCENARIOS_ENABLED", "1")
    app = create_app()
    with TestClient(app) as client:
        ok = client.get("/dev/scenarios/ok")
        client_error = client.get("/dev/scenarios/client-error")
        server_error = client.get("/dev/scenarios/server-error")
        slow = client.get("/dev/scenarios/slow", params={"delay_ms": "5"})
    assert ok.status_code == 200
    assert ok.json()["status"] == "ok"
    assert client_error.status_code == 400
    assert server_error.status_code == 500
    assert slow.status_code == 200
    assert slow.json()["delay_ms"] == 5


def test_dev_traffic_requires_api_key(
    backend_test_database_url: str,
    monkeypatch,
) -> None:
    _truncate_tables(backend_test_database_url)
    monkeypatch.setenv("DEV_SCENARIOS_ENABLED", "1")
    app = create_app()
    payload = {
        "duration_seconds": 8,
        "base_rate_per_second": 2.0,
        "seed": 7,
    }
    with TestClient(app) as client:
        response = client.post("/dev/scenarios/traffic", json=payload)
    assert response.status_code == 401
    assert _count_events(backend_test_database_url) == 0


def test_dev_traffic_generates_and_persists_capped_events(
    backend_test_database_url: str,
    monkeypatch,
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("DEV_SCENARIOS_ENABLED", "1")
    monkeypatch.setenv("DEV_SCENARIOS_MAX_EVENTS", "30")
    app = create_app()
    payload = {
        "duration_seconds": 40,
        "base_rate_per_second": 20.0,
        "spike_chance": 0.5,
        "spike_multiplier": 3.0,
        "error_burst_chance": 0.2,
        "service_names": "api,worker",
        "environments": "dev,staging",
        "seed": 42,
    }
    with TestClient(app) as client:
        response = client.post(
            "/dev/scenarios/traffic",
            json=payload,
            headers={"Authorization": f"Bearer {key}"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] > 0
    assert body["accepted"] <= 30
    assert body["generated"] == body["accepted"]
    assert body["reached_event_cap"] is True
    assert _count_events(backend_test_database_url) == body["accepted"]
