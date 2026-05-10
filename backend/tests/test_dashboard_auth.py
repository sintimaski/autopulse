from __future__ import annotations

import asyncio
import email
import re
from datetime import UTC, datetime, timedelta
from email import policy
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from lumonox_backend.app import create_app
from lumonox_backend.auth import generate_api_key
from lumonox_backend.dashboard.routes import auth_routes as auth_routes_module
from lumonox_backend.models import ApiKey, Event, Project


def _seed_singleton_bootstrap_project(database_url: str) -> str:
    """Mimic local dev bootstrap: one project row, no org (ingest key optional)."""

    async def run() -> str:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                project = Project(name="Lumonox Embedded Project")
                session.add(project)
                await session.commit()
                await session.refresh(project)
                return str(project.id)
        finally:
            await engine.dispose()

    return asyncio.run(run())


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


def _insert_one_request_event(database_url: str, *, project_id: UUID) -> None:
    async def run() -> None:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                now = datetime.now(tz=UTC)
                session.add(
                    Event(
                        project_id=project_id,
                        timestamp=now,
                        received_at=now,
                        sdk_version="0.1.0",
                        type="request",
                        service_name="api",
                        environment="test",
                        method="GET",
                        path="/",
                        status_code=200,
                        latency_ms=1.0,
                        payload={"type": "request"},
                        request_id="req-onboarding-complete",
                    )
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(run())


def _truncate_tables(database_url: str) -> None:
    async def run() -> None:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        tables = (
            "dashboard_sessions",
            "dashboard_magic_links",
            "governance_audit_events",
            "organization_memberships",
            "archived_events",
            "error_group_aggregates",
            "metric_buckets",
            "events",
            "api_keys",
            "dashboard_users",
            "projects",
            "organizations",
        )
        try:
            async with session_maker() as session:
                if "sqlite" in database_url:
                    res = await session.execute(
                        text("SELECT name FROM sqlite_master WHERE type='table'")
                    )
                    existing = {str(row[0]) for row in res.fetchall()}
                    await session.execute(text("PRAGMA foreign_keys=OFF"))
                    for table in tables:
                        if table in existing:
                            await session.execute(text(f"DELETE FROM {table}"))
                    await session.execute(text("PRAGMA foreign_keys=ON"))
                else:
                    await session.execute(
                        text("TRUNCATE TABLE " + ", ".join(tables) + " RESTART IDENTITY CASCADE")
                    )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(run())


def _list_governance_audit_events(database_url: str) -> list[dict[str, object]]:
    async def run() -> list[dict[str, object]]:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                result = await session.execute(
                    text(
                        "SELECT action, target_type, target_id, detail "
                        "FROM governance_audit_events ORDER BY id"
                    )
                )
                return [dict(row) for row in result.mappings().all()]
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _extract_magic_link_token_from_outbox(tmp_path) -> str:
    """Decode MIME so quoted-printable outbox tokens are not truncated at ``=`` or soft breaks."""
    outbox_files = list(tmp_path.glob("*.eml"))
    assert outbox_files
    # Filenames are random UUIDs; pick newest by mtime so this matches the latest send.
    latest = max(outbox_files, key=lambda p: p.stat().st_mtime)
    msg = email.message_from_bytes(latest.read_bytes(), policy=policy.default)
    plaintext = msg.get_body(preferencelist=("plain",))
    body = plaintext.get_content() if plaintext is not None else ""
    match = re.search(r"token=([A-Za-z0-9_-]+)", body)
    assert match is not None
    return match.group(1)


def _request_magic_link_token(client: TestClient, *, email: str, tmp_path) -> str:
    request_response = client.post(
        "/dashboard/auth/magic-link/request",
        json={"email": email},
    )
    assert request_response.status_code == 200
    return _extract_magic_link_token_from_outbox(tmp_path)


def test_dashboard_magic_link_request_exposes_dev_token_when_enabled(
    backend_test_database_url: str,
    monkeypatch,
    tmp_path,
) -> None:
    _truncate_tables(backend_test_database_url)
    _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.setenv("DASHBOARD_AUTH_MAGIC_LINK_DEV_EXPOSE_TOKEN", "1")
    monkeypatch.setenv(
        "DASHBOARD_AUTH_MAGIC_LINK_BASE_URL", "http://localhost:8000/lumonox/ui/auth/magic-link"
    )
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("ALERT_EMAIL_FILE_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alerts@example.com")
    app = create_app()

    with TestClient(app) as client:
        response = client.post(
            "/dashboard/auth/magic-link/request",
            json={"email": "owner@example.com"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["accepted"] is True
        assert isinstance(payload.get("dev_token"), str) and payload["dev_token"]
        assert isinstance(payload.get("dev_magic_link_url"), str)
        assert payload["dev_token"] in payload["dev_magic_link_url"]


def test_dashboard_magic_link_session_flow(
    backend_test_database_url: str,
    monkeypatch,
    tmp_path,
) -> None:
    _truncate_tables(backend_test_database_url)
    _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("ALERT_EMAIL_FILE_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alerts@example.com")
    app = create_app()

    with TestClient(app) as client:
        pre_session = client.get("/dashboard/auth/session")
        assert pre_session.status_code == 200
        assert pre_session.json()["authenticated"] is False

        token = _request_magic_link_token(client, email="owner@example.com", tmp_path=tmp_path)
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


def test_dashboard_magic_link_verify_aligns_singleton_duckdb_project_ids(
    backend_test_database_url: str,
    monkeypatch,
    tmp_path,
) -> None:
    _truncate_tables(backend_test_database_url)
    _seed_singleton_bootstrap_project(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("ALERT_EMAIL_FILE_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alerts@example.com")

    stale_project_id = "06d85246-d7aa-4391-91ac-03b7da5b7b58"
    reassign_calls: list[tuple[str, UUID]] = []

    class _FakeStore:
        def list_project_ids(self) -> list[str]:
            return [stale_project_id]

        def reassign_project_id(
            self, *, from_project_id: str, to_project_id: UUID
        ) -> tuple[int, int]:
            reassign_calls.append((from_project_id, to_project_id))
            return (12, 4)

    async def _run_sync_passthrough(fn, /, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(auth_routes_module, "event_store_enabled", lambda _settings: True)
    monkeypatch.setattr(auth_routes_module, "try_get_duckdb_event_store", lambda: _FakeStore())
    monkeypatch.setattr(auth_routes_module, "run_duckdb_read_sync", _run_sync_passthrough)
    monkeypatch.setattr(auth_routes_module, "run_duckdb_write_sync", _run_sync_passthrough)

    app = create_app()
    with TestClient(app) as client:
        token = _request_magic_link_token(client, email="owner@example.com", tmp_path=tmp_path)
        verify_response = client.post(
            "/dashboard/auth/magic-link/verify",
            json={"token": token},
        )
        assert verify_response.status_code == 200
        project_id = UUID(verify_response.json()["project_id"])

    assert reassign_calls == [(stale_project_id, project_id)]


def test_dashboard_magic_link_verify_accepts_quoted_printable_corrupted_token(
    backend_test_database_url: str,
    monkeypatch,
    tmp_path,
) -> None:
    _truncate_tables(backend_test_database_url)
    _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("ALERT_EMAIL_FILE_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alerts@example.com")
    monkeypatch.setenv("LUMONOX_DASHBOARD_REALTIME_ENABLED", "true")
    monkeypatch.setenv("LUMONOX_DASHBOARD_REALTIME_WS_ENABLED", "true")
    app = create_app()

    with TestClient(app) as client:
        token = _request_magic_link_token(client, email="owner@example.com", tmp_path=tmp_path)

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


def test_dashboard_member_cannot_invite_organization_members(
    backend_test_database_url: str,
    monkeypatch,
    tmp_path,
) -> None:
    _truncate_tables(backend_test_database_url)
    _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("ALERT_EMAIL_FILE_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alerts@example.com")
    app = create_app()

    with TestClient(app) as client:
        owner_token = _request_magic_link_token(
            client, email="owner@example.com", tmp_path=tmp_path
        )
        assert (
            client.post(
                "/dashboard/auth/magic-link/verify", json={"token": owner_token}
            ).status_code
            == 200
        )
        orgs = client.get("/dashboard/organizations").json()["organizations"]
        organization_id = orgs[0]["organization_id"]
        assert (
            client.post(
                f"/dashboard/organizations/{organization_id}/members/invite",
                json={"email": "member@example.com", "role": "member"},
            ).status_code
            == 200
        )
        assert client.post("/dashboard/auth/logout").status_code == 200

    member_app = create_app()
    with TestClient(member_app) as member_client:
        member_client.post(
            "/dashboard/auth/magic-link/request",
            json={"email": "member@example.com"},
        )
        member_token = _extract_magic_link_token_from_outbox(tmp_path)
        assert (
            member_client.post(
                "/dashboard/auth/magic-link/verify", json={"token": member_token}
            ).status_code
            == 200
        )
        deny = member_client.post(
            f"/dashboard/organizations/{organization_id}/members/invite",
            json={"email": "other@example.com", "role": "member"},
        )
        assert deny.status_code == 403


def test_dashboard_member_cannot_toggle_exclude_lumonox_via_theme_settings(
    backend_test_database_url: str,
    monkeypatch,
    tmp_path,
) -> None:
    _truncate_tables(backend_test_database_url)
    _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("ALERT_EMAIL_FILE_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alerts@example.com")
    app = create_app()

    with TestClient(app) as client:
        owner_token = _request_magic_link_token(
            client, email="owner@example.com", tmp_path=tmp_path
        )
        assert (
            client.post(
                "/dashboard/auth/magic-link/verify", json={"token": owner_token}
            ).status_code
            == 200
        )
        orgs = client.get("/dashboard/organizations").json()["organizations"]
        organization_id = orgs[0]["organization_id"]
        assert (
            client.post(
                f"/dashboard/organizations/{organization_id}/members/invite",
                json={"email": "member@example.com", "role": "member"},
            ).status_code
            == 200
        )
        assert client.post("/dashboard/auth/logout").status_code == 200

    member_app = create_app()
    with TestClient(member_app) as member_client:
        member_client.post(
            "/dashboard/auth/magic-link/request",
            json={"email": "member@example.com"},
        )
        member_token = _extract_magic_link_token_from_outbox(tmp_path)
        assert (
            member_client.post(
                "/dashboard/auth/magic-link/verify", json={"token": member_token}
            ).status_code
            == 200
        )

        read = member_client.get("/dashboard/theme-settings")
        assert read.status_code == 200
        initial = read.json()
        assert initial["exclude_lumonox_traffic"] is True

        deny_exclude = member_client.put(
            "/dashboard/theme-settings",
            json={
                "theme_preference": initial["theme_preference"],
                "exclude_lumonox_traffic": False,
            },
        )
        assert deny_exclude.status_code == 403

        allow_theme = member_client.put(
            "/dashboard/theme-settings",
            json={
                "theme_preference": "dark",
                "exclude_lumonox_traffic": initial["exclude_lumonox_traffic"],
            },
        )
        assert allow_theme.status_code == 200
        assert allow_theme.json()["theme_preference"] == "dark"


def test_dashboard_bootstrap_succeeds_for_invited_member(
    backend_test_database_url: str,
    monkeypatch,
    tmp_path,
) -> None:
    """Bootstrap includes API key list; members must receive 200 (not 403 from list keys)."""
    _truncate_tables(backend_test_database_url)
    _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("ALERT_EMAIL_FILE_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alerts@example.com")
    app = create_app()

    with TestClient(app) as client:
        owner_token = _request_magic_link_token(
            client, email="owner@example.com", tmp_path=tmp_path
        )
        assert (
            client.post(
                "/dashboard/auth/magic-link/verify", json={"token": owner_token}
            ).status_code
            == 200
        )
        orgs = client.get("/dashboard/organizations").json()["organizations"]
        organization_id = orgs[0]["organization_id"]
        invite = client.post(
            f"/dashboard/organizations/{organization_id}/members/invite",
            json={"email": "member@example.com", "role": "member"},
        )
        assert invite.status_code == 200
        assert client.post("/dashboard/auth/logout").status_code == 200

    member_app = create_app()
    with TestClient(member_app) as member_client:
        member_client.post(
            "/dashboard/auth/magic-link/request",
            json={"email": "member@example.com"},
        )
        member_token = _extract_magic_link_token_from_outbox(tmp_path)
        assert (
            member_client.post(
                "/dashboard/auth/magic-link/verify", json={"token": member_token}
            ).status_code
            == 200
        )
        bootstrap = member_client.get("/dashboard/bootstrap")
        assert bootstrap.status_code == 200
        payload = bootstrap.json()
        assert "api_keys" in payload
        assert isinstance(payload["api_keys"].get("items"), list)


def test_invited_member_magic_link_under_single_email_allowlist(
    backend_test_database_url: str,
    monkeypatch,
    tmp_path,
) -> None:
    """Invited org members must get magic links even when only the owner email is allowlisted."""
    _truncate_tables(backend_test_database_url)
    _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("ALERT_EMAIL_FILE_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alerts@example.com")
    app = create_app()

    with TestClient(app) as client:
        owner_token = _request_magic_link_token(
            client, email="owner@example.com", tmp_path=tmp_path
        )
        assert (
            client.post(
                "/dashboard/auth/magic-link/verify", json={"token": owner_token}
            ).status_code
            == 200
        )
        orgs = client.get("/dashboard/organizations").json()["organizations"]
        organization_id = orgs[0]["organization_id"]
        eml_before_invite = len(list(tmp_path.glob("*.eml")))
        invite = client.post(
            f"/dashboard/organizations/{organization_id}/members/invite",
            json={"email": "member@example.com", "role": "member"},
        )
        assert invite.status_code == 200
        assert len(list(tmp_path.glob("*.eml"))) > eml_before_invite

        request_response = client.post(
            "/dashboard/auth/magic-link/request",
            json={"email": "member@example.com"},
        )
        assert request_response.status_code == 200
        member_token = _extract_magic_link_token_from_outbox(tmp_path)
        verify_member = client.post(
            "/dashboard/auth/magic-link/verify",
            json={"token": member_token},
        )
        assert verify_member.status_code == 200
        assert verify_member.json()["authenticated"] is True


def test_dashboard_organization_governance_flow(
    backend_test_database_url: str,
    monkeypatch,
    tmp_path,
) -> None:
    _truncate_tables(backend_test_database_url)
    _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("ALERT_EMAIL_FILE_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alerts@example.com")
    app = create_app()

    with TestClient(app) as client:
        token = _request_magic_link_token(client, email="owner@example.com", tmp_path=tmp_path)
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


def test_dashboard_magic_link_adopts_singleton_bootstrap_project(
    backend_test_database_url: str,
    monkeypatch,
    tmp_path,
) -> None:
    _truncate_tables(backend_test_database_url)
    embedded_project_id = _seed_singleton_bootstrap_project(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("ALERT_EMAIL_FILE_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alerts@example.com")
    app = create_app()

    with TestClient(app) as client:
        token = _request_magic_link_token(client, email="owner@example.com", tmp_path=tmp_path)
        verify_response = client.post(
            "/dashboard/auth/magic-link/verify",
            json={"token": token},
        )
        assert verify_response.status_code == 200
        payload = verify_response.json()
        assert payload["authenticated"] is True
        assert payload["project_id"] == embedded_project_id


def test_dashboard_magic_link_bootstraps_default_project_when_empty(
    backend_test_database_url: str,
    monkeypatch,
    tmp_path,
) -> None:
    _truncate_tables(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("ALERT_EMAIL_FILE_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alerts@example.com")
    app = create_app()

    with TestClient(app) as client:
        token = _request_magic_link_token(client, email="owner@example.com", tmp_path=tmp_path)
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
    tmp_path,
) -> None:
    _truncate_tables(backend_test_database_url)
    _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("ALERT_EMAIL_FILE_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alerts@example.com")
    app = create_app()

    with TestClient(app) as client:
        token = _request_magic_link_token(client, email="owner@example.com", tmp_path=tmp_path)
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


def test_dashboard_api_key_lifecycle_owner_flow(
    backend_test_database_url: str,
    monkeypatch,
    tmp_path,
) -> None:
    _truncate_tables(backend_test_database_url)
    _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("ALERT_EMAIL_FILE_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alerts@example.com")
    app = create_app()

    with TestClient(app) as client:
        token = _request_magic_link_token(client, email="owner@example.com", tmp_path=tmp_path)
        verify_response = client.post("/dashboard/auth/magic-link/verify", json={"token": token})
        assert verify_response.status_code == 200

        issue_response = client.post("/dashboard/auth/api-keys/issue")
        assert issue_response.status_code == 200
        issued_key_id = issue_response.json()["key_id"]
        assert issue_response.json()["api_key"].startswith("ap_live_")

        list_response = client.get("/dashboard/auth/api-keys")
        assert list_response.status_code == 200
        assert any(item["key_id"] == issued_key_id for item in list_response.json()["items"])

        rotate_response = client.post(
            "/dashboard/auth/api-keys/rotate",
            json={"key_id": issued_key_id},
        )
        assert rotate_response.status_code == 200
        assert rotate_response.json()["revoked_key_id"] == issued_key_id
        replacement = rotate_response.json()["replacement_key_id"]

        revoke_response = client.post(
            "/dashboard/auth/api-keys/revoke",
            json={"key_id": replacement},
        )
        assert revoke_response.status_code == 200
        assert revoke_response.json()["key_id"] == replacement
        assert revoke_response.json()["revoked_at"] is not None


def test_dashboard_api_key_lifecycle_emits_governance_audit_events(
    backend_test_database_url: str,
    monkeypatch,
    tmp_path,
) -> None:
    _truncate_tables(backend_test_database_url)
    _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("ALERT_EMAIL_FILE_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alerts@example.com")
    app = create_app()

    with TestClient(app) as client:
        token = _request_magic_link_token(client, email="owner@example.com", tmp_path=tmp_path)
        verify_response = client.post("/dashboard/auth/magic-link/verify", json={"token": token})
        assert verify_response.status_code == 200

        issue = client.post("/dashboard/auth/api-keys/issue")
        assert issue.status_code == 200
        issued_key_id = issue.json()["key_id"]
        issued_raw_key = issue.json()["api_key"]

        rotate = client.post(
            "/dashboard/auth/api-keys/rotate",
            json={"key_id": issued_key_id},
        )
        assert rotate.status_code == 200
        replacement_key_id = rotate.json()["replacement_key_id"]
        replacement_raw_key = rotate.json()["replacement_api_key"]

        revoke = client.post(
            "/dashboard/auth/api-keys/revoke",
            json={"key_id": replacement_key_id},
        )
        assert revoke.status_code == 200

    events = _list_governance_audit_events(backend_test_database_url)
    assert [event["action"] for event in events] == [
        "api_key_issued",
        "api_key_rotated",
        "api_key_revoked",
    ]
    for event in events:
        assert event["target_type"] == "api_key"
        detail = event.get("detail") if isinstance(event.get("detail"), dict) else {}
        detail_text = str(detail)
        # Audit trail should reference key ids/project scope, not raw API key material.
        assert "ap_live_" not in detail_text
        assert issued_raw_key not in detail_text
        assert replacement_raw_key not in detail_text


def test_dashboard_issue_key_syncs_env_lumonox_file(
    backend_test_database_url: str,
    monkeypatch,
    tmp_path,
) -> None:
    _truncate_tables(backend_test_database_url)
    _seed_project_and_key(backend_test_database_url)
    outbox = tmp_path / "outbox"
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("ALERT_EMAIL_FILE_OUTBOX_DIR", str(outbox))
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alerts@example.com")
    env_lumonox_path = tmp_path / ".env.lumonox"
    monkeypatch.setenv("LUMONOX_ENV_FILE", str(env_lumonox_path))
    app = create_app()

    with TestClient(app) as client:
        token = _request_magic_link_token(client, email="owner@example.com", tmp_path=outbox)
        verify_response = client.post("/dashboard/auth/magic-link/verify", json={"token": token})
        assert verify_response.status_code == 200

        issue_response = client.post("/dashboard/auth/api-keys/issue")
        assert issue_response.status_code == 200
        issued = issue_response.json()["api_key"]

    content = env_lumonox_path.read_text(encoding="utf-8")
    assert f"LUMONOX_API_KEY={issued}" in content
    assert f"NEXT_PUBLIC_LUMONOX_API_KEY={issued}" in content


def test_dashboard_member_cannot_manage_api_keys(
    backend_test_database_url: str,
    monkeypatch,
    tmp_path,
) -> None:
    _truncate_tables(backend_test_database_url)
    _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("ALERT_EMAIL_FILE_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alerts@example.com")
    app = create_app()

    with TestClient(app) as client:
        owner_token = _request_magic_link_token(
            client, email="owner@example.com", tmp_path=tmp_path
        )
        verify_owner = client.post("/dashboard/auth/magic-link/verify", json={"token": owner_token})
        assert verify_owner.status_code == 200
        orgs = client.get("/dashboard/organizations").json()["organizations"]
        assert orgs
        organization_id = orgs[0]["organization_id"]
        invite = client.post(
            f"/dashboard/organizations/{organization_id}/members/invite",
            json={"email": "member@example.com", "role": "member"},
        )
        assert invite.status_code == 200
        assert client.post("/dashboard/auth/logout").status_code == 200

    monkeypatch.delenv("DASHBOARD_AUTH_ALLOWED_EMAIL", raising=False)
    app = create_app()
    with TestClient(app) as member_client:
        member_token = _request_magic_link_token(
            member_client, email="member@example.com", tmp_path=tmp_path
        )
        member_client.post("/dashboard/auth/magic-link/verify", json={"token": member_token})
        member_issue = member_client.post("/dashboard/auth/api-keys/issue")
        assert member_issue.status_code == 403


def test_dashboard_magic_link_does_not_bind_new_user_to_existing_project(
    backend_test_database_url: str,
    monkeypatch,
    tmp_path,
) -> None:
    """New users must not inherit ownership of an unrelated seeded tenant.

    Before hardening, magic-link verification assigned every new user to the
    earliest-created project via ``_resolve_default_project_id`` and silently
    granted owner membership on its organization, leaking ownership across
    tenants. After the fix, the new user must land on a fresh org/project they
    actually own.
    """
    _truncate_tables(backend_test_database_url)
    _seed_project_and_key(backend_test_database_url)

    async def _seeded_project_id() -> str:
        engine = create_async_engine(backend_test_database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                result = await session.execute(text("SELECT id FROM projects LIMIT 1"))
                row = result.first()
                assert row is not None
                return str(row[0])
        finally:
            await engine.dispose()

    seeded_project_id = asyncio.run(_seeded_project_id())
    monkeypatch.delenv("DASHBOARD_AUTH_ALLOWED_EMAIL", raising=False)
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("ALERT_EMAIL_FILE_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alerts@example.com")
    app = create_app()

    with TestClient(app) as client:
        token = _request_magic_link_token(client, email="new-user@example.com", tmp_path=tmp_path)
        verify_response = client.post("/dashboard/auth/magic-link/verify", json={"token": token})
        assert verify_response.status_code == 200
        payload = verify_response.json()
        assert payload["authenticated"] is True
        assert payload["project_id"] != seeded_project_id

        orgs_response = client.get("/dashboard/organizations")
        assert orgs_response.status_code == 200
        organizations = orgs_response.json()["organizations"]
        assert len(organizations) == 1
        assert organizations[0]["role"] == "owner"


def test_dashboard_session_cookie_expired_is_unauthenticated(
    backend_test_database_url: str,
    monkeypatch,
    tmp_path,
) -> None:
    _truncate_tables(backend_test_database_url)
    _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("ALERT_EMAIL_FILE_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alerts@example.com")
    app = create_app()

    with TestClient(app) as client:
        token = _request_magic_link_token(client, email="owner@example.com", tmp_path=tmp_path)
        verify_response = client.post("/dashboard/auth/magic-link/verify", json={"token": token})
        assert verify_response.status_code == 200

        async def _expire_sessions() -> None:
            engine = create_async_engine(backend_test_database_url, pool_pre_ping=True)
            session_maker = async_sessionmaker(
                bind=engine, expire_on_commit=False, class_=AsyncSession
            )
            try:
                async with session_maker() as session:
                    await session.execute(
                        text("UPDATE dashboard_sessions SET expires_at = :past"),
                        {"past": datetime.now(tz=UTC) - timedelta(minutes=1)},
                    )
                    await session.commit()
            finally:
                await engine.dispose()

        asyncio.run(_expire_sessions())

        session_response = client.get("/dashboard/auth/session")
        assert session_response.status_code == 200
        assert session_response.json()["authenticated"] is False

        denied_response = client.get(
            "/dashboard/overview",
            params={
                "from_timestamp": (datetime.now(tz=UTC) - timedelta(minutes=5)).isoformat(),
                "to_timestamp": datetime.now(tz=UTC).isoformat(),
            },
        )
        assert denied_response.status_code == 401


def test_dashboard_session_without_membership_is_rejected(
    backend_test_database_url: str,
    monkeypatch,
    tmp_path,
) -> None:
    """Sessions pointing at a tenant the user does not belong to must be rejected."""
    _truncate_tables(backend_test_database_url)
    _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("ALERT_EMAIL_FILE_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alerts@example.com")
    app = create_app()

    with TestClient(app) as client:
        token = _request_magic_link_token(client, email="owner@example.com", tmp_path=tmp_path)
        verify_response = client.post("/dashboard/auth/magic-link/verify", json={"token": token})
        assert verify_response.status_code == 200

        async def _drop_membership() -> None:
            engine = create_async_engine(backend_test_database_url, pool_pre_ping=True)
            session_maker = async_sessionmaker(
                bind=engine, expire_on_commit=False, class_=AsyncSession
            )
            try:
                async with session_maker() as session:
                    await session.execute(text("DELETE FROM organization_memberships"))
                    await session.commit()
            finally:
                await engine.dispose()

        asyncio.run(_drop_membership())

        session_response = client.get("/dashboard/auth/session")
        assert session_response.status_code == 200
        assert session_response.json()["authenticated"] is False

        denied_response = client.get(
            "/dashboard/overview",
            params={
                "from_timestamp": (datetime.now(tz=UTC) - timedelta(minutes=5)).isoformat(),
                "to_timestamp": datetime.now(tz=UTC).isoformat(),
            },
        )
        assert denied_response.status_code == 401


def test_dashboard_onboarding_status_and_alert_capabilities(
    backend_test_database_url: str,
    monkeypatch,
    tmp_path,
) -> None:
    _truncate_tables(backend_test_database_url)
    _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("ALERT_EMAIL_FILE_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alerts@example.com")
    app = create_app()

    with TestClient(app) as client:
        unauth = client.get("/dashboard/auth/onboarding-status")
        assert unauth.status_code == 401

        token = _request_magic_link_token(client, email="owner@example.com", tmp_path=tmp_path)
        verify_response = client.post("/dashboard/auth/magic-link/verify", json={"token": token})
        assert verify_response.status_code == 200

        onboarding = client.get("/dashboard/auth/onboarding-status")
        assert onboarding.status_code == 200
        payload = onboarding.json()
        assert isinstance(payload.get("next_recommended_action"), str)
        assert payload["session_authenticated"] is True
        assert payload["project_ready"] is True
        assert payload["ingest_key_ready"] is True
        assert payload["onboarding_completed"] is False
        assert payload["current_step"] in {
            "send_first_event",
            "open_diagnosis",
            "completed",
        }

        capabilities = client.get("/dashboard/alert-capabilities")
        assert capabilities.status_code == 200
        channels = {item["channel"]: item for item in capabilities.json()["channels"]}
        assert channels["email"]["status"] in {"active", "unavailable"}
        assert channels["slack"]["status"] == "planned"


def test_dashboard_onboarding_complete_requires_event_then_persists(
    backend_test_database_url: str,
    monkeypatch,
    tmp_path,
) -> None:
    _truncate_tables(backend_test_database_url)
    _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("ALERT_EMAIL_FILE_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alerts@example.com")
    app = create_app()

    with TestClient(app) as client:
        token = _request_magic_link_token(client, email="owner@example.com", tmp_path=tmp_path)
        verify_response = client.post("/dashboard/auth/magic-link/verify", json={"token": token})
        assert verify_response.status_code == 200
        project_id = UUID(verify_response.json()["project_id"])

        denied = client.post("/dashboard/auth/onboarding-complete")
        assert denied.status_code == 400

        _insert_one_request_event(backend_test_database_url, project_id=project_id)
        ok = client.post("/dashboard/auth/onboarding-complete")
        assert ok.status_code == 200
        assert ok.json()["onboarding_completed"] is True

        status = client.get("/dashboard/auth/onboarding-status")
        assert status.status_code == 200
        assert status.json()["onboarding_completed"] is True


def test_dashboard_updates_websocket_subscribes_after_magic_link(
    backend_test_database_url: str,
    monkeypatch,
    tmp_path,
) -> None:
    """Authenticated dashboard WebSocket should receive ``subscribed`` after upgrade (HTTP 101)."""
    _truncate_tables(backend_test_database_url)
    _seed_project_and_key(backend_test_database_url)
    monkeypatch.setenv("DASHBOARD_AUTH_ALLOWED_EMAIL", "owner@example.com")
    monkeypatch.setenv("LUMONOX_DASHBOARD_REALTIME_ENABLED", "true")
    monkeypatch.setenv("LUMONOX_DASHBOARD_REALTIME_WS_ENABLED", "true")
    monkeypatch.setenv("DASHBOARD_ENFORCE_ORIGIN_FOR_MUTATIONS", "false")
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("ALERT_EMAIL_FILE_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alerts@example.com")
    app = create_app()

    with TestClient(app) as client:
        token = _request_magic_link_token(client, email="owner@example.com", tmp_path=tmp_path)
        verify_response = client.post("/dashboard/auth/magic-link/verify", json={"token": token})
        assert verify_response.status_code == 200
        expected_project_id = verify_response.json()["project_id"]

        with client.websocket_connect("/dashboard/updates") as ws:
            first = ws.receive_json()
            assert first["type"] == "subscribed"
            assert first["project_id"] == expected_project_id
            second = ws.receive_json()
            assert second["type"] == "dashboard.snapshot"
            assert second["project_id"] == expected_project_id
            assert isinstance(second["snapshot_version"], int)


def test_dashboard_active_project_rebinds_session_to_sibling_project(
    backend_test_database_url: str,
    monkeypatch,
    tmp_path,
) -> None:
    """Session defaults to the org's oldest project; active-project switches scope for queries."""
    _truncate_tables(backend_test_database_url)
    monkeypatch.delenv("DASHBOARD_AUTH_ALLOWED_EMAIL", raising=False)
    monkeypatch.setenv("ALERT_EMAIL_PROVIDER", "file")
    monkeypatch.setenv("ALERT_EMAIL_FILE_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alerts@example.com")
    app = create_app()

    with TestClient(app) as client:
        token = _request_magic_link_token(
            client, email="active-proj@example.com", tmp_path=tmp_path
        )
        verify_response = client.post("/dashboard/auth/magic-link/verify", json={"token": token})
        assert verify_response.status_code == 200
        first_project_id = verify_response.json()["project_id"]
        organization_id = verify_response.json()["organization_id"]
        assert organization_id

        second_project_id = str(uuid4())

        async def _insert_second_project() -> None:
            engine = create_async_engine(backend_test_database_url, pool_pre_ping=True)
            session_maker = async_sessionmaker(
                bind=engine, expire_on_commit=False, class_=AsyncSession
            )
            try:
                async with session_maker() as session:
                    session.add(
                        Project(
                            id=UUID(second_project_id),
                            name="Sibling project",
                            organization_id=UUID(organization_id),
                        )
                    )
                    await session.commit()
            finally:
                await engine.dispose()

        asyncio.run(_insert_second_project())

        switch = client.post(
            "/dashboard/auth/active-project",
            json={"project_id": second_project_id},
        )
        assert switch.status_code == 200, switch.text
        assert switch.json()["project_id"] == second_project_id

        session_payload = client.get("/dashboard/auth/session").json()
        assert session_payload["authenticated"] is True
        assert session_payload["project_id"] == second_project_id
        assert session_payload["project_id"] != first_project_id

        missing = client.post("/dashboard/auth/active-project", json={"project_id": str(uuid4())})
        assert missing.status_code == 404
