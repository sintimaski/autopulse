from __future__ import annotations

import threading
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from autopulse_backend.core.config import get_settings


def repair_sqlite_dashboard_users_oidc_columns(database_url: str) -> None:
    """Ensure ``dashboard_users`` has OIDC link columns (SQLite dev drift).

    Local SQLite historically used ``create_all``, which does not add new columns
    to existing tables when models gain fields. Some databases were also stamped
    at Alembic head without running the migration. This repair is idempotent.
    """
    if not database_url.startswith("sqlite"):
        return
    engine = create_engine(_sync_database_url(database_url))
    try:
        with engine.begin() as conn:
            table = conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name='dashboard_users'"
                )
            ).first()
            if table is None:
                return
            cols = {row[1] for row in conn.execute(text("PRAGMA table_info(dashboard_users)"))}
            if "idp_provider" not in cols:
                conn.execute(
                    text("ALTER TABLE dashboard_users ADD COLUMN idp_provider VARCHAR(64)")
                )
            if "idp_subject" not in cols:
                conn.execute(
                    text("ALTER TABLE dashboard_users ADD COLUMN idp_subject VARCHAR(255)")
                )
            idx = conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='index' "
                    "AND name='ux_dashboard_users_idp_provider_subject'"
                )
            ).first()
            if idx is None:
                conn.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS "
                        "ux_dashboard_users_idp_provider_subject "
                        "ON dashboard_users (idp_provider, idp_subject) "
                        "WHERE idp_provider IS NOT NULL AND idp_subject IS NOT NULL"
                    )
                )
    finally:
        engine.dispose()


_SQLITE_UPGRADE_LOCK = threading.Lock()
_SQLITE_UPGRADE_DONE_URLS: set[str] = set()


def reset_sqlite_upgrade_to_head_cache() -> None:
    """Clear the per-process SQLite migration skip cache.

    Use when tests recreate the database file at the same ``DATABASE_URL`` path.
    """
    with _SQLITE_UPGRADE_LOCK:
        _SQLITE_UPGRADE_DONE_URLS.clear()


def _sync_database_url(database_url: str) -> str:
    return database_url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg")


def _sqlite_schema_exists_without_alembic(database_url: str) -> bool:
    if not database_url.startswith("sqlite"):
        return False
    engine = create_engine(_sync_database_url(database_url))
    try:
        with engine.connect() as connection:
            projects_exists = connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='projects'")
            ).first()
            alembic_exists = connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
            ).first()
            return projects_exists is not None and alembic_exists is None
    finally:
        engine.dispose()


def _run_alembic_upgrade_to_head(config: Config, database_url: str) -> None:
    if _sqlite_schema_exists_without_alembic(database_url):
        command.stamp(config, "head")
        return
    try:
        command.upgrade(config, "head")
    except SQLAlchemyError:
        if _sqlite_schema_exists_without_alembic(database_url):
            command.stamp(config, "head")
            return
        raise


def upgrade_to_head() -> None:
    database_url = get_settings().database_url
    backend_root = Path(__file__).resolve().parents[3]
    alembic_ini = backend_root / "alembic.ini"
    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    if database_url.startswith("sqlite"):
        repair_sqlite_dashboard_users_oidc_columns(database_url)
        with _SQLITE_UPGRADE_LOCK:
            if database_url in _SQLITE_UPGRADE_DONE_URLS:
                return
            _run_alembic_upgrade_to_head(config, database_url)
            _SQLITE_UPGRADE_DONE_URLS.add(database_url)
        return

    _run_alembic_upgrade_to_head(config, database_url)
