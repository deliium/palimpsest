"""Persistence codec v7 pairs with event schema 10 for new-agent provenance."""

from __future__ import annotations

import logging

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.journal import decode_persistence, encode_persistence, hash_snapshot
from simulation.models import RunId, SimulationRunConfig
from simulation.new_agent_initialization import default_new_agent_initialization_spec
from simulation.persistence import (
    PROJECTOR_VERSION,
    PayloadHash,
    SnapshotId,
    WorldSnapshot,
    checkpoint_schema_for_production,
)
from simulation.runner_models import (
    example_population_lifecycle_spec,
    seed_bootstrap_lifecycle_records,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.events import EVENT_SCHEMA_REPLAY_V10
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.new_agent_snapshot_codec_v7")


def test_write_pair_selects_v10_v7_when_provenance_active() -> None:
    _LOG.debug("case_id=write_pair_v7")
    assert checkpoint_schema_for_production(
        production_active=False,
        dynamics_active=False,
        artifacts_active=False,
        lifecycle_active=True,
        new_agent_provenance_active=True,
    ) == (EVENT_SCHEMA_REPLAY_V10, "v7")


def test_codec_v7_round_trip_preserves_lifecycle_records() -> None:
    _LOG.debug("case_id=codec_v7_round_trip")
    body = alive_body("body-1")
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-nai-codec"),
        revision=WorldRevision(0),
        locations=(make_location(),),
        bodies=(body,),
        weather=(make_weather(),),
        registrations=(AgentRegistration(AgentId("agent-1"), body.entity_id),),
    )
    spec = example_population_lifecycle_spec(lifespan_ticks=20)
    records = seed_bootstrap_lifecycle_records(
        registrations=bootstrap.registrations, spec=spec
    )
    init = default_new_agent_initialization_spec()
    engine = WorldEngine(
        config=SimulationRunConfig(
            seed=17, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=bootstrap,
        run_id=RunId("run-nai-codec"),
        population_lifecycle=spec,
        lifecycle_records=records,
        new_agent_initialization=init,
    )
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-nai-v7"),
        run_id=engine.run_id,
        world_id=engine.world_id,
        seed=17,
        config=engine._config,
        registrations=engine.ordered_registrations,
        locations=tuple(engine._snapshot.world.state.locations.values()),
        bodies=tuple(engine._snapshot.world.state.bodies.values()),
        items=(),
        resources=(),
        weather=tuple(engine._snapshot.world.state.weather.values()),
        next_tick=Tick(0),
        revision=engine.revision,
        event_schema_version=EVENT_SCHEMA_REPLAY_V10,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version="v7",
        derivation_version="v3",
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        lifecycle_records=tuple(engine.lifecycle_records),
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
        lifecycle_records=draft.lifecycle_records,
    )
    encoded = encode_persistence(snap)
    restored = decode_persistence(encoded, WorldSnapshot)
    assert type(restored) is WorldSnapshot
    assert restored.persistence_codec_version == "v7"
    assert restored.event_schema_version == EVENT_SCHEMA_REPLAY_V10
    assert len(restored.lifecycle_records) == len(engine.lifecycle_records)
