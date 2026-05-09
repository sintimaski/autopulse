from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from http.cookies import CookieError, SimpleCookie

from fastapi import HTTPException, Response, status
from starlette.requests import HTTPConnection

from lumonox_backend.core.config import Settings


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
    return settings.dashboard_auth_session_cookie_name or "lumonox_dashboard_session"


def _raw_dashboard_session_token_from_request(
    request: HTTPConnection,
    settings: Settings,
) -> str | None:
    """Resolve the dashboard session cookie value."""
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
