"""Codec-v19 persistence and continuation replay for a pending journey."""

from __future__ import annotations

import uuid

import pytest
from tests.simulation_helpers import (
    alive_body,
    connected_locations,
    weather_for_locations,
)

from agents.models import AgentId
from infrastructure.database import DatabaseResources
from persistence import (
    create_analysis_evidence_loader,
    create_run_repository,
    create_snapshot_repository,
    create_tick_journal_repository,
)
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from simulation.models import RunId, SimulationRunConfig
from simulation.persistence import (
    ReplayMode,
    ReplayRequest,
    ReplayStatus,
    RunCreateRequest,
    SnapshotId,
)
from simulation.replay import ReplayService
from simulation.runner import _bootstrap_snapshot
from simulation.service import PersistentSimulationService
from world.actions import Move
from world.events import JourneyArrived, JourneyStarted
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import non_lethal_physical_rules
from world.regions import (
    CognitionMode,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)

pytestmark = pytest.mark.integration


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


async def test_pending_journey_checkpoint_resume_and_tail_replay(
    database_resources: DatabaseResources,
) -> None:
    factory = database_resources.session_factory
    runs = create_run_repository(factory)
    journal = create_tick_journal_repository(factory)
    snapshots = create_snapshot_repository(factory)
    run_id = RunId(_unique("run-regional"))
    world_id = WorldId(_unique("world-regional"))
    locations = connected_locations(("loc-1", "Origin"), ("loc-2", "Destination"))
    body = alive_body("body-1", location_id="loc-1")
    registrations = (AgentRegistration(AgentId("agent-1"), body.entity_id),)
    spec = RegionsMigrationSpec(
        regions=(RegionDefinition("origin", "Origin"), RegionDefinition("far", "Far")),
        location_regions=(
            LocationRegion(EntityId("loc-1"), "origin"),
            LocationRegion(EntityId("loc-2"), "far"),
        ),
        routes=(RouteSpec(EntityId("loc-1"), EntityId("loc-2"), 2, 3),),
        max_arrival_wait_ticks=1,
        residence_min_ticks=2,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )
    config = SimulationRunConfig(seed=87, physical_rules=non_lethal_physical_rules())
    engine = WorldEngine(
        config=config,
        bootstrap=WorldBootstrap(
            world_id=world_id,
            revision=WorldRevision(0),
            locations=locations,
            bodies=(body,),
            weather=weather_for_locations(locations),
            registrations=registrations,
            regions_migration=spec,
        ),
        run_id=run_id,
    )
    bootstrap = _bootstrap_snapshot(engine)
    await runs.create_run(
        RunCreateRequest(
            run_id=run_id,
            world_id=world_id,
            seed=config.seed,
            config=config,
            bootstrap=bootstrap,
            event_schema_version=bootstrap.event_schema_version,
            projector_version=bootstrap.projector_version,
            persistence_codec_version=bootstrap.persistence_codec_version,
            derivation_version=bootstrap.derivation_version,
        )
    )
    service = PersistentSimulationService(engine, journal)

    observed = engine.observe()
    committed = await service.resolve_tick(
        (
            ActionSubmission(
                observed.token,
                AgentId("agent-1"),
                Move(EntityId("loc-2")),
            ),
        ),
        checkpoint_id=SnapshotId(_unique("journey-snapshot")),
    )
    assert any(
        isinstance(record.event.details, JourneyStarted)
        for record in engine._last_tick_result.events
    )
    assert committed.snapshot_id is not None
    mid = await snapshots.get_snapshot(committed.snapshot_id)
    assert mid is not None
    assert mid.persistence_codec_version == "v19"
    assert mid.regions_migration == spec
    assert len(mid.journeys or ()) == 1

    engine.observe()
    await service.resolve_tick(())
    assert any(
        isinstance(record.event.details, JourneyArrived)
        for record in engine._last_tick_result.events
    )
    live_state = engine._snapshot.world.state

    replay = ReplayService(runs, journal, snapshots)
    continuation = await replay.replay(ReplayRequest(run_id=run_id, target_tick=None))
    assert continuation.result.status is ReplayStatus.OK
    assert continuation.result.mode is ReplayMode.CONTINUATION
    assert continuation.engine is not None
    resumed_state = continuation.engine._snapshot.world.state
    assert resumed_state.regions_migration == live_state.regions_migration
    assert resumed_state.journeys == live_state.journeys == {}
    assert resumed_state.bodies == live_state.bodies

    evidence_reader = create_analysis_evidence_loader(factory)
    detached = await evidence_reader.load(
        run_id=run_id.value,
        owner_id="agent-1",
    )
    assert detached.regional_context is not None
    assert detached.regional_context.residence_min_ticks == spec.residence_min_ticks
    assert detached.regional_context.initial_placements[0].location_id == "loc-1"
    assert detached.objective_complete_through_boundary == 2

    from experiments.composition import regional_population_input_from_snapshot
    from simulation.evidence import EvidenceHighWaterMarks, build_evidence_manifest

    prefix_manifest = build_evidence_manifest(
        run_id=run_id.value,
        objective_commit_hash=committed.commit_hash.value,
        high_water=EvidenceHighWaterMarks(
            direct_memories=0,
            communicated_memories=0,
            reconstructions=0,
            beliefs=0,
            relationships=0,
            goals=0,
            resolutions=0,
            truth_specs=0,
        ),
    )
    prefix = await evidence_reader.load(
        run_id=run_id.value,
        owner_id="agent-1",
        manifest=prefix_manifest,
    )
    assert prefix.objective_complete_through_boundary == 1
    assert all(event.tick == 0 for event in prefix.events)
    prefix_inputs = regional_population_input_from_snapshot(
        prefix,
        input_revision="regional-prefix",
        window_end=2,
    )
    assert prefix_inputs is not None
    assert prefix_inputs.complete_through_boundary == 1
