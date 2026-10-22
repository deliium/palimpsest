"""Finalized generational stopping and terminal latches."""

from __future__ import annotations

from dataclasses import replace

import pytest

from simulation.generational_models import (
    GenerationalRunSpec,
    PopulationThresholdComparison,
    PopulationThresholdSpec,
)
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    LifecycleStageId,
    LifecycleStageThreshold,
    RunnerStopReasonCode,
)
from tests.unit.test_generational_population_runner import _v55_config


def _config(
    *,
    generational_run: GenerationalRunSpec | None = None,
    max_ticks: int = 6,
    lifespan_ticks: int = 30,
    entries_per_interval: int = 1,
):
    config = _v55_config()
    lifecycle = config.population_lifecycle
    assert lifecycle is not None
    thresholds = (
        (LifecycleStageThreshold(LifecycleStageId("infant"), 0),)
        if lifespan_ticks <= 1
        else (
            LifecycleStageThreshold(LifecycleStageId("infant"), 0),
            LifecycleStageThreshold(
                LifecycleStageId("adult"), lifespan_ticks - 1
            ),
        )
    )
    params = dict(lifecycle.demographic_policy_params)
    params["entries_per_interval"] = entries_per_interval
    lifecycle = replace(
        lifecycle,
        lifespan_ticks=lifespan_ticks,
        stage_thresholds=thresholds,
        dependent_until_stage=LifecycleStageId("infant"),
        demographic_policy_params=params,
    )
    return replace(
        config,
        stop_policy=replace(config.stop_policy, max_ticks=max_ticks),
        population_lifecycle=lifecycle,
        generational_run=(
            generational_run
            if generational_run is not None
            else GenerationalRunSpec(max_generation_index=1)
        ),
    )


@pytest.mark.asyncio
async def test_generation_horizon_stops_after_real_admission_and_latches() -> None:
    runner = await SimulationRunner.from_config(_config())
    try:
        receipts = [await runner.run_tick() for _ in range(3)]
        assert [receipt.stop_reason for receipt in receipts] == [
            None,
            None,
            RunnerStopReasonCode.GENERATION_HORIZON,
        ]
        tick_before = runner._engine.tick.value
        events_before = len(runner._engine.last_tick_result.events)
        repeated = await runner.run_tick()
        assert repeated == receipts[-1]
        assert runner._engine.tick.value == tick_before
        assert len(runner._engine.last_tick_result.events) == events_before
        assert runner._stop_evidence is not None
        assert (
            runner._stop_evidence.primary_condition_code
            == RunnerStopReasonCode.GENERATION_HORIZON.value
        )
    finally:
        await runner.aclose()


@pytest.mark.asyncio
async def test_extinction_stops_after_same_tick_deaths() -> None:
    runner = await SimulationRunner.from_config(
        _config(
            generational_run=GenerationalRunSpec(
                max_generation_index=None, stop_on_extinction=True
            ),
            lifespan_ticks=1,
            entries_per_interval=0,
            max_ticks=6,
        )
    )
    try:
        while runner._terminal_receipt is None:
            await runner.run_tick()
        receipt = runner._terminal_receipt
        assert receipt is not None
        assert receipt.stop_reason is RunnerStopReasonCode.POPULATION_EXTINCTION
        assert runner._generational_progress is not None
        assert runner._generational_progress.living_population == 0
    finally:
        await runner.aclose()


@pytest.mark.asyncio
async def test_threshold_is_inclusive_and_evaluated_after_first_boundary() -> None:
    runner = await SimulationRunner.from_config(
        _config(
            generational_run=GenerationalRunSpec(
                max_generation_index=None,
                stop_on_extinction=False,
                population_threshold=PopulationThresholdSpec(
                    comparison=PopulationThresholdComparison.AT_LEAST, value=3
                ),
            ),
            entries_per_interval=0,
        )
    )
    try:
        receipt = await runner.run_tick()
        assert receipt.stop_reason is RunnerStopReasonCode.POPULATION_THRESHOLD
        assert runner._generational_progress is not None
        assert runner._generational_progress.boundary_tick == 1
    finally:
        await runner.aclose()


@pytest.mark.asyncio
async def test_extinction_outranks_at_most_zero_threshold() -> None:
    runner = await SimulationRunner.from_config(
        _config(
            generational_run=GenerationalRunSpec(
                max_generation_index=None,
                stop_on_extinction=True,
                population_threshold=PopulationThresholdSpec(
                    comparison=PopulationThresholdComparison.AT_MOST, value=0
                ),
            ),
            lifespan_ticks=1,
            entries_per_interval=0,
            max_ticks=6,
        )
    )
    try:
        while runner._terminal_receipt is None:
            await runner.run_tick()
        evidence = runner._stop_evidence
        assert evidence is not None
        assert evidence.primary_condition_code == "population_extinction"
        assert "population_threshold" in evidence.matched_condition_codes
    finally:
        await runner.aclose()


@pytest.mark.asyncio
async def test_empty_population_continues_without_extinction_or_terminal() -> None:
    runner = await SimulationRunner.from_config(
        _config(
            generational_run=GenerationalRunSpec(
                max_generation_index=None,
                stop_on_extinction=False,
            ),
            lifespan_ticks=1,
            entries_per_interval=0,
            max_ticks=4,
        )
    )
    try:
        while runner._terminal_receipt is None:
            await runner.run_tick()
        receipt = runner._terminal_receipt
        assert receipt is not None
        assert receipt.stop_reason is RunnerStopReasonCode.MAX_TICKS
        assert runner._generational_progress is not None
        assert runner._generational_progress.living_population == 0
    finally:
        await runner.aclose()


@pytest.mark.asyncio
async def test_simultaneous_tick_and_generation_horizon_keep_both_matches() -> None:
    runner = await SimulationRunner.from_config(
        _config(
            generational_run=GenerationalRunSpec(max_generation_index=1),
            max_ticks=3,
        )
    )
    try:
        receipts = [await runner.run_tick() for _ in range(3)]
        final = receipts[-1]
        assert final.stop_reason is RunnerStopReasonCode.MAX_TICKS
        evidence = runner._stop_evidence
        assert evidence is not None
        assert set(evidence.matched_condition_codes) == {
            "max_ticks",
            "generation_horizon",
        }
        assert evidence.primary_condition_code == "max_ticks"
    finally:
        await runner.aclose()


@pytest.mark.asyncio
async def test_run_returns_v3_evidence_after_max_tick_horizon() -> None:
    runner = await SimulationRunner.from_config(_config(max_ticks=2))
    try:
        result = await runner.run()
        assert result.stop_reason is RunnerStopReasonCode.MAX_TICKS
        assert result.generational_progress is not None
        assert result.stop_evidence is not None
        assert result.generational_progress.boundary_tick == 2
    finally:
        await runner.aclose()
