"""Proofs for matrix resume, crash reset, fingerprint mismatch, and group_role."""

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
    MatrixExecutionPolicy,
    MatrixFactor,
    MatrixFactorId,
    MatrixFactorLevel,
    MatrixGroupOverlay,
    MatrixValidationError,
    RunVersionIdentity,
    matrix_spec_fingerprint,
)
from experiments.matrix_runner import MatrixBatchDependencies, MatrixBatchRunner
from experiments.models import ExperimentSeedMatrix
from simulation.runner_models import RunnerStopReasonCode


def _spec() -> ExperimentMatrixSpec:
    return ExperimentMatrixSpec(
        matrix_id="matrix-resume-demo",
        schema_version=EXPERIMENT_MATRIX_SCHEMA_VERSION,
        base=MatrixEmbeddedBase(
            runner_config=matrix_reference_fixture_base(max_ticks=1)
        ),
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
                factor_id=MatrixFactorId.IMAGINATION,
                levels=(
                    MatrixFactorLevel(
                        level_id="disabled",
                        label_code="imag_off",
                        group_role=GroupRole.CONTROL,
                    ),
                    MatrixFactorLevel(
                        level_id="enabled",
                        label_code="imag_on",
                        group_role=GroupRole.TREATMENT,
                    ),
                ),
            ),
        ),
        seed_matrix=ExperimentSeedMatrix(seeds=(11,)),
        execution=MatrixExecutionPolicy(max_concurrency=1),
        groups=(
            MatrixGroupOverlay(
                group_id="force-control",
                level_match=(
                    ("memory_type", "reconstructive"),
                    ("imagination", "enabled"),
                ),
                group_role=GroupRole.CONTROL,
            ),
        ),
    )


def test_group_role_overlay_and_treatment_any() -> None:
    _definition, cells = expand_matrix(_spec())
    roles = {cell.condition_id: cell.group_role for cell in cells}
    assert (
        roles["memory_type-reference__imagination-disabled"] is GroupRole.CONTROL
    )
    assert (
        roles["memory_type-reference__imagination-enabled"] is GroupRole.TREATMENT
    )
    # Overlay forces reconstructive+enabled → control despite treatment levels.
    assert (
        roles["memory_type-reconstructive__imagination-enabled"] is GroupRole.CONTROL
    )


@pytest.mark.asyncio
async def test_crash_running_resets_and_reruns(tmp_path) -> None:
    spec = _spec()
    definition, cells = expand_matrix(spec)
    fingerprint = matrix_spec_fingerprint(spec)
    store = FilesystemMatrixManifestStore(tmp_path)
    store.create(
        MatrixManifestHeader(
            matrix_id=spec.matrix_id,
            matrix_fingerprint=fingerprint,
        ),
        cells,
    )
    # Complete one cell, leave another stuck in running.
    done = cells[0]
    identity = RunVersionIdentity(
        package_version="0.0.0",
        runner_schema_version="runner-config-v4",
        experiment_schema_version="experiment-definition-v1",
        matrix_schema_version=EXPERIMENT_MATRIX_SCHEMA_VERSION,
        derivation_version=definition.conditions[0].runner_config.derivation_version,
        matrix_fingerprint=fingerprint,
        cell_fingerprint=done.cell_fingerprint,
        config_fingerprint=done.config_fingerprint,
    )
    store.write_completion(
        MatrixCompletionRecord(
            cell_id=done.cell_id,
            run_id="run-done",
            stop_reason=RunnerStopReasonCode.MAX_TICKS,
            version_identity=identity,
        )
    )
    stuck = cells[1]
    store.transition(stuck.cell_id, state=MatrixCellState.RUNNING)
    store.open()
    assert store.get_cell(stuck.cell_id).state is MatrixCellState.PENDING

    runner = MatrixBatchRunner(
        MatrixBatchDependencies(package_version="0.0.0-test")
    )
    result = await runner.run(spec, store)
    assert result.skipped_valid >= 1
    assert result.completed >= 1
    assert store.get_cell(stuck.cell_id).state in (
        MatrixCellState.COMPLETED,
        MatrixCellState.SKIPPED_VALID,
    )


def test_fingerprint_mismatch_fails_closed(tmp_path) -> None:
    spec = _spec()
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
    # Tamper completion with wrong matrix fingerprint.
    cell = cells[0]
    bad = RunVersionIdentity(
        package_version="0.0.0",
        runner_schema_version="runner-config-v4",
        experiment_schema_version="experiment-definition-v1",
        matrix_schema_version=EXPERIMENT_MATRIX_SCHEMA_VERSION,
        derivation_version="derivation-v1",
        matrix_fingerprint="0" * 64,
        cell_fingerprint=cell.cell_fingerprint,
        config_fingerprint=cell.config_fingerprint,
    )
    store.write_completion(
        MatrixCompletionRecord(
            cell_id=cell.cell_id,
            run_id="run-bad",
            stop_reason=RunnerStopReasonCode.MAX_TICKS,
            version_identity=bad,
        )
    )
    assert not store.has_valid_completion(cell, matrix_fingerprint=fingerprint)
    with pytest.raises(MatrixValidationError) as exc:
        store.create(
            MatrixManifestHeader(
                matrix_id=spec.matrix_id,
                matrix_fingerprint="1" * 64,
            ),
            cells,
        )
    assert exc.value.code == "divergent_manifest_rewrite"


def test_factor_expansion_shares_stochastic_identity() -> None:
    definition, _cells = expand_matrix(_spec())
    identities = {
        cond.runner_config.stochastic_identity for cond in definition.conditions
    }
    assert len(identities) == 1
    seeds = {cond.runner_config.seed for cond in definition.conditions}
    assert len(seeds) == 1
