from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from autopulse_backend.core.config import (
    _is_workspace_default_dev_sqlite_file,
    get_settings,
    redact_database_url_for_log,
    resolve_autopulse_data_root,
)
from autopulse_backend.database import get_engine, warm_database_connections
from autopulse_backend.jobs import (
    RetentionPressurePollHandle,
    SchedulerHandle,
    retention_pressure_poll_should_run,
    start_retention_only_scheduler,
    start_retention_pressure_poll,
    start_scheduler,
)
from autopulse_backend.models import Base
from autopulse_backend.realtime.bus import run_postgres_realtime_subscriber
from autopulse_backend.realtime.dashboard_ws_tick import run_dashboard_ws_live_tick_loop
from autopulse_backend.services.duckdb_async import shutdown_duckdb_executors
from autopulse_backend.services.event_plane_compactor_worker import (
    EventPlaneCompactorWorkerHandle,
    start_event_plane_compactor_worker,
)
from autopulse_backend.services.event_plane_shards import shutdown_event_plane_shard_writer
from autopulse_backend.services.event_store import (
    event_store_enabled,
    shutdown_duckdb_event_store,
    try_get_duckdb_event_store,
)
from autopulse_backend.services.ingest_aggregate_worker import (
    IngestAggregateWorkerHandle,
    start_ingest_aggregate_worker,
    stop_ingest_aggregate_worker,
)

logger = logging.getLogger(__name__)


def _ensure_autopulse_backend_logging() -> None:
    """Ensure ``autopulse_backend`` INFO logs reach stderr.

    Uvicorn leaves the root logger at WARNING. Some environments also attach a
    ``NullHandler`` (or other handlers) to ``autopulse_backend`` before lifespan
    runs; the old early-return skipped adding a ``StreamHandler``, so startup
    ``logger.info`` lines never appeared.
    """
    pkg = logging.getLogger("autopulse_backend")
    pkg.setLevel(logging.INFO)
    has_stream = any(isinstance(h, logging.StreamHandler) for h in pkg.handlers)
    if not has_stream:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
        handler.setLevel(logging.INFO)
        pkg.addHandler(handler)
    else:
        for h in pkg.handlers:
            if isinstance(h, logging.StreamHandler) and h.level > logging.INFO:
                h.setLevel(logging.INFO)
    pkg.propagate = False


def _log_grouped_startup_settings() -> None:
    """Log non-secret effective settings grouped for startup debugging."""
    settings = get_settings()
    # Log on the package logger so messages always use the handlers configured in
    # ``_ensure_autopulse_backend_logging`` (child loggers can be misconfigured in some hosts).
    log = logging.getLogger("autopulse_backend")
    log.info(
        "Startup settings [database]: database_url=%s",
        redact_database_url_for_log(settings.database_url),
    )
    log.info(
        "Startup settings [cors]: cors_allow_origins=%s",
        ",".join(settings.cors_allow_origins),
    )
    log.info(
        "Startup settings [ingest]: max_request_bytes=%d rate_limit=%d/%ds "
        "distributed_rate_limit=%s async_aggregate=%s aggregate_queue_max=%d "
        "drop_autopulse_traffic=%s sql_tail_repair_enabled=%s "
        "sql_tail_repair_interval_seconds=%.2f sql_tail_repair_batch_size=%d "
        "sql_tail_repair_max_retries=%d",
        settings.ingest_max_request_bytes,
        settings.ingest_rate_limit_requests_per_window,
        settings.ingest_rate_limit_window_seconds,
        settings.ingest_distributed_rate_limit_enabled,
        settings.ingest_async_aggregate_enabled,
        settings.ingest_async_aggregate_queue_max_size,
        settings.ingest_drop_autopulse_traffic_from_db,
        settings.ingest_sql_tail_repair_enabled,
        settings.ingest_sql_tail_repair_interval_seconds,
        settings.ingest_sql_tail_repair_batch_size,
        settings.ingest_sql_tail_repair_max_retries,
    )
    log.info(
        "Startup settings [jobs_retention]: jobs_enable_scheduler=%s "
        "scheduler_lease_enabled=%s scheduler_lease_ttl_seconds=%d "
        "alert_interval_seconds=%.2f retention_interval_seconds=%.2f "
        "retention_pressure_poll_seconds=%.2f "
        "retention_pressure_min_interval_seconds=%.2f retention_raw_events_days=%d "
        "sqlite_max_db_file_mb=%s",
        settings.jobs_enable_scheduler,
        settings.jobs_scheduler_lease_enabled,
        settings.jobs_scheduler_lease_ttl_seconds,
        settings.jobs_alert_interval_seconds,
        settings.jobs_retention_interval_seconds,
        settings.retention_pressure_poll_seconds,
        settings.retention_pressure_min_interval_seconds,
        settings.retention_raw_events_days,
        settings.sqlite_max_db_file_mb,
    )
    log.info(
        "Startup settings [dashboard_auth]: enabled=%s allowed_email=%s "
        "api_key_fallback=%s session_ttl_minutes=%d magic_link_ttl_minutes=%d",
        settings.dashboard_auth_enabled,
        settings.dashboard_auth_allowed_email,
        settings.dashboard_auth_allow_api_key_fallback,
        settings.dashboard_auth_session_ttl_minutes,
        settings.dashboard_auth_magic_link_ttl_minutes,
    )
    log.info(
        "Startup settings [deployment]: autopulse_env=%s aggregate_max_retries=%d "
        "run_migrations_on_startup=%s parquet_export_enabled=%s "
        "parquet_export_interval_seconds=%.2f parquet_export_window_seconds=%d "
        "parquet_export_root=%s",
        settings.autopulse_env,
        settings.ingest_aggregate_worker_max_retries,
        settings.database_run_migrations_on_startup,
        settings.parquet_export_enabled,
        settings.parquet_export_interval_seconds,
        settings.parquet_export_window_seconds,
        settings.parquet_export_root,
    )
    log.info(
        "Startup settings [alerts]: enabled=%s sender_mode=%s email_provider=%s "
        "email_from=%s default_destination_set=%s webhook_set=%s slack_set=%s "
        "discord_set=%s",
        settings.alerts_enabled,
        settings.alert_sender_mode,
        settings.alert_email_provider,
        settings.alert_email_from,
        bool(settings.alert_default_destination_email),
        bool(settings.alert_webhook_url),
        bool(settings.alert_slack_webhook_url),
        bool(settings.alert_discord_webhook_url),
    )
    log.info(
        (
            "Startup settings [realtime]: dashboard_ws_live_tick_seconds=%.2f "
            "realtime_bus_backend=%s realtime_bus_channel=%s"
        ),
        settings.dashboard_ws_live_tick_seconds,
        settings.dashboard_realtime_bus_backend,
        settings.dashboard_realtime_bus_channel,
    )
    if settings.event_store == "duckdb":
        log.info(
            "Startup settings [event_store]: mode=%s event_plane_mode=%s duckdb_path=%s "
            "shards_path=%s snapshots_path=%s data_root=%s",
            settings.event_store,
            settings.event_plane_mode,
            settings.event_store_duckdb_path,
            settings.event_plane_shards_path,
            settings.event_plane_snapshots_path,
            str(resolve_autopulse_data_root()),
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup and shutdown (replaces deprecated on_event hooks)."""
    _ensure_autopulse_backend_logging()
    _log_grouped_startup_settings()
    settings = get_settings()

    # Alembic must run for SQLite too: ``create_all`` only creates missing tables and does not
    # ALTER existing tables when ORM columns are added (otherwise startup hits "no such column").
    if settings.database_run_migrations_on_startup:
        from autopulse_backend.database.migrations import upgrade_to_head

        upgrade_to_head()
        logger.info("Applied Alembic migrations to head")
    else:
        logger.info(
            "Skipping Alembic migrations on startup (DATABASE_RUN_MIGRATIONS_ON_STARTUP=false)"
        )

    if settings.database_url.startswith("sqlite"):
        engine = get_engine(settings.database_url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    await warm_database_connections(settings.database_url)
    if event_store_enabled(settings):
        try_get_duckdb_event_store()

    if settings.jobs_enable_scheduler:
        app.state._autopulse_scheduler = start_scheduler(settings=settings)
        logger.info(
            "Background scheduler started (alerts + retention, retention every %.0fs)",
            settings.jobs_retention_interval_seconds,
        )
    elif _is_workspace_default_dev_sqlite_file(settings.database_url):
        app.state._autopulse_scheduler = start_retention_only_scheduler(settings=settings)
        logger.info(
            "Retention-only scheduler started (JOBS_ENABLE_SCHEDULER=false; interval %.0fs)",
            settings.jobs_retention_interval_seconds,
        )
    else:
        app.state._autopulse_scheduler = None
        if not settings.database_url.startswith("sqlite"):
            logger.info("No background scheduler (non-SQLite DATABASE_URL)")
        else:
            logger.info(
                "No background scheduler (set JOBS_ENABLE_SCHEDULER=true or use default "
                "SQLite under .autopulse/ (autopulse.db or autopulse_embedded.db) for "
                "automatic retention)"
            )
    if settings.ingest_async_aggregate_enabled:
        app.state._autopulse_ingest_aggregate_worker = start_ingest_aggregate_worker(settings)
    else:
        app.state._autopulse_ingest_aggregate_worker = None

    if retention_pressure_poll_should_run(settings):
        app.state._autopulse_retention_pressure_poll = start_retention_pressure_poll(
            settings=settings
        )
        logger.info(
            "SQLite retention pressure poll enabled (every %.2fs; min run gap %.0fs)",
            settings.retention_pressure_poll_seconds,
            settings.retention_pressure_min_interval_seconds,
        )
    else:
        app.state._autopulse_retention_pressure_poll = None

    if settings.dashboard_ws_live_tick_seconds > 0:
        app.state._autopulse_dashboard_ws_tick_task = asyncio.create_task(
            run_dashboard_ws_live_tick_loop(
                interval_seconds=settings.dashboard_ws_live_tick_seconds,
            ),
            name="autopulse-dashboard-ws-tick",
        )
        logger.info(
            "Dashboard WebSocket live tick enabled (every %.2fs for connected clients)",
            settings.dashboard_ws_live_tick_seconds,
        )
    else:
        app.state._autopulse_dashboard_ws_tick_task = None

    if settings.dashboard_realtime_bus_backend == "postgres_notify":
        app.state._autopulse_realtime_bus_subscriber_task = asyncio.create_task(
            run_postgres_realtime_subscriber(settings=settings),
            name="autopulse-realtime-bus-subscriber",
        )
        logger.info(
            "Realtime bus subscriber enabled (backend=%s channel=%s)",
            settings.dashboard_realtime_bus_backend,
            settings.dashboard_realtime_bus_channel,
        )
    else:
        app.state._autopulse_realtime_bus_subscriber_task = None
    app.state._autopulse_event_plane_compactor_worker = start_event_plane_compactor_worker(
        settings=settings
    )

    yield

    scheduler = getattr(app.state, "_autopulse_scheduler", None)
    if isinstance(scheduler, SchedulerHandle):
        await scheduler.stop()
    app.state._autopulse_scheduler = None
    aggregate_worker = getattr(app.state, "_autopulse_ingest_aggregate_worker", None)
    if isinstance(aggregate_worker, IngestAggregateWorkerHandle):
        await stop_ingest_aggregate_worker()
    app.state._autopulse_ingest_aggregate_worker = None
    pressure = getattr(app.state, "_autopulse_retention_pressure_poll", None)
    if isinstance(pressure, RetentionPressurePollHandle):
        await pressure.stop()
    app.state._autopulse_retention_pressure_poll = None
    tick_task = getattr(app.state, "_autopulse_dashboard_ws_tick_task", None)
    if isinstance(tick_task, asyncio.Task) and not tick_task.done():
        tick_task.cancel()
        with suppress(asyncio.CancelledError):
            await tick_task
    app.state._autopulse_dashboard_ws_tick_task = None
    bus_task = getattr(app.state, "_autopulse_realtime_bus_subscriber_task", None)
    if isinstance(bus_task, asyncio.Task) and not bus_task.done():
        bus_task.cancel()
        with suppress(asyncio.CancelledError):
            await bus_task
    app.state._autopulse_realtime_bus_subscriber_task = None
    compactor_worker = getattr(app.state, "_autopulse_event_plane_compactor_worker", None)
    if isinstance(compactor_worker, EventPlaneCompactorWorkerHandle):
        await compactor_worker.stop()
    app.state._autopulse_event_plane_compactor_worker = None
    shutdown_duckdb_executors(wait=True)
    shutdown_event_plane_shard_writer()
    shutdown_duckdb_event_store()
