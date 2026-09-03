"""Alembic environment — async-capable for SQLAlchemy 2.0 + asyncpg/aiosqlite."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# Import all models so metadata is populated
from app.models.base import Base
import app.models.domain  # noqa: F401
import app.models.literature  # noqa: F401
import app.models.user  # noqa: F401
import app.models.conversation  # noqa: F401
import app.models.tool_call  # noqa: F401
import app.models.project  # noqa: F401
import app.models.strategy_checkpoint  # noqa: F401
import app.models.identity_consistency  # noqa: F401
from app.core.config import Settings

# Alembic Config object
config = context.config

settings = Settings()

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    # Build directly from the application URL. ConfigParser interpolation
    # treats percent-encoded password bytes (for example ``%28``) as syntax.
    connectable = create_async_engine(settings.DATABASE_URL, poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
