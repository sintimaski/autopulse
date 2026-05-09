from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from lumonox_backend.core.config import Settings, get_settings
from lumonox_backend.metrics import service_metrics


def _compact_ts(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _sha256_bytes(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_dumps(payload: object) -> bytes:
    return (json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")


def _collect_parquet_files(export_root: Path) -> list[Path]:
    return sorted(
        path.resolve()
        for path in export_root.glob("date=*/service=*/environment=*/*.parquet")
        if path.is_file()
    )


def _normalize_prefix(prefix: str) -> str:
    cleaned = prefix.strip().strip("/")
    if not cleaned:
        return ""
    return cleaned


def _join_key(*parts: str) -> str:
    normalized = [part.strip("/") for part in parts if part and part.strip("/")]
    return "/".join(normalized)


@dataclass(frozen=True, slots=True)
class _LocalObjectStore:
    root: Path
    prefix: str

    def _full_path(self, key: str) -> Path:
        return self.root / key

    def put_bytes(self, key: str, payload: bytes) -> None:
        target = self._full_path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.parent / f".{target.name}.tmp"
        tmp.write_bytes(payload)
        tmp.replace(target)

    def get_bytes(self, key: str) -> bytes:
        return self._full_path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._full_path(key).is_file()

    def list_keys(self, prefix: str) -> list[str]:
        base = self.root / prefix
        if not base.exists():
            return []
        return sorted(
            str(path.relative_to(self.root)).replace("\\", "/")
            for path in base.rglob("*")
            if path.is_file()
        )


@dataclass(frozen=True, slots=True)
class _S3ObjectStore:
    bucket: str
    prefix: str
    endpoint_url: str | None
    region: str | None
    access_key_id: str | None
    secret_access_key: str | None
    session_token: str | None

    def _client(self) -> Any:
        try:
            import boto3  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "S3 object storage requires boto3. Install it in the backend environment."
            ) from exc
        return boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            region_name=self.region,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            aws_session_token=self.session_token,
        )

    def put_bytes(self, key: str, payload: bytes) -> None:
        client = self._client()
        client.put_object(Bucket=self.bucket, Key=key, Body=payload)

    def get_bytes(self, key: str) -> bytes:
        client = self._client()
        obj = client.get_object(Bucket=self.bucket, Key=key)
        return bytes(obj["Body"].read())

    def exists(self, key: str) -> bool:
        client = self._client()
        try:
            client.head_object(Bucket=self.bucket, Key=key)
        except Exception:
            return False
        return True

    def list_keys(self, prefix: str) -> list[str]:
        client = self._client()
        paginator = client.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                key = item.get("Key")
                if isinstance(key, str) and key:
                    keys.append(key)
        return sorted(keys)


def _resolve_store(settings: Settings) -> _LocalObjectStore | _S3ObjectStore:
    uri = (settings.parquet_object_storage_uri or "").strip()
    if not uri:
        raise ValueError("LUMONOX_PARQUET_OBJECT_STORAGE_URI is required when enabled")
    parsed = urlparse(uri)
    if parsed.scheme in {"", "file"}:
        raw_path = parsed.path if parsed.scheme == "file" else uri
        if parsed.scheme == "file" and parsed.netloc:
            raw_path = f"/{parsed.netloc}{parsed.path}"
        root = Path(unquote(raw_path)).expanduser().resolve()
        return _LocalObjectStore(
            root=root, prefix=_normalize_prefix(settings.parquet_object_storage_prefix)
        )
    if parsed.scheme == "s3":
        bucket = (parsed.netloc or "").strip()
        if not bucket:
            raise ValueError("S3 URI must include a bucket, e.g. s3://my-bucket/path")
        uri_prefix = _normalize_prefix(unquote(parsed.path))
        config_prefix = _normalize_prefix(settings.parquet_object_storage_prefix)
        prefix = _join_key(uri_prefix, config_prefix)
        return _S3ObjectStore(
            bucket=bucket,
            prefix=prefix,
            endpoint_url=settings.parquet_object_storage_endpoint_url,
            region=settings.parquet_object_storage_region,
            access_key_id=settings.parquet_object_storage_access_key_id,
            secret_access_key=settings.parquet_object_storage_secret_access_key,
            session_token=settings.parquet_object_storage_session_token,
        )
    raise ValueError(f"Unsupported parquet object storage URI scheme: {parsed.scheme}")


def _state_path(export_root: Path) -> Path:
    return export_root / "_state" / "object_storage_state.json"


def _load_state(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return raw


def _save_state(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.tmp"
    tmp.write_text(
        json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


@dataclass(frozen=True, slots=True)
class ParquetObjectStorageSyncResult:
    scanned_files: int
    uploaded_files: int
    uploaded_bytes: int
    skipped_files: int
    verified_objects: int
    manifest_key: str | None
    manifest_sha256: str | None


@dataclass(frozen=True, slots=True)
class ParquetObjectStorageRestoreResult:
    restored_files: int
    restored_bytes: int
    manifest_key: str | None
    target_root: str


def run_parquet_object_storage_sync_once(
    *, settings: Settings | None = None
) -> ParquetObjectStorageSyncResult:
    resolved = settings or get_settings()
    if not resolved.parquet_object_storage_enabled:
        return ParquetObjectStorageSyncResult(0, 0, 0, 0, 0, None, None)
    export_root = Path(resolved.parquet_export_root).expanduser().resolve()
    if not export_root.is_dir():
        return ParquetObjectStorageSyncResult(0, 0, 0, 0, 0, None, None)
    store = _resolve_store(resolved)
    state_path = _state_path(export_root)
    state = _load_state(state_path)
    uploaded_map = state.get("uploaded_files")
    if not isinstance(uploaded_map, dict):
        uploaded_map = {}
    previous_manifest_key = state.get("last_manifest_key")
    previous_manifest_sha = state.get("last_manifest_sha256")
    if not isinstance(previous_manifest_key, str):
        previous_manifest_key = None
    if not isinstance(previous_manifest_sha, str):
        previous_manifest_sha = None
    if previous_manifest_key and not store.exists(previous_manifest_key):
        raise ValueError("object_storage_manifest_continuity_broken_missing_previous_manifest")
    parquet_files = _collect_parquet_files(export_root)
    uploaded_files = 0
    uploaded_bytes = 0
    skipped_files = 0
    verified_objects = 0
    manifest_files: list[dict[str, object]] = []
    next_uploaded_map: dict[str, str] = {}
    key_prefix = _normalize_prefix(store.prefix)
    for parquet_file in parquet_files:
        rel = parquet_file.relative_to(export_root).as_posix()
        checksum = _sha256_file(parquet_file)
        object_key = _join_key(key_prefix, "data", rel)
        next_uploaded_map[rel] = checksum
        if uploaded_map.get(rel) == checksum and store.exists(object_key):
            skipped_files += 1
        else:
            payload = parquet_file.read_bytes()
            store.put_bytes(object_key, payload)
            uploaded_files += 1
            uploaded_bytes += len(payload)
            if resolved.parquet_object_storage_verify_upload:
                echoed = store.get_bytes(object_key)
                if _sha256_bytes(echoed) != checksum:
                    raise ValueError(f"object_storage_checksum_mismatch key={object_key}")
                verified_objects += 1
        manifest_files.append(
            {
                "path": rel,
                "size_bytes": int(parquet_file.stat().st_size),
                "sha256": checksum,
                "object_key": object_key,
            }
        )
    now = datetime.now(tz=UTC)
    manifest_payload = {
        "version": 1,
        "created_at": now.isoformat().replace("+00:00", "Z"),
        "source_root": str(export_root),
        "previous_manifest_key": previous_manifest_key,
        "previous_manifest_sha256": previous_manifest_sha,
        "files": manifest_files,
    }
    manifest_bytes = _json_dumps(manifest_payload)
    manifest_sha = _sha256_bytes(manifest_bytes)
    manifest_key = _join_key(
        key_prefix,
        "manifests",
        f"object-sync-{_compact_ts(now)}-{manifest_sha[:12]}.json",
    )
    store.put_bytes(manifest_key, manifest_bytes)
    if resolved.parquet_object_storage_verify_upload:
        echoed_manifest = store.get_bytes(manifest_key)
        if _sha256_bytes(echoed_manifest) != manifest_sha:
            raise ValueError("object_storage_manifest_checksum_mismatch")
        verified_objects += 1
    _save_state(
        state_path,
        {
            "last_updated_at": now.isoformat().replace("+00:00", "Z"),
            "last_manifest_key": manifest_key,
            "last_manifest_sha256": manifest_sha,
            "uploaded_files": next_uploaded_map,
        },
    )
    service_metrics.increment("parquet.object_storage.sync.scanned_files", len(parquet_files))
    service_metrics.increment("parquet.object_storage.sync.uploaded_files", uploaded_files)
    service_metrics.increment("parquet.object_storage.sync.uploaded_bytes", uploaded_bytes)
    service_metrics.increment("parquet.object_storage.sync.verified_objects", verified_objects)
    service_metrics.increment("parquet.object_storage.sync.runs.succeeded")
    return ParquetObjectStorageSyncResult(
        scanned_files=len(parquet_files),
        uploaded_files=uploaded_files,
        uploaded_bytes=uploaded_bytes,
        skipped_files=skipped_files,
        verified_objects=verified_objects,
        manifest_key=manifest_key,
        manifest_sha256=manifest_sha,
    )


def run_parquet_object_storage_restore_once(
    *, settings: Settings | None = None
) -> ParquetObjectStorageRestoreResult:
    resolved = settings or get_settings()
    if not resolved.parquet_object_storage_enabled:
        return ParquetObjectStorageRestoreResult(
            0, 0, None, resolved.parquet_object_storage_restore_root
        )
    store = _resolve_store(resolved)
    key_prefix = _normalize_prefix(store.prefix)
    requested_manifest = (
        resolved.parquet_object_storage_restore_manifest_key or ""
    ).strip() or None
    if requested_manifest is None:
        manifest_prefix = _join_key(key_prefix, "manifests")
        candidates = [key for key in store.list_keys(manifest_prefix) if key.endswith(".json")]
        if not candidates:
            return ParquetObjectStorageRestoreResult(
                0, 0, None, resolved.parquet_object_storage_restore_root
            )
        manifest_key = candidates[-1]
    else:
        manifest_key = requested_manifest
    manifest_raw = store.get_bytes(manifest_key)
    manifest = json.loads(manifest_raw.decode("utf-8"))
    files = manifest.get("files")
    if not isinstance(files, list):
        raise ValueError("Invalid object storage manifest: files list missing")
    target_root = Path(resolved.parquet_object_storage_restore_root).expanduser().resolve()
    restored_files = 0
    restored_bytes = 0
    for entry in files:
        if not isinstance(entry, dict):
            continue
        rel_path = entry.get("path")
        obj_key = entry.get("object_key")
        expected_sha = entry.get("sha256")
        if not isinstance(rel_path, str) or not rel_path:
            continue
        if not isinstance(obj_key, str) or not obj_key:
            continue
        if not isinstance(expected_sha, str) or not expected_sha:
            continue
        payload = store.get_bytes(obj_key)
        actual_sha = _sha256_bytes(payload)
        if actual_sha != expected_sha:
            raise ValueError(f"object_storage_restore_checksum_mismatch key={obj_key}")
        out_path = target_root / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(payload)
        restored_files += 1
        restored_bytes += len(payload)
    state_dir = target_root / "_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "restored-from-object-storage.json").write_bytes(
        _json_dumps(
            {
                "restored_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
                "manifest_key": manifest_key,
                "restored_files": restored_files,
                "restored_bytes": restored_bytes,
            }
        )
    )
    service_metrics.increment("parquet.object_storage.restore.files", restored_files)
    service_metrics.increment("parquet.object_storage.restore.bytes", restored_bytes)
    service_metrics.increment("parquet.object_storage.restore.runs.succeeded")
    return ParquetObjectStorageRestoreResult(
        restored_files=restored_files,
        restored_bytes=restored_bytes,
        manifest_key=manifest_key,
        target_root=str(target_root),
    )
