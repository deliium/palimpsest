"""Disabled carry leaves the owner terminology ledger unset."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.cognition.configuration import (
    CognitionLoopConfig,
    CognitionSemanticNamingMode,
    build_cognitive_loop,
)
from agents.cognition.defaults import default_cognitive_loop
from agents.cognition.models import (
    CognitiveLoopInput,
    InternalAgentState,
    SubjectiveSnapshot,
)
from agents.cognition.semantic_naming import (
    empty_terminology_ledger,
    require_owner_semantic_naming,
)
from agents.models import Agent, AgentId
from simulation.agent_runtime import AgentRuntime
from simulation.bootstrap import registration_translator
from simulation.subjective_serialization import SUBJECTIVE_SCHEMA_VERSION
from tests.unit.test_agent_runtime import _bootstrap
from tests.unit.test_group_formation import _body, _north_identity, _observe

_LOOP_LOGGER = "agents.cognition.loop"
_RUNTIME_LOGGER = "simulation.agent_runtime"


def _owner(value: str = "north_a") -> AgentId:
    return AgentId(value)


def _snapshot(
    owner: AgentId,
    *,
    ledger: object | None = None,
    tick: int = 2,
) -> CognitiveLoopInput:
    snapshot = SubjectiveSnapshot(
        owner_id=owner,
        revision=0,
        memories=(),
        legacy_beliefs=(),
        semantic_beliefs=(),
        social_identity=_north_identity(owner.value),
        semantic_naming=ledger,
    )
    return CognitiveLoopInput(
        agent_id=owner,
        observation=_observe(
            tick=tick,
            owner_entity="body-a",
            bodies=(_body("body-b"),),
        ),
        internal_state=InternalAgentState(owner_id=owner),
        snapshot=snapshot,
    )


def _runtime(loop: object, owner: str = "agent-1") -> AgentRuntime:
    agent_id = AgentId(owner)
    from memory.models import BeliefStore, MemoryStore

    memories = MemoryStore(agent_id)
    beliefs = BeliefStore(agent_id)
    return AgentRuntime(
        agent=Agent(agent_id=agent_id, name=owner, goals=()),
        translator=registration_translator(_bootstrap()),
        cognitive_loop=loop,  # type: ignore[arg-type]
        memory_reader=memories,
        memory_writer=memories,
        belief_reader=beliefs,
        belief_writer=beliefs,
    )


def test_runtime_slot_defaults_absent_and_owner_check_is_closed() -> None:
    assert "_semantic_naming" in AgentRuntime.__slots__
    owner = AgentId("ada")
    assert (
        require_owner_semantic_naming(None, owner, field_name="semantic_naming")
        is None
    )
    ledger = empty_terminology_ledger(owner)
    assert (
        require_owner_semantic_naming(ledger, owner, field_name="semantic_naming")
        is None
    )
    with pytest.raises(ValueError, match="owner_id mismatch"):
        require_owner_semantic_naming(
            ledger, AgentId("ben"), field_name="semantic_naming"
        )


@pytest.mark.asyncio
async def test_disabled_keeps_the_command_and_stores_no_ledger(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOOP_LOGGER)
    owner = _owner()
    loop_input = _snapshot(owner)

    def _forbid_update(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("disabled mode called apply_naming_update")

    monkeypatch.setattr(
        "agents.cognition.semantic_naming.apply_naming_update",
        _forbid_update,
    )

    from agents.cognition.models import MemoryUpdateKind
    from world.actions import Wait

    disabled = await default_cognitive_loop().run(
        loop_input, invocation_id="inv-naming-off"
    )
    assert disabled.semantic_naming is None
    assert type(disabled.command) is Wait
    assert SUBJECTIVE_SCHEMA_VERSION == "subjective-v1"
    assert all(
        intent.kind is not MemoryUpdateKind.REVISE_RELATIONSHIP
        for intent in disabled.memory_update_intents
    )
    assert not any(
        record.getMessage().startswith("naming_penalty_applied")
        for record in caplog.records
        if record.name == _LOOP_LOGGER
    )


def test_runtime_commits_enabled_ledgers_and_clears_disabled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_RUNTIME_LOGGER)
    owner = AgentId("agent-1")
    enabled = _runtime(
        build_cognitive_loop(
            CognitionLoopConfig(
                semantic_naming_mode=CognitionSemanticNamingMode.DETERMINISTIC
            )
        )
    )
    assert enabled._semantic_naming is None
    ledger = empty_terminology_ledger(owner)
    enabled._commit_semantic_naming(ledger, 4)
    assert enabled._semantic_naming is ledger
    exported = enabled.export_runtime_checkpoint()
    assert exported.semantic_naming is ledger

    restored = _runtime(default_cognitive_loop())
    restored.restore_runtime_checkpoint(exported)
    assert restored._semantic_naming is ledger
    restored._commit_semantic_naming(ledger, 5)
    assert restored._semantic_naming is None
    messages = [record.getMessage() for record in caplog.records]
    assert any(
        message.startswith(
            "semantic_naming_carried owner_id=agent-1 binding_count=0 tick=4"
        )
        for message in messages
    )


def test_foreign_ledger_is_rejected_on_snapshot_and_checkpoint() -> None:
    owner = _owner()
    foreign = empty_terminology_ledger(AgentId("north_b"))
    with pytest.raises(ValueError, match="owner_id mismatch"):
        _snapshot(owner, ledger=foreign)
    runtime = _runtime(default_cognitive_loop())
    exported = runtime.export_runtime_checkpoint()
    with pytest.raises(ValueError, match="owner_id mismatch"):
        replace(exported, semantic_naming=foreign)
