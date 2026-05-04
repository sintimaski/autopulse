from __future__ import annotations

import hashlib
import quopri
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http.cookies import CookieError, SimpleCookie
from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
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

# Legacy default project name from older local bootstrap flows (keep for DB adoption).
_LEGACY_SINGLETON_BOOTSTRAP_PROJECT_NAME = "AutoPulse Embedded Project"


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


def _email_matches_allowed_domains(email: str, domains: tuple[str, ...]) -> bool:
    if not domains:
        return False
    normalized = _normalize_email(email)
    if "@" not in normalized:
        return False
    _, _, domain = normalized.partition("@")
    host = domain.strip().lower()
    return any(host == d or host.endswith(f".{d}") for d in domains)


def _hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def _unauthorized(message: str = "Authentication required") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)


def _forbidden(message: str = "Email is not allowed for dashboard access") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)


def _cookie_name(settings: Settings) -> str:
    return settings.dashboard_auth_session_cookie_name or "autopulse_dashboard_session"


def _raw_dashboard_session_token_from_request(
    request: HTTPConnection,
    settings: Settings,
) -> str | None:
    """Resolve the dashboard session cookie value.

    Starlette's ``request.cookies`` is normally enough; some WebSocket upgrade paths
    expose the raw ``Cookie`` header more reliably than the parsed mapping, so we
    fall back to parsing the header manually.
    """

    name = _cookie_name(settings)
    raw = request.cookies.get(name)
    if raw:
        return raw
    header = request.headers.get("cookie")
    if not header:
        return None
    jar = SimpleCookie()
    try:
        jar.load(header)
    except CookieError:
        return None
    morsel = jar.get(name)
    if morsel is None:
        return None
    return morsel.value


def _request_is_secure(request: HTTPConnection) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto:
        first_proto = forwarded_proto.split(",", maxsplit=1)[0].strip().lower()
        if first_proto:
            return first_proto == "https"
    return request.url.scheme == "https"


def _set_session_cookie(
    response: Response,
    settings: Settings,
    request: HTTPConnection,
    token: str,
    *,
    expires_at: datetime,
) -> None:
    response.set_cookie(
        key=_cookie_name(settings),
        value=token,
        httponly=True,
        secure=_request_is_secure(request),
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
    """Resolve or create a default project when no tenant exists at all.

    Use this only as a last resort during empty-database bootstrap. Do NOT use it to
    silently bind newly-verifying users to the earliest project they do not own. The
    real per-user resolution lives in ``_resolve_project_for_user``.
    """
    project = await session.scalar(select(Project).order_by(Project.created_at.asc()).limit(1))
    if project is None:
        organization = Organization(name="Default Organization")
        session.add(organization)
        await session.flush()
        project = Project(name="Default Project", organization_id=organization.id)
        session.add(project)
        await session.flush()
    return project.id


async def _try_adopt_singleton_legacy_bootstrap_project(
    *,
    session: AsyncSession,
    user_id: UUID,
    email: str,
) -> tuple[UUID, UUID, str] | None:
    """Bind the first dashboard login to a lone legacy bootstrap project row.

    Without this, magic-link bootstrap creates a separate ``Default Project`` while ingest
    continues to use an API key tied to the singleton project, so the UI never sees events.
    """
    total_projects = await session.scalar(select(func.count()).select_from(Project))
    if total_projects != 1:
        return None
    project = await session.scalar(select(Project))
    if (
        project is None
        or project.name != _LEGACY_SINGLETON_BOOTSTRAP_PROJECT_NAME
        or project.organization_id is not None
    ):
        return None
    organization = Organization(name=f"{email}'s Organization")
    session.add(organization)
    await session.flush()
    project.organization_id = organization.id
    new_membership = OrganizationMembership(
        organization_id=organization.id,
        user_id=user_id,
        role="owner",
        invited_email=email,
    )
    session.add(new_membership)
    await session.flush()
    return project.id, organization.id, new_membership.role


async def _resolve_project_for_user(
    *,
    session: AsyncSession,
    user_id: UUID,
    email: str,
) -> tuple[UUID, UUID | None, str | None]:
    """Return ``(project_id, organization_id, membership_role)`` for this user.

    Resolution order:
    1. Most-recent existing membership for this user -> their org's oldest project
       (creating a project under that org if it has none).
    2. Empty-database bootstrap -> create a fresh org + project owned by this user.
    3. Otherwise (projects exist but none owned by this user) -> create a fresh
       org + project for this user so they never land on tenants they do not own.
    """
    membership = await session.scalar(
        select(OrganizationMembership)
        .where(OrganizationMembership.user_id == user_id)
        .order_by(OrganizationMembership.created_at.desc())
        .limit(1)
    )
    if membership is not None:
        organization_id = membership.organization_id
        project = await session.scalar(
            select(Project)
            .where(Project.organization_id == organization_id)
            .order_by(Project.created_at.asc())
            .limit(1)
        )
        if project is None:
            project = Project(name="Default Project", organization_id=organization_id)
            session.add(project)
            await session.flush()
        return project.id, organization_id, membership.role

    adopted = await _try_adopt_singleton_legacy_bootstrap_project(
        session=session, user_id=user_id, email=email
    )
    if adopted is not None:
        return adopted

    organization = Organization(name=f"{email}'s Organization")
    session.add(organization)
    await session.flush()
    project = Project(name="Default Project", organization_id=organization.id)
    session.add(project)
    await session.flush()
    new_membership = OrganizationMembership(
        organization_id=organization.id,
        user_id=user_id,
        role="owner",
        invited_email=email,
    )
    session.add(new_membership)
    await session.flush()
    return project.id, organization.id, new_membership.role


async def bootstrap_dashboard_tenant_for_user(
    *,
    session: AsyncSession,
    user_id: UUID,
    email: str,
    organization_name: str,
    project_name: str,
) -> tuple[UUID, UUID]:
    organization = Organization(name=organization_name.strip() or "Default Organization")
    session.add(organization)
    await session.flush()
    project = Project(
        name=project_name.strip() or "Default Project",
        organization_id=organization.id,
    )
    session.add(project)
    await session.flush()
    membership = OrganizationMembership(
        organization_id=organization.id,
        user_id=user_id,
        role="owner",
        invited_email=email,
    )
    session.add(membership)
    await session.commit()
    return organization.id, project.id


async def create_magic_link_token(
    *,
    session: AsyncSession,
    settings: Settings,
    email: str,
    magic_link_base_url: str | None = None,
) -> str | None:
    normalized_email = _normalize_email(email)
    if not settings.dashboard_auth_enabled:
        raise _forbidden("Dashboard authentication is disabled.")
    if not await dashboard_email_allowed_for_sign_in(session, settings, normalized_email):
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


def derive_magic_link_base_url(request: HTTPConnection, settings: Settings) -> str | None:
    """Build absolute magic-link verify URL when the request hits a ``/dashboard/...`` route."""
    configured = (settings.dashboard_auth_magic_link_base_url or "").strip()
    if configured:
        return configured
    path = request.url.path
    if "/dashboard/" in path:
        prefix = path.split("/dashboard/", 1)[0]
        return f"{request.base_url.scheme}://{request.base_url.netloc}{prefix}/ui/auth/magic-link"
    return None


async def _dashboard_user_has_organization_membership(
    session: AsyncSession, normalized_email: str
) -> bool:
    user_id = await session.scalar(
        select(DashboardUser.id).where(DashboardUser.email == normalized_email)
    )
    if user_id is None:
        return False
    return bool(
        await session.scalar(
            select(OrganizationMembership.id)
            .where(OrganizationMembership.user_id == user_id)
            .limit(1)
        )
    )


async def dashboard_email_allowed_for_sign_in(
    session: AsyncSession,
    settings: Settings,
    normalized_email: str,
) -> bool:
    """True when this email may request a magic link or complete OIDC sign-in.

    Uses configured allowlist/domain rules, then allows any email that already has at
    least one organization membership (e.g. invited teammates).
    """
    allowed_email = _normalize_email(settings.dashboard_auth_allowed_email or "")
    domains = settings.dashboard_allowed_email_domains
    env = (settings.autopulse_env or "development").strip().lower()
    if allowed_email:
        if normalized_email == allowed_email:
            return True
    elif domains:
        if _email_matches_allowed_domains(normalized_email, domains):
            return True
    else:
        if env != "production":
            return True

    return await _dashboard_user_has_organization_membership(session, normalized_email)


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


async def issue_dashboard_session_for_user(
    *,
    session: AsyncSession,
    response: Response,
    settings: Settings,
    request: HTTPConnection,
    email: str,
    idp_provider: str | None = None,
    idp_subject: str | None = None,
) -> DashboardAuthSession:
    """Create or refresh a dashboard user; optionally link IdP claims; set session cookie."""
    normalized_email = _normalize_email(email)
    now = _now()
    user: DashboardUser | None = None
    if idp_provider and idp_subject:
        user = await session.scalar(
            select(DashboardUser).where(
                DashboardUser.idp_provider == idp_provider,
                DashboardUser.idp_subject == idp_subject,
            )
        )
    if user is None:
        user = await session.scalar(
            select(DashboardUser).where(DashboardUser.email == normalized_email)
        )
    if user is None:
        user = DashboardUser(
            email=normalized_email,
            idp_provider=idp_provider,
            idp_subject=idp_subject,
        )
        session.add(user)
        await session.flush()
    else:
        user.email = normalized_email
        if idp_provider and idp_subject:
            user.idp_provider = idp_provider
            user.idp_subject = idp_subject
    user.last_login_at = now

    raw_session_token = secrets.token_urlsafe(48)
    expires_at = now + timedelta(minutes=settings.dashboard_auth_session_ttl_minutes)
    project_id, organization_id, membership_role = await _resolve_project_for_user(
        session=session,
        user_id=user.id,
        email=normalized_email,
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
    _set_session_cookie(response, settings, request, raw_session_token, expires_at=expires_at)
    return DashboardAuthSession(
        user_id=user.id,
        project_id=project_id,
        organization_id=organization_id,
        membership_role=membership_role,
        email=normalized_email,
        expires_at=expires_at,
    )


async def verify_magic_link_and_create_session(
    *,
    session: AsyncSession,
    response: Response,
    settings: Settings,
    token: str,
    request: HTTPConnection,
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
    magic_link.used_at = now
    await session.flush()
    return await issue_dashboard_session_for_user(
        session=session,
        response=response,
        settings=settings,
        request=request,
        email=email,
        idp_provider=None,
        idp_subject=None,
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
    raw_token = _raw_dashboard_session_token_from_request(request, settings)
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
    organization_id = session_row.organization_id
    membership_role: str | None = None
    if organization_id is None:
        # Legacy session predates organization tracking. Look up the project's org,
        # then require an existing membership for this user. Never silently grant
        # ownership on the auth heartbeat path.
        project = await session.scalar(select(Project).where(Project.id == session_row.project_id))
        if project is None or project.organization_id is None:
            return None
        organization_id = project.organization_id
        session_row.organization_id = organization_id
    membership = await session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user.id,
        )
    )
    if membership is None:
        # Session references a tenant the user does not actually belong to.
        # Treat as unauthenticated so the caller forces a clean re-login that
        # routes through ``_resolve_project_for_user``.
        return None
    membership_role = membership.role
    # Keep plain values before any write/rollback path; rollback can expire ORM attributes
    # and later attribute access may trigger async IO from sync contexts (MissingGreenlet).
    user_id = user.id
    user_email = user.email
    project_id = session_row.project_id
    session_expires_at = session_row.expires_at
    # Defer mutable writes until all read queries complete so auth checks do not
    # trigger an autoflush UPDATE in the middle of SELECT statements.
    session_row.last_seen_at = now
    try:
        await session.commit()
    except OperationalError:
        # SQLite can transiently lock under concurrent local requests.
        # Keep auth read-path healthy even if the heartbeat write is skipped.
        await session.rollback()
    return DashboardAuthSession(
        user_id=user_id,
        project_id=project_id,
        organization_id=organization_id,
        membership_role=membership_role,
        email=user_email,
        expires_at=session_expires_at,
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
    raw_token = _raw_dashboard_session_token_from_request(request, settings)
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


async def update_dashboard_session_active_project(
    *,
    request: HTTPConnection,
    session: AsyncSession,
    settings: Settings,
    user_id: UUID,
    next_project_id: UUID,
) -> DashboardAuthSession:
    """Point the current cookie session at another project the user may access.

    Without this, ``_resolve_project_for_user`` only runs at login, so the dashboard can stay
    bound to an org's oldest project while ingest uses a key for a different project in the
    same org — traffic queries then return empty series.
    """
    raw_token = _raw_dashboard_session_token_from_request(request, settings)
    if not raw_token:
        raise _unauthorized("Dashboard session is required")
    now = _now()
    session_row = await session.scalar(
        select(DashboardSession).where(
            DashboardSession.token_hash == _hash_token(raw_token),
            DashboardSession.revoked_at.is_(None),
            DashboardSession.expires_at >= now,
        )
    )
    if session_row is None or session_row.user_id != user_id:
        raise _unauthorized("Invalid dashboard session")
    project = await session.scalar(select(Project).where(Project.id == next_project_id))
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project is not linked to an organization",
        )
    membership = await session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == project.organization_id,
            OrganizationMembership.user_id == user_id,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this project's organization",
        )
    session_row.project_id = next_project_id
    session_row.organization_id = project.organization_id
    await session.commit()
    refreshed = await get_dashboard_auth_session(
        session=session, settings=settings, request=request
    )
    if refreshed is None:
        raise _unauthorized("Session could not be refreshed")
    return refreshed
