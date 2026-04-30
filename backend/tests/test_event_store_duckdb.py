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
