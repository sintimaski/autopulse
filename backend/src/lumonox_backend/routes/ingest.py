from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from lumonox_backend.auth import ProjectContext, authenticate_project
from lumonox_backend.commercial.plan_limits import effective_ingest_rate_limit_max
from lumonox_backend.core.config import Settings, get_settings
from lumonox_backend.dashboard.routes.query_bundle import mark_project_dashboard_dirty
from lumonox_backend.database import get_db_session, get_session_maker, write_session
from lumonox_backend.ingestion.exclude_lumonox import is_lumonox_internal_path
from lumonox_backend.ingestion.limits import ingest_rate_limiter
from lumonox_backend.ingestion.otlp_traces import convert_otlp_json_to_ingest_batch
from lumonox_backend.metrics import service_metrics
from lumonox_backend.realtime import (
    DashboardUpdateMessage,
    IngestBroadcastMessage,
    project_websocket_hub,
)
from lumonox_backend.realtime.bus import (
    publish_realtime_dashboard_update,
    publish_realtime_ingest,
)
from lumonox_backend.repositories import ingest_reliability as ingest_reliability_repo
from lumonox_backend.repositories.aggregates import (
    upsert_error_group_aggregates,
    upsert_metric_buckets,
)
from lumonox_backend.repositories.runtime_controls import allow_distributed_ingest_request
from lumonox_backend.schemas import IngestBatchRequest, IngestBatchResponse
from lumonox_backend.services.ingest_aggregate_worker import (
    IngestAggregatePayload,
    enqueue_ingest_aggregate_payload,
)
from lumonox_backend.services.ingest_service import persist_ingest_batch

router = APIRouter()
logger = logging.getLogger(__name__)
_INGEST_FANOUT_TASKS_STATE_KEY = "_lumonox_ingest_fanout_tasks"


def _dashboard_realtime_fanout_enabled(settings: Settings) -> bool:
    if not settings.dashboard_realtime_enabled:
        return False
    return settings.dashboard_realtime_ws_enabled or (
        settings.dashboard_realtime_bus_backend == "postgres_notify"
    )


async def _ingest_websocket_fanout(
    *,
    project_id: UUID,
    accepted: int,
    received_at: datetime,
    delta_payload: dict[str, object] | None,
) -> None:
    """Broadcast ingest + dashboard_update without blocking the ingest HTTP handler.

    Slow or stalled WebSocket clients must not delay ``POST /ingest`` or the live tick loop.
    """
    ingest_message = IngestBroadcastMessage(
        project_id=project_id,
        accepted=accepted,
        received_at=received_at,
    )
    await project_websocket_hub.publish_ingest(message=ingest_message)
    await publish_realtime_ingest(ingest_message, settings=get_settings())
    dashboard_version = await mark_project_dashboard_dirty(project_id)
    update_message = DashboardUpdateMessage(
        project_id=project_id,
        version=dashboard_version,
        reason="ingest",
        updated_slices=("overview", "requests", "errors", "widgets", "diagnosis"),
        updated_at=received_at,
        delta_payload=delta_payload,
    )
    await project_websocket_hub.publish_dashboard_update(message=update_message)
    await publish_realtime_dashboard_update(update_message, settings=get_settings())


def _get_or_create_ingest_fanout_tasks(app: FastAPI) -> set[asyncio.Task[None]]:
    existing = getattr(app.state, _INGEST_FANOUT_TASKS_STATE_KEY, None)
    if isinstance(existing, set):
        return existing
    created: set[asyncio.Task[None]] = set()
    setattr(app.state, _INGEST_FANOUT_TASKS_STATE_KEY, created)
    service_metrics.set_value("ingest.realtime_fanout.pending_tasks", 0)
    return created


def _schedule_ingest_fanout_task(
    app: FastAPI,
    *,
    project_id: UUID,
    accepted: int,
    received_at: datetime,
    delta_payload: dict[str, object] | None,
) -> None:
    tasks = _get_or_create_ingest_fanout_tasks(app)
    task = asyncio.create_task(
        _ingest_websocket_fanout(
            project_id=project_id,
            accepted=accepted,
            received_at=received_at,
            delta_payload=delta_payload,
        )
    )
    tasks.add(task)
    service_metrics.increment("ingest.realtime_fanout.scheduled")
    service_metrics.set_value("ingest.realtime_fanout.pending_tasks", len(tasks))

    def _on_done(done_task: asyncio.Task[None]) -> None:
        tasks.discard(done_task)
        service_metrics.set_value("ingest.realtime_fanout.pending_tasks", len(tasks))
        if done_task.cancelled():
            service_metrics.increment("ingest.realtime_fanout.cancelled")
            return
        exc = done_task.exception()
        if exc is not None:
            service_metrics.increment("ingest.realtime_fanout.failed")
            logger.exception(
                "ingest_websocket_fanout_failed",
                extra={"event": "ingest_websocket_fanout_failed", "project_id": str(project_id)},
                exc_info=exc,
            )
            return
        service_metrics.increment("ingest.realtime_fanout.succeeded")

    task.add_done_callback(_on_done)


async def drain_ingest_fanout_tasks(app: FastAPI, *, timeout_seconds: float = 5.0) -> None:
    tasks = _get_or_create_ingest_fanout_tasks(app)
    pending = [task for task in tasks if not task.done()]
    if not pending:
        tasks.clear()
        service_metrics.set_value("ingest.realtime_fanout.pending_tasks", 0)
        return
    for task in pending:
        task.cancel()
    try:
        await asyncio.wait_for(
            asyncio.gather(*pending, return_exceptions=True),
            timeout=max(0.1, float(timeout_seconds)),
        )
    except TimeoutError:
        logger.warning(
            "ingest_websocket_fanout_drain_timeout",
            extra={"event": "ingest_websocket_fanout_drain_timeout", "pending": len(pending)},
        )
    finally:
        tasks.clear()
        service_metrics.set_value("ingest.realtime_fanout.pending_tasks", 0)


def _is_https_request(request: Request, *, trust_forwarded_proto: bool) -> bool:
    if request.url.scheme.lower() == "https":
        return True
    if not trust_forwarded_proto:
        return False
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if not forwarded_proto:
        return False
    return any(part.strip().lower() == "https" for part in forwarded_proto.split(","))


def _build_ingest_delta_payload(
    *,
    batch: IngestBatchRequest,
    accepted: int,
    received_at: datetime,
    settings: Settings,
) -> dict[str, object] | None:
    sdk_version = batch.sdk_version or settings.default_sdk_version
    source_events = (
        [event for event in batch.events if not is_lumonox_internal_path(event.path)]
        if settings.ingest_drop_lumonox_traffic_from_db
        else list(batch.events)
    )
    if not source_events:
        return None
    requests_payload: list[dict[str, object | None]] = []
    error_count = 0
    latency_total_ms = 0.0
    count_2xx = 0
    count_3xx = 0
    count_4xx = 0
    count_5xx = 0
    for event in source_events:
        status = int(event.status_code)
        status_class = status // 100
        if status_class == 2:
            count_2xx += 1
        elif status_class == 3:
            count_3xx += 1
        elif status_class == 4:
            count_4xx += 1
        elif status_class == 5:
            count_5xx += 1
        if event.type == "error" or status >= 500:
            error_count += 1
        latency_total_ms += float(event.latency_ms)
        extra = event.model_extra or {}
        requests_payload.append(
            {
                "timestamp": event.timestamp.astimezone(UTC).isoformat(),
                "method": event.method,
                "path": event.path,
                "status_code": status,
                "latency_ms": float(event.latency_ms),
                "service_name": event.service_name,
                "environment": event.environment,
                "request_id": event.request_id,
                "log_message": (
                    extra.get("exception_message")
                    if isinstance(extra.get("exception_message"), str)
                    else None
                ),
                "event_id": None,
                "received_at": received_at.astimezone(UTC).isoformat(),
                "sdk_version": sdk_version,
                "event_kind": event.type,
                "trace_id": (
                    extra.get("trace_id") if isinstance(extra.get("trace_id"), str) else None
                ),
                "span_id": (
                    extra.get("span_id") if isinstance(extra.get("span_id"), str) else None
                ),
            }
        )
    return {
        "live_ingest": {
            "accepted": max(0, int(accepted)),
            "error_count": max(0, int(error_count)),
            "latency_total_ms": max(0.0, float(latency_total_ms)),
            "count_2xx": count_2xx,
            "count_3xx": count_3xx,
            "count_4xx": count_4xx,
            "count_5xx": count_5xx,
            "requests": requests_payload[: min(len(requests_payload), 20)],
        }
    }


@router.post("/ingest", response_model=IngestBatchResponse, status_code=status.HTTP_200_OK)
async def ingest_events(
    batch: IngestBatchRequest,
    request: Request,
    context: Annotated[ProjectContext, Depends(authenticate_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> IngestBatchResponse:
    settings = get_settings()
    idem_raw = (
        request.headers.get("Idempotency-Key") or request.headers.get("idempotency-key") or ""
    ).strip()
    idem_hash: str | None = None
    if idem_raw and len(idem_raw) <= 256:
        idem_hash = ingest_reliability_repo.hash_idempotency_key(idem_raw)
    idem_reserved = False
    if settings.ingest_require_https and not _is_https_request(
        request,
        trust_forwarded_proto=settings.ingest_trust_forwarded_proto,
    ):
        service_metrics.increment("ingest.rejected.non_https")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="HTTPS is required for ingest requests.",
        )

    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            content_length_bytes = int(content_length)
        except ValueError:
            content_length_bytes = 0
        if content_length_bytes > settings.ingest_max_request_bytes:
            service_metrics.increment("ingest.rejected.payload_too_large")
            logger.warning(
                "ingest_rejected payload_too_large",
                extra={
                    "event": "ingest_rejected",
                    "reason": "payload_too_large",
                    "content_length_bytes": content_length_bytes,
                    "ingest_max_request_bytes": settings.ingest_max_request_bytes,
                    "project_id": str(context.project_id),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    "Ingest payload exceeds max request size "
                    f"({settings.ingest_max_request_bytes} bytes)."
                ),
            )

    event_count = len(batch.events)
    if event_count > settings.ingest_max_events_per_batch:
        service_metrics.increment("ingest.rejected.batch_too_large")
        logger.warning(
            "ingest_rejected batch_too_large",
            extra={
                "event": "ingest_rejected",
                "reason": "batch_too_large",
                "event_count": event_count,
                "ingest_max_events_per_batch": settings.ingest_max_events_per_batch,
                "project_id": str(context.project_id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                "Ingest batch exceeds max event count "
                f"({settings.ingest_max_events_per_batch} events)."
            ),
        )

    if idem_hash:
        # reserve_idempotency_key reads then inserts — needs the write engine's
        # BEGIN IMMEDIATE so it never fails on a SHARED -> RESERVED upgrade.
        async with write_session(settings.database_url) as idem_session:
            completed = await ingest_reliability_repo.get_completed_idempotency_accepted(
                idem_session,
                project_id=context.project_id,
                key_hash=idem_hash,
            )
            if completed is not None:
                return IngestBatchResponse(accepted=completed)
            reservation = await ingest_reliability_repo.reserve_idempotency_key(
                idem_session,
                project_id=context.project_id,
                key_hash=idem_hash,
                ttl_hours=settings.ingest_idempotency_ttl_hours,
                stale_seconds=settings.ingest_idempotency_stale_seconds,
            )
        if reservation == "conflict":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Duplicate ingest request in flight for this Idempotency-Key.",
            )
        if reservation == "duplicate":
            read_session_maker = get_session_maker(settings.database_url)
            async with read_session_maker() as idem_session2:
                completed_again = await ingest_reliability_repo.get_completed_idempotency_accepted(
                    idem_session2,
                    project_id=context.project_id,
                    key_hash=idem_hash,
                )
            if completed_again is not None:
                return IngestBatchResponse(accepted=completed_again)
        idem_reserved = reservation == "reserved"

    effective_rate_limit = await effective_ingest_rate_limit_max(
        session,
        project_id=context.project_id,
        base_max_requests=settings.ingest_rate_limit_requests_per_window,
    )

    if settings.ingest_distributed_rate_limit_enabled:
        try:
            # Distributed limiter does delete + select + insert/update — run it on the
            # write engine so the window upsert never blocks on a lock upgrade.
            async with write_session(settings.database_url) as rl_session:
                allowed = await allow_distributed_ingest_request(
                    session=rl_session,
                    project_id=context.project_id,
                    max_requests=effective_rate_limit,
                    window_seconds=settings.ingest_rate_limit_window_seconds,
                )
        except Exception:
            # Fail open to in-memory limiter so ingest stays available when DB limiter is unhealthy.
            service_metrics.increment("ingest.rate_limit.distributed_fallback")
            allowed = ingest_rate_limiter.allow(
                project_id=context.project_id,
                max_requests=effective_rate_limit,
                window_seconds=settings.ingest_rate_limit_window_seconds,
            )
    else:
        allowed = ingest_rate_limiter.allow(
            project_id=context.project_id,
            max_requests=effective_rate_limit,
            window_seconds=settings.ingest_rate_limit_window_seconds,
        )
    if not allowed:
        if idem_reserved and idem_hash:
            async with write_session(settings.database_url) as idem_session:
                await ingest_reliability_repo.release_idempotency_reservation(
                    idem_session,
                    project_id=context.project_id,
                    key_hash=idem_hash,
                )
        service_metrics.increment("ingest.rejected.rate_limited")
        logger.warning(
            "ingest_rejected rate_limited",
            extra={
                "event": "ingest_rejected",
                "reason": "rate_limited",
                "project_id": str(context.project_id),
                "window_seconds": settings.ingest_rate_limit_window_seconds,
                "max_requests": effective_rate_limit,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Ingest rate limit exceeded. "
                f"Try again in {settings.ingest_rate_limit_window_seconds} seconds."
            ),
            headers={"Retry-After": str(settings.ingest_rate_limit_window_seconds)},
        )

    received_at = datetime.now(tz=UTC)
    try:
        persist_result = await persist_ingest_batch(
            session=session,
            project_id=context.project_id,
            batch=batch,
            received_at=received_at,
            persist_aggregates=not settings.ingest_async_aggregate_enabled,
        )
    except Exception:
        if idem_reserved and idem_hash:
            async with write_session(settings.database_url) as idem_session:
                await ingest_reliability_repo.release_idempotency_reservation(
                    idem_session,
                    project_id=context.project_id,
                    key_hash=idem_hash,
                )
        raise
    accepted = persist_result.accepted
    realtime_fanout_enabled = _dashboard_realtime_fanout_enabled(settings)
    delta_payload = (
        _build_ingest_delta_payload(
            batch=batch,
            accepted=accepted,
            received_at=received_at,
            settings=settings,
        )
        if realtime_fanout_enabled
        else None
    )
    if settings.ingest_async_aggregate_enabled:
        enqueued = enqueue_ingest_aggregate_payload(
            IngestAggregatePayload(
                metric_bucket_deltas=persist_result.metric_bucket_deltas,
                error_group_deltas=persist_result.error_group_deltas,
                enqueued_at=received_at,
            )
        )
        if not enqueued:
            service_metrics.increment("ingest.aggregate_worker.enqueue_failed")
            async with write_session(settings.database_url) as fallback_session:
                await upsert_metric_buckets(fallback_session, persist_result.metric_bucket_deltas)
                await upsert_error_group_aggregates(
                    fallback_session, persist_result.error_group_deltas
                )
            service_metrics.increment("ingest.aggregate_worker.sync_fallback")
    if realtime_fanout_enabled:
        _schedule_ingest_fanout_task(
            request.app,
            project_id=context.project_id,
            accepted=accepted,
            received_at=received_at,
            delta_payload=delta_payload,
        )
    else:
        # HTTP polling + bundle cache is the default dashboard path; bumping the
        # in-memory version keeps read-after-write freshness without WS fanout costs.
        await mark_project_dashboard_dirty(context.project_id)
    service_metrics.increment("ingest.accepted.batches")
    service_metrics.increment("ingest.accepted.events", amount=accepted)
    logger.info(
        "ingest_accepted",
        extra={
            "event": "ingest_accepted",
            "project_id": str(context.project_id),
            "accepted_events": accepted,
        },
    )
    if idem_hash:
        async with write_session(settings.database_url) as idem_session:
            await ingest_reliability_repo.complete_idempotency_key(
                idem_session,
                project_id=context.project_id,
                key_hash=idem_hash,
                accepted_events=accepted,
            )
    return IngestBatchResponse(accepted=accepted)


@router.post("/otlp/v1/traces", response_model=IngestBatchResponse, status_code=status.HTTP_200_OK)
@router.post(
    "/ingest/otlp/v1/traces", response_model=IngestBatchResponse, status_code=status.HTTP_200_OK
)
async def ingest_otlp_traces(
    request: Request,
    context: Annotated[ProjectContext, Depends(authenticate_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> IngestBatchResponse:
    try:
        payload_raw = await request.json()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid JSON body"
        ) from exc
    if not isinstance(payload_raw, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="OTLP payload must be a JSON object",
        )
    settings = get_settings()
    try:
        batch = convert_otlp_json_to_ingest_batch(
            payload_raw,
            max_events=settings.ingest_max_events_per_batch,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return await ingest_events(batch=batch, request=request, context=context, session=session)
