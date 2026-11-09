"""Argparse CLI for reproducible experiment matrices (no FastAPI)."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Final

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
from research_runner.civilization_benchmark_cli import (
    add_civilization_benchmark_parser,
)
from research_runner.composition import (
    build_batch_dependencies,
    build_manifest_store,
)
from research_runner.generational_composition import (
    GenerationalExecutionRecipe,
    PostgresHistoricalBoundaryReader,
)
from research_runner.path_dependence_cli import add_path_dependence_parser

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


_SPOOL_RUN_SEGMENT: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
)


def _run_scoped_spool_factory(root: Path) -> Callable[[str], object]:
    """Give every run/cell its own spool so batches cannot share a lane."""
    from persistence.evidence_spool_filesystem import create_evidence_spool

    resolved = Path(root)

    def _factory(run_id: str) -> object:
        if _SPOOL_RUN_SEGMENT.fullmatch(run_id or "") is None:
            raise ValueError("evidence_spool_run_id_invalid")
        return create_evidence_spool(resolved / run_id)

    return _factory


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
        "spool": getattr(args, "cultural_spool_root", None),
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
    spool_root = getattr(args, "cultural_spool_root", None)
    spool = None
    if spool_root is not None:
        spool = _run_scoped_spool_factory(Path(spool_root))
    return CulturalCaptureOptions(
        enabled=True,
        max_frames=max_frames,
        max_rows=max_rows,
        analysis_window=CulturalAnalysisWindow(
            baseline_boundary=baseline,
            end_boundary=end,
        ),
        spool=spool,
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
    try:
        civilization_options = _civilization_options_from_args(args)
    except (TypeError, ValueError) as exc:
        _LOG.error(
            "cli_civilization_options_invalid",
            extra={"experiment": {"reason_code": str(exc)}},
        )
        return 2
    store = build_manifest_store(Path(args.manifest_root))
    deps = build_batch_dependencies(code_revision=args.code_revision)
    if capture_options is not None:
        from dataclasses import replace

        deps = replace(deps, cultural_capture=capture_options)
    if civilization_options is not None:
        from dataclasses import replace

        from persistence.civilization_filesystem import (
            create_civilization_reader,
        )

        civilization_reader = create_civilization_reader(civilization_options.root)
        deps = replace(
            deps,
            civilization_installer=_civilization_installer(civilization_options),
            civilization_finalizer=_civilization_finalizer(civilization_options),
            civilization_require_durable=True,
            civilization_publication_exists=civilization_reader.has_run,
        )
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


def _lineage_producer_options(
    root: Path,
    cadence: int,
    max_publications: int,
    max_artifact_bytes: int,
    artifact_root: Path,
) -> Any:
    from research_runner.lineage_composition import LineageProducerOptions
    from simulation.lineage_capture import LineageCaptureOptions

    return LineageProducerOptions(
        root=root,
        capture=LineageCaptureOptions(
            cadence=cadence,
            max_publications=max_publications,
            max_artifact_bytes=max_artifact_bytes,
        ),
        artifact_root=artifact_root,
    )


def _lineage_installer(root: Path, cadence: int) -> Callable[[Any], object]:
    from research_runner.lineage_composition import install_lineage_capture

    options = _lineage_producer_options(root, cadence, 1_000, 268_435_456, root)

    def _install(runner: Any) -> object:
        return install_lineage_capture(runner, options)

    return _install


def _make_lineage_installer(options: Any) -> Callable[[Any], object]:
    from research_runner.lineage_composition import install_lineage_capture

    def _install(runner: Any) -> object:
        return install_lineage_capture(runner, options)

    return _install


def _lineage_finalizer(options: Any) -> Callable[[Any, Any], Any]:
    from research_runner.lineage_composition import finalize_lineage_capture

    async def _finalize(arm: Any, session: Any) -> object:
        return await finalize_lineage_capture(arm, session, options)

    return _finalize


def _civilization_producer_options(
    root: Path,
    cadence: int,
    max_boundaries: int,
    max_rows: int,
    max_bytes: int,
    status_root: Path | None,
    spool: object | None = None,
) -> Any:
    from research_runner.civilization_composition import (
        CivilizationProducerOptions,
    )
    from simulation.civilization_capture import CivilizationCaptureOptions

    return CivilizationProducerOptions(
        root=root,
        capture=CivilizationCaptureOptions(
            enabled=True,
            cadence=cadence,
            max_boundaries=max_boundaries,
            max_rows=max_rows,
            max_bytes=max_bytes,
        ),
        status_root=status_root,
        spool=spool,
    )


def _civilization_installer(options: Any) -> Callable[[Any], object]:
    from research_runner.civilization_composition import (
        install_civilization_capture,
    )

    def _install(runner: Any) -> object:
        return install_civilization_capture(runner, options)

    return _install


def _civilization_finalizer(options: Any) -> Callable[[Any, Any], Any]:
    from research_runner.civilization_composition import (
        finalize_civilization_capture,
    )

    async def _finalize(arm: Any, session: Any) -> object:
        return await finalize_civilization_capture(arm, session, options)

    return _finalize


def _civilization_options_from_args(args: argparse.Namespace) -> Any:
    root = getattr(args, "civilization_overlays_root", None)
    spool_root = getattr(args, "civilization_spool_root", None)
    cadence = getattr(args, "civilization_cadence", 1)
    max_boundaries = getattr(args, "civilization_max_boundaries", 10_000)
    max_rows = getattr(args, "civilization_max_rows", 1_000_000)
    max_bytes = getattr(args, "civilization_max_bytes", 268_435_456)
    if root is None and (
        cadence != 1
        or max_boundaries != 10_000
        or max_rows != 1_000_000
        or max_bytes != 268_435_456
    ):
        raise ValueError("civilization options require --civilization-overlays-root")
    if not 1 <= cadence <= 10_000:
        raise ValueError("civilization cadence is outside the supported range")
    if not 1 <= max_boundaries <= 10_000:
        raise ValueError("civilization boundary cap is outside the supported range")
    if not 1 <= max_rows <= 1_000_000:
        raise ValueError("civilization row cap is outside the supported range")
    if not 1 <= max_bytes <= 268_435_456:
        raise ValueError("civilization byte cap is outside the supported range")
    if root is None:
        if spool_root is not None:
            raise ValueError("civilization spool requires --civilization-overlays-root")
        return None
    spool = None
    if spool_root is not None:
        spool = _run_scoped_spool_factory(Path(spool_root))
    return _civilization_producer_options(
        Path(root),
        cadence,
        max_boundaries,
        max_rows,
        max_bytes,
        Path(root),
        spool,
    )


def _parse_auxiliary(values: Sequence[str]) -> tuple[Any, ...]:
    from simulation.history_archive import ArchiveAuxiliarySource

    rows: list[ArchiveAuxiliarySource] = []
    for raw in values:
        parts = raw.split(":", 2)
        if len(parts) != 3 or not all(parts):
            raise ValueError("auxiliary must be NAME:CAPABILITY:PATH")
        rows.append(
            ArchiveAuxiliarySource(
                name=parts[0],
                capability_class=parts[1],
                path=parts[2],
            )
        )
    return tuple(rows)


def _cmd_history_export(args: argparse.Namespace) -> int:
    from infrastructure.database import create_database_resources, dispose_engine
    from infrastructure.settings import load_settings
    from persistence import (
        create_run_repository,
        create_snapshot_repository,
        create_tick_journal_repository,
    )
    from research_runner.history_archive_composition import export_history_archive
    from simulation.clock import Tick
    from simulation.history_archive import ArchiveManifest, HistoryArchiveError
    from simulation.models import RunId

    try:
        auxiliary = _parse_auxiliary(tuple(args.auxiliary))
    except (TypeError, ValueError) as exc:
        _LOG.error(
            "cli_history_export_invalid",
            extra={"experiment": {"reason_code": str(exc)}},
        )
        return 2
    settings = load_settings()

    async def _run_export() -> ArchiveManifest:
        resources = create_database_resources(settings)
        try:
            session_factory = resources.session_factory
            resolved_auxiliary = list(auxiliary)
            if args.export_cognition_traces is not None:
                from persistence import create_cognition_trace_repository
                from research_runner.history_archive_composition import (
                    export_cognition_trace_auxiliary,
                )

                resolved_auxiliary.append(
                    await export_cognition_trace_auxiliary(
                        traces=create_cognition_trace_repository(session_factory),
                        run_id=RunId(args.run_id),
                        path=Path(args.export_cognition_traces),
                    )
                )
            return await export_history_archive(
                runs=create_run_repository(session_factory),
                journal=create_tick_journal_repository(session_factory),
                snapshots=create_snapshot_repository(session_factory),
                root=Path(args.output),
                run_id=RunId(args.run_id),
                through_tick=(
                    None if args.through_tick is None else Tick(args.through_tick)
                ),
                auxiliary=tuple(resolved_auxiliary),
                event_segment_rows=args.event_segment_rows,
                event_segment_bytes=args.event_segment_bytes,
                commit_segment_rows=args.commit_segment_rows,
                commit_segment_bytes=args.commit_segment_bytes,
                snapshot_segment_rows=args.snapshot_segment_rows,
                snapshot_segment_bytes=args.snapshot_segment_bytes,
                index_segment_rows=args.index_segment_rows,
                index_segment_bytes=args.index_segment_bytes,
            )
        finally:
            await dispose_engine(resources.engine)

    try:
        manifest = asyncio.run(_run_export())
    except HistoryArchiveError as exc:
        _LOG.error(
            "cli_history_export_failed",
            extra={"experiment": {"reason_code": exc.code}},
        )
        return 2
    _LOG.info(
        "cli_history_export_ready",
        extra={
            "experiment": {
                "archive_id": manifest.archive_id,
                "run_id": manifest.run_id,
                "event_count": manifest.coverage.event_count,
                "commit_count": manifest.coverage.commit_count,
                "snapshot_count": manifest.coverage.snapshot_count,
            }
        },
    )
    return 0


def _cmd_history_verify(args: argparse.Namespace) -> int:
    from research_runner.history_archive_composition import verify_history_archive
    from simulation.history_archive import HistoryArchiveError
    from simulation.models import RunId

    run_id = None if args.run_id is None else RunId(args.run_id)
    try:
        results = asyncio.run(
            verify_history_archive(
                Path(args.archive),
                run_id=run_id,
                full=bool(args.full),
                sample=args.sample,
            )
        )
    except HistoryArchiveError as exc:
        _LOG.error(
            "cli_history_verify_failed",
            extra={"experiment": {"reason_code": exc.code}},
        )
        return 2
    for result in results:
        _LOG.info(
            "cli_history_verify_ok",
            extra={"experiment": result.payload()},
        )
    return 0


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
        try:
            from research_runner.macro_society_composition import (
                producer_options_from_args,
            )

            macro_society_options = producer_options_from_args(args)
        except (TypeError, ValueError) as exc:
            _LOG.error(
                "cli_macro_society_options_invalid",
                extra={"experiment": {"reason_code": str(exc)}},
            )
            return 2
        try:
            from research_runner.organization_composition import (
                producer_options_from_args as organization_options_from_args,
            )

            organization_options = organization_options_from_args(args)
        except (TypeError, ValueError) as exc:
            _LOG.error(
                "cli_organization_options_invalid",
                extra={"experiment": {"reason_code": str(exc)}},
            )
            return 2
        try:
            from research_runner.formal_rule_composition import (
                producer_options_from_args as formal_rule_options_from_args,
            )

            formal_rule_options = formal_rule_options_from_args(args)
        except (TypeError, ValueError) as exc:
            _LOG.error(
                "cli_formal_rule_options_invalid",
                extra={"experiment": {"reason_code": str(exc)}},
            )
            return 2
        try:
            from research_runner.dispute_composition import (
                producer_options_from_args as dispute_options_from_args,
            )

            dispute_options = dispute_options_from_args(args)
        except (TypeError, ValueError) as exc:
            _LOG.error(
                "cli_dispute_options_invalid",
                extra={"experiment": {"reason_code": str(exc)}},
            )
            return 2
        try:
            from research_runner.evidence_testimony_composition import (
                producer_options_from_args as evidence_options_from_args,
            )

            evidence_options = evidence_options_from_args(args)
        except (TypeError, ValueError) as exc:
            _LOG.error(
                "cli_evidence_options_invalid",
                extra={"experiment": {"reason_code": str(exc)}},
            )
            return 2
        try:
            from research_runner.delegation_representation_composition import (
                producer_options_from_args as representation_options_from_args,
            )

            representation_options = representation_options_from_args(args)
        except (TypeError, ValueError) as exc:
            _LOG.error(
                "cli_representation_options_invalid",
                extra={"experiment": {"reason_code": str(exc)}},
            )
            return 2
        try:
            from research_runner.diplomacy_composition import (
                producer_options_from_args as diplomacy_options_from_args,
            )

            diplomacy_options = diplomacy_options_from_args(args)
        except (TypeError, ValueError) as exc:
            _LOG.error(
                "cli_diplomacy_options_invalid",
                extra={"experiment": {"reason_code": str(exc)}},
            )
            return 2
        try:
            from research_runner.organized_conflict_composition import (
                producer_options_from_args as organized_conflict_options_from_args,
            )

            organized_conflict_options = organized_conflict_options_from_args(args)
        except (TypeError, ValueError) as exc:
            _LOG.error(
                "cli_organized_conflict_options_invalid",
                extra={"experiment": {"reason_code": str(exc)}},
            )
            return 2
        try:
            from research_runner.borders_composition import (
                borders_producer_options_from_args,
            )

            borders_options = borders_producer_options_from_args(args)
        except (TypeError, ValueError) as exc:
            _LOG.error(
                "cli_borders_options_invalid",
                extra={"experiment": {"reason_code": str(exc)}},
            )
            return 2
        try:
            from research_runner.migration_displacement_composition import (
                migration_displacement_producer_options_from_args,
            )

            migration_displacement_options = (
                migration_displacement_producer_options_from_args(args)
            )
        except (TypeError, ValueError) as exc:
            _LOG.error(
                "cli_migration_displacement_options_invalid",
                extra={"experiment": {"reason_code": str(exc)}},
            )
            return 2
        try:
            from research_runner.inter_society_relations_composition import (
                inter_society_relations_producer_options_from_args,
            )

            inter_society_relations_options = (
                inter_society_relations_producer_options_from_args(args)
            )
        except (TypeError, ValueError) as exc:
            _LOG.error(
                "cli_inter_society_relations_options_invalid",
                extra={"experiment": {"reason_code": str(exc)}},
            )
            return 2
        try:
            from research_runner.infrastructure_composition import (
                infrastructure_networks_producer_options_from_args,
            )

            infrastructure_networks_options = (
                infrastructure_networks_producer_options_from_args(args)
            )
        except (TypeError, ValueError) as exc:
            _LOG.error(
                "cli_infrastructure_networks_options_invalid",
                extra={"experiment": {"reason_code": str(exc)}},
            )
            return 2
        lineage_root = getattr(args, "lineage_root", None)
        lineage_cadence = getattr(args, "lineage_cadence", 1)
        lineage_max_publications = getattr(args, "lineage_max_publications", 1000)
        lineage_max_bytes = getattr(args, "lineage_max_bytes", 268435456)
        if lineage_root is None and (
            lineage_cadence != 1
            or lineage_max_publications != 1000
            or lineage_max_bytes != 268435456
        ):
            raise ValueError("lineage options require --lineage-root")
        if lineage_cadence < 1:
            raise ValueError("lineage cadence must be positive")
        if not 1 <= lineage_max_publications <= 1_000:
            raise ValueError("lineage publication cap is outside the supported range")
        if not 1 <= lineage_max_bytes <= 268_435_456:
            raise ValueError("lineage byte cap is outside the supported range")
        try:
            civilization_options = _civilization_options_from_args(args)
        except (TypeError, ValueError) as exc:
            _LOG.error(
                "cli_civilization_options_invalid",
                extra={"experiment": {"reason_code": str(exc)}},
            )
            return 2
        if civilization_options is not None and not config.persistence.durable:
            _LOG.error(
                "cli_civilization_preflight_failed",
                extra={
                    "experiment": {
                        "reason_code": "civilization_capture_requires_durable_run"
                    }
                },
            )
            return 2
        if civilization_options is not None:
            from experiments.generational_adoption import verify_completed_archive
            from persistence.civilization_filesystem import (
                create_civilization_reader,
            )

            archive = verify_completed_archive(
                root=Path(args.artifact_root),
                run_id=RunId(args.run_id),
                expected_config=config,
                expected_code_revision=args.code_revision,
            )
            if archive is not None and not create_civilization_reader(
                civilization_options.root
            ).has_run(args.run_id):
                _LOG.error(
                    "cli_civilization_preflight_failed",
                    extra={
                        "experiment": {"reason_code": "civilization_capture_missing"}
                    },
                )
                return 2
        lineage_options = (
            None
            if lineage_root is None
            else _lineage_producer_options(
                Path(lineage_root),
                lineage_cadence,
                lineage_max_publications,
                lineage_max_bytes,
                Path(args.artifact_root),
            )
        )
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
            lineage_installer=(
                None
                if lineage_options is None
                else _make_lineage_installer(lineage_options)
            ),
            lineage_finalizer=(
                None if lineage_options is None else _lineage_finalizer(lineage_options)
            ),
            civilization_installer=(
                None
                if civilization_options is None
                else _civilization_installer(civilization_options)
            ),
            civilization_finalizer=(
                None
                if civilization_options is None
                else _civilization_finalizer(civilization_options)
            ),
        )
        arm = asyncio.run(execute_generational_assignment(assignment, context))
        print(f"run_id={assignment.run_id.value}")
        print(f"stop_reason={arm.runner_result.stop_reason.value}")
        print(f"ticks_committed={arm.runner_result.ticks_committed}")
        if macro_society_options.enabled:
            import json

            from analysis.macro_society_contract import MacroSocietyError
            from experiments.macro_society_completed_run import (
                build_completed_run_harvest,
            )
            from research_runner.macro_society_composition import (
                publish_macro_society_harvest,
            )
            from simulation.runner_models import runner_stop_is_failure

            receipt: dict[str, object]
            if runner_stop_is_failure(arm.runner_result.stop_reason):
                receipt = {
                    "status": "unavailable",
                    "reason_code": "macro_society_run_incomplete",
                }
            else:
                try:
                    harvest = build_completed_run_harvest(
                        run_id=assignment.run_id.value,
                        input_revision=arm.config_fingerprint,
                        events=arm.committed_events or (),
                        generated_tick=arm.runner_result.ticks_committed,
                    )
                except (MacroSocietyError, ValueError) as exc:
                    receipt = {
                        "status": "unavailable",
                        "reason_code": getattr(
                            exc, "reason_code", "macro_society_harvest_unavailable"
                        ),
                    }
                else:
                    receipt = publish_macro_society_harvest(
                        options=macro_society_options, harvest=harvest
                    )
            receipt_path = Path(args.artifact_root) / (
                f"macro-society-publication-{assignment.run_id.value}.json"
            )
            try:
                receipt_path.write_text(
                    json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n",
                    encoding="utf-8",
                )
            except OSError:
                _LOG.warning(
                    "macro_society_receipt_write_failed run=%s",
                    assignment.run_id.value,
                )
            print(f"macro_society_publication_status={receipt['status']}")
            print(f"macro_society_publication_reason={receipt['reason_code']}")
            if "publication_id" in receipt:
                print(f"macro_society_publication_id={receipt['publication_id']}")
        if organization_options.enabled:
            import json

            from research_runner.organization_composition import (
                publish_organization_harvest,
            )

            receipt = publish_organization_harvest(
                runner_result=arm.runner_result,
                run_id=assignment.run_id.value,
                input_revision=arm.config_fingerprint,
                generated_tick=arm.runner_result.ticks_committed,
                options=organization_options,
            )
            receipt_path = Path(args.artifact_root) / (
                f"organization-publication-{assignment.run_id.value}.json"
            )
            try:
                receipt_path.write_text(
                    json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n",
                    encoding="utf-8",
                )
            except OSError:
                _LOG.warning(
                    "organization_receipt_write_failed run=%s",
                    assignment.run_id.value,
                )
            print(f"organization_publication_status={receipt['status']}")
            print(f"organization_publication_reason={receipt['reason_code']}")
            if "publication_id" in receipt:
                print(f"organization_publication_id={receipt['publication_id']}")
        if formal_rule_options.enabled:
            from research_runner.formal_rule_composition import (
                publish_formal_rule_harvest,
                write_formal_rule_receipt,
            )

            formal_rule_receipt = publish_formal_rule_harvest(
                runner_result=arm.runner_result,
                run_id=assignment.run_id.value,
                input_revision=arm.config_fingerprint,
                generated_tick=arm.runner_result.ticks_committed,
                options=formal_rule_options,
            )
            write_formal_rule_receipt(
                args.artifact_root,
                run_id=assignment.run_id.value,
                receipt=formal_rule_receipt,
            )
            print(f"formal_rule_publication_status={formal_rule_receipt['status']}")
            print(
                f"formal_rule_publication_reason={formal_rule_receipt['reason_code']}"
            )
            if "publication_id" in formal_rule_receipt:
                print(
                    "formal_rule_publication_id="
                    f"{formal_rule_receipt['publication_id']}"
                )
        if dispute_options.enabled:
            from research_runner.dispute_composition import (
                publish_dispute_harvest,
                write_dispute_receipt,
            )

            dispute_receipt = publish_dispute_harvest(
                arm.runner_result,
                dispute_options,
                run_id=assignment.run_id.value,
                input_revision=arm.config_fingerprint,
                generated_tick=arm.runner_result.ticks_committed,
                entity_to_agent={
                    agent.entity_id.value: agent.agent_id.value
                    for agent in arm.assignment.runner_config.agents
                },
            )
            write_dispute_receipt(
                Path(args.artifact_root),
                assignment.run_id.value,
                dispute_receipt,
            )
            print(f"dispute_publication_status={dispute_receipt['status']}")
            print(f"dispute_publication_reason={dispute_receipt['reason_code']}")
            if "publication_id" in dispute_receipt:
                print(f"dispute_publication_id={dispute_receipt['publication_id']}")
        if evidence_options.enabled:
            from research_runner.evidence_testimony_composition import (
                publish_evidence_testimony_harvest,
                write_evidence_testimony_receipt,
            )

            evidence_receipt = publish_evidence_testimony_harvest(
                arm.runner_result,
                evidence_options,
                run_id=assignment.run_id.value,
                input_revision=arm.config_fingerprint,
                generated_tick=arm.runner_result.ticks_committed,
                entity_to_agent={
                    agent.entity_id.value: agent.agent_id.value
                    for agent in arm.assignment.runner_config.agents
                },
            )
            write_evidence_testimony_receipt(
                Path(args.artifact_root),
                assignment.run_id.value,
                evidence_receipt,
            )
            print(f"evidence_publication_status={evidence_receipt['status']}")
            print(f"evidence_publication_reason={evidence_receipt['reason_code']}")
            if "publication_id" in evidence_receipt:
                print(f"evidence_publication_id={evidence_receipt['publication_id']}")
        if representation_options.enabled:
            from research_runner.delegation_representation_composition import (
                publish_representation_harvest,
                write_representation_receipt,
            )

            representation_receipt = publish_representation_harvest(
                arm.runner_result,
                representation_options,
                entity_to_agent={
                    agent.entity_id.value: agent.agent_id.value
                    for agent in arm.assignment.runner_config.agents
                },
            )
            write_representation_receipt(
                Path(args.artifact_root),
                assignment.run_id.value,
                representation_receipt,
            )
            print(
                f"representation_publication_status={representation_receipt['status']}"
            )
            print(
                f"representation_publication_reason={representation_receipt['reason']}"
            )
            if "publication_id" in representation_receipt:
                print(
                    "representation_publication_id="
                    f"{representation_receipt['publication_id']}"
                )
        if diplomacy_options.enabled:
            from research_runner.diplomacy_composition import (
                publish_diplomacy_harvest,
                write_diplomacy_receipt,
            )

            diplomacy_receipt = publish_diplomacy_harvest(
                arm.runner_result,
                diplomacy_options,
                entity_to_agent={
                    agent.entity_id.value: agent.agent_id.value
                    for agent in arm.assignment.runner_config.agents
                },
                run_id=assignment.run_id.value,
                revision=arm.config_fingerprint,
                window_end=arm.runner_result.ticks_committed,
            )
            write_diplomacy_receipt(
                Path(args.artifact_root),
                assignment.run_id.value,
                diplomacy_receipt,
            )
            print(f"diplomacy_publication_status={diplomacy_receipt['status']}")
            print(f"diplomacy_publication_reason={diplomacy_receipt.get('reason')}")
            if diplomacy_receipt.get("publication_id"):
                print(f"diplomacy_publication_id={diplomacy_receipt['publication_id']}")
        if organized_conflict_options.enabled:
            from research_runner.organized_conflict_composition import (
                publish_organized_conflict_harvest,
                write_organized_conflict_receipt,
            )

            organized_conflict_receipt = publish_organized_conflict_harvest(
                arm.runner_result,
                organized_conflict_options,
                committed_events=arm.committed_events or (),
                run_id=assignment.run_id.value,
            )
            write_organized_conflict_receipt(
                Path(args.artifact_root),
                assignment.run_id.value,
                organized_conflict_receipt,
            )
            print(
                "organized_conflict_publication_status="
                f"{organized_conflict_receipt['status']}"
            )
            print(
                "organized_conflict_publication_reason="
                f"{organized_conflict_receipt.get('reason')}"
            )
        if borders_options.enabled:
            from research_runner.borders_composition import (
                publish_borders_harvest,
                write_borders_receipt,
            )

            borders_receipt = publish_borders_harvest(
                arm.runner_result,
                borders_options,
                committed_events=arm.committed_events or (),
                run_id=assignment.run_id.value,
            )
            write_borders_receipt(
                Path(args.artifact_root),
                assignment.run_id.value,
                borders_receipt,
            )
            print(f"borders_publication_status={borders_receipt['status']}")
            print(f"borders_publication_reason={borders_receipt.get('reason')}")
            if borders_receipt.get("publication_id"):
                print(f"borders_publication_id={borders_receipt['publication_id']}")
        if migration_displacement_options.enabled:
            from research_runner.migration_displacement_composition import (
                publish_migration_displacement_harvest,
                write_migration_displacement_receipt,
            )

            migration_displacement_receipt = publish_migration_displacement_harvest(
                arm.runner_result,
                migration_displacement_options,
                committed_events=arm.committed_events or (),
                run_id=assignment.run_id.value,
            )
            write_migration_displacement_receipt(
                Path(args.artifact_root),
                assignment.run_id.value,
                migration_displacement_receipt,
            )
            print(
                "migration_displacement_publication_status="
                f"{migration_displacement_receipt['status']}"
            )
            print(
                "migration_displacement_publication_reason="
                f"{migration_displacement_receipt.get('reason')}"
            )
            if migration_displacement_receipt.get("publication_id"):
                print(
                    "migration_displacement_publication_id="
                    f"{migration_displacement_receipt['publication_id']}"
                )
        if inter_society_relations_options.enabled:
            from research_runner.inter_society_relations_composition import (
                publish_inter_society_relations_harvest,
                write_inter_society_relations_receipt,
            )

            inter_society_relations_receipt = publish_inter_society_relations_harvest(
                arm.runner_result,
                inter_society_relations_options,
                committed_events=arm.committed_events or (),
                run_id=assignment.run_id.value,
            )
            write_inter_society_relations_receipt(
                Path(args.artifact_root),
                assignment.run_id.value,
                inter_society_relations_receipt,
            )
            print(
                "inter_society_relations_publication_status="
                f"{inter_society_relations_receipt['status']}"
            )
            print(
                "inter_society_relations_publication_reason="
                f"{inter_society_relations_receipt.get('reason')}"
            )
            if inter_society_relations_receipt.get("publication_id"):
                print(
                    "inter_society_relations_publication_id="
                    f"{inter_society_relations_receipt['publication_id']}"
                )
        if infrastructure_networks_options.enabled:
            from research_runner.infrastructure_composition import (
                publish_infrastructure_networks_harvest,
                write_infrastructure_networks_receipt,
            )

            infrastructure_networks_receipt = publish_infrastructure_networks_harvest(
                arm.runner_result,
                infrastructure_networks_options,
                committed_events=arm.committed_events or (),
                run_id=assignment.run_id.value,
            )
            write_infrastructure_networks_receipt(
                Path(args.artifact_root),
                assignment.run_id.value,
                infrastructure_networks_receipt,
            )
            print(
                "infrastructure_networks_publication_status="
                f"{infrastructure_networks_receipt['status']}"
            )
            print(
                "infrastructure_networks_publication_reason="
                f"{infrastructure_networks_receipt.get('reason')}"
            )
            if infrastructure_networks_receipt.get("publication_id"):
                print(
                    "infrastructure_networks_publication_id="
                    f"{infrastructure_networks_receipt['publication_id']}"
                )
        if lineage_options is not None:
            import json

            status_path = Path(args.artifact_root) / (
                f"lineage-capture-status-{assignment.run_id.value}.json"
            )
            if status_path.is_file():
                status = json.loads(status_path.read_text(encoding="utf-8"))
                print(f"lineage_capture_published={len(status.get('published', []))}")
                print(
                    f"lineage_capture_unavailable={len(status.get('unavailable', []))}"
                )
                print(f"lineage_capture_failure={status.get('failure_code')}")
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
    parser.add_argument("--macro-society-root", default=None)
    parser.add_argument("--macro-society-max-publications", type=int, default=16)
    parser.add_argument("--macro-society-max-bytes", type=int, default=8_388_608)
    parser.add_argument("--lineage-root", default=None)
    parser.add_argument("--lineage-cadence", type=int, default=1)
    parser.add_argument("--lineage-max-publications", type=int, default=1000)
    parser.add_argument("--lineage-max-bytes", type=int, default=268435456)
    parser.add_argument("--civilization-overlays-root", default=None)
    parser.add_argument("--civilization-cadence", type=int, default=1)
    parser.add_argument("--civilization-max-boundaries", type=int, default=10_000)
    parser.add_argument("--civilization-max-rows", type=int, default=1_000_000)
    parser.add_argument("--civilization-max-bytes", type=int, default=268_435_456)
    parser.add_argument("--civilization-spool-root", default=None)
    parser.add_argument("--cultural-spool-root", default=None)
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
    gen_p.add_argument("--macro-society-root", default=None)
    gen_p.add_argument("--macro-society-max-publications", type=int, default=16)
    gen_p.add_argument("--macro-society-max-bytes", type=int, default=8_388_608)
    gen_p.add_argument("--organization-root", default=None)
    gen_p.add_argument("--organization-max-publications", type=int, default=16)
    gen_p.add_argument("--organization-max-bytes", type=int, default=8_388_608)
    gen_p.add_argument("--formal-rule-root", default=None)
    gen_p.add_argument("--formal-rule-max-publications", type=int, default=16)
    gen_p.add_argument("--formal-rule-max-bytes", type=int, default=8_388_608)
    gen_p.add_argument("--dispute-root", default=None)
    gen_p.add_argument("--dispute-max-publications", type=int, default=16)
    gen_p.add_argument("--dispute-max-bytes", type=int, default=8_388_608)
    gen_p.add_argument("--evidence-root", default=None)
    gen_p.add_argument("--evidence-max-publications", type=int, default=16)
    gen_p.add_argument("--evidence-max-bytes", type=int, default=8_388_608)
    gen_p.add_argument("--representation-root", default=None)
    gen_p.add_argument("--representation-max-publications", type=int, default=16)
    gen_p.add_argument("--representation-max-bytes", type=int, default=8_388_608)
    gen_p.add_argument("--diplomacy-root", default=None)
    gen_p.add_argument("--diplomacy-max-publications", type=int, default=16)
    gen_p.add_argument("--diplomacy-max-bytes", type=int, default=8_388_608)
    gen_p.add_argument("--organized-conflict-root", default=None)
    gen_p.add_argument("--organized-conflict-max-publications", type=int, default=16)
    gen_p.add_argument("--organized-conflict-max-bytes", type=int, default=8_388_608)
    gen_p.add_argument("--borders-root", default=None)
    gen_p.add_argument("--borders-max-publications", type=int, default=16)
    gen_p.add_argument("--borders-max-bytes", type=int, default=8_388_608)
    gen_p.add_argument("--migration-displacement-root", default=None)
    gen_p.add_argument(
        "--migration-displacement-max-publications", type=int, default=16
    )
    gen_p.add_argument(
        "--migration-displacement-max-bytes", type=int, default=8_388_608
    )
    gen_p.add_argument("--inter-society-relations-root", default=None)
    gen_p.add_argument(
        "--inter-society-relations-max-publications", type=int, default=16
    )
    gen_p.add_argument(
        "--inter-society-relations-max-bytes", type=int, default=8_388_608
    )
    gen_p.add_argument("--infrastructure-networks-root", default=None)
    gen_p.add_argument(
        "--infrastructure-networks-max-publications", type=int, default=16
    )
    gen_p.add_argument(
        "--infrastructure-networks-max-bytes", type=int, default=8_388_608
    )
    gen_p.add_argument("--lineage-root", default=None)
    gen_p.add_argument("--lineage-cadence", type=int, default=1)
    gen_p.add_argument("--lineage-max-publications", type=int, default=1000)
    gen_p.add_argument("--lineage-max-bytes", type=int, default=268435456)
    gen_p.add_argument("--civilization-overlays-root", default=None)
    gen_p.add_argument("--civilization-cadence", type=int, default=1)
    gen_p.add_argument("--civilization-max-boundaries", type=int, default=10_000)
    gen_p.add_argument("--civilization-max-rows", type=int, default=1_000_000)
    gen_p.add_argument("--civilization-max-bytes", type=int, default=268435456)
    gen_p.set_defaults(func=_cmd_generational)

    export_p = sub.add_parser(
        "history-export",
        help="Copy one verified durable run into an offline history archive",
    )
    export_p.add_argument("--run-id", required=True)
    export_p.add_argument("--output", required=True, help="Archive root")
    export_p.add_argument(
        "--export-cognition-traces",
        default=None,
        help=(
            "Write a canonical read-only cognition-trace auxiliary JSONL file; "
            "traces stay outside scientific history and are not deleted"
        ),
    )
    export_p.add_argument("--through-tick", type=int, default=None)
    export_p.add_argument(
        "--auxiliary",
        action="append",
        default=[],
        metavar="NAME:CAPABILITY:PATH",
    )
    export_p.add_argument("--event-segment-rows", type=int, default=512)
    export_p.add_argument("--event-segment-bytes", type=int, default=524288)
    export_p.add_argument("--commit-segment-rows", type=int, default=1000)
    export_p.add_argument("--commit-segment-bytes", type=int, default=524288)
    export_p.add_argument("--snapshot-segment-rows", type=int, default=32)
    export_p.add_argument("--snapshot-segment-bytes", type=int, default=8388608)
    export_p.add_argument("--index-segment-rows", type=int, default=1024)
    export_p.add_argument("--index-segment-bytes", type=int, default=262144)
    export_p.set_defaults(func=_cmd_history_export)

    verify_p = sub.add_parser(
        "history-verify",
        help="Verify archive hashes, coverage and sampled objective replay",
    )
    verify_p.add_argument("--archive", required=True)
    verify_p.add_argument("--run-id", default=None)
    verify_p.add_argument("--full", action="store_true")
    verify_p.add_argument("--sample", type=int, default=3)
    verify_p.set_defaults(func=_cmd_history_verify)
    add_path_dependence_parser(sub)
    add_civilization_benchmark_parser(sub)

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
