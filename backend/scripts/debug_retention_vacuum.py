from __future__ import annotations

import argparse
import asyncio
import sqlite3
import time
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from autopulse_backend.core.config import get_settings
from autopulse_backend.database import get_engine
from autopulse_backend.jobs import run_retention_once
from autopulse_backend.maintenance.retention import (
    _resolve_sqlite_db_path,
    _sqlite_db_disk_footprint_bytes,
    sqlite_retention_pressure_pending,
)
from autopulse_backend.models import Event


def _fmt_mb(value: int) -> str:
    return f"{value / (1024 * 1024):.2f}MB"


def _sqlite_vacuum_probe(db_path: Path) -> tuple[bool, str]:
    try:
        with sqlite3.connect(str(db_path), timeout=2.0) as connection:
            connection.execute("PRAGMA busy_timeout=2000")
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            connection.execute("VACUUM")
        return True, "ok"
    except sqlite3.OperationalError as exc:
        return False, str(exc)


async def _run(iterations: int, sleep_seconds: float, dispose_engine_after: bool) -> None:
    settings = get_settings()
    db_path = _resolve_sqlite_db_path(settings.database_url)
    if db_path is None:
        raise SystemExit(f"DATABASE_URL is not file-backed sqlite: {settings.database_url}")

    engine = get_engine(settings.database_url)
    session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    print(f"db={db_path}")
    print(
        f"cap_mb={settings.embedded_sqlite_max_db_file_mb} "
        f"interval={settings.jobs_retention_interval_seconds} "
        f"pressure_poll={settings.retention_pressure_poll_seconds}"
    )

    for i in range(iterations):
        async with session_maker() as session:
            pending = await sqlite_retention_pressure_pending(session, settings)
            event_count = int((await session.execute(select(func.count(Event.id)))).scalar_one())
        before = _sqlite_db_disk_footprint_bytes(db_path)
        start = time.monotonic()
        deleted = await run_retention_once(
            settings=settings, dispose_engine_after=dispose_engine_after
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        after = _sqlite_db_disk_footprint_bytes(db_path)
        probe_ok, probe_msg = _sqlite_vacuum_probe(db_path)
        print(
            f"[{i + 1}/{iterations}] pending={pending} events={event_count} deleted={deleted} "
            f"before={_fmt_mb(before)} after={_fmt_mb(after)} elapsed_ms={elapsed_ms} "
            f"vacuum_probe={'ok' if probe_ok else 'locked'} ({probe_msg})"
        )
        if i < iterations - 1:
            await asyncio.sleep(sleep_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description="Debug scheduled retention + VACUUM behavior.")
    parser.add_argument(
        "--iterations", type=int, default=8, help="How many retention passes to run."
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=2.0,
        help="Sleep seconds between passes.",
    )
    parser.add_argument(
        "--dispose-engine-after",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Dispose shared async engine before VACUUM (default: true).",
    )
    args = parser.parse_args()
    asyncio.run(_run(args.iterations, args.sleep, args.dispose_engine_after))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
