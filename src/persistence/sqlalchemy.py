"""Async SQLAlchemy repository implementations for simulation persistence ports.

Write paths are append-only: no UPDATE/DELETE on authoritative history.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from infrastructure.database import session_scope
from infrastructure.logging import get_logger
from persistence.errors import (
    PersistenceAdapterError,
    PersistenceConflictError,
    PersistenceCorruptionError,
    PersistenceNotFoundError,
)
from persistence.orm import (
    ExperimentOrm,
    ExperimentRunOrm,
    SimulationRunOrm,
    SnapshotBodyOrm,
    SnapshotInventoryOrm,
    SnapshotItemOrm,
    SnapshotLocationOrm,
    SnapshotRegistrationOrm,
    SnapshotResourceOrm,
    SnapshotWeatherOrm,
    TickCommitOrm,
    WorldEventOrm,
    WorldSnapshotOrm,
)
from persistence.readers import (
    advisory_lock_keys,
    canonical_payload_dict,
    event_details_payload,
    event_from_orm,
    manifest_from_run_orm,
    snapshot_from_canonical_payload,
    tick_commit_from_orm,
)
from simulation.clock import Tick
from simulation.journal import (
    compute_commit_hash,
    hash_snapshot,
    hash_tick_events,
    hash_tick_payload,
    hash_world_event,
)
from simulation.models import RunId
from simulation.persistence import (
    ExperimentId,
    ExperimentMetadata,
    ExperimentRepository,
    ExperimentRunAssignment,
    RunCreateRequest,
    RunManifest,
    SimulationRunRepository,
    SnapshotId,
    SnapshotRepository,
    TickAppendRequest,
    TickCommit,
    TickJournalRepository,
    WorldEvent,
    WorldSnapshot,
    persistence_diagnostic_fields,
)

_LOGGER = get_logger("persistence.sqlalchemy")

__all__ = [
    "SqlAlchemyExperimentRepository",
    "SqlAlchemySimulationRunRepository",
    "SqlAlchemySnapshotRepository",
    "SqlAlchemyTickJournalRepository",
    "create_experiment_repository",
    "create_run_repository",
    "create_snapshot_repository",
    "create_tick_journal_repository",
]


def create_run_repository(
    session_factory: async_sessionmaker[AsyncSession],
) -> SimulationRunRepository:
    return SqlAlchemySimulationRunRepository(session_factory)


def create_tick_journal_repository(
    session_factory: async_sessionmaker[AsyncSession],
) -> TickJournalRepository:
    return SqlAlchemyTickJournalRepository(session_factory)


def create_snapshot_repository(
    session_factory: async_sessionmaker[AsyncSession],
) -> SnapshotRepository:
    return SqlAlchemySnapshotRepository(session_factory)


def create_experiment_repository(
    session_factory: async_sessionmaker[AsyncSession],
) -> ExperimentRepository:
    return SqlAlchemyExperimentRepository(session_factory)


class SqlAlchemySimulationRunRepository:
    """Atomic run creation and manifest loading."""

    __slots__ = ("_session_factory",)

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        self._session_factory = session_factory

    async def create_run(self, request: RunCreateRequest) -> RunManifest:
        if type(request) is not RunCreateRequest:
            raise TypeError("create_run requires RunCreateRequest")
        bootstrap = request.bootstrap
        _verify_snapshot_integrity(bootstrap)
        fields = persistence_diagnostic_fields(
            run_id=request.run_id,
            tick=bootstrap.next_tick,
            revision=bootstrap.revision,
            commit_hash=bootstrap.integrity_hash,
        )
        _LOGGER.debug("run_create_started", **fields)
        try:
            async with session_scope(self._session_factory) as session:
                existing = await session.get(SimulationRunOrm, request.run_id.value)
                if existing is not None:
                    raise PersistenceConflictError(
                        "run_exists", operation="create_run"
                    )
                await _insert_snapshot_graph(session, bootstrap)
                session.add(
                    SimulationRunOrm(
                        run_id=request.run_id.value,
                        world_id=request.world_id.value,
                        seed=Decimal(request.seed),
                        config_seed=Decimal(request.config.seed),
                        derivation_version=request.derivation_version,
                        event_schema_version=request.event_schema_version,
                        projector_version=request.projector_version,
                        persistence_codec_version=request.persistence_codec_version,
                        bootstrap_snapshot_id=bootstrap.snapshot_id.value,
                    )
                )
                if request.experiment_assignment is not None:
                    await session.flush()
                    await _insert_assignment(
                        session, request.experiment_assignment
                    )
                await session.commit()
                manifest = RunManifest(
                    run_id=request.run_id,
                    world_id=request.world_id,
                    seed=request.seed,
                    config=request.config,
                    derivation_version=request.derivation_version,
                    event_schema_version=request.event_schema_version,
                    projector_version=request.projector_version,
                    persistence_codec_version=request.persistence_codec_version,
                )
        except PersistenceAdapterError:
            raise
        except IntegrityError as exc:
            _LOGGER.error(
                "run_create_conflict",
                error=type(exc).__name__,
                **fields,
            )
            raise PersistenceConflictError(
                "integrity_conflict", operation="create_run"
            ) from exc
        except Exception as exc:
            _LOGGER.error(
                "run_create_failed",
                error=type(exc).__name__,
                **fields,
            )
            raise
        _LOGGER.info("run_created", **fields)
        return manifest

    async def get_run(self, run_id: RunId) -> RunManifest | None:
        if type(run_id) is not RunId:
            raise TypeError("get_run requires RunId")
        async with session_scope(self._session_factory) as session:
            row = await session.get(SimulationRunOrm, run_id.value)
            if row is None:
                return None
            return manifest_from_run_orm(row)


class SqlAlchemyTickJournalRepository:
    """Append-only tick commits with advisory locking and idempotency."""

    __slots__ = ("_session_factory",)

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        self._session_factory = session_factory

    async def append_tick(self, request: TickAppendRequest) -> TickCommit:
        if type(request) is not TickAppendRequest:
            raise TypeError("append_tick requires TickAppendRequest")
        fields = persistence_diagnostic_fields(
            run_id=request.run_id,
            tick=request.tick,
            revision=request.expected_base_revision,
            record_count=len(request.events),
        )
        _LOGGER.debug("tick_append_started", **fields)
        candidate: TickCommit | None = None
        try:
            async with session_scope(self._session_factory) as session:
                await _acquire_run_lock(session, request.run_id.value)
                run = await session.get(SimulationRunOrm, request.run_id.value)
                if run is None:
                    raise PersistenceNotFoundError(
                        "run_missing", operation="append_tick"
                    )

                by_idem = await _load_commit_by_idempotency(
                    session, request.run_id.value, request.idempotency_key
                )
                by_tick = await _load_commit_by_tick(
                    session, request.run_id.value, request.tick.value
                )
                candidate = _build_tick_commit(request)

                if by_idem is not None:
                    existing = tick_commit_from_orm(by_idem)
                    if _commits_equivalent(existing, candidate):
                        _LOGGER.warning(
                            "tick_idempotent_retry",
                            **persistence_diagnostic_fields(
                                run_id=request.run_id,
                                tick=request.tick,
                                commit_hash=existing.commit_hash,
                            ),
                        )
                        return existing
                    raise PersistenceConflictError(
                        "idempotency_conflict", operation="append_tick"
                    )
                if by_tick is not None:
                    existing = tick_commit_from_orm(by_tick)
                    if _commits_equivalent(existing, candidate):
                        _LOGGER.warning(
                            "tick_idempotent_retry",
                            **persistence_diagnostic_fields(
                                run_id=request.run_id,
                                tick=request.tick,
                                commit_hash=existing.commit_hash,
                            ),
                        )
                        return existing
                    raise PersistenceConflictError(
                        "tick_conflict", operation="append_tick"
                    )

                await _validate_predecessor(session, request)
                if request.snapshot is not None:
                    if (
                        request.snapshot.predecessor_commit_hash
                        != candidate.commit_hash
                    ):
                        raise PersistenceConflictError(
                            "snapshot_predecessor_mismatch",
                            operation="append_tick",
                        )
                    _verify_snapshot_integrity(request.snapshot)
                    await _insert_snapshot_graph(session, request.snapshot)

                session.add(_tick_commit_orm(candidate))
                for event in request.events:
                    session.add(_event_orm(event))
                await session.commit()
        except PersistenceAdapterError:
            raise
        except IntegrityError as exc:
            _LOGGER.error(
                "tick_append_conflict",
                error=type(exc).__name__,
                **fields,
            )
            raise PersistenceConflictError(
                "integrity_conflict", operation="append_tick"
            ) from exc
        except DBAPIError as exc:
            _LOGGER.error(
                "tick_append_db_error",
                error=type(exc).__name__,
                **fields,
            )
            raise PersistenceAdapterError(
                "database_error", operation="append_tick"
            ) from exc
        except Exception as exc:
            _LOGGER.error(
                "tick_append_failed",
                error=type(exc).__name__,
                **fields,
            )
            raise

        assert candidate is not None
        _LOGGER.info(
            "tick_committed",
            **persistence_diagnostic_fields(
                run_id=request.run_id,
                tick=request.tick,
                revision=candidate.resulting_revision,
                record_count=candidate.event_count,
                commit_hash=candidate.commit_hash,
            ),
        )
        return candidate

    async def get_tick_commit(
        self, run_id: RunId, tick: Tick
    ) -> TickCommit | None:
        if type(run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        if type(tick) is not Tick:
            raise TypeError("tick must be Tick")
        async with session_scope(self._session_factory) as session:
            row = await _load_commit_by_tick(session, run_id.value, tick.value)
            if row is None:
                return None
            return tick_commit_from_orm(row)

    async def list_events(
        self,
        run_id: RunId,
        *,
        from_tick: Tick,
        to_tick: Tick | None,
        limit: int,
        offset: int,
    ) -> tuple[WorldEvent, ...]:
        if type(run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        if type(from_tick) is not Tick:
            raise TypeError("from_tick must be Tick")
        if to_tick is not None and type(to_tick) is not Tick:
            raise TypeError("to_tick must be Tick or None")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError("limit must be a non-negative int")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("offset must be a non-negative int")
        stmt = (
            select(WorldEventOrm)
            .where(WorldEventOrm.run_id == run_id.value)
            .where(WorldEventOrm.tick >= from_tick.value)
            .order_by(WorldEventOrm.tick, WorldEventOrm.sequence)
            .offset(offset)
            .limit(limit)
        )
        if to_tick is not None:
            stmt = stmt.where(WorldEventOrm.tick <= to_tick.value)
        async with session_scope(self._session_factory) as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
            events: list[WorldEvent] = []
            for row in rows:
                decoded = event_from_orm(row)
                if type(decoded) is not WorldEvent:
                    raise PersistenceCorruptionError(
                        "invalid_event", operation="list_events"
                    )
                events.append(decoded)
            return tuple(events)

    async def list_tick_commits(
        self,
        run_id: RunId,
        *,
        from_tick: Tick,
        to_tick: Tick | None,
    ) -> tuple[TickCommit, ...]:
        if type(run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        if type(from_tick) is not Tick:
            raise TypeError("from_tick must be Tick")
        if to_tick is not None and type(to_tick) is not Tick:
            raise TypeError("to_tick must be Tick or None")
        stmt = (
            select(TickCommitOrm)
            .where(TickCommitOrm.run_id == run_id.value)
            .where(TickCommitOrm.tick >= from_tick.value)
            .order_by(TickCommitOrm.tick)
        )
        if to_tick is not None:
            stmt = stmt.where(TickCommitOrm.tick <= to_tick.value)
        async with session_scope(self._session_factory) as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return tuple(tick_commit_from_orm(row) for row in rows)


class SqlAlchemySnapshotRepository:
    """Immutable checkpoint lookup."""

    __slots__ = ("_session_factory",)

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        self._session_factory = session_factory

    async def get_latest_at_or_before(
        self, run_id: RunId, tick: Tick
    ) -> WorldSnapshot | None:
        if type(run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        if type(tick) is not Tick:
            raise TypeError("tick must be Tick")
        stmt = (
            select(WorldSnapshotOrm)
            .where(WorldSnapshotOrm.run_id == run_id.value)
            .where(WorldSnapshotOrm.next_tick <= tick.value)
            .order_by(WorldSnapshotOrm.next_tick.desc())
            .limit(1)
        )
        async with session_scope(self._session_factory) as session:
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return await _load_snapshot_graph(session, row)

    async def get_snapshot(self, snapshot_id: SnapshotId) -> WorldSnapshot | None:
        if type(snapshot_id) is not SnapshotId:
            raise TypeError("snapshot_id must be SnapshotId")
        async with session_scope(self._session_factory) as session:
            row = await session.get(WorldSnapshotOrm, snapshot_id.value)
            if row is None:
                return None
            return await _load_snapshot_graph(session, row)


class SqlAlchemyExperimentRepository:
    """Experiment metadata and run assignment ports."""

    __slots__ = ("_session_factory",)

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        self._session_factory = session_factory

    async def create_experiment(
        self, metadata: ExperimentMetadata
    ) -> ExperimentMetadata:
        if type(metadata) is not ExperimentMetadata:
            raise TypeError("create_experiment requires ExperimentMetadata")
        fields = {"experiment_id": metadata.experiment_id.value}
        _LOGGER.debug("experiment_create_started", **fields)
        try:
            async with session_scope(self._session_factory) as session:
                existing = await session.get(
                    ExperimentOrm, metadata.experiment_id.value
                )
                if existing is not None:
                    raise PersistenceConflictError(
                        "experiment_exists", operation="create_experiment"
                    )
                session.add(
                    ExperimentOrm(
                        experiment_id=metadata.experiment_id.value,
                        label=metadata.label,
                    )
                )
                await session.commit()
        except PersistenceAdapterError:
            raise
        except IntegrityError as exc:
            raise PersistenceConflictError(
                "integrity_conflict", operation="create_experiment"
            ) from exc
        _LOGGER.info("experiment_created", **fields)
        return metadata

    async def assign_run(
        self, assignment: ExperimentRunAssignment
    ) -> ExperimentRunAssignment:
        if type(assignment) is not ExperimentRunAssignment:
            raise TypeError("assign_run requires ExperimentRunAssignment")
        try:
            async with session_scope(self._session_factory) as session:
                await _insert_assignment(session, assignment)
                await session.commit()
        except PersistenceAdapterError:
            raise
        except IntegrityError as exc:
            raise PersistenceConflictError(
                "integrity_conflict", operation="assign_run"
            ) from exc
        return assignment

    async def get_experiment(
        self, experiment_id: ExperimentId
    ) -> ExperimentMetadata | None:
        if type(experiment_id) is not ExperimentId:
            raise TypeError("experiment_id must be ExperimentId")
        async with session_scope(self._session_factory) as session:
            row = await session.get(ExperimentOrm, experiment_id.value)
            if row is None:
                return None
            return ExperimentMetadata(
                experiment_id=ExperimentId(row.experiment_id),
                label=row.label,
            )


async def _acquire_run_lock(session: AsyncSession, run_id: str) -> None:
    key1, key2 = advisory_lock_keys(run_id)
    _LOGGER.debug(
        "advisory_lock_acquired",
        run_id=run_id,
        lock_key1=key1,
        lock_key2=key2,
    )
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:k1, :k2)"),
        {"k1": key1, "k2": key2},
    )


async def _load_commit_by_tick(
    session: AsyncSession, run_id: str, tick: int
) -> TickCommitOrm | None:
    return await session.get(TickCommitOrm, (run_id, tick))


async def _load_commit_by_idempotency(
    session: AsyncSession, run_id: str, idempotency_key: str
) -> TickCommitOrm | None:
    stmt = (
        select(TickCommitOrm)
        .where(TickCommitOrm.run_id == run_id)
        .where(TickCommitOrm.idempotency_key == idempotency_key)
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _validate_predecessor(
    session: AsyncSession, request: TickAppendRequest
) -> None:
    if request.tick.value == 0:
        if request.expected_predecessor_commit_hash is not None:
            raise PersistenceConflictError(
                "stale_predecessor", operation="append_tick"
            )
        return
    previous = await _load_commit_by_tick(
        session, request.run_id.value, request.tick.value - 1
    )
    if previous is None:
        raise PersistenceConflictError("tick_gap", operation="append_tick")
    if previous.resulting_revision != request.expected_base_revision.value:
        _LOGGER.warning(
            "stale_writer",
            **persistence_diagnostic_fields(
                run_id=request.run_id,
                tick=request.tick,
                revision=request.expected_base_revision,
            ),
        )
        raise PersistenceConflictError("stale_writer", operation="append_tick")
    expected_pred = request.expected_predecessor_commit_hash
    actual_pred = previous.commit_hash
    if expected_pred is None or expected_pred.value != actual_pred:
        raise PersistenceConflictError(
            "predecessor_mismatch", operation="append_tick"
        )


def _build_tick_commit(request: TickAppendRequest) -> TickCommit:
    events = request.events
    for index, event in enumerate(events):
        if event.sequence != index:
            raise PersistenceConflictError(
                "sequence_gap", operation="append_tick"
            )
    payload = hash_tick_payload(events)
    event_hashes = hash_tick_events(events)
    if events:
        resulting_revision = events[-1].resulting_revision
    else:
        resulting_revision = request.expected_base_revision
    if resulting_revision.value < request.expected_base_revision.value:
        raise PersistenceConflictError(
            "revision_regression", operation="append_tick"
        )
    if resulting_revision.value - request.expected_base_revision.value > 1:
        raise PersistenceConflictError(
            "revision_delta", operation="append_tick"
        )
    commit_hash = compute_commit_hash(
        predecessor_commit_hash=request.expected_predecessor_commit_hash,
        run_id=request.run_id,
        tick=request.tick,
        base_revision=request.expected_base_revision,
        resulting_revision=resulting_revision,
        event_hashes=event_hashes,
        payload_hash=payload,
    )
    return TickCommit(
        run_id=request.run_id,
        tick=request.tick,
        resulting_tick=Tick(request.tick.value + 1),
        base_revision=request.expected_base_revision,
        resulting_revision=resulting_revision,
        predecessor_commit_hash=request.expected_predecessor_commit_hash,
        commit_hash=commit_hash,
        idempotency_key=request.idempotency_key,
        event_count=len(events),
        payload_hash=payload,
        snapshot_id=(
            None if request.snapshot is None else request.snapshot.snapshot_id
        ),
    )


def _commits_equivalent(existing: TickCommit, candidate: TickCommit) -> bool:
    return (
        existing.run_id == candidate.run_id
        and existing.tick == candidate.tick
        and existing.resulting_tick == candidate.resulting_tick
        and existing.base_revision == candidate.base_revision
        and existing.resulting_revision == candidate.resulting_revision
        and existing.predecessor_commit_hash == candidate.predecessor_commit_hash
        and existing.commit_hash == candidate.commit_hash
        and existing.idempotency_key == candidate.idempotency_key
        and existing.event_count == candidate.event_count
        and existing.payload_hash == candidate.payload_hash
        and existing.snapshot_id == candidate.snapshot_id
    )


def _tick_commit_orm(commit: TickCommit) -> TickCommitOrm:
    return TickCommitOrm(
        run_id=commit.run_id.value,
        tick=commit.tick.value,
        resulting_tick=commit.resulting_tick.value,
        base_revision=commit.base_revision.value,
        resulting_revision=commit.resulting_revision.value,
        predecessor_commit_hash=(
            None
            if commit.predecessor_commit_hash is None
            else commit.predecessor_commit_hash.value
        ),
        commit_hash=commit.commit_hash.value,
        idempotency_key=commit.idempotency_key,
        event_count=commit.event_count,
        payload_hash=commit.payload_hash.value,
        snapshot_id=None if commit.snapshot_id is None else commit.snapshot_id.value,
    )


def _event_orm(event: WorldEvent) -> WorldEventOrm:
    return WorldEventOrm(
        run_id=event.run_id,
        tick=event.tick,
        sequence=event.sequence,
        event_id=event.event_id.value,
        world_id=event.world_id.value,
        request_id=event.request_id.value,
        resulting_revision=event.resulting_revision.value,
        schema_version=event.schema_version,
        event_type=event.event_type,
        actor_id=None if event.actor_id is None else event.actor_id.value,
        target_id=None if event.target_id is None else event.target_id.value,
        details=event_details_payload(event),
        payload_hash=hash_world_event(event).value,
    )


def _verify_snapshot_integrity(snapshot: WorldSnapshot) -> None:
    computed = hash_snapshot(snapshot)
    if computed.value != snapshot.integrity_hash.value:
        raise PersistenceCorruptionError(
            "integrity_mismatch", operation="verify_snapshot"
        )


async def _insert_assignment(
    session: AsyncSession, assignment: ExperimentRunAssignment
) -> None:
    experiment = await session.get(
        ExperimentOrm, assignment.experiment_id.value
    )
    if experiment is None:
        raise PersistenceNotFoundError(
            "experiment_missing", operation="assign_run"
        )
    run = await session.get(SimulationRunOrm, assignment.run_id.value)
    if run is None:
        raise PersistenceNotFoundError("run_missing", operation="assign_run")
    session.add(
        ExperimentRunOrm(
            experiment_id=assignment.experiment_id.value,
            run_id=assignment.run_id.value,
            ordinal=assignment.ordinal,
        )
    )


async def _insert_snapshot_graph(
    session: AsyncSession, snapshot: WorldSnapshot
) -> None:
    # Flush the immutable parent before normalized projections. Bootstrap
    # creation has a deferred run↔snapshot FK cycle; without an explicit
    # parent flush, SQLAlchemy can emit child rows first and trip FKs.
    session.add(
        WorldSnapshotOrm(
            snapshot_id=snapshot.snapshot_id.value,
            run_id=snapshot.run_id.value,
            world_id=snapshot.world_id.value,
            seed=Decimal(snapshot.seed),
            config_seed=Decimal(snapshot.config.seed),
            next_tick=snapshot.next_tick.value,
            revision=snapshot.revision.value,
            event_schema_version=snapshot.event_schema_version,
            projector_version=snapshot.projector_version,
            persistence_codec_version=snapshot.persistence_codec_version,
            derivation_version=snapshot.derivation_version,
            integrity_hash=snapshot.integrity_hash.value,
            predecessor_commit_hash=(
                None
                if snapshot.predecessor_commit_hash is None
                else snapshot.predecessor_commit_hash.value
            ),
            canonical_payload=canonical_payload_dict(snapshot),
        )
    )
    await session.flush()
    for location in snapshot.locations:
        session.add(
            SnapshotLocationOrm(
                run_id=snapshot.run_id.value,
                snapshot_id=snapshot.snapshot_id.value,
                entity_id=location.entity_id.value,
                name=location.name,
            )
        )
    for ordinal, registration in enumerate(snapshot.registrations):
        session.add(
            SnapshotRegistrationOrm(
                run_id=snapshot.run_id.value,
                snapshot_id=snapshot.snapshot_id.value,
                ordinal=ordinal,
                agent_id=registration.agent_id.value,
                entity_id=registration.entity_id.value,
            )
        )
    for body in snapshot.bodies:
        session.add(
            SnapshotBodyOrm(
                run_id=snapshot.run_id.value,
                snapshot_id=snapshot.snapshot_id.value,
                entity_id=body.entity_id.value,
                location_id=body.location_id.value,
                health=body.health.value,
                hunger=body.hunger.value,
                thirst=body.thirst.value,
                fatigue=body.fatigue.value,
                temperature=body.temperature.value,
                life_status=body.life_status.value,
            )
        )
        for position, item_id in enumerate(body.inventory):
            session.add(
                SnapshotInventoryOrm(
                    run_id=snapshot.run_id.value,
                    snapshot_id=snapshot.snapshot_id.value,
                    body_id=body.entity_id.value,
                    position=position,
                    item_id=item_id.value,
                )
            )
    for item in snapshot.items:
        session.add(
            SnapshotItemOrm(
                run_id=snapshot.run_id.value,
                snapshot_id=snapshot.snapshot_id.value,
                entity_id=item.entity_id.value,
                name=item.name,
                location_id=(
                    None if item.location_id is None else item.location_id.value
                ),
                holder_id=None if item.holder_id is None else item.holder_id.value,
            )
        )
    for resource in snapshot.resources:
        session.add(
            SnapshotResourceOrm(
                run_id=snapshot.run_id.value,
                snapshot_id=snapshot.snapshot_id.value,
                entity_id=resource.entity_id.value,
                name=resource.name,
                location_id=resource.location_id.value,
                quantity=resource.quantity,
                unit=resource.unit,
            )
        )
    for entry in snapshot.weather:
        session.add(
            SnapshotWeatherOrm(
                run_id=snapshot.run_id.value,
                snapshot_id=snapshot.snapshot_id.value,
                location_id=entry.location_id.value,
                condition=entry.condition,
                temperature=entry.temperature.value,
            )
        )


async def _load_snapshot_graph(
    session: AsyncSession, row: WorldSnapshotOrm
) -> WorldSnapshot:
    del session  # Normalized rows are query projections; codec payload is authority.
    payload = row.canonical_payload
    if not isinstance(payload, dict):
        raise PersistenceCorruptionError(
            "invalid_payload", operation="load_snapshot"
        )
    return snapshot_from_canonical_payload(
        payload, expected_integrity_hash=row.integrity_hash
    )
