"""LLM reflection may only choose ids from the deterministic candidate set."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.configuration import CognitionReflectionMode
from agents.cognition.emotion import PassthroughEmotionalStateAppraiser
from agents.cognition.goal_manager import PassthroughGoalManager
from agents.cognition.loop import CognitiveLoop
from agents.cognition.models import (
    CognitiveLoopInput,
    InternalAgentState,
    SubjectiveSnapshot,
)
from agents.cognition.reflection import (
    LLMReflectionSelector,
    ReflectionContext,
    ReflectionPolicy,
    ReflectionSelectionOutput,
    ReflectionTriggerKind,
    ReflectionTriggerResult,
    materialize_reflection_candidates,
    plan_reflection,
)
from agents.models import AgentId
from tests.fakes import FakeLLMProvider, ScriptedSuccess
from tests.typecheck.cognitive_loop import (
    ScriptedFutureImagination,
    ScriptedIntentionSelector,
    ScriptedMemoryRetriever,
    ScriptedMemoryUpdateHook,
    ScriptedMotivationEvaluator,
    ScriptedPerceptionInterpreter,
    ScriptedPlanner,
    ScriptedSelfStateProjector,
    ScriptedSituationModeler,
)
from tests.unit.test_reflection_runtime import _help_trace
from world.actions import Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.observations import Observation

_REQUEST_ID = "reflection-4-agent-1"


def _provider(output: ReflectionSelectionOutput) -> FakeLLMProvider:
    provider = FakeLLMProvider()
    provider.enqueue(_REQUEST_ID, ScriptedSuccess(output=output))
    return provider


def _context() -> ReflectionContext:
    return ReflectionContext(
        owner_id=AgentId("agent-1"),
        tick=4,
        policy=ReflectionPolicy(
            interval_ticks=1,
            min_gap_ticks=1,
            min_pattern_count=3,
            allow_provider=True,
        ),
        memories=tuple(_help_trace(f"m-{index}") for index in range(3)),
        owner_entity_id=EntityId("agent-1"),
    )


def _triggers() -> ReflectionTriggerResult:
    return ReflectionTriggerResult(
        matched=(ReflectionTriggerKind.ELAPSED_TICKS,),
        skipped=(),
        gap_elapsed=True,
    )


def _loop(**overrides: object) -> CognitiveLoop:
    kwargs: dict[str, object] = {
        "perception": ScriptedPerceptionInterpreter(),
        "memory": ScriptedMemoryRetriever(),
        "situation": ScriptedSituationModeler(),
        "self_state": ScriptedSelfStateProjector(),
        "goal_manager": PassthroughGoalManager(),
        "emotional_state": PassthroughEmotionalStateAppraiser(),
        "futures": ScriptedFutureImagination(),
        "motivation": ScriptedMotivationEvaluator(),
        "intention": ScriptedIntentionSelector(),
        "planner": ScriptedPlanner(),
        "memory_updates": ScriptedMemoryUpdateHook(),
    }
    kwargs.update(overrides)
    return CognitiveLoop(**kwargs)  # type: ignore[arg-type]


def _input() -> CognitiveLoopInput:
    owner = AgentId("agent-1")
    return CognitiveLoopInput(
        agent_id=owner,
        observation=Observation(
            world_id=WorldId("world-1"),
            observer_id=EntityId("body-1"),
            revision=WorldRevision(0),
            tick=4,
        ),
        internal_state=InternalAgentState(owner_id=owner),
        snapshot=SubjectiveSnapshot(
            owner_id=owner,
            revision=0,
            memories=tuple(_help_trace(f"m-{index}") for index in range(3)),
            legacy_beliefs=(),
            semantic_beliefs=(),
        ),
    )


@pytest.mark.asyncio
async def test_legal_subset_changes_conclusions_without_new_ids(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.reflection")
    context = _context()
    candidates = materialize_reflection_candidates(context)
    belief = next(item for item in candidates if item.belief_request is not None)
    provider = _provider(ReflectionSelectionOutput(selected_ids=(belief.candidate_id,)))
    selected, fallback = await LLMReflectionSelector(provider).select(
        candidates,
        policy=context.policy,
        owner_id=context.owner_id,
        tick=context.tick,
    )
    plan = plan_reflection(
        context=context,
        triggers=_triggers(),
        mode="llm_assisted",
        selected_ids=selected,
        fallback_used=fallback,
    )
    assert len(provider.calls()) == 1
    assert fallback is False
    assert plan is not None
    assert plan.belief_revisions
    assert plan.relationship_revisions == ()
    assert plan.audit.fallback_used is False
    text = " ".join(record.getMessage() for record in caplog.records)
    assert "reflection_llm_start" in text
    assert "schema_version=reflection.selection.v1" in text
    assert "used_provider=True" in text
    assert "help_received" not in text


@pytest.mark.asyncio
async def test_foreign_id_falls_back_without_extra_writes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.reflection")
    context = _context()
    candidates = materialize_reflection_candidates(context)
    provider = _provider(ReflectionSelectionOutput(selected_ids=("not-a-candidate",)))
    selected, fallback = await LLMReflectionSelector(provider).select(
        candidates,
        policy=context.policy,
        owner_id=context.owner_id,
        tick=context.tick,
    )
    plan = plan_reflection(
        context=context,
        triggers=_triggers(),
        mode="llm_assisted",
        selected_ids=selected,
        fallback_used=fallback,
    )
    full = plan_reflection(context=context, triggers=_triggers(), mode="deterministic")
    assert fallback is True
    assert selected is None
    assert plan is not None and full is not None
    assert len(plan.belief_revisions) == len(full.belief_revisions)
    assert len(plan.relationship_revisions) == len(full.relationship_revisions)
    assert plan.audit.fallback_used is True
    text = " ".join(record.getMessage() for record in caplog.records)
    assert "reason_code=foreign_id" in text


@pytest.mark.asyncio
async def test_unbound_provider_falls_back_and_keeps_the_command(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.reflection")
    policy = ReflectionPolicy(interval_ticks=1, min_gap_ticks=1, allow_provider=True)
    counting = FakeLLMProvider()
    assisted = _loop(
        reflection_mode=CognitionReflectionMode.LLM_ASSISTED,
        reflection_policy=policy,
    )
    deterministic = _loop(
        reflection_mode=CognitionReflectionMode.DETERMINISTIC,
        reflection_policy=ReflectionPolicy(interval_ticks=1, min_gap_ticks=1),
        reflection_selector=LLMReflectionSelector(counting),
    )
    assisted_result = await assisted.complete(
        await assisted.prepare(_input(), invocation_id="inv-llm"),
        effective_command=Wait(),
    )
    deterministic_result = await deterministic.complete(
        await deterministic.prepare(_input(), invocation_id="inv-det"),
        effective_command=Wait(),
    )
    assert type(assisted_result.command) is type(deterministic_result.command)
    assert assisted_result.reflection is not None
    assert assisted_result.reflection.audit.fallback_used is True
    assert deterministic_result.reflection is not None
    assert deterministic_result.reflection.audit.fallback_used is False
    assert counting.calls() == ()
    text = " ".join(
        record.getMessage()
        for record in caplog.records
        if record.name == "agents.cognition.reflection"
    )
    assert "help_received" not in text
