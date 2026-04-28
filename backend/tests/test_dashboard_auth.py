from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from autopulse_backend.app import create_app
from autopulse_backend.auth import generate_api_key
from autopulse_backend.models import ApiKey, Project


def _seed_project_and_key(database_url: str) -> str:
    async def run() -> str:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                project = Project(id=uuid4(), name="Auth Test Project")
                key_value, key_id, key_salt, key_hash = generate_api_key()
                api_key = ApiKey(
                    project_id=project.id,
                    key_id=key_id,
                    key_salt=key_salt,
                    key_hash=key_hash,
                )
                session.add(project)
                session.add(api_key)
                await session.commit()
                return key_value
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _truncate_tables(database_url: str) -> None:
    async def run() -> None:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                await session.execute(
                    text(
                        "TRUNCATE TABLE dashboard_sessions, dashboard_magic_links, "
                        "governance_audit_events, organization_memberships, archived_events, "
                        "error_group_aggregates, metric_buckets, dashboard_users, events, "
                        "api_keys, projects, organizations "
                        "RESTART IDENTITY CASCADE"
                    )
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_dashboard_magic_link_session_flow(
    backend_test_database_url: str,
    monkeypatch,
    tmp_path,
) -> None:
    _truncate_tables(backend_test_database_url)
    _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.setenv("DASHBOARD_AUTH_MAGIC_LINK_DEV_EXPOSE_TOKEN", "1")
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("ALERT_EMAIL_FILE_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alerts@example.com")
    app = create_app()

    with TestClient(app) as client:
        pre_session = client.get("/dashboard/auth/session")
        assert pre_session.status_code == 200
        assert pre_session.json()["authenticated"] is False

        request_response = client.post(
            "/dashboard/auth/magic-link/request",
            json={"email": "owner@example.com"},
        )
        assert request_response.status_code == 200
        payload = request_response.json()
        token = payload.get("dev_magic_link_token")
        assert isinstance(token, str) and token
        outbox_files = list(tmp_path.glob("*.eml"))
        assert len(outbox_files) == 1
        outbox_content = outbox_files[0].read_text()
        assert token in outbox_content
        assert "dashboard_magic_link" in outbox_content

        verify_response = client.post(
            "/dashboard/auth/magic-link/verify",
            json={"token": token},
        )
        assert verify_response.status_code == 200
        assert verify_response.json()["authenticated"] is True
        assert verify_response.json()["email"] == "owner@example.com"

        session_response = client.get("/dashboard/auth/session")
        assert session_response.status_code == 200
        assert session_response.json()["authenticated"] is True

        from_time = datetime.now(tz=UTC) - timedelta(minutes=5)
        dashboard_response = client.get(
            "/dashboard/overview",
            params={
                "from_timestamp": from_time.isoformat(),
                "to_timestamp": (from_time + timedelta(minutes=1)).isoformat(),
            },
        )
        assert dashboard_response.status_code == 200

        logout_response = client.post("/dashboard/auth/logout")
        assert logout_response.status_code == 200
        assert logout_response.json()["authenticated"] is False

        post_logout_session = client.get("/dashboard/auth/session")
        assert post_logout_session.status_code == 200
        assert post_logout_session.json()["authenticated"] is False


def test_dashboard_magic_link_verify_accepts_quoted_printable_corrupted_token(
    backend_test_database_url: str,
    monkeypatch,
) -> None:
    _truncate_tables(backend_test_database_url)
    _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.setenv("DASHBOARD_AUTH_MAGIC_LINK_DEV_EXPOSE_TOKEN", "1")
    app = create_app()

    with TestClient(app) as client:
        request_response = client.post(
            "/dashboard/auth/magic-link/request",
            json={"email": "owner@example.com"},
        )
        assert request_response.status_code == 200
        token = request_response.json().get("dev_magic_link_token")
        assert isinstance(token, str) and token

        # Simulates copy-paste from raw quoted-printable email body:
        # `token=3D<token with soft-break '=' + inserted space>`
        split_at = max(1, len(token) // 2)
        corrupted = f"3D{token[:split_at]}= {token[split_at:]}"
        verify_response = client.post(
            "/dashboard/auth/magic-link/verify",
            json={"token": corrupted},
        )
        assert verify_response.status_code == 200
        assert verify_response.json()["authenticated"] is True


def test_dashboard_organization_governance_flow(
    backend_test_database_url: str,
    monkeypatch,
) -> None:
    _truncate_tables(backend_test_database_url)
    _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.setenv("DASHBOARD_AUTH_MAGIC_LINK_DEV_EXPOSE_TOKEN", "1")
    app = create_app()

    with TestClient(app) as client:
        token = client.post(
            "/dashboard/auth/magic-link/request",
            json={"email": "owner@example.com"},
        ).json()["dev_magic_link_token"]
        assert isinstance(token, str)
        verify_response = client.post("/dashboard/auth/magic-link/verify", json={"token": token})
        assert verify_response.status_code == 200

        orgs_response = client.get("/dashboard/organizations")
        assert orgs_response.status_code == 200
        organizations = orgs_response.json()["organizations"]
        assert organizations
        organization_id = organizations[0]["organization_id"]

        invite_response = client.post(
            f"/dashboard/organizations/{organization_id}/members/invite",
            json={"email": "member@example.com", "role": "member"},
        )
        assert invite_response.status_code == 200

        members_response = client.get(f"/dashboard/organizations/{organization_id}/members")
        assert members_response.status_code == 200
        members = members_response.json()["members"]
        invited = next(
            (member for member in members if member["email"] == "member@example.com"),
            None,
        )
        assert invited is not None

        promote_response = client.put(
            f"/dashboard/organizations/{organization_id}/members/{invited['user_id']}/role",
            json={"role": "owner"},
        )
        assert promote_response.status_code == 200
        assert promote_response.json()["role"] == "owner"


def test_dashboard_magic_link_bootstraps_default_project_when_empty(
    backend_test_database_url: str,
    monkeypatch,
) -> None:
    _truncate_tables(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.setenv("DASHBOARD_AUTH_MAGIC_LINK_DEV_EXPOSE_TOKEN", "1")
    app = create_app()

    with TestClient(app) as client:
        request_response = client.post(
            "/dashboard/auth/magic-link/request",
            json={"email": "owner@example.com"},
        )
        assert request_response.status_code == 200
        token = request_response.json().get("dev_magic_link_token")
        assert isinstance(token, str) and token
        verify_response = client.post(
            "/dashboard/auth/magic-link/verify",
            json={"token": token},
        )
        assert verify_response.status_code == 200
        payload = verify_response.json()
        assert payload["authenticated"] is True
        assert isinstance(payload.get("project_id"), str) and payload["project_id"]
        assert isinstance(payload.get("organization_id"), str) and payload["organization_id"]


def test_dashboard_bootstrap_creates_org_project_and_api_key(
    backend_test_database_url: str,
    monkeypatch,
) -> None:
    _truncate_tables(backend_test_database_url)
    _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.setenv("DASHBOARD_AUTH_MAGIC_LINK_DEV_EXPOSE_TOKEN", "1")
    app = create_app()

    with TestClient(app) as client:
        token = client.post(
            "/dashboard/auth/magic-link/request",
            json={"email": "owner@example.com"},
        ).json()["dev_magic_link_token"]
        client.post("/dashboard/auth/magic-link/verify", json={"token": token})
        bootstrap_response = client.post(
            "/dashboard/auth/bootstrap",
            json={
                "organization_name": "Acme Org",
                "project_name": "Acme API",
            },
        )
        assert bootstrap_response.status_code == 200
        payload = bootstrap_response.json()
        assert payload["organization_name"] == "Acme Org"
        assert payload["project_name"] == "Acme API"
        assert isinstance(payload["api_key"], str) and payload["api_key"].startswith("ap_live_")


def test_dashboard_api_key_fallback_is_opt_in(
    backend_test_database_url: str,
    monkeypatch,
) -> None:
    _truncate_tables(backend_test_database_url)
    key = _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.delenv("DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK", raising=False)
    app = create_app()

    with TestClient(app) as client:
        denied_response = client.get(
            "/dashboard/overview",
            headers={"Authorization": f"Bearer {key}"},
        )
        assert denied_response.status_code == 401

    monkeypatch.setenv("DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK", "1")
    app = create_app()
    with TestClient(app) as client:
        allowed_response = client.get(
            "/dashboard/overview",
            headers={"Authorization": f"Bearer {key}"},
        )
        assert allowed_response.status_code == 200
