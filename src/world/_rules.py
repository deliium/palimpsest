"""Pure V1 action rule interfaces and outcome matrix.

Rules evaluate immutable snapshots and validated operations only. They do not
import simulation, logging, wall clocks, UUID factories, or randomness.
Behavioral mutation handlers are applied by later rule/transition stages;
this module owns dispositions, reason codes, and precedence.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final

from world._operations import (
    ValidatedWorldOperation,
    _AmendOp,
    _AnnotateRecordOp,
    _AskOp,
    _AttackOp,
    _BuildOp,
    _CopyRecordOp,
    _CraftOp,
    _DamageRecordOp,
    _DrinkOp,
    _DropOp,
    _EatOp,
    _EraseOp,
    _FeedOp,
    _FleeOp,
    _GiveOp,
    _HarvestOp,
    _HelpOp,
    _InscribeOp,
    _MoveOp,
    _RepairOp,
    _SearchOp,
    _SleepOp,
    _StoreOp,
    _TakeOp,
    _TalkOp,
    _TellOp,
    _TransferArtifactOp,
    _TransportOp,
    _WaitOp,
)
from world._state import WorldState, rebuild_world_state
from world.artifacts import (
    MAX_ARTIFACT_MARKS,
    MAX_ARTIFACT_RELATIONS,
    MAX_HELD_ARTIFACTS_PER_BODY,
    ArtifactContent,
    DurableRecordsRuleContext,
    InformationArtifact,
    RecordIntegrity,
    artifact_kind_is_durable_capable,
    artifact_kind_is_portable,
)
from world.communications import StructuredUtterance
from world.effects import (
    DeathCause,
    ResolvedActionEffects,
    ResolvedArtifactCopyEffect,
    ResolvedArtifactInscribeEffect,
    ResolvedAttackEffect,
    ResolvedFleeEffect,
    ResolvedProductionEffect,
    ResolvedSearchEffect,
)
from world.events import (
    ArtifactAnnotated,
    ArtifactCopied,
    ArtifactCreated,
    ArtifactDamaged,
    ArtifactDestroyed,
    ArtifactModified,
    ArtifactMoved,
    ArtifactPartiallyLost,
    Asked,
    Attacked,
    Died,
    Dropped,
    Drunk,
    Eaten,
    EventDetails,
    Fed,
    Fled,
    Given,
    Helped,
    Moved,
    Searched,
    Slept,
    Taken,
    Talked,
    Told,
    Transported,
    Waited,
)
from world.identifiers import EntityId
from world.models import (
    AgentBody,
    Item,
    LifeStatus,
    PhysicalRules,
    Resource,
    copy_body,
    copy_item,
    copy_resource,
    default_physical_rules,
)
from world.observations import CONTENT_VISIBILITY_THRESHOLD
from world.values import (
    Fatigue,
    Health,
    Hunger,
    ItemKind,
    ItemLoad,
    ResourceKind,
    Thirst,
    WeatherCondition,
    clamp_need,
    round_physical,
)

_OPS_LOG: Final[logging.Logger] = logging.getLogger("world._operations")

__all__: list[str] = [
    "COMMAND_RULE_MATRIX",
    "CommandRulePolicy",
    "RuleApplication",
    "RuleDisposition",
    "RuleReason",
    "RuleResult",
    "apply_operation",
    "evaluate_operation",
    "find_eligible_flee_destinations",
    "find_eligible_search_resource",
]


class RuleDisposition(StrEnum):
    """Closed rule outcome category for one validated operation."""

    MUTATE = "mutate"
    EVENT_ONLY = "event_only"
    DEFERRED = "deferred"
    REJECT = "reject"


class RuleReason(StrEnum):
    """Stable reason codes for engine DEBUG correlation (no free-form text)."""

    OCCURRENCE = "occurrence"
    DEAD_ACTOR = "dead_actor"
    DEAD_TARGET = "dead_target"
    NOT_HELD = "not_held"
    NOT_AT_LOCATION = "not_at_location"
    NOT_COLOCATED = "not_colocated"
    NOT_ADJACENT = "not_adjacent"
    NO_BODY_CAPACITY = "no_body_capacity"
    NO_ITEM_CAPACITY = "no_item_capacity"
    NO_CARRY_CAPACITY = "no_carry_capacity"
    RESOURCE_DEPLETED = "resource_depleted"
    WRONG_KIND = "wrong_kind"
    MISSING_RESOLVED_EFFECT = "missing_resolved_effect"
    ALREADY_AT_DESTINATION = "already_at_destination"
    DEFERRED_POLICY = "deferred_policy"
    STRUCTURAL_OK = "structural_ok"
    COMMUNICATION_INVISIBLE = "communication_invisible"
    COMMUNICATION_SOURCE_MISMATCH = "communication_source_mismatch"
    PRODUCTION_DISABLED = "production_disabled"
    UNKNOWN_RECIPE = "unknown_recipe"
    RECIPE_ACTION_MISMATCH = "recipe_action_mismatch"
    ACTOR_BUSY = "actor_busy"
    MATERIALS_UNAVAILABLE = "materials_unavailable"
    STRUCTURE_INTACT = "structure_intact"
    SHELTER_ALREADY_PRESENT = "shelter_already_present"
    STORE_ALREADY_PRESENT = "store_already_present"
    UNKNOWN_ARTIFACT = "unknown_artifact"
    ARTIFACT_NOT_PORTABLE = "artifact_not_portable"
    ARTIFACT_NOT_HELD = "artifact_not_held"
    ARTIFACT_NOT_COLOCATED = "artifact_not_colocated"
    ARTIFACT_CONTENT_INVALID = "artifact_content_invalid"
    INVALID_ARTIFACT_KIND = "invalid_artifact_kind"
    INVALID_ARTIFACT_HOLD = "invalid_artifact_hold"
    ARTIFACT_TRANSFER_MODE_INVALID = "artifact_transfer_mode_invalid"
    ARTIFACT_HOLD_CAP = "artifact_hold_cap"
    RECIPIENT_UNAVAILABLE = "recipient_unavailable"
    NOT_AN_ITEM = "not_an_item"
    DEPENDENCY_CARE_CHANNEL_OFF = "dependency_care_channel_off"
    DEPENDENCY_CARE_TARGET_INVALID = "dependency_care_target_invalid"
    DEPENDENCY_CARE_ACTION_DISABLED = "dependency_care_action_disabled"
    DURABLE_RECORDS_INACTIVE = "durable_records_inactive"
    DURABLE_GENRE_REQUIRED = "durable_genre_required"
    DURABLE_GENRE_DISABLED = "durable_genre_disabled"
    DURABLE_COPY_GENERATION_CAP = "durable_copy_generation_cap"
    DURABLE_PARENT_DESTROYED = "durable_parent_destroyed"
    DURABLE_ANNOTATION_CAP = "durable_annotation_cap"
    DURABLE_INTEGRITY_DESTROYED = "durable_integrity_destroyed"
    DURABLE_DAMAGE_DISABLED = "durable_damage_disabled"
    DURABLE_PARTIAL_LOSS_DISABLED = "durable_partial_loss_disabled"


@dataclass(frozen=True, slots=True)
class CommandRulePolicy:
    """Documented V1 policy row for one command family."""

    disposition: RuleDisposition
    emits_event_when_applied: bool
    mutates_state_when_applied: bool
    requires_living_actor: bool
    notes: str


@dataclass(frozen=True, slots=True)
class RuleResult:
    """Pure evaluation result. Contains no snapshots or communication text."""

    disposition: RuleDisposition
    reason: RuleReason
    emits_event: bool
    mutates_state: bool
    action_kind: str

    def __post_init__(self) -> None:
        if type(self.disposition) is not RuleDisposition:
            raise TypeError("RuleResult.disposition must be RuleDisposition")
        if type(self.reason) is not RuleReason:
            raise TypeError("RuleResult.reason must be RuleReason")
        if type(self.emits_event) is not bool:
            raise TypeError("RuleResult.emits_event must be bool")
        if type(self.mutates_state) is not bool:
            raise TypeError("RuleResult.mutates_state must be bool")
        if type(self.action_kind) is not str or not self.action_kind:
            raise TypeError("RuleResult.action_kind must be a non-empty str")
        if self.disposition is RuleDisposition.REJECT:
            if self.emits_event or self.mutates_state:
                raise ValueError("rejected rules never emit events or mutate")
        if self.disposition is RuleDisposition.DEFERRED:
            if self.emits_event or self.mutates_state:
                raise ValueError("deferred rules never emit events or mutate")
        if self.disposition is RuleDisposition.EVENT_ONLY and self.mutates_state:
            raise ValueError("event-only rules must not mutate state")
        if self.disposition is RuleDisposition.MUTATE and not self.mutates_state:
            raise ValueError("mutate disposition requires mutates_state")


# Complete V1 outcome matrix (interfaces + precedence documentation).
COMMAND_RULE_MATRIX: Final[dict[type, CommandRulePolicy]] = {
    _TakeOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="local ground item; carry capacity; inventory/holder agreement",
    ),
    _DropOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="item held by actor; free local ground item capacity",
    ),
    _GiveOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="item held; living colocated recipient; recipient carry capacity",
    ),
    _SearchOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes=(
            "eligible local resource + free ground slot; mutate-or-event via resolved"
        ),
    ),
    _TalkOp: CommandRulePolicy(
        disposition=RuleDisposition.EVENT_ONLY,
        emits_event_when_applied=True,
        mutates_state_when_applied=False,
        requires_living_actor=True,
        notes=(
            "living colocated recipient; visibility threshold; "
            "declared immediate source must match actor; event-only"
        ),
    ),
    _AskOp: CommandRulePolicy(
        disposition=RuleDisposition.EVENT_ONLY,
        emits_event_when_applied=True,
        mutates_state_when_applied=False,
        requires_living_actor=True,
        notes=(
            "living colocated recipient; visibility threshold; "
            "declared immediate source must match actor; event-only; no auto-answer"
        ),
    ),
    _TellOp: CommandRulePolicy(
        disposition=RuleDisposition.EVENT_ONLY,
        emits_event_when_applied=True,
        mutates_state_when_applied=False,
        requires_living_actor=True,
        notes=(
            "living colocated recipient; visibility threshold; "
            "declared immediate source must match actor; event-only; no truth inference"
        ),
    ),
    _WaitOp: CommandRulePolicy(
        disposition=RuleDisposition.EVENT_ONLY,
        emits_event_when_applied=True,
        mutates_state_when_applied=False,
        requires_living_actor=True,
        notes="validated occurrence only",
    ),
    _MoveOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="adjacent destination with free body slot; add move fatigue",
    ),
    _EatOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="held food item; consume and reduce hunger",
    ),
    _DrinkOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="held water item or local water resource qty>=1; reduce thirst",
    ),
    _SleepOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="reduce fatigue by sleep recovery; shelter does not gate",
    ),
    _HelpOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="living colocated target; heal + helper fatigue; no revival",
    ),
    _FeedOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes=(
            "dependency-care Feed: held FOOD/WATER to colocated DEPENDENT; "
            "channel + allow_feed required"
        ),
    ),
    _TransportOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes=(
            "dependency-care Transport: relocates caregiver + colocated DEPENDENT; "
            "channel + allow_transport required"
        ),
    ),
    _AttackOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes=(
            "living colocated target; mutate-or-event via resolved; "
            "lethal hit emits Attacked then Died"
        ),
    ),
    _HarvestOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="catalog recipe; harvest resource at the actor location",
    ),
    _CraftOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="catalog recipe; consume held inputs; duration may defer the item",
    ),
    _BuildOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="catalog recipe; one shelter per location",
    ),
    _RepairOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="catalog recipe; repair a colocated shelter below full integrity",
    ),
    _StoreOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="catalog recipe; store food; first success creates the store",
    ),
    _FleeOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes=(
            "optional living colocated threat; eligible adjacent capacity; "
            "mutate-or-event via resolved"
        ),
    ),
    _InscribeOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="create artifact at actor location or held (portable only)",
    ),
    _AmendOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="replace content; actor colocated or holder",
    ),
    _EraseOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="destroy artifact; actor colocated or holder",
    ),
    _TransferArtifactOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="rebind portable placement: claim/deposit/give",
    ),
    _CopyRecordOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="durable copy with parent/source lineage; imperfect fidelity",
    ),
    _AnnotateRecordOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="merge annotation marks into durable record content",
    ),
    _DamageRecordOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="damage / partial_loss / destroy (tombstone optional)",
    ),
}

_OPERATION_KIND: Final[dict[type, str]] = {
    _MoveOp: "move",
    _SearchOp: "search",
    _TakeOp: "take",
    _DropOp: "drop",
    _GiveOp: "give",
    _EatOp: "eat",
    _DrinkOp: "drink",
    _SleepOp: "sleep",
    _TalkOp: "talk",
    _AskOp: "ask",
    _TellOp: "tell",
    _HelpOp: "help",
    _FeedOp: "feed",
    _TransportOp: "transport",
    _AttackOp: "attack",
    _FleeOp: "flee",
    _WaitOp: "wait",
    _HarvestOp: "harvest",
    _CraftOp: "craft",
    _BuildOp: "build",
    _RepairOp: "repair",
    _StoreOp: "store",
    _InscribeOp: "inscribe",
    _AmendOp: "amend",
    _EraseOp: "erase",
    _TransferArtifactOp: "transfer_artifact",
    _CopyRecordOp: "copy_record",
    _AnnotateRecordOp: "annotate_record",
    _DamageRecordOp: "damage_record",
}

_SEARCH_RESOURCE_KINDS: Final[frozenset[ResourceKind]] = frozenset(
    {ResourceKind.FOOD, ResourceKind.WATER, ResourceKind.MATERIAL}
)

_ITEM_KIND_FOR_RESOURCE: Final[dict[ResourceKind, ItemKind]] = {
    ResourceKind.FOOD: ItemKind.FOOD,
    ResourceKind.WATER: ItemKind.WATER,
    ResourceKind.MATERIAL: ItemKind.MATERIAL,
}


def evaluate_operation(
    state: WorldState,
    operation: ValidatedWorldOperation,
    *,
    rules: PhysicalRules | None = None,
    resolved: ResolvedActionEffects | None = None,
    tick: int | None = None,
    effective_carry_capacity: Mapping[EntityId, int] | None = None,
    dependency_care_context: object | None = None,
    durable_records_context: object | None = None,
) -> RuleResult:
    """Evaluate a validated operation against an immutable snapshot.

    Precedence:
    1. dead actor (all commands)
    2. deferred-policy family
    3. command-specific placement/ownership/co-location/dead-target checks
    4. mutate or event-only success

    One-action slot consumption is enforced by the engine, not by rules.
    Conflict classification across a batch is handled by batch preparation.
    ``effective_carry_capacity`` is ephemeral stage scaling — stored body
    capacity is never rewritten here.
    ``dependency_care_context`` gates Feed/Transport when the channel is on.
    ``durable_records_context`` gates Copy/Annotate/Damage and durable Inscribe.
    """
    if type(state) is not WorldState:
        raise TypeError("evaluate_operation requires WorldState")
    physical_rules = _require_rules(rules)
    if resolved is not None and type(resolved) is not ResolvedActionEffects:
        raise TypeError("evaluate_operation resolved must be ResolvedActionEffects")
    capacity_map: Mapping[EntityId, int] | None = None
    if effective_carry_capacity is not None:
        if not isinstance(effective_carry_capacity, Mapping):
            raise TypeError("effective_carry_capacity must be a mapping")
        capacity_map = effective_carry_capacity
    care_context = _require_dependency_care_context(dependency_care_context)
    durable_context = _require_durable_records_context(durable_records_context)
    op_type = type(operation)
    policy = COMMAND_RULE_MATRIX.get(op_type)
    if policy is None:
        raise TypeError(f"unsupported operation type {op_type.__name__}")
    kind = _OPERATION_KIND[op_type]
    actor = state.bodies.get(operation.actor_id)
    if actor is None:
        # Structural validation should have caught this; fail closed.
        return RuleResult(
            disposition=RuleDisposition.REJECT,
            reason=RuleReason.DEAD_ACTOR,
            emits_event=False,
            mutates_state=False,
            action_kind=kind,
        )
    if actor.life_status is LifeStatus.DEAD:
        return RuleResult(
            disposition=RuleDisposition.REJECT,
            reason=RuleReason.DEAD_ACTOR,
            emits_event=False,
            mutates_state=False,
            action_kind=kind,
        )
    if operation.actor_id in state.production_jobs:
        from world._production import _warn

        recipe_id = getattr(operation, "recipe_id", None)
        _warn(operation.actor_id, recipe_id, "actor_busy")
        return _reject(kind, RuleReason.ACTOR_BUSY)
    if policy.disposition is RuleDisposition.DEFERRED:
        return RuleResult(
            disposition=RuleDisposition.DEFERRED,
            reason=RuleReason.DEFERRED_POLICY,
            emits_event=False,
            mutates_state=False,
            action_kind=kind,
        )
    match operation:
        case _MoveOp(destination_id=destination_id):
            return _evaluate_move(state, operation.actor_id, destination_id, kind)
        case _SearchOp(target_id=target_id):
            return _evaluate_search(
                state,
                operation.actor_id,
                target_id,
                kind,
                request_id=operation.request_id,
                resolved=resolved,
            )
        case _TakeOp(item_id=item_id):
            return _evaluate_take(
                state,
                operation.actor_id,
                item_id,
                kind,
                effective_carry_capacity=capacity_map,
            )
        case _DropOp(item_id=item_id):
            return _evaluate_drop(state, operation.actor_id, item_id, kind)
        case _GiveOp(recipient_id=recipient_id, item_id=item_id):
            return _evaluate_give(
                state,
                operation.actor_id,
                recipient_id,
                item_id,
                kind,
                effective_carry_capacity=capacity_map,
            )
        case _EatOp(item_id=item_id):
            return _evaluate_eat(state, operation.actor_id, item_id, kind)
        case _DrinkOp(source_id=source_id):
            return _evaluate_drink(
                state, operation.actor_id, source_id, kind, rules=physical_rules
            )
        case _SleepOp():
            return RuleResult(
                disposition=RuleDisposition.MUTATE,
                reason=RuleReason.OCCURRENCE,
                emits_event=True,
                mutates_state=True,
                action_kind=kind,
            )
        case _HelpOp(target_id=target_id):
            return _evaluate_help(state, operation.actor_id, target_id, kind)
        case _FeedOp(target_id=target_id, item_id=item_id):
            return _evaluate_feed(
                state,
                operation.actor_id,
                target_id,
                item_id,
                kind,
                care_context=care_context,
            )
        case _TransportOp(target_id=target_id, destination_id=destination_id):
            return _evaluate_transport(
                state,
                operation.actor_id,
                target_id,
                destination_id,
                kind,
                care_context=care_context,
            )
        case _AttackOp(target_id=target_id):
            return _evaluate_attack(
                state,
                operation.actor_id,
                target_id,
                kind,
                request_id=operation.request_id,
                resolved=resolved,
            )
        case _FleeOp(threat_id=threat_id):
            return _evaluate_flee(
                state,
                operation.actor_id,
                threat_id,
                kind,
                request_id=operation.request_id,
                resolved=resolved,
            )
        case _TalkOp(actor_id=actor_id, recipient_id=recipient_id, utterance=utterance):
            return _evaluate_communication(
                state,
                actor_id,
                recipient_id,
                utterance,
                kind,
                rules=_require_rules(rules),
                tick=tick,
            )
        case _AskOp(actor_id=actor_id, recipient_id=recipient_id, utterance=utterance):
            return _evaluate_communication(
                state,
                actor_id,
                recipient_id,
                utterance,
                kind,
                rules=_require_rules(rules),
                tick=tick,
            )
        case _TellOp(actor_id=actor_id, recipient_id=recipient_id, utterance=utterance):
            return _evaluate_communication(
                state,
                actor_id,
                recipient_id,
                utterance,
                kind,
                rules=_require_rules(rules),
                tick=tick,
            )
        case _HarvestOp() | _CraftOp() | _BuildOp() | _RepairOp() | _StoreOp():
            return _evaluate_production(state, operation, kind, resolved=resolved)
        case _InscribeOp():
            return _evaluate_inscribe(
                state,
                operation,
                kind,
                resolved=resolved,
                durable_context=durable_context,
            )
        case _AmendOp():
            return _evaluate_amend(
                state, operation, kind, durable_context=durable_context
            )
        case _EraseOp():
            return _evaluate_erase(
                state, operation, kind, durable_context=durable_context
            )
        case _TransferArtifactOp():
            return _evaluate_transfer_artifact(state, operation, kind)
        case _CopyRecordOp():
            return _evaluate_copy_record(
                state,
                operation,
                kind,
                resolved=resolved,
                durable_context=durable_context,
            )
        case _AnnotateRecordOp():
            return _evaluate_annotate_record(
                state, operation, kind, durable_context=durable_context
            )
        case _DamageRecordOp():
            return _evaluate_damage_record(
                state, operation, kind, durable_context=durable_context
            )
        case _WaitOp():
            return RuleResult(
                disposition=RuleDisposition.EVENT_ONLY,
                reason=RuleReason.OCCURRENCE,
                emits_event=True,
                mutates_state=False,
                action_kind=kind,
            )
        case _:
            raise TypeError(f"unhandled operation type {op_type.__name__}")


def find_eligible_search_resource(
    state: WorldState,
    actor_id: EntityId,
    target_id: EntityId | None,
) -> EntityId | None:
    """Return the eligible Search resource id, or None when structurally invalid."""
    if type(state) is not WorldState:
        raise TypeError("find_eligible_search_resource requires WorldState")
    if type(actor_id) is not EntityId:
        raise TypeError("find_eligible_search_resource requires EntityId actor")
    if target_id is not None and type(target_id) is not EntityId:
        raise TypeError("find_eligible_search_resource target must be EntityId")
    actor = state.bodies.get(actor_id)
    if actor is None or actor.life_status is LifeStatus.DEAD:
        return None
    if (
        _ground_item_count(state, actor.location_id)
        >= state.locations[actor.location_id].item_capacity.value
    ):
        return None
    if target_id is not None:
        if not _resource_search_eligible(state, actor, target_id):
            return None
        return target_id
    for resource_id in sorted(state.resources, key=lambda value: value.value):
        if _resource_search_eligible(state, actor, resource_id):
            return resource_id
    return None


def find_eligible_flee_destinations(
    state: WorldState, actor_id: EntityId
) -> tuple[EntityId, ...]:
    """Return canonically sorted adjacent destinations with free body capacity."""
    if type(state) is not WorldState:
        raise TypeError("find_eligible_flee_destinations requires WorldState")
    if type(actor_id) is not EntityId:
        raise TypeError("find_eligible_flee_destinations requires EntityId actor")
    actor = state.bodies.get(actor_id)
    if actor is None or actor.life_status is LifeStatus.DEAD:
        return ()
    location = state.locations[actor.location_id]
    eligible: list[EntityId] = []
    for destination_id in sorted(location.adjacent, key=lambda value: value.value):
        destination = state.locations[destination_id]
        if _body_count(state, destination_id) < destination.body_capacity.value:
            eligible.append(destination_id)
    return tuple(eligible)


def _evaluate_move(
    state: WorldState, actor_id: EntityId, destination_id: EntityId, kind: str
) -> RuleResult:
    actor = state.bodies[actor_id]
    if destination_id == actor.location_id:
        return _reject(kind, RuleReason.ALREADY_AT_DESTINATION)
    location = state.locations[actor.location_id]
    if destination_id not in location.adjacent:
        return _reject(kind, RuleReason.NOT_ADJACENT)
    destination = state.locations[destination_id]
    if _body_count(state, destination_id) >= destination.body_capacity.value:
        return _reject(kind, RuleReason.NO_BODY_CAPACITY)
    return RuleResult(
        disposition=RuleDisposition.MUTATE,
        reason=RuleReason.OCCURRENCE,
        emits_event=True,
        mutates_state=True,
        action_kind=kind,
    )


def _evaluate_search(
    state: WorldState,
    actor_id: EntityId,
    target_id: EntityId | None,
    kind: str,
    *,
    request_id: object,
    resolved: ResolvedActionEffects | None,
) -> RuleResult:
    structural = _search_structural_reject(state, actor_id, target_id, kind)
    if structural is not None:
        return structural
    if resolved is None:
        return _reject(kind, RuleReason.MISSING_RESOLVED_EFFECT)
    from world.identifiers import RequestId

    if type(request_id) is not RequestId:
        raise TypeError("search evaluation requires RequestId")
    effect = resolved.require(request_id, ResolvedSearchEffect)
    assert type(effect) is ResolvedSearchEffect
    if target_id is not None and effect.resource_id != target_id:
        raise ValueError("resolved search resource_id must match Search target")
    actor = state.bodies[actor_id]
    if (
        _ground_item_count(state, actor.location_id)
        >= state.locations[actor.location_id].item_capacity.value
    ):
        return _reject(kind, RuleReason.NO_ITEM_CAPACITY)
    resource_reject = _search_resource_reject(state, actor, effect.resource_id, kind)
    if resource_reject is not None:
        return resource_reject
    if effect.success:
        return RuleResult(
            disposition=RuleDisposition.MUTATE,
            reason=RuleReason.OCCURRENCE,
            emits_event=True,
            mutates_state=True,
            action_kind=kind,
        )
    return RuleResult(
        disposition=RuleDisposition.EVENT_ONLY,
        reason=RuleReason.OCCURRENCE,
        emits_event=True,
        mutates_state=False,
        action_kind=kind,
    )


def _search_structural_reject(
    state: WorldState,
    actor_id: EntityId,
    target_id: EntityId | None,
    kind: str,
) -> RuleResult | None:
    actor = state.bodies[actor_id]
    location = state.locations[actor.location_id]
    if _ground_item_count(state, actor.location_id) >= location.item_capacity.value:
        return _reject(kind, RuleReason.NO_ITEM_CAPACITY)
    if target_id is None:
        if find_eligible_search_resource(state, actor_id, None) is None:
            return _reject(kind, RuleReason.RESOURCE_DEPLETED)
        return None
    return _search_resource_reject(state, actor, target_id, kind)


def _search_resource_reject(
    state: WorldState, actor: AgentBody, resource_id: EntityId, kind: str
) -> RuleResult | None:
    resource = state.resources.get(resource_id)
    if resource is None or type(resource) is not Resource:
        return _reject(kind, RuleReason.WRONG_KIND)
    if resource.kind not in _SEARCH_RESOURCE_KINDS:
        return _reject(kind, RuleReason.WRONG_KIND)
    if resource.location_id != actor.location_id:
        return _reject(kind, RuleReason.NOT_AT_LOCATION)
    if resource.quantity < 1.0:
        return _reject(kind, RuleReason.RESOURCE_DEPLETED)
    return None


def _resource_search_eligible(
    state: WorldState, actor: AgentBody, resource_id: EntityId
) -> bool:
    return _search_resource_reject(state, actor, resource_id, "search") is None


def _evaluate_take(
    state: WorldState,
    actor_id: EntityId,
    item_id: EntityId,
    kind: str,
    *,
    effective_carry_capacity: Mapping[EntityId, int] | None = None,
) -> RuleResult:
    actor = state.bodies[actor_id]
    item = state.items[item_id]
    if item.location_id is None or item.holder_id is not None:
        return _reject(kind, RuleReason.NOT_AT_LOCATION)
    if item.location_id != actor.location_id:
        return _reject(kind, RuleReason.NOT_AT_LOCATION)
    capacity = actor.carry_capacity.value
    if effective_carry_capacity is not None and actor_id in effective_carry_capacity:
        capacity = effective_carry_capacity[actor_id]
    if _inventory_load(state, actor) + item.load.value > capacity:
        return _reject(kind, RuleReason.NO_CARRY_CAPACITY)
    return RuleResult(
        disposition=RuleDisposition.MUTATE,
        reason=RuleReason.OCCURRENCE,
        emits_event=True,
        mutates_state=True,
        action_kind=kind,
    )


def _evaluate_drop(
    state: WorldState, actor_id: EntityId, item_id: EntityId, kind: str
) -> RuleResult:
    actor = state.bodies[actor_id]
    item = state.items[item_id]
    if item.holder_id != actor_id or item_id not in actor.inventory:
        return _reject(kind, RuleReason.NOT_HELD)
    location = state.locations[actor.location_id]
    if _ground_item_count(state, actor.location_id) >= location.item_capacity.value:
        return _reject(kind, RuleReason.NO_ITEM_CAPACITY)
    return RuleResult(
        disposition=RuleDisposition.MUTATE,
        reason=RuleReason.OCCURRENCE,
        emits_event=True,
        mutates_state=True,
        action_kind=kind,
    )


def _evaluate_give(
    state: WorldState,
    actor_id: EntityId,
    recipient_id: EntityId,
    item_id: EntityId,
    kind: str,
    *,
    effective_carry_capacity: Mapping[EntityId, int] | None = None,
) -> RuleResult:
    actor = state.bodies[actor_id]
    recipient = state.bodies[recipient_id]
    item = state.items[item_id]
    if recipient.life_status is LifeStatus.DEAD:
        return _reject(kind, RuleReason.DEAD_TARGET)
    if item.holder_id != actor_id or item_id not in actor.inventory:
        return _reject(kind, RuleReason.NOT_HELD)
    if recipient.location_id != actor.location_id:
        return _reject(kind, RuleReason.NOT_COLOCATED)
    capacity = recipient.carry_capacity.value
    if (
        effective_carry_capacity is not None
        and recipient_id in effective_carry_capacity
    ):
        capacity = effective_carry_capacity[recipient_id]
    if _inventory_load(state, recipient) + item.load.value > capacity:
        return _reject(kind, RuleReason.NO_CARRY_CAPACITY)
    return RuleResult(
        disposition=RuleDisposition.MUTATE,
        reason=RuleReason.OCCURRENCE,
        emits_event=True,
        mutates_state=True,
        action_kind=kind,
    )


def _evaluate_eat(
    state: WorldState, actor_id: EntityId, item_id: EntityId, kind: str
) -> RuleResult:
    actor = state.bodies[actor_id]
    item = state.items[item_id]
    if item.holder_id != actor_id or item_id not in actor.inventory:
        return _reject(kind, RuleReason.NOT_HELD)
    if item.kind is not ItemKind.FOOD:
        return _reject(kind, RuleReason.WRONG_KIND)
    return RuleResult(
        disposition=RuleDisposition.MUTATE,
        reason=RuleReason.OCCURRENCE,
        emits_event=True,
        mutates_state=True,
        action_kind=kind,
    )


def _evaluate_drink(
    state: WorldState,
    actor_id: EntityId,
    source_id: EntityId,
    kind: str,
    *,
    rules: PhysicalRules,
) -> RuleResult:
    del rules  # extraction threshold is fixed at 1.0 per contract
    actor = state.bodies[actor_id]
    item = state.items.get(source_id)
    if item is not None and type(item) is Item:
        if item.holder_id != actor_id or source_id not in actor.inventory:
            return _reject(kind, RuleReason.NOT_HELD)
        if item.kind is not ItemKind.WATER:
            return _reject(kind, RuleReason.WRONG_KIND)
        return RuleResult(
            disposition=RuleDisposition.MUTATE,
            reason=RuleReason.OCCURRENCE,
            emits_event=True,
            mutates_state=True,
            action_kind=kind,
        )
    resource = state.resources.get(source_id)
    if resource is None or type(resource) is not Resource:
        return _reject(kind, RuleReason.WRONG_KIND)
    if resource.kind is not ResourceKind.WATER:
        return _reject(kind, RuleReason.WRONG_KIND)
    if resource.location_id != actor.location_id:
        return _reject(kind, RuleReason.NOT_AT_LOCATION)
    if resource.quantity < 1.0:
        return _reject(kind, RuleReason.RESOURCE_DEPLETED)
    return RuleResult(
        disposition=RuleDisposition.MUTATE,
        reason=RuleReason.OCCURRENCE,
        emits_event=True,
        mutates_state=True,
        action_kind=kind,
    )


def _evaluate_help(
    state: WorldState, actor_id: EntityId, target_id: EntityId, kind: str
) -> RuleResult:
    actor = state.bodies[actor_id]
    target = state.bodies[target_id]
    if target.life_status is LifeStatus.DEAD:
        return _reject(kind, RuleReason.DEAD_TARGET)
    if target.location_id != actor.location_id:
        return _reject(kind, RuleReason.NOT_COLOCATED)
    return RuleResult(
        disposition=RuleDisposition.MUTATE,
        reason=RuleReason.OCCURRENCE,
        emits_event=True,
        mutates_state=True,
        action_kind=kind,
    )


def _evaluate_feed(
    state: WorldState,
    actor_id: EntityId,
    target_id: EntityId,
    item_id: EntityId,
    kind: str,
    *,
    care_context: object | None,
) -> RuleResult:
    from world.dependency_care import DependencyCareRuleContext

    if care_context is None:
        return _reject(kind, RuleReason.DEPENDENCY_CARE_CHANNEL_OFF)
    assert type(care_context) is DependencyCareRuleContext
    if not care_context.allow_feed:
        return _reject(kind, RuleReason.DEPENDENCY_CARE_ACTION_DISABLED)
    actor = state.bodies[actor_id]
    target = state.bodies[target_id]
    if target.life_status is LifeStatus.DEAD:
        return _reject(kind, RuleReason.DEAD_TARGET)
    if target_id not in care_context.dependent_body_ids:
        return _reject(kind, RuleReason.DEPENDENCY_CARE_TARGET_INVALID)
    if care_context.require_colocated and target.location_id != actor.location_id:
        return _reject(kind, RuleReason.NOT_COLOCATED)
    item = state.items.get(item_id)
    if item is None or item.holder_id != actor_id or item_id not in actor.inventory:
        return _reject(kind, RuleReason.NOT_HELD)
    if item.kind not in {ItemKind.FOOD, ItemKind.WATER}:
        return _reject(kind, RuleReason.WRONG_KIND)
    return RuleResult(
        disposition=RuleDisposition.MUTATE,
        reason=RuleReason.OCCURRENCE,
        emits_event=True,
        mutates_state=True,
        action_kind=kind,
    )


def _evaluate_transport(
    state: WorldState,
    actor_id: EntityId,
    target_id: EntityId,
    destination_id: EntityId,
    kind: str,
    *,
    care_context: object | None,
) -> RuleResult:
    from world.dependency_care import DependencyCareRuleContext

    if care_context is None:
        return _reject(kind, RuleReason.DEPENDENCY_CARE_CHANNEL_OFF)
    assert type(care_context) is DependencyCareRuleContext
    if not care_context.allow_transport:
        return _reject(kind, RuleReason.DEPENDENCY_CARE_ACTION_DISABLED)
    actor = state.bodies[actor_id]
    target = state.bodies[target_id]
    if target.life_status is LifeStatus.DEAD:
        return _reject(kind, RuleReason.DEAD_TARGET)
    if target_id not in care_context.dependent_body_ids:
        return _reject(kind, RuleReason.DEPENDENCY_CARE_TARGET_INVALID)
    if care_context.require_colocated and target.location_id != actor.location_id:
        return _reject(kind, RuleReason.NOT_COLOCATED)
    if destination_id == actor.location_id:
        return _reject(kind, RuleReason.ALREADY_AT_DESTINATION)
    location = state.locations[actor.location_id]
    if destination_id not in location.adjacent:
        return _reject(kind, RuleReason.NOT_ADJACENT)
    destination = state.locations[destination_id]
    # Both caregiver and dependent relocate together.
    if _body_count(state, destination_id) + 2 > destination.body_capacity.value:
        return _reject(kind, RuleReason.NO_BODY_CAPACITY)
    return RuleResult(
        disposition=RuleDisposition.MUTATE,
        reason=RuleReason.OCCURRENCE,
        emits_event=True,
        mutates_state=True,
        action_kind=kind,
    )


def _evaluate_attack(
    state: WorldState,
    actor_id: EntityId,
    target_id: EntityId,
    kind: str,
    *,
    request_id: object,
    resolved: ResolvedActionEffects | None,
) -> RuleResult:
    structural = _attack_structural_reject(state, actor_id, target_id, kind)
    if structural is not None:
        return structural
    if resolved is None:
        return _reject(kind, RuleReason.MISSING_RESOLVED_EFFECT)
    from world.identifiers import RequestId

    if type(request_id) is not RequestId:
        raise TypeError("attack evaluation requires RequestId")
    effect = resolved.require(request_id, ResolvedAttackEffect)
    assert type(effect) is ResolvedAttackEffect
    if effect.hit:
        return RuleResult(
            disposition=RuleDisposition.MUTATE,
            reason=RuleReason.OCCURRENCE,
            emits_event=True,
            mutates_state=True,
            action_kind=kind,
        )
    return RuleResult(
        disposition=RuleDisposition.EVENT_ONLY,
        reason=RuleReason.OCCURRENCE,
        emits_event=True,
        mutates_state=False,
        action_kind=kind,
    )


def _attack_structural_reject(
    state: WorldState, actor_id: EntityId, target_id: EntityId, kind: str
) -> RuleResult | None:
    actor = state.bodies[actor_id]
    target = state.bodies[target_id]
    if target.life_status is LifeStatus.DEAD:
        return _reject(kind, RuleReason.DEAD_TARGET)
    if target.location_id != actor.location_id:
        return _reject(kind, RuleReason.NOT_COLOCATED)
    return None


def _evaluate_flee(
    state: WorldState,
    actor_id: EntityId,
    threat_id: EntityId | None,
    kind: str,
    *,
    request_id: object,
    resolved: ResolvedActionEffects | None,
) -> RuleResult:
    structural = _flee_structural_reject(state, actor_id, threat_id, kind)
    if structural is not None:
        return structural
    if resolved is None:
        return _reject(kind, RuleReason.MISSING_RESOLVED_EFFECT)
    from world.identifiers import RequestId

    if type(request_id) is not RequestId:
        raise TypeError("flee evaluation requires RequestId")
    effect = resolved.require(request_id, ResolvedFleeEffect)
    assert type(effect) is ResolvedFleeEffect
    eligible = find_eligible_flee_destinations(state, actor_id)
    if not eligible:
        return _reject(kind, RuleReason.NO_BODY_CAPACITY)
    if not effect.success:
        return RuleResult(
            disposition=RuleDisposition.EVENT_ONLY,
            reason=RuleReason.OCCURRENCE,
            emits_event=True,
            mutates_state=False,
            action_kind=kind,
        )
    assert effect.destination_index is not None
    if effect.destination_index >= len(eligible):
        return _reject(kind, RuleReason.NO_BODY_CAPACITY)
    return RuleResult(
        disposition=RuleDisposition.MUTATE,
        reason=RuleReason.OCCURRENCE,
        emits_event=True,
        mutates_state=True,
        action_kind=kind,
    )


def _flee_structural_reject(
    state: WorldState,
    actor_id: EntityId,
    threat_id: EntityId | None,
    kind: str,
) -> RuleResult | None:
    actor = state.bodies[actor_id]
    if threat_id is not None:
        threat = state.bodies[threat_id]
        if threat.life_status is LifeStatus.DEAD:
            return _reject(kind, RuleReason.DEAD_TARGET)
        if threat.location_id != actor.location_id:
            return _reject(kind, RuleReason.NOT_COLOCATED)
    location = state.locations[actor.location_id]
    if not location.adjacent:
        return _reject(kind, RuleReason.NOT_ADJACENT)
    if not find_eligible_flee_destinations(state, actor_id):
        return _reject(kind, RuleReason.NO_BODY_CAPACITY)
    return None


def _evaluate_communication(
    state: WorldState,
    actor_id: EntityId,
    recipient_id: EntityId,
    utterance: StructuredUtterance,
    kind: str,
    *,
    rules: PhysicalRules,
    tick: int | None,
) -> RuleResult:
    """Versioned communication eligibility (living, colocated, visible)."""
    if type(utterance) is not StructuredUtterance:
        raise TypeError("utterance must be StructuredUtterance")
    if utterance.declared.immediate_source_id != actor_id:
        return _reject(kind, RuleReason.COMMUNICATION_SOURCE_MISMATCH)
    recipient = state.bodies[recipient_id]
    if recipient.life_status is LifeStatus.DEAD:
        return _reject(kind, RuleReason.DEAD_TARGET)
    actor = state.bodies[actor_id]
    if recipient.location_id != actor.location_id:
        return _reject(kind, RuleReason.NOT_COLOCATED)
    location = state.locations[actor.location_id]
    weather = state.weather.get(actor.location_id)
    condition = weather.condition if weather is not None else WeatherCondition.CLEAR
    tick_value = 0 if tick is None else tick
    visibility = rules.effective_visibility(
        location_visibility=location.visibility_factor.value,
        phase=rules.day_phase_for_tick(tick_value),
        condition=condition,
    )
    if visibility < CONTENT_VISIBILITY_THRESHOLD:
        return _reject(kind, RuleReason.COMMUNICATION_INVISIBLE)
    return RuleResult(
        disposition=RuleDisposition.EVENT_ONLY,
        reason=RuleReason.OCCURRENCE,
        emits_event=True,
        mutates_state=False,
        action_kind=kind,
    )


_PRODUCTION_REASONS: Final[dict[str, RuleReason]] = {
    "production_disabled": RuleReason.PRODUCTION_DISABLED,
    "unknown_recipe": RuleReason.UNKNOWN_RECIPE,
    "recipe_action_mismatch": RuleReason.RECIPE_ACTION_MISMATCH,
    "actor_busy": RuleReason.ACTOR_BUSY,
    "materials_unavailable": RuleReason.MATERIALS_UNAVAILABLE,
    "structure_intact": RuleReason.STRUCTURE_INTACT,
    "shelter_already_present": RuleReason.SHELTER_ALREADY_PRESENT,
    "store_already_present": RuleReason.STORE_ALREADY_PRESENT,
}


def _held_artifact_count(state: WorldState, holder_id: EntityId) -> int:
    return sum(
        1 for artifact in state.artifacts.values() if artifact.holder_id == holder_id
    )


def _artifact_access_reject(
    state: WorldState,
    actor_id: EntityId,
    artifact_id: EntityId,
    kind: str,
) -> RuleResult | None:
    artifact = state.artifacts.get(artifact_id)
    if artifact is None:
        return _artifact_reject(
            kind, RuleReason.UNKNOWN_ARTIFACT, actor_id, artifact_id
        )
    actor = state.bodies[actor_id]
    if artifact.holder_id == actor_id:
        return None
    if (
        artifact.location_id is not None
        and artifact.location_id == actor.location_id
    ):
        return None
    return _artifact_reject(
        kind, RuleReason.ARTIFACT_NOT_COLOCATED, actor_id, artifact_id
    )


def _artifact_reject(
    kind: str,
    reason: RuleReason,
    actor_id: EntityId,
    artifact_id: EntityId | None,
    *,
    op: str | None = None,
    mode: str | None = None,
) -> RuleResult:
    _OPS_LOG.warning(
        "artifact_rejected actor_id=%s artifact_id=%s reason_code=%s",
        actor_id.value,
        None if artifact_id is None else artifact_id.value,
        reason.value,
    )
    _OPS_LOG.debug(
        "artifact_resolved kind=%s op=%s mode=%s reason_code=%s",
        kind,
        op or kind,
        mode or "-",
        reason.value,
    )
    return _reject(kind, reason)


def _artifact_success(
    kind: str,
    *,
    op: str,
    mode: str | None = None,
) -> RuleResult:
    _OPS_LOG.debug(
        "artifact_resolved kind=%s op=%s mode=%s reason_code=%s",
        kind,
        op,
        mode or "-",
        RuleReason.OCCURRENCE.value,
    )
    return RuleResult(
        disposition=RuleDisposition.MUTATE,
        reason=RuleReason.OCCURRENCE,
        emits_event=True,
        mutates_state=True,
        action_kind=kind,
    )


def _evaluate_inscribe(
    state: WorldState,
    operation: _InscribeOp,
    kind: str,
    *,
    resolved: ResolvedActionEffects | None,
    durable_context: DurableRecordsRuleContext | None,
) -> RuleResult:
    if operation.record_genre is not None and durable_context is None:
        return _artifact_reject(
            kind,
            RuleReason.DURABLE_RECORDS_INACTIVE,
            operation.actor_id,
            None,
            op="inscribe",
        )
    if durable_context is not None and artifact_kind_is_durable_capable(
        operation.artifact_kind
    ):
        if operation.record_genre is None:
            return _artifact_reject(
                kind,
                RuleReason.DURABLE_GENRE_REQUIRED,
                operation.actor_id,
                None,
                op="inscribe",
            )
        if operation.record_genre.value not in durable_context.enabled_genres:
            return _artifact_reject(
                kind,
                RuleReason.DURABLE_GENRE_DISABLED,
                operation.actor_id,
                None,
                op="inscribe",
            )
    if operation.hold:
        if not artifact_kind_is_portable(operation.artifact_kind):
            return _artifact_reject(
                kind,
                RuleReason.INVALID_ARTIFACT_HOLD,
                operation.actor_id,
                None,
                op="inscribe",
            )
        if (
            _held_artifact_count(state, operation.actor_id)
            >= MAX_HELD_ARTIFACTS_PER_BODY
        ):
            return _artifact_reject(
                kind,
                RuleReason.ARTIFACT_HOLD_CAP,
                operation.actor_id,
                None,
                op="inscribe",
            )
    if resolved is None:
        return _artifact_reject(
            kind,
            RuleReason.MISSING_RESOLVED_EFFECT,
            operation.actor_id,
            None,
            op="inscribe",
        )
    try:
        effect = resolved.require(
            operation.request_id, ResolvedArtifactInscribeEffect
        )
    except (TypeError, ValueError):
        return _artifact_reject(
            kind,
            RuleReason.MISSING_RESOLVED_EFFECT,
            operation.actor_id,
            None,
            op="inscribe",
        )
    assert type(effect) is ResolvedArtifactInscribeEffect
    return _artifact_success(kind, op="inscribe")


def _evaluate_amend(
    state: WorldState,
    operation: _AmendOp,
    kind: str,
    *,
    durable_context: DurableRecordsRuleContext | None,
) -> RuleResult:
    access = _artifact_access_reject(
        state, operation.actor_id, operation.artifact_id, kind
    )
    if access is not None:
        return access
    if durable_context is not None:
        artifact = state.artifacts[operation.artifact_id]
        if artifact.integrity is RecordIntegrity.DESTROYED:
            return _artifact_reject(
                kind,
                RuleReason.DURABLE_INTEGRITY_DESTROYED,
                operation.actor_id,
                operation.artifact_id,
                op="amend",
            )
    return _artifact_success(kind, op="amend")


def _evaluate_erase(
    state: WorldState,
    operation: _EraseOp,
    kind: str,
    *,
    durable_context: DurableRecordsRuleContext | None,
) -> RuleResult:
    access = _artifact_access_reject(
        state, operation.actor_id, operation.artifact_id, kind
    )
    if access is not None:
        return access
    if durable_context is not None:
        artifact = state.artifacts[operation.artifact_id]
        if artifact.integrity is RecordIntegrity.DESTROYED:
            return _artifact_reject(
                kind,
                RuleReason.DURABLE_INTEGRITY_DESTROYED,
                operation.actor_id,
                operation.artifact_id,
                op="erase",
            )
    return _artifact_success(kind, op="erase")


def _evaluate_copy_record(
    state: WorldState,
    operation: _CopyRecordOp,
    kind: str,
    *,
    resolved: ResolvedActionEffects | None,
    durable_context: DurableRecordsRuleContext | None,
) -> RuleResult:
    if durable_context is None:
        return _artifact_reject(
            kind,
            RuleReason.DURABLE_RECORDS_INACTIVE,
            operation.actor_id,
            operation.artifact_id,
            op="copy_record",
        )
    parent = state.artifacts.get(operation.artifact_id)
    if parent is None:
        return _artifact_reject(
            kind,
            RuleReason.UNKNOWN_ARTIFACT,
            operation.actor_id,
            operation.artifact_id,
            op="copy_record",
        )
    if parent.integrity is RecordIntegrity.DESTROYED:
        if durable_context.destroyed_parent_blocks_copy:
            return _artifact_reject(
                kind,
                RuleReason.DURABLE_PARENT_DESTROYED,
                operation.actor_id,
                operation.artifact_id,
                op="copy_record",
            )
    else:
        if durable_context.copy_requires_hold_or_colocation:
            access = _artifact_access_reject(
                state, operation.actor_id, operation.artifact_id, kind
            )
            if access is not None:
                return access
    if parent.record_genre is None or not artifact_kind_is_durable_capable(parent.kind):
        return _artifact_reject(
            kind,
            RuleReason.DURABLE_GENRE_REQUIRED,
            operation.actor_id,
            operation.artifact_id,
            op="copy_record",
        )
    if parent.record_genre.value not in durable_context.enabled_genres:
        return _artifact_reject(
            kind,
            RuleReason.DURABLE_GENRE_DISABLED,
            operation.actor_id,
            operation.artifact_id,
            op="copy_record",
        )
    child_generation = parent.copy_generation + 1
    if child_generation > durable_context.max_copy_generation:
        return _artifact_reject(
            kind,
            RuleReason.DURABLE_COPY_GENERATION_CAP,
            operation.actor_id,
            operation.artifact_id,
            op="copy_record",
        )
    if operation.hold:
        if not artifact_kind_is_portable(parent.kind):
            return _artifact_reject(
                kind,
                RuleReason.INVALID_ARTIFACT_HOLD,
                operation.actor_id,
                operation.artifact_id,
                op="copy_record",
            )
        if (
            _held_artifact_count(state, operation.actor_id)
            >= MAX_HELD_ARTIFACTS_PER_BODY
        ):
            return _artifact_reject(
                kind,
                RuleReason.ARTIFACT_HOLD_CAP,
                operation.actor_id,
                operation.artifact_id,
                op="copy_record",
            )
    if resolved is None:
        return _artifact_reject(
            kind,
            RuleReason.MISSING_RESOLVED_EFFECT,
            operation.actor_id,
            operation.artifact_id,
            op="copy_record",
        )
    try:
        effect = resolved.require(operation.request_id, ResolvedArtifactCopyEffect)
    except (TypeError, ValueError):
        return _artifact_reject(
            kind,
            RuleReason.MISSING_RESOLVED_EFFECT,
            operation.actor_id,
            operation.artifact_id,
            op="copy_record",
        )
    assert type(effect) is ResolvedArtifactCopyEffect
    return _artifact_success(kind, op="copy_record")


def _evaluate_annotate_record(
    state: WorldState,
    operation: _AnnotateRecordOp,
    kind: str,
    *,
    durable_context: DurableRecordsRuleContext | None,
) -> RuleResult:
    if durable_context is None:
        return _artifact_reject(
            kind,
            RuleReason.DURABLE_RECORDS_INACTIVE,
            operation.actor_id,
            operation.artifact_id,
            op="annotate_record",
        )
    access = _artifact_access_reject(
        state, operation.actor_id, operation.artifact_id, kind
    )
    if access is not None:
        return access
    artifact = state.artifacts[operation.artifact_id]
    if artifact.integrity is RecordIntegrity.DESTROYED:
        return _artifact_reject(
            kind,
            RuleReason.DURABLE_INTEGRITY_DESTROYED,
            operation.actor_id,
            operation.artifact_id,
            op="annotate_record",
        )
    if artifact.record_genre is None or not artifact_kind_is_durable_capable(
        artifact.kind
    ):
        return _artifact_reject(
            kind,
            RuleReason.DURABLE_GENRE_REQUIRED,
            operation.actor_id,
            operation.artifact_id,
            op="annotate_record",
        )
    if artifact.annotation_revisions >= durable_context.max_annotations_per_record:
        return _artifact_reject(
            kind,
            RuleReason.DURABLE_ANNOTATION_CAP,
            operation.actor_id,
            operation.artifact_id,
            op="annotate_record",
        )
    merged_marks = len(artifact.content.marks) + len(operation.content.marks)
    merged_relations = len(artifact.content.relations) + len(
        operation.content.relations
    )
    if (
        merged_marks > MAX_ARTIFACT_MARKS
        or merged_relations > MAX_ARTIFACT_RELATIONS
    ):
        return _artifact_reject(
            kind,
            RuleReason.ARTIFACT_CONTENT_INVALID,
            operation.actor_id,
            operation.artifact_id,
            op="annotate_record",
        )
    return _artifact_success(kind, op="annotate_record")


def _evaluate_damage_record(
    state: WorldState,
    operation: _DamageRecordOp,
    kind: str,
    *,
    durable_context: DurableRecordsRuleContext | None,
) -> RuleResult:
    if durable_context is None:
        return _artifact_reject(
            kind,
            RuleReason.DURABLE_RECORDS_INACTIVE,
            operation.actor_id,
            operation.artifact_id,
            op="damage_record",
        )
    access = _artifact_access_reject(
        state, operation.actor_id, operation.artifact_id, kind
    )
    if access is not None:
        return access
    artifact = state.artifacts[operation.artifact_id]
    if artifact.integrity is RecordIntegrity.DESTROYED:
        return _artifact_reject(
            kind,
            RuleReason.DURABLE_INTEGRITY_DESTROYED,
            operation.actor_id,
            operation.artifact_id,
            op="damage_record",
        )
    if artifact.record_genre is None or not artifact_kind_is_durable_capable(
        artifact.kind
    ):
        return _artifact_reject(
            kind,
            RuleReason.DURABLE_GENRE_REQUIRED,
            operation.actor_id,
            operation.artifact_id,
            op="damage_record",
        )
    if operation.mode == "damage" and not durable_context.allow_damage:
        return _artifact_reject(
            kind,
            RuleReason.DURABLE_DAMAGE_DISABLED,
            operation.actor_id,
            operation.artifact_id,
            op="damage_record",
            mode=operation.mode,
        )
    if operation.mode == "partial_loss" and not durable_context.allow_partial_loss:
        return _artifact_reject(
            kind,
            RuleReason.DURABLE_PARTIAL_LOSS_DISABLED,
            operation.actor_id,
            operation.artifact_id,
            op="damage_record",
            mode=operation.mode,
        )
    return _artifact_success(kind, op="damage_record", mode=operation.mode)


def _evaluate_transfer_artifact(
    state: WorldState, operation: _TransferArtifactOp, kind: str
) -> RuleResult:
    artifact = state.artifacts.get(operation.artifact_id)
    if artifact is None:
        return _artifact_reject(
            kind,
            RuleReason.UNKNOWN_ARTIFACT,
            operation.actor_id,
            operation.artifact_id,
            op="transfer_artifact",
            mode=operation.mode,
        )
    if not artifact_kind_is_portable(artifact.kind):
        return _artifact_reject(
            kind,
            RuleReason.ARTIFACT_NOT_PORTABLE,
            operation.actor_id,
            operation.artifact_id,
            op="transfer_artifact",
            mode=operation.mode,
        )
    actor = state.bodies[operation.actor_id]
    if operation.mode == "claim":
        if artifact.location_id != actor.location_id or artifact.holder_id is not None:
            return _artifact_reject(
                kind,
                RuleReason.ARTIFACT_NOT_COLOCATED,
                operation.actor_id,
                operation.artifact_id,
                op="transfer_artifact",
                mode=operation.mode,
            )
        if (
            _held_artifact_count(state, operation.actor_id)
            >= MAX_HELD_ARTIFACTS_PER_BODY
        ):
            return _artifact_reject(
                kind,
                RuleReason.ARTIFACT_HOLD_CAP,
                operation.actor_id,
                operation.artifact_id,
                op="transfer_artifact",
                mode=operation.mode,
            )
    elif operation.mode == "deposit":
        if artifact.holder_id != operation.actor_id:
            return _artifact_reject(
                kind,
                RuleReason.ARTIFACT_NOT_HELD,
                operation.actor_id,
                operation.artifact_id,
                op="transfer_artifact",
                mode=operation.mode,
            )
    elif operation.mode == "give":
        if artifact.holder_id != operation.actor_id:
            return _artifact_reject(
                kind,
                RuleReason.ARTIFACT_NOT_HELD,
                operation.actor_id,
                operation.artifact_id,
                op="transfer_artifact",
                mode=operation.mode,
            )
        recipient_id = operation.recipient_id
        if recipient_id is None:
            return _artifact_reject(
                kind,
                RuleReason.ARTIFACT_TRANSFER_MODE_INVALID,
                operation.actor_id,
                operation.artifact_id,
                op="transfer_artifact",
                mode=operation.mode,
            )
        recipient = state.bodies.get(recipient_id)
        if (
            recipient is None
            or recipient.life_status is LifeStatus.DEAD
            or recipient.location_id != actor.location_id
        ):
            return _artifact_reject(
                kind,
                RuleReason.RECIPIENT_UNAVAILABLE,
                operation.actor_id,
                operation.artifact_id,
                op="transfer_artifact",
                mode=operation.mode,
            )
        if _held_artifact_count(state, recipient_id) >= MAX_HELD_ARTIFACTS_PER_BODY:
            return _artifact_reject(
                kind,
                RuleReason.ARTIFACT_HOLD_CAP,
                operation.actor_id,
                operation.artifact_id,
                op="transfer_artifact",
                mode=operation.mode,
            )
    else:
        return _artifact_reject(
            kind,
            RuleReason.ARTIFACT_TRANSFER_MODE_INVALID,
            operation.actor_id,
            operation.artifact_id,
            op="transfer_artifact",
            mode=operation.mode,
        )
    return _artifact_success(
        kind, op="transfer_artifact", mode=operation.mode
    )


def _apply_inscribe(
    state: WorldState,
    operation: _InscribeOp,
    *,
    result: RuleResult,
    resolved: ResolvedActionEffects | None,
    tick: int,
    durable_context: DurableRecordsRuleContext | None,
) -> RuleApplication:
    if resolved is None:
        return RuleApplication(
            result=_artifact_reject(
                result.action_kind,
                RuleReason.MISSING_RESOLVED_EFFECT,
                operation.actor_id,
                None,
                op="inscribe",
            ),
            next_state=state,
            event_details=None,
        )
    effect = resolved.require(
        operation.request_id, ResolvedArtifactInscribeEffect
    )
    assert type(effect) is ResolvedArtifactInscribeEffect
    actor = state.bodies[operation.actor_id]
    location_id = None if operation.hold else actor.location_id
    holder_id = operation.actor_id if operation.hold else None
    source_id = (
        effect.created_artifact_id
        if durable_context is not None and operation.record_genre is not None
        else None
    )
    created = InformationArtifact(
        artifact_id=effect.created_artifact_id,
        kind=operation.artifact_kind,
        author_id=operation.actor_id,
        created_tick=tick,
        content=operation.content,
        content_revision=0,
        location_id=location_id,
        holder_id=holder_id,
        record_genre=operation.record_genre,
        source_artifact_id=source_id,
        copy_generation=0,
        integrity=RecordIntegrity.INTACT,
    )
    artifacts = dict(state.artifacts)
    artifacts[effect.created_artifact_id] = created
    next_state = rebuild_world_state(state, artifacts=artifacts)
    if operation.record_genre is not None:
        _OPS_LOG.info(
            "durable_record_created artifact_id=%s genre=%s integrity=%s",
            effect.created_artifact_id.value,
            operation.record_genre.value,
            RecordIntegrity.INTACT.value,
        )
    return RuleApplication(
        result=result,
        next_state=next_state,
        event_details=ArtifactCreated(
            artifact_id=effect.created_artifact_id,
            artifact_kind=operation.artifact_kind,
            author_id=operation.actor_id,
            content_revision=0,
            resulting_location_id=location_id,
            resulting_holder_id=holder_id,
        ),
    )


def _apply_amend(
    state: WorldState,
    operation: _AmendOp,
    *,
    result: RuleResult,
) -> RuleApplication:
    prior = state.artifacts[operation.artifact_id]
    updated = replace(
        prior,
        content=operation.content,
        content_revision=prior.content_revision + 1,
    )
    artifacts = dict(state.artifacts)
    artifacts[operation.artifact_id] = updated
    next_state = rebuild_world_state(state, artifacts=artifacts)
    return RuleApplication(
        result=result,
        next_state=next_state,
        event_details=ArtifactModified(
            artifact_id=operation.artifact_id,
            artifact_kind=updated.kind,
            content_revision=updated.content_revision,
            resulting_location_id=updated.location_id,
            resulting_holder_id=updated.holder_id,
        ),
    )


def _apply_erase(
    state: WorldState,
    operation: _EraseOp,
    *,
    result: RuleResult,
    durable_context: DurableRecordsRuleContext | None,
) -> RuleApplication:
    prior = state.artifacts[operation.artifact_id]
    artifacts = dict(state.artifacts)
    tombstone = False
    if durable_context is not None and durable_context.tombstone_on_destroy:
        updated = replace(
            prior,
            integrity=RecordIntegrity.DESTROYED,
            location_id=None,
            holder_id=None,
        )
        artifacts[operation.artifact_id] = updated
        tombstone = True
        _OPS_LOG.info(
            "durable_record_destroyed artifact_id=%s genre=%s integrity=%s "
            "tombstone=%s",
            operation.artifact_id.value,
            prior.record_genre.value if prior.record_genre is not None else "-",
            RecordIntegrity.DESTROYED.value,
            True,
        )
    else:
        del artifacts[operation.artifact_id]
    next_state = rebuild_world_state(state, artifacts=artifacts)
    return RuleApplication(
        result=result,
        next_state=next_state,
        event_details=ArtifactDestroyed(
            artifact_id=operation.artifact_id,
            artifact_kind=prior.kind,
            content_revision=prior.content_revision,
            tombstone=tombstone,
            integrity=RecordIntegrity.DESTROYED.value if tombstone else None,
        ),
    )


def _apply_copy_record(
    state: WorldState,
    operation: _CopyRecordOp,
    *,
    result: RuleResult,
    resolved: ResolvedActionEffects | None,
    tick: int,
    durable_context: DurableRecordsRuleContext,
) -> RuleApplication:
    if resolved is None:
        return RuleApplication(
            result=_artifact_reject(
                result.action_kind,
                RuleReason.MISSING_RESOLVED_EFFECT,
                operation.actor_id,
                operation.artifact_id,
                op="copy_record",
            ),
            next_state=state,
            event_details=None,
        )
    effect = resolved.require(operation.request_id, ResolvedArtifactCopyEffect)
    assert type(effect) is ResolvedArtifactCopyEffect
    parent = state.artifacts[operation.artifact_id]
    child_content = effect.child_content
    child_genre = parent.record_genre
    source_id = (
        parent.source_artifact_id
        if parent.source_artifact_id is not None
        else parent.artifact_id
    )
    actor = state.bodies[operation.actor_id]
    location_id = None if operation.hold else actor.location_id
    holder_id = operation.actor_id if operation.hold else None
    child_generation = parent.copy_generation + 1
    created = InformationArtifact(
        artifact_id=effect.created_artifact_id,
        kind=parent.kind,
        author_id=operation.actor_id,
        created_tick=tick,
        content=child_content,
        content_revision=0,
        location_id=location_id,
        holder_id=holder_id,
        record_genre=child_genre,
        parent_artifact_id=parent.artifact_id,
        source_artifact_id=source_id,
        copy_generation=child_generation,
        integrity=RecordIntegrity.INTACT,
    )
    artifacts = dict(state.artifacts)
    artifacts[effect.created_artifact_id] = created
    next_state = rebuild_world_state(state, artifacts=artifacts)
    _OPS_LOG.info(
        "durable_record_copied artifact_id=%s parent_id=%s genre=%s "
        "integrity=%s fidelity=%s generation=%s",
        effect.created_artifact_id.value,
        parent.artifact_id.value,
        child_genre.value if child_genre is not None else "-",
        RecordIntegrity.INTACT.value,
        effect.fidelity_mode,
        child_generation,
    )
    _OPS_LOG.debug(
        "durable_copy_fidelity mode=%s parent_mark_count=%s child_mark_count=%s "
        "edit_counts=%s,%s",
        effect.fidelity_mode,
        len(parent.content.marks),
        len(child_content.marks),
        effect.mark_edit_count,
        effect.relation_edit_count,
    )
    assert child_genre is not None
    return RuleApplication(
        result=result,
        next_state=next_state,
        event_details=ArtifactCopied(
            child_artifact_id=effect.created_artifact_id,
            parent_artifact_id=parent.artifact_id,
            source_artifact_id=source_id,
            fidelity_mode=effect.fidelity_mode,
            copy_generation=child_generation,
            content_revision=0,
            record_genre=child_genre.value,
        ),
    )


def _apply_annotate_record(
    state: WorldState,
    operation: _AnnotateRecordOp,
    *,
    result: RuleResult,
) -> RuleApplication:
    prior = state.artifacts[operation.artifact_id]
    merged = ArtifactContent(
        marks=prior.content.marks + operation.content.marks,
        relations=prior.content.relations + operation.content.relations,
    )
    updated = replace(
        prior,
        content=merged,
        content_revision=prior.content_revision + 1,
        annotation_revisions=prior.annotation_revisions + 1,
    )
    artifacts = dict(state.artifacts)
    artifacts[operation.artifact_id] = updated
    next_state = rebuild_world_state(state, artifacts=artifacts)
    _OPS_LOG.info(
        "durable_record_annotated artifact_id=%s genre=%s integrity=%s "
        "annotation_revisions=%s",
        operation.artifact_id.value,
        prior.record_genre.value if prior.record_genre is not None else "-",
        updated.integrity.value,
        updated.annotation_revisions,
    )
    return RuleApplication(
        result=result,
        next_state=next_state,
        event_details=ArtifactAnnotated(
            artifact_id=operation.artifact_id,
            annotation_revisions=updated.annotation_revisions,
            content_revision=updated.content_revision,
            integrity=updated.integrity.value,
        ),
    )


def _apply_damage_record(
    state: WorldState,
    operation: _DamageRecordOp,
    *,
    result: RuleResult,
    durable_context: DurableRecordsRuleContext,
) -> RuleApplication:
    prior = state.artifacts[operation.artifact_id]
    artifacts = dict(state.artifacts)
    if operation.mode == "destroy":
        tombstone = durable_context.tombstone_on_destroy
        if tombstone:
            updated = replace(
                prior,
                integrity=RecordIntegrity.DESTROYED,
                location_id=None,
                holder_id=None,
            )
            artifacts[operation.artifact_id] = updated
        else:
            del artifacts[operation.artifact_id]
        next_state = rebuild_world_state(state, artifacts=artifacts)
        _OPS_LOG.info(
            "durable_record_destroyed artifact_id=%s genre=%s integrity=%s "
            "tombstone=%s",
            operation.artifact_id.value,
            prior.record_genre.value if prior.record_genre is not None else "-",
            RecordIntegrity.DESTROYED.value,
            tombstone,
        )
        return RuleApplication(
            result=result,
            next_state=next_state,
            event_details=ArtifactDestroyed(
                artifact_id=operation.artifact_id,
                artifact_kind=prior.kind,
                content_revision=prior.content_revision,
                tombstone=tombstone,
                integrity=RecordIntegrity.DESTROYED.value if tombstone else None,
            ),
        )

    marks = prior.content.marks
    lost_delta = 0
    if operation.mode == "damage":
        drop = min(durable_context.max_mark_edits, len(marks))
        if drop:
            marks = marks[: len(marks) - drop]
            lost_delta = drop
        next_integrity = RecordIntegrity.DAMAGED
    else:
        target = durable_context.partial_loss_min_marks_remaining
        if len(marks) > target:
            lost_delta = len(marks) - target
            marks = marks[:target]
        next_integrity = RecordIntegrity.PARTIALLY_LOST

    relations = prior.content.relations
    if operation.mode == "damage":
        relation_drop = min(durable_context.max_relation_edits, len(relations))
        if relation_drop:
            relations = relations[: len(relations) - relation_drop]

    updated = replace(
        prior,
        content=ArtifactContent(marks=marks, relations=relations),
        content_revision=prior.content_revision + 1,
        integrity=next_integrity,
        lost_mark_count=prior.lost_mark_count + lost_delta,
    )
    artifacts[operation.artifact_id] = updated
    next_state = rebuild_world_state(state, artifacts=artifacts)
    _OPS_LOG.info(
        "durable_record_%s artifact_id=%s genre=%s integrity=%s "
        "lost_mark_count=%s",
        operation.mode,
        operation.artifact_id.value,
        prior.record_genre.value if prior.record_genre is not None else "-",
        next_integrity.value,
        updated.lost_mark_count,
    )
    if operation.mode == "damage":
        details: EventDetails = ArtifactDamaged(
            artifact_id=operation.artifact_id,
            prior_integrity=prior.integrity.value,
            next_integrity=next_integrity.value,
            lost_mark_count_delta=lost_delta,
            content_revision=updated.content_revision,
        )
    else:
        details = ArtifactPartiallyLost(
            artifact_id=operation.artifact_id,
            marks_remaining=len(updated.content.marks),
            lost_mark_count=updated.lost_mark_count,
            content_revision=updated.content_revision,
            integrity=next_integrity.value,
        )
    return RuleApplication(
        result=result,
        next_state=next_state,
        event_details=details,
    )


def _apply_transfer_artifact(
    state: WorldState,
    operation: _TransferArtifactOp,
    *,
    result: RuleResult,
) -> RuleApplication:
    prior = state.artifacts[operation.artifact_id]
    actor = state.bodies[operation.actor_id]
    if operation.mode == "claim":
        updated = replace(
            prior, location_id=None, holder_id=operation.actor_id
        )
    elif operation.mode == "deposit":
        updated = replace(
            prior, location_id=actor.location_id, holder_id=None
        )
    else:
        assert operation.recipient_id is not None
        updated = replace(
            prior, location_id=None, holder_id=operation.recipient_id
        )
    artifacts = dict(state.artifacts)
    artifacts[operation.artifact_id] = updated
    next_state = rebuild_world_state(state, artifacts=artifacts)
    return RuleApplication(
        result=result,
        next_state=next_state,
        event_details=ArtifactMoved(
            artifact_id=operation.artifact_id,
            artifact_kind=updated.kind,
            content_revision=updated.content_revision,
            resulting_location_id=updated.location_id,
            resulting_holder_id=updated.holder_id,
        ),
    )


def _command_for_production(operation: ValidatedWorldOperation) -> object:
    from world.actions import Build, Craft, Harvest, Repair, Store

    if type(operation) is _HarvestOp:
        return Harvest(operation.recipe_id, operation.resource_id)
    if type(operation) is _CraftOp:
        return Craft(operation.recipe_id)
    if type(operation) is _BuildOp:
        return Build(operation.recipe_id)
    if type(operation) is _RepairOp:
        return Repair(operation.recipe_id, operation.structure_id)
    assert type(operation) is _StoreOp
    return Store(operation.recipe_id, operation.item_id)


def _evaluate_production(
    state: WorldState,
    operation: ValidatedWorldOperation,
    kind: str,
    *,
    resolved: ResolvedActionEffects | None,
) -> RuleResult:
    from world._production import _warn, block_reason

    recipe_id = getattr(operation, "recipe_id", None)
    if resolved is None:
        _warn(operation.actor_id, recipe_id, "production_disabled")
        return _reject(kind, RuleReason.PRODUCTION_DISABLED)
    try:
        effect = resolved.require(operation.request_id, ResolvedProductionEffect)
    except (TypeError, ValueError):
        _warn(operation.actor_id, recipe_id, "production_disabled")
        return _reject(kind, RuleReason.PRODUCTION_DISABLED)
    if type(effect) is not ResolvedProductionEffect:
        return _reject(kind, RuleReason.PRODUCTION_DISABLED)
    if effect.reason_code is not None:
        _warn(operation.actor_id, effect.recipe_id, effect.reason_code)
        reason = _PRODUCTION_REASONS.get(
            effect.reason_code, RuleReason.PRODUCTION_DISABLED
        )
        return _reject(kind, reason)
    blocked = block_reason(
        state, operation.actor_id, _command_for_production(operation), effect.recipe
    )
    if blocked is not None:
        _warn(operation.actor_id, effect.recipe_id, blocked)
        return _reject(
            kind, _PRODUCTION_REASONS.get(blocked, RuleReason.MATERIALS_UNAVAILABLE)
        )
    return RuleResult(
        disposition=RuleDisposition.MUTATE,
        reason=RuleReason.OCCURRENCE,
        emits_event=True,
        mutates_state=True,
        action_kind=kind,
    )


def _drink_node_witness(
    prior: WorldState,
    resulting: WorldState,
    source_id: EntityId,
) -> EventDetails | None:
    from world.events import node_quantity_witness

    if source_id not in prior.resources or source_id not in resulting.resources:
        return None
    return node_quantity_witness(
        source_id,
        prior.resources[source_id].quantity,
        resulting.resources[source_id].quantity,
    )


def _apply_production(
    state: WorldState,
    operation: ValidatedWorldOperation,
    *,
    result: RuleResult,
    resolved: ResolvedActionEffects | None,
    tick: int,
    witness_resource_nodes: bool = False,
) -> RuleApplication:
    from world._production import apply_resolved

    if resolved is None:
        return RuleApplication(
            result=_reject(result.action_kind, RuleReason.PRODUCTION_DISABLED),
            next_state=state,
            event_details=None,
        )
    effect = resolved.require(operation.request_id, ResolvedProductionEffect)
    assert type(effect) is ResolvedProductionEffect
    next_state, details, reason, witness = apply_resolved(
        state,
        actor_id=operation.actor_id,
        command=_command_for_production(operation),
        effect=effect,
        tick=tick,
        witness_resource_nodes=witness_resource_nodes,
    )
    if reason is not None or details is None:
        mapped = _PRODUCTION_REASONS.get(
            reason or "production_disabled", RuleReason.PRODUCTION_DISABLED
        )
        return RuleApplication(
            result=_reject(result.action_kind, mapped),
            next_state=state,
            event_details=None,
        )
    from world.events import require_event_details

    extra: tuple[EventDetails, ...] = ()
    if witness is not None:
        extra = (require_event_details(witness),)
    return RuleApplication(
        result=result,
        next_state=next_state,
        event_details=require_event_details(details),
        extra_event_details=extra,
    )


def _reject(kind: str, reason: RuleReason) -> RuleResult:
    return RuleResult(
        disposition=RuleDisposition.REJECT,
        reason=reason,
        emits_event=False,
        mutates_state=False,
        action_kind=kind,
    )


@dataclass(frozen=True, slots=True)
class RuleApplication:
    """Pure apply result: disposition metadata plus optional next state/details."""

    result: RuleResult
    next_state: WorldState
    event_details: EventDetails | None
    extra_event_details: tuple[EventDetails, ...] = ()

    def __post_init__(self) -> None:
        if type(self.result) is not RuleResult:
            raise TypeError("RuleApplication.result must be RuleResult")
        if type(self.next_state) is not WorldState:
            raise TypeError("RuleApplication.next_state must be WorldState")
        if not isinstance(self.extra_event_details, tuple):
            raise TypeError("RuleApplication.extra_event_details must be a tuple")
        for detail in self.extra_event_details:
            from world.events import require_event_details

            require_event_details(detail)
        if self.event_details is not None and not self.result.emits_event:
            raise ValueError("event_details require emits_event")
        if self.event_details is None and self.result.emits_event:
            raise ValueError("emits_event requires event_details")
        if self.extra_event_details and not self.result.emits_event:
            raise ValueError("extra_event_details require emits_event")
        if self.extra_event_details and self.event_details is None:
            raise ValueError("extra_event_details require primary event_details")
        if self.result.mutates_state and self.next_state is None:
            raise ValueError("mutate requires next_state")

    def all_event_details(self) -> tuple[EventDetails, ...]:
        """Ordered primary and secondary details under one action cause."""
        if self.event_details is None:
            return ()
        return (self.event_details, *self.extra_event_details)


def apply_operation(
    state: WorldState,
    operation: ValidatedWorldOperation,
    *,
    rules: PhysicalRules | None = None,
    resolved: ResolvedActionEffects | None = None,
    tick: int | None = None,
    skill_efficiency: object | None = None,
    witness_resource_nodes: bool = False,
    effective_carry_capacity: Mapping[EntityId, int] | None = None,
    dependency_care_context: object | None = None,
    durable_records_context: object | None = None,
) -> RuleApplication:
    """Evaluate then apply immutable physical or event-only effects.

    Deferred and rejected outcomes never mutate state and never produce events.
    Revision bumping is owned by batch preparation, not by this helper.
    """
    physical_rules = _require_rules(rules)
    if skill_efficiency is not None:
        from world._skills import SkillEfficiencyOverride

        if type(skill_efficiency) is not SkillEfficiencyOverride:
            raise TypeError("skill_efficiency must be SkillEfficiencyOverride")
    if resolved is not None and type(resolved) is not ResolvedActionEffects:
        raise TypeError("apply_operation resolved must be ResolvedActionEffects")
    durable_context = _require_durable_records_context(durable_records_context)
    result = evaluate_operation(
        state,
        operation,
        rules=physical_rules,
        resolved=resolved,
        tick=tick,
        effective_carry_capacity=effective_carry_capacity,
        dependency_care_context=dependency_care_context,
        durable_records_context=durable_context,
    )
    if result.disposition in {
        RuleDisposition.REJECT,
        RuleDisposition.DEFERRED,
    }:
        return RuleApplication(result=result, next_state=state, event_details=None)
    if type(operation) is _SearchOp:
        return _apply_search(
            state,
            operation,
            result=result,
            rules=physical_rules,
            resolved=resolved,
            witness_resource_nodes=witness_resource_nodes,
        )
    if type(operation) is _AttackOp:
        return _apply_attack(
            state, operation, result=result, rules=physical_rules, resolved=resolved
        )
    if type(operation) in {_HarvestOp, _CraftOp, _BuildOp, _RepairOp, _StoreOp}:
        return _apply_production(
            state,
            operation,
            result=result,
            resolved=resolved,
            tick=0 if tick is None else tick,
            witness_resource_nodes=witness_resource_nodes,
        )
    if type(operation) is _InscribeOp:
        return _apply_inscribe(
            state,
            operation,
            result=result,
            resolved=resolved,
            tick=0 if tick is None else tick,
            durable_context=durable_context,
        )
    if type(operation) is _AmendOp:
        return _apply_amend(state, operation, result=result)
    if type(operation) is _EraseOp:
        return _apply_erase(
            state, operation, result=result, durable_context=durable_context
        )
    if type(operation) is _TransferArtifactOp:
        return _apply_transfer_artifact(state, operation, result=result)
    if type(operation) is _CopyRecordOp:
        assert durable_context is not None
        return _apply_copy_record(
            state,
            operation,
            result=result,
            resolved=resolved,
            tick=0 if tick is None else tick,
            durable_context=durable_context,
        )
    if type(operation) is _AnnotateRecordOp:
        return _apply_annotate_record(state, operation, result=result)
    if type(operation) is _DamageRecordOp:
        assert durable_context is not None
        return _apply_damage_record(
            state,
            operation,
            result=result,
            durable_context=durable_context,
        )
    if type(operation) is _FleeOp:
        return _apply_flee(
            state,
            operation,
            result=result,
            rules=physical_rules,
            resolved=resolved,
            skill_efficiency=skill_efficiency,
        )
    details = _event_details_for(state, operation, rules=physical_rules)
    if result.disposition is RuleDisposition.EVENT_ONLY:
        return RuleApplication(result=result, next_state=state, event_details=details)
    assert result.disposition is RuleDisposition.MUTATE
    next_state = _apply_mutation(
        state, operation, rules=physical_rules, skill_efficiency=skill_efficiency
    )
    # Recompute details from next_state for resulting physiology facts where needed.
    details = _event_details_for(
        state, operation, rules=physical_rules, next_state=next_state
    )
    extra: tuple[EventDetails, ...] = ()
    if witness_resource_nodes and type(operation) is _DrinkOp:
        witness = _drink_node_witness(state, next_state, operation.source_id)
        if witness is not None:
            extra = (witness,)
    return RuleApplication(
        result=result,
        next_state=next_state,
        event_details=details,
        extra_event_details=extra,
    )


def _apply_search(
    state: WorldState,
    operation: _SearchOp,
    *,
    result: RuleResult,
    rules: PhysicalRules,
    resolved: ResolvedActionEffects | None,
    witness_resource_nodes: bool = False,
) -> RuleApplication:
    if resolved is None:
        raise ValueError("search apply requires ResolvedActionEffects")
    effect = resolved.require(operation.request_id, ResolvedSearchEffect)
    assert type(effect) is ResolvedSearchEffect
    if not effect.success:
        return RuleApplication(
            result=result,
            next_state=state,
            event_details=Searched(target_id=effect.resource_id, success=False),
        )
    assert effect.created_item_id is not None
    resource = state.resources[effect.resource_id]
    extract = rules.resource_extraction_amount
    resulting_quantity = round_physical(resource.quantity - extract)
    item_kind = _ITEM_KIND_FOR_RESOURCE[resource.kind]
    actor = state.bodies[operation.actor_id]
    created = Item(
        entity_id=effect.created_item_id,
        name=f"foraged-{resource.kind.value}",
        kind=item_kind,
        load=ItemLoad(1),
        location_id=actor.location_id,
        holder_id=None,
    )
    resources = dict(state.resources)
    resources[effect.resource_id] = copy_resource(resource, quantity=resulting_quantity)
    items = dict(state.items)
    items[effect.created_item_id] = created
    next_state = rebuild_world_state(state, items=items, resources=resources)
    extra: tuple[EventDetails, ...] = ()
    if witness_resource_nodes:
        from world.events import node_quantity_witness

        witness = node_quantity_witness(
            effect.resource_id, resource.quantity, resulting_quantity
        )
        if witness is not None:
            extra = (witness,)
    return RuleApplication(
        result=result,
        next_state=next_state,
        event_details=Searched(
            target_id=effect.resource_id,
            success=True,
            created_item_id=effect.created_item_id,
            extracted_quantity=extract,
            resulting_resource_quantity=resulting_quantity,
        ),
        extra_event_details=extra,
    )


def _apply_attack(
    state: WorldState,
    operation: _AttackOp,
    *,
    result: RuleResult,
    rules: PhysicalRules,
    resolved: ResolvedActionEffects | None,
) -> RuleApplication:
    del rules
    if resolved is None:
        raise ValueError("attack apply requires ResolvedActionEffects")
    effect = resolved.require(operation.request_id, ResolvedAttackEffect)
    assert type(effect) is ResolvedAttackEffect
    if not effect.hit:
        return RuleApplication(
            result=result,
            next_state=state,
            event_details=Attacked(
                target_id=operation.target_id,
                hit=False,
            ),
        )
    assert effect.damage is not None
    target = state.bodies[operation.target_id]
    resulting_health = clamp_need(
        round_physical(target.health.value - float(effect.damage))
    )
    bodies = dict(state.bodies)
    if resulting_health <= 0.0:
        bodies[operation.target_id] = copy_body(
            target,
            health=Health(0.0),
            life_status=LifeStatus.DEAD,
        )
        next_state = rebuild_world_state(state, bodies=bodies)
        return RuleApplication(
            result=result,
            next_state=next_state,
            event_details=Attacked(
                target_id=operation.target_id,
                hit=True,
                damage=effect.damage,
                resulting_target_health=0.0,
            ),
            extra_event_details=(
                Died(
                    body_id=operation.target_id,
                    death_cause=DeathCause.ATTACK,
                ),
            ),
        )
    bodies[operation.target_id] = copy_body(target, health=Health(resulting_health))
    next_state = rebuild_world_state(state, bodies=bodies)
    return RuleApplication(
        result=result,
        next_state=next_state,
        event_details=Attacked(
            target_id=operation.target_id,
            hit=True,
            damage=effect.damage,
            resulting_target_health=resulting_health,
        ),
    )


def _apply_flee(
    state: WorldState,
    operation: _FleeOp,
    *,
    result: RuleResult,
    rules: PhysicalRules,
    resolved: ResolvedActionEffects | None,
    skill_efficiency: object | None = None,
) -> RuleApplication:
    if resolved is None:
        raise ValueError("flee apply requires ResolvedActionEffects")
    effect = resolved.require(operation.request_id, ResolvedFleeEffect)
    assert type(effect) is ResolvedFleeEffect
    if not effect.success:
        return RuleApplication(
            result=result,
            next_state=state,
            event_details=Fled(
                threat_id=operation.threat_id,
                success=False,
            ),
        )
    eligible = find_eligible_flee_destinations(state, operation.actor_id)
    assert effect.destination_index is not None
    if effect.destination_index >= len(eligible):
        raise ValueError("flee destination_index out of range for eligible set")
    destination_id = eligible[effect.destination_index]
    if skill_efficiency is None:
        next_state = _mutate_flee(
            state, operation.actor_id, destination_id, rules=rules
        )
    else:
        from world._skills import SkillEfficiencyOverride

        assert type(skill_efficiency) is SkillEfficiencyOverride
        next_state = _mutate_flee(
            state,
            operation.actor_id,
            destination_id,
            rules=rules,
            flee_fatigue=skill_efficiency.flee_fatigue,
        )
    prior = state.bodies[operation.actor_id]
    resulting = next_state.bodies[operation.actor_id]
    return RuleApplication(
        result=result,
        next_state=next_state,
        event_details=Fled(
            threat_id=operation.threat_id,
            success=True,
            destination_id=destination_id,
            fatigue_delta=round_physical(resulting.fatigue.value - prior.fatigue.value),
            resulting_fatigue=resulting.fatigue.value,
        ),
    )


def _event_details_for(
    state: WorldState,
    operation: ValidatedWorldOperation,
    *,
    rules: PhysicalRules,
    next_state: WorldState | None = None,
) -> EventDetails:
    match operation:
        case _MoveOp(actor_id=actor_id, destination_id=destination_id):
            resulting = next_state.bodies[actor_id] if next_state is not None else None
            prior = state.bodies[actor_id]
            fatigue_delta = (
                None
                if resulting is None
                else round_physical(resulting.fatigue.value - prior.fatigue.value)
            )
            return Moved(
                destination_id,
                resulting_location_id=(
                    None if resulting is None else resulting.location_id
                ),
                fatigue_delta=fatigue_delta,
                resulting_fatigue=(
                    None if resulting is None else resulting.fatigue.value
                ),
            )
        case _TakeOp(actor_id=actor_id, item_id=item_id):
            return Taken(item_id, resulting_holder_id=actor_id)
        case _DropOp(actor_id=actor_id, item_id=item_id):
            actor = state.bodies[actor_id]
            return Dropped(item_id, resulting_location_id=actor.location_id)
        case _GiveOp(recipient_id=recipient_id, item_id=item_id):
            return Given(recipient_id, item_id, resulting_holder_id=recipient_id)
        case _EatOp(actor_id=actor_id, item_id=item_id):
            prior = state.bodies[actor_id]
            resulting = next_state.bodies[actor_id] if next_state is not None else prior
            return Eaten(
                item_id,
                hunger_delta=round_physical(
                    resulting.hunger.value - prior.hunger.value
                ),
                resulting_hunger=resulting.hunger.value,
            )
        case _DrinkOp(actor_id=actor_id, source_id=source_id):
            prior = state.bodies[actor_id]
            resulting = next_state.bodies[actor_id] if next_state is not None else prior
            consumed_item = source_id in state.items
            quantity_delta = None
            resulting_resource_quantity = None
            if not consumed_item:
                quantity_delta = -rules.resource_extraction_amount
                if next_state is not None:
                    resulting_resource_quantity = next_state.resources[
                        source_id
                    ].quantity
            return Drunk(
                source_id,
                consumed_item=consumed_item,
                quantity_delta=quantity_delta,
                resulting_resource_quantity=resulting_resource_quantity,
                thirst_delta=round_physical(
                    resulting.thirst.value - prior.thirst.value
                ),
                resulting_thirst=resulting.thirst.value,
            )
        case _SleepOp(actor_id=actor_id):
            prior = state.bodies[actor_id]
            resulting = next_state.bodies[actor_id] if next_state is not None else prior
            return Slept(
                fatigue_delta=round_physical(
                    resulting.fatigue.value - prior.fatigue.value
                ),
                resulting_fatigue=resulting.fatigue.value,
            )
        case _HelpOp(actor_id=actor_id, target_id=target_id):
            prior_target = state.bodies[target_id]
            prior_helper = state.bodies[actor_id]
            resulting_target = (
                next_state.bodies[target_id] if next_state is not None else prior_target
            )
            resulting_helper = (
                next_state.bodies[actor_id] if next_state is not None else prior_helper
            )
            return Helped(
                target_id,
                health_delta=round_physical(
                    resulting_target.health.value - prior_target.health.value
                ),
                resulting_target_health=resulting_target.health.value,
                helper_fatigue_delta=round_physical(
                    resulting_helper.fatigue.value - prior_helper.fatigue.value
                ),
                resulting_helper_fatigue=resulting_helper.fatigue.value,
            )
        case _FeedOp(actor_id=actor_id, target_id=target_id, item_id=item_id):
            prior_target = state.bodies[target_id]
            resulting_target = (
                next_state.bodies[target_id] if next_state is not None else prior_target
            )
            item = state.items[item_id]
            hunger_delta = None
            thirst_delta = None
            resulting_hunger = None
            resulting_thirst = None
            if item.kind is ItemKind.FOOD:
                hunger_delta = round_physical(
                    resulting_target.hunger.value - prior_target.hunger.value
                )
                resulting_hunger = resulting_target.hunger.value
            else:
                thirst_delta = round_physical(
                    resulting_target.thirst.value - prior_target.thirst.value
                )
                resulting_thirst = resulting_target.thirst.value
            return Fed(
                target_id,
                item_id,
                item.kind.value,
                hunger_delta=hunger_delta,
                thirst_delta=thirst_delta,
                resulting_target_hunger=resulting_hunger,
                resulting_target_thirst=resulting_thirst,
            )
        case _TransportOp(actor_id=actor_id, target_id=target_id, destination_id=destination_id):
            prior_helper = state.bodies[actor_id]
            resulting_helper = (
                next_state.bodies[actor_id] if next_state is not None else prior_helper
            )
            return Transported(
                target_id,
                destination_id,
                origin_location_id=prior_helper.location_id,
                helper_fatigue_delta=round_physical(
                    resulting_helper.fatigue.value - prior_helper.fatigue.value
                ),
                resulting_helper_fatigue=resulting_helper.fatigue.value,
            )
        case _TalkOp(recipient_id=recipient_id, utterance=utterance):
            return Talked(recipient_id, utterance)
        case _AskOp(recipient_id=recipient_id, utterance=utterance):
            return Asked(recipient_id, utterance)
        case _TellOp(recipient_id=recipient_id, utterance=utterance):
            return Told(recipient_id, utterance)
        case _WaitOp():
            return Waited()
        case _:
            raise TypeError(f"no event details for {type(operation).__name__}")


def _apply_mutation(
    state: WorldState,
    operation: ValidatedWorldOperation,
    *,
    rules: PhysicalRules,
    skill_efficiency: object | None = None,
) -> WorldState:
    match operation:
        case _MoveOp(actor_id=actor_id, destination_id=destination_id):
            if skill_efficiency is None:
                return _mutate_move(state, actor_id, destination_id, rules=rules)
            from world._skills import SkillEfficiencyOverride

            assert type(skill_efficiency) is SkillEfficiencyOverride
            return _mutate_move(
                state,
                actor_id,
                destination_id,
                rules=rules,
                move_fatigue=skill_efficiency.move_fatigue,
            )
        case _TakeOp(actor_id=actor_id, item_id=item_id):
            return _mutate_take(state, actor_id, item_id)
        case _DropOp(actor_id=actor_id, item_id=item_id):
            return _mutate_drop(state, actor_id, item_id)
        case _GiveOp(actor_id=actor_id, recipient_id=recipient_id, item_id=item_id):
            return _mutate_give(state, actor_id, recipient_id, item_id)
        case _EatOp(actor_id=actor_id, item_id=item_id):
            return _mutate_eat(state, actor_id, item_id, rules=rules)
        case _DrinkOp(actor_id=actor_id, source_id=source_id):
            return _mutate_drink(state, actor_id, source_id, rules=rules)
        case _SleepOp(actor_id=actor_id):
            return _mutate_sleep(state, actor_id, rules=rules)
        case _HelpOp(actor_id=actor_id, target_id=target_id):
            if skill_efficiency is None:
                return _mutate_help(state, actor_id, target_id, rules=rules)
            from world._skills import SkillEfficiencyOverride

            assert type(skill_efficiency) is SkillEfficiencyOverride
            return _mutate_help(
                state,
                actor_id,
                target_id,
                rules=rules,
                help_health_gain=skill_efficiency.help_health_gain,
            )
        case _FeedOp(actor_id=actor_id, target_id=target_id, item_id=item_id):
            return _mutate_feed(state, actor_id, target_id, item_id, rules=rules)
        case _TransportOp(
            actor_id=actor_id, target_id=target_id, destination_id=destination_id
        ):
            return _mutate_transport(
                state, actor_id, target_id, destination_id, rules=rules
            )
        case _:
            raise TypeError(f"mutation unsupported for {type(operation).__name__}")


def _mutate_move(
    state: WorldState,
    actor_id: EntityId,
    destination_id: EntityId,
    *,
    rules: PhysicalRules,
    move_fatigue: float | None = None,
) -> WorldState:
    actor = state.bodies[actor_id]
    fatigue_cost = rules.move_fatigue if move_fatigue is None else move_fatigue
    fatigue = Fatigue(clamp_need(round_physical(actor.fatigue.value + fatigue_cost)))
    bodies = dict(state.bodies)
    bodies[actor_id] = copy_body(actor, location_id=destination_id, fatigue=fatigue)
    return rebuild_world_state(state, bodies=bodies)


def _mutate_take(
    state: WorldState, actor_id: EntityId, item_id: EntityId
) -> WorldState:
    actor = state.bodies[actor_id]
    item = state.items[item_id]
    items = dict(state.items)
    bodies = dict(state.bodies)
    items[item_id] = copy_item(item, location_id=None, holder_id=actor_id)
    bodies[actor_id] = copy_body(actor, inventory=(*actor.inventory, item_id))
    return rebuild_world_state(state, items=items, bodies=bodies)


def _mutate_drop(
    state: WorldState, actor_id: EntityId, item_id: EntityId
) -> WorldState:
    actor = state.bodies[actor_id]
    item = state.items[item_id]
    items = dict(state.items)
    bodies = dict(state.bodies)
    items[item_id] = copy_item(item, location_id=actor.location_id, holder_id=None)
    bodies[actor_id] = copy_body(
        actor,
        inventory=tuple(owned for owned in actor.inventory if owned != item_id),
    )
    return rebuild_world_state(state, items=items, bodies=bodies)


def _mutate_give(
    state: WorldState,
    actor_id: EntityId,
    recipient_id: EntityId,
    item_id: EntityId,
) -> WorldState:
    actor = state.bodies[actor_id]
    recipient = state.bodies[recipient_id]
    item = state.items[item_id]
    items = dict(state.items)
    bodies = dict(state.bodies)
    items[item_id] = copy_item(item, location_id=None, holder_id=recipient_id)
    bodies[actor_id] = copy_body(
        actor,
        inventory=tuple(owned for owned in actor.inventory if owned != item_id),
    )
    bodies[recipient_id] = copy_body(
        recipient, inventory=(*recipient.inventory, item_id)
    )
    return rebuild_world_state(state, items=items, bodies=bodies)


def _mutate_eat(
    state: WorldState,
    actor_id: EntityId,
    item_id: EntityId,
    *,
    rules: PhysicalRules,
) -> WorldState:
    actor = state.bodies[actor_id]
    hunger = Hunger(
        clamp_need(round_physical(actor.hunger.value - rules.eat_hunger_relief))
    )
    items = dict(state.items)
    del items[item_id]
    bodies = dict(state.bodies)
    bodies[actor_id] = copy_body(
        actor,
        hunger=hunger,
        inventory=tuple(owned for owned in actor.inventory if owned != item_id),
    )
    return rebuild_world_state(state, items=items, bodies=bodies)


def _mutate_drink(
    state: WorldState,
    actor_id: EntityId,
    source_id: EntityId,
    *,
    rules: PhysicalRules,
) -> WorldState:
    actor = state.bodies[actor_id]
    thirst = Thirst(
        clamp_need(round_physical(actor.thirst.value - rules.drink_thirst_relief))
    )
    bodies = dict(state.bodies)
    if source_id in state.items:
        items = dict(state.items)
        del items[source_id]
        bodies[actor_id] = copy_body(
            actor,
            thirst=thirst,
            inventory=tuple(owned for owned in actor.inventory if owned != source_id),
        )
        return rebuild_world_state(state, items=items, bodies=bodies)
    resource = state.resources[source_id]
    resulting_quantity = round_physical(
        resource.quantity - rules.resource_extraction_amount
    )
    resources = dict(state.resources)
    resources[source_id] = copy_resource(resource, quantity=resulting_quantity)
    bodies[actor_id] = copy_body(actor, thirst=thirst)
    return rebuild_world_state(state, bodies=bodies, resources=resources)


def _mutate_sleep(
    state: WorldState,
    actor_id: EntityId,
    *,
    rules: PhysicalRules,
) -> WorldState:
    actor = state.bodies[actor_id]
    fatigue = Fatigue(
        clamp_need(round_physical(actor.fatigue.value - rules.sleep_fatigue_recovery))
    )
    bodies = dict(state.bodies)
    bodies[actor_id] = copy_body(actor, fatigue=fatigue)
    return rebuild_world_state(state, bodies=bodies)


def _mutate_help(
    state: WorldState,
    actor_id: EntityId,
    target_id: EntityId,
    *,
    rules: PhysicalRules,
    help_health_gain: float | None = None,
) -> WorldState:
    actor = state.bodies[actor_id]
    target = state.bodies[target_id]
    health_gain = (
        rules.help_health_gain if help_health_gain is None else help_health_gain
    )
    health = Health(clamp_need(round_physical(target.health.value + health_gain)))
    fatigue = Fatigue(
        clamp_need(round_physical(actor.fatigue.value + rules.help_fatigue))
    )
    bodies = dict(state.bodies)
    bodies[target_id] = copy_body(target, health=health)
    bodies[actor_id] = copy_body(actor, fatigue=fatigue)
    return rebuild_world_state(state, bodies=bodies)


def _mutate_feed(
    state: WorldState,
    actor_id: EntityId,
    target_id: EntityId,
    item_id: EntityId,
    *,
    rules: PhysicalRules,
) -> WorldState:
    actor = state.bodies[actor_id]
    target = state.bodies[target_id]
    item = state.items[item_id]
    items = dict(state.items)
    del items[item_id]
    bodies = dict(state.bodies)
    bodies[actor_id] = copy_body(
        actor,
        inventory=tuple(owned for owned in actor.inventory if owned != item_id),
    )
    if item.kind is ItemKind.FOOD:
        hunger = Hunger(
            clamp_need(
                round_physical(target.hunger.value - rules.feed_hunger_relief)
            )
        )
        bodies[target_id] = copy_body(target, hunger=hunger)
    else:
        thirst = Thirst(
            clamp_need(
                round_physical(target.thirst.value - rules.feed_thirst_relief)
            )
        )
        bodies[target_id] = copy_body(target, thirst=thirst)
    return rebuild_world_state(state, items=items, bodies=bodies)


def _mutate_transport(
    state: WorldState,
    actor_id: EntityId,
    target_id: EntityId,
    destination_id: EntityId,
    *,
    rules: PhysicalRules,
) -> WorldState:
    actor = state.bodies[actor_id]
    target = state.bodies[target_id]
    fatigue = Fatigue(
        clamp_need(round_physical(actor.fatigue.value + rules.transport_fatigue))
    )
    bodies = dict(state.bodies)
    bodies[actor_id] = copy_body(
        actor, location_id=destination_id, fatigue=fatigue
    )
    bodies[target_id] = copy_body(target, location_id=destination_id)
    return rebuild_world_state(state, bodies=bodies)


def _mutate_flee(
    state: WorldState,
    actor_id: EntityId,
    destination_id: EntityId,
    *,
    rules: PhysicalRules,
    flee_fatigue: float | None = None,
) -> WorldState:
    actor = state.bodies[actor_id]
    fatigue_cost = rules.flee_fatigue if flee_fatigue is None else flee_fatigue
    fatigue = Fatigue(clamp_need(round_physical(actor.fatigue.value + fatigue_cost)))
    bodies = dict(state.bodies)
    bodies[actor_id] = copy_body(actor, location_id=destination_id, fatigue=fatigue)
    return rebuild_world_state(state, bodies=bodies)


def _require_rules(rules: PhysicalRules | None) -> PhysicalRules:
    if rules is None:
        return default_physical_rules()
    if type(rules) is not PhysicalRules:
        raise TypeError("rules must be PhysicalRules")
    return rules


def _require_dependency_care_context(value: object | None) -> object | None:
    if value is None:
        return None
    from world.dependency_care import DependencyCareRuleContext

    if type(value) is not DependencyCareRuleContext:
        raise TypeError(
            "dependency_care_context must be DependencyCareRuleContext or None"
        )
    return value


def _require_durable_records_context(
    value: object | None,
) -> DurableRecordsRuleContext | None:
    if value is None:
        return None
    if type(value) is not DurableRecordsRuleContext:
        raise TypeError(
            "durable_records_context must be DurableRecordsRuleContext or None"
        )
    return value


def _inventory_load(state: WorldState, body: AgentBody) -> int:
    return sum(state.items[item_id].load.value for item_id in body.inventory)


def _ground_item_count(state: WorldState, location_id: EntityId) -> int:
    return sum(1 for item in state.items.values() if item.location_id == location_id)


def _body_count(state: WorldState, location_id: EntityId) -> int:
    return sum(1 for body in state.bodies.values() if body.location_id == location_id)
