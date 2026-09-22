"""SQLAlchemy adapters for scientific evidence and the unified stream.

Implements ``ScientificEvidenceRepository`` and ``StreamRepository``.
Never logs evidence payloads, resolution commands, truth specs, stream bodies,
SQL, or DSNs.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from infrastructure.database import session_scope
from infrastructure.logging import get_logger
from persistence.errors import (
    PersistenceAdapterError,
    PersistenceConflictError,
    PersistenceCorruptionError,
)
from persistence.orm import (
    ActionResolutionOrm,
    EvidenceManifestOrm,
    GoalRevisionOrm,
    RunStreamHeadOrm,
    RunStreamRecordOrm,
)
from simulation.evidence import (
    ActionResolutionRecord,
    EvidenceHighWaterMarks,
    EvidenceManifest,
    GoalRevisionRecord,
    OpaqueCanonicalEnvelope,
    build_evidence_manifest,
)
from simulation.models import RunId
from simulation.persistence import FinalizedBoundaryBatch
from simulation.run_control import StreamRecord, StreamRecordDraft, StreamRecordKind

_LOGGER = get_logger("persistence.scientific_evidence_sqlalchemy")

__all__ = [
    "SqlAlchemyScientificEvidenceRepository",
    "SqlAlchemyStreamRepository",
    "create_scientific_evidence_repository",
    "create_stream_repository",
]


def create_scientific_evidence_repository(
    session_factory: async_sessionmaker[AsyncSession],
) -> SqlAlchemyScientificEvidenceRepository:
    return SqlAlchemyScientificEvidenceRepository(session_factory)


def create_stream_repository(
    session_factory: async_sessionmaker[AsyncSession],
) -> SqlAlchemyStreamRepository:
    return SqlAlchemyStreamRepository(session_factory)


class SqlAlchemyScientificEvidenceRepository:
    """PostgreSQL append-only scientific evidence + atomic boundary publish."""

    __slots__ = ("_session_factory",)

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def append_goal_revision(self, record: GoalRevisionRecord) -> None:
        if type(record) is not GoalRevisionRecord:
            raise TypeError("append_goal_revision requires GoalRevisionRecord")
        fields = {
            "operation": "append_goal_revision",
            "run_id": record.run_id,
            "revision_id": f"{record.goal_id}:{record.revision}",
            "version": record.envelope.schema_version,
            "hash_prefix": record.envelope.content_hash[:12],
        }
        _LOGGER.debug("goal_revision_append_started", **fields)
        try:
            async with session_scope(self._session_factory) as session:
                key = (record.run_id, record.goal_id, record.revision)
                existing = await session.get(GoalRevisionOrm, key)
                if existing is not None:
                    if _goal_matches(existing, record):
                        _LOGGER.warning("goal_revision_identical_retry", **fields)
                        return
                    _LOGGER.error(
                        "goal_revision_divergent_conflict",
                        **fields,
                        reason_code="goal_revision_conflict",
                    )
                    raise PersistenceConflictError(
                        "goal_revision_conflict", operation="append_goal_revision"
                    )
                session.add(_goal_from_record(record))
                await session.commit()
        except PersistenceAdapterError:
            raise
        except IntegrityError as exc:
            _LOGGER.error(
                "goal_revision_integrity_conflict",
                **fields,
                reason_code="integrity_conflict",
            )
            raise PersistenceConflictError(
                "integrity_conflict", operation="append_goal_revision"
            ) from exc
        _LOGGER.info("goal_revision_committed", **fields)

    async def append_action_resolution(self, record: ActionResolutionRecord) -> None:
        if type(record) is not ActionResolutionRecord:
            raise TypeError("append_action_resolution requires ActionResolutionRecord")
        fields = {
            "operation": "append_action_resolution",
            "run_id": record.run_id,
            "tick": record.tick,
            "ordinal": record.ordinal,
            "hash_prefix": record.envelope.content_hash[:12],
        }
        _LOGGER.debug("action_resolution_append_started", **fields)
        try:
            async with session_scope(self._session_factory) as session:
                key = (record.run_id, record.tick, record.ordinal)
                existing = await session.get(ActionResolutionOrm, key)
                if existing is not None:
                    if _resolution_matches(existing, record):
                        _LOGGER.warning(
                            "action_resolution_identical_retry", **fields
                        )
                        return
                    _LOGGER.error(
                        "action_resolution_divergent_conflict",
                        **fields,
                        reason_code="action_resolution_conflict",
                    )
                    raise PersistenceConflictError(
                        "action_resolution_conflict",
                        operation="append_action_resolution",
                    )
                session.add(_resolution_from_record(record))
                await session.commit()
        except PersistenceAdapterError:
            raise
        except IntegrityError as exc:
            _LOGGER.error(
                "action_resolution_integrity_conflict",
                **fields,
                reason_code="integrity_conflict",
            )
            raise PersistenceConflictError(
                "integrity_conflict", operation="append_action_resolution"
            ) from exc
        _LOGGER.info("action_resolution_committed", **fields)

    async def append_manifest(self, manifest: EvidenceManifest) -> None:
        if type(manifest) is not EvidenceManifest:
            raise TypeError("append_manifest requires EvidenceManifest")
        fields = {
            "operation": "append_manifest",
            "run_id": manifest.run_id,
            "version": manifest.schema_version,
            "hash_prefix": manifest.manifest_hash[:12],
            "count": sum(manifest.high_water.as_canonical_dict().values()),
        }
        _LOGGER.debug("evidence_manifest_append_started", **fields)
        try:
            async with session_scope(self._session_factory) as session:
                await _append_manifest_in_session(session, manifest, fields=fields)
                await session.commit()
        except PersistenceAdapterError:
            raise
        except IntegrityError as exc:
            _LOGGER.error(
                "evidence_manifest_integrity_conflict",
                **fields,
                reason_code="integrity_conflict",
            )
            raise PersistenceConflictError(
                "integrity_conflict", operation="append_manifest"
            ) from exc
        _LOGGER.info("evidence_manifest_committed", **fields)

    async def get_manifest(
        self, *, run_id: str, manifest_hash: str | None = None
    ) -> EvidenceManifest | None:
        async with session_scope(self._session_factory) as session:
            if manifest_hash is not None:
                row = await session.get(
                    EvidenceManifestOrm, (run_id, manifest_hash)
                )
                if row is None:
                    return None
                return _manifest_from_orm(row)
            stmt = (
                select(EvidenceManifestOrm)
                .where(EvidenceManifestOrm.run_id == run_id)
                .order_by(EvidenceManifestOrm.created_ordinal.desc())
                .limit(1)
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                return None
            return _manifest_from_orm(row)

    async def list_goal_revisions(
        self, *, run_id: str
    ) -> tuple[GoalRevisionRecord, ...]:
        async with session_scope(self._session_factory) as session:
            stmt = (
                select(GoalRevisionOrm)
                .where(GoalRevisionOrm.run_id == run_id)
                .order_by(
                    GoalRevisionOrm.goal_id,
                    GoalRevisionOrm.revision,
                )
            )
            rows = (await session.execute(stmt)).scalars().all()
            return tuple(_goal_to_record(row) for row in rows)

    async def list_action_resolutions(
        self, *, run_id: str, tick: int | None = None
    ) -> tuple[ActionResolutionRecord, ...]:
        async with session_scope(self._session_factory) as session:
            stmt = select(ActionResolutionOrm).where(
                ActionResolutionOrm.run_id == run_id
            )
            if tick is not None:
                stmt = stmt.where(ActionResolutionOrm.tick == tick)
            stmt = stmt.order_by(
                ActionResolutionOrm.tick, ActionResolutionOrm.ordinal
            )
            rows = (await session.execute(stmt)).scalars().all()
            return tuple(_resolution_to_record(row) for row in rows)

    async def publish_finalized_boundary(
        self, batch: FinalizedBoundaryBatch
    ) -> tuple[StreamRecord, ...]:
        if type(batch) is not FinalizedBoundaryBatch:
            raise TypeError(
                "publish_finalized_boundary requires FinalizedBoundaryBatch"
            )
        fields = {
            "operation": "publish_finalized_boundary",
            "run_id": batch.run_id.value,
            "tick": batch.tick,
            "count": (
                len(batch.resolutions)
                + len(batch.goal_revisions)
                + len(batch.stream_drafts)
                + (1 if batch.manifest is not None else 0)
            ),
        }
        _LOGGER.debug("finalized_boundary_publish_started", **fields)
        try:
            async with session_scope(self._session_factory) as session:
                for resolution in batch.resolutions:
                    await _append_resolution_in_session(session, resolution)
                for goal in batch.goal_revisions:
                    await _append_goal_in_session(session, goal)
                if batch.manifest is not None:
                    await _append_manifest_in_session(
                        session,
                        batch.manifest,
                        fields={
                            "operation": "publish_finalized_boundary",
                            "run_id": batch.run_id.value,
                            "hash_prefix": batch.manifest.manifest_hash[:12],
                        },
                    )
                published = await _publish_stream_in_session(
                    session, run_id=batch.run_id, drafts=batch.stream_drafts
                )
                await session.commit()
        except PersistenceAdapterError:
            raise
        except IntegrityError as exc:
            _LOGGER.error(
                "finalized_boundary_integrity_conflict",
                **fields,
                reason_code="integrity_conflict",
            )
            raise PersistenceConflictError(
                "integrity_conflict", operation="publish_finalized_boundary"
            ) from exc
        _LOGGER.info(
            "finalized_boundary_published",
            **fields,
            stream_count=len(published),
        )
        return published


class SqlAlchemyStreamRepository:
    """PostgreSQL unified stream/outbox with monotonic per-run cursors."""

    __slots__ = ("_session_factory",)

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def publish(
        self, *, run_id: RunId, drafts: Sequence[StreamRecordDraft]
    ) -> tuple[StreamRecord, ...]:
        if type(run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        draft_tuple = tuple(drafts)
        fields = {
            "operation": "stream_publish",
            "run_id": run_id.value,
            "count": len(draft_tuple),
        }
        if draft_tuple:
            fields["record_kind"] = draft_tuple[0].kind.value
        _LOGGER.debug("stream_publish_started", **fields)
        try:
            async with session_scope(self._session_factory) as session:
                published = await _publish_stream_in_session(
                    session, run_id=run_id, drafts=draft_tuple
                )
                # Wake-up only — never authoritative for cursor/order.
                if published:
                    await session.execute(
                        text("SELECT pg_notify('palimpsest_stream', :run_id)"),
                        {"run_id": run_id.value},
                    )
                await session.commit()
        except PersistenceAdapterError:
            raise
        except IntegrityError as exc:
            _LOGGER.error(
                "stream_publish_integrity_conflict",
                **fields,
                reason_code="integrity_conflict",
            )
            raise PersistenceConflictError(
                "integrity_conflict", operation="stream_publish"
            ) from exc
        _LOGGER.debug(
            "stream_publish_complete",
            **fields,
            cursor=published[-1].cursor if published else 0,
        )
        return published

    async def read_after(
        self, *, run_id: RunId, after_cursor: int, limit: int
    ) -> tuple[StreamRecord, ...]:
        if type(run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        if after_cursor < 0:
            raise ValueError("after_cursor must be non-negative")
        if limit < 1:
            raise ValueError("limit must be >= 1")
        async with session_scope(self._session_factory) as session:
            stmt = (
                select(RunStreamRecordOrm)
                .where(
                    RunStreamRecordOrm.run_id == run_id.value,
                    RunStreamRecordOrm.cursor_value > after_cursor,
                )
                .order_by(RunStreamRecordOrm.cursor_value)
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            records = tuple(_stream_to_record(row) for row in rows)
        _LOGGER.debug(
            "stream_read_after",
            operation="read_after",
            run_id=run_id.value,
            cursor=after_cursor,
            count=len(records),
            limit=limit,
        )
        return records

    async def high_water(self, *, run_id: RunId) -> int:
        if type(run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        async with session_scope(self._session_factory) as session:
            head = await session.get(RunStreamHeadOrm, run_id.value)
            value = 0 if head is None else head.high_water
        _LOGGER.debug(
            "stream_high_water",
            operation="high_water",
            run_id=run_id.value,
            cursor=value,
        )
        return value


async def _append_manifest_in_session(
    session: AsyncSession,
    manifest: EvidenceManifest,
    *,
    fields: dict[str, object],
) -> None:
    existing = await session.get(
        EvidenceManifestOrm, (manifest.run_id, manifest.manifest_hash)
    )
    if existing is not None:
        if _manifest_matches(existing, manifest):
            _LOGGER.warning("evidence_manifest_identical_retry", **fields)
            return
        _LOGGER.error(
            "evidence_manifest_divergent_conflict",
            **fields,
            reason_code="manifest_conflict",
        )
        raise PersistenceConflictError(
            "manifest_conflict", operation="append_manifest"
        )
    session.add(
        EvidenceManifestOrm(
            run_id=manifest.run_id,
            manifest_hash=manifest.manifest_hash,
            schema_version=manifest.schema_version,
            objective_commit_hash=manifest.objective_commit_hash,
            high_water_json=manifest.high_water.as_canonical_dict(),
        )
    )


async def _append_goal_in_session(
    session: AsyncSession, record: GoalRevisionRecord
) -> None:
    key = (record.run_id, record.goal_id, record.revision)
    existing = await session.get(GoalRevisionOrm, key)
    if existing is not None:
        if _goal_matches(existing, record):
            _LOGGER.warning(
                "goal_revision_identical_retry",
                operation="publish_finalized_boundary",
                run_id=record.run_id,
                revision_id=f"{record.goal_id}:{record.revision}",
                hash_prefix=record.envelope.content_hash[:12],
            )
            return
        raise PersistenceConflictError(
            "goal_revision_conflict", operation="publish_finalized_boundary"
        )
    session.add(_goal_from_record(record))


async def _append_resolution_in_session(
    session: AsyncSession, record: ActionResolutionRecord
) -> None:
    key = (record.run_id, record.tick, record.ordinal)
    existing = await session.get(ActionResolutionOrm, key)
    if existing is not None:
        if _resolution_matches(existing, record):
            _LOGGER.warning(
                "action_resolution_identical_retry",
                operation="publish_finalized_boundary",
                run_id=record.run_id,
                tick=record.tick,
                ordinal=record.ordinal,
                hash_prefix=record.envelope.content_hash[:12],
            )
            return
        raise PersistenceConflictError(
            "action_resolution_conflict", operation="publish_finalized_boundary"
        )
    session.add(_resolution_from_record(record))


async def _publish_stream_in_session(
    session: AsyncSession,
    *,
    run_id: RunId,
    drafts: Sequence[StreamRecordDraft],
) -> tuple[StreamRecord, ...]:
    if not drafts:
        return ()
    head = await session.get(RunStreamHeadOrm, run_id.value, with_for_update=True)
    if head is None:
        head = RunStreamHeadOrm(run_id=run_id.value, high_water=0)
        session.add(head)
        await session.flush()
    published: list[StreamRecord] = []
    cursor = head.high_water
    for draft in drafts:
        if type(draft) is not StreamRecordDraft:
            raise TypeError("drafts must be StreamRecordDraft")
        cursor += 1
        session.add(
            RunStreamRecordOrm(
                run_id=run_id.value,
                cursor_value=cursor,
                record_kind=draft.kind.value,
                schema_version=draft.envelope.schema_version,
                content_hash=draft.envelope.content_hash,
                payload=draft.envelope.payload,
                related_tick=draft.related_tick,
            )
        )
        published.append(
            StreamRecord(
                run_id=run_id,
                cursor=cursor,
                kind=draft.kind,
                envelope=draft.envelope,
                related_tick=draft.related_tick,
            )
        )
        _LOGGER.debug(
            "stream_record_appended",
            operation="stream_publish",
            run_id=run_id.value,
            cursor=cursor,
            record_kind=draft.kind.value,
            hash_prefix=draft.envelope.content_hash[:12],
        )
    head.high_water = cursor
    return tuple(published)


def _goal_from_record(record: GoalRevisionRecord) -> GoalRevisionOrm:
    return GoalRevisionOrm(
        run_id=record.run_id,
        goal_id=record.goal_id,
        revision=record.revision,
        owner_id=record.owner_id,
        tick=record.tick,
        schema_version=record.envelope.schema_version,
        content_hash=record.envelope.content_hash,
        payload=record.envelope.payload,
    )


def _goal_to_record(row: GoalRevisionOrm) -> GoalRevisionRecord:
    return GoalRevisionRecord(
        run_id=row.run_id,
        goal_id=row.goal_id,
        revision=row.revision,
        owner_id=row.owner_id,
        tick=row.tick,
        envelope=OpaqueCanonicalEnvelope(
            schema_version=row.schema_version,
            content_hash=row.content_hash,
            payload=bytes(row.payload),
        ),
    )


def _goal_matches(row: GoalRevisionOrm, record: GoalRevisionRecord) -> bool:
    return (
        row.owner_id == record.owner_id
        and row.tick == record.tick
        and row.schema_version == record.envelope.schema_version
        and row.content_hash == record.envelope.content_hash
        and bytes(row.payload) == record.envelope.payload
    )


def _resolution_from_record(record: ActionResolutionRecord) -> ActionResolutionOrm:
    return ActionResolutionOrm(
        run_id=record.run_id,
        tick=record.tick,
        ordinal=record.ordinal,
        schema_version=record.envelope.schema_version,
        content_hash=record.envelope.content_hash,
        payload=record.envelope.payload,
    )


def _resolution_to_record(row: ActionResolutionOrm) -> ActionResolutionRecord:
    return ActionResolutionRecord(
        run_id=row.run_id,
        tick=row.tick,
        ordinal=row.ordinal,
        envelope=OpaqueCanonicalEnvelope(
            schema_version=row.schema_version,
            content_hash=row.content_hash,
            payload=bytes(row.payload),
        ),
    )


def _resolution_matches(
    row: ActionResolutionOrm, record: ActionResolutionRecord
) -> bool:
    return (
        row.schema_version == record.envelope.schema_version
        and row.content_hash == record.envelope.content_hash
        and bytes(row.payload) == record.envelope.payload
    )


def _require_high_water_int(raw: dict[str, object], key: str) -> int:
    value = raw[key]
    if type(value) is not int or isinstance(value, bool):
        raise TypeError(key)
    if value < 0:
        raise ValueError(key)
    return value


def _manifest_from_orm(row: EvidenceManifestOrm) -> EvidenceManifest:
    high_water_raw = dict(row.high_water_json)
    try:
        high_water = EvidenceHighWaterMarks(
            direct_memories=_require_high_water_int(high_water_raw, "direct_memories"),
            communicated_memories=_require_high_water_int(
                high_water_raw, "communicated_memories"
            ),
            reconstructions=_require_high_water_int(high_water_raw, "reconstructions"),
            beliefs=_require_high_water_int(high_water_raw, "beliefs"),
            relationships=_require_high_water_int(high_water_raw, "relationships"),
            goals=_require_high_water_int(high_water_raw, "goals"),
            resolutions=_require_high_water_int(high_water_raw, "resolutions"),
            truth_specs=_require_high_water_int(high_water_raw, "truth_specs"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PersistenceCorruptionError(
            "manifest_high_water_corrupt", operation="get_manifest"
        ) from exc
    rebuilt = build_evidence_manifest(
        run_id=row.run_id,
        objective_commit_hash=row.objective_commit_hash,
        high_water=high_water,
        schema_version=row.schema_version,
    )
    if rebuilt.manifest_hash != row.manifest_hash:
        raise PersistenceCorruptionError(
            "manifest_hash_corrupt", operation="get_manifest"
        )
    return rebuilt


def _manifest_matches(row: EvidenceManifestOrm, manifest: EvidenceManifest) -> bool:
    return (
        row.schema_version == manifest.schema_version
        and row.objective_commit_hash == manifest.objective_commit_hash
        and dict(row.high_water_json) == manifest.high_water.as_canonical_dict()
    )


def _stream_to_record(row: RunStreamRecordOrm) -> StreamRecord:
    return StreamRecord(
        run_id=RunId(row.run_id),
        cursor=row.cursor_value,
        kind=StreamRecordKind(row.record_kind),
        envelope=OpaqueCanonicalEnvelope(
            schema_version=row.schema_version,
            content_hash=row.content_hash,
            payload=bytes(row.payload),
        ),
        related_tick=row.related_tick,
    )
