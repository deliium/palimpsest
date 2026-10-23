"""Async process-local matrix batch runner with resume and recovery."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final

from experiments.collectors import collect_for_experiment
from experiments.coordinator import ExperimentArmResult, ExperimentAssignment
from experiments.cultural_metric_artifacts import CulturalCaptureOptions
from experiments.generational_adoption import (
    VerifiedGenerationalArchive,
    verify_completed_archive,
)
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
from simulation.runner_models import (
    RunnerStopReasonCode,
    SimulationRunnerResult,
)
from simulation.runner_serialization import runner_config_fingerprint

_LOG: Final[logging.Logger] = logging.getLogger("experiments.matrix_runner")

# Durable cells at-or-above this max_ticks should enable checkpoint cadence.
_LONG_CELL_TICK_WARN_THRESHOLD: Final[int] = 1_000


@dataclass(frozen=True, slots=True)
class MatrixBatchDependencies:
    """Injected version identity sources (never invent wall-clock surrogates)."""

    package_version: str
    code_revision: str = ""
    archive_root: Path | None = None
    durable_origin_exists: Callable[[str], bool] | None = None
    generational_contexts: (
        Callable[[ExperimentAssignment, str], object | None] | None
    ) = None
    require_generational_context: bool = False
    cultural_capture: object | None = None


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
    *,
    capture_options: object | None = None,
    source_revision: str = "unknown",
) -> ExperimentArmResult:
    """Run one assignment with a fresh SimulationRunner (shared helper)."""
    from experiments.cultural_evidence import (
        install_cultural_recorder,
        kinship_parent_child_edges,
    )

    recorder = None
    kinship_edges: tuple[tuple[str, str], ...] = ()
    async with await SimulationRunner.from_config(
        assignment.runner_config,
        run_id=assignment.run_id,
    ) as runner:
        recorder = install_cultural_recorder(runner, capture_options)  # type: ignore[arg-type]
        if assignment.experiment_id == "cultural_contact@1":
            from experiments.cultural_contact_scenario import (
                cultural_contact_arbiter,
            )

            runner.set_intervention_arbiter(
                cultural_contact_arbiter(
                    assignment.condition_id, assignment.runner_config
                )
            )
        if assignment.experiment_id == "regional_migration@1":
            from experiments.regional_migration_scenario import (
                regional_migration_arbiter,
            )

            runner.set_intervention_arbiter(
                regional_migration_arbiter(
                    assignment.condition_id, assignment.runner_config
                )
            )
        runner_result = await runner.run()
        if recorder is not None:
            recorder.merge_capture_status(runner.export_cultural_capture_status())
        committed_events = tuple(runner.engine.export_events().events)
        kinship_edges = kinship_parent_child_edges(runner.engine.kinship_graph)
        traces = await runner.export_regional_destination_traces()
        from experiments.composition import (
            regional_destination_evidence_rows_from_traces,
        )

        evidence = (
            None
            if traces is None
            else regional_destination_evidence_rows_from_traces(traces)
        )
    fingerprint = runner_config_fingerprint(assignment.runner_config)
    cultural_fields: dict[str, object] = {}
    if recorder is not None and capture_options is not None:
        from experiments.cultural_evidence import build_cultural_arm_fields

        cultural_fields = build_cultural_arm_fields(
            recorder,
            run_id=assignment.run_id.value,
            config_fingerprint=fingerprint,
            options=capture_options,  # type: ignore[arg-type]
            source_revision=source_revision,
            parent_child_edges=kinship_edges,
        )
    arm = ExperimentArmResult(
        assignment=assignment,
        runner_result=runner_result,
        config_fingerprint=fingerprint,
        committed_events=committed_events,
        regional_destination_evidence=evidence,
        **cultural_fields,  # type: ignore[arg-type]
    )
    return replace(arm, metrics=collect_for_experiment(arm))


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


def _archive_stop_reason(
    archive: VerifiedGenerationalArchive,
) -> RunnerStopReasonCode:
    result_document = archive.completion.get("result_document")
    if isinstance(result_document, dict):
        raw = result_document.get("stop_reason")
        if isinstance(raw, str):
            try:
                return RunnerStopReasonCode(raw)
            except ValueError:
                pass
    return RunnerStopReasonCode.MAX_TICKS


def _stop_is_success(result: SimulationRunnerResult) -> bool:
    return result.stop_reason in DEFAULT_SUCCESS_STOP_REASONS


def _cultural_failure_code(error: Exception) -> str:
    if getattr(error, "code", None) == "capture_policy_mismatch":
        return "cultural_capture_policy_mismatch"
    return "cultural_artifact_invalid"


def _check_existing_cultural_artifacts(
    store: MatrixManifestStore,
    *,
    cell: MatrixCell,
    assignment: ExperimentAssignment,
    matrix_fingerprint: str,
    options: CulturalCaptureOptions,
    source_revision: str,
) -> str | None:
    """Return a safe failure code when the required pair is absent or invalid."""
    from experiments.cultural_metric_artifacts import (
        CulturalArtifactError,
        verify_cultural_pair,
    )

    try:
        pair = store.read_cultural_artifacts(cell.cell_id)
    except CulturalArtifactError as exc:
        return _cultural_failure_code(exc)
    if pair is None:
        return "cultural_capture_missing"
    try:
        verify_cultural_pair(
            pair[0],
            pair[1],
            cell_id=cell.cell_id,
            matrix_fingerprint=matrix_fingerprint,
            cell_fingerprint=cell.cell_fingerprint,
            config_fingerprint=runner_config_fingerprint(assignment.runner_config),
            run_id=assignment.run_id.value,
            capture_options=options,
            source_revision=source_revision,
        )
    except CulturalArtifactError as exc:
        return _cultural_failure_code(exc)
    return None


def _write_cultural_artifacts(
    store: MatrixManifestStore,
    *,
    arm: ExperimentArmResult,
    cell: MatrixCell,
    assignment: ExperimentAssignment,
    matrix_fingerprint: str,
    options: CulturalCaptureOptions,
) -> None:
    """Write the bound evidence/metric pair before objective completion."""
    from experiments.cultural_evidence_serialization import (
        encode_cultural_evolution_evidence,
    )
    from experiments.cultural_metric_artifacts import (
        CulturalCellMetrics,
        cultural_capture_policy,
        encode_cultural_cell_metrics,
    )

    evidence_inputs = arm.cultural_evolution_evidence
    capture_status = arm.cultural_evolution_capture_status
    if evidence_inputs is None or capture_status is None:
        from experiments.cultural_metric_artifacts import CulturalArtifactError

        raise CulturalArtifactError("cultural_capture_missing")
    policy = cultural_capture_policy(options)
    config_fingerprint = runner_config_fingerprint(assignment.runner_config)
    evidence_bytes = encode_cultural_evolution_evidence(
        evidence_inputs,  # type: ignore[arg-type]
        config_fingerprint=config_fingerprint,
        capture_options=policy,
        capture_status=capture_status,  # type: ignore[arg-type]
    )
    cell_metrics = CulturalCellMetrics(
        cell_id=cell.cell_id,
        matrix_fingerprint=matrix_fingerprint,
        cell_fingerprint=cell.cell_fingerprint,
        config_fingerprint=config_fingerprint,
        run_id=assignment.run_id.value,
        capture_policy=policy,
        analysis_window=options.analysis_window,
        evidence_digest=arm.cultural_evolution_evidence_digest or "",
        documents=tuple(arm.cultural_evolution_documents),  # type: ignore[arg-type]
        digest="",
    )
    store.write_cultural_artifacts(
        cell.cell_id,
        evidence_bytes=evidence_bytes,
        cell_metrics_bytes=encode_cultural_cell_metrics(cell_metrics),
    )


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
        from experiments.path_dependence_catalog import (
            grouped_experiment_id_from_matrix_base,
            require_independent_execution,
        )

        grouped_id = grouped_experiment_id_from_matrix_base(spec.base)
        if grouped_id is not None:
            require_independent_execution(grouped_id)
        definition, cells = expand_matrix(spec)
        matrix_fp = matrix_spec_fingerprint(spec)
        header = MatrixManifestHeader(
            matrix_id=spec.matrix_id,
            matrix_fingerprint=matrix_fp,
        )
        store.create(header, cells)
        store.open()

        cultural_options = self._deps.cultural_capture
        if (
            cultural_options is not None
            and type(cultural_options) is not CulturalCaptureOptions
        ):
            raise TypeError("cultural_capture must be CulturalCaptureOptions")
        source_revision = self._deps.code_revision or "unknown"

        condition_ordinals = {
            condition.condition_id: index
            for index, condition in enumerate(definition.conditions)
        }
        cell_by_id = {cell.cell_id: cell for cell in cells}

        # Durable cells force serial execution.
        durable = any(
            definition.conditions[
                condition_ordinals[cell.condition_id]
            ].runner_config.persistence.durable
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

        _warn_long_run_checkpoint_guidance(definition, cells, condition_ordinals)

        semaphore = asyncio.Semaphore(max_concurrency)
        completed = 0
        failed = 0
        skipped_valid = 0
        arm_results: list[ExperimentArmResult] = []
        stop_batch = False
        pending_ids: list[str] = []
        for record in store.list_cells():
            cell = cell_by_id[record.cell_id]
            already_valid = record.state in (
                MatrixCellState.COMPLETED,
                MatrixCellState.SKIPPED_VALID,
            ) or store.has_valid_completion(cell, matrix_fingerprint=matrix_fp)
            if already_valid:
                assignment = _assignment_for_cell(
                    definition=definition,
                    cell=cell,
                    condition_ordinal=condition_ordinals[cell.condition_id],
                )
                if cultural_options is not None:
                    failure = _check_existing_cultural_artifacts(
                        store,
                        cell=cell,
                        assignment=assignment,
                        matrix_fingerprint=matrix_fp,
                        options=cultural_options,
                        source_revision=source_revision,
                    )
                    if failure is not None:
                        store.transition(
                            record.cell_id,
                            state=MatrixCellState.FAILED,
                            last_error_code=failure,
                            run_id=assignment.run_id.value,
                        )
                        failed += 1
                        _LOG.error(
                            "matrix_cultural_capture_preflight_failed cell_id=%s "
                            "reason_code=%s",
                            record.cell_id,
                            failure,
                        )
                        continue
                if self._deps.archive_root is not None:
                    if assignment.runner_config.generational_run is not None:
                        archive = verify_completed_archive(
                            root=self._deps.archive_root,
                            run_id=assignment.run_id,
                            expected_config=assignment.runner_config,
                            expected_code_revision=(self._deps.code_revision or None),
                        )
                        if archive is None:
                            _LOG.warning(
                                "matrix_cell_archive_rejected cell_id=%s run_id=%s",
                                record.cell_id,
                                assignment.run_id.value,
                            )
                            store.transition(
                                record.cell_id,
                                state=MatrixCellState.FAILED,
                                last_error_code="archive_identity_mismatch",
                                run_id=assignment.run_id.value,
                            )
                            failed += 1
                            continue
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
                if cultural_options is not None:
                    assignment = _assignment_for_cell(
                        definition=definition,
                        cell=cell,
                        condition_ordinal=condition_ordinals[cell.condition_id],
                    )
                    failure = _check_existing_cultural_artifacts(
                        store,
                        cell=cell,
                        assignment=assignment,
                        matrix_fingerprint=matrix_fp,
                        options=cultural_options,
                        source_revision=source_revision,
                    )
                    if failure is not None:
                        store.transition(
                            cell_id,
                            state=MatrixCellState.FAILED,
                            last_error_code=failure,
                            run_id=assignment.run_id.value,
                        )
                        failed += 1
                        _LOG.error(
                            "matrix_cultural_capture_skip_failed cell_id=%s "
                            "reason_code=%s",
                            cell_id,
                            failure,
                        )
                        return
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
                    archive = None
                    if (
                        self._deps.archive_root is not None
                        and assignment.runner_config.generational_run is not None
                    ):
                        archive = verify_completed_archive(
                            root=self._deps.archive_root,
                            run_id=assignment.run_id,
                            expected_config=assignment.runner_config,
                            expected_code_revision=(self._deps.code_revision or None),
                        )
                    if archive is not None:
                        if cultural_options is not None:
                            failure = _check_existing_cultural_artifacts(
                                store,
                                cell=cell,
                                assignment=assignment,
                                matrix_fingerprint=matrix_fp,
                                options=cultural_options,
                                source_revision=source_revision,
                            )
                            if failure is not None:
                                store.transition(
                                    cell_id,
                                    state=MatrixCellState.FAILED,
                                    last_error_code=failure,
                                    run_id=assignment.run_id.value,
                                )
                                failed += 1
                                _LOG.error(
                                    "matrix_cultural_capture_adoption_failed "
                                    "cell_id=%s reason_code=%s",
                                    cell_id,
                                    failure,
                                )
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
                                stop_reason=_archive_stop_reason(archive),
                                version_identity=identity,
                            )
                        )
                        store.transition(cell_id, state=MatrixCellState.SKIPPED_VALID)
                        skipped_valid += 1
                        _LOG.info(
                            "matrix_cell_archive_adopted",
                            extra={
                                "experiment": {
                                    "cell_id": cell_id,
                                    "attempt_id": archive.attempt_id,
                                }
                            },
                        )
                        return
                    if (
                        assignment.runner_config.persistence.durable
                        and self._deps.durable_origin_exists is not None
                        and self._deps.durable_origin_exists(assignment.run_id.value)
                    ):
                        store.transition(
                            cell_id,
                            state=MatrixCellState.FAILED,
                            attempt_count=attempt,
                            last_error_code="durable_origin_rerun_unsupported",
                            run_id=assignment.run_id.value,
                        )
                        failed += 1
                        if spec.execution.stop_on_first_error:
                            stop_batch = True
                        return
                    context = (
                        None
                        if self._deps.generational_contexts is None
                        else self._deps.generational_contexts(assignment, cell.cell_id)
                    )
                    if (
                        assignment.runner_config.generational_run is not None
                        and context is None
                    ):
                        store.transition(
                            cell_id,
                            state=MatrixCellState.FAILED,
                            attempt_count=attempt,
                            last_error_code="generational_context_required",
                            run_id=assignment.run_id.value,
                        )
                        failed += 1
                        if spec.execution.stop_on_first_error:
                            stop_batch = True
                        return
                    try:
                        if (
                            assignment.runner_config.generational_run is not None
                            and context is not None
                        ):
                            from experiments.generational_execution import (
                                GenerationalExecutionContext,
                                execute_generational_assignment,
                            )

                            if (
                                cultural_options is not None
                                and type(context) is GenerationalExecutionContext
                            ):
                                context = replace(
                                    context, cultural_capture=cultural_options
                                )
                            arm = await execute_generational_assignment(
                                assignment,
                                context,  # type: ignore[arg-type]
                            )
                        else:
                            arm = await run_one_assignment(
                                assignment,
                                capture_options=cultural_options,
                                source_revision=source_revision,
                            )
                    except Exception as exc:
                        reason = type(exc).__name__
                        retryable = (
                            reason in spec.execution.retry_policy.transient_reason_codes
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
                        runner_schema_version=(assignment.runner_config.schema_version),
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
                    if cultural_options is not None:
                        try:
                            _write_cultural_artifacts(
                                store,
                                arm=arm,
                                cell=cell,
                                assignment=assignment,
                                matrix_fingerprint=matrix_fp,
                                options=cultural_options,
                            )
                        except Exception as exc:
                            raw_code = getattr(exc, "code", None)
                            if raw_code == "artifact_conflict":
                                reason = "cultural_artifact_conflict"
                            elif raw_code == "cultural_capture_missing":
                                reason = "cultural_capture_missing"
                            elif raw_code in {"too_large", "excessive_depth"}:
                                reason = "cultural_artifact_invalid"
                            else:
                                reason = "cultural_artifact_write_failed"
                            store.transition(
                                cell_id,
                                state=MatrixCellState.FAILED,
                                attempt_count=attempt,
                                last_error_code=reason,
                                run_id=assignment.run_id.value,
                            )
                            failed += 1
                            _LOG.error(
                                "matrix_cultural_artifact_write_failed "
                                "cell_id=%s reason_code=%s",
                                cell_id,
                                reason,
                            )
                            if spec.execution.stop_on_first_error:
                                stop_batch = True
                            return
                    store.write_completion(
                        MatrixCompletionRecord(
                            cell_id=cell_id,
                            run_id=assignment.run_id.value,
                            stop_reason=arm.runner_result.stop_reason,
                            version_identity=identity,
                        )
                    )
                    try:
                        from experiments.collectors import assemble_arm_metric_bundle

                        bundle = assemble_arm_metric_bundle(arm)
                        write_metrics = getattr(store, "write_metric_documents", None)
                        if write_metrics is not None:
                            write_metrics(cell_id, bundle.documents)
                    except Exception:
                        _LOG.warning(
                            "matrix_metric_sidecar_skip",
                            extra={
                                "experiment": {
                                    "cell_id": cell_id,
                                    "reason_code": "metric_sidecar_failed",
                                }
                            },
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


def _warn_long_run_checkpoint_guidance(
    definition: ExperimentDefinition,
    cells: tuple[MatrixCell, ...],
    condition_ordinals: dict[str, int],
) -> None:
    """WARN when durable long cells run with checkpoints disabled."""
    recommended = 100
    for cell in cells:
        condition = definition.conditions[condition_ordinals[cell.condition_id]]
        config = condition.runner_config
        if not config.persistence.durable:
            continue
        max_ticks = config.stop_policy.max_ticks
        if max_ticks < _LONG_CELL_TICK_WARN_THRESHOLD:
            continue
        checkpoint = config.persistence.checkpoint
        if checkpoint.enabled and checkpoint.cadence_ticks is not None:
            continue
        _LOG.warning(
            "[matrix] long_run_checkpoint_recommended cadence_ticks=%s "
            "cell_id=%s max_ticks=%s",
            recommended,
            cell.cell_id,
            max_ticks,
        )


__all__ = [
    "MatrixBatchDependencies",
    "MatrixBatchResult",
    "MatrixBatchRunner",
    "run_one_assignment",
]
