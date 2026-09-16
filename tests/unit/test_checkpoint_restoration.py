"""Checkpoint restoration through WorldEngine without state-replacement hooks."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.clock import Tick
from simulation.engine import EnginePhase, WorldEngine
from simulation.journal import hash_snapshot
from simulation.lifecycle import EngineDiagnosticCode
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.persistence import (
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    PayloadHash,
    SnapshotId,
    WorldSnapshot,
)
from world._state import World
from world.events import Taken, Waited, make_replayable_event
from world.identifiers import (
    EntityId,
    EventId,
    RequestId,
    WorldId,
    WorldRevision,
)
from world.models import AgentBody, Item, LifeStatus, Location
from world.values import Fatigue, Health, Hunger, TemperatureCelsius, Thirst

_HASH_PLACEHOLDER = "a" * 64


def _alive(
    entity_id: str = "body-1",
    *,
    location_id: str = "loc-1",
    inventory: tuple[EntityId, ...] = (),
) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId(location_id),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=inventory,
        life_status=LifeStatus.ALIVE,
    )


def _make_snapshot(
    *,
    seed: int = 7,
    next_tick: int = 0,
    revision: int = 0,
    items: tuple[Item, ...] = (),
    bodies: tuple[AgentBody, ...] | None = None,
) -> WorldSnapshot:
    body_tuple = bodies if bodies is not None else (_alive(),)
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-1"),
        run_id=RunId("run-restore-1"),
        world_id=WorldId("world-1"),
        seed=seed,
        config=SimulationRunConfig(seed=seed),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
        ),
        locations=(Location(entity_id=EntityId("loc-1"), name="Camp"),),
        bodies=body_tuple,
        items=items,
        resources=(),
        weather=(),
        next_tick=Tick(next_tick),
        revision=WorldRevision(revision),
        event_schema_version=EVENT_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
        derivation_version=DERIVATION_VERSION,
        integrity_hash=PayloadHash(_HASH_PLACEHOLDER),
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


def test_restore_bootstrap_only_awaits_observation() -> None:
    snapshot = _make_snapshot()
    engine = WorldEngine.restore_from_snapshot(snapshot)
    assert engine.run_id == snapshot.run_id
    assert engine.tick == Tick(0)
    assert engine.revision == WorldRevision(0)
    assert engine.phase is EnginePhase.AWAITING_OBSERVATION
    assert engine.world_id == snapshot.world_id
    batch = engine.observe()
    assert batch.token is not None
    assert batch.tick == Tick(0)


def test_restore_applies_events_and_advances_tick() -> None:
    item = Item(
        entity_id=EntityId("item-1"),
        name="Rock",
        location_id=EntityId("loc-1"),
    )
    snapshot = _make_snapshot(items=(item,))
    event = make_replayable_event(
        event_id=EventId("evt-1"),
        run_id=snapshot.run_id.value,
        world_id=snapshot.world_id,
        tick=0,
        sequence=0,
        request_id=RequestId("req-1"),
        resulting_revision=WorldRevision(1),
        details=Taken(EntityId("item-1"), resulting_holder_id=EntityId("body-1")),
        actor_id=EntityId("body-1"),
    )
    engine = WorldEngine.restore_from_snapshot(snapshot, events=(event,))
    assert engine.tick == Tick(1)
    assert engine.revision == WorldRevision(1)
    assert engine.phase is EnginePhase.AWAITING_OBSERVATION
    export = engine.export_events()
    assert len(export.events) == 1
    assert export.events[0].event_id == event.event_id


def test_restore_rejects_corrupt_integrity_hash() -> None:
    snapshot = _make_snapshot()
    corrupt = WorldSnapshot(
        snapshot_id=snapshot.snapshot_id,
        run_id=snapshot.run_id,
        world_id=snapshot.world_id,
        seed=snapshot.seed,
        config=snapshot.config,
        registrations=snapshot.registrations,
        locations=snapshot.locations,
        bodies=snapshot.bodies,
        items=snapshot.items,
        resources=snapshot.resources,
        weather=snapshot.weather,
        next_tick=snapshot.next_tick,
        revision=snapshot.revision,
        event_schema_version=snapshot.event_schema_version,
        projector_version=snapshot.projector_version,
        persistence_codec_version=snapshot.persistence_codec_version,
        derivation_version=snapshot.derivation_version,
        integrity_hash=PayloadHash("b" * 64),
        predecessor_commit_hash=None,
    )
    with pytest.raises(ValueError, match="integrity_hash_mismatch"):
        WorldEngine.restore_from_snapshot(corrupt)


def test_world_replace_state_remains_unsupported() -> None:
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-1"),
        revision=WorldRevision(0),
        locations=(Location(entity_id=EntityId("loc-1"), name="Camp"),),
        bodies=(_alive(),),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
        ),
    )
    engine = WorldEngine(
        config=SimulationRunConfig(seed=1),
        bootstrap=bootstrap,
        run_id=RunId("run-1"),
    )
    world = engine._snapshot.world
    assert type(world) is World
    with pytest.raises(RuntimeError, match="not a supported mutation path"):
        world.replace_state(world.state)


def test_restore_logs_debug_info_without_payloads(
    caplog: pytest.LogCaptureFixture,
) -> None:
    snapshot = _make_snapshot(seed=2**80 + 99)
    event = make_replayable_event(
        event_id=EventId("evt-wait"),
        run_id=snapshot.run_id.value,
        world_id=snapshot.world_id,
        tick=0,
        sequence=0,
        request_id=RequestId("req-wait"),
        resulting_revision=WorldRevision(0),
        details=Waited(),
        actor_id=EntityId("body-1"),
    )
    with caplog.at_level(logging.DEBUG, logger="simulation.engine"):
        WorldEngine.restore_from_snapshot(snapshot, events=(event,))
    joined = "\n".join(record.getMessage() for record in caplog.records)
    assert EngineDiagnosticCode.CHECKPOINT_RESTORE.value in joined
    assert "events_applied=1" in joined
    assert "Rock" not in joined
    assert "Waited" not in joined
    assert str(snapshot.seed) not in joined
