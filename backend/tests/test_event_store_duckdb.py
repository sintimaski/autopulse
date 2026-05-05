from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from autopulse_backend.services.event_store import DuckDbEventStore, EventStoreFilters


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
