"""Unit tests for MatrixBatchRunner concurrency and resume."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import pytest

from experiments.cultural_metric_artifacts import CulturalCaptureOptions
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
async def test_batch_runner_completes_and_skips_on_resume(tmp_path: Path) -> None:
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
async def test_durable_rejects_concurrency_gt_one(tmp_path: Path) -> None:
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
    runner = MatrixBatchRunner(MatrixBatchDependencies(package_version="0.0.0-test"))
    with pytest.raises(MatrixValidationError) as exc:
        await runner.run(spec, store)
    assert exc.value.code == "durable_requires_serial_matrix"


def test_expand_for_runner_fixture() -> None:
    definition, cells = expand_matrix(_spec())
    assert len(definition.conditions) == 4
    assert len(cells) == 4


@pytest.mark.asyncio
async def test_capture_enabled_matrix_writes_and_reuses_pairs(tmp_path: Path) -> None:
    spec = _spec()
    store = FilesystemMatrixManifestStore(tmp_path)
    options = CulturalCaptureOptions(enabled=True)
    deps = MatrixBatchDependencies(
        package_version="0.0.0-test",
        code_revision="rev-test",
        cultural_capture=options,
    )
    first = await MatrixBatchRunner(deps).run(spec, store)
    assert first.completed == 4
    assert first.failed == 0
    for record in store.list_cells():
        pair = store.read_cultural_artifacts(record.cell_id)
        assert pair is not None
    second = await MatrixBatchRunner(deps).run(spec, store)
    assert second.completed == 0
    assert second.skipped_valid == 4


@pytest.mark.asyncio
async def test_capture_preflight_missing_pair_preserves_objective_completion(
    tmp_path: Path,
) -> None:
    spec = _spec()
    store = FilesystemMatrixManifestStore(tmp_path)
    options = CulturalCaptureOptions(enabled=True)
    deps = MatrixBatchDependencies(
        package_version="0.0.0-test",
        code_revision="rev-test",
        cultural_capture=options,
    )
    await MatrixBatchRunner(deps).run(spec, store)
    target = store.list_cells()[0]
    (tmp_path / "cells" / f"{target.cell_id}.cultural-evidence.json").unlink()
    (tmp_path / "cells" / f"{target.cell_id}.cultural-metrics.json").unlink()

    second = await MatrixBatchRunner(deps).run(spec, store)
    assert second.completed == 0
    assert second.failed == 1
    assert second.skipped_valid == 3
    failed_record = store.get_cell(target.cell_id)
    assert failed_record.state is MatrixCellState.FAILED
    assert failed_record.attempt_count == 1
    assert failed_record.last_error_code == "cultural_capture_missing"


@pytest.mark.asyncio
async def test_capture_preflight_policy_mismatch_does_not_rerun(tmp_path: Path) -> None:
    spec = _spec()
    store = FilesystemMatrixManifestStore(tmp_path)
    deps = MatrixBatchDependencies(
        package_version="0.0.0-test",
        code_revision="rev-test",
        cultural_capture=CulturalCaptureOptions(enabled=True),
    )
    await MatrixBatchRunner(deps).run(spec, store)
    changed = MatrixBatchDependencies(
        package_version="0.0.0-test",
        code_revision="rev-test",
        cultural_capture=CulturalCaptureOptions(enabled=True, max_frames=99),
    )
    second = await MatrixBatchRunner(changed).run(spec, store)
    assert second.completed == 0
    assert second.failed == 4
    assert all(
        record.last_error_code == "cultural_capture_policy_mismatch"
        and record.attempt_count == 1
        for record in store.list_cells()
    )


@pytest.mark.asyncio
async def test_capture_preflight_corrupt_pair_is_invalid(tmp_path: Path) -> None:
    spec = _spec()
    store = FilesystemMatrixManifestStore(tmp_path)
    deps = MatrixBatchDependencies(
        package_version="0.0.0-test",
        code_revision="rev-test",
        cultural_capture=CulturalCaptureOptions(enabled=True),
    )
    await MatrixBatchRunner(deps).run(spec, store)
    target = store.list_cells()[0]
    (tmp_path / "cells" / f"{target.cell_id}.cultural-evidence.json").write_bytes(b"{}")
    second = await MatrixBatchRunner(deps).run(spec, store)
    assert second.failed == 1
    assert store.get_cell(target.cell_id).last_error_code == "cultural_artifact_invalid"


@pytest.mark.asyncio
async def test_cultural_comparison_loader_reads_completed_pairs(tmp_path: Path) -> None:
    from experiments.cultural_metric_comparison import (
        load_cultural_metric_comparison,
    )

    spec = _spec()
    store = FilesystemMatrixManifestStore(tmp_path)
    deps = MatrixBatchDependencies(
        package_version="0.0.0-test",
        code_revision="rev-test",
        cultural_capture=CulturalCaptureOptions(enabled=True),
    )
    await MatrixBatchRunner(deps).run(spec, store)
    comparison = load_cultural_metric_comparison(
        spec=spec,
        cells=expand_matrix(spec)[1],
        store=store,
    )
    assert comparison.schema_version == "cultural-metric-comparison-v1"
    assert len(comparison.conditions) == 4
    assert all(condition.measurements for condition in comparison.conditions)


class _FailingCulturalStore:
    def __init__(self, inner: FilesystemMatrixManifestStore) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> object:
        return getattr(self._inner, name)

    def write_cultural_artifacts(self, cell_id: str, **kwargs: object) -> None:
        from experiments.cultural_metric_artifacts import CulturalArtifactError

        raise CulturalArtifactError("artifact_conflict")


@pytest.mark.asyncio
async def test_cultural_artifact_write_fault_blocks_completion(tmp_path: Path) -> None:
    spec = _spec()
    inner = FilesystemMatrixManifestStore(tmp_path)
    store = _FailingCulturalStore(inner)
    deps = MatrixBatchDependencies(
        package_version="0.0.0-test",
        code_revision="rev-test",
        cultural_capture=CulturalCaptureOptions(enabled=True),
    )
    result = await MatrixBatchRunner(deps).run(spec, store)  # type: ignore[arg-type]
    assert result.completed == 0
    assert result.failed == 4
    assert all(
        record.state is MatrixCellState.FAILED
        and record.last_error_code == "cultural_artifact_conflict"
        for record in inner.list_cells()
    )
    assert not any(
        name.endswith(".completion.json") for name in os.listdir(tmp_path / "cells")
    )
