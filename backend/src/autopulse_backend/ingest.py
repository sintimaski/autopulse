from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.auth import ProjectContext, authenticate_project
from autopulse_backend.config import get_settings
from autopulse_backend.db import get_db_session
from autopulse_backend.models import Event
from autopulse_backend.schemas import IngestBatchRequest, IngestBatchResponse, event_payload

router = APIRouter()


@router.post("/ingest", response_model=IngestBatchResponse, status_code=status.HTTP_200_OK)
async def ingest_events(
    batch: IngestBatchRequest,
    context: Annotated[ProjectContext, Depends(authenticate_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> IngestBatchResponse:
    settings = get_settings()
    received_at = datetime.now(tz=UTC)
    sdk_version = batch.sdk_version or settings.default_sdk_version
    rows = [
        Event(
            project_id=context.project_id,
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
    session.add_all(rows)
    await session.commit()
    return IngestBatchResponse(accepted=len(rows))
