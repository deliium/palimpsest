"""Runtime checkpoint continuation without owner transfer."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition.configuration import (
    CognitionInstitutionalMemoryMode,
    CognitionLoopConfig,
    build_cognitive_loop,
)
from agents.cognition.institutional_memory import (
    InstitutionalMemoryLedger,
    empty_institutional_memory_ledger,
)
from agents.models import AgentId
from experiments.institutionalization_scenario import institutionalization_scenario
from simulation.agent_runtime import AgentRuntimeError
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V53,
    InstitutionalMemoryMode,
    InstitutionConceptMode,
)


def _config():
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
                institutional_memory_mode=InstitutionalMemoryMode.DETERMINISTIC,
            ),
        )
        for agent in base.agents
    )
    return replace(base, schema_version=RUNNER_SCHEMA_VERSION_V53, agents=agents)


@pytest.mark.asyncio
async def test_checkpoint_round_trip_preserves_owner_ledgers() -> None:
    config = _config()
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-institutional-checkpoint")
    ) as runner:
        await runner.run()
        checkpoint = runner.export_runtime_checkpoint()
        exported = runner.export_institutional_memory_ledgers()
    assert all(type(ledger) is InstitutionalMemoryLedger for ledger in exported)

    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-institutional-checkpoint")
    ) as restored:
        restored.apply_runtime_checkpoint(checkpoint)
        restored_ledgers = restored.export_institutional_memory_ledgers()
        assert restored_ledgers == exported
        assert all(
            ledger.owner_id == runtime.agent_id
            for runtime, ledger in zip(
                restored._runtimes, restored_ledgers, strict=True
            )
        )


@pytest.mark.asyncio
async def test_disabled_runtime_rejects_institutional_checkpoint_state() -> None:
    config = _config()
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-institutional-checkpoint")
    ) as runner:
        await runner.run()
        checkpoint = runner.export_runtime_checkpoint()
    disabled_config = replace(
        config,
        schema_version="runner-config-v49",
        agents=tuple(
            replace(
                agent,
                cognition=replace(
                    agent.cognition,
                    institutional_memory_mode=InstitutionalMemoryMode.DISABLED,
                    institution_concept_mode=InstitutionConceptMode.DETERMINISTIC,
                ),
            )
            for agent in config.agents
        ),
    )
    async with await SimulationRunner.from_config(
        disabled_config, run_id=RunId("run-institutional-checkpoint")
    ) as restored:
        with pytest.raises((ValueError, AgentRuntimeError)):
            restored.apply_runtime_checkpoint(checkpoint)


def test_checkpoint_field_rejects_foreign_owner() -> None:
    from agents.cognition.models import InternalAgentState
    from simulation.agent_runtime import AgentRuntimeStatus
    from simulation.run_control import AgentRuntimeCheckpoint

    with pytest.raises(ValueError, match="owner_id mismatch"):
        AgentRuntimeCheckpoint(
            agent_id=AgentId("alice"),
            status=AgentRuntimeStatus.CREATED,
            internal_state=InternalAgentState(owner_id=AgentId("alice")),
            last_observation_key=None,
            processed_invocation_count=0,
            finalized_hash_count=0,
            goals=(),
            institutional_memory=empty_institutional_memory_ledger(AgentId("bob")),
        )


def test_disabled_direct_loop_rejects_injected_selection() -> None:
    loop = build_cognitive_loop(CognitionLoopConfig())
    assert loop._institutional_memory_mode is CognitionInstitutionalMemoryMode.DISABLED
