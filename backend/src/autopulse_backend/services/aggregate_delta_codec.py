from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from autopulse_backend.repositories.aggregates import ErrorGroupAggregateDelta, MetricBucketDelta


def metric_bucket_delta_to_dict(delta: MetricBucketDelta) -> dict[str, Any]:
    return {
        "project_id": str(delta.project_id),
        "minute_start": delta.minute_start.isoformat(),
        "service_name": delta.service_name,
        "environment": delta.environment,
        "request_count": delta.request_count,
        "error_count": delta.error_count,
        "latency_total_ms": delta.latency_total_ms,
        "count_2xx": delta.count_2xx,
        "count_3xx": delta.count_3xx,
        "count_4xx": delta.count_4xx,
        "count_5xx": delta.count_5xx,
    }


def error_group_delta_to_dict(delta: ErrorGroupAggregateDelta) -> dict[str, Any]:
    return {
        "project_id": str(delta.project_id),
        "group_key": delta.group_key,
        "path": delta.path,
        "exception_type": delta.exception_type,
        "message": delta.message,
        "sample_stack_trace": delta.sample_stack_trace,
        "count": delta.count,
        "first_seen": delta.first_seen.isoformat(),
        "last_seen": delta.last_seen.isoformat(),
    }


def encode_aggregate_payload(
    *,
    metric_bucket_deltas: list[MetricBucketDelta],
    error_group_deltas: list[ErrorGroupAggregateDelta],
) -> dict[str, Any]:
    return {
        "metric_bucket_deltas": [metric_bucket_delta_to_dict(d) for d in metric_bucket_deltas],
        "error_group_deltas": [error_group_delta_to_dict(d) for d in error_group_deltas],
    }


def _parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def metric_bucket_delta_from_dict(row: dict[str, Any]) -> MetricBucketDelta:
    return MetricBucketDelta(
        project_id=UUID(str(row["project_id"])),
        minute_start=_parse_dt(str(row["minute_start"])),
        service_name=str(row["service_name"]),
        environment=str(row["environment"]),
        request_count=int(row["request_count"]),
        error_count=int(row["error_count"]),
        latency_total_ms=float(row["latency_total_ms"]),
        count_2xx=int(row["count_2xx"]),
        count_3xx=int(row["count_3xx"]),
        count_4xx=int(row["count_4xx"]),
        count_5xx=int(row["count_5xx"]),
    )


def error_group_delta_from_dict(row: dict[str, Any]) -> ErrorGroupAggregateDelta:
    return ErrorGroupAggregateDelta(
        project_id=UUID(str(row["project_id"])),
        group_key=str(row["group_key"]),
        path=str(row["path"]),
        exception_type=row.get("exception_type"),
        message=row.get("message"),
        sample_stack_trace=row.get("sample_stack_trace"),
        count=int(row["count"]),
        first_seen=_parse_dt(str(row["first_seen"])),
        last_seen=_parse_dt(str(row["last_seen"])),
    )


def _as_dict_row(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("invalid_delta_row")
    return value


def decode_aggregate_payload(
    payload: dict[str, Any],
) -> tuple[list[MetricBucketDelta], list[ErrorGroupAggregateDelta]]:
    metrics_raw = payload.get("metric_bucket_deltas") or []
    errors_raw = payload.get("error_group_deltas") or []
    if not isinstance(metrics_raw, list) or not isinstance(errors_raw, list):
        raise ValueError("invalid_aggregate_dead_letter_payload")
    metrics = [metric_bucket_delta_from_dict(_as_dict_row(m)) for m in metrics_raw]
    errors = [error_group_delta_from_dict(_as_dict_row(e)) for e in errors_raw]
    return metrics, errors
