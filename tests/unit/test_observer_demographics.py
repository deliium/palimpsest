"""Detached lifecycle facts stay frozen, cursor-scoped, and channel-explicit."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.journal import hash_snapshot
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.observer_facts import (
    ObjectiveFacts,
    ObjectiveFactsError,
    ObjectiveScene,
    scene_from_facts,
    scene_from_snapshot,
)
from simulation.persistence import (
    PROJECTOR_VERSION,
    PayloadHash,
    SnapshotId,
    WorldSnapshot,
)
from simulation.runner_models import example_population_lifecycle_spec
from tests.simulation_helpers import (
    alive_body,
    make_location,
    weather_for_locations,
)
from world.events import EVENT_SCHEMA_REPLAY_V10
from world.identifiers import EntityId, WorldId, WorldRevision
from world.lifecycle import (
    AgentLifecycleRecord,
    DependencyStatus,
    LifecycleStageId,
    OriginProvenance,
)

pytestmark = pytest.mark.unit

_STAGE = LifecycleStageId("infant")


def _record(body_id: str = "body-1", agent_id: str = "agent-1") -> AgentLifecycleRecord:
    return AgentLifecycleRecord(
        body_id=EntityId(body_id),
        agent_id=agent_id,
        entry_tick=0,
        stage=_STAGE,
        dependency_status=DependencyStatus.DEPENDENT,
        generation_index=0,
        cohort_id="founders",
        provenance=OriginProvenance.BOOTSTRAP,
        assigned_lifespan_ticks=20,
    )


def _registration(
    body_id: str = "body-1", agent_id: str = "agent-1"
) -> AgentRegistration:
    return AgentRegistration(AgentId(agent_id), EntityId(body_id))


def _facts(
    *,
    lifecycle_records: tuple[AgentLifecycleRecord, ...] | None = None,
    records: bool = True,
) -> ObjectiveFacts:
    locations = (make_location("loc-1"),)
    registrations = (_registration(),) if records else ()
    return ObjectiveFacts(
        run_id="run-1",
        world_id="world-1",
        tick=0,
        revision=0,
        locations=locations,
        bodies=(alive_body("body-1"),) if records else (),
        items=(),
        resources=(),
        weather=weather_for_locations(locations),
        registrations=registrations,
        lifecycle_records=lifecycle_records,
    )


def test_absent_lifecycle_is_unknown_not_empty() -> None:
    scene = scene_from_facts(_facts(lifecycle_records=None))
    assert scene.lifecycle_records is None


def test_active_empty_lifecycle_is_an_explicit_empty_tuple() -> None:
    locations = (make_location("loc-1"),)
    facts = ObjectiveFacts(
        run_id="run-empty",
        world_id="world-empty",
        tick=0,
        revision=0,
        locations=locations,
        bodies=(),
        items=(),
        resources=(),
        weather=weather_for_locations(locations),
        registrations=(),
        lifecycle_records=(),
    )
    scene = scene_from_facts(facts)
    assert scene.lifecycle_records == ()


def test_lifecycle_records_are_copied_and_validated() -> None:
    record = _record()
    scene = scene_from_facts(_facts(lifecycle_records=(record,)))
    assert isinstance(scene, ObjectiveScene)
    assert scene.lifecycle_records == (record,)


def test_lifecycle_records_reject_duplicate_body_and_agent() -> None:
    duplicate = (
        _record(),
        _record(body_id="body-1", agent_id="agent-2"),
    )
    with pytest.raises(ObjectiveFactsError) as duplicate_body:
        scene_from_facts(_facts(lifecycle_records=duplicate))
    assert duplicate_body.value.reason_code == "lifecycle_record_duplicate"
    duplicate_agent = (
        _record(),
        _record(body_id="body-2", agent_id="agent-1"),
    )
    with pytest.raises(ObjectiveFactsError) as same_agent:
        scene_from_facts(_facts(lifecycle_records=duplicate_agent))
    assert same_agent.value.reason_code == "lifecycle_record_duplicate"


def test_lifecycle_records_reject_missing_body_and_identity_mismatch() -> None:
    with pytest.raises(ObjectiveFactsError) as missing:
        scene_from_facts(_facts(lifecycle_records=(_record(body_id="body-9"),)))
    assert missing.value.reason_code == "lifecycle_body_missing"
    with pytest.raises(ObjectiveFactsError) as mismatch:
        scene_from_facts(_facts(lifecycle_records=(_record(agent_id="agent-9"),)))
    assert mismatch.value.reason_code == "lifecycle_identity_mismatch"


def _snapshot(
    *,
    lifecycle_records: tuple[AgentLifecycleRecord, ...] = (),
    schema_version: int = EVENT_SCHEMA_REPLAY_V10,
    codec: str = "v7",
) -> WorldSnapshot:
    locations = (make_location("loc-1"),)
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-demographics"),
        run_id=RunId("run-1"),
        world_id=WorldId("world-1"),
        seed=7,
        config=SimulationRunConfig(seed=7),
        registrations=(_registration(),),
        locations=locations,
        bodies=(alive_body("body-1"),),
        items=(),
        resources=(),
        weather=weather_for_locations(locations),
        next_tick=Tick(0),
        revision=WorldRevision(0),
        event_schema_version=schema_version,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=codec,
        derivation_version=DERIVATION_VERSION,
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        lifecycle_records=lifecycle_records,
    )
    return WorldSnapshot(
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


def test_scene_from_snapshot_distinguishes_absent_and_active_empty() -> None:
    assert scene_from_snapshot(_snapshot()).lifecycle_records is None
    active_empty = scene_from_snapshot(_snapshot(), lifecycle_active=True)
    assert active_empty.lifecycle_records == ()
    inactive = scene_from_snapshot(_snapshot(), lifecycle_active=False)
    assert inactive.lifecycle_records is None
    with_records = scene_from_snapshot(_snapshot(lifecycle_records=(_record(),)))
    assert with_records.lifecycle_records == (_record(),)
    with pytest.raises(ObjectiveFactsError) as invalid:
        scene_from_snapshot(
            _snapshot(lifecycle_records=(_record(),)),
            lifecycle_active=False,
        )
    assert invalid.value.reason_code == "lifecycle_records_with_inactive_channel"


def test_engine_facts_expose_absent_and_active_empty_channels() -> None:
    bootstrap = WorldBootstrap(world_id=WorldId("world-1"), revision=WorldRevision(0))
    absent = WorldEngine(
        bootstrap=bootstrap,
        config=SimulationRunConfig(seed=7),
        run_id=RunId("run-absent"),
    )
    tick_before = absent.tick
    revision_before = absent.revision
    assert absent.detached_objective_facts().lifecycle_records is None
    assert absent.tick == tick_before
    assert absent.revision == revision_before

    active = WorldEngine(
        bootstrap=bootstrap,
        config=SimulationRunConfig(seed=7),
        run_id=RunId("run-empty"),
        population_lifecycle=example_population_lifecycle_spec(),
    )
    facts = active.detached_objective_facts()
    assert facts.lifecycle_records == ()
    assert facts.locations == ()


def test_engine_facts_copy_sorted_lifecycle_records(
    caplog: pytest.LogCaptureFixture,
) -> None:
    locations = (make_location("loc-1"),)
    records = (
        _record(body_id="body-2", agent_id="agent-2"),
        _record(body_id="body-1", agent_id="agent-1"),
    )
    engine = WorldEngine(
        bootstrap=WorldBootstrap(
            world_id=WorldId("world-1"),
            revision=WorldRevision(0),
            locations=locations,
            bodies=(alive_body("body-1"), alive_body("body-2")),
            weather=weather_for_locations(locations),
            registrations=(
                _registration("body-1", "agent-1"),
                _registration("body-2", "agent-2"),
            ),
        ),
        config=SimulationRunConfig(seed=7),
        run_id=RunId("run-sorted"),
        population_lifecycle=example_population_lifecycle_spec(),
        lifecycle_records=records,
    )
    with caplog.at_level(logging.DEBUG, logger="simulation.observer_facts"):
        facts = engine.detached_objective_facts()
        scene = scene_from_facts(facts)
    assert facts.lifecycle_records is not None
    assert [item.agent_id for item in facts.lifecycle_records] == [
        "agent-1",
        "agent-2",
    ]
    assert scene.lifecycle_records == facts.lifecycle_records
    assert any("lifecycle_record_count=2" in message for message in caplog.messages)


def test_lifecycle_record_requires_matching_body_not_only_registration() -> None:
    locations = (make_location("loc-1"),)
    facts = ObjectiveFacts(
        run_id="run-1",
        world_id="world-1",
        tick=0,
        revision=0,
        locations=locations,
        bodies=(),
        items=(),
        resources=(),
        weather=weather_for_locations(locations),
        registrations=(_registration(),),
        lifecycle_records=(_record(),),
    )
    with pytest.raises(ObjectiveFactsError) as rejected:
        scene_from_facts(facts)
    assert rejected.value.reason_code == "lifecycle_body_missing"
