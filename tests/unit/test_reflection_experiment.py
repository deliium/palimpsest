"""Experiment G shares history through the first reflection and audits one arm."""

from __future__ import annotations

import pytest

from analysis.reflection_metrics import ReflectionReport, compute_reflection
from experiments import experiment_g_reflection, map_reflection_audits_to_report
from experiments.composition import map_reflection_audits_to_report as mapped
from simulation.models import RunId
from simulation.runner import SimulationRunner
from tests.unit.test_experiment_definitions import _base
from world.identifiers import require_stable_id


async def _run(condition_id: str, run_id: str):
    definition = experiment_g_reflection(_base())
    config = next(
        item.runner_config
        for item in definition.conditions
        if item.condition_id == condition_id
    )
    async with await SimulationRunner.from_config(
        config, run_id=RunId(run_id)
    ) as runner:
        return await runner.run()


def _hash_through(result: object, tick: int) -> tuple[str, ...]:
    hashes = []
    for receipt in result.finalized_tick_receipts:
        if receipt.tick > tick:
            break
        hashes.append(receipt.objective_state_hash)
    return tuple(hashes)


@pytest.mark.asyncio
async def test_deterministic_arm_audits_without_rewriting_the_reflection_tick() -> None:
    disabled = await _run("g-disabled", "run-g-disabled")
    deterministic = await _run("g-deterministic", "run-g-deterministic")
    repeated = await _run("g-deterministic", "run-g-deterministic-repeat")
    assert disabled.reflection_audits == ()
    assert deterministic.reflection_audits
    reflection_tick = deterministic.reflection_audits[0].tick
    assert _hash_through(disabled, reflection_tick) == _hash_through(
        deterministic, reflection_tick
    )
    assert deterministic.objective_state_hash == repeated.objective_state_hash
    report = mapped(
        run_id="run-g-deterministic",
        audits=deterministic.reflection_audits,
    )
    assert type(report) is ReflectionReport
    assert report.reflection_invocations >= 1
    revision = require_stable_id("rev", "rev-g")
    document = compute_reflection(report, input_revision=revision)
    assert document.metric_family == "reflection"
    assert document.values["reflection_invocations"] >= 1
    assert map_reflection_audits_to_report is mapped
