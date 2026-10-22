"""Generational matrix cells execute with the new factors."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from agents.models import DriveKind
from experiments import (
    EXPERIMENT_MATRIX_SCHEMA_VERSION,
    ExperimentMatrixSpec,
    ExperimentSeedMatrix,
    GroupRole,
    MatrixEmbeddedBase,
    MatrixFactor,
    MatrixFactorId,
    MatrixFactorLevel,
    expand_matrix,
    generational_comparison_base,
)
from experiments.collectors import assemble_arm_metric_bundle
from experiments.coordinator import ExperimentCoordinator
from experiments.generational_comparison_base import (
    assert_comparable_generational_conditions,
)
from experiments.generational_execution import (
    PLAIN_RECIPE_ID,
    GenerationalExecutionContext,
)
from research_runner.generational_composition import GenerationalExecutionRecipe
from simulation.new_agent_initialization import ParameterDistributionSpec
from simulation.runner import RunnerDependencyFactories
from simulation.runner_models import LifespanDistributionSpec


def _spec() -> ExperimentMatrixSpec:
    return ExperimentMatrixSpec(
        matrix_id="generational-matrix-execution",
        schema_version=EXPERIMENT_MATRIX_SCHEMA_VERSION,
        base=MatrixEmbeddedBase(generational_comparison_base(seed=23, max_ticks=8)),
        factors=(
            MatrixFactor(
                MatrixFactorId.LIFESPAN,
                (
                    MatrixFactorLevel("short", "short_control", GroupRole.CONTROL),
                    MatrixFactorLevel("long", "long_treatment", GroupRole.TREATMENT),
                ),
            ),
            MatrixFactor(
                MatrixFactorId.TEACHING_FREQUENCY,
                (
                    MatrixFactorLevel("low", "low_control", GroupRole.CONTROL),
                    MatrixFactorLevel("high", "high_treatment", GroupRole.TREATMENT),
                ),
            ),
        ),
        seed_matrix=ExperimentSeedMatrix(seeds=(23,)),
    )


@pytest.mark.asyncio
async def test_generational_matrix_cells_execute(tmp_path: Path) -> None:
    definition, cells = expand_matrix(_spec())
    assert len(definition.conditions) == 4
    assert len(cells) == 4
    assert {cell.group_role for cell in cells} == {
        GroupRole.CONTROL,
        GroupRole.TREATMENT,
    }
    configs = tuple(
        condition.runner_config for condition in definition.conditions
    )
    assert_comparable_generational_conditions(configs)
    assert all(config.schema_version == "runner-config-v55" for config in configs)
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
    results = await ExperimentCoordinator(
        definition, generational_contexts={"*": context}
    ).run_all()
    assert len(results) == 4
    for arm in results:
        result = arm.runner_result
        assert result.generational_progress is not None
        assert result.stop_reason.value == "max_ticks"
        config = arm.assignment.runner_config
        assert config.schema_version == "runner-config-v55"
        assert config.population_lifecycle is not None
        lifespan = config.population_lifecycle.lifespan_ticks
        offer_window = config.agents[0].cognition.offer_window
        if "lifespan-short" in arm.assignment.condition_id:
            assert lifespan == 8
        else:
            assert lifespan == 24
        if "teaching_frequency-low" in arm.assignment.condition_id:
            assert offer_window == 4
        else:
            assert offer_window == 12
        bundle = assemble_arm_metric_bundle(arm)
        assert "generational_cohort_comparison" in {
            document.metric_family for document in bundle.documents
        }


def test_comparability_rejects_false_same_identity_claims() -> None:
    """Run-ID-scoped draws remain honest: only a fixed comparable base passes.

    Demography, initialization, and lifespan streams are scoped to a durable
    run ID. This gate does not claim that two arbitrary run IDs reproduce one
    another; it proves the declared arms share a passthrough lifespan and a
    deterministic ``none`` initialization, so their admitted generations are
    comparable.
    """
    base = generational_comparison_base(seed=23, max_ticks=8)
    assert_comparable_generational_conditions((base, base))
    lifecycle = base.population_lifecycle
    assert lifecycle is not None
    altered = replace(
        base,
        population_lifecycle=replace(
            lifecycle,
            lifespan_distribution=LifespanDistributionSpec(
                distribution_id="uniform_int",
                params={"min_ticks": 8, "max_ticks": 12},
            ),
        ),
    )
    with pytest.raises(ValueError) as error:
        assert_comparable_generational_conditions((base, altered))
    assert str(error.value) == "comparison_lifespan_distribution_not_passthrough"

    assert base.new_agent_initialization is not None
    initialization = replace(
        base.new_agent_initialization,
        parameter_distributions=ParameterDistributionSpec(
            distribution_id="uniform_drive_delta",
            params={
                "drive_kind": DriveKind.CURIOSITY.value,
                "min_delta": 0.1,
                "max_delta": 0.2,
            },
        ),
    )
    with pytest.raises(ValueError) as initialization_error:
        assert_comparable_generational_conditions(
            (base, replace(base, new_agent_initialization=initialization))
        )
    assert (
        str(initialization_error.value)
        == "comparison_initialization_not_deterministic"
    )
