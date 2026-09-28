"""Versioned deterministic subjective ImaginationEngine (V1).

Candidates are derived only from the owned observation affordances and
owner-scoped subjective evidence. Never consults WorldState, ObservationBatch,
objective probabilities, or event repositories.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Final

from agents.cognition.emotion_bias import scale_subjective_risks
from agents.cognition.models import (
    ActionDirection,
    CognitiveLoopInput,
    DecisionMetadata,
    DriveEffect,
    EmotionalStateEvaluation,
    FutureSourceRef,
    GoalBoard,
    GoalEffect,
    ImaginedFuture,
    PossibleFutures,
    RetrievedMemoryContext,
    SelfModel,
    SituationClaimCode,
    SituationModel,
    SocialEffect,
    SubjectiveRisk,
    SubjectiveRiskKind,
    SubjectiveUncertainty,
    UncertaintyBand,
    episode_facts,
    require_confidence,
)
from agents.cognition.world_model import (
    CausalHypothesis,
    CausalOutcome,
    CausalWorldModel,
    contemplated_situation_atoms,
    match_hypothesis,
)
from agents.models import (
    AgentId,
    DriveKind,
    Goal,
    GoalOutcomeKind,
    GoalStatus,
)
from memory.beliefs import (
    BeliefActivationState,
    BeliefValueKind,
    SemanticBelief,
)
from social.relationships import (
    DirectedRelationshipProfile,
    RelationshipActivationState,
    RelationshipDimension,
)
from world.observations import Observation, ObservedSelf
from world.values import ItemKind, ResourceKind

__all__ = [
    "MIN_BELIEF_CONFIDENCE",
    "POLICY_VERSION",
    "ImaginationEngine",
]

POLICY_VERSION: Final[str] = "imagination.v1"
MIN_BELIEF_CONFIDENCE: Final[float] = 0.1
_MAX_CANDIDATES: Final[int] = 16
_MAX_MOVE_TARGETS: Final[int] = 4
_MAX_SOCIAL_TARGETS: Final[int] = 2
_EFFECT_QUANTUM: Final[float] = 1e-6
_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.imagination")

# Closed subjective evidence codes — never free-form narrative parsing.
_DANGER_PREDICATES: Final[frozenset[str]] = frozenset(
    {
        "is_dangerous",
        "threatens_life",
        "is_hostile",
        "causes_harm",
    }
)
_SAFETY_PREDICATES: Final[frozenset[str]] = frozenset(
    {
        "is_safe",
        "is_shelter",
        "is_helpful",
        "reduces_harm",
    }
)
_DANGER_CONCEPTS: Final[frozenset[str]] = frozenset(
    {"danger", "threat", "harm", "hostile", "lethal"}
)
_SAFETY_CONCEPTS: Final[frozenset[str]] = frozenset(
    {"safety", "shelter", "help", "ally", "refuge"}
)


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


@dataclass(frozen=True, slots=True)
class _SubjectiveEvidence:
    """Aggregated owner-scoped danger/safety evidence (metadata only)."""

    danger: float
    safety: float
    belief_ids: tuple[str, ...]
    memory_ids: tuple[str, ...]
    relationship_ids: tuple[str, ...]
    usable_belief_count: int
    reconstruction_count: int
    ignored_belief_count: int


@dataclass(frozen=True, slots=True)
class _CandidateSeed:
    future_id: str
    direction: ActionDirection
    claim_codes: tuple[SituationClaimCode, ...]
    target_entity_id: str | None = None
    target_agent_id: AgentId | None = None


class ImaginationEngine:
    """Deterministic V1 imagination over typed observation affordances."""

    __slots__ = ("_prospective_audit",)

    def __init__(self) -> None:
        self._prospective_audit: object | None = None

    def last_prospective_audit(self) -> object | None:
        return self._prospective_audit

    async def imagine(
        self,
        loop_input: CognitiveLoopInput,
        situation: SituationModel,
        self_state: SelfModel,
        memory: RetrievedMemoryContext,
        goal_board: GoalBoard | None = None,
        emotional_state: EmotionalStateEvaluation | None = None,
        causal_world_model: object | None = None,
        theory_of_mind: object | None = None,
        prospective_policy: object | None = None,
        llm_provider: object | None = None,
    ) -> PossibleFutures:
        owner = loop_input.agent_id
        tick = loop_input.observation.tick
        fallback = False
        evidence = _SubjectiveEvidence(
            danger=0.0,
            safety=0.0,
            belief_ids=(),
            memory_ids=(),
            relationship_ids=(),
            usable_belief_count=0,
            reconstruction_count=0,
            ignored_belief_count=0,
        )

        _LOG.debug(
            "imagination_start",
            extra={
                "cognition": {
                    "owner_id": owner.value,
                    "tick": tick,
                    "policy_version": POLICY_VERSION,
                    "status": "start",
                }
            },
        )
        if prospective_policy is None:
            self._prospective_audit = None
            _LOG.debug(
                "prospective_skipped owner_id=%s tick=%s status=skipped",
                owner.value,
                tick,
            )

        try:
            futures: tuple[ImaginedFuture, ...]
            if SituationClaimCode.TERMINAL_SELF in situation.claim_codes:
                fallback = True
                futures = (
                    _wait_future(
                        future_id="wait-terminal",
                        claim_codes=(SituationClaimCode.TERMINAL_SELF,),
                        confidence=1.0,
                        evidence=evidence,
                    ),
                )
            elif memory.owner_id != owner:
                _LOG.error(
                    "imagination_ownership",
                    extra={
                        "cognition": {
                            "owner_id": owner.value,
                            "tick": tick,
                            "policy_version": POLICY_VERSION,
                            "reason_code": "ownership",
                        }
                    },
                )
                raise ValueError("RetrievedMemoryContext: ownership")
            elif prospective_policy is not None:
                evidence = _collect_evidence(
                    owner=owner,
                    loop_input=loop_input,
                    memory=memory,
                    self_state=self_state,
                )
                futures = await self._prospective_futures(
                    loop_input=loop_input,
                    situation=situation,
                    self_state=self_state,
                    memory=memory,
                    goal_board=goal_board,
                    emotional_state=emotional_state,
                    causal_world_model=causal_world_model,
                    theory_of_mind=theory_of_mind,
                    prospective_policy=prospective_policy,
                    llm_provider=llm_provider,
                )
            else:
                evidence = _collect_evidence(
                    owner=owner,
                    loop_input=loop_input,
                    memory=memory,
                    self_state=self_state,
                )
                seeds = _affordances(
                    observation=loop_input.observation,
                    situation=situation,
                    loop_input=loop_input,
                )
                if not seeds:
                    fallback = True
                    seeds = (
                        _CandidateSeed(
                            future_id="wait-fallback",
                            direction=ActionDirection.WAIT,
                            claim_codes=(SituationClaimCode.IDLE,),
                        ),
                    )
                active_goals = _eligible_planning_goals(loop_input, goal_board)
                built: list[ImaginedFuture] = []
                for seed in seeds[:_MAX_CANDIDATES]:
                    built.append(
                        _build_future(
                            seed=seed,
                            evidence=evidence,
                            observation=loop_input.observation,
                            active_goals=active_goals,
                            relationships=_owned_relationships(loop_input, owner),
                        )
                    )
                futures = tuple(built)
        except (TypeError, ValueError) as exc:
            _LOG.error(
                "imagination_contract_failure",
                extra={
                    "cognition": {
                        "owner_id": owner.value,
                        "tick": tick,
                        "policy_version": POLICY_VERSION,
                        "reason_code": type(exc).__name__,
                    }
                },
            )
            raise

        biased: list[ImaginedFuture] = []
        risk_bias_applied = False
        for future in futures:
            scaled, changed = scale_subjective_risks(future.risks, emotional_state)
            if changed:
                risk_bias_applied = True
                biased.append(replace(future, risks=scaled))
            else:
                biased.append(future)
        futures = tuple(biased)
        if causal_world_model is None:
            _LOG.debug(
                "world_model_imagination_bias owner_id=%s tick=%s status=skipped",
                owner.value,
                tick,
            )
        else:
            futures = _apply_world_model_imagination(
                futures,
                observation=loop_input.observation,
                model=causal_world_model,
                owner_id=owner,
                tick=tick,
            )
        from agents.cognition.theory_of_mind import mind_imagination_deltas

        if theory_of_mind is None:
            _LOG.debug(
                "theory_of_mind_imagination_bias owner_id=%s tick=%s status=skipped",
                owner.value,
                tick,
            )
        else:
            mind_adjusted: list[ImaginedFuture] = []
            for future in futures:
                harm, belonging, hypothesis_id, action_atom = mind_imagination_deltas(
                    theory_of_mind,
                    direction=future.direction.value,
                    target_id=future.target_entity_id,
                )
                risks = future.risks
                drives = future.drive_effects
                if harm:
                    risks = _raise_physical_harm(risks, harm)
                if belonging:
                    drives = _shift_drive(drives, DriveKind.BELONGING, belonging)
                if risks is future.risks and drives is future.drive_effects:
                    mind_adjusted.append(future)
                    continue
                mind_adjusted.append(replace(future, risks=risks, drive_effects=drives))
                _LOG.debug(
                    "theory_of_mind_imagination_bias owner_id=%s tick=%s "
                    "hypothesis_id=%s action=%s confidence=%s direction=%s",
                    owner.value,
                    tick,
                    hypothesis_id,
                    action_atom,
                    harm or belonging,
                    future.direction.value,
                )
            futures = tuple(mind_adjusted)

        if evidence.ignored_belief_count > 0:
            _LOG.warning(
                "imagination_evidence_truncated",
                extra={
                    "cognition": {
                        "owner_id": owner.value,
                        "tick": tick,
                        "policy_version": POLICY_VERSION,
                        "reason_code": "ignored_beliefs",
                        "ignored_belief_count": evidence.ignored_belief_count,
                    }
                },
            )

        direction_codes = tuple(
            f"{future.future_id}:{future.direction.value}" for future in futures
        )
        if risk_bias_applied:
            direction_codes = (*direction_codes, "emotion_risk_scale")
        confidence = min((future.confidence for future in futures), default=1.0)
        result = PossibleFutures(
            owner_id=owner,
            futures=futures,
            confidence=require_confidence("PossibleFutures.confidence", confidence),
            decision_metadata=DecisionMetadata(
                selection_codes=direction_codes,
                candidate_count=len(futures),
            ),
        )
        _LOG.debug(
            "imagination_complete",
            extra={
                "cognition": {
                    "owner_id": owner.value,
                    "tick": tick,
                    "policy_version": POLICY_VERSION,
                    "usable_belief_count": evidence.usable_belief_count,
                    "reconstruction_count": evidence.reconstruction_count,
                    "relationship_count": len(evidence.relationship_ids),
                    "candidate_count": len(futures),
                    "direction_codes": list(direction_codes),
                    "fallback": fallback,
                    "status": "complete",
                }
            },
        )
        return result

    async def _prospective_futures(
        self,
        *,
        loop_input: CognitiveLoopInput,
        situation: SituationModel,
        self_state: SelfModel,
        memory: RetrievedMemoryContext,
        goal_board: GoalBoard | None,
        emotional_state: EmotionalStateEvaluation | None,
        causal_world_model: object | None,
        theory_of_mind: object | None,
        prospective_policy: object,
        llm_provider: object | None,
    ) -> tuple[ImaginedFuture, ...]:
        from dataclasses import replace

        from agents.cognition.prospective import (
            ProspectivePolicy,
            ProspectivePruneReason,
            build_prospective_audit,
            collapse_prospective_future,
            rollout_prospective,
            selection_token_floor,
        )

        if type(prospective_policy) is not ProspectivePolicy:
            raise TypeError("prospective_policy must be ProspectivePolicy")
        rollout = rollout_prospective(
            loop_input,
            situation,
            self_state,
            memory,
            prospective_policy,
            goal_board=goal_board,
            emotional_state=emotional_state,
            causal_world_model=causal_world_model,
            theory_of_mind=theory_of_mind,
        )
        preferred: tuple[str, ...] = ()
        extra: list[ProspectivePruneReason] = []
        fallback_used = False
        llm_calls = 0
        token_count = 0
        if prospective_policy.allow_provider:
            floor = selection_token_floor()
            if prospective_policy.max_llm_calls < 1:
                extra.append(ProspectivePruneReason.BUDGET_LLM)
                fallback_used = True
                _log_selection_budget(loop_input, rollout, reason_code="budget_llm")
            elif prospective_policy.max_tokens < floor:
                extra.append(ProspectivePruneReason.BUDGET_TOKENS)
                fallback_used = True
                _log_selection_budget(loop_input, rollout, reason_code="budget_tokens")
            else:
                from agents.cognition.prospective_selection import (
                    rank_prospective_transitions,
                )

                ranked = await rank_prospective_transitions(
                    rollout,
                    prospective_policy,
                    provider=llm_provider,
                    tick=loop_input.observation.tick,
                    output_tokens=floor,
                )
                preferred = ranked.selected_ids
                fallback_used = ranked.fallback_used
                llm_calls = ranked.llm_call_count
                token_count = ranked.token_count
        if extra or llm_calls or fallback_used:
            rollout = replace(
                rollout,
                budgets_exhausted=(*rollout.budgets_exhausted, *extra),
                llm_call_count=llm_calls,
                token_count=token_count,
                fallback_used=fallback_used,
            )
        future = collapse_prospective_future(
            rollout,
            loop_input=loop_input,
            situation=situation,
            self_state=self_state,
            memory=memory,
            goal_board=goal_board,
            preferred_ids=preferred,
        )
        self._prospective_audit = build_prospective_audit(
            rollout,
            tick=loop_input.observation.tick,
            future=future,
        )
        return (future,)


def _log_selection_budget(
    loop_input: CognitiveLoopInput,
    rollout: object,
    *,
    reason_code: str,
) -> None:
    from agents.cognition.prospective import log_prospective_llm_selection

    transitions = getattr(rollout, "transitions", ())
    kept = sum(1 for item in transitions if item.prune_reason is None)
    log_prospective_llm_selection(
        owner_id=loop_input.agent_id.value,
        tick=loop_input.observation.tick,
        candidate_count=kept,
        selected_count=0,
        token_count=0,
        fallback_used=True,
        reason_code=reason_code,
    )


def _apply_world_model_imagination(
    futures: tuple[ImaginedFuture, ...],
    *,
    observation: Observation,
    model: object,
    owner_id: AgentId,
    tick: int,
) -> tuple[ImaginedFuture, ...]:
    if type(model) is not CausalWorldModel:
        raise TypeError("causal_world_model must be CausalWorldModel")
    adjusted: list[ImaginedFuture] = []
    for future in futures:
        atoms = contemplated_situation_atoms(
            observation,
            direction=future.direction,
            target_entity_id=future.target_entity_id,
        )
        risks = future.risks
        drives = future.drive_effects
        danger = match_hypothesis(model, outcome=CausalOutcome.DANGER, atoms=atoms)
        if danger is not None and future.direction in {
            ActionDirection.MOVE,
            ActionDirection.SEARCH,
        }:
            risks = _raise_physical_harm(risks, danger.confidence)
            _log_imagination_bias(owner_id, tick, danger, future.direction)
        help_match = match_hypothesis(model, outcome=CausalOutcome.HELP, atoms=atoms)
        if help_match is not None and future.direction is ActionDirection.COMMUNICATE:
            drives = _shift_drive(drives, DriveKind.BELONGING, help_match.confidence)
            _log_imagination_bias(owner_id, tick, help_match, future.direction)
        if future.direction is ActionDirection.SEARCH:
            failure = match_hypothesis(
                model, outcome=CausalOutcome.SEARCH_FAILURE, atoms=atoms
            )
            success = match_hypothesis(
                model, outcome=CausalOutcome.SEARCH_SUCCESS, atoms=atoms
            )
            if failure is not None:
                drives = _shift_drive(drives, DriveKind.CURIOSITY, -failure.confidence)
                _log_imagination_bias(owner_id, tick, failure, future.direction)
            if success is not None:
                drives = _shift_drive(drives, DriveKind.CURIOSITY, success.confidence)
                _log_imagination_bias(owner_id, tick, success, future.direction)
        if risks is future.risks and drives is future.drive_effects:
            adjusted.append(future)
        else:
            adjusted.append(replace(future, risks=risks, drive_effects=drives))
    return tuple(adjusted)


def _log_imagination_bias(
    owner_id: AgentId,
    tick: int,
    hypothesis: CausalHypothesis,
    direction: ActionDirection,
) -> None:
    _LOG.debug(
        "world_model_imagination_bias owner_id=%s tick=%s hypothesis_id=%s "
        "outcome=%s confidence=%s direction=%s",
        owner_id.value,
        tick,
        hypothesis.hypothesis_id,
        hypothesis.outcome.value,
        hypothesis.confidence,
        direction.value,
    )


def _raise_physical_harm(
    risks: tuple[SubjectiveRisk, ...], magnitude: float
) -> tuple[SubjectiveRisk, ...]:
    updated: list[SubjectiveRisk] = []
    found = False
    for risk in risks:
        if risk.kind is not SubjectiveRiskKind.PHYSICAL_HARM:
            updated.append(risk)
            continue
        found = True
        updated.append(
            SubjectiveRisk(
                kind=risk.kind,
                severity=_quantize_unit(risk.severity + magnitude),
                likelihood=_quantize_unit(risk.likelihood + magnitude),
                confidence=risk.confidence,
            )
        )
    if not found:
        updated.append(
            SubjectiveRisk(
                kind=SubjectiveRiskKind.PHYSICAL_HARM,
                severity=_quantize_unit(magnitude),
                likelihood=_quantize_unit(magnitude),
                confidence=_quantize_unit(magnitude),
            )
        )
    return tuple(updated)


def _shift_drive(
    effects: tuple[DriveEffect, ...], kind: DriveKind, magnitude: float
) -> tuple[DriveEffect, ...]:
    updated: list[DriveEffect] = []
    found = False
    for effect in effects:
        if effect.kind is not kind:
            updated.append(effect)
            continue
        found = True
        updated.append(
            DriveEffect(
                kind=effect.kind,
                delta=_clamp_signed(effect.delta + magnitude),
                confidence=effect.confidence,
            )
        )
    if not found:
        updated.append(
            DriveEffect(
                kind=kind,
                delta=_clamp_signed(magnitude),
                confidence=_quantize_unit(max(magnitude, 0.0)),
            )
        )
    by_kind = {effect.kind: effect for effect in updated}
    return tuple(by_kind[item] for item in DriveKind if item in by_kind)


def _eligible_planning_goals(
    loop_input: CognitiveLoopInput,
    goal_board: GoalBoard | None,
) -> tuple[Goal, ...]:
    """ACTIVE goals from GoalBoard when present; else snapshot ACTIVE goals.

    SUSPENDED / FAILED / ABANDONED / COMPLETED are excluded from forward planning.
    """

    owner = loop_input.agent_id
    if goal_board is not None:
        if goal_board.owner_id != owner:
            raise ValueError("GoalBoard: ownership")
        return tuple(
            goal
            for goal in goal_board.goals
            if goal.status is GoalStatus.ACTIVE and goal.owner_id == owner
        )
    if loop_input.snapshot is None:
        return ()
    return tuple(
        goal
        for goal in loop_input.snapshot.goals
        if goal.status is GoalStatus.ACTIVE and goal.owner_id == owner
    )


def _active_goals(loop_input: CognitiveLoopInput) -> tuple[Goal, ...]:
    return _eligible_planning_goals(loop_input, None)


def _owned_relationships(
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


def _collect_evidence(
    *,
    owner: AgentId,
    loop_input: CognitiveLoopInput,
    memory: RetrievedMemoryContext,
    self_state: SelfModel,
) -> _SubjectiveEvidence:
    _ = self_state
    beliefs = memory.semantic_beliefs
    if not beliefs and loop_input.snapshot is not None:
        beliefs = loop_input.snapshot.semantic_beliefs

    danger = 0.0
    safety = 0.0
    belief_ids: list[str] = []
    ignored = 0
    usable = 0
    for belief in beliefs:
        if type(belief) is not SemanticBelief:
            ignored += 1
            continue
        if belief.owner_id != owner:
            ignored += 1
            continue
        if belief.activation_state is not BeliefActivationState.ACTIVE:
            ignored += 1
            continue
        confidence = belief.confidence.confidence
        if confidence < MIN_BELIEF_CONFIDENCE:
            ignored += 1
            continue
        usable += 1
        predicate = belief.claim.predicate
        strength = confidence
        value = belief.claim.value
        if value.kind is BeliefValueKind.BOOL and value.bool_value is False:
            strength = 0.0
        elif value.kind is BeliefValueKind.NUMBER and value.number_value is not None:
            strength = _quantize_unit(confidence * abs(value.number_value))
        if predicate in _DANGER_PREDICATES:
            danger = _quantize_unit(max(danger, strength))
            belief_ids.append(belief.belief_id.value)
        elif predicate in _SAFETY_PREDICATES:
            safety = _quantize_unit(max(safety, strength))
            belief_ids.append(belief.belief_id.value)

    memory_ids: list[str] = []
    facts = episode_facts(memory)
    for episode in facts:
        if episode.owner_id != owner:
            continue
        conf = episode.confidence
        if conf < MIN_BELIEF_CONFIDENCE:
            continue
        concepts = {item.concept for item in episode.concepts}
        salience = episode.emotional_salience
        weight = _quantize_unit(conf * max(0.25, salience))
        if concepts & _DANGER_CONCEPTS:
            danger = _quantize_unit(max(danger, weight))
            memory_ids.extend(mid.value for mid in episode.source_memory_ids)
        if concepts & _SAFETY_CONCEPTS:
            safety = _quantize_unit(max(safety, weight))
            memory_ids.extend(mid.value for mid in episode.source_memory_ids)
        for relation in episode.relations:
            if relation.predicate in _DANGER_PREDICATES:
                danger = _quantize_unit(max(danger, weight))
                memory_ids.extend(mid.value for mid in episode.source_memory_ids)
            elif relation.predicate in _SAFETY_PREDICATES:
                safety = _quantize_unit(max(safety, weight))
                memory_ids.extend(mid.value for mid in episode.source_memory_ids)

    relationship_ids: list[str] = []
    for profile in _owned_relationships(loop_input, owner):
        dims = profile.dimension_map()
        fear = dims.get(RelationshipDimension.FEAR)
        affection = dims.get(RelationshipDimension.AFFECTION)
        if fear is not None and fear.value > 0.0:
            danger = _quantize_unit(
                max(danger, fear.value * fear.confidence.confidence)
            )
            relationship_ids.append(profile.relationship_id.value)
        if affection is not None and affection.value > 0.0:
            safety = _quantize_unit(
                max(safety, affection.value * affection.confidence.confidence)
            )
            relationship_ids.append(profile.relationship_id.value)

    return _SubjectiveEvidence(
        danger=danger,
        safety=safety,
        belief_ids=tuple(sorted(set(belief_ids))),
        memory_ids=tuple(sorted(set(memory_ids))),
        relationship_ids=tuple(sorted(set(relationship_ids))),
        usable_belief_count=usable,
        reconstruction_count=len(facts),
        ignored_belief_count=ignored,
    )


def _affordances(
    *,
    observation: Observation,
    situation: SituationModel,
    loop_input: CognitiveLoopInput,
) -> tuple[_CandidateSeed, ...]:
    seeds: list[_CandidateSeed] = []
    self_body = observation.self_body
    claims_local = (
        (SituationClaimCode.LOCAL_SCENE,)
        if SituationClaimCode.LOCAL_SCENE in situation.claim_codes
        else (SituationClaimCode.IDLE,)
    )

    seeds.append(
        _CandidateSeed(
            future_id="wait",
            direction=ActionDirection.WAIT,
            claim_codes=claims_local,
        )
    )

    if self_body is None:
        return tuple(seeds)

    physiology = _physiology_pressures(self_body)

    water_id = _first_water_source(observation, self_body)
    if water_id is not None:
        seeds.append(
            _CandidateSeed(
                future_id="drink",
                direction=ActionDirection.DRINK,
                claim_codes=(SituationClaimCode.RESOURCE_PRESENT,),
                target_entity_id=water_id,
            )
        )

    food_id = _first_food_source(observation, self_body)
    if food_id is not None:
        seeds.append(
            _CandidateSeed(
                future_id="eat",
                direction=ActionDirection.EAT,
                claim_codes=(SituationClaimCode.RESOURCE_PRESENT,),
                target_entity_id=food_id,
            )
        )

    if physiology["fatigue"] >= 0.1:
        seeds.append(
            _CandidateSeed(
                future_id="sleep",
                direction=ActionDirection.SLEEP,
                claim_codes=claims_local,
            )
        )

    if observation.items or observation.occurrences or observation.resources:
        seeds.append(
            _CandidateSeed(
                future_id="search",
                direction=ActionDirection.SEARCH,
                claim_codes=claims_local,
            )
        )

    exits = sorted(observation.exits, key=lambda item: item.destination_id.value)
    for index, exit_item in enumerate(exits[:_MAX_MOVE_TARGETS]):
        seeds.append(
            _CandidateSeed(
                future_id=f"move-{index}",
                direction=ActionDirection.MOVE,
                claim_codes=(SituationClaimCode.LOCAL_SCENE,),
                target_entity_id=exit_item.destination_id.value,
            )
        )

    alive_bodies = sorted(
        (
            body
            for body in observation.visible_bodies
            if body.entity_id != self_body.entity_id
        ),
        key=lambda body: body.entity_id.value,
    )
    if alive_bodies:
        threat = alive_bodies[0]
        seeds.append(
            _CandidateSeed(
                future_id="flee",
                direction=ActionDirection.FLEE,
                claim_codes=(SituationClaimCode.THREAT_SIGNAL,),
                target_entity_id=threat.entity_id.value,
            )
        )

    social_targets = _social_targets(loop_input, observation, alive_bodies)
    for index, (entity_id, agent_id) in enumerate(social_targets[:_MAX_SOCIAL_TARGETS]):
        seeds.append(
            _CandidateSeed(
                future_id=f"talk-{index}",
                direction=ActionDirection.COMMUNICATE,
                claim_codes=(SituationClaimCode.SOCIAL_SIGNAL,),
                target_entity_id=entity_id,
                target_agent_id=agent_id,
            )
        )
        seeds.append(
            _CandidateSeed(
                future_id=f"help-{index}",
                direction=ActionDirection.HELP,
                claim_codes=(SituationClaimCode.SOCIAL_SIGNAL,),
                target_entity_id=entity_id,
                target_agent_id=agent_id,
            )
        )

    # Stable order by future_id then direction.
    seeds.sort(key=lambda seed: (seed.future_id, seed.direction.value))
    return tuple(seeds)


def _social_targets(
    loop_input: CognitiveLoopInput,
    observation: Observation,
    alive_bodies: Sequence[object],
) -> list[tuple[str, AgentId | None]]:
    bindings: dict[str, AgentId] = {}
    if (
        loop_input.snapshot is not None
        and loop_input.snapshot.social_identity is not None
    ):
        for binding in loop_input.snapshot.social_identity.counterparts:
            bindings[binding.entity_id.value] = binding.agent_id

    targets: list[tuple[str, AgentId | None]] = []
    for body in alive_bodies:
        entity_value = body.entity_id.value  # type: ignore[attr-defined]
        targets.append((entity_value, bindings.get(entity_value)))
    if not targets and observation.communications:
        for message in sorted(
            observation.communications, key=lambda item: item.speaker_id.value
        ):
            speaker = message.speaker_id.value
            if speaker == observation.observer_id.value:
                continue
            targets.append((speaker, bindings.get(speaker)))
            if len(targets) >= _MAX_SOCIAL_TARGETS:
                break
    return targets


def _first_water_source(
    observation: Observation, self_body: ObservedSelf
) -> str | None:
    _ = self_body
    for resource in sorted(
        observation.resources, key=lambda item: item.entity_id.value
    ):
        if resource.kind is ResourceKind.WATER and resource.quantity > 0.0:
            return resource.entity_id.value
    for item in sorted(observation.items, key=lambda entry: entry.entity_id.value):
        if item.kind is ItemKind.WATER:
            return item.entity_id.value
    return None


def _first_food_source(observation: Observation, self_body: ObservedSelf) -> str | None:
    _ = self_body
    for resource in sorted(
        observation.resources, key=lambda item: item.entity_id.value
    ):
        if resource.kind is ResourceKind.FOOD and resource.quantity > 0.0:
            return resource.entity_id.value
    for item in sorted(observation.items, key=lambda entry: entry.entity_id.value):
        if item.kind is ItemKind.FOOD:
            return item.entity_id.value
    return None


def _wait_future(
    *,
    future_id: str,
    claim_codes: tuple[SituationClaimCode, ...],
    confidence: float,
    evidence: _SubjectiveEvidence,
) -> ImaginedFuture:
    return ImaginedFuture(
        future_id=future_id,
        claim_codes=claim_codes,
        confidence=confidence,
        direction=ActionDirection.WAIT,
        horizon_ticks=1,
        drive_effects=(
            DriveEffect(kind=DriveKind.PREDICTABILITY, delta=0.1, confidence=1.0),
        ),
        risks=(),
        uncertainty=SubjectiveUncertainty(
            epistemic=0.0, aleatory=0.0, band=UncertaintyBand.LOW
        ),
        subjective_probability=confidence,
        source_refs=FutureSourceRef(
            belief_ids=evidence.belief_ids,
            memory_ids=evidence.memory_ids,
            relationship_ids=evidence.relationship_ids,
        ),
    )


def _build_future(
    *,
    seed: _CandidateSeed,
    evidence: _SubjectiveEvidence,
    observation: Observation,
    active_goals: tuple[Goal, ...],
    relationships: tuple[DirectedRelationshipProfile, ...],
) -> ImaginedFuture:
    physiology = _physiology_pressures(observation.self_body)
    base_confidence = 0.55
    danger_bias = evidence.danger
    safety_bias = evidence.safety

    drive_effects = _direction_drive_effects(
        seed.direction, physiology=physiology, danger=danger_bias, safety=safety_bias
    )
    goal_effects = _direction_goal_effects(seed.direction, active_goals)
    social_effects = _direction_social_effects(
        seed.direction, seed.target_agent_id, relationships
    )
    risks, uncertainty = _direction_risks(
        seed.direction, danger=danger_bias, safety=safety_bias
    )

    # Belief confidence ≠ subjective outcome probability.
    # Outcome probability blends affordance baseline with danger/safety evidence.
    if seed.direction is ActionDirection.FLEE:
        subjective_probability = _quantize_unit(0.45 + 0.40 * danger_bias)
        confidence = _quantize_unit(base_confidence + 0.30 * danger_bias)
    elif seed.direction in {ActionDirection.DRINK, ActionDirection.EAT}:
        subjective_probability = _quantize_unit(0.70 + 0.20 * safety_bias)
        confidence = _quantize_unit(0.65 + 0.20 * safety_bias)
    elif seed.direction is ActionDirection.WAIT:
        subjective_probability = _quantize_unit(0.80 - 0.35 * danger_bias)
        confidence = _quantize_unit(0.70 - 0.25 * danger_bias + 0.15 * safety_bias)
    elif seed.direction is ActionDirection.MOVE:
        subjective_probability = _quantize_unit(
            0.55 + 0.20 * safety_bias - 0.25 * danger_bias
        )
        confidence = _quantize_unit(0.50 + 0.20 * safety_bias - 0.20 * danger_bias)
    elif seed.direction is ActionDirection.SEARCH:
        subjective_probability = _quantize_unit(0.50 + 0.15 * (1.0 - danger_bias))
        confidence = _quantize_unit(0.45 + 0.20 * (1.0 - danger_bias))
    elif seed.direction is ActionDirection.COMMUNICATE:
        subjective_probability = _quantize_unit(
            0.50 + 0.25 * safety_bias - 0.20 * danger_bias
        )
        confidence = _quantize_unit(0.45 + 0.25 * safety_bias)
    elif seed.direction is ActionDirection.HELP:
        subjective_probability = _quantize_unit(
            0.45 + 0.30 * safety_bias - 0.15 * danger_bias
        )
        confidence = _quantize_unit(0.40 + 0.30 * safety_bias)
    elif seed.direction is ActionDirection.SLEEP:
        subjective_probability = _quantize_unit(0.60 - 0.40 * danger_bias)
        confidence = _quantize_unit(0.55 - 0.30 * danger_bias)
    else:
        subjective_probability = 0.5
        confidence = base_confidence

    confidence = max(0.05, min(1.0, confidence))
    subjective_probability = max(0.05, min(1.0, subjective_probability))

    return ImaginedFuture(
        future_id=seed.future_id,
        claim_codes=seed.claim_codes,
        confidence=confidence,
        direction=seed.direction,
        target_entity_id=seed.target_entity_id,
        target_agent_id=seed.target_agent_id,
        horizon_ticks=1,
        drive_effects=drive_effects,
        goal_effects=goal_effects,
        social_effects=social_effects,
        risks=risks,
        uncertainty=uncertainty,
        subjective_probability=subjective_probability,
        source_refs=FutureSourceRef(
            belief_ids=evidence.belief_ids,
            memory_ids=evidence.memory_ids,
            relationship_ids=evidence.relationship_ids,
        ),
    )


def _physiology_pressures(self_body: ObservedSelf | None) -> dict[str, float]:
    if self_body is None:
        return {"hunger": 0.0, "thirst": 0.0, "fatigue": 0.0, "health_deficit": 0.0}
    return {
        "hunger": _quantize_unit(self_body.hunger.value / 100.0),
        "thirst": _quantize_unit(self_body.thirst.value / 100.0),
        "fatigue": _quantize_unit(self_body.fatigue.value / 100.0),
        "health_deficit": _quantize_unit(1.0 - self_body.health.value / 100.0),
    }


def _direction_drive_effects(
    direction: ActionDirection,
    *,
    physiology: dict[str, float],
    danger: float,
    safety: float,
) -> tuple[DriveEffect, ...]:
    effects: list[DriveEffect] = []

    def add(kind: DriveKind, delta: float, confidence: float = 0.8) -> None:
        effects.append(
            DriveEffect(
                kind=kind,
                delta=_clamp_signed(delta),
                confidence=_quantize_unit(confidence),
            )
        )

    if direction is ActionDirection.DRINK:
        add(DriveKind.THIRST, -0.6 - 0.3 * physiology["thirst"])
        add(DriveKind.SAFETY, 0.1 * safety)
    elif direction is ActionDirection.EAT:
        add(DriveKind.HUNGER, -0.6 - 0.3 * physiology["hunger"])
        add(DriveKind.COMPETENCE, 0.1)
    elif direction is ActionDirection.SLEEP:
        add(DriveKind.FATIGUE, -0.5 - 0.3 * physiology["fatigue"])
        add(DriveKind.SAFETY, -0.2 * danger)
        add(DriveKind.PREDICTABILITY, 0.2)
    elif direction is ActionDirection.FLEE:
        add(DriveKind.SAFETY, 0.5 + 0.4 * danger)
        add(DriveKind.AUTONOMY, 0.2)
        add(DriveKind.BELONGING, -0.1)
        add(DriveKind.PREDICTABILITY, -0.2)
    elif direction is ActionDirection.SEARCH:
        add(DriveKind.CURIOSITY, 0.4)
        add(DriveKind.NOVELTY, 0.3)
        add(DriveKind.COMPETENCE, 0.2)
        add(DriveKind.PREDICTABILITY, -0.1)
    elif direction is ActionDirection.MOVE:
        add(DriveKind.AUTONOMY, 0.3)
        add(DriveKind.NOVELTY, 0.2)
        add(DriveKind.CURIOSITY, 0.2)
        add(DriveKind.SAFETY, 0.15 * safety - 0.2 * danger)
    elif direction is ActionDirection.COMMUNICATE:
        add(DriveKind.BELONGING, 0.4 + 0.2 * safety)
        add(DriveKind.STATUS, 0.2)
        add(DriveKind.SAFETY, 0.1 * safety - 0.2 * danger)
    elif direction is ActionDirection.HELP:
        add(DriveKind.BELONGING, 0.5)
        add(DriveKind.STATUS, 0.3)
        add(DriveKind.COMPETENCE, 0.2)
        add(DriveKind.SAFETY, -0.1 * danger)
    elif direction is ActionDirection.WAIT:
        add(DriveKind.PREDICTABILITY, 0.3)
        add(DriveKind.SAFETY, 0.05 * safety - 0.15 * danger)
        add(DriveKind.NOVELTY, -0.1)
        add(DriveKind.AUTONOMY, -0.05)

    # Canonical DriveKind order, unique.
    by_kind = {effect.kind: effect for effect in effects}
    ordered = tuple(by_kind[kind] for kind in DriveKind if kind in by_kind)
    return ordered


def _direction_goal_effects(
    direction: ActionDirection, goals: tuple[Goal, ...]
) -> tuple[GoalEffect, ...]:
    effects: list[GoalEffect] = []
    for goal in goals:
        outcome = goal.outcome
        if outcome is None:
            continue
        delta = 0.0
        if (
            outcome.kind is GoalOutcomeKind.SATISFY_DRIVE
            and outcome.drive_kind is DriveKind.THIRST
            and direction is ActionDirection.DRINK
        ):
            delta = 0.5
        elif (
            outcome.kind is GoalOutcomeKind.SATISFY_DRIVE
            and outcome.drive_kind is DriveKind.HUNGER
            and direction is ActionDirection.EAT
        ):
            delta = 0.5
        elif (
            outcome.kind is GoalOutcomeKind.SATISFY_DRIVE
            and outcome.drive_kind is DriveKind.FATIGUE
            and direction is ActionDirection.SLEEP
        ):
            delta = 0.4
        elif (
            outcome.kind is GoalOutcomeKind.PRESERVE_LIFE
            and direction is ActionDirection.FLEE
        ):
            delta = 0.4
        elif (
            outcome.kind is GoalOutcomeKind.GATHER_INFORMATION
            and direction is ActionDirection.SEARCH
        ):
            delta = 0.4
        elif (
            outcome.kind is GoalOutcomeKind.REACH_PLACE
            and direction is ActionDirection.MOVE
        ):
            delta = 0.3
        elif outcome.kind is GoalOutcomeKind.RELATE_TO_AGENT and direction in {
            ActionDirection.COMMUNICATE,
            ActionDirection.HELP,
        }:
            delta = 0.35
        elif (
            outcome.kind is GoalOutcomeKind.AVOID_ENTITY
            and direction is ActionDirection.FLEE
        ):
            delta = 0.4
        if delta != 0.0:
            effects.append(
                GoalEffect(
                    goal_id=goal.goal_id,
                    progress_delta=_clamp_signed(delta),
                    confidence=0.7,
                )
            )
    effects.sort(key=lambda item: item.goal_id.value)
    return tuple(effects)


def _direction_social_effects(
    direction: ActionDirection,
    target_agent_id: AgentId | None,
    relationships: tuple[DirectedRelationshipProfile, ...],
) -> tuple[SocialEffect, ...]:
    if direction not in {ActionDirection.COMMUNICATE, ActionDirection.HELP}:
        return ()
    affinity = 0.2 if direction is ActionDirection.COMMUNICATE else 0.35
    if target_agent_id is not None:
        for profile in relationships:
            if profile.target_id == target_agent_id:
                dims = profile.dimension_map()
                affection = dims.get(RelationshipDimension.AFFECTION)
                if affection is not None:
                    affinity = _clamp_signed(affinity + 0.3 * affection.value)
                break
    return (
        SocialEffect(
            counterpart_id=target_agent_id,
            affinity_delta=_clamp_signed(affinity),
            confidence=0.6,
        ),
    )


def _direction_risks(
    direction: ActionDirection, *, danger: float, safety: float
) -> tuple[tuple[SubjectiveRisk, ...], SubjectiveUncertainty]:
    risks: list[SubjectiveRisk] = []

    def add(
        kind: SubjectiveRiskKind, severity: float, likelihood: float, confidence: float
    ) -> None:
        risks.append(
            SubjectiveRisk(
                kind=kind,
                severity=_quantize_unit(severity),
                likelihood=_quantize_unit(likelihood),
                confidence=_quantize_unit(confidence),
            )
        )

    if direction is ActionDirection.FLEE:
        add(SubjectiveRiskKind.PHYSICAL_HARM, 0.3, max(0.1, 0.5 - 0.3 * danger), 0.6)
        add(SubjectiveRiskKind.AUTONOMY_LOSS, 0.1, 0.2, 0.5)
    elif direction is ActionDirection.SLEEP:
        add(
            SubjectiveRiskKind.PHYSICAL_HARM,
            0.4 * danger,
            0.3 + 0.4 * danger,
            0.5 + 0.3 * danger,
        )
    elif direction is ActionDirection.WAIT:
        add(
            SubjectiveRiskKind.PHYSICAL_HARM,
            0.35 * danger,
            0.25 + 0.45 * danger,
            0.5 + 0.3 * danger,
        )
        if danger > 0.0:
            add(SubjectiveRiskKind.GOAL_FORECLOSURE, 0.3 * danger, danger, 0.5)
    elif direction is ActionDirection.MOVE:
        add(
            SubjectiveRiskKind.PHYSICAL_HARM,
            0.25 * danger,
            0.2 + 0.3 * danger,
            0.45,
        )
        add(SubjectiveRiskKind.UNKNOWN, 0.2, 0.3, 0.4)
    elif direction is ActionDirection.SEARCH:
        add(SubjectiveRiskKind.UNKNOWN, 0.25, 0.35, 0.4)
        add(SubjectiveRiskKind.RESOURCE_LOSS, 0.1, 0.15, 0.4)
    elif direction is ActionDirection.COMMUNICATE:
        add(SubjectiveRiskKind.SOCIAL_COST, 0.2 + 0.2 * danger, 0.25, 0.5)
        add(SubjectiveRiskKind.PHYSICAL_HARM, 0.2 * danger, 0.2 * danger, 0.4)
    elif direction is ActionDirection.HELP:
        add(SubjectiveRiskKind.PHYSICAL_HARM, 0.25 * danger, 0.3 * danger, 0.45)
        add(SubjectiveRiskKind.SOCIAL_COST, 0.15, 0.2, 0.4)
    elif direction in {ActionDirection.DRINK, ActionDirection.EAT}:
        add(SubjectiveRiskKind.RESOURCE_LOSS, 0.1, 0.1, 0.5)
        if danger > safety:
            add(SubjectiveRiskKind.PHYSICAL_HARM, 0.2 * danger, 0.2 * danger, 0.4)

    epistemic = _quantize_unit(0.15 + 0.4 * (1.0 - max(danger, safety)))
    aleatory = _quantize_unit(0.1 + 0.3 * danger)
    total = epistemic + aleatory
    if total >= 1.0:
        band = UncertaintyBand.HIGH
    elif total >= 0.45:
        band = UncertaintyBand.MEDIUM
    else:
        band = UncertaintyBand.LOW
    by_kind = {risk.kind: risk for risk in risks}
    ordered = tuple(by_kind[kind] for kind in SubjectiveRiskKind if kind in by_kind)
    return ordered, SubjectiveUncertainty(
        epistemic=epistemic, aleatory=aleatory, band=band
    )
