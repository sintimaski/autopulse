from __future__ import annotations

import argparse
import asyncio
import secrets
from collections.abc import Awaitable, Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from autopulse_backend.alerts import AlertSender, build_alert_sender, evaluate_alerts_once
from autopulse_backend.core.config import Settings, get_settings
from autopulse_backend.database import get_engine
from autopulse_backend.maintenance.retention import run_retention_cleanup_once
from autopulse_backend.metrics import JobExecutionTelemetry, service_metrics
from autopulse_backend.repositories.runtime_controls import acquire_scheduler_lease


@dataclass(slots=True)
class SchedulerHandle:
    stop_event: asyncio.Event
    tasks: list[asyncio.Task[None]]

    async def stop(self) -> None:
        self.stop_event.set()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
            self.tasks.clear()


async def run_alerts_once(
    *,
    settings: Settings | None = None,
    sender: AlertSender | None = None,
) -> int:
    resolved_settings = settings or get_settings()
    resolved_sender = sender or build_alert_sender(resolved_settings)
    engine = get_engine(resolved_settings.database_url)
    session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        return await evaluate_alerts_once(session, resolved_settings, sender=resolved_sender)


async def run_retention_once(*, settings: Settings | None = None) -> int:
    resolved_settings = settings or get_settings()
    engine = get_engine(resolved_settings.database_url)
    session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        result = await run_retention_cleanup_once(session, resolved_settings)
    return result.deleted_events


async def _record_job_execution(
    *,
    job_name: str,
    operation: Callable[[], Awaitable[int]],
) -> int:
    started_at = datetime.now(tz=UTC)
    service_metrics.increment(f"jobs.{job_name}.started")
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
    engine = get_engine(settings.database_url)
    session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    while not stop_event.is_set():
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
        with suppress(Exception):
            await operation()
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
            operation=lambda: run_retention_once(settings=resolved_settings),
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run AutoPulse background jobs.")
    parser.add_argument(
        "command",
        choices=("alerts-once", "retention-once"),
        help="Which one-off job to run.",
    )
    return parser


async def _run_command(command: str) -> int:
    if command == "alerts-once":
        return await _record_job_execution(job_name="alerts", operation=run_alerts_once)
    if command == "retention-once":
        return await _record_job_execution(job_name="retention", operation=run_retention_once)
    raise ValueError(f"Unsupported command: {command}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    executed = asyncio.run(_run_command(args.command))
    print(executed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
