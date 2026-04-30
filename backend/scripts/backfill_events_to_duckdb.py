from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from autopulse_backend.database import AsyncSessionLocal
from autopulse_backend.models import Event
from autopulse_backend.services.event_store import get_duckdb_event_store


async def run_backfill(*, batch_size: int, since: datetime | None) -> int:
    store = get_duckdb_event_store()
    copied = 0
    last_id = 0
    while True:
        async with AsyncSessionLocal() as session:
            query = (
                select(Event).where(Event.id > last_id).order_by(Event.id.asc()).limit(batch_size)
            )
            if since is not None:
                query = query.where(Event.received_at >= since)
            rows = (await session.scalars(query)).all()
        if not rows:
            break
        payload = [
            {
                "project_id": row.project_id,
                "timestamp": row.timestamp,
                "received_at": row.received_at,
                "sdk_version": row.sdk_version,
                "type": row.type,
                "service_name": row.service_name,
                "environment": row.environment,
                "method": row.method,
                "path": row.path,
                "status_code": row.status_code,
                "latency_ms": row.latency_ms,
                "payload": row.payload,
                "request_id": row.request_id,
            }
            for row in rows
        ]
        await asyncio.to_thread(store.insert_rows, payload)
        copied += len(rows)
        last_id = int(rows[-1].id)
    return copied


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill SQL events into DuckDB event store")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument(
        "--since",
        type=str,
        default="",
        help="Optional ISO timestamp, e.g. 2026-04-01T00:00:00Z",
    )
    return parser.parse_args()


def _parse_since(raw: str) -> datetime | None:
    value = raw.strip()
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


if __name__ == "__main__":
    args = parse_args()
    total = asyncio.run(
        run_backfill(
            batch_size=max(1, int(args.batch_size)),
            since=_parse_since(args.since),
        )
    )
    print(f"backfilled_events={total}")
