"""Codec-v20 checkpoints preserve v19 region payloads and contact events."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration
from simulation.clock import Tick
from simulation.journal import decode_persistence, encode_persistence, hash_snapshot
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.persistence import (
    PROJECTOR_VERSION,
    PayloadHash,
    SnapshotId,
    WorldSnapshot,
)
from tests.simulation_helpers import (
    alive_body,
    connected_locations,
    weather_for_locations,
)
from world.events import EVENT_SCHEMA_REPLAY_V22
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules
from world.regions import (
    CognitionMode,
    Journey,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)


def _v20_snapshot() -> WorldSnapshot:
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
    journey = Journey(
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
    )
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snapshot-contact"),
        run_id=RunId("run-contact"),
        world_id=WorldId("world-contact"),
        seed=7,
        config=SimulationRunConfig(seed=7, physical_rules=default_physical_rules()),
        registrations=(AgentRegistration(AgentId("agent-1"), body.entity_id),),
        locations=locations,
        bodies=(body,),
        items=(),
        resources=(),
        weather=weather_for_locations(locations),
        next_tick=Tick(2),
        revision=WorldRevision(1),
        event_schema_version=EVENT_SCHEMA_REPLAY_V22,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version="v20",
        derivation_version=DERIVATION_VERSION,
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        regions_migration=spec,
        journeys=(journey,),
    )
    return replace(draft, integrity_hash=hash_snapshot(draft))


def test_codec_v20_round_trips_regions_and_journeys() -> None:
    snapshot = _v20_snapshot()
    decoded = cast(
        WorldSnapshot, decode_persistence(encode_persistence(snapshot), WorldSnapshot)
    )
    assert decoded.persistence_codec_version == "v20"
    assert decoded.event_schema_version == EVENT_SCHEMA_REPLAY_V22
    assert decoded.regions_migration == snapshot.regions_migration
    assert decoded.journeys == snapshot.journeys
