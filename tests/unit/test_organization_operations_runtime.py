"""V4-04 operation ledger carry: loop, perspective, runtime, checkpoint, runner."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from agents.cognition import (
    OrganizationOperationLedger,
    Perspective,
    build_cognitive_loop,
    empty_organization_operation_ledger,
)
from agents.cognition.configuration import (
    CognitionLoopConfig,
    CognitionOrganizationMode,
)
from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    SimulationRunnerConfig,
    V4CapabilityFlags,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world import Observation
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit


def _base() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="cmp-v4-organization-operations-runtime",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-organization-operations-runtime"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body,),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=2,
    )


def _config(*, enabled: bool) -> SimulationRunnerConfig:
    return replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v4_capability_flags=V4CapabilityFlags(organizations=enabled),
    )


def test_disabled_loop_allocates_no_operation_ledger() -> None:
    loop = build_cognitive_loop(CognitionLoopConfig())
    assert loop._organization_operation_policy is None
    assert loop._prepared_organization_operations is None


def test_enabled_loop_allocates_the_operation_policy() -> None:
    loop = build_cognitive_loop(
        CognitionLoopConfig(
            organization_concept_mode=CognitionOrganizationMode.DETERMINISTIC
        )
    )
    assert loop._organization_operation_policy is not None
    assert loop._prepared_organization_operations is None


def test_perspective_snapshot_preserves_the_operation_ledger() -> None:
    ledger = empty_organization_operation_ledger(AgentId("agent-1"))
    perspective = Perspective(
        agent_id=AgentId("agent-1"),
        observation=Observation(
            world_id=WorldId("world-1"),
            observer_id=EntityId("ent-1"),
            revision=WorldRevision(0),
        ),
        memories=(),
        beliefs=(),
        inbox=(),
        organization_operations=ledger,
    )
    snapshot = perspective.to_snapshot()
    assert snapshot.organization_operations is ledger
    assert snapshot.organization_operations.owner_id == AgentId("agent-1")


def test_fork_state_carries_the_prepared_operation_ledger() -> None:
    config = CognitionLoopConfig(
        organization_concept_mode=CognitionOrganizationMode.DETERMINISTIC
    )
    loop = build_cognitive_loop(config)
    ledger = empty_organization_operation_ledger(AgentId("agent-1"))
    loop._prepared_organization_operations = ledger
    state = loop.export_fork_state()
    assert state.prepared_organization_operations is ledger
    restored = build_cognitive_loop(config)
    restored.restore_fork_state(state)
    assert restored._prepared_organization_operations is ledger


@pytest.mark.asyncio
async def test_disabled_runner_exports_no_operation_ledgers() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=False), run_id=RunId("run-organization-op-disabled")
    ) as runner:
        for runtime in runner._runtimes:
            assert runtime._organization_operations is None
        result = await runner.run()
        assert runner.export_organization_operation_ledgers() == ()
        assert result.organization_operation_ledgers == ()


@pytest.mark.asyncio
async def test_enabled_runner_prepares_and_exports_operation_ledgers() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-organization-op-enabled")
    ) as runner:
        runtime = runner._runtimes[0]
        assert runtime._organization_operations is None
        result = await runner.run()
        exported = runner.export_organization_operation_ledgers()

    assert len(exported) == 1
    ledgers = cast(tuple[OrganizationOperationLedger, ...], exported)
    assert type(ledgers[0]) is OrganizationOperationLedger
    assert ledgers[0].owner_id == AgentId("agent-1")
    assert result.organization_operation_ledgers == exported
    assert len({ledger.owner_id for ledger in ledgers}) == 1


@pytest.mark.asyncio
async def test_checkpoint_round_trip_preserves_operation_ledgers() -> None:
    config = _config(enabled=True)
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-organization-op-checkpoint")
    ) as runner:
        await runner.run()
        checkpoint = runner.export_runtime_checkpoint()
        exported = runner.export_organization_operation_ledgers()

    assert len(exported) == 1
    ledgers = cast(tuple[OrganizationOperationLedger, ...], exported)
    assert ledgers[0].owner_id == AgentId("agent-1")

    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-organization-op-checkpoint")
    ) as restored:
        restored.apply_runtime_checkpoint(checkpoint)
        assert restored.export_organization_operation_ledgers() == exported


@pytest.mark.asyncio
async def test_runtime_rejects_a_foreign_operation_ledger() -> None:
    from simulation.agent_runtime import AgentRuntimeError

    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-organization-op-foreign")
    ) as runner:
        runtime = runner._runtimes[0]
        foreign = OrganizationOperationLedger(owner_id=AgentId("someone-else"))
        with pytest.raises(AgentRuntimeError):
            runtime._commit_organization_operations(foreign, 0)


@pytest.mark.asyncio
async def test_disabled_runner_rejects_operation_checkpoint_state() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-organization-op-reject")
    ) as runner:
        await runner.run()
        checkpoint = runner.export_runtime_checkpoint()

    states = list(checkpoint.runtime_states)
    tampered_state = replace(
        states[0],
        organization_operations=empty_organization_operation_ledger(
            AgentId("agent-1")
        ),
    )
    tampered = replace(checkpoint, runtime_states=(tampered_state,))
    async with await SimulationRunner.from_config(
        _config(enabled=False), run_id=RunId("run-organization-op-reject")
    ) as disabled:
        with pytest.raises(ValueError, match="organization ledger for disabled owner"):
            disabled.apply_runtime_checkpoint(tampered)
