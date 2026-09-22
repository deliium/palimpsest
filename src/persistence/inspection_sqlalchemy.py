"""Read-only SQLAlchemy loaders for objective/subjective inspection.

SELECT-only. Run-scoped (experiment membership optional). Keyset pagination
with fail-closed page-size limits. Manifest constraints applied under one
repeatable-read session. Never logs rows, projected state, observations,
events, claims, memories, relationships, SQL, or DSNs.
"""

from __future__ import annotations

import logging
import time
from typing import Final

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from experiments.persistence import PersistedReconstructionRow
from infrastructure.database import session_scope
from memory.models import AgentId, MemorySourceKind
from persistence.errors import PersistenceAdapterError, PersistenceNotFoundError
from persistence.memory_orm import MemoryReconstructionOrm, MemoryTraceOrm
from persistence.orm import SimulationRunOrm, WorldEventOrm
from persistence.readers import (
    event_from_orm,
    keyset_after_tuple,
    next_event_keyset_cursor,
)
from persistence.subjective_orm import DirectedRelationshipOrm, SemanticBeliefOrm
from simulation.evidence import (
    EvidenceManifest,
    clamp_sequence_to_high_water,
    manifest_hash_prefix,
)
from simulation.inspection import (
    DEFAULT_INSPECTION_PAGE_SIZE,
    EventKeysetCursor,
    InspectionAvailability,
    InspectionError,
    InspectionEventPage,
    MemoryKeysetCursor,
    SubjectiveInspectionPage,
    clamp_inspection_page_limit,
    constrain_events_to_manifest,
)
from simulation.models import RunId

__all__ = [
    "SqlAlchemyInspectionEvidenceLoader",
    "SqlAlchemyObjectiveEvidenceLoader",
    "SqlAlchemySubjectiveEvidenceLoader",
    "create_inspection_evidence_loader",
    "create_objective_evidence_loader",
    "create_subjective_evidence_loader",
]

_LOG: Final[logging.Logger] = logging.getLogger("persistence.inspection_sqlalchemy")


class SqlAlchemyObjectiveEvidenceLoader:
    """Run-scoped objective event loader with keyset pagination."""

    __slots__ = ("_session_factory",)

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def load_events_page(
        self,
        *,
        run_id: str,
        after: EventKeysetCursor | None = None,
        limit: int = DEFAULT_INSPECTION_PAGE_SIZE,
        manifest: EvidenceManifest | None = None,
    ) -> InspectionEventPage:
        run_id = RunId(run_id).value
        limit = clamp_inspection_page_limit(limit)
        if after is not None and type(after) is not EventKeysetCursor:
            raise TypeError("after must be EventKeysetCursor or None")
        if manifest is not None:
            if type(manifest) is not EvidenceManifest:
                raise TypeError("manifest must be EvidenceManifest")
            if manifest.run_id != run_id:
                _LOG.error(
                    "objective_loader_manifest_scope_mismatch",
                    extra={
                        "operation": "load_events_page",
                        "reason_code": "manifest_run_scope_mismatch",
                        "run_id": run_id,
                    },
                )
                raise InspectionError("manifest_run_scope_mismatch")
        started = time.perf_counter()
        after_tick, after_sequence = keyset_after_tuple(after)
        _LOG.debug(
            "objective_events_page_start",
            extra={
                "operation": "load_events_page",
                "query_type": "objective_events",
                "run_id": run_id,
                "cursor_tick": after_tick,
                "cursor_sequence": after_sequence,
                "limit": limit,
                "has_manifest": manifest is not None,
            },
        )
        async with session_scope(self._session_factory) as session:
            await _require_run(session, run_id=run_id, operation="load_events_page")
            stmt = (
                select(WorldEventOrm)
                .where(WorldEventOrm.run_id == run_id)
                .where(
                    or_(
                        WorldEventOrm.tick > after_tick,
                        and_(
                            WorldEventOrm.tick == after_tick,
                            WorldEventOrm.sequence > after_sequence,
                        ),
                    )
                )
                .order_by(WorldEventOrm.tick, WorldEventOrm.sequence)
                .limit(limit + 1)
            )
            rows = list((await session.execute(stmt)).scalars().all())
            decoded: list[object] = []
            for row in rows:
                event = event_from_orm(row)
                if type(event).__name__ != "WorldEvent":
                    _LOG.error(
                        "objective_loader_invalid_event",
                        extra={
                            "operation": "load_events_page",
                            "reason_code": "invalid_event",
                            "run_id": run_id,
                        },
                    )
                    raise PersistenceAdapterError(
                        "invalid_event", operation="load_events_page"
                    )
                decoded.append(event)
            if manifest is not None:
                # Full ordered history must be clamped before page slicing for
                # deterministic high-water semantics; page reads after mark.
                all_rows = list(
                    (
                        await session.execute(
                            select(WorldEventOrm)
                            .where(WorldEventOrm.run_id == run_id)
                            .order_by(WorldEventOrm.tick, WorldEventOrm.sequence)
                        )
                    )
                    .scalars()
                    .all()
                )
                all_events = tuple(
                    cast_event
                    for cast_event in (event_from_orm(r) for r in all_rows)
                    if type(cast_event).__name__ == "WorldEvent"
                )
                constrained = constrain_events_to_manifest(
                    all_events, manifest, run_id=run_id
                )
                filtered = tuple(
                    event
                    for event in constrained
                    if (event.tick, event.sequence) > (after_tick, after_sequence)
                )
                page_events = filtered[:limit]
                has_more = len(filtered) > limit
            else:
                has_more = len(decoded) > limit
                page_events = tuple(decoded[:limit])

        next_cursor = next_event_keyset_cursor(page_events) if has_more else None
        page = InspectionEventPage(
            run_id=run_id,
            limit=limit,
            events=page_events,
            next_cursor=next_cursor,
            availability=InspectionAvailability.AVAILABLE,
            manifest_hash=None if manifest is None else manifest.manifest_hash,
        )
        _LOG.debug(
            "objective_events_page_complete",
            extra={
                "operation": "load_events_page",
                "query_type": "objective_events",
                "run_id": run_id,
                "limit": limit,
                "count": len(page_events),
                "has_more": has_more,
                "availability": page.availability.value,
                "manifest_hash_prefix": (
                    None if manifest is None else manifest_hash_prefix(manifest)
                ),
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            },
        )
        return page


class SqlAlchemySubjectiveEvidenceLoader:
    """Run/owner-scoped subjective evidence loader (debug surface)."""

    __slots__ = ("_session_factory",)

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def load_traces_page(
        self,
        *,
        run_id: str,
        owner_id: str,
        after: MemoryKeysetCursor | None = None,
        limit: int = DEFAULT_INSPECTION_PAGE_SIZE,
        manifest: EvidenceManifest | None = None,
    ) -> SubjectiveInspectionPage:
        return await self._load_memory_id_page(
            run_id=run_id,
            owner_id=owner_id,
            after=after,
            limit=limit,
            manifest=manifest,
            kind="traces",
        )

    async def load_reconstructions_page(
        self,
        *,
        run_id: str,
        owner_id: str,
        after: MemoryKeysetCursor | None = None,
        limit: int = DEFAULT_INSPECTION_PAGE_SIZE,
        manifest: EvidenceManifest | None = None,
    ) -> SubjectiveInspectionPage:
        run_id = RunId(run_id).value
        owner_id = AgentId(owner_id).value
        limit = clamp_inspection_page_limit(limit)
        after_tick, after_id = _memory_after(after)
        _validate_manifest_scope(manifest, run_id=run_id, operation="reconstructions")
        started = time.perf_counter()
        async with session_scope(self._session_factory) as session:
            await _require_run(
                session, run_id=run_id, operation="load_reconstructions_page"
            )
            rows = list(
                (
                    await session.execute(
                        select(MemoryReconstructionOrm)
                        .where(
                            MemoryReconstructionOrm.run_id == run_id,
                            MemoryReconstructionOrm.owner_id == owner_id,
                        )
                        .order_by(
                            MemoryReconstructionOrm.created_tick,
                            MemoryReconstructionOrm.reconstruction_id,
                        )
                    )
                )
                .scalars()
                .all()
            )
            ordered = [
                PersistedReconstructionRow(
                    reconstruction_id=row.reconstruction_id,
                    source_memory_ids=(),
                    created_tick=int(row.created_tick),
                    generation=int(row.generation),
                    policy_id=row.policy_id,
                    policy_version=row.policy_version,
                    used_provider=bool(row.used_provider),
                    fallback_used=bool(row.fallback_used),
                    prompt_version=row.prompt_version,
                    schema_version=row.schema_version,
                    payload_sha256=row.payload_sha256,
                )
                for row in rows
            ]
            if manifest is not None:
                ordered = list(
                    clamp_sequence_to_high_water(
                        ordered,
                        manifest.high_water.reconstructions,
                        source_label="reconstructions",
                    )
                )
            filtered = [
                row
                for row in ordered
                if (row.created_tick, row.reconstruction_id) > (after_tick, after_id)
            ]
            page_rows = filtered[:limit]
            has_more = len(filtered) > limit
            # Reconstruction narrative payloads are not stored on this table —
            # metadata-only pages report content_available=False (partial).
            content_available = False
            availability = (
                InspectionAvailability.PARTIAL
                if page_rows
                else InspectionAvailability.AVAILABLE
            )
            if page_rows and not content_available:
                _LOG.warning(
                    "subjective_reconstruction_content_unavailable",
                    extra={
                        "operation": "load_reconstructions_page",
                        "reason_code": "reconstruction_content_unavailable",
                        "run_id": run_id,
                        "owner_id": owner_id,
                        "count": len(page_rows),
                    },
                )
        next_cursor = None
        if has_more and page_rows:
            last = page_rows[-1]
            next_cursor = MemoryKeysetCursor(
                created_tick=last.created_tick, row_id=last.reconstruction_id
            )
        page = SubjectiveInspectionPage(
            run_id=run_id,
            owner_id=owner_id,
            limit=limit,
            item_count=len(page_rows),
            next_cursor=next_cursor,
            availability=availability,
            content_available=content_available,
            manifest_hash=None if manifest is None else manifest.manifest_hash,
        )
        _LOG.debug(
            "subjective_reconstructions_page_complete",
            extra={
                "operation": "load_reconstructions_page",
                "query_type": "reconstructions",
                "run_id": run_id,
                "owner_id": owner_id,
                "limit": limit,
                "count": page.item_count,
                "availability": page.availability.value,
                "content_available": content_available,
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            },
        )
        return page

    async def load_beliefs_page(
        self,
        *,
        run_id: str,
        owner_id: str,
        after: MemoryKeysetCursor | None = None,
        limit: int = DEFAULT_INSPECTION_PAGE_SIZE,
        manifest: EvidenceManifest | None = None,
    ) -> SubjectiveInspectionPage:
        return await self._load_subjective_head_page(
            run_id=run_id,
            owner_id=owner_id,
            after=after,
            limit=limit,
            manifest=manifest,
            orm_cls=SemanticBeliefOrm,
            id_attr="belief_id",
            tick_attr="created_tick",
            high_water_field="beliefs",
            query_type="beliefs",
        )

    async def load_relationships_page(
        self,
        *,
        run_id: str,
        owner_id: str,
        after: MemoryKeysetCursor | None = None,
        limit: int = DEFAULT_INSPECTION_PAGE_SIZE,
        manifest: EvidenceManifest | None = None,
    ) -> SubjectiveInspectionPage:
        return await self._load_subjective_head_page(
            run_id=run_id,
            owner_id=owner_id,
            after=after,
            limit=limit,
            manifest=manifest,
            orm_cls=DirectedRelationshipOrm,
            id_attr="relationship_id",
            tick_attr="created_tick",
            high_water_field="relationships",
            query_type="relationships",
            owner_column="source_id",
        )

    async def _load_memory_id_page(
        self,
        *,
        run_id: str,
        owner_id: str,
        after: MemoryKeysetCursor | None,
        limit: int,
        manifest: EvidenceManifest | None,
        kind: str,
    ) -> SubjectiveInspectionPage:
        run_id = RunId(run_id).value
        owner_id = AgentId(owner_id).value
        limit = clamp_inspection_page_limit(limit)
        after_tick, after_id = _memory_after(after)
        _validate_manifest_scope(manifest, run_id=run_id, operation=kind)
        started = time.perf_counter()
        async with session_scope(self._session_factory) as session:
            await _require_run(session, run_id=run_id, operation=f"load_{kind}_page")
            rows = list(
                (
                    await session.execute(
                        select(MemoryTraceOrm)
                        .where(
                            MemoryTraceOrm.run_id == run_id,
                            MemoryTraceOrm.owner_id == owner_id,
                        )
                        .order_by(MemoryTraceOrm.created_tick, MemoryTraceOrm.memory_id)
                    )
                )
                .scalars()
                .all()
            )
            if manifest is not None:
                direct = [
                    row
                    for row in rows
                    if row.source_kind == MemorySourceKind.DIRECT_OBSERVATION.value
                ]
                communicated = [
                    row
                    for row in rows
                    if row.source_kind == MemorySourceKind.COMMUNICATED.value
                ]
                marks = manifest.high_water
                clamped = list(
                    clamp_sequence_to_high_water(
                        direct, marks.direct_memories, source_label="direct_memories"
                    )
                ) + list(
                    clamp_sequence_to_high_water(
                        communicated,
                        marks.communicated_memories,
                        source_label="communicated_memories",
                    )
                )
                rows = clamped
            filtered = [
                row
                for row in rows
                if (int(row.created_tick), row.memory_id) > (after_tick, after_id)
            ]
            page_rows = filtered[:limit]
            has_more = len(filtered) > limit
        next_cursor = None
        if has_more and page_rows:
            last = page_rows[-1]
            next_cursor = MemoryKeysetCursor(
                created_tick=int(last.created_tick), row_id=last.memory_id
            )
        page = SubjectiveInspectionPage(
            run_id=run_id,
            owner_id=owner_id,
            limit=limit,
            item_count=len(page_rows),
            next_cursor=next_cursor,
            availability=InspectionAvailability.AVAILABLE,
            content_available=True,
            manifest_hash=None if manifest is None else manifest.manifest_hash,
        )
        _LOG.debug(
            "subjective_traces_page_complete",
            extra={
                "operation": f"load_{kind}_page",
                "query_type": kind,
                "run_id": run_id,
                "owner_id": owner_id,
                "limit": limit,
                "count": page.item_count,
                "availability": page.availability.value,
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            },
        )
        return page

    async def _load_subjective_head_page(
        self,
        *,
        run_id: str,
        owner_id: str,
        after: MemoryKeysetCursor | None,
        limit: int,
        manifest: EvidenceManifest | None,
        orm_cls: type,
        id_attr: str,
        tick_attr: str,
        high_water_field: str,
        query_type: str,
        owner_column: str = "owner_id",
    ) -> SubjectiveInspectionPage:
        run_id = RunId(run_id).value
        owner_id = AgentId(owner_id).value
        limit = clamp_inspection_page_limit(limit)
        after_tick, after_id = _memory_after(after)
        _validate_manifest_scope(manifest, run_id=run_id, operation=query_type)
        started = time.perf_counter()
        owner_col = getattr(orm_cls, owner_column)
        id_col = getattr(orm_cls, id_attr)
        tick_col = getattr(orm_cls, tick_attr)
        async with session_scope(self._session_factory) as session:
            await _require_run(
                session, run_id=run_id, operation=f"load_{query_type}_page"
            )
            rows = list(
                (
                    await session.execute(
                        select(orm_cls)
                        .where(orm_cls.run_id == run_id, owner_col == owner_id)
                        .order_by(tick_col, id_col)
                    )
                )
                .scalars()
                .all()
            )
            if manifest is not None:
                high_water = getattr(manifest.high_water, high_water_field)
                rows = list(
                    clamp_sequence_to_high_water(
                        rows, high_water, source_label=high_water_field
                    )
                )
            filtered = [
                row
                for row in rows
                if (int(getattr(row, tick_attr)), getattr(row, id_attr))
                > (after_tick, after_id)
            ]
            page_rows = filtered[:limit]
            has_more = len(filtered) > limit
        next_cursor = None
        if has_more and page_rows:
            last = page_rows[-1]
            next_cursor = MemoryKeysetCursor(
                created_tick=int(getattr(last, tick_attr)),
                row_id=getattr(last, id_attr),
            )
        page = SubjectiveInspectionPage(
            run_id=run_id,
            owner_id=owner_id,
            limit=limit,
            item_count=len(page_rows),
            next_cursor=next_cursor,
            availability=InspectionAvailability.AVAILABLE,
            content_available=True,
            manifest_hash=None if manifest is None else manifest.manifest_hash,
        )
        _LOG.debug(
            "subjective_page_complete",
            extra={
                "operation": f"load_{query_type}_page",
                "query_type": query_type,
                "run_id": run_id,
                "owner_id": owner_id,
                "limit": limit,
                "count": page.item_count,
                "availability": page.availability.value,
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            },
        )
        return page


class SqlAlchemyInspectionEvidenceLoader:
    """Facade combining objective and subjective inspection loaders."""

    __slots__ = ("_objective", "_subjective")

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._objective = SqlAlchemyObjectiveEvidenceLoader(session_factory)
        self._subjective = SqlAlchemySubjectiveEvidenceLoader(session_factory)

    @property
    def objective(self) -> SqlAlchemyObjectiveEvidenceLoader:
        return self._objective

    @property
    def subjective(self) -> SqlAlchemySubjectiveEvidenceLoader:
        return self._subjective


def create_objective_evidence_loader(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> SqlAlchemyObjectiveEvidenceLoader:
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory", operation="create_objective_evidence_loader"
        )
    return SqlAlchemyObjectiveEvidenceLoader(session_factory)


def create_subjective_evidence_loader(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> SqlAlchemySubjectiveEvidenceLoader:
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory", operation="create_subjective_evidence_loader"
        )
    return SqlAlchemySubjectiveEvidenceLoader(session_factory)


def create_inspection_evidence_loader(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> SqlAlchemyInspectionEvidenceLoader:
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory", operation="create_inspection_evidence_loader"
        )
    return SqlAlchemyInspectionEvidenceLoader(session_factory)


async def _require_run(
    session: AsyncSession, *, run_id: str, operation: str
) -> None:
    row = await session.get(SimulationRunOrm, run_id)
    if row is None:
        _LOG.error(
            "inspection_run_not_found",
            extra={
                "operation": operation,
                "run_id": run_id,
                "reason_code": "run_not_found",
            },
        )
        raise PersistenceNotFoundError("run_not_found", operation=operation)


def _validate_manifest_scope(
    manifest: EvidenceManifest | None, *, run_id: str, operation: str
) -> None:
    if manifest is None:
        return
    if type(manifest) is not EvidenceManifest:
        raise TypeError("manifest must be EvidenceManifest")
    if manifest.run_id != run_id:
        _LOG.error(
            "subjective_loader_manifest_scope_mismatch",
            extra={
                "operation": operation,
                "reason_code": "manifest_run_scope_mismatch",
                "run_id": run_id,
            },
        )
        raise InspectionError("manifest_run_scope_mismatch")


def _memory_after(after: MemoryKeysetCursor | None) -> tuple[int, str]:
    if after is None:
        return (0, "")
    if type(after) is not MemoryKeysetCursor:
        raise TypeError("after must be MemoryKeysetCursor or None")
    return (after.created_tick, after.row_id)
