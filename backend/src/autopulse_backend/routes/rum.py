from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from autopulse_backend.core.config import get_settings
from autopulse_backend.metrics import service_metrics
from autopulse_backend.schemas import DashboardRumEvent, DashboardRumIngestResponse

router = APIRouter(tags=["dashboard"])
logger = logging.getLogger(__name__)


@router.post(
    "/rum", response_model=DashboardRumIngestResponse, status_code=status.HTTP_202_ACCEPTED
)
async def ingest_dashboard_rum(
    request: Request,
) -> DashboardRumIngestResponse:
    settings = get_settings()
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            content_length_bytes = int(content_length)
        except ValueError:
            content_length_bytes = 0
        if content_length_bytes > settings.dashboard_rum_max_request_bytes:
            service_metrics.increment("dashboard.rum.rejected.payload_too_large")
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=(
                    "RUM payload exceeds max request size "
                    f"({settings.dashboard_rum_max_request_bytes} bytes)."
                ),
            )
    payload_bytes = await request.body()
    if len(payload_bytes) > settings.dashboard_rum_max_request_bytes:
        service_metrics.increment("dashboard.rum.rejected.payload_too_large")
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                "RUM payload exceeds max request size "
                f"({settings.dashboard_rum_max_request_bytes} bytes)."
            ),
        )
    try:
        event = DashboardRumEvent.model_validate_json(payload_bytes)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

    service_metrics.increment("dashboard.rum.accepted")
    service_metrics.increment(f"dashboard.rum.type.{event.type}")
    if settings.dashboard_rum_log_payloads:
        logger.info(
            "dashboard_rum_event",
            extra={
                "event": "dashboard_rum_event",
                "rum_type": event.type,
                "path": event.path,
                "session_id": event.session_id,
                "timestamp": event.ts.isoformat(),
                "data": event.data,
            },
        )
    return DashboardRumIngestResponse(accepted=True)
