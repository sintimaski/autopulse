from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb

from autopulse_backend.core.config import Settings, get_settings
from autopulse_backend.metrics import service_metrics


def _safe_partition_component(raw: object) -> str:
    value = str(raw or "unknown").strip() or "unknown"
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    return cleaned[:120] or "unknown"


def _fmt_compact_ts(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _sql_string_literal(value: object) -> str:
    """Single-quoted SQL string literal (for COPY target path; not user-controlled text)."""
    return "'" + str(value).replace("'", "''") + "'"


# Watermarks at or before this are treated as "never exported" (fresh DB or legacy
# default file). Using a fixed early cutoff avoids crawling epoch→now in tiny
# ``parquet_export_window_seconds`` steps, which would never reach real event times.
_INITIAL_EXPORT_WATERMARK_CUTOFF = datetime(1971, 1, 1, tzinfo=UTC)


def _load_watermark(path: Path) -> datetime:
    if not path.is_file():
        return datetime(1970, 1, 1, tzinfo=UTC)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return datetime(1970, 1, 1, tzinfo=UTC)
    watermark_raw = raw.get("watermark")
    if not isinstance(watermark_raw, str) or not watermark_raw.strip():
        return datetime(1970, 1, 1, tzinfo=UTC)
    parsed = datetime.fromisoformat(watermark_raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _save_watermark(path: Path, *, watermark: datetime, exported_rows: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.tmp"
    payload = {
        "watermark": watermark.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "updated_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "last_exported_rows": int(exported_rows),
    }
    tmp.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    tmp.replace(path)


@dataclass(frozen=True, slots=True)
class ParquetExportRunResult:
    from_timestamp: datetime
    to_timestamp: datetime
    partitions_exported: int
    rows_exported: int
    bytes_written: int


def run_parquet_export_once(*, settings: Settings | None = None) -> ParquetExportRunResult:
    resolved = settings or get_settings()
    if not resolved.parquet_export_enabled:
        return ParquetExportRunResult(
            from_timestamp=datetime.now(tz=UTC),
            to_timestamp=datetime.now(tz=UTC),
            partitions_exported=0,
            rows_exported=0,
            bytes_written=0,
        )
    if resolved.event_store != "duckdb":
        return ParquetExportRunResult(
            from_timestamp=datetime.now(tz=UTC),
            to_timestamp=datetime.now(tz=UTC),
            partitions_exported=0,
            rows_exported=0,
            bytes_written=0,
        )
    export_root = Path(resolved.parquet_export_root).expanduser().resolve()
    state_root = export_root / "_state"
    watermark_path = state_root / "watermark.json"
    source_path = Path(resolved.event_store_duckdb_path).expanduser().resolve()
    if not source_path.is_file():
        return ParquetExportRunResult(
            from_timestamp=datetime.now(tz=UTC),
            to_timestamp=datetime.now(tz=UTC),
            partitions_exported=0,
            rows_exported=0,
            bytes_written=0,
        )
    current_watermark = _load_watermark(watermark_path)
    upper_bound = datetime.now(tz=UTC)
    max_window = timedelta(seconds=max(60, int(resolved.parquet_export_window_seconds)))
    if current_watermark >= upper_bound:
        return ParquetExportRunResult(
            from_timestamp=current_watermark,
            to_timestamp=current_watermark,
            partitions_exported=0,
            rows_exported=0,
            bytes_written=0,
        )
    # First meaningful export: default watermark is epoch; a short incremental window
    # from 1970 would miss all real events. Catch up to ``upper_bound`` in one tick.
    if current_watermark < _INITIAL_EXPORT_WATERMARK_CUTOFF:
        window_end = upper_bound
    else:
        window_end = min(upper_bound, current_watermark + max_window)
    try:
        conn = duckdb.connect(str(source_path), read_only=True)
    except duckdb.IOException as exc:
        raise RuntimeError(
            "Parquet export cannot open the DuckDB events file: another process already "
            "holds a lock (usually the API or another job using the same path). Stop that "
            "process, or run export from a host where only this job opens the file, then retry. "
            f"path={source_path}"
        ) from exc
    total_rows = 0
    total_partitions = 0
    total_bytes = 0
    try:
        partitions = conn.execute(
            """
            SELECT
                CAST(date_trunc('day', timestamp) AS DATE) AS day_bucket,
                service_name,
                environment,
                COUNT(*) AS row_count
            FROM events
            WHERE timestamp > CAST(? AS TIMESTAMP)
              AND timestamp <= CAST(? AS TIMESTAMP)
            GROUP BY 1, 2, 3
            ORDER BY 1 ASC, 2 ASC, 3 ASC
            """,
            [current_watermark.replace(tzinfo=None), window_end.replace(tzinfo=None)],
        ).fetchall()
        for day_bucket, service_name, environment, row_count in partitions:
            row_count_int = int(row_count or 0)
            if row_count_int <= 0:
                continue
            day = str(day_bucket)
            safe_service = _safe_partition_component(service_name)
            safe_environment = _safe_partition_component(environment)
            partition_dir = (
                export_root
                / f"date={day}"
                / f"service={safe_service}"
                / f"environment={safe_environment}"
            )
            partition_dir.mkdir(parents=True, exist_ok=True)
            suffix = f"{_fmt_compact_ts(current_watermark)}-{_fmt_compact_ts(window_end)}"
            final_path = partition_dir / f"part-{suffix}.parquet"
            temp_path = partition_dir / f".part-{suffix}.tmp.parquet"
            # DuckDB does not bind the COPY destination path; only the filter uses parameters.
            path_sql = _sql_string_literal(str(temp_path.resolve()))
            copy_sql = (
                "COPY ("  # nosec B608
                "SELECT * FROM events "
                "WHERE timestamp > CAST(? AS TIMESTAMP) "
                "AND timestamp <= CAST(? AS TIMESTAMP) "
                "AND CAST(date_trunc('day', timestamp) AS DATE) = CAST(? AS DATE) "
                "AND service_name = ? "
                "AND environment = ?"
                ") TO " + path_sql + " (FORMAT PARQUET, COMPRESSION ZSTD)"
            )
            conn.execute(
                copy_sql,
                [
                    current_watermark.replace(tzinfo=None),
                    window_end.replace(tzinfo=None),
                    day_bucket,
                    service_name,
                    environment,
                ],
            )
            exported_count = conn.execute(
                "SELECT COUNT(*) FROM read_parquet(?)",
                [str(temp_path)],
            ).fetchone()
            exported_count_int = int(exported_count[0] if exported_count else 0)
            if exported_count_int != row_count_int:
                temp_path.unlink(missing_ok=True)
                raise ValueError(
                    "parquet_export_reconciliation_mismatch "
                    f"(expected={row_count_int} got={exported_count_int})"
                )
            temp_path.replace(final_path)
            total_rows += row_count_int
            total_partitions += 1
            total_bytes += int(final_path.stat().st_size)
    finally:
        conn.close()
    _save_watermark(
        watermark_path,
        watermark=window_end,
        exported_rows=total_rows,
    )
    service_metrics.increment("parquet.export.rows", amount=max(0, total_rows))
    service_metrics.increment("parquet.export.partitions", amount=max(0, total_partitions))
    service_metrics.increment("parquet.export.bytes", amount=max(0, total_bytes))
    if total_partitions > 0:
        service_metrics.increment("parquet.export.runs.succeeded")
    return ParquetExportRunResult(
        from_timestamp=current_watermark,
        to_timestamp=window_end,
        partitions_exported=total_partitions,
        rows_exported=total_rows,
        bytes_written=total_bytes,
    )
