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
    client: TestClient,
    key: str,
    timestamp: datetime,
    status_code: int,
    method: str,
    path: str,
    *,
    event_type: str | None = None,
    payload_overrides: dict[str, object] | None = None,
) -> None:
    resolved_type = event_type or ("error" if status_code >= 500 else "request")
    event_payload: dict[str, object] = {
        "type": resolved_type,
        "timestamp": timestamp.isoformat(),
        "service_name": "api",
        "environment": "test",
        "method": method,
        "path": path,
        "status_code": status_code,
        "latency_ms": 20.0 + status_code / 100.0,
        "request_id": f"req-{status_code}-{path}",
    }
    if payload_overrides:
        event_payload.update(payload_overrides)
    payload = {
        "sdk_version": "0.1.0",
        "events": [event_payload],
    }
    response = client.post("/ingest", json=payload, headers={"Authorization": f"Bearer {key}"})
    assert response.status_code == 200


def test_dashboard_reads_require_auth(backend_test_database_url: str) -> None:
    _truncate_tables(backend_test_database_url)
    app = create_app()
    with TestClient(app) as client:
        overview_response = client.get("/dashboard/overview")
        requests_response = client.get("/dashboard/requests")
        error_groups_response = client.get("/dashboard/error-groups")
        alert_settings_response = client.get("/dashboard/alert-settings")
    assert overview_response.status_code == 401
    assert requests_response.status_code == 401
    assert error_groups_response.status_code == 401
    assert alert_settings_response.status_code == 401


def test_dashboard_preflight_returns_cors_headers(backend_test_database_url: str) -> None:
    _truncate_tables(backend_test_database_url)
    app = create_app()
    with TestClient(app) as client:
        preflight = client.options(
            "/dashboard/overview",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
    assert preflight.status_code == 200
    assert preflight.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "authorization" in preflight.headers.get("access-control-allow-headers", "").lower()


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
    assert "server_now" in payload
    assert payload["request_count"] == 2
    assert payload["error_count"] == 1
    assert payload["error_rate"] == 0.5
    assert payload["avg_latency_ms"] > 0
    assert payload["requests_per_minute"] > 0
    assert len(payload["series"]) >= 2


def test_dashboard_overview_series_aggregates_per_minute(backend_test_database_url: str) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Project Series")
    base_time = datetime.now(tz=UTC).replace(second=0, microsecond=0) - timedelta(minutes=10)

    app = create_app()
    with TestClient(app) as client:
        _ingest(client, key, base_time, 200, "GET", "/ok")
        _ingest(client, key, base_time + timedelta(seconds=20), 500, "GET", "/fail")
        _ingest(client, key, base_time + timedelta(minutes=1), 200, "GET", "/ok2")

        response = client.get(
            "/dashboard/overview",
            params={
                "from_timestamp": (base_time - timedelta(seconds=10)).isoformat(),
                "to_timestamp": (base_time + timedelta(minutes=2)).isoformat(),
            },
            headers={"Authorization": f"Bearer {key}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert "server_now" in payload
    assert payload["request_count"] == 3
    assert payload["error_count"] == 1
    series_by_minute = {entry["minute"]: entry for entry in payload["series"]}
    first_minute = base_time.isoformat()
    second_minute = (base_time + timedelta(minutes=1)).isoformat()

    assert first_minute in series_by_minute
    assert second_minute in series_by_minute
    assert series_by_minute[first_minute]["request_count"] == 2
    assert series_by_minute[first_minute]["error_count"] == 1
    assert series_by_minute[first_minute]["avg_latency_ms"] > 0
    assert series_by_minute[second_minute]["request_count"] == 1
    assert series_by_minute[second_minute]["error_count"] == 0


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
    assert "server_now" in payload
    assert payload["total"] == 2
    assert payload["limit"] == 1
    assert payload["offset"] == 0
    assert len(payload["items"]) == 1
    assert payload["items"][0]["method"] == "POST"
    assert payload["items"][0]["status_code"] >= 500


def test_dashboard_requests_support_latency_path_and_tag_filters(
    backend_test_database_url: str,
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Project Rich Filters")
    base_time = datetime.now(tz=UTC) - timedelta(minutes=20)
    app = create_app()

    with TestClient(app) as client:
        _ingest(
            client,
            key,
            base_time,
            200,
            "GET",
            "/checkout",
            payload_overrides={
                "latency_ms": 80.0,
                "service_name": "api",
                "environment": "prod",
            },
        )
        _ingest(
            client,
            key,
            base_time + timedelta(minutes=1),
            500,
            "GET",
            "/checkout",
            payload_overrides={
                "latency_ms": 420.0,
                "service_name": "api",
                "environment": "prod",
            },
        )
        _ingest(
            client,
            key,
            base_time + timedelta(minutes=2),
            200,
            "GET",
            "/health",
            payload_overrides={
                "latency_ms": 20.0,
                "service_name": "worker",
                "environment": "dev",
            },
        )

        filtered = client.get(
            "/dashboard/requests",
            params={
                "from_timestamp": (base_time - timedelta(minutes=1)).isoformat(),
                "to_timestamp": (base_time + timedelta(minutes=10)).isoformat(),
                "path_contains": "check",
                "environments": "prod",
                "services": "api",
                "min_latency_ms": 100,
                "max_latency_ms": 500,
                "limit": 50,
                "offset": 0,
            },
            headers={"Authorization": f"Bearer {key}"},
        )

    assert filtered.status_code == 200
    payload = filtered.json()
    assert payload["total"] == 1
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["path"] == "/checkout"
    assert item["status_code"] == 500
    assert item["service_name"] == "api"
    assert item["environment"] == "prod"


def test_dashboard_error_groups_merge_hashes_and_scope_by_project(
    backend_test_database_url: str,
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Project Errors")
    other_key, _ = _seed_project_and_key(backend_test_database_url, "Other Project")
    base_time = datetime.now(tz=UTC).replace(second=0, microsecond=0) - timedelta(minutes=5)
    shared_hash = "hash-shared"

    app = create_app()
    with TestClient(app) as client:
        _ingest(
            client,
            key,
            base_time,
            500,
            "GET",
            "/boom",
            event_type="error",
            payload_overrides={
                "error_hash": shared_hash,
                "exception_type": "ValueError",
                "exception_message": "boom",
                "stack_trace": "trace-a",
            },
        )
        _ingest(
            client,
            key,
            base_time + timedelta(minutes=1),
            500,
            "GET",
            "/boom",
            event_type="error",
            payload_overrides={
                "error_hash": shared_hash,
                "exception_type": "ValueError",
                "exception_message": "boom",
                "stack_trace": "trace-b",
            },
        )
        _ingest(
            client,
            key,
            base_time + timedelta(minutes=2),
            500,
            "GET",
            "/boom-alt",
            event_type="error",
            payload_overrides={
                "error_hash": "hash-other",
                "exception_type": "RuntimeError",
                "exception_message": "other",
                "stack_trace": "trace-c",
            },
        )
        _ingest(
            client,
            key,
            base_time + timedelta(minutes=3),
            500,
            "GET",
            "/missing-hash",
            event_type="error",
            payload_overrides={
                "exception_type": "KeyError",
                "exception_message": "missing",
                "stack_trace": "trace-d",
            },
        )
        _ingest(
            client,
            other_key,
            base_time + timedelta(minutes=4),
            500,
            "GET",
            "/boom",
            event_type="error",
            payload_overrides={
                "error_hash": shared_hash,
                "exception_type": "ValueError",
                "exception_message": "foreign",
                "stack_trace": "trace-other-project",
            },
        )

        response = client.get(
            "/dashboard/error-groups",
            params={
                "from_timestamp": (base_time - timedelta(minutes=1)).isoformat(),
                "to_timestamp": (base_time + timedelta(minutes=6)).isoformat(),
            },
            headers={"Authorization": f"Bearer {key}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert "server_now" in payload
    assert payload["total"] == 3
    assert len(payload["items"]) == 3

    by_key = {item["group_key"]: item for item in payload["items"]}
    assert shared_hash in by_key
    assert by_key[shared_hash]["count"] == 2
    assert by_key[shared_hash]["exception_type"] == "ValueError"
    assert by_key[shared_hash]["message"] == "boom"
    assert by_key[shared_hash]["path"] == "/boom"
    assert by_key[shared_hash]["sample_stack_trace"] in {"trace-a", "trace-b"}

    other_group = by_key["hash-other"]
    assert other_group["count"] == 1
    assert other_group["exception_type"] == "RuntimeError"
    assert other_group["path"] == "/boom-alt"

    synthetic_groups = [
        item for item in payload["items"] if item["group_key"] not in {shared_hash, "hash-other"}
    ]
    assert len(synthetic_groups) == 1
    assert synthetic_groups[0]["count"] == 1
    assert synthetic_groups[0]["path"] == "/missing-hash"
    assert synthetic_groups[0]["exception_type"] == "KeyError"


def test_dashboard_error_groups_http_fallback_when_no_exception_payload(
    backend_test_database_url: str,
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Sparse errors")
    base_time = datetime.now(tz=UTC) - timedelta(minutes=2)
    app = create_app()
    with TestClient(app) as client:
        _ingest(client, key, base_time, 503, "GET", "/legacy-ingest-shape")
        response = client.get(
            "/dashboard/error-groups",
            params={
                "from_timestamp": (base_time - timedelta(minutes=1)).isoformat(),
                "to_timestamp": (base_time + timedelta(minutes=5)).isoformat(),
            },
            headers={"Authorization": f"Bearer {key}"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    item = payload["items"][0]
    assert item["exception_type"] == "HTTP 503"
    assert "/legacy-ingest-shape" in item["message"]
    assert item["sample_stack_trace"] is None


def test_dashboard_alert_settings_read_and_update(backend_test_database_url: str) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Project Alerts Config")
    app = create_app()
    headers = {"Authorization": f"Bearer {key}"}
    with TestClient(app) as client:
        read_response = client.get("/dashboard/alert-settings", headers=headers)
        assert read_response.status_code == 200
        current = read_response.json()
        assert current["enabled"] is True
        assert current["error_spike_ratio_threshold"] == 0.4
        assert current["error_spike_min_requests"] == 20
        assert current["outage_min_requests"] == 10
        assert current["cooldown_minutes"] == 15

        update_payload = {
            "enabled": False,
            "destination_email": "team@example.com",
            "error_spike_ratio_threshold": 0.6,
            "error_spike_min_requests": 35,
            "error_spike_window_minutes": 7,
            "outage_min_requests": 18,
            "outage_window_minutes": 9,
            "cooldown_minutes": 20,
        }
        update_response = client.put(
            "/dashboard/alert-settings",
            json=update_payload,
            headers=headers,
        )
        assert update_response.status_code == 200
        assert update_response.json() == update_payload

        verify_response = client.get("/dashboard/alert-settings", headers=headers)
        assert verify_response.status_code == 200
        assert verify_response.json() == update_payload


def test_dashboard_alert_settings_are_scoped_by_project(backend_test_database_url: str) -> None:
    _truncate_tables(backend_test_database_url)
    key_one, _ = _seed_project_and_key(backend_test_database_url, "Project One")
    key_two, _ = _seed_project_and_key(backend_test_database_url, "Project Two")
    app = create_app()
    with TestClient(app) as client:
        update_response = client.put(
            "/dashboard/alert-settings",
            json={
                "enabled": True,
                "destination_email": "project-one@example.com",
                "error_spike_ratio_threshold": 0.55,
                "error_spike_min_requests": 25,
                "error_spike_window_minutes": 6,
                "outage_min_requests": 12,
                "outage_window_minutes": 8,
                "cooldown_minutes": 18,
            },
            headers={"Authorization": f"Bearer {key_one}"},
        )
        assert update_response.status_code == 200

        other_read = client.get(
            "/dashboard/alert-settings",
            headers={"Authorization": f"Bearer {key_two}"},
        )
        assert other_read.status_code == 200
        payload = other_read.json()
        assert payload["destination_email"] is None
        assert payload["error_spike_ratio_threshold"] == 0.4
