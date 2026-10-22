"""Per-assignment generational execution context and archive completion."""

from __future__ import annotations

from pathlib import Path

import pytest

from experiments.coordinator import ExperimentAssignment
from experiments.generational_execution import (
    BL_RECIPE_ID,
    PLAIN_RECIPE_ID,
    GenerationalExecutionContext,
    GenerationalExecutionError,
    execute_generational_assignment,
)
from experiments.generational_runner_scenario import generational_runner_scenario
from research_runner.generational_composition import GenerationalExecutionRecipe
from simulation.runner import RunnerDependencyFactories


def _assignment(
    condition_id: str = "bl-generational-unassisted",
) -> ExperimentAssignment:
    definition = generational_runner_scenario(seed=23, max_ticks=6)
    condition = next(
        item for item in definition.conditions if item.condition_id == condition_id
    )
    return ExperimentAssignment(
        experiment_id=definition.experiment_id,
        condition_id=condition.condition_id,
        condition_ordinal=0,
        seed=condition.runner_config.seed,
        seed_ordinal=0,
        replicate_index=0,
        run_id=__import__("simulation.models", fromlist=["RunId"]).RunId(
            "run-exec-1"
        ),
        runner_config=condition.runner_config,
    )


@pytest.mark.asyncio
async def test_execute_assignment_writes_completion(tmp_path: Path) -> None:
    assignment = _assignment()
    context = GenerationalExecutionContext(
        artifact_root=tmp_path,
        source_identity={
            "code_revision": "abc123",
            "source_artifact_digest": None,
            "source_clean": True,
        },
        recipe=GenerationalExecutionRecipe(
            recipe_id=PLAIN_RECIPE_ID, version="1"
        ),
        factories=RunnerDependencyFactories(),
    )
    arm = await execute_generational_assignment(assignment, context)
    assert arm.runner_result.generational_progress is not None
    assert arm.metrics
    from experiments.generational_artifacts import GenerationalRunArtifactStore

    store = GenerationalRunArtifactStore(
        root=tmp_path, run_id=assignment.run_id.value
    )
    completion = store.read_completion()
    assert completion["run_id"] == assignment.run_id.value


def test_recipe_preflight_rejects_mismatches(tmp_path: Path) -> None:
    assignment = _assignment()
    plain = GenerationalExecutionContext(
        artifact_root=tmp_path,
        source_identity={
            "code_revision": "abc123",
            "source_artifact_digest": None,
            "source_clean": True,
        },
        recipe=GenerationalExecutionRecipe(
            recipe_id=PLAIN_RECIPE_ID,
            version="1",
            params={"unexpected": True},
        ),
        factories=RunnerDependencyFactories(),
    )
    with pytest.raises(GenerationalExecutionError, match="recipe_descriptor_mismatch"):
        plain.preflight(assignment.runner_config)

    bad_treatment = GenerationalExecutionContext(
        artifact_root=tmp_path,
        source_identity={
            "code_revision": "abc123",
            "source_artifact_digest": None,
            "source_clean": True,
        },
        recipe=GenerationalExecutionRecipe(
            recipe_id=BL_RECIPE_ID,
            version="1",
            params={"treatment": "unknown"},
        ),
        factories=RunnerDependencyFactories(),
    )
    with pytest.raises(GenerationalExecutionError, match="recipe_treatment_invalid"):
        bad_treatment.preflight(assignment.runner_config)

    single = _assignment("bl-single-cohort")
    mismatched = GenerationalExecutionContext(
        artifact_root=tmp_path,
        source_identity={
            "code_revision": "abc123",
            "source_artifact_digest": None,
            "source_clean": True,
        },
        recipe=GenerationalExecutionRecipe(
            recipe_id=BL_RECIPE_ID,
            version="1",
            params={"treatment": "unassisted"},
        ),
        factories=RunnerDependencyFactories(),
    )
    with pytest.raises(
        GenerationalExecutionError, match="generational_treatment_requires_schedule"
    ):
        mismatched.preflight(single.runner_config)
