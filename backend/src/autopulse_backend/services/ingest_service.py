from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.config import get_settings
from autopulse_backend.dashboard.error_grouping import (
    derived_error_group_key,
    error_group_labels,
)
from autopulse_backend.dashboard.time_window import minute_bucket
from autopulse_backend.models import Event
from autopulse_backend.repositories import events as events_repo
from autopulse_backend.repositories.aggregates import (
    ErrorGroupAggregateDelta,
    MetricBucketDelta,
    upsert_error_group_aggregates,
    upsert_metric_buckets,
)
from autopulse_backend.schemas import IngestBatchRequest, event_payload


async def persist_ingest_batch(
    *,
    session: AsyncSession,
    project_id: UUID,
    batch: IngestBatchRequest,
    received_at: datetime,
) -> int:
    settings = get_settings()
    sdk_version = batch.sdk_version or settings.default_sdk_version
    rows = [
        Event(
            project_id=project_id,
            timestamp=event.timestamp,
            received_at=received_at,
            sdk_version=sdk_version,
            type=event.type,
            service_name=event.service_name,
            environment=event.environment,
            method=event.method,
            path=event.path,
            status_code=event.status_code,
            latency_ms=event.latency_ms,
            payload=event_payload(event),
            request_id=event.request_id,
        )
        for event in batch.events
    ]
    accepted = await events_repo.insert_ingest_events(session, rows)
    metric_bucket_deltas, error_group_deltas = _build_aggregate_deltas(
        project_id=project_id,
        rows=rows,
    )
    await upsert_metric_buckets(session, metric_bucket_deltas)
    await upsert_error_group_aggregates(session, error_group_deltas)
    return accepted


def _build_aggregate_deltas(
    *, project_id: UUID, rows: list[Event]
) -> tuple[list[MetricBucketDelta], list[ErrorGroupAggregateDelta]]:
    metric_by_key: dict[tuple[datetime, str, str], MetricBucketDelta] = {}
    error_group_by_key: dict[str, ErrorGroupAggregateDelta] = {}
    for row in rows:
        bucket_key = (
            minute_bucket(row.timestamp),
            row.service_name or "unknown",
            row.environment or "unknown",
        )
        existing_metric = metric_by_key.get(bucket_key)
        is_error = row.type == "error" or row.status_code >= 500
        status_class = int(row.status_code or 0) // 100
        metric_increment = MetricBucketDelta(
            project_id=project_id,
            minute_start=bucket_key[0],
            service_name=bucket_key[1],
            environment=bucket_key[2],
            request_count=1,
            error_count=1 if is_error else 0,
            latency_total_ms=float(row.latency_ms or 0.0),
            count_2xx=1 if status_class == 2 else 0,
            count_3xx=1 if status_class == 3 else 0,
            count_4xx=1 if status_class == 4 else 0,
            count_5xx=1 if status_class == 5 else 0,
        )
        if existing_metric is None:
            metric_by_key[bucket_key] = metric_increment
        else:
            metric_by_key[bucket_key] = MetricBucketDelta(
                project_id=project_id,
                minute_start=existing_metric.minute_start,
                service_name=existing_metric.service_name,
                environment=existing_metric.environment,
                request_count=existing_metric.request_count + metric_increment.request_count,
                error_count=existing_metric.error_count + metric_increment.error_count,
                latency_total_ms=(
                    existing_metric.latency_total_ms + metric_increment.latency_total_ms
                ),
                count_2xx=existing_metric.count_2xx + metric_increment.count_2xx,
                count_3xx=existing_metric.count_3xx + metric_increment.count_3xx,
                count_4xx=existing_metric.count_4xx + metric_increment.count_4xx,
                count_5xx=existing_metric.count_5xx + metric_increment.count_5xx,
            )

        if not is_error:
            continue
        payload_dict = row.payload if isinstance(row.payload, dict) else {}
        group_key = derived_error_group_key(payload_dict, row.path)
        exception_type = payload_dict.get("exception_type")
        message = payload_dict.get("exception_message")
        stack_trace = payload_dict.get("stack_trace")
        label_exception, label_message, label_stack = error_group_labels(
            row.path,
            int(row.status_code or 0),
            exception_type if isinstance(exception_type, str) else None,
            message if isinstance(message, str) else None,
            stack_trace if isinstance(stack_trace, str) else None,
        )
        existing_error_group = error_group_by_key.get(group_key)
        delta = ErrorGroupAggregateDelta(
            project_id=project_id,
            group_key=group_key,
            path=row.path,
            exception_type=label_exception,
            message=label_message,
            sample_stack_trace=label_stack,
            count=1,
            first_seen=row.timestamp,
            last_seen=row.timestamp,
        )
        if existing_error_group is None:
            error_group_by_key[group_key] = delta
            continue
        error_group_by_key[group_key] = ErrorGroupAggregateDelta(
            project_id=project_id,
            group_key=group_key,
            path=(
                delta.path
                if delta.last_seen >= existing_error_group.last_seen
                else existing_error_group.path
            ),
            exception_type=(
                delta.exception_type
                if delta.last_seen >= existing_error_group.last_seen
                else existing_error_group.exception_type
            ),
            message=(
                delta.message
                if delta.last_seen >= existing_error_group.last_seen
                else existing_error_group.message
            ),
            sample_stack_trace=(
                delta.sample_stack_trace
                if delta.last_seen >= existing_error_group.last_seen
                else existing_error_group.sample_stack_trace
            ),
            count=existing_error_group.count + 1,
            first_seen=min(existing_error_group.first_seen, delta.first_seen),
            last_seen=max(existing_error_group.last_seen, delta.last_seen),
        )
    return list(metric_by_key.values()), list(error_group_by_key.values())
