from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import duckdb

from lumonox_backend.services.event_store import DuckDbEventStore, EventStoreFilters


def test_duckdb_event_store_insert_filter_and_delete(tmp_path) -> None:
    store = DuckDbEventStore(str(tmp_path / "events.duckdb"))
    project_id = uuid4()
    now = datetime.now(tz=UTC)
    store.insert_rows(
        [
            {
                "project_id": project_id,
                "timestamp": now - timedelta(minutes=2),
                "received_at": now - timedelta(minutes=2),
                "sdk_version": "0.1.0",
                "type": "request",
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/ok",
                "status_code": 200,
                "latency_ms": 12.0,
                "payload": {"message": "ok"},
                "request_id": "r-1",
            },
            {
                "project_id": project_id,
                "timestamp": now - timedelta(minutes=1),
                "received_at": now - timedelta(minutes=1),
                "sdk_version": "0.1.0",
                "type": "error",
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/fail",
                "status_code": 500,
                "latency_ms": 42.0,
                "payload": {"exception_type": "ValueError"},
                "request_id": "r-2",
            },
        ]
    )
    filters = EventStoreFilters(
        project_id=project_id,
        from_timestamp=now - timedelta(minutes=5),
        to_timestamp=now,
        status_class=5,
    )
    assert store.count_events(filters) == 1
    rows = store.fetch_events(filters)
    assert len(rows) == 1
    assert int(rows[0][4]) == 500

    deleted = store.delete_events_before(cutoff=now - timedelta(seconds=90))
    assert deleted == 1


def test_duckdb_include_received_at_in_time_window_matches_recent_ingest(tmp_path) -> None:
    """Stale span ``timestamp`` (e.g. demo OTLP) must still match when ``received_at`` is recent."""
    store = DuckDbEventStore(str(tmp_path / "recv_window.duckdb"))
    project_id = uuid4()
    now = datetime.now(tz=UTC)
    stale_span_ts = now - timedelta(days=400)
    store.insert_rows(
        [
            {
                "project_id": project_id,
                "timestamp": stale_span_ts,
                "received_at": now - timedelta(seconds=20),
                "sdk_version": "otlp-http-json",
                "type": "request",
                "service_name": "api",
                "environment": "prod",
                "method": "GET",
                "path": "/checkout",
                "status_code": 503,
                "latency_ms": 50.0,
                "payload": {"trace_id": "0" * 32, "span_id": "1" * 16},
                "request_id": "0" * 32,
            },
        ]
    )
    window_from = now - timedelta(hours=1)
    window_to = now
    assert (
        store.count_events(
            EventStoreFilters(
                project_id=project_id,
                from_timestamp=window_from,
                to_timestamp=window_to,
            )
        )
        == 0
    )
    assert (
        store.count_events(
            EventStoreFilters(
                project_id=project_id,
                from_timestamp=window_from,
                to_timestamp=window_to,
                include_received_at_in_time_window=True,
            )
        )
        == 1
    )


def test_duckdb_fetch_events_with_total_slim_pagination(tmp_path) -> None:
    store = DuckDbEventStore(str(tmp_path / "events2.duckdb"))
    project_id = uuid4()
    now = datetime.now(tz=UTC)
    rows_in = []
    for i in range(5):
        rows_in.append(
            {
                "project_id": project_id,
                "timestamp": now - timedelta(minutes=10 - i),
                "received_at": now - timedelta(minutes=10 - i),
                "sdk_version": "0.1.0",
                "type": "request",
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": f"/p{i}",
                "status_code": 200,
                "latency_ms": float(i),
                "payload": {"n": i},
                "request_id": f"r-{i}",
            }
        )
    store.insert_rows(rows_in)
    filters = EventStoreFilters(
        project_id=project_id,
        from_timestamp=now - timedelta(minutes=30),
        to_timestamp=now,
    )
    total, page = store.fetch_events_with_total(
        filters, limit=2, offset=0, slim_payload=True, order_by="timestamp DESC, id DESC"
    )
    assert total == 5
    assert len(page) == 2
    total2, page2 = store.fetch_events_with_total(
        filters, limit=2, offset=2, slim_payload=True, order_by="timestamp DESC, id DESC"
    )
    assert total2 == 5
    assert len(page2) == 2


def test_duckdb_http_events_only_excludes_job_rows(tmp_path) -> None:
    store = DuckDbEventStore(str(tmp_path / "events_job.duckdb"))
    project_id = uuid4()
    now = datetime.now(tz=UTC)
    store.insert_rows(
        [
            {
                "project_id": project_id,
                "timestamp": now - timedelta(minutes=1),
                "received_at": now - timedelta(minutes=1),
                "sdk_version": "0.1.0",
                "type": "request",
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/ok",
                "status_code": 200,
                "latency_ms": 1.0,
                "payload": {},
                "request_id": "r-1",
            },
            {
                "project_id": project_id,
                "timestamp": now - timedelta(minutes=1),
                "received_at": now - timedelta(minutes=1),
                "sdk_version": "0.1.0",
                "type": "job",
                "service_name": "api",
                "environment": "test",
                "method": "JOB",
                "path": "task_a",
                "status_code": 500,
                "latency_ms": 9.0,
                "payload": {"exception_message": "x"},
                "request_id": None,
            },
        ]
    )
    filters = EventStoreFilters(
        project_id=project_id,
        from_timestamp=now - timedelta(minutes=5),
        to_timestamp=now,
        http_events_only=True,
    )
    assert store.count_events(filters) == 1
    job_filters = EventStoreFilters(
        project_id=project_id,
        from_timestamp=now - timedelta(minutes=5),
        to_timestamp=now,
        http_events_only=False,
        require_event_types=("job",),
        status_class=5,
    )
    assert store.count_events(job_filters) == 1


def test_duckdb_delete_widget_points_before_cutoff(tmp_path) -> None:
    store = DuckDbEventStore(str(tmp_path / "events_wp_cutoff.duckdb"))
    project_id = uuid4()
    now = datetime.now(tz=UTC)
    store.insert_widget_points(
        [
            {
                "project_id": project_id,
                "widget_id": "w1",
                "timestamp": now - timedelta(hours=2),
                "label": None,
                "value": 1.0,
            },
            {
                "project_id": project_id,
                "widget_id": "w1",
                "timestamp": now - timedelta(minutes=5),
                "label": None,
                "value": 2.0,
            },
        ]
    )
    deleted = store.delete_widget_points_before(
        cutoff=now - timedelta(hours=1), project_id=project_id
    )
    assert deleted == 1
    assert store.count_widget_points_for_project(project_id) == 1


def test_duckdb_widget_point_rotation_helpers(tmp_path) -> None:
    store = DuckDbEventStore(str(tmp_path / "events3.duckdb"))
    project_id = uuid4()
    now = datetime.now(tz=UTC)
    store.insert_widget_points(
        [
            {
                "project_id": project_id,
                "widget_id": "w1",
                "timestamp": now - timedelta(minutes=3),
                "label": "cpu",
                "value": 10.0,
            },
            {
                "project_id": project_id,
                "widget_id": "w1",
                "timestamp": now - timedelta(minutes=2),
                "label": "cpu",
                "value": 20.0,
            },
            {
                "project_id": project_id,
                "widget_id": "w1",
                "timestamp": now - timedelta(minutes=1),
                "label": "cpu",
                "value": 30.0,
            },
        ]
    )
    assert store.count_widget_points_for_project(project_id) == 3
    deleted = store.delete_oldest_widget_points(rows_to_delete=2, project_id=project_id)
    assert deleted == 2
    assert store.count_widget_points_for_project(project_id) == 1


def test_duckdb_event_rotation_deletes_eldest_by_event_timestamp(tmp_path) -> None:
    store = DuckDbEventStore(str(tmp_path / "events4.duckdb"))
    project_id = uuid4()
    now = datetime.now(tz=UTC)
    # The first inserted row has an old event timestamp but recent received_at,
    # mirroring backfill/late-ingest behavior.
    store.insert_rows(
        [
            {
                "project_id": project_id,
                "timestamp": now - timedelta(days=10),
                "received_at": now - timedelta(minutes=1),
                "sdk_version": "0.1.0",
                "type": "request",
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/old-event",
                "status_code": 200,
                "latency_ms": 10.0,
                "payload": {"message": "old"},
                "request_id": "r-old",
            },
            {
                "project_id": project_id,
                "timestamp": now - timedelta(minutes=5),
                "received_at": now - timedelta(days=2),
                "sdk_version": "0.1.0",
                "type": "request",
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/newer-event",
                "status_code": 200,
                "latency_ms": 12.0,
                "payload": {"message": "newer"},
                "request_id": "r-newer",
            },
        ]
    )

    deleted = store.delete_oldest_events(rows_to_delete=1, project_id=project_id)
    assert deleted == 1

    filters = EventStoreFilters(
        project_id=project_id,
        from_timestamp=now - timedelta(days=30),
        to_timestamp=now,
    )
    remaining = store.fetch_events(filters, order_by="timestamp ASC, id ASC")
    assert len(remaining) == 1
    assert remaining[0][3] == "/newer-event"


def test_duckdb_hybrid_hot_cold_reads_old_data_from_parquet(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "events_hybrid.duckdb"
    parquet_root = tmp_path / "parquet"
    monkeypatch.setenv("LUMONOX_EVENT_STORE", "duckdb")
    monkeypatch.setenv("LUMONOX_PARQUET_QUERY_ENABLED", "true")
    monkeypatch.setenv("LUMONOX_PARQUET_HOT_WINDOW_HOURS", "24")
    monkeypatch.setenv("LUMONOX_PARQUET_EXPORT_ROOT", str(parquet_root))
    store = DuckDbEventStore(str(db_path))
    project_id = uuid4()
    now = datetime.now(tz=UTC)
    old_ts = now - timedelta(hours=48)
    new_ts = now - timedelta(hours=1)
    store.insert_rows(
        [
            {
                "project_id": project_id,
                "timestamp": old_ts,
                "received_at": old_ts,
                "sdk_version": "0.1.0",
                "type": "request",
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/old",
                "status_code": 200,
                "latency_ms": 10.0,
                "payload": {},
                "request_id": "old-1",
            },
            {
                "project_id": project_id,
                "timestamp": new_ts,
                "received_at": new_ts,
                "sdk_version": "0.1.0",
                "type": "request",
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/new",
                "status_code": 200,
                "latency_ms": 12.0,
                "payload": {},
                "request_id": "new-1",
            },
        ]
    )
    day = old_ts.date().isoformat()
    partition_dir = parquet_root / f"date={day}" / "service=api" / "environment=test"
    partition_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = partition_dir / "part-test.parquet"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            "COPY (SELECT * FROM events WHERE path = '/old') TO ? (FORMAT PARQUET)",
            [str(parquet_path)],
        )
    finally:
        conn.close()
    deleted = store.delete_events_before(cutoff=now - timedelta(hours=24), project_id=project_id)
    assert deleted == 1
    filters = EventStoreFilters(
        project_id=project_id,
        from_timestamp=now - timedelta(hours=72),
        to_timestamp=now,
    )
    assert store.count_events(filters) == 2
    rows = store.fetch_events(filters, order_by="timestamp ASC, id ASC")
    assert [row[3] for row in rows] == ["/old", "/new"]


def test_duckdb_hybrid_falls_back_to_hot_store_when_no_parquet_files(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "events_hybrid_fallback.duckdb"
    monkeypatch.setenv("LUMONOX_EVENT_STORE", "duckdb")
    monkeypatch.setenv("LUMONOX_PARQUET_QUERY_ENABLED", "true")
    monkeypatch.setenv("LUMONOX_PARQUET_HOT_WINDOW_HOURS", "24")
    monkeypatch.setenv("LUMONOX_PARQUET_EXPORT_ROOT", str(tmp_path / "missing-parquet"))
    store = DuckDbEventStore(str(db_path))
    project_id = uuid4()
    now = datetime.now(tz=UTC)
    store.insert_rows(
        [
            {
                "project_id": project_id,
                "timestamp": now - timedelta(hours=72),
                "received_at": now - timedelta(hours=72),
                "sdk_version": "0.1.0",
                "type": "request",
                "service_name": "api",
                "environment": "test",
                "method": "GET",
                "path": "/legacy",
                "status_code": 200,
                "latency_ms": 20.0,
                "payload": {},
                "request_id": "legacy-1",
            }
        ]
    )
    filters = EventStoreFilters(
        project_id=project_id,
        from_timestamp=now - timedelta(days=4),
        to_timestamp=now,
    )
    assert store.count_events(filters) == 1
    rows = store.fetch_events(filters)
    assert len(rows) == 1
    assert rows[0][3] == "/legacy"


def test_list_parquet_export_files_missing_root_returns_empty(tmp_path) -> None:
    store = DuckDbEventStore(str(tmp_path / "events_list_parquet.duckdb"))
    missing = tmp_path / "no-such-parquet-root"
    assert (
        store._list_parquet_export_files(
            export_root=str(missing),
            from_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            to_timestamp=datetime(2026, 1, 3, tzinfo=UTC),
        )
        == []
    )


def test_list_parquet_export_files_inverted_date_window_returns_empty(tmp_path) -> None:
    store = DuckDbEventStore(str(tmp_path / "events_list_parquet2.duckdb"))
    root = tmp_path / "parquet-empty-window"
    root.mkdir()
    assert (
        store._list_parquet_export_files(
            export_root=str(root),
            from_timestamp=datetime(2026, 1, 5, tzinfo=UTC),
            to_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        )
        == []
    )


def test_query_scoped_events_sql_skip_timestamp_counts_full_project(tmp_path) -> None:
    """Query Explorer project-wide mode relies on ``skip_timestamp_filter``."""
    store = DuckDbEventStore(str(tmp_path / "qe_skip_ts.duckdb"))
    project_id = uuid4()
    now = datetime.now(tz=UTC)
    old = now - timedelta(days=60)
    base_row = {
        "project_id": project_id,
        "received_at": now,
        "sdk_version": "0.1.0",
        "type": "request",
        "service_name": "api",
        "environment": "test",
        "method": "GET",
        "path": "/x",
        "status_code": 200,
        "latency_ms": 10.0,
        "payload": {},
        "request_id": "r-old",
    }
    store.insert_rows(
        [
            {**base_row, "timestamp": old, "request_id": "r-old"},
            {
                **base_row,
                "timestamp": now - timedelta(minutes=1),
                "request_id": "r-new",
            },
        ]
    )
    narrow = EventStoreFilters(
        project_id=project_id,
        from_timestamp=now - timedelta(minutes=10),
        to_timestamp=now,
        http_events_only=False,
    )
    wide = EventStoreFilters(
        project_id=project_id,
        from_timestamp=now,
        to_timestamp=now,
        http_events_only=False,
        skip_timestamp_filter=True,
    )
    _cols_n, rows_n = store.query_scoped_events_sql(
        narrow, "SELECT COUNT(*)::BIGINT AS c FROM scoped_events", 50
    )
    _cols_w, rows_w = store.query_scoped_events_sql(
        wide, "SELECT COUNT(*)::BIGINT AS c FROM scoped_events", 50
    )
    assert int(rows_n[0][0]) == 1
    assert int(rows_w[0][0]) == 2
