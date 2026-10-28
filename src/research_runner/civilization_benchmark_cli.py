"""CLI helpers for the V3 generational civilization benchmark (no HTTP)."""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

from experiments.civilization_benchmark_artifacts import (
    BenchmarkArtifactError,
    BenchmarkArtifactStore,
)
from experiments.civilization_benchmark_base import V3_BENCHMARK_PROFILE_BUDGETS
from experiments.civilization_benchmark_models import (
    V3BenchmarkLane,
    V3BenchmarkProfile,
)
from experiments.civilization_benchmark_suite import (
    V3_BENCHMARK_SCENARIO_IDS,
    list_v3_benchmark_scenarios,
)
from experiments.generational_artifacts import (
    GenerationalArtifactError,
    source_identity_preflight,
)
from research_runner import civilization_benchmark_composition as composition

_LOG: Final[logging.Logger] = logging.getLogger(
    "research_runner.civilization_benchmark_cli"
)

VISUAL_RECIPE_ID: Final[str] = "v3-visual-integration-v1"
_SHA256: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")


class BenchmarkCliError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def add_civilization_benchmark_parser(
    sub: argparse._SubParsersAction,  # type: ignore[type-arg]
) -> None:
    parser = sub.add_parser(
        "civilization-benchmark",
        help="List, run or verify V3 generational benchmark artifacts",
    )
    bench = parser.add_subparsers(dest="benchmark_command", required=True)

    list_p = bench.add_parser("list", help="List the 30 registered scenarios")
    list_p.set_defaults(benchmark_func=_cmd_list, func=execute_cli)

    run_p = bench.add_parser("run", help="Execute selected scenarios")
    run_p.add_argument("--scenario", action="append", default=None)
    run_p.add_argument(
        "--profile",
        choices=("smoke", "research", "visual"),
        default="smoke",
    )
    run_p.add_argument(
        "--lane", choices=("mechanism", "research"), default="research"
    )
    run_p.add_argument("--output", required=True)
    run_p.add_argument("--timeout-seconds", type=int, required=True)
    run_p.add_argument("--code-revision", required=True)
    run_p.add_argument("--source-clean", action="store_true")
    run_p.add_argument("--source-artifact-digest", default=None)
    run_p.set_defaults(benchmark_func=_cmd_run, func=execute_cli)

    verify_p = bench.add_parser("verify", help="Verify a published suite")
    verify_p.add_argument("--output", required=True)
    verify_p.add_argument("--code-revision", required=True)
    verify_p.add_argument("--source-clean", action="store_true")
    verify_p.add_argument("--source-artifact-digest", default=None)
    verify_p.add_argument("--require-complete", action="store_true")
    verify_p.set_defaults(benchmark_func=_cmd_verify, func=execute_cli)


def _source_identity(args: argparse.Namespace) -> dict[str, object]:
    digest = args.source_artifact_digest
    clean = bool(args.source_clean)
    if clean and digest is not None:
        raise BenchmarkCliError("source_assertion_ambiguous")
    if not args.code_revision:
        raise BenchmarkCliError("missing_source_revision")
    if not clean and digest is None:
        raise BenchmarkCliError("clean_source_assertion_required")
    if digest is not None and not _SHA256.match(digest):
        raise BenchmarkCliError("invalid_source_artifact_digest")
    try:
        return source_identity_preflight(
            code_revision=args.code_revision,
            source_clean=clean,
            source_artifact_digest=digest,
        )
    except GenerationalArtifactError as exc:
        raise BenchmarkCliError(exc.code) from exc


def _cmd_list(args: argparse.Namespace) -> int:
    for spec in list_v3_benchmark_scenarios():
        print(
            f"{spec.scenario_id}\t{spec.title}\t"
            f"{spec.execution_kind.value}\t{spec.recipe.profile.value}"
        )
    return 0


def _select_items(
    args: argparse.Namespace,
) -> list[composition.BenchmarkSelectionItem]:
    profile = V3BenchmarkProfile(args.profile)
    lane = V3BenchmarkLane(args.lane)
    if args.timeout_seconds <= 0:
        raise BenchmarkCliError("invalid_timeout")
    if profile is V3BenchmarkProfile.VISUAL:
        if args.scenario:
            raise BenchmarkCliError("visual_selection_invalid")
        if lane is V3BenchmarkLane.RESEARCH:
            raise BenchmarkCliError("visual_selection_invalid")
        from experiments.civilization_benchmark_visual import (
            VISUAL_BENCHMARK_RECIPE_ID,
        )

        if args.timeout_seconds <= 0:
            raise BenchmarkCliError("invalid_timeout")
        return [
            composition.BenchmarkSelectionItem(
                scenario_id=VISUAL_BENCHMARK_RECIPE_ID,
                lane=lane,
                profile=profile,
                seed=V3_BENCHMARK_PROFILE_BUDGETS[profile].seeds[0],
                arm_id="observation",
            )
        ]
    seeds = V3_BENCHMARK_PROFILE_BUDGETS[profile].seeds
    selected = args.scenario or list(V3_BENCHMARK_SCENARIO_IDS)
    for scenario_id in selected:
        spec = next(
            (
                item
                for item in list_v3_benchmark_scenarios()
                if item.scenario_id == scenario_id
            ),
            None,
        )
        if spec is None:
            raise BenchmarkCliError("unknown_scenario")
        if spec.recipe.arm_count > 1:
            raise BenchmarkCliError("grouped_case_not_supported")
        if lane not in spec.lanes:
            raise BenchmarkCliError("unsupported_lane")
    return [
        composition.BenchmarkSelectionItem(
            scenario_id=scenario_id,
            lane=lane,
            profile=profile,
            seed=seeds[0],
            arm_id="observation",
        )
        for scenario_id in selected
    ]


def _cmd_run(args: argparse.Namespace) -> int:
    source_identity = _source_identity(args)
    items = _select_items(args)
    if not items:
        raise BenchmarkCliError("empty_selection")
    documents = asyncio.run(
        _execute_selection(
            items,
            output_root=Path(args.output),
            source_identity=source_identity,
            timeout_seconds=args.timeout_seconds,
        )
    )
    from experiments.civilization_benchmark_artifacts import run_passes

    failed = [doc["scenario_id"] for doc in documents if not run_passes(doc)]
    if failed:
        _LOG.error(
            "benchmark_run_required_gate_failed scenario_count=%s",
            len(failed),
        )
        return 1
    return 0


async def _execute_selection(
    items: list[composition.BenchmarkSelectionItem],
    *,
    output_root: Path,
    source_identity: dict[str, object],
    timeout_seconds: int,
) -> Sequence[Mapping[str, object]]:
    """Indirection point for tests; production executes the real composition."""
    return await composition.execute_selection(
        items,
        output_root=output_root,
        source_identity=source_identity,
        timeout_seconds=timeout_seconds,
    )


def _cmd_verify(args: argparse.Namespace) -> int:
    source_identity = _source_identity(args)
    try:
        suite = BenchmarkArtifactStore(
            Path(args.output), profile=V3BenchmarkProfile.SMOKE
        ).verify(
            source_identity=source_identity,
            require_complete=bool(args.require_complete),
        )
    except BenchmarkArtifactError as exc:
        if exc.code in {"incomplete_suite", "reference_hash_mismatch"}:
            _LOG.error("benchmark_verify_failed reason_code=%s", exc.code)
            return 1
        raise BenchmarkCliError(exc.code) from exc
    print(f"benchmark_suite_status={suite.get('status')}")
    return 0


def execute_cli(args: argparse.Namespace) -> int:
    """Entry point invoked from the shared matrix CLI dispatcher."""
    try:
        return int(args.benchmark_func(args))
    except BenchmarkCliError as exc:
        _LOG.error("benchmark_cli_preflight_failed reason_code=%s", exc.code)
        print(f"invalid_preflight={exc.code}", file=sys.stderr)
        return 2
    except composition.BenchmarkCompositionError as exc:
        _LOG.error("benchmark_composition_failed reason_code=%s", exc.code)
        print(f"failed_gate={exc.code}", file=sys.stderr)
        return 1


__all__ = [
    "VISUAL_RECIPE_ID",
    "BenchmarkCliError",
    "add_civilization_benchmark_parser",
    "execute_cli",
]
