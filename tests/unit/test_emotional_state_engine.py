"""Unit tests for deterministic ``emotion.v1`` EmotionalStateEngine."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.emotion import (
    EMOTION_POLICY_VERSION,
    EmotionalStateEngine,
    PassthroughEmotionalStateAppraiser,
)
from agents.cognition.models import (
    AgentEmotionalState,
    CognitiveLoopInput,
    EmotionDriverCode,
    EmotionIntensity,
    EmotionKind,
    GoalBoard,
    GoalTransitionIntent,
    GoalTransitionIntentReason,
    InternalAgentState,
    InterpretedPerception,
    PerceptionClaimCode,
    RetrievedMemoryContext,
    SelfModel,
    SituationClaimCode,
    SituationModel,
    empty_emotional_state,
)
from agents.models import AgentId, GoalId, GoalStatus
from memory.models import quantize_score
from social.relationships import RelationshipDimension
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import Observation

_OWNER = AgentId("agent-1")
_TICK = 5


def _observation(*, tick: int = _TICK) -> Observation:
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=tick,
    )


def _perception(*, tick: int = _TICK) -> InterpretedPerception:
    return InterpretedPerception(
        owner_id=_OWNER,
        observer_id=EntityId("body-1"),
        tick=tick,
        revision=WorldRevision(0),
        life_status=LifeStatus.ALIVE,
        location_id=EntityId("loc-1"),
        claim_codes=(
            PerceptionClaimCode.SELF_ALIVE,
            PerceptionClaimCode.HAS_LOCATION,
        ),
        counts={},
        confidence=1.0,
    )


def _situation(
    *claims: SituationClaimCode, tick: int = _TICK
) -> SituationModel:
    return SituationModel(
        owner_id=_OWNER,
        tick=tick,
        claim_codes=claims or (SituationClaimCode.LOCAL_SCENE,),
        confidence=1.0,
    )


def _memory() -> RetrievedMemoryContext:
    return RetrievedMemoryContext(
        owner_id=_OWNER,
        memory_ids=(),
        belief_ids=(),
        confidence=1.0,
    )


def _self_model() -> SelfModel:
    return SelfModel(
        owner_id=_OWNER,
        policy_id="self-model-projection",
        policy_version="1",
        life_status=LifeStatus.ALIVE,
        beliefs=(),
        goal_ids=(),
        confidence=1.0,
        candidate_count=0,
    )


def _board(
    *,
    tick: int = _TICK,
    intents: tuple[GoalTransitionIntent, ...] = (),
) -> GoalBoard:
    return GoalBoard(
        owner_id=_OWNER,
        tick=tick,
        goals=(),
        foci_ids=(),
        transition_intents=intents,
        confidence=1.0,
        policy_version="goals.v1",
    )


def _loop_input(*, tick: int = _TICK) -> CognitiveLoopInput:
    return CognitiveLoopInput(
        agent_id=_OWNER,
        observation=_observation(tick=tick),
        internal_state=InternalAgentState(owner_id=_OWNER),
    )


@pytest.mark.asyncio
async def test_threat_raises_fear_and_anxiety() -> None:
    engine = EmotionalStateEngine()
    evaluation = await engine.appraise(
        _loop_input(),
        _perception(),
        _situation(SituationClaimCode.THREAT_SIGNAL),
        _memory(),
        _self_model(),
        _board(),
    )
    assert EmotionDriverCode.THREAT in evaluation.driver_codes
    assert evaluation.state.get(EmotionKind.FEAR) >= quantize_score(0.35)
    assert evaluation.state.get(EmotionKind.ANXIETY) >= quantize_score(0.25)
    assert "afraid" not in repr(evaluation).lower()


@pytest.mark.asyncio
async def test_goal_failure_intents_raise_sadness_and_anger() -> None:
    engine = EmotionalStateEngine()
    intent = GoalTransitionIntent(
        goal_id=GoalId("goal-1"),
        owner_id=_OWNER,
        from_status=GoalStatus.ACTIVE,
        to_status=GoalStatus.FAILED,
        reason_code=GoalTransitionIntentReason.FAILED,
        tick=_TICK,
    )
    evaluation = await engine.appraise(
        _loop_input(),
        _perception(),
        _situation(),
        _memory(),
        _self_model(),
        _board(intents=(intent,)),
    )
    assert EmotionDriverCode.GOAL_FAILURE in evaluation.driver_codes
    assert evaluation.state.get(EmotionKind.SADNESS) >= quantize_score(0.30)
    assert evaluation.state.get(EmotionKind.ANGER) >= quantize_score(0.20)


@pytest.mark.asyncio
async def test_goal_progress_raises_relief_and_confidence() -> None:
    engine = EmotionalStateEngine()
    intent = GoalTransitionIntent(
        goal_id=GoalId("goal-1"),
        owner_id=_OWNER,
        from_status=GoalStatus.ACTIVE,
        to_status=GoalStatus.ACTIVE,
        reason_code=GoalTransitionIntentReason.PROGRESS_UPDATED,
        tick=_TICK,
    )
    evaluation = await engine.appraise(
        _loop_input(),
        _perception(),
        _situation(),
        _memory(),
        _self_model(),
        _board(intents=(intent,)),
    )
    assert EmotionDriverCode.GOAL_PROGRESS in evaluation.driver_codes
    assert evaluation.state.get(EmotionKind.RELIEF) >= quantize_score(0.20)
    assert evaluation.state.get(EmotionKind.CONFIDENCE) >= quantize_score(0.25)


@pytest.mark.asyncio
async def test_decay_toward_baseline_over_ticks() -> None:
    engine = EmotionalStateEngine()
    prior = AgentEmotionalState(
        owner_id=_OWNER,
        tick=1,
        intensities=(EmotionIntensity(kind=EmotionKind.FEAR, intensity=0.8),),
        last_update_tick=1,
        policy_version=EMOTION_POLICY_VERSION,
    )
    evaluation = await engine.appraise(
        _loop_input(tick=4),
        _perception(tick=4),
        _situation(tick=4),
        _memory(),
        _self_model(),
        _board(tick=4),
        prior_state=prior,
    )
    assert EmotionDriverCode.DECAY in evaluation.driver_codes
    assert evaluation.state.get(EmotionKind.FEAR) < 0.8
    assert evaluation.state.get(EmotionKind.FEAR) > 0.0


@pytest.mark.asyncio
async def test_identical_inputs_are_deterministic() -> None:
    engine = EmotionalStateEngine()
    kwargs = dict(
        loop_input=_loop_input(),
        perception=_perception(),
        situation=_situation(SituationClaimCode.THREAT_SIGNAL),
        memory=_memory(),
        self_state=_self_model(),
        goal_board=_board(),
    )
    a = await engine.appraise(**kwargs)
    b = await engine.appraise(**kwargs)
    assert a == b


@pytest.mark.asyncio
async def test_passthrough_emits_prior_without_driver_deltas() -> None:
    appraiser = PassthroughEmotionalStateAppraiser()
    prior = AgentEmotionalState(
        owner_id=_OWNER,
        tick=1,
        intensities=(EmotionIntensity(kind=EmotionKind.FEAR, intensity=0.5),),
        last_update_tick=1,
        policy_version=EMOTION_POLICY_VERSION,
    )
    evaluation = await appraiser.appraise(
        _loop_input(),
        _perception(),
        _situation(SituationClaimCode.THREAT_SIGNAL),
        _memory(),
        _self_model(),
        _board(),
        prior_state=prior,
    )
    assert evaluation.driver_codes == (EmotionDriverCode.PASSTHROUGH,)
    assert evaluation.state.get(EmotionKind.FEAR) == 0.5


@pytest.mark.asyncio
async def test_ownership_fail_closed() -> None:
    engine = EmotionalStateEngine()
    with pytest.raises(ValueError, match="ownership"):
        await engine.appraise(
            _loop_input(),
            _perception(),
            _situation(),
            _memory(),
            _self_model(),
            _board(),
            prior_state=empty_emotional_state(AgentId("other"), tick=0),
        )


@pytest.mark.asyncio
async def test_relationship_fear_distinct_from_emotion_kind(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """RelationshipDimension.FEAR feeds emotion fear without type conflation."""
    assert EmotionKind.FEAR is not RelationshipDimension.FEAR
    engine = EmotionalStateEngine()
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.emotion"):
        evaluation = await engine.appraise(
            _loop_input(),
            _perception(),
            _situation(SituationClaimCode.THREAT_SIGNAL),
            _memory(),
            _self_model(),
            _board(),
        )
    assert EmotionKind.FEAR in {e.kind for e in evaluation.state.intensities}
    for record in caplog.records:
        extra = getattr(record, "cognition", None)
        if isinstance(extra, dict):
            assert "afraid" not in str(extra).lower()
            assert set(extra).issubset(
                {
                    "policy_version",
                    "owner_id",
                    "tick",
                    "mode",
                    "active_kind_count",
                    "max_intensity_band",
                    "driver_code_counts",
                    "decay_applied",
                    "status",
                    "reason_code",
                    "kind",
                }
            )
