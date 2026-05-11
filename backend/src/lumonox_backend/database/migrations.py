from __future__ import annotations

from contextlib import suppress
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import SQLAlchemyError

from lumonox_backend.core.config import get_settings


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


def _sqlite_file_paths(database_url: str) -> list[Path] | None:
    """On-disk SQLite paths (including WAL sidecars), or None if not a file-backed URL."""
    sync = _sync_database_url(database_url)
    if not sync.startswith("sqlite"):
        return None
    url = make_url(sync)
    db_path = url.database
    if db_path is None or db_path in {":memory:", ""}:
        return None
    path = Path(db_path)
    path = path.resolve() if path.is_absolute() else (Path.cwd() / path).resolve()
    return [path, Path(f"{path}-wal"), Path(f"{path}-shm")]


def _unlink_sqlite_files(paths: list[Path]) -> None:
    for p in paths:
        with suppress(OSError):
            p.unlink(missing_ok=True)


def upgrade_to_head() -> None:
    database_url = get_settings().database_url
    pkg_root = Path(__file__).resolve().parents[1]
    alembic_dir = pkg_root / "alembic"
    if not alembic_dir.is_dir():
        msg = (
            "Alembic migration scripts not found next to lumonox_backend package "
            f"({alembic_dir}); reinstall lumonox or run from repository sources."
        )
        raise RuntimeError(msg)
    # Load config without relying on alembic.ini on disk — required for installs from wheels
    # where scripts live under site-packages next to lumonox_backend.
    config = Config()
    config.set_main_option("script_location", str(alembic_dir))
    if _sqlite_schema_exists_without_alembic(database_url):
        command.stamp(config, "head")
        return

    def _run_upgrade() -> None:
        command.upgrade(config, "head")

    try:
        _run_upgrade()
    except SQLAlchemyError:
        if _sqlite_schema_exists_without_alembic(database_url):
            command.stamp(config, "head")
            return
        raise
    except Exception as exc:
        # Replacing the migration chain leaves stale revision ids in alembic_version on
        # developer SQLite files; wipe the file-backed DB once and rebuild from ``initial``.
        if "can't locate revision" in str(exc).lower() and database_url.lower().startswith(
            "sqlite"
        ):
            paths = _sqlite_file_paths(database_url)
            if paths:
                _unlink_sqlite_files(paths)
                _run_upgrade()
                return
        raise
