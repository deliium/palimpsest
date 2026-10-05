"""Dual-key lifecycle checkpoint assigned_lifespan_ticks encode/decode."""

from __future__ import annotations

import logging

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.journal import (
    consume_pending_assigned_lifespan_synthesis,
    decode_persistence,
    encode_persistence,
    hash_snapshot,
)
from simulation.models import RunId, SimulationRunConfig
from simulation.persistence import (
    PROJECTOR_VERSION,
    PayloadHash,
    SnapshotId,
    WorldSnapshot,
)
from simulation.runner_models import (
    example_population_lifecycle_spec,
    seed_bootstrap_lifecycle_records,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.events import EVENT_SCHEMA_REPLAY_V9
from world.identifiers import WorldId, WorldRevision
from world.lifecycle import AgentLifecycleRecord
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.lifecycle_snapshot_assigned_lifespan")


def test_new_snapshot_round_trips_assigned_lifespan() -> None:
    _LOG.debug("case_id=round_trip_assigned")
    body = alive_body("body-1")
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-assigned-lifespan"),
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
    assert records[0].assigned_lifespan_ticks == 20
    engine = WorldEngine(
        config=SimulationRunConfig(
            seed=13, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=bootstrap,
        run_id=RunId("run-assigned-lifespan"),
        population_lifecycle=spec,
        lifecycle_records=records,
    )
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-assigned"),
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
    decoded = decode_persistence(encode_persistence(snap), WorldSnapshot)
    assert type(decoded) is WorldSnapshot
    assert decoded.lifecycle_records[0].assigned_lifespan_ticks == 20
    restored = WorldEngine.restore_from_snapshot(
        decoded, population_lifecycle=spec
    )
    assert restored.lifecycle_records[0].assigned_lifespan_ticks == 20


def test_legacy_keyset_synthesizes_run_lifespan_on_restore() -> None:
    _LOG.debug("case_id=legacy_synthesize_on_restore")
    consume_pending_assigned_lifespan_synthesis()
    from simulation.journal import _decode_lifecycle_record

    legacy = {
        "agent_id": "agent-1",
        "body_id": "body-1",
        "cohort_id": "cohort-bootstrap",
        "dependency_status": "dependent",
        "entry_tick": 0,
        "generation_index": 0,
        "provenance": "bootstrap",
        "stage": "infant",
    }
    record = _decode_lifecycle_record(legacy, path="$.test")
    assert isinstance(record, AgentLifecycleRecord)
    assert record.assigned_lifespan_ticks == 1
    pending = consume_pending_assigned_lifespan_synthesis()
    assert "body-1" in pending

    # Re-decode and restore through engine so pending synthesis remaps.
    consume_pending_assigned_lifespan_synthesis()
    record2 = _decode_lifecycle_record(legacy, path="$.test")
    body = alive_body("body-1")
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-legacy-assigned"),
        revision=WorldRevision(0),
        locations=(make_location(),),
        bodies=(body,),
        weather=(make_weather(),),
        registrations=(AgentRegistration(AgentId("agent-1"), body.entity_id),),
    )
    spec = example_population_lifecycle_spec(lifespan_ticks=20)
    engine = WorldEngine(
        config=SimulationRunConfig(
            seed=5, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=bootstrap,
        run_id=RunId("run-legacy-assigned"),
        population_lifecycle=spec,
        lifecycle_records=(record2,),
    )
    # Direct construct does not synthesize; restore path does.
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-legacy"),
        run_id=engine.run_id,
        world_id=engine.world_id,
        seed=5,
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
        integrity_hash=PayloadHash("b" * 64),
        predecessor_commit_hash=None,
        lifecycle_records=(record2,),
    )
    # Manually encode with legacy key set by stripping assigned from JSON.
    import json

    encoded = encode_persistence(
        WorldSnapshot(
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
    )
    document = json.loads(encoded.decode("utf-8"))
    for item in document["data"]["lifecycle_records"]:
        item.pop("assigned_lifespan_ticks", None)
    legacy_bytes = json.dumps(document, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    decoded = decode_persistence(legacy_bytes, WorldSnapshot)
    restored = WorldEngine.restore_from_snapshot(
        decoded, population_lifecycle=spec
    )
    assert restored.lifecycle_records[0].assigned_lifespan_ticks == 20
