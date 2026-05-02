from __future__ import annotations

import logging
from logging.config import fileConfig
from os import getenv

from alembic import context
from sqlalchemy import engine_from_config, pool

from autopulse_backend.core.config import normalize_database_url
from autopulse_backend.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
    # ``alembic.ini`` sets the Alembic loggers to INFO; that is useful for one-off CLI
    # sessions but noisy when ``upgrade_to_head()`` runs during Uvicorn startup (and
    # on every worker / reload). Keep SQLAlchemy engine at WARN from the ini; tame the
    # migration framework chatter unless explicitly overridden.
    if getenv("AUTOPULSE_ALEMBIC_LOG", "").strip().lower() not in {
        "1",
        "true",
        "yes",
        "debug",
        "info",
    }:
        for _name in ("alembic", "alembic.runtime.migration"):
            logging.getLogger(_name).setLevel(logging.WARNING)

target_metadata = Base.metadata


def _database_url() -> str:
    return (
        normalize_database_url(
            getenv(
                "DATABASE_URL",
                config.get_main_option("sqlalchemy.url"),
            )
        )
        .replace("+asyncpg", "+psycopg")
        .replace("+aiosqlite", "")
    )


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
