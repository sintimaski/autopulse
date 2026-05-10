from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from db_reset import truncate_ingest_core_tables as _truncate_tables
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from test_dashboard import _ingest, _seed_project_and_key

from lumonox_backend.app import create_app
from lumonox_backend.models import MetricBucket
from lumonox_backend.services.event_store import shutdown_duckdb_event_store


def test_overview_traffic_merges_sql_metric_buckets_when_duck_bucket_empty(
    backend_test_database_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """DuckDB raw rows missing for a minute while SQLite ``metric_buckets`` still has totals."""
    _truncate_tables(backend_test_database_url)
    key, project_id_str = _seed_project_and_key(backend_test_database_url, "metric-merge-overview")
    project_id = UUID(project_id_str)

    duck = tmp_path / "ev.duckdb"
    monkeypatch.setenv("LUMONOX_EVENT_STORE", "duckdb")
    monkeypatch.setenv("LUMONOX_DUCKDB_PATH", str(duck))
    monkeypatch.setenv("DASHBOARD_AUTH_ENABLED", "false")
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK", "true")
    shutdown_duckdb_event_store()

    base = datetime.now(tz=UTC).replace(second=0, microsecond=0)

    async def _seed_metric() -> None:
        engine = create_async_engine(backend_test_database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                session.add(
                    MetricBucket(
                        project_id=project_id,
                        minute_start=base + timedelta(minutes=10),
                        service_name="api",
                        environment="test",
                        request_count=100,
                        error_count=15,
                        latency_total_ms=1500.0,
                        count_2xx=85,
                        count_3xx=0,
                        count_4xx=0,
                        count_5xx=15,
                    )
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(_seed_metric())

    app = create_app()
    with TestClient(app) as client:
        _ingest(client, key, base + timedelta(minutes=40), 200, "GET", "/late")
        response = client.get(
            "/dashboard/overview",
            params={
                "from_timestamp": base.isoformat(),
                "to_timestamp": (base + timedelta(minutes=45)).isoformat(),
            },
            headers={"Authorization": f"Bearer {key}"},
        )

    assert response.status_code == 200
    payload = response.json()
    sql_hits = [e for e in payload["series"] if int(e["request_count"]) == 100]
    assert len(sql_hits) == 1
    assert sql_hits[0]["error_count"] == 15
    duck_hits = [e for e in payload["series"] if int(e["request_count"]) == 1]
    assert len(duck_hits) == 1
    assert int(payload["request_count"]) == 101
