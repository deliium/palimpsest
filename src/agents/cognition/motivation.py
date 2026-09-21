"""Versioned drive/goal/mortality appraisal policy (V1).

Preserves independent drive activations, appraises each imagined future, and
models fear of death as opportunity foreclosure (no hard-coded death_penalty).
"""

from __future__ import annotations

import logging
from typing import Final

from agents.cognition.models import (
    ActionDirection,
    CognitiveLoopInput,
    DecisionMetadata,
    DriveEffect,
    FutureAppraisal,
    GoalEffect,
    ImaginedFuture,
    MortalityOpportunityForeclosure,
    MotivationCode,
    MotivationEvaluation,
    MotivationScore,
    OptionSpaceChange,
    PerceivedNeedPressures,
    PossibleFutures,
    SelfModel,
    SituationClaimCode,
    SituationModel,
    SubjectiveRiskKind,
    UncertaintyBand,
    require_confidence,
)
from agents.models import (
    REQUIRED_DRIVE_KINDS,
    AgentId,
    DriveActivation,
    DriveDisposition,
    DriveKind,
    DriveProfile,
    DriveState,
    Goal,
    GoalOutcomeKind,
    GoalStatus,
    default_drive_profile,
)
from social.relationships import (
    DirectedRelationshipProfile,
    RelationshipActivationState,
    RelationshipDimension,
)
from world.models import LifeStatus
from world.observations import ObservedSelf

__all__ = [
    "POLICY_VERSION",
    "MotivationAppraisal",
    "activate_drives",
    "derive_need_pressures",
]

POLICY_VERSION: Final[str] = "motivation.v1"
_ACTIVATION_THRESHOLD: Final[float] = 0.15
_EFFECT_QUANTUM: Final[float] = 1e-6
_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.motivation")

_DIRECTION_MOTIVE: Final[dict[ActionDirection, MotivationCode]] = {
    ActionDirection.WAIT: MotivationCode.WAIT,
    ActionDirection.SLEEP: MotivationCode.REST,
    ActionDirection.SEARCH: MotivationCode.EXPLORE,
    ActionDirection.MOVE: MotivationCode.EXPLORE,
    ActionDirection.COMMUNICATE: MotivationCode.SOCIALIZE,
    ActionDirection.HELP: MotivationCode.SOCIALIZE,
    ActionDirection.FLEE: MotivationCode.SURVIVE,
    ActionDirection.DRINK: MotivationCode.SURVIVE,
    ActionDirection.EAT: MotivationCode.SURVIVE,
    ActionDirection.ATTACK: MotivationCode.SURVIVE,
}


def _quantize_unit(value: float) -> float:
    steps = round(value / _EFFECT_QUANTUM)
    quantized = steps * _EFFECT_QUANTUM
    if quantized < 0.0:
        quantized = 0.0
    elif quantized > 1.0:
        quantized = 1.0
    return 0.0 if quantized == 0.0 else quantized


def _clamp_signed(value: float) -> float:
    if value < -1.0:
        return -1.0
    if value > 1.0:
        return 1.0
    return 0.0 if value == 0.0 else value


def derive_need_pressures(self_body: ObservedSelf | None) -> PerceivedNeedPressures:
    """Map ObservedSelf physiology onto unit-interval need pressures."""
    if self_body is None:
        return PerceivedNeedPressures(
            hunger=0.0, thirst=0.0, fatigue=0.0, health=0.0, confidence=0.0
        )
    health_pressure = _quantize_unit(1.0 - self_body.health.value / 100.0)
    if self_body.life_status is LifeStatus.DEAD:
        health_pressure = 1.0
    return PerceivedNeedPressures(
        hunger=_quantize_unit(self_body.hunger.value / 100.0),
        thirst=_quantize_unit(self_body.thirst.value / 100.0),
        fatigue=_quantize_unit(self_body.fatigue.value / 100.0),
        health=health_pressure,
        confidence=1.0,
    )


def activate_drives(
    *,
    profile: DriveProfile,
    pressures: PerceivedNeedPressures,
    situation: SituationModel,
    danger_signal: float,
    social_signal: float,
) -> DriveState:
    """Combine dispositions, physiology, and situation into activations."""
    by_kind = {item.kind: item for item in profile.dispositions}
    activations: list[DriveActivation] = []
    threat = 1.0 if SituationClaimCode.THREAT_SIGNAL in situation.claim_codes else 0.0
    resource = (
        1.0 if SituationClaimCode.RESOURCE_PRESENT in situation.claim_codes else 0.0
    )
    social = 1.0 if SituationClaimCode.SOCIAL_SIGNAL in situation.claim_codes else 0.0
    social = max(social, social_signal)
    threat = max(threat, danger_signal)

    situational: dict[DriveKind, float] = {
        DriveKind.HUNGER: pressures.hunger,
        DriveKind.THIRST: pressures.thirst,
        DriveKind.FATIGUE: pressures.fatigue,
        DriveKind.SAFETY: max(pressures.health, threat),
        DriveKind.BELONGING: social,
        DriveKind.CURIOSITY: 0.35 + 0.2 * resource,
        DriveKind.STATUS: 0.2 * social,
        DriveKind.AUTONOMY: 0.25,
        DriveKind.COMPETENCE: 0.2 + 0.15 * resource,
        DriveKind.PREDICTABILITY: 0.3 * (1.0 - threat),
        DriveKind.NOVELTY: 0.25 + 0.2 * resource,
    }

    for kind in REQUIRED_DRIVE_KINDS:
        disposition: DriveDisposition = by_kind[kind]
        pressure = situational.get(kind, 0.0)
        activation = _quantize_unit(
            disposition.baseline * 0.35 + disposition.sensitivity * pressure * 0.65
        )
        urgency = _quantize_unit(pressure * disposition.sensitivity)
        activations.append(
            DriveActivation(
                kind=kind,
                activation=activation,
                urgency=urgency,
                confidence=pressures.confidence if pressures.confidence > 0 else 0.5,
            )
        )
    return DriveState(owner_id=profile.owner_id, activations=tuple(activations))


class MotivationAppraisal:
    """Deterministic V1 appraisal over independent drives, goals, and mortality."""

    __slots__ = ()

    async def evaluate(
        self,
        loop_input: CognitiveLoopInput,
        situation: SituationModel,
        self_state: SelfModel,
        futures: PossibleFutures,
    ) -> MotivationEvaluation:
        owner = loop_input.agent_id
        tick = loop_input.observation.tick
        _LOG.debug(
            "motivation_start",
            extra={
                "cognition": {
                    "owner_id": owner.value,
                    "tick": tick,
                    "policy_version": POLICY_VERSION,
                    "status": "start",
                }
            },
        )

        profile = _drive_profile(loop_input, owner)
        pressures = derive_need_pressures(loop_input.observation.self_body)
        danger_signal = _max_danger(futures)
        social_signal = _social_presence(loop_input)
        drive_state = activate_drives(
            profile=profile,
            pressures=pressures,
            situation=situation,
            danger_signal=danger_signal,
            social_signal=social_signal,
        )
        active_goals = _active_goals(loop_input, owner)
        relationships = _relationships(loop_input, owner)
        activation_map = {item.kind: item for item in drive_state.activations}

        appraisals: list[FutureAppraisal] = []
        for future in futures.futures:
            appraisals.append(
                _appraise_future(
                    future=future,
                    activation_map=activation_map,
                    active_goals=active_goals,
                    relationships=relationships,
                    pressures=pressures,
                    self_state=self_state,
                    option_count=len(futures.futures),
                )
            )

        active_drive_kinds = tuple(
            item.kind
            for item in drive_state.activations
            if item.activation >= _ACTIVATION_THRESHOLD
        )
        active_goal_ids = tuple(goal.goal_id for goal in active_goals)
        scores = _project_scores(appraisals, futures.futures)
        top_confidence = max((score.score for score in scores), default=0.5)
        risk_kind_counts = _risk_kind_counts(appraisals)
        uncertainty_band = _aggregate_uncertainty_band(appraisals)

        result = MotivationEvaluation(
            owner_id=owner,
            scores=scores,
            confidence=require_confidence(
                "MotivationEvaluation.confidence", top_confidence
            ),
            decision_metadata=DecisionMetadata(
                selection_codes=tuple(score.motive.value for score in scores),
                candidate_count=len(appraisals),
            ),
            appraisals=tuple(appraisals),
            active_drive_kinds=active_drive_kinds,
            active_goal_ids=active_goal_ids,
        )
        _LOG.debug(
            "motivation_complete",
            extra={
                "cognition": {
                    "owner_id": owner.value,
                    "tick": tick,
                    "policy_version": POLICY_VERSION,
                    "active_drive_count": len(active_drive_kinds),
                    "active_goal_count": len(active_goal_ids),
                    "appraised_future_count": len(appraisals),
                    "risk_kind_counts": risk_kind_counts,
                    "uncertainty_band": uncertainty_band,
                    "status": "complete",
                }
            },
        )
        return result


def _drive_profile(loop_input: CognitiveLoopInput, owner: AgentId) -> DriveProfile:
    if loop_input.snapshot is not None and loop_input.snapshot.drives is not None:
        return loop_input.snapshot.drives
    return default_drive_profile(owner)


def _active_goals(loop_input: CognitiveLoopInput, owner: AgentId) -> tuple[Goal, ...]:
    if loop_input.snapshot is None:
        return ()
    return tuple(
        goal
        for goal in loop_input.snapshot.goals
        if goal.status is GoalStatus.ACTIVE and goal.owner_id == owner
    )


def _relationships(
    loop_input: CognitiveLoopInput, owner: AgentId
) -> tuple[DirectedRelationshipProfile, ...]:
    if loop_input.snapshot is None:
        return ()
    profiles: list[DirectedRelationshipProfile] = []
    for item in loop_input.snapshot.relationships:
        if type(item) is not DirectedRelationshipProfile:
            continue
        if item.source_id != owner:
            continue
        if item.activation_state is not RelationshipActivationState.ACTIVE:
            continue
        profiles.append(item)
    return tuple(sorted(profiles, key=lambda p: p.relationship_id.value))


def _max_danger(futures: PossibleFutures) -> float:
    danger = 0.0
    for future in futures.futures:
        for risk in future.risks:
            if risk.kind is SubjectiveRiskKind.PHYSICAL_HARM:
                danger = max(danger, risk.severity * risk.likelihood)
        if future.subjective_probability is not None and future.direction is (
            ActionDirection.FLEE
        ):
            danger = max(danger, 1.0 - future.subjective_probability)
    return _quantize_unit(danger)


def _social_presence(loop_input: CognitiveLoopInput) -> float:
    observation = loop_input.observation
    if observation.visible_bodies or observation.communications:
        return 0.5
    if loop_input.snapshot is not None and loop_input.snapshot.inbox:
        return 0.3
    return 0.0


def _appraise_future(
    *,
    future: ImaginedFuture,
    activation_map: dict[DriveKind, DriveActivation],
    active_goals: tuple[Goal, ...],
    relationships: tuple[DirectedRelationshipProfile, ...],
    pressures: PerceivedNeedPressures,
    self_state: SelfModel,
    option_count: int,
) -> FutureAppraisal:
    _ = pressures, self_state
    drive_effects = _refine_drive_effects(future.drive_effects, activation_map)
    goal_effects = _refine_goal_effects(future.goal_effects, active_goals)
    risks = future.risks
    uncertainty = future.uncertainty
    mortality = _mortality_foreclosure(
        future=future,
        activation_map=activation_map,
        active_goals=active_goals,
        relationships=relationships,
        option_count=option_count,
    )
    support_drive = sum(
        1
        for effect in drive_effects
        if (
            effect.delta < 0.0
            if effect.kind in {DriveKind.HUNGER, DriveKind.THIRST, DriveKind.FATIGUE}
            else effect.delta > 0.0
        )
    )
    support_goal = sum(1 for effect in goal_effects if effect.progress_delta > 0.0)
    support_social = sum(
        1 for effect in future.social_effects if effect.affinity_delta > 0.0
    )
    return FutureAppraisal(
        future_id=future.future_id,
        drive_effects=drive_effects,
        goal_effects=goal_effects,
        risks=risks,
        mortality=mortality,
        uncertainty=uncertainty,
        support_drive_count=support_drive,
        support_goal_count=support_goal,
        support_social_count=support_social,
    )


def _refine_drive_effects(
    effects: tuple[DriveEffect, ...],
    activation_map: dict[DriveKind, DriveActivation],
) -> tuple[DriveEffect, ...]:
    refined: list[DriveEffect] = []
    seen: set[DriveKind] = set()
    for effect in effects:
        activation = activation_map.get(effect.kind)
        scale = 1.0 if activation is None else 0.5 + 0.5 * activation.activation
        refined.append(
            DriveEffect(
                kind=effect.kind,
                delta=_clamp_signed(effect.delta * scale),
                confidence=effect.confidence,
            )
        )
        seen.add(effect.kind)
    # Preserve visibility of activated drives even when candidate omitted them.
    for kind, activation in activation_map.items():
        if kind in seen:
            continue
        if activation.activation < _ACTIVATION_THRESHOLD:
            continue
        refined.append(
            DriveEffect(kind=kind, delta=0.0, confidence=activation.confidence)
        )
    by_kind = {item.kind: item for item in refined}
    return tuple(by_kind[kind] for kind in REQUIRED_DRIVE_KINDS if kind in by_kind)


def _refine_goal_effects(
    effects: tuple[GoalEffect, ...], active_goals: tuple[Goal, ...]
) -> tuple[GoalEffect, ...]:
    active_ids = {goal.goal_id for goal in active_goals}
    refined = tuple(effect for effect in effects if effect.goal_id in active_ids)
    return refined


def _mortality_foreclosure(
    *,
    future: ImaginedFuture,
    activation_map: dict[DriveKind, DriveActivation],
    active_goals: tuple[Goal, ...],
    relationships: tuple[DirectedRelationshipProfile, ...],
    option_count: int,
) -> MortalityOpportunityForeclosure:
    death_probability = _subjective_death_probability(future)
    outstanding_goal_value = _outstanding_goal_value(active_goals, future)
    attachment_loss = _attachment_loss(relationships, future)
    safety = activation_map.get(DriveKind.SAFETY)
    safety_activation = 0.0 if safety is None else safety.activation
    autonomy = activation_map.get(DriveKind.AUTONOMY)
    autonomy_base = 0.0 if autonomy is None else autonomy.activation
    autonomy_loss = _quantize_unit(
        autonomy_base * (0.4 if future.direction is ActionDirection.FLEE else 0.2)
        + sum(
            risk.severity * risk.likelihood
            for risk in future.risks
            if risk.kind is SubjectiveRiskKind.AUTONOMY_LOSS
        )
    )
    retained = _quantize_unit(
        1.0 if option_count <= 1 else (option_count - 1) / option_count
    )
    if future.direction in {ActionDirection.WAIT, ActionDirection.SLEEP}:
        foreclosed = _quantize_unit(0.15 + 0.5 * death_probability)
        retained = _quantize_unit(1.0 - foreclosed)
    elif future.direction is ActionDirection.FLEE:
        foreclosed = _quantize_unit(0.25 * death_probability)
        retained = _quantize_unit(0.7 + 0.2 * (1.0 - death_probability))
    else:
        foreclosed = _quantize_unit(0.1 + 0.4 * death_probability)
        retained = _quantize_unit(max(0.2, retained - foreclosed))

    return MortalityOpportunityForeclosure(
        death_probability=death_probability,
        outstanding_goal_value=outstanding_goal_value,
        attachment_loss=attachment_loss,
        safety_activation=safety_activation,
        autonomy_loss=autonomy_loss,
        option_space=OptionSpaceChange(
            retained_options_ratio=retained,
            foreclosed_ratio=foreclosed,
        ),
    )


def _subjective_death_probability(future: ImaginedFuture) -> float:
    harm = 0.0
    foreclosure = 0.0
    for risk in future.risks:
        weight = risk.severity * risk.likelihood * risk.confidence
        if risk.kind is SubjectiveRiskKind.PHYSICAL_HARM:
            harm = max(harm, weight)
        elif risk.kind is SubjectiveRiskKind.GOAL_FORECLOSURE:
            foreclosure = max(foreclosure, weight)
    # Stay vs flee: waiting under high harm raises subjective mortality.
    if future.direction in {ActionDirection.WAIT, ActionDirection.SLEEP}:
        return _quantize_unit(0.15 * harm + 0.85 * harm + 0.2 * foreclosure)
    if future.direction is ActionDirection.FLEE:
        return _quantize_unit(0.35 * harm)
    if future.direction is ActionDirection.HELP:
        return _quantize_unit(0.55 * harm)
    return _quantize_unit(0.45 * harm + 0.1 * foreclosure)


def _outstanding_goal_value(goals: tuple[Goal, ...], future: ImaginedFuture) -> float:
    if not goals:
        return 0.0
    total = 0.0
    for goal in goals:
        progress = 0.0 if goal.progress is None else goal.progress.estimate
        remaining = _quantize_unit(1.0 - progress)
        weight = goal.priority * remaining
        if (
            goal.outcome is not None
            and goal.outcome.kind is GoalOutcomeKind.PRESERVE_LIFE
        ):
            weight = _quantize_unit(weight + 0.2)
        # Progressing the goal reduces foreclosure cost for this candidate.
        for effect in future.goal_effects:
            if effect.goal_id == goal.goal_id and effect.progress_delta > 0.0:
                weight = _quantize_unit(weight * (1.0 - 0.4 * effect.progress_delta))
        total += weight
    return _quantize_unit(total / max(1, len(goals)))


def _attachment_loss(
    relationships: tuple[DirectedRelationshipProfile, ...], future: ImaginedFuture
) -> float:
    if not relationships:
        return 0.0
    scores: list[float] = []
    for profile in relationships:
        dims = profile.dimension_map()
        dependency = dims.get(RelationshipDimension.DEPENDENCY)
        affection = dims.get(RelationshipDimension.AFFECTION)
        trust = dims.get(RelationshipDimension.TRUST)
        value = 0.0
        if dependency is not None:
            value += max(0.0, dependency.value) * dependency.confidence.confidence
        if affection is not None:
            value += max(0.0, affection.value) * affection.confidence.confidence * 0.7
        if trust is not None:
            value += max(0.0, trust.value) * trust.confidence.confidence * 0.4
        # Social actions retain attachments; flee/wait under threat risk them.
        if future.direction in {ActionDirection.COMMUNICATE, ActionDirection.HELP}:
            value *= 0.4
        elif future.direction is ActionDirection.FLEE:
            value *= 0.7
        scores.append(_quantize_unit(value))
    if not scores:
        return 0.0
    return _quantize_unit(sum(scores) / len(scores))


def _project_scores(
    appraisals: list[FutureAppraisal], futures: tuple[ImaginedFuture, ...]
) -> tuple[MotivationScore, ...]:
    """Lossy compatibility projection onto closed MotivationCode scores."""
    by_id = {future.future_id: future for future in futures}
    buckets: dict[MotivationCode, float] = {
        MotivationCode.WAIT: 0.0,
        MotivationCode.SURVIVE: 0.0,
        MotivationCode.REST: 0.0,
        MotivationCode.EXPLORE: 0.0,
        MotivationCode.SOCIALIZE: 0.0,
    }
    for appraisal in appraisals:
        future = by_id.get(appraisal.future_id)
        if future is None:
            continue
        motive = _DIRECTION_MOTIVE.get(future.direction, MotivationCode.WAIT)
        support = (
            0.35 * appraisal.support_drive_count
            + 0.45 * appraisal.support_goal_count
            + 0.20 * appraisal.support_social_count
        )
        harm = sum(
            risk.severity * risk.likelihood
            for risk in appraisal.risks
            if risk.kind is SubjectiveRiskKind.PHYSICAL_HARM
        )
        mortality = (
            0.0 if appraisal.mortality is None else appraisal.mortality.composite
        )
        # Higher support and lower mortality → higher projected score.
        raw = _quantize_unit(
            0.25
            + 0.15 * future.confidence
            + 0.08 * support
            - 0.35 * mortality
            - 0.15 * harm
        )
        if (
            motive is MotivationCode.SURVIVE
            and future.direction is ActionDirection.FLEE
        ):
            raw = _quantize_unit(raw + 0.2 * harm)
        buckets[motive] = max(buckets[motive], raw)

    if all(value == 0.0 for value in buckets.values()):
        buckets[MotivationCode.WAIT] = 0.5

    order = (
        MotivationCode.SURVIVE,
        MotivationCode.SOCIALIZE,
        MotivationCode.EXPLORE,
        MotivationCode.REST,
        MotivationCode.WAIT,
    )
    return tuple(
        MotivationScore(motive=motive, score=buckets[motive])
        for motive in order
        if buckets[motive] > 0.0
    )


def _risk_kind_counts(appraisals: list[FutureAppraisal]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for appraisal in appraisals:
        for risk in appraisal.risks:
            key = risk.kind.value
            counts[key] = counts.get(key, 0) + 1
    return counts


def _aggregate_uncertainty_band(appraisals: list[FutureAppraisal]) -> str:
    if not appraisals:
        return UncertaintyBand.LOW.value
    bands = [appraisal.uncertainty.band for appraisal in appraisals]
    if UncertaintyBand.HIGH in bands:
        return UncertaintyBand.HIGH.value
    if UncertaintyBand.MEDIUM in bands:
        return UncertaintyBand.MEDIUM.value
    return UncertaintyBand.LOW.value
