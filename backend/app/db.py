"""
NEXUS -- Async Database Engine & Session Factory.

Provides:
- ``engine``           -- global async SQLAlchemy engine (created lazily).
- ``async_session``    -- session factory bound to the engine.
- ``get_session()``    -- async context-manager yielding a session (for CLI/pipeline).
- ``get_db_session()`` -- FastAPI dependency yielding a session (for routes).
- ``init_db()``        -- creates the pgvector extension + all tables.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine() -> AsyncEngine:
    """Create or return the global async engine (lazy singleton)."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.log_level == "DEBUG",
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Create or return the session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=_get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session, rolling back on unhandled exceptions.

    Used by CLI commands and the scraping pipeline.  For FastAPI route
    handlers, use ``get_db_session`` instead.
    """
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session.

    The route handler is responsible for calling ``session.commit()``
    when it wants to persist changes.  On unhandled exceptions the
    session is rolled back automatically.

    This is intentionally **not** an ``@asynccontextmanager`` -- FastAPI
    needs a bare async generator for ``Depends()``.
    """
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """
    Ensure the ``pgvector`` extension exists and create all ORM tables.

    Safe to call multiple times -- uses ``CREATE EXTENSION IF NOT EXISTS``
    and ``CREATE TABLE IF NOT EXISTS`` semantics.
    """
    from app.models import Base  # local import to avoid circular deps

    engine = _get_engine()

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        logger.info("pgvector extension ready.")
        await conn.run_sync(Base.metadata.create_all)
        logger.info("All tables created / verified.")


async def dispose_engine() -> None:
    """Dispose of the connection pool (call on shutdown)."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None

