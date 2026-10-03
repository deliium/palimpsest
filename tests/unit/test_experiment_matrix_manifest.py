"""Unit tests for filesystem matrix manifest store."""

from __future__ import annotations

import pytest

from experiments.matrix_expand import expand_matrix
from experiments.matrix_factors import matrix_reference_fixture_base
from experiments.matrix_manifest import (
    FilesystemMatrixManifestStore,
    MatrixCompletionRecord,
    MatrixManifestHeader,
)
from experiments.matrix_models import (
    EXPERIMENT_MATRIX_SCHEMA_VERSION,
    ExperimentMatrixSpec,
    GroupRole,
    MatrixCellState,
    MatrixEmbeddedBase,
    MatrixFactor,
    MatrixFactorId,
    MatrixFactorLevel,
    MatrixValidationError,
    RunVersionIdentity,
    matrix_spec_fingerprint,
)
from experiments.models import ExperimentSeedMatrix
from simulation.runner_models import RunnerStopReasonCode


def _expand(tmp_path):
    spec = ExperimentMatrixSpec(
        matrix_id="matrix-manifest-demo",
        schema_version=EXPERIMENT_MATRIX_SCHEMA_VERSION,
        base=MatrixEmbeddedBase(runner_config=matrix_reference_fixture_base()),
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
            MatrixFactor(
                factor_id=MatrixFactorId.TOM,
                levels=(
                    MatrixFactorLevel(level_id="off", label_code="tom_off"),
                    MatrixFactorLevel(level_id="on", label_code="tom_on"),
                ),
            ),
        ),
        seed_matrix=ExperimentSeedMatrix(seeds=(11,)),
    )
    _definition, cells = expand_matrix(spec)
    fingerprint = matrix_spec_fingerprint(spec)
    store = FilesystemMatrixManifestStore(tmp_path)
    store.create(
        MatrixManifestHeader(
            matrix_id=spec.matrix_id,
            matrix_fingerprint=fingerprint,
        ),
        cells,
    )
    return spec, cells, fingerprint, store


def test_create_open_and_crash_reset(tmp_path) -> None:
    _spec, cells, fingerprint, store = _expand(tmp_path)
    header = store.open()
    assert header.matrix_fingerprint == fingerprint
    cell = cells[0]
    store.transition(cell.cell_id, state=MatrixCellState.RUNNING)
    assert store.get_cell(cell.cell_id).state is MatrixCellState.RUNNING
    # Re-open without completion → crash reset to pending.
    store2 = FilesystemMatrixManifestStore(tmp_path)
    store2.open()
    assert store2.get_cell(cell.cell_id).state is MatrixCellState.PENDING
    assert store2.get_cell(cell.cell_id).last_error_code == "crash_reset"


def test_valid_completion_and_divergent_rewrite(tmp_path) -> None:
    spec, cells, fingerprint, store = _expand(tmp_path)
    cell = cells[0]
    identity = RunVersionIdentity(
        package_version="0.0.0",
        runner_schema_version="runner-config-v4",
        experiment_schema_version="experiment-definition-v1",
        matrix_schema_version=EXPERIMENT_MATRIX_SCHEMA_VERSION,
        derivation_version="derivation-v1",
        matrix_fingerprint=fingerprint,
        cell_fingerprint=cell.cell_fingerprint,
        config_fingerprint=cell.config_fingerprint,
        code_revision="",
    )
    store.write_completion(
        MatrixCompletionRecord(
            cell_id=cell.cell_id,
            run_id="run-1",
            stop_reason=RunnerStopReasonCode.MAX_TICKS,
            version_identity=identity,
        )
    )
    assert store.has_valid_completion(cell, matrix_fingerprint=fingerprint)
    # Divergent rewrite fails closed.
    with pytest.raises(MatrixValidationError) as exc:
        store.create(
            MatrixManifestHeader(
                matrix_id=spec.matrix_id,
                matrix_fingerprint="f" * 64,
            ),
            cells,
        )
    assert exc.value.code == "divergent_manifest_rewrite"
