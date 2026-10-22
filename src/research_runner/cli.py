"""Argparse CLI for reproducible experiment matrices (no FastAPI)."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from experiments.coordinator import ExperimentAssignment
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


def _cmd_run(args: argparse.Namespace) -> int:
    spec = _load_spec(Path(args.matrix))
    store = build_manifest_store(Path(args.manifest_root))
    deps = build_batch_dependencies(code_revision=args.code_revision)
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
        create_pending_finalization_repository,
        create_run_repository,
        create_scientific_evidence_repository,
        create_snapshot_repository,
        create_tick_journal_repository,
    )
    from simulation.models import RunId
    from simulation.runner import RecordingStoreSettings, RunnerDependencyFactories
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
        if args.recording_root is not None:
            from llm.recording import LookupMode

            recording_store = RecordingStoreSettings(
                root_dir=Path(args.recording_root),
                cache_namespace=args.recording_namespace,
                lookup_mode=LookupMode(args.recording_lookup_mode),
            )
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
            )
        if not config.persistence.durable:
            factories = RunnerDependencyFactories(
                recording_store=recording_store
            )
        context = GenerationalExecutionContext(
            artifact_root=Path(args.artifact_root),
            source_identity=source_identity,
            recipe=recipe,
            factories=factories,
            reader=reader,
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
    run_p.set_defaults(func=_cmd_run)

    resume_p = sub.add_parser("resume", help="Resume an existing matrix batch")
    resume_p.add_argument("--matrix", required=True, help="Path to matrix JSON")
    resume_p.add_argument(
        "--manifest-root",
        required=True,
        help="Directory for manifest.json + cells/",
    )
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
