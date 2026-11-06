# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap"
"""Deterministic ``Wait`` replacement for owner-scoped conflict plans.

This screen is the only conflict helper allowed to return an ``AgentCommand``.
It applies only to an exact ``Wait`` selection, returns only existing command
types, never submits or resolves anything, and never mutates a ledger. Ordinary
``WorldEngine`` admission decides every physical outcome.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Final

from agents.cognition.organized_conflict import (
    ConflictActionAudit,
    ConflictLedger,
    ConflictOperation,
    ConflictPlan,
    ConflictPlanStatus,
    ConflictTargetKind,
    OrganizedConflictPolicy,
    conflict_target_token,
)
from agents.cognition.organized_conflict_communication import (
    ConflictAct,
    ConflictFrame,
    conflict_frame_relation,
)
from world.actions import (
    AgentCommand,
    Attack,
    Feed,
    Flee,
    Give,
    Help,
    Move,
    OpposePublicGood,
    Take,
    Tell,
    Transport,
    Wait,
)
from world.communications import origin_utterance

__all__ = ["organized_conflict_wait_replacement"]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.organized_conflict.actions"
)

_ACTIVE_STATUSES: Final[frozenset[ConflictPlanStatus]] = frozenset(
    {
        ConflictPlanStatus.PROPOSED,
        ConflictPlanStatus.JOINED,
        ConflictPlanStatus.ACTIVE,
    }
)
_TERMINAL_STATUSES: Final[frozenset[str]] = frozenset({"dead", "terminal", "removed"})


def _token(value: object) -> str | None:
    if value is None:
        return None
    raw = getattr(value, "value", value)
    if not raw:
        return None
    return conflict_target_token(str(raw))


def _targets(observation: object) -> dict[str, Any]:
    """Map every locally visible target token to its owner-safe value."""

    targets: dict[str, object] = {}

    def add(value: object) -> None:
        token = _token(value)
        if token is not None:
            targets.setdefault(token, value)

    for body in getattr(observation, "visible_bodies", ()):
        add(getattr(body, "entity_id", None))
    for location in getattr(observation, "locations", ()):
        add(getattr(location, "entity_id", None))
    for item in getattr(observation, "items", ()):
        add(getattr(item, "entity_id", None))
    for resource in getattr(observation, "resources", ()):
        add(getattr(resource, "entity_id", None))
    for structure in getattr(observation, "structures", ()):
        add(getattr(structure, "entity_id", None))
    for project in getattr(observation, "collective_projects", ()):
        add(getattr(project, "project_id", None))
    for exit_view in getattr(observation, "exits", ()):
        add(getattr(exit_view, "destination_id", None))
    self_body = getattr(observation, "self_body", None)
    if self_body is not None:
        add(getattr(self_body, "location_id", None))
    return targets


def _counterpart_targets(identity: object | None) -> dict[str, Any]:
    targets: dict[str, object] = {}
    for binding in getattr(identity, "counterparts", ()) or ():
        entity = getattr(binding, "entity_id", None)
        agent = getattr(binding, "agent_id", None)
        if entity is None:
            continue
        token = _token(agent.value if agent is not None else entity.value)
        if token is not None:
            targets.setdefault(token, entity)
    return targets


def _resolve(
    plan: ConflictPlan,
    targets: Mapping[str, object],
    observation: object,
    owner_token: str,
) -> Any:
    if plan.target_ref in targets:
        return targets[plan.target_ref]
    if plan.target_kind is ConflictTargetKind.GROUP:
        members = [
            targets[ref]
            for ref in plan.participant_refs
            if ref in targets and ref != owner_token
        ]
        if members:
            return sorted(members, key=lambda item: str(getattr(item, "value", item)))[
                0
            ]
        bodies = [
            targets[_token(body.entity_id) or ""]
            for body in getattr(observation, "visible_bodies", ())
            if _token(body.entity_id) in targets
            and _token(body.entity_id) != owner_token
        ]
        if bodies:
            return sorted(bodies, key=lambda item: str(getattr(item, "value", item)))[0]
    return None


def _bodies(observation: object) -> list[Any]:
    return list(getattr(observation, "visible_bodies", ()) or ())


def _hostile_body(observation: object, owner_token: str) -> Any:
    for occurrence in getattr(observation, "occurrences", ()) or ():
        if getattr(occurrence, "kind", "") != "attack":
            continue
        actor = _token(getattr(occurrence, "actor_id", None))
        other = _token(getattr(occurrence, "other_entity_id", None))
        if other == owner_token:
            return getattr(occurrence, "actor_id", None)
        if actor == owner_token:
            return getattr(occurrence, "other_entity_id", None)
        if actor is not None and other is None:
            return getattr(occurrence, "actor_id", None)
    return None


def _injured_ally(observation: object, owner_token: str) -> Any:
    for body in _bodies(observation):
        token = _token(getattr(body, "entity_id", None))
        if token == owner_token:
            continue
        status = str(getattr(body, "coarse_health", "")).lower()
        if status in {"injured", "critical"}:
            return getattr(body, "entity_id", None)
    return None


def _self_in_danger(observation: object) -> bool:
    self_body = getattr(observation, "self_body", None)
    if self_body is None:
        return False
    status = str(getattr(self_body, "coarse_health", "")).lower()
    return status in {"injured", "critical"}


def _held_item(observation: object) -> Any:
    for item in getattr(observation, "items", ()) or ():
        if str(getattr(item, "placement", "")).lower() == "held_by_self":
            return getattr(item, "entity_id", None)
    return None


def _loose_item(observation: object) -> Any:
    for item in getattr(observation, "items", ()) or ():
        if str(getattr(item, "placement", "")).lower() in {
            "ground_here",
            "corpse_here",
        }:
            return getattr(item, "entity_id", None)
    return None


def _completed_public_good(observation: object) -> Any:
    for project in getattr(observation, "collective_projects", ()) or ():
        if str(getattr(project, "status", "")).lower() != "completed":
            continue
        if getattr(project, "public_acts", ()) or str(
            getattr(project, "kind", "")
        ).startswith("public"):
            return getattr(project, "project_id", None)
    return None


def _route_endpoint(observation: object) -> Any:
    exits = list(getattr(observation, "exits", ()) or ())
    if not exits:
        return None
    exits.sort(key=lambda item: str(item.destination_id.value))
    return getattr(exits[0], "destination_id", None)


def _coordination_recipient(
    plan: ConflictPlan,
    targets: Mapping[str, object],
    owner_token: str,
) -> Any:
    for ref in plan.participant_refs:
        if ref != owner_token and ref in targets:
            return targets[ref]
    for ref, value in sorted(targets.items()):
        if ref != owner_token:
            return value
    return None


def _coordination_tell(
    plan: ConflictPlan,
    *,
    owner_token: str,
    tick: int,
    targets: Mapping[str, object],
    observation: object,
    policy: OrganizedConflictPolicy,
    identity: object | None,
) -> Tell | None:
    if tick > plan.start_tick and tick - plan.start_tick < policy.plan_ttl_ticks:
        return None
    if plan.status is ConflictPlanStatus.PROPOSED:
        act = ConflictAct.PROPOSE
    elif (
        plan.provenance.value == "communicated" and owner_token in plan.participant_refs
    ):
        act = ConflictAct.JOIN
    else:
        return None
    recipient = _coordination_recipient(plan, targets, owner_token)
    if recipient is None:
        return None
    frame = ConflictFrame(
        act=act,
        plan_ref=plan.plan_id,
        operation=plan.operation,
        target_kind=plan.target_kind,
        target_ref=plan.target_ref,
        role=plan.role,
        side_ref=owner_token,
        window_start=plan.start_tick,
        window_end=plan.end_tick or None,
        participant_refs=plan.participant_refs[:4],
    )
    speaker = getattr(observation, "observer_id", None)
    if speaker is None:
        return None
    utterance = origin_utterance(
        text="ocf_v1",
        speaker_id=speaker,
        concepts=("ocf_v1",),
        relations=(conflict_frame_relation(frame),),
    )
    return Tell(recipient_id=recipient, utterance=utterance)


def organized_conflict_wait_replacement(
    command: AgentCommand,
    *,
    owner_id: object,
    tick: int,
    observation: object,
    identity: object | None,
    ledger: object | None,
    policy: OrganizedConflictPolicy,
) -> tuple[AgentCommand, tuple[ConflictActionAudit, ...] | None]:
    """Return one existing command for the owner's first resolvable active plan.

    Returns the exact input command unchanged when it is not ``Wait``, when the
    ledger is absent, or when no plan has a locally resolvable target.
    """

    if type(command) is not Wait:
        return command, None
    if type(ledger) is not ConflictLedger:
        return command, None
    if ledger.owner_id != owner_id:
        raise ValueError("conflict_owner_mismatch")
    if type(tick) is not int or tick < 0:
        raise TypeError("tick must be a non-negative int")

    owner_token = _token(getattr(owner_id, "value", owner_id))
    if owner_token is None:
        return command, None
    owner_body_token = _token(getattr(observation, "observer_id", None)) or owner_token
    targets = {**_counterpart_targets(identity), **_targets(observation)}
    active_plans = sorted(
        (
            plan
            for plan in ledger.plans
            if plan.status in _ACTIVE_STATUSES
            and (
                plan.side_ref == owner_token
                or owner_token in plan.participant_refs
                or plan.provenance.value == "self_declared"
            )
        ),
        key=lambda plan: (plan.start_tick, plan.plan_id),
    )
    for plan in active_plans:
        target = _resolve(plan, targets, observation, owner_token)
        tell = _coordination_tell(
            plan,
            owner_token=owner_token,
            tick=tick,
            targets=targets,
            observation=observation,
            policy=policy,
            identity=identity,
        )
        if tell is not None:
            audit = ConflictActionAudit(
                owner_id=owner_token,
                tick=tick,
                plan_id=plan.plan_id,
                operation=plan.operation,
                role=plan.role,
                reason_code="coordination_tell",
                target_kind=plan.target_kind,
            )
            _LOG.debug(
                "organized_conflict_action owner_token=%s operation=%s role=%s "
                "reason_code=%s",
                owner_token[:8],
                plan.operation.value,
                plan.role.value,
                audit.reason_code,
            )
            return tell, (audit,)

        replacement: AgentCommand | None = None
        reason = plan.operation.value
        if plan.operation is ConflictOperation.COORDINATED_ATTACK:
            if target is not None:
                replacement = Attack(target_id=target)
        elif plan.operation is ConflictOperation.DEFENSE:
            ally = _injured_ally(observation, owner_body_token)
            hostile = _hostile_body(observation, owner_body_token)
            if ally is not None:
                replacement = Help(target_id=ally)
                reason = "defense_help"
            elif hostile is not None:
                replacement = Attack(target_id=hostile)
                reason = "defense_attack"
            elif target is not None and hasattr(target, "value"):
                replacement = Move(destination_id=target)
                reason = "defense_move"
        elif plan.operation is ConflictOperation.MOVEMENT_GROUP:
            if target is not None and hasattr(target, "value"):
                replacement = Move(destination_id=target)
        elif plan.operation is ConflictOperation.RESOURCE_CAPTURE:
            loose = _loose_item(observation)
            held = _held_item(observation)
            if loose is not None:
                replacement = Take(item_id=loose)
            elif held is not None and target is not None and hasattr(target, "value"):
                replacement = Give(recipient_id=target, item_id=held)
                reason = "resource_give"
        elif plan.operation is ConflictOperation.STRUCTURE_ATTACK:
            project = _completed_public_good(observation)
            if project is not None:
                replacement = OpposePublicGood(project_id=project)
                reason = "structure_opposition"
            elif target is not None and any(
                getattr(body, "entity_id", None) == target
                for body in _bodies(observation)
            ):
                replacement = Attack(target_id=target)
                reason = "structure_occupant_attack"
        elif plan.operation is ConflictOperation.ROUTE_BLOCKING:
            endpoint = _route_endpoint(observation)
            hostile = _hostile_body(observation, owner_body_token)
            if hostile is not None and _self_in_danger(observation):
                replacement = Flee(threat_id=hostile)
                reason = "route_block_flee"
            elif hostile is not None and _token(hostile) != owner_token:
                replacement = Attack(target_id=hostile)
                reason = "route_block_attack"
            elif endpoint is not None:
                replacement = Move(destination_id=endpoint)
                reason = "route_block_move"
        elif plan.operation is ConflictOperation.RETREAT:
            threat = _hostile_body(observation, owner_body_token)
            if threat is not None:
                replacement = Flee(threat_id=threat)
        elif plan.operation is ConflictOperation.ASSISTANCE:
            if target is not None and hasattr(target, "value"):
                replacement = Help(target_id=target)
                held = _held_item(observation)
                dependent = any(
                    _token(getattr(body, "entity_id", None)) == _token(target)
                    and getattr(body, "dependency_needs", None) is not None
                    for body in _bodies(observation)
                )
                if dependent and held is not None:
                    replacement = Feed(target_id=target, item_id=held)
                    reason = "assistance_feed"
                elif dependent:
                    endpoint = _route_endpoint(observation)
                    if endpoint is not None:
                        replacement = Transport(
                            target_id=target, destination_id=endpoint
                        )
                        reason = "assistance_transport"
        if replacement is None:
            continue
        audit = ConflictActionAudit(
            owner_id=owner_token,
            tick=tick,
            plan_id=plan.plan_id,
            operation=plan.operation,
            role=plan.role,
            reason_code=reason,
            target_kind=plan.target_kind,
        )
        _LOG.debug(
            "organized_conflict_action owner_token=%s operation=%s role=%s "
            "reason_code=%s",
            owner_token[:8],
            plan.operation.value,
            plan.role.value,
            reason,
        )
        return replacement, (audit,)
    return command, None
