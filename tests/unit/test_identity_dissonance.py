"""Conflicting actions add contradiction without changing the command."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.configuration import CognitionIdentityMode
from agents.cognition.emotion import PassthroughEmotionalStateAppraiser
from agents.cognition.goal_manager import PassthroughGoalManager
from agents.cognition.identity import (
    IDENTITY_POLICY_ID,
    IDENTITY_POLICY_VERSION,
    IdentityAspect,
    IdentityConflictCode,
    IdentityProvenanceKind,
    IdentityRevisionPoint,
    IdentityRevisionSummary,
    IdentityState,
    assemble_identity_belief_view,
    build_identity_claim,
    detect_identity_dissonance,
    identity_predicate,
)
from agents.cognition.loop import CognitiveLoop
from agents.cognition.models import (
    ActionDirection,
    CognitiveLoopInput,
    DecisionMetadata,
    ImaginedFuture,
    PossibleFutures,
    SelfModel,
    SituationClaimCode,
    SubjectiveRisk,
    SubjectiveRiskKind,
    SubjectiveSnapshot,
    project_identity_state,
)
from agents.models import (
    AgentId,
    Goal,
    GoalHorizon,
    GoalId,
    GoalOutcome,
    GoalOutcomeKind,
    GoalStatus,
)
from memory.belief_formation import belief_id_for_claim
from memory.belief_service import InMemorySemanticBeliefService
from memory.beliefs import (
    BeliefActivationState,
    BeliefEvidenceBundle,
    BeliefEvidenceContribution,
    BeliefRevisionRequest,
    BeliefValueKind,
    ClaimValue,
    EvidenceStance,
)
from memory.models import MemoryId, MemoryRunId, MemoryScope
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
from tests.unit.test_identity_runtime import _loop_input, _memory, _observation
from world.actions import Move, Wait
from world.identifiers import EntityId


def _claim(owner: AgentId, aspect: IdentityAspect, token: str):
    return build_identity_claim(
        owner,
        identity_predicate(aspect, IdentityProvenanceKind.GOAL_OUTCOME, token),
        ClaimValue(kind=BeliefValueKind.BOOL, bool_value=True),
    )


def _view(
    owner: AgentId,
    aspect: IdentityAspect,
    token: str,
    *,
    provenance: IdentityProvenanceKind = IdentityProvenanceKind.GOAL_OUTCOME,
    confidence: float = 0.8,
    support: tuple[str, ...] = ("mem-move",),
    contradict: tuple[str, ...] = (),
):
    claim = build_identity_claim(
        owner,
        identity_predicate(aspect, provenance, token),
        ClaimValue(kind=BeliefValueKind.BOOL, bool_value=True),
    )
    points = (
        IdentityRevisionPoint(
            ordinal=0, tick=1, confidence=confidence, contradicted=False
        ),
    )
    summaries = (
        IdentityRevisionSummary(
            ordinal=0, tick=1, activation=BeliefActivationState.CANDIDATE
        ),
    )
    return assemble_identity_belief_view(
        belief_id=belief_id_for_claim(owner_id=owner, claim=claim),
        claim=claim,
        confidence=confidence,
        supporting_memory_ids=tuple(MemoryId(item) for item in support),
        contradicting_memory_ids=tuple(MemoryId(item) for item in contradict),
        activation=BeliefActivationState.CANDIDATE,
        revision_points=points,
        revision_summaries=summaries,
    )


def _identity(owner: AgentId, *views) -> IdentityState:
    return IdentityState(
        owner_id=owner,
        policy_id=IDENTITY_POLICY_ID,
        policy_version=IDENTITY_POLICY_VERSION,
        views=views,
        aggregate_confidence=0.8,
    )


def _goal(owner: AgentId) -> Goal:
    return Goal(
        goal_id=GoalId("goal-reach"),
        owner_id=owner,
        description="reach camp",
        priority=0.5,
        status=GoalStatus.ACTIVE,
        horizon=GoalHorizon.LONG_TERM,
        outcome=GoalOutcome(kind=GoalOutcomeKind.REACH_PLACE, place_id="loc-1"),
    )


def _memory_trace(owner: AgentId):
    return _memory(owner)


def test_commitment_conflict_keeps_bool_claim(caplog: pytest.LogCaptureFixture) -> None:
    owner = AgentId("agent-1")
    view = _view(owner, IdentityAspect.COMMITMENT, "goal-reach")
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.identity"):
        result = detect_identity_dissonance(
            owner_id=owner,
            tick=4,
            command=Wait(),
            goals=(_goal(owner),),
            futures=None,
            identity=_identity(owner, view),
            memories=(_memory_trace(owner),),
        )
    assert result.notices
    assert result.notices[0].conflict_code is IdentityConflictCode.COMMITMENT_COMMAND
    assert result.requests
    request = result.requests[0]
    assert request.claim.value.bool_value is True
    assert request.evidence.contradicting
    assert request.evidence.supporting == ()
    records = [item for item in caplog.records if item.message == "identity_dissonance"]
    assert records
    rendered = str(records[-1].__dict__)
    assert "goal-reach" not in rendered
    assert "reach camp" not in rendered


def test_matching_commitment_adds_no_notice() -> None:
    owner = AgentId("agent-1")
    view = _view(owner, IdentityAspect.COMMITMENT, "goal-reach")
    result = detect_identity_dissonance(
        owner_id=owner,
        tick=4,
        command=Move(destination_id=EntityId("loc-2")),
        goals=(_goal(owner),),
        futures=None,
        identity=_identity(owner, view),
        memories=(_memory_trace(owner),),
    )
    assert result.notices == ()
    assert result.requests == ()


def test_inferred_value_needs_another_future() -> None:
    owner = AgentId("agent-1")
    view = _view(
        owner,
        IdentityAspect.INFERRED_VALUE,
        "move",
        provenance=IdentityProvenanceKind.OWN_CHOICE,
    )
    futures = PossibleFutures(
        owner_id=owner,
        futures=(
            ImaginedFuture(
                future_id="future-move",
                claim_codes=(SituationClaimCode.IDLE,),
                confidence=0.6,
                direction=ActionDirection.MOVE,
            ),
        ),
        confidence=0.6,
        decision_metadata=DecisionMetadata(candidate_count=1),
    )
    conflict = detect_identity_dissonance(
        owner_id=owner,
        tick=4,
        command=Wait(),
        goals=(),
        futures=futures,
        identity=_identity(owner, view),
        memories=(_memory_trace(owner),),
    )
    assert conflict.notices[0].conflict_code is (
        IdentityConflictCode.INFERRED_VALUE_COMMAND
    )
    quiet = detect_identity_dissonance(
        owner_id=owner,
        tick=4,
        command=Wait(),
        goals=(),
        futures=None,
        identity=_identity(owner, view),
        memories=(_memory_trace(owner),),
    )
    assert quiet.notices == ()


def test_risk_above_minimum_harm() -> None:
    owner = AgentId("agent-1")
    view = _view(
        owner,
        IdentityAspect.RISK_TOLERANCE,
        "move",
        provenance=IdentityProvenanceKind.OWN_CHOICE,
        support=("mem-s",),
        contradict=("mem-c1", "mem-c2"),
    )
    futures = PossibleFutures(
        owner_id=owner,
        futures=(
            ImaginedFuture(
                future_id="future-wait",
                claim_codes=(SituationClaimCode.IDLE,),
                confidence=0.5,
                direction=ActionDirection.WAIT,
            ),
            ImaginedFuture(
                future_id="future-move",
                claim_codes=(SituationClaimCode.THREAT_SIGNAL,),
                confidence=0.5,
                direction=ActionDirection.MOVE,
                risks=(
                    SubjectiveRisk(
                        kind=SubjectiveRiskKind.PHYSICAL_HARM,
                        severity=0.8,
                        likelihood=1.0,
                        confidence=1.0,
                    ),
                ),
            ),
        ),
        confidence=0.5,
        decision_metadata=DecisionMetadata(candidate_count=2),
    )
    result = detect_identity_dissonance(
        owner_id=owner,
        tick=4,
        command=Move(destination_id=EntityId("loc-2")),
        goals=(),
        futures=futures,
        identity=_identity(owner, view),
        memories=(_memory_trace(owner),),
        selected_future_id="future-move",
    )
    assert result.notices[0].conflict_code is IdentityConflictCode.RISK_ABOVE_TOLERANCE


def test_missing_memory_defers_until_a_later_tick(
    caplog: pytest.LogCaptureFixture,
) -> None:
    owner = AgentId("agent-1")
    view = _view(owner, IdentityAspect.COMMITMENT, "goal-reach")
    identity = _identity(owner, view)
    with caplog.at_level(logging.WARNING, logger="agents.cognition.identity"):
        deferred = detect_identity_dissonance(
            owner_id=owner,
            tick=4,
            command=Wait(),
            goals=(_goal(owner),),
            futures=None,
            identity=identity,
            memories=(),
        )
    assert deferred.notices == ()
    assert deferred.requests == ()
    assert deferred.deferred
    assert any(
        record.message == "identity_dissonance_deferred" for record in caplog.records
    )
    later = detect_identity_dissonance(
        owner_id=owner,
        tick=5,
        command=Move(destination_id=EntityId("loc-2")),
        goals=(_goal(owner),),
        futures=None,
        identity=identity,
        memories=(_memory_trace(owner),),
        deferred=deferred.deferred,
    )
    assert later.notices
    assert later.requests
    assert later.deferred == ()
    assert later.requests[0].evidence.contradicting[0].stance is (
        EvidenceStance.CONTRADICTING
    )


@pytest.mark.asyncio
async def test_contradiction_lowers_stability() -> None:
    owner = AgentId("agent-1")
    claim = _claim(owner, IdentityAspect.COMMITMENT, "goal-reach")
    scope = MemoryScope(run_id=MemoryRunId("run-dissonance"), owner_id=owner)

    async def history(*, contradict: bool):
        service = InMemorySemanticBeliefService(scope)
        belief_id = belief_id_for_claim(owner_id=owner, claim=claim)
        first = BeliefRevisionRequest(
            owner_id=owner,
            operation_id="identity-support-1",
            logical_tick=1,
            claim=claim,
            evidence=_bundle("mem-1", contradicting=False),
            policy=service.policy.as_ref(),
            belief_id=belief_id,
        )
        second = BeliefRevisionRequest(
            owner_id=owner,
            operation_id=(
                "identity-support-2" if not contradict else "identity-contra-2"
            ),
            logical_tick=4,
            claim=claim,
            evidence=_bundle("mem-2", contradicting=contradict),
            policy=service.policy.as_ref(),
            belief_id=belief_id,
            expected_revision_ordinal=0,
        )
        await service.revise(first)
        await service.revise(second)
        return service.history_sync(belief_id)

    calm_history = await history(contradict=False)
    clash_history = await history(contradict=True)
    calm = project_identity_state(owner_id=owner, histories=(calm_history,))
    clash = project_identity_state(owner_id=owner, histories=(clash_history,))
    assert clash.views[0].derived_stability < calm.views[0].derived_stability
    assert len(clash.views[0].contradicting_memory_ids) > len(
        calm.views[0].contradicting_memory_ids
    )


def _bundle(memory_id: str, *, contradicting: bool) -> BeliefEvidenceBundle:
    stance = (
        EvidenceStance.CONTRADICTING if contradicting else EvidenceStance.SUPPORTING
    )
    return BeliefEvidenceBundle(
        supporting=()
        if contradicting
        else (
            BeliefEvidenceContribution(
                memory_id=MemoryId(memory_id),
                stance=stance,
                contribution=0.5,
                ordinal=0,
                lineage_root_id=MemoryId(memory_id),
            ),
        ),
        contradicting=(
            ()
            if not contradicting
            else (
                BeliefEvidenceContribution(
                    memory_id=MemoryId(memory_id),
                    stance=stance,
                    contribution=0.5,
                    ordinal=0,
                    lineage_root_id=MemoryId(memory_id),
                ),
            )
        ),
    )


class _IdentityProjector(ScriptedSelfStateProjector):
    def __init__(self, model: SelfModel) -> None:
        self._model = model

    async def project(self, loop_input, situation, memory):  # type: ignore[no-untyped-def]
        _ = loop_input, situation, memory
        return self._model


def _model(owner: AgentId) -> SelfModel:
    return SelfModel(
        owner_id=owner,
        policy_id="self-model-projection",
        policy_version="1",
        life_status=None,
        beliefs=(),
        goal_ids=(),
        confidence=1.0,
        candidate_count=0,
        identity=_identity(
            owner, _view(owner, IdentityAspect.COMMITMENT, "goal-reach")
        ),
    )


@pytest.mark.asyncio
async def test_loop_keeps_conflicting_command_and_passthrough_is_empty() -> None:
    owner = AgentId("agent-1")
    goal = _goal(owner)
    observation = _observation()
    base = _loop_input(owner)
    loop_input = CognitiveLoopInput(
        agent_id=owner,
        observation=observation,
        internal_state=base.internal_state,
        snapshot=SubjectiveSnapshot(
            owner_id=owner,
            revision=0,
            memories=base.snapshot.memories,  # type: ignore[union-attr]
            legacy_beliefs=(),
            semantic_beliefs=(),
            goals=(goal,),
        ),
    )

    def loop(mode: CognitionIdentityMode) -> CognitiveLoop:
        return CognitiveLoop(
            perception=ScriptedPerceptionInterpreter(),
            memory=ScriptedMemoryRetriever(),
            situation=ScriptedSituationModeler(),
            self_state=(
                _IdentityProjector(_model(owner))
                if mode is CognitionIdentityMode.ENABLED
                else ScriptedSelfStateProjector()
            ),
            goal_manager=PassthroughGoalManager(),
            emotional_state=PassthroughEmotionalStateAppraiser(),
            futures=ScriptedFutureImagination(),
            motivation=ScriptedMotivationEvaluator(),
            intention=ScriptedIntentionSelector(),
            planner=ScriptedPlanner(),
            memory_updates=ScriptedMemoryUpdateHook(),
            identity_mode=mode,
        )

    enabled = loop(CognitionIdentityMode.ENABLED)
    proposal = await enabled.prepare(loop_input, invocation_id="inv-dissonance")
    result = await enabled.complete(proposal, effective_command=Wait())
    assert type(result.command) is Wait
    assert result.identity_dissonance
    assert result.identity_dissonance[0].conflict_code is (
        IdentityConflictCode.COMMITMENT_COMMAND
    )

    quiet = loop(CognitionIdentityMode.PASSTHROUGH)
    quiet_proposal = await quiet.prepare(loop_input, invocation_id="inv-quiet")
    quiet_result = await quiet.complete(quiet_proposal, effective_command=Wait())
    assert quiet_result.identity_dissonance == ()
