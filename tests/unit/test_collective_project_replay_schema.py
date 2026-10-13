"""Replay 19 and codec v17 keep collective projects off the v16 channel."""

from __future__ import annotations

import json
import logging

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.clock import Tick
from simulation.engine import WorldEngine, select_checkpoint_schema
from simulation.journal import (
    PersistenceSerializationError,
    decode_persistence,
    encode_persistence,
    hash_snapshot,
)
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.persistence import (
    EVENT_SCHEMA_REPLAY_V18,
    EVENT_SCHEMA_REPLAY_V19,
    PROJECTOR_VERSION,
    PayloadHash,
    SnapshotId,
    WorldSnapshot,
    checkpoint_schema_for_production,
)
from tests.simulation_helpers import alive_body, make_item, make_location, make_weather
from world._replay import project_events
from world._state import WorldState
from world.collective_projects import (
    CollectiveProject,
    CollectiveProjectKind,
    CollectiveProjectStatus,
    ProjectContribution,
)
from world.effects import ActionCause
from world.events import (
    EVENT_SCHEMA_REPLAY_V19 as WORLD_SCHEMA_19,
)
from world.events import (
    OccurrenceContext,
    ProjectCompleted,
    ProjectContributed,
    ProjectCreated,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.models import non_lethal_physical_rules
from world.production import Structure, StructureKind
from world.values import ItemKind

pytestmark = pytest.mark.unit
_RUN = "run-projects"
_WORLD = WorldId("world-projects")


def test_channel_on_selects_replay_19_ahead_of_profile() -> None:
    pair = checkpoint_schema_for_production(
        production_active=False,
        resource_exchange_profile_active=True,
        collective_projects_active=True,
    )
    assert pair == (EVENT_SCHEMA_REPLAY_V19, "v17")
    agreed = select_checkpoint_schema(
        production_active=False,
        dynamics_active=False,
        resource_exchange_profile_active=True,
        collective_projects_active=True,
    )
    assert agreed == (EVENT_SCHEMA_REPLAY_V19, "v17")


def test_channel_off_does_not_select_v17() -> None:
    pair = checkpoint_schema_for_production(
        production_active=False,
        resource_exchange_profile_active=True,
    )
    assert pair == (EVENT_SCHEMA_REPLAY_V18, "v16")


def _engine() -> WorldEngine:
    alice = alive_body("body-a")
    return WorldEngine(
        config=SimulationRunConfig(seed=19, physical_rules=non_lethal_physical_rules()),
        bootstrap=WorldBootstrap(
            world_id=_WORLD,
            revision=WorldRevision(0),
            locations=(make_location(),),
            bodies=(alice,),
            weather=(make_weather(),),
            registrations=(
                AgentRegistration(AgentId("agent-1"), alice.entity_id),
            ),
        ),
        run_id=RunId(_RUN),
        collective_projects_active=True,
    )


def _snapshot(
    engine: WorldEngine,
    *,
    codec: str,
    schema: int,
    projects: tuple[object, ...] = (),
    structures: tuple[Structure, ...] = (),
) -> WorldSnapshot:
    state = engine._snapshot.world.state
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-projects"),
        run_id=engine.run_id,
        world_id=engine.world_id,
        seed=engine._config.seed,
        config=engine._config,
        registrations=engine._registrations,
        locations=tuple(state.locations.values()),
        bodies=tuple(state.bodies.values()),
        items=tuple(state.items.values()),
        resources=tuple(state.resources.values()),
        weather=tuple(state.weather.values()),
        next_tick=Tick(0),
        revision=engine.revision,
        event_schema_version=schema,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=codec,
        derivation_version=engine._config.derivation_version or DERIVATION_VERSION,
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        structures=structures,
        collective_projects=projects,
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
        structures=draft.structures,
        collective_projects=draft.collective_projects,
    )


def _open_project() -> CollectiveProject:
    return CollectiveProject(
        project_id=EntityId("project-1"),
        location_id=EntityId("loc-1"),
        kind=CollectiveProjectKind.STORAGE,
        status=CollectiveProjectStatus.OPEN,
        labor_done=0,
        labor_required=2,
        materials_done=0,
        materials_required=1,
        opened_tick=0,
        last_accepted_tick=0,
        shortage_count=0,
        contributions=(
            ProjectContribution(
                actor_id=EntityId("body-a"),
                tick=0,
                accepted=True,
                labor_delta=0,
            ),
        ),
    )


def test_v16_rejects_projects_and_new_structure_kinds(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _engine()
    caplog.set_level(logging.WARNING)
    with pytest.raises(ValueError, match="collective_projects require codec v17"):
        _snapshot(
            engine,
            codec="v16",
            schema=EVENT_SCHEMA_REPLAY_V18,
            projects=(_open_project(),),
        )
    assert "collective_projects present on pre-v17 payload" in caplog.text
    caplog.clear()
    bridge = Structure(
        entity_id=EntityId("structure-bridge"),
        location_id=EntityId("loc-1"),
        kind=StructureKind.BRIDGE,
        integrity=1.0,
        stored_quantity=0,
    )
    with pytest.raises(ValueError, match="bridge and record_site require codec v17"):
        _snapshot(
            engine,
            codec="v16",
            schema=EVENT_SCHEMA_REPLAY_V18,
            structures=(bridge,),
        )
    assert "structure kind rejected on pre-v17 payload" in caplog.text


def test_v17_round_trips_a_project(caplog: pytest.LogCaptureFixture) -> None:
    engine = _engine()
    snap = _snapshot(
        engine,
        codec="v17",
        schema=EVENT_SCHEMA_REPLAY_V19,
        projects=(_open_project(),),
    )
    caplog.set_level(logging.DEBUG, logger="simulation.serialization")
    encoded = encode_persistence(snap)
    assert "collective_projects encoded project_count=1" in caplog.text
    decoded = decode_persistence(encoded, WorldSnapshot)
    assert decoded.persistence_codec_version == "v17"
    assert len(decoded.collective_projects) == 1
    assert decoded.collective_projects[0].project_id == EntityId("project-1")
    assert decoded.collective_projects[0].kind is CollectiveProjectKind.STORAGE


def test_v16_payload_with_project_key_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _engine()
    snap = _snapshot(engine, codec="v16", schema=EVENT_SCHEMA_REPLAY_V18)
    document = json.loads(encode_persistence(snap))
    document["data"]["collective_projects"] = []
    caplog.set_level(logging.WARNING, logger="simulation.serialization")
    with pytest.raises(PersistenceSerializationError):
        decode_persistence(json.dumps(document).encode(), WorldSnapshot)
    assert "project_count=0" in caplog.text


def _event(details, *, event_id: str, sequence: int, actor: EntityId):
    return make_physical_replayable_event(
        event_id=EventId(event_id),
        run_id=_RUN,
        world_id=_WORLD,
        tick=1,
        sequence=sequence,
        cause=ActionCause(RequestId(f"req-{event_id}"), actor),
        resulting_revision=WorldRevision(1),
        details=details,
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=WORLD_SCHEMA_19,
    )


def test_replay_rebuilds_storage_counters_and_structure() -> None:
    wood = make_item(
        "wood-1",
        name="wood",
        kind=ItemKind.MATERIAL,
        location_id=None,
        holder_id="body-a",
    )
    actor = alive_body("body-a", inventory=(wood.entity_id,))
    state = WorldState(
        WorldRevision(0),
        locations=(make_location(),),
        bodies=(actor,),
        items=(wood,),
        weather=(make_weather(),),
    )
    project_id = EntityId("project-storage")
    created = ProjectCreated(
        project_id=project_id,
        location_id=EntityId("loc-1"),
        project_kind="storage",
        actor_id=actor.entity_id,
        labor_required=2,
        materials_required=1,
    )
    material = ProjectContributed(
        project_id=project_id,
        actor_id=actor.entity_id,
        accepted=True,
        labor_done=1,
        materials_done=1,
        item_id=wood.entity_id,
    )
    labor = ProjectContributed(
        project_id=project_id,
        actor_id=actor.entity_id,
        accepted=True,
        labor_done=2,
        materials_done=1,
    )
    completed = ProjectCompleted(
        project_id=project_id,
        project_kind="storage",
        structure_id=EntityId(f"structure-{project_id.value}"),
        stored_delta=0,
    )
    after = project_events(
        state,
        (
            _event(created, event_id="evt-created", sequence=0, actor=actor.entity_id),
            _event(material, event_id="evt-wood", sequence=1, actor=actor.entity_id),
            _event(labor, event_id="evt-labor", sequence=2, actor=actor.entity_id),
            _event(completed, event_id="evt-done", sequence=3, actor=actor.entity_id),
        ),
        expected_run_id=_RUN,
        expected_world_id=_WORLD,
    )
    project = after.collective_projects[project_id]
    assert project.status is CollectiveProjectStatus.COMPLETED
    assert project.labor_done == 2
    assert project.materials_done == 1
    assert len(project.contributions) == 3
    assert wood.entity_id not in after.items
    built = after.structures[EntityId(f"structure-{project_id.value}")]
    assert built.kind is StructureKind.STORE
    assert built.stored_quantity == 0


def test_replay_winter_reserve_adds_three() -> None:
    store = Structure(
        entity_id=EntityId("store-a"),
        location_id=EntityId("loc-1"),
        kind=StructureKind.STORE,
        integrity=1.0,
        stored_quantity=1,
    )
    actor = alive_body("body-a")
    state = WorldState(
        WorldRevision(0),
        locations=(make_location(),),
        bodies=(actor,),
        weather=(make_weather(),),
        structures=(store,),
    )
    project_id = EntityId("project-winter")
    created = ProjectCreated(
        project_id=project_id,
        location_id=EntityId("loc-1"),
        project_kind="winter_reserve",
        actor_id=actor.entity_id,
        labor_required=2,
        materials_required=3,
    )
    completed = ProjectCompleted(
        project_id=project_id,
        project_kind="winter_reserve",
        structure_id=store.entity_id,
        stored_delta=3,
    )
    after = project_events(
        state,
        (
            _event(created, event_id="evt-open", sequence=0, actor=actor.entity_id),
            _event(completed, event_id="evt-fill", sequence=1, actor=actor.entity_id),
        ),
        expected_run_id=_RUN,
        expected_world_id=_WORLD,
    )
    project = after.collective_projects[project_id]
    assert project.target_structure_id == store.entity_id
    assert after.structures[store.entity_id].stored_quantity == 4
