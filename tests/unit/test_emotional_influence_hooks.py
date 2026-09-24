"""Unit tests for updated-state emotion influence hooks."""

from __future__ import annotations

from agents.cognition.emotion_bias import (
    prefer_emotion_directions,
    scale_subjective_risks,
    social_act_preference,
    updated_emotion_bias_active,
)
from agents.cognition.models import (
    ActionDirection,
    AgentEmotionalState,
    DecisionMetadata,
    EmotionalStateEvaluation,
    EmotionDriverCode,
    EmotionIntensity,
    EmotionKind,
    SubjectiveRisk,
    SubjectiveRiskKind,
    empty_emotional_state,
)
from agents.models import AgentId
from memory.models import quantize_score
from social.relationships import RelationshipDimension


def _evaluation(*, kind: EmotionKind, intensity: float) -> EmotionalStateEvaluation:
    owner = AgentId("agent-1")
    state = AgentEmotionalState(
        owner_id=owner,
        tick=2,
        intensities=(EmotionIntensity(kind=kind, intensity=intensity),),
        last_update_tick=2,
        policy_version="emotion.v1",
    )
    return EmotionalStateEvaluation(
        owner_id=owner,
        tick=2,
        state=state,
        driver_codes=(EmotionDriverCode.THREAT,),
        confidence=1.0,
        policy_version="emotion.v1",
        decision_metadata=DecisionMetadata(
            selection_codes=("test",), candidate_count=1
        ),
    )


def test_emotion_kind_fear_distinct_from_relationship_fear() -> None:
    assert EmotionKind.FEAR is not RelationshipDimension.FEAR


def test_updated_emotion_bias_inactive_for_neutral() -> None:
    owner = AgentId("agent-1")
    evaluation = EmotionalStateEvaluation(
        owner_id=owner,
        tick=0,
        state=empty_emotional_state(owner, tick=0),
        driver_codes=(EmotionDriverCode.PASSTHROUGH,),
        confidence=1.0,
        policy_version="emotion.v1",
        decision_metadata=DecisionMetadata(
            selection_codes=("passthrough",), candidate_count=0
        ),
    )
    assert updated_emotion_bias_active(None) is False
    assert updated_emotion_bias_active(evaluation) is False


def test_scale_subjective_risks_raises_physical_harm_under_fear() -> None:
    risk = SubjectiveRisk(
        kind=SubjectiveRiskKind.PHYSICAL_HARM,
        severity=0.4,
        likelihood=0.4,
        confidence=0.5,
    )
    foreclosure = SubjectiveRisk(
        kind=SubjectiveRiskKind.GOAL_FORECLOSURE,
        severity=0.5,
        likelihood=0.5,
        confidence=0.5,
    )
    fear = _evaluation(kind=EmotionKind.FEAR, intensity=0.8)
    scaled, changed = scale_subjective_risks((risk, foreclosure), fear)
    assert changed is True
    assert scaled[0].severity > risk.severity
    assert scaled[0].likelihood > risk.likelihood

    confidence = _evaluation(kind=EmotionKind.CONFIDENCE, intensity=0.8)
    scaled_conf, changed_conf = scale_subjective_risks((foreclosure,), confidence)
    assert changed_conf is True
    assert scaled_conf[0].severity < foreclosure.severity


def test_prefer_emotion_directions_and_social_acts() -> None:
    fear = _evaluation(kind=EmotionKind.FEAR, intensity=0.8)
    preferred, code = prefer_emotion_directions(
        (ActionDirection.WAIT, ActionDirection.FLEE, ActionDirection.MOVE),
        fear,
    )
    assert preferred == frozenset({ActionDirection.FLEE})
    assert code == "emotion_prefer_flee"

    attachment = _evaluation(kind=EmotionKind.ATTACHMENT, intensity=0.8)
    preferred_c, code_c = prefer_emotion_directions(
        (ActionDirection.WAIT, ActionDirection.COMMUNICATE),
        attachment,
    )
    assert preferred_c == frozenset({ActionDirection.COMMUNICATE})
    assert code_c == "emotion_prefer_communicate"
    assert social_act_preference(attachment) == "talk"
    anxiety = _evaluation(kind=EmotionKind.ANXIETY, intensity=0.8)
    anger = _evaluation(kind=EmotionKind.ANGER, intensity=0.8)
    assert social_act_preference(anxiety) == "ask"
    assert social_act_preference(anger) == "tell"


def test_passthrough_none_leaves_risks_unchanged() -> None:
    risk = SubjectiveRisk(
        kind=SubjectiveRiskKind.PHYSICAL_HARM,
        severity=quantize_score(0.4),
        likelihood=quantize_score(0.4),
        confidence=0.5,
    )
    scaled, changed = scale_subjective_risks((risk,), None)
    assert changed is False
    assert scaled == (risk,)
