from __future__ import annotations

import logging
import os
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlencode
from uuid import UUID

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
from autopulse_backend.core.config import Settings, get_settings
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
from autopulse_backend.services.duckdb_async import run_duckdb_read_sync, run_duckdb_write_sync
from autopulse_backend.services.event_store import event_store_enabled, try_get_duckdb_event_store

OnboardingStep = Literal[
    "authenticate_session",
    "confirm_project",
    "provision_ingest_key",
    "send_first_event",
    "open_diagnosis",
    "completed",
]

router = APIRouter()
logger = logging.getLogger(__name__)


async def _project_has_received_any_event(
    session: AsyncSession,
    *,
    project_id: UUID,
    settings: Settings,
) -> bool:
    """True when SQL ``events`` or DuckDB has at least one row for the project."""
    has_sql_event = bool(
        await session.scalar(select(exists().where(Event.project_id == project_id)))
    )
    if has_sql_event:
        return True
    if not event_store_enabled(settings):
        return False
    store = try_get_duckdb_event_store()
    if store is None:
        return False
    with suppress(Exception):
        duckdb_count = await run_duckdb_read_sync(store.count_events_for_project, project_id)
        return bool(duckdb_count > 0)
    return False


async def _maybe_align_singleton_duckdb_project(
    *,
    session: AsyncSession,
    project_id: UUID,
    settings: Settings,
) -> None:
    """Local/dev guard: merge orphaned DuckDB singleton project ids into active tenant."""
    if not event_store_enabled(settings):
        return
    store = try_get_duckdb_event_store()
    if store is None:
        return
    sql_project_ids = (await session.execute(select(Project.id))).scalars().all()
    if len(sql_project_ids) != 1 or sql_project_ids[0] != project_id:
        return
    with suppress(Exception):
        duckdb_project_ids = await run_duckdb_read_sync(store.list_project_ids)
        if not duckdb_project_ids:
            return
        target = str(project_id)
        stale_ids = [raw for raw in duckdb_project_ids if str(raw).strip() and str(raw) != target]
        if not stale_ids:
            return
        moved_events = 0
        moved_widgets = 0
        for stale in stale_ids:
            events_count, widgets_count = await run_duckdb_write_sync(
                store.reassign_project_id,
                from_project_id=str(stale),
                to_project_id=project_id,
            )
            moved_events += int(events_count)
            moved_widgets += int(widgets_count)
        if moved_events > 0 or moved_widgets > 0:
            logger.warning(
                "duckdb_project_alignment_applied target_project=%s stale_project_ids=%s "
                "moved_events=%s moved_widget_points=%s",
                target,
                ",".join(stale_ids),
                moved_events,
                moved_widgets,
            )


def _sync_env_autopulse_key_bundle(raw_api_key: str) -> None:
    """Best-effort local helper: keep `.env.autopulse` in sync after key issue/rotate."""
    path = Path(os.getenv("AUTOPULSE_ENV_AUTOPULSE_FILE", ".env.autopulse")).expanduser()
    # Standalone: ``/dashboard`` and ``/ingest`` — not under ``/autopulse`` unless client sets base.
    base = (os.getenv("NEXT_PUBLIC_AUTOPULSE_API_BASE_URL") or "").strip()
    content = (
        "# AutoPulse — synced from dashboard API key lifecycle.\n"
        "# Source before static UI build: set -a && source .env.autopulse && set +a\n"
        f"NEXT_PUBLIC_AUTOPULSE_API_BASE_URL={base}\n"
        f"AUTOPULSE_API_KEY={raw_api_key}\n"
        f"NEXT_PUBLIC_AUTOPULSE_API_KEY={raw_api_key}\n"
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.tmp")
        tmp.write_text(content, encoding="utf-8")
        with suppress(OSError):
            os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except OSError:
        return


@router.post("/auth/magic-link/request", response_model=DashboardMagicLinkRequestResponse)
async def request_dashboard_magic_link(
    payload: DashboardMagicLinkRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardMagicLinkRequestResponse:
    settings = get_settings()
    derived_magic_link_base_url = _derive_magic_link_base_url(request, settings)
    raw_token = await create_magic_link_token(
        session=session,
        settings=settings,
        email=payload.email,
        magic_link_base_url=derived_magic_link_base_url,
    )
    dev_magic_link_url: str | None = None
    if settings.dashboard_auth_magic_link_dev_expose_token and raw_token:
        base = (
            derived_magic_link_base_url or settings.dashboard_auth_magic_link_base_url or ""
        ).strip()
        if base:
            query = urlencode({"token": raw_token})
            dev_magic_link_url = f"{base}?{query}" if "?" not in base else f"{base}&{query}"
    return DashboardMagicLinkRequestResponse(
        accepted=True,
        expires_in_seconds=max(60, settings.dashboard_auth_magic_link_ttl_minutes * 60),
        dev_token=raw_token if settings.dashboard_auth_magic_link_dev_expose_token else None,
        dev_magic_link_url=dev_magic_link_url,
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
    await _maybe_align_singleton_duckdb_project(
        session=session,
        project_id=auth_session.project_id,
        settings=settings,
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
    _sync_env_autopulse_key_bundle(raw_api_key)
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
    _sync_env_autopulse_key_bundle(raw_api_key)
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
    settings = get_settings()
    project = await session.get(Project, auth_session.project_id)
    onboarding_completed = project.onboarding_completed if project is not None else False
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
    has_first_event = await _project_has_received_any_event(
        session, project_id=auth_session.project_id, settings=settings
    )
    has_diagnostic_signal = await session.scalar(
        select(
            exists().where(
                ErrorGroupAggregate.project_id == auth_session.project_id,
                ErrorGroupAggregate.count > 0,
            )
        )
    )
    if onboarding_completed:
        current_step: OnboardingStep = "completed"
    elif has_diagnostic_signal:
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
    return DashboardOnboardingStatusResponse(
        session_authenticated=True,
        project_ready=bool(project_exists),
        ingest_key_ready=bool(has_ingest_key),
        first_event_received=bool(has_first_event),
        first_diagnostic_signal_ready=bool(has_diagnostic_signal),
        onboarding_completed=onboarding_completed,
        current_step=current_step,
        next_recommended_action=hints.get(current_step, "Continue onboarding."),
    )


@router.post("/auth/onboarding-complete", response_model=DashboardOnboardingStatusResponse)
async def post_dashboard_onboarding_complete(
    auth_session: Annotated[DashboardAuthSession, Depends(require_dashboard_auth_session)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardOnboardingStatusResponse:
    settings = get_settings()
    project = await session.get(Project, auth_session.project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Project not found")
    has_first_event = await _project_has_received_any_event(
        session, project_id=auth_session.project_id, settings=settings
    )
    if not has_first_event:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="At least one ingested event is required before completing onboarding.",
        )
    project.onboarding_completed = True
    await session.commit()
    await session.refresh(project)
    return await get_dashboard_onboarding_status(auth_session=auth_session, session=session)


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
