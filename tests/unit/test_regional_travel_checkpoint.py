"""Codec-v19 checkpoints preserve topology and mid-journey state."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration
from simulation.branch_service import rematerialize_snapshot
from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.journal import (
    PersistenceSerializationError,
    decode_persistence,
    encode_persistence,
    hash_snapshot,
)
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.persistence import (
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    PayloadHash,
    SnapshotId,
    WorldSnapshot,
    checkpoint_schema_for_production,
)
from tests.simulation_helpers import (
    alive_body,
    connected_locations,
    weather_for_locations,
)
from world.effects import SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V21,
    JourneyArrived,
    build_occurrence_context,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.models import default_physical_rules
from world.regions import (
    CognitionMode,
    Journey,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)


def _snapshot(codec: str = "v19", schema: int = 21) -> WorldSnapshot:
    locations = connected_locations(("loc-1", "One"), ("loc-2", "Two"))
    body = alive_body("body-1", location_id="loc-1")
    spec = RegionsMigrationSpec(
        regions=(
            RegionDefinition("north", "North"),
            RegionDefinition("south", "South"),
        ),
        location_regions=(
            LocationRegion(EntityId("loc-1"), "north"),
            LocationRegion(EntityId("loc-2"), "south"),
        ),
        routes=(RouteSpec(EntityId("loc-1"), EntityId("loc-2"), 2, 4.0),),
        max_arrival_wait_ticks=1,
        residence_min_ticks=3,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )
    region_journeys = (
        Journey(
            journey_id="journey-checkpoint",
            participant_body_ids=(body.entity_id,),
            actor_body_id=body.entity_id,
            origin_location_id=EntityId("loc-1"),
            destination_location_id=EntityId("loc-2"),
            origin_region_id="north",
            destination_region_id="south",
            start_tick=1,
            due_tick=2,
            charged_fatigue_cost=4.0,
            arrival_wait_deadline_tick=3,
        ),
    )
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snapshot-regions"),
        run_id=RunId("run-regions"),
        world_id=WorldId("world-regions"),
        seed=7,
        config=SimulationRunConfig(
            seed=7,
            physical_rules=default_physical_rules(),
        ),
        registrations=(AgentRegistration(AgentId("agent-1"), body.entity_id),),
        locations=locations,
        bodies=(body,),
        items=(),
        resources=(),
        weather=weather_for_locations(locations),
        next_tick=Tick(2),
        revision=WorldRevision(1),
        event_schema_version=schema,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=codec,
        derivation_version=DERIVATION_VERSION,
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        regions_migration=spec if codec == "v19" else None,
        journeys=region_journeys if codec == "v19" else None,
    )
    return replace(draft, integrity_hash=hash_snapshot(draft))


def test_codec_v19_round_trips_region_definitions_and_capacity_wait() -> None:
    snapshot = _snapshot()
    payload = encode_persistence(snapshot)
    decoded = decode_persistence(payload, WorldSnapshot)
    assert decoded.regions_migration == snapshot.regions_migration
    assert decoded.journeys == snapshot.journeys
    assert hash_snapshot(decoded) == decoded.integrity_hash
    raw = json.loads(payload)
    assert "regions_migration" in raw["data"]
    assert "journeys" in raw["data"]


def test_codec_v19_rejects_unknown_region_fields() -> None:
    payload = json.loads(encode_persistence(_snapshot()))
    payload["data"]["regions_migration"]["regions"][0]["extra"] = True
    with pytest.raises(PersistenceSerializationError, match="invalid_fields"):
        decode_persistence(json.dumps(payload).encode(), WorldSnapshot)


def test_legacy_codec_payload_omits_regions_and_journeys() -> None:
    snapshot = _snapshot(
        codec=PERSISTENCE_CODEC_VERSION,
        schema=EVENT_SCHEMA_VERSION,
    )
    payload = json.loads(encode_persistence(snapshot))
    assert "regions_migration" not in payload["data"]
    assert "journeys" not in payload["data"]


def test_regions_channel_selects_replay_v21_codec_v19_pair() -> None:
    assert checkpoint_schema_for_production(
        production_active=False,
        dynamics_active=False,
        regions_migration_active=True,
    ) == (21, "v19")


def test_restored_engine_advances_pending_journey_without_resubmission() -> None:
    snapshot = _snapshot()
    restored = WorldEngine.restore_from_snapshot(snapshot)
    from simulation.bootstrap import WorldBootstrap

    live = WorldEngine(
        config=snapshot.config,
        bootstrap=WorldBootstrap(
            world_id=snapshot.world_id,
            revision=snapshot.revision,
            locations=snapshot.locations,
            bodies=snapshot.bodies,
            items=snapshot.items,
            resources=snapshot.resources,
            weather=snapshot.weather,
            registrations=snapshot.registrations,
            regions_migration=snapshot.regions_migration,
            journeys=snapshot.journeys,
        ),
        run_id=snapshot.run_id,
        start_tick=snapshot.next_tick,
    )
    live_batch = live.observe()
    batch = restored.observe()
    assert batch.observations == live_batch.observations
    assert batch.revision == snapshot.revision
    result = restored.resolve_tick(())
    assert result is not None
    assert any(
        record.event.details.kind == "journey_arrived" for record in result.events
    )
    assert restored._snapshot.world.state.bodies[
        EntityId("body-1")
    ].location_id == EntityId("loc-2")
    assert restored._snapshot.world.state.journeys == {}


@pytest.mark.asyncio
async def test_codec_v19_arrival_retry_is_idempotent() -> None:
    from simulation.service import PersistentSimulationService
    from tests.unit.test_persistent_simulation_service import _FakeJournal

    snapshot = _snapshot()
    journal = _FakeJournal()
    first_engine = WorldEngine.restore_from_snapshot(snapshot)
    first_engine.observe()
    first_service = PersistentSimulationService(first_engine, journal)
    first = await first_service.resolve_tick((), idempotency_key="v19-arrival")

    retry_engine = WorldEngine.restore_from_snapshot(snapshot)
    retry_engine.observe()
    retry_service = PersistentSimulationService(retry_engine, journal)
    retried = await retry_service.resolve_tick((), idempotency_key="v19-arrival")
    assert retried.commit_hash == first.commit_hash
    assert journal.calls == 2
    assert retry_engine._snapshot.world.state.journeys == {}


def test_snapshot_replay_tail_arrival_matches_live_arrival_effect() -> None:
    snapshot = _snapshot()
    journey = snapshot.journeys[0]
    details = JourneyArrived(
        journey.journey_id,
        journey.participant_body_ids,
        journey.origin_location_id,
        journey.destination_location_id,
    )
    event = make_physical_replayable_event(
        event_id=EventId("event-restored-arrival"),
        run_id=snapshot.run_id.value,
        world_id=snapshot.world_id,
        tick=2,
        sequence=0,
        cause=SystemCause(
            RequestId("cause-restored-arrival"),
            SystemEffectFamily.TRAVEL,
            journey.actor_body_id,
            0,
        ),
        resulting_revision=WorldRevision(2),
        details=details,
        occurrence=build_occurrence_context(
            details,
            origin_location_id=None,
            destination_location_id=journey.destination_location_id,
        ),
        schema_version=EVENT_SCHEMA_REPLAY_V21,
    )
    restored = WorldEngine.restore_from_snapshot(
        snapshot,
        events=(event,),
        committed_through_tick=Tick(2),
    )
    assert restored._snapshot.world.state.journeys == {}
    assert restored._snapshot.world.state.bodies[
        EntityId("body-1")
    ].location_id == EntityId("loc-2")


def test_fork_rematerialization_keeps_regions_and_pending_journeys() -> None:
    parent = _snapshot()
    child = rematerialize_snapshot(
        parent,
        child_run_id=RunId("child-run-regions"),
        snapshot_id=SnapshotId("child-snapshot-regions"),
    )
    assert child.regions_migration == parent.regions_migration
    assert child.journeys == parent.journeys
    assert child.run_id == RunId("child-run-regions")
    assert hash_snapshot(child) == child.integrity_hash
    parent_engine = WorldEngine.restore_from_snapshot(parent)
    child_engine = WorldEngine.restore_from_snapshot(child)
    parent_engine.observe()
    child_engine.observe()
    parent_engine.resolve_tick(())
    child_engine.resolve_tick(())
    parent_state = parent_engine._snapshot.world.state
    child_state = child_engine._snapshot.world.state
    assert child_state.regions_migration == parent_state.regions_migration
    assert child_state.journeys == parent_state.journeys == {}
    assert child_state.bodies == parent_state.bodies


def test_runner_bootstrap_snapshot_selects_v19_and_carries_enabled_topology() -> None:
    from simulation.bootstrap import WorldBootstrap
    from simulation.runner import _bootstrap_snapshot

    source = _snapshot()
    bootstrap = WorldBootstrap(
        world_id=source.world_id,
        revision=WorldRevision(0),
        locations=source.locations,
        bodies=source.bodies,
        weather=source.weather,
        registrations=source.registrations,
        regions_migration=source.regions_migration,
    )
    engine = WorldEngine(config=source.config, bootstrap=bootstrap)
    snapshot = _bootstrap_snapshot(engine)
    assert snapshot.event_schema_version == 21
    assert snapshot.persistence_codec_version == "v19"
    assert snapshot.regions_migration == source.regions_migration
    assert snapshot.journeys == ()
