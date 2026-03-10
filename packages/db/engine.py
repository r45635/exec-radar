"""Async SQLAlchemy engine and session factory.

All database access in the application flows through the engine built
here.  The ``database_url`` is read from ``Settings`` (via env vars).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Module-level singletons — initialised lazily via ``init_engine``.
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(
    url: str,
    *,
    echo: bool = False,
    pool_size: int = 5,
) -> AsyncEngine:
    """Create (or replace) the module-level async engine.

    Args:
        url: SQLAlchemy-compatible async database URL.
        echo: Whether to log all SQL statements.
        pool_size: Connection pool size (ignored for SQLite).

    Returns:
        The newly created :class:`AsyncEngine`.
    """
    global _engine, _session_factory

    kwargs: dict = {"echo": echo}
    # SQLite doesn't support pool_size
    if not url.startswith("sqlite"):
        kwargs["pool_size"] = pool_size

    _engine = create_async_engine(url, **kwargs)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_engine() -> AsyncEngine:
    """Return the current engine, raising if not initialised."""
    if _engine is None:
        msg = "Database engine not initialised — call init_engine() first"
        raise RuntimeError(msg)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the session factory, raising if not initialised."""
    if _session_factory is None:
        msg = "Session factory not initialised — call init_engine() first"
        raise RuntimeError(msg)
    return _session_factory
