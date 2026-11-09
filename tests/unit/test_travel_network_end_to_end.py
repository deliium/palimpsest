"""V4-17 in-process travel-network end-to-end proof."""

from __future__ import annotations

from typing import cast

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.journal import decode_persistence, encode_persistence, hash_snapshot
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.persistence import (
    PROJECTOR_VERSION,
    PayloadHash,
    SnapshotId,
    WorldSnapshot,
    checkpoint_schema_for_production,
)
from simulation.runner_models import V4CapabilityFlags
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.actions import Move, Wait
from world.environment import Season, scarcity_scenario_dynamics
from world.events import JourneyStarted
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import non_lethal_physical_rules
from world.regions import (
    CognitionMode,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)
from world.travel_network import RouteStatus

pytestmark = pytest.mark.unit

A = EntityId("loc-a")
B = EntityId("loc-b")


def _engine() -> WorldEngine:
    spec = RegionsMigrationSpec(
        regions=(RegionDefinition("west", "West"), RegionDefinition("east", "East")),
        location_regions=(LocationRegion(A, "west"), LocationRegion(B, "east")),
        routes=(RouteSpec(A, B, 2, 3.0),),
        max_arrival_wait_ticks=2,
        residence_min_ticks=2,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-travel-e2e"),
        revision=WorldRevision(0),
        locations=(
            make_location("loc-a", adjacent=("loc-b",)),
            make_location("loc-b", adjacent=("loc-a",)),
        ),
        bodies=(alive_body("body-1", location_id="loc-a"),),
        weather=(make_weather("loc-a"), make_weather("loc-b")),
        registrations=(AgentRegistration(AgentId("agent-1"), EntityId("body-1")),),
        regions_migration=spec,
    )
    return WorldEngine(
        config=SimulationRunConfig(seed=23, physical_rules=non_lethal_physical_rules()),
        bootstrap=bootstrap,
        run_id=RunId("run-travel-e2e"),
        environmental_dynamics=scarcity_scenario_dynamics(),
        collective_projects_active=True,
        infrastructure_networks_active=True,
        travel_network_active=True,
    )


def _wait_tick(engine: WorldEngine) -> None:
    observation = engine.observe()
    engine.resolve_tick(
        (ActionSubmission(observation.token, AgentId("agent-1"), Wait()),)
    )


def test_route_channel_seeds_transitions_and_rejects_closed_move() -> None:
    engine = _engine()
    assert engine.travel_network_active is True
    initial = engine._snapshot.world.state.route_condition(A, B)
    assert initial is not None
    assert initial.status is RouteStatus.OPEN
    assert initial.duration_ticks == 2

    for _ in range(8):
        _wait_tick(engine)
    autumn = engine._snapshot.world.state.route_condition(A, B)
    assert autumn is not None
    assert autumn.status is RouteStatus.RESTRICTED

    for _ in range(4):
        _wait_tick(engine)
    assert (
        engine._snapshot.world.state.regions_migration is not None
        and engine._snapshot.tick.value >= 12
    )
    _wait_tick(engine)
    winter = engine._snapshot.world.state.route_condition(A, B)
    assert winter is not None
    assert winter.status is RouteStatus.CLOSED

    from world.events import RouteConditionChanged

    route_events = [
        event.details
        for event in engine.export_events().events
        if isinstance(event.details, RouteConditionChanged)
    ]
    assert route_events
    assert any(event.current_status == "closed" for event in route_events)

    batch = engine.observe()
    observation = batch.observations[0]
    exit_row = next(item for item in observation.exits if item.destination_id == B)
    assert exit_row.route_status == "closed"


def test_real_move_uses_condition_and_closed_route_rejects() -> None:
    engine = _engine()
    batch = engine.observe()
    result = engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId("agent-1"), Move(B)),)
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    events = engine.export_events().events
    journeys = [
        event.details
        for event in events
        if isinstance(event.details, JourneyStarted)
    ]
    assert journeys
    assert journeys[0].journey.destination_location_id == B

    for _ in range(3):
        _wait_tick(engine)
    assert engine._snapshot.world.state.bodies[EntityId("body-1")].location_id == B

    closed_engine = _engine()
    for _ in range(13):
        _wait_tick(closed_engine)
    winter = closed_engine._snapshot.world.state.route_condition(A, B)
    assert winter is not None and winter.status is RouteStatus.CLOSED
    closed_batch = closed_engine.observe()
    closed_result = closed_engine.resolve_tick(
        (ActionSubmission(closed_batch.token, AgentId("agent-1"), Move(B)),)
    )
    assert closed_result.resolutions[0].status is ActionResolutionStatus.REJECTED


def test_v25_snapshot_round_trips_route_channel() -> None:
    from dataclasses import replace as dataclass_replace

    engine = _engine()
    state = engine._snapshot.world.state
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snapshot-travel-e2e"),
        run_id=RunId("run-travel-e2e"),
        world_id=WorldId("world-travel-e2e"),
        seed=23,
        config=engine._config,
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
        ),
        locations=tuple(state.locations.values()),
        bodies=tuple(state.bodies.values()),
        items=(),
        resources=(),
        weather=tuple(state.weather.values()),
        next_tick=Tick(0),
        revision=state.revision,
        event_schema_version=27,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version="v25",
        derivation_version=DERIVATION_VERSION,
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        regions_migration=state.regions_migration,
        journeys=(),
        infrastructure=(),
        travel_network=tuple(state.travel_network),
    )
    snapshot = dataclass_replace(draft, integrity_hash=hash_snapshot(draft))
    decoded = cast(
        WorldSnapshot,
        decode_persistence(encode_persistence(snapshot), expected_type=WorldSnapshot),
    )
    assert decoded.travel_network == snapshot.travel_network
    restored = WorldEngine.restore_from_snapshot(
        decoded,
        environmental_dynamics=scarcity_scenario_dynamics(),
    )
    live_exits = engine.observe().observations[0].exits
    restored_exits = restored.observe().observations[0].exits
    assert restored_exits == live_exits


def test_engine_state_route_quality_reads_operational_road() -> None:
    from world._state import rebuild_world_state
    from world.infrastructure import (
        InfrastructureAsset,
        InfrastructureKind,
        InfrastructureStatus,
        InfrastructureTopology,
    )
    from world.travel_network import derive_route_condition

    engine = _engine()
    state = engine._snapshot.world.state
    road = InfrastructureAsset(
        asset_id=EntityId("infra-road"),
        kind=InfrastructureKind.ROAD,
        topology=InfrastructureTopology.EDGE,
        status=InfrastructureStatus.OPERATIONAL,
        integrity=0.9,
        location_id=A,
        endpoint_location_id=B,
        linked_structure_id=None,
        linked_project_id=EntityId("proj-road"),
        created_tick=0,
        last_maintained_tick=0,
    )
    with_road = rebuild_world_state(
        state, infrastructure={road.asset_id: road}
    )
    route = derive_route_condition(
        with_road, A, B, season=Season.SPRING, tick=0
    )
    assert route.infrastructure_quality == pytest.approx(0.9)
    assert route.capacity == 10
    assert route.duration_ticks <= 2


def test_snapshot_v2_carries_engine_route_rows() -> None:
    from experiments.infrastructure_completed_run import (
        build_completed_run_infrastructure_networks_analysis,
        compose_infrastructure_networks_snapshot,
    )

    engine = _engine()
    state = engine._snapshot.world.state
    analysis = build_completed_run_infrastructure_networks_analysis(
        (), routes=state.travel_network
    )
    snapshot = compose_infrastructure_networks_snapshot(
        analysis, run_id="run-travel-e2e"
    )
    assert snapshot.schema_version == "infrastructure-networks-snapshot-v2"
    assert snapshot.routes
    assert snapshot.routes[0].origin_location_id == "loc-a"


def test_checkpoint_selector_uses_travel_pair() -> None:
    assert checkpoint_schema_for_production(
        production_active=False, travel_network_active=True
    ) == (27, "v25")
    flags = V4CapabilityFlags(infrastructure_networks=True)
    assert flags.owned_enabled_names() == ("infrastructure_networks",)
    assert Season.WINTER.value == "winter"
