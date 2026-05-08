from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from autopulse_backend.core.config import get_settings


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


def upgrade_to_head() -> None:
    database_url = get_settings().database_url
    pkg_root = Path(__file__).resolve().parents[1]
    alembic_dir = pkg_root / "alembic"
    if not alembic_dir.is_dir():
        msg = (
            "Alembic migration scripts not found next to autopulse_backend package "
            f"({alembic_dir}); reinstall autopulse-backend or run from repository sources."
        )
        raise RuntimeError(msg)
    # Load config without relying on alembic.ini on disk — required for installs from wheels
    # where scripts live under site-packages next to autopulse_backend.
    config = Config()
    config.set_main_option("script_location", str(alembic_dir))
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
