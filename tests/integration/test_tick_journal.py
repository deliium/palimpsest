"""Integration: atomic run create, tick append, idempotency, and snapshot reads."""

from __future__ import annotations

import uuid

import pytest

from agents.models import AgentId
from infrastructure.database import DatabaseResources
from persistence import (
    PersistenceConflictError,
    create_experiment_repository,
    create_run_repository,
    create_snapshot_repository,
    create_tick_journal_repository,
)
from simulation.bootstrap import AgentRegistration
from simulation.clock import Tick
from simulation.journal import hash_snapshot
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.persistence import (
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    ExperimentId,
    ExperimentMetadata,
    ExperimentRunAssignment,
    PayloadHash,
    RunCreateRequest,
    SnapshotId,
    TickAppendRequest,
    WorldSnapshot,
)
from world.events import Waited, make_replayable_event
from world.identifiers import (
    EntityId,
    EventId,
    RequestId,
    WorldId,
    WorldRevision,
)
from world.models import AgentBody, LifeStatus, Location
from world.values import Fatigue, Health, Hunger, TemperatureCelsius, Thirst

pytestmark = pytest.mark.integration


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _alive() -> AgentBody:
    return AgentBody(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
    )


def _bootstrap(*, run_id: str, seed: int = 11) -> WorldSnapshot:
    draft = WorldSnapshot(
        snapshot_id=SnapshotId(_unique("snap")),
        run_id=RunId(run_id),
        world_id=WorldId("world-1"),
        seed=seed,
        config=SimulationRunConfig(seed=seed),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
        ),
        locations=(Location(entity_id=EntityId("loc-1"), name="Camp"),),
        bodies=(_alive(),),
        items=(),
        resources=(),
        weather=(),
        next_tick=Tick(0),
        revision=WorldRevision(0),
        event_schema_version=EVENT_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
        derivation_version=DERIVATION_VERSION,
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
    )
    return WorldSnapshot(
        snapshot_id=draft.snapshot_id,
        run_id=draft.run_id,
        world_id=draft.world_id,
        seed=draft.seed,
        config=draft.config,
        registrations=draft.registrations,
        locations=draft.locations,
        bodies=draft.bodies,
        items=draft.items,
        resources=draft.resources,
        weather=draft.weather,
        next_tick=draft.next_tick,
        revision=draft.revision,
        event_schema_version=draft.event_schema_version,
        projector_version=draft.projector_version,
        persistence_codec_version=draft.persistence_codec_version,
        derivation_version=draft.derivation_version,
        integrity_hash=hash_snapshot(draft),
        predecessor_commit_hash=None,
    )


async def test_create_run_append_tick_idempotent_and_list_events(
    database_resources: DatabaseResources,
) -> None:
    factory = database_resources.session_factory
    runs = create_run_repository(factory)
    journal = create_tick_journal_repository(factory)
    snapshots = create_snapshot_repository(factory)
    experiments = create_experiment_repository(factory)

    run_id = _unique("run")
    exp_id = _unique("exp")
    await experiments.create_experiment(
        ExperimentMetadata(experiment_id=ExperimentId(exp_id), label="baseline")
    )
    bootstrap = _bootstrap(run_id=run_id, seed=2**80)
    request = RunCreateRequest(
        run_id=RunId(run_id),
        world_id=WorldId("world-1"),
        seed=bootstrap.seed,
        config=bootstrap.config,
        bootstrap=bootstrap,
        experiment_assignment=ExperimentRunAssignment(
            experiment_id=ExperimentId(exp_id),
            run_id=RunId(run_id),
            ordinal=0,
        ),
    )
    manifest = await runs.create_run(request)
    assert manifest.run_id.value == run_id
    assert manifest.seed == 2**80

    loaded = await runs.get_run(RunId(run_id))
    assert loaded is not None
    assert loaded.seed == 2**80

    snap = await snapshots.get_snapshot(bootstrap.snapshot_id)
    assert snap is not None
    assert snap.seed == bootstrap.seed
    assert snap.integrity_hash == bootstrap.integrity_hash

    event = make_replayable_event(
        event_id=EventId(_unique("evt")),
        run_id=run_id,
        world_id=WorldId("world-1"),
        tick=0,
        sequence=0,
        request_id=RequestId(_unique("req")),
        resulting_revision=WorldRevision(0),
        details=Waited(),
        actor_id=EntityId("body-1"),
    )
    append = TickAppendRequest(
        run_id=RunId(run_id),
        tick=Tick(0),
        expected_base_revision=WorldRevision(0),
        expected_predecessor_commit_hash=None,
        idempotency_key=_unique("idem"),
        events=(event,),
    )
    commit = await journal.append_tick(append)
    assert commit.event_count == 1
    again = await journal.append_tick(append)
    assert again.commit_hash == commit.commit_hash

    events = await journal.list_events(
        RunId(run_id),
        from_tick=Tick(0),
        to_tick=Tick(0),
        limit=10,
        offset=0,
    )
    assert len(events) == 1
    assert events[0].event_id == event.event_id

    divergent = TickAppendRequest(
        run_id=RunId(run_id),
        tick=Tick(0),
        expected_base_revision=WorldRevision(0),
        expected_predecessor_commit_hash=None,
        idempotency_key=append.idempotency_key,
        events=(),
    )
    with pytest.raises(PersistenceConflictError):
        await journal.append_tick(divergent)

    gap = TickAppendRequest(
        run_id=RunId(run_id),
        tick=Tick(2),
        expected_base_revision=WorldRevision(0),
        expected_predecessor_commit_hash=commit.commit_hash,
        idempotency_key=_unique("idem"),
        events=(),
    )
    with pytest.raises(PersistenceConflictError):
        await journal.append_tick(gap)

    empty = TickAppendRequest(
        run_id=RunId(run_id),
        tick=Tick(1),
        expected_base_revision=WorldRevision(0),
        expected_predecessor_commit_hash=commit.commit_hash,
        idempotency_key=_unique("idem"),
        events=(),
    )
    second = await journal.append_tick(empty)
    assert second.event_count == 0
    assert second.tick == Tick(1)

    latest = await snapshots.get_latest_at_or_before(RunId(run_id), Tick(1))
    assert latest is not None
    assert latest.snapshot_id == bootstrap.snapshot_id
