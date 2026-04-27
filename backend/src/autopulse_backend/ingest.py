from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.auth import ProjectContext, authenticate_project
from autopulse_backend.config import get_settings
from autopulse_backend.db import get_db_session
from autopulse_backend.ingest_limits import ingest_rate_limiter
from autopulse_backend.models import Event
from autopulse_backend.realtime import IngestBroadcastMessage, project_websocket_hub
from autopulse_backend.schemas import IngestBatchRequest, IngestBatchResponse, event_payload

router = APIRouter()


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
    session.add_all(rows)
    await session.commit()
    return len(rows)


@router.post("/ingest", response_model=IngestBatchResponse, status_code=status.HTTP_200_OK)
async def ingest_events(
    batch: IngestBatchRequest,
    request: Request,
    context: Annotated[ProjectContext, Depends(authenticate_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> IngestBatchResponse:
    settings = get_settings()
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            content_length_bytes = int(content_length)
        except ValueError:
            content_length_bytes = 0
        if content_length_bytes > settings.ingest_max_request_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    "Ingest payload exceeds max request size "
                    f"({settings.ingest_max_request_bytes} bytes)."
                ),
            )

    if not ingest_rate_limiter.allow(
        max_requests=settings.ingest_rate_limit_requests_per_window,
        window_seconds=settings.ingest_rate_limit_window_seconds,
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Ingest rate limit exceeded. "
                f"Try again in {settings.ingest_rate_limit_window_seconds} seconds."
            ),
            headers={"Retry-After": str(settings.ingest_rate_limit_window_seconds)},
        )

    received_at = datetime.now(tz=UTC)
    accepted = await persist_ingest_batch(
        session=session,
        project_id=context.project_id,
        batch=batch,
        received_at=received_at,
    )
    await project_websocket_hub.publish_ingest(
        message=IngestBroadcastMessage(
            project_id=context.project_id,
            accepted=accepted,
            received_at=received_at,
        )
    )
    return IngestBatchResponse(accepted=accepted)
