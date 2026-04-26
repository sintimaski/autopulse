from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from autopulse_backend.config import get_settings
from autopulse_backend.dashboard import router as dashboard_router
from autopulse_backend.db import get_engine
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

    app.include_router(ingest_router)
    app.include_router(dashboard_router)
    return app
