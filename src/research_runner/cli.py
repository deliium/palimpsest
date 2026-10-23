"""Argparse CLI for reproducible experiment matrices (no FastAPI)."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from analysis.cultural_evolution_evidence import CulturalAnalysisWindow
from analysis.cultural_metric_comparison import (
    CULTURAL_METRIC_COMPARISON_SCHEMA_VERSION,
    CulturalComparisonRequest,
    CulturalMetricComparison,
)
from experiments.coordinator import ExperimentAssignment
from experiments.cultural_metric_artifacts import (
    CulturalArtifactError,
    CulturalCaptureOptions,
)
from experiments.cultural_metric_comparison import (
    encode_cultural_metric_comparison,
    load_cultural_metric_comparison,
)
from experiments.generational_execution import (
    GenerationalExecutionContext,
    execute_generational_assignment,
)
from experiments.matrix_aggregate import (
    build_matrix_aggregate,
    encode_matrix_aggregate,
)
from experiments.matrix_expand import expand_matrix
from experiments.matrix_metric_summary import (
    encode_matrix_metric_summary,
    load_matrix_metric_summary_from_store,
)
from experiments.matrix_models import ExperimentMatrixSpec, matrix_spec_fingerprint
from experiments.matrix_runner import MatrixBatchRunner
from experiments.matrix_serialization import decode_matrix_spec
from research_runner.composition import (
    build_batch_dependencies,
    build_manifest_store,
)
from research_runner.generational_composition import (
    GenerationalExecutionRecipe,
    PostgresHistoricalBoundaryReader,
)

_LOG: Final[logging.Logger] = logging.getLogger("research_runner.cli")


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s %(message)s",
    )


def _load_spec(path: Path) -> ExperimentMatrixSpec:
    payload = path.read_bytes()
    return decode_matrix_spec(payload)


def _matrix_max_ticks(spec: ExperimentMatrixSpec) -> int:
    config = getattr(getattr(spec, "base", None), "runner_config", None)
    if config is None:
        definition, _cells = expand_matrix(spec)
        config = definition.conditions[0].runner_config
    max_ticks = getattr(config.stop_policy, "max_ticks", 0)
    return 0 if max_ticks is None else int(max_ticks)


def _build_capture_options(
    args: argparse.Namespace,
    spec: ExperimentMatrixSpec,
) -> CulturalCaptureOptions | None:
    capture = bool(getattr(args, "cultural_metrics", False))
    supplied = {
        "max_frames": getattr(args, "cultural_max_frames", None),
        "max_rows": getattr(args, "cultural_max_rows", None),
        "baseline": getattr(args, "cultural_baseline_boundary", None),
        "end": getattr(args, "cultural_end_boundary", None),
    }
    if not capture:
        if any(value is not None for value in supplied.values()):
            raise ValueError("cultural_options_require_capture")
        return None
    max_frames = (
        10_000 if supplied["max_frames"] is None else int(supplied["max_frames"])
    )
    max_rows = 1_000_000 if supplied["max_rows"] is None else int(supplied["max_rows"])
    baseline = 0 if supplied["baseline"] is None else int(supplied["baseline"])
    end = None if supplied["end"] is None else int(supplied["end"])
    if max_frames < 1 or max_rows < 1:
        raise ValueError("cultural_capture_cap_invalid")
    if baseline < 0:
        raise ValueError("cultural_baseline_invalid")
    horizon = _matrix_max_ticks(spec)
    if baseline > horizon:
        raise ValueError("cultural_baseline_exceeds_horizon")
    if end is not None and (end <= baseline or end > horizon):
        raise ValueError("cultural_end_boundary_invalid")
    return CulturalCaptureOptions(
        enabled=True,
        max_frames=max_frames,
        max_rows=max_rows,
        analysis_window=CulturalAnalysisWindow(
            baseline_boundary=baseline,
            end_boundary=end,
        ),
    )


def _parse_contrasts(
    raw_values: Sequence[str],
    known_conditions: frozenset[str],
) -> tuple[CulturalComparisonRequest, ...]:
    requests: list[CulturalComparisonRequest] = []
    seen: set[tuple[str, str]] = set()
    for index, raw in enumerate(raw_values, start=1):
        if raw.count(":") != 1:
            raise ValueError("cultural_contrast_invalid")
        control, treatment = raw.split(":")
        if not control or not treatment or control == treatment:
            raise ValueError("cultural_contrast_invalid")
        if control not in known_conditions or treatment not in known_conditions:
            raise ValueError("cultural_contrast_unknown_condition")
        if (control, treatment) in seen:
            raise ValueError("cultural_contrast_duplicate")
        seen.add((control, treatment))
        requests.append(
            CulturalComparisonRequest(
                contrast_id=f"contrast-{index}",
                control_condition_id=control,
                treatment_condition_id=treatment,
            )
        )
    return tuple(requests)


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _cmd_run(args: argparse.Namespace) -> int:
    spec = _load_spec(Path(args.matrix))
    try:
        capture_options = _build_capture_options(args, spec)
    except (TypeError, ValueError) as exc:
        _LOG.error(
            "cli_cultural_options_invalid",
            extra={"experiment": {"reason_code": str(exc)}},
        )
        return 2
    store = build_manifest_store(Path(args.manifest_root))
    deps = build_batch_dependencies(code_revision=args.code_revision)
    if capture_options is not None:
        from dataclasses import replace

        deps = replace(deps, cultural_capture=capture_options)
    resources = None
    try:
        if args.generational_artifact_root is not None:
            from dataclasses import replace

            from experiments.matrix_models import MatrixEmbeddedBase
            from simulation.runner import (
                RunnerDependencyFactories,
                recording_store_settings,
            )

            if not args.source_clean and not args.source_artifact_digest:
                _LOG.error(
                    "cli_generational_preflight_failed",
                    extra={"experiment": {"reason_code": "source_assertion_required"}},
                )
                return 2
            if args.execution_recipe is None:
                _LOG.error(
                    "cli_generational_preflight_failed",
                    extra={"experiment": {"reason_code": "execution_recipe_required"}},
                )
                return 2
            try:
                recipe = _load_recipe(Path(args.execution_recipe))
            except Exception as exc:
                _LOG.error(
                    "cli_generational_preflight_failed",
                    extra={"experiment": {"reason_code": type(exc).__name__}},
                )
                return 2
            recording_values = (
                args.recording_root,
                args.recording_artifact_id,
                args.recording_namespace,
                args.recording_lookup_mode,
            )
            if any(recording_values) and not all(recording_values):
                _LOG.error(
                    "cli_generational_preflight_failed",
                    extra={"experiment": {"reason_code": "recording_flags_incomplete"}},
                )
                return 2
            recording_identity = (
                {
                    "recording_artifact_id": args.recording_artifact_id,
                    "recording_namespace": args.recording_namespace,
                    "lookup_mode": args.recording_lookup_mode,
                }
                if all(recording_values)
                else None
            )
            recording_store = (
                recording_store_settings(
                    root_dir=Path(args.recording_root),
                    cache_namespace=args.recording_namespace,
                    lookup_mode=args.recording_lookup_mode,
                )
                if args.recording_root is not None
                else None
            )
            durable = (
                isinstance(spec.base, MatrixEmbeddedBase)
                and spec.base.runner_config.persistence.durable
            )
            factories = RunnerDependencyFactories(recording_store=recording_store)
            reader = None
            if durable:
                from infrastructure.database import (
                    create_database_resources,
                    dispose_engine,
                )
                from infrastructure.settings import load_settings
                from persistence import (
                    create_analysis_evidence_loader,
                    create_pending_finalization_repository,
                    create_run_repository,
                    create_scientific_evidence_repository,
                    create_snapshot_repository,
                    create_tick_journal_repository,
                )

                settings = load_settings(env_file=False)
                resources = create_database_resources(settings)
                session_factory = resources.session_factory
                factories = RunnerDependencyFactories(
                    recording_store=recording_store,
                    run_repository=create_run_repository(session_factory),
                    journal=create_tick_journal_repository(session_factory),
                    pending_finalizations=(
                        create_pending_finalization_repository(session_factory)
                    ),
                    scientific_evidence=(
                        create_scientific_evidence_repository(session_factory)
                    ),
                )
                from research_runner.generational_composition import (
                    PostgresHistoricalBoundaryReader,
                )

                reader = PostgresHistoricalBoundaryReader(
                    runs=create_run_repository(session_factory),
                    journal=create_tick_journal_repository(session_factory),
                    snapshots=create_snapshot_repository(session_factory),
                    evidence=create_scientific_evidence_repository(session_factory),
                )
                from research_runner.generational_composition import (
                    PostgresCommunitySampleProvider,
                )

                analysis_loader = create_analysis_evidence_loader(session_factory)
            source_identity = {
                "code_revision": args.code_revision or "",
                "source_clean": bool(args.source_clean),
                "source_artifact_digest": args.source_artifact_digest,
            }
            base_context = GenerationalExecutionContext(
                artifact_root=Path(args.generational_artifact_root),
                source_identity=source_identity,
                recipe=recipe,
                factories=factories,
                reader=reader,
                recording_identity=recording_identity,
            )

            def _context_for(assignment: ExperimentAssignment, cell_id: str) -> object:
                generational = assignment.runner_config.generational_run
                cadence = (
                    None
                    if generational is None
                    else generational.historical_checkpoint_cadence_ticks
                )
                attempt_id = (
                    f"{assignment.condition_id}-"
                    f"{assignment.condition_ordinal}-"
                    f"{assignment.replicate_index}-"
                    f"{assignment.seed_ordinal}"
                )
                community_provider = (
                    None
                    if reader is None
                    else PostgresCommunitySampleProvider(
                        loader=analysis_loader,
                        run_id=assignment.run_id.value,
                        owner_id=assignment.runner_config.agents[0].agent_id.value,
                        window_ticks=cadence or 100,
                    )
                )
                return replace(
                    base_context,
                    attempt_id=attempt_id,
                    matrix_id=spec.matrix_id,
                    cell_id=cell_id,
                    condition_ordinal=assignment.condition_ordinal,
                    community_sampler=(
                        None
                        if community_provider is None
                        else community_provider.sample
                    ),
                    criterion_factory=(
                        None
                        if community_provider is None
                        else community_provider.criterion_factory()
                    ),
                    cadence_ticks=cadence,
                    sample_on_generation_change=(
                        True
                        if generational is None
                        else generational.sample_on_generation_change
                    ),
                    reader=reader if cadence is not None else None,
                )

            deps = replace(
                deps,
                archive_root=Path(args.generational_artifact_root),
                generational_contexts=_context_for,
                require_generational_context=True,
            )
        runner = MatrixBatchRunner(deps)
        _LOG.info(
            "cli_matrix_run",
            extra={
                "experiment": {
                    "command": "run",
                    "matrix_id": spec.matrix_id,
                    "manifest_root": str(args.manifest_root),
                }
            },
        )
        result = asyncio.run(runner.run(spec, store))
        aggregate = build_matrix_aggregate(
            matrix_id=spec.matrix_id,
            matrix_fingerprint=result.matrix_fingerprint,
            cells=result.cells,
            arm_results=result.arm_results,
        )
        out = Path(args.manifest_root) / "aggregate.json"
        out.write_bytes(encode_matrix_aggregate(aggregate))
        _LOG.info(
            "cli_matrix_run_complete",
            extra={
                "experiment": {
                    "completed": result.completed,
                    "failed": result.failed,
                    "skipped_valid": result.skipped_valid,
                }
            },
        )
        if args.print_fingerprint:
            print(result.matrix_fingerprint)
        return 0 if result.failed == 0 else 1
    finally:
        if resources is not None:
            from infrastructure.database import dispose_engine

            asyncio.run(dispose_engine(resources.engine))


def _cmd_resume(args: argparse.Namespace) -> int:
    # Resume is identical to run against an existing manifest root.
    return _cmd_run(args)


def _cmd_status(args: argparse.Namespace) -> int:
    store = build_manifest_store(Path(args.manifest_root))
    header = store.open()
    records = store.list_cells()
    counts: dict[str, int] = {}
    for record in records:
        counts[record.state.value] = counts.get(record.state.value, 0) + 1
    _LOG.info(
        "cli_matrix_status",
        extra={
            "experiment": {
                "command": "status",
                "matrix_id": header.matrix_id,
                "cell_counts": counts,
            }
        },
    )
    print(f"matrix_id={header.matrix_id}")
    print(f"fingerprint_prefix={header.matrix_fingerprint[:12]}")
    for state, count in sorted(counts.items()):
        print(f"{state}={count}")
    if args.print_fingerprint:
        print(header.matrix_fingerprint)
    return 0


def _cmd_aggregate(args: argparse.Namespace) -> int:
    spec = _load_spec(Path(args.matrix))
    _definition, cells = expand_matrix(spec)
    store = build_manifest_store(Path(args.manifest_root))
    header = store.open()
    fingerprint = matrix_spec_fingerprint(spec)
    if header.matrix_fingerprint != fingerprint:
        _LOG.error(
            "cli_aggregate_fingerprint_mismatch",
            extra={"experiment": {"reason_code": "fingerprint_mismatch"}},
        )
        return 2
    summary_requested = bool(getattr(args, "cultural_summary", False))
    contrast_values = tuple(getattr(args, "cultural_contrast", ()) or ())
    confidence_arg = getattr(args, "confidence", None)
    if (contrast_values or confidence_arg is not None) and not summary_requested:
        _LOG.error(
            "cli_cultural_summary_options_invalid",
            extra={"experiment": {"reason_code": "cultural_summary_required"}},
        )
        return 2
    confidence = 0.95 if confidence_arg is None else float(confidence_arg)
    if not 0.0 < confidence < 1.0:
        _LOG.error(
            "cli_cultural_summary_options_invalid",
            extra={"experiment": {"reason_code": "invalid_confidence"}},
        )
        return 2
    try:
        comparisons = _parse_contrasts(
            contrast_values,
            frozenset(cell.condition_id for cell in cells),
        )
    except ValueError as exc:
        _LOG.error(
            "cli_cultural_summary_options_invalid",
            extra={"experiment": {"reason_code": str(exc)}},
        )
        return 2
    # Aggregate from completion sidecars only when arm results unavailable —
    # status-only aggregate emits empty arm_results refs from completed cells.
    aggregate = build_matrix_aggregate(
        matrix_id=spec.matrix_id,
        matrix_fingerprint=fingerprint,
        cells=cells,
        arm_results=(),
    )
    out = Path(args.aggregate_out or (Path(args.manifest_root) / "aggregate.json"))
    out.write_bytes(encode_matrix_aggregate(aggregate))
    if args.metric_summary:
        summary = load_matrix_metric_summary_from_store(store, cells)
        summary_out = Path(args.manifest_root) / "metric-summary.json"
        summary_out.write_bytes(encode_matrix_metric_summary(summary))
        _LOG.info(
            "cli_matrix_metric_summary",
            extra={
                "experiment": {
                    "command": "aggregate",
                    "output_path": str(summary_out),
                    "key_summary_count": len(summary.key_summaries),
                }
            },
        )
    if summary_requested:
        comparison_out = Path(args.manifest_root) / "cultural-metric-comparison.json"
        try:
            comparison = load_cultural_metric_comparison(
                spec=spec,
                cells=cells,
                store=store,
                comparisons=comparisons,
                confidence=confidence,
                source_revision=args.code_revision or None,
            )
        except CulturalArtifactError as exc:
            if exc.code != "cultural_capture_missing":
                _LOG.error(
                    "cli_cultural_summary_failed",
                    extra={"experiment": {"reason_code": exc.code}},
                )
                return 1
            _LOG.warning(
                "cli_cultural_summary_insufficient",
                extra={"experiment": {"reason_code": "cultural_capture_missing"}},
            )
            comparison = CulturalMetricComparison(
                schema_version=CULTURAL_METRIC_COMPARISON_SCHEMA_VERSION,
                matrix_fingerprint=fingerprint,
                confidence=confidence,
                method="student_t_seed_block_mean",
                conditions=(),
                contrasts=(),
                excluded_cells=tuple(sorted(cell.cell_id for cell in cells)),
                reasons=("cultural_capture_missing",),
            )
        except Exception as exc:
            _LOG.error(
                "cli_cultural_summary_failed",
                extra={"experiment": {"reason_code": type(exc).__name__}},
            )
            return 1
        _write_atomic(
            comparison_out,
            encode_cultural_metric_comparison(comparison),
        )
        _LOG.info(
            "cli_cultural_metric_comparison",
            extra={
                "experiment": {
                    "command": "aggregate",
                    "output_path": str(comparison_out),
                    "condition_count": len(comparison.conditions),
                    "contrast_count": len(comparison.contrasts),
                }
            },
        )
    _LOG.info(
        "cli_matrix_aggregate",
        extra={
            "experiment": {
                "command": "aggregate",
                "matrix_id": spec.matrix_id,
                "cell_count": len(cells),
            }
        },
    )
    return 0


def _load_recipe(path: Path) -> GenerationalExecutionRecipe:
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("execution recipe must be an object")
    expected = {
        "recipe_id",
        "version",
        "params",
        "intervention_id",
        "intervention_version",
        "intervention_params",
    }
    if set(data) != expected:
        raise ValueError("execution recipe exact key set mismatch")
    return GenerationalExecutionRecipe(
        recipe_id=data["recipe_id"],
        version=data["version"],
        params=data["params"],
        intervention_id=data["intervention_id"],
        intervention_version=data["intervention_version"],
        intervention_params=data["intervention_params"],
    )


def _cmd_generational(args: argparse.Namespace) -> int:
    from dataclasses import replace

    from infrastructure.database import create_database_resources, dispose_engine
    from infrastructure.settings import load_settings
    from persistence import (
        create_analysis_evidence_loader,
        create_pending_finalization_repository,
        create_run_repository,
        create_scientific_evidence_repository,
        create_snapshot_repository,
        create_tick_journal_repository,
    )
    from research_runner.generational_composition import (
        PostgresCommunitySampleProvider,
    )
    from simulation.models import RunId
    from simulation.runner import (
        RunnerDependencyFactories,
        recording_store_settings,
    )
    from simulation.runner_models import ExperimentAssignmentRef
    from simulation.runner_serialization import decode_runner_config

    try:
        config = decode_runner_config(Path(args.config).read_bytes())
        if config.generational_run is None:
            raise ValueError("generational command requires runner-config-v55")
        recipe = _load_recipe(Path(args.execution_recipe))
        if args.source_clean and args.source_artifact_digest:
            raise ValueError("choose --source-clean or --source-artifact-digest")
        if not args.source_clean and not args.source_artifact_digest:
            raise ValueError("source clean assertion or artifact digest required")
        source_identity = {
            "code_revision": args.code_revision,
            "source_clean": bool(args.source_clean),
            "source_artifact_digest": args.source_artifact_digest,
        }
        recording_values = (
            args.recording_root,
            args.recording_artifact_id,
            args.recording_namespace,
            args.recording_lookup_mode,
        )
        if any(recording_values) and not all(recording_values):
            raise ValueError("recording flags require a complete set")
        if config.provider.recording_policy.value == "deterministic_fake" and any(
            recording_values
        ):
            raise ValueError("deterministic fake rejects recording flags")
        experiment = config.experiment or ExperimentAssignmentRef(
            experiment_id="generational_runner_ad_hoc@1",
            condition_id="standalone",
            replicate_index=0,
            seed_ordinal=0,
        )
        config = replace(config, experiment=experiment)
        assignment = ExperimentAssignment(
            experiment_id=experiment.experiment_id,
            condition_id=experiment.condition_id,
            condition_ordinal=0,
            seed=config.seed,
            seed_ordinal=experiment.seed_ordinal,
            replicate_index=experiment.replicate_index,
            run_id=RunId(args.run_id),
            runner_config=config,
        )
    except Exception as exc:
        _LOG.error(
            "cli_generational_preflight_failed",
            extra={"experiment": {"reason_code": type(exc).__name__}},
        )
        return 2

    resources = None
    try:
        factories = RunnerDependencyFactories()
        reader = None
        recording_store = None
        recording_identity = None
        if args.recording_root is not None:
            recording_store = recording_store_settings(
                root_dir=Path(args.recording_root),
                cache_namespace=args.recording_namespace,
                lookup_mode=args.recording_lookup_mode,
            )
            recording_identity = {
                "recording_artifact_id": args.recording_artifact_id,
                "recording_namespace": args.recording_namespace,
                "lookup_mode": args.recording_lookup_mode,
            }
        if config.persistence.durable:
            settings = load_settings(env_file=False)
            resources = create_database_resources(settings)
            session_factory = resources.session_factory
            factories = RunnerDependencyFactories(
                run_repository=create_run_repository(session_factory),
                journal=create_tick_journal_repository(session_factory),
                pending_finalizations=create_pending_finalization_repository(
                    session_factory
                ),
                scientific_evidence=create_scientific_evidence_repository(
                    session_factory
                ),
                recording_store=recording_store,
            )
            reader = PostgresHistoricalBoundaryReader(
                runs=create_run_repository(session_factory),
                journal=create_tick_journal_repository(session_factory),
                snapshots=create_snapshot_repository(session_factory),
                evidence=create_scientific_evidence_repository(session_factory),
            )
            community_provider = PostgresCommunitySampleProvider(
                loader=create_analysis_evidence_loader(session_factory),
                run_id=assignment.run_id.value,
                owner_id=config.agents[0].agent_id.value,
                window_ticks=(
                    config.generational_run.historical_checkpoint_cadence_ticks or 100
                    if config.generational_run is not None
                    else 100
                ),
            )
        else:
            community_provider = None
        if not config.persistence.durable:
            factories = RunnerDependencyFactories(recording_store=recording_store)
        context = GenerationalExecutionContext(
            artifact_root=Path(args.artifact_root),
            source_identity=source_identity,
            recipe=recipe,
            factories=factories,
            reader=reader,
            recording_identity=recording_identity,
            community_sampler=(
                None if community_provider is None else community_provider.sample
            ),
            criterion_factory=(
                None
                if community_provider is None
                else community_provider.criterion_factory()
            ),
            cadence_ticks=(
                None
                if config.generational_run is None
                else config.generational_run.historical_checkpoint_cadence_ticks
            ),
            sample_on_generation_change=(
                True
                if config.generational_run is None
                else config.generational_run.sample_on_generation_change
            ),
        )
        arm = asyncio.run(execute_generational_assignment(assignment, context))
        print(f"run_id={assignment.run_id.value}")
        print(f"stop_reason={arm.runner_result.stop_reason.value}")
        print(f"ticks_committed={arm.runner_result.ticks_committed}")
        return 0
    except Exception as exc:
        _LOG.error(
            "cli_generational_execution_failed",
            extra={"experiment": {"reason_code": type(exc).__name__}},
        )
        return 1
    finally:
        if resources is not None:
            asyncio.run(dispose_engine(resources.engine))


def _add_generational_matrix_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--generational-artifact-root", default=None)
    parser.add_argument("--execution-recipe", default=None)
    parser.add_argument("--source-clean", action="store_true")
    parser.add_argument("--source-artifact-digest", default=None)
    parser.add_argument("--recording-root", default=None)
    parser.add_argument("--recording-artifact-id", default=None)
    parser.add_argument("--recording-namespace", default=None)
    parser.add_argument("--recording-lookup-mode", default=None)
    parser.add_argument(
        "--cultural-metrics",
        action="store_true",
        help="Opt in to detached cultural evidence capture",
    )
    parser.add_argument("--cultural-max-frames", type=int, default=None)
    parser.add_argument("--cultural-max-rows", type=int, default=None)
    parser.add_argument("--cultural-baseline-boundary", type=int, default=None)
    parser.add_argument("--cultural-end-boundary", type=int, default=None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="palimpsest-matrix",
        description="Run resumable experiment matrices (no HTTP).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging",
    )
    parser.add_argument(
        "--print-fingerprint",
        action="store_true",
        help="Print matrix fingerprint (metadata only)",
    )
    parser.add_argument(
        "--code-revision",
        default=None,
        help="Optional injected code revision (else PALIMPSEST_CODE_REVISION)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Expand and run a matrix batch")
    run_p.add_argument("--matrix", required=True, help="Path to matrix JSON")
    run_p.add_argument(
        "--manifest-root",
        required=True,
        help="Directory for manifest.json + cells/",
    )
    _add_generational_matrix_args(run_p)
    run_p.set_defaults(func=_cmd_run)

    resume_p = sub.add_parser("resume", help="Resume an existing matrix batch")
    resume_p.add_argument("--matrix", required=True, help="Path to matrix JSON")
    resume_p.add_argument(
        "--manifest-root",
        required=True,
        help="Directory for manifest.json + cells/",
    )
    _add_generational_matrix_args(resume_p)
    resume_p.set_defaults(func=_cmd_resume)

    status_p = sub.add_parser("status", help="Show cell state counts")
    status_p.add_argument(
        "--manifest-root",
        required=True,
        help="Directory for manifest.json + cells/",
    )
    status_p.set_defaults(func=_cmd_status)

    agg_p = sub.add_parser("aggregate", help="Write matrix-aggregate-v1 JSON")
    agg_p.add_argument("--matrix", required=True, help="Path to matrix JSON")
    agg_p.add_argument(
        "--manifest-root",
        required=True,
        help="Directory for manifest.json + cells/",
    )
    agg_p.add_argument(
        "--aggregate-out",
        default=None,
        help="Optional aggregate output path",
    )
    agg_p.add_argument(
        "--metric-summary",
        action="store_true",
        help="Also write matrix-metric-summary-v1 from cell metric sidecars",
    )
    agg_p.add_argument(
        "--cultural-summary",
        action="store_true",
        help="Also write cultural-metric-comparison-v1 from verified cell artifacts",
    )
    agg_p.add_argument(
        "--cultural-contrast",
        action="append",
        default=[],
        metavar="CONTROL:TREATMENT",
        help="Explicit paired condition contrast (requires --cultural-summary)",
    )
    agg_p.add_argument(
        "--confidence",
        type=float,
        default=None,
        help="Student-t confidence level (default 0.95; requires --cultural-summary)",
    )
    agg_p.set_defaults(func=_cmd_aggregate)
    gen_p = sub.add_parser(
        "generational",
        help="Run one generational runner configuration with an archive",
    )
    gen_p.add_argument("--config", required=True, help="Runner config JSON")
    gen_p.add_argument(
        "--execution-recipe", required=True, help="Registered recipe JSON"
    )
    gen_p.add_argument("--artifact-root", required=True, help="Archive root")
    gen_p.add_argument("--run-id", required=True, help="Scientific run ID")
    gen_p.add_argument("--code-revision", required=True, help="Source revision")
    source_group = gen_p.add_mutually_exclusive_group()
    source_group.add_argument("--source-clean", action="store_true")
    source_group.add_argument("--source-artifact-digest", default=None)
    gen_p.add_argument("--recording-root", default=None)
    gen_p.add_argument("--recording-artifact-id", default=None)
    gen_p.add_argument("--recording-namespace", default=None)
    gen_p.add_argument("--recording-lookup-mode", default=None)
    gen_p.set_defaults(func=_cmd_generational)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    _configure_logging(args.verbose)
    _LOG.info(
        "cli_start",
        extra={"experiment": {"command": args.command}},
    )
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
