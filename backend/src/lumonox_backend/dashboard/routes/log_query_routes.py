"""Dashboard SQL log query API (HTTP only).

Clients validate log queries with ``POST /dashboard/log-query/validate``. There is **no**
WebSocket for log streaming and no server-side paginated execute endpoint: structured log
exploration runs through the shared ``POST /dashboard/query`` batch path instead.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from lumonox_backend.auth import ProjectContext, authenticate_dashboard_project
from lumonox_backend.dashboard.log_query import parse_log_query
from lumonox_backend.database import get_db_session
from lumonox_backend.schemas import (
    DashboardLogQueryRequest,
    DashboardLogQueryValidationResponse,
)

router = APIRouter()


@router.post("/log-query/validate", response_model=DashboardLogQueryValidationResponse)
async def validate_dashboard_log_query(
    payload: DashboardLogQueryRequest,
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardLogQueryValidationResponse:
    _ = context
    _ = session
    try:
        parsed = parse_log_query(payload.query)
    except HTTPException as exc:
        return DashboardLogQueryValidationResponse(
            valid=False,
            normalized_query=payload.query.strip(),
            error=str(exc.detail),
        )
    return DashboardLogQueryValidationResponse(
        valid=True,
        normalized_query=parsed.normalized_query,
        error=None,
    )
