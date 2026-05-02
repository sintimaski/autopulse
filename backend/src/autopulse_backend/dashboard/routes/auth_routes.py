from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import exists

from autopulse_backend.auth import (
    DashboardAuthSession,
    bootstrap_dashboard_tenant_for_user,
    clear_session_cookie,
    create_magic_link_token,
    generate_api_key,
    get_dashboard_auth_session,
    normalize_membership_role,
    require_dashboard_auth_session,
    require_owner,
    require_owner_or_admin,
    revoke_current_dashboard_session,
    verify_magic_link_and_create_session,
)
from autopulse_backend.config import Settings, get_settings
from autopulse_backend.database import get_db_session
from autopulse_backend.models import (
    ApiKey,
    ErrorGroupAggregate,
    Event,
    GovernanceAuditEvent,
    Project,
)
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
    DashboardOnboardingStatusResponse,
    DashboardSessionResponse,
)

router = APIRouter()


@router.post("/auth/magic-link/request", response_model=DashboardMagicLinkRequestResponse)
async def request_dashboard_magic_link(
    payload: DashboardMagicLinkRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardMagicLinkRequestResponse:
    settings = get_settings()
    derived_magic_link_base_url = _derive_magic_link_base_url(request, settings)
    await create_magic_link_token(
        session=session,
        settings=settings,
        email=payload.email,
        magic_link_base_url=derived_magic_link_base_url,
    )
    return DashboardMagicLinkRequestResponse(
        accepted=True,
        expires_in_seconds=max(60, settings.dashboard_auth_magic_link_ttl_minutes * 60),
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
        membership_role=normalize_membership_role(auth_session.membership_role),
    )


@router.post("/auth/bootstrap", response_model=DashboardBootstrapTenantResponse)
async def bootstrap_dashboard_tenant(
    payload: DashboardBootstrapTenantRequest,
    auth_session: Annotated[DashboardAuthSession, Depends(require_dashboard_auth_session)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardBootstrapTenantResponse:
    require_owner(auth_session)
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
    require_owner_or_admin(auth_session)
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
    require_owner_or_admin(auth_session)
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
    require_owner_or_admin(auth_session)
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
    require_owner_or_admin(auth_session)
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
        membership_role=normalize_membership_role(auth_session.membership_role),
    )


@router.get("/auth/onboarding-status", response_model=DashboardOnboardingStatusResponse)
async def get_dashboard_onboarding_status(
    auth_session: Annotated[DashboardAuthSession, Depends(require_dashboard_auth_session)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardOnboardingStatusResponse:
    project_exists = await session.scalar(
        select(exists().where(Project.id == auth_session.project_id))
    )
    has_ingest_key = await session.scalar(
        select(
            exists().where(
                ApiKey.project_id == auth_session.project_id, ApiKey.revoked_at.is_(None)
            )
        )
    )
    has_first_event = await session.scalar(
        select(exists().where(Event.project_id == auth_session.project_id))
    )
    has_diagnostic_signal = await session.scalar(
        select(
            exists().where(
                ErrorGroupAggregate.project_id == auth_session.project_id,
                ErrorGroupAggregate.count > 0,
            )
        )
    )
    if has_diagnostic_signal:
        current_step = "completed"
    elif has_first_event:
        current_step = "open_diagnosis"
    elif has_ingest_key:
        current_step = "send_first_event"
    elif project_exists:
        current_step = "provision_ingest_key"
    else:
        current_step = "confirm_project"
    hints: dict[str, str] = {
        "authenticate_session": "Sign in with magic link or OIDC to continue.",
        "confirm_project": "Confirm your project exists or create one from onboarding.",
        "provision_ingest_key": "Issue an ingest API key from Settings and store it in your app.",
        "send_first_event": (
            "Send traffic from your instrumented app so AutoPulse can receive events."
        ),
        "open_diagnosis": "Open Diagnosis to view grouped errors and recent failures.",
        "completed": "You are receiving diagnostic signals for this project.",
    }
    onboarding_step = cast(
        Literal[
            "authenticate_session",
            "confirm_project",
            "provision_ingest_key",
            "send_first_event",
            "open_diagnosis",
            "completed",
        ],
        current_step,
    )
    return DashboardOnboardingStatusResponse(
        session_authenticated=True,
        project_ready=bool(project_exists),
        ingest_key_ready=bool(has_ingest_key),
        first_event_received=bool(has_first_event),
        first_diagnostic_signal_ready=bool(has_diagnostic_signal),
        current_step=onboarding_step,
        next_recommended_action=hints.get(current_step, "Continue onboarding."),
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
