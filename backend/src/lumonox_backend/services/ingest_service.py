from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from lumonox_backend.core.config import Settings, get_settings
from lumonox_backend.dashboard.error_grouping import (
    derived_error_group_key,
    error_group_labels,
)
from lumonox_backend.dashboard.payload_limits import MAX_WIDGET_POINTS_PER_INGEST_BATCH
from lumonox_backend.dashboard.time_window import minute_bucket
from lumonox_backend.database import get_session_maker
from lumonox_backend.ingestion.exclude_lumonox import is_lumonox_internal_path
from lumonox_backend.metrics import service_metrics
from lumonox_backend.models import Event
from lumonox_backend.repositories import dashboard_widgets as dashboard_widgets_repo
from lumonox_backend.repositories import events as events_repo
from lumonox_backend.repositories import ingest_reliability as ingest_reliability_repo
from lumonox_backend.repositories.aggregates import (
    ErrorGroupAggregateDelta,
    MetricBucketDelta,
    upsert_error_group_aggregates,
    upsert_metric_buckets,
)
from lumonox_backend.schemas import IngestBatchRequest, event_payload
from lumonox_backend.services.event_plane_shards import (
    EventPlaneBackpressureError,
    append_events_to_shards,
)
from lumonox_backend.services.event_store import event_store_enabled, insert_events_duckdb
from lumonox_backend.services.infrastructure_metrics import (
    InfrastructureMetricsSampler,
)
from lumonox_backend.services.infrastructure_metrics import (
    to_widget_payload as infrastructure_to_widget_payload,
)
from lumonox_backend.services.ingest_sql_tail_codec import encode_ingest_sql_tail_payload
from lumonox_backend.services.ingest_widgets import (
    extract_dashboard_widget_rows,
    extract_operational_widget_rows,
)
from lumonox_backend.services.project_activity import project_has_received_any_event

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PersistIngestResult:
    accepted: int
    metric_bucket_deltas: list[MetricBucketDelta]
    error_group_deltas: list[ErrorGroupAggregateDelta]


_infrastructure_sampler = InfrastructureMetricsSampler()
_shadow_parity_lock = Lock()
_shadow_parity_window_counts: dict[tuple[str, datetime], tuple[int, int]] = {}
_SHADOW_PARITY_MAX_WINDOWS = 4096


def _extract_dashboard_widget_rows(
    *,
    project_id: UUID,
    rows: list[Event],
    max_points: int | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Backward-compatible wrapper for focused unit tests."""
    return extract_dashboard_widget_rows(project_id=project_id, rows=rows, max_points=max_points)


def _event_plane_shadow_write_enabled(*, settings: Settings) -> bool:
    return settings.event_store == "duckdb" and settings.event_plane_mode == "duckdb_log_shards"


async def _maybe_shadow_write_event_plane_shards(
    *,
    project_id: UUID,
    received_at: datetime,
    rows: list[dict[str, object]],
) -> int | None:
    settings = get_settings()
    if not rows or not _event_plane_shadow_write_enabled(settings=settings):
        return None
    started = time.perf_counter()
    try:
        result = await asyncio.to_thread(
            append_events_to_shards,
            project_id=str(project_id),
            received_at=received_at,
            rows=rows,
            settings=settings,
        )
        if result is not None:
            service_metrics.increment(
                "event_plane.shards.appended_total",
                amount=max(0, int(result.records_appended)),
            )
            if int(result.records_appended) != len(rows):
                service_metrics.increment("event_plane.shards.shadow_count_mismatch_total")
                logger.warning(
                    "event_plane_shard_count_mismatch",
                    extra={
                        "event": "event_plane_shard_count_mismatch",
                        "project_id": str(project_id),
                        "expected_rows": len(rows),
                        "appended_rows": int(result.records_appended),
                    },
                )
            elapsed_s = time.perf_counter() - started
            # ``int(ms)`` rounds sub-millisecond work down to 0, which makes operator dashboards
            # look broken even when shadow writes are happening. Treat any nonzero duration as at
            # least 1ms so totals remain a useful lower bound without adding per-batch overhead.
            elapsed_ms = 0
            if elapsed_s > 0:
                elapsed_ms = max(1, int(elapsed_s * 1000))
            service_metrics.increment("event_plane.shards.shadow_write_batches_total")
            service_metrics.increment(
                "event_plane.shards.shadow_write_ms_total",
                amount=elapsed_ms,
            )
            return int(result.records_appended)
    except EventPlaneBackpressureError as exc:
        service_metrics.increment("event_plane.shards.append_rejected_total")
        logger.warning(
            "event_plane_shard_append_rejected",
            extra={
                "event": "event_plane_shard_append_rejected",
                "project_id": str(project_id),
                "rows": len(rows),
                "reason": str(exc),
            },
        )
    except Exception as exc:
        service_metrics.increment("event_plane.shards.append_failed_total")
        logger.warning(
            "event_plane_shard_append_failed",
            extra={
                "event": "event_plane_shard_append_failed",
                "project_id": str(project_id),
                "rows": len(rows),
                "error_type": type(exc).__name__,
            },
        )
    return 0


def _record_shadow_window_parity(
    *,
    project_id: UUID,
    received_at: datetime,
    authoritative_rows: int,
    shadow_rows: int,
) -> None:
    bucket = minute_bucket(received_at)
    key = (str(project_id), bucket)
    with _shadow_parity_lock:
        previous = _shadow_parity_window_counts.get(key, (0, 0))
        merged = (
            previous[0] + max(0, int(authoritative_rows)),
            previous[1] + max(0, int(shadow_rows)),
        )
        _shadow_parity_window_counts[key] = merged
        if len(_shadow_parity_window_counts) > _SHADOW_PARITY_MAX_WINDOWS:
            oldest = min(_shadow_parity_window_counts.keys(), key=lambda item: item[1])
            _shadow_parity_window_counts.pop(oldest, None)
    if merged[0] == merged[1]:
        service_metrics.increment("event_plane.shards.shadow_window_match_total")
    else:
        service_metrics.increment("event_plane.shards.shadow_window_mismatch_total")
        logger.warning(
            "event_plane_shadow_window_mismatch",
            extra={
                "event": "event_plane_shadow_window_mismatch",
                "project_id": str(project_id),
                "window_start": bucket.isoformat(),
                "authoritative_rows": merged[0],
                "shadow_rows": merged[1],
            },
        )


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
    incoming_events = (
        [event for event in batch.events if not is_lumonox_internal_path(event.path)]
        if settings.ingest_drop_lumonox_traffic_from_db
        else list(batch.events)
    )
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
        for event in incoming_events
    ]
    duckdb_rows = [
        {
            "project_id": project_id,
            "timestamp": event.timestamp,
            "received_at": received_at,
            "sdk_version": sdk_version,
            "type": event.type,
            "service_name": event.service_name,
            "environment": event.environment,
            "method": event.method,
            "path": event.path,
            "status_code": event.status_code,
            "latency_ms": event.latency_ms,
            "payload": event_payload(event),
            "request_id": event.request_id,
        }
        for event in incoming_events
    ]
    had_events_before_batch = False
    if rows:
        had_events_before_batch = await project_has_received_any_event(
            session, project_id=project_id, settings=settings
        )
    if event_store_enabled():
        await insert_events_duckdb(duckdb_rows)
        accepted = len(duckdb_rows)
        settings = get_settings()
        if _event_plane_shadow_write_enabled(settings=settings):
            shadow_rows = await _maybe_shadow_write_event_plane_shards(
                project_id=project_id,
                received_at=received_at,
                rows=cast(list[dict[str, object]], duckdb_rows),
            )
            if shadow_rows is not None:
                _record_shadow_window_parity(
                    project_id=project_id,
                    received_at=received_at,
                    authoritative_rows=accepted,
                    shadow_rows=shadow_rows,
                )
    else:
        accepted = await events_repo.insert_ingest_events(session, rows)
    if rows and not had_events_before_batch and accepted > 0:
        service_metrics.increment("ingest.first_event_by_project_total")
    metric_bucket_deltas, error_group_deltas = _build_aggregate_deltas(
        project_id=project_id,
        rows=rows,
    )
    widget_definitions, widget_points = extract_dashboard_widget_rows(
        project_id=project_id,
        rows=rows,
        max_points=MAX_WIDGET_POINTS_PER_INGEST_BATCH,
    )
    has_infrastructure_points = any(
        isinstance(point.get("widget_id"), str) and str(point["widget_id"]).startswith("infra_")
        for point in widget_points
    )
    if not has_infrastructure_points:
        sampled = await _infrastructure_sampler.sample()
        # Only persist synthesized infra points when psutil actually refreshed; otherwise every
        # ingest batch would duplicate the same host snapshot into DuckDB.
        if _infrastructure_sampler.should_persist_fallback_widget_points():
            fallback_definitions, fallback_points = infrastructure_to_widget_payload(sampled)
            if fallback_definitions or fallback_points:
                room = max(0, MAX_WIDGET_POINTS_PER_INGEST_BATCH - len(widget_points))
                fb_pts = fallback_points[:room] if room else []
                if fallback_definitions:
                    widget_definitions.extend(
                        [
                            {"project_id": project_id, "updated_at": received_at, **definition}
                            for definition in fallback_definitions
                        ]
                    )
                # Stagger timestamps by microseconds so each metric is a distinct instant in
                # DuckDB/SQL. Without this, fallback rows share `received_at` and roll-up charts
                # show one x bucket.
                if fb_pts:
                    widget_points.extend(
                        [
                            {
                                "project_id": project_id,
                                "timestamp": received_at + timedelta(microseconds=idx),
                                **point,
                            }
                            for idx, point in enumerate(fb_pts)
                        ]
                    )
            _infrastructure_sampler.mark_fallback_widget_points_persisted()
    operational_definitions, operational_points = extract_operational_widget_rows(
        project_id=project_id,
        timestamp=received_at,
        rows=rows,
    )
    widget_definitions.extend(operational_definitions)
    op_room = max(0, MAX_WIDGET_POINTS_PER_INGEST_BATCH - len(widget_points))
    if op_room > 0:
        widget_points.extend(operational_points[:op_room])
    # Widget payload persistence must not depend on metric aggregate mode.
    # Some deployments disable inline aggregate writes and rely on workers.
    try:
        await dashboard_widgets_repo.upsert_widget_definitions(session, widget_definitions)
        await dashboard_widgets_repo.insert_widget_points(session, widget_points)
        if persist_aggregates:
            await upsert_metric_buckets(session, metric_bucket_deltas)
            await upsert_error_group_aggregates(session, error_group_deltas)
    except Exception as exc:
        service_metrics.increment("ingest.persist_sql_tail_failed")
        # Clear the request-bound SQLAlchemy transaction state before continuing with
        # a durable repair record; the original write path already failed.
        await session.rollback()
        logger.exception(
            "ingest_persist_sql_tail_failed",
            extra={
                "event": "ingest_persist_sql_tail_failed",
                "project_id": str(project_id),
                "event_store_duckdb": bool(event_store_enabled()),
            },
        )
        if not event_store_enabled():
            raise
        try:
            payload = encode_ingest_sql_tail_payload(
                widget_definitions=widget_definitions,
                metric_bucket_deltas=metric_bucket_deltas,
                error_group_deltas=error_group_deltas,
                persist_aggregates=persist_aggregates,
            )
            session_maker = get_session_maker(settings.database_url)
            async with session_maker() as repair_session:
                await ingest_reliability_repo.insert_sql_tail_repair_item(
                    repair_session,
                    project_id=project_id,
                    payload=payload,
                    last_error=f"{type(exc).__name__}: {exc}",
                )
            service_metrics.increment("ingest.sql_tail.repair_queued")
            logger.warning(
                "ingest_sql_tail_repair_queued",
                extra={
                    "event": "ingest_sql_tail_repair_queued",
                    "project_id": str(project_id),
                    "persist_aggregates": bool(persist_aggregates),
                },
            )
        except Exception:
            service_metrics.increment("ingest.sql_tail.repair_enqueue_failed")
            logger.exception(
                "ingest_sql_tail_repair_enqueue_failed",
                extra={
                    "event": "ingest_sql_tail_repair_enqueue_failed",
                    "project_id": str(project_id),
                },
            )
            raise exc from None
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
        if row.type == "job":
            continue
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
