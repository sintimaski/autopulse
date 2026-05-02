from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass
from hashlib import pbkdf2_hmac
from typing import Annotated, Final
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.auth.dashboard import get_dashboard_auth_session
from autopulse_backend.core.config import get_settings
from autopulse_backend.database import get_db_session
from autopulse_backend.models import ApiKey

_API_KEY_PREFIX: Final[str] = "ap_live"
_DERIVE_ITERATIONS: Final[int] = 120_000
_KEY_ID_BYTES: Final[int] = 6
_SECRET_BYTES: Final[int] = 24
_SALT_BYTES: Final[int] = 16


@dataclass(frozen=True, slots=True)
class ProjectContext:
    project_id: UUID
    membership_role: str | None = None


def _derive_secret_hash(secret: str, salt: bytes) -> bytes:
    return pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, _DERIVE_ITERATIONS)


def generate_api_key() -> tuple[str, str, bytes, bytes]:
    """Create a key string and hashed-at-rest values.

    Key format: ap_live_<key_id>_<secret>.
    We store only key_id + (salt, pbkdf2 hash(secret)).
    """
    key_id = secrets.token_hex(_KEY_ID_BYTES)
    secret = secrets.token_urlsafe(_SECRET_BYTES)
    salt = secrets.token_bytes(_SALT_BYTES)
    secret_hash = _derive_secret_hash(secret, salt)
    return (f"{_API_KEY_PREFIX}_{key_id}_{secret}", key_id, salt, secret_hash)


def parse_api_key(value: str) -> tuple[str, str] | None:
    parts = value.split("_", maxsplit=3)
    if len(parts) != 4:
        return None
    prefix_1, prefix_2, key_id, secret = parts
    if f"{prefix_1}_{prefix_2}" != _API_KEY_PREFIX:
        return None
    if not key_id or not secret:
        return None
    return key_id, secret


def verify_api_key_secret(secret: str, salt: bytes, expected_hash: bytes) -> bool:
    return hmac.compare_digest(_derive_secret_hash(secret, salt), expected_hash)


def build_api_key_record(api_key: str) -> tuple[str, bytes, bytes] | None:
    """Build storage fields for an existing raw API key."""
    parsed = parse_api_key(api_key)
    if parsed is None:
        return None
    key_id, secret = parsed
    salt = secrets.token_bytes(_SALT_BYTES)
    secret_hash = _derive_secret_hash(secret, salt)
    return key_id, salt, secret_hash


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
    )


async def authenticate_project(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    authorization: Annotated[str | None, Header()] = None,
) -> ProjectContext:
    if authorization is None:
        raise _unauthorized()
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized()
    return await authenticate_project_token(session=session, token=token)


async def authenticate_project_token(*, session: AsyncSession, token: str) -> ProjectContext:
    parsed = parse_api_key(token)
    if parsed is None:
        raise _unauthorized()
    key_id, secret = parsed
    api_key = await session.scalar(
        select(ApiKey).where(ApiKey.key_id == key_id, ApiKey.revoked_at.is_(None))
    )
    if api_key is None:
        raise _unauthorized()
    if not verify_api_key_secret(secret, api_key.key_salt, api_key.key_hash):
        raise _unauthorized()
    return ProjectContext(project_id=api_key.project_id)


async def authenticate_dashboard_project(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectContext:
    settings = get_settings()
    auth_session = await get_dashboard_auth_session(
        session=session, settings=settings, request=request
    )
    if auth_session is None:
        authorization = request.headers.get("authorization")
        if settings.dashboard_auth_allow_api_key_fallback and authorization:
            scheme, _, token = authorization.partition(" ")
            if scheme.lower() == "bearer" and token:
                ctx = await authenticate_project_token(session=session, token=token)
                return ProjectContext(project_id=ctx.project_id, membership_role="owner")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Dashboard session is required",
        )
    return ProjectContext(
        project_id=auth_session.project_id,
        membership_role=auth_session.membership_role,
    )
