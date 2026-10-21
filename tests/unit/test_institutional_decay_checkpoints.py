"""Institutional-decay runtime checkpoint continuation and validation."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition.institutional_decay import (
    empty_institution_decay_ledger,
)
from agents.models import AgentId
from experiments.institutionalization_scenario import institutionalization_scenario
from simulation.agent_runtime import AgentRuntimeError, AgentRuntimeStatus
from simulation.models import RunId
from simulation.new_agent_initialization import SUBJECTIVE_COPY_DENY_LIST
from simulation.run_control import AgentRuntimeCheckpoint
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V54,
    InstitutionalDecayMode,
    InstitutionalMemoryMode,
    InstitutionConceptMode,
    SimulationRunnerConfig,
)


def _config(*, enabled: bool = True) -> SimulationRunnerConfig:
    definition = institutionalization_scenario(seed=23, max_ticks=2)
    base = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bf-institution-on"
    )
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                institution_concept_mode=InstitutionConceptMode.DETERMINISTIC,
                institutional_memory_mode=InstitutionalMemoryMode.DISABLED,
                institutional_decay_mode=(
                    InstitutionalDecayMode.DETERMINISTIC
                    if enabled
                    else InstitutionalDecayMode.DISABLED
                ),
            ),
        )
        for agent in base.agents
    )
    return replace(base, schema_version=RUNNER_SCHEMA_VERSION_V54, agents=agents)


@pytest.mark.asyncio
async def test_checkpoint_round_trip_preserves_decay_ledgers() -> None:
    config = _config()
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-decay-checkpoint")
    ) as runner:
        await runner.run()
        checkpoint = runner.export_runtime_checkpoint()
        exported = runner.export_institutional_decay_ledgers()

    assert exported
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-decay-checkpoint")
    ) as restored:
        restored.apply_runtime_checkpoint(checkpoint)
        assert restored.export_institutional_decay_ledgers() == exported


@pytest.mark.asyncio
async def test_disabled_runtime_rejects_decay_checkpoint_state() -> None:
    config = _config()
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-decay-checkpoint")
    ) as runner:
        await runner.run()
        checkpoint = runner.export_runtime_checkpoint()
    disabled_agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                institutional_decay_mode=InstitutionalDecayMode.DISABLED,
                institutional_memory_mode=InstitutionalMemoryMode.DETERMINISTIC,
            ),
        )
        for agent in config.agents
    )
    disabled = replace(
        config, schema_version="runner-config-v53", agents=disabled_agents
    )
    async with await SimulationRunner.from_config(
        disabled, run_id=RunId("run-decay-checkpoint")
    ) as restored:
        with pytest.raises((ValueError, AgentRuntimeError)):
            restored.apply_runtime_checkpoint(checkpoint)


def test_checkpoint_field_rejects_foreign_owner() -> None:
    from agents.cognition.models import InternalAgentState

    with pytest.raises(ValueError, match="owner_id mismatch"):
        AgentRuntimeCheckpoint(
            agent_id=AgentId("alice"),
            status=AgentRuntimeStatus.CREATED,
            internal_state=InternalAgentState(owner_id=AgentId("alice")),
            last_observation_key=None,
            processed_invocation_count=0,
            finalized_hash_count=0,
            goals=(),
            institutional_decay=empty_institution_decay_ledger(AgentId("bob")),
        )


def test_decay_state_is_denied_to_newborn_copy() -> None:
    assert "institutional_decay" in SUBJECTIVE_COPY_DENY_LIST
