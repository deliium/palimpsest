"""CognitiveLoop sequencing, replacement, and failure tests."""

from __future__ import annotations

import asyncio
import logging

import pytest

from agents.cognition.loop import (
    COMPONENT_VERSION,
    CognitiveLoop,
    CognitiveLoopError,
)
from agents.cognition.models import (
    ActionPlan,
    CognitionFailureReason,
    CognitiveLoopInput,
    ComponentKind,
    ComponentStatus,
    IntentionCode,
    InternalAgentState,
    InterpretedPerception,
    MotivationCode,
    MotivationEvaluation,
    MotivationScore,
    PerceptionClaimCode,
    PossibleFutures,
    RetrievedMemoryContext,
    SituationClaimCode,
    SituationModel,
    diagnostic_projection,
)
from agents.models import AgentId
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
from world.actions import Move, Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import Observation


def _loop_input(agent_id: str = "agent-1") -> CognitiveLoopInput:
    owner = AgentId(agent_id)
    return CognitiveLoopInput(
        agent_id=owner,
        observation=Observation(
            world_id=WorldId("world-1"),
            observer_id=EntityId("body-1"),
            revision=WorldRevision(0),
            tick=4,
        ),
        internal_state=InternalAgentState(owner_id=owner),
    )


def _loop(**overrides: object) -> CognitiveLoop:
    kwargs = {
        "perception": ScriptedPerceptionInterpreter(),
        "memory": ScriptedMemoryRetriever(),
        "situation": ScriptedSituationModeler(),
        "self_state": ScriptedSelfStateProjector(),
        "futures": ScriptedFutureImagination(),
        "motivation": ScriptedMotivationEvaluator(),
        "intention": ScriptedIntentionSelector(),
        "planner": ScriptedPlanner(),
        "memory_updates": ScriptedMemoryUpdateHook(),
    }
    kwargs.update(overrides)
    return CognitiveLoop(**kwargs)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_loop_runs_exact_stage_order_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls: list[str] = []

    class TrackingPerception(ScriptedPerceptionInterpreter):
        async def interpret(
            self, loop_input: CognitiveLoopInput
        ) -> InterpretedPerception:
            calls.append("perception")
            return await super().interpret(loop_input)

    class TrackingMemory(ScriptedMemoryRetriever):
        async def retrieve(self, loop_input, perception):  # type: ignore[no-untyped-def]
            calls.append("memory_retrieval")
            return await super().retrieve(loop_input, perception)

    class TrackingSituation(ScriptedSituationModeler):
        async def model(self, loop_input, perception, memory):  # type: ignore[no-untyped-def]
            calls.append("situation")
            return await super().model(loop_input, perception, memory)

    class TrackingSelf(ScriptedSelfStateProjector):
        async def project(self, loop_input, situation, memory):  # type: ignore[no-untyped-def]
            calls.append("self_state")
            return await super().project(loop_input, situation, memory)

    class TrackingFutures(ScriptedFutureImagination):
        async def imagine(self, loop_input, situation, self_state, memory):  # type: ignore[no-untyped-def]
            calls.append("futures")
            return await super().imagine(loop_input, situation, self_state, memory)

    class TrackingMotivation(ScriptedMotivationEvaluator):
        async def evaluate(self, loop_input, situation, self_state, futures):  # type: ignore[no-untyped-def]
            calls.append("motivation")
            return await super().evaluate(loop_input, situation, self_state, futures)

    class TrackingIntention(ScriptedIntentionSelector):
        async def select(self, loop_input, motivation, futures):  # type: ignore[no-untyped-def]
            calls.append("intention")
            return await super().select(loop_input, motivation, futures)

    class TrackingPlanner(ScriptedPlanner):
        async def plan(self, loop_input, intention, futures, memory=None):  # type: ignore[no-untyped-def]
            calls.append("planning")
            return await super().plan(loop_input, intention, futures)

    class TrackingUpdates(ScriptedMemoryUpdateHook):
        async def propose_updates(  # type: ignore[no-untyped-def]
            self, loop_input, plan, perception, memory, intention
        ):
            calls.append("memory_update")
            return await super().propose_updates(
                loop_input, plan, perception, memory, intention
            )

    caplog.set_level(logging.DEBUG, logger="agents.cognition.loop")
    result = await _loop(
        perception=TrackingPerception(),
        memory=TrackingMemory(),
        situation=TrackingSituation(),
        self_state=TrackingSelf(),
        futures=TrackingFutures(),
        motivation=TrackingMotivation(),
        intention=TrackingIntention(),
        planner=TrackingPlanner(),
        memory_updates=TrackingUpdates(),
    ).run(_loop_input(), invocation_id="inv-order")

    assert calls == [
        "perception",
        "memory_retrieval",
        "situation",
        "self_state",
        "futures",
        "motivation",
        "intention",
        "planning",
        "memory_update",
    ]
    assert type(result.command) is Wait
    assert len(result.boundary_records) == 9
    assert [r.component_kind for r in result.boundary_records] == [
        ComponentKind.PERCEPTION,
        ComponentKind.MEMORY_RETRIEVAL,
        ComponentKind.SITUATION,
        ComponentKind.SELF_STATE,
        ComponentKind.FUTURES,
        ComponentKind.MOTIVATION,
        ComponentKind.INTENTION,
        ComponentKind.PLANNING,
        ComponentKind.MEMORY_UPDATE,
    ]
    assert [r.ordinal for r in result.boundary_records] == list(range(9))
    assert all(
        r.component_version == COMPONENT_VERSION for r in result.boundary_records
    )
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "cognitive_stage_start" in messages
    assert "cognitive_loop_complete" in messages
    assert "Observation(" not in messages


@pytest.mark.asyncio
async def test_component_replacement_changes_command() -> None:
    class MovePlanner(ScriptedPlanner):
        async def plan(self, loop_input, intention, futures, memory=None):  # type: ignore[no-untyped-def]
            return ActionPlan(
                owner_id=loop_input.agent_id,
                command=Move(destination_id=EntityId("loc-2")),
                confidence=0.7,
            )

    result = await _loop(planner=MovePlanner()).run(
        _loop_input(), invocation_id="inv-move"
    )
    assert type(result.command) is Move
    assert result.final_confidence == 0.7
    assert result.internal_state.last_command_kind == "move"
    assert result.internal_state.last_intention is IntentionCode.WAIT


@pytest.mark.asyncio
async def test_wrong_output_type_short_circuits() -> None:
    class BadMemory(ScriptedMemoryRetriever):
        async def retrieve(self, loop_input, perception):  # type: ignore[no-untyped-def]
            return SituationModel(
                owner_id=loop_input.agent_id,
                tick=0,
                claim_codes=(SituationClaimCode.IDLE,),
                confidence=1.0,
            )

    with pytest.raises(CognitiveLoopError) as exc_info:
        await _loop(memory=BadMemory()).run(_loop_input(), invocation_id="inv-bad")
    failure = exc_info.value.failure
    assert failure.reason is CognitionFailureReason.TYPE_MISMATCH
    assert failure.component_kind is ComponentKind.MEMORY_RETRIEVAL
    assert failure.ordinal == 1
    assert len(failure.boundary_records) == 2
    assert failure.boundary_records[0].status is ComponentStatus.COMPLETED
    assert failure.boundary_records[1].status is ComponentStatus.FAILED


@pytest.mark.asyncio
async def test_component_exception_short_circuits() -> None:
    class BoomMotivation(ScriptedMotivationEvaluator):
        async def evaluate(self, loop_input, situation, self_state, futures):  # type: ignore[no-untyped-def]
            raise RuntimeError("secret motive payload")

    with pytest.raises(CognitiveLoopError) as exc_info:
        await _loop(motivation=BoomMotivation()).run(
            _loop_input(), invocation_id="inv-boom"
        )
    assert exc_info.value.failure.reason is CognitionFailureReason.COMPONENT_FAILED
    assert exc_info.value.failure.component_kind is ComponentKind.MOTIVATION
    assert "secret" not in str(exc_info.value)
    assert "secret" not in repr(exc_info.value.failure)


@pytest.mark.asyncio
async def test_cancellation_records_cancelled_boundary() -> None:
    class CancelIntention(ScriptedIntentionSelector):
        async def select(self, loop_input, motivation, futures):  # type: ignore[no-untyped-def]
            raise asyncio.CancelledError

    with pytest.raises(CognitiveLoopError) as exc_info:
        await _loop(intention=CancelIntention()).run(
            _loop_input(), invocation_id="inv-cancel"
        )
    failure = exc_info.value.failure
    assert failure.reason is CognitionFailureReason.CANCELLED
    assert failure.boundary_records[-1].status is ComponentStatus.CANCELLED


@pytest.mark.asyncio
async def test_ownership_mismatch_rejected() -> None:
    class ForeignPerception(ScriptedPerceptionInterpreter):
        async def interpret(
            self, loop_input: CognitiveLoopInput
        ) -> InterpretedPerception:
            return InterpretedPerception(
                owner_id=AgentId("other"),
                observer_id=loop_input.observation.observer_id,
                tick=loop_input.observation.tick,
                revision=loop_input.observation.revision,
                life_status=LifeStatus.ALIVE,
                location_id=None,
                claim_codes=(PerceptionClaimCode.SELF_PRESENT,),
                counts={},
                confidence=1.0,
            )

    with pytest.raises(CognitiveLoopError) as exc_info:
        await _loop(perception=ForeignPerception()).run(
            _loop_input(), invocation_id="inv-own"
        )
    assert exc_info.value.failure.reason is CognitionFailureReason.OWNERSHIP


@pytest.mark.asyncio
async def test_diagnostic_projection_omits_artifacts() -> None:
    result = await _loop().run(_loop_input(), invocation_id="inv-diag")
    text = str(dict(diagnostic_projection(result)))
    for record in result.boundary_records:
        text += str(dict(diagnostic_projection(record)))
    assert "Observation(" not in text
    assert "secret" not in text
    assert result.boundary_records[0].input_artifact is not None


@pytest.mark.asyncio
async def test_no_world_authority_in_result() -> None:
    result = await _loop().run(_loop_input(), invocation_id="inv-auth")
    assert not hasattr(result, "world_state")
    assert not hasattr(result, "tick_token")
    assert not hasattr(result, "action_submission")
    names = set(type(result).__dataclass_fields__)
    assert "command" in names
    assert "WorldState" not in repr(result)


@pytest.mark.asyncio
async def test_input_propagation_uses_prior_outputs() -> None:
    seen: dict[str, object] = {}

    class CaptureSituation(ScriptedSituationModeler):
        async def model(self, loop_input, perception, memory):  # type: ignore[no-untyped-def]
            seen["perception"] = perception
            seen["memory"] = memory
            return await super().model(loop_input, perception, memory)

    class CaptureMotivation(ScriptedMotivationEvaluator):
        async def evaluate(self, loop_input, situation, self_state, futures):  # type: ignore[no-untyped-def]
            seen["situation"] = situation
            seen["futures"] = futures
            return MotivationEvaluation(
                owner_id=loop_input.agent_id,
                scores=(MotivationScore(motive=MotivationCode.WAIT, score=1.0),),
                confidence=1.0,
            )

    await _loop(
        situation=CaptureSituation(),
        motivation=CaptureMotivation(),
    ).run(_loop_input(), invocation_id="inv-prop")
    assert type(seen["perception"]) is InterpretedPerception
    assert type(seen["memory"]) is RetrievedMemoryContext
    assert type(seen["situation"]) is SituationModel
    assert type(seen["futures"]) is PossibleFutures


@pytest.mark.asyncio
async def test_prepare_excludes_memory_update_and_complete_binds_effective() -> None:
    class TrackingHook:
        def __init__(self) -> None:
            self.commands: list[str] = []

        async def propose_updates(self, loop_input, plan, perception, memory, intention):
            self.commands.append(type(plan.command).__name__)
            return ()

    hook = TrackingHook()
    loop = _loop(memory_updates=hook)
    proposal = await loop.prepare(_loop_input(), invocation_id="inv-prep")
    assert type(proposal.proposed_command) is Wait
    assert all(
        record.component_kind is not ComponentKind.MEMORY_UPDATE
        for record in proposal.boundary_records
    )
    assert hook.commands == []

    result = await loop.complete(
        proposal, effective_command=Move(destination_id=EntityId("loc-2"))
    )
    assert type(result.command) is Move
    assert result.internal_state.last_command_kind == "move"
    assert hook.commands == ["Move"]
