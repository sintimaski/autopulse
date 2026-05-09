from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb

from lumonox_backend.services.event_plane_parity import (
    build_cutover_decision,
    build_event_plane_parity_report,
    parity_allows_cutover,
    parity_report_to_dict,
    resolve_current_snapshot_duckdb_path,
)


def _write_events_db(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(path))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                project_id VARCHAR NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                received_at TIMESTAMP NOT NULL,
                type VARCHAR NOT NULL,
                status_code INTEGER NOT NULL,
                latency_ms DOUBLE NOT NULL
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO events (
                project_id, timestamp, received_at, type, status_code, latency_ms
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    str(row["project_id"]),
                    str(row["timestamp"]),
                    str(row["received_at"]),
                    str(row["type"]),
                    int(row["status_code"]),
                    float(row["latency_ms"]),
                )
                for row in rows
            ],
        )
    finally:
        conn.close()


def test_build_event_plane_parity_report_matches_for_equal_windows(tmp_path: Path) -> None:
    project_id = "project-1"
    window_start = datetime(2026, 5, 6, 10, 0, tzinfo=UTC)
    window_end = window_start + timedelta(minutes=5)
    rows = [
        {
            "project_id": project_id,
            "timestamp": window_start.isoformat(),
            "received_at": window_start.isoformat(),
            "type": "request",
            "status_code": 200,
            "latency_ms": 12.5,
        },
        {
            "project_id": project_id,
            "timestamp": (window_start + timedelta(minutes=1)).isoformat(),
            "received_at": (window_start + timedelta(minutes=1)).isoformat(),
            "type": "error",
            "status_code": 500,
            "latency_ms": 30.0,
        },
    ]
    legacy = tmp_path / "legacy.duckdb"
    snapshot = tmp_path / "snapshot.duckdb"
    _write_events_db(legacy, rows)
    _write_events_db(snapshot, rows)

    report = build_event_plane_parity_report(
        project_id=project_id,
        window_start=window_start,
        window_end=window_end,
        legacy_db_path=legacy,
        snapshot_db_path=snapshot,
    )

    assert report.is_match is True
    assert report.mismatches == ()
    assert parity_allows_cutover(report) is True


def test_parity_report_includes_project_window_and_query_signature_on_mismatch(
    tmp_path: Path,
) -> None:
    project_id = "project-1"
    window_start = datetime(2026, 5, 6, 10, 0, tzinfo=UTC)
    window_end = window_start + timedelta(minutes=5)
    legacy = tmp_path / "legacy.duckdb"
    snapshot = tmp_path / "snapshot.duckdb"
    _write_events_db(
        legacy,
        [
            {
                "project_id": project_id,
                "timestamp": window_start.isoformat(),
                "received_at": window_start.isoformat(),
                "type": "request",
                "status_code": 200,
                "latency_ms": 5.0,
            }
        ],
    )
    _write_events_db(
        snapshot,
        [
            {
                "project_id": project_id,
                "timestamp": window_start.isoformat(),
                "received_at": window_start.isoformat(),
                "type": "request",
                "status_code": 200,
                "latency_ms": 50.0,
            },
            {
                "project_id": project_id,
                "timestamp": (window_start + timedelta(minutes=1)).isoformat(),
                "received_at": (window_start + timedelta(minutes=1)).isoformat(),
                "type": "error",
                "status_code": 500,
                "latency_ms": 100.0,
            },
        ],
    )

    report = build_event_plane_parity_report(
        project_id=project_id,
        window_start=window_start,
        window_end=window_end,
        legacy_db_path=legacy,
        snapshot_db_path=snapshot,
    )

    assert report.is_match is False
    assert parity_allows_cutover(report) is False
    assert report.mismatches
    signatures = {m.query_signature for m in report.mismatches}
    assert "overview.request_count" in signatures
    for mismatch in report.mismatches:
        assert mismatch.project_id == project_id
        assert mismatch.window_start == window_start.replace(tzinfo=None)
        assert mismatch.window_end == window_end.replace(tzinfo=None)

    as_dict = parity_report_to_dict(report)
    assert as_dict["is_match"] is False
    assert as_dict["mismatches"]


def test_build_cutover_decision_reads_current_pointer_and_blocks_on_regression(
    tmp_path: Path,
) -> None:
    project_id = "project-1"
    window_start = datetime(2026, 5, 6, 10, 0, tzinfo=UTC)
    window_end = window_start + timedelta(minutes=5)
    legacy = tmp_path / "legacy.duckdb"
    _write_events_db(
        legacy,
        [
            {
                "project_id": project_id,
                "timestamp": window_start.isoformat(),
                "received_at": window_start.isoformat(),
                "type": "request",
                "status_code": 200,
                "latency_ms": 10.0,
            }
        ],
    )
    snapshots_root = tmp_path / "snapshots"
    snapshot_dir = snapshots_root / "snapshot-20260506T100000000000Z"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_db = snapshot_dir / "events.duckdb"
    _write_events_db(
        snapshot_db,
        [
            {
                "project_id": project_id,
                "timestamp": window_start.isoformat(),
                "received_at": window_start.isoformat(),
                "type": "request",
                "status_code": 200,
                "latency_ms": 20.0,
            }
        ],
    )
    (snapshot_dir / "COMPLETE").write_text("ok\n", encoding="utf-8")
    (snapshots_root / "CURRENT").write_text(
        json.dumps(
            {
                "snapshot_version": "20260506T100000000000Z",
                "snapshot_dir": snapshot_dir.name,
                "published_at": datetime.now(tz=UTC).isoformat(),
            }
        ),
        encoding="utf-8",
    )

    resolved = resolve_current_snapshot_duckdb_path(snapshots_root)
    assert resolved == snapshot_db
    allowed, report = build_cutover_decision(
        project_id=project_id,
        window_start=window_start,
        window_end=window_end,
        legacy_db_path=legacy,
        snapshots_root=snapshots_root,
    )
    assert allowed is False
    assert report.is_match is False
