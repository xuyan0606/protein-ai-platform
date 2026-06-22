"""SQLAlchemy 2.0 async database engine and session management."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

_is_sqlite = settings.USE_SQLITE

_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    **({} if _is_sqlite else dict(pool_size=20, max_overflow=10, pool_pre_ping=True)),
)

_async_session_factory = async_sessionmaker(
    _engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_engine():
    """Return the async engine (useful for lifespan events)."""
    return _engine


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async DB session."""
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope():
    """Context-manager style session for non-FastAPI usage (scripts, tasks)."""
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Create all tables from model metadata (MVP dev convenience)."""
    from app.models.base import Base
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_engine():
    """Clean up the engine on shutdown."""
    await _engine.dispose()
