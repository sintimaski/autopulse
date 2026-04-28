from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.auth import ProjectContext, authenticate_project
from autopulse_backend.config import get_settings
from autopulse_backend.database import get_db_session
from autopulse_backend.ingestion.limits import ingest_rate_limiter
from autopulse_backend.metrics import service_metrics
from autopulse_backend.realtime import IngestBroadcastMessage, project_websocket_hub
from autopulse_backend.repositories.runtime_controls import allow_distributed_ingest_request
from autopulse_backend.schemas import IngestBatchRequest, IngestBatchResponse
from autopulse_backend.services.ingest_aggregate_worker import (
    IngestAggregatePayload,
    enqueue_ingest_aggregate_payload,
)
from autopulse_backend.services.ingest_service import persist_ingest_batch

router = APIRouter()
logger = logging.getLogger(__name__)


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
            service_metrics.increment("ingest.rejected.payload_too_large")
            logger.warning(
                "ingest_rejected payload_too_large",
                extra={
                    "event": "ingest_rejected",
                    "reason": "payload_too_large",
                    "content_length_bytes": content_length_bytes,
                    "ingest_max_request_bytes": settings.ingest_max_request_bytes,
                    "project_id": str(context.project_id),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    "Ingest payload exceeds max request size "
                    f"({settings.ingest_max_request_bytes} bytes)."
                ),
            )

    if settings.ingest_distributed_rate_limit_enabled:
        allowed = await allow_distributed_ingest_request(
            session=session,
            project_id=context.project_id,
            max_requests=settings.ingest_rate_limit_requests_per_window,
            window_seconds=settings.ingest_rate_limit_window_seconds,
        )
    else:
        allowed = ingest_rate_limiter.allow(
            project_id=context.project_id,
            max_requests=settings.ingest_rate_limit_requests_per_window,
            window_seconds=settings.ingest_rate_limit_window_seconds,
        )
    if not allowed:
        service_metrics.increment("ingest.rejected.rate_limited")
        logger.warning(
            "ingest_rejected rate_limited",
            extra={
                "event": "ingest_rejected",
                "reason": "rate_limited",
                "project_id": str(context.project_id),
                "window_seconds": settings.ingest_rate_limit_window_seconds,
                "max_requests": settings.ingest_rate_limit_requests_per_window,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Ingest rate limit exceeded. "
                f"Try again in {settings.ingest_rate_limit_window_seconds} seconds."
            ),
            headers={"Retry-After": str(settings.ingest_rate_limit_window_seconds)},
        )

    received_at = datetime.now(tz=UTC)
    persist_result = await persist_ingest_batch(
        session=session,
        project_id=context.project_id,
        batch=batch,
        received_at=received_at,
        persist_aggregates=not settings.ingest_async_aggregate_enabled,
    )
    accepted = persist_result.accepted
    if settings.ingest_async_aggregate_enabled:
        enqueued = enqueue_ingest_aggregate_payload(
            IngestAggregatePayload(
                metric_bucket_deltas=persist_result.metric_bucket_deltas,
                error_group_deltas=persist_result.error_group_deltas,
                enqueued_at=received_at,
            )
        )
        if not enqueued:
            service_metrics.increment("ingest.aggregate_worker.enqueue_failed")
    await project_websocket_hub.publish_ingest(
        message=IngestBroadcastMessage(
            project_id=context.project_id,
            accepted=accepted,
            received_at=received_at,
        )
    )
    service_metrics.increment("ingest.accepted.batches")
    service_metrics.increment("ingest.accepted.events", amount=accepted)
    logger.info(
        "ingest_accepted",
        extra={
            "event": "ingest_accepted",
            "project_id": str(context.project_id),
            "accepted_events": accepted,
        },
    )
    return IngestBatchResponse(accepted=accepted)
