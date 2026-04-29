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
    backend_root = Path(__file__).resolve().parents[3]
    alembic_ini = backend_root / "alembic.ini"
    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(backend_root / "alembic"))
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
