from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import duckdb

from autopulse_backend.core.config import Settings
from autopulse_backend.services.parquet_exporter import run_parquet_export_once


def _base_settings(tmp_path: Path) -> Settings:
    db_path = tmp_path / "events.duckdb"
    return Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'meta.db'}",
        event_store="duckdb",
        event_store_duckdb_path=str(db_path),
        parquet_export_enabled=True,
        parquet_export_root=str(tmp_path / "parquet"),
        # Default window (900s); first run must still export events far from epoch watermark.
        parquet_export_window_seconds=900,
        autopulse_env="development",
    )


def _seed_duckdb_events(db_path: Path) -> None:
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE events (
                id BIGINT PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                received_at TIMESTAMP NOT NULL,
                sdk_version VARCHAR NOT NULL,
                type VARCHAR NOT NULL,
                service_name VARCHAR NOT NULL,
                environment VARCHAR NOT NULL,
                method VARCHAR NOT NULL,
                path VARCHAR NOT NULL,
                status_code INTEGER NOT NULL,
                latency_ms DOUBLE NOT NULL,
                payload JSON NOT NULL,
                request_id VARCHAR
            )
            """
        )
        project = str(uuid4())
        conn.executemany(
            """
            INSERT INTO events (
                id, project_id, timestamp, received_at, sdk_version, type, service_name,
                environment, method, path, status_code, latency_ms, payload, request_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    1,
                    project,
                    datetime(2026, 5, 6, 19, 5, tzinfo=UTC).replace(tzinfo=None),
                    datetime(2026, 5, 6, 19, 5, tzinfo=UTC).replace(tzinfo=None),
                    "1.0",
                    "request",
                    "api",
                    "prod",
                    "GET",
                    "/orders",
                    200,
                    12.0,
                    json.dumps({}),
                    "r1",
                ),
                (
                    2,
                    project,
                    datetime(2026, 5, 6, 19, 6, tzinfo=UTC).replace(tzinfo=None),
                    datetime(2026, 5, 6, 19, 6, tzinfo=UTC).replace(tzinfo=None),
                    "1.0",
                    "request",
                    "worker",
                    "prod",
                    "POST",
                    "/jobs/run",
                    200,
                    33.0,
                    json.dumps({}),
                    "r2",
                ),
            ],
        )
    finally:
        conn.close()


def test_parquet_exporter_writes_partitioned_files_and_updates_watermark(tmp_path: Path) -> None:
    settings = _base_settings(tmp_path)
    _seed_duckdb_events(Path(settings.event_store_duckdb_path))

    result = run_parquet_export_once(settings=settings)

    assert result.rows_exported == 2
    assert result.partitions_exported == 2
    export_root = Path(settings.parquet_export_root)
    files = list(export_root.glob("date=*/service=*/environment=*/part-*.parquet"))
    assert len(files) == 2
    watermark_path = export_root / "_state" / "watermark.json"
    assert watermark_path.is_file()
    raw = json.loads(watermark_path.read_text(encoding="utf-8"))
    assert isinstance(raw.get("watermark"), str)


def test_parquet_exporter_initial_catchup_ignores_short_window_after_epoch(tmp_path: Path) -> None:
    """Regression: epoch watermark + default window must not skip all real-world timestamps."""
    db_path = tmp_path / "events.duckdb"
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'meta.db'}",
        event_store="duckdb",
        event_store_duckdb_path=str(db_path),
        parquet_export_enabled=True,
        parquet_export_root=str(tmp_path / "parquet2"),
        parquet_export_window_seconds=900,
        autopulse_env="development",
    )
    _seed_duckdb_events(db_path)
    result = run_parquet_export_once(settings=settings)
    assert result.rows_exported == 2


def test_parquet_exporter_is_restart_safe_with_watermark(tmp_path: Path) -> None:
    settings = _base_settings(tmp_path)
    _seed_duckdb_events(Path(settings.event_store_duckdb_path))
    first = run_parquet_export_once(settings=settings)
    assert first.rows_exported == 2

    second = run_parquet_export_once(settings=replace(settings, parquet_export_window_seconds=3600))
    assert second.rows_exported == 0
    assert second.partitions_exported == 0
