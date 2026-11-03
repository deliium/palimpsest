"""Synthetic owner ledgers for detached formal-rule analysis tests."""

from __future__ import annotations

import hashlib

from agents.cognition import (
    FormalRule,
    FormalRuleAuthorityKind,
    FormalRuleConstraintKind,
    FormalRuleLedger,
    FormalRulePositionStance,
    FormalRuleProponent,
    FormalRuleProvenance,
    FormalRuleRecognition,
    FormalRuleResponse,
    FormalRuleResponseKind,
    FormalRuleScope,
    FormalRuleScopeKind,
    FormalRuleStage,
    FormalRuleStatus,
    FormalRuleSystem,
    FormalRuleVersion,
    formal_rule_id,
    formal_rule_position_id,
    formal_rule_response_id,
    formal_rule_system_id,
    formal_rule_version_id,
)
from agents.models import AgentId


def _digest(number: int) -> str:
    return hashlib.sha256(f"version-{number}".encode()).hexdigest()


def make_ledger(
    *,
    owner: str = "agent-1",
    action: str = "maintain",
    constraint: FormalRuleConstraintKind = FormalRuleConstraintKind.OBLIGATION,
    authority: FormalRuleAuthorityKind = FormalRuleAuthorityKind.CUSTOM,
    ticks: tuple[int, ...] = (0,),
    stage: FormalRuleStage = FormalRuleStage.NORM,
    status: FormalRuleStatus = FormalRuleStatus.ACTIVE,
    recognition: FormalRuleRecognition = FormalRuleRecognition.CLAIMED,
    scope_anchors: tuple[str, ...] = (),
    response_kinds: tuple[FormalRuleResponseKind, ...] = (),
    actors: tuple[str, ...] = (),
    system_status: FormalRuleStatus = FormalRuleStatus.ACTIVE,
) -> FormalRuleLedger:
    owner_id = AgentId(owner)
    scope = FormalRuleScope(FormalRuleScopeKind.UNSPECIFIED, scope_anchors)
    system_id = formal_rule_system_id(owner, scope.digest, authority)
    rule_id = formal_rule_id(owner, system_id, constraint, action, scope.digest)
    versions: list[FormalRuleVersion] = []
    previous: str | None = None
    for number, tick in enumerate(ticks, start=1):
        version = FormalRuleVersion(
            version_id=formal_rule_version_id(rule_id, number, _digest(number)),
            rule_id=rule_id,
            version_number=number,
            stage=stage,
            constraint=constraint,
            authority=authority,
            recognition=recognition,
            scope=scope,
            tick=tick,
            supersedes_version_id=previous,
        )
        versions.append(version)
        previous = version.version_id
    proponents = tuple(
        FormalRuleProponent(
            position_id=formal_rule_position_id(
                rule_id, actor, FormalRulePositionStance.PROPONENT, index
            ),
            rule_id=rule_id,
            actor_id=actor,
            stance=FormalRulePositionStance.PROPONENT,
            provenance=FormalRuleProvenance.SELF_AUTHORED,
            tick=ticks[-1],
            ordinal=index,
        )
        for index, actor in enumerate(actors)
    )
    responses = tuple(
        FormalRuleResponse(
            response_id=formal_rule_response_id(
                rule_id, owner, kind, ticks[-1]
            ),
            rule_id=rule_id,
            actor_id=owner,
            kind=kind,
            tick=ticks[-1],
        )
        for kind in response_kinds
    )
    rule = FormalRule(
        rule_id=rule_id,
        system_id=system_id,
        owner_id=owner_id,
        stage=stage,
        constraint=constraint,
        action_token=action,
        scope=scope,
        authority=authority,
        recognition=recognition,
        status=status,
        strength=0.5,
        proponents=proponents,
        versions=tuple(versions),
        responses=responses,
        first_tick=ticks[0],
        last_tick=ticks[-1],
    )
    system = FormalRuleSystem(
        system_id=system_id,
        owner_id=owner_id,
        scope=scope,
        authority=authority,
        status=system_status,
        rule_ids=(rule_id,),
        first_tick=ticks[0],
        last_tick=ticks[-1],
    )
    return FormalRuleLedger(
        owner_id=owner_id,
        systems=(system,),
        rules=(rule,),
    )
