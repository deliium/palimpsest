"""SQLAlchemy adapters for simulation persistence repository ports.

Public facade. Importing this package does not connect to a database, run
migrations, or configure logging.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from persistence.errors import (
    PersistenceAdapterError,
    PersistenceConflictError,
    PersistenceCorruptionError,
    PersistenceNotFoundError,
)
from simulation.persistence import (
    ExperimentRepository,
    SimulationRunRepository,
    SnapshotRepository,
    TickJournalRepository,
)

__all__ = [
    "PersistenceAdapterError",
    "PersistenceConflictError",
    "PersistenceCorruptionError",
    "PersistenceNotFoundError",
    "create_experiment_repository",
    "create_run_repository",
    "create_snapshot_repository",
    "create_tick_journal_repository",
]


def create_run_repository(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> SimulationRunRepository:
    """Build the async simulation-run repository."""
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory", operation="create_run_repository"
        )
    from persistence.sqlalchemy import create_run_repository as impl

    return impl(session_factory)


def create_tick_journal_repository(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> TickJournalRepository:
    """Build the async tick/event journal repository."""
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory", operation="create_tick_journal_repository"
        )
    from persistence.sqlalchemy import create_tick_journal_repository as impl

    return impl(session_factory)


def create_snapshot_repository(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> SnapshotRepository:
    """Build the async snapshot repository."""
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory", operation="create_snapshot_repository"
        )
    from persistence.sqlalchemy import create_snapshot_repository as impl

    return impl(session_factory)


def create_experiment_repository(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> ExperimentRepository:
    """Build the async experiment repository."""
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory", operation="create_experiment_repository"
        )
    from persistence.sqlalchemy import create_experiment_repository as impl

    return impl(session_factory)
