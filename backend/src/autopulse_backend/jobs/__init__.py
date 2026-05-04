from __future__ import annotations

import argparse
import asyncio
import logging
import secrets
import time
from collections.abc import Awaitable, Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from autopulse_backend.alerts import AlertSender, build_alert_sender, evaluate_alerts_once
from autopulse_backend.core.config import Settings, get_settings, redact_database_url_for_log
from autopulse_backend.database import dispose_engine_for_url, get_engine, get_session_maker
from autopulse_backend.maintenance.retention import (
    _resolve_sqlite_db_path,
    _sqlite_db_disk_footprint_bytes,
    _vacuum_sqlite_db_file,
    retention_pressure_pending,
    run_retention_cleanup_once,
)
from autopulse_backend.metrics import JobExecutionTelemetry, service_metrics
from autopulse_backend.models import Base
from autopulse_backend.repositories import ingest_reliability as ingest_reliability_repo
from autopulse_backend.repositories.aggregates import (
    upsert_error_group_aggregates,
    upsert_metric_buckets,
)
from autopulse_backend.repositories.runtime_controls import acquire_scheduler_lease
from autopulse_backend.services.aggregate_delta_codec import decode_aggregate_payload

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SchedulerHandle:
    stop_event: asyncio.Event
    tasks: list[asyncio.Task[None]]

    async def stop(self) -> None:
        self.stop_event.set()
        if self.tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.tasks, return_exceptions=True),
                    timeout=5.0,
                )
            except TimeoutError:
                logger.warning("Scheduler stop timed out; cancelling remaining tasks")
                for task in self.tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self.tasks, return_exceptions=True)
            self.tasks.clear()


@dataclass(slots=True)
class RetentionPressurePollHandle:
    stop_event: asyncio.Event
    task: asyncio.Task[None]

    async def stop(self) -> None:
        self.stop_event.set()
        if self.task.done():
            return
        self.task.cancel()
        try:
            await asyncio.wait_for(self.task, timeout=5.0)
        except (asyncio.CancelledError, TimeoutError):
            logger.warning("Retention pressure poll stop timed out")


_retention_run_lock = asyncio.Lock()


async def _ensure_sqlite_schema_from_models(database_url: str) -> None:
    """Match FastAPI lifespan: file-backed SQLite may be opened before the API has run."""
    if not database_url.startswith("sqlite"):
        return
    engine = get_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def run_alerts_once(
    *,
    settings: Settings | None = None,
    sender: AlertSender | None = None,
) -> int:
    resolved_settings = settings or get_settings()
    resolved_sender = sender or build_alert_sender(resolved_settings)
    await _ensure_sqlite_schema_from_models(resolved_settings.database_url)
    session_maker = get_session_maker(resolved_settings.database_url)
    async with session_maker() as session:
        return await evaluate_alerts_once(session, resolved_settings, sender=resolved_sender)


async def run_replay_aggregate_dead_letters_once(
    *, settings: Settings | None = None, limit: int = 50
) -> int:
    """Replay persisted aggregate dead letters (operator recovery)."""
    resolved_settings = settings or get_settings()
    await _ensure_sqlite_schema_from_models(resolved_settings.database_url)
    session_maker = get_session_maker(resolved_settings.database_url)
    replayed = 0
    async with session_maker() as session:
        rows = await ingest_reliability_repo.fetch_pending_dead_letters(session, limit=limit)
        for row in rows:
            try:
                metrics, errors = decode_aggregate_payload(row.payload)
                if not metrics and not errors:
                    await ingest_reliability_repo.mark_dead_letter_replayed(session, row.id)
                    replayed += 1
                    continue
                await upsert_metric_buckets(session, metrics)
                await upsert_error_group_aggregates(session, errors)
                await ingest_reliability_repo.mark_dead_letter_replayed(session, row.id)
                replayed += 1
            except Exception:
                logger.exception(
                    "replay_aggregate_dead_letter_failed",
                    extra={"dead_letter_id": row.id},
                )
    return replayed


async def run_retention_once(
    *,
    settings: Settings | None = None,
    dispose_engine_after: bool = False,
) -> int:
    """Run retention cleanup; serialized with the scheduled retention job and pressure poller.

    SQL work runs under ``_retention_run_lock``; ``VACUUM`` runs **after** the lock is
    released so long vacuums do not stall the next scheduled tick.

    When ``dispose_engine_after`` is true (``retention-once`` CLI), pooled connections are
    dropped before ``VACUUM`` so SQLite can reclaim space reliably.
    """
    resolved_settings = settings or get_settings()
    url = resolved_settings.database_url
    deleted = 0
    post_vacuum_path: Path | None = None
    size_before = 0
    size_after_cleanup = 0
    size_after_vacuum = 0
    cap_bytes = (
        int(resolved_settings.sqlite_max_db_file_mb) * 1024 * 1024
        if resolved_settings.sqlite_max_db_file_mb is not None
        else None
    )
    logger.info("Retention run start: database_url=%s", redact_database_url_for_log(url))
    async with _retention_run_lock:
        logger.info("Retention lock acquired")
        await _ensure_sqlite_schema_from_models(url)
        session_maker = get_session_maker(url)
        async with session_maker() as session:
            result = await run_retention_cleanup_once(session, resolved_settings)
        deleted = result.deleted_events
        logger.info("Retention cleanup complete: deleted=%d", deleted)

        if url.startswith("sqlite"):
            db_path = _resolve_sqlite_db_path(url)
            cap_mb = resolved_settings.sqlite_max_db_file_mb
            if db_path is not None:
                try:
                    size_before = _sqlite_db_disk_footprint_bytes(db_path)
                except OSError:
                    size_before = 0
            needs_vacuum = deleted > 0
            if db_path is not None and cap_mb is not None:
                with suppress(OSError):
                    needs_vacuum = needs_vacuum or (
                        _sqlite_db_disk_footprint_bytes(db_path) > int(cap_mb) * 1024 * 1024
                    )
            if needs_vacuum and db_path is not None:
                post_vacuum_path = db_path
            if db_path is not None:
                try:
                    size_after_cleanup = _sqlite_db_disk_footprint_bytes(db_path)
                except OSError:
                    size_after_cleanup = 0

    if post_vacuum_path is not None:
        if dispose_engine_after:
            await dispose_engine_for_url(url)
        try:
            before_bytes = _sqlite_db_disk_footprint_bytes(post_vacuum_path)
            started = time.monotonic()
            # Run VACUUM in a worker thread so the event loop remains responsive
            # (Ctrl-C/shutdown can proceed while retention cleanup is in progress).
            after_main = await asyncio.to_thread(_vacuum_sqlite_db_file, post_vacuum_path)
            elapsed_ms = int((time.monotonic() - started) * 1000)
            after_bytes = _sqlite_db_disk_footprint_bytes(post_vacuum_path)
            logger.info(
                "Retention VACUUM done: path=%s before=%d after=%d main_after=%d elapsed_ms=%d",
                post_vacuum_path,
                before_bytes,
                after_bytes,
                after_main,
                elapsed_ms,
            )
            size_after_vacuum = after_bytes
        except Exception:
            logger.exception("SQLite VACUUM after retention failed")
    if url.startswith("sqlite"):
        final_size = size_after_vacuum or size_after_cleanup or size_before
        logger.info(
            "Retention cap check: path=%s before=%d after_cleanup=%d "
            "after_vacuum=%d cap=%s over_cap=%s",
            _resolve_sqlite_db_path(url),
            size_before,
            size_after_cleanup,
            size_after_vacuum,
            str(cap_bytes) if cap_bytes is not None else "none",
            bool(cap_bytes is not None and final_size > cap_bytes),
        )
    logger.info("Retention run finished: deleted=%d", deleted)
    return deleted


def run_retention_sync(*, dispose_engine_after: bool = True) -> int:
    """Blocking retention for cron, systemd, Django management commands, or any sync host.

    Uses ``asyncio.run`` around :func:`run_retention_once`. Set ``DATABASE_URL`` (and other
    env vars) before calling. Default ``dispose_engine_after=True`` matches the CLI and is
    safest for one-off processes with no concurrent async engine.
    """
    return asyncio.run(run_retention_once(dispose_engine_after=dispose_engine_after))


async def _record_job_execution(
    *,
    job_name: str,
    operation: Callable[[], Awaitable[int]],
) -> int:
    started_at = datetime.now(tz=UTC)
    service_metrics.increment(f"jobs.{job_name}.started")
    logger.info("Job run start: name=%s", job_name)
    try:
        processed = await operation()
    except Exception as exc:
        finished_at = datetime.now(tz=UTC)
        duration_ms = max(0, int((finished_at - started_at).total_seconds() * 1000))
        service_metrics.increment(f"jobs.{job_name}.failed")
        service_metrics.set_job_last_run(
            JobExecutionTelemetry(
                job_name=job_name,
                status="failed",
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                records_processed=0,
                failure_reason=exc.__class__.__name__,
            )
        )
        raise
    finished_at = datetime.now(tz=UTC)
    duration_ms = max(0, int((finished_at - started_at).total_seconds() * 1000))
    service_metrics.increment(f"jobs.{job_name}.succeeded")
    service_metrics.increment(f"jobs.{job_name}.records_processed", max(0, int(processed)))
    service_metrics.set_job_last_run(
        JobExecutionTelemetry(
            job_name=job_name,
            status="succeeded",
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            records_processed=max(0, int(processed)),
            failure_reason=None,
        )
    )
    logger.info(
        "Job run succeeded: name=%s processed=%d duration_ms=%d",
        job_name,
        max(0, int(processed)),
        duration_ms,
    )
    return processed


async def _run_periodic(
    *,
    job_name: str,
    settings: Settings,
    scheduler_owner_token: str,
    interval_seconds: float,
    stop_event: asyncio.Event,
    operation: Callable[[], Awaitable[None]],
) -> None:
    session_maker = get_session_maker(settings.database_url)
    logger.info(
        "Periodic loop started: job=%s interval_seconds=%.2f lease_enabled=%s",
        job_name,
        float(interval_seconds),
        settings.jobs_scheduler_lease_enabled,
    )
    while not stop_event.is_set():
        logger.info("Periodic tick: job=%s", job_name)
        if settings.jobs_scheduler_lease_enabled:
            async with session_maker() as session:
                lease_acquired = await acquire_scheduler_lease(
                    session=session,
                    job_name=job_name,
                    owner_token=scheduler_owner_token,
                    lease_ttl_seconds=settings.jobs_scheduler_lease_ttl_seconds,
                )
            if not lease_acquired:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
                except TimeoutError:
                    continue
                continue
        try:
            await operation()
        except Exception:
            logger.exception("Periodic job %r failed", job_name)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except TimeoutError:
            continue


def start_scheduler(
    *,
    settings: Settings | None = None,
    sender: AlertSender | None = None,
) -> SchedulerHandle:
    resolved_settings = settings or get_settings()
    scheduler_owner_token = secrets.token_hex(16)
    stop_event = asyncio.Event()

    async def alert_tick() -> None:
        await _record_job_execution(
            job_name="alerts",
            operation=lambda: run_alerts_once(settings=resolved_settings, sender=sender),
        )

    async def retention_tick() -> None:
        await _record_job_execution(
            job_name="retention",
            operation=lambda: run_retention_once(
                settings=resolved_settings,
                dispose_engine_after=True,
            ),
        )

    tasks = [
        asyncio.create_task(
            _run_periodic(
                job_name="alerts",
                settings=resolved_settings,
                scheduler_owner_token=scheduler_owner_token,
                interval_seconds=resolved_settings.jobs_alert_interval_seconds,
                stop_event=stop_event,
                operation=alert_tick,
            )
        ),
        asyncio.create_task(
            _run_periodic(
                job_name="retention",
                settings=resolved_settings,
                scheduler_owner_token=scheduler_owner_token,
                interval_seconds=resolved_settings.jobs_retention_interval_seconds,
                stop_event=stop_event,
                operation=retention_tick,
            )
        ),
    ]
    return SchedulerHandle(stop_event=stop_event, tasks=tasks)


def start_retention_only_scheduler(
    *,
    settings: Settings | None = None,
) -> SchedulerHandle:
    """Run only retention on an interval.

    Used when alerts scheduler is off (e.g. ``JOBS_ENABLE_SCHEDULER=false``).
    """
    resolved_settings = settings or get_settings()
    scheduler_owner_token = secrets.token_hex(16)
    stop_event = asyncio.Event()

    async def retention_tick() -> None:
        await _record_job_execution(
            job_name="retention",
            operation=lambda: run_retention_once(
                settings=resolved_settings,
                dispose_engine_after=True,
            ),
        )

    tasks = [
        asyncio.create_task(
            _run_periodic(
                job_name="retention",
                settings=resolved_settings,
                scheduler_owner_token=scheduler_owner_token,
                interval_seconds=resolved_settings.jobs_retention_interval_seconds,
                stop_event=stop_event,
                operation=retention_tick,
            )
        ),
    ]
    return SchedulerHandle(stop_event=stop_event, tasks=tasks)


async def _retention_pressure_poll_loop(settings: Settings, stop_event: asyncio.Event) -> None:
    """Poll pressure and run retention when SQLite exceeds size/row caps."""
    poll = float(settings.retention_pressure_poll_seconds)
    min_interval = float(settings.retention_pressure_min_interval_seconds)
    if poll <= 0:
        return
    session_maker = get_session_maker(settings.database_url)
    last_run_mono: float | None = None
    while not stop_event.is_set():
        pending = False
        try:
            async with session_maker() as session:
                pending = await retention_pressure_pending(session, settings)
        except Exception:
            logger.exception("Retention pressure probe failed")
            pending = False
        if pending:
            now = time.monotonic()
            if last_run_mono is None or (now - last_run_mono) >= min_interval:
                try:
                    await _record_job_execution(
                        job_name="retention",
                        operation=lambda: run_retention_once(
                            settings=settings,
                            dispose_engine_after=True,
                        ),
                    )
                except Exception:
                    logger.exception("Pressure-triggered retention failed")
                last_run_mono = time.monotonic()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=poll)
        except TimeoutError:
            continue


def start_retention_pressure_poll(
    *, settings: Settings | None = None
) -> RetentionPressurePollHandle:
    resolved_settings = settings or get_settings()
    stop_event = asyncio.Event()
    task = asyncio.create_task(_retention_pressure_poll_loop(resolved_settings, stop_event))
    return RetentionPressurePollHandle(stop_event=stop_event, task=task)


def retention_pressure_poll_should_run(settings: Settings) -> bool:
    """Whether the in-process SQLite pressure poll loop should start (lifespan)."""
    if settings.retention_pressure_poll_seconds <= 0:
        return False
    if not settings.database_url.startswith("sqlite"):
        return False
    return _resolve_sqlite_db_path(settings.database_url) is not None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run AutoPulse background jobs.")
    parser.add_argument(
        "command",
        choices=("alerts-once", "retention-once", "replay-aggregate-dead-letters-once"),
        help="Which one-off job to run.",
    )
    return parser


async def _run_command(command: str) -> int:
    if command == "alerts-once":
        return await _record_job_execution(job_name="alerts", operation=run_alerts_once)
    if command == "retention-once":
        return await _record_job_execution(
            job_name="retention",
            operation=lambda: run_retention_once(dispose_engine_after=True),
        )
    if command == "replay-aggregate-dead-letters-once":
        return await _record_job_execution(
            job_name="replay_aggregate_dead_letters",
            operation=run_replay_aggregate_dead_letters_once,
        )
    raise ValueError(f"Unsupported command: {command}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    executed = asyncio.run(_run_command(args.command))
    print(executed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
