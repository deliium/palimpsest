"""Off-gate Experiment AN catalog for durable records on runner-config-v33."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments import (
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    durable_records_profile,
    experiment_an_durable_records,
)
from experiments.catalog import base_runner_config_from_scenario
from experiments.matrix_schema import finalize_matrix_cell_config
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    RUNNER_SCHEMA_VERSION_V33,
    AgentCognitionSpec,
    AgentRunnerSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_cultural_feature_provenance_spec,
    example_durable_records_spec,
    example_historical_memory_layers_spec,
)
from tests.physical_helpers import physical_config, two_location_fixture
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.actions import AnnotateRecord, CopyRecord, DamageRecord, Inscribe
from world.artifacts import (
    ArtifactContent,
    ArtifactKind,
    DurableRecordGenre,
    RecordIntegrity,
)
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.experiment_an_durable_records")

_AN_ARM_IDS = (
    "an-channel-off",
    "an-perfect-copy",
    "an-imperfect-copy",
    "an-author-death",
    "an-false-persist",
    "an-damage-loss",
    "an-annotate-edit",
    "an-flags-off",
)

pytestmark = pytest.mark.unit


def _base():
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    return base_runner_config_from_scenario(
        seed=211,
        stochastic_identity="cmp-an-durable-records",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-an-durable"),
            revision=WorldRevision(0),
            physical_rules=non_lethal_physical_rules(),
            locations=(make_location(body_capacity=8),),
            bodies=(body_a, body_b),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=AgentId("agent-a"),
                entity_id=body_a.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-a")),
            ),
            AgentRunnerSpec(
                agent_id=AgentId("agent-b"),
                entity_id=body_b.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-b")),
            ),
        ),
        max_ticks=8,
    )


def _arm(definition, arm_id: str):
    return next(
        item for item in definition.conditions if item.condition_id == arm_id
    ).runner_config


def test_an_catalog_arms_and_profile(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="experiments.catalog")
    definition = experiment_an_durable_records(_base())
    assert definition.experiment_id == "experiment-an-durable-records"
    assert "experiment-an-durable-records" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert tuple(item.condition_id for item in definition.conditions) == _AN_ARM_IDS

    channel_off = _arm(definition, "an-channel-off")
    assert channel_off.schema_version == RUNNER_SCHEMA_VERSION_V31
    assert channel_off.durable_records is None
    assert channel_off.cultural_feature_provenance is not None

    perfect = _arm(definition, "an-perfect-copy")
    assert perfect.schema_version == RUNNER_SCHEMA_VERSION_V33
    durable_records_profile(perfect)
    assert perfect.durable_records is not None
    assert perfect.durable_records.copy_fidelity_policy.default_fidelity == "perfect"

    imperfect = _arm(definition, "an-imperfect-copy")
    assert (
        imperfect.durable_records.copy_fidelity_policy.default_fidelity
        == "deterministic_mutation"
    )

    author_death = _arm(definition, "an-author-death")
    assert author_death.population_lifecycle is not None
    assert author_death.v3_capability_flags.generational_population is True

    flags_off = _arm(definition, "an-flags-off")
    assert flags_off.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert flags_off.durable_records is None
    assert flags_off.v3_capability_flags.cultural_historical_memory is False

    assert "experiment_an_built" in caplog.text


def test_durable_records_profile_rejects_wrong_schema() -> None:
    config = _arm(experiment_an_durable_records(_base()), "an-channel-off")
    with pytest.raises(ValueError, match="durable_records_profile_schema"):
        durable_records_profile(config)


def _engine(*, default_fidelity: str = "perfect") -> WorldEngine:
    return WorldEngine(
        config=physical_config(1),
        bootstrap=two_location_fixture().as_bootstrap(),
        artifacts_enabled=True,
        durable_records_spec=example_durable_records_spec(
            default_fidelity=default_fidelity
        ),
    )


def _act(engine: WorldEngine, command: object):
    batch = engine.observe()
    return engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId("agent-1"), command),)
    )


def test_arm_perfect_copy_lineage() -> None:
    arm_id = "an-perfect-copy"
    engine = _engine(default_fidelity="perfect")
    created = _act(
        engine,
        Inscribe(
            ArtifactKind.RECORD,
            ArtifactContent(marks=("a", "b")),
            record_genre=DurableRecordGenre.WARNING,
        ),
    )
    assert created.resolutions[0].status is ActionResolutionStatus.APPLIED, arm_id
    parent_id = next(iter(engine._snapshot.world.state.artifacts))
    parent_marks = engine._snapshot.world.state.artifacts[parent_id].content.marks
    copied = _act(engine, CopyRecord(parent_id))
    assert copied.resolutions[0].status is ActionResolutionStatus.APPLIED, arm_id
    children = [
        item
        for item in engine._snapshot.world.state.artifacts.values()
        if item.parent_artifact_id == parent_id
    ]
    assert len(children) == 1, f"{arm_id}: expected one child copy"
    child = children[0]
    assert child.copy_generation == 1, f"{arm_id}: expected generation=1"
    assert child.content.marks == parent_marks, f"{arm_id}: perfect copy marks mismatch"


def test_arm_imperfect_copy_mutates_marks() -> None:
    arm_id = "an-imperfect-copy"
    engine = _engine(default_fidelity="deterministic_mutation")
    created = _act(
        engine,
        Inscribe(
            ArtifactKind.RECORD,
            ArtifactContent(marks=("alpha", "beta", "gamma", "delta")),
            record_genre=DurableRecordGenre.STORY,
        ),
    )
    assert created.resolutions[0].status is ActionResolutionStatus.APPLIED, arm_id
    parent_id = next(iter(engine._snapshot.world.state.artifacts))
    parent_marks = engine._snapshot.world.state.artifacts[parent_id].content.marks
    copied = _act(engine, CopyRecord(parent_id))
    assert copied.resolutions[0].status is ActionResolutionStatus.APPLIED, arm_id
    child = next(
        item
        for item in engine._snapshot.world.state.artifacts.values()
        if item.parent_artifact_id == parent_id
    )
    assert child.content.marks != parent_marks, (
        f"{arm_id}: expected mutated marks for imperfect copy"
    )
    assert child.copy_generation == 1, f"{arm_id}: lineage generation"


def test_arm_damage_loss_tombstone_invisible() -> None:
    arm_id = "an-damage-loss"
    engine = _engine()
    created = _act(
        engine,
        Inscribe(
            ArtifactKind.RECORD,
            ArtifactContent(marks=("x", "y")),
            record_genre=DurableRecordGenre.CHRONICLE,
        ),
    )
    assert created.resolutions[0].status is ActionResolutionStatus.APPLIED, arm_id
    artifact_id = next(iter(engine._snapshot.world.state.artifacts))
    _act(engine, DamageRecord(artifact_id, "damage"))
    assert (
        engine._snapshot.world.state.artifacts[artifact_id].integrity
        is RecordIntegrity.DAMAGED
    ), arm_id
    _act(engine, DamageRecord(artifact_id, "partial_loss"))
    assert (
        engine._snapshot.world.state.artifacts[artifact_id].integrity
        is RecordIntegrity.PARTIALLY_LOST
    ), arm_id
    _act(engine, DamageRecord(artifact_id, "destroy"))
    tombstone = engine._snapshot.world.state.artifacts[artifact_id]
    assert tombstone.integrity is RecordIntegrity.DESTROYED, (
        f"{arm_id}: expected tombstone retained"
    )
    obs = engine.observe().observations[0]
    assert all(item.entity_id != artifact_id for item in obs.artifacts), (
        f"{arm_id}: destroyed tombstone must be absent from Observation"
    )


def test_arm_annotate_edit_bumps_revisions() -> None:
    arm_id = "an-annotate-edit"
    engine = _engine()
    created = _act(
        engine,
        Inscribe(
            ArtifactKind.NOTE,
            ArtifactContent(marks=("base",)),
            hold=True,
            record_genre=DurableRecordGenre.INSTRUCTION,
        ),
    )
    assert created.resolutions[0].status is ActionResolutionStatus.APPLIED, arm_id
    artifact_id = next(iter(engine._snapshot.world.state.artifacts))
    author = engine._snapshot.world.state.artifacts[artifact_id].author_id
    annotated = _act(
        engine,
        AnnotateRecord(artifact_id, ArtifactContent(marks=("note",))),
    )
    assert annotated.resolutions[0].status is ActionResolutionStatus.APPLIED, arm_id
    record = engine._snapshot.world.state.artifacts[artifact_id]
    assert record.annotation_revisions >= 1, f"{arm_id}: annotation_revisions"
    assert record.content_revision >= 1, f"{arm_id}: content_revision"
    assert record.author_id == author, f"{arm_id}: author immutable"


def test_arm_genealogy_genre_does_not_write_kinship() -> None:
    arm_id = "an-perfect-copy"
    engine = _engine()
    created = _act(
        engine,
        Inscribe(
            ArtifactKind.RECORD,
            ArtifactContent(marks=("kin", "claim")),
            record_genre=DurableRecordGenre.GENEALOGY,
        ),
    )
    assert created.resolutions[0].status is ActionResolutionStatus.APPLIED, arm_id
    assert engine.kinship_graph.edges == (), (
        f"{arm_id}: genealogy genre must not write kinship edges"
    )


def test_matrix_finalize_durable_beats_historical_memory(
    caplog: pytest.LogCaptureFixture,
) -> None:
    base = _base()
    both = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V33,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        historical_memory_layers=example_historical_memory_layers_spec(),
        durable_records=example_durable_records_spec(),
        population_lifecycle=None,
        new_agent_initialization=None,
        mentorship=None,
        artifacts_enabled=True,
    )
    with caplog.at_level(logging.DEBUG, logger="experiments.matrix_schema"):
        finalized = finalize_matrix_cell_config(both)
    assert finalized.schema_version == RUNNER_SCHEMA_VERSION_V33
    assert "durable_records_on" in caplog.text

    layers_only = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V32,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        historical_memory_layers=example_historical_memory_layers_spec(),
        durable_records=None,
        population_lifecycle=None,
        new_agent_initialization=None,
        mentorship=None,
    )
    finalized_am = finalize_matrix_cell_config(layers_only)
    assert finalized_am.schema_version == RUNNER_SCHEMA_VERSION_V32

    cultural_only = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V31,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        historical_memory_layers=None,
        durable_records=None,
        population_lifecycle=None,
        new_agent_initialization=None,
        mentorship=None,
    )
    finalized_al = finalize_matrix_cell_config(cultural_only)
    assert finalized_al.schema_version == RUNNER_SCHEMA_VERSION_V31
