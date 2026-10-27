"""Exact paired-execution and historical-query oracles for V3 scaling.

The helpers here are intentionally reusable: later scalable paths must compare
against the reference fold rather than inventing a second semantic model.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

import pytest

from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import RunnerPersistenceSpec, SimulationRunnerConfig
from simulation.runner_serialization import (
    build_runner_result_document,
    objective_projection_hash,
)
from tests.benchmarks.v3_workloads import SMOKE_TICKS, V3ScaleLane, build_workload

_FAMILIES = (
    "genealogy",
    "mentorship",
    "technology",
    "knowledge",
    "record",
    "narrative",
    "institution",
    "office_succession",
)


@dataclass(frozen=True, slots=True)
class PairedExecution:
    """Reference outcome for one non-durable paired execution."""

    document: object
    ticks: int
    cohorts: tuple[tuple[int, int, str, int, int, int], ...]
    final_projection_hash: str


@dataclass(frozen=True, slots=True)
class QueryOracleRecord:
    """Minimum qualified identity for one historical query row."""

    family: str
    qualified_id: str
    root_id: str
    native_identity: str
    publication: str
    as_of_tick: int
    evidence_high_water: int
    coverage_numerator: int
    coverage_denominator: int | None
    cursor_scope: str
    available: bool = True


def assert_paired_identity(
    first_config: SimulationRunnerConfig,
    second_config: SimulationRunnerConfig,
    first_run_id: RunId,
    second_run_id: RunId,
) -> None:
    if first_run_id != second_run_id:
        raise AssertionError("scientific_identity_mismatch:run_id")
    if first_config != second_config:
        raise AssertionError("scientific_identity_mismatch:configuration")


async def run_paired_execution(
    config: SimulationRunnerConfig,
    *,
    run_id: RunId,
    observations: bool = True,
) -> tuple[PairedExecution, PairedExecution]:
    """Run the same scientific configuration twice with identical domain IDs."""
    del observations
    assert not config.persistence.durable
    outcomes: list[PairedExecution] = []
    for _ in range(2):
        runner = await SimulationRunner.from_config(config, run_id=run_id)
        try:
            result = await runner.run()
            document = build_runner_result_document(result=result, config=config)
            projection = runner.final_objective_projection()
            progress = result.generational_progress
            cohorts = (
                ()
                if progress is None
                else tuple(
                    (
                        row.generation_index,
                        row.entry_tick,
                        row.cohort_id,
                        row.admitted,
                        row.living,
                        row.dead,
                    )
                    for row in progress.cohorts
                )
            )
            outcomes.append(
                PairedExecution(
                    document=document,
                    ticks=result.ticks_committed,
                    cohorts=cohorts,
                    final_projection_hash=objective_projection_hash(projection),
                )
            )
        finally:
            await runner.aclose()
    return outcomes[0], outcomes[1]


def assert_paired_equivalence(first: PairedExecution, second: PairedExecution) -> None:
    assert first.ticks == second.ticks
    assert first.document == second.document
    assert first.document.exact_trajectory_hash == (  # type: ignore[attr-defined]
        second.document.exact_trajectory_hash  # type: ignore[attr-defined]
    )
    assert first.document.replica_normalized_trajectory_hash == (  # type: ignore[attr-defined]
        second.document.replica_normalized_trajectory_hash  # type: ignore[attr-defined]
    )
    assert first.cohorts == second.cohorts
    assert first.final_projection_hash == second.final_projection_hash


def historical_seek_targets(
    *,
    admissions: Sequence[int],
    deaths: Sequence[int],
    checkpoint_boundaries: Sequence[int],
    final_tick: int,
) -> tuple[int, ...]:
    """Return beginning, pre/post admission/death, checkpoint and final seeks."""
    if final_tick < 1:
        raise ValueError("final_tick must be >= 1")
    targets = {0, final_tick, max(0, final_tick // 2)}
    for value in (*admissions, *deaths, *checkpoint_boundaries):
        if type(value) is not int or value < 0:
            raise ValueError("historical boundaries must be non-negative integers")
        targets.add(max(0, value - 1))
        targets.add(min(final_tick, value))
        targets.add(min(final_tick, value + 1))
    return tuple(sorted(targets))


def assert_query_oracle(
    records: Sequence[QueryOracleRecord],
    *,
    expected_families: Sequence[str] = _FAMILIES,
) -> None:
    """Validate qualified identity, coverage and cursor scope per family."""
    if {record.family for record in records} != set(expected_families):
        raise AssertionError("lineage_family_coverage_mismatch")
    seen: set[tuple[str, str]] = set()
    for record in records:
        key = (record.family, record.qualified_id)
        if key in seen:
            raise AssertionError("lineage_duplicate_qualified_id")
        seen.add(key)
        if not record.root_id or not record.native_identity:
            raise AssertionError("lineage_missing_root_or_identity")
        if not record.publication or record.as_of_tick < 0:
            raise AssertionError("lineage_missing_publication_or_time")
        if record.evidence_high_water < record.as_of_tick:
            raise AssertionError("lineage_high_water_before_as_of")
        if record.coverage_denominator is None:
            if record.coverage_numerator != 0:
                raise AssertionError("lineage_missing_denominator_not_zero")
        elif record.coverage_numerator > record.coverage_denominator:
            raise AssertionError("lineage_coverage_out_of_range")
        if record.cursor_scope != record.family:
            raise AssertionError("lineage_cursor_scope_mismatch")
        if not record.available and record.coverage_numerator:
            raise AssertionError("unavailable_record_claims_coverage")


def _oracle_records() -> tuple[QueryOracleRecord, ...]:
    return tuple(
        QueryOracleRecord(
            family=family,
            qualified_id=f"{family}:run:one",
            root_id=f"root:{family}",
            native_identity=f"native:{family}",
            publication=f"{family}-publication-v1",
            as_of_tick=12,
            evidence_high_water=12,
            coverage_numerator=2,
            coverage_denominator=2,
            cursor_scope=family,
        )
        for family in _FAMILIES
    )


@pytest.mark.asyncio
async def test_paired_generational_execution_is_exactly_equivalent() -> None:
    workload = build_workload(V3ScaleLane.GENERATIONAL, ticks=SMOKE_TICKS)
    config = replace(workload.config, persistence=RunnerPersistenceSpec(durable=False))
    first, second = await run_paired_execution(config, run_id=workload.run_id)
    assert_paired_equivalence(first, second)
    assert first.ticks == SMOKE_TICKS
    assert first.cohorts


def test_paired_identity_mismatch_is_rejected_before_comparison() -> None:
    workload = build_workload(V3ScaleLane.GENERATIONAL, ticks=SMOKE_TICKS)
    with pytest.raises(AssertionError, match="run_id"):
        assert_paired_identity(
            workload.config,
            workload.config,
            workload.run_id,
            RunId("different-run"),
        )
    other = replace(workload.config, seed=workload.config.seed + 1)
    with pytest.raises(AssertionError, match="configuration"):
        assert_paired_identity(workload.config, other, workload.run_id, workload.run_id)


def test_historical_seek_targets_cover_every_boundary() -> None:
    targets = historical_seek_targets(
        admissions=(10, 40),
        deaths=(25, 55),
        checkpoint_boundaries=(20, 50),
        final_tick=64,
    )
    assert targets[0] == 0
    assert targets[-1] == 64
    for boundary in (9, 10, 11, 24, 25, 26, 39, 40, 41, 54, 55, 56):
        assert boundary in targets
    assert 20 in targets and 50 in targets
    assert 32 in targets


def test_historical_seek_targets_reject_invalid_input() -> None:
    with pytest.raises(ValueError):
        historical_seek_targets(
            admissions=(), deaths=(), checkpoint_boundaries=(), final_tick=0
        )
    with pytest.raises(ValueError):
        historical_seek_targets(
            admissions=(-1,), deaths=(), checkpoint_boundaries=(), final_tick=4
        )


def test_query_oracle_covers_all_eight_families() -> None:
    assert_query_oracle(_oracle_records())


def test_query_oracle_rejects_scope_high_water_and_coverage_tampering() -> None:
    record = _oracle_records()[0]
    with pytest.raises(AssertionError, match="cursor_scope"):
        assert_query_oracle(
            (replace(record, cursor_scope="knowledge"), *_oracle_records()[1:])
        )
    with pytest.raises(AssertionError, match="high_water"):
        assert_query_oracle(
            (replace(record, evidence_high_water=1), *_oracle_records()[1:])
        )
    with pytest.raises(AssertionError, match="denominator"):
        assert_query_oracle(
            (
                replace(
                    record,
                    coverage_numerator=1,
                    coverage_denominator=None,
                ),
                *_oracle_records()[1:],
            )
        )
    with pytest.raises(AssertionError, match="missing_root"):
        assert_query_oracle((replace(record, root_id=""), *_oracle_records()[1:]))


__all__: tuple[str, ...] = ()
