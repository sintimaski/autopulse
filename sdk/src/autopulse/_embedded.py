from __future__ import annotations

import os
import shlex
import subprocess  # nosec B404
from contextlib import suppress
from pathlib import Path
from typing import Any

import httpx
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.responses import RedirectResponse
from starlette.staticfiles import StaticFiles

DEFAULT_EMBEDDED_API_KEY = "ap_live_embeddedlocal_localdevsecret"
DEFAULT_EMBEDDED_DATABASE_URL = "sqlite+aiosqlite:///./autopulse_embedded.db"
DEFAULT_MOUNT_PREFIX = "/autopulse"
DEFAULT_PROJECT_NAME = "AutoPulse Embedded Project"


def _normalize_prefix(raw_prefix: str) -> str:
    prefix = raw_prefix.strip() or DEFAULT_MOUNT_PREFIX
    if not prefix.startswith("/"):
        prefix = f"/{prefix}"
    if prefix != "/":
        prefix = prefix.rstrip("/")
    return prefix


def _apply_backend_environment(*, database_url: str) -> None:
    os.environ["DATABASE_URL"] = database_url
    # Embedded mode must run retention housekeeping; otherwise local DB caps are never enforced.
    os.environ.setdefault("JOBS_ENABLE_SCHEDULER", "1")
    os.environ.setdefault("JOBS_RETENTION_INTERVAL_SECONDS", "300")


def _add_event_handler(app: Any, event: str, handler: Any) -> bool:
    add_event_handler = getattr(app, "add_event_handler", None)
    if callable(add_event_handler):
        add_event_handler(event, handler)
        return True
    router = getattr(app, "router", None)
    router_add_event_handler = getattr(router, "add_event_handler", None)
    if callable(router_add_event_handler):
        router_add_event_handler(event, handler)
        return True
    return False


async def _ensure_embedded_project_and_key(
    *, database_url: str, project_name: str, api_key: str
) -> None:
    from autopulse_backend.auth import build_api_key_record
    from autopulse_backend.database import get_engine
    from autopulse_backend.models import ApiKey, Base, Project, ProjectUiSettings

    key_record = build_api_key_record(api_key)
    if key_record is None:
        return
    key_id, key_salt, key_hash = key_record
    engine = get_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        existing_key = await session.scalar(
            select(ApiKey).where(ApiKey.key_id == key_id, ApiKey.revoked_at.is_(None))
        )
        if existing_key is not None:
            return
        project = await session.scalar(select(Project).where(Project.name == project_name))
        if project is None:
            project = Project(name=project_name)
            session.add(project)
            await session.flush()
        ui_settings = await session.scalar(
            select(ProjectUiSettings).where(ProjectUiSettings.project_id == project.id)
        )
        if ui_settings is None:
            # Keep embedded SQLite storage bounded by default.
            session.add(
                ProjectUiSettings(
                    project_id=project.id,
                    theme_preference="system",
                    retention_max_db_size_mb=100,
                )
            )
        session.add(
            ApiKey(
                project_id=project.id,
                key_id=key_id,
                key_salt=key_salt,
                key_hash=key_hash,
            )
        )
        await session.commit()


def _mount_embedded_ui(backend_app: Any, *, static_dir: str | None = None) -> None:
    if getattr(backend_app.state, "_autopulse_embedded_ui_mounted", False):
        return
    resolved_dir: Path
    if static_dir:
        resolved_dir = Path(static_dir)
    else:
        env_static_dir = os.getenv("AUTOPULSE_FRONTEND_STATIC_DIR")
        if env_static_dir:
            resolved_dir = Path(env_static_dir)
        else:
            workspace_export_dir = Path.cwd() / "frontend" / "out"
            if workspace_export_dir.exists():
                resolved_dir = workspace_export_dir
            else:
                resolved_dir = Path(__file__).resolve().parent / "ui"
    if not resolved_dir.exists():
        return
    backend_app.mount(
        "/ui",
        StaticFiles(directory=str(resolved_dir), html=True),
        name="autopulse-ui",
    )

    @backend_app.get("/", include_in_schema=False)
    async def _embedded_root_redirect() -> RedirectResponse:
        return RedirectResponse(url="/ui/")

    backend_app.state._autopulse_embedded_ui_mounted = True


def _configure_sidecar(
    app: Any, *, command: str | None, working_directory: str | None = None
) -> None:
    if not command or getattr(app.state, "_autopulse_sidecar_registered", False):
        return
    sidecar_cwd = Path(working_directory).resolve() if working_directory else Path.cwd()

    async def start_sidecar() -> None:
        if getattr(app.state, "_autopulse_sidecar_process", None) is not None:
            return
        process = subprocess.Popen(  # nosec B603
            shlex.split(command),
            cwd=sidecar_cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        app.state._autopulse_sidecar_process = process

    async def stop_sidecar() -> None:
        process = getattr(app.state, "_autopulse_sidecar_process", None)
        if process is None:
            return
        process.terminate()
        app.state._autopulse_sidecar_process = None

    _add_event_handler(app, "startup", start_sidecar)
    _add_event_handler(app, "shutdown", stop_sidecar)
    app.state._autopulse_sidecar_registered = True


def configure_embedded(app: Any, *, kwargs: dict[str, Any]) -> dict[str, Any]:
    mode = str(kwargs.get("mode", "embedded")).strip().lower()
    if mode != "embedded":
        return {}
    prefix = _normalize_prefix(str(kwargs.get("mount_prefix", DEFAULT_MOUNT_PREFIX)))
    database_url = str(kwargs.get("database_url") or DEFAULT_EMBEDDED_DATABASE_URL)
    project_name = str(kwargs.get("embedded_project_name", DEFAULT_PROJECT_NAME))
    api_key = str(
        kwargs.get("api_key") or os.getenv("AUTOPULSE_EMBEDDED_API_KEY") or DEFAULT_EMBEDDED_API_KEY
    )
    frontend_mode = str(kwargs.get("frontend_mode", "static")).strip().lower()
    probe_interval_ms = float(
        kwargs.get(
            "infrastructure_probe_interval_ms",
            os.getenv("AUTOPULSE_INFRA_PROBE_INTERVAL_MS", "100"),
        )
    )
    _apply_backend_environment(database_url=database_url)

    if not getattr(app.state, "_autopulse_embedded_configured", False):
        from autopulse_backend.app import mount_on_app

        backend_app = mount_on_app(app, prefix=prefix)

        async def ensure_project_key() -> None:
            from autopulse_backend.config import get_settings
            from autopulse_backend.jobs import run_retention_once

            await _ensure_embedded_project_and_key(
                database_url=database_url,
                project_name=project_name,
                api_key=api_key,
            )
            # Enforce limits at startup so oversized DBs are corrected immediately.
            with suppress(Exception):
                await run_retention_once(settings=get_settings())

        _add_event_handler(app, "startup", ensure_project_key)
        if frontend_mode == "static":
            _mount_embedded_ui(backend_app, static_dir=kwargs.get("frontend_static_dir"))
        if frontend_mode == "sidecar":
            _configure_sidecar(
                app,
                command=kwargs.get("frontend_sidecar_command"),
                working_directory=kwargs.get("frontend_sidecar_cwd"),
            )
        app.state._autopulse_embedded_configured = True

    ingest_url = kwargs.get("ingest_url") or f"http://autopulse.local{prefix}/ingest"
    provided_http_client = kwargs.get("http_client")
    return {
        "api_key": api_key,
        "ingest_url": ingest_url,
        "infrastructure_probe_interval_ms": probe_interval_ms,
        "http_client": provided_http_client
        or httpx.AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False)),
        "owns_http_client": provided_http_client is None,
    }
