from __future__ import annotations

import asyncio
import logging
import os
import shlex
import subprocess  # nosec B404
from contextlib import suppress
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import httpx
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.exceptions import HTTPException
from starlette.responses import RedirectResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

_LOG = logging.getLogger(__name__)

# Example key for local ``.env`` / docs only. Never used as an automatic runtime fallback
# (generated keys are used when ``.env.autopulse`` cannot be written).
DEFAULT_EMBEDDED_API_KEY = "ap_live_embeddedlocal_localdevsecret"
DEFAULT_EMBEDDED_DATABASE_URL = "sqlite+aiosqlite:///./autopulse.db"
DEFAULT_MOUNT_PREFIX = "/autopulse"
DEFAULT_PROJECT_NAME = "AutoPulse Embedded Project"

# Single hand-off file at repo cwd (gitignored): embedded bearer + Next public
# keys for one `source`.
DEFAULT_ENV_AUTOPULSE_PATH = Path(".env.autopulse")
# Legacy single-line key (still read if present).
LEGACY_EMBEDDED_KEY_FILE = Path(".autopulse") / "embedded-api-key"
_DOTENV_APPLY_KEYS = frozenset(
    {
        "AUTOPULSE_EMBEDDED_API_KEY",
        "NEXT_PUBLIC_AUTOPULSE_API_KEY",
        "NEXT_PUBLIC_AUTOPULSE_API_BASE_URL",
    }
)


def _embedded_startup_ingest_ping_enabled() -> bool:
    raw = os.environ.get("AUTOPULSE_EMBEDDED_STARTUP_INGEST")
    if raw is None:
        return True
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_autopulse_path() -> Path:
    raw = os.environ.get("AUTOPULSE_ENV_AUTOPULSE_FILE", "").strip()
    return Path(raw).expanduser() if raw else DEFAULT_ENV_AUTOPULSE_PATH


def _parse_dotenv_lines(content: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in content.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("export "):
            s = s[7:].strip()
        if "=" not in s:
            continue
        key, _, val = s.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            out[key] = val
    return out


def _apply_env_autopulse_file_defaults(path: Path) -> None:
    """Load optional ``.env.autopulse`` into the process.

    Uses ``setdefault`` only, so explicit runtime env still wins.
    """
    if not path.is_file():
        return
    try:
        parsed = _parse_dotenv_lines(path.read_text(encoding="utf-8"))
    except OSError:
        return
    for key in _DOTENV_APPLY_KEYS:
        val = parsed.get(key, "").strip()
        if val:
            os.environ.setdefault(key, val)


def _read_embedded_key_from_files(env_path: Path) -> str | None:
    from autopulse_backend.auth import build_api_key_record

    if env_path.is_file():
        try:
            parsed = _parse_dotenv_lines(env_path.read_text(encoding="utf-8"))
        except OSError:
            parsed = {}
        candidate = parsed.get("AUTOPULSE_EMBEDDED_API_KEY", "").strip()
        if candidate and build_api_key_record(candidate) is not None:
            return candidate

    legacy = LEGACY_EMBEDDED_KEY_FILE
    raw = os.environ.get("AUTOPULSE_EMBEDDED_API_KEY_FILE", "").strip()
    if raw:
        legacy = Path(raw).expanduser()
    if legacy.is_file():
        try:
            candidate = legacy.read_text(encoding="utf-8").splitlines()[0].strip()
        except OSError:
            candidate = ""
        if candidate and build_api_key_record(candidate) is not None:
            return candidate
    return None


def _write_generated_env_autopulse(*, path: Path, raw_key: str, mount_prefix: str) -> None:
    base = mount_prefix.strip() or DEFAULT_MOUNT_PREFIX
    content = (
        "# AutoPulse — generated on first embedded monitor() boot.\n"
        "# Source before static UI build: set -a && source .env.autopulse && set +a\n"
        "# (scripts/run_synthetic_stack.sh sources this file automatically when present.)\n"
        f"NEXT_PUBLIC_AUTOPULSE_API_BASE_URL={base}\n"
        f"AUTOPULSE_EMBEDDED_API_KEY={raw_key}\n"
        f"NEXT_PUBLIC_AUTOPULSE_API_KEY={raw_key}\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    with suppress(OSError):
        os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    _apply_env_autopulse_file_defaults(path)


def _resolve_embedded_api_key(*, kwargs_api_key: str | None, mount_prefix: str) -> str:
    """Resolve bearer material for embedded ingest + DB seeding.

    Precedence: explicit ``api_key`` kwarg → ``AUTOPULSE_EMBEDDED_API_KEY`` env →
    ``.env.autopulse`` (``AUTOPULSE_EMBEDDED_API_KEY``) or legacy single-line file →
    generate a new key and write ``.env.autopulse`` (also seeds matching
    ``NEXT_PUBLIC_*`` lines) → public default constant.
    """
    if kwargs_api_key is not None and str(kwargs_api_key).strip():
        return str(kwargs_api_key).strip()
    env_key = os.environ.get("AUTOPULSE_EMBEDDED_API_KEY", "").strip()
    if env_key:
        return env_key

    from autopulse_backend.auth import generate_api_key

    env_path = _env_autopulse_path()
    from_file = _read_embedded_key_from_files(env_path)
    if from_file is not None:
        return from_file

    raw_key, _key_id, _salt, _hash = generate_api_key()
    try:
        _write_generated_env_autopulse(path=env_path, raw_key=raw_key, mount_prefix=mount_prefix)
        _LOG.info(
            "AutoPulse embedded wrote %s — source it before `npm run build` for static UI "
            "(NEXT_PUBLIC_* + AUTOPULSE_EMBEDDED_API_KEY).",
            env_path,
        )
        return raw_key
    except OSError as exc:
        _LOG.warning(
            "AutoPulse embedded could not write %s (%s); using an in-memory generated API key "
            "for this process only. Set AUTOPULSE_EMBEDDED_API_KEY (or fix permissions on %s) "
            "so the key persists across restarts and matches your static UI build.",
            env_path,
            exc,
            env_path,
        )
        return raw_key


def _embedded_max_db_size_mb_for_settings() -> int | None:
    """SQLite file cap in MB from env, or None when disabled (env <= 0)."""
    raw = os.environ.get("AUTOPULSE_EMBEDDED_MAX_DB_SIZE_MB", "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return None if value <= 0 else value


def _normalize_prefix(raw_prefix: str) -> str:
    prefix = raw_prefix.strip() or DEFAULT_MOUNT_PREFIX
    if not prefix.startswith("/"):
        prefix = f"/{prefix}"
    if prefix != "/":
        prefix = prefix.rstrip("/")
    return prefix


def _cwd_host_sqlite_file_database_url(database_url: str) -> str:
    """Resolve relative SQLite file URLs against the embedded host process cwd.

    ``normalize_database_url`` in the backend anchors ``./`` paths to the backend package
    tree for standalone servers. Embedded hosts (starter apps) must keep ``./autopulse.db``
    next to the user's project so ``_ensure_embedded_project_and_key`` and
    ``get_db_session``/ingest share the same SQLite file.
    """
    raw = database_url.strip()
    parsed = urlparse(raw)
    if parsed.scheme not in {"sqlite", "sqlite+aiosqlite"}:
        return database_url
    path = unquote(parsed.path or "")
    if raw.endswith(":memory:") or path in {":memory:", ""}:
        return database_url
    if path.startswith("/./") or path.startswith("/../"):
        rel = Path(path[1:])
        resolved = (Path.cwd() / rel).resolve()
        return f"{parsed.scheme}:///{resolved.as_posix()}"
    return database_url


def _apply_backend_environment(*, database_url: str) -> None:
    os.environ["DATABASE_URL"] = _cwd_host_sqlite_file_database_url(database_url)
    os.environ.setdefault("AUTOPULSE_RUNTIME_EMBEDDED", "1")
    # Embedded mode must run retention housekeeping; otherwise local DB caps are never enforced.
    # Do not use setdefault: a repo `.env` often sets JOBS_ENABLE_SCHEDULER=false, which would win.
    os.environ["JOBS_ENABLE_SCHEDULER"] = "1"
    os.environ.setdefault("JOBS_RETENTION_INTERVAL_SECONDS", "300")
    # Global SQLite file ceiling (oldest events across all projects). Set to 0 to disable.
    os.environ.setdefault("AUTOPULSE_EMBEDDED_MAX_DB_SIZE_MB", "512")


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
        cap_mb = _embedded_max_db_size_mb_for_settings()

        if existing_key is not None:
            project = await session.scalar(select(Project).where(Project.name == project_name))
            if project is not None:
                ui_settings = await session.scalar(
                    select(ProjectUiSettings).where(ProjectUiSettings.project_id == project.id)
                )
                if ui_settings is None:
                    session.add(
                        ProjectUiSettings(
                            project_id=project.id,
                            theme_preference="system",
                            retention_max_db_size_mb=cap_mb,
                        )
                    )
                    await session.commit()
                elif cap_mb is not None and ui_settings.retention_max_db_size_mb is None:
                    ui_settings.retention_max_db_size_mb = cap_mb
                    await session.commit()
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
            session.add(
                ProjectUiSettings(
                    project_id=project.id,
                    theme_preference="system",
                    retention_max_db_size_mb=cap_mb,
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


def _start_embedded_background_jobs(app: Any) -> None:
    """Start backend scheduler/poller explicitly for embedded hosts.

    Mounted backend lifespans are not guaranteed to run in all host setups, so start
    retention/alerts loops from the host app startup path as well.
    """
    from autopulse_backend.core.config import (
        _is_autopulse_embedded_default_sqlite_file,
        get_settings,
    )
    from autopulse_backend.jobs import (
        retention_pressure_poll_should_run,
        start_retention_only_scheduler,
        start_retention_pressure_poll,
        start_scheduler,
    )

    settings = get_settings()
    if getattr(app.state, "_autopulse_scheduler", None) is None:
        if settings.jobs_enable_scheduler:
            app.state._autopulse_scheduler = start_scheduler(settings=settings)
        elif _is_autopulse_embedded_default_sqlite_file(settings.database_url):
            app.state._autopulse_scheduler = start_retention_only_scheduler(settings=settings)
        else:
            app.state._autopulse_scheduler = None

    if getattr(app.state, "_autopulse_retention_pressure_poll", None) is None:
        if retention_pressure_poll_should_run(settings):
            app.state._autopulse_retention_pressure_poll = start_retention_pressure_poll(
                settings=settings
            )
        else:
            app.state._autopulse_retention_pressure_poll = None


_EMBEDDED_UI_ASSET_SUFFIXES: frozenset[str] = frozenset(
    {
        ".css",
        ".eot",
        ".gif",
        ".ico",
        ".jpeg",
        ".jpg",
        ".js",
        ".json",
        ".map",
        ".mjs",
        ".png",
        ".svg",
        ".ttf",
        ".txt",
        ".webp",
        ".woff",
        ".woff2",
    }
)


def _embedded_ui_path_looks_like_static_asset(path: str) -> bool:
    """Avoid SPA fallback for real static requests (Next ``_next/``, images, fonts, …)."""
    tail = path.rstrip("/").rsplit("/", 1)[-1].lower()
    if "." not in tail:
        return False
    return any(tail.endswith(suffix) for suffix in _EMBEDDED_UI_ASSET_SUFFIXES)


class _EmbeddedDashboardStaticFiles(StaticFiles):
    """Next static export under ``/ui``; fall back to ``index.html`` for client routes."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or not self.html:
                raise
            if _embedded_ui_path_looks_like_static_asset(path):
                raise
            return await super().get_response("index.html", scope)


async def _stop_embedded_background_jobs(app: Any) -> None:
    from autopulse_backend.jobs import RetentionPressurePollHandle, SchedulerHandle

    scheduler = getattr(app.state, "_autopulse_scheduler", None)
    if isinstance(scheduler, SchedulerHandle):
        await scheduler.stop()
    app.state._autopulse_scheduler = None

    pressure = getattr(app.state, "_autopulse_retention_pressure_poll", None)
    if isinstance(pressure, RetentionPressurePollHandle):
        await pressure.stop()
    app.state._autopulse_retention_pressure_poll = None


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
        _EmbeddedDashboardStaticFiles(directory=str(resolved_dir), html=True),
        name="autopulse-ui",
    )

    @backend_app.get("/", include_in_schema=False)  # type: ignore[untyped-decorator]
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
    _apply_env_autopulse_file_defaults(_env_autopulse_path())
    raw_kw = kwargs.get("api_key")
    kwargs_api_key = raw_kw.strip() if isinstance(raw_kw, str) and raw_kw.strip() else None
    api_key = _resolve_embedded_api_key(kwargs_api_key=kwargs_api_key, mount_prefix=prefix)
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

            # Never block application startup on retention; large local DB cleanup can be slow.
            async def _run_retention_background() -> None:
                with suppress(Exception):
                    await run_retention_once(settings=get_settings())

            task = asyncio.create_task(_run_retention_background())
            app.state._autopulse_startup_retention_task = task
            # Ensure periodic loops run in embedded hosts even if mounted
            # subapp lifespan is skipped.
            _start_embedded_background_jobs(app)

        async def stop_startup_retention_task() -> None:
            task = getattr(app.state, "_autopulse_startup_retention_task", None)
            if task is None:
                return
            if not task.done():
                task.cancel()
                with suppress(Exception):
                    await task
            app.state._autopulse_startup_retention_task = None
            await _stop_embedded_background_jobs(app)

        _add_event_handler(app, "startup", ensure_project_key)
        _add_event_handler(app, "shutdown", stop_startup_retention_task)
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
        "embedded_startup_ingest_ping": _embedded_startup_ingest_ping_enabled(),
        "http_client": provided_http_client
        or httpx.AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False)),
        "owns_http_client": provided_http_client is None,
    }
