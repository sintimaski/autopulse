from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from autopulse_backend.alerts import StubAlertSender, evaluate_alerts_once
from autopulse_backend.config import get_settings
from autopulse_backend.models import Event, Project


def _truncate_tables(database_url: str) -> None:
    async def run() -> None:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                await session.execute(
                    text(
                        "TRUNCATE TABLE alert_dispatches, project_alert_settings, "
                        "events, api_keys, projects "
                        "RESTART IDENTITY CASCADE"
                    )
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(run())


def _seed_request_events(
    database_url: str,
    *,
    request_count: int,
    error_count: int,
    base_time: datetime,
) -> str:
    async def run() -> str:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                project = Project(id=uuid4(), name="Alert Test Project")
                session.add(project)
                await session.flush()
                for index in range(request_count):
                    is_error = index < error_count
                    event_time = base_time + timedelta(seconds=index)
                    session.add(
                        Event(
                            project_id=project.id,
                            timestamp=event_time,
                            received_at=event_time,
                            sdk_version="0.1.0",
                            type="request",
                            service_name="api",
                            environment="test",
                            method="GET",
                            path="/work",
                            status_code=500 if is_error else 200,
                            latency_ms=20.0,
                            payload={"type": "request"},
                            request_id=f"req-{index}",
                        )
                    )
                await session.commit()
                return str(project.id)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _run_alert_job(
    database_url: str,
    *,
    now: datetime,
    error_spike_min_requests: int,
    error_spike_ratio_threshold: float,
    outage_min_requests: int,
    cooldown_minutes: int,
) -> tuple[int, int]:
    async def run() -> tuple[int, int]:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        sender = StubAlertSender()
        try:
            async with session_maker() as session:
                base_settings = get_settings()
                settings = replace(
                    base_settings,
                    alerts_enabled=True,
                    alert_default_destination_email="ops@example.com",
                    alert_error_spike_min_requests=error_spike_min_requests,
                    alert_error_spike_ratio_threshold=error_spike_ratio_threshold,
                    alert_outage_min_requests=outage_min_requests,
                    alert_cooldown_minutes=cooldown_minutes,
                )
                triggered = await evaluate_alerts_once(
                    session,
                    settings,
                    sender=sender,
                    now=now,
                )
                dispatch_rows = await session.execute(text("SELECT COUNT(*) FROM alert_dispatches"))
                stored_count = int(dispatch_rows.scalar_one())
                return triggered, stored_count
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_alert_job_triggers_error_spike_and_suppresses_inside_cooldown(
    backend_test_database_url: str,
) -> None:
    _truncate_tables(backend_test_database_url)
    base_time = datetime.now(tz=UTC) - timedelta(minutes=2)
    _seed_request_events(
        backend_test_database_url,
        request_count=10,
        error_count=7,
        base_time=base_time,
    )

    first_triggered, first_stored = _run_alert_job(
        backend_test_database_url,
        now=base_time + timedelta(minutes=1),
        error_spike_min_requests=5,
        error_spike_ratio_threshold=0.5,
        outage_min_requests=50,
        cooldown_minutes=30,
    )
    second_triggered, second_stored = _run_alert_job(
        backend_test_database_url,
        now=base_time + timedelta(minutes=2),
        error_spike_min_requests=5,
        error_spike_ratio_threshold=0.5,
        outage_min_requests=50,
        cooldown_minutes=30,
    )

    assert first_triggered == 1
    assert first_stored == 1
    assert second_triggered == 0
    assert second_stored == 1


def test_alert_job_triggers_outage_when_no_success_requests(
    backend_test_database_url: str,
) -> None:
    _truncate_tables(backend_test_database_url)
    base_time = datetime.now(tz=UTC) - timedelta(minutes=2)
    _seed_request_events(
        backend_test_database_url,
        request_count=6,
        error_count=6,
        base_time=base_time,
    )

    triggered, stored = _run_alert_job(
        backend_test_database_url,
        now=base_time + timedelta(minutes=1),
        error_spike_min_requests=100,
        error_spike_ratio_threshold=0.95,
        outage_min_requests=5,
        cooldown_minutes=10,
    )

    assert triggered == 1
    assert stored == 1
