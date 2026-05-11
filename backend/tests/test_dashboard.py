from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from db_reset import truncate_ingest_core_tables as _truncate_tables
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.websockets import WebSocketDisconnect

from lumonox_backend.app import create_app
from lumonox_backend.auth import generate_api_key
from lumonox_backend.metrics import JobExecutionTelemetry, service_metrics
from lumonox_backend.models import (
    AlertDispatch,
    ApiKey,
    IngestAggregateDeadLetter,
    IngestSqlTailRepairItem,
    Project,
)


def _utc_json_minute(dt: datetime) -> str:
    """Match dashboard JSON ``minute`` keys (UTC with ``Z`` suffix from SQLite/JSON encoding)."""
    return dt.astimezone(UTC).replace(second=0, microsecond=0).isoformat().replace("+00:00", "Z")


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
                await session.flush()
                session.add(api_key)
                await session.commit()
                return (key_value, str(project.id))
        finally:
            await engine.dispose()

    return asyncio.run(run())


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
        system_diagnostics_response = client.get("/dashboard/system-diagnostics")
    assert overview_response.status_code == 401
    assert requests_response.status_code == 401
    assert error_groups_response.status_code == 401
    assert alert_settings_response.status_code == 401
    assert system_diagnostics_response.status_code == 401


def test_dashboard_bookmarks_require_cookie_session(backend_test_database_url: str) -> None:
    """Bookmarks are per signed-in user; API-key-only dashboard auth must not read them."""
    _truncate_tables(backend_test_database_url)
    key, _project_id = _seed_project_and_key(backend_test_database_url, "bookmark-auth-test")
    app = create_app()
    with TestClient(app) as client:
        bookmarks = client.get(
            "/dashboard/bookmarks",
            headers={"Authorization": f"Bearer {key}"},
        )
        create = client.post(
            "/dashboard/bookmarks",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "title": "Test",
                "pathname": "/requests",
                "query_string": "window_minutes=60",
                "hash_fragment": "request-row:abc",
            },
        )
    assert bookmarks.status_code == 401
    assert create.status_code == 401


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


def test_dashboard_widgets_returns_custom_widget_definitions_and_points(
    backend_test_database_url: str,
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Project Widgets")
    base_time = datetime.now(tz=UTC).replace(second=0, microsecond=0) - timedelta(minutes=5)
    app = create_app()
    with TestClient(app) as client:
        _ingest(
            client,
            key,
            base_time,
            200,
            "GET",
            "/widgets",
            payload_overrides={
                "infrastructure_metrics": {
                    "host_cpu_percent": 35.0,
                    "host_memory_used_percent": 72.4,
                    "process_memory_percent": 3.0,
                    "process_memory_rss_bytes": 157286400.0,
                    "disk_used_percent": 61.2,
                    "network_bytes_recv": 524288000.0,
                    "network_bytes_sent": 104857600.0,
                },
                "dashboard_widgets": {
                    "definitions": [
                        {
                            "widget_id": "queue_depth",
                            "type": "card",
                            "title": "Queue depth",
                            "description": "Current queue size",
                            "order": 10,
                            "config": {"unit": "jobs", "tone": "warning"},
                        },
                        {
                            "widget_id": "latency_hist",
                            "type": "histogram",
                            "title": "Latency distribution",
                            "description": "Latency buckets",
                            "order": 20,
                            "config": {"unit": "req"},
                        },
                    ],
                    "points": [
                        {
                            "widget_id": "queue_depth",
                            "timestamp": base_time.isoformat(),
                            "value": 7.0,
                        },
                        {
                            "widget_id": "latency_hist",
                            "timestamp": base_time.isoformat(),
                            "label": "<50ms",
                            "value": 12.0,
                        },
                    ],
                },
            },
        )
        response = client.get(
            "/dashboard/widgets",
            params={
                "from_timestamp": (base_time - timedelta(minutes=1)).isoformat(),
                "to_timestamp": (base_time + timedelta(minutes=1)).isoformat(),
            },
            headers={"Authorization": f"Bearer {key}"},
        )
    assert response.status_code == 200
    payload = response.json()
    by_id = {item["widget_id"]: item for item in payload["definitions"]}
    assert by_id["queue_depth"]["type"] == "card"
    assert by_id["latency_hist"]["type"] == "histogram"
    assert by_id["infra_host_cpu_percent"]["type"] == "line"
    assert by_id["infra_process_memory_rss_mb"]["type"] == "line"
    points_by_widget: dict[str, list[dict[str, object]]] = {}
    for point in payload["points"]:
        points_by_widget.setdefault(str(point["widget_id"]), []).append(point)
    assert points_by_widget["queue_depth"][0]["value"] == 7.0
    assert points_by_widget["latency_hist"][0]["label"] == "<50ms"
    assert points_by_widget["infra_host_cpu_percent"][0]["value"] == 35.0
    assert points_by_widget["infra_process_memory_rss_mb"][0]["value"] == 150.0
    # 524288000 B = 500 MiB; 104857600 B = 100 MiB (must not be stored as raw bytes).
    assert points_by_widget["infra_network_received_mb"][0]["value"] == 500.0
    assert points_by_widget["infra_network_sent_mb"][0]["value"] == 100.0


def test_dashboard_widgets_include_infrastructure_fallback_when_sdk_payload_missing(
    backend_test_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Project Infra Fallback")
    base_time = datetime.now(tz=UTC).replace(second=0, microsecond=0) - timedelta(minutes=3)

    # Widget point timestamps follow ingest ``received_at`` (~wall clock), not the synthetic
    # event ``base_time``; narrow windows around ``base_time`` would exclude operational rows.
    class _FakeInfraSampler:
        async def sample(self) -> dict[str, float]:
            return {
                "host_cpu_percent": 12.0,
                "host_memory_used_percent": 55.0,
                "host_memory_total_bytes": 8_000_000_000.0,
                "host_memory_used_bytes": 4_000_000_000.0,
                "process_cpu_percent": 3.0,
                "process_memory_percent": 4.5,
                "process_memory_rss_bytes": 200_000_000.0,
                "disk_used_percent": 50.0,
                "disk_total_bytes": 500_000_000_000.0,
                "disk_used_bytes": 250_000_000_000.0,
                "disk_io_read_bytes": 1_048_576.0,
                "disk_io_write_bytes": 2_097_152.0,
                "network_bytes_sent": 10_485_760.0,
                "network_bytes_recv": 20_971_520.0,
            }

        def should_persist_fallback_widget_points(self) -> bool:
            return True

        def mark_fallback_widget_points_persisted(self) -> None:
            return None

    monkeypatch.setattr(
        "lumonox_backend.services.ingest_service._infrastructure_sampler",
        _FakeInfraSampler(),
    )
    app = create_app()
    with TestClient(app) as client:
        _ingest(client, key, base_time, 200, "GET", "/health")
        server_now = datetime.now(tz=UTC)
        response = client.get(
            "/dashboard/widgets",
            params={
                "from_timestamp": (base_time - timedelta(minutes=5)).isoformat(),
                "to_timestamp": (server_now + timedelta(minutes=2)).isoformat(),
            },
            headers={"Authorization": f"Bearer {key}"},
        )
    assert response.status_code == 200
    payload = response.json()
    by_id = {item["widget_id"]: item for item in payload["definitions"]}
    assert by_id["infra_host_cpu_percent"]["type"] == "line"
    assert by_id["infra_process_memory_percent"]["type"] == "line"
    assert by_id["infra_disk_io_read_mb"]["type"] == "line"
    assert by_id["infra_dependency_map"]["type"] == "bar"
    assert by_id["infra_cache_hit_miss"]["type"] == "bar"
    assert by_id["infra_db_query_performance"]["type"] == "bar"
    point_widget_ids = {str(point["widget_id"]) for point in payload["points"]}
    assert "infra_host_cpu_percent" in point_widget_ids
    assert "infra_process_memory_percent" in point_widget_ids
    assert "infra_disk_io_read_mb" in point_widget_ids
    assert "infra_dependency_map" in point_widget_ids
    assert "infra_cache_hit_miss" in point_widget_ids
    assert "infra_db_query_performance" in point_widget_ids


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
    first_minute = _utc_json_minute(base_time)
    second_minute = _utc_json_minute(base_time + timedelta(minutes=1))

    assert first_minute in series_by_minute
    assert second_minute in series_by_minute
    assert series_by_minute[first_minute]["request_count"] == 2
    assert series_by_minute[first_minute]["error_count"] == 1
    assert series_by_minute[first_minute]["count_2xx"] == 1
    assert series_by_minute[first_minute]["count_3xx"] == 0
    assert series_by_minute[first_minute]["count_4xx"] == 0
    assert series_by_minute[first_minute]["count_5xx"] == 1
    assert series_by_minute[first_minute]["avg_latency_ms"] > 0
    assert series_by_minute[second_minute]["request_count"] == 1
    assert series_by_minute[second_minute]["error_count"] == 0
    assert series_by_minute[second_minute]["count_2xx"] == 1
    assert series_by_minute[second_minute]["count_3xx"] == 0
    assert series_by_minute[second_minute]["count_4xx"] == 0
    assert series_by_minute[second_minute]["count_5xx"] == 0


def test_dashboard_overview_series_fills_empty_minute_buckets(
    backend_test_database_url: str,
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Project Series Gap Fill")
    base_time = datetime.now(tz=UTC).replace(second=0, microsecond=0) - timedelta(minutes=10)
    app = create_app()
    with TestClient(app) as client:
        _ingest(client, key, base_time, 200, "GET", "/minute-0")
        _ingest(client, key, base_time + timedelta(minutes=2), 500, "GET", "/minute-2")

        response = client.get(
            "/dashboard/overview",
            params={
                "from_timestamp": base_time.isoformat(),
                "to_timestamp": (base_time + timedelta(minutes=2)).isoformat(),
            },
            headers={"Authorization": f"Bearer {key}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["series"]) == 3
    by_minute = {entry["minute"]: entry for entry in payload["series"]}
    gap_minute = _utc_json_minute(base_time + timedelta(minutes=1))
    assert by_minute[gap_minute]["request_count"] == 0
    assert by_minute[gap_minute]["error_count"] == 0
    assert by_minute[gap_minute]["avg_latency_ms"] == 0.0
    assert by_minute[gap_minute]["count_2xx"] == 0
    assert by_minute[gap_minute]["count_3xx"] == 0
    assert by_minute[gap_minute]["count_4xx"] == 0
    assert by_minute[gap_minute]["count_5xx"] == 0


def test_dashboard_requests_include_log_message_for_error_events(
    backend_test_database_url: str,
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Project Log Msg")
    base_time = datetime.now(tz=UTC) - timedelta(minutes=5)
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
                "exception_type": "RuntimeError",
                "exception_message": "something failed",
            },
        )
        response = client.get(
            "/dashboard/requests",
            params={
                "from_timestamp": (base_time - timedelta(minutes=1)).isoformat(),
                "to_timestamp": (base_time + timedelta(minutes=10)).isoformat(),
            },
            headers={"Authorization": f"Bearer {key}"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["log_message"] == "something failed"


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


def test_dashboard_requests_focus_errors_matches_status_class_five(
    backend_test_database_url: str,
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Project Focus")
    base_time = datetime.now(tz=UTC) - timedelta(minutes=20)
    app = create_app()

    with TestClient(app) as client:
        _ingest(client, key, base_time, 200, "GET", "/a")
        _ingest(client, key, base_time + timedelta(minutes=1), 502, "POST", "/b")
        _ingest(client, key, base_time + timedelta(minutes=2), 404, "GET", "/c")

        via_focus = client.get(
            "/dashboard/requests",
            params={
                "from_timestamp": (base_time - timedelta(minutes=1)).isoformat(),
                "to_timestamp": (base_time + timedelta(minutes=10)).isoformat(),
                "focus": "errors",
            },
            headers={"Authorization": f"Bearer {key}"},
        )
        via_class = client.get(
            "/dashboard/requests",
            params={
                "from_timestamp": (base_time - timedelta(minutes=1)).isoformat(),
                "to_timestamp": (base_time + timedelta(minutes=10)).isoformat(),
                "status_class": 5,
            },
            headers={"Authorization": f"Bearer {key}"},
        )

    assert via_focus.status_code == 200
    assert via_class.status_code == 200
    assert via_focus.json()["total"] == via_class.json()["total"] == 1
    assert via_focus.json()["items"][0]["path"] == "/b"


def test_dashboard_requests_explicit_status_class_beats_focus_errors(
    backend_test_database_url: str,
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Project Focus Override")
    base_time = datetime.now(tz=UTC) - timedelta(minutes=20)
    app = create_app()

    with TestClient(app) as client:
        _ingest(client, key, base_time, 404, "GET", "/nf")
        _ingest(client, key, base_time + timedelta(minutes=1), 502, "POST", "/err")

        response = client.get(
            "/dashboard/requests",
            params={
                "from_timestamp": (base_time - timedelta(minutes=1)).isoformat(),
                "to_timestamp": (base_time + timedelta(minutes=10)).isoformat(),
                "focus": "errors",
                "status_class": 4,
            },
            headers={"Authorization": f"Bearer {key}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["path"] == "/nf"


def test_dashboard_requests_event_sql_filter_scopes_results(backend_test_database_url: str) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Project SQL Filter")
    base_time = datetime.now(tz=UTC) - timedelta(minutes=5)
    app = create_app()

    with TestClient(app) as client:
        _ingest(client, key, base_time, 200, "GET", "/ok")
        _ingest(client, key, base_time + timedelta(seconds=30), 503, "POST", "/boom")

        filtered = client.get(
            "/dashboard/requests",
            params={
                "from_timestamp": (base_time - timedelta(minutes=1)).isoformat(),
                "to_timestamp": (base_time + timedelta(minutes=10)).isoformat(),
                "event_sql_filter": "status_code >= 500",
            },
            headers={"Authorization": f"Bearer {key}"},
        )

    assert filtered.status_code == 200
    payload = filtered.json()
    assert payload["total"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["path"] == "/boom"


def test_dashboard_requests_event_sql_filter_invalid_returns_422(
    backend_test_database_url: str,
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Project SQL Bad")
    app = create_app()
    with TestClient(app) as client:
        response = client.get(
            "/dashboard/requests",
            params={"event_sql_filter": "unknown_column = 1"},
            headers={"Authorization": f"Bearer {key}"},
        )
    assert response.status_code == 422


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
    boom_key = f"{shared_hash}\x1e/boom"
    assert boom_key in by_key
    assert by_key[boom_key]["count"] == 2
    assert by_key[boom_key]["exception_type"] == "ValueError"
    assert by_key[boom_key]["message"] == "boom"
    assert by_key[boom_key]["path"] == "/boom"
    assert by_key[boom_key]["sample_stack_trace"] in {"trace-a", "trace-b"}

    other_key = "hash-other\x1e/boom-alt"
    other_group = by_key[other_key]
    assert other_group["count"] == 1
    assert other_group["exception_type"] == "RuntimeError"
    assert other_group["path"] == "/boom-alt"

    synthetic_groups = [
        item for item in payload["items"] if item["group_key"] not in {boom_key, other_key}
    ]
    assert len(synthetic_groups) == 1
    assert synthetic_groups[0]["count"] == 1
    assert synthetic_groups[0]["path"] == "/missing-hash"
    assert synthetic_groups[0]["exception_type"] == "KeyError"


def test_dashboard_error_groups_split_same_error_hash_by_path(
    backend_test_database_url: str,
) -> None:
    """SDK error_hash omits path; dashboard must still show one row per route."""
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Split By Path")
    base_time = datetime.now(tz=UTC).replace(second=0, microsecond=0) - timedelta(minutes=5)
    shared_hash = "hash-same-across-routes"
    app = create_app()
    with TestClient(app) as client:
        for path in ("/boom", "/orders"):
            _ingest(
                client,
                key,
                base_time,
                500,
                "GET",
                path,
                event_type="error",
                payload_overrides={
                    "error_hash": shared_hash,
                    "exception_type": "ValueError",
                    "exception_message": "boom",
                    "stack_trace": f"trace-{path}",
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
    assert payload["total"] == 2
    paths = {item["path"] for item in payload["items"]}
    assert paths == {"/boom", "/orders"}
    for item in payload["items"]:
        assert item["group_key"] == f"{shared_hash}\x1e{item['path']}"
        assert item["count"] == 1


def test_dashboard_error_groups_dedupes_request_when_paired_error_event_exists(
    backend_test_database_url: str,
) -> None:
    """Paired request+error rows share request_id; only the error row counts for grouping."""
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Paired Request Error")
    base_time = datetime.now(tz=UTC).replace(second=0, microsecond=0) - timedelta(minutes=3)
    rid = "paired-req-1"
    app = create_app()
    with TestClient(app) as client:
        _ingest(
            client,
            key,
            base_time,
            500,
            "GET",
            "/boom",
            event_type="request",
            payload_overrides={"request_id": rid},
        )
        _ingest(
            client,
            key,
            base_time + timedelta(seconds=1),
            500,
            "GET",
            "/boom",
            event_type="error",
            payload_overrides={
                "request_id": rid,
                "error_hash": "dedupe-hash",
                "exception_type": "ValueError",
                "exception_message": "nope",
                "stack_trace": "tb",
            },
        )
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
    assert payload["items"][0]["group_key"].startswith("dedupe-hash")


def test_dashboard_error_groups_includes_request_only_server_errors(
    backend_test_database_url: str,
) -> None:
    """HTTPException 503 may be request-only (no type=error); grouping must still include it."""
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Request Only 5xx")
    base_time = datetime.now(tz=UTC).replace(second=0, microsecond=0) - timedelta(minutes=3)
    app = create_app()
    with TestClient(app) as client:
        _ingest(
            client,
            key,
            base_time,
            503,
            "POST",
            "/orders",
            event_type="request",
            payload_overrides={"request_id": "load-00882-001"},
        )
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
    assert payload["total"] >= 1
    paths = {item["path"] for item in payload["items"]}
    assert "/orders" in paths


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


def test_dashboard_alert_settings_read_and_update(
    backend_test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Project Alerts Config")
    monkeypatch.delenv("DASHBOARD_AUTH_ALLOWED_EMAIL", raising=False)
    monkeypatch.delenv("DASHBOARD_ALLOWED_EMAIL_DOMAINS", raising=False)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK", "1")
    app = create_app()
    headers = {"Authorization": f"Bearer {key}"}
    with TestClient(app) as client:
        read_response = client.get("/dashboard/alert-settings", headers=headers)
        assert read_response.status_code == 200
        current = read_response.json()
        assert current["enabled"] is True
        assert current["email_enabled"] is True
        assert current["slack_enabled"] is False
        assert current["discord_enabled"] is False
        assert current["webhook_enabled"] is False
        assert current["error_spike_ratio_threshold"] == 0.4
        assert current["error_spike_min_requests"] == 20
        assert current["outage_min_requests"] == 10
        assert current["cooldown_minutes"] == 15

        update_payload = {
            "enabled": False,
            "destination_email": "team@example.com",
            "email_enabled": True,
            "slack_enabled": True,
            "slack_webhook_url": "https://hooks.slack.test/abc",
            "discord_enabled": True,
            "discord_webhook_url": "https://discord.test/webhooks/1",
            "webhook_enabled": True,
            "webhook_url": "https://example.com/webhook",
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
        assert update_response.status_code == 401

        verify_response = client.get("/dashboard/alert-settings", headers=headers)
        assert verify_response.status_code == 200
        assert verify_response.json() == current


def test_dashboard_alert_settings_are_scoped_by_project(
    backend_test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _truncate_tables(backend_test_database_url)
    key_one, _ = _seed_project_and_key(backend_test_database_url, "Project One")
    key_two, _ = _seed_project_and_key(backend_test_database_url, "Project Two")
    monkeypatch.delenv("DASHBOARD_AUTH_ALLOWED_EMAIL", raising=False)
    monkeypatch.delenv("DASHBOARD_ALLOWED_EMAIL_DOMAINS", raising=False)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK", "1")
    app = create_app()
    with TestClient(app) as client:
        baseline_read = client.get(
            "/dashboard/alert-settings",
            headers={"Authorization": f"Bearer {key_two}"},
        )
        assert baseline_read.status_code == 200
        baseline_payload = baseline_read.json()
        update_response = client.put(
            "/dashboard/alert-settings",
            json={
                "enabled": True,
                "destination_email": "project-one@example.com",
                "email_enabled": True,
                "slack_enabled": False,
                "slack_webhook_url": None,
                "discord_enabled": False,
                "discord_webhook_url": None,
                "webhook_enabled": False,
                "webhook_url": None,
                "error_spike_ratio_threshold": 0.55,
                "error_spike_min_requests": 25,
                "error_spike_window_minutes": 6,
                "outage_min_requests": 12,
                "outage_window_minutes": 8,
                "cooldown_minutes": 18,
            },
            headers={"Authorization": f"Bearer {key_one}"},
        )
        assert update_response.status_code == 401

        other_read = client.get(
            "/dashboard/alert-settings",
            headers={"Authorization": f"Bearer {key_two}"},
        )
        assert other_read.status_code == 200
        payload = other_read.json()
        assert payload == baseline_payload


def test_dashboard_alert_dispatches_include_delivery_status_fields(
    backend_test_database_url: str,
) -> None:
    _truncate_tables(backend_test_database_url)
    key, project_id = _seed_project_and_key(backend_test_database_url, "Project Alerts Dispatches")
    now = datetime.now(tz=UTC).replace(microsecond=0)

    async def seed_dispatch() -> None:
        engine = create_async_engine(backend_test_database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                session.add(
                    AlertDispatch(
                        project_id=UUID(project_id),
                        alert_type="error_spike",
                        destination_email="ops@example.com",
                        delivered_via="email",
                        status="failed",
                        reason_code="provider_rejected",
                        attempt_count=2,
                        triggered_at=now,
                        window_start=now - timedelta(minutes=5),
                        window_end=now,
                        detail={"request_count": 42},
                    )
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(seed_dispatch())
    app = create_app()
    with TestClient(app) as client:
        response = client.get(
            "/dashboard/alert-dispatches",
            params={
                "from_timestamp": (now - timedelta(minutes=10)).isoformat(),
                "to_timestamp": (now + timedelta(minutes=1)).isoformat(),
            },
            headers={"Authorization": f"Bearer {key}"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    item = payload["items"][0]
    assert item["status"] == "failed"
    assert item["reason_code"] == "provider_rejected"
    assert item["reason_message"]
    assert item["attempt_count"] == 2
    assert item["delivered_at"] is None


def test_dashboard_alert_capabilities_reports_active_and_unavailable_channels(
    backend_test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Project Alert Capabilities")
    monkeypatch.setenv("ALERTS_ENABLED", "true")
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("ALERT_SENDER_MODE", "email")
    monkeypatch.setenv("ALERT_DEFAULT_DESTINATION_EMAIL", "ops@example.com")
    monkeypatch.setenv("ALERT_SLACK_WEBHOOK_URL", "https://hooks.example.com/slack")
    monkeypatch.delenv("ALERT_DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)
    app = create_app()
    with TestClient(app) as client:
        response = client.get(
            "/dashboard/alert-capabilities",
            headers={"Authorization": f"Bearer {key}"},
        )
    assert response.status_code == 200
    payload = response.json()
    by_channel = {channel["channel"]: channel for channel in payload["channels"]}
    assert by_channel["email"]["status"] == "active"
    assert by_channel["email"]["enabled"] is True
    assert by_channel["slack"]["status"] == "active"
    assert by_channel["slack"]["enabled"] is True
    assert "enabled and webhook is configured" in by_channel["slack"]["reason"].lower()
    assert by_channel["discord"]["status"] == "planned"
    assert by_channel["webhook"]["status"] == "planned"


def test_dashboard_alert_test_dispatch_records_attempt(
    backend_test_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _truncate_tables(backend_test_database_url)
    key, project_id = _seed_project_and_key(
        backend_test_database_url, "Project Alert Test Dispatch"
    )
    monkeypatch.setenv("ALERTS_ENABLED", "true")
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("ALERT_EMAIL_FILE_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("ALERT_SENDER_MODE", "email")
    monkeypatch.setenv("ALERT_DEFAULT_DESTINATION_EMAIL", "ops@example.com")
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/dashboard/alert-test",
            headers={"Authorization": f"Bearer {key}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "sent"
        assert payload["delivered_via"] in {"email", "file"}
        assert payload["destination_email"] == "ops@example.com"

        dispatches = client.get(
            "/dashboard/alert-dispatches",
            headers={"Authorization": f"Bearer {key}"},
        )
    assert dispatches.status_code == 200
    items = dispatches.json()["items"]
    test_alerts = [item for item in items if item["alert_type"] == "test"]
    assert len(test_alerts) == 1
    assert project_id


def test_dashboard_theme_settings_can_exclude_lumonox_traffic(
    backend_test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Project UI Settings")
    base_time = datetime.now(tz=UTC) - timedelta(minutes=2)
    monkeypatch.setenv("INGEST_DROP_LUMONOX_TRAFFIC_FROM_DB", "false")
    # Do not inherit host .env allowlist-only auth (Bearer ingest key must reach dashboard reads).
    monkeypatch.delenv("DASHBOARD_AUTH_ALLOWED_EMAIL", raising=False)
    monkeypatch.delenv("DASHBOARD_ALLOWED_EMAIL_DOMAINS", raising=False)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK", "1")
    app = create_app()
    headers = {"Authorization": f"Bearer {key}"}
    with TestClient(app) as client:
        read_response = client.get("/dashboard/theme-settings", headers=headers)
        assert read_response.status_code == 200
        initial = read_response.json()
        assert initial["theme_preference"] == "system"
        assert initial["exclude_lumonox_traffic"] is True

        disable_filter = client.put(
            "/dashboard/theme-settings",
            json={
                "theme_preference": "system",
                "exclude_lumonox_traffic": False,
            },
            headers=headers,
        )
        assert disable_filter.status_code == 200
        assert disable_filter.json()["exclude_lumonox_traffic"] is False

        _ingest(client, key, base_time, 200, "GET", "/lumonox/dashboard/overview")
        _ingest(client, key, base_time + timedelta(seconds=10), 200, "GET", "/users/42")
        _ingest(client, key, base_time + timedelta(seconds=11), 200, "GET", "/dashboard/overview")
        _ingest(client, key, base_time + timedelta(seconds=12), 200, "POST", "/ingest")

        overview_all = client.get(
            "/dashboard/overview",
            params={
                "from_timestamp": (base_time - timedelta(minutes=1)).isoformat(),
                "to_timestamp": (base_time + timedelta(minutes=5)).isoformat(),
            },
            headers=headers,
        )
        assert overview_all.status_code == 200
        assert overview_all.json()["request_count"] == 4

        enable_filter = client.put(
            "/dashboard/theme-settings",
            json={
                "theme_preference": "system",
                "exclude_lumonox_traffic": True,
            },
            headers=headers,
        )
        assert enable_filter.status_code == 200
        assert enable_filter.json()["exclude_lumonox_traffic"] is True

        overview_filtered = client.get(
            "/dashboard/overview",
            params={
                "from_timestamp": (base_time - timedelta(minutes=1)).isoformat(),
                "to_timestamp": (base_time + timedelta(minutes=5)).isoformat(),
            },
            headers=headers,
        )
        assert overview_filtered.status_code == 200
        assert overview_filtered.json()["request_count"] == 1


def test_dashboard_event_plane_cutover_toggle_can_enable_and_rollback(
    backend_test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Project Cutover Toggle")
    monkeypatch.delenv("DASHBOARD_AUTH_ALLOWED_EMAIL", raising=False)
    monkeypatch.delenv("DASHBOARD_ALLOWED_EMAIL_DOMAINS", raising=False)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK", "1")
    app = create_app()
    headers = {"Authorization": f"Bearer {key}"}
    with TestClient(app) as client:
        initial = client.get("/dashboard/event-plane-cutover", headers=headers)
        assert initial.status_code == 200
        assert initial.json()["use_snapshot_read"] is False

        enable = client.put(
            "/dashboard/event-plane-cutover",
            json={"use_snapshot_read": True},
            headers=headers,
        )
        assert enable.status_code == 401

        disable = client.put(
            "/dashboard/event-plane-cutover",
            json={"use_snapshot_read": False},
            headers=headers,
        )
        assert disable.status_code == 401


def test_dashboard_event_plane_cutover_enable_blocked_on_parity_mismatch(
    backend_test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Project Cutover Parity Gate")
    monkeypatch.delenv("DASHBOARD_AUTH_ALLOWED_EMAIL", raising=False)
    monkeypatch.delenv("DASHBOARD_ALLOWED_EMAIL_DOMAINS", raising=False)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK", "1")
    monkeypatch.setenv("LUMONOX_EVENT_PLANE_MODE", "duckdb_log_shards")
    monkeypatch.setenv("LUMONOX_EVENT_STORE", "duckdb")
    monkeypatch.setattr(
        "lumonox_backend.dashboard.routes.ui_settings.build_cutover_decision",
        lambda **_: (False, SimpleNamespace(mismatches=[object()])),
    )
    app = create_app()
    headers = {"Authorization": f"Bearer {key}"}
    with TestClient(app) as client:
        response = client.put(
            "/dashboard/event-plane-cutover",
            json={"use_snapshot_read": True},
            headers=headers,
        )
    assert response.status_code == 401


def test_dashboard_internal_metrics_requires_server_token_flag(
    backend_test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Project Internal Metrics Disabled")
    monkeypatch.delenv("INTERNAL_METRICS_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("DASHBOARD_AUTH_ALLOWED_EMAIL", raising=False)
    monkeypatch.delenv("DASHBOARD_ALLOWED_EMAIL_DOMAINS", raising=False)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK", "1")
    app = create_app()
    with TestClient(app) as client:
        response = client.get(
            "/dashboard/internal-metrics",
            headers={"Authorization": f"Bearer {key}"},
        )
    assert response.status_code == 401


def test_dashboard_internal_metrics_returns_snapshot_for_admin_scope(
    backend_test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Project Internal Metrics Enabled")
    monkeypatch.setenv("INTERNAL_METRICS_BEARER_TOKEN", "test-dashboard-internal-metrics")
    monkeypatch.delenv("DASHBOARD_AUTH_ALLOWED_EMAIL", raising=False)
    monkeypatch.delenv("DASHBOARD_ALLOWED_EMAIL_DOMAINS", raising=False)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK", "1")
    app = create_app()
    with TestClient(app) as client:
        response = client.get(
            "/dashboard/internal-metrics",
            headers={"Authorization": f"Bearer {key}"},
        )
    assert response.status_code == 401


def test_dashboard_system_diagnostics_returns_supportability_snapshot(
    backend_test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _truncate_tables(backend_test_database_url)
    key, project_id = _seed_project_and_key(backend_test_database_url, "Project System Diagnostics")
    project_uuid = UUID(project_id)
    monkeypatch.setenv("INTERNAL_METRICS_BEARER_TOKEN", "test-dashboard-internal-metrics")
    monkeypatch.delenv("DASHBOARD_AUTH_ALLOWED_EMAIL", raising=False)
    monkeypatch.delenv("DASHBOARD_ALLOWED_EMAIL_DOMAINS", raising=False)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK", "1")
    monkeypatch.setenv("JOBS_RETENTION_INTERVAL_SECONDS", "120")

    base_time = datetime.now(tz=UTC) - timedelta(minutes=2)
    run_started = datetime.now(tz=UTC).replace(microsecond=0) - timedelta(minutes=1)
    run_finished = run_started + timedelta(seconds=2)
    service_metrics.set_job_last_run(
        JobExecutionTelemetry(
            job_name="retention",
            status="failed",
            started_at=run_started,
            finished_at=run_finished,
            duration_ms=2000,
            records_processed=0,
            failure_reason="RuntimeError",
        )
    )

    async def seed_reliability_rows() -> None:
        engine = create_async_engine(backend_test_database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                session.add(
                    IngestSqlTailRepairItem(
                        project_id=project_uuid,
                        payload={"events": 1},
                        last_error="pending failure",
                        attempt_count=1,
                        next_retry_at=base_time,
                    )
                )
                session.add(
                    IngestSqlTailRepairItem(
                        project_id=project_uuid,
                        payload={"events": 1},
                        last_error="dead-lettered failure",
                        attempt_count=4,
                        next_retry_at=base_time,
                        dead_lettered_at=datetime.now(tz=UTC) - timedelta(seconds=30),
                    )
                )
                session.add(
                    IngestAggregateDeadLetter(
                        payload={"metric_bucket_deltas": []},
                        last_error="aggregate failed",
                    )
                )
                await session.commit()
        finally:
            await engine.dispose()

    app = create_app()
    with TestClient(app) as client:
        _ingest(client, key, base_time, 500, "GET", "/diag")
        asyncio.run(seed_reliability_rows())
        response = client.get(
            "/dashboard/system-diagnostics",
            headers={"Authorization": f"Bearer {key}"},
        )
    assert response.status_code == 401


def test_dashboard_overview_extended_and_diagnosis_endpoints(
    backend_test_database_url: str,
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Project Diagnosis")
    base_time = datetime.now(tz=UTC).replace(second=0, microsecond=0) - timedelta(minutes=8)
    app = create_app()
    headers = {"Authorization": f"Bearer {key}"}
    with TestClient(app) as client:
        _ingest(client, key, base_time, 200, "GET", "/ok")
        _ingest(client, key, base_time + timedelta(minutes=1), 502, "GET", "/checkout")
        _ingest(client, key, base_time + timedelta(minutes=2), 503, "POST", "/checkout")
        _ingest(client, key, base_time + timedelta(minutes=3), 200, "GET", "/users")

        extended = client.get(
            "/dashboard/overview/extended",
            params={
                "from_timestamp": (base_time - timedelta(minutes=1)).isoformat(),
                "to_timestamp": (base_time + timedelta(minutes=5)).isoformat(),
            },
            headers=headers,
        )
        timeline = client.get(
            "/dashboard/diagnosis/timeline",
            params={
                "from_timestamp": (base_time - timedelta(minutes=1)).isoformat(),
                "to_timestamp": (base_time + timedelta(minutes=5)).isoformat(),
            },
            headers=headers,
        )
        failures = client.get(
            "/dashboard/diagnosis/failures-by-route",
            params={
                "from_timestamp": (base_time - timedelta(minutes=1)).isoformat(),
                "to_timestamp": (base_time + timedelta(minutes=5)).isoformat(),
            },
            headers=headers,
        )

    assert extended.status_code == 200
    extended_payload = extended.json()
    assert extended_payload["p95_latency_ms"] > 0
    assert 0.0 <= extended_payload["apdex_score"] <= 1.0
    assert isinstance(extended_payload["active_sessions_estimate"], int)
    assert isinstance(extended_payload["error_type_breakdown"], list)
    assert isinstance(extended_payload["alerts_timeline"], list)
    assert isinstance(extended_payload["service_breakdown"], list)
    assert isinstance(extended_payload["route_breakdown"], list)
    assert timeline.status_code == 200
    assert len(timeline.json()["buckets"]) >= 1
    assert failures.status_code == 200
    assert failures.json()["items"][0]["path"] == "/checkout"


def test_dashboard_diagnosis_timeline_fills_empty_minute_buckets(
    backend_test_database_url: str,
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Project Timeline Gap Fill")
    base_time = datetime.now(tz=UTC).replace(second=0, microsecond=0) - timedelta(minutes=8)
    app = create_app()
    headers = {"Authorization": f"Bearer {key}"}
    with TestClient(app) as client:
        _ingest(client, key, base_time, 200, "GET", "/ok")
        _ingest(client, key, base_time + timedelta(minutes=2), 503, "GET", "/fail")
        response = client.get(
            "/dashboard/diagnosis/timeline",
            params={
                "from_timestamp": base_time.isoformat(),
                "to_timestamp": (base_time + timedelta(minutes=2)).isoformat(),
            },
            headers=headers,
        )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["buckets"]) == 3
    by_minute = {entry["minute"]: entry for entry in payload["buckets"]}
    gap_minute = _utc_json_minute(base_time + timedelta(minutes=1))
    assert by_minute[gap_minute]["request_count"] == 0
    assert by_minute[gap_minute]["error_count"] == 0


def test_dashboard_log_query_validate_execute_and_retention_settings(
    backend_test_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Project Query")
    monkeypatch.delenv("DASHBOARD_AUTH_ALLOWED_EMAIL", raising=False)
    monkeypatch.delenv("DASHBOARD_ALLOWED_EMAIL_DOMAINS", raising=False)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK", "1")
    base_time = datetime.now(tz=UTC) - timedelta(minutes=5)
    app = create_app()
    headers = {"Authorization": f"Bearer {key}"}
    query = "SELECT * FROM events WHERE status_code >= 500 ORDER BY timestamp DESC LIMIT 2"
    with TestClient(app) as client:
        _ingest(client, key, base_time, 200, "GET", "/ok")
        _ingest(client, key, base_time + timedelta(minutes=1), 500, "POST", "/boom")
        _ingest(client, key, base_time + timedelta(minutes=2), 503, "POST", "/boom")
        validate = client.post(
            "/dashboard/log-query/validate",
            json={"query": query},
            headers=headers,
        )
        assert validate.status_code == 200
        assert validate.json()["valid"] is True

        execute = client.post(
            "/dashboard/log-query/execute",
            json={"query": query},
            headers=headers,
        )
        assert execute.status_code == 200
        execute_payload = execute.json()
        assert len(execute_payload["items"]) == 2
        assert "next_cursor" in execute_payload

        retention_read = client.get("/dashboard/retention-settings", headers=headers)
        assert retention_read.status_code == 200
        retention_update = client.put(
            "/dashboard/retention-settings",
            json={"raw_events_days": 7, "logs_query_max_window_minutes": 120},
            headers=headers,
        )
        assert retention_update.status_code == 401


def test_dashboard_log_query_has_no_websocket_stream(
    backend_test_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Log queries are HTTP-only; the old /dashboard/log-query/stream path must not exist."""
    _truncate_tables(backend_test_database_url)
    _seed_project_and_key(backend_test_database_url, "No WS Log Query")
    monkeypatch.delenv("DASHBOARD_AUTH_ALLOWED_EMAIL", raising=False)
    monkeypatch.delenv("DASHBOARD_ALLOWED_EMAIL_DOMAINS", raising=False)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK", "1")
    app = create_app()
    with TestClient(app) as client:
        for path in ("/dashboard/log-query/stream", "/lumonox/dashboard/log-query/stream"):
            with pytest.raises(WebSocketDisconnect) as excinfo, client.websocket_connect(path):
                pass
            # Starlette closes unknown WebSocket routes without accepting (no matching handler).
            assert excinfo.value.code == 1000


def test_dashboard_query_explorer_executes_scoped_sql(
    backend_test_database_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Project Query Explorer")
    monkeypatch.setenv("LUMONOX_EVENT_STORE", "duckdb")
    monkeypatch.setenv("LUMONOX_DUCKDB_PATH", str(tmp_path / "query_explorer_scoped.duckdb"))
    from lumonox_backend.services.event_store import shutdown_duckdb_event_store

    shutdown_duckdb_event_store()
    base_time = datetime.now(tz=UTC) - timedelta(minutes=5)
    app = create_app()
    headers = {"Authorization": f"Bearer {key}"}
    with TestClient(app) as client:
        _ingest(client, key, base_time, 200, "GET", "/orders")
        _ingest(client, key, base_time + timedelta(seconds=10), 503, "GET", "/orders")
        response = client.post(
            "/dashboard/query-explorer/execute",
            json={
                "query": (
                    "SELECT service_name, COUNT(*) AS c "
                    "FROM scoped_events GROUP BY service_name ORDER BY c DESC"
                ),
                "row_limit": 100,
            },
            headers=headers,
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["columns"] == ["service_name", "c"]
    assert len(payload["rows"]) == 1
    assert payload["rows"][0][1] == 2


def test_dashboard_query_explorer_project_wide_counts_outside_time_window(
    backend_test_database_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _truncate_tables(backend_test_database_url)
    key, _ = _seed_project_and_key(backend_test_database_url, "Project Query Explorer Wide")
    monkeypatch.setenv("LUMONOX_EVENT_STORE", "duckdb")
    monkeypatch.setenv("LUMONOX_DUCKDB_PATH", str(tmp_path / "query_explorer_wide.duckdb"))
    from lumonox_backend.services.event_store import shutdown_duckdb_event_store

    shutdown_duckdb_event_store()
    old = datetime.now(tz=UTC) - timedelta(days=40)
    recent = datetime.now(tz=UTC) - timedelta(minutes=5)
    app = create_app()
    headers = {"Authorization": f"Bearer {key}"}
    count_sql = "SELECT COUNT(*)::BIGINT AS c FROM scoped_events"
    with TestClient(app) as client:
        _ingest(client, key, old, 200, "GET", "/old")
        _ingest(client, key, recent, 200, "GET", "/new")
        windowed = client.post(
            "/dashboard/query-explorer/execute",
            json={"query": count_sql, "row_limit": 10, "window_minutes": 60},
            headers=headers,
        )
        wide = client.post(
            "/dashboard/query-explorer/execute",
            json={"query": count_sql, "row_limit": 10, "scope_mode": "project_wide"},
            headers=headers,
        )
    assert windowed.status_code == 200
    assert wide.status_code == 200
    assert windowed.json()["rows"][0][0] == 1
    assert wide.json()["rows"][0][0] == 2


def test_dashboard_traces_search_and_detail(
    backend_test_database_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _truncate_tables(backend_test_database_url)
    key, project_id = _seed_project_and_key(backend_test_database_url, "Project Traces")
    monkeypatch.setenv("LUMONOX_EVENT_STORE", "duckdb")
    monkeypatch.setenv("LUMONOX_DUCKDB_PATH", str(tmp_path / "traces_search.duckdb"))
    from lumonox_backend.services.event_store import shutdown_duckdb_event_store

    shutdown_duckdb_event_store()
    base_time = datetime.now(tz=UTC) - timedelta(minutes=5)
    trace_id = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    app = create_app()
    headers = {"Authorization": f"Bearer {key}"}
    with TestClient(app) as client:
        _ingest(
            client,
            key,
            base_time,
            200,
            "GET",
            "/checkout",
            payload_overrides={
                "trace_id": trace_id,
                "span_id": "1111111111111111",
                "span_name": "GET /checkout",
            },
        )
        _ingest(
            client,
            key,
            base_time + timedelta(milliseconds=300),
            503,
            "GET",
            "/checkout",
            payload_overrides={
                "trace_id": trace_id,
                "span_id": "2222222222222222",
                "parent_span_id": "1111111111111111",
                "span_name": "db.query checkout",
            },
        )
        search = client.get("/dashboard/traces/search", params={"q": "checkout"}, headers=headers)
        detail = client.get(f"/dashboard/traces/{trace_id}", headers=headers)
    assert search.status_code == 200
    search_payload = search.json()
    assert search_payload["total"] >= 1
    assert search_payload.get("project_id") == project_id
    assert any(item["trace_id"] == trace_id for item in search_payload["items"])
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["trace_id"] == trace_id
    assert len(detail_payload["items"]) == 2
    assert detail_payload["error_count"] == 1
