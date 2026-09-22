"""SQLAlchemy adapter for experiment definition/assignment/result records.

Implements ``experiments.persistence.ExperimentRecordRepository``. Append-only:
identical re-writes succeed; divergent primary-key reuse conflicts.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from experiments.persistence import (
    ExperimentAssignmentRecord,
    ExperimentDefinitionRecord,
    ExperimentResultRecord,
)
from infrastructure.database import session_scope
from infrastructure.logging import get_logger
from persistence.errors import (
    PersistenceAdapterError,
    PersistenceConflictError,
)
from persistence.orm import (
    ExperimentAssignmentOrm,
    ExperimentDefinitionOrm,
    ExperimentResultOrm,
)

_LOGGER = get_logger("persistence.experiment_sqlalchemy")

__all__ = [
    "SqlAlchemyExperimentRecordRepository",
    "create_experiment_record_repository",
]


def create_experiment_record_repository(
    session_factory: async_sessionmaker[AsyncSession],
) -> SqlAlchemyExperimentRecordRepository:
    return SqlAlchemyExperimentRecordRepository(session_factory)


class SqlAlchemyExperimentRecordRepository:
    """Append-only PostgreSQL experiment record repository."""

    __slots__ = ("_session_factory",)

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def append_definition(self, record: ExperimentDefinitionRecord) -> None:
        if type(record) is not ExperimentDefinitionRecord:
            raise TypeError("append_definition requires ExperimentDefinitionRecord")
        fields = {
            "experiment_id": record.experiment_id,
            "payload_hash_prefix": record.payload_hash[:12],
        }
        _LOGGER.debug("experiment_definition_append_started", **fields)
        try:
            async with session_scope(self._session_factory) as session:
                existing = await session.get(
                    ExperimentDefinitionOrm, record.experiment_id
                )
                if existing is not None:
                    if _definition_matches(existing, record):
                        _LOGGER.warning(
                            "experiment_definition_idempotent", **fields
                        )
                        return
                    raise PersistenceConflictError(
                        "definition_conflict", operation="append_definition"
                    )
                session.add(
                    ExperimentDefinitionOrm(
                        experiment_id=record.experiment_id,
                        schema_version=record.schema_version,
                        payload_hash=record.payload_hash,
                        definition_fingerprint=record.definition_fingerprint,
                    )
                )
                await session.commit()
        except PersistenceAdapterError:
            raise
        except IntegrityError as exc:
            _LOGGER.error("experiment_definition_conflict", **fields)
            raise PersistenceConflictError(
                "integrity_conflict", operation="append_definition"
            ) from exc
        _LOGGER.info("experiment_definition_appended", **fields)

    async def append_assignment(self, record: ExperimentAssignmentRecord) -> None:
        if type(record) is not ExperimentAssignmentRecord:
            raise TypeError("append_assignment requires ExperimentAssignmentRecord")
        fields = {
            "experiment_id": record.experiment_id,
            "condition_id": record.condition_id,
            "seed_ordinal": record.seed_ordinal,
            "replicate_index": record.replicate_index,
            "run_id": record.run_id,
        }
        _LOGGER.debug("experiment_assignment_append_started", **fields)
        key = (
            record.experiment_id,
            record.condition_id,
            record.seed_ordinal,
            record.replicate_index,
        )
        try:
            async with session_scope(self._session_factory) as session:
                existing = await session.get(ExperimentAssignmentOrm, key)
                if existing is not None:
                    if _assignment_matches(existing, record):
                        _LOGGER.warning(
                            "experiment_assignment_idempotent", **fields
                        )
                        return
                    raise PersistenceConflictError(
                        "assignment_conflict", operation="append_assignment"
                    )
                definition = await session.get(
                    ExperimentDefinitionOrm, record.experiment_id
                )
                if definition is None:
                    raise PersistenceConflictError(
                        "definition_missing", operation="append_assignment"
                    )
                session.add(
                    ExperimentAssignmentOrm(
                        experiment_id=record.experiment_id,
                        condition_id=record.condition_id,
                        seed_ordinal=record.seed_ordinal,
                        replicate_index=record.replicate_index,
                        run_id=record.run_id,
                        seed=record.seed,
                        config_fingerprint=record.config_fingerprint,
                    )
                )
                await session.commit()
        except PersistenceAdapterError:
            raise
        except IntegrityError as exc:
            _LOGGER.error("experiment_assignment_conflict", **fields)
            raise PersistenceConflictError(
                "integrity_conflict", operation="append_assignment"
            ) from exc
        _LOGGER.info("experiment_assignment_appended", **fields)

    async def append_result(self, record: ExperimentResultRecord) -> None:
        if type(record) is not ExperimentResultRecord:
            raise TypeError("append_result requires ExperimentResultRecord")
        fields = {
            "run_id": record.run_id,
            "experiment_id": record.experiment_id,
            "condition_id": record.condition_id,
            "ticks_committed": record.ticks_committed,
            "payload_hash_prefix": record.payload_hash[:12],
        }
        _LOGGER.debug("experiment_result_append_started", **fields)
        try:
            async with session_scope(self._session_factory) as session:
                existing = await session.get(ExperimentResultOrm, record.run_id)
                if existing is not None:
                    if _result_matches(existing, record):
                        _LOGGER.warning("experiment_result_idempotent", **fields)
                        return
                    raise PersistenceConflictError(
                        "result_conflict", operation="append_result"
                    )
                assignment = await session.execute(
                    select(ExperimentAssignmentOrm).where(
                        ExperimentAssignmentOrm.run_id == record.run_id
                    )
                )
                if assignment.scalar_one_or_none() is None:
                    raise PersistenceConflictError(
                        "assignment_missing", operation="append_result"
                    )
                session.add(
                    ExperimentResultOrm(
                        run_id=record.run_id,
                        experiment_id=record.experiment_id,
                        condition_id=record.condition_id,
                        payload_hash=record.payload_hash,
                        stop_reason=record.stop_reason,
                        ticks_committed=record.ticks_committed,
                    )
                )
                await session.commit()
        except PersistenceAdapterError:
            raise
        except IntegrityError as exc:
            _LOGGER.error("experiment_result_conflict", **fields)
            raise PersistenceConflictError(
                "integrity_conflict", operation="append_result"
            ) from exc
        _LOGGER.info("experiment_result_appended", **fields)

    async def get_definition(
        self, experiment_id: str
    ) -> ExperimentDefinitionRecord | None:
        async with session_scope(self._session_factory) as session:
            row = await session.get(ExperimentDefinitionOrm, experiment_id)
            if row is None:
                return None
            return ExperimentDefinitionRecord(
                experiment_id=row.experiment_id,
                schema_version=row.schema_version,
                payload_hash=row.payload_hash,
                definition_fingerprint=row.definition_fingerprint,
            )

    async def list_assignments(
        self, experiment_id: str
    ) -> tuple[ExperimentAssignmentRecord, ...]:
        async with session_scope(self._session_factory) as session:
            stmt = (
                select(ExperimentAssignmentOrm)
                .where(ExperimentAssignmentOrm.experiment_id == experiment_id)
                .order_by(
                    ExperimentAssignmentOrm.condition_id,
                    ExperimentAssignmentOrm.seed_ordinal,
                    ExperimentAssignmentOrm.replicate_index,
                )
            )
            rows = (await session.execute(stmt)).scalars().all()
            return tuple(
                ExperimentAssignmentRecord(
                    experiment_id=row.experiment_id,
                    condition_id=row.condition_id,
                    seed_ordinal=row.seed_ordinal,
                    replicate_index=row.replicate_index,
                    run_id=row.run_id,
                    seed=row.seed,
                    config_fingerprint=row.config_fingerprint,
                )
                for row in rows
            )


def _definition_matches(
    row: ExperimentDefinitionOrm, record: ExperimentDefinitionRecord
) -> bool:
    return (
        row.schema_version == record.schema_version
        and row.payload_hash == record.payload_hash
        and row.definition_fingerprint == record.definition_fingerprint
    )


def _assignment_matches(
    row: ExperimentAssignmentOrm, record: ExperimentAssignmentRecord
) -> bool:
    return (
        row.run_id == record.run_id
        and row.seed == record.seed
        and row.config_fingerprint == record.config_fingerprint
    )


def _result_matches(
    row: ExperimentResultOrm, record: ExperimentResultRecord
) -> bool:
    return (
        row.experiment_id == record.experiment_id
        and row.condition_id == record.condition_id
        and row.payload_hash == record.payload_hash
        and row.stop_reason == record.stop_reason
        and row.ticks_committed == record.ticks_committed
    )
