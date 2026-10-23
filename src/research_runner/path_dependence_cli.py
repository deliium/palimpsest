"""CLI helpers for historical-contingency research artifacts (no HTTP)."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Final

from analysis.path_dependence_comparison import (
    ComparisonContrast,
    PathDependenceComparisonRequest,
    PathDependenceOutcomeCell,
    build_path_dependence_comparison,
)
from experiments.path_dependence_artifacts import (
    PathDependenceArtifactStore,
    build_comparison_document,
    build_ensemble_document,
)
from experiments.path_dependence_models import PathDependenceSpec
from experiments.path_dependence_resume import (
    ResumeDecision,
    classify_path_dependence_resume,
)
from experiments.path_dependence_serialization import decode_path_dependence_spec

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


def cmd_resume(args: argparse.Namespace) -> int:
    store = _store(Path(args.ensemble))
    ensemble = _ensemble(store, args.ensemble_id)
    spec = _spec(ensemble)
    expected_base = {
        "ensemble_id": ensemble["ensemble_id"],
        "spec_fingerprint": ensemble["spec_fingerprint"],
    }

    class _NoRuns:
        def exists(self, run_id: str) -> bool:
            return False

        def terminal(self, run_id: str) -> dict[str, object] | None:
            return None

    counts = {decision.value: 0 for decision in ResumeDecision}
    for slot in _slots(ensemble).values():
        expected = {
            **expected_base,
            "parent_id": "pd-parent-" + str(ensemble["spec_fingerprint"])[:24],
            "parent_attempt": "attempt-1",
            "child_id": slot["child_run_id"],
            "child_attempt": "attempt-1",
            "fork_tick": slot["fork_tick"],
        }
        classification = classify_path_dependence_resume(
            expected=expected, store=store, repositories=_NoRuns()
        )
        counts[classification.decision.value] += 1
        print(
            f"slot={slot['slot_ordinal']} child={slot['child_run_id']} "
            f"decision={classification.decision.value} "
            f"reason={classification.reason_code}"
        )
    del spec
    _LOG.info(
        "path_dependence_resume_inventory ensemble_id=%s %s",
        ensemble["ensemble_id"],
        counts,
    )
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Preflight a spec and seal its immutable ensemble document."""
    root = Path(args.artifact_root)
    store = _store(root)
    spec = decode_path_dependence_spec(Path(args.spec).read_bytes())
    document = build_ensemble_document(
        spec,
        source_revision=args.code_revision,
        source_artifact_digest=args.source_artifact_digest,
    )
    store.write_ensemble(document)
    print(f"ensemble_id={document['ensemble_id']}")
    slots = document["slots"]
    if not isinstance(slots, list):
        raise PathDependenceCliError("artifact_identity_mismatch")
    print(f"slots={len(slots)}")
    print("execution=not_started")
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
    run_p.set_defaults(func=cmd_run)

    resume_p = nested.add_parser("resume", help="Classify every planned slot")
    resume_p.add_argument("--ensemble", required=True)
    resume_p.add_argument("--ensemble-id", required=True)
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
