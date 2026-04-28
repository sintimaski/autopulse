from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.auth import (
    DashboardAuthSession,
    bootstrap_dashboard_tenant_for_user,
    clear_session_cookie,
    create_magic_link_token,
    generate_api_key,
    get_dashboard_auth_session,
    require_dashboard_auth_session,
    revoke_current_dashboard_session,
    verify_magic_link_and_create_session,
)
from autopulse_backend.config import Settings, get_settings
from autopulse_backend.database import get_db_session
from autopulse_backend.models import ApiKey, GovernanceAuditEvent
from autopulse_backend.schemas import (
    DashboardApiKeyIssueResponse,
    DashboardApiKeyItem,
    DashboardApiKeyListResponse,
    DashboardApiKeyRevokeRequest,
    DashboardApiKeyRotateRequest,
    DashboardApiKeyRotateResponse,
    DashboardBootstrapTenantRequest,
    DashboardBootstrapTenantResponse,
    DashboardMagicLinkRequest,
    DashboardMagicLinkRequestResponse,
    DashboardMagicLinkVerifyRequest,
    DashboardSessionResponse,
)

router = APIRouter()


def _require_owner(auth_session: DashboardAuthSession) -> None:
    if auth_session.membership_role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner role required")


@router.post("/auth/magic-link/request", response_model=DashboardMagicLinkRequestResponse)
async def request_dashboard_magic_link(
    payload: DashboardMagicLinkRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardMagicLinkRequestResponse:
    settings = get_settings()
    derived_magic_link_base_url = _derive_magic_link_base_url(request, settings)
    token = await create_magic_link_token(
        session=session,
        settings=settings,
        email=payload.email,
        magic_link_base_url=derived_magic_link_base_url,
    )
    return DashboardMagicLinkRequestResponse(
        accepted=True,
        expires_in_seconds=max(60, settings.dashboard_auth_magic_link_ttl_minutes * 60),
        dev_magic_link_token=token if settings.dashboard_auth_magic_link_dev_expose_token else None,
    )


def _derive_magic_link_base_url(request: Request, settings: Settings) -> str | None:
    configured = (settings.dashboard_auth_magic_link_base_url or "").strip()
    if configured:
        return configured
    path = request.url.path
    marker = "/dashboard/auth/magic-link/request"
    if marker in path:
        prefix = path.split(marker, 1)[0]
        return f"{request.base_url.scheme}://{request.base_url.netloc}{prefix}/ui/auth/magic-link"
    return None


@router.post("/auth/magic-link/verify", response_model=DashboardSessionResponse)
async def verify_dashboard_magic_link(
    payload: DashboardMagicLinkVerifyRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardSessionResponse:
    settings = get_settings()
    auth_session = await verify_magic_link_and_create_session(
        session=session,
        response=response,
        settings=settings,
        token=payload.token,
        request=request,
    )
    return DashboardSessionResponse(
        authenticated=True,
        email=auth_session.email,
        expires_at=auth_session.expires_at,
        project_id=str(auth_session.project_id),
        organization_id=(
            str(auth_session.organization_id) if auth_session.organization_id is not None else None
        ),
        membership_role=(
            auth_session.membership_role
            if auth_session.membership_role in {"owner", "member"}
            else None
        ),
    )


@router.post("/auth/bootstrap", response_model=DashboardBootstrapTenantResponse)
async def bootstrap_dashboard_tenant(
    payload: DashboardBootstrapTenantRequest,
    auth_session: Annotated[DashboardAuthSession, Depends(require_dashboard_auth_session)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardBootstrapTenantResponse:
    organization_id, project_id = await bootstrap_dashboard_tenant_for_user(
        session=session,
        user_id=auth_session.user_id,
        email=auth_session.email,
        organization_name=payload.organization_name,
        project_name=payload.project_name,
    )
    raw_api_key, key_id, key_salt, key_hash = generate_api_key()
    session.add(
        ApiKey(
            project_id=project_id,
            key_id=key_id,
            key_salt=key_salt,
            key_hash=key_hash,
        )
    )
    await session.commit()
    return DashboardBootstrapTenantResponse(
        organization_id=str(organization_id),
        project_id=str(project_id),
        organization_name=payload.organization_name,
        project_name=payload.project_name,
        api_key=raw_api_key,
    )


@router.get("/auth/api-keys", response_model=DashboardApiKeyListResponse)
async def list_dashboard_api_keys(
    auth_session: Annotated[DashboardAuthSession, Depends(require_dashboard_auth_session)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardApiKeyListResponse:
    _require_owner(auth_session)
    rows = (
        (
            await session.execute(
                select(ApiKey)
                .where(ApiKey.project_id == auth_session.project_id)
                .order_by(ApiKey.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return DashboardApiKeyListResponse(
        items=[
            DashboardApiKeyItem(
                key_id=row.key_id,
                created_at=row.created_at,
                revoked_at=row.revoked_at,
            )
            for row in rows
        ]
    )


@router.post("/auth/api-keys/issue", response_model=DashboardApiKeyIssueResponse)
async def issue_dashboard_api_key(
    auth_session: Annotated[DashboardAuthSession, Depends(require_dashboard_auth_session)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardApiKeyIssueResponse:
    _require_owner(auth_session)
    raw_api_key, key_id, key_salt, key_hash = generate_api_key()
    created_at = datetime.now(tz=UTC)
    session.add(
        ApiKey(
            project_id=auth_session.project_id,
            key_id=key_id,
            key_salt=key_salt,
            key_hash=key_hash,
            created_at=created_at,
        )
    )
    session.add(
        GovernanceAuditEvent(
            organization_id=auth_session.organization_id,
            actor_user_id=auth_session.user_id,
            action="api_key_issued",
            target_type="api_key",
            target_id=key_id,
            detail={"project_id": str(auth_session.project_id)},
        )
    )
    await session.commit()
    return DashboardApiKeyIssueResponse(
        key_id=key_id,
        api_key=raw_api_key,
        created_at=created_at,
    )


@router.post("/auth/api-keys/rotate", response_model=DashboardApiKeyRotateResponse)
async def rotate_dashboard_api_key(
    payload: DashboardApiKeyRotateRequest,
    auth_session: Annotated[DashboardAuthSession, Depends(require_dashboard_auth_session)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardApiKeyRotateResponse:
    _require_owner(auth_session)
    existing = await session.scalar(
        select(ApiKey).where(
            ApiKey.project_id == auth_session.project_id,
            ApiKey.key_id == payload.key_id,
            ApiKey.revoked_at.is_(None),
        )
    )
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    rotated_at = datetime.now(tz=UTC)
    existing.revoked_at = rotated_at
    raw_api_key, next_key_id, key_salt, key_hash = generate_api_key()
    session.add(
        ApiKey(
            project_id=auth_session.project_id,
            key_id=next_key_id,
            key_salt=key_salt,
            key_hash=key_hash,
            created_at=rotated_at,
        )
    )
    session.add(
        GovernanceAuditEvent(
            organization_id=auth_session.organization_id,
            actor_user_id=auth_session.user_id,
            action="api_key_rotated",
            target_type="api_key",
            target_id=payload.key_id,
            detail={"replacement_key_id": next_key_id, "project_id": str(auth_session.project_id)},
        )
    )
    await session.commit()
    return DashboardApiKeyRotateResponse(
        revoked_key_id=payload.key_id,
        replacement_key_id=next_key_id,
        replacement_api_key=raw_api_key,
        rotated_at=rotated_at,
    )


@router.post("/auth/api-keys/revoke", response_model=DashboardApiKeyItem)
async def revoke_dashboard_api_key(
    payload: DashboardApiKeyRevokeRequest,
    auth_session: Annotated[DashboardAuthSession, Depends(require_dashboard_auth_session)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardApiKeyItem:
    _require_owner(auth_session)
    existing = await session.scalar(
        select(ApiKey).where(
            ApiKey.project_id == auth_session.project_id,
            ApiKey.key_id == payload.key_id,
            ApiKey.revoked_at.is_(None),
        )
    )
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    existing.revoked_at = datetime.now(tz=UTC)
    session.add(
        GovernanceAuditEvent(
            organization_id=auth_session.organization_id,
            actor_user_id=auth_session.user_id,
            action="api_key_revoked",
            target_type="api_key",
            target_id=payload.key_id,
            detail={"project_id": str(auth_session.project_id)},
        )
    )
    await session.commit()
    return DashboardApiKeyItem(
        key_id=existing.key_id,
        created_at=existing.created_at,
        revoked_at=existing.revoked_at,
    )


@router.get("/auth/session", response_model=DashboardSessionResponse)
async def get_dashboard_session(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardSessionResponse:
    settings = get_settings()
    auth_session = await get_dashboard_auth_session(
        session=session,
        settings=settings,
        request=request,
    )
    if auth_session is None:
        return DashboardSessionResponse(authenticated=False)
    return DashboardSessionResponse(
        authenticated=True,
        email=auth_session.email,
        expires_at=auth_session.expires_at,
        project_id=str(auth_session.project_id),
        organization_id=(
            str(auth_session.organization_id) if auth_session.organization_id is not None else None
        ),
        membership_role=(
            auth_session.membership_role
            if auth_session.membership_role in {"owner", "member"}
            else None
        ),
    )


@router.post("/auth/logout", response_model=DashboardSessionResponse)
async def logout_dashboard_session(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardSessionResponse:
    settings = get_settings()
    await revoke_current_dashboard_session(
        request=request,
        session=session,
        settings=settings,
    )
    clear_session_cookie(response, settings)
    return DashboardSessionResponse(authenticated=False)
