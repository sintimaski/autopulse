from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from db_reset import truncate_ingest_core_tables as _truncate_tables
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from lumonox_backend.app import create_app
from lumonox_backend.auth import generate_api_key
from lumonox_backend.models import ApiKey, Project


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
                return key_value, str(project.id)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _query_sdk_versions(database_url: str) -> list[str]:
    async def run() -> list[str]:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                result = await session.execute(text("SELECT sdk_version FROM events ORDER BY id"))
                return [str(version) for version in result.scalars().all()]
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _ingest_event(
    client: TestClient,
    key: str,
    *,
    timestamp: datetime,
    method: str = "GET",
    path: str = "/route",
    status_code: int = 200,
    event_type: str | None = None,
    sdk_version: str | None = "0.1.0",
) -> None:
    payload: dict[str, object] = {
        "events": [
            {
                "type": event_type or ("error" if status_code >= 500 else "request"),
                "timestamp": timestamp.isoformat(),
                "service_name": "api",
                "environment": "test",
                "method": method,
                "path": path,
                "status_code": status_code,
                "latency_ms": 25.0 + status_code / 50.0,
                "request_id": f"req-{method}-{status_code}-{path}",
            }
        ]
    }
    if sdk_version is not None:
        payload["sdk_version"] = sdk_version
    response = client.post("/ingest", json=payload, headers={"Authorization": f"Bearer {key}"})
    assert response.status_code == 200
    assert response.json() == {"accepted": 1}


def test_end_to_end_ingest_then_dashboard_reads(backend_test_database_url: str) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Integration Project")
    start = datetime.now(tz=UTC) - timedelta(minutes=6)
    app = create_app()

    with TestClient(app) as client:
        _ingest_event(client, key, timestamp=start, method="GET", path="/health", status_code=200)
        _ingest_event(
            client,
            key,
            timestamp=start + timedelta(minutes=1),
            method="POST",
            path="/users",
            status_code=503,
        )
        _ingest_event(
            client,
            key,
            timestamp=start + timedelta(minutes=2),
            method="GET",
            path="/users/1",
            status_code=404,
        )

        overview = client.get(
            "/dashboard/overview",
            params={
                "from_timestamp": (start - timedelta(minutes=1)).isoformat(),
                "to_timestamp": (start + timedelta(minutes=3)).isoformat(),
            },
            headers={"Authorization": f"Bearer {key}"},
        )
        requests = client.get(
            "/dashboard/requests",
            params={
                "from_timestamp": (start - timedelta(minutes=1)).isoformat(),
                "to_timestamp": (start + timedelta(minutes=3)).isoformat(),
            },
            headers={"Authorization": f"Bearer {key}"},
        )

    assert overview.status_code == 200
    overview_payload = overview.json()
    assert overview_payload["request_count"] == 3
    assert overview_payload["error_count"] == 1
    assert overview_payload["error_rate"] == 1 / 3
    assert overview_payload["avg_latency_ms"] > 0
    assert len(overview_payload["series"]) == 3

    assert requests.status_code == 200
    requests_payload = requests.json()
    assert requests_payload["total"] == 3
    assert len(requests_payload["items"]) == 3
    assert requests_payload["items"][0]["path"] == "/users/1"
    assert requests_payload["items"][-1]["path"] == "/health"


def test_project_isolation_across_ingest_and_reads(backend_test_database_url: str) -> None:
    _truncate_tables(backend_test_database_url)
    key_a, _ = _seed_project_and_key(backend_test_database_url, "Tenant A")
    key_b, _ = _seed_project_and_key(backend_test_database_url, "Tenant B")
    now = datetime.now(tz=UTC)
    app = create_app()

    with TestClient(app) as client:
        _ingest_event(client, key_a, timestamp=now, path="/tenant-a", status_code=200)
        _ingest_event(client, key_b, timestamp=now, path="/tenant-b", status_code=500)

        response = client.get("/dashboard/requests", headers={"Authorization": f"Bearer {key_a}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["path"] == "/tenant-a"


def test_overview_handles_reversed_time_window(backend_test_database_url: str) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Window Project")
    base = datetime.now(tz=UTC) - timedelta(minutes=4)
    app = create_app()

    with TestClient(app) as client:
        _ingest_event(client, key, timestamp=base, path="/in-window", status_code=200)
        response = client.get(
            "/dashboard/overview",
            params={
                "from_timestamp": (base + timedelta(minutes=2)).isoformat(),
                "to_timestamp": (base - timedelta(minutes=1)).isoformat(),
            },
            headers={"Authorization": f"Bearer {key}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["request_count"] == 1
    assert payload["from_timestamp"] < payload["to_timestamp"]


def test_requests_method_filter_is_case_insensitive(backend_test_database_url: str) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Method Filter Project")
    t0 = datetime.now(tz=UTC) - timedelta(minutes=5)
    app = create_app()

    with TestClient(app) as client:
        _ingest_event(client, key, timestamp=t0, method="POST", path="/post-only", status_code=201)
        _ingest_event(client, key, timestamp=t0, method="GET", path="/get-only", status_code=200)
        response = client.get(
            "/dashboard/requests",
            params={"method": "post"},
            headers={"Authorization": f"Bearer {key}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["method"] == "POST"
    assert payload["items"][0]["path"] == "/post-only"


def test_requests_status_class_filter_and_offset(backend_test_database_url: str) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Pagination Project")
    base = datetime.now(tz=UTC) - timedelta(minutes=3)
    app = create_app()

    with TestClient(app) as client:
        _ingest_event(client, key, timestamp=base, path="/ok", status_code=200)
        _ingest_event(
            client, key, timestamp=base + timedelta(seconds=10), path="/bad-1", status_code=500
        )
        _ingest_event(
            client, key, timestamp=base + timedelta(seconds=20), path="/bad-2", status_code=502
        )
        _ingest_event(
            client, key, timestamp=base + timedelta(seconds=30), path="/bad-3", status_code=503
        )

        response = client.get(
            "/dashboard/requests",
            params={"status_class": 5, "limit": 1, "offset": 1},
            headers={"Authorization": f"Bearer {key}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert payload["limit"] == 1
    assert payload["offset"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["path"] == "/bad-2"


def test_requests_invalid_status_class_validation_error(backend_test_database_url: str) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Validation Project")
    app = create_app()

    with TestClient(app) as client:
        response = client.get(
            "/dashboard/requests",
            params={"status_class": 9},
            headers={"Authorization": f"Bearer {key}"},
        )

    assert response.status_code == 422


def test_empty_window_returns_zero_metrics_and_no_rows(backend_test_database_url: str) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Empty Window Project")
    app = create_app()
    start = datetime.now(tz=UTC) - timedelta(days=7)
    end = start + timedelta(minutes=5)

    with TestClient(app) as client:
        overview = client.get(
            "/dashboard/overview",
            params={"from_timestamp": start.isoformat(), "to_timestamp": end.isoformat()},
            headers={"Authorization": f"Bearer {key}"},
        )
        requests = client.get(
            "/dashboard/requests",
            params={"from_timestamp": start.isoformat(), "to_timestamp": end.isoformat()},
            headers={"Authorization": f"Bearer {key}"},
        )

    assert overview.status_code == 200
    overview_payload = overview.json()
    assert overview_payload["request_count"] == 0
    assert overview_payload["error_count"] == 0
    assert overview_payload["error_rate"] == 0.0
    assert overview_payload["avg_latency_ms"] == 0.0
    assert overview_payload["series"] == []

    assert requests.status_code == 200
    requests_payload = requests.json()
    assert requests_payload["total"] == 0
    assert requests_payload["items"] == []


def test_ingest_uses_default_sdk_version_when_missing(backend_test_database_url: str) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Default SDK Version Project")
    now = datetime.now(tz=UTC)
    app = create_app()

    with TestClient(app) as client:
        _ingest_event(
            client,
            key,
            timestamp=now,
            path="/no-sdk-version",
            status_code=200,
            sdk_version=None,
        )

    versions = _query_sdk_versions(backend_test_database_url)
    assert versions == ["unknown"]
