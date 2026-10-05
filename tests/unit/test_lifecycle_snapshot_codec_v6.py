"""Persistence codec v6 round-trip for lifecycle records."""

from __future__ import annotations

import logging

from agents.models import AgentId
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
from simulation.runner_models import (
    example_population_lifecycle_spec,
    seed_bootstrap_lifecycle_records,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.events import EVENT_SCHEMA_REPLAY_V9
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.lifecycle_snapshot_codec_v6")


def test_write_pair_selects_v9_v6_when_lifecycle_active() -> None:
    _LOG.debug("case_id=write_pair_v6")
    assert checkpoint_schema_for_production(
        production_active=False,
        dynamics_active=False,
        artifacts_active=False,
        lifecycle_active=True,
    ) == (EVENT_SCHEMA_REPLAY_V9, "v6")


def test_lifecycle_snapshot_round_trip_and_restore() -> None:
    _LOG.debug("case_id=codec_v6_round_trip")
    body = alive_body("body-1")
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-lifecycle-codec"),
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
    engine = WorldEngine(
        config=SimulationRunConfig(
            seed=13, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=bootstrap,
        run_id=RunId("run-lifecycle-codec"),
        population_lifecycle=spec,
        lifecycle_records=records,
    )
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-lifecycle-v6"),
        run_id=engine.run_id,
        world_id=engine.world_id,
        seed=13,
        config=engine._config,
        registrations=engine.ordered_registrations,
        locations=tuple(engine._snapshot.world.state.locations.values()),
        bodies=tuple(engine._snapshot.world.state.bodies.values()),
        items=(),
        resources=(),
        weather=tuple(engine._snapshot.world.state.weather.values()),
        next_tick=Tick(0),
        revision=engine.revision,
        event_schema_version=EVENT_SCHEMA_REPLAY_V9,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version="v6",
        derivation_version="derivation-v3",
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        lifecycle_records=engine.lifecycle_records,
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
    decoded = decode_persistence(encoded, WorldSnapshot)
    assert type(decoded) is WorldSnapshot
    assert decoded.persistence_codec_version == "v6"
    assert len(decoded.lifecycle_records) == 1
    assert decoded.lifecycle_records[0].cohort_id == "cohort-bootstrap"

    restored = WorldEngine.restore_from_snapshot(
        decoded, population_lifecycle=spec
    )
    assert restored.lifecycle_channel_active is True
    assert len(restored.lifecycle_records) == 1
    assert restored.lifecycle_records[0].stage.value == "infant"


def _lifecycle_snapshot() -> tuple[WorldSnapshot, object]:
    body = alive_body("body-1")
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-lifecycle-fork"),
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
    engine = WorldEngine(
        config=SimulationRunConfig(
            seed=19, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=bootstrap,
        run_id=RunId("run-lifecycle-fork-parent"),
        population_lifecycle=spec,
        lifecycle_records=records,
    )
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-lifecycle-fork"),
        run_id=engine.run_id,
        world_id=engine.world_id,
        seed=19,
        config=engine._config,
        registrations=engine.ordered_registrations,
        locations=tuple(engine._snapshot.world.state.locations.values()),
        bodies=tuple(engine._snapshot.world.state.bodies.values()),
        items=(),
        resources=(),
        weather=tuple(engine._snapshot.world.state.weather.values()),
        next_tick=Tick(0),
        revision=engine.revision,
        event_schema_version=EVENT_SCHEMA_REPLAY_V9,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version="v6",
        derivation_version="derivation-v3",
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        lifecycle_records=engine.lifecycle_records,
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
    return snap, spec


def test_research_fork_rematerialize_preserves_lifecycle_records() -> None:
    from simulation.branch_service import rematerialize_snapshot

    _LOG.debug("case_id=research_fork_lifecycle_preserve")
    parent, spec = _lifecycle_snapshot()
    child = rematerialize_snapshot(
        parent,
        child_run_id=RunId("run-lifecycle-fork-child"),
        snapshot_id=SnapshotId("snap-lifecycle-fork-child"),
    )
    assert child.run_id.value == "run-lifecycle-fork-child"
    assert child.persistence_codec_version == "v6"
    assert len(child.lifecycle_records) == len(parent.lifecycle_records)
    assert child.lifecycle_records[0].cohort_id == parent.lifecycle_records[0].cohort_id
    assert child.registrations == parent.registrations
    restored = WorldEngine.restore_from_snapshot(
        child, population_lifecycle=spec
    )
    assert restored.lifecycle_channel_active is True
    assert len(restored.lifecycle_records) == 1
    assert restored.ordered_registrations == parent.registrations


def test_codec_v6_restore_requires_population_lifecycle_spec() -> None:
    import pytest

    _LOG.debug("case_id=restore_missing_lifecycle_spec")
    snap, _spec = _lifecycle_snapshot()
    with pytest.raises(ValueError, match="lifecycle_restore_missing_spec"):
        WorldEngine.restore_from_snapshot(snap)


def test_replay_request_carries_population_lifecycle() -> None:
    from simulation.clock import Tick as ReplayTick
    from simulation.persistence import ReplayRequest

    _LOG.debug("case_id=replay_request_lifecycle_field")
    _snap, spec = _lifecycle_snapshot()
    request = ReplayRequest(
        run_id=RunId("run-lifecycle-replay-req"),
        target_tick=ReplayTick(0),
        population_lifecycle=spec,
    )
    assert request.population_lifecycle is spec
