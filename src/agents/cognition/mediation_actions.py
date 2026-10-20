"""Typed adapters from an owner's selected mediation undertaking to actions.

Only the acting owner's independently selected recommendation may compile into
an existing legal command. Unsupported terms remain discussion; nothing here
transfers another actor's property or invents a new world command.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Final

from agents.cognition.mediation import (
    MediationAttempt,
    MediationAttemptStatus,
    MediationLedger,
    MediationRecommendation,
    MediationRecommendationStatus,
)
from agents.cognition.models import OwnerSafeSocialIdentity
from agents.models import AgentId
from world.actions import AgentCommand, Give
from world.identifiers import EntityId

__all__ = [
    "compile_mediation_undertaking",
    "record_mediation_attempt",
    "selected_mediation_recommendation",
]

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.mediation_actions")

_SUPPORTED_ACTIONS: Final[frozenset[str]] = frozenset({"give"})


def selected_mediation_recommendation(
    ledger: MediationLedger,
    owner_id: AgentId,
    tick: int,
) -> MediationRecommendation | None:
    """Return the owner's actionable undertaking for this tick, if any."""
    if type(ledger) is not MediationLedger:
        raise TypeError("ledger must be MediationLedger")
    if ledger.owner_id != owner_id:
        raise ValueError("ledger owner_id mismatch")
    for case in sorted(ledger.actionable_cases, key=lambda item: item.case_id):
        for recommendation in sorted(
            ledger.recommendations,
            key=lambda item: (item.case_ref, item.revision),
        ):
            if recommendation.case_ref != case.case_ref:
                continue
            if (
                recommendation.status is not MediationRecommendationStatus.ACTIVE
                or recommendation.proposed_actor_id != owner_id
                or not recommendation.supports_tick(tick)
            ):
                continue
            return recommendation
    return None


def _counterpart_entity(
    identity: OwnerSafeSocialIdentity, agent_id: AgentId
) -> EntityId | None:
    if agent_id == identity.owner_id:
        return identity.owner_entity_id
    for binding in identity.counterparts:
        if binding.agent_id == agent_id:
            return binding.entity_id
    return None


def compile_mediation_undertaking(
    ledger: MediationLedger,
    *,
    owner_id: AgentId,
    tick: int,
    identity: OwnerSafeSocialIdentity,
    inventory: tuple[EntityId, ...],
) -> tuple[MediationRecommendation, AgentCommand] | None:
    """Compile the exact selected undertaking, never a merely similar action.

    A named non-food held item compiles to ``Give(item_id=..., recipient_id=...)``
    using the existing command signature. Unsupported, missing, or unresolvable
    terms return ``None``; they are not replaced by another action.
    """
    if type(ledger) is not MediationLedger:
        raise TypeError("ledger must be MediationLedger")
    if type(identity) is not OwnerSafeSocialIdentity:
        raise TypeError("identity must be OwnerSafeSocialIdentity")
    if ledger.owner_id != owner_id or identity.owner_id != owner_id:
        raise ValueError("owner mismatch")
    recommendation = selected_mediation_recommendation(ledger, owner_id, tick)
    if recommendation is None:
        return None
    if recommendation.action_token not in _SUPPORTED_ACTIONS:
        _LOG.debug(
            "mediation_undertaking_unsupported owner_id=%s action=%s",
            owner_id.value,
            recommendation.action_token,
        )
        return None
    if not recommendation.target_ids:
        return None
    recipient = _counterpart_entity(identity, recommendation.target_ids[0])
    if recipient is None:
        return None
    if recommendation.item_token is None:
        return None
    wanted = recommendation.item_token.lower()
    matches = tuple(item for item in inventory if item.value.lower() == wanted)
    if len(matches) != 1:
        return None
    command: AgentCommand = Give(recipient_id=recipient, item_id=matches[0])
    _LOG.debug(
        "mediation_undertaking_compiled owner_id=%s case_ref=%s revision=%s",
        owner_id.value,
        recommendation.case_ref[:8],
        recommendation.revision,
    )
    return recommendation, command


def record_mediation_attempt(
    ledger: MediationLedger,
    recommendation: MediationRecommendation,
    *,
    owner_id: AgentId,
    tick: int,
    final_command: object,
    identity: OwnerSafeSocialIdentity | None = None,
) -> MediationLedger:
    """Attribute only an exactly matching final command as an attempt.

    A different Give (wrong recipient or item), a non-Give command, or a
    command that cannot be reconciled with the recommendation is no attempt.
    """
    if type(ledger) is not MediationLedger:
        raise TypeError("ledger must be MediationLedger")
    if recommendation.owner_id != owner_id:
        raise ValueError("recommendation owner mismatch")
    if type(final_command) is not Give or not recommendation.target_ids:
        _LOG.debug(
            "mediation_attempt_skipped owner_id=%s reason=%s",
            owner_id.value,
            "non_matching_command",
        )
        return ledger
    if identity is not None:
        expected_recipient = _counterpart_entity(
            identity, recommendation.target_ids[0]
        )
        if (
            expected_recipient is None
            or final_command.recipient_id != expected_recipient
        ):
            _LOG.debug(
                "mediation_attempt_skipped owner_id=%s reason=%s",
                owner_id.value,
                "recipient_mismatch",
            )
            return ledger
    if recommendation.item_token is not None and (
        final_command.item_id.value.lower() != recommendation.item_token
    ):
        _LOG.debug(
            "mediation_attempt_skipped owner_id=%s reason=%s",
            owner_id.value,
            "item_mismatch",
        )
        return ledger
    status = MediationAttemptStatus.ATTEMPTED
    command_token: str | None = "give"
    if not recommendation.supports_tick(tick):
        status = MediationAttemptStatus.BLOCKED
    attempt_id = hashlib.sha256(
        (
            f"{owner_id.value}|mediation-attempt|{recommendation.case_ref}|"
            f"{recommendation.revision}|{tick}|{len(ledger.attempts)}"
        ).encode()
    ).hexdigest()
    attempt = MediationAttempt(
        attempt_id=attempt_id,
        owner_id=owner_id,
        case_ref=recommendation.case_ref,
        actor_id=owner_id,
        status=status,
        tick=tick,
        recommendation_ref=recommendation.recommendation_id,
        recommendation_revision=recommendation.revision,
        action_token=recommendation.action_token,
        target_ids=recommendation.target_ids,
        item_token=recommendation.item_token,
        resulting_command_token=command_token,
        notices=()
        if status is MediationAttemptStatus.ATTEMPTED
        else ("expired_reference",),
    )
    _LOG.debug(
        "mediation_attempt_recorded owner_id=%s status=%s tick=%s",
        owner_id.value,
        status.value,
        tick,
    )
    return MediationLedger(
        owner_id=ledger.owner_id,
        cases=ledger.cases,
        accounts=ledger.accounts,
        recommendations=ledger.recommendations,
        responses=ledger.responses,
        role_expressions=ledger.role_expressions,
        attempts=(*ledger.attempts, attempt),
        outcomes=ledger.outcomes,
        notices=ledger.notices,
        policy_version=ledger.policy_version,
        retired_case_refs=ledger.retired_case_refs,
        first_observed_tick=ledger.first_observed_tick,
        last_observed_tick=ledger.last_observed_tick,
        observation_count=ledger.observation_count,
        pruned_case_count=ledger.pruned_case_count,
        pruned_evidence_count=ledger.pruned_evidence_count,
        pruned_recommendation_count=ledger.pruned_recommendation_count,
        pruned_response_count=ledger.pruned_response_count,
    )
