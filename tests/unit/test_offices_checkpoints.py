"""Office runtime checkpoint continuation and fork parity (not durable restart)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from experiments.institutionalization_scenario import institutionalization_scenario
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V50,
    InstitutionConceptMode,
    OfficeSuccessionMode,
)


def _config(max_ticks: int = 6):
    definition = institutionalization_scenario(seed=23, max_ticks=max_ticks)
    base = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bf-institution-on"
    )
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V50,
        agents=tuple(
            replace(
                agent,
                cognition=replace(
                    agent.cognition,
                    institution_concept_mode=InstitutionConceptMode.DISABLED,
                    office_succession_mode=OfficeSuccessionMode.DETERMINISTIC,
                ),
            )
            for agent in base.agents
        ),
    )


def _owner_ids(config) -> list[str]:
    return [agent.agent_id.value for agent in config.agents]


@pytest.mark.asyncio
async def test_runtime_checkpoint_preserves_office_state() -> None:
    config = _config()
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-office-ckpt")
    ) as runner:
        await runner.run_tick()
        await runner.run_tick()
        checkpoint = runner.export_runtime_checkpoint()
        before = runner.export_office_concept_ledgers()

    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-office-ckpt")
    ) as restored:
        restored.apply_runtime_checkpoint(checkpoint)
        after_restore = restored.export_office_concept_ledgers()

    assert after_restore == before
    assert [ledger.owner_id.value for ledger in after_restore] == _owner_ids(config)
    assert all(state.office_concepts is not None for state in checkpoint.runtime_states)


@pytest.mark.asyncio
async def test_restored_continuation_matches_uninterrupted_office_state() -> None:
    config = _config()
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-office-continuation")
    ) as runner:
        await runner.run_tick()
        await runner.run_tick()
        checkpoint = runner.export_runtime_checkpoint()
        for _ in range(4):
            await runner.run_tick()
        uninterrupted = runner.export_office_concept_ledgers()

    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-office-continuation")
    ) as restored:
        restored.apply_runtime_checkpoint(checkpoint)
        for _ in range(4):
            await restored.run_tick()
        restored_final = restored.export_office_concept_ledgers()

    assert restored_final == uninterrupted


@pytest.mark.asyncio
async def test_forks_detach_office_values() -> None:
    config = _config(max_ticks=4)
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-office-fork")
    ) as runner:
        await runner.run_tick()
        checkpoint = runner.export_runtime_checkpoint()

    async with (
        await SimulationRunner.from_config(
            config, run_id=RunId("run-office-fork")
        ) as left,
        await SimulationRunner.from_config(
            config, run_id=RunId("run-office-fork")
        ) as right,
    ):
        left.apply_runtime_checkpoint(checkpoint)
        right.apply_runtime_checkpoint(checkpoint)
        left_ledgers = left.export_office_concept_ledgers()
        right_ledgers = right.export_office_concept_ledgers()
        assert left_ledgers == right_ledgers
        for _ in range(3):
            await left.run_tick()
            await right.run_tick()
        assert (
            left.export_office_concept_ledgers()
            == right.export_office_concept_ledgers()
        )


@pytest.mark.asyncio
async def test_cross_owner_checkpoint_rejects() -> None:
    config = _config(max_ticks=2)
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-office-cross")
    ) as runner:
        checkpoint = runner.export_runtime_checkpoint()
    states = list(checkpoint.runtime_states)
    states[0] = replace(states[0], agent_id=states[1].agent_id)
    forged = replace(checkpoint, runtime_states=tuple(states))
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-office-cross")
    ) as runner:
        with pytest.raises(
            ValueError,
            match="duplicate runtime state owner",
        ):
            runner.apply_runtime_checkpoint(forged)
