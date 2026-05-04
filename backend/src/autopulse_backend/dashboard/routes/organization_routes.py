from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.auth import (
    DashboardAuthSession,
    create_magic_link_token,
    normalize_membership_role,
    require_dashboard_auth_session,
)
from autopulse_backend.auth.dashboard import derive_magic_link_base_url
from autopulse_backend.core.config import get_settings
from autopulse_backend.database import get_db_session
from autopulse_backend.models import (
    DashboardUser,
    GovernanceAuditEvent,
    Organization,
    OrganizationMembership,
    Project,
)
from autopulse_backend.schemas import (
    DashboardInviteMemberRequest,
    DashboardMembershipItem,
    DashboardMembershipListResponse,
    DashboardOrganizationListResponse,
    DashboardOrganizationSummary,
    DashboardProjectSummary,
    DashboardUpdateMemberRoleRequest,
)

router = APIRouter()


async def _require_org_membership(
    *,
    session: AsyncSession,
    organization_id: UUID,
    user_id: UUID,
) -> OrganizationMembership:
    membership = await session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization access required",
        )
    return membership


@router.get("/organizations", response_model=DashboardOrganizationListResponse)
async def list_organizations(
    auth_session: Annotated[DashboardAuthSession, Depends(require_dashboard_auth_session)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardOrganizationListResponse:
    memberships = (
        (
            await session.execute(
                select(OrganizationMembership).where(
                    OrganizationMembership.user_id == auth_session.user_id
                )
            )
        )
        .scalars()
        .all()
    )
    organizations: list[DashboardOrganizationSummary] = []
    for membership in memberships:
        organization = await session.scalar(
            select(Organization).where(Organization.id == membership.organization_id)
        )
        if organization is None:
            continue
        projects = (
            (
                await session.execute(
                    select(Project).where(Project.organization_id == organization.id)
                )
            )
            .scalars()
            .all()
        )
        organizations.append(
            DashboardOrganizationSummary(
                organization_id=str(organization.id),
                organization_name=organization.name,
                role=normalize_membership_role(membership.role) or "member",
                projects=[
                    DashboardProjectSummary(
                        project_id=str(project.id),
                        project_name=project.name,
                        organization_id=str(organization.id),
                    )
                    for project in projects
                ],
            )
        )
    return DashboardOrganizationListResponse(organizations=organizations)


@router.get(
    "/organizations/{organization_id}/members",
    response_model=DashboardMembershipListResponse,
)
async def list_organization_members(
    organization_id: UUID,
    auth_session: Annotated[DashboardAuthSession, Depends(require_dashboard_auth_session)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardMembershipListResponse:
    await _require_org_membership(
        session=session,
        organization_id=organization_id,
        user_id=auth_session.user_id,
    )
    memberships = (
        (
            await session.execute(
                select(OrganizationMembership).where(
                    OrganizationMembership.organization_id == organization_id
                )
            )
        )
        .scalars()
        .all()
    )
    members: list[DashboardMembershipItem] = []
    for membership in memberships:
        user = await session.scalar(
            select(DashboardUser).where(DashboardUser.id == membership.user_id)
        )
        if user is None:
            continue
        members.append(
            DashboardMembershipItem(
                user_id=str(user.id),
                email=user.email,
                role=normalize_membership_role(membership.role) or "member",
                invited_email=membership.invited_email,
                created_at=membership.created_at,
            )
        )
    return DashboardMembershipListResponse(
        organization_id=str(organization_id),
        members=members,
    )


@router.post(
    "/organizations/{organization_id}/members/invite",
    response_model=DashboardMembershipItem,
)
async def invite_organization_member(
    organization_id: UUID,
    payload: DashboardInviteMemberRequest,
    request: Request,
    auth_session: Annotated[DashboardAuthSession, Depends(require_dashboard_auth_session)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardMembershipItem:
    acting_membership = await _require_org_membership(
        session=session,
        organization_id=organization_id,
        user_id=auth_session.user_id,
    )
    acting_role = (acting_membership.role or "").lower()
    if acting_role not in {"owner", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner or admin role required",
        )
    if acting_role == "admin" and payload.role in {"owner", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins cannot assign owner or admin roles",
        )
    invited_user = await session.scalar(
        select(DashboardUser).where(DashboardUser.email == payload.email)
    )
    if invited_user is None:
        invited_user = DashboardUser(email=payload.email)
        session.add(invited_user)
        await session.flush()
    membership = await session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == invited_user.id,
        )
    )
    if membership is None:
        membership = OrganizationMembership(
            organization_id=organization_id,
            user_id=invited_user.id,
            role=payload.role,
            invited_email=payload.email,
        )
        session.add(membership)
    else:
        membership.role = payload.role
        membership.invited_email = payload.email
    session.add(
        GovernanceAuditEvent(
            organization_id=organization_id,
            actor_user_id=auth_session.user_id,
            action="member_invited",
            target_type="organization_member",
            target_id=str(invited_user.id),
            detail={"email": payload.email, "role": payload.role},
        )
    )
    await session.commit()
    await session.refresh(membership)
    settings = get_settings()
    if settings.dashboard_auth_enabled:
        magic_base = derive_magic_link_base_url(request, settings)
        await create_magic_link_token(
            session=session,
            settings=settings,
            email=payload.email,
            magic_link_base_url=magic_base,
        )
    return DashboardMembershipItem(
        user_id=str(invited_user.id),
        email=invited_user.email,
        role=normalize_membership_role(membership.role) or "member",
        invited_email=membership.invited_email,
        created_at=membership.created_at,
    )


@router.put(
    "/organizations/{organization_id}/members/{target_user_id}/role",
    response_model=DashboardMembershipItem,
)
async def update_organization_member_role(
    organization_id: UUID,
    target_user_id: UUID,
    payload: DashboardUpdateMemberRoleRequest,
    auth_session: Annotated[DashboardAuthSession, Depends(require_dashboard_auth_session)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardMembershipItem:
    acting_membership = await _require_org_membership(
        session=session,
        organization_id=organization_id,
        user_id=auth_session.user_id,
    )
    if acting_membership.role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner role required")
    membership = await session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == target_user_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")
    membership.role = payload.role
    session.add(
        GovernanceAuditEvent(
            organization_id=organization_id,
            actor_user_id=auth_session.user_id,
            action="member_role_updated",
            target_type="organization_member",
            target_id=str(target_user_id),
            detail={"role": payload.role},
        )
    )
    await session.commit()
    user = await session.scalar(select(DashboardUser).where(DashboardUser.id == target_user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return DashboardMembershipItem(
        user_id=str(user.id),
        email=user.email,
        role=normalize_membership_role(membership.role) or "member",
        invited_email=membership.invited_email,
        created_at=membership.created_at,
    )
