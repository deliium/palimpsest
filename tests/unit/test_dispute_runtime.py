"""V4-07 dispute carry through cognition, checkpoints, and the runner."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition import (
    DisputeLedger,
    Perspective,
    build_cognitive_loop,
    empty_dispute_ledger,
)
from agents.cognition.configuration import (
    CognitionDisputeMode,
    CognitionLoopConfig,
)
from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.agent_runtime import AgentRuntime, AgentRuntimeError
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
        stochastic_identity="cmp-v4-dispute-runtime",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-dispute-runtime"),
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
        v4_capability_flags=V4CapabilityFlags(legal_disputes=enabled),
    )


def test_disabled_mode_never_allocates_a_ledger() -> None:
    loop = build_cognitive_loop(CognitionLoopConfig())
    assert loop._dispute_mode is CognitionDisputeMode.DISABLED
    assert loop._dispute_policy is None
    assert loop._prepared_disputes is None


def test_deterministic_mode_carries_owner_ledger() -> None:
    loop = build_cognitive_loop(
        CognitionLoopConfig(dispute_mode=CognitionDisputeMode.DETERMINISTIC)
    )
    assert loop._dispute_mode is CognitionDisputeMode.DETERMINISTIC
    assert loop._dispute_policy is not None
    assert loop._dispute_policy.version == "dispute-resolution.v1"
    ledger = empty_dispute_ledger(OWNER)
    loop._prepared_disputes = ledger
    state = loop.export_fork_state()
    restored = build_cognitive_loop(
        CognitionLoopConfig(dispute_mode=CognitionDisputeMode.DETERMINISTIC)
    )
    restored.restore_fork_state(state)
    assert restored._prepared_disputes == ledger


@pytest.mark.asyncio
async def test_enabled_runner_exports_one_owner_ledger() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-dispute-enabled")
    ) as runner:
        for runtime in runner._runtimes:
            assert runtime._loop._dispute_mode is CognitionDisputeMode.DETERMINISTIC
        assert runner.export_dispute_ledgers() == ()
        result = await runner.run()

    assert len(result.dispute_ledgers) == 1
    ledger = result.dispute_ledgers[0]
    assert isinstance(ledger, DisputeLedger)
    assert ledger.owner_id == OWNER.value
    assert ledger.has_content is False


@pytest.mark.asyncio
async def test_disabled_runner_carries_no_ledger() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=False), run_id=RunId("run-dispute-disabled")
    ) as runner:
        result = await runner.run()

    assert runner.export_dispute_ledgers() == ()
    assert result.dispute_ledgers == ()


@pytest.mark.asyncio
async def test_checkpoint_round_trip_preserves_disputes() -> None:
    config = _config(enabled=True)
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-dispute-checkpoint")
    ) as runner:
        await runner.run()
        checkpoint = runner.export_runtime_checkpoint()
        exported = runner.export_dispute_ledgers()

    assert len(exported) == 1
    assert checkpoint.runtime_states[0].disputes == exported[0]

    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-dispute-checkpoint")
    ) as restored:
        restored.apply_runtime_checkpoint(checkpoint)
        assert restored.export_dispute_ledgers() == exported


@pytest.mark.asyncio
async def test_checkpoint_rejects_wrong_owner() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-dispute-foreign")
    ) as runner:
        await runner.run()
        checkpoint = runner.export_runtime_checkpoint()

    state = checkpoint.runtime_states[0]
    with pytest.raises(ValueError):
        replace(state, disputes=DisputeLedger(owner_id="other"))


@pytest.mark.asyncio
async def test_runner_exports_owner_ordered_ledgers() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-dispute-order")
    ) as runner:
        result = await runner.run()

    owners = [
        ledger.owner_id
        for ledger in result.dispute_ledgers
        if isinstance(ledger, DisputeLedger)
    ]
    assert owners == sorted(owners)
    assert owners == [OWNER.value]


@pytest.mark.asyncio
async def test_worker_cannot_write_another_owner_ledger() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-dispute-worker")
    ) as runner:
        runtime = runner._runtimes[0]
        with pytest.raises(AgentRuntimeError):
            runtime._commit_disputes(DisputeLedger(owner_id="other"), 1)


def test_public_facades_export_dispute_contracts() -> None:
    import agents.cognition as cognition
    import simulation

    assert cognition.DisputeLedger is DisputeLedger
    assert cognition.DisputePolicy is not None
    assert cognition.apply_dispute_update is not None
    assert cognition.record_dispute_utterance is not None
    assert cognition.compile_dispute_undertaking is not None
    assert simulation.DisputeLedger is DisputeLedger
    assert simulation.empty_dispute_ledger is empty_dispute_ledger
    assert simulation.require_owner_disputes is not None


@pytest.mark.asyncio
async def test_runner_result_ledgers_are_narrowed_before_field_access() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-dispute-narrow")
    ) as runner:
        result = await runner.run()

    for ledger in result.dispute_ledgers:
        assert isinstance(ledger, DisputeLedger)
        assert ledger.owner_id.startswith("agent-")

    with pytest.raises(TypeError, match="dispute_ledgers must be ordered"):
        replace(
            result,
            dispute_ledgers=frozenset(result.dispute_ledgers),  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError, match="dispute_ledgers: invalid_item"):
        replace(result, dispute_ledgers=(object(),))


def test_perspective_carries_the_ledger() -> None:
    ledger = empty_dispute_ledger(OWNER)
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
        disputes=ledger,
    )
    assert perspective.disputes is ledger


def test_agent_runtime_slots_include_disputes() -> None:
    assert "_disputes" in AgentRuntime.__slots__
