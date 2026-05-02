from __future__ import annotations

import asyncio
import secrets

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import text

from autopulse_backend.core.config import get_settings
from autopulse_backend.database import get_engine
from autopulse_backend.jobs import RetentionPressurePollHandle, SchedulerHandle
from autopulse_backend.metrics import service_metrics
from autopulse_backend.services.event_store import (
    event_store_enabled,
    try_get_duckdb_event_store,
)

router = APIRouter(tags=["system"])


def _require_internal_metrics_access(request: Request) -> None:
    settings = get_settings()
    expected = settings.internal_metrics_bearer_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Metrics endpoint is disabled.",
        )
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token or not secrets.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized metrics access",
        )


def _build_ingest_pressure_view(counters: dict[str, int]) -> dict[str, object]:
    """Summarize ingest backpressure signals operators should watch.

    Thresholds (defaults; tune with real traffic):
    - ``rate_limited_total`` > 0 while ``accepted_batches`` is flat: SDK hot loop
      or client mis-tuning; verify `INGEST_RATE_LIMIT_*`.
    - ``payload_too_large_total`` > 0: SDK batching too aggressively; check SDK
      ``batch_size_max_events`` and body scrubbing.
    - ``aggregate_worker_sync_fallback_total`` > 0: async worker queue saturated;
      ingest still served, but the async path is not keeping up.
    - ``aggregate_worker_failed_total`` > 0: inspect logs for the accompanying
      ``ingest_aggregate_worker_failed`` exception traceback.
    """
    accepted_batches = int(counters.get("ingest.accepted.batches", 0))
    accepted_events = int(counters.get("ingest.accepted.events", 0))
    rate_limited = int(counters.get("ingest.rejected.rate_limited", 0))
    batch_too_large = int(counters.get("ingest.rejected.batch_too_large", 0))
    payload_too_large_header = int(counters.get("ingest.rejected.payload_too_large", 0))
    payload_too_large_stream = int(counters.get("ingest.rejected.payload_too_large_stream", 0))
    non_https = int(counters.get("ingest.rejected.non_https", 0))
    distributed_fallback = int(counters.get("ingest.rate_limit.distributed_fallback", 0))
    enqueue_failed = int(counters.get("ingest.aggregate_worker.enqueue_failed", 0))
    queue_full = int(counters.get("ingest.aggregate_worker.queue_full", 0))
    sync_fallback = int(counters.get("ingest.aggregate_worker.sync_fallback", 0))
    worker_succeeded = int(counters.get("ingest.aggregate_worker.succeeded", 0))
    worker_failed = int(counters.get("ingest.aggregate_worker.failed", 0))
    return {
        "accepted_batches_total": accepted_batches,
        "accepted_events_total": accepted_events,
        "rate_limited_total": rate_limited,
        "batch_too_large_total": batch_too_large,
        "payload_too_large_total": payload_too_large_header + payload_too_large_stream,
        "payload_too_large_header_total": payload_too_large_header,
        "payload_too_large_stream_total": payload_too_large_stream,
        "non_https_rejected_total": non_https,
        "distributed_rate_limit_fallback_total": distributed_fallback,
        "aggregate_worker_enqueue_failed_total": enqueue_failed,
        "aggregate_worker_queue_full_total": queue_full,
        "aggregate_worker_sync_fallback_total": sync_fallback,
        "aggregate_worker_succeeded_total": worker_succeeded,
        "aggregate_worker_failed_total": worker_failed,
    }


def _build_metrics_snapshot(request: Request) -> dict[str, object]:
    settings = get_settings()
    scheduler = getattr(request.app.state, "_autopulse_scheduler", None)
    pressure = getattr(request.app.state, "_autopulse_retention_pressure_poll", None)
    tick_task = getattr(request.app.state, "_autopulse_dashboard_ws_tick_task", None)
    aggregate_worker = getattr(request.app.state, "_autopulse_ingest_aggregate_worker", None)
    dashboard_ws_tick_running = isinstance(tick_task, asyncio.Task) and not tick_task.done()
    duckdb_metrics: dict[str, object] = {}
    if event_store_enabled(settings):
        store = try_get_duckdb_event_store()
        if store is not None:
            size_bytes = int(store.file_size_bytes())
            cap_mb = settings.embedded_sqlite_max_db_file_mb
            duckdb_metrics = {
                "path": settings.event_store_duckdb_path,
                "file_size_bytes": size_bytes,
                "file_size_mb": round(size_bytes / (1024 * 1024), 3),
                "max_size_mb": int(cap_mb) if cap_mb is not None else None,
                "usage_ratio": (
                    float(size_bytes) / float(int(cap_mb) * 1024 * 1024)
                    if cap_mb is not None and int(cap_mb) > 0
                    else None
                ),
            }
    counters = service_metrics.snapshot()
    aggregate_queue_depth: int | None = None
    aggregate_queue_max_size: int | None = None
    try:
        if aggregate_worker is not None and hasattr(aggregate_worker, "queue"):
            aggregate_queue_depth = aggregate_worker.queue.qsize()
            max_size = aggregate_worker.queue.maxsize
            aggregate_queue_max_size = int(max_size) if max_size else None
    except Exception:  # noqa: BLE001 - best-effort telemetry
        aggregate_queue_depth = None
    return {
        "service": "autopulse-backend",
        "dashboard_ws_live_tick_seconds": settings.dashboard_ws_live_tick_seconds,
        "dashboard_ws_tick_running": dashboard_ws_tick_running,
        "scheduler_running": isinstance(scheduler, SchedulerHandle),
        "retention_pressure_poll_running": isinstance(pressure, RetentionPressurePollHandle)
        and not pressure.task.done(),
        "jobs_enable_scheduler": settings.jobs_enable_scheduler,
        "retention_pressure_poll_seconds": settings.retention_pressure_poll_seconds,
        "jobs_retention_interval_seconds": settings.jobs_retention_interval_seconds,
        "event_store": settings.event_store,
        "duckdb": duckdb_metrics if duckdb_metrics else None,
        "counters": counters,
        "jobs": service_metrics.job_snapshot(),
        "ingest_pressure": _build_ingest_pressure_view(counters),
        "ingest_aggregate_queue": {
            "enabled": settings.ingest_async_aggregate_enabled,
            "depth": aggregate_queue_depth,
            "max_size": aggregate_queue_max_size,
        },
    }


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> dict[str, str]:
    settings = get_settings()
    engine = get_engine(settings.database_url)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not ready",
        ) from exc
    return {"status": "ready"}


@router.get("/internal/metrics")
async def internal_metrics(request: Request) -> dict[str, object]:
    _require_internal_metrics_access(request)
    return _build_metrics_snapshot(request)


@router.get("/metrics")
async def prometheus_metrics(request: Request) -> Response:
    _require_internal_metrics_access(request)
    snapshot = _build_metrics_snapshot(request)
    counters = snapshot.get("counters", {})
    jobs = snapshot.get("jobs", {})
    pressure = snapshot.get("ingest_pressure", {})
    aggregate_queue = snapshot.get("ingest_aggregate_queue", {})
    lines = [
        "# TYPE autopulse_scheduler_running gauge",
        f"autopulse_scheduler_running {1 if snapshot.get('scheduler_running') else 0}",
    ]
    if isinstance(counters, dict):
        for name, value in counters.items():
            metric_name = f"autopulse_{str(name).replace('.', '_')}"
            try:
                lines.append(f"# TYPE {metric_name} counter")
                lines.append(f"{metric_name} {int(value)}")
            except (TypeError, ValueError):
                continue
    if isinstance(jobs, dict):
        for job_name, telemetry in jobs.items():
            if not isinstance(telemetry, dict):
                continue
            metric_name = f"autopulse_job_{job_name}_last_duration_ms"
            lines.append(f"# TYPE {metric_name} gauge")
            duration = telemetry.get("duration_ms", 0)
            try:
                lines.append(f"{metric_name} {int(duration)}")
            except (TypeError, ValueError):
                lines.append(f"{metric_name} 0")
    if isinstance(pressure, dict):
        for name, value in pressure.items():
            metric_name = f"autopulse_ingest_pressure_{name}"
            try:
                lines.append(f"# TYPE {metric_name} gauge")
                lines.append(f"{metric_name} {int(value)}")
            except (TypeError, ValueError):
                continue
    if isinstance(aggregate_queue, dict):
        depth = aggregate_queue.get("depth")
        max_size = aggregate_queue.get("max_size")
        if isinstance(depth, int):
            lines.append("# TYPE autopulse_ingest_aggregate_queue_depth gauge")
            lines.append(f"autopulse_ingest_aggregate_queue_depth {depth}")
        if isinstance(max_size, int) and max_size > 0:
            lines.append("# TYPE autopulse_ingest_aggregate_queue_max_size gauge")
            lines.append(f"autopulse_ingest_aggregate_queue_max_size {max_size}")
    lines.append("")
    return Response(content="\n".join(lines), media_type="text/plain; version=0.0.4")
