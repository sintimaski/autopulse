from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb

from autopulse_backend.core.config import Settings
from autopulse_backend.services.parquet_lifecycle import run_parquet_lifecycle_once


def _write_partition_file(
    *,
    path: Path,
    event_id: int,
    timestamp: datetime,
    project_id: str = "project-1",
    service_name: str = "api",
    environment: str = "prod",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect()
    try:
        conn.execute(
            """
            CREATE TABLE events (
                id BIGINT,
                project_id VARCHAR,
                timestamp TIMESTAMP,
                received_at TIMESTAMP,
                sdk_version VARCHAR,
                type VARCHAR,
                service_name VARCHAR,
                environment VARCHAR,
                method VARCHAR,
                path VARCHAR,
                status_code INTEGER,
                latency_ms DOUBLE,
                payload JSON,
                request_id VARCHAR
            )
            """
        )
        conn.execute(
            """
            INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                event_id,
                project_id,
                timestamp.replace(tzinfo=None),
                timestamp.replace(tzinfo=None),
                "1.0",
                "request",
                service_name,
                environment,
                "GET",
                "/orders",
                200,
                12.0,
                "{}",
                f"r-{event_id}",
            ],
        )
        conn.execute(
            "COPY (SELECT * FROM events) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
            [str(path.resolve())],
        )
    finally:
        conn.close()


def _base_settings(tmp_path: Path, *, dry_run: bool = False) -> Settings:
    return Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'meta.db'}",
        event_store="duckdb",
        event_store_duckdb_path=str(tmp_path / "events.duckdb"),
        parquet_export_root=str(tmp_path / "parquet"),
        parquet_lifecycle_enabled=True,
        parquet_lifecycle_interval_seconds=3600.0,
        parquet_lifecycle_retention_days=2,
        parquet_lifecycle_dry_run=dry_run,
        parquet_lifecycle_compaction_min_files=2,
        parquet_lifecycle_verify_sample_size=10,
        autopulse_env="development",
    )


def test_parquet_lifecycle_compacts_retains_and_writes_manifest(tmp_path: Path) -> None:
    settings = _base_settings(tmp_path, dry_run=False)
    root = Path(settings.parquet_export_root)
    now = datetime.now(tz=UTC)
    old_day = (now - timedelta(days=10)).date().isoformat()
    recent_day = (now - timedelta(days=1)).date().isoformat()
    old_partition = root / f"date={old_day}" / "service=api" / "environment=prod"
    recent_partition = root / f"date={recent_day}" / "service=api" / "environment=prod"
    _write_partition_file(path=old_partition / "part-old.parquet", event_id=1, timestamp=now)
    _write_partition_file(path=recent_partition / "part-a.parquet", event_id=2, timestamp=now)
    _write_partition_file(path=recent_partition / "part-b.parquet", event_id=3, timestamp=now)

    result = run_parquet_lifecycle_once(settings=settings)

    assert result.compacted_partitions == 1
    assert result.retention_deleted_partitions == 1
    assert result.retention_planned_partitions == 1
    assert result.verified_files >= 1
    assert result.files_before >= 3
    assert result.files_after >= 1
    assert result.manifest_path is not None
    assert Path(result.manifest_path).is_file()
    assert not old_partition.exists()
    compacted_files = list(recent_partition.glob("compact-*.parquet"))
    assert len(compacted_files) == 1


def test_parquet_lifecycle_dry_run_preserves_existing_files(tmp_path: Path) -> None:
    settings = _base_settings(tmp_path, dry_run=True)
    root = Path(settings.parquet_export_root)
    now = datetime.now(tz=UTC)
    old_day = (now - timedelta(days=10)).date().isoformat()
    recent_day = (now - timedelta(days=1)).date().isoformat()
    old_partition = root / f"date={old_day}" / "service=api" / "environment=prod"
    recent_partition = root / f"date={recent_day}" / "service=api" / "environment=prod"
    _write_partition_file(path=old_partition / "part-old.parquet", event_id=1, timestamp=now)
    _write_partition_file(path=recent_partition / "part-a.parquet", event_id=2, timestamp=now)
    _write_partition_file(path=recent_partition / "part-b.parquet", event_id=3, timestamp=now)

    result = run_parquet_lifecycle_once(settings=settings)

    assert result.compacted_partitions == 1
    assert result.retention_planned_partitions == 1
    assert result.retention_deleted_partitions == 0
    assert old_partition.exists()
    assert (recent_partition / "part-a.parquet").is_file()
    assert (recent_partition / "part-b.parquet").is_file()


def test_parquet_lifecycle_returns_empty_when_disabled(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'meta.db'}",
        event_store="duckdb",
        event_store_duckdb_path=str(tmp_path / "events.duckdb"),
        parquet_export_root=str(tmp_path / "parquet"),
        parquet_lifecycle_enabled=False,
        autopulse_env="development",
    )

    result = run_parquet_lifecycle_once(settings=settings)

    assert result.compacted_partitions == 0
    assert result.retention_deleted_partitions == 0
    assert result.verified_files == 0
