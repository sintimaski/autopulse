from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.config import get_settings
from autopulse_backend.models import Event
from autopulse_backend.repositories import events as events_repo
from autopulse_backend.schemas import IngestBatchRequest, event_payload


async def persist_ingest_batch(
    *,
    session: AsyncSession,
    project_id: UUID,
    batch: IngestBatchRequest,
    received_at: datetime,
) -> int:
    settings = get_settings()
    sdk_version = batch.sdk_version or settings.default_sdk_version
    rows = [
        Event(
            project_id=project_id,
            timestamp=event.timestamp,
            received_at=received_at,
            sdk_version=sdk_version,
            type=event.type,
            service_name=event.service_name,
            environment=event.environment,
            method=event.method,
            path=event.path,
            status_code=event.status_code,
            latency_ms=event.latency_ms,
            payload=event_payload(event),
            request_id=event.request_id,
        )
        for event in batch.events
    ]
    return await events_repo.insert_ingest_events(session, rows)
