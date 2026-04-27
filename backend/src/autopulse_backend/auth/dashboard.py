from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import HTTPConnection

from autopulse_backend.core.config import Settings, get_settings
from autopulse_backend.database import get_db_session
from autopulse_backend.models import DashboardMagicLink, DashboardSession, DashboardUser, Project


@dataclass(frozen=True, slots=True)
class DashboardAuthSession:
    user_id: UUID
    project_id: UUID
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


async def create_magic_link_token(
    *,
    session: AsyncSession,
    settings: Settings,
    email: str,
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
    return raw_token


async def verify_magic_link_and_create_session(
    *,
    session: AsyncSession,
    response: Response,
    settings: Settings,
    token: str,
) -> DashboardAuthSession:
    token_hash = _hash_token(token)
    now = _now()
    magic_link = await session.scalar(
        select(DashboardMagicLink).where(
            DashboardMagicLink.token_hash == token_hash,
            DashboardMagicLink.used_at.is_(None),
            DashboardMagicLink.expires_at >= now,
        )
    )
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
    session_row = DashboardSession(
        user_id=user.id,
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
        email=email,
        expires_at=expires_at,
    )


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
    await session.commit()
    return DashboardAuthSession(
        user_id=user.id,
        project_id=session_row.project_id,
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
