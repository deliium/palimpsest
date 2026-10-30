"""Unit tests for the civilization benchmark CLI surface."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol

import pytest

from experiments.civilization_benchmark_artifacts import (
    BenchmarkArtifactStore,
    build_run_document,
)
from experiments.civilization_benchmark_models import (
    V3BenchmarkCheck,
    V3BenchmarkCheckStatus,
    V3BenchmarkCoverage,
    V3BenchmarkEvidenceAvailability,
    V3BenchmarkExecutionStatus,
    V3BenchmarkLane,
    V3BenchmarkPhenomenon,
    V3BenchmarkProfile,
    V3BenchmarkRunResult,
    V3BenchmarkSourceKind,
    V3BenchmarkSourceReference,
)
from experiments.civilization_benchmark_suite import (
    V3_BENCH_01_BLANK_SLATE,
    V3_BENCH_29_FOUNDER_CONTINGENCY,
)
from research_runner import civilization_benchmark_cli as cli
from research_runner.civilization_benchmark_composition import BenchmarkSelectionItem
from research_runner.cli import main

_SOURCE_ARGS = ("--code-revision", "deadbeef", "--source-clean")


class _ExecuteSelection(Protocol):
    async def __call__(
        self,
        items: list[BenchmarkSelectionItem],
        *,
        output_root: Path,
        source_identity: Mapping[str, object],
        timeout_seconds: int,
    ) -> Sequence[Mapping[str, object]]: ...


def _result(
    scenario_id: str,
    *,
    passing: bool = True,
    lane: V3BenchmarkLane = V3BenchmarkLane.RESEARCH,
) -> V3BenchmarkRunResult:
    check = V3BenchmarkCheck(
        selector_id="new_agent_initialization_evidence",
        selector_version=1,
        status=(
            V3BenchmarkCheckStatus.PASS
            if passing
            else V3BenchmarkCheckStatus.UNEXECUTED
        ),
        reason_code="blank_slate_measured" if passing else "probe_unavailable",
        evidence=(
            V3BenchmarkEvidenceAvailability.COMPLETE
            if passing
            else V3BenchmarkEvidenceAvailability.PARTIAL
        ),
        coverage=V3BenchmarkCoverage.EXERCISED,
        source_references=(
            V3BenchmarkSourceReference(
                source_kind=V3BenchmarkSourceKind.SUBJECTIVE_DEBUG,
                reference_id="agent-1",
                owner_id="agent-1",
            ),
        )
        if passing
        else (),
        boundary_start_tick=0,
        boundary_end_tick=4,
        numerator=1,
        denominator=1,
    )
    return V3BenchmarkRunResult(
        scenario_id=scenario_id,
        lane=lane,
        execution_status=V3BenchmarkExecutionStatus.COMPLETED,
        declared_horizon=4,
        ticks_committed=4,
        coverage=V3BenchmarkCoverage.EXERCISED,
        evidence=(
            V3BenchmarkEvidenceAvailability.COMPLETE
            if passing
            else V3BenchmarkEvidenceAvailability.PARTIAL
        ),
        phenomenon=(
            V3BenchmarkPhenomenon.NOT_DETECTED
            if passing
            else V3BenchmarkPhenomenon.UNKNOWN
        ),
        checks=(check,),
    )


def _fake_execute(passing: bool = True) -> _ExecuteSelection:
    async def execute(
        items: list[BenchmarkSelectionItem],
        *,
        output_root: Path,
        source_identity: Mapping[str, object],
        timeout_seconds: int,
    ) -> Sequence[Mapping[str, object]]:
        store = BenchmarkArtifactStore(output_root, profile=items[0].profile)
        references = []
        documents = []
        for item in items:
            document = build_run_document(
                scenario_id=item.scenario_id,
                lane=item.lane,
                profile=item.profile,
                arm_id=item.arm_id,
                seed=item.seed,
                source_identity=source_identity,
                config_fingerprint="a" * 64,
                recipe={"recipe_id": "v3-benchmark", "version": "1"},
                run_id=f"run-{item.scenario_id}",
                result=_result(
                    item.scenario_id, passing=passing, lane=item.lane
                ),
            )
            documents.append(document)
            references.append(store.publish_run(document))
        store.publish_suite(
            source_identity=source_identity,
            run_references=tuple(references),
            required=tuple(
                (item.scenario_id, item.lane.value) for item in items
            ),
        )
        return tuple(documents)

    return execute


def test_list_prints_all_thirty_ids_without_database(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["civilization-benchmark", "list"]) == 0
    output = capsys.readouterr().out
    lines = [line for line in output.splitlines() if line.strip()]
    assert len(lines) == 30
    assert lines[0].startswith("v3-bench-01-blank-slate")
    assert lines[-1].startswith("v3-bench-30-multigeneration-fork")


def test_run_and_verify_round_trip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "_execute_selection", _fake_execute(passing=True))
    output = tmp_path / "artifacts"
    code = main(
        [
            "civilization-benchmark",
            "run",
            "--scenario",
            V3_BENCH_01_BLANK_SLATE,
            "--profile",
            "smoke",
            "--lane",
            "research",
            "--output",
            str(output),
            "--timeout-seconds",
            "5",
            *_SOURCE_ARGS,
        ]
    )
    assert code == 0
    verify_args = [
        "civilization-benchmark",
        "verify",
        "--output",
        str(output),
        "--require-complete",
        *_SOURCE_ARGS,
    ]
    assert main(verify_args) == 0
    assert "benchmark_suite_status=complete" in capsys.readouterr().out


def test_failed_required_gate_exits_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "_execute_selection", _fake_execute(passing=False))
    code = main(
        [
            "civilization-benchmark",
            "run",
            "--scenario",
            V3_BENCH_01_BLANK_SLATE,
            "--profile",
            "smoke",
            "--lane",
            "research",
            "--output",
            str(tmp_path / "failed"),
            "--timeout-seconds",
            "5",
            *_SOURCE_ARGS,
        ]
    )
    assert code == 1


def test_invalid_source_assertions_exit_two(tmp_path: Path) -> None:
    base = [
        "civilization-benchmark",
        "run",
        "--scenario",
        V3_BENCH_01_BLANK_SLATE,
        "--output",
        str(tmp_path),
        "--timeout-seconds",
        "5",
        "--code-revision",
        "deadbeef",
    ]
    assert main(base) == 2
    assert main([*base, "--source-clean", "--source-artifact-digest", "a" * 64]) == 2
    assert main([*base, "--source-artifact-digest", "not-a-digest"]) == 2
    assert main(
        [
            "civilization-benchmark",
            "run",
            "--scenario",
            V3_BENCH_01_BLANK_SLATE,
            "--output",
            str(tmp_path),
            "--timeout-seconds",
            "0",
            *_SOURCE_ARGS,
        ]
    ) == 2


def test_visual_selection_fails_closed(tmp_path: Path) -> None:
    visual = [
        "civilization-benchmark",
        "run",
        "--profile",
        "visual",
        "--lane",
        "mechanism",
        "--output",
        str(tmp_path),
        "--timeout-seconds",
        "5",
        *_SOURCE_ARGS,
    ]
    assert main([*visual, "--scenario", V3_BENCH_01_BLANK_SLATE]) == 2
    assert main([*visual, "--seed", "23"]) == 2
    assert main(
        [
            "civilization-benchmark",
            "run",
            "--profile",
            "visual",
            "--lane",
            "research",
            "--output",
            str(tmp_path),
            "--timeout-seconds",
            "5",
            *_SOURCE_ARGS,
        ]
    ) == 2


def test_grouped_case_selection_uses_the_grouped_arm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[list[BenchmarkSelectionItem]] = []
    base = _fake_execute(passing=True)

    async def capture(
        items: list[BenchmarkSelectionItem],
        *,
        output_root: Path,
        source_identity: Mapping[str, object],
        timeout_seconds: int,
    ) -> Sequence[Mapping[str, object]]:
        seen.append(list(items))
        return await base(
            items,
            output_root=output_root,
            source_identity=source_identity,
            timeout_seconds=timeout_seconds,
        )

    monkeypatch.setattr(cli, "_execute_selection", capture)
    assert main(
        [
            "civilization-benchmark",
            "run",
            "--scenario",
            V3_BENCH_29_FOUNDER_CONTINGENCY,
            "--profile",
            "smoke",
            "--lane",
            "research",
            "--output",
            str(tmp_path / "grouped"),
            "--timeout-seconds",
            "5",
            *_SOURCE_ARGS,
        ]
    ) == 0
    item = seen[0][0]
    assert item.scenario_id == V3_BENCH_29_FOUNDER_CONTINGENCY
    assert item.arm_id == "grouped"


def test_research_profile_selects_every_predeclared_seed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from experiments.civilization_benchmark_suite import RESEARCH_SEEDS

    seen: list[list[BenchmarkSelectionItem]] = []
    base = _fake_execute(passing=True)

    async def capture(
        items: list[BenchmarkSelectionItem],
        *,
        output_root: Path,
        source_identity: Mapping[str, object],
        timeout_seconds: int,
    ) -> Sequence[Mapping[str, object]]:
        seen.append(list(items))
        return await base(
            items,
            output_root=output_root,
            source_identity=source_identity,
            timeout_seconds=timeout_seconds,
        )

    monkeypatch.setattr(cli, "_execute_selection", capture)
    assert main(
        [
            "civilization-benchmark",
            "run",
            "--scenario",
            V3_BENCH_01_BLANK_SLATE,
            "--profile",
            "research",
            "--lane",
            "research",
            "--output",
            str(tmp_path / "research"),
            "--timeout-seconds",
            "5",
            *_SOURCE_ARGS,
        ]
    ) == 0
    assert tuple(item.seed for item in seen[0]) == RESEARCH_SEEDS


def test_undeclared_or_duplicate_seeds_fail_closed(tmp_path: Path) -> None:
    base = [
        "civilization-benchmark",
        "run",
        "--scenario",
        V3_BENCH_01_BLANK_SLATE,
        "--profile",
        "smoke",
        "--lane",
        "research",
        "--output",
        str(tmp_path),
        "--timeout-seconds",
        "5",
        *_SOURCE_ARGS,
    ]
    assert main([*base, "--seed", "11"]) == 2
    assert main([*base, "--seed", "23", "--seed", "23"]) == 2


def test_visual_selection_uses_the_integration_recipe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from experiments.civilization_benchmark_visual import (
        VISUAL_BENCHMARK_RECIPE_ID,
    )

    seen: list[list[BenchmarkSelectionItem]] = []

    base = _fake_execute(passing=True)

    async def capture(
        items: list[BenchmarkSelectionItem],
        *,
        output_root: Path,
        source_identity: Mapping[str, object],
        timeout_seconds: int,
    ) -> Sequence[Mapping[str, object]]:
        seen.append(list(items))
        return await base(
            items,
            output_root=output_root,
            source_identity=source_identity,
            timeout_seconds=timeout_seconds,
        )

    monkeypatch.setattr(cli, "_execute_selection", capture)
    assert main(
        [
            "civilization-benchmark",
            "run",
            "--profile",
            "visual",
            "--lane",
            "mechanism",
            "--output",
            str(tmp_path / "visual"),
            "--timeout-seconds",
            "5",
            *_SOURCE_ARGS,
        ]
    ) == 0
    assert seen
    item = seen[0][0]
    assert item.scenario_id == VISUAL_BENCHMARK_RECIPE_ID
    assert item.profile is V3BenchmarkProfile.VISUAL
    assert item.lane is V3BenchmarkLane.MECHANISM


def test_tampered_reference_and_source_mismatch_fail_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "_execute_selection", _fake_execute(passing=True))
    output = tmp_path / "artifacts"
    assert (
        main(
            [
                "civilization-benchmark",
                "run",
                "--scenario",
                V3_BENCH_01_BLANK_SLATE,
                "--output",
                str(output),
                "--timeout-seconds",
                "5",
                *_SOURCE_ARGS,
            ]
        )
        == 0
    )
    verify_args = [
        "civilization-benchmark",
        "verify",
        "--output",
        str(output),
        "--require-complete",
        *_SOURCE_ARGS,
    ]
    assert main(
        [
            "civilization-benchmark",
            "verify",
            "--output",
            str(output),
            "--require-complete",
            "--code-revision",
            "different",
            "--source-clean",
        ]
    ) == 2
    run_files = sorted((output / "runs").glob("*.json"))
    assert run_files
    payload = bytearray(run_files[0].read_bytes())
    payload[-2] = payload[-2] ^ 0x01
    run_files[0].write_bytes(bytes(payload))
    assert main(verify_args) in {1, 2}
