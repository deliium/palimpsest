"""Mediation runtime checkpoint continuation and preflight rejection."""

from __future__ import annotations

from dataclasses import replace

import pytest

from experiments.institutionalization_scenario import institutionalization_scenario
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V52,
    MediationMode,
    SimulationRunnerConfig,
)


def _config(max_ticks: int = 6, *, enabled: bool = True) -> SimulationRunnerConfig:
    definition = institutionalization_scenario(seed=23, max_ticks=max_ticks)
    base = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bf-baseline"
    )
    if not enabled:
        return base
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V52,
        agents=tuple(
            replace(
                agent,
                cognition=replace(
                    agent.cognition,
                    mediation_mode=MediationMode.DETERMINISTIC,
                ),
            )
            for agent in base.agents
        ),
    )


@pytest.mark.asyncio
async def test_runtime_checkpoint_preserves_enabled_owner_ledgers() -> None:
    config = _config()
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-mediation-ckpt")
    ) as runner:
        await runner.run_tick()
        await runner.run_tick()
        checkpoint = runner.export_runtime_checkpoint()
        before = runner.export_mediation_ledgers()

    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-mediation-ckpt")
    ) as restored:
        restored.apply_runtime_checkpoint(checkpoint)
        after = restored.export_mediation_ledgers()

    assert after == before
    assert len(after) == len(config.agents)
    assert all(state.mediation is not None for state in checkpoint.runtime_states)


@pytest.mark.asyncio
async def test_restored_continuation_matches_uninterrupted_state() -> None:
    config = _config()
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-mediation-continuation")
    ) as runner:
        await runner.run_tick()
        await runner.run_tick()
        checkpoint = runner.export_runtime_checkpoint()
        for _ in range(4):
            await runner.run_tick()
        uninterrupted = runner.export_mediation_ledgers()

    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-mediation-continuation")
    ) as restored:
        restored.apply_runtime_checkpoint(checkpoint)
        for _ in range(4):
            await restored.run_tick()
        assert restored.export_mediation_ledgers() == uninterrupted


@pytest.mark.asyncio
async def test_disabled_owners_export_nothing() -> None:
    config = _config(enabled=False)
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-mediation-off")
    ) as runner:
        await runner.run_tick()
        assert runner.export_mediation_ledgers() == ()


@pytest.mark.asyncio
async def test_disabled_target_rejects_non_none_mediation() -> None:
    enabled = _config()
    disabled = _config(enabled=False)
    async with await SimulationRunner.from_config(
        enabled, run_id=RunId("run-mediation-reject")
    ) as runner:
        await runner.run_tick()
        checkpoint = runner.export_runtime_checkpoint()
    async with await SimulationRunner.from_config(
        disabled, run_id=RunId("run-mediation-reject")
    ) as target:
        with pytest.raises((TypeError, ValueError)):
            target.apply_runtime_checkpoint(checkpoint)
        assert target.export_mediation_ledgers() == ()


@pytest.mark.asyncio
async def test_wrong_ledger_type_is_rejected_before_partial_apply() -> None:
    config = _config()
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-mediation-type")
    ) as runner:
        await runner.run_tick()
        checkpoint = runner.export_runtime_checkpoint()
    from simulation.run_control import AgentRuntimeCheckpoint

    states = list(checkpoint.runtime_states)
    tampered_state = object.__new__(AgentRuntimeCheckpoint)
    for name in AgentRuntimeCheckpoint.__dataclass_fields__:
        object.__setattr__(tampered_state, name, getattr(states[1], name))
    object.__setattr__(tampered_state, "mediation", object())
    states[1] = tampered_state
    tampered = object.__new__(type(checkpoint))
    for name in type(checkpoint).__dataclass_fields__:
        object.__setattr__(tampered, name, getattr(checkpoint, name))
    object.__setattr__(tampered, "runtime_states", tuple(states))
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-mediation-type")
    ) as target:
        with pytest.raises(TypeError):
            target.apply_runtime_checkpoint(tampered)
        assert target.export_mediation_ledgers() == ()
