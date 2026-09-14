"""Async SQLAlchemy engine and session lifecycle.

Engine construction does not connect. Request sessions never auto-commit.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Protocol, TypedDict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from infrastructure.logging import get_logger
from infrastructure.settings import Settings, redact_secrets

_LOGGER = get_logger("infrastructure.database")
READINESS_SQL = text("SELECT 1")


class SessionLike(Protocol):
    async def rollback(self) -> None: ...

    async def close(self) -> None: ...


class DisposableEngine(Protocol):
    async def dispose(self) -> None: ...


class EngineKwargs(TypedDict):
    pool_size: int
    max_overflow: int
    pool_timeout: float
    pool_pre_ping: bool
    hide_parameters: bool


@dataclass(frozen=True, slots=True)
class DatabaseResources:
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]


def engine_kwargs_from_settings(settings: Settings) -> EngineKwargs:
    """Pool bounds used at engine construction. Does not open a connection."""
    return {
        "pool_size": settings.pool_size,
        "max_overflow": settings.max_overflow,
        "pool_timeout": settings.pool_timeout_seconds,
        "pool_pre_ping": True,
        "hide_parameters": True,
    }


def create_engine(settings: Settings) -> AsyncEngine:
    """Build an async engine without connecting."""
    engine = create_async_engine(
        settings.database_dsn(),
        **engine_kwargs_from_settings(settings),
    )
    _LOGGER.debug(
        "engine_created",
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_pre_ping=True,
    )
    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )


def create_database_resources(settings: Settings) -> DatabaseResources:
    engine = create_engine(settings)
    return DatabaseResources(
        engine=engine,
        session_factory=create_session_factory(engine),
    )


@asynccontextmanager
async def session_scope[TSession: SessionLike](
    session_factory: Callable[[], TSession],
) -> AsyncIterator[TSession]:
    """Yield a session, close on success, roll back and close on failure.

    Callers own commits. This helper never commits application work.
    """
    session = session_factory()
    _LOGGER.debug("session_opened")
    try:
        yield session
        _LOGGER.debug("session_closed")
    except Exception as exc:
        _LOGGER.error("transaction_failed", error=type(exc).__name__)
        await session.rollback()
        raise
    finally:
        await session.close()


async def check_readiness(engine: AsyncEngine) -> None:
    """Run ``SELECT 1``. Does not run migrations or create tables."""
    _LOGGER.debug("readiness_check_started")
    try:
        async with engine.connect() as connection:
            await connection.execute(READINESS_SQL)
    except Exception as exc:
        _LOGGER.warning(
            "readiness_check_failed",
            error=type(exc).__name__,
            detail=redact_secrets(type(exc).__name__),
        )
        raise
    _LOGGER.info("database_ready")


async def dispose_engine(engine: DisposableEngine) -> None:
    _LOGGER.debug("engine_disposing")
    await engine.dispose()
    _LOGGER.debug("engine_disposed")
