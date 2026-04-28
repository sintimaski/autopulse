from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from db_reset import truncate_full_schema
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from autopulse_backend.config import get_settings
from autopulse_backend.maintenance import run_retention_cleanup_once
from autopulse_backend.models import Event, Project, ProjectUiSettings


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


def test_retention_cleanup_respects_project_override(
    backend_test_database_url: str,
) -> None:
    now = datetime.now(tz=UTC)

    async def run() -> tuple[int, int]:
        engine = create_async_engine(backend_test_database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                project = Project(id=uuid4(), name="Override Project")
                session.add(project)
                await session.flush()
                session.add(
                    ProjectUiSettings(
                        project_id=project.id,
                        theme_preference="system",
                        exclude_autopulse_traffic=True,
                        retention_raw_events_days=2,
                        logs_query_max_window_minutes=60,
                    )
                )
                old_time = now - timedelta(days=3)
                session.add(
                    Event(
                        project_id=project.id,
                        timestamp=old_time,
                        received_at=old_time,
                        sdk_version="0.1.0",
                        type="request",
                        service_name="api",
                        environment="test",
                        method="GET",
                        path="/old-override",
                        status_code=200,
                        latency_ms=10.0,
                        payload={"path": "/old-override"},
                        request_id="override-1",
                    )
                )
                await session.commit()
                settings = replace(get_settings(), retention_raw_events_days=14)
                result = await run_retention_cleanup_once(session, settings, now=now)
                remaining_result = await session.execute(text("SELECT COUNT(*) FROM events"))
                return result.deleted_events, int(remaining_result.scalar_one())
        finally:
            await engine.dispose()

    truncate_full_schema(backend_test_database_url)
    deleted, remaining = asyncio.run(run())
    assert deleted == 1
    assert remaining == 0


def test_retention_cleanup_archives_before_delete_when_enabled(
    backend_test_database_url: str,
) -> None:
    now = datetime.now(tz=UTC)

    async def run() -> tuple[int, int]:
        engine = create_async_engine(backend_test_database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                project = Project(id=uuid4(), name="Archive Project")
                session.add(project)
                await session.flush()
                session.add(
                    ProjectUiSettings(
                        project_id=project.id,
                        theme_preference="system",
                        exclude_autopulse_traffic=True,
                        retention_raw_events_days=2,
                        retention_plan="extended",
                        archival_enabled=True,
                        archival_mode="db_archive",
                        archival_status="idle",
                        logs_query_max_window_minutes=60,
                    )
                )
                old_time = now - timedelta(days=10)
                session.add(
                    Event(
                        project_id=project.id,
                        timestamp=old_time,
                        received_at=old_time,
                        sdk_version="0.1.0",
                        type="request",
                        service_name="api",
                        environment="test",
                        method="GET",
                        path="/archive-me",
                        status_code=500,
                        latency_ms=10.0,
                        payload={"path": "/archive-me"},
                        request_id="archive-1",
                    )
                )
                await session.commit()
                settings = replace(get_settings(), retention_raw_events_days=14)
                result = await run_retention_cleanup_once(session, settings, now=now)
                archived_count = int(
                    (
                        await session.execute(text("SELECT COUNT(*) FROM archived_events"))
                    ).scalar_one()
                )
                return result.deleted_events, archived_count
        finally:
            await engine.dispose()

    truncate_full_schema(backend_test_database_url)
    deleted, archived = asyncio.run(run())
    assert deleted == 1
    assert archived == 1
