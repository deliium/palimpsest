"""Alembic environment.

The database URL is loaded from validated settings, never from alembic.ini.
"""

from __future__ import annotations

import asyncio

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from infrastructure.logging import get_logger, log_setup_failure
from infrastructure.orm import metadata
from infrastructure.settings import load_migration_settings, redact_secrets

config = context.config
_ = config.get_main_option("script_location")
target_metadata = metadata
_LOGGER = get_logger("infrastructure.migrations")
REVISION_HEAD = "0001"


def run_migrations_offline() -> None:
    settings = load_migration_settings()
    context.configure(
        url=settings.database_dsn(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    _LOGGER.info("migration_started", revision=REVISION_HEAD, mode="offline")
    try:
        with context.begin_transaction():
            context.run_migrations()
    except Exception as exc:
        log_setup_failure(redact_secrets(type(exc).__name__))
        raise
    _LOGGER.info("migration_completed", revision=REVISION_HEAD, mode="offline")


def _configure_connection(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    settings = load_migration_settings()
    engine = create_async_engine(
        settings.database_dsn(),
        poolclass=pool.NullPool,
        hide_parameters=True,
    )
    _LOGGER.info("migration_started", revision=REVISION_HEAD, mode="online")
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_configure_connection)
    except Exception as exc:
        log_setup_failure(redact_secrets(type(exc).__name__))
        raise
    finally:
        await engine.dispose()
    _LOGGER.info("migration_completed", revision=REVISION_HEAD, mode="online")


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
