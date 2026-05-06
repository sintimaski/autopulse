from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from db_reset import truncate_full_schema
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from test_alerts import _seed_request_events
from test_parquet_exporter import _seed_duckdb_events

from autopulse_backend import jobs
from autopulse_backend.database import dispose_engine_for_url
from autopulse_backend.metrics import service_metrics
from autopulse_backend.models import IngestSqlTailRepairItem, Project
from autopulse_backend.services.ingest_sql_tail_codec import encode_ingest_sql_tail_payload


def _insert_sql_tail_repair_item(database_url: str) -> None:
    async def run() -> None:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                project = Project(id=uuid4(), name="Repair Project")
                session.add(project)
                await session.flush()
                payload = encode_ingest_sql_tail_payload(
                    widget_definitions=[
                        {
                            "project_id": project.id,
                            "widget_id": "requests_per_minute",
                            "widget_type": "timeseries",
                            "title": "Requests/min",
                            "description": None,
                            "display_order": 10,
                            "config": {},
                            "updated_at": datetime.now(tz=UTC),
                        }
                    ],
                    metric_bucket_deltas=[],
                    error_group_deltas=[],
                    persist_aggregates=False,
                )
                session.add(
                    IngestSqlTailRepairItem(
                        project_id=project.id,
                        payload=payload,
                    )
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(run())


def _count_dead_lettered_sql_tail_repairs(database_url: str) -> int:
    async def run() -> int:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                result = await session.execute(
                    text(
                        "SELECT COUNT(*) FROM ingest_sql_tail_repair_items "
                        "WHERE dead_lettered_at IS NOT NULL"
                    )
                )
                return int(result.scalar_one())
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _count_pending_sql_tail_repairs(database_url: str) -> int:
    async def run() -> int:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                result = await session.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM ingest_sql_tail_repair_items
                        WHERE resolved_at IS NULL AND dead_lettered_at IS NULL
                        """
                    )
                )
                return int(result.scalar_one())
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_jobs_cli_alerts_once_prints_zero_with_no_projects(
    backend_test_database_url: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    truncate_full_schema(backend_test_database_url)

    exit_code = jobs.main(["alerts-once"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "0"


def test_jobs_cli_alerts_once_prints_dispatch_count_after_spike(
    backend_test_database_url: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    truncate_full_schema(backend_test_database_url)
    base_time = datetime.now(tz=UTC) - timedelta(minutes=2)
    _seed_request_events(
        backend_test_database_url,
        request_count=25,
        error_count=10,
        base_time=base_time,
    )

    exit_code = jobs.main(["alerts-once"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "1"


def test_jobs_cli_retention_once_runs(
    backend_test_database_url: str, capsys: pytest.CaptureFixture[str]
) -> None:
    truncate_full_schema(backend_test_database_url)

    exit_code = jobs.main(["retention-once"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip().isdigit()


def test_jobs_cli_records_last_run_telemetry(
    backend_test_database_url: str,
) -> None:
    truncate_full_schema(backend_test_database_url)

    jobs.main(["retention-once"])
    snapshot = service_metrics.job_snapshot()

    assert "retention" in snapshot
    assert snapshot["retention"]["status"] == "succeeded"
    assert isinstance(snapshot["retention"]["duration_ms"], int)


def test_run_retention_sync_runs_on_fresh_sqlite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "sync_retention.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")

    from autopulse_backend.jobs import run_retention_sync

    n = run_retention_sync()
    assert isinstance(n, int)
    assert db_path.exists()


def test_retention_once_creates_sqlite_schema_on_fresh_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI must not assume tables exist (cron may run before first API start)."""
    db_path = tmp_path / "fresh_cli.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")

    exit_code = jobs.main(["retention-once"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip().isdigit()
    assert db_path.exists()


def test_jobs_cli_replay_sql_tail_repairs_once(
    backend_test_database_url: str, capsys: pytest.CaptureFixture[str]
) -> None:
    truncate_full_schema(backend_test_database_url)
    _insert_sql_tail_repair_item(backend_test_database_url)
    assert _count_pending_sql_tail_repairs(backend_test_database_url) == 1

    exit_code = jobs.main(["replay-sql-tail-repairs-once"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "1"
    assert _count_pending_sql_tail_repairs(backend_test_database_url) == 0


def test_replay_sql_tail_repairs_dead_letters_after_repeated_failure(
    backend_test_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    truncate_full_schema(backend_test_database_url)
    _insert_sql_tail_repair_item(backend_test_database_url)
    monkeypatch.setenv("INGEST_SQL_TAIL_REPAIR_MAX_RETRIES", "1")

    async def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("simulated replay failure")

    monkeypatch.setattr(
        "autopulse_backend.jobs.dashboard_widgets_repo.upsert_widget_definitions",
        boom,
    )
    from autopulse_backend.jobs import run_replay_sql_tail_repairs_once

    repaired = asyncio.run(run_replay_sql_tail_repairs_once())
    assert repaired == 0
    assert _count_pending_sql_tail_repairs(backend_test_database_url) == 0
    assert _count_dead_lettered_sql_tail_repairs(backend_test_database_url) == 1


def test_replay_sql_tail_repairs_skips_rows_until_next_retry_at(
    backend_test_database_url: str,
) -> None:
    truncate_full_schema(backend_test_database_url)
    _insert_sql_tail_repair_item(backend_test_database_url)
    assert _count_pending_sql_tail_repairs(backend_test_database_url) == 1

    async def bump_next_retry() -> None:
        engine = create_async_engine(backend_test_database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                await session.execute(
                    text(
                        "UPDATE ingest_sql_tail_repair_items SET next_retry_at = :ts "
                        "WHERE resolved_at IS NULL AND dead_lettered_at IS NULL"
                    ),
                    {"ts": datetime.now(tz=UTC) + timedelta(days=1)},
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(bump_next_retry())
    assert _count_pending_sql_tail_repairs(backend_test_database_url) == 1

    from autopulse_backend.jobs import run_replay_sql_tail_repairs_once

    assert asyncio.run(run_replay_sql_tail_repairs_once()) == 0


def test_jobs_cli_parquet_export_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = tmp_path / "events.duckdb"
    meta_db = tmp_path / "meta.db"
    _seed_duckdb_events(db_path)
    parquet_root = tmp_path / "parquet-out"
    database_url = f"sqlite+aiosqlite:///{meta_db}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("AUTOPULSE_ENV", "development")
    monkeypatch.setenv("AUTOPULSE_EVENT_STORE", "duckdb")
    monkeypatch.setenv("AUTOPULSE_EVENT_PLANE_MODE", "duckdb_single_writer")
    monkeypatch.setenv("AUTOPULSE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTOPULSE_DUCKDB_PATH", str(db_path.resolve()))
    monkeypatch.setenv("AUTOPULSE_PARQUET_EXPORT_ENABLED", "true")
    monkeypatch.setenv("AUTOPULSE_PARQUET_EXPORT_ROOT", str(parquet_root))
    monkeypatch.setenv("AUTOPULSE_PARQUET_EXPORT_WINDOW_SECONDS", "900")
    try:
        exit_code = jobs.main(["parquet-export-once"])
    finally:
        asyncio.run(dispose_engine_for_url(database_url))

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "2"
    assert any(parquet_root.glob("date=*/service=*/environment=*/part-*.parquet"))


def test_jobs_cli_parquet_lifecycle_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = tmp_path / "events.duckdb"
    meta_db = tmp_path / "meta.db"
    _seed_duckdb_events(db_path)
    parquet_root = tmp_path / "parquet-out"
    database_url = f"sqlite+aiosqlite:///{meta_db}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("AUTOPULSE_ENV", "development")
    monkeypatch.setenv("AUTOPULSE_EVENT_STORE", "duckdb")
    monkeypatch.setenv("AUTOPULSE_EVENT_PLANE_MODE", "duckdb_single_writer")
    monkeypatch.setenv("AUTOPULSE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTOPULSE_DUCKDB_PATH", str(db_path.resolve()))
    monkeypatch.setenv("AUTOPULSE_PARQUET_EXPORT_ENABLED", "true")
    monkeypatch.setenv("AUTOPULSE_PARQUET_EXPORT_ROOT", str(parquet_root))
    monkeypatch.setenv("AUTOPULSE_PARQUET_EXPORT_WINDOW_SECONDS", "900")
    monkeypatch.setenv("AUTOPULSE_PARQUET_LIFECYCLE_ENABLED", "true")
    monkeypatch.setenv("AUTOPULSE_PARQUET_LIFECYCLE_COMPACTION_MIN_FILES", "2")
    monkeypatch.setenv("AUTOPULSE_PARQUET_LIFECYCLE_RETENTION_DAYS", "3650")
    try:
        export_exit_code = jobs.main(["parquet-export-once"])
        lifecycle_exit_code = jobs.main(["parquet-lifecycle-once"])
    finally:
        asyncio.run(dispose_engine_for_url(database_url))

    assert export_exit_code == 0
    assert lifecycle_exit_code == 0
    assert capsys.readouterr().out.strip().splitlines()[-1].isdigit()


def test_jobs_cli_parquet_object_sync_and_restore_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = tmp_path / "events.duckdb"
    meta_db = tmp_path / "meta.db"
    _seed_duckdb_events(db_path)
    parquet_root = tmp_path / "parquet-out"
    object_store_root = tmp_path / "object-store"
    restore_root = tmp_path / "restored"
    database_url = f"sqlite+aiosqlite:///{meta_db}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("AUTOPULSE_ENV", "development")
    monkeypatch.setenv("AUTOPULSE_EVENT_STORE", "duckdb")
    monkeypatch.setenv("AUTOPULSE_EVENT_PLANE_MODE", "duckdb_single_writer")
    monkeypatch.setenv("AUTOPULSE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTOPULSE_DUCKDB_PATH", str(db_path.resolve()))
    monkeypatch.setenv("AUTOPULSE_PARQUET_EXPORT_ENABLED", "true")
    monkeypatch.setenv("AUTOPULSE_PARQUET_EXPORT_ROOT", str(parquet_root))
    monkeypatch.setenv("AUTOPULSE_PARQUET_EXPORT_WINDOW_SECONDS", "900")
    monkeypatch.setenv("AUTOPULSE_PARQUET_OBJECT_STORAGE_ENABLED", "true")
    monkeypatch.setenv(
        "AUTOPULSE_PARQUET_OBJECT_STORAGE_URI",
        f"file://{object_store_root.resolve()}",
    )
    monkeypatch.setenv("AUTOPULSE_PARQUET_OBJECT_STORAGE_PREFIX", "snapshots")
    monkeypatch.setenv("AUTOPULSE_PARQUET_OBJECT_STORAGE_RESTORE_ROOT", str(restore_root))
    try:
        export_exit_code = jobs.main(["parquet-export-once"])
        sync_exit_code = jobs.main(["parquet-object-sync-once"])
        restore_exit_code = jobs.main(["parquet-object-restore-once"])
    finally:
        asyncio.run(dispose_engine_for_url(database_url))

    assert export_exit_code == 0
    assert sync_exit_code == 0
    assert restore_exit_code == 0
    lines = [line for line in capsys.readouterr().out.strip().splitlines() if line]
    assert lines[-2] == "2"
    assert lines[-1] == "2"
    assert any(restore_root.glob("date=*/service=*/environment=*/part-*.parquet"))
