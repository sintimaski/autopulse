from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import text

from autopulse_backend.core.config import get_settings
from autopulse_backend.database import get_engine
from autopulse_backend.jobs import SchedulerHandle
from autopulse_backend.metrics import service_metrics

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
    return {
        "service": "autopulse-backend",
        "scheduler_running": isinstance(scheduler, SchedulerHandle),
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
