"""Idempotent finish_run and terminal attempt-ledger behavior."""

from __future__ import annotations

from dataclasses import replace

import pytest

from simulation.runner import SimulationRunner
from simulation.runner_models import RunnerStopReasonCode
from tests.unit.test_generational_population_runner import _v55_config


@pytest.mark.asyncio
async def test_finish_run_is_idempotent_and_rejects_conflicting_reason() -> None:
    runner = await SimulationRunner.from_config(_v55_config())
    try:
        await runner.run_tick()
        first = await runner.finish_run(RunnerStopReasonCode.MAX_TICKS)
        second = await runner.finish_run(RunnerStopReasonCode.MAX_TICKS)
        assert first is second
        with pytest.raises(Exception, match="finish_run_conflict"):
            await runner.finish_run(RunnerStopReasonCode.AUTHORITY_FAILURE)
    finally:
        await runner.aclose()


@pytest.mark.asyncio
async def test_terminal_receipt_does_not_duplicate_attempts() -> None:
    config = _v55_config()
    config = replace(
        config,
        stop_policy=replace(config.stop_policy, max_ticks=1),
    )
    runner = await SimulationRunner.from_config(config)
    try:
        first = await runner.run_tick()
        assert first.stop_reason is RunnerStopReasonCode.MAX_TICKS
        count = len(runner._attempt_receipts)
        repeated = await runner.run_tick()
        assert repeated == first
        assert len(runner._attempt_receipts) == count
    finally:
        await runner.aclose()
