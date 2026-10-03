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
    "create_branch_lineage_repository",
    "create_cognition_trace_repository",
    "create_debugger_event_lookup",
    "create_debugger_lineage_ports",
    "create_experiment_record_repository",
    "create_experiment_repository",
    "create_inspection_evidence_loader",
    "create_memory_service",
    "create_metric_document_repository",
    "create_metric_set_repository",
    "create_objective_evidence_loader",
    "create_pending_finalization_repository",
    "create_run_control_repository",
    "create_run_repository",
    "create_runner_attempt_state_repository",
    "create_scientific_evidence_repository",
    "create_snapshot_repository",
    "create_stream_repository",
    "create_subjective_evidence_loader",
    "create_subjective_state_service",
    "create_tick_journal_repository",
    "create_truth_spec_repository",
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


def create_run_control_repository(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
):
    """Build the durable run-control lifecycle/lease repository."""
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory",
            operation="create_run_control_repository",
        )
    from persistence.run_control_sqlalchemy import (
        create_run_control_repository as impl,
    )

    return impl(session_factory)


def create_scientific_evidence_repository(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
):
    """Build the append-only scientific evidence repository."""
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory",
            operation="create_scientific_evidence_repository",
        )
    from persistence.scientific_evidence_sqlalchemy import (
        create_scientific_evidence_repository as impl,
    )

    return impl(session_factory)


def create_stream_repository(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
):
    """Build the unified durable stream/outbox repository."""
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory",
            operation="create_stream_repository",
        )
    from persistence.scientific_evidence_sqlalchemy import (
        create_stream_repository as impl,
    )

    return impl(session_factory)


def create_branch_lineage_repository(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
):
    """Build the control-plane research branch lineage repository."""
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory",
            operation="create_branch_lineage_repository",
        )
    from persistence.branch_lineage_sqlalchemy import (
        create_branch_lineage_repository as impl,
    )

    return impl(session_factory)


def create_cognition_trace_repository(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
):
    """Build the append-only cognition execution trace repository."""
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory",
            operation="create_cognition_trace_repository",
        )
    from persistence.cognition_trace_sqlalchemy import (
        create_cognition_trace_repository as impl,
    )

    return impl(session_factory)


def create_debugger_event_lookup(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
):
    """Build indexed debugger event identity lookup (no Alembic bump)."""
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory",
            operation="create_debugger_event_lookup",
        )
    from persistence.debugger_sqlalchemy import create_debugger_event_lookup as impl

    return impl(session_factory)


def create_debugger_lineage_ports(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    *,
    checkpoint_lookup=None,
):
    """Build debugger lineage enrichment ports keyed by closed kind."""
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory",
            operation="create_debugger_lineage_ports",
        )
    from persistence.debugger_sqlalchemy import create_debugger_lineage_ports as impl

    return impl(session_factory, checkpoint_lookup=checkpoint_lookup)


def create_truth_spec_repository(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
):
    """Build the append-only claim truth-spec repository."""
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory",
            operation="create_truth_spec_repository",
        )
    from persistence.metric_sqlalchemy import create_truth_spec_repository as impl

    return impl(session_factory)


def create_metric_set_repository(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
):
    """Build the metric-set lifecycle repository."""
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory",
            operation="create_metric_set_repository",
        )
    from persistence.metric_sqlalchemy import create_metric_set_repository as impl

    return impl(session_factory)


def create_metric_document_repository(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
):
    """Build the append-only metric document repository."""
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory",
            operation="create_metric_document_repository",
        )
    from persistence.metric_sqlalchemy import (
        create_metric_document_repository as impl,
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


def create_objective_evidence_loader(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
):
    """Build a run-scoped objective inspection event loader."""
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory", operation="create_objective_evidence_loader"
        )
    from persistence.inspection_sqlalchemy import (
        create_objective_evidence_loader as impl,
    )

    return impl(session_factory)


def create_subjective_evidence_loader(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
):
    """Build a run/owner-scoped subjective inspection loader (debug surface)."""
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory", operation="create_subjective_evidence_loader"
        )
    from persistence.inspection_sqlalchemy import (
        create_subjective_evidence_loader as impl,
    )

    return impl(session_factory)


def create_inspection_evidence_loader(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
):
    """Build the combined objective/subjective inspection loader facade."""
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory", operation="create_inspection_evidence_loader"
        )
    from persistence.inspection_sqlalchemy import (
        create_inspection_evidence_loader as impl,
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
