"""Hierarchical goal management policy and cognition-local goal IDs.

Production policy version ``goals.v1`` maintains owner-scoped boards without
importing ``simulation`` or collapsing motivations into a scalar utility.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final

from agents.cognition.models import (
    CognitiveLoopInput,
    DecisionMetadata,
    GoalBoard,
    GoalTransitionIntent,
    GoalTransitionIntentReason,
    RetrievedMemoryContext,
    SelfModel,
    SituationModel,
    SubjectiveSnapshot,
)
from agents.models import (
    AgentId,
    DriveKind,
    Goal,
    GoalHorizon,
    GoalId,
    GoalOriginKind,
    GoalOutcome,
    GoalOutcomeKind,
    GoalProgress,
    GoalProvenance,
    GoalRelationEdge,
    GoalRelationKind,
    GoalStatus,
)
from world.observations import Observation

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.goal_manager")

GOAL_POLICY_VERSION: Final[str] = "goals.v1"
_GOAL_ID_PREFIX: Final[str] = "cg-"
_GOAL_ID_DIGEST_CHARS: Final[int] = 48
_MAX_FOCI: Final[int] = 8
_MAX_BOARD_GOALS: Final[int] = 64
_CRITICAL_NEED: Final[float] = 0.75
_REINFORCE_PROGRESS_STEP: Final[float] = 0.05
_REINFORCE_CONFIDENCE_BLEND: Final[float] = 0.1
_FAIL_PROGRESS_PENALTY: Final[float] = 0.05
_FAIL_CONFIDENCE_PENALTY: Final[float] = 0.05
_FOCUS_TEMPLATE_CODE: Final[str] = "current_intention.v1"
_TERMINAL_PARENT_STATUSES: Final[frozenset[GoalStatus]] = frozenset(
    {GoalStatus.FAILED, GoalStatus.ABANDONED}
)
_ABANDONABLE_STATUSES: Final[frozenset[GoalStatus]] = frozenset(
    {GoalStatus.ACTIVE, GoalStatus.SUSPENDED}
)
_ABSENCE_MARKERS: Final[frozenset[str]] = frozenset(
    (
        "absent",
        "missing",
        "impossible",
        "unavailable",
        "gone",
        "depleted",
        "resource_impossible",
        "place_absent",
    )
)

__all__ = [
    "GOAL_POLICY_VERSION",
    "HierarchicalGoalManager",
    "PassthroughGoalManager",
    "derive_cognition_goal_id",
]


def derive_cognition_goal_id(
    *,
    owner_id: str,
    tick: int,
    parent_goal_id: str | None,
    template_code: str,
    ordinal: int,
) -> GoalId:
    """Build a stable cognition-local ``GoalId`` without importing simulation."""

    if not isinstance(owner_id, str) or not owner_id.strip():
        raise ValueError("derive_cognition_goal_id.owner_id: invalid")
    if isinstance(tick, bool) or not isinstance(tick, int) or tick < 0:
        raise ValueError("derive_cognition_goal_id.tick: invalid")
    if parent_goal_id is not None and (
        not isinstance(parent_goal_id, str) or not parent_goal_id.strip()
    ):
        raise ValueError("derive_cognition_goal_id.parent_goal_id: invalid")
    if not isinstance(template_code, str) or not template_code.strip():
        raise ValueError("derive_cognition_goal_id.template_code: invalid")
    if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 0:
        raise ValueError("derive_cognition_goal_id.ordinal: invalid")
    material = "|".join(
        (
            owner_id,
            str(tick),
            "" if parent_goal_id is None else parent_goal_id,
            template_code,
            str(ordinal),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[
        :_GOAL_ID_DIGEST_CHARS
    ]
    return GoalId(f"{_GOAL_ID_PREFIX}{digest}")


@dataclass(frozen=True, slots=True)
class _ChildSkeleton:
    """Closed child skeleton for one decomposition ordinal."""

    horizon: GoalHorizon
    outcome: GoalOutcome
    description: str
    drive_links: tuple[DriveKind, ...]
    relation_kind: GoalRelationKind | None
    depends_on_parent: bool
    priority_scale: float


@dataclass(frozen=True, slots=True)
class _DecompositionTemplate:
    """Closed template: parent outcome match → ordered child skeletons."""

    template_code: str
    parent_outcome_kinds: frozenset[GoalOutcomeKind]
    parent_horizons: frozenset[GoalHorizon]
    require_hunger_link: bool
    children: tuple[_ChildSkeleton, ...]


_TEMPLATE_REGISTRY: Final[tuple[_DecompositionTemplate, ...]] = (
    _DecompositionTemplate(
        template_code="survive_winter.v1",
        parent_outcome_kinds=frozenset(
            (GoalOutcomeKind.PRESERVE_LIFE, GoalOutcomeKind.ACHIEVE_CODE)
        ),
        parent_horizons=frozenset((GoalHorizon.DESIRE, GoalHorizon.LONG_TERM)),
        require_hunger_link=False,
        children=(
            _ChildSkeleton(
                horizon=GoalHorizon.LONG_TERM,
                outcome=GoalOutcome(
                    kind=GoalOutcomeKind.SATISFY_DRIVE, drive_kind=DriveKind.HUNGER
                ),
                description="food-reserve",
                drive_links=(DriveKind.HUNGER,),
                relation_kind=GoalRelationKind.REINFORCES,
                depends_on_parent=False,
                priority_scale=0.9,
            ),
        ),
    ),
    _DecompositionTemplate(
        template_code="food_reserve.v1",
        parent_outcome_kinds=frozenset(
            (GoalOutcomeKind.SATISFY_DRIVE, GoalOutcomeKind.ACHIEVE_CODE)
        ),
        parent_horizons=frozenset(
            (GoalHorizon.LONG_TERM, GoalHorizon.MEDIUM_TERM)
        ),
        require_hunger_link=True,
        children=(
            _ChildSkeleton(
                horizon=GoalHorizon.SUBGOAL,
                outcome=GoalOutcome(
                    kind=GoalOutcomeKind.OBTAIN_ENTITY, entity_id="food-cache"
                ),
                description="obtain-food-cache",
                drive_links=(DriveKind.HUNGER,),
                relation_kind=GoalRelationKind.DEPENDS_ON,
                depends_on_parent=True,
                priority_scale=0.85,
            ),
            _ChildSkeleton(
                horizon=GoalHorizon.SUBGOAL,
                outcome=GoalOutcome(
                    kind=GoalOutcomeKind.GATHER_INFORMATION,
                    outcome_code="locate_food_sources",
                ),
                description="gather-food-sources",
                drive_links=(DriveKind.HUNGER, DriveKind.CURIOSITY),
                relation_kind=GoalRelationKind.DEPENDS_ON,
                depends_on_parent=True,
                priority_scale=0.75,
            ),
        ),
    ),
)


def _status_histogram(goals: tuple[Goal, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for goal in goals:
        key = goal.status.value
        counts[key] = counts.get(key, 0) + 1
    return counts


def _horizon_histogram(goals: tuple[Goal, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for goal in goals:
        key = goal.horizon.value
        counts[key] = counts.get(key, 0) + 1
    return counts


def _transition_reason_histogram(
    intents: tuple[GoalTransitionIntent, ...],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for intent in intents:
        key = intent.reason_code.value
        counts[key] = counts.get(key, 0) + 1
    return counts


def _template_code_histogram(goals: tuple[Goal, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for goal in goals:
        provenance = goal.provenance
        if provenance is None or provenance.template_code is None:
            continue
        key = provenance.template_code
        counts[key] = counts.get(key, 0) + 1
    return counts


def _passthrough_foci(goals: tuple[Goal, ...]) -> tuple[GoalId, ...]:
    return tuple(
        goal.goal_id
        for goal in goals
        if goal.status is GoalStatus.ACTIVE
        and goal.horizon is GoalHorizon.CURRENT_INTENTION
    )


def _validate_owner_goals(
    goals: tuple[Goal, ...], *, owner: AgentId, tick: int
) -> None:
    for goal in goals:
        if goal.owner_id != owner:
            _LOG.error(
                "goal_manager_ownership_failure",
                extra={
                    "cognition": {
                        "policy_version": GOAL_POLICY_VERSION,
                        "owner_id": owner.value,
                        "tick": tick,
                        "reason": "owner_mismatch",
                        "status": "error",
                    }
                },
            )
            raise ValueError("GoalBoard.goals: owner_mismatch")


def _snapshot_goals(loop_input: CognitiveLoopInput) -> tuple[Goal, ...]:
    snapshot = loop_input.snapshot
    if snapshot is None:
        return ()
    return tuple(snapshot.goals)


def _unit_clamp(value: float) -> float:
    if value <= 0.0:
        return 0.0
    if value >= 1.0:
        return 1.0
    return value


def _physiology_pressures(observation: Observation) -> tuple[float, float]:
    self_body = observation.self_body
    if self_body is None:
        return 0.0, 0.0
    return self_body.hunger.value / 100.0, self_body.thirst.value / 100.0


def _critical_need_active(observation: Observation) -> bool:
    hunger, thirst = _physiology_pressures(observation)
    return hunger >= _CRITICAL_NEED or thirst >= _CRITICAL_NEED


def _critical_drive_kinds(observation: Observation) -> frozenset[DriveKind]:
    hunger, thirst = _physiology_pressures(observation)
    drives: set[DriveKind] = set()
    if hunger >= _CRITICAL_NEED:
        drives.add(DriveKind.HUNGER)
    if thirst >= _CRITICAL_NEED:
        drives.add(DriveKind.THIRST)
    return frozenset(drives)


def _parent_has_children(goals: Sequence[Goal], parent_id: GoalId) -> bool:
    return any(goal.parent_goal_id == parent_id for goal in goals)


def _hunger_linked(goal: Goal) -> bool:
    if DriveKind.HUNGER in goal.drive_links:
        return True
    outcome = goal.outcome
    if outcome is None:
        return False
    if (
        outcome.kind is GoalOutcomeKind.SATISFY_DRIVE
        and outcome.drive_kind is DriveKind.HUNGER
    ):
        return True
    if (
        outcome.kind is GoalOutcomeKind.ACHIEVE_CODE
        and outcome.outcome_code is not None
    ):
        code = outcome.outcome_code.casefold()
        return "food" in code or "hunger" in code or "reserve" in code
    return False


def _template_matches(template: _DecompositionTemplate, parent: Goal) -> bool:
    if parent.status is not GoalStatus.ACTIVE:
        return False
    if parent.horizon not in template.parent_horizons:
        return False
    outcome = parent.outcome
    if outcome is None or outcome.kind not in template.parent_outcome_kinds:
        return False
    if template.require_hunger_link and not _hunger_linked(parent):
        return False
    return True


def _find_template(parent: Goal) -> _DecompositionTemplate | None:
    for template in _TEMPLATE_REGISTRY:
        if _template_matches(template, parent):
            return template
    return None


def _priority_for_child(parent: Goal, scale: float) -> float:
    return _unit_clamp(parent.priority * scale)


def _mint_child(
    *,
    owner: AgentId,
    tick: int,
    parent: Goal,
    template: _DecompositionTemplate,
    skeleton: _ChildSkeleton,
    ordinal: int,
) -> Goal:
    child_id = derive_cognition_goal_id(
        owner_id=owner.value,
        tick=tick,
        parent_goal_id=parent.goal_id.value,
        template_code=template.template_code,
        ordinal=ordinal,
    )
    relations: tuple[GoalRelationEdge, ...] = ()
    if skeleton.relation_kind is not None:
        relations = (
            GoalRelationEdge(
                kind=skeleton.relation_kind, target_goal_id=parent.goal_id
            ),
        )
    dependency_ids: tuple[GoalId, ...] = ()
    if skeleton.depends_on_parent:
        dependency_ids = (parent.goal_id,)
    return Goal(
        goal_id=child_id,
        owner_id=owner,
        description=skeleton.description,
        priority=_priority_for_child(parent, skeleton.priority_scale),
        status=GoalStatus.ACTIVE,
        outcome=skeleton.outcome,
        progress=GoalProgress(
            estimate=0.0, confidence=0.5, stall_count=0, horizon_ticks=0
        ),
        horizon=skeleton.horizon,
        confidence=0.5,
        provenance=GoalProvenance(
            origin_kind=GoalOriginKind.DECOMPOSED,
            template_code=template.template_code,
            source_goal_id=parent.goal_id,
        ),
        created_tick=tick,
        parent_goal_id=parent.goal_id,
        dependency_ids=dependency_ids,
        relations=relations,
        drive_links=skeleton.drive_links,
    )


def _collect_claim_tokens(
    situation: SituationModel,
    memory: RetrievedMemoryContext,
    snapshot: SubjectiveSnapshot | None,
) -> frozenset[str]:
    tokens: set[str] = set()
    for code in situation.claim_codes:
        tokens.add(code.value.casefold())
    beliefs = list(memory.semantic_beliefs)
    if snapshot is not None:
        beliefs.extend(snapshot.semantic_beliefs)
    for belief in beliefs:
        predicate = belief.claim.predicate.casefold()
        tokens.add(predicate)
        for part in predicate.replace(":", "_").split("_"):
            if part:
                tokens.add(part)
    for reconstruction in memory.reconstructions:
        for concept in reconstruction.concepts:
            text = concept.concept.casefold()
            tokens.add(text)
            for part in text.replace(":", "_").split("_"):
                if part:
                    tokens.add(part)
    return frozenset(tokens)


def _token_suggests_absence(token: str) -> bool:
    return any(marker in token for marker in _ABSENCE_MARKERS)


def _target_absent(target: str, tokens: frozenset[str]) -> bool:
    needle = target.casefold()
    if not needle:
        return False
    for token in tokens:
        if needle not in token and token != needle:
            continue
        if _token_suggests_absence(token) or needle in _ABSENCE_MARKERS:
            return True
    # Corroborated absence marker present alongside exact target token.
    if needle in tokens and any(_token_suggests_absence(token) for token in tokens):
        return True
    return False


def _outcome_believed_impossible(
    outcome: GoalOutcome, tokens: frozenset[str]
) -> bool:
    if outcome.kind is GoalOutcomeKind.ACHIEVE_CODE:
        code = outcome.outcome_code
        if code is None:
            return False
        folded = code.casefold()
        if folded in _ABSENCE_MARKERS and any(
            _token_suggests_absence(token) for token in tokens
        ):
            return True
        return _target_absent(folded, tokens)
    if outcome.kind is GoalOutcomeKind.REACH_PLACE:
        place_id = outcome.place_id
        if place_id is None:
            return False
        return _target_absent(place_id, tokens)
    if outcome.kind is GoalOutcomeKind.OBTAIN_ENTITY:
        entity_id = outcome.entity_id
        if entity_id is None:
            return False
        return _target_absent(entity_id, tokens)
    return False


def _failure_condition_fires(
    goal: Goal, tokens: frozenset[str]
) -> bool:
    for condition in goal.failure_conditions:
        if _outcome_believed_impossible(condition.outcome, tokens):
            return True
    return False


_IMPOSSIBILITY_OUTCOME_KINDS: Final[frozenset[GoalOutcomeKind]] = frozenset(
    (
        GoalOutcomeKind.ACHIEVE_CODE,
        GoalOutcomeKind.REACH_PLACE,
        GoalOutcomeKind.OBTAIN_ENTITY,
    )
)


def _success_believed_impossible(goal: Goal, tokens: frozenset[str]) -> bool:
    outcome = goal.outcome
    if outcome is None:
        return False
    if outcome.kind in _IMPOSSIBILITY_OUTCOME_KINDS:
        if _outcome_believed_impossible(outcome, tokens):
            return True
    for condition in goal.success_conditions:
        if (
            condition.outcome.kind in _IMPOSSIBILITY_OUTCOME_KINDS
            and _outcome_believed_impossible(condition.outcome, tokens)
        ):
            return True
    return False


def _replace_goal(goals: list[Goal], updated: Goal) -> None:
    for index, goal in enumerate(goals):
        if goal.goal_id == updated.goal_id:
            goals[index] = updated
            return
    raise ValueError("GoalBoard.goals: missing_goal")


def _emit_transition(
    *,
    goal_id: GoalId,
    owner: AgentId,
    tick: int,
    from_status: GoalStatus,
    to_status: GoalStatus,
    reason: GoalTransitionIntentReason,
    resulting_goal: Goal | None,
) -> GoalTransitionIntent:
    return GoalTransitionIntent(
        goal_id=goal_id,
        owner_id=owner,
        from_status=from_status,
        to_status=to_status,
        reason_code=reason,
        tick=tick,
        resulting_goal=resulting_goal,
    )


def _identity_tokens(
    identity: object, aspect: object, floor: float
) -> frozenset[str]:
    from agents.cognition.identity import IdentityAspect, IdentityBeliefView

    if type(aspect) is not IdentityAspect:
        raise TypeError("identity_goal_bias.aspect: invalid_type")
    tokens: set[str] = set()
    for view in getattr(identity, "views", ()):
        if type(view) is not IdentityBeliefView or view.aspect is not aspect:
            continue
        if view.confidence < floor:
            continue
        tokens.add(view.evidence_token)
    return frozenset(tokens)


def _identity_should_suspend(
    goal: Goal,
    *,
    weakness_tokens: frozenset[str],
    protected_tokens: frozenset[str],
    critical: bool,
    critical_drives: frozenset[DriveKind],
    require_active: bool = True,
) -> bool:
    from agents.cognition.identity import satisfying_command_kinds

    if require_active and goal.status is not GoalStatus.ACTIVE:
        return False
    if goal.horizon is not GoalHorizon.MEDIUM_TERM:
        return False
    if critical and _goal_serves_drives(goal, critical_drives):
        return False
    kinds = satisfying_command_kinds(goal)
    if not kinds or kinds.isdisjoint(weakness_tokens):
        return False
    return kinds.isdisjoint(protected_tokens)


def _supporting_identity_refs(goal: Goal, identity: object) -> tuple[str, ...]:
    from agents.cognition.identity import (
        IdentityAspect,
        IdentityBeliefView,
        satisfying_command_kinds,
    )

    kinds = satisfying_command_kinds(goal)
    refs: list[str] = []
    seen: set[str] = set()
    for view in getattr(identity, "views", ()):
        if type(view) is not IdentityBeliefView:
            continue
        matched = (
            view.aspect is IdentityAspect.COMMITMENT
            and view.evidence_token == goal.goal_id.value
        ) or (
            view.aspect is IdentityAspect.COMPETENCE and view.evidence_token in kinds
        )
        if not matched or view.belief_id.value in seen:
            continue
        seen.add(view.belief_id.value)
        refs.append(view.belief_id.value)
    return tuple(refs)


def _apply_identity_goal_bias(
    *,
    owner: AgentId,
    tick: int,
    goals_list: list[Goal],
    intents: list[GoalTransitionIntent],
    selection_codes: list[str],
    identity: object,
    critical: bool,
    critical_drives: frozenset[DriveKind],
) -> None:
    from agents.cognition.identity import (
        IdentityAspect,
        IdentityPolicy,
        IdentityState,
        satisfying_command_kinds,
    )

    if type(identity) is not IdentityState:
        return
    policy = IdentityPolicy()
    weakness_tokens = _identity_tokens(
        identity, IdentityAspect.WEAKNESS, policy.weakness_floor
    )
    protected_tokens = _identity_tokens(
        identity, IdentityAspect.COMPETENCE, policy.competence_floor
    )

    view_ids = {view.belief_id.value for view in identity.views}
    kept = 0
    suspended_count = 0
    ref_count = 0
    for goal in tuple(goals_list):
        kinds = satisfying_command_kinds(goal)
        if (
            goal.status is GoalStatus.ACTIVE
            and kinds
            and not kinds.isdisjoint(protected_tokens)
        ):
            kept += 1
            if "identity_competence_keep" not in selection_codes:
                selection_codes.append("identity_competence_keep")
        if not _identity_should_suspend(
            goal,
            weakness_tokens=weakness_tokens,
            protected_tokens=protected_tokens,
            critical=critical,
            critical_drives=critical_drives,
        ):
            continue
        suspended = replace(goal, status=GoalStatus.SUSPENDED)
        _replace_goal(goals_list, suspended)
        intents.append(
            _emit_transition(
                goal_id=suspended.goal_id,
                owner=owner,
                tick=tick,
                from_status=GoalStatus.ACTIVE,
                to_status=GoalStatus.SUSPENDED,
                reason=GoalTransitionIntentReason.SUSPENDED,
                resulting_goal=suspended,
            )
        )
        suspended_count += 1
        if "identity_weakness_suspend" not in selection_codes:
            selection_codes.append("identity_weakness_suspend")

    for index, goal in enumerate(tuple(goals_list)):
        if goal.status is not GoalStatus.ACTIVE:
            continue
        supporting = _supporting_identity_refs(goal, identity)
        stale = tuple(ref for ref in goal.self_model_refs if ref not in view_ids)
        if stale:
            _LOG.warning(
                "identity_goal_ref_rejected",
                extra={
                    "reason_code": "belief_not_in_view",
                    "owner_id": owner.value,
                    "tick": tick,
                    "rejected_count": len(stale),
                },
            )
        if not supporting and not stale:
            continue
        refreshed = replace(goal, self_model_refs=supporting)
        if refreshed == goal:
            continue
        goals_list[index] = refreshed
        ref_count += len(supporting)
        replaced_intent = False
        for intent_index, intent in enumerate(intents):
            if intent.goal_id != goal.goal_id or intent.resulting_goal is None:
                continue
            intents[intent_index] = replace(intent, resulting_goal=refreshed)
            replaced_intent = True
        if not replaced_intent:
            intents.append(
                _emit_transition(
                    goal_id=refreshed.goal_id,
                    owner=owner,
                    tick=tick,
                    from_status=goal.status,
                    to_status=goal.status,
                    reason=GoalTransitionIntentReason.ADOPTED,
                    resulting_goal=refreshed,
                )
            )
    _LOG.debug(
        "identity_goal_bias",
        extra={
            "owner_id": owner.value,
            "tick": tick,
            "kept_count": kept,
            "suspended_count": suspended_count,
            "ref_count": ref_count,
        },
    )


def _dependencies_ready(goal: Goal, by_id: Mapping[GoalId, Goal]) -> bool:
    for dep_id in goal.dependency_ids:
        dep = by_id.get(dep_id)
        if dep is None:
            return False
        if dep.status in {GoalStatus.FAILED, GoalStatus.ABANDONED}:
            return False
    return True


def _should_abandon(
    goal: Goal,
    *,
    tick: int,
    by_id: Mapping[GoalId, Goal],
) -> bool:
    """True when deadline elapsed or parent is already terminal."""

    if goal.status not in _ABANDONABLE_STATUSES:
        return False
    if goal.deadline_tick is not None and tick > goal.deadline_tick:
        return True
    if goal.parent_goal_id is None:
        return False
    parent = by_id.get(goal.parent_goal_id)
    if parent is None:
        return False
    return parent.status in _TERMINAL_PARENT_STATUSES


def _dampen_parent_after_child_terminal(
    *,
    goals_list: list[Goal],
    by_id: dict[GoalId, Goal],
    child: Goal,
    owner: AgentId,
    tick: int,
    intents: list[GoalTransitionIntent],
    selection_codes: list[str],
) -> None:
    """Lower ACTIVE parent confidence/progress after a child fails or is abandoned."""

    parent_ids: list[GoalId] = []
    if child.parent_goal_id is not None:
        parent_ids.append(child.parent_goal_id)
    for edge in child.relations:
        if edge.kind is GoalRelationKind.REINFORCES:
            parent_ids.append(edge.target_goal_id)
    for parent_id in parent_ids:
        parent = by_id.get(parent_id)
        if parent is None or parent.status is not GoalStatus.ACTIVE:
            continue
        parent_progress = parent.progress
        if parent_progress is None:
            parent_progress = GoalProgress(
                estimate=0.0, confidence=0.0, stall_count=0, horizon_ticks=0
            )
        parent_confidence = (
            0.0 if parent.confidence is None else parent.confidence
        )
        new_estimate = _unit_clamp(
            parent_progress.estimate - _FAIL_PROGRESS_PENALTY
        )
        new_confidence = _unit_clamp(
            parent_confidence - _FAIL_CONFIDENCE_PENALTY
        )
        if (
            new_estimate == parent_progress.estimate
            and new_confidence == parent_confidence
        ):
            continue
        updated_progress = GoalProgress(
            estimate=new_estimate,
            confidence=min(parent_progress.confidence, new_confidence),
            stall_count=parent_progress.stall_count,
            horizon_ticks=parent_progress.horizon_ticks,
        )
        updated_parent = replace(
            parent,
            progress=updated_progress,
            confidence=new_confidence,
        )
        _replace_goal(goals_list, updated_parent)
        by_id[updated_parent.goal_id] = updated_parent
        intents.append(
            _emit_transition(
                goal_id=updated_parent.goal_id,
                owner=owner,
                tick=tick,
                from_status=GoalStatus.ACTIVE,
                to_status=GoalStatus.ACTIVE,
                reason=GoalTransitionIntentReason.PROGRESS_UPDATED,
                resulting_goal=updated_parent,
            )
        )
        if "parent_dampened" not in selection_codes:
            selection_codes.append("parent_dampened")


def _cascade_abandon(
    *,
    goals_list: list[Goal],
    owner: AgentId,
    tick: int,
    intents: list[GoalTransitionIntent],
    selection_codes: list[str],
) -> None:
    """Abandon ACTIVE/SUSPENDED goals past deadline or under terminal parents."""

    changed = True
    while changed:
        changed = False
        by_id = {goal.goal_id: goal for goal in goals_list}
        candidates = sorted(
            (
                goal
                for goal in goals_list
                if _should_abandon(goal, tick=tick, by_id=by_id)
            ),
            key=lambda item: item.goal_id.value,
        )
        for goal in candidates:
            abandoned = replace(goal, status=GoalStatus.ABANDONED)
            _replace_goal(goals_list, abandoned)
            by_id[abandoned.goal_id] = abandoned
            intents.append(
                _emit_transition(
                    goal_id=abandoned.goal_id,
                    owner=owner,
                    tick=tick,
                    from_status=goal.status,
                    to_status=GoalStatus.ABANDONED,
                    reason=GoalTransitionIntentReason.ABANDONED,
                    resulting_goal=abandoned,
                )
            )
            _dampen_parent_after_child_terminal(
                goals_list=goals_list,
                by_id=by_id,
                child=abandoned,
                owner=owner,
                tick=tick,
                intents=intents,
                selection_codes=selection_codes,
            )
            if "abandoned" not in selection_codes:
                selection_codes.append("abandoned")
            changed = True


def _has_active_focus_child(goals: Sequence[Goal], parent_id: GoalId) -> bool:
    return any(
        goal.parent_goal_id == parent_id
        and goal.horizon is GoalHorizon.CURRENT_INTENTION
        and goal.status is GoalStatus.ACTIVE
        for goal in goals
    )


def _mint_focus(
    *,
    owner: AgentId,
    tick: int,
    parent: Goal,
    ordinal: int,
) -> Goal:
    focus_id = derive_cognition_goal_id(
        owner_id=owner.value,
        tick=tick,
        parent_goal_id=parent.goal_id.value,
        template_code=_FOCUS_TEMPLATE_CODE,
        ordinal=ordinal,
    )
    outcome = parent.outcome
    if outcome is None:
        outcome = GoalOutcome(kind=GoalOutcomeKind.PRESERVE_LIFE)
    relations: list[GoalRelationEdge] = [
        GoalRelationEdge(
            kind=GoalRelationKind.DEPENDS_ON, target_goal_id=parent.goal_id
        )
    ]
    # Short-horizon focus may compete with a long-term ancestor without abandoning it.
    if parent.parent_goal_id is not None:
        relations.append(
            GoalRelationEdge(
                kind=GoalRelationKind.COMPETES_WITH,
                target_goal_id=parent.parent_goal_id,
            )
        )
    return Goal(
        goal_id=focus_id,
        owner_id=owner,
        description="current-intention-focus",
        priority=_unit_clamp(max(parent.priority, 0.9)),
        status=GoalStatus.ACTIVE,
        outcome=outcome,
        progress=GoalProgress(
            estimate=0.0, confidence=0.6, stall_count=0, horizon_ticks=0
        ),
        horizon=GoalHorizon.CURRENT_INTENTION,
        confidence=0.6,
        provenance=GoalProvenance(
            origin_kind=GoalOriginKind.DECOMPOSED,
            template_code=_FOCUS_TEMPLATE_CODE,
            source_goal_id=parent.goal_id,
        ),
        created_tick=tick,
        parent_goal_id=parent.goal_id,
        dependency_ids=(parent.goal_id,),
        relations=tuple(relations),
        drive_links=parent.drive_links,
    )


def _goal_serves_drives(goal: Goal, drives: frozenset[DriveKind]) -> bool:
    if not drives:
        return False
    if any(link in drives for link in goal.drive_links):
        return True
    outcome = goal.outcome
    if (
        outcome is not None
        and outcome.kind is GoalOutcomeKind.SATISFY_DRIVE
        and outcome.drive_kind in drives
    ):
        return True
    return False


def _competes_with_active_intention(
    goal: Goal, by_id: Mapping[GoalId, Goal]
) -> bool:
    for edge in goal.relations:
        if edge.kind is not GoalRelationKind.COMPETES_WITH:
            continue
        other = by_id.get(edge.target_goal_id)
        if (
            other is not None
            and other.status is GoalStatus.ACTIVE
            and other.horizon is GoalHorizon.CURRENT_INTENTION
        ):
            return True
    for other in by_id.values():
        if other.status is not GoalStatus.ACTIVE:
            continue
        if other.horizon is not GoalHorizon.CURRENT_INTENTION:
            continue
        for edge in other.relations:
            if (
                edge.kind is GoalRelationKind.COMPETES_WITH
                and edge.target_goal_id == goal.goal_id
            ):
                return True
    return False


def _board_confidence(goals: tuple[Goal, ...]) -> float:
    if not goals:
        return 0.0
    active = [goal for goal in goals if goal.status is GoalStatus.ACTIVE]
    if not active:
        return 0.0
    total = 0.0
    for goal in active:
        confidence = 0.0 if goal.confidence is None else goal.confidence
        total += confidence
    return _unit_clamp(total / len(active))


class PassthroughGoalManager:
    """Re-emit snapshot goals without decompose/compete mutations."""

    async def manage(
        self,
        loop_input: CognitiveLoopInput,
        situation: SituationModel,
        self_state: SelfModel,
        memory: RetrievedMemoryContext,
    ) -> GoalBoard:
        del situation, self_state, memory  # ownership validated via loop_input
        owner = loop_input.agent_id
        tick = loop_input.observation.tick
        goals = _snapshot_goals(loop_input)
        _validate_owner_goals(goals, owner=owner, tick=tick)
        foci = _passthrough_foci(goals)
        board = GoalBoard(
            owner_id=owner,
            tick=tick,
            goals=goals,
            foci_ids=foci,
            transition_intents=(),
            confidence=1.0 if goals else 0.0,
            policy_version=GOAL_POLICY_VERSION,
            decision_metadata=DecisionMetadata(
                selection_codes=("goal_management_passthrough",),
                candidate_count=len(goals),
            ),
        )
        _LOG.debug(
            "goal_manager_complete",
            extra={
                "cognition": {
                    "policy_version": GOAL_POLICY_VERSION,
                    "owner_id": owner.value,
                    "tick": tick,
                    "mode": "passthrough",
                    "goal_count": len(goals),
                    "status_counts": _status_histogram(goals),
                    "horizon_counts": _horizon_histogram(goals),
                    "transition_count": 0,
                    "foci_count": len(foci),
                    "status": "complete",
                }
            },
        )
        return board


class HierarchicalGoalManager:
    """Deterministic hierarchical maintenance (``goals.v1``)."""

    async def manage(
        self,
        loop_input: CognitiveLoopInput,
        situation: SituationModel,
        self_state: SelfModel,
        memory: RetrievedMemoryContext,
    ) -> GoalBoard:
        owner = loop_input.agent_id
        tick = loop_input.observation.tick
        _LOG.debug(
            "goal_manager_start",
            extra={
                "cognition": {
                    "policy_version": GOAL_POLICY_VERSION,
                    "owner_id": owner.value,
                    "tick": tick,
                    "mode": "enabled",
                    "status": "start",
                }
            },
        )
        goals_list: list[Goal] = list(_snapshot_goals(loop_input))
        _validate_owner_goals(tuple(goals_list), owner=owner, tick=tick)

        intents: list[GoalTransitionIntent] = []
        selection_codes: list[str] = ["goal_management_hierarchical"]
        tokens = _collect_claim_tokens(situation, memory, loop_input.snapshot)
        critical = _critical_need_active(loop_input.observation)
        critical_drives = _critical_drive_kinds(loop_input.observation)

        # 1) Decompose ACTIVE parents that match a closed template and lack children.
        parents_snapshot = tuple(goals_list)
        for parent in parents_snapshot:
            if _parent_has_children(goals_list, parent.goal_id):
                continue
            template = _find_template(parent)
            if template is None:
                continue
            if len(goals_list) + len(template.children) > _MAX_BOARD_GOALS:
                _LOG.warning(
                    "goal_manager_truncation",
                    extra={
                        "cognition": {
                            "policy_version": GOAL_POLICY_VERSION,
                            "owner_id": owner.value,
                            "tick": tick,
                            "reason": "board_capacity",
                            "status": "truncated",
                        }
                    },
                )
                break
            for ordinal, skeleton in enumerate(template.children):
                child = _mint_child(
                    owner=owner,
                    tick=tick,
                    parent=parent,
                    template=template,
                    skeleton=skeleton,
                    ordinal=ordinal,
                )
                goals_list.append(child)
                intents.append(
                    _emit_transition(
                        goal_id=child.goal_id,
                        owner=owner,
                        tick=tick,
                        from_status=GoalStatus.ACTIVE,
                        to_status=GoalStatus.ACTIVE,
                        reason=GoalTransitionIntentReason.DECOMPOSED,
                        resulting_goal=child,
                    )
                )
            if "decomposed" not in selection_codes:
                selection_codes.append("decomposed")

        by_id = {goal.goal_id: goal for goal in goals_list}

        # 2) Subjective impossibility → FAILED (never delete long-term parents).
        for goal in tuple(goals_list):
            if goal.status is not GoalStatus.ACTIVE:
                continue
            if not (
                _failure_condition_fires(goal, tokens)
                or _success_believed_impossible(goal, tokens)
            ):
                continue
            failed = replace(goal, status=GoalStatus.FAILED)
            _replace_goal(goals_list, failed)
            by_id[failed.goal_id] = failed
            intents.append(
                _emit_transition(
                    goal_id=failed.goal_id,
                    owner=owner,
                    tick=tick,
                    from_status=GoalStatus.ACTIVE,
                    to_status=GoalStatus.FAILED,
                    reason=GoalTransitionIntentReason.FAILED,
                    resulting_goal=failed,
                )
            )
            if "subjective_failure" not in selection_codes:
                selection_codes.append("subjective_failure")
            _dampen_parent_after_child_terminal(
                goals_list=goals_list,
                by_id=by_id,
                child=failed,
                owner=owner,
                tick=tick,
                intents=intents,
                selection_codes=selection_codes,
            )

        # 2b) Abandon: deadline elapsed or cascade under FAILED/ABANDONED parents.
        _cascade_abandon(
            goals_list=goals_list,
            owner=owner,
            tick=tick,
            intents=intents,
            selection_codes=selection_codes,
        )

        by_id = {goal.goal_id: goal for goal in goals_list}

        # 3) Compete: critical need may SUSPEND medium foci; clear → RESUME.
        if critical:
            for goal in tuple(goals_list):
                if goal.status is not GoalStatus.ACTIVE:
                    continue
                if goal.horizon in {
                    GoalHorizon.LONG_TERM,
                    GoalHorizon.DESIRE,
                    GoalHorizon.CURRENT_INTENTION,
                }:
                    continue
                if _goal_serves_drives(goal, critical_drives):
                    continue
                should_suspend = False
                if goal.horizon is GoalHorizon.MEDIUM_TERM:
                    should_suspend = True
                elif (
                    goal.horizon is GoalHorizon.SUBGOAL
                    and _competes_with_active_intention(goal, by_id)
                ):
                    should_suspend = True
                if not should_suspend:
                    continue
                suspended = replace(goal, status=GoalStatus.SUSPENDED)
                _replace_goal(goals_list, suspended)
                by_id[suspended.goal_id] = suspended
                intents.append(
                    _emit_transition(
                        goal_id=suspended.goal_id,
                        owner=owner,
                        tick=tick,
                        from_status=GoalStatus.ACTIVE,
                        to_status=GoalStatus.SUSPENDED,
                        reason=GoalTransitionIntentReason.SUSPENDED,
                        resulting_goal=suspended,
                    )
                )
                if "critical_need_suspend" not in selection_codes:
                    selection_codes.append("critical_need_suspend")
        else:
            weakness_tokens: frozenset[str] = frozenset()
            protected_tokens: frozenset[str] = frozenset()
            if self_state.identity is not None:
                from agents.cognition.identity import IdentityAspect, IdentityPolicy

                identity_policy = IdentityPolicy()
                weakness_tokens = _identity_tokens(
                    self_state.identity,
                    IdentityAspect.WEAKNESS,
                    identity_policy.weakness_floor,
                )
                protected_tokens = _identity_tokens(
                    self_state.identity,
                    IdentityAspect.COMPETENCE,
                    identity_policy.competence_floor,
                )
            for goal in tuple(goals_list):
                if goal.status is not GoalStatus.SUSPENDED:
                    continue
                if goal.horizon is GoalHorizon.LONG_TERM:
                    continue
                if weakness_tokens and _identity_should_suspend(
                    goal,
                    weakness_tokens=weakness_tokens,
                    protected_tokens=protected_tokens,
                    critical=False,
                    critical_drives=critical_drives,
                    require_active=False,
                ):
                    continue
                resumed = replace(goal, status=GoalStatus.ACTIVE)
                _replace_goal(goals_list, resumed)
                by_id[resumed.goal_id] = resumed
                intents.append(
                    _emit_transition(
                        goal_id=resumed.goal_id,
                        owner=owner,
                        tick=tick,
                        from_status=GoalStatus.SUSPENDED,
                        to_status=GoalStatus.ACTIVE,
                        reason=GoalTransitionIntentReason.RESUMED,
                        resulting_goal=resumed,
                    )
                )
                if "critical_need_resume" not in selection_codes:
                    selection_codes.append("critical_need_resume")

        by_id = {goal.goal_id: goal for goal in goals_list}
        if self_state.identity is not None:
            _apply_identity_goal_bias(
                owner=owner,
                tick=tick,
                goals_list=goals_list,
                intents=intents,
                selection_codes=selection_codes,
                identity=self_state.identity,
                critical=critical,
                critical_drives=critical_drives,
            )
            by_id = {goal.goal_id: goal for goal in goals_list}

        # 4) REINFORCES: child ACTIVE progress bumps parent conservatively.
        for goal in tuple(goals_list):
            if goal.status is not GoalStatus.ACTIVE:
                continue
            progress = goal.progress
            if progress is None or progress.estimate <= 0.0:
                continue
            parent_ids: list[GoalId] = []
            if goal.parent_goal_id is not None:
                parent_ids.append(goal.parent_goal_id)
            for edge in goal.relations:
                if edge.kind is GoalRelationKind.REINFORCES:
                    parent_ids.append(edge.target_goal_id)
            for parent_id in parent_ids:
                parent = by_id.get(parent_id)
                if parent is None or parent.status is not GoalStatus.ACTIVE:
                    continue
                parent_progress = parent.progress
                if parent_progress is None:
                    parent_progress = GoalProgress(
                        estimate=0.0, confidence=0.0, stall_count=0, horizon_ticks=0
                    )
                new_estimate = _unit_clamp(
                    parent_progress.estimate
                    + _REINFORCE_PROGRESS_STEP * progress.estimate
                )
                child_confidence = 0.0 if goal.confidence is None else goal.confidence
                parent_confidence = (
                    0.0 if parent.confidence is None else parent.confidence
                )
                new_confidence = _unit_clamp(
                    parent_confidence * (1.0 - _REINFORCE_CONFIDENCE_BLEND)
                    + child_confidence * _REINFORCE_CONFIDENCE_BLEND
                )
                if (
                    new_estimate == parent_progress.estimate
                    and new_confidence == parent_confidence
                ):
                    continue
                updated_progress = GoalProgress(
                    estimate=new_estimate,
                    confidence=max(parent_progress.confidence, new_confidence),
                    stall_count=parent_progress.stall_count,
                    horizon_ticks=parent_progress.horizon_ticks,
                )
                updated_parent = replace(
                    parent,
                    progress=updated_progress,
                    confidence=max(parent_confidence, new_confidence),
                )
                _replace_goal(goals_list, updated_parent)
                by_id[updated_parent.goal_id] = updated_parent
                intents.append(
                    _emit_transition(
                        goal_id=updated_parent.goal_id,
                        owner=owner,
                        tick=tick,
                        from_status=GoalStatus.ACTIVE,
                        to_status=GoalStatus.ACTIVE,
                        reason=GoalTransitionIntentReason.PROGRESS_UPDATED,
                        resulting_goal=updated_parent,
                    )
                )
                if "reinforced" not in selection_codes:
                    selection_codes.append("reinforced")

        by_id = {goal.goal_id: goal for goal in goals_list}

        # 5) Mint CURRENT_INTENTION foci from ready subgoals when missing.
        focus_ordinal = 0
        ready_subgoals = [
            goal
            for goal in goals_list
            if goal.status is GoalStatus.ACTIVE
            and goal.horizon is GoalHorizon.SUBGOAL
            and _dependencies_ready(goal, by_id)
            and not _has_active_focus_child(goals_list, goal.goal_id)
        ]
        ready_subgoals.sort(key=lambda item: (-item.priority, item.goal_id.value))
        for parent in ready_subgoals:
            if len(goals_list) >= _MAX_BOARD_GOALS:
                _LOG.warning(
                    "goal_manager_truncation",
                    extra={
                        "cognition": {
                            "policy_version": GOAL_POLICY_VERSION,
                            "owner_id": owner.value,
                            "tick": tick,
                            "reason": "board_capacity",
                            "status": "truncated",
                        }
                    },
                )
                break
            focus = _mint_focus(
                owner=owner, tick=tick, parent=parent, ordinal=focus_ordinal
            )
            focus_ordinal += 1
            goals_list.append(focus)
            by_id[focus.goal_id] = focus
            intents.append(
                _emit_transition(
                    goal_id=focus.goal_id,
                    owner=owner,
                    tick=tick,
                    from_status=GoalStatus.ACTIVE,
                    to_status=GoalStatus.ACTIVE,
                    reason=GoalTransitionIntentReason.FOCUS_SELECTED,
                    resulting_goal=focus,
                )
            )
            if "focus_selected" not in selection_codes:
                selection_codes.append("focus_selected")

        goals = tuple(goals_list)
        by_id = {goal.goal_id: goal for goal in goals}

        # 6) Select ordered ACTIVE CURRENT_INTENTION foci (capped).
        focus_candidates = [
            goal
            for goal in goals
            if goal.status is GoalStatus.ACTIVE
            and goal.horizon is GoalHorizon.CURRENT_INTENTION
        ]

        def _focus_sort_key(goal: Goal) -> tuple[int, float, str]:
            serves = 1 if _goal_serves_drives(goal, critical_drives) else 0
            return (-serves, -goal.priority, goal.goal_id.value)

        focus_candidates.sort(key=_focus_sort_key)
        if len(focus_candidates) > _MAX_FOCI:
            _LOG.warning(
                "goal_manager_truncation",
                extra={
                    "cognition": {
                        "policy_version": GOAL_POLICY_VERSION,
                        "owner_id": owner.value,
                        "tick": tick,
                        "reason": "foci_cap",
                        "status": "truncated",
                    }
                },
            )
            focus_candidates = focus_candidates[:_MAX_FOCI]
        foci_ids = tuple(goal.goal_id for goal in focus_candidates)

        if len(intents) > 64:
            intents = intents[:64]
            _LOG.warning(
                "goal_manager_truncation",
                extra={
                    "cognition": {
                        "policy_version": GOAL_POLICY_VERSION,
                        "owner_id": owner.value,
                        "tick": tick,
                        "reason": "transition_cap",
                        "status": "truncated",
                    }
                },
            )

        transition_intents = tuple(intents)
        board = GoalBoard(
            owner_id=owner,
            tick=tick,
            goals=goals,
            foci_ids=foci_ids,
            transition_intents=transition_intents,
            confidence=_board_confidence(goals),
            policy_version=GOAL_POLICY_VERSION,
            decision_metadata=DecisionMetadata(
                selection_codes=tuple(selection_codes),
                candidate_count=len(goals),
            ),
        )
        _LOG.debug(
            "goal_manager_complete",
            extra={
                "cognition": {
                    "policy_version": GOAL_POLICY_VERSION,
                    "owner_id": owner.value,
                    "tick": tick,
                    "mode": "enabled",
                    "goal_count": len(goals),
                    "status_counts": _status_histogram(goals),
                    "horizon_counts": _horizon_histogram(goals),
                    "transition_count": len(transition_intents),
                    "transition_counts_by_reason": _transition_reason_histogram(
                        transition_intents
                    ),
                    "foci_count": len(foci_ids),
                    "template_code_counts": _template_code_histogram(goals),
                    "status": "complete",
                }
            },
        )
        return board
