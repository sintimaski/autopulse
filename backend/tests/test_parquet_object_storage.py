from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import duckdb
import pytest
from test_parquet_exporter import _base_settings, _seed_duckdb_events

from autopulse_backend.services import parquet_object_storage as pos
from autopulse_backend.services.parquet_exporter import run_parquet_export_once
from autopulse_backend.services.parquet_object_storage import (
    run_parquet_object_storage_restore_once,
    run_parquet_object_storage_sync_once,
)


def test_object_storage_sync_verify_manifest_checksum_mismatch_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_get_bytes = pos._LocalObjectStore.get_bytes

    def get_bytes_tampered(self: pos._LocalObjectStore, key: str) -> bytes:
        if "/manifests/" in key.replace("\\", "/") and key.endswith(".json"):
            return b'{"version":1,"tampered":true}\n'
        return real_get_bytes(self, key)

    monkeypatch.setattr(pos._LocalObjectStore, "get_bytes", get_bytes_tampered)

    settings = _base_settings(tmp_path)
    _seed_duckdb_events(Path(settings.event_store_duckdb_path))
    assert run_parquet_export_once(settings=settings).rows_exported == 2
    object_store_root = tmp_path / "object-store-manifest-bad"
    object_settings = replace(
        settings,
        parquet_object_storage_enabled=True,
        parquet_object_storage_uri=f"file://{object_store_root}",
        parquet_object_storage_prefix="snapshots",
        parquet_object_storage_verify_upload=True,
    )
    with pytest.raises(ValueError, match="object_storage_manifest_checksum_mismatch"):
        run_parquet_object_storage_sync_once(settings=object_settings)


def test_object_storage_sync_verify_data_object_checksum_mismatch_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_get_bytes = pos._LocalObjectStore.get_bytes

    def get_bytes_tampered(self: pos._LocalObjectStore, key: str) -> bytes:
        norm = key.replace("\\", "/")
        if "/data/" in norm and norm.endswith(".parquet"):
            return b"not-parquet"
        return real_get_bytes(self, key)

    monkeypatch.setattr(pos._LocalObjectStore, "get_bytes", get_bytes_tampered)

    settings = _base_settings(tmp_path)
    _seed_duckdb_events(Path(settings.event_store_duckdb_path))
    assert run_parquet_export_once(settings=settings).rows_exported == 2
    object_store_root = tmp_path / "object-store-data-bad"
    object_settings = replace(
        settings,
        parquet_object_storage_enabled=True,
        parquet_object_storage_uri=f"file://{object_store_root}",
        parquet_object_storage_prefix="snapshots",
        parquet_object_storage_verify_upload=True,
    )
    with pytest.raises(ValueError, match="object_storage_checksum_mismatch"):
        run_parquet_object_storage_sync_once(settings=object_settings)


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


def test_object_storage_sync_disabled_returns_zeros(tmp_path: Path) -> None:
    settings = _base_settings(tmp_path)
    _seed_duckdb_events(Path(settings.event_store_duckdb_path))
    assert run_parquet_export_once(settings=settings).rows_exported == 2
    result = run_parquet_object_storage_sync_once(
        settings=replace(settings, parquet_object_storage_enabled=False)
    )
    assert result == pos.ParquetObjectStorageSyncResult(0, 0, 0, 0, 0, None, None)


def test_object_storage_sync_raises_when_enabled_without_uri(tmp_path: Path) -> None:
    settings = _base_settings(tmp_path)
    _seed_duckdb_events(Path(settings.event_store_duckdb_path))
    assert run_parquet_export_once(settings=settings).rows_exported == 2
    bad = replace(
        settings,
        parquet_object_storage_enabled=True,
        parquet_object_storage_uri=None,
    )
    with pytest.raises(ValueError, match="AUTOPULSE_PARQUET_OBJECT_STORAGE_URI"):
        run_parquet_object_storage_sync_once(settings=bad)


def test_object_storage_sync_empty_export_returns_zeros(tmp_path: Path) -> None:
    empty_root = tmp_path / "empty-parquet"
    empty_root.mkdir(parents=True)
    store_root = tmp_path / "object-store"
    settings = replace(
        _base_settings(tmp_path),
        parquet_export_root=str(empty_root),
        parquet_object_storage_enabled=True,
        parquet_object_storage_uri=f"file://{store_root}",
        parquet_object_storage_prefix="snapshots",
    )
    result = run_parquet_object_storage_sync_once(settings=settings)
    assert result.scanned_files == 0
    assert result.uploaded_files == 0
    assert result.manifest_key is not None
    assert result.manifest_sha256 is not None


def test_resolve_store_local_bare_path_and_s3_prefix(tmp_path: Path) -> None:
    bare = tmp_path / "local-store"
    bare.mkdir()
    local = pos._resolve_store(
        replace(
            _base_settings(tmp_path),
            parquet_object_storage_uri=str(bare),
            parquet_object_storage_prefix="  snapshots/ ",
        )
    )
    assert isinstance(local, pos._LocalObjectStore)
    assert local.root == bare.resolve()
    assert local.prefix == "snapshots"

    s3 = pos._resolve_store(
        replace(
            _base_settings(tmp_path),
            parquet_object_storage_uri="s3://my-bucket/foo/bar",
            parquet_object_storage_prefix="pfx",
        )
    )
    assert isinstance(s3, pos._S3ObjectStore)
    assert s3.bucket == "my-bucket"
    assert s3.prefix == "foo/bar/pfx"


def test_resolve_store_rejects_unsupported_scheme(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        pos._resolve_store(
            replace(
                _base_settings(tmp_path),
                parquet_object_storage_uri="https://example.com/bucket",
            )
        )


def test_manifest_continuity_raises_when_previous_manifest_missing(tmp_path: Path) -> None:
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
    assert first.manifest_key is not None
    manifest_path = object_store_root / first.manifest_key
    assert manifest_path.is_file()
    manifest_path.unlink()
    with pytest.raises(ValueError, match="object_storage_manifest_continuity"):
        run_parquet_object_storage_sync_once(settings=object_settings)


def test_restore_raises_on_checksum_mismatch(tmp_path: Path) -> None:
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
    sync = run_parquet_object_storage_sync_once(settings=object_settings)
    assert sync.manifest_key is not None
    manifest = json.loads((object_store_root / sync.manifest_key).read_text(encoding="utf-8"))
    first_file = manifest["files"][0]
    obj_key = str(first_file["object_key"])
    obj_path = object_store_root / obj_key
    obj_path.write_bytes(b"tampered")

    restore_settings = replace(
        object_settings,
        parquet_object_storage_restore_manifest_key=sync.manifest_key,
        parquet_object_storage_restore_root=str(tmp_path / "restore-out"),
    )
    with pytest.raises(ValueError, match="object_storage_restore_checksum_mismatch"):
        run_parquet_object_storage_restore_once(settings=restore_settings)


def test_restore_with_explicit_manifest_key(tmp_path: Path) -> None:
    settings = _base_settings(tmp_path)
    _seed_duckdb_events(Path(settings.event_store_duckdb_path))
    assert run_parquet_export_once(settings=settings).rows_exported == 2
    object_store_root = tmp_path / "object-store"
    restore_root = tmp_path / "restore-explicit"
    object_settings = replace(
        settings,
        parquet_object_storage_enabled=True,
        parquet_object_storage_uri=f"file://{object_store_root}",
        parquet_object_storage_prefix="snapshots",
        parquet_object_storage_verify_upload=False,
        parquet_object_storage_restore_root=str(restore_root),
    )
    sync = run_parquet_object_storage_sync_once(settings=object_settings)
    explicit = replace(
        object_settings,
        parquet_object_storage_restore_manifest_key=sync.manifest_key,
    )
    result = run_parquet_object_storage_restore_once(settings=explicit)
    assert result.manifest_key == sync.manifest_key
    assert result.restored_files == 2
    assert any(restore_root.glob("date=*/service=*/environment=*/*.parquet"))


def test_restore_disabled_returns_empty(tmp_path: Path) -> None:
    settings = _base_settings(tmp_path)
    out = run_parquet_object_storage_restore_once(
        settings=replace(settings, parquet_object_storage_enabled=False)
    )
    assert out.restored_files == 0
    assert out.manifest_key is None


def test_object_storage_sync_export_root_not_directory_returns_zeros(tmp_path: Path) -> None:
    export_root = tmp_path / "export-not-dir"
    export_root.write_text("x", encoding="utf-8")
    store_root = tmp_path / "object-store"
    settings = replace(
        _base_settings(tmp_path),
        parquet_export_root=str(export_root),
        parquet_object_storage_enabled=True,
        parquet_object_storage_uri=f"file://{store_root}",
        parquet_object_storage_prefix="snapshots",
    )
    result = run_parquet_object_storage_sync_once(settings=settings)
    assert result == pos.ParquetObjectStorageSyncResult(0, 0, 0, 0, 0, None, None)


def test_object_storage_restore_no_manifest_in_store_returns_zeros(tmp_path: Path) -> None:
    store_root = tmp_path / "empty-object-store"
    store_root.mkdir()
    restore_root = tmp_path / "restore-empty"
    settings = replace(
        _base_settings(tmp_path),
        parquet_object_storage_enabled=True,
        parquet_object_storage_uri=f"file://{store_root}",
        parquet_object_storage_prefix="snapshots",
        parquet_object_storage_restore_root=str(restore_root),
    )
    out = run_parquet_object_storage_restore_once(settings=settings)
    assert out.restored_files == 0
    assert out.manifest_key is None


def test_object_storage_sync_corrupt_state_json_recovers_and_uploads(tmp_path: Path) -> None:
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
    state_path = Path(settings.parquet_export_root) / "_state" / "object_storage_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("{not-json", encoding="utf-8")

    result = run_parquet_object_storage_sync_once(settings=object_settings)
    assert result.uploaded_files == 2
    assert result.manifest_key is not None


def test_resolve_s3_uri_missing_bucket_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="bucket"):
        pos._resolve_store(
            replace(
                _base_settings(tmp_path),
                parquet_object_storage_uri="s3:///only/path",
                parquet_object_storage_prefix="pfx",
            )
        )


def test_restore_invalid_manifest_missing_files_list_raises(tmp_path: Path) -> None:
    settings = _base_settings(tmp_path)
    store_root = tmp_path / "object-store"
    store_root.mkdir()
    bad_key = "snapshots/manifests/bad.json"
    (store_root / bad_key).parent.mkdir(parents=True, exist_ok=True)
    (store_root / bad_key).write_text(
        json.dumps({"version": 1, "created_at": "x", "files": "nope"}),
        encoding="utf-8",
    )
    bad = replace(
        settings,
        parquet_object_storage_enabled=True,
        parquet_object_storage_uri=f"file://{store_root}",
        parquet_object_storage_prefix="snapshots",
        parquet_object_storage_restore_root=str(tmp_path / "out"),
        parquet_object_storage_restore_manifest_key=bad_key,
    )
    with pytest.raises(ValueError, match="Invalid object storage manifest"):
        run_parquet_object_storage_restore_once(settings=bad)
