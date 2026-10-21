"""Runtime preparation, perspective carry, and detached decay exports."""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType

import pytest

from agents.cognition.configuration import (
    CognitionInstitutionalDecayMode,
    CognitionInstitutionConceptMode,
    CognitionLoopConfig,
    build_cognitive_loop,
)
from agents.cognition.institution_concepts import empty_institution_concept_ledger
from agents.cognition.institutional_decay import (
    InstitutionDecayLedger,
    empty_institution_decay_ledger,
)
from agents.cognition.models import (
    CognitiveLoopInput,
    InternalAgentState,
    OwnerSafeSocialIdentity,
    SubjectiveSnapshot,
)
from agents.models import AgentId
from experiments.institutionalization_scenario import institutionalization_scenario
from simulation.bootstrap import AgentRegistration, RegistrationTranslator
from simulation.models import RunId
from simulation.perception import build_perspective
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V54,
    InstitutionalDecayMode,
    InstitutionalMemoryMode,
    InstitutionConceptMode,
    SimulationRunnerConfig,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.observations import Observation

_OWNER = AgentId("alice")


def _translator() -> RegistrationTranslator:
    entity_id = EntityId("alice-body")
    return RegistrationTranslator(
        _forward=MappingProxyType({_OWNER: entity_id}),
        _reverse=MappingProxyType({entity_id: _OWNER}),
        _order=(AgentRegistration(_OWNER, entity_id),),
    )


def _identity() -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(
        owner_id=_OWNER,
        owner_entity_id=EntityId("alice-body"),
    )


def _input(*, decay: object | None = None) -> CognitiveLoopInput:
    return CognitiveLoopInput(
        agent_id=_OWNER,
        observation=Observation(
            world_id=WorldId("world"),
            observer_id=EntityId("alice-body"),
            revision=WorldRevision(1),
            tick=2,
        ),
        internal_state=InternalAgentState(owner_id=_OWNER),
        snapshot=SubjectiveSnapshot(
            owner_id=_OWNER,
            revision=0,
            memories=(),
            legacy_beliefs=(),
            semantic_beliefs=(),
            social_identity=_identity(),
            institution_concepts=empty_institution_concept_ledger(_OWNER),
            institutional_decay=decay,
        ),
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


def test_disabled_loop_preparation_allocates_nothing() -> None:
    loop = build_cognitive_loop(CognitionLoopConfig())
    assert loop._institutional_decay_mode is (CognitionInstitutionalDecayMode.DISABLED)
    assert loop._prepared_institutional_decay is None
    assert (
        loop._prepare_institution_concepts(
            _input(),
            social_norms=None,
            social_conventions=None,
            group_formation=None,
            possession_legitimacy=None,
        )
        is None
    )
    assert loop._prepared_institutional_decay is None


def test_enabled_preparation_produces_paired_state() -> None:
    loop = build_cognitive_loop(
        CognitionLoopConfig(
            institution_concept_mode=CognitionInstitutionConceptMode.DETERMINISTIC,
            institutional_decay_mode=CognitionInstitutionalDecayMode.DETERMINISTIC,
        )
    )
    loop._prepare_institution_concepts(
        _input(decay=empty_institution_decay_ledger(_OWNER)),
        social_norms=None,
        social_conventions=None,
        group_formation=None,
        possession_legitimacy=None,
    )
    assert type(loop._prepared_institutional_decay) is InstitutionDecayLedger


def test_perspective_boundary_forwards_owner_ledger() -> None:
    ledger = empty_institution_decay_ledger(_OWNER)
    translator = _translator()
    perspective = build_perspective(
        agent_id=_OWNER,
        observation=Observation(
            world_id=WorldId("world"),
            observer_id=EntityId("alice-body"),
            revision=WorldRevision(1),
            tick=1,
        ),
        translator=translator,
        institution_concepts=empty_institution_concept_ledger(_OWNER),
        institutional_decay=ledger,
    )
    snapshot = perspective.to_snapshot()
    assert snapshot.institutional_decay is ledger


def test_perspective_rejects_foreign_owner_ledger() -> None:
    translator = _translator()
    with pytest.raises(ValueError, match="owner_id mismatch"):
        build_perspective(
            agent_id=_OWNER,
            observation=Observation(
                world_id=WorldId("world"),
                observer_id=EntityId("alice-body"),
                revision=WorldRevision(1),
                tick=1,
            ),
            translator=translator,
            institution_concepts=empty_institution_concept_ledger(_OWNER),
            institutional_decay=empty_institution_decay_ledger(AgentId("bob")),
        )


@pytest.mark.asyncio
async def test_actual_runtime_carries_and_exports_decay_state() -> None:
    config = _config()
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-decay-runtime")
    ) as runner:
        await runner.run()
        exported = runner.export_institutional_decay_ledgers()
        checkpoint = runner.export_runtime_checkpoint()

    assert exported
    assert all(type(ledger) is InstitutionDecayLedger for ledger in exported)
    assert any(
        isinstance(ledger, InstitutionDecayLedger) and ledger.samples
        for ledger in exported
    )
    assert all(
        getattr(ledger, "owner_id", None) == runtime.agent_id
        for runtime, ledger in zip(runner._runtimes, exported, strict=True)
        if getattr(runtime.export_runtime_checkpoint(), "institutional_decay", None)
        is not None
    )

    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-decay-runtime")
    ) as restored:
        restored.apply_runtime_checkpoint(checkpoint)
        assert restored.export_institutional_decay_ledgers() == exported
