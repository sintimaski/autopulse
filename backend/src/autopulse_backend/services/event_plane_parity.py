from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb


def _as_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _window_sql_ts(value: datetime) -> str:
    return _as_naive_utc(value).strftime("%Y-%m-%d %H:%M:%S.%f")


def resolve_current_snapshot_duckdb_path(snapshots_root: str | Path) -> Path | None:
    root = Path(snapshots_root).expanduser().resolve()
    pointer = root / "CURRENT"
    if not pointer.is_file():
        return None
    try:
        payload = json.loads(pointer.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    snapshot_dir = str(payload.get("snapshot_dir", "")).strip()
    if not snapshot_dir:
        return None
    snapshot_path = (root / snapshot_dir).resolve()
    duckdb_path = snapshot_path / "events.duckdb"
    if not snapshot_path.is_dir():
        return None
    if not (snapshot_path / "COMPLETE").is_file():
        return None
    if not duckdb_path.is_file():
        return None
    return duckdb_path


@dataclass(frozen=True, slots=True)
class ParityQueryMismatch:
    project_id: str
    window_start: datetime
    window_end: datetime
    query_signature: str
    legacy_value: float
    plan_b_value: float
    delta: float


@dataclass(frozen=True, slots=True)
class EventPlaneParityReport:
    project_id: str
    window_start: datetime
    window_end: datetime
    legacy_db_path: Path
    snapshot_db_path: Path
    generated_at: datetime
    compared_queries: tuple[str, ...]
    mismatches: tuple[ParityQueryMismatch, ...]

    @property
    def is_match(self) -> bool:
        return not self.mismatches


_QUERY_SIGNATURES: tuple[str, ...] = (
    "overview.request_count",
    "overview.error_count",
    "overview.avg_latency_ms",
    "overview.p95_latency_ms",
)


def _read_window_summary(
    *,
    db_path: Path,
    project_id: str,
    window_start: datetime,
    window_end: datetime,
) -> dict[str, float]:
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute(
            """
            SELECT
                COUNT(*)::DOUBLE AS request_count,
                SUM(CASE WHEN type = 'error' OR status_code >= 500 THEN 1 ELSE 0 END)::DOUBLE
                    AS error_count,
                COALESCE(AVG(latency_ms), 0.0)::DOUBLE AS avg_latency_ms,
                COALESCE(quantile_cont(latency_ms, 0.95), 0.0)::DOUBLE AS p95_latency_ms
            FROM events
            WHERE project_id = ?
              AND timestamp >= CAST(? AS TIMESTAMP)
              AND timestamp <= CAST(? AS TIMESTAMP)
              AND type IN ('request', 'error')
            """,
            [
                project_id,
                _window_sql_ts(window_start),
                _window_sql_ts(window_end),
            ],
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return {signature: 0.0 for signature in _QUERY_SIGNATURES}
    return {
        "overview.request_count": float(row[0] or 0.0),
        "overview.error_count": float(row[1] or 0.0),
        "overview.avg_latency_ms": float(row[2] or 0.0),
        "overview.p95_latency_ms": float(row[3] or 0.0),
    }


def build_event_plane_parity_report(
    *,
    project_id: str,
    window_start: datetime,
    window_end: datetime,
    legacy_db_path: str | Path,
    snapshot_db_path: str | Path,
    float_tolerance: float = 0.001,
) -> EventPlaneParityReport:
    legacy_path = Path(legacy_db_path).expanduser().resolve()
    snapshot_path = Path(snapshot_db_path).expanduser().resolve()
    if not legacy_path.is_file():
        raise FileNotFoundError(f"legacy db missing: {legacy_path}")
    if not snapshot_path.is_file():
        raise FileNotFoundError(f"snapshot db missing: {snapshot_path}")
    start = _as_naive_utc(window_start)
    end = _as_naive_utc(window_end)
    if end < start:
        raise ValueError("window_end must be greater than or equal to window_start")
    legacy = _read_window_summary(
        db_path=legacy_path,
        project_id=project_id,
        window_start=start,
        window_end=end,
    )
    plan_b = _read_window_summary(
        db_path=snapshot_path,
        project_id=project_id,
        window_start=start,
        window_end=end,
    )
    mismatches: list[ParityQueryMismatch] = []
    for signature in _QUERY_SIGNATURES:
        lv = float(legacy.get(signature, 0.0))
        pv = float(plan_b.get(signature, 0.0))
        delta = pv - lv
        if abs(delta) <= float_tolerance:
            continue
        mismatches.append(
            ParityQueryMismatch(
                project_id=project_id,
                window_start=start,
                window_end=end,
                query_signature=signature,
                legacy_value=lv,
                plan_b_value=pv,
                delta=delta,
            )
        )
    return EventPlaneParityReport(
        project_id=project_id,
        window_start=start,
        window_end=end,
        legacy_db_path=legacy_path,
        snapshot_db_path=snapshot_path,
        generated_at=datetime.now(tz=UTC),
        compared_queries=_QUERY_SIGNATURES,
        mismatches=tuple(mismatches),
    )


def parity_allows_cutover(report: EventPlaneParityReport) -> bool:
    return report.is_match


def build_cutover_decision(
    *,
    project_id: str,
    window_start: datetime,
    window_end: datetime,
    legacy_db_path: str | Path,
    snapshots_root: str | Path,
    float_tolerance: float = 0.001,
) -> tuple[bool, EventPlaneParityReport]:
    snapshot_db = resolve_current_snapshot_duckdb_path(snapshots_root)
    if snapshot_db is None:
        raise FileNotFoundError(
            f"no readable CURRENT snapshot under snapshots root: {Path(snapshots_root).resolve()}"
        )
    report = build_event_plane_parity_report(
        project_id=project_id,
        window_start=window_start,
        window_end=window_end,
        legacy_db_path=legacy_db_path,
        snapshot_db_path=snapshot_db,
        float_tolerance=float_tolerance,
    )
    return parity_allows_cutover(report), report


def parity_report_to_dict(report: EventPlaneParityReport) -> dict[str, Any]:
    return {
        "project_id": report.project_id,
        "window_start": report.window_start.isoformat(),
        "window_end": report.window_end.isoformat(),
        "legacy_db_path": str(report.legacy_db_path),
        "snapshot_db_path": str(report.snapshot_db_path),
        "generated_at": report.generated_at.isoformat(),
        "is_match": report.is_match,
        "compared_queries": list(report.compared_queries),
        "mismatches": [
            {
                "project_id": mismatch.project_id,
                "window_start": mismatch.window_start.isoformat(),
                "window_end": mismatch.window_end.isoformat(),
                "query_signature": mismatch.query_signature,
                "legacy_value": mismatch.legacy_value,
                "plan_b_value": mismatch.plan_b_value,
                "delta": mismatch.delta,
            }
            for mismatch in report.mismatches
        ],
    }
