"""Carry an owner group ledger without changing the selected command."""

from __future__ import annotations

import inspect
import logging
from dataclasses import replace

import pytest

from agents.cognition.configuration import (
    CognitionGroupFormationMode,
    CognitionLoopConfig,
    build_cognitive_loop,
)
from agents.cognition.defaults import default_cognitive_loop
from agents.cognition.group_formation import GroupLedger, empty_group_ledger
from agents.cognition.loop import CognitiveLoop
from agents.cognition.models import (
    CognitiveLoopInput,
    InternalAgentState,
    SubjectiveSnapshot,
)
from agents.models import Agent, AgentId
from memory.models import BeliefStore, MemoryStore
from simulation.agent_runtime import AgentRuntime
from simulation.bootstrap import registration_translator
from simulation.subjective_serialization import SUBJECTIVE_SCHEMA_VERSION
from tests.typecheck.cognitive_loop import (
    ScriptedIntentionSelector,
    ScriptedPlanner,
)
from tests.unit.test_agent_runtime import _bootstrap
from tests.unit.test_cognitive_loop import _loop
from tests.unit.test_group_formation import _body, _north_identity, _observe
from world.actions import Wait

_LOOP_LOGGER = "agents.cognition.loop"
_RUNTIME_LOGGER = "simulation.agent_runtime"


def _owner(value: str = "north_a") -> AgentId:
    return AgentId(value)


def _snapshot(
    owner: AgentId,
    *,
    ledger: object | None = None,
    tick: int = 2,
) -> tuple[CognitiveLoopInput, SubjectiveSnapshot]:
    snapshot = SubjectiveSnapshot(
        owner_id=owner,
        revision=0,
        memories=(),
        legacy_beliefs=(),
        semantic_beliefs=(),
        social_identity=_north_identity(owner.value),
        group_formation=ledger,
    )
    loop_input = CognitiveLoopInput(
        agent_id=owner,
        observation=_observe(
            tick=tick,
            owner_entity="body-a",
            bodies=(_body("body-b"),),
        ),
        internal_state=InternalAgentState(owner_id=owner),
        snapshot=snapshot,
    )
    return loop_input, snapshot


def _runtime(loop: object, owner: str = "agent-1") -> AgentRuntime:
    agent_id = AgentId(owner)
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


@pytest.mark.asyncio
async def test_disabled_keeps_the_command_and_stores_no_ledger(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOOP_LOGGER)
    owner = _owner()
    loop_input, _snapshot_value = _snapshot(owner)

    def _forbid_update(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("disabled mode called apply_group_update")

    monkeypatch.setattr(
        "agents.cognition.group_formation.apply_group_update",
        _forbid_update,
    )
    monkeypatch.setattr(
        "agents.cognition.reputation.apply_reputation_update",
        _forbid_update,
    )
    monkeypatch.setattr(
        "agents.cognition.territorial.apply_territorial_update",
        _forbid_update,
    )

    disabled = await default_cognitive_loop().run(
        loop_input, invocation_id="inv-group-off"
    )
    assert disabled.group_formation is None
    assert type(disabled.command) is Wait
    assert SUBJECTIVE_SCHEMA_VERSION == "subjective-v1"
    command_logs = [
        record.getMessage()
        for record in caplog.records
        if record.name == _LOOP_LOGGER
        and record.getMessage().startswith("group_command_unchanged")
    ]
    assert command_logs == [f"group_command_unchanged owner_id={owner.value} tick=2"]
    assert all("we" not in message for message in command_logs)
    assert all("our_group" not in message for message in command_logs)


@pytest.mark.asyncio
async def test_enabled_carry_does_not_change_the_command(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOOP_LOGGER)
    owner = _owner()
    loop_input, _snapshot_value = _snapshot(owner)
    disabled = await default_cognitive_loop().run(
        loop_input, invocation_id="inv-group-plain"
    )
    enabled_loop = build_cognitive_loop(
        CognitionLoopConfig(
            group_formation_mode=CognitionGroupFormationMode.DETERMINISTIC
        )
    )
    enabled = await enabled_loop.run(loop_input, invocation_id="inv-group-on")
    assert type(disabled.command) is Wait
    assert type(enabled.command) is Wait
    assert disabled.command == enabled.command
    assert type(enabled.group_formation) is GroupLedger
    assert enabled.group_formation.owner_id == owner
    assert enabled.group_formation.concepts == ()

    carried_input, _carried = _snapshot(
        owner, ledger=enabled.group_formation, tick=3
    )
    again = await enabled_loop.run(carried_input, invocation_id="inv-group-next")
    assert type(again.command) is Wait
    assert type(again.group_formation) is GroupLedger
    assert again.group_formation.beliefs
    assert all(
        "we" not in record.getMessage() and "our_group" not in record.getMessage()
        for record in caplog.records
        if record.name == _LOOP_LOGGER
        and record.getMessage().startswith("group_command_unchanged")
    )


@pytest.mark.asyncio
async def test_deliberation_does_not_receive_the_ledger() -> None:
    owner = _owner()
    loop_input, _snapshot_value = _snapshot(owner)
    intention = ScriptedIntentionSelector()
    planner = ScriptedPlanner()
    seen: dict[str, object] = {}

    def _accepted(method: object, kwargs: dict[str, object]) -> dict[str, object]:
        parameters = inspect.signature(method).parameters  # type: ignore[arg-type]
        return {key: value for key, value in kwargs.items() if key in parameters}

    class RecordingIntention(ScriptedIntentionSelector):
        async def select(self, *args: object, **kwargs: object) -> object:
            seen["intention"] = kwargs
            return await intention.select(
                *args,
                **_accepted(intention.select, kwargs),  # type: ignore[arg-type]
            )

    class RecordingPlanner(ScriptedPlanner):
        async def plan(self, *args: object, **kwargs: object) -> object:
            seen["planner"] = kwargs
            return await planner.plan(
                *args,
                **_accepted(planner.plan, kwargs),  # type: ignore[arg-type]
            )

    loop = _loop(
        intention=RecordingIntention(),
        planner=RecordingPlanner(),
        group_formation_mode=CognitionGroupFormationMode.DETERMINISTIC,
    )
    result = await loop.run(loop_input, invocation_id="inv-deliberate")
    assert type(result.group_formation) is GroupLedger
    assert "group_formation" not in seen["intention"]
    assert "group_formation" not in seen["planner"]
    assert type(loop) is CognitiveLoop


def test_runtime_commits_enabled_ledgers_and_clears_disabled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_RUNTIME_LOGGER)
    owner = AgentId("agent-1")
    enabled = _runtime(
        build_cognitive_loop(
            CognitionLoopConfig(
                group_formation_mode=CognitionGroupFormationMode.DETERMINISTIC
            )
        )
    )
    assert enabled._group_formation is None
    ledger = empty_group_ledger(owner)
    enabled._commit_group_formation(ledger, 4)
    assert enabled._group_formation is ledger
    exported = enabled.export_runtime_checkpoint()
    assert exported.group_formation is ledger

    restored = _runtime(default_cognitive_loop())
    restored.restore_runtime_checkpoint(exported)
    assert restored._group_formation is ledger
    restored._commit_group_formation(ledger, 5)
    assert restored._group_formation is None
    messages = [record.getMessage() for record in caplog.records]
    assert any(
        message.startswith(
            "group_ledger_carried owner_id=agent-1 tick=4 mode=deterministic "
            "belief_count=0 concept_count=0"
        )
        for message in messages
    )
    assert any(
        message.startswith(
            "group_ledger_skipped owner_id=agent-1 tick=5 mode=disabled "
            "belief_count=0 concept_count=0"
        )
        for message in messages
    )
    assert all("we" not in message for message in messages)


def test_foreign_ledger_is_rejected_on_snapshot_and_checkpoint() -> None:
    owner = _owner()
    foreign = empty_group_ledger(AgentId("north_b"))
    with pytest.raises(ValueError, match="owner_id mismatch"):
        _snapshot(owner, ledger=foreign)
    runtime = _runtime(default_cognitive_loop())
    exported = runtime.export_runtime_checkpoint()
    with pytest.raises(ValueError, match="owner_id mismatch"):
        replace(exported, group_formation=foreign)
