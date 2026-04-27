from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
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
    }
