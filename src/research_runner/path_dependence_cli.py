"""CLI helpers for historical-contingency research artifacts (no HTTP)."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path
from typing import Final, cast

from analysis.path_dependence_comparison import (
    ComparisonContrast,
    PathDependenceComparisonRequest,
    PathDependenceOutcomeCell,
    build_path_dependence_comparison,
)
from analysis.path_dependence_models import compute_path_dependence_outcomes
from experiments.cultural_evidence import CulturalEvidenceRecorder
from experiments.path_dependence_artifacts import (
    PathDependenceArtifactStore,
    build_branch_document,
    build_comparison_document,
    build_ensemble_document,
    build_outcomes_document,
    build_prefix_document,
)
from experiments.path_dependence_evidence import PathDependenceEvidenceRecorder
from experiments.path_dependence_models import PathDependenceSpec
from experiments.path_dependence_resume import (
    ResumeDecision,
    classify_path_dependence_resume,
)
from experiments.path_dependence_runner import (
    PathDependenceBatchRunner,
    PathDependenceExecutionContext,
    PathDependenceExecutionSummary,
)
from experiments.path_dependence_serialization import (
    action_schedule_digest,
    decode_path_dependence_spec,
)
from research_runner.path_dependence_composition import (
    build_path_dependence_postgres_composition,
)
from simulation.branch_service import rematerialize_snapshot
from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.fork_checkpoint import RunnerForkCheckpoint
from simulation.models import RunId
from simulation.persistence import SnapshotId
from simulation.runner import RunnerDependencyFactories

_LOG: Final[logging.Logger] = logging.getLogger("research_runner.path_dependence_cli")


class PathDependenceCliError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _store(path: Path) -> PathDependenceArtifactStore:
    if not path.is_absolute():
        raise PathDependenceCliError("artifact_path_unsafe")
    return PathDependenceArtifactStore(path)


def _ensemble(
    store: PathDependenceArtifactStore, ensemble_id: str
) -> dict[str, object]:
    return store.read_ensemble(ensemble_id)


def _spec(document: dict[str, object]) -> PathDependenceSpec:
    import json

    return decode_path_dependence_spec(
        json.dumps(document["spec"], sort_keys=True).encode("utf-8")
    )


def _int_value(value: object, code: str = "artifact_identity_mismatch") -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise PathDependenceCliError(code)
    return value


def _float_value(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PathDependenceCliError("artifact_identity_mismatch")
    return float(value)


def _slots(document: dict[str, object]) -> dict[str, dict[str, object]]:
    raw = document.get("slots")
    if not isinstance(raw, list):
        raise PathDependenceCliError("artifact_identity_mismatch")
    slots: dict[str, dict[str, object]] = {}
    for slot in raw:
        if not isinstance(slot, dict):
            raise PathDependenceCliError("artifact_identity_mismatch")
        child_id = slot.get("child_run_id")
        if type(child_id) is not str or not child_id:
            raise PathDependenceCliError("artifact_identity_mismatch")
        slots[child_id] = slot
    return slots


def _prefix_dir(store: PathDependenceArtifactStore) -> Path:
    return store.root


def cmd_inspect(args: argparse.Namespace) -> int:
    """Read-only lineage inventory for one ensemble."""
    store = _store(Path(args.ensemble))
    ensemble = _ensemble(store, args.ensemble_id)
    slots = _slots(ensemble)
    prefixes = 0
    branches = 0
    completed = 0
    failures = 0
    for path in store.root.rglob("*.json"):
        name = path.name
        if name == "prefix.json":
            prefixes += 1
        elif name in {"preparation.json", "branch.json"}:
            branches += 1
        elif name == "completion.json":
            completed += 1
        elif name == "failure.json":
            failures += 1
    print(f"ensemble_id={ensemble['ensemble_id']}")
    print(f"spec_fingerprint={ensemble['spec_fingerprint']}")
    print(f"slots={len(slots)} prefixes={prefixes} branches={branches}")
    print(f"completed={completed} failures={failures}")
    _LOG.info(
        "path_dependence_inspect ensemble_id=%s slots=%s completed=%s",
        ensemble["ensemble_id"],
        len(slots),
        completed,
    )
    return 0


def _cells_and_contrasts(
    store: PathDependenceArtifactStore, ensemble: dict[str, object]
) -> tuple[tuple[PathDependenceOutcomeCell, ...], tuple[ComparisonContrast, ...]]:
    spec = _spec(ensemble)
    slots = _slots(ensemble)
    contrasts = tuple(
        ComparisonContrast(item.contrast_id, item.control_arm_id, item.treatment_arm_id)
        for item in spec.contrasts
    )
    by_child: dict[str, dict[str, object]] = {}
    for path in store.root.rglob("branch.json"):
        data = store.read_branch(
            ensemble_id=str(ensemble["ensemble_id"]),
            child_id=path.parent.parent.name,
            attempt_id=path.parent.name,
            kind="result",
        )
        by_child[str(data["child_scientific_id"])] = data
    cells: list[PathDependenceOutcomeCell] = []
    for path in store.root.rglob("outcomes.json"):
        child_id = path.parent.parent.name
        attempt_id = path.parent.name
        outcomes = store.read_outcomes(
            ensemble_id=str(ensemble["ensemble_id"]),
            child_id=child_id,
            attempt_id=attempt_id,
        )
        result = by_child.get(child_id)
        if result is None:
            continue
        slot = slots.get(child_id)
        if slot is None:
            raise PathDependenceCliError("artifact_identity_mismatch")
        rows = outcomes.get("rows")
        if not isinstance(rows, list):
            raise PathDependenceCliError("artifact_identity_mismatch")
        for row in rows:
            if not isinstance(row, dict):
                raise PathDependenceCliError("artifact_identity_mismatch")
            cells.append(
                PathDependenceOutcomeCell(
                    cell_id=f"{child_id}:{row['selector_id']}:{row['window_id']}",
                    parent_id=str(result["parent_scientific_id"]),
                    fork_tick=_int_value(result["fork_tick"]),
                    numeric_seed=_int_value(slot["numeric_seed"]),
                    seed_ordinal=_int_value(slot["seed_ordinal"]),
                    replicate=_int_value(slot["replicate"]),
                    arm_id=str(result["arm_id"]),
                    contrast_id=",".join(item.contrast_id for item in contrasts),
                    outcome_key=str(row["selector_id"]),
                    window_id=str(row["window_id"]),
                    source_digest=str(result["prefix_digest"]),
                    channel_alignment="shared",
                    value=_float_value(row.get("value")),
                    availability=str(row.get("availability", "present")),
                    config_digest=str(ensemble["config_fingerprint"]),
                    provider_basis=str(
                        getattr(
                            spec.base.provider,
                            "adapter_kind",
                            "deterministic_fake",
                        )
                    ),
                    planned_child_run_id=child_id,
                    child_run_id=child_id,
                )
            )
    return tuple(cells), contrasts


def cmd_compare(args: argparse.Namespace) -> int:
    store = _store(Path(args.ensemble))
    ensemble = _ensemble(store, args.ensemble_id)
    cells, contrasts = _cells_and_contrasts(store, ensemble)
    if not contrasts:
        raise PathDependenceCliError("missing_contrast")
    per_contrast: list[PathDependenceOutcomeCell] = []
    for cell in cells:
        for contrast in contrasts:
            per_contrast.append(
                PathDependenceOutcomeCell(
                    cell_id=cell.cell_id,
                    parent_id=cell.parent_id,
                    fork_tick=cell.fork_tick,
                    numeric_seed=cell.numeric_seed,
                    seed_ordinal=cell.seed_ordinal,
                    replicate=cell.replicate,
                    arm_id=cell.arm_id,
                    contrast_id=contrast.contrast_id,
                    outcome_key=cell.outcome_key,
                    window_id=cell.window_id,
                    source_digest=cell.source_digest,
                    channel_alignment=cell.channel_alignment,
                    value=cell.value,
                    availability=cell.availability,
                    config_digest=cell.config_digest,
                    provider_basis=cell.provider_basis,
                    planned_child_run_id=cell.planned_child_run_id,
                    child_run_id=cell.child_run_id,
                )
            )
    results = build_path_dependence_comparison(
        PathDependenceComparisonRequest(cells=tuple(per_contrast), contrasts=contrasts)
    )
    comparison = build_comparison_document(
        comparison_id=args.comparison_id,
        ensemble_id=str(ensemble["ensemble_id"]),
        spec_fingerprint=str(ensemble["spec_fingerprint"]),
        input_digests=tuple(
            sorted(
                str(document["digest"])
                for document in (
                    store.read_outcomes(
                        ensemble_id=str(ensemble["ensemble_id"]),
                        child_id=path.parent.parent.name,
                        attempt_id=path.parent.name,
                    )
                    for path in store.root.rglob("outcomes.json")
                )
            )
        ),
        contrasts=tuple(
            {
                "contrast_id": item.contrast_id,
                "outcome_key": item.outcome_key,
                "window_id": item.window_id,
                "fork_tick": item.fork_tick,
                "block_count": item.block_count,
                "paired_slot_count": item.paired_slot_count,
                "mean": item.mean,
                "ci_low": item.ci_low,
                "ci_high": item.ci_high,
                "status": item.status,
                "causal_claim": item.causal_claim,
                "multiplicity_policy": item.multiplicity_policy,
            }
            for item in results
        ),
        formula_versions={"comparison": "path-dependence-comparison-v1"},
    )
    store.write_comparison(
        ensemble_id=str(ensemble["ensemble_id"]),
        comparison_id=args.comparison_id,
        document=comparison,
    )
    for item in results:
        print(
            f"{item.contrast_id} {item.outcome_key} n={item.block_count} "
            f"mean={item.mean} status={item.status} causal_claim=false"
        )
        if item.block_count <= 1:
            print("illustrative/descriptive; no confidence interval")
    return 0


async def _resume(args: argparse.Namespace) -> int:
    store = _store(Path(args.ensemble))
    ensemble = _ensemble(store, args.ensemble_id)
    spec = _spec(ensemble)
    expected_base = {
        "ensemble_id": ensemble["ensemble_id"],
        "spec_fingerprint": ensemble["spec_fingerprint"],
    }

    class _NoRuns:
        async def exists(self, run_id: str) -> bool:
            return False

        async def terminal(self, run_id: str) -> dict[str, object] | None:
            return None

    counts = {decision.value: 0 for decision in ResumeDecision}
    composition = None
    reader: object = _NoRuns()
    if getattr(args, "database", False):
        from infrastructure.settings import Settings

        composition = build_path_dependence_postgres_composition(Settings())
        reader = composition.presence
    for slot in _slots(ensemble).values():
        expected = {
            **expected_base,
            "parent_id": "pd-parent-" + str(ensemble["spec_fingerprint"])[:24],
            "parent_attempt": "attempt-1",
            "child_id": slot["child_run_id"],
            "child_attempt": "attempt-1",
            "fork_tick": slot["fork_tick"],
        }
        classification = await classify_path_dependence_resume(
            expected=expected,
            store=store,
            repositories=reader,  # type: ignore[arg-type]
        )
        counts[classification.decision.value] += 1
        print(
            f"slot={slot['slot_ordinal']} child={slot['child_run_id']} "
            f"decision={classification.decision.value} "
            f"reason={classification.reason_code}"
        )
    del spec
    if composition is not None:
        await composition.close()
    _LOG.info(
        "path_dependence_resume_inventory ensemble_id=%s %s",
        ensemble["ensemble_id"],
        counts,
    )
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    return asyncio.run(_resume(args))


async def _materialize(
    checkpoint: RunnerForkCheckpoint, child_run: RunId
) -> WorldEngine:
    snapshot = rematerialize_snapshot(
        checkpoint.snapshot,
        child_run_id=child_run,
        snapshot_id=SnapshotId(f"child-{child_run.value}"),
        predecessor_commit_hash=None,
        next_tick=Tick(checkpoint.boundary_tick.value),
    )
    config = checkpoint.config
    return WorldEngine.restore_from_snapshot(
        snapshot,
        population_lifecycle=config.population_lifecycle,
        new_agent_initialization=config.new_agent_initialization,
        kinship_spec=config.kinship,
        environmental_dynamics=config.environmental_dynamics,
        artifacts_enabled=config.artifacts_enabled,
    )


async def _execute(
    *,
    spec_path: Path,
    root: Path,
    code_revision: str,
    source_artifact_digest: str,
    factories: RunnerDependencyFactories | None = None,
) -> tuple[dict[str, object], PathDependenceExecutionSummary]:
    store = _store(root)
    payload = await asyncio.to_thread(spec_path.read_bytes)
    spec = decode_path_dependence_spec(payload)
    ensemble = build_ensemble_document(
        spec,
        source_revision=code_revision,
        source_artifact_digest=source_artifact_digest,
    )
    store.write_ensemble(ensemble)
    fork_by_child = {
        str(slot["child_run_id"]): _int_value(slot["fork_tick"])
        for slot in cast(list[dict[str, object]], ensemble["slots"])
    }
    cultural_recorders: dict[str, CulturalEvidenceRecorder] = {}
    captured: dict[str, tuple[object, tuple[object, ...]]] = {}

    def _sink_factory(run_id: RunId) -> object | None:
        fork_tick = fork_by_child.get(run_id.value)
        if fork_tick is None:
            return None
        recorder = CulturalEvidenceRecorder()
        recorder.start_at_boundary(fork_tick)
        cultural_recorders[run_id.value] = recorder
        return recorder

    async def _observe_child(child: object, slot: object) -> None:
        try:
            boundary = await child.export_finalized_research_boundary()  # type: ignore[attr-defined]
        except Exception:
            _LOG.warning(
                "path_dependence_outcome_capture_failed child_id=%s "
                "reason_code=outcome_endpoint_missing",
                slot.child_run_id,  # type: ignore[attr-defined]
            )
            return
        recorder = cultural_recorders.get(slot.child_run_id)  # type: ignore[attr-defined]
        frames = () if recorder is None else recorder.result().frames
        captured[slot.child_run_id] = (boundary, frames)  # type: ignore[attr-defined]

    summary = await PathDependenceBatchRunner().run(
        spec,
        PathDependenceExecutionContext(
            factories=factories or RunnerDependencyFactories(),
            materialize_engine=_materialize,
            cultural_sink_factory=_sink_factory,
            child_observer=_observe_child,
            source_identity=code_revision,
        ),
    )
    ensemble_id = str(ensemble["ensemble_id"])
    provider = spec.base.provider
    for prefix in summary.prefixes:
        prefix_document = build_prefix_document(
            ensemble_id=ensemble_id,
            parent_scientific_id=prefix.parent_run_id,
            parent_attempt_id="attempt-1",
            fork_tick=prefix.fork_tick,
            boundary_revision=prefix.boundary_revision,
            config_fingerprint=prefix.config_fingerprint,
            source_revision=code_revision,
            provider_identity=provider.adapter_kind.value,
            complete_state_digest=prefix.complete_state_digest,
            checkpoint_format_version="runner-fork-checkpoint-v1",
            bootstrap_hash=prefix.bootstrap_hash,
            snapshot_hash=prefix.snapshot_hash,
            objective_head_hash=prefix.objective_head_hash,
            common_setup_digest="0" * 64,
            eligible=prefix.eligible,
            eligibility_reason=prefix.reason_code,
            eligibility_witness=prefix.eligibility_witness,
        )
        store.write_prefix(
            ensemble_id=ensemble_id,
            parent_id=prefix.parent_run_id,
            attempt_id="attempt-1",
            fork_tick=prefix.fork_tick,
            document=prefix_document,
        )
        for child in prefix.child_results:
            actions = spec.arms[
                next(
                    index
                    for index, arm in enumerate(spec.arms)
                    if arm.arm_id == child.arm_id
                )
            ].actions_for(Tick(prefix.fork_tick))
            schedule_digest = action_schedule_digest(actions)
            base = {
                "ensemble_id": ensemble_id,
                "parent_scientific_id": prefix.parent_run_id,
                "parent_attempt_id": "attempt-1",
                "fork_tick": prefix.fork_tick,
                "child_scientific_id": child.child_run_id,
                "child_attempt_id": "attempt-1",
                "slot_ordinal": child.slot_ordinal,
                "arm_id": child.arm_id,
                "action_schedule_digest": schedule_digest,
                "assignment_seed": spec.assignment_seed,
                "assignment_policy": "permuted-treatment-blind-slots-v1",
                "prefix_digest": str(prefix_document["digest"]),
            }
            store.write_branch(
                ensemble_id=ensemble_id,
                child_id=child.child_run_id,
                attempt_id="attempt-1",
                kind="preparation",
                document=build_branch_document(
                    kind="preparation",
                    **base,  # type: ignore[arg-type]
                    details={
                        "expected_checkpoint_digest": prefix.complete_state_digest
                    },
                ),
            )
            outcome_rows: list[dict[str, object]] = []
            observed = captured.get(child.child_run_id)
            if observed is not None:
                boundary, frames = observed
                for window in spec.windows:
                    window_selectors = tuple(
                        selector
                        for selector in spec.selectors
                        if selector.window_id == window.window_id
                    )
                    if not window_selectors:
                        continue
                    evidence_recorder = PathDependenceEvidenceRecorder()
                    evidence_recorder.capture(boundary)  # type: ignore[arg-type]
                    evidence = evidence_recorder.analysis_evidence(
                        window, cultural_frames=frames
                    )
                    for row in compute_path_dependence_outcomes(
                        evidence, window_selectors, (window,)
                    ):
                        outcome_rows.append(
                            {
                                "selector_id": row.selector_id,
                                "domain": row.domain.value,
                                "window_id": row.window_id,
                                "value": row.value,
                                "availability": row.availability.value,
                                "coverage": row.coverage,
                                "reason_code": row.reason_code,
                                "evidence_refs": list(row.evidence_refs),
                            }
                        )
            if not outcome_rows:
                outcome_rows = [
                    {
                        "selector_id": selector.selector_id,
                        "domain": selector.domain.value,
                        "window_id": selector.window_id,
                        "value": None,
                        "availability": "unknown",
                        "coverage": "missing",
                        "reason_code": "outcome_not_collected",
                    }
                    for selector in spec.selectors
                ]
            outcomes = build_outcomes_document(
                ensemble_id=ensemble_id,
                child_scientific_id=child.child_run_id,
                child_attempt_id="attempt-1",
                slot_ordinal=child.slot_ordinal,
                fork_tick=prefix.fork_tick,
                rows=outcome_rows,
                coverage={
                    "complete": all(
                        row["availability"] in {"present", "known_zero"}
                        for row in outcome_rows
                    ),
                    "reason_code": "outcome_capture_complete"
                    if all(
                        row["availability"] in {"present", "known_zero"}
                        for row in outcome_rows
                    )
                    else "outcome_capture_partial",
                },
                evidence_refs=(),
            )
            store.write_outcomes(
                ensemble_id=ensemble_id,
                child_id=child.child_run_id,
                attempt_id="attempt-1",
                document=outcomes,
            )
            if child.status == "completed":
                result = build_branch_document(
                    kind="result",
                    **base,  # type: ignore[arg-type]
                    details={
                        "child_run_id": child.child_run_id,
                        "requested_actions": len(actions),
                        "treatment_ledger": tuple(
                            {
                                "intervention_id": entry.intervention_id,
                                "tick": entry.tick,
                                "actor_id": entry.actor_id.value,
                                "action_kind": entry.action_kind,
                                "status": entry.status.value,
                                "resolution_status": entry.resolution_status,
                            }
                            for entry in child.treatment_ledger
                        ),
                        "stop_reason": child.stop_reason or "unknown",
                        "terminal_tick": child.ticks_committed,
                        "terminal_revision": child.terminal_revision or 0,
                        "pre_treatment_state_digest": prefix.complete_state_digest,
                        "channel_manifest": (provider.adapter_kind.value,),
                        "outcomes_digest": str(outcomes["digest"]),
                    },
                )
                store.write_branch(
                    ensemble_id=ensemble_id,
                    child_id=child.child_run_id,
                    attempt_id="attempt-1",
                    kind="result",
                    document=result,
                )
                completion = build_branch_document(
                    kind="completion",
                    **base,  # type: ignore[arg-type]
                    details={
                        "result_digest": str(result["digest"]),
                        "outcomes_digest": str(outcomes["digest"]),
                        "objective_head_hash": (child.objective_head_hash or "0" * 64),
                        "terminal_tick": child.ticks_committed,
                        "terminal_revision": child.terminal_revision or 0,
                    },
                )
                store.write_branch(
                    ensemble_id=ensemble_id,
                    child_id=child.child_run_id,
                    attempt_id="attempt-1",
                    kind="completion",
                    document=completion,
                )
            else:
                store.write_branch(
                    ensemble_id=ensemble_id,
                    child_id=child.child_run_id,
                    attempt_id="attempt-1",
                    kind="failure",
                    document=build_branch_document(
                        kind="failure",
                        **base,  # type: ignore[arg-type]
                        details={
                            "last_durable_tick": child.ticks_committed,
                            "stage": "child_execution",
                            "committed_status": child.status,
                            "reason_code": child.error_code or "child_failed",
                        },
                    ),
                )
    return ensemble, summary


async def _execute_with_database(
    *,
    spec_path: Path,
    root: Path,
    code_revision: str,
    source_artifact_digest: str,
) -> tuple[dict[str, object], PathDependenceExecutionSummary]:
    from infrastructure.settings import Settings

    composition = build_path_dependence_postgres_composition(Settings())
    try:
        return await _execute(
            spec_path=spec_path,
            root=root,
            code_revision=code_revision,
            source_artifact_digest=source_artifact_digest,
            factories=composition.factories,
        )
    finally:
        await composition.close()


def cmd_run(args: argparse.Namespace) -> int:
    """Execute an ensemble and seal its lineage artifacts."""
    root = Path(args.artifact_root)
    coroutine = (
        _execute_with_database(
            spec_path=Path(args.spec),
            root=root,
            code_revision=args.code_revision,
            source_artifact_digest=args.source_artifact_digest,
        )
        if getattr(args, "database", False)
        else _execute(
            spec_path=Path(args.spec),
            root=root,
            code_revision=args.code_revision,
            source_artifact_digest=args.source_artifact_digest,
        )
    )
    ensemble, summary = asyncio.run(coroutine)
    slots = ensemble["slots"]
    if not isinstance(slots, list):
        raise PathDependenceCliError("artifact_identity_mismatch")
    print(f"ensemble_id={ensemble['ensemble_id']}")
    print(f"slots={len(slots)}")
    print(f"prefixes={len(summary.prefixes)}")
    print(f"completed={summary.completed_count} failed={summary.failed_count}")
    return 0


def add_path_dependence_parser(
    sub: argparse._SubParsersAction,  # type: ignore[type-arg]
) -> None:
    parser = sub.add_parser(
        "path-dependence",
        help="Historical-contingency artifact protocol (no HTTP)",
    )
    nested = parser.add_subparsers(dest="path_dependence_command", required=True)

    run_p = nested.add_parser("run", help="Seal a spec and prepare execution")
    run_p.add_argument("--spec", required=True)
    run_p.add_argument("--artifact-root", required=True)
    run_p.add_argument("--code-revision", required=True)
    run_p.add_argument("--source-artifact-digest", required=True)
    run_p.add_argument(
        "--database",
        action="store_true",
        help="Persist objective runs and journals in the configured database",
    )
    run_p.set_defaults(func=cmd_run)

    resume_p = nested.add_parser("resume", help="Classify every planned slot")
    resume_p.add_argument("--ensemble", required=True)
    resume_p.add_argument("--ensemble-id", required=True)
    resume_p.add_argument(
        "--database",
        action="store_true",
        help="Check objective presence in the configured PALIMPSEST database",
    )
    resume_p.set_defaults(func=cmd_resume)

    inspect_p = nested.add_parser("inspect", help="Read-only lineage inventory")
    inspect_p.add_argument("--ensemble", required=True)
    inspect_p.add_argument("--ensemble-id", required=True)
    inspect_p.set_defaults(func=cmd_inspect)

    compare_p = nested.add_parser("compare", help="Write paired comparisons")
    compare_p.add_argument("--ensemble", required=True)
    compare_p.add_argument("--ensemble-id", required=True)
    compare_p.add_argument("--comparison-id", default="comparison-1")
    compare_p.set_defaults(func=cmd_compare)


def dispatch(args: argparse.Namespace) -> int:
    return int(args.func(args))


__all__ = [
    "PathDependenceCliError",
    "add_path_dependence_parser",
    "cmd_compare",
    "cmd_inspect",
    "cmd_resume",
    "cmd_run",
    "dispatch",
]
