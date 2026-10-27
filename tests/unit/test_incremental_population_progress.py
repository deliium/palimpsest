"""Incremental population totals and bounded history traversal."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from simulation._history import HistorySequence
from simulation.generational_progress import (
    PopulationProgressAccumulator,
    build_population_progress,
)
from simulation.runner import SimulationRunner
from tests.unit.test_runner_active_owners import _active_config


@given(st.lists(st.integers(min_value=0, max_value=8), max_size=24))
def test_history_tick_count_matches_linear_scan(ticks: list[int]) -> None:
    sequence: HistorySequence[SimpleNamespace] = HistorySequence()
    chunks: list[SimpleNamespace] = []
    for tick in ticks:
        item = SimpleNamespace(tick=tick)
        chunks.append(item)
        sequence = sequence.append((item,))
    for tick in range(9):
        assert sequence.count_with_tick(tick) == sum(
            1 for item in chunks if item.tick == tick
        )
        expected = [item for item in chunks if item.tick >= tick]
        assert list(sequence.iter_from_tick(tick)) == expected
        assert sequence.to_tuple_from_tick(tick) == tuple(expected)


def test_history_suffix_preserves_empty_and_complete_cases() -> None:
    sequence: HistorySequence[SimpleNamespace] = HistorySequence()
    assert sequence.to_tuple_from_tick(0) == ()
    for tick, value in ((0, "a"), (1, "b"), (1, "c"), (3, "d")):
        sequence = sequence.append((SimpleNamespace(tick=tick, v=value),))
    assert [item.v for item in sequence.iter_from_tick(1)] == ["b", "c", "d"]
    assert [item.v for item in sequence.iter_from_tick(4)] == []


@pytest.mark.asyncio
async def test_accumulator_matches_full_fold_every_boundary() -> None:
    workload, config = _active_config(ticks=14)
    runner = await SimulationRunner.from_config(config, run_id=workload.run_id)
    try:
        for _ in range(14):
            await runner.run_tick()
            expected = build_population_progress(
                lifecycle_records=runner.engine.lifecycle_records,
                detached_bodies=runner.engine.detached_bodies(),
                boundary_tick=runner.ticks_committed,
            )
            assert runner._generational_progress == expected
    finally:
        await runner.aclose()


@pytest.mark.asyncio
async def test_accumulator_rejects_boundary_replay_conflicts() -> None:
    workload, config = _active_config(ticks=6)
    runner = await SimulationRunner.from_config(config, run_id=workload.run_id)
    try:
        await runner.run_tick()
        accumulator = PopulationProgressAccumulator.bootstrap(
            lifecycle_records=runner.engine.lifecycle_records,
            detached_bodies=runner.engine.detached_bodies(),
            boundary_tick=runner.ticks_committed,
        )
        records = runner.engine.lifecycle_records
        assert accumulator.apply_boundary(
            boundary_tick=runner.ticks_committed,
            lifecycle_records=records,
            died_body_ids=(),
        ) == accumulator.snapshot(boundary_tick=runner.ticks_committed)
        with pytest.raises(ValueError, match=r"boundary_conflict|regressed"):
            accumulator.apply_boundary(
                boundary_tick=0,
                lifecycle_records=records,
                died_body_ids=(),
            )
    finally:
        await runner.aclose()


__all__: tuple[str, ...] = ()
