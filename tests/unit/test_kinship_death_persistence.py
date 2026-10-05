"""Kinship edges survive death and checkpoint restore including dead nodes."""

from __future__ import annotations

import logging
from dataclasses import replace

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.journal import encode_persistence, hash_snapshot
from simulation.lifecycle import ActionSubmission
from simulation.models import RunId, SimulationRunConfig
from simulation.persistence import (
    PROJECTOR_VERSION,
    PayloadHash,
    SnapshotId,
    WorldSnapshot,
)
from simulation.runner_models import example_kinship_spec
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.actions import Attack, Wait
from world.events import EVENT_SCHEMA_REPLAY_V11, Died
from world.identifiers import EntityId, WorldId, WorldRevision
from world.kinship import ancestors_of, parents_of
from world.models import LifeStatus, default_physical_rules

_LOG = logging.getLogger("tests.kinship_death_persistence")


def _lethal_rules():
    return replace(
        default_physical_rules(),
        attack_hit_probability=1.0,
        attack_damage_min=100,
        attack_damage_max_exclusive=101,
    )


def _engine() -> WorldEngine:
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-kinship-death"),
        revision=WorldRevision(0),
        locations=(make_location(),),
        bodies=(body_a, body_b),
        weather=(make_weather(),),
        registrations=(
            AgentRegistration(AgentId("agent-a"), body_a.entity_id),
            AgentRegistration(AgentId("agent-b"), body_b.entity_id),
        ),
    )
    return WorldEngine(
        config=SimulationRunConfig(seed=41, physical_rules=_lethal_rules()),
        bootstrap=bootstrap,
        run_id=RunId("run-kinship-death"),
        kinship_spec=example_kinship_spec(
            parent_agent_id="agent-a",
            child_agent_id="agent-b",
        ),
    )


def _act(engine: WorldEngine, agent_id: str, command: object) -> None:
    batch = engine.observe()
    submissions = []
    for observation in batch.observations:
        agent = engine.registration_translator.to_agent_id(observation.observer_id)
        if agent.value == agent_id:
            submissions.append(ActionSubmission(batch.token, agent, command))
        else:
            submissions.append(ActionSubmission(batch.token, agent, Wait()))
    engine.resolve_tick(tuple(submissions))


def test_edges_survive_parent_death() -> None:
    _LOG.debug("case_id=edges_survive_died")
    engine = _engine()
    assert parents_of(engine.kinship_graph, AgentId("agent-b")) == (
        AgentId("agent-a"),
    )
    parent_body_id = EntityId("body-a")
    _act(engine, "agent-b", Attack(parent_body_id))
    body = engine._snapshot.world.state.bodies[parent_body_id]
    assert body.life_status is LifeStatus.DEAD
    assert parents_of(engine.kinship_graph, AgentId("agent-b")) == (
        AgentId("agent-a"),
    )
    assert ancestors_of(
        engine.kinship_graph,
        AgentId("agent-b"),
        max_depth=4,
        config_max_depth=8,
    ) == (AgentId("agent-a"),)
    assert engine.last_tick_result is not None
    assert any(
        type(record.event.details) is Died
        for record in engine.last_tick_result.events
    )


def test_restore_preserves_edges_involving_dead() -> None:
    _LOG.debug("case_id=restore_dead_kinship")
    engine = _engine()
    parent_body_id = EntityId("body-a")
    _act(engine, "agent-b", Attack(parent_body_id))
    assert (
        engine._snapshot.world.state.bodies[parent_body_id].life_status
        is LifeStatus.DEAD
    )
    kinship = example_kinship_spec(
        parent_agent_id="agent-a",
        child_agent_id="agent-b",
    )
    graph = engine.kinship_graph
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-kinship-death"),
        run_id=engine.run_id,
        world_id=engine.world_id,
        seed=41,
        config=engine._config,
        registrations=engine.ordered_registrations,
        locations=tuple(engine._snapshot.world.state.locations.values()),
        bodies=tuple(engine._snapshot.world.state.bodies.values()),
        items=(),
        resources=(),
        weather=tuple(engine._snapshot.world.state.weather.values()),
        next_tick=engine._snapshot.tick,
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
    encode_persistence(snap)
    restored = WorldEngine.restore_from_snapshot(snap, kinship_spec=kinship)
    assert restored.kinship_channel_active is True
    assert parents_of(restored.kinship_graph, AgentId("agent-b")) == (
        AgentId("agent-a"),
    )
    assert (
        restored._snapshot.world.state.bodies[parent_body_id].life_status
        is LifeStatus.DEAD
    )
