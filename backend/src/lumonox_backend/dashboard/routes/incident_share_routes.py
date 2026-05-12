from __future__ import annotations

import secrets
from datetime import UTC, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from lumonox_backend.auth import (
    DashboardAuthSession,
    ProjectContext,
    authenticate_dashboard_project,
    require_dashboard_auth_session,
)
from lumonox_backend.auth.dashboard_security import _hash_token, _now
from lumonox_backend.dashboard.incident_scoped_query import (
    parse_scoped_state_payload,
    scoped_state_to_query_string,
)
from lumonox_backend.database import get_db_session
from lumonox_backend.models import (
    DashboardIncidentShare,
    OrganizationMembership,
    Project,
)
from lumonox_backend.schemas.dashboard import (
    DashboardIncidentShareCreate,
    DashboardIncidentShareCreateResponse,
    DashboardIncidentShareListItem,
    DashboardIncidentShareRedeemRequest,
    DashboardIncidentShareRedeemResponse,
    DashboardIncidentShareWrongProjectResponse,
)

router = APIRouter()


def _ensure_session_project_matches(context: ProjectContext, auth: DashboardAuthSession) -> None:
    if auth.project_id != context.project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session project does not match requested project",
        )


async def _organization_id_for_project(session: AsyncSession, project_id: UUID) -> UUID | None:
    return await session.scalar(select(Project.organization_id).where(Project.id == project_id))


async def _user_has_org_membership(
    session: AsyncSession, *, user_id: UUID, organization_id: UUID
) -> bool:
    mid = await session.scalar(
        select(OrganizationMembership.id)
        .where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
        )
        .limit(1)
    )
    return mid is not None


async def _validate_allowed_users_in_org(
    session: AsyncSession,
    *,
    organization_id: UUID,
    allowed_user_ids: list[UUID],
) -> None:
    for uid in allowed_user_ids:
        ok = await _user_has_org_membership(session, user_id=uid, organization_id=organization_id)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="allowed_user_ids must be organization members",
            )


@router.get(
    "/incident-shares",
    response_model=list[DashboardIncidentShareListItem],
)
async def list_incident_shares(
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    auth: Annotated[DashboardAuthSession, Depends(require_dashboard_auth_session)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(default=50, ge=1, le=100),
) -> list[DashboardIncidentShareListItem]:
    _ensure_session_project_matches(context, auth)
    rows = (
        await session.scalars(
            select(DashboardIncidentShare)
            .where(DashboardIncidentShare.project_id == context.project_id)
            .order_by(desc(DashboardIncidentShare.created_at))
            .limit(limit)
        )
    ).all()
    return [DashboardIncidentShareListItem.model_validate(row) for row in rows]


@router.post(
    "/incident-shares",
    response_model=DashboardIncidentShareCreateResponse,
)
async def create_incident_share(
    payload: DashboardIncidentShareCreate,
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    auth: Annotated[DashboardAuthSession, Depends(require_dashboard_auth_session)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardIncidentShareCreateResponse:
    _ensure_session_project_matches(context, auth)
    org_id = await _organization_id_for_project(session, context.project_id)
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has no organization; cannot create incident share",
        )

    if not await _user_has_org_membership(session, user_id=auth.user_id, organization_id=org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not an organization member"
        )

    scoped = parse_scoped_state_payload(payload.scope_state)
    _ = scoped_state_to_query_string(scoped)

    allowed: list[str] | None = None
    if payload.access_mode == "restricted" and payload.allowed_user_ids:
        await _validate_allowed_users_in_org(
            session, organization_id=org_id, allowed_user_ids=payload.allowed_user_ids
        )
        allowed = [str(u) for u in payload.allowed_user_ids]

    raw_token = secrets.token_urlsafe(32)
    expires_at = _now() + timedelta(days=payload.expires_in_days)
    row = DashboardIncidentShare(
        project_id=context.project_id,
        created_by_user_id=auth.user_id,
        token_hash=_hash_token(raw_token),
        scope_state=scoped.model_dump(by_alias=True),
        access_mode=payload.access_mode,
        allowed_user_ids=allowed,
        expires_at=expires_at,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return DashboardIncidentShareCreateResponse(
        share_id=row.id,
        token=raw_token,
        expires_at=row.expires_at,
    )


@router.post("/incident-shares/redeem", response_model=None)
async def redeem_incident_share(
    payload: DashboardIncidentShareRedeemRequest,
    auth: Annotated[DashboardAuthSession, Depends(require_dashboard_auth_session)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardIncidentShareRedeemResponse | JSONResponse:
    token_hash = _hash_token(payload.token)
    row = await session.scalar(
        select(DashboardIncidentShare).where(DashboardIncidentShare.token_hash == token_hash)
    )
    if row is None or row.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")

    now = _now()
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    else:
        expires_at = expires_at.astimezone(UTC)
    if expires_at <= now:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Share expired")

    if auth.project_id != row.project_id:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=DashboardIncidentShareWrongProjectResponse(
                project_id=row.project_id
            ).model_dump(mode="json"),
        )

    org_id = await _organization_id_for_project(session, row.project_id)
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Project misconfigured"
        )

    if not await _user_has_org_membership(session, user_id=auth.user_id, organization_id=org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to use this share"
        )

    if row.access_mode == "restricted":
        allowed_raw = row.allowed_user_ids or []
        allowed = {UUID(str(x)) for x in allowed_raw}
        if auth.user_id not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to use this share"
            )

    scoped = parse_scoped_state_payload(dict(row.scope_state))
    return DashboardIncidentShareRedeemResponse(
        scoped_query=scoped_state_to_query_string(scoped),
        project_id=row.project_id,
    )
