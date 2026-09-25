"""Identity views bias hierarchical goals without changing the flag-off board."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.cognition.goal_manager import HierarchicalGoalManager
from agents.cognition.identity import (
    IDENTITY_POLICY_ID,
    IDENTITY_POLICY_VERSION,
    IdentityAspect,
    IdentityProvenanceKind,
    IdentityRevisionPoint,
    IdentityRevisionSummary,
    IdentityState,
    aggregate_identity_confidence,
    assemble_identity_belief_view,
    build_identity_claim,
    identity_predicate,
)
from agents.cognition.models import (
    CognitiveLoopInput,
    GoalTransitionIntentReason,
    InternalAgentState,
    RetrievedMemoryContext,
    SelfModel,
    SituationClaimCode,
    SituationModel,
    SubjectiveSnapshot,
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
from memory.beliefs import BeliefActivationState, BeliefValueKind, ClaimValue
from memory.models import BeliefId, MemoryId
from simulation.serialization import decode_domain, encode_domain
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import Observation, ObservedSelf
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)

_OWNER = AgentId("agent-1")


def _observation(*, thirst: float, tick: int = 3) -> Observation:
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=tick,
        self_body=ObservedSelf(
            entity_id=EntityId("body-1"),
            location_id=EntityId("loc-1"),
            health=Health(100.0),
            hunger=Hunger(0.0),
            thirst=Thirst(thirst),
            fatigue=Fatigue(0.0),
            temperature=TemperatureCelsius(36.5),
            inventory=(),
            life_status=LifeStatus.ALIVE,
            carry_capacity=CarryCapacity(10),
        ),
    )


def _goal(
    *,
    goal_id: str,
    horizon: GoalHorizon,
    outcome: GoalOutcome,
    status: GoalStatus = GoalStatus.ACTIVE,
    refs: tuple[str, ...] = (),
) -> Goal:
    return Goal(
        goal_id=GoalId(goal_id),
        owner_id=_OWNER,
        description="reach camp",
        priority=0.6,
        status=status,
        horizon=horizon,
        outcome=outcome,
        self_model_refs=refs,
        created_tick=1,
    )


def _explore(
    *, status: GoalStatus = GoalStatus.ACTIVE, refs: tuple[str, ...] = ()
) -> Goal:
    return _goal(
        goal_id="mt-explore",
        horizon=GoalHorizon.MEDIUM_TERM,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.GATHER_INFORMATION, outcome_code="map_area"
        ),
        status=status,
        refs=refs,
    )


def _reserve() -> Goal:
    return _goal(
        goal_id="lt-food-reserve",
        horizon=GoalHorizon.LONG_TERM,
        outcome=GoalOutcome(kind=GoalOutcomeKind.PRESERVE_LIFE),
    )


def _view(
    *,
    aspect: IdentityAspect,
    provenance: IdentityProvenanceKind,
    token: str,
    belief_id: str,
    confidence: float,
) -> object:
    predicate = identity_predicate(aspect, provenance, token)
    claim = build_identity_claim(
        _OWNER,
        predicate,
        ClaimValue(kind=BeliefValueKind.BOOL, bool_value=True),
    )
    return assemble_identity_belief_view(
        belief_id=BeliefId(belief_id),
        claim=claim,
        confidence=confidence,
        supporting_memory_ids=(MemoryId("mem-1"),),
        contradicting_memory_ids=(),
        activation=BeliefActivationState.CANDIDATE,
        revision_points=(
            IdentityRevisionPoint(
                ordinal=0, tick=1, confidence=confidence, contradicted=False
            ),
        ),
        revision_summaries=(
            IdentityRevisionSummary(
                ordinal=0, tick=1, activation=BeliefActivationState.CANDIDATE
            ),
        ),
    )


def _identity(*views: object) -> IdentityState:
    typed = tuple(views)
    return IdentityState(
        owner_id=_OWNER,
        policy_id=IDENTITY_POLICY_ID,
        policy_version=IDENTITY_POLICY_VERSION,
        views=typed,  # type: ignore[arg-type]
        aggregate_confidence=aggregate_identity_confidence(typed),  # type: ignore[arg-type]
    )


def _self_state(identity: IdentityState | None) -> SelfModel:
    return SelfModel(
        owner_id=_OWNER,
        policy_id="self-model-projection",
        policy_version="1",
        life_status=LifeStatus.ALIVE,
        beliefs=(),
        goal_ids=(),
        confidence=1.0,
        candidate_count=0,
        identity=identity,
    )


def _loop(*goals: Goal, thirst: float) -> CognitiveLoopInput:
    return CognitiveLoopInput(
        agent_id=_OWNER,
        observation=_observation(thirst=thirst),
        internal_state=InternalAgentState(owner_id=_OWNER),
        snapshot=SubjectiveSnapshot(
            owner_id=_OWNER,
            revision=1,
            memories=(),
            legacy_beliefs=(),
            semantic_beliefs=(),
            goals=goals,
        ),
    )


async def _manage(
    *goals: Goal, identity: IdentityState | None, thirst: float = 10.0
) -> object:
    return await HierarchicalGoalManager().manage(
        _loop(*goals, thirst=thirst),
        SituationModel(
            owner_id=_OWNER,
            tick=3,
            claim_codes=(SituationClaimCode.LOCAL_SCENE,),
            confidence=1.0,
        ),
        _self_state(identity),
        RetrievedMemoryContext(
            owner_id=_OWNER, memory_ids=(), belief_ids=(), confidence=1.0
        ),
    )


def _named(board: object, goal_id: str) -> Goal:
    from agents.cognition.models import GoalBoard

    if type(board) is not GoalBoard:
        raise TypeError("board")
    for goal in board.goals:
        if goal.goal_id.value == goal_id:
            return goal
    raise AssertionError(goal_id)


@pytest.mark.asyncio
async def test_weakness_suspends_medium_goal_without_critical_need() -> None:
    identity = _identity(
        _view(
            aspect=IdentityAspect.WEAKNESS,
            provenance=IdentityProvenanceKind.OBSERVED_OUTCOME,
            token="search",
            belief_id="belief-weak-search",
            confidence=0.8,
        )
    )
    board = await _manage(_explore(), _reserve(), identity=identity)
    assert _named(board, "mt-explore").status is GoalStatus.SUSPENDED
    assert _named(board, "lt-food-reserve").status is GoalStatus.ACTIVE
    assert "identity_weakness_suspend" in board.decision_metadata.selection_codes  # type: ignore[attr-defined]
    assert _named(board, "mt-explore").self_model_refs == ()


@pytest.mark.asyncio
async def test_competence_keeps_the_same_goal_and_copies_refs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.goal_manager")
    competence = _view(
        aspect=IdentityAspect.COMPETENCE,
        provenance=IdentityProvenanceKind.OBSERVED_OUTCOME,
        token="search",
        belief_id="belief-comp-search",
        confidence=0.8,
    )
    commitment = _view(
        aspect=IdentityAspect.COMMITMENT,
        provenance=IdentityProvenanceKind.GOAL_OUTCOME,
        token="mt-explore",
        belief_id="belief-commit-explore",
        confidence=0.7,
    )
    weakness = _view(
        aspect=IdentityAspect.WEAKNESS,
        provenance=IdentityProvenanceKind.OBSERVED_OUTCOME,
        token="search",
        belief_id="belief-weak-search",
        confidence=0.9,
    )
    identity = _identity(competence, commitment, weakness)
    board = await _manage(_explore(), identity=identity)
    kept = _named(board, "mt-explore")
    assert kept.status is GoalStatus.ACTIVE
    assert kept.self_model_refs == ("belief-comp-search", "belief-commit-explore")
    assert "belief-weak-search" not in kept.self_model_refs
    codes = board.decision_metadata.selection_codes  # type: ignore[attr-defined]
    assert "identity_competence_keep" in codes
    assert "identity_weakness_suspend" not in codes
    adopted = [
        intent
        for intent in board.transition_intents  # type: ignore[attr-defined]
        if intent.goal_id == kept.goal_id
        and intent.reason_code is GoalTransitionIntentReason.ADOPTED
    ]
    assert len(adopted) == 1
    assert adopted[0].resulting_goal is not None
    assert adopted[0].resulting_goal.self_model_refs == kept.self_model_refs
    records = [
        record for record in caplog.records if record.message == "identity_goal_bias"
    ]
    assert records
    payload = records[-1].__dict__
    assert payload["kept_count"] == 1
    assert payload["suspended_count"] == 0
    assert payload["ref_count"] == 2
    assert "reach camp" not in str(payload)


@pytest.mark.asyncio
async def test_below_floor_weakness_does_not_suspend() -> None:
    identity = _identity(
        _view(
            aspect=IdentityAspect.WEAKNESS,
            provenance=IdentityProvenanceKind.OBSERVED_OUTCOME,
            token="search",
            belief_id="belief-weak-search",
            confidence=0.4,
        )
    )
    board = await _manage(_explore(), identity=identity)
    assert _named(board, "mt-explore").status is GoalStatus.ACTIVE


@pytest.mark.asyncio
async def test_weakness_suspend_survives_the_next_noncritical_resume() -> None:
    identity = _identity(
        _view(
            aspect=IdentityAspect.WEAKNESS,
            provenance=IdentityProvenanceKind.OBSERVED_OUTCOME,
            token="search",
            belief_id="belief-weak-search",
            confidence=0.8,
        )
    )
    board = await _manage(
        _explore(status=GoalStatus.SUSPENDED), identity=identity, thirst=10.0
    )
    assert _named(board, "mt-explore").status is GoalStatus.SUSPENDED
    reasons = {
        intent.reason_code
        for intent in board.transition_intents  # type: ignore[attr-defined]
        if intent.goal_id.value == "mt-explore"
    }
    assert GoalTransitionIntentReason.RESUMED not in reasons


@pytest.mark.asyncio
async def test_critical_need_still_suspends_a_competent_medium_goal() -> None:
    identity = _identity(
        _view(
            aspect=IdentityAspect.COMPETENCE,
            provenance=IdentityProvenanceKind.OBSERVED_OUTCOME,
            token="search",
            belief_id="belief-comp-search",
            confidence=0.9,
        )
    )
    board = await _manage(_explore(), identity=identity, thirst=80.0)
    assert _named(board, "mt-explore").status is GoalStatus.SUSPENDED
    codes = board.decision_metadata.selection_codes  # type: ignore[attr-defined]
    assert "critical_need_suspend" in codes
    assert "identity_competence_keep" not in codes


@pytest.mark.asyncio
async def test_stale_ref_is_warned_and_dropped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="agents.cognition.goal_manager")
    identity = _identity(
        _view(
            aspect=IdentityAspect.COMPETENCE,
            provenance=IdentityProvenanceKind.OBSERVED_OUTCOME,
            token="search",
            belief_id="belief-comp-search",
            confidence=0.8,
        )
    )
    board = await _manage(
        _explore(refs=("missing-belief",)),
        identity=identity,
    )
    assert _named(board, "mt-explore").self_model_refs == ("belief-comp-search",)
    warnings = [
        record
        for record in caplog.records
        if record.message == "identity_goal_ref_rejected"
    ]
    assert warnings
    assert warnings[-1].reason_code == "belief_not_in_view"  # type: ignore[attr-defined]
    assert "reach camp" not in str(warnings[-1].__dict__)


def test_self_model_refs_round_trip_through_goal_codec() -> None:
    goal = replace(_explore(), self_model_refs=("belief-comp-search",))
    assert decode_domain(encode_domain(goal)) == goal
