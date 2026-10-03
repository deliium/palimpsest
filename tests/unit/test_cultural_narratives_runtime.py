"""Disabled carry leaves the owner narrative ledger unset."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.configuration import (
    CognitionCulturalNarrativeMode,
    CognitionLoopConfig,
    build_cognitive_loop,
)
from agents.cognition.cultural_narratives import (
    empty_narrative_ledger,
    require_owner_cultural_narratives,
)
from agents.cognition.defaults import default_cognitive_loop
from agents.cognition.models import (
    CognitiveLoopInput,
    InternalAgentState,
    SubjectiveSnapshot,
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


def _snapshot(owner: AgentId, *, ledger: object | None = None, tick: int = 2):
    snapshot = SubjectiveSnapshot(
        owner_id=owner,
        revision=0,
        memories=(),
        legacy_beliefs=(),
        semantic_beliefs=(),
        social_identity=_north_identity(owner.value),
        cultural_narratives=ledger,
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
    assert "_cultural_narratives" in AgentRuntime.__slots__
    owner = AgentId("ada")
    assert (
        require_owner_cultural_narratives(None, owner, field_name="cultural_narratives")
        is None
    )
    ledger = empty_narrative_ledger(owner)
    assert (
        require_owner_cultural_narratives(
            ledger, owner, field_name="cultural_narratives"
        )
        is None
    )
    with pytest.raises(ValueError, match="owner_id mismatch"):
        require_owner_cultural_narratives(
            ledger, AgentId("ben"), field_name="cultural_narratives"
        )


@pytest.mark.asyncio
async def test_disabled_keeps_the_command_and_stores_no_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _owner()
    loop_input = _snapshot(owner)

    def _forbid_update(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("disabled mode called apply_narrative_update")

    monkeypatch.setattr(
        "agents.cognition.cultural_narratives.apply_narrative_update",
        _forbid_update,
    )
    from world.actions import Wait

    disabled = await default_cognitive_loop().run(
        loop_input, invocation_id="inv-narrative-off"
    )
    assert disabled.cultural_narratives is None
    assert type(disabled.command) is Wait
    assert SUBJECTIVE_SCHEMA_VERSION == "subjective-v1"


def test_runtime_commits_enabled_ledgers_and_clears_disabled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_RUNTIME_LOGGER)
    owner = AgentId("agent-1")
    enabled = _runtime(
        build_cognitive_loop(
            CognitionLoopConfig(
                cultural_narrative_mode=CognitionCulturalNarrativeMode.DETERMINISTIC
            )
        )
    )
    assert enabled._cultural_narratives is None
    ledger = empty_narrative_ledger(owner)
    enabled._commit_cultural_narratives(ledger, 4)
    assert enabled._cultural_narratives is ledger
    exported = enabled.export_runtime_checkpoint()
    assert exported.cultural_narratives is ledger

    restored = _runtime(default_cognitive_loop())
    restored.restore_runtime_checkpoint(exported)
    assert restored._cultural_narratives is ledger
    restored._commit_cultural_narratives(ledger, 5)
    assert restored._cultural_narratives is None
