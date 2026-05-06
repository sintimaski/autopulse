from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb

from autopulse_backend.core.config import Settings, get_settings
from autopulse_backend.metrics import service_metrics


def _sql_string_literal(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _compact_ts(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _leaf_partitions(export_root: Path) -> list[Path]:
    return sorted(
        path.resolve()
        for path in export_root.glob("date=*/service=*/environment=*")
        if path.is_dir()
    )


def _partition_date(path: Path) -> date | None:
    for part in path.parts:
        if part.startswith("date="):
            raw = part.split("=", 1)[1].strip()
            if not raw:
                return None
            try:
                return date.fromisoformat(raw)
            except ValueError:
                return None
    return None


def _parquet_files(partition_dir: Path) -> list[Path]:
    return sorted(path.resolve() for path in partition_dir.glob("*.parquet") if path.is_file())


def _count_all_parquet(export_root: Path) -> tuple[int, int]:
    count = 0
    total_bytes = 0
    for path in export_root.glob("date=*/service=*/environment=*/*.parquet"):
        if not path.is_file():
            continue
        count += 1
        total_bytes += int(path.stat().st_size)
    return count, total_bytes


@dataclass(frozen=True, slots=True)
class ParquetLifecycleRunResult:
    compacted_partitions: int
    retention_deleted_partitions: int
    retention_planned_partitions: int
    verified_files: int
    files_before: int
    files_after: int
    bytes_before: int
    bytes_after: int
    dry_run: bool
    manifest_path: str | None


def run_parquet_lifecycle_once(*, settings: Settings | None = None) -> ParquetLifecycleRunResult:
    resolved = settings or get_settings()
    dry_run = bool(resolved.parquet_lifecycle_dry_run)
    if not resolved.parquet_lifecycle_enabled:
        return ParquetLifecycleRunResult(0, 0, 0, 0, 0, 0, 0, 0, dry_run, None)
    if resolved.event_store != "duckdb":
        return ParquetLifecycleRunResult(0, 0, 0, 0, 0, 0, 0, 0, dry_run, None)
    export_root = Path(resolved.parquet_export_root).expanduser().resolve()
    if not export_root.is_dir():
        return ParquetLifecycleRunResult(0, 0, 0, 0, 0, 0, 0, 0, dry_run, None)

    files_before, bytes_before = _count_all_parquet(export_root)
    now = datetime.now(tz=UTC)
    retention_cutoff = (
        now - timedelta(days=max(1, int(resolved.parquet_lifecycle_retention_days)))
    ).date()
    min_files = max(2, int(resolved.parquet_lifecycle_compaction_min_files))
    verify_n = max(1, int(resolved.parquet_lifecycle_verify_sample_size))
    run_token = _compact_ts(now)

    compacted_partitions = 0
    retention_deleted_partitions = 0
    retention_planned_partitions = 0
    verified_files = 0
    compaction_actions: list[dict[str, object]] = []
    retention_actions: list[dict[str, object]] = []

    conn = duckdb.connect()
    try:
        for partition_dir in _leaf_partitions(export_root):
            day = _partition_date(partition_dir)
            if day is None:
                continue
            files = _parquet_files(partition_dir)
            if len(files) >= min_files:
                files_sql = ",".join(_sql_string_literal(str(path)) for path in files)
                before_count_row = conn.execute(
                    f"SELECT COUNT(*) FROM read_parquet([{files_sql}], hive_partitioning=1)"  # nosec B608
                ).fetchone()
                before_count = int(before_count_row[0] if before_count_row else 0)
                temp_path = partition_dir / f".compact-{run_token}.tmp.parquet"
                final_path = partition_dir / f"compact-{run_token}.parquet"
                read_src = (
                    f"SELECT * FROM read_parquet([{files_sql}], "
                    "hive_partitioning=1) ORDER BY timestamp, id"  # nosec B608
                )
                conn.execute(
                    "COPY ("
                    + read_src
                    + ") TO "
                    + _sql_string_literal(str(temp_path.resolve()))
                    + " (FORMAT PARQUET, COMPRESSION ZSTD)"
                )
                after_count_row = conn.execute(
                    "SELECT COUNT(*) FROM read_parquet(?)",
                    [str(temp_path.resolve())],
                ).fetchone()
                after_count = int(after_count_row[0] if after_count_row else 0)
                if after_count != before_count:
                    temp_path.unlink(missing_ok=True)
                    raise ValueError(
                        "parquet_lifecycle_compaction_mismatch "
                        f"(partition={partition_dir} expected={before_count} got={after_count})"
                    )
                if dry_run:
                    temp_path.unlink(missing_ok=True)
                else:
                    temp_path.replace(final_path)
                    for old in files:
                        old.unlink(missing_ok=True)
                compacted_partitions += 1
                compaction_actions.append(
                    {
                        "partition": str(partition_dir),
                        "input_files": len(files),
                        "rows": before_count,
                        "output_file": final_path.name,
                        "dry_run": dry_run,
                    }
                )
            if day < retention_cutoff:
                retention_planned_partitions += 1
                retention_actions.append(
                    {
                        "partition": str(partition_dir),
                        "date": day.isoformat(),
                        "deleted": not dry_run,
                    }
                )
                if not dry_run:
                    shutil.rmtree(partition_dir)
                    retention_deleted_partitions += 1

        verify_candidates = sorted(
            path.resolve()
            for path in export_root.glob("date=*/service=*/environment=*/*.parquet")
            if path.is_file()
        )
        for parquet_path in verify_candidates[:verify_n]:
            conn.execute("SELECT COUNT(*) FROM read_parquet(?)", [str(parquet_path)])
            verified_files += 1
    finally:
        conn.close()

    files_after, bytes_after = _count_all_parquet(export_root)
    summary = ParquetLifecycleRunResult(
        compacted_partitions=compacted_partitions,
        retention_deleted_partitions=retention_deleted_partitions,
        retention_planned_partitions=retention_planned_partitions,
        verified_files=verified_files,
        files_before=files_before,
        files_after=files_after,
        bytes_before=bytes_before,
        bytes_after=bytes_after,
        dry_run=dry_run,
        manifest_path=None,
    )
    state_dir = export_root / "_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = state_dir / f"lifecycle-{run_token}.json"
    payload = {
        "run_at": now.isoformat().replace("+00:00", "Z"),
        "summary": asdict(summary),
        "compaction_actions": compaction_actions,
        "retention_actions": retention_actions,
    }
    manifest_path.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    result = ParquetLifecycleRunResult(
        compacted_partitions=summary.compacted_partitions,
        retention_deleted_partitions=summary.retention_deleted_partitions,
        retention_planned_partitions=summary.retention_planned_partitions,
        verified_files=summary.verified_files,
        files_before=summary.files_before,
        files_after=summary.files_after,
        bytes_before=summary.bytes_before,
        bytes_after=summary.bytes_after,
        dry_run=summary.dry_run,
        manifest_path=str(manifest_path),
    )
    service_metrics.increment(
        "parquet.lifecycle.compacted_partitions", amount=max(0, result.compacted_partitions)
    )
    service_metrics.increment(
        "parquet.lifecycle.retention_deleted_partitions",
        amount=max(0, result.retention_deleted_partitions),
    )
    service_metrics.increment(
        "parquet.lifecycle.retention_planned_partitions",
        amount=max(0, result.retention_planned_partitions),
    )
    service_metrics.increment(
        "parquet.lifecycle.verified_files", amount=max(0, result.verified_files)
    )
    service_metrics.increment(
        "parquet.lifecycle.bytes_reclaimed",
        amount=max(0, result.bytes_before - result.bytes_after),
    )
    service_metrics.increment("parquet.lifecycle.runs.succeeded")
    return result
