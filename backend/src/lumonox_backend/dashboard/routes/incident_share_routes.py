from __future__ import annotations

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
from lumonox_backend.auth.dashboard_security import _now
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
    DashboardIncidentShareGetResponse,
    DashboardIncidentShareListItem,
    DashboardIncidentShareRedeemRequest,
    DashboardIncidentShareRedeemResponse,
    DashboardIncidentShareUpdate,
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


async def _require_org_member_for_project(
    session: AsyncSession, *, project_id: UUID, user_id: UUID
) -> UUID:
    org_id = await _organization_id_for_project(session, project_id)
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has no organization",
        )
    if not await _user_has_org_membership(session, user_id=user_id, organization_id=org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not an organization member"
        )
    return org_id


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
    await _require_org_member_for_project(
        session, project_id=context.project_id, user_id=auth.user_id
    )
    rows = (
        await session.scalars(
            select(DashboardIncidentShare)
            .where(
                DashboardIncidentShare.project_id == context.project_id,
                DashboardIncidentShare.revoked_at.is_(None),
            )
            .order_by(desc(DashboardIncidentShare.updated_at))
            .limit(limit)
        )
    ).all()
    return [DashboardIncidentShareListItem.model_validate(row) for row in rows]


@router.get(
    "/incident-shares/{share_id}",
    response_model=DashboardIncidentShareGetResponse,
)
async def get_incident_share(
    share_id: UUID,
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    auth: Annotated[DashboardAuthSession, Depends(require_dashboard_auth_session)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardIncidentShareGetResponse:
    _ensure_session_project_matches(context, auth)
    await _require_org_member_for_project(
        session, project_id=context.project_id, user_id=auth.user_id
    )
    row = await session.scalar(
        select(DashboardIncidentShare).where(DashboardIncidentShare.id == share_id)
    )
    if row is None or row.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    if row.project_id != context.project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Wrong project")
    scoped = parse_scoped_state_payload(dict(row.scope_state))
    return DashboardIncidentShareGetResponse(
        id=row.id,
        title=row.title,
        project_id=row.project_id,
        scoped_query=scoped_state_to_query_string(scoped),
        notebook_document=row.notebook_document,
    )


@router.patch("/incident-shares/{share_id}", response_model=DashboardIncidentShareListItem)
async def patch_incident_share(
    share_id: UUID,
    payload: DashboardIncidentShareUpdate,
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    auth: Annotated[DashboardAuthSession, Depends(require_dashboard_auth_session)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardIncidentShareListItem:
    _ensure_session_project_matches(context, auth)
    patch = payload.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    row = await session.scalar(
        select(DashboardIncidentShare).where(DashboardIncidentShare.id == share_id)
    )
    if row is None or row.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    if row.project_id != context.project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Wrong project")
    if row.created_by_user_id != auth.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the creator can edit this incident",
        )
    if "title" in patch:
        t = patch["title"]
        row.title = (str(t).strip() or None) if t is not None else None
    if "scope_state" in patch and patch["scope_state"] is not None:
        scoped = parse_scoped_state_payload(patch["scope_state"])
        _ = scoped_state_to_query_string(scoped)
        row.scope_state = scoped.model_dump(by_alias=True)
    if "notebook_document" in patch:
        row.notebook_document = patch["notebook_document"]
    row.updated_at = _now()
    await session.commit()
    await session.refresh(row)
    return DashboardIncidentShareListItem.model_validate(row)


@router.delete("/incident-shares/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_incident_share(
    share_id: UUID,
    context: Annotated[ProjectContext, Depends(authenticate_dashboard_project)],
    auth: Annotated[DashboardAuthSession, Depends(require_dashboard_auth_session)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    _ensure_session_project_matches(context, auth)
    row = await session.scalar(
        select(DashboardIncidentShare).where(DashboardIncidentShare.id == share_id)
    )
    if row is None or row.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    if row.project_id != context.project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Wrong project")
    if row.created_by_user_id != auth.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the creator can delete this incident",
        )
    row.revoked_at = _now()
    row.updated_at = _now()
    await session.commit()


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
    org_id = await _require_org_member_for_project(
        session, project_id=context.project_id, user_id=auth.user_id
    )

    scoped = parse_scoped_state_payload(payload.scope_state)
    _ = scoped_state_to_query_string(scoped)

    allowed: list[str] | None = None
    if payload.access_mode == "restricted" and payload.allowed_user_ids:
        await _validate_allowed_users_in_org(
            session, organization_id=org_id, allowed_user_ids=payload.allowed_user_ids
        )
        allowed = [str(u) for u in payload.allowed_user_ids]

    expires_at = _now() + timedelta(days=payload.expires_in_days)
    title = (payload.title or "").strip() or None
    row = DashboardIncidentShare(
        project_id=context.project_id,
        created_by_user_id=auth.user_id,
        title=title,
        scope_state=scoped.model_dump(by_alias=True),
        notebook_document=payload.notebook_document,
        access_mode=payload.access_mode,
        allowed_user_ids=allowed,
        expires_at=expires_at,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return DashboardIncidentShareCreateResponse(
        share_id=row.id,
        expires_at=row.expires_at,
    )


@router.post("/incident-shares/redeem", response_model=None)
async def redeem_incident_share(
    payload: DashboardIncidentShareRedeemRequest,
    auth: Annotated[DashboardAuthSession, Depends(require_dashboard_auth_session)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardIncidentShareRedeemResponse | JSONResponse:
    row = await session.scalar(
        select(DashboardIncidentShare).where(DashboardIncidentShare.id == payload.share_id)
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
        notebook_document=row.notebook_document,
    )
