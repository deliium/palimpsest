"""V4-08 evidence ledger carry through cognition, runtime, and results."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition import (
    EvidenceError,
    EvidenceLedger,
    Perspective,
    build_cognitive_loop,
    empty_evidence_ledger,
    require_owner_evidence,
)
from agents.cognition.configuration import (
    CognitionEvidenceMode,
    CognitionLoopConfig,
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
        stochastic_identity="cmp-v4-evidence-runtime",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-evidence-runtime"),
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


def _observation() -> Observation:
    return Observation(
        world_id=WorldId("world-v4-evidence-runtime"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=1,
        occurrences=(),
    )


def test_perspective_carries_evidence_into_the_snapshot() -> None:
    ledger = empty_evidence_ledger(OWNER)
    perspective = Perspective(
        agent_id=OWNER,
        observation=_observation(),
        memories=(),
        beliefs=(),
        inbox=(),
        semantic_beliefs=(),
        evidence=ledger,
    )
    snapshot = perspective.to_snapshot()
    assert snapshot.evidence is ledger
    assert require_owner_evidence(snapshot.evidence, OWNER) is ledger

    with pytest.raises(EvidenceError) as error:
        replace(snapshot, evidence=empty_evidence_ledger("agent-2"))
    assert error.value.code == "evidence_owner_mismatch"


def test_fork_state_preserves_prepared_evidence() -> None:
    loop = build_cognitive_loop(
        CognitionLoopConfig(evidence_mode=CognitionEvidenceMode.DETERMINISTIC)
    )
    ledger = empty_evidence_ledger(OWNER)
    loop._prepared_evidence = ledger
    state = loop.export_fork_state()
    assert state.prepared_evidence is ledger

    restored = build_cognitive_loop(
        CognitionLoopConfig(evidence_mode=CognitionEvidenceMode.DETERMINISTIC)
    )
    restored.restore_fork_state(state)
    assert restored._prepared_evidence is ledger


@pytest.mark.asyncio
async def test_enabled_runner_exports_one_owner_ledger() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-evidence-enabled")
    ) as runner:
        for runtime in runner._runtimes:
            assert runtime._loop._evidence_mode is (CognitionEvidenceMode.DETERMINISTIC)
        assert runner.export_evidence_ledgers() == ()
        result = await runner.run()

    assert len(result.evidence_ledgers) == 1
    ledger = result.evidence_ledgers[0]
    assert isinstance(ledger, EvidenceLedger)
    assert ledger.owner_id == OWNER.value
    assert ledger.observation_count >= 1
    assert ledger.policy_version == "evidence-testimony.v1"


@pytest.mark.asyncio
async def test_disabled_runner_carries_no_ledger() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=False), run_id=RunId("run-evidence-disabled")
    ) as runner:
        result = await runner.run()

    assert runner.export_evidence_ledgers() == ()
    assert result.evidence_ledgers == ()


@pytest.mark.asyncio
async def test_checkpoint_round_trip_preserves_evidence() -> None:
    config = _config(enabled=True)
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-evidence-checkpoint")
    ) as runner:
        await runner.run()
        checkpoint = runner.export_runtime_checkpoint()
        exported = runner.export_evidence_ledgers()

    assert len(exported) == 1
    assert checkpoint.runtime_states[0].evidence == exported[0]

    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-evidence-checkpoint")
    ) as restored:
        restored.apply_runtime_checkpoint(checkpoint)
        assert restored.export_evidence_ledgers() == exported


@pytest.mark.asyncio
async def test_checkpoint_rejects_wrong_owner() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-evidence-foreign")
    ) as runner:
        await runner.run()
        checkpoint = runner.export_runtime_checkpoint()

    state = checkpoint.runtime_states[0]
    with pytest.raises(EvidenceError):
        replace(state, evidence=EvidenceLedger(owner_id="other"))


@pytest.mark.asyncio
async def test_runner_exports_owner_ordered_ledgers() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-evidence-order")
    ) as runner:
        result = await runner.run()

    owners = [
        ledger.owner_id
        for ledger in result.evidence_ledgers
        if isinstance(ledger, EvidenceLedger)
    ]
    assert owners == sorted(owners)
    assert owners == [OWNER.value]


@pytest.mark.asyncio
async def test_worker_cannot_write_another_owner_ledger() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-evidence-worker")
    ) as runner:
        runtime = runner._runtimes[0]
        from simulation.agent_runtime import AgentRuntimeError

        with pytest.raises(AgentRuntimeError):
            runtime._commit_evidence(EvidenceLedger(owner_id="other"), 1)


def test_public_facades_export_evidence_contracts() -> None:
    import agents.cognition as cognition
    import simulation

    assert cognition.EvidenceLedger is EvidenceLedger
    assert cognition.empty_evidence_ledger is not None
    assert cognition.apply_evidence_update is not None
    assert cognition.record_evidence_utterance is not None
    assert cognition.evaluate_evidence is not None
    assert simulation.EvidenceLedger is EvidenceLedger
    assert simulation.empty_evidence_ledger is not None
    assert simulation.require_owner_evidence is not None
    assert (
        cognition.EVIDENCE_TESTIMONY_POLICY_VERSION
        == simulation.EVIDENCE_TESTIMONY_POLICY_VERSION
    )
