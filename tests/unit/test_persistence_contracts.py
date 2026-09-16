"""Immutable persistence DTO and repository protocol contracts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration
from simulation.clock import Tick
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.persistence import (
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    CommitHash,
    ExperimentId,
    ExperimentMetadata,
    ExperimentRunAssignment,
    PayloadHash,
    ReplayFallbackPolicy,
    ReplayMode,
    ReplayRequest,
    ReplayResult,
    ReplayStatus,
    RunCreateRequest,
    RunManifest,
    SnapshotId,
    TickAppendRequest,
    TickCommit,
    WorldSnapshot,
    persistence_diagnostic_fields,
    require_commit_hash,
)
from world.events import EVENT_SCHEMA_REPLAY_V1, Waited, make_replayable_event
from world.identifiers import (
    EntityId,
    EventId,
    RequestId,
    WorldId,
    WorldRevision,
)
from world.models import AgentBody, Item, LifeStatus, Location
from world.values import Fatigue, Health, Hunger, TemperatureCelsius, Thirst

_HASH_A = "a" * 64
_HASH_B = "b" * 64
_HASH_C = "c" * 64


def _alive_body(
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


def _bootstrap_snapshot(
    *,
    run_id: str = "run-1",
    seed: int = 7,
    inventory: tuple[EntityId, ...] = (),
    items: tuple[Item, ...] = (),
    registrations: tuple[AgentRegistration, ...] | None = None,
    bodies: tuple[AgentBody, ...] | None = None,
) -> WorldSnapshot:
    location = Location(entity_id=EntityId("loc-1"), name="Camp")
    if bodies is None:
        bodies = (_alive_body(inventory=inventory),)
    if registrations is None:
        registrations = (
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
        )
    return WorldSnapshot(
        snapshot_id=SnapshotId("snap-bootstrap"),
        run_id=RunId(run_id),
        world_id=WorldId("world-1"),
        seed=seed,
        config=SimulationRunConfig(seed=seed),
        registrations=registrations,
        locations=(location,),
        bodies=bodies,
        items=items,
        resources=(),
        weather=(),
        next_tick=Tick(0),
        revision=WorldRevision(0),
        event_schema_version=EVENT_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
        derivation_version=DERIVATION_VERSION,
        integrity_hash=PayloadHash(_HASH_A),
        predecessor_commit_hash=None,
    )


def test_version_constants_align_with_replay_schema() -> None:
    assert EVENT_SCHEMA_VERSION == EVENT_SCHEMA_REPLAY_V1 == 2
    assert PROJECTOR_VERSION == "v1"
    assert PERSISTENCE_CODEC_VERSION == "v1"


def test_commit_hash_requires_lowercase_sha256_hex() -> None:
    assert CommitHash(_HASH_A).value == _HASH_A
    with pytest.raises(ValueError, match="64 lowercase"):
        CommitHash("A" * 64)
    with pytest.raises(ValueError, match="64 lowercase"):
        require_commit_hash("x", "abc")
    with pytest.raises(ValueError, match="must be a str"):
        require_commit_hash("x", 123)  # type: ignore[arg-type]


def test_world_snapshot_copies_sequences_and_preserves_order() -> None:
    item_a = Item(
        entity_id=EntityId("item-a"), name="A", holder_id=EntityId("body-1")
    )
    item_b = Item(
        entity_id=EntityId("item-b"), name="B", holder_id=EntityId("body-1")
    )
    inventory = (EntityId("item-b"), EntityId("item-a"))
    bodies = [_alive_body(inventory=inventory)]
    registrations = [
        AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
    ]
    snapshot = _bootstrap_snapshot(
        inventory=inventory,
        items=(item_a, item_b),
        bodies=tuple(bodies),
        registrations=tuple(registrations),
    )
    assert snapshot.bodies[0].inventory == inventory
    assert snapshot.items[0].entity_id == EntityId("item-a")
    assert snapshot.registrations[0].agent_id == AgentId("agent-1")
    assert isinstance(snapshot.registrations, tuple)
    assert isinstance(snapshot.locations, tuple)
    assert isinstance(snapshot.bodies, tuple)
    with pytest.raises(FrozenInstanceError):
        snapshot.seed = 99  # type: ignore[misc]
    with pytest.raises(TypeError, match="ordered sequence"):
        WorldSnapshot(
            snapshot_id=SnapshotId("snap-1"),
            run_id=RunId("run-1"),
            world_id=WorldId("world-1"),
            seed=1,
            config=SimulationRunConfig(seed=1),
            registrations={registrations[0]},  # type: ignore[arg-type]
            locations=(Location(entity_id=EntityId("loc-1"), name="Camp"),),
            bodies=(_alive_body(),),
            items=(),
            resources=(),
            weather=(),
            next_tick=Tick(0),
            revision=WorldRevision(0),
            event_schema_version=EVENT_SCHEMA_VERSION,
            projector_version=PROJECTOR_VERSION,
            persistence_codec_version=PERSISTENCE_CODEC_VERSION,
            derivation_version=DERIVATION_VERSION,
            integrity_hash=PayloadHash(_HASH_A),
            predecessor_commit_hash=None,
        )


def test_run_create_request_requires_bootstrap_at_tick_zero() -> None:
    bootstrap = _bootstrap_snapshot()
    request = RunCreateRequest(
        run_id=RunId("run-1"),
        world_id=WorldId("world-1"),
        seed=7,
        config=SimulationRunConfig(seed=7),
        bootstrap=bootstrap,
        experiment_assignment=ExperimentRunAssignment(
            experiment_id=ExperimentId("exp-1"),
            run_id=RunId("run-1"),
            ordinal=0,
        ),
    )
    assert request.bootstrap.next_tick == Tick(0)
    advanced = WorldSnapshot(
        snapshot_id=SnapshotId("snap-1"),
        run_id=RunId("run-1"),
        world_id=WorldId("world-1"),
        seed=7,
        config=SimulationRunConfig(seed=7),
        registrations=bootstrap.registrations,
        locations=bootstrap.locations,
        bodies=bootstrap.bodies,
        items=bootstrap.items,
        resources=bootstrap.resources,
        weather=bootstrap.weather,
        next_tick=Tick(1),
        revision=WorldRevision(0),
        event_schema_version=EVENT_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
        derivation_version=DERIVATION_VERSION,
        integrity_hash=PayloadHash(_HASH_A),
        predecessor_commit_hash=None,
    )
    with pytest.raises(ValueError, match="next_tick must be Tick\\(0\\)"):
        RunCreateRequest(
            run_id=RunId("run-1"),
            world_id=WorldId("world-1"),
            seed=7,
            config=SimulationRunConfig(seed=7),
            bootstrap=advanced,
        )


def test_run_manifest_and_tick_commit_are_immutable() -> None:
    manifest = RunManifest(
        run_id=RunId("run-1"),
        world_id=WorldId("world-1"),
        seed=3,
        config=SimulationRunConfig(seed=3),
        derivation_version=DERIVATION_VERSION,
        event_schema_version=EVENT_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
    )
    commit = TickCommit(
        run_id=RunId("run-1"),
        tick=Tick(0),
        resulting_tick=Tick(1),
        base_revision=WorldRevision(0),
        resulting_revision=WorldRevision(1),
        predecessor_commit_hash=None,
        commit_hash=CommitHash(_HASH_B),
        idempotency_key="idem-1",
        event_count=0,
        payload_hash=PayloadHash(_HASH_C),
        snapshot_id=SnapshotId("snap-1"),
    )
    with pytest.raises(FrozenInstanceError):
        manifest.seed = 1  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        commit.event_count = 2  # type: ignore[misc]
    with pytest.raises(ValueError, match="tick \\+ 1"):
        TickCommit(
            run_id=RunId("run-1"),
            tick=Tick(0),
            resulting_tick=Tick(2),
            base_revision=WorldRevision(0),
            resulting_revision=WorldRevision(0),
            predecessor_commit_hash=None,
            commit_hash=CommitHash(_HASH_B),
            idempotency_key="idem-1",
            event_count=0,
            payload_hash=PayloadHash(_HASH_C),
        )


def test_tick_append_request_copies_events_and_rejects_sets() -> None:
    event = make_replayable_event(
        event_id=EventId("evt-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=0,
        sequence=0,
        request_id=RequestId("r-1"),
        resulting_revision=WorldRevision(1),
        details=Waited(),
        actor_id=EntityId("body-1"),
    )
    request = TickAppendRequest(
        run_id=RunId("run-1"),
        tick=Tick(0),
        expected_base_revision=WorldRevision(0),
        expected_predecessor_commit_hash=None,
        idempotency_key="idem-1",
        events=[event],
    )
    assert request.events == (event,)
    assert isinstance(request.events, tuple)
    with pytest.raises(TypeError, match="ordered sequence"):
        TickAppendRequest(
            run_id=RunId("run-1"),
            tick=Tick(0),
            expected_base_revision=WorldRevision(0),
            expected_predecessor_commit_hash=None,
            idempotency_key="idem-1",
            events={event},  # type: ignore[arg-type]
        )


def test_experiment_and_replay_dtos() -> None:
    meta = ExperimentMetadata(
        experiment_id=ExperimentId("exp-1"),
        label="baseline",
    )
    assert meta.label == "baseline"
    result = ReplayResult(
        run_id=RunId("run-1"),
        status=ReplayStatus.OK,
        mode=ReplayMode.READONLY,
        snapshot_id=SnapshotId("snap-1"),
        snapshot_next_tick=Tick(0),
        target_tick=Tick(3),
        events_applied=3,
        event_schema_version=EVENT_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
    )
    request = ReplayRequest(
        run_id=RunId("run-1"),
        target_tick=Tick(3),
        fallback_policy=ReplayFallbackPolicy.LATEST_AT_OR_BEFORE,
    )
    assert request.target_tick == Tick(3)
    assert result.mode is ReplayMode.READONLY
    with pytest.raises(FrozenInstanceError):
        meta.label = "other"  # type: ignore[misc]


def test_persistence_diagnostic_fields_exclude_secrets() -> None:
    fields = persistence_diagnostic_fields(
        run_id=RunId("run-1"),
        tick=Tick(4),
        revision=WorldRevision(9),
        record_count=12,
        version=PROJECTOR_VERSION,
        commit_hash=CommitHash(_HASH_A),
    )
    assert fields == {
        "run_id": "run-1",
        "tick": 4,
        "revision": 9,
        "record_count": 12,
        "version": "v1",
        "hash_prefix": "aaaaaaaa",
    }
    assert "seed" not in fields
    assert "config" not in fields
    assert "snapshot" not in fields
    assert "events" not in fields
    assert "label" not in fields
    assert _HASH_A not in fields.values()
    assert persistence_diagnostic_fields(
        commit_hash=PayloadHash(_HASH_B)
    ) == {"hash_prefix": "bbbbbbbb"}
