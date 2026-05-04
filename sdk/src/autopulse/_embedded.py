from __future__ import annotations

import asyncio
import logging
import os
import shlex
import socket
import subprocess  # nosec B404
import threading
import time
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path
from typing import Any

import httpx
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.exceptions import HTTPException
from starlette.responses import RedirectResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from autopulse._embedded_loopback_proxy import AutopulseLoopbackMountProxy

_LOG = logging.getLogger(__name__)

# Example key for local ``.env`` / docs only. Never used as an automatic runtime fallback
# (generated keys are used when ``.env.autopulse`` cannot be written).
DEFAULT_EMBEDDED_API_KEY = "ap_live_embeddedlocal_localdevsecret"
DEFAULT_EMBEDDED_DATABASE_URL = "sqlite+aiosqlite:///./.autopulse/autopulse.db"
DEFAULT_MOUNT_PREFIX = "/autopulse"
DEFAULT_PROJECT_NAME = "AutoPulse Embedded Project"

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


def _embedded_startup_retention_enabled() -> bool:
    raw = os.environ.get("AUTOPULSE_EMBEDDED_STARTUP_RETENTION")
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_embedded_data_root() -> Path:
    """Stable root for embedded defaults (env bundle + relative SQLite paths)."""
    for key in ("AUTOPULSE_DATA_DIR", "AUTOPULSE_PROJECT_ROOT"):
        raw = os.environ.get(key, "").strip()
        if raw:
            return Path(raw).expanduser().resolve()
    with suppress(Exception):
        from autopulse_backend.core.config import resolve_autopulse_data_root

        return resolve_autopulse_data_root()
    return Path.cwd().resolve()


def _env_autopulse_path() -> Path:
    raw = os.environ.get("AUTOPULSE_ENV_AUTOPULSE_FILE", "").strip()
    if raw:
        return Path(raw).expanduser()
    return _resolve_embedded_data_root() / ".env.autopulse"


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
        "# (run_synthetic_stack.sh sources when present; sidecar sets NEXT_PUBLIC_* in env.)\n"
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


def _normalize_embedded_database_url(database_url: str) -> str:
    """Normalize embedded DB URL against AutoPulse data-root semantics.

    This keeps embedded project/key metadata stable across restarts even when the
    process current working directory changes.
    """
    with suppress(Exception):
        from autopulse_backend.core.config import normalize_database_url

        return normalize_database_url(database_url)
    return database_url


def _apply_backend_environment(*, database_url: str) -> None:
    os.environ["DATABASE_URL"] = database_url
    os.environ.setdefault("AUTOPULSE_RUNTIME_EMBEDDED", "1")
    # Respect backend/.env or explicit runtime JOBS_ENABLE_SCHEDULER choices.
    # If unset, backend defaults still enable scheduler for embedded default SQLite paths.
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
                elif ui_settings.retention_max_db_size_mb != cap_mb:
                    # Keep persisted per-project retention cap aligned with current embedded env.
                    # This also allows clearing an old cap when env changes to disabled (None).
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
        elif ui_settings.retention_max_db_size_mb != cap_mb:
            ui_settings.retention_max_db_size_mb = cap_mb
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


def _normalize_sidecar_argv(command: str | Sequence[str] | None) -> list[str] | None:
    if command is None:
        return None
    if isinstance(command, str):
        parts = shlex.split(command.strip())
        return parts or None
    out = [str(p).strip() for p in command]
    out = [p for p in out if p]
    return out or None


def _resolve_sidecar_frontend_root(cwd_hint: str | None) -> Path | None:
    """Directory containing the Next.js ``package.json`` for ``npm run dev``."""
    if cwd_hint:
        p = Path(cwd_hint).expanduser().resolve()
        if (p / "package.json").is_file():
            return p
    candidate = Path.cwd() / "frontend"
    if (candidate / "package.json").is_file():
        return candidate.resolve()
    return None


def _configure_sidecar(
    app: Any,
    *,
    command: str | Sequence[str] | None,
    working_directory: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> None:
    argv = _normalize_sidecar_argv(command)
    if not argv or getattr(app.state, "_autopulse_sidecar_registered", False):
        return
    sidecar_cwd = Path(working_directory).resolve() if working_directory else Path.cwd()

    async def start_sidecar() -> None:
        if getattr(app.state, "_autopulse_sidecar_process", None) is not None:
            return
        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)
        _LOG.info(
            "Starting dashboard frontend sidecar (cwd=%s argv=%s)",
            sidecar_cwd,
            argv,
        )
        process = subprocess.Popen(  # nosec B603
            argv,
            cwd=str(sidecar_cwd),
            env=env,
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


def _resolve_embedded_ingest_transport(kwargs: dict[str, Any]) -> str:
    """``http`` (default): loopback FastAPI + HTTP ingest (matches split-stack responsiveness).

    ``asgi``: legacy in-process ASGI transport to the host app (smaller surface, can lag WS).
    """
    raw_kw = kwargs.get("embedded_ingest_transport")
    if raw_kw is not None:
        v = str(raw_kw).strip().lower()
        return v if v in {"http", "asgi"} else "http"
    env = os.getenv("AUTOPULSE_EMBEDDED_INGEST_TRANSPORT", "http").strip().lower()
    return env if env in {"http", "asgi"} else "http"


def _pick_loopback_tcp_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])
    finally:
        s.close()


def _wait_loopback_ready(*, port: int, prefix: str, timeout_s: float = 30.0) -> None:
    base = prefix.rstrip("/") or ""
    url = f"http://127.0.0.1:{port}{base}/ready"
    deadline = time.perf_counter() + timeout_s
    last_exc: Exception | None = None
    while time.perf_counter() < deadline:
        try:
            with httpx.Client(timeout=0.75) as client:
                response = client.get(url)
                if response.status_code == 200:
                    return
        except (httpx.RequestError, OSError) as exc:
            last_exc = exc
        time.sleep(0.05)
    msg = f"AutoPulse embedded loopback server did not become ready at {url}"
    if last_exc is not None:
        raise RuntimeError(msg) from last_exc
    raise RuntimeError(msg)


def _start_uvicorn_embedded_loopback(app: Any, *, port: int) -> tuple[Any, threading.Thread]:
    import asyncio

    import uvicorn

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)

    def _serve() -> None:
        asyncio.run(server.serve())

    thread = threading.Thread(target=_serve, name="autopulse-embedded-loopback", daemon=True)
    thread.start()
    return server, thread


def configure_embedded(app: Any, *, kwargs: dict[str, Any]) -> dict[str, Any]:
    mode = str(kwargs.get("mode", "embedded")).strip().lower()
    if mode != "embedded":
        return {}
    prefix = _normalize_prefix(str(kwargs.get("mount_prefix", DEFAULT_MOUNT_PREFIX)))
    database_url = _normalize_embedded_database_url(
        str(kwargs.get("database_url") or DEFAULT_EMBEDDED_DATABASE_URL)
    )
    project_name = str(kwargs.get("embedded_project_name", DEFAULT_PROJECT_NAME))
    _apply_env_autopulse_file_defaults(_env_autopulse_path())
    raw_kw = kwargs.get("api_key")
    kwargs_api_key = raw_kw.strip() if isinstance(raw_kw, str) and raw_kw.strip() else None
    api_key = _resolve_embedded_api_key(kwargs_api_key=kwargs_api_key, mount_prefix=prefix)
    if "frontend_mode" in kwargs and kwargs.get("frontend_mode") is not None:
        raw_frontend = str(kwargs["frontend_mode"]).strip().lower()
    else:
        raw_frontend = os.getenv("AUTOPULSE_FRONTEND_MODE", "static").strip().lower()
    frontend_mode = raw_frontend if raw_frontend in {"static", "sidecar"} else "static"
    probe_interval_ms = float(
        kwargs.get(
            "infrastructure_probe_interval_ms",
            os.getenv("AUTOPULSE_INFRA_PROBE_INTERVAL_MS", "100"),
        )
    )
    _apply_backend_environment(database_url=database_url)

    ingest_transport = _resolve_embedded_ingest_transport(kwargs)

    if not getattr(app.state, "_autopulse_embedded_configured", False):
        if ingest_transport == "http":
            from fastapi import FastAPI

            from autopulse_backend.app import mount_on_app

            loopback_root = FastAPI()
            backend_app = mount_on_app(loopback_root, prefix=prefix)
            if frontend_mode == "static":
                _mount_embedded_ui(backend_app, static_dir=kwargs.get("frontend_static_dir"))
            port = _pick_loopback_tcp_port()
            server, loopback_thread = _start_uvicorn_embedded_loopback(loopback_root, port=port)
            _wait_loopback_ready(port=port, prefix=prefix)

            proxy = AutopulseLoopbackMountProxy(loopback_port=port)
            mount_path = prefix.rstrip("/") or "/"
            app.mount(mount_path, proxy)

            app.state._autopulse_embedded_loopback_http = True
            app.state._autopulse_embedded_loopback_server = server
            app.state._autopulse_embedded_loopback_thread = loopback_thread
            app.state._autopulse_embedded_loopback_port = port
            app.state._autopulse_embedded_loopback_proxy = proxy
            app.state._autopulse_embedded_loopback_ingest_url = (
                f"http://127.0.0.1:{port}{prefix}/ingest"
            )

            async def ensure_project_key() -> None:
                from autopulse_backend.config import get_settings
                from autopulse_backend.jobs import run_retention_once

                await _ensure_embedded_project_and_key(
                    database_url=database_url,
                    project_name=project_name,
                    api_key=api_key,
                )

                if _embedded_startup_retention_enabled():

                    async def _run_retention_background() -> None:
                        with suppress(Exception):
                            await run_retention_once(settings=get_settings())

                    task = asyncio.create_task(_run_retention_background())
                    app.state._autopulse_startup_retention_task = task
                else:
                    app.state._autopulse_startup_retention_task = None

            async def stop_embedded_stack() -> None:
                task = getattr(app.state, "_autopulse_startup_retention_task", None)
                if task is not None:
                    if not task.done():
                        task.cancel()
                        with suppress(Exception):
                            await task
                    app.state._autopulse_startup_retention_task = None
                proxy_obj = getattr(app.state, "_autopulse_embedded_loopback_proxy", None)
                if proxy_obj is not None:
                    await proxy_obj.aclose()
                srv = getattr(app.state, "_autopulse_embedded_loopback_server", None)
                if srv is not None:
                    srv.should_exit = True
                thr = getattr(app.state, "_autopulse_embedded_loopback_thread", None)
                if thr is not None and thr.is_alive():
                    await asyncio.to_thread(thr.join, 15.0)
                app.state._autopulse_embedded_loopback_proxy = None
                app.state._autopulse_embedded_loopback_server = None
                app.state._autopulse_embedded_loopback_thread = None

            _add_event_handler(app, "startup", ensure_project_key)
            _add_event_handler(app, "shutdown", stop_embedded_stack)
            _LOG.info(
                "AutoPulse embedded loopback ingest=http://127.0.0.1:%s%s/ingest; "
                "dashboard mount on your app remains at %s",
                port,
                prefix,
                prefix,
            )
        else:
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

                if _embedded_startup_retention_enabled():

                    async def _run_retention_background() -> None:
                        with suppress(Exception):
                            await run_retention_once(settings=get_settings())

                    task = asyncio.create_task(_run_retention_background())
                    app.state._autopulse_startup_retention_task = task
                else:
                    app.state._autopulse_startup_retention_task = None
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
            cmd_kw = kwargs.get("frontend_sidecar_command")
            cmd_env = os.getenv("AUTOPULSE_FRONTEND_SIDECAR_COMMAND", "").strip() or None
            if cmd_kw not in (None, ""):
                explicit_cmd = cmd_kw
            elif cmd_env:
                explicit_cmd = cmd_env
            else:
                explicit_cmd = None
            cwd_kw = kwargs.get("frontend_sidecar_cwd")
            cwd_env = os.getenv("AUTOPULSE_FRONTEND_DIR", "").strip() or None
            merged_cwd = cwd_kw or cwd_env
            if explicit_cmd is not None:
                _configure_sidecar(
                    app,
                    command=explicit_cmd,
                    working_directory=merged_cwd,
                    extra_env={"AUTOPULSE_FRONTEND_MODE": "sidecar"},
                )
            else:
                root = _resolve_sidecar_frontend_root(merged_cwd)
                if root is None:
                    _LOG.warning(
                        "AUTOPULSE_FRONTEND_MODE=sidecar but no frontend_sidecar_command / "
                        "AUTOPULSE_FRONTEND_SIDECAR_COMMAND and no frontend/package.json under cwd "
                        "or AUTOPULSE_FRONTEND_DIR — skipping Next dev sidecar."
                    )
                else:
                    _configure_sidecar(
                        app,
                        command=["npm", "run", "dev"],
                        working_directory=str(root),
                        extra_env={"AUTOPULSE_FRONTEND_MODE": "sidecar"},
                    )
        app.state._autopulse_embedded_configured = True

    loopback_ingest = getattr(app.state, "_autopulse_embedded_loopback_ingest_url", None)
    if loopback_ingest and ingest_transport == "http":
        ingest_url = kwargs.get("ingest_url") or loopback_ingest
        provided_http_client = kwargs.get("http_client")
        return {
            "api_key": api_key,
            "ingest_url": ingest_url,
            "infrastructure_probe_interval_ms": probe_interval_ms,
            "embedded_startup_ingest_ping": _embedded_startup_ingest_ping_enabled(),
            "http_client": provided_http_client or httpx.AsyncClient(timeout=httpx.Timeout(30.0)),
            "owns_http_client": provided_http_client is None,
        }

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
