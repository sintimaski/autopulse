from __future__ import annotations

import argparse
import asyncio
from collections.abc import Awaitable, Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from autopulse_backend.alerts import AlertSender, build_alert_sender, evaluate_alerts_once
from autopulse_backend.core.config import Settings, get_settings
from autopulse_backend.database import get_engine
from autopulse_backend.maintenance.retention import run_retention_cleanup_once


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


async def _run_periodic(
    *,
    interval_seconds: float,
    stop_event: asyncio.Event,
    operation: Callable[[], Awaitable[None]],
) -> None:
    while not stop_event.is_set():
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
    stop_event = asyncio.Event()

    async def alert_tick() -> None:
        await run_alerts_once(settings=resolved_settings, sender=sender)

    async def retention_tick() -> None:
        await run_retention_once(settings=resolved_settings)

    tasks = [
        asyncio.create_task(
            _run_periodic(
                interval_seconds=resolved_settings.jobs_alert_interval_seconds,
                stop_event=stop_event,
                operation=alert_tick,
            )
        ),
        asyncio.create_task(
            _run_periodic(
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
        return await run_alerts_once()
    if command == "retention-once":
        return await run_retention_once()
    raise ValueError(f"Unsupported command: {command}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    executed = asyncio.run(_run_command(args.command))
    print(executed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
