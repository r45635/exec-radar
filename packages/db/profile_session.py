"""Shared async SQLite session factory for profile management.

Used by both the API routes and the dashboard routes to access the
same profiles database.  Provides a ``reset()`` function for tests.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from packages.db.base import Base
from packages.db.models import ProfileRecord  # noqa: F401

_PROFILES_DB_PATH = Path(
    os.getenv("EXEC_RADAR_PROFILES_DB", ".data/profiles.sqlite3")
)
_PROFILES_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
_PROFILES_DB_URL = f"sqlite+aiosqlite:///{_PROFILES_DB_PATH}"

_engine = create_async_engine(_PROFILES_DB_URL, echo=False)
_session_factory = async_sessionmaker(_engine, expire_on_commit=False)
_initialized = False


async def ensure_tables() -> None:
    """Create tables on first access (idempotent)."""
    global _initialized
    if _initialized:
        return
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    _initialized = True


async def get_session() -> AsyncSession:
    """Return a new async session (caller manages lifecycle)."""
    await ensure_tables()
    return _session_factory()


async def reset_for_tests() -> None:
    """Drop and recreate all tables. Only for tests."""
    global _initialized
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    _initialized = True
