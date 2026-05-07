from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import duckdb
import pytest

import autopulse_backend.services.parquet_exporter as parquet_exporter_module
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


def test_parquet_exporter_returns_empty_when_disabled(tmp_path: Path) -> None:
    settings = replace(_base_settings(tmp_path), parquet_export_enabled=False)
    _seed_duckdb_events(Path(settings.event_store_duckdb_path))
    result = run_parquet_export_once(settings=settings)
    assert result.rows_exported == 0
    assert result.partitions_exported == 0
    assert result.bytes_written == 0


def test_parquet_exporter_returns_empty_when_event_store_not_duckdb(tmp_path: Path) -> None:
    settings = replace(_base_settings(tmp_path), event_store="sqlite")
    result = run_parquet_export_once(settings=settings)
    assert result.rows_exported == 0


def test_parquet_exporter_returns_empty_when_duckdb_file_missing(tmp_path: Path) -> None:
    settings = replace(
        _base_settings(tmp_path),
        event_store_duckdb_path=str(tmp_path / "missing-events.duckdb"),
    )
    result = run_parquet_export_once(settings=settings)
    assert result.rows_exported == 0


def test_parquet_exporter_noop_when_watermark_already_caught_up(tmp_path: Path) -> None:
    settings = _base_settings(tmp_path)
    _seed_duckdb_events(Path(settings.event_store_duckdb_path))
    assert run_parquet_export_once(settings=settings).rows_exported == 2

    future = datetime(2099, 1, 1, tzinfo=UTC)
    state_dir = Path(settings.parquet_export_root) / "_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "watermark.json").write_text(
        json.dumps(
            {
                "watermark": future.isoformat().replace("+00:00", "Z"),
                "updated_at": future.isoformat().replace("+00:00", "Z"),
                "last_exported_rows": 0,
            },
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    result = run_parquet_export_once(settings=settings)
    assert result.rows_exported == 0
    assert result.partitions_exported == 0


def test_parquet_exporter_corrupt_watermark_json_catchup(tmp_path: Path) -> None:
    settings = _base_settings(tmp_path)
    db_path = Path(settings.event_store_duckdb_path)
    _seed_duckdb_events(db_path)
    state_dir = Path(settings.parquet_export_root) / "_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "watermark.json").write_text("{not json\n", encoding="utf-8")

    result = run_parquet_export_once(settings=settings)
    assert result.rows_exported == 2


def test_parquet_exporter_reconciliation_mismatch_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Post-COPY read_parquet row count must match pre-export aggregate."""
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

    settings = _base_settings(tmp_path)
    _seed_duckdb_events(Path(settings.event_store_duckdb_path))
    monkeypatch.setattr(parquet_exporter_module.duckdb, "connect", connect_wrapped)

    with pytest.raises(ValueError, match="parquet_export_reconciliation_mismatch"):
        run_parquet_export_once(settings=settings)


def test_parquet_exporter_sanitizes_partition_path_components(tmp_path: Path) -> None:
    db_path = tmp_path / "events.duckdb"
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'meta.db'}",
        event_store="duckdb",
        event_store_duckdb_path=str(db_path),
        parquet_export_enabled=True,
        parquet_export_root=str(tmp_path / "parquet-sanitize"),
        parquet_export_window_seconds=900,
        autopulse_env="development",
    )
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
        conn.execute(
            """
            INSERT INTO events (
                id, project_id, timestamp, received_at, sdk_version, type, service_name,
                environment, method, path, status_code, latency_ms, payload, request_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                1,
                project,
                datetime(2026, 5, 6, 19, 5, tzinfo=UTC).replace(tzinfo=None),
                datetime(2026, 5, 6, 19, 5, tzinfo=UTC).replace(tzinfo=None),
                "1.0",
                "request",
                "api/v2",
                "prod east",
                "GET",
                "/x",
                200,
                1.0,
                json.dumps({}),
                "r1",
            ],
        )
    finally:
        conn.close()

    run_parquet_export_once(settings=settings)
    root = Path(settings.parquet_export_root)
    dirs = list(root.glob("date=*/service=*/environment=*"))
    assert len(dirs) == 1
    assert "service=api_v2" in str(dirs[0])
    assert "environment=prod_east" in str(dirs[0])
