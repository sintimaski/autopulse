"""Dashboard membership roles: owner > admin > member > viewer."""

from __future__ import annotations

from typing import Annotated, Final, Literal, cast

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.auth.dashboard import DashboardAuthSession
from autopulse_backend.database import get_db_session

ROLE_RANK: Final[dict[str, int]] = {
    "viewer": 0,
    "member": 1,
    "admin": 2,
    "owner": 3,
}

KNOWN_ROLES: Final[frozenset[str]] = frozenset(ROLE_RANK)

MembershipRole = Literal["owner", "admin", "member", "viewer"]


def normalize_membership_role(role: str | None) -> MembershipRole | None:
    if role is None:
        return None
    if role in KNOWN_ROLES:
        return cast(MembershipRole, role)
    return "member"


def _rank(role: str | None) -> int:
    if not role:
        return 0
    return ROLE_RANK.get(role, 0)


def require_min_dashboard_role(auth_session: DashboardAuthSession, *, min_role: str) -> None:
    need = ROLE_RANK.get(min_role, 0)
    if _rank(auth_session.membership_role) < need:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{min_role} role or higher required",
        )


def require_owner(auth_session: DashboardAuthSession) -> None:
    require_min_dashboard_role(auth_session, min_role="owner")


def require_owner_or_admin(auth_session: DashboardAuthSession) -> None:
    require_min_dashboard_role(auth_session, min_role="admin")


def require_member_or_above(auth_session: DashboardAuthSession) -> None:
    require_min_dashboard_role(auth_session, min_role="member")


def require_dashboard_org_member(auth_session: DashboardAuthSession) -> None:
    """Require a recognized org role (viewer through owner) for read-only project metadata."""
    if normalize_membership_role(auth_session.membership_role) is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization membership required",
        )


async def ensure_dashboard_not_viewer(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    from autopulse_backend.auth.dashboard import get_dashboard_auth_session
    from autopulse_backend.core.config import get_settings

    settings = get_settings()
    auth_session = await get_dashboard_auth_session(
        session=session, settings=settings, request=request
    )
    if auth_session is None:
        return
    require_member_or_above(auth_session)


async def ensure_dashboard_admin_or_owner(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    from autopulse_backend.auth.dashboard import get_dashboard_auth_session
    from autopulse_backend.core.config import get_settings

    settings = get_settings()
    auth_session = await get_dashboard_auth_session(
        session=session, settings=settings, request=request
    )
    if auth_session is None:
        return
    require_min_dashboard_role(auth_session, min_role="admin")
