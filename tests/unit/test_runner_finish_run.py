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


@pytest.mark.asyncio
async def test_generational_checkpoint_carries_control_and_latch() -> None:
    config = _v55_config()
    first = await SimulationRunner.from_config(config)
    try:
        for _ in range(2):
            await first.run_tick()
        checkpoint = first.export_runtime_checkpoint()
        assert checkpoint.generational_control_state is not None
        assert checkpoint.generational_control_state.boundary_tick == 2
        assert checkpoint.generational_control_state.progress is not None
    finally:
        await first.aclose()

    restored = await SimulationRunner.from_config(config, run_id=first.run_id)
    try:
        restored.apply_runtime_checkpoint(checkpoint)
        assert restored._ticks_committed == 2
        assert restored._generational_progress is not None
        assert restored._generational_progress.boundary_tick == 2
        assert restored._finalized_tick_ids == {
            receipt.tick for receipt in restored._finalized_tick_receipts
        }
    finally:
        await restored.aclose()


@pytest.mark.asyncio
async def test_terminal_latch_survives_runtime_checkpoint() -> None:
    config = _v55_config()
    first = await SimulationRunner.from_config(config)
    try:
        while first._terminal_receipt is None:
            await first.run_tick()
        terminal = first._terminal_receipt
        checkpoint = first.export_runtime_checkpoint()
    finally:
        await first.aclose()

    restored = await SimulationRunner.from_config(config, run_id=first.run_id)
    try:
        restored.apply_runtime_checkpoint(checkpoint)
        assert restored._terminal_receipt == terminal
        repeated = await restored.run_tick()
        assert repeated == terminal
    finally:
        await restored.aclose()


@pytest.mark.asyncio
async def test_finished_result_carry_rejects_further_ticks() -> None:
    config = _v55_config()
    first = await SimulationRunner.from_config(config)
    try:
        await first.run()
        checkpoint = first.export_runtime_checkpoint()
        assert checkpoint.generational_control_state is not None
        assert checkpoint.generational_control_state.finished_result is not None
    finally:
        await first.aclose()

    restored = await SimulationRunner.from_config(config, run_id=first.run_id)
    try:
        restored.apply_runtime_checkpoint(checkpoint)
        assert restored._finished_result is not None
        with pytest.raises(Exception, match="finished_run"):
            await restored.run_tick()
    finally:
        await restored.aclose()


@pytest.mark.asyncio
async def test_generational_checkpoint_requires_control_state() -> None:
    config = _v55_config()
    runner = await SimulationRunner.from_config(config)
    try:
        checkpoint = runner.export_runtime_checkpoint()
        broken = replace(checkpoint, generational_control_state=None)
        with pytest.raises(ValueError, match="requires control state"):
            runner.apply_runtime_checkpoint(broken)
        control = checkpoint.generational_control_state
        assert control is not None
        mismatched = replace(control, boundary_tick=control.boundary_tick + 1)
        with pytest.raises(ValueError, match="boundary mismatch"):
            runner.apply_runtime_checkpoint(
                replace(checkpoint, generational_control_state=mismatched)
            )
    finally:
        await runner.aclose()
