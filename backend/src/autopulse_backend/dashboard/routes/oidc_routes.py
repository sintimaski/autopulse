"""OIDC / OAuth2 login (Auth0, WorkOS, etc.) — complements magic-link auth."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from typing import Annotated, Any, cast
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse, Response

from autopulse_backend.auth.dashboard import (
    _email_matches_allowed_domains,
    issue_dashboard_session_for_user,
)
from autopulse_backend.config import get_settings
from autopulse_backend.database import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/oidc", tags=["dashboard-oidc"])


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return _b64url(digest)


def _sign_oidc_cookie(secret: str, payload: dict[str, Any]) -> str:
    body = _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    sig = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def _verify_oidc_cookie(secret: str, raw: str, *, max_age_seconds: int = 900) -> dict[str, Any]:
    try:
        body_b64, sig = raw.split(".", 1)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OIDC state cookie"
        ) from exc
    expected = hmac.new(
        secret.encode("utf-8"),
        body_b64.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OIDC state signature"
        )
    padded = body_b64 + "=" * (-len(body_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")))
    iat = int(payload.get("iat", 0))
    if iat <= 0 or (time.time() - iat) > max_age_seconds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="OIDC state cookie expired"
        )
    return payload


async def _fetch_discovery(issuer: str) -> dict[str, Any]:
    issuer = issuer.rstrip("/")
    url = f"{issuer}/.well-known/openid-configuration"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url)
    if response.status_code >= 400:
        logger.error("oidc_discovery_failed", extra={"url": url, "status": response.status_code})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load OIDC discovery document",
        )
    payload = response.json()
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Invalid OIDC discovery document",
        )
    return cast(dict[str, Any], payload)


@router.get("/login")
async def oidc_login_start(request: Request) -> Response:
    settings = get_settings()
    if not settings.dashboard_oidc_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OIDC login is disabled")
    secret = settings.dashboard_oidc_state_secret or ""
    if not secret.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DASHBOARD_OIDC_STATE_SECRET is not configured",
        )
    issuer = (settings.dashboard_oidc_issuer_url or "").strip().rstrip("/")
    client_id = (settings.dashboard_oidc_client_id or "").strip()
    redirect_uri = (settings.dashboard_oidc_redirect_uri or "").strip()
    if not issuer or not client_id or not redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC issuer, client id, or redirect URI is not configured",
        )
    discovery = await _fetch_discovery(issuer)
    authorization_endpoint = discovery.get("authorization_endpoint")
    if not isinstance(authorization_endpoint, str) or not authorization_endpoint.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC discovery document missing authorization_endpoint",
        )
    verifier = secrets.token_urlsafe(48)
    state = secrets.token_urlsafe(32)
    cookie_payload = {
        "verifier": verifier,
        "state": state,
        "iat": int(time.time()),
    }
    signed = _sign_oidc_cookie(secret, cookie_payload)
    redirect = Response(status_code=status.HTTP_302_FOUND)
    redirect.set_cookie(
        key=settings.dashboard_oidc_cookie_name,
        value=signed,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        max_age=900,
        path="/",
    )
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": settings.dashboard_oidc_scopes,
        "state": state,
        "code_challenge": _pkce_challenge(verifier),
        "code_challenge_method": "S256",
    }
    redirect.headers["location"] = f"{authorization_endpoint}?{urlencode(params)}"
    return redirect


@router.get("/callback")
async def oidc_login_callback(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RedirectResponse:
    settings = get_settings()
    post_login = (settings.dashboard_oidc_post_login_redirect or "").strip()
    if not post_login:
        post_login = "http://localhost:3000/autopulse/ui/"
    if not settings.dashboard_oidc_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OIDC login is disabled")
    secret = settings.dashboard_oidc_state_secret or ""
    if not secret.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DASHBOARD_OIDC_STATE_SECRET is not configured",
        )
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Missing code or state query parameter"
        )
    raw_cookie = request.cookies.get(settings.dashboard_oidc_cookie_name or "")
    if not raw_cookie:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Missing OIDC state cookie"
        )
    payload = _verify_oidc_cookie(secret, raw_cookie)
    if payload.get("state") != state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OIDC state mismatch")
    verifier = str(payload.get("verifier") or "")
    if not verifier:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing PKCE verifier")

    issuer = (settings.dashboard_oidc_issuer_url or "").strip().rstrip("/")
    client_id = (settings.dashboard_oidc_client_id or "").strip()
    client_secret = settings.dashboard_oidc_client_secret or ""
    redirect_uri = (settings.dashboard_oidc_redirect_uri or "").strip()
    discovery = await _fetch_discovery(issuer)
    token_endpoint = discovery.get("token_endpoint")
    userinfo_endpoint = discovery.get("userinfo_endpoint")
    if not isinstance(token_endpoint, str) or not token_endpoint.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC discovery document missing token_endpoint",
        )
    token_body = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": verifier,
        "client_secret": client_secret,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        token_response = await client.post(
            token_endpoint,
            data=token_body,
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
    if token_response.status_code >= 400:
        logger.warning(
            "oidc_token_exchange_failed",
            extra={"status": token_response.status_code, "body": token_response.text[:500]},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OIDC token exchange failed",
        )
    token_payload = token_response.json()
    if not isinstance(token_payload, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OIDC token response was not a JSON object",
        )
    token_json: dict[str, Any] = cast(dict[str, Any], token_payload)
    access_token = token_json.get("access_token")
    id_token = token_json.get("id_token")
    email: str | None = None
    sub: str | None = None
    if isinstance(access_token, str) and isinstance(userinfo_endpoint, str) and userinfo_endpoint:
        async with httpx.AsyncClient(timeout=20.0) as client:
            userinfo_response = await client.get(
                userinfo_endpoint,
                headers={"authorization": f"Bearer {access_token}"},
            )
        if userinfo_response.status_code < 400:
            raw_claims = userinfo_response.json()
            if isinstance(raw_claims, dict):
                claims = cast(dict[str, Any], raw_claims)
                if isinstance(claims.get("email"), str):
                    email = claims["email"]
                if isinstance(claims.get("sub"), str):
                    sub = claims["sub"]
    if (email is None or sub is None) and isinstance(id_token, str) and id_token.count(".") == 2:
        try:
            jwt_payload_b64 = id_token.split(".", maxsplit=2)[1]
            padded = jwt_payload_b64 + "=" * (-len(jwt_payload_b64) % 4)
            jwt_payload = json.loads(
                base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
            )
            if email is None and isinstance(jwt_payload.get("email"), str):
                email = jwt_payload["email"]
            if sub is None and isinstance(jwt_payload.get("sub"), str):
                sub = jwt_payload["sub"]
        except (ValueError, json.JSONDecodeError, KeyError, UnicodeDecodeError):
            pass
    if not email or "@" not in email.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OIDC response did not include a usable email claim",
        )
    if not sub or not str(sub).strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OIDC response did not include a subject (sub) claim",
        )
    normalized_email = email.strip().lower()
    allow = (settings.dashboard_auth_allowed_email or "").strip().lower()
    domains = settings.dashboard_allowed_email_domains
    if allow and normalized_email != allow:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Email is not allowed for this deployment"
        )
    if domains and not _email_matches_allowed_domains(normalized_email, domains):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email domain is not allowed for this deployment",
        )

    parsed_issuer = urlparse(issuer)
    idp_provider = (parsed_issuer.netloc or parsed_issuer.path or issuer)[:64]
    redirect = RedirectResponse(url=post_login, status_code=status.HTTP_302_FOUND)
    await issue_dashboard_session_for_user(
        session=session,
        response=redirect,
        settings=settings,
        request=request,
        email=normalized_email,
        idp_provider=idp_provider,
        idp_subject=sub.strip()[:255],
    )
    redirect.delete_cookie(key=settings.dashboard_oidc_cookie_name, path="/")
    return redirect
