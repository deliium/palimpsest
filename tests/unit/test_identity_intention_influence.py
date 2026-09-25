"""Identity adds one pairwise vote and never vetoes the last feasible future."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.cognition.deliberation import (
    CommandPlanner,
    MultiCriteriaIntentionSelector,
)
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
    ActionDirection,
    FutureAppraisal,
    GoalBoard,
    MotivationEvaluation,
    PossibleFutures,
    SelfModel,
)
from agents.models import (
    AgentId,
    DriveKind,
    Goal,
    GoalHorizon,
    GoalId,
    GoalOutcome,
    GoalStatus,
    GoalOutcomeKind,
)
from memory.beliefs import BeliefActivationState, BeliefValueKind, ClaimValue
from memory.models import BeliefId, MemoryId
from tests.unit.test_intention_selection import _appraisal, _future, _loop_input
from world.models import LifeStatus

_OWNER = AgentId("agent-1")


def _chain(confidence: float) -> tuple[IdentityRevisionPoint, ...]:
    ticks = (1, 3, 5, 9)
    return tuple(
        IdentityRevisionPoint(
            ordinal=index,
            tick=tick,
            confidence=confidence,
            contradicted=False,
        )
        for index, tick in enumerate(ticks)
    )


def _summaries() -> tuple[IdentityRevisionSummary, ...]:
    return tuple(
        IdentityRevisionSummary(
            ordinal=index, tick=tick, activation=BeliefActivationState.ACTIVE
        )
        for index, tick in enumerate((1, 3, 5, 9))
    )


def _commitment(*, confidence: float = 0.9) -> IdentityState:
    predicate = identity_predicate(
        IdentityAspect.COMMITMENT,
        IdentityProvenanceKind.GOAL_OUTCOME,
        "mt-explore",
    )
    claim = build_identity_claim(
        _OWNER,
        predicate,
        ClaimValue(kind=BeliefValueKind.BOOL, bool_value=True),
    )
    points = _chain(confidence)
    view = assemble_identity_belief_view(
        belief_id=BeliefId("belief-commit-explore"),
        claim=claim,
        confidence=confidence,
        supporting_memory_ids=(MemoryId("mem-1"), MemoryId("mem-2")),
        contradicting_memory_ids=(),
        activation=BeliefActivationState.ACTIVE,
        revision_points=points,
        revision_summaries=_summaries(),
    )
    return IdentityState(
        owner_id=_OWNER,
        policy_id=IDENTITY_POLICY_ID,
        policy_version=IDENTITY_POLICY_VERSION,
        views=(view,),
        aggregate_confidence=aggregate_identity_confidence((view,)),
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


def _board() -> GoalBoard:
    goal = Goal(
        goal_id=GoalId("mt-explore"),
        owner_id=_OWNER,
        description="reach camp",
        priority=0.6,
        status=GoalStatus.ACTIVE,
        horizon=GoalHorizon.MEDIUM_TERM,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.GATHER_INFORMATION, outcome_code="map_area"
        ),
        created_tick=1,
    )
    return GoalBoard(
        owner_id=_OWNER,
        tick=5,
        goals=(goal,),
        foci_ids=(),
        transition_intents=(),
        confidence=1.0,
        policy_version="goals.v1",
    )


def _evaluation(
    appraisals: tuple[FutureAppraisal, ...],
    futures: tuple[object, ...],
    *,
    drives: tuple[DriveKind, ...] = (),
) -> tuple[MotivationEvaluation, PossibleFutures]:
    imagined = tuple(futures)
    return (
        MotivationEvaluation(
            owner_id=_OWNER,
            scores=(),
            confidence=0.7,
            appraisals=appraisals,
            active_drive_kinds=drives,
        ),
        PossibleFutures(owner_id=_OWNER, futures=imagined, confidence=1.0),
    )


@pytest.mark.asyncio
async def test_commitment_vote_prefers_the_nonviolating_future(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.deliberation")
    search = _future("search", ActionDirection.SEARCH)
    flee = _future("flee", ActionDirection.FLEE)
    motivation, futures = _evaluation(
        (_appraisal(search), _appraisal(flee)), (search, flee)
    )
    absent = await MultiCriteriaIntentionSelector().select(
        _loop_input(),
        motivation,
        futures,
        _board(),
        None,
        _self_state(None),
    )
    present = await MultiCriteriaIntentionSelector().select(
        _loop_input(),
        motivation,
        futures,
        _board(),
        None,
        _self_state(_commitment()),
    )
    assert absent.direction is ActionDirection.FLEE
    assert present.direction is ActionDirection.SEARCH
    assert present.selected_future_id == "search"
    records = [
        record
        for record in caplog.records
        if record.message == "identity_violation_cost"
    ]
    assert len(records) == 1
    payload = records[0].__dict__
    assert payload["candidate_count"] == 2
    assert payload["winning_direction"] == "search"
    assert payload["identity_vote"] == 1
    assert payload["cost_band"] in {"low", "mid", "high"}
    assert "reach camp" not in str(payload)


@pytest.mark.asyncio
async def test_drive_votes_can_still_beat_the_commitment() -> None:
    search = _future("search", ActionDirection.SEARCH)
    flee = _future("flee", ActionDirection.FLEE, thirst_relief=0.4, safety=0.4)
    search_appraisal = replace(_appraisal(search), support_goal_count=1)
    motivation, futures = _evaluation(
        (search_appraisal, _appraisal(flee)),
        (search, flee),
        drives=(DriveKind.THIRST, DriveKind.SAFETY),
    )
    selected = await MultiCriteriaIntentionSelector().select(
        _loop_input(),
        motivation,
        futures,
        _board(),
        None,
        _self_state(_commitment()),
    )
    assert selected.direction is ActionDirection.FLEE


@pytest.mark.asyncio
async def test_critical_thirst_veto_overrides_commitment() -> None:
    search = _future("search", ActionDirection.SEARCH)
    drink = _future("drink", ActionDirection.DRINK, target="water-1")
    motivation, futures = _evaluation(
        (_appraisal(search), _appraisal(drink)), (search, drink)
    )
    selected = await MultiCriteriaIntentionSelector().select(
        _loop_input(thirst=90.0, with_water=True),
        motivation,
        futures,
        _board(),
        None,
        _self_state(_commitment()),
    )
    assert selected.direction is ActionDirection.DRINK


@pytest.mark.asyncio
async def test_identity_does_not_drop_the_only_feasible_future(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.deliberation")
    flee = _future("flee", ActionDirection.FLEE)
    motivation, futures = _evaluation((_appraisal(flee),), (flee,))
    selected = await MultiCriteriaIntentionSelector().select(
        _loop_input(),
        motivation,
        futures,
        _board(),
        None,
        _self_state(_commitment()),
    )
    assert selected.direction is ActionDirection.FLEE
    plan = await CommandPlanner().plan(_loop_input(), selected, futures)
    assert plan.decision_metadata.candidate_count == 1
    records = [
        record
        for record in caplog.records
        if record.message == "identity_violation_cost"
    ]
    assert records[-1].identity_vote == 0  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_owner_mismatch_is_rejected() -> None:
    other = AgentId("agent-2")
    identity = _commitment()
    foreign = IdentityState(
        owner_id=other,
        policy_id=IDENTITY_POLICY_ID,
        policy_version=IDENTITY_POLICY_VERSION,
        views=(),
        aggregate_confidence=0.0,
    )
    state = _self_state(identity)
    object.__setattr__(state, "identity", foreign)
    search = _future("search", ActionDirection.SEARCH)
    motivation, futures = _evaluation((_appraisal(search),), (search,))
    with pytest.raises(ValueError, match="owner_mismatch"):
        await MultiCriteriaIntentionSelector().select(
            _loop_input(),
            motivation,
            futures,
            _board(),
            None,
            state,
        )
