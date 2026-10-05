"""KinshipEdgeRecorded schema v11, write-pair priority, bootstrap, projector."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.journal import decode_persistence, encode_persistence, hash_snapshot
from simulation.models import RunId, SimulationRunConfig
from simulation.persistence import (
    PROJECTOR_VERSION,
    PayloadHash,
    SnapshotId,
    WorldSnapshot,
    checkpoint_schema_for_production,
)
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V27,
    AgentCognitionSpec,
    AgentRunnerSpec,
    KinshipBootstrapEdgeSpec,
    KinshipSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_kinship_spec,
)
from simulation.serialization import decode_domain, encode_domain
from tests.simulation_helpers import alive_body, make_location, make_weather
from world._replay import project_events
from world._state import WorldState
from world.effects import SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V10,
    EVENT_SCHEMA_REPLAY_V11,
    KinshipEdgeRecorded,
    build_occurrence_context,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.kinship import parents_of, siblings_of, stable_kinship_edge_id
from world.models import default_physical_rules, non_lethal_physical_rules


def _two_agent_config():
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    agent_a = AgentId("agent-a")
    agent_b = AgentId("agent-b")
    return base_runner_config_from_scenario(
        seed=2705,
        stochastic_identity="cmp-kinship-events",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-kinship-events"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body_a, body_b),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_a,
                entity_id=body_a.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_a),
            ),
            AgentRunnerSpec(
                agent_id=agent_b,
                entity_id=body_b.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_b),
            ),
        ),
        max_ticks=2,
    )


def _kinship_details() -> KinshipEdgeRecorded:
    edge_id = stable_kinship_edge_id(
        parent_agent_id=AgentId("agent-a"),
        child_agent_id=AgentId("agent-b"),
        established_tick=0,
    )
    return KinshipEdgeRecorded(
        parent_agent_id="agent-a",
        child_agent_id="agent-b",
        established_tick=0,
        edge_id=edge_id,
    )


def _event(*, schema_version: int):
    details = _kinship_details()
    return make_physical_replayable_event(
        event_id=EventId("evt-kinship-1"),
        run_id="run-kinship",
        world_id=WorldId("world-kinship-events"),
        tick=0,
        sequence=0,
        cause=SystemCause(
            RequestId("req-kinship-1"),
            SystemEffectFamily.LIFECYCLE,
            EntityId("body-b"),
            0,
        ),
        resulting_revision=WorldRevision(0),
        details=details,
        occurrence=build_occurrence_context(
            details, origin_location_id=EntityId("loc-1")
        ),
        schema_version=schema_version,
    )


def test_checkpoint_schema_kinship_first() -> None:
    assert checkpoint_schema_for_production(
        production_active=False,
        kinship_active=True,
        new_agent_provenance_active=True,
        lifecycle_active=True,
    ) == (EVENT_SCHEMA_REPLAY_V11, "v8")
    assert checkpoint_schema_for_production(
        production_active=True,
        dynamics_active=True,
        artifacts_active=True,
        new_agent_provenance_active=True,
        lifecycle_active=True,
        kinship_active=False,
    ) == (EVENT_SCHEMA_REPLAY_V10, "v7")


def test_kinship_details_require_schema_v11() -> None:
    with pytest.raises(ValueError):
        _event(schema_version=EVENT_SCHEMA_REPLAY_V10)


def test_kinship_edge_recorded_round_trip() -> None:
    event = _event(schema_version=EVENT_SCHEMA_REPLAY_V11)
    decoded = decode_domain(encode_domain(event))
    assert type(decoded.details) is KinshipEdgeRecorded
    assert decoded.details.parent_agent_id == "agent-a"
    assert decoded.details.child_agent_id == "agent-b"
    assert decoded.details.kind == "kinship_edge_recorded"
    assert decoded.schema_version == EVENT_SCHEMA_REPLAY_V11


@pytest.mark.asyncio
async def test_bootstrap_kinship_graph_and_queries() -> None:
    base = _two_agent_config()
    config = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V27,
        v3_capability_flags=V3CapabilityFlags(kinship_inheritance=True),
        kinship=KinshipSpec(
            bootstrap_edges=(
                KinshipBootstrapEdgeSpec(
                    parent_agent_id=AgentId("agent-a"),
                    child_agent_id=AgentId("agent-b"),
                    established_tick=0,
                ),
            )
        ),
    )
    runner = await SimulationRunner.from_config(
        config, run_id=RunId("run-kinship-bootstrap")
    )
    engine = runner._engine
    assert engine.kinship_channel_active is True
    graph = engine.kinship_graph
    assert parents_of(graph, AgentId("agent-b")) == (AgentId("agent-a"),)
    assert siblings_of(graph, AgentId("agent-b")) == ()


def test_kinship_edge_projector_is_world_noop() -> None:
    event = _event(schema_version=EVENT_SCHEMA_REPLAY_V11)
    # Projector path needs tick > 0 relative to empty history; use tick 1.
    details = _kinship_details()
    event = make_physical_replayable_event(
        event_id=EventId("evt-kinship-noop"),
        run_id="run-kinship",
        world_id=WorldId("world-kinship-events"),
        tick=1,
        sequence=0,
        cause=SystemCause(
            RequestId("req-kinship-noop"),
            SystemEffectFamily.LIFECYCLE,
            EntityId("body-b"),
            0,
        ),
        resulting_revision=WorldRevision(0),
        details=details,
        occurrence=build_occurrence_context(
            details, origin_location_id=EntityId("loc-1")
        ),
        schema_version=EVENT_SCHEMA_REPLAY_V11,
    )
    body = alive_body("body-b")
    state = WorldState(
        WorldRevision(0),
        locations=(make_location(),),
        items=(),
        resources=(),
        bodies=(body,),
        weather=(make_weather(),),
    )
    projected = project_events(
        state,
        (event,),
        expected_run_id="run-kinship",
        expected_world_id=WorldId("world-kinship-events"),
    )
    assert projected.revision == WorldRevision(0)


def test_kinship_snapshot_codec_v8_round_trip_and_restore() -> None:
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-kinship-codec"),
        revision=WorldRevision(0),
        locations=(make_location(),),
        bodies=(body_a, body_b),
        weather=(make_weather(),),
        registrations=(
            AgentRegistration(AgentId("agent-a"), body_a.entity_id),
            AgentRegistration(AgentId("agent-b"), body_b.entity_id),
        ),
    )
    kinship = example_kinship_spec(
        parent_agent_id="agent-a",
        child_agent_id="agent-b",
    )
    engine = WorldEngine(
        config=SimulationRunConfig(
            seed=27, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=bootstrap,
        run_id=RunId("run-kinship-codec"),
        kinship_spec=kinship,
    )
    graph = engine.kinship_graph
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-kinship-v8"),
        run_id=engine.run_id,
        world_id=engine.world_id,
        seed=27,
        config=engine._config,
        registrations=engine.ordered_registrations,
        locations=tuple(engine._snapshot.world.state.locations.values()),
        bodies=tuple(engine._snapshot.world.state.bodies.values()),
        items=(),
        resources=(),
        weather=tuple(engine._snapshot.world.state.weather.values()),
        next_tick=Tick(0),
        revision=engine.revision,
        event_schema_version=EVENT_SCHEMA_REPLAY_V11,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version="v8",
        derivation_version="derivation-v3",
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        kinship_edges=graph.edges,  # type: ignore[attr-defined]
    )
    snap = WorldSnapshot(
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
        kinship_edges=draft.kinship_edges,
    )
    encoded = encode_persistence(snap)
    decoded = decode_persistence(encoded, WorldSnapshot)
    assert type(decoded) is WorldSnapshot
    assert decoded.persistence_codec_version == "v8"
    assert len(decoded.kinship_edges) == 1

    restored = WorldEngine.restore_from_snapshot(decoded, kinship_spec=kinship)
    assert restored.kinship_channel_active is True
    assert parents_of(restored.kinship_graph, AgentId("agent-b")) == (
        AgentId("agent-a"),
    )
