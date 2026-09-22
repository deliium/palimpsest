"""SQLAlchemy adapters for simulation persistence repository ports.

Public facade. Importing this package does not connect to a database, run
migrations, or configure logging.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from memory.contracts import MemoryService
from memory.models import (
    MemoryRetentionPolicy,
    MemoryScope,
    MemoryScoringPolicy,
)
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

if TYPE_CHECKING:
    from memory.belief_formation import BeliefFormationPolicy
    from persistence.analysis_sqlalchemy import SqlAlchemyAnalysisEvidenceLoader
    from simulation.subjective_state import SubjectiveStateService
    from social.relationships import RelationshipFormationPolicy

__all__ = [
    "PersistenceAdapterError",
    "PersistenceConflictError",
    "PersistenceCorruptionError",
    "PersistenceNotFoundError",
    "create_analysis_evidence_loader",
    "create_experiment_record_repository",
    "create_experiment_repository",
    "create_memory_service",
    "create_pending_finalization_repository",
    "create_run_repository",
    "create_runner_attempt_state_repository",
    "create_snapshot_repository",
    "create_subjective_state_service",
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


def create_experiment_record_repository(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
):
    """Build the append-only experiment definition/assignment/result repository."""
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory",
            operation="create_experiment_record_repository",
        )
    from persistence.experiment_sqlalchemy import (
        create_experiment_record_repository as impl,
    )

    return impl(session_factory)


def create_pending_finalization_repository(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
):
    """Build the append-only pending finalization outbox repository."""
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory",
            operation="create_pending_finalization_repository",
        )
    from persistence.runner_sqlalchemy import (
        create_pending_finalization_repository as impl,
    )

    return impl(session_factory)


def create_runner_attempt_state_repository(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
):
    """Build the append-only runner attempt recovery repository."""
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory",
            operation="create_runner_attempt_state_repository",
        )
    from persistence.runner_sqlalchemy import (
        create_runner_attempt_state_repository as impl,
    )

    return impl(session_factory)


def create_analysis_evidence_loader(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> SqlAlchemyAnalysisEvidenceLoader:
    """Build a read-only experiment analysis evidence loader (SELECT only)."""
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory", operation="create_analysis_evidence_loader"
        )
    from persistence.analysis_sqlalchemy import (
        create_analysis_evidence_loader as impl,
    )

    return impl(session_factory)


def create_memory_service(
    *,
    scope: MemoryScope,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    scoring_policy: MemoryScoringPolicy,
    retention_policy: MemoryRetentionPolicy | None = None,
) -> MemoryService:
    """Build an owner-scoped durable ``MemoryService`` (no unscoped admin API)."""
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory", operation="create_memory_service"
        )
    from persistence.memory_sqlalchemy import create_sqlalchemy_memory_service as impl

    return impl(
        scope=scope,
        session_factory=session_factory,
        scoring_policy=scoring_policy,
        retention_policy=retention_policy,
    )


def create_subjective_state_service(
    *,
    scope: MemoryScope,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    memory_service: MemoryService,
    belief_policy: BeliefFormationPolicy | None = None,
    relationship_policy: RelationshipFormationPolicy | None = None,
) -> SubjectiveStateService:
    """Build an owner-scoped durable ``SubjectiveStateService``."""
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory", operation="create_subjective_state_service"
        )
    from persistence.memory_sqlalchemy import SqlAlchemyMemoryService
    from persistence.subjective_sqlalchemy import (
        create_sqlalchemy_subjective_state_service as impl,
    )

    if type(memory_service) is not SqlAlchemyMemoryService:
        raise PersistenceAdapterError(
            "invalid_memory_service", operation="create_subjective_state_service"
        )
    return impl(
        scope=scope,
        session_factory=session_factory,
        memory_service=memory_service,
        belief_policy=belief_policy,
        relationship_policy=relationship_policy,
    )
