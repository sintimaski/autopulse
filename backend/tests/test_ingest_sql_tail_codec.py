from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from autopulse_backend.repositories.aggregates import MetricBucketDelta
from autopulse_backend.services.ingest_sql_tail_codec import (
    decode_ingest_sql_tail_payload,
    encode_ingest_sql_tail_payload,
)


def test_sql_tail_codec_roundtrip_preserves_widget_defs_and_aggregate_deltas() -> None:
    project_id = uuid4()
    payload = encode_ingest_sql_tail_payload(
        widget_definitions=[
            {
                "project_id": project_id,
                "widget_id": "requests_per_minute",
                "widget_type": "timeseries",
                "title": "Requests/min",
                "description": None,
                "display_order": 10,
                "config": {"series": ["requests"]},
                "updated_at": datetime(2026, 5, 6, 19, 0, tzinfo=UTC),
            }
        ],
        metric_bucket_deltas=[
            MetricBucketDelta(
                project_id=project_id,
                minute_start=datetime(2026, 5, 6, 19, 0, tzinfo=UTC),
                service_name="api",
                environment="prod",
                request_count=5,
                error_count=1,
                latency_total_ms=42.0,
                count_2xx=4,
                count_3xx=0,
                count_4xx=0,
                count_5xx=1,
            )
        ],
        error_group_deltas=[],
        persist_aggregates=True,
    )
    decoded = decode_ingest_sql_tail_payload(payload)
    assert decoded.persist_aggregates is True
    assert len(decoded.widget_definitions) == 1
    assert decoded.widget_definitions[0]["project_id"] == project_id
    assert decoded.widget_definitions[0]["widget_id"] == "requests_per_minute"
    assert len(decoded.metric_bucket_deltas) == 1
    assert decoded.metric_bucket_deltas[0].project_id == project_id
    assert decoded.metric_bucket_deltas[0].request_count == 5


def test_sql_tail_codec_rejects_missing_aggregate_payload() -> None:
    with pytest.raises(ValueError):
        decode_ingest_sql_tail_payload({"widget_definitions": [], "persist_aggregates": False})
