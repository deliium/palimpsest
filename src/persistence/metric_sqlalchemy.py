"""SQLAlchemy adapters for claim truth specs and metric-set documents.

Implements experiments.persistence metric/truth ports. Never imports analysis.
Never logs truth specs, metric bodies, SQL, or DSNs.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from experiments.persistence import (
    EvidenceAvailability,
    MetricDocumentRecord,
    MetricSetLifecycle,
    MetricSetRecord,
    TruthSpecRecord,
)
from infrastructure.database import session_scope
from infrastructure.logging import get_logger
from persistence.errors import (
    PersistenceAdapterError,
    PersistenceConflictError,
    PersistenceNotFoundError,
)
from persistence.orm import (
    ClaimTruthSpecOrm,
    MetricDocumentOrm,
    MetricSetOrm,
)
from simulation.evidence import OpaqueCanonicalEnvelope

_LOGGER = get_logger("persistence.metric_sqlalchemy")

__all__ = [
    "SqlAlchemyMetricDocumentRepository",
    "SqlAlchemyMetricSetRepository",
    "SqlAlchemyTruthSpecRepository",
    "create_metric_document_repository",
    "create_metric_set_repository",
    "create_truth_spec_repository",
]

_ALLOWED_METRIC_TRANSITIONS: dict[MetricSetLifecycle, frozenset[MetricSetLifecycle]] = {
    MetricSetLifecycle.PENDING: frozenset(
        {
            MetricSetLifecycle.RUNNING,
            MetricSetLifecycle.FAILED,
        }
    ),
    MetricSetLifecycle.RUNNING: frozenset(
        {
            MetricSetLifecycle.COMPLETE,
            MetricSetLifecycle.PARTIAL,
            MetricSetLifecycle.FAILED,
        }
    ),
    MetricSetLifecycle.PARTIAL: frozenset(
        {
            MetricSetLifecycle.COMPLETE,
            MetricSetLifecycle.FAILED,
            MetricSetLifecycle.RUNNING,
        }
    ),
    MetricSetLifecycle.COMPLETE: frozenset(),
    MetricSetLifecycle.FAILED: frozenset(),
}


def create_truth_spec_repository(
    session_factory: async_sessionmaker[AsyncSession],
) -> SqlAlchemyTruthSpecRepository:
    return SqlAlchemyTruthSpecRepository(session_factory)


def create_metric_set_repository(
    session_factory: async_sessionmaker[AsyncSession],
) -> SqlAlchemyMetricSetRepository:
    return SqlAlchemyMetricSetRepository(session_factory)


def create_metric_document_repository(
    session_factory: async_sessionmaker[AsyncSession],
) -> SqlAlchemyMetricDocumentRepository:
    return SqlAlchemyMetricDocumentRepository(session_factory)


class SqlAlchemyTruthSpecRepository:
    """Append-only opaque claim truth specifications."""

    __slots__ = ("_session_factory",)

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def append_truth_spec(self, record: TruthSpecRecord) -> None:
        if type(record) is not TruthSpecRecord:
            raise TypeError("append_truth_spec requires TruthSpecRecord")
        fields = {
            "operation": "append_truth_spec",
            "run_id": record.run_id,
            "revision_id": record.claim_id,
            "availability": record.availability.value,
        }
        if record.envelope is not None:
            fields["hash_prefix"] = record.envelope.content_hash[:12]
            fields["version"] = record.envelope.schema_version
        _LOGGER.debug("truth_spec_append_started", **fields)
        try:
            async with session_scope(self._session_factory) as session:
                existing = await session.get(
                    ClaimTruthSpecOrm, (record.run_id, record.claim_id)
                )
                if existing is not None:
                    if _truth_matches(existing, record):
                        _LOGGER.warning("truth_spec_identical_retry", **fields)
                        return
                    _LOGGER.error(
                        "truth_spec_divergent_conflict",
                        **fields,
                        reason_code="truth_spec_conflict",
                    )
                    raise PersistenceConflictError(
                        "truth_spec_conflict", operation="append_truth_spec"
                    )
                session.add(_truth_from_record(record))
                await session.commit()
        except PersistenceAdapterError:
            raise
        except IntegrityError as exc:
            _LOGGER.error(
                "truth_spec_integrity_conflict",
                **fields,
                reason_code="integrity_conflict",
            )
            raise PersistenceConflictError(
                "integrity_conflict", operation="append_truth_spec"
            ) from exc
        _LOGGER.info("truth_spec_committed", **fields)

    async def get_truth_spec(
        self, *, run_id: str, claim_id: str
    ) -> TruthSpecRecord | None:
        async with session_scope(self._session_factory) as session:
            row = await session.get(ClaimTruthSpecOrm, (run_id, claim_id))
            if row is None:
                return None
            return _truth_to_record(row)

    async def list_truth_specs(
        self, *, run_id: str
    ) -> tuple[TruthSpecRecord, ...]:
        async with session_scope(self._session_factory) as session:
            stmt = (
                select(ClaimTruthSpecOrm)
                .where(ClaimTruthSpecOrm.run_id == run_id)
                .order_by(ClaimTruthSpecOrm.created_ordinal)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return tuple(_truth_to_record(row) for row in rows)


class SqlAlchemyMetricSetRepository:
    """Mutable metric-set lifecycle with optimistic versioning."""

    __slots__ = ("_session_factory",)

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def upsert_metric_set(self, record: MetricSetRecord) -> MetricSetRecord:
        if type(record) is not MetricSetRecord:
            raise TypeError("upsert_metric_set requires MetricSetRecord")
        fields = {
            "operation": "upsert_metric_set",
            "run_id": record.run_id,
            "revision_id": record.metric_set_id,
            "lifecycle_code": record.lifecycle_state.value,
            "hash_prefix": record.evidence_manifest_hash[:12],
            "version": record.lifecycle_version,
        }
        _LOGGER.debug("metric_set_upsert_started", **fields)
        try:
            async with session_scope(self._session_factory) as session:
                existing = await session.get(
                    MetricSetOrm, (record.run_id, record.metric_set_id)
                )
                if existing is not None:
                    if _metric_set_matches(existing, record):
                        _LOGGER.debug("metric_set_upsert_idempotent", **fields)
                        return _metric_set_to_record(existing)
                    raise PersistenceConflictError(
                        "metric_set_conflict", operation="upsert_metric_set"
                    )
                session.add(
                    MetricSetOrm(
                        run_id=record.run_id,
                        metric_set_id=record.metric_set_id,
                        lifecycle_state=record.lifecycle_state.value,
                        evidence_manifest_hash=record.evidence_manifest_hash,
                        lifecycle_version=record.lifecycle_version,
                    )
                )
                await session.commit()
        except PersistenceAdapterError:
            raise
        except IntegrityError as exc:
            _LOGGER.error(
                "metric_set_integrity_conflict",
                **fields,
                reason_code="integrity_conflict",
            )
            raise PersistenceConflictError(
                "integrity_conflict", operation="upsert_metric_set"
            ) from exc
        _LOGGER.info("metric_set_upserted", **fields)
        return record

    async def get_metric_set(
        self, *, run_id: str, metric_set_id: str
    ) -> MetricSetRecord | None:
        async with session_scope(self._session_factory) as session:
            row = await session.get(MetricSetOrm, (run_id, metric_set_id))
            if row is None:
                return None
            return _metric_set_to_record(row)

    async def transition_metric_set(
        self,
        *,
        run_id: str,
        metric_set_id: str,
        expected_version: int,
        to_state: MetricSetLifecycle,
    ) -> MetricSetRecord:
        if type(to_state) is not MetricSetLifecycle:
            raise TypeError("to_state must be MetricSetLifecycle")
        fields = {
            "operation": "transition_metric_set",
            "run_id": run_id,
            "revision_id": metric_set_id,
            "lifecycle_code": to_state.value,
            "version": expected_version,
        }
        _LOGGER.debug("metric_set_transition_started", **fields)
        try:
            async with session_scope(self._session_factory) as session:
                row = await session.get(MetricSetOrm, (run_id, metric_set_id))
                if row is None:
                    raise PersistenceNotFoundError(
                        "metric_set_missing", operation="transition_metric_set"
                    )
                if row.lifecycle_version != expected_version:
                    raise PersistenceConflictError(
                        "version_conflict", operation="transition_metric_set"
                    )
                current = MetricSetLifecycle(row.lifecycle_state)
                if current == to_state:
                    return _metric_set_to_record(row)
                allowed = _ALLOWED_METRIC_TRANSITIONS.get(current, frozenset())
                if to_state not in allowed:
                    _LOGGER.error(
                        "metric_set_illegal_transition",
                        **fields,
                        reason_code="illegal_metric_set_transition",
                    )
                    raise PersistenceConflictError(
                        "illegal_metric_set_transition",
                        operation="transition_metric_set",
                    )
                if to_state is MetricSetLifecycle.PARTIAL:
                    _LOGGER.warning("metric_set_partial_state", **fields)
                row.lifecycle_state = to_state.value
                row.lifecycle_version = expected_version + 1
                result = _metric_set_to_record(row)
                await session.commit()
        except PersistenceAdapterError:
            raise
        except IntegrityError as exc:
            _LOGGER.error(
                "metric_set_transition_integrity_conflict",
                **fields,
                reason_code="integrity_conflict",
            )
            raise PersistenceConflictError(
                "integrity_conflict", operation="transition_metric_set"
            ) from exc
        _LOGGER.info(
            "metric_set_transitioned",
            **fields,
            version=result.lifecycle_version,
        )
        return result


class SqlAlchemyMetricDocumentRepository:
    """Append-only immutable metric documents."""

    __slots__ = ("_session_factory",)

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def append_metric_document(self, record: MetricDocumentRecord) -> None:
        if type(record) is not MetricDocumentRecord:
            raise TypeError("append_metric_document requires MetricDocumentRecord")
        fields = {
            "operation": "append_metric_document",
            "run_id": record.run_id,
            "revision_id": f"{record.metric_set_id}:{record.metric_family}",
            "hash_prefix": record.envelope.content_hash[:12],
            "version": record.envelope.schema_version,
        }
        _LOGGER.debug("metric_document_append_started", **fields)
        try:
            async with session_scope(self._session_factory) as session:
                key = (record.run_id, record.metric_set_id, record.metric_family)
                existing = await session.get(MetricDocumentOrm, key)
                if existing is not None:
                    if _metric_document_matches(existing, record):
                        _LOGGER.warning(
                            "metric_document_identical_retry", **fields
                        )
                        return
                    _LOGGER.error(
                        "metric_document_divergent_conflict",
                        **fields,
                        reason_code="metric_document_conflict",
                    )
                    raise PersistenceConflictError(
                        "metric_document_conflict",
                        operation="append_metric_document",
                    )
                metric_set = await session.get(
                    MetricSetOrm, (record.run_id, record.metric_set_id)
                )
                if metric_set is None:
                    raise PersistenceConflictError(
                        "metric_set_missing", operation="append_metric_document"
                    )
                if metric_set.evidence_manifest_hash != record.evidence_manifest_hash:
                    raise PersistenceConflictError(
                        "evidence_revision_mismatch",
                        operation="append_metric_document",
                    )
                session.add(
                    MetricDocumentOrm(
                        run_id=record.run_id,
                        metric_set_id=record.metric_set_id,
                        metric_family=record.metric_family,
                        evidence_manifest_hash=record.evidence_manifest_hash,
                        schema_version=record.envelope.schema_version,
                        content_hash=record.envelope.content_hash,
                        payload=record.envelope.payload,
                    )
                )
                await session.commit()
        except PersistenceAdapterError:
            raise
        except IntegrityError as exc:
            _LOGGER.error(
                "metric_document_integrity_conflict",
                **fields,
                reason_code="integrity_conflict",
            )
            raise PersistenceConflictError(
                "integrity_conflict", operation="append_metric_document"
            ) from exc
        _LOGGER.info("metric_document_committed", **fields)

    async def get_metric_document(
        self, *, run_id: str, metric_set_id: str, metric_family: str
    ) -> MetricDocumentRecord | None:
        async with session_scope(self._session_factory) as session:
            row = await session.get(
                MetricDocumentOrm, (run_id, metric_set_id, metric_family)
            )
            if row is None:
                return None
            return _metric_document_to_record(row)

    async def list_metric_documents(
        self, *, run_id: str, metric_set_id: str | None = None
    ) -> tuple[MetricDocumentRecord, ...]:
        async with session_scope(self._session_factory) as session:
            stmt = select(MetricDocumentOrm).where(
                MetricDocumentOrm.run_id == run_id
            )
            if metric_set_id is not None:
                stmt = stmt.where(MetricDocumentOrm.metric_set_id == metric_set_id)
            stmt = stmt.order_by(
                MetricDocumentOrm.metric_set_id,
                MetricDocumentOrm.metric_family,
            )
            rows = (await session.execute(stmt)).scalars().all()
            return tuple(_metric_document_to_record(row) for row in rows)


def _truth_from_record(record: TruthSpecRecord) -> ClaimTruthSpecOrm:
    if record.availability is EvidenceAvailability.UNAVAILABLE:
        return ClaimTruthSpecOrm(
            run_id=record.run_id,
            claim_id=record.claim_id,
            availability=record.availability.value,
            schema_version=None,
            content_hash=None,
            payload=None,
        )
    assert record.envelope is not None
    return ClaimTruthSpecOrm(
        run_id=record.run_id,
        claim_id=record.claim_id,
        availability=record.availability.value,
        schema_version=record.envelope.schema_version,
        content_hash=record.envelope.content_hash,
        payload=record.envelope.payload,
    )


def _truth_to_record(row: ClaimTruthSpecOrm) -> TruthSpecRecord:
    availability = EvidenceAvailability(row.availability)
    if availability is EvidenceAvailability.UNAVAILABLE:
        return TruthSpecRecord(
            run_id=row.run_id,
            claim_id=row.claim_id,
            availability=availability,
            envelope=None,
        )
    assert row.schema_version is not None
    assert row.content_hash is not None
    assert row.payload is not None
    return TruthSpecRecord(
        run_id=row.run_id,
        claim_id=row.claim_id,
        availability=availability,
        envelope=OpaqueCanonicalEnvelope(
            schema_version=row.schema_version,
            content_hash=row.content_hash,
            payload=bytes(row.payload),
        ),
    )


def _truth_matches(row: ClaimTruthSpecOrm, record: TruthSpecRecord) -> bool:
    if row.availability != record.availability.value:
        return False
    if record.availability is EvidenceAvailability.UNAVAILABLE:
        return (
            row.schema_version is None
            and row.content_hash is None
            and row.payload is None
        )
    assert record.envelope is not None
    return (
        row.schema_version == record.envelope.schema_version
        and row.content_hash == record.envelope.content_hash
        and bytes(row.payload or b"") == record.envelope.payload
    )


def _metric_set_to_record(row: MetricSetOrm) -> MetricSetRecord:
    return MetricSetRecord(
        run_id=row.run_id,
        metric_set_id=row.metric_set_id,
        lifecycle_state=MetricSetLifecycle(row.lifecycle_state),
        evidence_manifest_hash=row.evidence_manifest_hash,
        lifecycle_version=row.lifecycle_version,
    )


def _metric_set_matches(row: MetricSetOrm, record: MetricSetRecord) -> bool:
    return (
        row.lifecycle_state == record.lifecycle_state.value
        and row.evidence_manifest_hash == record.evidence_manifest_hash
        and row.lifecycle_version == record.lifecycle_version
    )


def _metric_document_to_record(row: MetricDocumentOrm) -> MetricDocumentRecord:
    return MetricDocumentRecord(
        run_id=row.run_id,
        metric_set_id=row.metric_set_id,
        metric_family=row.metric_family,
        evidence_manifest_hash=row.evidence_manifest_hash,
        envelope=OpaqueCanonicalEnvelope(
            schema_version=row.schema_version,
            content_hash=row.content_hash,
            payload=bytes(row.payload),
        ),
    )


def _metric_document_matches(
    row: MetricDocumentOrm, record: MetricDocumentRecord
) -> bool:
    return (
        row.evidence_manifest_hash == record.evidence_manifest_hash
        and row.schema_version == record.envelope.schema_version
        and row.content_hash == record.envelope.content_hash
        and bytes(row.payload) == record.envelope.payload
    )
