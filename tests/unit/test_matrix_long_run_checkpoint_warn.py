"""Matrix long-cell checkpoint guidance WARN."""

from __future__ import annotations

from dataclasses import replace

import pytest

from experiments.matrix_expand import expand_matrix
from experiments.matrix_factors import matrix_reference_fixture_base
from experiments.matrix_models import (
    EXPERIMENT_MATRIX_SCHEMA_VERSION,
    ExperimentMatrixSpec,
    GroupRole,
    MatrixEmbeddedBase,
    MatrixExecutionPolicy,
    MatrixFactor,
    MatrixFactorId,
    MatrixFactorLevel,
)
from experiments.matrix_runner import _warn_long_run_checkpoint_guidance
from experiments.models import ExperimentSeedMatrix
from simulation.runner_models import RunnerCheckpointPolicy, RunnerPersistenceSpec


def test_long_run_checkpoint_recommended_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    base = matrix_reference_fixture_base(max_ticks=2_000)
    base = replace(
        base,
        persistence=RunnerPersistenceSpec(
            durable=True,
            checkpoint=RunnerCheckpointPolicy(enabled=False),
        ),
        stop_policy=replace(base.stop_policy, max_ticks=2_000),
    )
    spec = ExperimentMatrixSpec(
        matrix_id="matrix-long-guide",
        schema_version=EXPERIMENT_MATRIX_SCHEMA_VERSION,
        base=MatrixEmbeddedBase(runner_config=base),
        factors=(
            MatrixFactor(
                factor_id=MatrixFactorId.MEMORY_TYPE,
                levels=(
                    MatrixFactorLevel(
                        level_id="reference",
                        label_code="ref",
                        group_role=GroupRole.CONTROL,
                    ),
                    MatrixFactorLevel(
                        level_id="reconstructive",
                        label_code="recon",
                        group_role=GroupRole.TREATMENT,
                    ),
                ),
            ),
        ),
        seed_matrix=ExperimentSeedMatrix(seeds=(11,)),
        execution=MatrixExecutionPolicy(max_concurrency=1),
    )
    definition, cells = expand_matrix(spec)
    ordinals = {
        condition.condition_id: index
        for index, condition in enumerate(definition.conditions)
    }
    with caplog.at_level("WARNING"):
        _warn_long_run_checkpoint_guidance(definition, cells, ordinals)
    assert "long_run_checkpoint_recommended" in caplog.text
    assert "cadence_ticks=100" in caplog.text
