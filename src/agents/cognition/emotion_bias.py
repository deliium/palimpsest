"""Deterministic prior-emotion bias for retrieval, reconstruction, and focus.

Applies closed numeric adjustments from ``AgentEmotionalState`` only when
``enabled`` is true and prior state is non-neutral. Never mutates stored
``MemoryTrace`` values; never emits free-form affect narrative.

Ordering vs V2 dynamics: ``MemoryService.recall`` (including dynamics +
``RecallAuditRecord``) completes first. These helpers only re-rank
agent-visible hits/reconstructions afterward. Audit ``selected_ids`` remain
pre-emotion and are never rewritten here.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import replace
from typing import Final

from agents.cognition.models import (
    ActionDirection,
    AgentEmotionalState,
    EmotionalStateEvaluation,
    EmotionKind,
    SituationClaimCode,
    SubjectiveRisk,
    SubjectiveRiskKind,
)
from memory.models import (
    MemoryRankedHit,
    ReconstructedMemory,
    quantize_score,
)

__all__ = [
    "EMOTION_BIAS_POLICY_VERSION",
    "apply_reconstruction_emotion_bias",
    "apply_retrieval_emotion_bias",
    "apply_situation_focus_bias",
    "prefer_emotion_directions",
    "prior_emotion_bias_active",
    "scale_subjective_risks",
    "social_act_preference",
    "updated_emotion_bias_active",
]

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.emotion_bias")

EMOTION_BIAS_POLICY_VERSION: Final[str] = "emotion-bias.v1"

_FEAR_SALIENCE_GAIN: Final[float] = 0.30
_ANXIETY_SALIENCE_GAIN: Final[float] = 0.20
_THREAT_TAG_GAIN: Final[float] = 0.25
_ATTACHMENT_SOCIAL_GAIN: Final[float] = 0.30
_MAX_SCORE_BIAS: Final[float] = 0.40

_THREAT_TAGS: Final[frozenset[str]] = frozenset(
    {
        "threat_signal",
        "threat",
        "has_visible_bodies",
        SituationClaimCode.THREAT_SIGNAL.value,
    }
)
_SOCIAL_TAGS: Final[frozenset[str]] = frozenset(
    {
        "social_signal",
        "social",
        "has_communications",
        SituationClaimCode.SOCIAL_SIGNAL.value,
    }
)


def prior_emotion_bias_active(
    prior: AgentEmotionalState | None,
    *,
    enabled: bool,
) -> bool:
    """Return whether prior emotion should alter ranking/focus this tick."""
    if not enabled:
        return False
    if prior is None:
        return False
    if type(prior) is not AgentEmotionalState:
        raise TypeError("prior must be AgentEmotionalState")
    return not prior.is_neutral()


def apply_retrieval_emotion_bias(
    hits: Sequence[MemoryRankedHit],
    prior: AgentEmotionalState | None,
    *,
    enabled: bool,
) -> tuple[tuple[MemoryRankedHit, ...], bool]:
    """Re-rank hits by prior emotion congruence; identity when inactive."""
    ordered = tuple(hits)
    if not prior_emotion_bias_active(prior, enabled=enabled):
        return ordered, False
    assert prior is not None
    fear = prior.get(EmotionKind.FEAR)
    anxiety = prior.get(EmotionKind.ANXIETY)
    attachment = prior.get(EmotionKind.ATTACHMENT)

    scored: list[tuple[float, int, MemoryRankedHit]] = []
    for index, hit in enumerate(ordered):
        if type(hit) is not MemoryRankedHit:
            raise TypeError("hits must be MemoryRankedHit")
        bonus = 0.0
        salience = hit.trace.emotional_salience
        tags = frozenset(hit.trace.context.tags)
        threat_tagged = bool(tags & _THREAT_TAGS)
        social_tagged = bool(tags & _SOCIAL_TAGS)
        if fear > 0.0:
            bonus += fear * _FEAR_SALIENCE_GAIN * salience
            if threat_tagged:
                bonus += fear * _THREAT_TAG_GAIN
        if anxiety > 0.0:
            bonus += anxiety * _ANXIETY_SALIENCE_GAIN * salience
            if threat_tagged:
                bonus += anxiety * _THREAT_TAG_GAIN * 0.5
        if attachment > 0.0 and social_tagged:
            bonus += attachment * _ATTACHMENT_SOCIAL_GAIN
        if bonus > _MAX_SCORE_BIAS:
            bonus = _MAX_SCORE_BIAS
        adjusted = quantize_score(min(1.0, hit.score + bonus))
        scored.append((adjusted, index, hit))

    # Stable: higher score first; ties preserve prior order via index.
    scored.sort(key=lambda item: (-item[0], item[1]))
    reordered: list[MemoryRankedHit] = []
    for rank, (score, _index, hit) in enumerate(scored, start=1):
        reordered.append(replace(hit, rank=rank, score=score))
    bias_applied = tuple(hit.trace.memory_id for hit in reordered) != tuple(
        hit.trace.memory_id for hit in ordered
    ) or any(
        reordered[i].score != ordered[i].score for i in range(len(ordered))
    )
    _LOG.debug(
        "retrieval_emotion_bias",
        extra={
            "cognition": {
                "bias_applied": bias_applied,
                "policy_version": EMOTION_BIAS_POLICY_VERSION,
                "hit_count": len(reordered),
                "owner_id": prior.owner_id.value,
                "tick": prior.tick,
                "status": "complete",
            }
        },
    )
    return tuple(reordered), bias_applied


def apply_reconstruction_emotion_bias(
    reconstructions: Sequence[ReconstructedMemory],
    prior: AgentEmotionalState | None,
    *,
    enabled: bool,
) -> tuple[tuple[ReconstructedMemory, ...], bool]:
    """Reorder reconstructions by emotion-congruent salience blend."""
    ordered = tuple(reconstructions)
    if not prior_emotion_bias_active(prior, enabled=enabled):
        return ordered, False
    assert prior is not None
    fear = prior.get(EmotionKind.FEAR)
    anxiety = prior.get(EmotionKind.ANXIETY)
    attachment = prior.get(EmotionKind.ATTACHMENT)

    scored: list[tuple[float, int, ReconstructedMemory]] = []
    for index, item in enumerate(ordered):
        if type(item) is not ReconstructedMemory:
            raise TypeError("reconstructions must be ReconstructedMemory")
        blend = item.emotional_salience
        tags = frozenset(item.context.tags)
        if fear > 0.0 or anxiety > 0.0:
            threat = bool(tags & _THREAT_TAGS)
            blend = quantize_score(
                min(
                    1.0,
                    blend
                    + fear * _FEAR_SALIENCE_GAIN * item.emotional_salience
                    + anxiety * _ANXIETY_SALIENCE_GAIN * item.emotional_salience
                    + (fear + anxiety) * _THREAT_TAG_GAIN * (0.5 if threat else 0.0),
                )
            )
        if attachment > 0.0 and bool(tags & _SOCIAL_TAGS):
            blend = quantize_score(
                min(1.0, blend + attachment * _ATTACHMENT_SOCIAL_GAIN)
            )
        scored.append((blend, index, item))
    scored.sort(key=lambda item: (-item[0], item[1]))
    reordered = tuple(item for _blend, _index, item in scored)
    bias_applied = reordered != ordered
    _LOG.debug(
        "reconstruction_emotion_bias",
        extra={
            "cognition": {
                "bias_applied": bias_applied,
                "policy_version": EMOTION_BIAS_POLICY_VERSION,
                "hit_count": len(reordered),
                "owner_id": prior.owner_id.value,
                "tick": prior.tick,
                "status": "complete",
            }
        },
    )
    return reordered, bias_applied


def apply_situation_focus_bias(
    claim_codes: Sequence[SituationClaimCode],
    prior: AgentEmotionalState | None,
    *,
    enabled: bool,
) -> tuple[tuple[SituationClaimCode, ...], dict[str, int], bool]:
    """Reorder situation claims so congruent signals surface earlier."""
    ordered = tuple(claim_codes)
    focus_counts: dict[str, int] = {}
    if not prior_emotion_bias_active(prior, enabled=enabled):
        return ordered, focus_counts, False
    assert prior is not None

    priority: dict[SituationClaimCode, float] = {
        code: float(len(ordered) - index) for index, code in enumerate(ordered)
    }
    fear = prior.get(EmotionKind.FEAR)
    anxiety = prior.get(EmotionKind.ANXIETY)
    attachment = prior.get(EmotionKind.ATTACHMENT)
    confidence = prior.get(EmotionKind.CONFIDENCE)

    if SituationClaimCode.THREAT_SIGNAL in priority:
        boost = fear * 3.0 + anxiety * 2.0
        if boost > 0.0:
            priority[SituationClaimCode.THREAT_SIGNAL] += boost
            focus_counts["threat_focus"] = 1
    if SituationClaimCode.SOCIAL_SIGNAL in priority and attachment > 0.0:
        priority[SituationClaimCode.SOCIAL_SIGNAL] += attachment * 3.0
        focus_counts["social_focus"] = 1
    if SituationClaimCode.LOCAL_SCENE in priority and confidence > 0.0:
        priority[SituationClaimCode.LOCAL_SCENE] += confidence * 1.5
        focus_counts["explore_focus"] = 1
    if SituationClaimCode.TERMINAL_SELF in priority:
        # Terminal remains first when present — never demote mortality.
        priority[SituationClaimCode.TERMINAL_SELF] += 100.0

    reordered = tuple(
        sorted(ordered, key=lambda code: (-priority.get(code, 0.0), code.value))
    )
    bias_applied = reordered != ordered
    _LOG.debug(
        "situation_focus_emotion_bias",
        extra={
            "cognition": {
                "bias_applied": bias_applied,
                "policy_version": EMOTION_BIAS_POLICY_VERSION,
                "focus_code_counts": dict(focus_counts),
                "claim_count": len(reordered),
                "owner_id": prior.owner_id.value,
                "tick": prior.tick,
                "status": "complete",
            }
        },
    )
    return reordered, focus_counts, bias_applied


def updated_emotion_bias_active(
    evaluation: EmotionalStateEvaluation | None,
) -> bool:
    """Return whether updated-stage emotion should bias downstream stages."""
    if evaluation is None:
        return False
    if type(evaluation) is not EmotionalStateEvaluation:
        raise TypeError("evaluation must be EmotionalStateEvaluation")
    return not evaluation.state.is_neutral()


def scale_subjective_risks(
    risks: Sequence[SubjectiveRisk],
    evaluation: EmotionalStateEvaluation | None,
) -> tuple[tuple[SubjectiveRisk, ...], bool]:
    """Scale physical-harm / foreclosure risks from updated emotion."""
    ordered = tuple(risks)
    if not updated_emotion_bias_active(evaluation):
        return ordered, False
    assert evaluation is not None
    state = evaluation.state
    fear = state.get(EmotionKind.FEAR)
    anxiety = state.get(EmotionKind.ANXIETY)
    confidence = state.get(EmotionKind.CONFIDENCE)
    harm_scale = 1.0 + 0.35 * fear + 0.25 * anxiety
    foreclosure_scale = max(0.5, 1.0 - 0.40 * confidence)
    scaled: list[SubjectiveRisk] = []
    changed = False
    for risk in ordered:
        if type(risk) is not SubjectiveRisk:
            raise TypeError("risks must be SubjectiveRisk")
        severity = risk.severity
        likelihood = risk.likelihood
        if risk.kind is SubjectiveRiskKind.PHYSICAL_HARM and harm_scale != 1.0:
            severity = quantize_score(min(1.0, severity * harm_scale))
            likelihood = quantize_score(min(1.0, likelihood * harm_scale))
        elif (
            risk.kind is SubjectiveRiskKind.GOAL_FORECLOSURE
            and foreclosure_scale != 1.0
        ):
            severity = quantize_score(min(1.0, severity * foreclosure_scale))
            likelihood = quantize_score(min(1.0, likelihood * foreclosure_scale))
        if severity != risk.severity or likelihood != risk.likelihood:
            changed = True
            scaled.append(
                SubjectiveRisk(
                    kind=risk.kind,
                    severity=severity,
                    likelihood=likelihood,
                    confidence=risk.confidence,
                )
            )
        else:
            scaled.append(risk)
    if changed:
        _LOG.debug(
            "emotion_risk_scale",
            extra={
                "cognition": {
                    "reason_code": "emotion_risk_scale",
                    "policy_version": EMOTION_BIAS_POLICY_VERSION,
                    "owner_id": state.owner_id.value,
                    "tick": state.tick,
                    "max_intensity_band": state.max_intensity(),
                    "status": "complete",
                }
            },
        )
    return tuple(scaled), changed


def prefer_emotion_directions(
    directions: Sequence[ActionDirection],
    evaluation: EmotionalStateEvaluation | None,
) -> tuple[frozenset[ActionDirection] | None, str | None]:
    """Return preferred direction set + reason code, or ``(None, None)``."""
    if not updated_emotion_bias_active(evaluation):
        return None, None
    assert evaluation is not None
    state = evaluation.state
    fear = state.get(EmotionKind.FEAR) + state.get(EmotionKind.ANXIETY)
    attachment = state.get(EmotionKind.ATTACHMENT)
    anger = state.get(EmotionKind.ANGER)
    available = frozenset(directions)
    if fear >= 0.4 and ActionDirection.FLEE in available:
        _LOG.debug(
            "emotion_intention_vote",
            extra={
                "cognition": {
                    "reason_code": "emotion_intention_vote",
                    "preference": "flee",
                    "policy_version": EMOTION_BIAS_POLICY_VERSION,
                    "owner_id": state.owner_id.value,
                    "tick": state.tick,
                    "status": "complete",
                }
            },
        )
        return frozenset({ActionDirection.FLEE}), "emotion_prefer_flee"
    if attachment >= 0.4 and ActionDirection.COMMUNICATE in available:
        _LOG.debug(
            "emotion_intention_vote",
            extra={
                "cognition": {
                    "reason_code": "emotion_intention_vote",
                    "preference": "communicate",
                    "policy_version": EMOTION_BIAS_POLICY_VERSION,
                    "owner_id": state.owner_id.value,
                    "tick": state.tick,
                    "status": "complete",
                }
            },
        )
        return frozenset({ActionDirection.COMMUNICATE}), "emotion_prefer_communicate"
    if anger >= 0.5 and ActionDirection.ATTACK in available:
        _LOG.debug(
            "emotion_intention_vote",
            extra={
                "cognition": {
                    "reason_code": "emotion_intention_vote",
                    "preference": "attack",
                    "policy_version": EMOTION_BIAS_POLICY_VERSION,
                    "owner_id": state.owner_id.value,
                    "tick": state.tick,
                    "status": "complete",
                }
            },
        )
        return frozenset({ActionDirection.ATTACK}), "emotion_prefer_attack"
    return None, None


def social_act_preference(
    evaluation: EmotionalStateEvaluation | None,
) -> str | None:
    """Return closed social-act preference code, or ``None`` when inactive."""
    if not updated_emotion_bias_active(evaluation):
        return None
    assert evaluation is not None
    state = evaluation.state
    attachment = state.get(EmotionKind.ATTACHMENT)
    anxiety = state.get(EmotionKind.ANXIETY)
    anger = state.get(EmotionKind.ANGER)
    preference: str | None = None
    if attachment >= 0.4:
        preference = "talk"
    elif anxiety >= 0.4:
        preference = "ask"
    elif anger >= 0.4:
        preference = "tell"
    if preference is not None:
        _LOG.debug(
            "emotion_social_bias",
            extra={
                "cognition": {
                    "reason_code": "emotion_social_bias",
                    "preference": preference,
                    "policy_version": EMOTION_BIAS_POLICY_VERSION,
                    "owner_id": state.owner_id.value,
                    "tick": state.tick,
                    "status": "complete",
                }
            },
        )
    return preference
