"""Runtime preparation, mixed owners, and deferred institutional state."""

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
from agents.cognition.models import (
    CognitiveLoopInput,
    InternalAgentState,
    OwnerSafeSocialIdentity,
    SubjectiveSnapshot,
)
from agents.models import AgentId
from experiments.institutionalization_scenario import institutionalization_scenario
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V53,
    InstitutionalMemoryMode,
    InstitutionConceptMode,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.observations import Observation

_OWNER = AgentId("alice")


def _identity() -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(
        owner_id=_OWNER,
        owner_entity_id=EntityId("alice-body"),
    )


def _input(*, institutional_memory: object | None = None) -> CognitiveLoopInput:
    return CognitiveLoopInput(
        agent_id=_OWNER,
        observation=Observation(
            world_id=WorldId("world"),
            observer_id=EntityId("alice-body"),
            revision=WorldRevision(1),
            tick=1,
        ),
        internal_state=InternalAgentState(owner_id=_OWNER),
        snapshot=SubjectiveSnapshot(
            owner_id=_OWNER,
            revision=0,
            memories=(),
            legacy_beliefs=(),
            semantic_beliefs=(),
            social_identity=_identity(),
            institutional_memory=institutional_memory,
        ),
    )


def _config(*, enabled: bool, mixed: bool = False):
    definition = institutionalization_scenario(seed=23, max_ticks=2)
    base = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bf-institution-on"
    )
    agents = []
    for index, agent in enumerate(base.agents):
        mode = (
            InstitutionalMemoryMode.DETERMINISTIC
            if enabled and (not mixed or index == 0)
            else InstitutionalMemoryMode.DISABLED
        )
        agents.append(
            replace(
                agent,
                cognition=replace(
                    agent.cognition,
                    institution_concept_mode=InstitutionConceptMode.DETERMINISTIC,
                    institutional_memory_mode=mode,
                ),
            )
        )
    return replace(base, schema_version=RUNNER_SCHEMA_VERSION_V53, agents=tuple(agents))


def test_disabled_preparation_allocates_nothing() -> None:
    loop = build_cognitive_loop(CognitionLoopConfig())
    assert loop._institutional_memory_mode is CognitionInstitutionalMemoryMode.DISABLED
    assert (
        loop._prepare_institutional_memory(
            _input(),
            office_concepts=None,
            institution_concepts=None,
            artifact_interpretations=None,
            retrieved_memory_context=None,
        )
        is None
    )


def test_enabled_preparation_increments_only_owner_window() -> None:
    loop = build_cognitive_loop(
        CognitionLoopConfig(
            institutional_memory_mode=CognitionInstitutionalMemoryMode.DETERMINISTIC
        )
    )
    prepared = loop._prepare_institutional_memory(
        _input(institutional_memory=empty_institutional_memory_ledger(_OWNER)),
        office_concepts=None,
        institution_concepts=None,
        artifact_interpretations=None,
        retrieved_memory_context=None,
    )
    assert type(prepared) is InstitutionalMemoryLedger
    assert prepared.owner_id == _OWNER
    assert prepared.observation_count == 1


def test_foreign_ledger_is_rejected_by_snapshot() -> None:
    with pytest.raises(ValueError, match="owner_id mismatch"):
        SubjectiveSnapshot(
            owner_id=_OWNER,
            revision=0,
            memories=(),
            legacy_beliefs=(),
            semantic_beliefs=(),
            institutional_memory=empty_institutional_memory_ledger(AgentId("bob")),
        )


@pytest.mark.asyncio
async def test_enabled_run_carries_empty_owner_ledgers() -> None:
    config = _config(enabled=True)
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-institutional-memory")
    ) as runner:
        await runner.run()
        ledgers = [runtime._institutional_memory for runtime in runner._runtimes]
    assert len(ledgers) == len(config.agents)
    assert all(type(ledger) is InstitutionalMemoryLedger for ledger in ledgers)
    assert [ledger.owner_id.value for ledger in ledgers] == [
        runtime.agent_id.value for runtime in runner._runtimes
    ]
    assert all(ledger.observation_count >= 1 for ledger in ledgers)


@pytest.mark.asyncio
async def test_mixed_owners_keep_disabled_runtime_state_none() -> None:
    config = _config(enabled=True, mixed=True)
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-institutional-memory-mixed")
    ) as runner:
        await runner.run()
        ledgers = [runtime._institutional_memory for runtime in runner._runtimes]
    assert type(ledgers[0]) is InstitutionalMemoryLedger
    assert all(ledger is None for ledger in ledgers[1:])
