"""SQLite retention pressure probe (file size + row caps)."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from autopulse_backend.core.config import get_settings, normalize_database_url
from autopulse_backend.maintenance.retention import sqlite_retention_pressure_pending
from autopulse_backend.models import Base, Event, Project, ProjectUiSettings


def test_sqlite_retention_pressure_pending_true_when_events_exceed_row_cap(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "pressure_rows.db"
    database_url = normalize_database_url(f"sqlite+aiosqlite:///{db_path}")
    now = datetime.now(tz=UTC)

    async def run() -> bool:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)
            async with session_maker() as session:
                project = Project(id=uuid4(), name="Pressure Project")
                session.add(project)
                await session.flush()
                session.add(
                    ProjectUiSettings(
                        project_id=project.id,
                        theme_preference="system",
                        retention_max_log_rows=2,
                    )
                )
                for index in range(4):
                    t = now - timedelta(seconds=index)
                    session.add(
                        Event(
                            project_id=project.id,
                            timestamp=t,
                            received_at=t,
                            sdk_version="0.1.0",
                            type="request",
                            service_name="api",
                            environment="test",
                            method="GET",
                            path=f"/p-{index}",
                            status_code=200,
                            latency_ms=1.0,
                            payload={},
                            request_id=f"r-{index}",
                        )
                    )
                await session.commit()
            settings = replace(
                get_settings(),
                database_url=database_url,
                embedded_sqlite_max_db_file_mb=None,
            )
            async with session_maker() as session:
                return await sqlite_retention_pressure_pending(session, settings)
        finally:
            await engine.dispose()

    assert asyncio.run(run()) is True


def test_sqlite_retention_pressure_pending_false_when_within_row_cap(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "pressure_ok.db"
    database_url = normalize_database_url(f"sqlite+aiosqlite:///{db_path}")
    now = datetime.now(tz=UTC)

    async def run() -> bool:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)
            async with session_maker() as session:
                project = Project(id=uuid4(), name="Ok Project")
                session.add(project)
                await session.flush()
                session.add(
                    ProjectUiSettings(
                        project_id=project.id,
                        theme_preference="system",
                        retention_max_log_rows=10,
                    )
                )
                session.add(
                    Event(
                        project_id=project.id,
                        timestamp=now,
                        received_at=now,
                        sdk_version="0.1.0",
                        type="request",
                        service_name="api",
                        environment="test",
                        method="GET",
                        path="/one",
                        status_code=200,
                        latency_ms=1.0,
                        payload={},
                        request_id="r-1",
                    )
                )
                await session.commit()
            settings = replace(
                get_settings(),
                database_url=database_url,
                embedded_sqlite_max_db_file_mb=None,
            )
            async with session_maker() as session:
                return await sqlite_retention_pressure_pending(session, settings)
        finally:
            await engine.dispose()

    assert asyncio.run(run()) is False
