from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from db_reset import truncate_full_schema
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from lumonox_backend.alerts import StubAlertSender, evaluate_alerts_once
from lumonox_backend.core.config import get_settings
from lumonox_backend.models import Event, Project
from lumonox_backend.repositories.events import request_window_counts
from lumonox_backend.services.event_store import get_duckdb_event_store, shutdown_duckdb_event_store


def _base_row(
    timestamp: datetime, *, event_type: str, status_code: int, suffix: str
) -> dict[str, object]:
    return {
        "timestamp": timestamp,
        "received_at": timestamp,
        "sdk_version": "0.1.0",
        "type": event_type,
        "service_name": "api",
        "environment": "test",
        "method": "GET",
        "path": f"/work/{suffix}",
        "status_code": status_code,
        "latency_ms": 15.0,
        "payload": {"type": event_type},
        "request_id": f"req-{suffix}",
    }


def _seed_sql_events(
    session: AsyncSession,
    *,
    project_id: UUID,
    rows: list[dict[str, object]],
) -> None:
    for row in rows:
        session.add(
            Event(
                project_id=project_id,
                timestamp=row["timestamp"],
                received_at=row["received_at"],
                sdk_version=str(row["sdk_version"]),
                type=str(row["type"]),
                service_name=str(row["service_name"]),
                environment=str(row["environment"]),
                method=str(row["method"]),
                path=str(row["path"]),
                status_code=int(row["status_code"]),
                latency_ms=float(row["latency_ms"]),
                payload=dict(row["payload"]),
                request_id=str(row["request_id"]),
            )
        )


def _seed_duckdb_events(*, project_id: UUID, rows: list[dict[str, object]]) -> None:
    store = get_duckdb_event_store()
    store.insert_rows([{"project_id": str(project_id), **row} for row in rows])


def _request_window_counts_for_mode(
    database_url: str,
    *,
    mode: str,
    rows: list[dict[str, object]],
    now: datetime,
) -> tuple[int, int, int]:
    async def run() -> tuple[int, int, int]:
        shutdown_duckdb_event_store()
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                project = Project(id=uuid4(), name=f"alert-window-{mode}")
                session.add(project)
                await session.flush()
                _seed_sql_events(session, project_id=project.id, rows=rows)
                await session.commit()
                if mode == "duckdb":
                    _seed_duckdb_events(project_id=project.id, rows=rows)
                return await request_window_counts(
                    session,
                    project.id,
                    now - timedelta(minutes=5),
                    now + timedelta(minutes=1),
                )
        finally:
            await engine.dispose()
            shutdown_duckdb_event_store()

    return asyncio.run(run())


def _evaluate_alerts_for_mode(
    database_url: str,
    *,
    mode: str,
    rows: list[dict[str, object]],
    now: datetime,
    error_spike_min_requests: int,
    error_spike_ratio_threshold: float,
    outage_min_requests: int,
) -> tuple[int, str]:
    async def run() -> tuple[int, str]:
        shutdown_duckdb_event_store()
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                project = Project(id=uuid4(), name=f"alert-eval-{mode}")
                session.add(project)
                await session.flush()
                _seed_sql_events(session, project_id=project.id, rows=rows)
                await session.commit()
                if mode == "duckdb":
                    _seed_duckdb_events(project_id=project.id, rows=rows)

                settings = replace(
                    get_settings(),
                    alerts_enabled=True,
                    alert_default_destination_email="ops@example.com",
                    alert_error_spike_min_requests=error_spike_min_requests,
                    alert_error_spike_ratio_threshold=error_spike_ratio_threshold,
                    alert_outage_min_requests=outage_min_requests,
                    alert_cooldown_minutes=0,
                )
                triggered = await evaluate_alerts_once(
                    session,
                    settings,
                    sender=StubAlertSender(),
                    now=now,
                )
                row = await session.execute(
                    text("SELECT alert_type FROM alert_dispatches ORDER BY id DESC LIMIT 1")
                )
                alert_type = str(row.scalar_one())
                return triggered, alert_type
        finally:
            await engine.dispose()
            shutdown_duckdb_event_store()

    return asyncio.run(run())


def test_request_window_counts_match_sql_and_duckdb_for_mixed_error_contract(
    backend_test_database_url: str,
    monkeypatch,
    tmp_path: Path,
) -> None:
    truncate_full_schema(backend_test_database_url)
    now = datetime.now(tz=UTC)
    rows = [
        _base_row(now - timedelta(seconds=30), event_type="request", status_code=200, suffix="ok"),
        _base_row(now - timedelta(seconds=25), event_type="request", status_code=503, suffix="5xx"),
        _base_row(
            now - timedelta(seconds=20), event_type="error", status_code=200, suffix="typed-error"
        ),
        _base_row(
            now - timedelta(seconds=15), event_type="error", status_code=500, suffix="both-error"
        ),
        _base_row(now - timedelta(seconds=10), event_type="request", status_code=404, suffix="4xx"),
    ]
    duckdb_path = tmp_path / "parity-counts.duckdb"
    monkeypatch.setenv("LUMONOX_DUCKDB_PATH", str(duckdb_path))

    monkeypatch.setenv("LUMONOX_EVENT_STORE", "sqlite")
    sql_counts = _request_window_counts_for_mode(
        backend_test_database_url,
        mode="sqlite",
        rows=rows,
        now=now,
    )

    monkeypatch.setenv("LUMONOX_EVENT_STORE", "duckdb")
    duckdb_counts = _request_window_counts_for_mode(
        backend_test_database_url,
        mode="duckdb",
        rows=rows,
        now=now,
    )

    assert sql_counts == (5, 3, 2)
    assert duckdb_counts == sql_counts


def test_alert_evaluation_parity_for_spike_and_outage_windows(
    backend_test_database_url: str,
    monkeypatch,
    tmp_path: Path,
) -> None:
    now = datetime.now(tz=UTC)

    spike_rows = [
        _base_row(
            now - timedelta(seconds=30), event_type="request", status_code=500, suffix="spike-1"
        ),
        _base_row(
            now - timedelta(seconds=20), event_type="error", status_code=200, suffix="spike-2"
        ),
        _base_row(
            now - timedelta(seconds=10), event_type="request", status_code=200, suffix="spike-3"
        ),
    ]
    outage_rows = [
        _base_row(
            now - timedelta(seconds=30), event_type="request", status_code=500, suffix="outage-1"
        ),
        _base_row(
            now - timedelta(seconds=20), event_type="error", status_code=200, suffix="outage-2"
        ),
        _base_row(
            now - timedelta(seconds=10), event_type="error", status_code=500, suffix="outage-3"
        ),
    ]
    duckdb_path = tmp_path / "parity-alerts.duckdb"
    monkeypatch.setenv("LUMONOX_DUCKDB_PATH", str(duckdb_path))

    for mode in ("sqlite", "duckdb"):
        monkeypatch.setenv("LUMONOX_EVENT_STORE", mode)
        truncate_full_schema(backend_test_database_url)
        spike_triggered, spike_type = _evaluate_alerts_for_mode(
            backend_test_database_url,
            mode=mode,
            rows=spike_rows,
            now=now,
            error_spike_min_requests=3,
            error_spike_ratio_threshold=0.6,
            outage_min_requests=99,
        )
        assert spike_triggered == 1
        assert spike_type == "error_spike"

        truncate_full_schema(backend_test_database_url)
        outage_triggered, outage_type = _evaluate_alerts_for_mode(
            backend_test_database_url,
            mode=mode,
            rows=outage_rows,
            now=now,
            error_spike_min_requests=99,
            error_spike_ratio_threshold=0.99,
            outage_min_requests=3,
        )
        assert outage_triggered == 1
        assert outage_type == "possible_outage"
