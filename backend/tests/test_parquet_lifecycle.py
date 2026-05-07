from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb
import pytest

import autopulse_backend.services.parquet_lifecycle as parquet_lifecycle_module
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
    assert result.manifest_path is not None
    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["summary"]["dry_run"] is True
    assert any(a.get("dry_run") is True for a in manifest.get("compaction_actions", []))


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
    assert result.manifest_path is None


def test_parquet_lifecycle_returns_empty_when_event_store_not_duckdb(tmp_path: Path) -> None:
    root = tmp_path / "parquet"
    root.mkdir()
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'meta.db'}",
        event_store="sqlite",
        event_store_duckdb_path=str(tmp_path / "unused.duckdb"),
        parquet_export_root=str(root),
        parquet_lifecycle_enabled=True,
        autopulse_env="development",
    )
    result = run_parquet_lifecycle_once(settings=settings)
    assert result.compacted_partitions == 0
    assert result.manifest_path is None


def test_parquet_lifecycle_returns_empty_when_export_root_missing(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'meta.db'}",
        event_store="duckdb",
        event_store_duckdb_path=str(tmp_path / "events.duckdb"),
        parquet_export_root=str(tmp_path / "no-such-parquet-dir"),
        parquet_lifecycle_enabled=True,
        autopulse_env="development",
    )
    result = run_parquet_lifecycle_once(settings=settings)
    assert result.compacted_partitions == 0
    assert result.manifest_path is None


def test_parquet_lifecycle_returns_empty_when_export_root_is_file(tmp_path: Path) -> None:
    bogus = tmp_path / "not-a-directory"
    bogus.write_text("x", encoding="utf-8")
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'meta.db'}",
        event_store="duckdb",
        event_store_duckdb_path=str(tmp_path / "events.duckdb"),
        parquet_export_root=str(bogus),
        parquet_lifecycle_enabled=True,
        autopulse_env="development",
    )
    result = run_parquet_lifecycle_once(settings=settings)
    assert result.compacted_partitions == 0
    assert result.manifest_path is None


def test_parquet_lifecycle_skips_partition_with_unparseable_date_prefix(tmp_path: Path) -> None:
    """Malformed ``date=`` segment yields no calendar day; partition is skipped (no crash)."""
    settings = _base_settings(tmp_path, dry_run=False)
    root = Path(settings.parquet_export_root)
    bad = root / "date=not-a-date" / "service=api" / "environment=prod"
    _write_partition_file(path=bad / "part.parquet", event_id=1, timestamp=datetime.now(tz=UTC))

    result = run_parquet_lifecycle_once(settings=settings)

    assert result.compacted_partitions == 0
    assert result.retention_deleted_partitions == 0
    assert bad.exists()


def test_parquet_lifecycle_no_compaction_when_only_one_file_in_partition(tmp_path: Path) -> None:
    settings = _base_settings(tmp_path, dry_run=False)
    root = Path(settings.parquet_export_root)
    now = datetime.now(tz=UTC)
    recent_day = (now - timedelta(days=1)).date().isoformat()
    partition = root / f"date={recent_day}" / "service=api" / "environment=prod"
    _write_partition_file(path=partition / "solo.parquet", event_id=1, timestamp=now)

    result = run_parquet_lifecycle_once(settings=settings)

    assert result.compacted_partitions == 0
    assert (partition / "solo.parquet").is_file()


def test_parquet_lifecycle_retention_deletes_old_partition_with_single_file(tmp_path: Path) -> None:
    settings = _base_settings(tmp_path, dry_run=False)
    root = Path(settings.parquet_export_root)
    now = datetime.now(tz=UTC)
    old_day = (now - timedelta(days=30)).date().isoformat()
    old_partition = root / f"date={old_day}" / "service=api" / "environment=prod"
    _write_partition_file(path=old_partition / "only.parquet", event_id=1, timestamp=now)

    result = run_parquet_lifecycle_once(settings=settings)

    assert result.compacted_partitions == 0
    assert result.retention_deleted_partitions == 1
    assert not old_partition.exists()


def test_parquet_lifecycle_compaction_mismatch_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Force post-COPY row reconciliation to fail (simulated wrong count)."""
    real_connect = duckdb.connect

    class _WrongCountResult:
        def fetchone(self) -> tuple[int]:
            return (0,)

    class _ConnProxy:
        __slots__ = ("_inner",)

        def __init__(self, inner: Any) -> None:
            self._inner = inner

        def execute(self, query: object, parameters: object | None = None) -> object:
            q = query if isinstance(query, str) else str(query)
            if (
                parameters is not None
                and isinstance(parameters, list | tuple)
                and len(parameters) == 1
                and isinstance(parameters[0], str)
                and parameters[0].endswith(".tmp.parquet")
                and "read_parquet(?)" in q
            ):
                return _WrongCountResult()
            if parameters is not None:
                return self._inner.execute(query, parameters)
            return self._inner.execute(query)

        def close(self) -> None:
            self._inner.close()

    def connect_wrapped(*args: object, **kwargs: object) -> _ConnProxy:
        return _ConnProxy(real_connect(*args, **kwargs))

    monkeypatch.setattr(parquet_lifecycle_module.duckdb, "connect", connect_wrapped)

    settings = _base_settings(tmp_path, dry_run=False)
    root = Path(settings.parquet_export_root)
    now = datetime.now(tz=UTC)
    recent_day = (now - timedelta(days=1)).date().isoformat()
    partition = root / f"date={recent_day}" / "service=api" / "environment=prod"
    _write_partition_file(path=partition / "part-a.parquet", event_id=1, timestamp=now)
    _write_partition_file(path=partition / "part-b.parquet", event_id=2, timestamp=now)

    with pytest.raises(ValueError, match="parquet_lifecycle_compaction_mismatch"):
        run_parquet_lifecycle_once(settings=settings)

    assert (partition / "part-a.parquet").is_file()
    assert (partition / "part-b.parquet").is_file()
