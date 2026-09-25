"""Versioned multi-criteria intention selection and command planning (V1).

No permanent total reward. Feasibility gates, critical vetoes, Pareto filtering,
pairwise comparison, and documented stable tie-breaks select one future; the
planner compiles it into exactly one fresh closed ``AgentCommand``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Final

from agents.cognition.models import (
    ActionDirection,
    ActionPlan,
    CognitiveLoopInput,
    DecisionMetadata,
    EmotionalStateEvaluation,
    FutureAppraisal,
    GoalBoard,
    ImaginedFuture,
    IntentionCode,
    MotivationCode,
    MotivationEvaluation,
    PossibleFutures,
    RetrievedMemoryContext,
    SelectedIntention,
    SelfModel,
    SubjectiveRiskKind,
    SubjectiveSnapshot,
    intention_for_action_direction,
    require_confidence,
)
from agents.models import AgentId, DriveKind
from world.actions import (
    AgentCommand,
    Ask,
    Drink,
    Eat,
    Flee,
    Help,
    Move,
    Search,
    Sleep,
    Talk,
    Tell,
    Wait,
)
from world.communications import (
    observation_allows_communication_target,
)
from world.identifiers import EntityId
from world.observations import CONTENT_VISIBILITY_THRESHOLD, Observation
from world.values import ItemKind, ResourceKind

__all__ = [
    "DELIBERATION_POLICY_VERSION",
    "PLANNER_POLICY_VERSION",
    "SAFE_SOCIAL_PHRASE",
    "CommandPlanner",
    "MultiCriteriaIntentionSelector",
]

DELIBERATION_POLICY_VERSION: Final[str] = "deliberation.v1"
PLANNER_POLICY_VERSION: Final[str] = "planner.v1"
SAFE_SOCIAL_PHRASE: Final[str] = "hello"
_CRITICAL_NEED: Final[float] = 0.75
_CRITICAL_HARM: Final[float] = 0.55
_EFFECT_QUANTUM: Final[float] = 1e-6
_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.deliberation")

# Need-reduction drives: negative deltas are beneficial (relief).
_RELIEF_DRIVES: Final[frozenset[DriveKind]] = frozenset(
    {DriveKind.HUNGER, DriveKind.THIRST, DriveKind.FATIGUE}
)

# Stable direction priority used only as final tie-break (lower wins).
_DIRECTION_TIE_RANK: Final[Mapping[ActionDirection, int]] = {
    ActionDirection.FLEE: 0,
    ActionDirection.DRINK: 1,
    ActionDirection.EAT: 2,
    ActionDirection.SLEEP: 3,
    ActionDirection.HELP: 4,
    ActionDirection.COMMUNICATE: 5,
    ActionDirection.MOVE: 6,
    ActionDirection.SEARCH: 7,
    ActionDirection.WAIT: 8,
    ActionDirection.ATTACK: 9,
}

_TIE_BREAK_DIRECTION: Final[str] = "direction_rank"
_TIE_BREAK_FUTURE_ID: Final[str] = "future_id"
_TIE_BREAK_NONE: Final[str] = "none"


def _quantize_unit(value: float) -> float:
    steps = round(value / _EFFECT_QUANTUM)
    quantized = steps * _EFFECT_QUANTUM
    if quantized < 0.0:
        quantized = 0.0
    elif quantized > 1.0:
        quantized = 1.0
    return 0.0 if quantized == 0.0 else quantized


class MultiCriteriaIntentionSelector:
    """Select one intention via feasibility, vetoes, Pareto, and pairwise votes."""

    __slots__ = ()

    async def select(
        self,
        loop_input: CognitiveLoopInput,
        motivation: MotivationEvaluation,
        futures: PossibleFutures,
        goal_board: GoalBoard | None = None,
        emotional_state: EmotionalStateEvaluation | None = None,
        self_state: SelfModel | None = None,
    ) -> SelectedIntention:
        owner = loop_input.agent_id
        tick = loop_input.observation.tick
        appraisals = motivation.appraisals
        _LOG.debug(
            "deliberation_start",
            extra={
                "cognition": {
                    "owner_id": owner.value,
                    "tick": tick,
                    "policy_version": DELIBERATION_POLICY_VERSION,
                    "candidate_count": len(appraisals),
                    "foci_count": 0 if goal_board is None else len(goal_board.foci_ids),
                    "status": "start",
                }
            },
        )

        futures_by_id = {future.future_id: future for future in futures.futures}
        before = len(appraisals)
        feasible = _feasibility_filter(
            appraisals, futures_by_id, loop_input.observation
        )
        after_feasibility = len(feasible)
        if not feasible:
            _LOG.warning(
                "deliberation_no_feasible",
                extra={
                    "cognition": {
                        "owner_id": owner.value,
                        "tick": tick,
                        "policy_version": DELIBERATION_POLICY_VERSION,
                        "reason_code": "no_feasible_candidate",
                        "candidate_count_before": before,
                    }
                },
            )
            return _wait_intention(owner, motivation, tie_break=_TIE_BREAK_NONE)

        surviving = _critical_vetoes(
            feasible, futures_by_id, loop_input.observation, motivation
        )
        after_veto = len(surviving)
        if not surviving:
            surviving = feasible

        focus_supported = _prefer_goal_focus_support(
            surviving, futures_by_id, goal_board
        )
        if focus_supported:
            surviving = focus_supported

        from agents.cognition.emotion_bias import prefer_emotion_directions

        emotion_code: str | None = None
        preferred, emotion_code = prefer_emotion_directions(
            tuple(
                futures_by_id[item.future_id].direction
                for item in surviving
                if item.future_id in futures_by_id
            ),
            emotional_state,
        )
        if preferred is not None:
            emotion_filtered = [
                item
                for item in surviving
                if item.future_id in futures_by_id
                and futures_by_id[item.future_id].direction in preferred
            ]
            if emotion_filtered:
                surviving = emotion_filtered

        undominated = _pareto_filter(surviving, futures_by_id, motivation)
        after_pareto = len(undominated)
        if not undominated:
            undominated = surviving

        identity_costs = _identity_direction_costs(
            owner=owner,
            identity=None if self_state is None else self_state.identity,
            goals=() if goal_board is None else goal_board.goals,
            futures=futures,
        )
        winner, tie_break = _pairwise_select(
            undominated, futures_by_id, motivation, identity_costs
        )
        future = futures_by_id.get(winner.future_id)
        direction = ActionDirection.WAIT if future is None else future.direction
        intention = intention_for_action_direction(direction)
        confidence = _selection_confidence(winner, future)
        selection_codes = [
            f"direction:{direction.value}",
            f"future:{winner.future_id}",
            f"tie:{tie_break}",
        ]
        if emotion_code is not None:
            selection_codes.append(emotion_code)
        if goal_board is not None and goal_board.foci_ids and future is not None:
            focus_ids = set(goal_board.foci_ids)
            if any(effect.goal_id in focus_ids for effect in future.goal_effects):
                selection_codes.append("goal_focus_support")

        result = SelectedIntention(
            owner_id=owner,
            intention=intention,
            source_motive=_motive_for_direction(direction),
            confidence=confidence,
            decision_metadata=DecisionMetadata(
                selection_codes=tuple(selection_codes),
                candidate_count=before,
                tie_break_applied=tie_break != _TIE_BREAK_NONE,
            ),
            selected_future_id=winner.future_id,
            direction=direction,
            appraisal_future_ids=tuple(item.future_id for item in undominated),
        )
        _LOG.debug(
            "deliberation_complete",
            extra={
                "cognition": {
                    "owner_id": owner.value,
                    "tick": tick,
                    "policy_version": DELIBERATION_POLICY_VERSION,
                    "candidate_count_before": before,
                    "candidate_count_after_feasibility": after_feasibility,
                    "candidate_count_after_veto": after_veto,
                    "candidate_count_after_pareto": after_pareto,
                    "selected_direction": direction.value,
                    "selected_future_id": winner.future_id,
                    "tie_break_code": tie_break,
                    "status": "complete",
                }
            },
        )
        if identity_costs is not None:
            from agents.cognition.identity import identity_stability_band

            _LOG.debug(
                "identity_violation_cost",
                extra={
                    "owner_id": owner.value,
                    "tick": tick,
                    "candidate_count": len(undominated),
                    "winning_direction": direction.value,
                    "cost_band": identity_stability_band(
                        identity_costs.get(winner.future_id, 0.0)
                    ),
                    "identity_vote": _identity_vote_for_winner(
                        winner.future_id, undominated, identity_costs
                    ),
                },
            )
        return result


class CommandPlanner:
    """Compile selected direction+target into one fresh closed AgentCommand."""

    __slots__ = ("_social_messages",)

    def __init__(self, social_messages: object | None = None) -> None:
        from agents.cognition.communication import DeterministicSocialMessagePolicy

        if social_messages is None:
            social_messages = DeterministicSocialMessagePolicy()
        self._social_messages = social_messages

    async def plan(
        self,
        loop_input: CognitiveLoopInput,
        intention: SelectedIntention,
        futures: PossibleFutures,
        memory: RetrievedMemoryContext | None = None,
        goal_board: GoalBoard | None = None,
        emotional_state: EmotionalStateEvaluation | None = None,
    ) -> ActionPlan:
        _ = goal_board
        owner = loop_input.agent_id
        tick = loop_input.observation.tick
        future = _resolve_future(intention, futures)
        command: AgentCommand = Wait()
        command_type = "Wait"
        used_fallback = False

        if future is None or intention.direction is None:
            used_fallback = True
            _LOG.warning(
                "planner_fallback",
                extra={
                    "cognition": {
                        "owner_id": owner.value,
                        "tick": tick,
                        "policy_version": PLANNER_POLICY_VERSION,
                        "reason_code": "missing_future",
                    }
                },
            )
        else:
            compiled = _compile_command(
                future,
                loop_input.observation,
                owner_id=owner,
                memory=memory,
                social_messages=self._social_messages,
                snapshot=loop_input.snapshot,
                emotional_state=emotional_state,
            )
            if compiled is None:
                used_fallback = True
                _LOG.warning(
                    "planner_fallback",
                    extra={
                        "cognition": {
                            "owner_id": owner.value,
                            "tick": tick,
                            "policy_version": PLANNER_POLICY_VERSION,
                            "reason_code": "target_unavailable",
                            "direction": future.direction.value,
                        }
                    },
                )
            else:
                command = compiled
                command_type = type(command).__name__

        if type(command) not in {
            Wait,
            Drink,
            Eat,
            Sleep,
            Flee,
            Search,
            Move,
            Talk,
            Ask,
            Tell,
            Help,
        }:
            _LOG.error(
                "planner_invalid_output",
                extra={
                    "cognition": {
                        "owner_id": owner.value,
                        "tick": tick,
                        "policy_version": PLANNER_POLICY_VERSION,
                        "reason_code": "invalid_command_type",
                        "command_type": type(command).__name__,
                    }
                },
            )
            command = Wait()
            command_type = "Wait"
            used_fallback = True

        confidence = intention.confidence if not used_fallback else 1.0
        plan = ActionPlan(
            owner_id=owner,
            command=command,
            confidence=require_confidence("ActionPlan.confidence", confidence),
            decision_metadata=DecisionMetadata(
                selection_codes=(command_type.lower(), PLANNER_POLICY_VERSION),
                candidate_count=1,
            ),
        )
        band = (
            "high" if confidence >= 0.75 else "medium" if confidence >= 0.4 else "low"
        )
        _LOG.debug(
            "planner_complete",
            extra={
                "cognition": {
                    "owner_id": owner.value,
                    "tick": tick,
                    "policy_version": PLANNER_POLICY_VERSION,
                    "command_type": command_type,
                    "confidence_band": band,
                    "fallback": used_fallback,
                    "status": "complete",
                }
            },
        )
        return plan


def _drive_utility(kind: DriveKind, delta: float) -> float:
    """Map signed drive deltas onto a higher-is-better utility."""
    if kind in _RELIEF_DRIVES:
        return -delta
    return delta


def _feasibility_filter(
    appraisals: Sequence[FutureAppraisal],
    futures_by_id: Mapping[str, ImaginedFuture],
    observation: Observation,
) -> list[FutureAppraisal]:
    result: list[FutureAppraisal] = []
    for appraisal in appraisals:
        future = futures_by_id.get(appraisal.future_id)
        if future is None:
            continue
        if _is_feasible(future.direction, future.target_entity_id, observation):
            result.append(appraisal)
    return result


def _is_feasible(
    direction: ActionDirection,
    target_entity_id: str | None,
    observation: Observation,
) -> bool:
    self_body = observation.self_body
    if direction is ActionDirection.WAIT:
        return True
    if self_body is None:
        return False
    if direction is ActionDirection.SLEEP:
        return True
    if direction is ActionDirection.SEARCH:
        return True
    if direction is ActionDirection.DRINK:
        return _has_water(observation, target_entity_id)
    if direction is ActionDirection.EAT:
        return _has_food(observation, target_entity_id)
    if direction is ActionDirection.MOVE:
        if target_entity_id is None:
            return False
        return any(
            exit_item.destination_id.value == target_entity_id
            for exit_item in observation.exits
        )
    if direction is ActionDirection.FLEE:
        return True
    if direction is ActionDirection.COMMUNICATE:
        return _has_communication_target(observation, target_entity_id)
    if direction is ActionDirection.HELP:
        return _has_social_target(observation, target_entity_id)
    if direction is ActionDirection.ATTACK:
        return _has_social_target(observation, target_entity_id)
    return False


def _has_water(observation: Observation, target_entity_id: str | None) -> bool:
    for resource in observation.resources:
        if resource.kind is ResourceKind.WATER and resource.quantity > 0.0:
            if target_entity_id is None or resource.entity_id.value == target_entity_id:
                return True
    for item in observation.items:
        if item.kind is ItemKind.WATER:
            if target_entity_id is None or item.entity_id.value == target_entity_id:
                return True
    return False


def _has_food(observation: Observation, target_entity_id: str | None) -> bool:
    for resource in observation.resources:
        if resource.kind is ResourceKind.FOOD and resource.quantity > 0.0:
            if target_entity_id is None or resource.entity_id.value == target_entity_id:
                return True
    for item in observation.items:
        if item.kind is ItemKind.FOOD:
            if target_entity_id is None or item.entity_id.value == target_entity_id:
                return True
    return False


def _has_communication_target(
    observation: Observation, target_entity_id: str | None
) -> bool:
    """Feasibility aligned with world communication eligibility (no private import)."""
    if target_entity_id is None:
        return any(
            observation_allows_communication_target(
                visibility=observation.visibility,
                visible_body_ids=tuple(
                    body.entity_id for body in observation.visible_bodies
                ),
                recipient_id=body.entity_id,
                visibility_threshold=CONTENT_VISIBILITY_THRESHOLD,
            )
            for body in observation.visible_bodies
        )
    recipient = EntityId(target_entity_id)
    return observation_allows_communication_target(
        visibility=observation.visibility,
        visible_body_ids=tuple(body.entity_id for body in observation.visible_bodies),
        recipient_id=recipient,
        visibility_threshold=CONTENT_VISIBILITY_THRESHOLD,
    )


def _has_social_target(observation: Observation, target_entity_id: str | None) -> bool:
    body_ids = {body.entity_id.value for body in observation.visible_bodies}
    if target_entity_id is not None:
        if target_entity_id in body_ids:
            return True
        return any(
            message.speaker_id.value == target_entity_id
            for message in observation.communications
        )
    return bool(observation.visible_bodies) or bool(observation.communications)


def _prefer_goal_focus_support(
    appraisals: list[FutureAppraisal],
    futures_by_id: dict[str, ImaginedFuture],
    goal_board: GoalBoard | None,
) -> list[FutureAppraisal]:
    """Narrow to futures that advance CURRENT_INTENTION foci when any exist."""

    if goal_board is None or not goal_board.foci_ids:
        return []
    focus_ids = set(goal_board.foci_ids)
    supported: list[FutureAppraisal] = []
    for appraisal in appraisals:
        future = futures_by_id.get(appraisal.future_id)
        if future is None:
            continue
        if any(
            effect.goal_id in focus_ids and effect.progress_delta > 0.0
            for effect in future.goal_effects
        ):
            supported.append(appraisal)
        elif any(effect.goal_id in focus_ids for effect in appraisal.goal_effects):
            if any(e.progress_delta > 0.0 for e in appraisal.goal_effects):
                supported.append(appraisal)
    return supported


def _critical_vetoes(
    appraisals: Sequence[FutureAppraisal],
    futures_by_id: Mapping[str, ImaginedFuture],
    observation: Observation,
    motivation: MotivationEvaluation,
) -> list[FutureAppraisal]:
    self_body = observation.self_body
    thirst = 0.0 if self_body is None else self_body.thirst.value / 100.0
    hunger = 0.0 if self_body is None else self_body.hunger.value / 100.0
    fatigue = 0.0 if self_body is None else self_body.fatigue.value / 100.0
    health_deficit = 0.0 if self_body is None else 1.0 - self_body.health.value / 100.0
    safety_active = DriveKind.SAFETY in motivation.active_drive_kinds

    surviving: list[FutureAppraisal] = []
    for appraisal in appraisals:
        future = futures_by_id[appraisal.future_id]
        harm = _harm_score(appraisal)
        # Critical safety: veto waiting/sleeping under high subjective harm when flee exists.  # noqa: E501
        if (
            safety_active
            and harm >= _CRITICAL_HARM
            and future.direction in {ActionDirection.WAIT, ActionDirection.SLEEP}
            and any(
                futures_by_id[item.future_id].direction is ActionDirection.FLEE
                for item in appraisals
            )
        ):
            continue
        # Critical need: veto exploration when drink/eat urgently available.
        if thirst >= _CRITICAL_NEED and future.direction in {
            ActionDirection.WAIT,
            ActionDirection.SEARCH,
            ActionDirection.MOVE,
            ActionDirection.COMMUNICATE,
            ActionDirection.SLEEP,
        }:
            if any(
                futures_by_id[item.future_id].direction is ActionDirection.DRINK
                for item in appraisals
            ):
                continue
        if hunger >= _CRITICAL_NEED and future.direction in {
            ActionDirection.WAIT,
            ActionDirection.SEARCH,
            ActionDirection.MOVE,
            ActionDirection.COMMUNICATE,
            ActionDirection.SLEEP,
        }:
            if any(
                futures_by_id[item.future_id].direction is ActionDirection.EAT
                for item in appraisals
            ):
                continue
        if fatigue >= _CRITICAL_NEED and future.direction is ActionDirection.SEARCH:
            if any(
                futures_by_id[item.future_id].direction is ActionDirection.SLEEP
                for item in appraisals
            ):
                continue
        if (
            health_deficit >= _CRITICAL_NEED
            and future.direction is ActionDirection.HELP
        ):
            continue
        surviving.append(appraisal)
    return surviving


def _harm_score(appraisal: FutureAppraisal) -> float:
    harm = 0.0
    for risk in appraisal.risks:
        if risk.kind is SubjectiveRiskKind.PHYSICAL_HARM:
            harm = max(harm, risk.severity * risk.likelihood)
    if appraisal.mortality is not None:
        harm = max(harm, appraisal.mortality.death_probability)
    return _quantize_unit(harm)


def _pareto_filter(
    appraisals: Sequence[FutureAppraisal],
    futures_by_id: Mapping[str, ImaginedFuture],
    motivation: MotivationEvaluation,
) -> list[FutureAppraisal]:
    vectors = [
        (appraisal, _effect_vector(appraisal, futures_by_id, motivation))
        for appraisal in appraisals
    ]
    undominated: list[FutureAppraisal] = []
    for index, (candidate, vector) in enumerate(vectors):
        dominated = False
        for other_index, (_other, other_vector) in enumerate(vectors):
            if other_index == index:
                continue
            if _dominates(other_vector, vector):
                dominated = True
                break
        if not dominated:
            undominated.append(candidate)
    return undominated


def _effect_vector(
    appraisal: FutureAppraisal,
    futures_by_id: Mapping[str, ImaginedFuture],
    motivation: MotivationEvaluation,
) -> tuple[float, ...]:
    """Independent criteria vector: higher is better on every component."""
    active = set(motivation.active_drive_kinds)
    drive_map = {effect.kind: effect.delta for effect in appraisal.drive_effects}
    drive_scores = tuple(
        _drive_utility(kind, drive_map.get(kind, 0.0)) if kind in active else 0.0
        for kind in DriveKind
    )
    goal_support = float(appraisal.support_goal_count)
    social_support = float(appraisal.support_social_count)
    harm = -_harm_score(appraisal)
    mortality = 0.0 if appraisal.mortality is None else -appraisal.mortality.composite
    uncertainty = -(appraisal.uncertainty.epistemic + appraisal.uncertainty.aleatory)
    future = futures_by_id.get(appraisal.future_id)
    confidence = 0.0 if future is None else future.confidence
    return (
        *drive_scores,
        goal_support,
        social_support,
        harm,
        mortality,
        uncertainty,
        confidence,
    )


def _dominates(left: tuple[float, ...], right: tuple[float, ...]) -> bool:
    if len(left) != len(right):
        return False
    strictly_better = False
    for a, b in zip(left, right, strict=True):
        if a < b:
            return False
        if a > b:
            strictly_better = True
    return strictly_better


def _identity_direction_costs(
    *,
    owner: AgentId,
    identity: object | None,
    goals: Sequence[object],
    futures: PossibleFutures,
) -> dict[str, float] | None:
    from agents.cognition.identity import IdentityState, identity_violation_cost
    from agents.models import Goal

    if identity is None:
        return None
    if type(identity) is not IdentityState:
        raise TypeError("identity_violation_cost.identity: invalid_type")
    if identity.owner_id != owner:
        _LOG.error(
            "identity_violation_cost_rejected",
            extra={"reason_code": "owner_mismatch", "owner_id": owner.value},
        )
        raise ValueError("identity_violation_cost: owner_mismatch")
    owned_goals = tuple(goal for goal in goals if type(goal) is Goal)
    costs: dict[str, float] = {}
    for future in futures.futures:
        costs[future.future_id] = identity_violation_cost(
            owner_id=owner,
            direction=future.direction.value,
            identity=identity,
            goals=owned_goals,
            futures=futures,
        )
    return costs


def _identity_vote_for_winner(
    winner_id: str,
    appraisals: Sequence[FutureAppraisal],
    costs: Mapping[str, float],
) -> int:
    votes: list[int] = []
    winner_cost = costs.get(winner_id, 0.0)
    for item in appraisals:
        if item.future_id == winner_id:
            continue
        other = costs.get(item.future_id, 0.0)
        if winner_cost < other:
            votes.append(1)
        elif winner_cost > other:
            votes.append(-1)
        else:
            votes.append(0)
    if not votes or any(vote != votes[0] for vote in votes):
        return 0
    return votes[0]


def _pairwise_select(
    appraisals: Sequence[FutureAppraisal],
    futures_by_id: Mapping[str, ImaginedFuture],
    motivation: MotivationEvaluation,
    identity_costs: Mapping[str, float] | None = None,
) -> tuple[FutureAppraisal, str]:
    if len(appraisals) == 1:
        return appraisals[0], _TIE_BREAK_NONE

    scores: dict[str, int] = {item.future_id: 0 for item in appraisals}
    for index, left in enumerate(appraisals):
        for right in appraisals[index + 1 :]:
            cmp = _pairwise_compare(
                left, right, futures_by_id, motivation, identity_costs
            )
            if cmp > 0:
                scores[left.future_id] += 1
            elif cmp < 0:
                scores[right.future_id] += 1

    best_score = max(scores.values())
    contenders = [item for item in appraisals if scores[item.future_id] == best_score]
    if len(contenders) == 1:
        return contenders[0], _TIE_BREAK_NONE

    # Tie-break 1: direction rank.
    contenders.sort(
        key=lambda item: (
            _DIRECTION_TIE_RANK.get(futures_by_id[item.future_id].direction, 99),
            item.future_id,
        )
    )
    first = contenders[0]
    second = contenders[1]
    first_dir = futures_by_id[first.future_id].direction
    second_dir = futures_by_id[second.future_id].direction
    if first_dir != second_dir:
        return first, _TIE_BREAK_DIRECTION
    return first, _TIE_BREAK_FUTURE_ID


def _pairwise_compare(
    left: FutureAppraisal,
    right: FutureAppraisal,
    futures_by_id: Mapping[str, ImaginedFuture],
    motivation: MotivationEvaluation,
    identity_costs: Mapping[str, float] | None = None,
) -> int:
    """Return positive if left preferred, negative if right preferred, else 0."""
    active_drives = set(motivation.active_drive_kinds)
    left_drives = {effect.kind: effect for effect in left.drive_effects}
    right_drives = {effect.kind: effect for effect in right.drive_effects}
    drive_votes = 0
    for kind in DriveKind:
        if kind not in active_drives:
            continue
        left_delta = (
            0.0
            if kind not in left_drives
            else _drive_utility(kind, left_drives[kind].delta)
        )
        right_delta = (
            0.0
            if kind not in right_drives
            else _drive_utility(kind, right_drives[kind].delta)
        )
        if left_delta > right_delta:
            drive_votes += 1
        elif right_delta > left_delta:
            drive_votes -= 1

    goal_votes = left.support_goal_count - right.support_goal_count
    social_votes = left.support_social_count - right.support_social_count
    risk_votes = 0
    left_harm = _harm_score(left)
    right_harm = _harm_score(right)
    if left_harm < right_harm:
        risk_votes += 1
    elif right_harm < left_harm:
        risk_votes -= 1
    left_mort = 0.0 if left.mortality is None else left.mortality.composite
    right_mort = 0.0 if right.mortality is None else right.mortality.composite
    if left_mort < right_mort:
        risk_votes += 1
    elif right_mort < left_mort:
        risk_votes -= 1

    left_unc = left.uncertainty.epistemic + left.uncertainty.aleatory
    right_unc = right.uncertainty.epistemic + right.uncertainty.aleatory
    unc_votes = 0
    # Prefer lower uncertainty when predictability is active; prefer novelty otherwise.
    if (
        DriveKind.PREDICTABILITY in active_drives
        and DriveKind.NOVELTY not in active_drives
    ):
        if left_unc < right_unc:
            unc_votes += 1
        elif right_unc < left_unc:
            unc_votes -= 1
    elif (
        DriveKind.NOVELTY in active_drives
        and DriveKind.PREDICTABILITY not in active_drives
    ):
        if left_unc > right_unc:
            unc_votes += 1
        elif right_unc > left_unc:
            unc_votes -= 1

    left_future = futures_by_id.get(left.future_id)
    right_future = futures_by_id.get(right.future_id)
    conf_votes = 0
    if left_future is not None and right_future is not None:
        if left_future.confidence > right_future.confidence:
            conf_votes += 1
        elif right_future.confidence > left_future.confidence:
            conf_votes -= 1

    identity_vote = 0
    if identity_costs is not None:
        left_cost = identity_costs.get(left.future_id, 0.0)
        right_cost = identity_costs.get(right.future_id, 0.0)
        if left_cost < right_cost:
            identity_vote = 1
        elif right_cost < left_cost:
            identity_vote = -1
    total = (
        drive_votes
        + goal_votes
        + social_votes
        + risk_votes
        + unc_votes
        + conf_votes
        + identity_vote
    )
    if total > 0:
        return 1
    if total < 0:
        return -1
    return 0


def _selection_confidence(
    appraisal: FutureAppraisal, future: ImaginedFuture | None
) -> float:
    base = 0.5 if future is None else future.confidence
    support = (
        0.05 * appraisal.support_drive_count
        + 0.08 * appraisal.support_goal_count
        + 0.05 * appraisal.support_social_count
    )
    return require_confidence(
        "SelectedIntention.confidence",
        _quantize_unit(min(1.0, base + support)),
    )


def _motive_for_direction(direction: ActionDirection) -> MotivationCode:
    mapping = {
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
    return mapping.get(direction, MotivationCode.WAIT)


def _wait_intention(
    owner: object,
    motivation: MotivationEvaluation,
    *,
    tie_break: str,
) -> SelectedIntention:
    from agents.models import AgentId

    assert type(owner) is AgentId
    return SelectedIntention(
        owner_id=owner,
        intention=IntentionCode.WAIT,
        source_motive=MotivationCode.WAIT,
        confidence=1.0,
        decision_metadata=DecisionMetadata(
            selection_codes=(
                f"direction:{ActionDirection.WAIT.value}",
                f"tie:{tie_break}",
            ),
            candidate_count=len(motivation.appraisals),
            tie_break_applied=False,
        ),
        selected_future_id=None,
        direction=ActionDirection.WAIT,
        appraisal_future_ids=tuple(item.future_id for item in motivation.appraisals),
    )


def _resolve_future(
    intention: SelectedIntention, futures: PossibleFutures
) -> ImaginedFuture | None:
    if intention.selected_future_id is not None:
        for future in futures.futures:
            if future.future_id == intention.selected_future_id:
                return future
    if intention.direction is not None:
        matches = [
            future
            for future in futures.futures
            if future.direction is intention.direction
        ]
        if matches:
            return sorted(matches, key=lambda item: item.future_id)[0]
    return None


def _compile_command(
    future: ImaginedFuture,
    observation: Observation,
    *,
    owner_id: AgentId,
    memory: RetrievedMemoryContext | None = None,
    social_messages: object | None = None,
    snapshot: SubjectiveSnapshot | None = None,
    emotional_state: EmotionalStateEvaluation | None = None,
) -> AgentCommand | None:
    direction = future.direction
    target = future.target_entity_id
    if direction is ActionDirection.WAIT:
        return Wait()
    if direction is ActionDirection.SLEEP:
        return Sleep()
    if direction is ActionDirection.SEARCH:
        target_id = None if target is None else EntityId(target)
        if (
            target_id is not None
            and not any(item.entity_id == target_id for item in observation.items)
            and not any(
                resource.entity_id == target_id for resource in observation.resources
            )
        ):
            target_id = None
        return Search(target_id=target_id)
    if direction is ActionDirection.DRINK:
        source = _resolve_entity(target, observation, kind="water")
        if source is None:
            return None
        return Drink(source_id=source)
    if direction is ActionDirection.EAT:
        source = _resolve_entity(target, observation, kind="food")
        if source is None:
            return None
        return Eat(item_id=source)
    if direction is ActionDirection.MOVE:
        if target is None:
            return None
        destination = EntityId(target)
        if not any(
            exit_item.destination_id == destination for exit_item in observation.exits
        ):
            return None
        return Move(destination_id=destination)
    if direction is ActionDirection.FLEE:
        threat = None if target is None else EntityId(target)
        if threat is not None and not any(
            body.entity_id == threat for body in observation.visible_bodies
        ):
            threat = None
        return Flee(threat_id=threat)
    if direction is ActionDirection.COMMUNICATE:
        from agents.cognition.communication import DeterministicSocialMessagePolicy

        preferred = None if target is None else EntityId(target)
        speaker = (
            observation.self_body.entity_id
            if observation.self_body is not None
            else observation.observer_id
        )
        policy = social_messages
        if policy is None:
            policy = DeterministicSocialMessagePolicy()
        empty_memory = RetrievedMemoryContext(
            owner_id=owner_id,
            memory_ids=(),
            belief_ids=(),
            confidence=1.0,
            decision_metadata=DecisionMetadata(candidate_count=0),
            semantic_beliefs=(() if snapshot is None else snapshot.semantic_beliefs),
        )
        memory_ctx = empty_memory if memory is None else memory
        if (
            memory is not None
            and snapshot is not None
            and not memory.semantic_beliefs
            and snapshot.semantic_beliefs
        ):
            memory_ctx = RetrievedMemoryContext(
                owner_id=memory.owner_id,
                memory_ids=memory.memory_ids,
                belief_ids=memory.belief_ids,
                confidence=memory.confidence,
                decision_metadata=memory.decision_metadata,
                semantic_beliefs=snapshot.semantic_beliefs,
                reconstructions=memory.reconstructions,
                ranked_hits=memory.ranked_hits,
                pending_accesses=memory.pending_accesses,
                reconsolidation=memory.reconsolidation,
                reconstruction_policy_version=memory.reconstruction_policy_version,
            )
        select = getattr(policy, "select", None)
        if select is None:
            return None
        decision = select(
            owner_id=owner_id,
            speaker_id=speaker,
            observation=observation,
            memory=memory_ctx,
            preferred_recipient_id=preferred,
            snapshot_memories=(() if snapshot is None else snapshot.memories),
            emotional_state=emotional_state,
        )
        if decision is None:
            return None
        return decision.command
    if direction is ActionDirection.HELP:
        helped = _resolve_social_entity(target, observation)
        if helped is None:
            return None
        return Help(target_id=helped)
    return None


def _resolve_entity(
    target: str | None, observation: Observation, *, kind: str
) -> EntityId | None:
    wanted = ResourceKind.WATER if kind == "water" else ResourceKind.FOOD
    item_kind = ItemKind.WATER if kind == "water" else ItemKind.FOOD
    if target is not None:
        entity = EntityId(target)
        for resource in observation.resources:
            if resource.entity_id == entity and resource.kind is wanted:
                return entity
        for item in observation.items:
            if item.entity_id == entity and item.kind is item_kind:
                return entity
        return None
    for resource in sorted(
        observation.resources, key=lambda item: item.entity_id.value
    ):
        if resource.kind is wanted and resource.quantity > 0.0:
            return resource.entity_id
    for item in sorted(observation.items, key=lambda entry: entry.entity_id.value):
        if item.kind is item_kind:
            return item.entity_id
    return None


def _resolve_visible_body(
    target: str | None, observation: Observation
) -> EntityId | None:
    if target is not None:
        entity = EntityId(target)
        if any(body.entity_id == entity for body in observation.visible_bodies):
            if observation_allows_communication_target(
                visibility=observation.visibility,
                visible_body_ids=tuple(
                    body.entity_id for body in observation.visible_bodies
                ),
                recipient_id=entity,
                visibility_threshold=CONTENT_VISIBILITY_THRESHOLD,
            ):
                return entity
        return None
    bodies = sorted(observation.visible_bodies, key=lambda body: body.entity_id.value)
    for body in bodies:
        if observation_allows_communication_target(
            visibility=observation.visibility,
            visible_body_ids=tuple(
                item.entity_id for item in observation.visible_bodies
            ),
            recipient_id=body.entity_id,
            visibility_threshold=CONTENT_VISIBILITY_THRESHOLD,
        ):
            return body.entity_id
    return None


def _resolve_social_entity(
    target: str | None, observation: Observation
) -> EntityId | None:
    if target is not None:
        entity = EntityId(target)
        if any(body.entity_id == entity for body in observation.visible_bodies):
            return entity
        if any(message.speaker_id == entity for message in observation.communications):
            return entity
        return None
    bodies = sorted(observation.visible_bodies, key=lambda body: body.entity_id.value)
    if bodies:
        return bodies[0].entity_id
    messages = sorted(
        observation.communications, key=lambda message: message.speaker_id.value
    )
    if messages:
        return messages[0].speaker_id
    return None
