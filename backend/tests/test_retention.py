from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from db_reset import truncate_full_schema
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from autopulse_backend.config import get_settings
from autopulse_backend.models import Event, Project
from autopulse_backend.retention import run_retention_cleanup_once


def _seed_old_and_fresh_events(database_url: str, now: datetime) -> None:
    async def run() -> None:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                project = Project(id=uuid4(), name="Retention Project")
                session.add(project)
                await session.flush()
                old_time = now - timedelta(days=30)
                fresh_time = now - timedelta(days=2)
                session.add_all(
                    [
                        Event(
                            project_id=project.id,
                            timestamp=old_time,
                            received_at=old_time,
                            sdk_version="0.1.0",
                            type="request",
                            service_name="api",
                            environment="test",
                            method="GET",
                            path="/old",
                            status_code=200,
                            latency_ms=10.0,
                            payload={"path": "/old"},
                            request_id="old-1",
                        ),
                        Event(
                            project_id=project.id,
                            timestamp=fresh_time,
                            received_at=fresh_time,
                            sdk_version="0.1.0",
                            type="request",
                            service_name="api",
                            environment="test",
                            method="GET",
                            path="/fresh",
                            status_code=200,
                            latency_ms=12.0,
                            payload={"path": "/fresh"},
                            request_id="fresh-1",
                        ),
                    ]
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(run())


def _run_retention(database_url: str, now: datetime) -> tuple[int, int]:
    async def run() -> tuple[int, int]:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                settings = replace(get_settings(), retention_raw_events_days=14)
                result = await run_retention_cleanup_once(session, settings, now=now)
                remaining_result = await session.execute(text("SELECT COUNT(*) FROM events"))
                remaining = int(remaining_result.scalar_one())
                return result.deleted_events, remaining
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_retention_cleanup_deletes_only_rows_older_than_window(
    backend_test_database_url: str,
) -> None:
    now = datetime.now(tz=UTC)
    truncate_full_schema(backend_test_database_url)
    _seed_old_and_fresh_events(backend_test_database_url, now)

    deleted, remaining = _run_retention(backend_test_database_url, now)

    assert deleted == 1
    assert remaining == 1
