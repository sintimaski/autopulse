from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from test_dashboard_auth import _request_magic_link_token, _truncate_tables

from lumonox_backend.app import create_app
from lumonox_backend.auth import generate_api_key
from lumonox_backend.models import ApiKey, Project


def _seed_project_and_key(database_url: str) -> None:
    async def run() -> None:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with session_maker() as session:
                project = Project(id=uuid4(), name="Incident share seed project")
                key_value, key_id, key_salt, key_hash = generate_api_key()
                session.add(project)
                await session.flush()
                session.add(
                    ApiKey(
                        project_id=project.id,
                        key_id=key_id,
                        key_salt=key_salt,
                        key_hash=key_hash,
                    )
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_incident_share_create_redeem_organization_mode(
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
        bootstrap = client.post(
            "/dashboard/auth/bootstrap",
            json={"organization_name": "Share Org", "project_name": "Share Project"},
        )
        assert bootstrap.status_code == 200, bootstrap.text
        session_after = client.get("/dashboard/auth/session")
        assert session_after.status_code == 200, session_after.text
        project_id = session_after.json()["project_id"]

        scope_state = {"windowMinutes": 45, "isAbsoluteWindow": False}
        notebook_document = {
            "version": 1,
            "cells": [{"id": "snap-cell", "type": "markdown", "source": "from-share"}],
        }
        create = client.post(
            "/dashboard/incident-shares",
            json={
                "scope_state": scope_state,
                "notebook_document": notebook_document,
                "access_mode": "organization",
                "expires_in_days": 14,
            },
        )
        assert create.status_code == 200, create.text
        created = create.json()
        assert created.get("share_id")
        assert "expires_at" in created
        assert "token" not in created

        redeem = client.post(
            "/dashboard/incident-shares/redeem",
            json={"share_id": created["share_id"]},
        )
        assert redeem.status_code == 200, redeem.text
        body = redeem.json()
        assert body["project_id"] == project_id
        assert "window_minutes=45" in body["scoped_query"]
        assert body.get("notebook_document") is not None
        assert body["notebook_document"]["cells"][0]["source"] == "from-share"

        listed = client.get("/dashboard/incident-shares")
        assert listed.status_code == 200, listed.text
        rows = listed.json()
        assert isinstance(rows, list) and len(rows) == 1
        assert rows[0]["access_mode"] == "organization"
        assert rows[0]["id"] == created["share_id"]
        assert "updated_at" in rows[0]


def test_incident_share_redeem_wrong_active_project_returns_409(
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
        bootstrap = client.post(
            "/dashboard/auth/bootstrap",
            json={"organization_name": "Two Proj Org", "project_name": "Primary"},
        )
        assert bootstrap.status_code == 200, bootstrap.text
        session_after = client.get("/dashboard/auth/session")
        assert session_after.status_code == 200, session_after.text
        primary_project_id = session_after.json()["project_id"]
        organization_id = session_after.json()["organization_id"]
        assert organization_id

        create = client.post(
            "/dashboard/incident-shares",
            json={
                "scope_state": {},
                "access_mode": "organization",
                "expires_in_days": 7,
            },
        )
        assert create.status_code == 200, create.text
        share_id = create.json()["share_id"]
        sibling_id = str(uuid4())

        async def _insert_sibling() -> None:
            engine = create_async_engine(backend_test_database_url, pool_pre_ping=True)
            session_maker = async_sessionmaker(
                bind=engine, expire_on_commit=False, class_=AsyncSession
            )
            try:
                async with session_maker() as session:
                    session.add(
                        Project(
                            id=UUID(sibling_id),
                            name="Sibling",
                            organization_id=UUID(organization_id),
                        )
                    )
                    await session.commit()
            finally:
                await engine.dispose()

        asyncio.run(_insert_sibling())

        switch = client.post("/dashboard/auth/active-project", json={"project_id": sibling_id})
        assert switch.status_code == 200, switch.text

        conflict = client.post(
            "/dashboard/incident-shares/redeem",
            json={"share_id": share_id},
        )
        assert conflict.status_code == 409, conflict.text
        payload = conflict.json()
        assert payload.get("code") == "wrong_project"
        assert payload.get("project_id") == primary_project_id


def test_incident_share_get_patch_delete(
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
        bootstrap = client.post(
            "/dashboard/auth/bootstrap",
            json={"organization_name": "Crud Org", "project_name": "Crud Project"},
        )
        assert bootstrap.status_code == 200, bootstrap.text
        session_after = client.get("/dashboard/auth/session")
        assert session_after.status_code == 200, session_after.text
        project_id = session_after.json()["project_id"]

        scope_state = {"windowMinutes": 45, "isAbsoluteWindow": False}
        create = client.post(
            "/dashboard/incident-shares",
            json={
                "scope_state": scope_state,
                "title": "Alpha",
                "access_mode": "organization",
                "expires_in_days": 14,
            },
        )
        assert create.status_code == 200, create.text
        share_id = create.json()["share_id"]

        got = client.get(f"/dashboard/incident-shares/{share_id}")
        assert got.status_code == 200, got.text
        body = got.json()
        assert body["id"] == share_id
        assert body["project_id"] == project_id
        assert body["title"] == "Alpha"
        assert "window_minutes=45" in body["scoped_query"]

        patch = client.patch(
            f"/dashboard/incident-shares/{share_id}",
            json={"title": "Beta"},
        )
        assert patch.status_code == 200, patch.text
        assert patch.json()["title"] == "Beta"

        dele = client.delete(f"/dashboard/incident-shares/{share_id}")
        assert dele.status_code == 204, dele.text

        listed = client.get("/dashboard/incident-shares")
        assert listed.status_code == 200, listed.text
        assert listed.json() == []

        gone = client.get(f"/dashboard/incident-shares/{share_id}")
        assert gone.status_code == 404, gone.text
