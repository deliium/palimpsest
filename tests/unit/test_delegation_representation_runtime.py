"""V4-09 representation ledger carry through cognition, runtime, and results."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

import pytest

from agents.cognition import (
    Perspective,
    RepresentationError,
    RepresentationLedger,
    build_cognitive_loop,
    empty_representation_ledger,
    require_owner_representation,
)
from agents.cognition.configuration import (
    CognitionLoopConfig,
    CognitionRepresentationMode,
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
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules
from world.observations import Observation

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-1")


def _base() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = OWNER
    return base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="cmp-v4-representation-runtime",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-representation-runtime"),
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


def _observation() -> Observation:
    return Observation(
        world_id=WorldId("world-v4-representation-runtime"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=1,
        occurrences=(),
    )


def test_perspective_carries_representation_into_the_snapshot() -> None:
    ledger = empty_representation_ledger(OWNER)
    perspective = Perspective(
        agent_id=OWNER,
        observation=_observation(),
        memories=(),
        beliefs=(),
        inbox=(),
        semantic_beliefs=(),
        representation=ledger,
    )
    snapshot = perspective.to_snapshot()
    assert snapshot.representation is ledger
    require_owner_representation(snapshot.representation, OWNER)

    with pytest.raises(RepresentationError):
        replace(snapshot, representation=empty_representation_ledger("agent-2"))


def test_fork_state_preserves_prepared_representation() -> None:
    loop = build_cognitive_loop(
        CognitionLoopConfig(
            representation_mode=CognitionRepresentationMode.DETERMINISTIC
        )
    )
    ledger = empty_representation_ledger(OWNER)
    loop._prepared_representation = ledger
    state = loop.export_fork_state()
    assert state.prepared_representation is ledger

    restored = build_cognitive_loop(
        CognitionLoopConfig(
            representation_mode=CognitionRepresentationMode.DETERMINISTIC
        )
    )
    restored.restore_fork_state(state)
    assert restored._prepared_representation is ledger


@pytest.mark.asyncio
async def test_enabled_runner_exports_one_owner_ledger() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-representation-enabled")
    ) as runner:
        for runtime in runner._runtimes:
            assert runtime._loop._representation_mode is (
                CognitionRepresentationMode.DETERMINISTIC
            )
        assert runner.export_representation_ledgers() == ()
        result = await runner.run()

    assert len(result.representation_ledgers) == 1
    ledger = result.representation_ledgers[0]
    assert isinstance(ledger, RepresentationLedger)
    assert ledger.owner_id == OWNER.value
    assert ledger.policy_version == "delegation-representation.v1"


@pytest.mark.asyncio
async def test_disabled_runner_carries_no_ledger() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=False), run_id=RunId("run-representation-disabled")
    ) as runner:
        result = await runner.run()

    assert runner.export_representation_ledgers() == ()
    assert result.representation_ledgers == ()


@pytest.mark.asyncio
async def test_checkpoint_round_trip_preserves_representation() -> None:
    config = _config(enabled=True)
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-representation-checkpoint")
    ) as runner:
        await runner.run()
        checkpoint = runner.export_runtime_checkpoint()
        exported = runner.export_representation_ledgers()

    assert len(exported) == 1
    assert checkpoint.runtime_states[0].representation == exported[0]

    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-representation-checkpoint")
    ) as restored:
        restored.apply_runtime_checkpoint(checkpoint)
        assert restored.export_representation_ledgers() == exported


@pytest.mark.asyncio
async def test_result_rejects_unordered_or_wrong_type() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=False), run_id=RunId("run-representation-result")
    ) as runner:
        result = await runner.run()

    with pytest.raises(TypeError, match="representation_ledgers must be ordered"):
        replace(
            result,
            representation_ledgers=cast(Any, [empty_representation_ledger(OWNER)]),
        )
    with pytest.raises(TypeError, match="invalid_item"):
        replace(result, representation_ledgers=(object(),))


@pytest.mark.asyncio
async def test_worker_cannot_write_another_owner_ledger() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-representation-worker")
    ) as runner:
        runtime = runner._runtimes[0]
        from simulation.agent_runtime import AgentRuntimeError

        with pytest.raises(AgentRuntimeError):
            runtime._commit_representation(RepresentationLedger(owner_id="other"), 1)


def test_public_facades_export_representation_contracts() -> None:
    import agents.cognition as cognition
    import simulation

    assert cognition.RepresentationLedger is RepresentationLedger
    assert cognition.empty_representation_ledger is not None
    assert cognition.apply_representation_update is not None
    assert cognition.record_representation_utterance is not None
    assert cognition.representation_standing_summary is not None
    assert simulation.RepresentationLedger is RepresentationLedger
    assert simulation.empty_representation_ledger is not None
    assert simulation.require_owner_representation is not None
