"""Short-term emotional state contracts and deterministic ``emotion.v1`` engine.

Contract types live in ``agents.cognition.models`` and are re-exported here.
``EmotionalStateEngine`` applies closed numeric driver deltas only — never
free-form affect narrative or LLM-authored labels.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Final

from agents.cognition.models import (
    DEFAULT_EMOTION_KINDS,
    DEFAULT_EMOTION_POLICY_VERSION,
    AgentEmotionalState,
    CognitiveLoopInput,
    DecisionMetadata,
    EmotionalStateEvaluation,
    EmotionDriverCode,
    EmotionIntensity,
    EmotionKind,
    EmotionRegulationPolicy,
    GoalBoard,
    GoalTransitionIntentReason,
    InterpretedPerception,
    PerceptionClaimCode,
    RetrievedMemoryContext,
    SelfModel,
    SituationClaimCode,
    SituationModel,
    UncertaintyBand,
    default_emotion_regulation_policy,
    empty_emotional_state,
    intensity_band,
    require_confidence,
)
from agents.cognition.motivation import derive_need_pressures
from agents.models import GoalStatus
from memory.models import quantize_score
from social.relationships import DirectedRelationshipProfile, RelationshipDimension
from world.models import LifeStatus
from world.observations import ObservedSelf

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.emotion")

EMOTION_POLICY_VERSION: Final[str] = DEFAULT_EMOTION_POLICY_VERSION

# Closed driver gain weights (unit interval contributions before clamp).
_THREAT_FEAR: Final[float] = 0.35
_THREAT_ANXIETY: Final[float] = 0.25
_GOAL_FAIL_SADNESS: Final[float] = 0.30
_GOAL_FAIL_ANGER: Final[float] = 0.20
_GOAL_PROGRESS_RELIEF: Final[float] = 0.20
_GOAL_PROGRESS_CONFIDENCE: Final[float] = 0.25
_SALIENCE_SCALE: Final[float] = 0.20
_REL_FEAR_SCALE: Final[float] = 0.25
_REL_AFFECTION_SCALE: Final[float] = 0.25
_SOCIAL_ATTACHMENT: Final[float] = 0.15
_PHYS_ANXIETY_SCALE: Final[float] = 0.20
_PHYS_FEAR_SCALE: Final[float] = 0.15
_PHYS_SADNESS_DEAD: Final[float] = 0.40
_THREAT_RELIEF: Final[float] = 0.15
_OBS_COMM_ATTACHMENT: Final[float] = 0.10

_FAILURE_REASONS: Final[frozenset[GoalTransitionIntentReason]] = frozenset(
    {
        GoalTransitionIntentReason.FAILED,
        GoalTransitionIntentReason.ABANDONED,
    }
)
_PROGRESS_REASONS: Final[frozenset[GoalTransitionIntentReason]] = frozenset(
    {
        GoalTransitionIntentReason.PROGRESS_UPDATED,
        GoalTransitionIntentReason.RESUMED,
        GoalTransitionIntentReason.FOCUS_SELECTED,
    }
)

__all__ = [
    "DEFAULT_EMOTION_KINDS",
    "DEFAULT_EMOTION_POLICY_VERSION",
    "EMOTION_POLICY_VERSION",
    "AgentEmotionalState",
    "EmotionDriverCode",
    "EmotionIntensity",
    "EmotionKind",
    "EmotionRegulationPolicy",
    "EmotionalStateEngine",
    "EmotionalStateEvaluation",
    "PassthroughEmotionalStateAppraiser",
    "UncertaintyBand",
    "default_emotion_regulation_policy",
    "empty_emotional_state",
    "intensity_band",
]


def _clamp_unit(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _add_delta(
    acc: dict[EmotionKind, float],
    kind: EmotionKind,
    delta: float,
    *,
    enabled: frozenset[EmotionKind],
) -> bool:
    if kind not in enabled:
        return False
    if delta == 0.0:
        return False
    acc[kind] = acc.get(kind, 0.0) + delta
    return True


class PassthroughEmotionalStateAppraiser:
    """Re-emit prior/zero emotional state without driver deltas."""

    async def appraise(
        self,
        loop_input: CognitiveLoopInput,
        perception: InterpretedPerception,
        situation: SituationModel,
        memory: RetrievedMemoryContext,
        self_state: SelfModel,
        goal_board: GoalBoard,
        prior_state: AgentEmotionalState | None = None,
    ) -> EmotionalStateEvaluation:
        del perception, situation, memory, self_state, goal_board
        owner = loop_input.agent_id
        tick = loop_input.observation.tick
        if prior_state is not None:
            if type(prior_state) is not AgentEmotionalState:
                _LOG.error(
                    "emotional_state_contract_failure",
                    extra={
                        "cognition": {
                            "reason_code": "type_mismatch",
                            "owner_id": owner.value,
                            "tick": tick,
                            "status": "error",
                        }
                    },
                )
                raise TypeError("prior_state must be AgentEmotionalState")
            if prior_state.owner_id != owner:
                _LOG.error(
                    "emotional_state_contract_failure",
                    extra={
                        "cognition": {
                            "reason_code": "ownership",
                            "owner_id": owner.value,
                            "tick": tick,
                            "status": "error",
                        }
                    },
                )
                raise ValueError("prior_state: ownership")
            state = AgentEmotionalState(
                owner_id=owner,
                tick=tick,
                intensities=prior_state.intensities,
                last_update_tick=prior_state.last_update_tick,
                policy_version=prior_state.policy_version,
            )
        else:
            state = empty_emotional_state(owner, tick=tick)
        evaluation = EmotionalStateEvaluation(
            owner_id=owner,
            tick=tick,
            state=state,
            driver_codes=(EmotionDriverCode.PASSTHROUGH,),
            confidence=1.0,
            policy_version=EMOTION_POLICY_VERSION,
            decision_metadata=DecisionMetadata(
                selection_codes=("emotional_state_passthrough",),
                candidate_count=len(state.intensities),
            ),
        )
        _LOG.debug(
            "emotional_state_complete",
            extra={
                "cognition": {
                    "policy_version": EMOTION_POLICY_VERSION,
                    "owner_id": owner.value,
                    "tick": tick,
                    "mode": "passthrough",
                    "active_kind_count": len(state.intensities),
                    "max_intensity_band": intensity_band(state.max_intensity()).value,
                    "driver_code_counts": {EmotionDriverCode.PASSTHROUGH.value: 1},
                    "decay_applied": False,
                    "status": "complete",
                }
            },
        )
        return evaluation


class EmotionalStateEngine:
    """Deterministic ``emotion.v1`` appraisal from closed subjective drivers."""

    def __init__(
        self,
        *,
        policy: EmotionRegulationPolicy | None = None,
    ) -> None:
        self._policy = (
            policy if policy is not None else default_emotion_regulation_policy()
        )
        if type(self._policy) is not EmotionRegulationPolicy:
            raise TypeError("policy must be EmotionRegulationPolicy")
        if self._policy.policy_version != EMOTION_POLICY_VERSION:
            raise ValueError("unsupported emotion policy_version")

    async def appraise(
        self,
        loop_input: CognitiveLoopInput,
        perception: InterpretedPerception,
        situation: SituationModel,
        memory: RetrievedMemoryContext,
        self_state: SelfModel,
        goal_board: GoalBoard,
        prior_state: AgentEmotionalState | None = None,
    ) -> EmotionalStateEvaluation:
        owner = loop_input.agent_id
        tick = loop_input.observation.tick
        _validate_stage_inputs(
            owner_id=owner,
            tick=tick,
            perception=perception,
            situation=situation,
            memory=memory,
            self_state=self_state,
            goal_board=goal_board,
            prior_state=prior_state,
        )
        policy = self._policy
        enabled = frozenset(policy.enabled_kinds)
        _LOG.debug(
            "emotional_state_start",
            extra={
                "cognition": {
                    "policy_version": EMOTION_POLICY_VERSION,
                    "owner_id": owner.value,
                    "tick": tick,
                    "mode": "enabled",
                    "active_kind_count": len(enabled),
                    "status": "start",
                }
            },
        )

        current = _seed_intensities(
            prior_state, enabled=enabled, owner=owner, tick=tick
        )
        driver_codes: list[EmotionDriverCode] = []
        driver_counts: dict[str, int] = {}
        deltas: dict[EmotionKind, float] = {kind: 0.0 for kind in enabled}

        decay_applied = _apply_decay(
            current,
            prior_state=prior_state,
            tick=tick,
            policy=policy,
            deltas=deltas,
        )
        if decay_applied:
            _record_driver(driver_codes, driver_counts, EmotionDriverCode.DECAY)
            _record_driver(driver_codes, driver_counts, EmotionDriverCode.REGULATION)

        if _drive_threat(situation, deltas, enabled=enabled):
            _record_driver(driver_codes, driver_counts, EmotionDriverCode.THREAT)
        elif prior_state is not None and prior_state.get(EmotionKind.FEAR) > 0.0:
            if _add_delta(deltas, EmotionKind.RELIEF, _THREAT_RELIEF, enabled=enabled):
                _record_driver(driver_codes, driver_counts, EmotionDriverCode.THREAT)

        fail_hit, progress_hit = _goal_driver_hits(goal_board)
        if _drive_goal_board(
            fail_hit=fail_hit,
            progress_hit=progress_hit,
            deltas=deltas,
            enabled=enabled,
        ):
            if fail_hit:
                _record_driver(
                    driver_codes, driver_counts, EmotionDriverCode.GOAL_FAILURE
                )
            if progress_hit:
                _record_driver(
                    driver_codes, driver_counts, EmotionDriverCode.GOAL_PROGRESS
                )

        if _drive_memory_salience(memory, deltas, enabled=enabled):
            _record_driver(
                driver_codes, driver_counts, EmotionDriverCode.MEMORY_SALIENCE
            )

        if _drive_observation(perception, deltas, enabled=enabled):
            _record_driver(driver_codes, driver_counts, EmotionDriverCode.OBSERVATION)

        if _drive_social(loop_input, situation, deltas, enabled=enabled):
            _record_driver(
                driver_codes, driver_counts, EmotionDriverCode.SOCIAL_INTERACTION
            )

        if _drive_relationships(loop_input, deltas, enabled=enabled):
            _record_driver(driver_codes, driver_counts, EmotionDriverCode.RELATIONSHIP)

        if _drive_physical(loop_input, perception, deltas, enabled=enabled):
            _record_driver(
                driver_codes, driver_counts, EmotionDriverCode.PHYSICAL_CONDITION
            )

        intensities = _finalize_intensities(
            current,
            deltas=deltas,
            policy=policy,
            enabled=enabled,
        )
        state = AgentEmotionalState(
            owner_id=owner,
            tick=tick,
            intensities=intensities,
            last_update_tick=tick,
            policy_version=EMOTION_POLICY_VERSION,
        )
        codes = tuple(driver_codes) if driver_codes else (EmotionDriverCode.REGULATION,)
        evaluation = EmotionalStateEvaluation(
            owner_id=owner,
            tick=tick,
            state=state,
            driver_codes=codes,
            confidence=1.0,
            policy_version=EMOTION_POLICY_VERSION,
            decision_metadata=DecisionMetadata(
                selection_codes=("emotional_state_enabled",),
                candidate_count=len(intensities),
            ),
        )
        _LOG.debug(
            "emotional_state_complete",
            extra={
                "cognition": {
                    "policy_version": EMOTION_POLICY_VERSION,
                    "owner_id": owner.value,
                    "tick": tick,
                    "mode": "enabled",
                    "active_kind_count": len(intensities),
                    "max_intensity_band": intensity_band(state.max_intensity()).value,
                    "driver_code_counts": dict(driver_counts),
                    "decay_applied": decay_applied,
                    "status": "complete",
                }
            },
        )
        return evaluation


def _record_driver(
    codes: list[EmotionDriverCode],
    counts: dict[str, int],
    code: EmotionDriverCode,
) -> None:
    if code not in codes:
        codes.append(code)
    counts[code.value] = counts.get(code.value, 0) + 1


def _validate_stage_inputs(
    *,
    owner_id: object,
    tick: int,
    perception: InterpretedPerception,
    situation: SituationModel,
    memory: RetrievedMemoryContext,
    self_state: SelfModel,
    goal_board: GoalBoard,
    prior_state: AgentEmotionalState | None,
) -> None:
    if type(perception) is not InterpretedPerception:
        raise TypeError("perception must be InterpretedPerception")
    if perception.owner_id != owner_id:
        raise ValueError("perception: ownership")
    if type(situation) is not SituationModel:
        raise TypeError("situation must be SituationModel")
    if situation.owner_id != owner_id:
        raise ValueError("situation: ownership")
    if type(memory) is not RetrievedMemoryContext:
        raise TypeError("memory must be RetrievedMemoryContext")
    if memory.owner_id != owner_id:
        raise ValueError("memory: ownership")
    if type(self_state) is not SelfModel:
        raise TypeError("self_state must be SelfModel")
    if self_state.owner_id != owner_id:
        raise ValueError("self_state: ownership")
    if type(goal_board) is not GoalBoard:
        raise TypeError("goal_board must be GoalBoard")
    if goal_board.owner_id != owner_id:
        raise ValueError("goal_board: ownership")
    if goal_board.tick != tick:
        raise ValueError("goal_board: tick_mismatch")
    if prior_state is not None:
        if type(prior_state) is not AgentEmotionalState:
            raise TypeError("prior_state must be AgentEmotionalState")
        if prior_state.owner_id != owner_id:
            raise ValueError("prior_state: ownership")


def _seed_intensities(
    prior_state: AgentEmotionalState | None,
    *,
    enabled: frozenset[EmotionKind],
    owner: object,
    tick: int,
) -> dict[EmotionKind, float]:
    del owner, tick
    values = {kind: 0.0 for kind in enabled}
    if prior_state is None:
        return values
    for entry in prior_state.intensities:
        if entry.kind not in enabled:
            _LOG.warning(
                "emotional_state_disabled_kind_rejected",
                extra={
                    "cognition": {
                        "kind": entry.kind.value,
                        "reason_code": "disabled_kind",
                        "status": "truncated",
                    }
                },
            )
            continue
        values[entry.kind] = entry.intensity
    return values


def _apply_decay(
    current: dict[EmotionKind, float],
    *,
    prior_state: AgentEmotionalState | None,
    tick: int,
    policy: EmotionRegulationPolicy,
    deltas: dict[EmotionKind, float],
) -> bool:
    if prior_state is None:
        return False
    tick_delta = tick - prior_state.last_update_tick
    if tick_delta <= 0:
        return False
    applied = False
    for kind, intensity in current.items():
        baseline = policy.baselines[kind]
        decay_rate = policy.decay_rates[kind]
        remain = (1.0 - decay_rate) ** tick_delta
        target = baseline + (intensity - baseline) * remain
        delta = quantize_score(target - intensity)
        if delta != 0.0:
            deltas[kind] = deltas.get(kind, 0.0) + delta
            applied = True
    return applied


def _drive_threat(
    situation: SituationModel,
    deltas: dict[EmotionKind, float],
    *,
    enabled: frozenset[EmotionKind],
) -> bool:
    if SituationClaimCode.THREAT_SIGNAL not in situation.claim_codes:
        return False
    hit = False
    hit |= _add_delta(deltas, EmotionKind.FEAR, _THREAT_FEAR, enabled=enabled)
    hit |= _add_delta(deltas, EmotionKind.ANXIETY, _THREAT_ANXIETY, enabled=enabled)
    return hit


def _goal_driver_hits(goal_board: GoalBoard) -> tuple[bool, bool]:
    fail_hit = False
    progress_hit = False
    for intent in goal_board.transition_intents:
        if intent.reason_code in _FAILURE_REASONS or intent.to_status in (
            GoalStatus.FAILED,
            GoalStatus.ABANDONED,
        ):
            fail_hit = True
        if intent.reason_code in _PROGRESS_REASONS:
            progress_hit = True
    for goal in goal_board.goals:
        if goal.status is GoalStatus.FAILED:
            fail_hit = True
    return fail_hit, progress_hit


def _drive_goal_board(
    *,
    fail_hit: bool,
    progress_hit: bool,
    deltas: dict[EmotionKind, float],
    enabled: frozenset[EmotionKind],
) -> bool:
    hit = False
    if fail_hit:
        hit |= _add_delta(
            deltas, EmotionKind.SADNESS, _GOAL_FAIL_SADNESS, enabled=enabled
        )
        hit |= _add_delta(deltas, EmotionKind.ANGER, _GOAL_FAIL_ANGER, enabled=enabled)
    if progress_hit:
        hit |= _add_delta(
            deltas, EmotionKind.RELIEF, _GOAL_PROGRESS_RELIEF, enabled=enabled
        )
        hit |= _add_delta(
            deltas, EmotionKind.CONFIDENCE, _GOAL_PROGRESS_CONFIDENCE, enabled=enabled
        )
    return hit


def _mean_salience(memory: RetrievedMemoryContext) -> float | None:
    values: list[float] = []
    for hit in memory.ranked_hits:
        values.append(hit.trace.emotional_salience)
    for item in memory.reconstructions:
        values.append(item.emotional_salience)
    for item in memory.reference_episodes:
        values.append(item.emotional_salience)
    if not values:
        return None
    return quantize_score(sum(values) / len(values))


def _drive_memory_salience(
    memory: RetrievedMemoryContext,
    deltas: dict[EmotionKind, float],
    *,
    enabled: frozenset[EmotionKind],
) -> bool:
    mean = _mean_salience(memory)
    if mean is None or mean <= 0.0:
        return False
    amount = quantize_score(mean * _SALIENCE_SCALE)
    hit = False
    hit |= _add_delta(deltas, EmotionKind.ANXIETY, amount, enabled=enabled)
    hit |= _add_delta(deltas, EmotionKind.FEAR, amount * 0.5, enabled=enabled)
    return hit


def _drive_observation(
    perception: InterpretedPerception,
    deltas: dict[EmotionKind, float],
    *,
    enabled: frozenset[EmotionKind],
) -> bool:
    hit = False
    if PerceptionClaimCode.HAS_COMMUNICATIONS in perception.claim_codes:
        hit |= _add_delta(
            deltas, EmotionKind.ATTACHMENT, _OBS_COMM_ATTACHMENT, enabled=enabled
        )
    if PerceptionClaimCode.SELF_DEAD in perception.claim_codes:
        hit |= _add_delta(
            deltas, EmotionKind.SADNESS, _PHYS_SADNESS_DEAD, enabled=enabled
        )
        hit |= _add_delta(deltas, EmotionKind.FEAR, _PHYS_FEAR_SCALE, enabled=enabled)
    return hit


def _drive_social(
    loop_input: CognitiveLoopInput,
    situation: SituationModel,
    deltas: dict[EmotionKind, float],
    *,
    enabled: frozenset[EmotionKind],
) -> bool:
    inbox_count = 0
    if loop_input.snapshot is not None:
        inbox_count = len(loop_input.snapshot.inbox)
    social = SituationClaimCode.SOCIAL_SIGNAL in situation.claim_codes
    if inbox_count == 0 and not social:
        return False
    amount = _SOCIAL_ATTACHMENT
    if inbox_count > 0:
        amount = quantize_score(_SOCIAL_ATTACHMENT + min(0.1, 0.02 * inbox_count))
    return _add_delta(deltas, EmotionKind.ATTACHMENT, amount, enabled=enabled)


def _drive_relationships(
    loop_input: CognitiveLoopInput,
    deltas: dict[EmotionKind, float],
    *,
    enabled: frozenset[EmotionKind],
) -> bool:
    if loop_input.snapshot is None:
        return False
    relationships = loop_input.snapshot.relationships
    if not relationships:
        return False
    max_fear = 0.0
    max_affection = 0.0
    for profile in relationships:
        if type(profile) is not DirectedRelationshipProfile:
            continue
        for dim in profile.dimensions:
            # RelationshipDimension.FEAR is directed assessment — not EmotionKind.
            if dim.dimension is RelationshipDimension.FEAR:
                if dim.value > max_fear:
                    max_fear = dim.value
            elif dim.dimension is RelationshipDimension.AFFECTION:
                if dim.value > max_affection:
                    max_affection = dim.value
    hit = False
    if max_fear > 0.0:
        amount = quantize_score(max_fear * _REL_FEAR_SCALE)
        hit |= _add_delta(deltas, EmotionKind.FEAR, amount, enabled=enabled)
        hit |= _add_delta(deltas, EmotionKind.ANXIETY, amount * 0.5, enabled=enabled)
    if max_affection > 0.0:
        amount = quantize_score(max_affection * _REL_AFFECTION_SCALE)
        hit |= _add_delta(deltas, EmotionKind.ATTACHMENT, amount, enabled=enabled)
    return hit


def _drive_physical(
    loop_input: CognitiveLoopInput,
    perception: InterpretedPerception,
    deltas: dict[EmotionKind, float],
    *,
    enabled: frozenset[EmotionKind],
) -> bool:
    self_body: ObservedSelf | None = loop_input.observation.self_body
    pressures = derive_need_pressures(self_body)
    hit = False
    distress = quantize_score(
        max(pressures.hunger, pressures.thirst, pressures.fatigue, pressures.health)
    )
    if distress > 0.0:
        hit |= _add_delta(
            deltas,
            EmotionKind.ANXIETY,
            quantize_score(distress * _PHYS_ANXIETY_SCALE),
            enabled=enabled,
        )
        hit |= _add_delta(
            deltas,
            EmotionKind.FEAR,
            quantize_score(distress * _PHYS_FEAR_SCALE),
            enabled=enabled,
        )
    if perception.life_status is LifeStatus.DEAD or (
        self_body is not None and self_body.life_status is LifeStatus.DEAD
    ):
        hit |= _add_delta(
            deltas, EmotionKind.SADNESS, _PHYS_SADNESS_DEAD, enabled=enabled
        )
    return hit


def _finalize_intensities(
    current: Mapping[EmotionKind, float],
    *,
    deltas: Mapping[EmotionKind, float],
    policy: EmotionRegulationPolicy,
    enabled: frozenset[EmotionKind],
) -> tuple[EmotionIntensity, ...]:
    ordered: list[EmotionIntensity] = []
    for kind in DEFAULT_EMOTION_KINDS:
        if kind not in enabled:
            continue
        base = current.get(kind, 0.0)
        raw_delta = deltas.get(kind, 0.0)
        gain_cap = policy.gain_caps[kind]
        if raw_delta > gain_cap:
            raw_delta = gain_cap
        elif raw_delta < -gain_cap:
            raw_delta = -gain_cap
        value = quantize_score(
            _clamp_unit(
                max(
                    policy.floors[kind],
                    min(policy.ceilings[kind], base + raw_delta),
                )
            )
        )
        value = require_confidence(f"emotion[{kind.value}]", value)
        ordered.append(EmotionIntensity(kind=kind, intensity=value))
    return tuple(ordered)
