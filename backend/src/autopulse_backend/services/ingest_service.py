from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.config import get_settings
from autopulse_backend.dashboard.error_grouping import (
    derived_error_group_key,
    error_group_labels,
)
from autopulse_backend.dashboard.time_window import minute_bucket
from autopulse_backend.models import Event
from autopulse_backend.repositories import dashboard_widgets as dashboard_widgets_repo
from autopulse_backend.repositories import events as events_repo
from autopulse_backend.repositories.aggregates import (
    ErrorGroupAggregateDelta,
    MetricBucketDelta,
    upsert_error_group_aggregates,
    upsert_metric_buckets,
)
from autopulse_backend.schemas import IngestBatchRequest, event_payload
from autopulse_backend.services.infrastructure_metrics import (
    InfrastructureMetricsSampler,
)
from autopulse_backend.services.infrastructure_metrics import (
    to_widget_payload as infrastructure_to_widget_payload,
)


@dataclass(frozen=True, slots=True)
class PersistIngestResult:
    accepted: int
    metric_bucket_deltas: list[MetricBucketDelta]
    error_group_deltas: list[ErrorGroupAggregateDelta]


_infrastructure_sampler = InfrastructureMetricsSampler()


async def persist_ingest_batch(
    *,
    session: AsyncSession,
    project_id: UUID,
    batch: IngestBatchRequest,
    received_at: datetime,
    persist_aggregates: bool = True,
) -> PersistIngestResult:
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
    widget_definitions, widget_points = _extract_dashboard_widget_rows(
        project_id=project_id, rows=rows
    )
    has_infrastructure_points = any(
        isinstance(point.get("widget_id"), str) and str(point["widget_id"]).startswith("infra_")
        for point in widget_points
    )
    if not has_infrastructure_points:
        sampled = _infrastructure_sampler.sample()
        fallback_definitions, fallback_points = infrastructure_to_widget_payload(sampled)
        widget_definitions.extend(
            [
                {"project_id": project_id, "updated_at": received_at, **definition}
                for definition in fallback_definitions
            ]
        )
        widget_points.extend(
            [
                {"project_id": project_id, "timestamp": received_at, **point}
                for point in fallback_points
            ]
        )
    # Widget payload persistence must not depend on metric aggregate mode.
    # Some deployments disable inline aggregate writes and rely on workers.
    await dashboard_widgets_repo.upsert_widget_definitions(session, widget_definitions)
    await dashboard_widgets_repo.insert_widget_points(session, widget_points)
    if persist_aggregates:
        await upsert_metric_buckets(session, metric_bucket_deltas)
        await upsert_error_group_aggregates(session, error_group_deltas)
    return PersistIngestResult(
        accepted=accepted,
        metric_bucket_deltas=metric_bucket_deltas,
        error_group_deltas=error_group_deltas,
    )


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


def _as_utc_datetime(raw: object, *, fallback: datetime) -> datetime:
    if isinstance(raw, datetime):
        value = raw
    elif isinstance(raw, str):
        try:
            value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return fallback
    else:
        return fallback
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _extract_dashboard_widget_rows(
    *, project_id: UUID, rows: list[Event]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    definitions_by_id: dict[str, dict[str, object]] = {}
    points: list[dict[str, object]] = []
    for row in rows:
        payload = row.payload if isinstance(row.payload, dict) else {}
        widget_payload = payload.get("dashboard_widgets")
        if not isinstance(widget_payload, dict):
            continue
        definitions = widget_payload.get("definitions")
        if isinstance(definitions, list):
            for item in definitions:
                if not isinstance(item, dict):
                    continue
                widget_id = item.get("widget_id")
                widget_type = item.get("type")
                title = item.get("title")
                if not isinstance(widget_id, str) or not widget_id.strip():
                    continue
                if widget_type not in {
                    "card",
                    "line",
                    "bar",
                    "donut",
                    "histogram",
                    "scatter",
                    "stacked_area",
                }:
                    continue
                if not isinstance(title, str) or not title.strip():
                    continue
                definitions_by_id[widget_id] = {
                    "project_id": project_id,
                    "widget_id": widget_id,
                    "widget_type": widget_type,
                    "title": title.strip()[:255],
                    "description": (
                        str(item.get("description"))[:2000]
                        if isinstance(item.get("description"), str)
                        else None
                    ),
                    "display_order": int(item.get("order") or 100),
                    "config": item.get("config") if isinstance(item.get("config"), dict) else {},
                    "updated_at": row.timestamp,
                }
        datapoints = widget_payload.get("points")
        if isinstance(datapoints, list):
            for point in datapoints:
                if not isinstance(point, dict):
                    continue
                widget_id = point.get("widget_id")
                value = point.get("value")
                if not isinstance(widget_id, str) or not widget_id.strip():
                    continue
                if not isinstance(value, int | float):
                    continue
                points.append(
                    {
                        "project_id": project_id,
                        "widget_id": widget_id,
                        "timestamp": _as_utc_datetime(
                            point.get("timestamp"), fallback=row.timestamp
                        ),
                        "label": str(point.get("label"))[:255]
                        if isinstance(point.get("label"), str)
                        else None,
                        "value": float(value),
                    }
                )
        infra_payload = payload.get("infrastructure_metrics")
        if isinstance(infra_payload, dict):
            infra_definitions, infra_points = _extract_infrastructure_widget_rows(
                project_id=project_id,
                timestamp=row.timestamp,
                payload=infra_payload,
            )
            for definition in infra_definitions:
                definitions_by_id[str(definition["widget_id"])] = definition
            points.extend(infra_points)
    return list(definitions_by_id.values()), points


def _extract_infrastructure_widget_rows(
    *,
    project_id: UUID,
    timestamp: datetime,
    payload: dict[str, object],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    metric_specs: tuple[tuple[str, str, str, str, str, int], ...] = (
        ("host_cpu_percent", "infra_host_cpu_percent", "Host CPU", "%", "line", 500),
        (
            "host_memory_used_percent",
            "infra_host_memory_percent",
            "Host memory used",
            "%",
            "line",
            510,
        ),
        ("process_cpu_percent", "infra_process_cpu_percent", "App CPU", "%", "line", 520),
        (
            "process_memory_percent",
            "infra_process_memory_percent",
            "App memory share",
            "%",
            "line",
            530,
        ),
        (
            "process_memory_rss_bytes",
            "infra_process_memory_rss_mb",
            "App RSS memory",
            "MB",
            "line",
            540,
        ),
        ("disk_used_percent", "infra_disk_used_percent", "Host disk used", "%", "line", 550),
        ("network_bytes_recv", "infra_network_received_mb", "Network received", "MB", "line", 560),
        ("network_bytes_sent", "infra_network_sent_mb", "Network sent", "MB", "line", 570),
    )
    definitions: list[dict[str, object]] = []
    points: list[dict[str, object]] = []
    for source_key, widget_id, title, unit, widget_type, order in metric_specs:
        raw_value = payload.get(source_key)
        if not isinstance(raw_value, int | float):
            continue
        value = float(raw_value)
        if source_key.endswith("_bytes"):
            value = value / (1024 * 1024)
        definitions.append(
            {
                "project_id": project_id,
                "widget_id": widget_id,
                "widget_type": widget_type,
                "title": title,
                "description": "AutoPulse SDK host/app infrastructure metric",
                "display_order": order,
                "config": {"unit": unit},
                "updated_at": timestamp,
            }
        )
        points.append(
            {
                "project_id": project_id,
                "widget_id": widget_id,
                "timestamp": timestamp,
                "value": value,
            }
        )
    return definitions, points
