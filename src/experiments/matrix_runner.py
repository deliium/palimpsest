"""Async process-local matrix batch runner with resume and recovery."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, replace
from typing import Final

from experiments.collectors import collect_for_experiment
from experiments.coordinator import ExperimentArmResult, ExperimentAssignment
from experiments.matrix_expand import expand_matrix
from experiments.matrix_manifest import (
    MatrixCompletionRecord,
    MatrixManifestHeader,
    MatrixManifestStore,
)
from experiments.matrix_models import (
    DEFAULT_SUCCESS_STOP_REASONS,
    EXPERIMENT_MATRIX_SCHEMA_VERSION,
    ExperimentMatrixSpec,
    MatrixCell,
    MatrixCellState,
    MatrixValidationError,
    RunVersionIdentity,
    matrix_spec_fingerprint,
)
from experiments.models import EXPERIMENT_SCHEMA_VERSION, ExperimentDefinition
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import SimulationRunnerResult
from simulation.runner_serialization import runner_config_fingerprint

_LOG: Final[logging.Logger] = logging.getLogger("experiments.matrix_runner")


@dataclass(frozen=True, slots=True)
class MatrixBatchDependencies:
    """Injected version identity sources (never invent wall-clock surrogates)."""

    package_version: str
    code_revision: str = ""


@dataclass(frozen=True, slots=True)
class MatrixBatchResult:
    """Batch outcome summary (metadata only)."""

    definition: ExperimentDefinition
    cells: tuple[MatrixCell, ...]
    arm_results: tuple[ExperimentArmResult, ...]
    completed: int
    failed: int
    skipped_valid: int
    matrix_fingerprint: str


async def run_one_assignment(
    assignment: ExperimentAssignment,
) -> ExperimentArmResult:
    """Run one assignment with a fresh SimulationRunner (shared helper)."""
    async with await SimulationRunner.from_config(
        assignment.runner_config,
        run_id=assignment.run_id,
    ) as runner:
        runner_result = await runner.run()
    fingerprint = runner_config_fingerprint(assignment.runner_config)
    arm = ExperimentArmResult(
        assignment=assignment,
        runner_result=runner_result,
        config_fingerprint=fingerprint,
    )
    metrics = collect_for_experiment(arm)
    return ExperimentArmResult(
        assignment=assignment,
        runner_result=runner_result,
        config_fingerprint=fingerprint,
        metrics=metrics,
    )


def _assignment_for_cell(
    *,
    definition: ExperimentDefinition,
    cell: MatrixCell,
    condition_ordinal: int,
) -> ExperimentAssignment:
    condition = definition.conditions[condition_ordinal]
    config = replace(condition.runner_config, seed=cell.seed)
    return ExperimentAssignment(
        experiment_id=definition.experiment_id,
        condition_id=cell.condition_id,
        condition_ordinal=condition_ordinal,
        seed=cell.seed,
        seed_ordinal=cell.seed_ordinal,
        replicate_index=cell.replicate_index,
        run_id=RunId(cell.cell_id),
        runner_config=config,
    )


def _stop_is_success(result: SimulationRunnerResult) -> bool:
    return result.stop_reason in DEFAULT_SUCCESS_STOP_REASONS


class MatrixBatchRunner:
    """Process-local concurrent matrix runner with filesystem resume."""

    __slots__ = ("_deps",)

    def __init__(self, deps: MatrixBatchDependencies) -> None:
        if type(deps) is not MatrixBatchDependencies:
            raise TypeError("deps must be MatrixBatchDependencies")
        self._deps = deps

    async def run(
        self,
        spec: ExperimentMatrixSpec,
        store: MatrixManifestStore,
    ) -> MatrixBatchResult:
        if type(spec) is not ExperimentMatrixSpec:
            raise TypeError("spec must be ExperimentMatrixSpec")
        definition, cells = expand_matrix(spec)
        matrix_fp = matrix_spec_fingerprint(spec)
        header = MatrixManifestHeader(
            matrix_id=spec.matrix_id,
            matrix_fingerprint=matrix_fp,
        )
        store.create(header, cells)
        store.open()

        condition_ordinals = {
            condition.condition_id: index
            for index, condition in enumerate(definition.conditions)
        }
        cell_by_id = {cell.cell_id: cell for cell in cells}

        # Durable cells force serial execution.
        durable = any(
            definition.conditions[condition_ordinals[cell.condition_id]]
            .runner_config.persistence.durable
            for cell in cells
        )
        max_concurrency = spec.execution.max_concurrency
        if durable and max_concurrency > 1:
            _LOG.error(
                "matrix_durable_requires_serial",
                extra={
                    "experiment": {
                        "matrix_id": spec.matrix_id,
                        "reason_code": "durable_requires_serial_matrix",
                        "max_concurrency": max_concurrency,
                    }
                },
            )
            raise MatrixValidationError(
                "durable_requires_serial_matrix",
                "durable persistence requires max_concurrency=1",
            )
        if durable:
            max_concurrency = 1

        semaphore = asyncio.Semaphore(max_concurrency)
        completed = 0
        failed = 0
        skipped_valid = 0
        arm_results: list[ExperimentArmResult] = []
        stop_batch = False
        pending_ids: list[str] = []
        for record in store.list_cells():
            cell = cell_by_id[record.cell_id]
            if record.state in (
                MatrixCellState.COMPLETED,
                MatrixCellState.SKIPPED_VALID,
            ) or store.has_valid_completion(cell, matrix_fingerprint=matrix_fp):
                if record.state is not MatrixCellState.SKIPPED_VALID:
                    store.transition(
                        record.cell_id, state=MatrixCellState.SKIPPED_VALID
                    )
                skipped_valid += 1
                continue
            if record.state in (MatrixCellState.PENDING, MatrixCellState.FAILED):
                pending_ids.append(record.cell_id)

        _LOG.info(
            "matrix_batch_start",
            extra={
                "experiment": {
                    "matrix_id": spec.matrix_id,
                    "pending_count": len(pending_ids),
                    "skipped_valid": skipped_valid,
                    "max_concurrency": max_concurrency,
                }
            },
        )

        async def _run_cell(cell_id: str) -> None:
            nonlocal completed, failed, skipped_valid, stop_batch
            if stop_batch:
                return
            cell = cell_by_id[cell_id]
            if store.has_valid_completion(cell, matrix_fingerprint=matrix_fp):
                store.transition(cell_id, state=MatrixCellState.SKIPPED_VALID)
                skipped_valid += 1
                _LOG.debug(
                    "matrix_cell_skipped_valid",
                    extra={"experiment": {"cell_id": cell_id}},
                )
                return

            async with semaphore:
                while True:
                    if stop_batch:
                        return
                    record = store.get_cell(cell_id)
                    attempt = record.attempt_count + 1
                    store.transition(
                        cell_id,
                        state=MatrixCellState.RUNNING,
                        attempt_count=attempt,
                    )
                    assignment = _assignment_for_cell(
                        definition=definition,
                        cell=cell,
                        condition_ordinal=condition_ordinals[cell.condition_id],
                    )
                    try:
                        arm = await run_one_assignment(assignment)
                    except Exception as exc:
                        reason = type(exc).__name__
                        retryable = (
                            reason
                            in spec.execution.retry_policy.transient_reason_codes
                        )
                        if (
                            retryable
                            and attempt < spec.execution.retry_policy.max_attempts
                        ):
                            store.transition(
                                cell_id,
                                state=MatrixCellState.PENDING,
                                attempt_count=attempt,
                                last_error_code=reason,
                            )
                            _LOG.warning(
                                "matrix_cell_retry",
                                extra={
                                    "experiment": {
                                        "cell_id": cell_id,
                                        "attempt_count": attempt,
                                        "reason_code": reason,
                                    }
                                },
                            )
                            continue
                        store.transition(
                            cell_id,
                            state=MatrixCellState.FAILED,
                            attempt_count=attempt,
                            last_error_code=reason,
                        )
                        failed += 1
                        if spec.execution.stop_on_first_error:
                            stop_batch = True
                        return

                    if not _stop_is_success(arm.runner_result):
                        store.transition(
                            cell_id,
                            state=MatrixCellState.FAILED,
                            attempt_count=attempt,
                            last_error_code=arm.runner_result.stop_reason.value,
                            run_id=assignment.run_id.value,
                            stop_reason=arm.runner_result.stop_reason.value,
                        )
                        failed += 1
                        if spec.execution.stop_on_first_error:
                            stop_batch = True
                        return

                    identity = RunVersionIdentity(
                        package_version=self._deps.package_version,
                        runner_schema_version=(
                            assignment.runner_config.schema_version
                        ),
                        experiment_schema_version=EXPERIMENT_SCHEMA_VERSION,
                        matrix_schema_version=EXPERIMENT_MATRIX_SCHEMA_VERSION,
                        derivation_version=(
                            assignment.runner_config.derivation_version
                        ),
                        matrix_fingerprint=matrix_fp,
                        cell_fingerprint=cell.cell_fingerprint,
                        config_fingerprint=cell.config_fingerprint,
                        code_revision=self._deps.code_revision,
                    )
                    store.write_completion(
                        MatrixCompletionRecord(
                            cell_id=cell_id,
                            run_id=assignment.run_id.value,
                            stop_reason=arm.runner_result.stop_reason,
                            version_identity=identity,
                        )
                    )
                    arm_results.append(arm)
                    completed += 1
                    return

        await asyncio.gather(*(_run_cell(cell_id) for cell_id in pending_ids))
        _LOG.info(
            "matrix_batch_complete",
            extra={
                "experiment": {
                    "matrix_id": spec.matrix_id,
                    "completed": completed,
                    "failed": failed,
                    "skipped_valid": skipped_valid,
                }
            },
        )
        return MatrixBatchResult(
            definition=definition,
            cells=cells,
            arm_results=tuple(arm_results),
            completed=completed,
            failed=failed,
            skipped_valid=skipped_valid,
            matrix_fingerprint=matrix_fp,
        )


__all__ = [
    "MatrixBatchDependencies",
    "MatrixBatchResult",
    "MatrixBatchRunner",
    "run_one_assignment",
]
