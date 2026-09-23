"""Tests for cognition trace stage projection."""

from __future__ import annotations

from agents.cognition import (
    FORBIDDEN_TRACE_ATTRIBUTES,
    SCIENTIFIC_TRACE_STAGE_SEQUENCE,
    TOM_UNAVAILABLE_REASON,
    ActionPlan,
    CognitionTraceCountKey,
    CognitionTraceStageKind,
    CognitionTraceStageStatus,
    CognitiveLoopInput,
    CognitiveLoopResult,
    ComponentBoundaryRecord,
    ComponentKind,
    ComponentStatus,
    DecisionMetadata,
    IntentionCode,
    InternalAgentState,
    InterpretedPerception,
    MotivationCode,
    MotivationEvaluation,
    MotivationScore,
    PerceptionClaimCode,
    PossibleFutures,
    RetrievedMemoryContext,
    SelectedIntention,
    SituationClaimCode,
    SituationModel,
    SubjectiveSnapshot,
    project_cognition_trace_stages,
    stage_summaries_content_hash,
)
from agents.models import AgentId, Goal, GoalId, GoalStatus
from memory.models import BeliefId, MemoryId
from world.actions import Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import Observation


def _observation(*, tick: int = 0) -> Observation:
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=tick,
    )


def _perception(agent: AgentId) -> InterpretedPerception:
    return InterpretedPerception(
        owner_id=agent,
        observer_id=EntityId("body-1"),
        tick=0,
        revision=WorldRevision(0),
        life_status=LifeStatus.ALIVE,
        location_id=EntityId("loc-1"),
        claim_codes=(
            PerceptionClaimCode.SELF_PRESENT,
            PerceptionClaimCode.SELF_ALIVE,
        ),
        counts={"communications": 0, "visible_bodies": 1},
        confidence=0.9,
        decision_metadata=DecisionMetadata(selection_codes=("self_alive",)),
    )


def _record(
    *,
    kind: ComponentKind,
    ordinal: int,
    output: object,
    input_artifact: object | None = None,
    agent: AgentId | None = None,
) -> ComponentBoundaryRecord:
    owner = agent or AgentId("agent-1")
    return ComponentBoundaryRecord(
        invocation_id="inv-1",
        component_kind=kind,
        component_version="v1",
        ordinal=ordinal,
        status=ComponentStatus.COMPLETED,
        confidence=0.8,
        input_artifact=input_artifact
        if input_artifact is not None
        else CognitiveLoopInput(
            agent_id=owner,
            observation=_observation(),
            internal_state=InternalAgentState(owner_id=owner),
        ),
        output_artifact=output,
        decision_metadata=DecisionMetadata(),
    )


def test_project_full_scientific_sequence_and_tom_unavailable() -> None:
    agent = AgentId("agent-1")
    perception = _perception(agent)
    memory = RetrievedMemoryContext(
        owner_id=agent,
        memory_ids=(MemoryId("mem-1"),),
        belief_ids=(BeliefId("bel-1"),),
        confidence=0.7,
        candidate_count=1,
    )
    situation = SituationModel(
        owner_id=agent,
        tick=0,
        claim_codes=(SituationClaimCode.LOCAL_SCENE,),
        confidence=0.6,
    )
    futures = PossibleFutures(owner_id=agent, futures=(), confidence=0.5)
    motivation = MotivationEvaluation(
        owner_id=agent,
        scores=(MotivationScore(motive=MotivationCode.WAIT, score=0.4),),
        confidence=0.55,
        active_goal_ids=(GoalId("goal-1"),),
    )
    intention = SelectedIntention(
        owner_id=agent,
        intention=IntentionCode.WAIT,
        source_motive=MotivationCode.WAIT,
        confidence=0.7,
    )
    plan = ActionPlan(owner_id=agent, command=Wait(), confidence=0.85)
    records = (
        _record(
            kind=ComponentKind.PERCEPTION,
            ordinal=0,
            output=perception,
            input_artifact=_observation(),
        ),
        _record(kind=ComponentKind.MEMORY_RETRIEVAL, ordinal=1, output=memory),
        _record(kind=ComponentKind.SITUATION, ordinal=2, output=situation),
        _record(kind=ComponentKind.FUTURES, ordinal=3, output=futures),
        _record(kind=ComponentKind.MOTIVATION, ordinal=4, output=motivation),
        _record(kind=ComponentKind.INTENTION, ordinal=5, output=intention),
        _record(kind=ComponentKind.PLANNING, ordinal=6, output=plan),
    )
    snap = SubjectiveSnapshot(
        owner_id=agent,
        revision=0,
        memories=(),
        legacy_beliefs=(),
        semantic_beliefs=(),
        goals=(
            Goal(
                goal_id=GoalId("goal-1"),
                owner_id=agent,
                description="stay alive",
                priority=0.5,
                status=GoalStatus.ACTIVE,
            ),
        ),
    )
    stages = project_cognition_trace_stages(
        boundary_records=records,
        snapshot=snap,
        agent_id=agent.value,
        tick=0,
        invocation_id="inv-1",
    )
    assert len(stages) == len(SCIENTIFIC_TRACE_STAGE_SEQUENCE)
    assert (
        tuple(stage.stage_kind for stage in stages) == SCIENTIFIC_TRACE_STAGE_SEQUENCE
    )
    tom = stages[8]
    assert tom.stage_kind is CognitionTraceStageKind.THEORY_OF_MIND
    assert tom.status is CognitionTraceStageStatus.UNAVAILABLE
    assert tom.reason_code == TOM_UNAVAILABLE_REASON
    planned = stages[10]
    assert planned.command_kind == "wait"
    assert planned.confidence == 0.85
    retrieved = stages[1]
    assert retrieved.counts is not None
    assert retrieved.counts[CognitionTraceCountKey.MEMORY_HIT_COUNT.value] == 0
    assert any(ref.value == "mem-1" for ref in retrieved.id_refs)


def test_project_from_loop_result_hash_stable() -> None:
    agent = AgentId("agent-1")
    perception = _perception(agent)
    plan = ActionPlan(owner_id=agent, command=Wait(), confidence=1.0)
    records = (
        _record(
            kind=ComponentKind.PERCEPTION,
            ordinal=0,
            output=perception,
            input_artifact=_observation(),
        ),
        _record(kind=ComponentKind.PLANNING, ordinal=1, output=plan),
    )
    result = CognitiveLoopResult(
        invocation_id="inv-1",
        agent_id=agent,
        command=Wait(),
        boundary_records=records,
        memory_update_intents=(),
        final_confidence=1.0,
        internal_state=InternalAgentState(owner_id=agent, invocation_count=1),
    )
    a = project_cognition_trace_stages(loop_result=result)
    b = project_cognition_trace_stages(loop_result=result)
    assert stage_summaries_content_hash(a) == stage_summaries_content_hash(b)
    assert a[0].stage_kind is CognitionTraceStageKind.OBSERVATION
    assert a[-1].command_kind == "wait"


def test_projected_summaries_forbid_payload_fields() -> None:
    agent = AgentId("agent-1")
    stages = project_cognition_trace_stages(
        boundary_records=(
            _record(
                kind=ComponentKind.PERCEPTION,
                ordinal=0,
                output=_perception(agent),
                input_artifact=_observation(),
            ),
        ),
        agent_id=agent.value,
    )
    joined = "\n".join(repr(stage) for stage in stages)
    for token in FORBIDDEN_TRACE_ATTRIBUTES:
        assert token not in joined
    assert "Observation(" not in joined
    assert "stay alive" not in joined
    assert not any(hasattr(stage, "run_id") for stage in stages)
    assert not any(hasattr(stage, "latency_ms") for stage in stages)
