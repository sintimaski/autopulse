from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import duckdb
from test_parquet_exporter import _base_settings, _seed_duckdb_events

from autopulse_backend.services.parquet_exporter import run_parquet_export_once
from autopulse_backend.services.parquet_object_storage import (
    run_parquet_object_storage_restore_once,
    run_parquet_object_storage_sync_once,
)


def test_object_storage_sync_and_restore_roundtrip_local_file_store(tmp_path: Path) -> None:
    settings = _base_settings(tmp_path)
    _seed_duckdb_events(Path(settings.event_store_duckdb_path))
    export_result = run_parquet_export_once(settings=settings)
    assert export_result.rows_exported == 2
    object_store_root = tmp_path / "object-store"
    restore_root = tmp_path / "restored"
    object_settings = replace(
        settings,
        parquet_object_storage_enabled=True,
        parquet_object_storage_uri=f"file://{object_store_root}",
        parquet_object_storage_prefix="snapshots",
        parquet_object_storage_verify_upload=True,
        parquet_object_storage_restore_root=str(restore_root),
    )

    sync_result = run_parquet_object_storage_sync_once(settings=object_settings)

    assert sync_result.scanned_files == 2
    assert sync_result.uploaded_files == 2
    assert sync_result.manifest_key is not None

    local_parquet_files = list(
        Path(settings.parquet_export_root).glob("date=*/service=*/environment=*/*.parquet")
    )
    assert len(local_parquet_files) == 2
    for path in local_parquet_files:
        path.unlink()

    restore_result = run_parquet_object_storage_restore_once(settings=object_settings)

    assert restore_result.restored_files == 2
    restored_files = sorted(restore_root.glob("date=*/service=*/environment=*/*.parquet"))
    assert len(restored_files) == 2
    conn = duckdb.connect()
    try:
        count_row = conn.execute(
            "SELECT COUNT(*) FROM read_parquet(?)",
            [str(restored_files[0])],
        ).fetchone()
        assert int(count_row[0] if count_row else 0) > 0
    finally:
        conn.close()


def test_object_storage_sync_is_idempotent_after_initial_upload(tmp_path: Path) -> None:
    settings = _base_settings(tmp_path)
    _seed_duckdb_events(Path(settings.event_store_duckdb_path))
    assert run_parquet_export_once(settings=settings).rows_exported == 2
    object_store_root = tmp_path / "object-store"
    object_settings = replace(
        settings,
        parquet_object_storage_enabled=True,
        parquet_object_storage_uri=f"file://{object_store_root}",
        parquet_object_storage_prefix="snapshots",
        parquet_object_storage_verify_upload=False,
    )
    first = run_parquet_object_storage_sync_once(settings=object_settings)
    second = run_parquet_object_storage_sync_once(settings=object_settings)

    assert first.uploaded_files == 2
    assert second.uploaded_files == 0
    assert second.skipped_files == 2
