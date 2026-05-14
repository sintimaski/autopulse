"""File-backed SQLite must survive several concurrent writers in one process.

Regression cover for the ``database is locked`` snowball. The fix is a two-engine
split (``database/session.py``): read transactions keep a deferred ``BEGIN`` (they
only ever take a SHARED lock, so they stay concurrent under WAL and never hold the
write lock), while ``write_session()`` opens ``BEGIN IMMEDIATE`` so a read-then-write
transaction never fails on a SHARED -> RESERVED upgrade. These tests pin both halves.
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

from sqlalchemy import text

from lumonox_backend.database.session import (
    dispose_engine_for_url,
    get_engine,
    get_session_maker,
    get_write_session_maker,
    write_session,
)


def _sqlite_url(db_path: Path) -> str:
    return f"sqlite+aiosqlite:///{db_path}"


def _raw_write_succeeds(db_path: Path) -> bool:
    """True if a separate connection can INSERT now (i.e. no one holds the write lock)."""
    raw = sqlite3.connect(str(db_path), timeout=0.3)
    try:
        raw.execute("INSERT INTO t (v) VALUES (1)")
        raw.commit()
        return True
    except sqlite3.OperationalError as exc:
        if "locked" in str(exc):
            return False
        raise
    finally:
        raw.close()


def test_write_session_holds_write_lock_after_select_only(tmp_path: Path) -> None:
    """A ``write_session`` that has only run a ``SELECT`` already holds the write lock.

    Proves ``write_session`` opens ``BEGIN IMMEDIATE``: under a deferred ``BEGIN`` a
    select-only transaction would hold only SHARED and WAL would let the raw writer
    through.
    """
    db_path = tmp_path / "write_immediate.db"
    url = _sqlite_url(db_path)

    async def run() -> bool:
        engine = get_engine(url)
        async with engine.begin() as conn:
            await conn.exec_driver_sql("CREATE TABLE t (id INTEGER PRIMARY KEY, v INTEGER)")
        async with write_session(url) as session:
            await session.execute(text("SELECT 1"))  # read only — no write statement yet
            return _raw_write_succeeds(db_path)

    try:
        raw_write_succeeded = asyncio.run(run())
    finally:
        asyncio.run(dispose_engine_for_url(url))

    assert raw_write_succeeded is False


def test_read_session_does_not_hold_write_lock(tmp_path: Path) -> None:
    """A read session leaves the write lock free — reads must stay concurrent under WAL.

    Regression guard against re-introducing a global ``BEGIN IMMEDIATE`` (which
    self-deadlocked the SQL-tail repair job: an outer read session would own the
    write lock its own inner write sessions needed).
    """
    db_path = tmp_path / "read_deferred.db"
    url = _sqlite_url(db_path)

    async def run() -> bool:
        engine = get_engine(url)
        async with engine.begin() as conn:
            await conn.exec_driver_sql("CREATE TABLE t (id INTEGER PRIMARY KEY, v INTEGER)")
        session_maker = get_session_maker(url)
        async with session_maker() as session:
            await session.execute(text("SELECT 1"))  # deferred BEGIN → SHARED only
            return _raw_write_succeeds(db_path)

    try:
        raw_write_succeeded = asyncio.run(run())
    finally:
        asyncio.run(dispose_engine_for_url(url))

    assert raw_write_succeeded is True


def test_concurrent_read_then_write_sessions_all_commit(tmp_path: Path) -> None:
    """Many concurrent read-then-write ``write_session`` transactions all commit.

    The ingest snowball in miniature: each task mirrors the ingest tail (read, then
    write). Before the ``BEGIN IMMEDIATE`` write engine these collided on the lock
    upgrade and raised ``OperationalError``.
    """
    db_path = tmp_path / "concurrent_writers.db"
    url = _sqlite_url(db_path)
    writers = 16

    async def run() -> int:
        engine = get_engine(url)
        async with engine.begin() as conn:
            await conn.exec_driver_sql(
                "CREATE TABLE counter (id INTEGER PRIMARY KEY, v INTEGER NOT NULL)"
            )
            await conn.exec_driver_sql("INSERT INTO counter (id, v) VALUES (1, 0)")

        async def read_then_write(delta: int) -> None:
            async with write_session(url) as session:
                current = await session.scalar(text("SELECT v FROM counter WHERE id = 1"))
                await session.execute(
                    text("UPDATE counter SET v = :v WHERE id = 1"),
                    {"v": int(current or 0) + delta},
                )
                await session.commit()

        await asyncio.gather(*(read_then_write(1) for _ in range(writers)))

        read_maker = get_session_maker(url)
        async with read_maker() as session:
            return int(await session.scalar(text("SELECT v FROM counter WHERE id = 1")) or 0)

    try:
        final = asyncio.run(run())
    finally:
        asyncio.run(dispose_engine_for_url(url))

    # BEGIN IMMEDIATE serializes the writers, so every increment lands.
    assert final == writers


def test_open_read_session_does_not_block_a_write_session(tmp_path: Path) -> None:
    """An open read session (SHARED) must not block a concurrent ``write_session``.

    This is the SQL-tail repair job's shape: an outer session reads the pending
    queue and stays open while inner ``write_session`` transactions apply each row.
    The inner writes must commit without raising "database is locked".
    """
    db_path = tmp_path / "read_plus_write.db"
    url = _sqlite_url(db_path)

    async def run() -> int:
        engine = get_engine(url)
        async with engine.begin() as conn:
            await conn.exec_driver_sql("CREATE TABLE t (id INTEGER PRIMARY KEY, v INTEGER)")

        read_maker = get_session_maker(url)
        write_maker = get_write_session_maker(url)
        async with read_maker() as read_session:
            # Hold a read transaction open (SHARED) across the writes below.
            await read_session.execute(text("SELECT COUNT(*) FROM t"))
            for value in range(5):
                async with write_maker() as inner_write:
                    await inner_write.execute(text("INSERT INTO t (v) VALUES (:v)"), {"v": value})
                    await inner_write.commit()

        # A fresh read transaction sees every committed row.
        async with read_maker() as session:
            return int(await session.scalar(text("SELECT COUNT(*) FROM t")) or 0)

    try:
        final_count = asyncio.run(run())
    finally:
        asyncio.run(dispose_engine_for_url(url))

    assert final_count == 5
