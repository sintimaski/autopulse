from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from autopulse_backend.config import get_settings
from autopulse_backend.dashboard import router as dashboard_router
from autopulse_backend.db import get_engine
from autopulse_backend.dev_scenarios import router as dev_scenarios_router
from autopulse_backend.ingest import router as ingest_router
from autopulse_backend.jobs import SchedulerHandle, start_scheduler
from autopulse_backend.models import Base


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="AutoPulse Backend")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allow_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def ensure_sqlite_schema() -> None:
        if not settings.database_url.startswith("sqlite"):
            return
        engine = get_engine(settings.database_url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    @app.on_event("startup")
    async def start_background_jobs() -> None:
        if not settings.jobs_enable_scheduler:
            return
        app.state._autopulse_scheduler = start_scheduler(settings=settings)

    @app.on_event("shutdown")
    async def stop_background_jobs() -> None:
        scheduler = getattr(app.state, "_autopulse_scheduler", None)
        if isinstance(scheduler, SchedulerHandle):
            await scheduler.stop()
            app.state._autopulse_scheduler = None

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> dict[str, str]:
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

    app.include_router(ingest_router)
    app.include_router(dashboard_router)
    if settings.dev_scenarios_enabled:
        app.include_router(dev_scenarios_router)
    return app


def mount_on_app(host_app: Any, *, prefix: str = "/autopulse") -> FastAPI:
    """Mount the backend app under a host FastAPI application."""
    mounted_app = create_app()
    host_app.mount(prefix.rstrip("/") or "/", mounted_app)
    return mounted_app
