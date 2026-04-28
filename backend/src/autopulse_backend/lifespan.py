from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from autopulse_backend.core.config import get_settings
from autopulse_backend.database import get_engine
from autopulse_backend.jobs import SchedulerHandle, start_scheduler
from autopulse_backend.models import Base
from autopulse_backend.services.ingest_aggregate_worker import (
    IngestAggregateWorkerHandle,
    start_ingest_aggregate_worker,
    stop_ingest_aggregate_worker,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup and shutdown (replaces deprecated on_event hooks)."""
    settings = get_settings()

    if settings.database_url.startswith("sqlite"):
        engine = get_engine(settings.database_url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    if settings.jobs_enable_scheduler:
        app.state._autopulse_scheduler = start_scheduler(settings=settings)
    else:
        app.state._autopulse_scheduler = None
    if settings.ingest_async_aggregate_enabled:
        app.state._autopulse_ingest_aggregate_worker = start_ingest_aggregate_worker(settings)
    else:
        app.state._autopulse_ingest_aggregate_worker = None

    yield

    scheduler = getattr(app.state, "_autopulse_scheduler", None)
    if isinstance(scheduler, SchedulerHandle):
        await scheduler.stop()
    app.state._autopulse_scheduler = None
    aggregate_worker = getattr(app.state, "_autopulse_ingest_aggregate_worker", None)
    if isinstance(aggregate_worker, IngestAggregateWorkerHandle):
        await stop_ingest_aggregate_worker()
    app.state._autopulse_ingest_aggregate_worker = None
