"""Feed/Transport care actions and replay-v12 / codec v9 write-pair."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.clock import Tick
from simulation.engine import WorldEngine, select_checkpoint_schema
from simulation.journal import decode_persistence, encode_persistence, hash_snapshot
from simulation.lifecycle import ActionSubmission
from simulation.models import RunId, SimulationRunConfig
from simulation.persistence import (
    PROJECTOR_VERSION,
    PayloadHash,
    SnapshotId,
    WorldSnapshot,
    checkpoint_schema_for_production,
)
from simulation.runner_models import (
    example_dependency_care_spec,
    example_population_lifecycle_spec,
    seed_bootstrap_lifecycle_records,
)
from tests.simulation_helpers import (
    alive_body,
    connected_locations,
    make_location,
    make_weather,
    weather_for_locations,
)
from world.actions import Feed, Transport
from world.dependency_care import DependencyNeedRegister
from world.events import EVENT_SCHEMA_REPLAY_V11, EVENT_SCHEMA_REPLAY_V12
from world.identifiers import EntityId, WorldId, WorldRevision
from world.lifecycle import DependencyStatus, LifecycleStageId
from world.models import Item, non_lethal_physical_rules
from world.values import Hunger, ItemKind, ItemLoad

_LOG = logging.getLogger("tests.dependency_care_actions_replay")


def _care_engine(
    *, allow_feed: bool = True, allow_transport: bool = True
) -> WorldEngine:
    caregiver = alive_body("body-care", inventory=(EntityId("item-food"),))
    dependent = replace(
        alive_body("body-dep"),
        hunger=Hunger(40.0),
    )
    food = Item(
        entity_id=EntityId("item-food"),
        name="Food",
        kind=ItemKind.FOOD,
        location_id=None,
        holder_id=caregiver.entity_id,
        load=ItemLoad(1),
    )
    loc_a, loc_b = connected_locations(("loc-1", "A"), ("loc-2", "B"))
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-dep-care-act"),
        revision=WorldRevision(0),
        locations=(loc_a, loc_b),
        bodies=(caregiver, dependent),
        weather=weather_for_locations((loc_a, loc_b)),
        items=(food,),
        registrations=(
            AgentRegistration(AgentId("agent-care"), caregiver.entity_id),
            AgentRegistration(AgentId("agent-dep"), dependent.entity_id),
        ),
    )
    spec = example_population_lifecycle_spec(lifespan_ticks=40, max_population=4)
    records = seed_bootstrap_lifecycle_records(
        registrations=bootstrap.registrations, spec=spec
    )
    care_record = replace(
        records[0],
        stage=LifecycleStageId("adult"),
        dependency_status=DependencyStatus.INDEPENDENT,
    )
    dep_record = replace(
        records[1],
        stage=LifecycleStageId("infant"),
        dependency_status=DependencyStatus.DEPENDENT,
    )
    care = example_dependency_care_spec(
        allow_feed=allow_feed, allow_transport=allow_transport
    )
    return WorldEngine(
        config=SimulationRunConfig(
            seed=61, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=bootstrap,
        population_lifecycle=spec,
        lifecycle_records=(care_record, dep_record),
        dependency_care_spec=care,
    )


def test_checkpoint_schema_dependency_care_takes_priority() -> None:
    assert checkpoint_schema_for_production(
        production_active=False,
        dynamics_active=False,
        lifecycle_active=True,
        kinship_active=True,
        dependency_care_active=True,
    ) == (EVENT_SCHEMA_REPLAY_V12, "v9")
    assert select_checkpoint_schema(
        production_active=False,
        dynamics_active=False,
        lifecycle_active=True,
        kinship_active=True,
        dependency_care_active=True,
    ) == (EVENT_SCHEMA_REPLAY_V12, "v9")
    assert checkpoint_schema_for_production(
        production_active=False,
        dynamics_active=False,
        lifecycle_active=True,
        kinship_active=True,
        dependency_care_active=False,
    ) == (EVENT_SCHEMA_REPLAY_V11, "v8")


def test_feed_relieves_dependent_hunger(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _care_engine()
    dep_before = engine._snapshot.world.state.bodies[EntityId("body-dep")].hunger.value
    batch = engine.observe()
    with caplog.at_level(logging.INFO, logger="world._operations"):
        commit = engine.resolve_tick(
            (
                ActionSubmission(
                    batch.token,
                    AgentId("agent-care"),
                    Feed(EntityId("body-dep"), EntityId("item-food")),
                ),
            )
        )
    assert commit is not None
    dep_after = engine._snapshot.world.state.bodies[EntityId("body-dep")].hunger.value
    assert dep_after < dep_before
    assert EntityId("item-food") not in engine._snapshot.world.state.items
    assert any("dependency_care_mutate" in rec.message for rec in caplog.records)
    kinds = {record.event.details.kind for record in commit.events}
    assert "feed" in kinds


def test_transport_moves_caregiver_and_dependent() -> None:
    engine = _care_engine()
    dest = EntityId("loc-2")
    batch = engine.observe()
    engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-care"),
                Transport(EntityId("body-dep"), dest),
            ),
        )
    )
    state = engine._snapshot.world.state
    assert state.bodies[EntityId("body-care")].location_id == dest
    assert state.bodies[EntityId("body-dep")].location_id == dest


def test_feed_rejects_when_channel_off(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Rebuild without dependency_care by clearing channel via new engine.
    body = alive_body("body-1", inventory=(EntityId("item-food"),))
    other = alive_body("body-2")
    food = Item(
        entity_id=EntityId("item-food"),
        name="Food",
        kind=ItemKind.FOOD,
        location_id=None,
        holder_id=body.entity_id,
        load=ItemLoad(1),
    )
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-dep-off"),
        revision=WorldRevision(0),
        locations=(make_location(body_capacity=8),),
        bodies=(body, other),
        weather=(make_weather(),),
        items=(food,),
        registrations=(
            AgentRegistration(AgentId("agent-1"), body.entity_id),
            AgentRegistration(AgentId("agent-2"), other.entity_id),
        ),
    )
    engine = WorldEngine(
        config=SimulationRunConfig(
            seed=62, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=bootstrap,
    )
    batch = engine.observe()
    with caplog.at_level(logging.WARNING, logger="world._operations"):
        commit = engine.resolve_tick(
            (
                ActionSubmission(
                    batch.token,
                    AgentId("agent-1"),
                    Feed(EntityId("body-2"), EntityId("item-food")),
                ),
            )
        )
    assert all(record.event.details.kind != "feed" for record in commit.events)
    assert any(
        "dependency_care_reject" in rec.message
        and "dependency_care_channel_off" in rec.message
        for rec in caplog.records
    )


def test_codec_v9_round_trips_dependency_need_registers() -> None:
    engine = _care_engine()
    agent_id = AgentId("agent-dep")
    engine._dependency_need_registers[agent_id] = DependencyNeedRegister(
        agent_id=agent_id,
        deficits={"learning": 0.25},
    )
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-dep-v9"),
        run_id=RunId("run-dep-v9"),
        world_id=engine.world_id,
        seed=engine._config.seed,
        config=engine._config,
        registrations=engine._registrations,
        locations=tuple(engine._snapshot.world.state.locations.values()),
        bodies=tuple(engine._snapshot.world.state.bodies.values()),
        items=tuple(engine._snapshot.world.state.items.values()),
        resources=(),
        weather=tuple(engine._snapshot.world.state.weather.values()),
        next_tick=Tick(0),
        revision=engine.revision,
        event_schema_version=EVENT_SCHEMA_REPLAY_V12,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version="v9",
        derivation_version="v3",
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        lifecycle_records=engine.lifecycle_records,
        kinship_edges=(),
        dependency_need_registers=tuple(engine._dependency_need_registers.values()),
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
        kinship_edges=draft.kinship_edges,
        dependency_need_registers=draft.dependency_need_registers,
    )
    encoded = encode_persistence(snap)
    decoded = decode_persistence(encoded, WorldSnapshot)
    assert decoded.persistence_codec_version == "v9"
    assert len(decoded.dependency_need_registers) == 1
    register = decoded.dependency_need_registers[0]
    assert type(register) is DependencyNeedRegister
    assert register.deficits == {"learning": 0.25}
    _LOG.debug("codec_v9_round_trip ok register_count=1")


def test_feed_event_uses_replay_v12_schema() -> None:
    engine = _care_engine()
    batch = engine.observe()
    commit = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-care"),
                Feed(EntityId("body-dep"), EntityId("item-food")),
            ),
        )
    )
    feed_events = [
        record.event for record in commit.events if record.event.details.kind == "feed"
    ]
    assert len(feed_events) == 1
    assert feed_events[0].schema_version == EVENT_SCHEMA_REPLAY_V12
    assert feed_events[0].details.item_kind == "food"
    assert feed_events[0].details.hunger_delta is not None
