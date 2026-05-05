from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from autopulse_backend.dashboard.payload_limits import MAX_WIDGET_POINTS_PER_INGEST_BATCH
from autopulse_backend.models import Event
from autopulse_backend.services.ingest_service import _extract_dashboard_widget_rows


def test_extract_dashboard_widget_rows_caps_datapoints() -> None:
    project_id = uuid4()
    ts = datetime.now(tz=UTC)
    oversized = [
        {
            "widget_id": "w",
            "timestamp": ts.isoformat().replace("+00:00", "Z"),
            "value": float(i),
        }
        for i in range(MAX_WIDGET_POINTS_PER_INGEST_BATCH + 200)
    ]
    row = Event(
        project_id=project_id,
        timestamp=ts,
        received_at=ts,
        sdk_version="0.1.0",
        type="request",
        service_name="api",
        environment="test",
        method="GET",
        path="/x",
        status_code=200,
        latency_ms=1.0,
        payload={"dashboard_widgets": {"definitions": [], "points": oversized}},
        request_id=None,
    )
    _definitions, points = _extract_dashboard_widget_rows(project_id=project_id, rows=[row])
    assert len(points) == MAX_WIDGET_POINTS_PER_INGEST_BATCH
