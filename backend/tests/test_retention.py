from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from db_reset import truncate_full_schema
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from lumonox_backend.core.config import get_settings, normalize_database_url
from lumonox_backend.maintenance import retention as retention_mod
from lumonox_backend.maintenance import run_retention_cleanup_once
from lumonox_backend.models import (
    Base,
    ErrorGroupAggregate,
    Event,
    MetricBucket,
    Project,
    ProjectUiSettings,
)


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
                        exclude_lumonox_traffic=True,
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
                        exclude_lumonox_traffic=True,
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


def test_retention_cleanup_enforces_project_log_row_cap_for_sqlite(
    backend_test_database_url: str,
) -> None:
    now = datetime.now(tz=UTC)

    async def run() -> tuple[int, int]:
        engine = create_async_engine(backend_test_database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                project = Project(id=uuid4(), name="Row Cap Project")
                session.add(project)
                await session.flush()
                session.add(
                    ProjectUiSettings(
                        project_id=project.id,
                        theme_preference="system",
                        exclude_lumonox_traffic=True,
                        retention_raw_events_days=90,
                        retention_max_log_rows=2,
                        logs_query_max_window_minutes=60,
                    )
                )
                for index in range(4):
                    event_time = now - timedelta(minutes=10 - index)
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
                            path=f"/row-cap-{index}",
                            status_code=200,
                            latency_ms=10.0,
                            payload={"path": f"/row-cap-{index}"},
                            request_id=f"row-cap-{index}",
                        )
                    )
                await session.commit()
                settings = replace(get_settings(), retention_raw_events_days=90)
                result = await run_retention_cleanup_once(session, settings, now=now)
                remaining_result = await session.execute(text("SELECT COUNT(*) FROM events"))
                remaining = int(remaining_result.scalar_one())
                return result.deleted_events, remaining
        finally:
            await engine.dispose()

    truncate_full_schema(backend_test_database_url)
    deleted, remaining = asyncio.run(run())
    assert deleted == 2
    assert remaining == 2


def test_retention_cleanup_applies_aggregate_cutoff_longer_than_raw(
    backend_test_database_url: str,
) -> None:
    now = datetime.now(tz=UTC)

    async def run() -> tuple[int, int, int]:
        engine = create_async_engine(backend_test_database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                project = Project(id=uuid4(), name="Aggregate Cutoff Project")
                session.add(project)
                await session.flush()
                session.add(
                    Event(
                        project_id=project.id,
                        timestamp=now - timedelta(days=20),
                        received_at=now - timedelta(days=20),
                        sdk_version="0.1.0",
                        type="request",
                        service_name="api",
                        environment="test",
                        method="GET",
                        path="/raw-old",
                        status_code=200,
                        latency_ms=10.0,
                        payload={"path": "/raw-old"},
                        request_id="raw-old-1",
                    )
                )
                session.add_all(
                    [
                        MetricBucket(
                            project_id=project.id,
                            minute_start=now - timedelta(days=40),
                            service_name="api",
                            environment="test",
                            request_count=1,
                            error_count=0,
                            latency_total_ms=12.0,
                            count_2xx=1,
                            count_3xx=0,
                            count_4xx=0,
                            count_5xx=0,
                        ),
                        MetricBucket(
                            project_id=project.id,
                            minute_start=now - timedelta(days=20),
                            service_name="api",
                            environment="test",
                            request_count=2,
                            error_count=0,
                            latency_total_ms=30.0,
                            count_2xx=2,
                            count_3xx=0,
                            count_4xx=0,
                            count_5xx=0,
                        ),
                        ErrorGroupAggregate(
                            project_id=project.id,
                            group_key="group-old",
                            path="/boom",
                            exception_type="ValueError",
                            message="boom",
                            sample_stack_trace="trace",
                            count=1,
                            first_seen=now - timedelta(days=40),
                            last_seen=now - timedelta(days=40),
                        ),
                        ErrorGroupAggregate(
                            project_id=project.id,
                            group_key="group-recent",
                            path="/boom2",
                            exception_type="RuntimeError",
                            message="boom2",
                            sample_stack_trace="trace2",
                            count=3,
                            first_seen=now - timedelta(days=20),
                            last_seen=now - timedelta(days=20),
                        ),
                    ]
                )
                await session.commit()
                settings = replace(
                    get_settings(),
                    retention_raw_events_days=7,
                    retention_aggregates_days=30,
                    sqlite_size_retention_only=False,
                )
                await run_retention_cleanup_once(session, settings, now=now)
                remaining_events = int(
                    (await session.execute(text("SELECT COUNT(*) FROM events"))).scalar_one()
                )
                remaining_metric_buckets = int(
                    (
                        await session.execute(text("SELECT COUNT(*) FROM metric_buckets"))
                    ).scalar_one()
                )
                remaining_error_groups = int(
                    (
                        await session.execute(text("SELECT COUNT(*) FROM error_group_aggregates"))
                    ).scalar_one()
                )
                return remaining_events, remaining_metric_buckets, remaining_error_groups
        finally:
            await engine.dispose()

    truncate_full_schema(backend_test_database_url)
    remaining_events, remaining_metric_buckets, remaining_error_groups = asyncio.run(run())
    assert remaining_events == 0
    assert remaining_metric_buckets == 1
    assert remaining_error_groups == 1


def test_retention_cleanup_project_override_keeps_aggregates_longer_than_project_raw(
    backend_test_database_url: str,
) -> None:
    now = datetime.now(tz=UTC)

    async def run() -> tuple[int, int]:
        engine = create_async_engine(backend_test_database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                project = Project(id=uuid4(), name="Aggregate Override Project")
                session.add(project)
                await session.flush()
                session.add(
                    ProjectUiSettings(
                        project_id=project.id,
                        theme_preference="system",
                        exclude_lumonox_traffic=True,
                        retention_raw_events_days=2,
                        logs_query_max_window_minutes=60,
                    )
                )
                session.add(
                    MetricBucket(
                        project_id=project.id,
                        minute_start=now - timedelta(days=10),
                        service_name="api",
                        environment="test",
                        request_count=1,
                        error_count=0,
                        latency_total_ms=10.0,
                        count_2xx=1,
                        count_3xx=0,
                        count_4xx=0,
                        count_5xx=0,
                    )
                )
                session.add(
                    ErrorGroupAggregate(
                        project_id=project.id,
                        group_key="group-override",
                        path="/override",
                        exception_type="Exception",
                        message="override",
                        sample_stack_trace="trace",
                        count=1,
                        first_seen=now - timedelta(days=10),
                        last_seen=now - timedelta(days=10),
                    )
                )
                await session.commit()
                settings = replace(
                    get_settings(),
                    retention_raw_events_days=7,
                    retention_aggregates_days=30,
                    sqlite_size_retention_only=False,
                )
                await run_retention_cleanup_once(session, settings, now=now)
                remaining_metric_buckets = int(
                    (
                        await session.execute(text("SELECT COUNT(*) FROM metric_buckets"))
                    ).scalar_one()
                )
                remaining_error_groups = int(
                    (
                        await session.execute(text("SELECT COUNT(*) FROM error_group_aggregates"))
                    ).scalar_one()
                )
                return remaining_metric_buckets, remaining_error_groups
        finally:
            await engine.dispose()

    truncate_full_schema(backend_test_database_url)
    remaining_metric_buckets, remaining_error_groups = asyncio.run(run())
    assert remaining_metric_buckets == 1
    assert remaining_error_groups == 1


def test_sqlite_global_file_cap_deletes_oldest_when_file_over_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "global_cap.db"
    database_url = normalize_database_url(f"sqlite+aiosqlite:///{db_path}")
    resolved = retention_mod._resolve_sqlite_db_path(database_url)
    assert resolved is not None

    async def seed() -> None:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)
            async with session_maker() as session:
                project = Project(id=uuid4(), name="Cap Project")
                session.add(project)
                await session.flush()
                now = datetime.now(tz=UTC)
                for i in range(3):
                    session.add(
                        Event(
                            project_id=project.id,
                            timestamp=now - timedelta(seconds=i),
                            received_at=now - timedelta(seconds=i),
                            sdk_version="0.1.0",
                            type="request",
                            service_name="api",
                            environment="test",
                            method="GET",
                            path=f"/p-{i}",
                            status_code=200,
                            latency_ms=1.0,
                            payload={"i": i},
                            request_id=f"r-{i}",
                        )
                    )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(seed())

    orig_stat = Path.stat
    real_st = orig_stat(resolved)
    marker = (real_st.st_dev, real_st.st_ino)

    def fake_stat(self: Path, *, follow_symlinks: bool = True):
        st = orig_stat(self, follow_symlinks=follow_symlinks)
        key = (st.st_dev, st.st_ino)
        # Retention and drivers may stat the DB file before the cap runs; keep the file
        # "virtually" over the cap until SQLite deletes drain the batch loop.
        if key == marker:
            return SimpleNamespace(st_size=99_000_000)
        return st

    monkeypatch.setattr(Path, "stat", fake_stat)

    async def run_retention() -> tuple[int, int]:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                settings = replace(
                    get_settings(),
                    database_url=database_url,
                    retention_raw_events_days=10_000,
                    sqlite_max_db_file_mb=50,
                )
                result = await run_retention_cleanup_once(
                    session, settings, now=datetime.now(tz=UTC)
                )
                deleted_events = result.deleted_events
            async with session_maker() as session2:
                remaining = int(
                    (await session2.execute(text("SELECT COUNT(*) FROM events"))).scalar_one()
                )
                return deleted_events, remaining
        finally:
            await engine.dispose()

    deleted, remaining = asyncio.run(run_retention())
    assert remaining == 0
    assert deleted >= 3


def test_sqlite_global_file_cap_uses_min_ui_when_sqlite_cap_unset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "ui_only_cap.db"
    database_url = normalize_database_url(f"sqlite+aiosqlite:///{db_path}")
    resolved = retention_mod._resolve_sqlite_db_path(database_url)
    assert resolved is not None

    async def seed() -> None:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)
            async with session_maker() as session:
                project = Project(id=uuid4(), name="UI Cap Project")
                session.add(project)
                await session.flush()
                session.add(
                    ProjectUiSettings(
                        project_id=project.id,
                        theme_preference="system",
                        exclude_lumonox_traffic=True,
                        retention_raw_events_days=90,
                        retention_max_db_size_mb=50,
                        logs_query_max_window_minutes=60,
                    )
                )
                now = datetime.now(tz=UTC)
                for i in range(2):
                    session.add(
                        Event(
                            project_id=project.id,
                            timestamp=now - timedelta(seconds=i),
                            received_at=now - timedelta(seconds=i),
                            sdk_version="0.1.0",
                            type="request",
                            service_name="api",
                            environment="test",
                            method="GET",
                            path=f"/p-{i}",
                            status_code=200,
                            latency_ms=1.0,
                            payload={"i": i},
                            request_id=f"r-{i}",
                        )
                    )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(seed())

    orig_stat = Path.stat
    real_st = orig_stat(resolved)
    marker = (real_st.st_dev, real_st.st_ino)

    def fake_stat(self: Path, *, follow_symlinks: bool = True):
        st = orig_stat(self, follow_symlinks=follow_symlinks)
        key = (st.st_dev, st.st_ino)
        if key == marker:
            return SimpleNamespace(st_size=99_000_000)
        return st

    monkeypatch.setattr(Path, "stat", fake_stat)

    async def run_retention() -> tuple[int, int]:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                settings = replace(
                    get_settings(),
                    database_url=database_url,
                    retention_raw_events_days=10_000,
                    sqlite_max_db_file_mb=None,
                )
                result = await run_retention_cleanup_once(
                    session, settings, now=datetime.now(tz=UTC)
                )
                deleted_events = result.deleted_events
            async with session_maker() as session2:
                remaining = int(
                    (await session2.execute(text("SELECT COUNT(*) FROM events"))).scalar_one()
                )
                return deleted_events, remaining
        finally:
            await engine.dispose()

    deleted, remaining = asyncio.run(run_retention())
    assert remaining == 0
    assert deleted >= 2


def test_duckdb_size_shrink_falls_back_to_widget_points(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lumonox_backend.maintenance import retention_duckdb

    class _FakeStore:
        def __init__(self) -> None:
            self._size_reads = 0
            self.event_delete_calls = 0
            self.widget_delete_calls = 0

        def checkpoint(self) -> None:
            return None

        def file_size_bytes(self) -> int:
            self._size_reads += 1
            # Over cap at first; under cap after widget-point cleanup.
            return 300 if self._size_reads < 3 else 80

        def delete_oldest_events(self, *, rows_to_delete: int, project_id=None) -> int:
            self.event_delete_calls += 1
            return 0

        def delete_oldest_widget_points(self, *, rows_to_delete: int, project_id=None) -> int:
            self.widget_delete_calls += 1
            return 250 if self.widget_delete_calls == 1 else 0

    store = _FakeStore()
    monkeypatch.setattr(retention_duckdb, "get_duckdb_event_store", lambda: store)

    async def _run_read(fn, *args, **kwargs):
        kwargs.pop("duckdb_read_operation", None)
        return fn(*args, **kwargs)

    async def _run_write(fn, *args, **kwargs):
        kwargs.pop("duckdb_write_operation", None)
        return fn(*args, **kwargs)

    monkeypatch.setattr(retention_duckdb, "run_duckdb_read_sync", _run_read)
    monkeypatch.setattr(retention_duckdb, "run_duckdb_write_sync", _run_write)

    deleted = asyncio.run(
        retention_duckdb._duckdb_shrink_under_size_cap(
            max_bytes=100,
            project_id=None,
        )
    )
    assert deleted == 250
    assert store.event_delete_calls >= 1
    assert store.widget_delete_calls >= 1
