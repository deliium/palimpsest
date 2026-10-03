"""Artifact write-pair selection and codec-v5 checkpoint folds."""

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
from simulation.lifecycle import ActionSubmission
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.persistence import (
    ACCEPTED_PERSISTENCE_CODEC_VERSIONS,
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    PayloadHash,
    RunCreateRequest,
    SnapshotId,
    WorldSnapshot,
    checkpoint_schema_for_production,
    schema_projector_compatible,
)
from tests.physical_helpers import physical_config, two_location_fixture
from tests.simulation_helpers import alive_body, make_item, make_location, make_weather
from world._replay import project_events
from world.actions import Build, Inscribe, Wait
from world.artifacts import ArtifactContent, ArtifactKind, InformationArtifact
from world.environment import ActiveHazard, HazardKind, scarcity_scenario_dynamics
from world.events import (
    EVENT_SCHEMA_REPLAY_V6,
    EVENT_SCHEMA_REPLAY_V7,
    EVENT_SCHEMA_REPLAY_V8,
)
from world.identifiers import EntityId, RecipeId, WorldId, WorldRevision
from world.production import StructureKind, example_production_catalog
from world.values import ItemKind

pytestmark = pytest.mark.unit


def _record(*, artifact_id: str = "art-record-1") -> InformationArtifact:
    return InformationArtifact(
        artifact_id=EntityId(artifact_id),
        kind=ArtifactKind.RECORD,
        author_id=EntityId("body-1"),
        created_tick=0,
        content=ArtifactContent(marks=("water", "north")),
        location_id=EntityId("loc-1"),
    )


def _seeded_engine(*, seed: int = 1, dynamics: object | None = None) -> WorldEngine:
    fixture = two_location_fixture()
    kwargs: dict[str, object] = {}
    if dynamics is not None:
        kwargs["environmental_dynamics"] = dynamics
    return WorldEngine(
        config=physical_config(seed),
        bootstrap=WorldBootstrap(
            world_id=fixture.world_id,
            revision=fixture.revision,
            locations=fixture.locations,
            items=fixture.items,
            resources=fixture.resources,
            bodies=fixture.bodies,
            weather=fixture.weather,
            registrations=fixture.registrations,
            artifacts=(_record(),),
        ),
        **kwargs,
    )


def test_seeded_artifacts_select_v8_v5_with_interpretation_disabled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert PERSISTENCE_CODEC_VERSION == "v2"
    assert EVENT_SCHEMA_VERSION == 5
    assert "v5" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert schema_projector_compatible(
        event_schema_version=EVENT_SCHEMA_REPLAY_V8, projector_version="v2"
    )
    caplog.set_level(logging.DEBUG, logger="simulation.engine")
    selected = select_checkpoint_schema(
        production_active=False,
        dynamics_active=False,
        artifacts_active=True,
    )
    assert selected == (EVENT_SCHEMA_REPLAY_V8, "v5")
    assert any(
        "artifact_schema_selected event_schema=8 codec=v5 artifacts_active=True"
        in record.getMessage()
        for record in caplog.records
    )
    engine = _seeded_engine()
    assert engine._artifacts_enabled is True
    # Task 7 interpretation stays DISABLED / absent; seeds alone still take v8/v5.
    assert checkpoint_schema_for_production(
        production_active=False,
        dynamics_active=False,
        artifacts_active=True,
    ) == (EVENT_SCHEMA_REPLAY_V8, "v5")
    from simulation.runner import _bootstrap_snapshot

    snapshot = _bootstrap_snapshot(engine)
    assert snapshot.event_schema_version == EVENT_SCHEMA_REPLAY_V8
    assert snapshot.persistence_codec_version == "v5"
    assert len(snapshot.artifacts) == 1
    assert snapshot.artifacts[0].content.marks == ("water", "north")
    created = RunCreateRequest(
        run_id=snapshot.run_id,
        world_id=snapshot.world_id,
        seed=snapshot.seed,
        config=snapshot.config,
        bootstrap=snapshot,
        derivation_version=snapshot.derivation_version,
        event_schema_version=EVENT_SCHEMA_REPLAY_V8,
        persistence_codec_version="v5",
    )
    assert created.event_schema_version == EVENT_SCHEMA_REPLAY_V8
    assert created.persistence_codec_version == "v5"


def test_dynamics_only_still_selects_v7_v4() -> None:
    assert checkpoint_schema_for_production(
        production_active=False, dynamics_active=True, artifacts_active=False
    ) == (EVENT_SCHEMA_REPLAY_V7, "v4")
    assert select_checkpoint_schema(
        production_active=True, dynamics_active=True, artifacts_active=False
    ) == (EVENT_SCHEMA_REPLAY_V7, "v4")


def test_production_only_still_selects_v6_v3() -> None:
    assert checkpoint_schema_for_production(
        production_active=True, dynamics_active=False, artifacts_active=False
    ) == (EVENT_SCHEMA_REPLAY_V6, "v3")
    assert select_checkpoint_schema(
        production_active=True, dynamics_active=False, artifacts_active=False
    ) == (EVENT_SCHEMA_REPLAY_V6, "v3")


def test_inactive_write_pair_keeps_replay_v5_codec_v2() -> None:
    assert checkpoint_schema_for_production(
        production_active=False, dynamics_active=False, artifacts_active=False
    ) == (EVENT_SCHEMA_VERSION, "v2")
    assert select_checkpoint_schema(
        production_active=False, dynamics_active=False, artifacts_active=False
    ) == (EVENT_SCHEMA_VERSION, "v2")
    assert EVENT_SCHEMA_VERSION == 5


def test_artifacts_plus_dynamics_select_v8_and_fold_hazards_structures(
    caplog: pytest.LogCaptureFixture,
) -> None:
    catalog = example_production_catalog()
    fixture = two_location_fixture()
    dynamics = scarcity_scenario_dynamics()
    material = make_item(
        "mat-1",
        name="plank",
        kind=ItemKind.MATERIAL,
        location_id=None,
        holder_id="body-1",
    )
    engine = WorldEngine(
        config=physical_config(4),
        bootstrap=WorldBootstrap(
            world_id=fixture.world_id,
            revision=fixture.revision,
            locations=fixture.locations,
            items=(material,),
            resources=fixture.resources,
            bodies=(
                alive_body("body-1", inventory=(EntityId("mat-1"),)),
                alive_body("body-2"),
            ),
            weather=fixture.weather,
            registrations=fixture.registrations,
            artifacts=(_record(),),
        ),
        production_catalog=catalog,
        environmental_dynamics=dynamics,
    )
    assert select_checkpoint_schema(
        production_active=True,
        dynamics_active=True,
        artifacts_active=True,
    ) == (EVENT_SCHEMA_REPLAY_V8, "v5")
    batch = engine.observe()
    engine.resolve_tick(
        (
            ActionSubmission(
                batch.token, AgentId("agent-1"), Build(RecipeId("build_shelter"))
            ),
        )
    )
    for _ in range(8):
        batch = engine.observe()
        engine.resolve_tick(
            (ActionSubmission(batch.token, AgentId("agent-1"), Wait()),)
        )
    live = engine._snapshot.world.state
    assert any(
        structure.kind is StructureKind.SHELTER for structure in live.structures.values()
    )
    assert EntityId("art-record-1") in live.artifacts
    caplog.set_level(logging.DEBUG, logger="simulation.replay")
    folded = project_events(
        WorldEngine(
            config=engine._config,
            bootstrap=engine._bootstrap,
            production_catalog=catalog,
            environmental_dynamics=dynamics,
        )._snapshot.world.state,
        engine._snapshot.event_history,
        expected_run_id=engine.run_id.value,
        expected_world_id=engine.world_id,
        production_catalog=catalog,
        environmental_dynamics=dynamics,
    )
    assert folded.artifacts[EntityId("art-record-1")].content.marks == (
        "water",
        "north",
    )
    assert any(
        structure.kind is StructureKind.SHELTER
        for structure in folded.structures.values()
    )
    assert folded.active_hazards == live.active_hazards
    assert any(
        "artifact_fold tick=" in record.getMessage() for record in caplog.records
    )
    assert any(
        "environment_fold tick=" in record.getMessage() for record in caplog.records
    )


def test_v4_checkpoint_rejects_artifacts() -> None:
    location = make_location("loc-1")
    hazard = ActiveHazard(EntityId("loc-1"), HazardKind.HEAT, 0, 2)
    with pytest.raises(ValueError, match="artifacts require codec v5"):
        WorldSnapshot(
            snapshot_id=SnapshotId("snap-reject"),
            run_id=RunId("run-reject"),
            world_id=WorldId("world-1"),
            seed=7,
            config=SimulationRunConfig(seed=7),
            registrations=(
                AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            ),
            locations=(location,),
            bodies=(alive_body(),),
            items=(),
            resources=(),
            weather=(make_weather(),),
            next_tick=Tick(0),
            revision=WorldRevision(0),
            event_schema_version=EVENT_SCHEMA_REPLAY_V7,
            projector_version=PROJECTOR_VERSION,
            persistence_codec_version="v4",
            derivation_version=DERIVATION_VERSION,
            integrity_hash=PayloadHash("a" * 64),
            predecessor_commit_hash=None,
            active_hazards=(hazard,),
            artifacts=(_record(),),
        )
    snapshot = WorldSnapshot(
        snapshot_id=SnapshotId("snap-v4"),
        run_id=RunId("run-v4"),
        world_id=WorldId("world-1"),
        seed=7,
        config=SimulationRunConfig(seed=7),
        registrations=(AgentRegistration(AgentId("agent-1"), EntityId("body-1")),),
        locations=(location,),
        bodies=(alive_body(),),
        items=(),
        resources=(),
        weather=(make_weather(),),
        next_tick=Tick(0),
        revision=WorldRevision(0),
        event_schema_version=EVENT_SCHEMA_REPLAY_V7,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version="v4",
        derivation_version=DERIVATION_VERSION,
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        active_hazards=(hazard,),
    )
    encoded = json.loads(encode_persistence(snapshot))
    encoded["data"]["artifacts"] = []
    with pytest.raises(PersistenceSerializationError) as rejected:
        decode_persistence(json.dumps(encoded).encode(), WorldSnapshot)
    assert rejected.value.code == "unknown_field"


def test_v5_round_trip_and_resume_restores_artifacts() -> None:
    engine = _seeded_engine()
    batch = engine.observe()
    engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-1"),
                Inscribe(kind=ArtifactKind.SIGN, content=ArtifactContent(marks=("path",))),
            ),
        )
    )
    from simulation.runner import _bootstrap_snapshot

    # Mid-run checkpoint via service-shaped draft fields.
    state = engine._snapshot.world.state
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-art"),
        run_id=engine.run_id,
        world_id=engine.world_id,
        seed=engine._config.seed,
        config=engine._config,
        registrations=tuple(engine._bootstrap.registrations),
        locations=tuple(state.locations.values()),
        bodies=tuple(state.bodies.values()),
        items=tuple(state.items.values()),
        resources=tuple(state.resources.values()),
        weather=tuple(state.weather.values()),
        next_tick=engine.tick,
        revision=state.revision,
        event_schema_version=EVENT_SCHEMA_REPLAY_V8,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version="v5",
        derivation_version=engine._config.derivation_version or DERIVATION_VERSION,
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        structures=tuple(state.structures.values()),
        production_jobs=tuple(state.production_jobs.values()),
        tool_marks=tuple(state.tool_marks.values()),
        active_hazards=tuple(state.active_hazards),
        artifacts=tuple(state.artifacts.values()),
    )
    snapshot = WorldSnapshot(
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
        production_jobs=draft.production_jobs,
        tool_marks=draft.tool_marks,
        active_hazards=draft.active_hazards,
        artifacts=draft.artifacts,
    )
    encoded = json.loads(encode_persistence(snapshot))
    assert "artifacts" in encoded["data"]
    assert "active_hazards" in encoded["data"]
    assert "structures" in encoded["data"]
    restored_snap = decode_persistence(encode_persistence(snapshot), WorldSnapshot)
    assert isinstance(restored_snap, WorldSnapshot)
    assert len(restored_snap.artifacts) == len(snapshot.artifacts)
    restored = WorldEngine.restore_from_snapshot(restored_snap)
    assert restored._artifacts_enabled is True
    assert restored._snapshot.world.state.artifacts[EntityId("art-record-1")].content.marks == (
        "water",
        "north",
    )
    bootstrap = _bootstrap_snapshot(engine)
    assert bootstrap.persistence_codec_version == "v5"
