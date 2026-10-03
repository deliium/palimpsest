"""Unit tests for MatrixBatchRunner concurrency and resume."""

from __future__ import annotations

from dataclasses import replace

import pytest

from experiments.matrix_expand import expand_matrix
from experiments.matrix_factors import matrix_reference_fixture_base
from experiments.matrix_manifest import FilesystemMatrixManifestStore
from experiments.matrix_models import (
    EXPERIMENT_MATRIX_SCHEMA_VERSION,
    ExperimentMatrixSpec,
    GroupRole,
    MatrixCellState,
    MatrixEmbeddedBase,
    MatrixExecutionPolicy,
    MatrixFactor,
    MatrixFactorId,
    MatrixFactorLevel,
    MatrixValidationError,
)
from experiments.matrix_runner import (
    MatrixBatchDependencies,
    MatrixBatchRunner,
)
from experiments.models import ExperimentSeedMatrix
from simulation.runner_models import RunnerPersistenceSpec


def _spec(**overrides: object) -> ExperimentMatrixSpec:
    kwargs: dict[str, object] = {
        "matrix_id": "matrix-batch-demo",
        "schema_version": EXPERIMENT_MATRIX_SCHEMA_VERSION,
        "base": MatrixEmbeddedBase(
            runner_config=matrix_reference_fixture_base(max_ticks=1)
        ),
        "factors": (
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
            MatrixFactor(
                factor_id=MatrixFactorId.TOM,
                levels=(
                    MatrixFactorLevel(level_id="off", label_code="tom_off"),
                    MatrixFactorLevel(level_id="on", label_code="tom_on"),
                ),
            ),
        ),
        "seed_matrix": ExperimentSeedMatrix(seeds=(11,)),
        "execution": MatrixExecutionPolicy(max_concurrency=1),
    }
    kwargs.update(overrides)
    return ExperimentMatrixSpec(**kwargs)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_batch_runner_completes_and_skips_on_resume(tmp_path) -> None:
    spec = _spec()
    store = FilesystemMatrixManifestStore(tmp_path)
    runner = MatrixBatchRunner(
        MatrixBatchDependencies(package_version="0.0.0-test", code_revision="")
    )
    first = await runner.run(spec, store)
    assert first.completed == 4
    assert first.failed == 0
    assert first.skipped_valid == 0
    assert all(
        record.state is MatrixCellState.COMPLETED for record in store.list_cells()
    )

    second = await runner.run(spec, store)
    assert second.completed == 0
    assert second.skipped_valid == 4
    assert all(
        record.state is MatrixCellState.SKIPPED_VALID for record in store.list_cells()
    )


@pytest.mark.asyncio
async def test_durable_rejects_concurrency_gt_one(tmp_path) -> None:
    base = matrix_reference_fixture_base(max_ticks=1)
    durable_base = replace(
        base,
        persistence=RunnerPersistenceSpec(durable=True),
    )
    spec = _spec(
        base=MatrixEmbeddedBase(runner_config=durable_base),
        execution=MatrixExecutionPolicy(max_concurrency=2),
    )
    store = FilesystemMatrixManifestStore(tmp_path)
    runner = MatrixBatchRunner(
        MatrixBatchDependencies(package_version="0.0.0-test")
    )
    with pytest.raises(MatrixValidationError) as exc:
        await runner.run(spec, store)
    assert exc.value.code == "durable_requires_serial_matrix"


def test_expand_for_runner_fixture() -> None:
    definition, cells = expand_matrix(_spec())
    assert len(definition.conditions) == 4
    assert len(cells) == 4
