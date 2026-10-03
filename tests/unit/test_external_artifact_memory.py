"""Experiment Z and external_artifact_memory@1 stay analysis-only."""

from __future__ import annotations

import inspect
import logging
from pathlib import Path

import pytest

from analysis.external_artifact_metrics import (
    EXTERNAL_ARTIFACT_MEMORY_METRIC_VERSION,
    compute_external_artifact_memory,
)
from analysis.models import MetricAvailability
from analysis.specifications import MetricFamilyId, metric_specification
from experiments.catalog import experiment_z_external_artifacts
from experiments.composition import (
    artifact_interpretation_rows_from_ledgers,
    artifact_memory_rows_from_traces,
    artifact_objective_rows_from_artifacts,
)
from experiments.external_artifacts_scenario import (
    OWNER_A_ID,
    SCARCE_RESOURCE_MARKS,
    SCENARIO_ARTIFACT_ID,
    external_artifacts_scenario,
    scarce_resource_record,
)
from simulation.runner_models import (
    ArtifactInterpretationMode,
    ConsolidationMode,
)
from world.identifiers import EntityId
from world.values import Fatigue, UnitInterval

_ROOT = Path(__file__).resolve().parents[2]


def test_metric_tag_and_absent_keys(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="analysis.external_artifact_memory")
    spec = metric_specification("external_artifact_memory")
    assert spec.version_identifier == EXTERNAL_ARTIFACT_MEMORY_METRIC_VERSION
    assert EXTERNAL_ARTIFACT_MEMORY_METRIC_VERSION == "external_artifact_memory@1"
    empty = compute_external_artifact_memory(
        {"objective_rows": (), "memory_rows": (), "interpretation_rows": ()},
        run_id="run-z",
        input_revision="rev-1",
    )
    assert empty.availability is MetricAvailability.ABSENT
    document = compute_external_artifact_memory(
        {
            "forget_tick": 4,
            "scenario_artifact_id": SCENARIO_ARTIFACT_ID,
            "owner_a_id": OWNER_A_ID,
            "objective_rows": (
                {
                    "tick": 5,
                    "artifact_id": SCENARIO_ARTIFACT_ID,
                    "kind": "record",
                    "content_revision": 0,
                    "present": True,
                    "marks": SCARCE_RESOURCE_MARKS,
                },
            ),
            "memory_rows": (
                {
                    "tick": 5,
                    "owner_id": OWNER_A_ID,
                    "has_cue_concept": True,
                    "forgotten": True,
                },
                {
                    "tick": 5,
                    "owner_id": OWNER_A_ID,
                    "has_cue_concept": True,
                    "forgotten": True,
                },
            ),
            "interpretation_rows": (
                {
                    "owner_id": "ben",
                    "artifact_id": SCENARIO_ARTIFACT_ID,
                    "observed_revision": 0,
                    "reading_marks": SCARCE_RESOURCE_MARKS,
                    "distorted": False,
                },
            ),
        },
        run_id="run-z",
        input_revision="rev-1",
    )
    assert document.availability is MetricAvailability.PRESENT
    assert document.values["record_present_after_forget"] == 1.0
    assert document.values["mean_content_revision"] == 0.0
    assert document.values["memory_loss_rate"] == 1.0
    assert document.values["reading_recovery_rate"] == 1.0
    assert document.values["interpretation_divergence"] == "absent"
    absent_means = compute_external_artifact_memory(
        {
            "forget_tick": 4,
            "scenario_artifact_id": SCENARIO_ARTIFACT_ID,
            "owner_a_id": OWNER_A_ID,
            "objective_rows": (
                {
                    "tick": 5,
                    "artifact_id": SCENARIO_ARTIFACT_ID,
                    "kind": "record",
                    "content_revision": 2,
                    "present": False,
                    "marks": SCARCE_RESOURCE_MARKS,
                },
            ),
            "memory_rows": (),
            "interpretation_rows": (),
        },
        run_id="run-z",
        input_revision="rev-1",
    )
    assert absent_means.values["record_present_after_forget"] == 0.0
    assert absent_means.values["mean_content_revision"] == "absent"
    assert absent_means.values["memory_loss_rate"] == "absent"
    assert absent_means.values["reading_recovery_rate"] == "absent"
    assert any(
        "external_artifact_memory_computed" in record.getMessage()
        for record in caplog.records
    )


def test_divergence_and_duck_typing() -> None:
    document = compute_external_artifact_memory(
        {
            "forget_tick": 1,
            "scenario_artifact_id": "art-1",
            "objective_rows": (
                type(
                    "Obj",
                    (),
                    {
                        "tick": 2,
                        "artifact_id": "art-1",
                        "kind": "record",
                        "content_revision": 1,
                        "present": True,
                        "marks": ("food", "scarce"),
                    },
                )(),
            ),
            "memory_rows": (
                type(
                    "Mem",
                    (),
                    {
                        "tick": 2,
                        "owner_id": "ada",
                        "has_cue_concept": True,
                        "forgotten": False,
                    },
                )(),
            ),
            "interpretation_rows": (
                type(
                    "Read",
                    (),
                    {
                        "owner_id": "ben",
                        "artifact_id": "art-1",
                        "observed_revision": 1,
                        "reading_marks": ("food", "scarce"),
                        "distorted": False,
                    },
                )(),
                type(
                    "Read",
                    (),
                    {
                        "owner_id": "cy",
                        "artifact_id": "art-1",
                        "observed_revision": 1,
                        "reading_marks": ("food", "plenty"),
                        "distorted": False,
                    },
                )(),
            ),
        },
        run_id="run-z-div",
        input_revision="rev-1",
    )
    assert document.values["interpretation_divergence"] == 1.0
    assert document.values["memory_loss_rate"] == 0.0
    source = (_ROOT / "src/analysis/external_artifact_metrics.py").read_text()
    assert "\nimport agents" not in source
    assert "\nfrom agents" not in source
    assert "apply_artifact_interpretation_update" not in source.split('"""', 2)[-1]
    assert "AgentRuntime" not in source.split('"""', 2)[-1]


def test_experiment_z_pairs_channel_and_memory_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="experiments.external_artifacts")
    caplog.set_level(logging.INFO, logger="experiments.catalog")
    parameters = inspect.signature(external_artifacts_scenario).parameters
    assert set(parameters) == {"seed", "max_ticks"}
    definition = experiment_z_external_artifacts()
    assert definition.experiment_id == "experiment-z-external-artifacts"
    by_id = {item.condition_id: item for item in definition.conditions}
    channel = by_id["artifact_channel"].runner_config
    memory_only = by_id["memory_only"].runner_config
    assert channel.schema_version == "runner-config-v19"
    assert memory_only.schema_version == "runner-config-v19"
    assert channel.seed == memory_only.seed
    assert channel.stochastic_identity == memory_only.stochastic_identity
    assert channel.artifacts_enabled is True
    assert memory_only.artifacts_enabled is True
    assert channel.scenario.artifacts
    assert memory_only.scenario.artifacts == ()
    assert {
        agent.cognition.artifact_interpretation_mode for agent in channel.agents
    } == {ArtifactInterpretationMode.DETERMINISTIC}
    assert {
        agent.cognition.consolidation_mode for agent in channel.agents
    } == {ConsolidationMode.DETERMINISTIC}
    assert all(
        place.visibility_factor == UnitInterval(1.0)
        for place in channel.scenario.locations
    )
    assert all(body.fatigue == Fatigue(0.0) for body in channel.scenario.bodies)
    bindings = {
        agent.agent_id.value: agent.entity_id.value for agent in channel.agents
    }
    assert bindings == {"ada": "body-ada", "ben": "body-ben"}
    assert "experiment-z-external-artifacts" not in {
        "experiment-a-memory",
        "experiment-b-imagination",
        "experiment-c-mortality",
        "experiment-d-drives",
        "experiment-e-false-story",
    }
    assert any("experiment_z_built" in record.getMessage() for record in caplog.records)


def test_artifact_arm_recovers_memory_only_fails() -> None:
    artifact_arm = compute_external_artifact_memory(
        {
            "forget_tick": 4,
            "scenario_artifact_id": SCENARIO_ARTIFACT_ID,
            "owner_a_id": OWNER_A_ID,
            "objective_rows": (
                {
                    "tick": 5,
                    "artifact_id": SCENARIO_ARTIFACT_ID,
                    "kind": "record",
                    "content_revision": 0,
                    "present": True,
                    "marks": SCARCE_RESOURCE_MARKS,
                },
            ),
            "memory_rows": (
                {
                    "tick": 5,
                    "owner_id": OWNER_A_ID,
                    "has_cue_concept": True,
                    "forgotten": True,
                },
            ),
            "interpretation_rows": (
                {
                    "owner_id": "ben",
                    "artifact_id": SCENARIO_ARTIFACT_ID,
                    "observed_revision": 0,
                    "reading_marks": SCARCE_RESOURCE_MARKS,
                    "distorted": False,
                },
            ),
        },
        run_id="run-z-channel",
        input_revision="rev-1",
    )
    assert artifact_arm.values["record_present_after_forget"] == 1.0
    assert artifact_arm.values["reading_recovery_rate"] == 1.0
    assert artifact_arm.values["memory_loss_rate"] == 1.0

    memory_only = compute_external_artifact_memory(
        {
            "forget_tick": 4,
            "scenario_artifact_id": SCENARIO_ARTIFACT_ID,
            "owner_a_id": OWNER_A_ID,
            "objective_rows": (),
            "memory_rows": (
                {
                    "tick": 5,
                    "owner_id": OWNER_A_ID,
                    "has_cue_concept": True,
                    "forgotten": True,
                },
            ),
            "interpretation_rows": (),
        },
        run_id="run-z-memory",
        input_revision="rev-1",
    )
    assert memory_only.values["record_present_after_forget"] == 0.0
    assert memory_only.values["reading_recovery_rate"] == "absent"
    assert memory_only.values["memory_loss_rate"] == 1.0


def test_composition_maps_detached_rows_only() -> None:
    record = scarce_resource_record()
    objective = artifact_objective_rows_from_artifacts((record,), tick=3)
    assert objective == (
        {
            "tick": 3,
            "artifact_id": SCENARIO_ARTIFACT_ID,
            "kind": "record",
            "content_revision": 0,
            "present": True,
            "marks": SCARCE_RESOURCE_MARKS,
        },
    )

    class _Trace:
        owner_id = type("Owner", (), {"value": "ada"})()
        concepts = ("food", "scarce")
        forgotten = True
        strength = 0.0

    memory = artifact_memory_rows_from_traces(
        (_Trace(),),
        tick=3,
        cue_concepts=("food", "scarce"),
    )
    assert memory[0]["has_cue_concept"] is True
    assert memory[0]["forgotten"] is True

    class _Entry:
        artifact_id = EntityId(SCENARIO_ARTIFACT_ID)
        observed_revision = 0
        reading_marks = SCARCE_RESOURCE_MARKS
        distorted = False

    class _Ledger:
        owner_id = type("Owner", (), {"value": "ben"})()
        interpretations = (_Entry(),)

    readings = artifact_interpretation_rows_from_ledgers((_Ledger(),))
    document = compute_external_artifact_memory(
        {
            "forget_tick": 2,
            "scenario_artifact_id": SCENARIO_ARTIFACT_ID,
            "owner_a_id": OWNER_A_ID,
            "objective_rows": objective,
            "memory_rows": memory,
            "interpretation_rows": readings,
        },
        run_id="run-z-comp",
        input_revision="rev-1",
    )
    assert document.values["reading_recovery_rate"] == 1.0
    assert document.values["memory_loss_rate"] == 1.0
