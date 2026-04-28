from __future__ import annotations

import hashlib
import quopri
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import HTTPConnection

from autopulse_backend.core.config import Settings, get_settings
from autopulse_backend.database import get_db_session
from autopulse_backend.models import (
    DashboardMagicLink,
    DashboardSession,
    DashboardUser,
    Organization,
    OrganizationMembership,
    Project,
)
from autopulse_backend.services.alert_service import AlertSignal, EmailAlertSender


@dataclass(frozen=True, slots=True)
class DashboardAuthSession:
    user_id: UUID
    project_id: UUID
    organization_id: UUID | None
    membership_role: str | None
    email: str
    expires_at: datetime


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def _unauthorized(message: str = "Authentication required") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)


def _forbidden(message: str = "Email is not allowed for dashboard access") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)


def _cookie_name(settings: Settings) -> str:
    return settings.dashboard_auth_session_cookie_name or "autopulse_dashboard_session"


def _set_session_cookie(
    response: Response, settings: Settings, token: str, *, expires_at: datetime
) -> None:
    response.set_cookie(
        key=_cookie_name(settings),
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        expires=int(expires_at.timestamp()),
        max_age=max(1, int((expires_at - _now()).total_seconds())),
        path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=_cookie_name(settings),
        path="/",
    )


async def _resolve_default_project_id(session: AsyncSession) -> UUID:
    project = await session.scalar(select(Project).order_by(Project.created_at.asc()).limit(1))
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No project exists yet for dashboard access.",
        )
    return project.id


async def _ensure_project_organization_membership(
    *,
    session: AsyncSession,
    project_id: UUID,
    user_id: UUID,
    email: str,
) -> tuple[UUID | None, str | None]:
    project = await session.scalar(select(Project).where(Project.id == project_id))
    if project is None:
        return None, None
    if project.organization_id is None:
        organization = Organization(name=f"{project.name} Organization")
        session.add(organization)
        await session.flush()
        project.organization_id = organization.id
    organization_id = project.organization_id
    if organization_id is None:
        return None, None
    membership = await session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
        )
    )
    if membership is None:
        membership = OrganizationMembership(
            organization_id=organization_id,
            user_id=user_id,
            role="owner",
            invited_email=email,
        )
        session.add(membership)
        await session.flush()
    return organization_id, membership.role


async def create_magic_link_token(
    *,
    session: AsyncSession,
    settings: Settings,
    email: str,
    magic_link_base_url: str | None = None,
) -> str | None:
    normalized_email = _normalize_email(email)
    allowed_email = _normalize_email(settings.dashboard_auth_allowed_email or "")
    if not settings.dashboard_auth_enabled:
        raise _forbidden("Dashboard authentication is disabled.")
    if allowed_email and normalized_email != allowed_email:
        # Return None for unknown email so request endpoint remains non-enumerating.
        return None

    raw_token = secrets.token_urlsafe(32)
    expires_at = _now() + timedelta(minutes=settings.dashboard_auth_magic_link_ttl_minutes)
    session.add(
        DashboardMagicLink(
            email=normalized_email,
            token_hash=_hash_token(raw_token),
            expires_at=expires_at,
        )
    )
    await session.commit()
    await _send_magic_link_email_best_effort(
        session=session,
        settings=settings,
        email=normalized_email,
        token=raw_token,
        expires_at=expires_at,
        magic_link_base_url=magic_link_base_url,
    )
    return raw_token


def _build_magic_link_url(settings: Settings, token: str, *, base_url: str | None = None) -> str:
    resolved_base_url = (
        base_url if base_url is not None else settings.dashboard_auth_magic_link_base_url
    )
    base = (resolved_base_url or "").strip() or "/auth/magic-link"
    query = urlencode({"token": token})
    return f"{base}?{query}" if "?" not in base else f"{base}&{query}"


async def _send_magic_link_email_best_effort(
    *,
    session: AsyncSession,
    settings: Settings,
    email: str,
    token: str,
    expires_at: datetime,
    magic_link_base_url: str | None = None,
) -> None:
    provider = (settings.alert_email_provider or "").strip().lower()
    if not provider:
        return
    link = _build_magic_link_url(settings, token, base_url=magic_link_base_url)
    project_id = await _resolve_default_project_id(session)
    signal = AlertSignal(
        project_id=project_id,
        alert_type="dashboard_magic_link",
        destination_email=email,
        triggered_at=_now(),
        window_start=_now(),
        window_end=expires_at,
        detail={
            "magic_link": link,
            "expires_at": expires_at.isoformat(),
            "email": email,
        },
    )
    sender = EmailAlertSender(
        provider=provider,
        api_key=settings.alert_email_api_key,
        from_email=settings.alert_email_from,
        smtp_host=settings.alert_email_smtp_host,
        smtp_port=settings.alert_email_smtp_port,
        smtp_use_tls=settings.alert_email_smtp_use_tls,
        smtp_username=settings.alert_email_smtp_username,
        smtp_password=settings.alert_email_smtp_password,
        file_outbox_dir=settings.alert_email_file_outbox_dir,
    )
    try:
        await sender.send(signal)
    except (TimeoutError, OSError, RuntimeError, ValueError):
        # Keep magic-link request non-failing even when delivery is misconfigured.
        return


async def verify_magic_link_and_create_session(
    *,
    session: AsyncSession,
    response: Response,
    settings: Settings,
    token: str,
) -> DashboardAuthSession:
    token_hashes = {_hash_token(candidate) for candidate in _token_candidates(token)}
    now = _now()
    magic_link = None
    for token_hash in token_hashes:
        magic_link = await session.scalar(
            select(DashboardMagicLink).where(
                DashboardMagicLink.token_hash == token_hash,
                DashboardMagicLink.used_at.is_(None),
                DashboardMagicLink.expires_at >= now,
            )
        )
        if magic_link is not None:
            break
    if magic_link is None:
        raise _unauthorized("Invalid or expired magic link.")

    email = _normalize_email(magic_link.email)
    user = await session.scalar(select(DashboardUser).where(DashboardUser.email == email))
    if user is None:
        user = DashboardUser(email=email)
        session.add(user)
        await session.flush()
    user.last_login_at = now
    magic_link.used_at = now

    raw_session_token = secrets.token_urlsafe(48)
    expires_at = now + timedelta(minutes=settings.dashboard_auth_session_ttl_minutes)
    project_id = await _resolve_default_project_id(session)
    organization_id, membership_role = await _ensure_project_organization_membership(
        session=session,
        project_id=project_id,
        user_id=user.id,
        email=email,
    )
    session_row = DashboardSession(
        user_id=user.id,
        organization_id=organization_id,
        project_id=project_id,
        token_hash=_hash_token(raw_session_token),
        expires_at=expires_at,
        last_seen_at=now,
    )
    session.add(session_row)
    await session.commit()
    _set_session_cookie(response, settings, raw_session_token, expires_at=expires_at)
    return DashboardAuthSession(
        user_id=user.id,
        project_id=project_id,
        organization_id=organization_id,
        membership_role=membership_role,
        email=email,
        expires_at=expires_at,
    )


def _token_candidates(raw_token: str) -> list[str]:
    """
    Accept small token corruptions that commonly happen when users copy from raw
    quoted-printable `.eml` files (e.g. leading `3D`, inserted spaces, soft-break `=`).
    """
    base = (raw_token or "").strip()
    if not base:
        return []
    candidates: list[str] = [base]
    collapsed = "".join(base.split())
    candidates.append(collapsed)
    no_equals = collapsed.replace("=", "")
    candidates.append(no_equals)
    if no_equals.startswith("3D"):
        candidates.append(no_equals[2:])
    # Raw .eml copy can contain quoted-printable escapes (`=3D...`) in query token.
    qp_decoded = quopri.decodestring(collapsed.encode("utf-8")).decode("utf-8", "ignore").strip()
    if qp_decoded:
        candidates.append(qp_decoded)
        qp_no_equals = qp_decoded.replace("=", "")
        candidates.append(qp_no_equals)
        if qp_no_equals.startswith("3D"):
            candidates.append(qp_no_equals[2:])
    # Keep only url-safe token characters for recovery from punctuation artifacts.
    for candidate in list(candidates):
        cleaned = re.sub(r"[^A-Za-z0-9_-]", "", candidate)
        if cleaned:
            candidates.append(cleaned)
            if cleaned.startswith("3D"):
                candidates.append(cleaned[2:])
    # Preserve order, drop empties and duplicates.
    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            ordered.append(candidate)
    return ordered


async def get_dashboard_auth_session(
    *,
    session: AsyncSession,
    settings: Settings,
    request: HTTPConnection,
) -> DashboardAuthSession | None:
    raw_token = request.cookies.get(_cookie_name(settings))
    if not raw_token:
        return None
    now = _now()
    session_row = await session.scalar(
        select(DashboardSession).where(
            DashboardSession.token_hash == _hash_token(raw_token),
            DashboardSession.revoked_at.is_(None),
            DashboardSession.expires_at >= now,
        )
    )
    if session_row is None:
        return None
    user = await session.scalar(
        select(DashboardUser).where(DashboardUser.id == session_row.user_id)
    )
    if user is None:
        return None
    session_row.last_seen_at = now
    organization_id = session_row.organization_id
    membership_role = None
    if organization_id is None:
        organization_id, membership_role = await _ensure_project_organization_membership(
            session=session,
            project_id=session_row.project_id,
            user_id=user.id,
            email=user.email,
        )
        session_row.organization_id = organization_id
    if organization_id is not None and membership_role is None:
        membership = await session.scalar(
            select(OrganizationMembership).where(
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.user_id == user.id,
            )
        )
        membership_role = membership.role if membership is not None else None
    await session.commit()
    return DashboardAuthSession(
        user_id=user.id,
        project_id=session_row.project_id,
        organization_id=organization_id,
        membership_role=membership_role,
        email=user.email,
        expires_at=session_row.expires_at,
    )


async def require_dashboard_auth_session(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardAuthSession:
    settings = get_settings()
    auth_session = await get_dashboard_auth_session(
        session=session, settings=settings, request=request
    )
    if auth_session is None:
        raise _unauthorized()
    return auth_session


async def revoke_current_dashboard_session(
    *,
    request: Request,
    session: AsyncSession,
    settings: Settings,
) -> bool:
    raw_token = request.cookies.get(_cookie_name(settings))
    if not raw_token:
        return False
    now = _now()
    row = await session.scalar(
        select(DashboardSession).where(
            DashboardSession.token_hash == _hash_token(raw_token),
            DashboardSession.revoked_at.is_(None),
        )
    )
    if row is None:
        return False
    row.revoked_at = now
    await session.commit()
    return True
