"""V4-06 formal-rule carry through cognition, runner, and checkpoints."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition import (
    FormalRuleLedger,
    Perspective,
    build_cognitive_loop,
    empty_formal_rule_ledger,
)
from agents.cognition.configuration import (
    CognitionFormalRuleMode,
    CognitionLoopConfig,
)
from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.agent_runtime import AgentRuntime
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
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules
from world.observations import Observation

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-1")


def _base() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="cmp-v4-formal-rule-runtime",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-formal-rule-runtime"),
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
        v4_capability_flags=V4CapabilityFlags(formal_rules=enabled),
    )


def test_disabled_mode_allocates_no_ledger() -> None:
    loop = build_cognitive_loop(CognitionLoopConfig())
    assert loop._formal_rule_mode is CognitionFormalRuleMode.DISABLED
    assert loop._formal_rule_policy is None
    assert loop._prepared_formal_rules is None


def test_deterministic_mode_installs_the_locked_policy() -> None:
    loop = build_cognitive_loop(
        CognitionLoopConfig(
            formal_rule_mode=CognitionFormalRuleMode.DETERMINISTIC
        )
    )
    assert loop._formal_rule_mode is CognitionFormalRuleMode.DETERMINISTIC
    assert loop._formal_rule_policy is not None
    assert loop._formal_rule_policy.version == "formal-rules.v1"


@pytest.mark.asyncio
async def test_enabled_runner_prepares_and_exports_one_ledger() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-formal-rule-enabled")
    ) as runner:
        for runtime in runner._runtimes:
            assert (
                runtime._loop._formal_rule_mode
                is CognitionFormalRuleMode.DETERMINISTIC
            )
        assert runner.export_formal_rule_ledgers() == ()
        result = await runner.run()

    assert len(result.formal_rule_ledgers) == 1
    ledger = result.formal_rule_ledgers[0]
    assert type(ledger) is FormalRuleLedger
    assert ledger.owner_id == OWNER
    assert ledger.rules == ()


@pytest.mark.asyncio
async def test_disabled_runner_carries_no_ledger() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=False), run_id=RunId("run-formal-rule-disabled")
    ) as runner:
        for runtime in runner._runtimes:
            assert (
                runtime._loop._formal_rule_mode
                is CognitionFormalRuleMode.DISABLED
            )
        result = await runner.run()

    assert runner.export_formal_rule_ledgers() == ()
    assert result.formal_rule_ledgers == ()


@pytest.mark.asyncio
async def test_runtime_checkpoint_field_round_trips_the_ledger() -> None:
    config = _config(enabled=True)
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-formal-rule-checkpoint")
    ) as runner:
        await runner.run()
        checkpoint = runner.export_runtime_checkpoint()
        exported = runner.export_formal_rule_ledgers()

    assert len(exported) == 1
    assert checkpoint.runtime_states[0].formal_rules == exported[0]

    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-formal-rule-checkpoint")
    ) as restored:
        restored.apply_runtime_checkpoint(checkpoint)
        assert restored.export_formal_rule_ledgers() == exported


@pytest.mark.asyncio
async def test_snapshot_and_checkpoint_reject_foreign_owner() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-formal-rule-foreign")
    ) as runner:
        await runner.run()
        checkpoint = runner.export_runtime_checkpoint()

    state = checkpoint.runtime_states[0]
    with pytest.raises(ValueError):
        replace(state, formal_rules=FormalRuleLedger(owner_id=AgentId("other")))

    tampered = replace(
        checkpoint,
        runtime_states=(
            replace(state, formal_rules=FormalRuleLedger(owner_id=OWNER)),
        ),
    )
    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-formal-rule-foreign")
    ) as runner:
        runner.apply_runtime_checkpoint(tampered)
        assert len(runner.export_formal_rule_ledgers()) == 1


@pytest.mark.asyncio
async def test_runner_result_requires_ordered_unique_ledgers() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-formal-rule-ordered")
    ) as runner:
        result = await runner.run()

    with pytest.raises(TypeError, match="formal_rule_ledgers must be ordered"):
        replace(
            result,
            formal_rule_ledgers=frozenset(result.formal_rule_ledgers),  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError, match="formal_rule_ledgers: invalid_item"):
        replace(result, formal_rule_ledgers=(object(),))


def test_perspective_carries_the_ledger() -> None:
    ledger = empty_formal_rule_ledger(OWNER)
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=0,
    )
    perspective = Perspective(
        agent_id=OWNER,
        observation=observation,
        memories=(),
        beliefs=(),
        inbox=(),
        formal_rules=ledger,
    )
    assert perspective.formal_rules is ledger


def test_fork_state_copies_the_prepared_ledger() -> None:
    loop = build_cognitive_loop(
        CognitionLoopConfig(
            formal_rule_mode=CognitionFormalRuleMode.DETERMINISTIC
        )
    )
    ledger = empty_formal_rule_ledger(OWNER)
    loop._prepared_formal_rules = ledger
    state = loop.export_fork_state()

    restored = build_cognitive_loop(
        CognitionLoopConfig(
            formal_rule_mode=CognitionFormalRuleMode.DETERMINISTIC
        )
    )
    restored.restore_fork_state(state)
    assert restored._prepared_formal_rules == ledger
    assert type(restored._prepared_formal_rules) is FormalRuleLedger


def test_agent_runtime_slots_include_formal_rules() -> None:
    assert "_formal_rules" in AgentRuntime.__slots__
