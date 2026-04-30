from __future__ import annotations

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
    scheduler = getattr(request.app.state, "_autopulse_scheduler", None)
    pressure = getattr(request.app.state, "_autopulse_retention_pressure_poll", None)
    settings = get_settings()
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
    return {
        "service": "autopulse-backend",
        "scheduler_running": isinstance(scheduler, SchedulerHandle),
        "retention_pressure_poll_running": isinstance(pressure, RetentionPressurePollHandle)
        and not pressure.task.done(),
        "jobs_enable_scheduler": settings.jobs_enable_scheduler,
        "retention_pressure_poll_seconds": settings.retention_pressure_poll_seconds,
        "jobs_retention_interval_seconds": settings.jobs_retention_interval_seconds,
        "event_store": settings.event_store,
        "duckdb": duckdb_metrics if duckdb_metrics else None,
        "counters": service_metrics.snapshot(),
        "jobs": service_metrics.job_snapshot(),
    }


@router.get("/metrics")
async def prometheus_metrics(request: Request) -> Response:
    snapshot = await internal_metrics(request)
    counters = snapshot.get("counters", {})
    jobs = snapshot.get("jobs", {})
    lines = [
        "# TYPE autopulse_scheduler_running gauge",
        f"autopulse_scheduler_running {1 if snapshot.get('scheduler_running') else 0}",
    ]
    for name, value in counters.items():
        metric_name = f"autopulse_{name.replace('.', '_')}"
        lines.append(f"# TYPE {metric_name} counter")
        lines.append(f"{metric_name} {int(value)}")
    for job_name, telemetry in jobs.items():
        metric_name = f"autopulse_job_{job_name}_last_duration_ms"
        lines.append(f"# TYPE {metric_name} gauge")
        lines.append(f"{metric_name} {int(telemetry.get('duration_ms', 0))}")
    lines.append("")
    return Response(content="\n".join(lines), media_type="text/plain; version=0.0.4")
