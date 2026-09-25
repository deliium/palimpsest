"""Experiment F sleeps on the same tick with and without consolidation."""

from __future__ import annotations

import pytest

from experiments import experiment_f_sleep_consolidation
from simulation.models import RunId
from simulation.runner import SimulationRunner
from tests.unit.test_experiment_definitions import _base


async def _run(condition_id: str, run_id: str):
    definition = experiment_f_sleep_consolidation(_base())
    config = next(
        item.runner_config
        for item in definition.conditions
        if item.condition_id == condition_id
    )
    async with await SimulationRunner.from_config(
        config, run_id=RunId(run_id)
    ) as runner:
        return await runner.run()


@pytest.mark.asyncio
async def test_both_arms_sleep_and_only_deterministic_audits() -> None:
    disabled = await _run("f-disabled", "run-f-disabled")
    deterministic = await _run("f-deterministic", "run-f-deterministic")
    disabled_again = await _run("f-disabled", "run-f-disabled-repeat")
    assert (
        disabled.finalized_tick_receipts[0].resolutions[0].command_kind == "sleep"
    )
    assert (
        deterministic.finalized_tick_receipts[0].resolutions[0].command_kind
        == "sleep"
    )
    assert disabled.offline_consolidation_audits == ()
    assert deterministic.offline_consolidation_audits
    assert any(
        audit.merge_count
        + audit.strengthen_count
        + audit.soft_forget_count
        + audit.belief_count
        > 0
        for audit in deterministic.offline_consolidation_audits
    )
    disabled_kinds = [
        resolution.command_kind
        for receipt in disabled.finalized_tick_receipts
        for resolution in receipt.resolutions
    ]
    deterministic_kinds = [
        resolution.command_kind
        for receipt in deterministic.finalized_tick_receipts
        for resolution in receipt.resolutions
    ]
    assert disabled_kinds == deterministic_kinds == ["sleep"] * len(disabled_kinds)
    assert disabled.objective_state_hash == disabled_again.objective_state_hash
