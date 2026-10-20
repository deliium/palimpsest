"""Encode and parse mediation speech over existing utterances.

The six primary acts, seven response kinds, and three auxiliary role
expressions travel as bounded ``CommunicationRelation`` atoms inside ordinary
``Talk``/``Ask``/``Tell`` speech. Delivery proves that speech happened; it never
proves truth, consent, settlement, legitimacy, or that a named third party
endorsed anything.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final, cast

from agents.cognition.mediation import (
    MEDIATION_POLICY_VERSION,
    MediationAct,
    MediationCase,
    MediationLedger,
    MediationPolicy,
    MediationResponseKind,
    MediationRoleExpressionKind,
)
from agents.cognition.models import OwnerSafeSocialIdentity
from agents.models import AgentId
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)
from world.identifiers import EntityId
from world.observations import Observation

__all__ = [
    "MEDIATION_COMMUNICATION_POLICY_VERSION",
    "MEDIATION_PREDICATES",
    "ParsedMediationRelation",
    "encode_mediation_relation",
    "mediation_communicate_utterance",
    "parse_mediation_relation",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.mediation_communication"
)

MEDIATION_COMMUNICATION_POLICY_VERSION: Final[str] = "mediation-communication.v1"
_MAX_OBJECT_CHARS: Final[int] = 256
_MAX_RELATIONS: Final[int] = 32
_MAX_RECIPE_TERMS: Final[int] = 2

MEDIATION_PREDICATES: Final[dict[MediationAct, str]] = {
    MediationAct.HEAR_DISPUTE: "mediation_hear",
    MediationAct.REQUEST_ACCOUNTS: "mediation_request",
    MediationAct.PROPOSE_COMPROMISE: "mediation_compromise",
    MediationAct.VOUCH: "mediation_vouch",
    MediationAct.MEDIATE: "mediation_mediate",
    MediationAct.RECOMMEND_RESTITUTION: "mediation_restitution",
}
_RESPONSE_PREDICATES: Final[dict[MediationResponseKind, str]] = {
    MediationResponseKind.ACCOUNT: "mediation_account",
    MediationResponseKind.ACCEPT: "mediation_accept",
    MediationResponseKind.REFUSE: "mediation_refuse",
    MediationResponseKind.DEFER: "mediation_defer",
    MediationResponseKind.COUNTERPROPOSE: "mediation_counter",
    MediationResponseKind.WITHDRAW: "mediation_withdraw",
    MediationResponseKind.CLAIM_SETTLEMENT: "mediation_claim_settlement",
}
_ROLE_PREDICATES: Final[dict[MediationRoleExpressionKind, str]] = {
    MediationRoleExpressionKind.INVITE_MEDIATOR: "mediation_invite",
    MediationRoleExpressionKind.ENDORSE_ROLE: "mediation_endorse",
    MediationRoleExpressionKind.WITHDRAW_ROLE_ENDORSEMENT: "mediation_withdraw_role",
}
_PREDICATE_TO_ACT: Final[dict[str, MediationAct]] = {
    predicate: act for act, predicate in MEDIATION_PREDICATES.items()
}
_PREDICATE_TO_RESPONSE: Final[dict[str, MediationResponseKind]] = {
    predicate: kind for kind, predicate in _RESPONSE_PREDICATES.items()
}
_PREDICATE_TO_ROLE: Final[dict[str, MediationRoleExpressionKind]] = {
    predicate: kind for kind, predicate in _ROLE_PREDICATES.items()
}
_MARKER_SUBJECT: Final[str] = "mediation"
_MARKER_PREDICATE: Final[str] = "mediation_policy"


@dataclass(frozen=True, slots=True)
class ParsedMediationRelation:
    """Parsed closed recipe; actors are always the verified observed speaker."""

    act: MediationAct | None = None
    response_kind: MediationResponseKind | None = None
    role_kind: MediationRoleExpressionKind | None = None
    case_ref: str = ""
    revision: int = 0
    subject_token: str | None = None
    claim_token: str | None = None
    action_token: str | None = None
    proposed_entity: EntityId | None = None
    target_entity: EntityId | None = None
    item_token: str | None = None
    project_token: str | None = None
    quantity: int = 1
    terms: tuple[str, ...] = ()
    accepted_terms: tuple[str, ...] = ()
    undertaking_token: str | None = None
    recommendation_ref: str | None = None
    recommendation_revision: int | None = None
    new_case_ref: str | None = None
    withdraws_id: str | None = None
    window_first_tick: int | None = None
    window_last_tick: int | None = None
    function_token: str | None = None
    context_key: str | None = None


def _optional(token: str) -> str | None:
    value = token.strip()
    if not value or value == "-":
        return None
    return value.lower()


def _parse_int(token: str) -> int | None:
    try:
        value = int(token.strip())
    except ValueError:
        return None
    return value if value >= 0 else None


def _parse_terms(token: str) -> tuple[str, ...] | None:
    token = token.strip()
    if not token or token == "-":
        return ()
    terms: list[str] = []
    for part in token.split(","):
        if not part:
            continue
        value = part.strip().lower()
        if value in terms:
            continue
        terms.append(value)
    if len(terms) > 8:
        return None
    return tuple(terms)


def _join_terms(terms: tuple[str, ...]) -> str:
    return "-" if not terms else ",".join(terms)


def _checked_object(
    subject: str, predicate: str, payload: str
) -> CommunicationRelation:
    if len(payload) > _MAX_OBJECT_CHARS:
        raise ValueError("mediation recipe exceeds relation capacity")
    return CommunicationRelation(subject=subject, predicate=predicate, object=payload)


def _entity_token(entity: EntityId | None) -> str:
    return "-" if entity is None else entity.value


def encode_mediation_relation(
    *,
    act: MediationAct | None = None,
    response_kind: MediationResponseKind | None = None,
    role_kind: MediationRoleExpressionKind | None = None,
    case_ref: str,
    revision: int = 0,
    subject_token: str | None = None,
    claim_token: str | None = None,
    action_token: str | None = None,
    proposed_entity: EntityId | None = None,
    target_entity: EntityId | None = None,
    item_token: str | None = None,
    project_token: str | None = None,
    quantity: int = 1,
    terms: tuple[str, ...] = (),
    accepted_terms: tuple[str, ...] = (),
    undertaking_token: str | None = None,
    recommendation_ref: str | None = None,
    recommendation_revision: int | None = None,
    new_case_ref: str | None = None,
    withdraws_id: str | None = None,
    window_first_tick: int | None = None,
    window_last_tick: int | None = None,
    function_token: str | None = None,
    context_key: str | None = None,
) -> CommunicationRelation:
    """Build exactly one bounded relation atom for a selected expression."""
    if not isinstance(case_ref, str) or len(case_ref) != 64:
        raise ValueError("case_ref must be a 64-char hex id")
    if isinstance(revision, bool) or type(revision) is not int or revision < 0:
        raise ValueError("revision must be a nonnegative int")
    if len(terms) > _MAX_RECIPE_TERMS or len(accepted_terms) > _MAX_RECIPE_TERMS:
        raise ValueError("mediation recipe terms exceed relation capacity")
    if (recommendation_ref is None) != (recommendation_revision is None):
        raise ValueError("recommendation reference incomplete")
    if act is not None:
        if type(act) is not MediationAct:
            raise TypeError("act must be MediationAct")
        predicate = MEDIATION_PREDICATES[act]
        if act in {MediationAct.HEAR_DISPUTE, MediationAct.REQUEST_ACCOUNTS}:
            payload = "|".join(
                (
                    case_ref,
                    str(revision),
                    subject_token or "item_share",
                    claim_token or "-",
                )
            )
        elif act in {MediationAct.MEDIATE, MediationAct.VOUCH}:
            payload = "|".join(
                (
                    case_ref,
                    str(revision),
                    _entity_token(target_entity),
                    claim_token or "-",
                )
            )
        else:
            first = 0 if window_first_tick is None else window_first_tick
            last = first if window_last_tick is None else window_last_tick
            if last < first:
                raise ValueError("window_last_tick before window_first_tick")
            if action_token is None:
                raise ValueError("recommendation act requires an action token")
            payload = "|".join(
                (
                    case_ref,
                    str(revision),
                    action_token,
                    _entity_token(proposed_entity),
                    item_token or "-",
                    str(quantity),
                    _join_terms(terms),
                    str(first),
                    str(last),
                )
            )
        return _checked_object(subject_token or "item_share", predicate, payload)
    if response_kind is not None:
        if type(response_kind) is not MediationResponseKind:
            raise TypeError("response_kind must be MediationResponseKind")
        payload = "|".join(
            (
                case_ref,
                str(revision),
                recommendation_ref or "-",
                (
                    "-"
                    if recommendation_revision is None
                    else str(recommendation_revision)
                ),
                undertaking_token or "-",
                _join_terms(terms),
                _join_terms(accepted_terms),
                new_case_ref or "-",
                withdraws_id or "-",
            )
        )
        return _checked_object(
            subject_token or "item_share",
            _RESPONSE_PREDICATES[response_kind],
            payload,
        )
    if role_kind is not None:
        if type(role_kind) is not MediationRoleExpressionKind:
            raise TypeError("role_kind must be MediationRoleExpressionKind")
        payload = "|".join(
            (
                case_ref,
                str(revision),
                function_token or "conflict_mediation",
                context_key or "-",
                withdraws_id or "-",
            )
        )
        return _checked_object(
            subject_token or "conflict_mediation",
            _ROLE_PREDICATES[role_kind],
            payload,
        )
    raise ValueError("exactly one mediation expression kind is required")


def policy_marker_relation() -> CommunicationRelation:
    return CommunicationRelation(
        subject=_MARKER_SUBJECT,
        predicate=_MARKER_PREDICATE,
        object=MEDIATION_POLICY_VERSION,
    )


def _parse_id(token: str) -> str | None:
    value = token.strip()
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        return None
    return value


def parse_mediation_relation(
    relation: CommunicationRelation,
) -> ParsedMediationRelation | None:
    """Parse one closed recipe; malformed or unrelated atoms return ``None``."""
    if type(relation) is not CommunicationRelation:
        raise TypeError("relation must be CommunicationRelation")
    act = _PREDICATE_TO_ACT.get(relation.predicate)
    response_kind = _PREDICATE_TO_RESPONSE.get(relation.predicate)
    role_kind = _PREDICATE_TO_ROLE.get(relation.predicate)
    if act is None and response_kind is None and role_kind is None:
        return None
    parts = relation.object.split("|")
    if len(parts) < 2:
        return None
    case_ref = _parse_id(parts[0])
    revision = _parse_int(parts[1])
    if case_ref is None or revision is None:
        return None
    subject = relation.subject.strip() or None
    if act is not None:
        if act in {MediationAct.HEAR_DISPUTE, MediationAct.REQUEST_ACCOUNTS}:
            if len(parts) != 4:
                return None
            return ParsedMediationRelation(
                act=act,
                case_ref=case_ref,
                revision=revision,
                subject_token=_optional(parts[2]) or "item_share",
                claim_token=_optional(parts[3]),
            )
        if act in {MediationAct.MEDIATE, MediationAct.VOUCH}:
            if len(parts) != 4:
                return None
            return ParsedMediationRelation(
                act=act,
                case_ref=case_ref,
                revision=revision,
                subject_token=subject,
                claim_token=_optional(parts[3]),
                target_entity=_entity(parts[2]),
            )
        if len(parts) != 9:
            return None
        quantity = _parse_int(parts[5])
        first = _parse_int(parts[7])
        last = _parse_int(parts[8])
        terms = _parse_terms(parts[6])
        action = _optional(parts[2])
        if (
            quantity is None
            or first is None
            or last is None
            or last < first
            or terms is None
            or action is None
        ):
            return None
        return ParsedMediationRelation(
            act=act,
            case_ref=case_ref,
            revision=revision,
            subject_token=subject,
            action_token=action,
            proposed_entity=_entity(parts[3]),
            item_token=_optional(parts[4]),
            quantity=quantity,
            terms=terms,
            window_first_tick=first,
            window_last_tick=last,
        )
    if response_kind is not None:
        if len(parts) != 9:
            return None
        terms = _parse_terms(parts[5])
        accepted = _parse_terms(parts[6])
        if terms is None or accepted is None:
            return None
        recommendation_ref = _optional_id(parts[2])
        recommendation_revision = _parse_int(parts[3])
        if (recommendation_ref is None) != (recommendation_revision is None):
            return None
        new_case_ref = _optional_id(parts[7])
        withdraws_id = _optional_id(parts[8])
        if parts[7].strip() not in {"", "-"} and new_case_ref is None:
            return None
        if parts[8].strip() not in {"", "-"} and withdraws_id is None:
            return None
        return ParsedMediationRelation(
            response_kind=response_kind,
            case_ref=case_ref,
            revision=revision,
            subject_token=subject,
            recommendation_ref=recommendation_ref,
            recommendation_revision=recommendation_revision,
            undertaking_token=_optional(parts[4]),
            terms=terms,
            accepted_terms=accepted,
            new_case_ref=new_case_ref,
            withdraws_id=withdraws_id,
        )
    if len(parts) < 4:
        return None
    withdraws_id = _optional_id(parts[4]) if len(parts) > 4 else None
    if len(parts) > 4 and parts[4].strip() not in {"", "-"} and withdraws_id is None:
        return None
    return ParsedMediationRelation(
        role_kind=role_kind,
        case_ref=case_ref,
        revision=revision,
        subject_token=subject,
        function_token=_optional(parts[2]),
        context_key=_optional(parts[3]),
        withdraws_id=withdraws_id,
    )


def _entity(token: str) -> EntityId | None:
    value = token.strip()
    if not value or value == "-":
        return None
    try:
        return EntityId(value)
    except ValueError:
        return None


def _optional_id(token: str) -> str | None:
    value = token.strip()
    if not value or value == "-":
        return None
    return _parse_id(value)


def _is_communication_command(command: object) -> bool:
    from world.actions import Ask, Talk, Tell

    return type(command) in {Talk, Ask, Tell}


def _select_case(
    ledger: MediationLedger, owner_id: AgentId, tick: int
) -> MediationCase | None:
    for case in sorted(ledger.cases, key=lambda item: item.case_id):
        if case.actionable and case.supports_tick(tick):
            return case
    return None


def _authority_strength(
    authority: Sequence[object], mediator_id: AgentId | None
) -> float | None:
    """Mean available appraisal strength, or None when nothing is available."""
    if mediator_id is None:
        return None
    for appraisal in authority:
        if getattr(appraisal, "mediator_id", None) != mediator_id:
            continue
        available = [
            float(component.strength)
            for component in getattr(appraisal, "components", ())
            if getattr(component, "available", False)
        ]
        if not available:
            return None
        return sum(available) / len(available)
    return None


def _case_has_request(case: MediationCase) -> bool:
    return any(
        item.lineage_ref.endswith("-mediation_request") for item in case.evidence
    )


def _case_account_count(ledger: MediationLedger, case_ref: str) -> int:
    return sum(
        1
        for item in ledger.accounts
        if item.case_ref == case_ref and item.active
    )


def _response_for_recommendation(
    ledger: MediationLedger,
    owner_id: AgentId,
    tick: int,
    authority: Sequence[object],
) -> ParsedMediationRelation | None:
    """Respond to an incoming owner-directed recommendation.

    Acceptance is never forced: unavailable appraisal yields deferral, weak or
    negative appraisal yields refusal, and only positive available appraisal
    yields acceptance. The response stays revision-specific.
    """
    for recommendation in sorted(
        ledger.recommendations,
        key=lambda item: (item.case_ref, item.revision),
    ):
        if (
            not recommendation.actionable
            or recommendation.proposed_actor_id != owner_id
            or not recommendation.supports_tick(tick)
        ):
            continue
        if any(
            response.case_ref == recommendation.case_ref
            and response.actor_id == owner_id
            and response.active
            and response.recommendation_ref == recommendation.recommendation_id
            for response in ledger.responses
        ):
            continue
        strength = _authority_strength(authority, recommendation.originator_id)
        if strength is None:
            kind = MediationResponseKind.DEFER
        elif strength >= 0.6:
            kind = MediationResponseKind.ACCEPT
        elif strength <= 0.25:
            kind = MediationResponseKind.REFUSE
        elif recommendation.terms:
            kind = MediationResponseKind.COUNTERPROPOSE
        else:
            kind = MediationResponseKind.DEFER
        return ParsedMediationRelation(
            response_kind=kind,
            case_ref=recommendation.case_ref,
            revision=recommendation.revision,
            subject_token="item_share",
            recommendation_ref=recommendation.recommendation_id,
            recommendation_revision=recommendation.revision,
            undertaking_token=(
                recommendation.action_token
                if kind is MediationResponseKind.ACCEPT
                else None
            ),
            terms=("partial_terms",)
            if kind is MediationResponseKind.COUNTERPROPOSE
            else (),
            accepted_terms=(
                recommendation.terms
                if kind is MediationResponseKind.ACCEPT
                else ()
            ),
        )
    return None


def _response_for_account_request(
    ledger: MediationLedger,
    owner_id: AgentId,
    tick: int,
) -> ParsedMediationRelation | None:
    """Answer a fresh owner-visible account request with a bounded claim."""
    _ = owner_id
    for case in sorted(ledger.cases, key=lambda item: item.case_id):
        if (
            not case.actionable
            or not case.supports_tick(tick)
            or case.last_tick != tick
            or not _case_has_request(case)
        ):
            continue
        if any(
            response.case_ref == case.case_ref
            and response.kind is MediationResponseKind.ACCOUNT
            and response.active
            for response in ledger.responses
        ):
            continue
        return ParsedMediationRelation(
            response_kind=MediationResponseKind.ACCOUNT,
            case_ref=case.case_ref,
            revision=0,
            subject_token=case.subject_token,
            terms=(case.subject_token,),
        )
    return None


def _select_mediation_speech(
    ledger: MediationLedger,
    owner_id: AgentId,
    tick: int,
    authority: Sequence[object],
    identity: OwnerSafeSocialIdentity | None,
) -> ParsedMediationRelation | None:
    response = _response_for_recommendation(ledger, owner_id, tick, authority)
    if response is not None:
        return response
    response = _response_for_account_request(ledger, owner_id, tick)
    if response is not None:
        return response
    case = _select_case(ledger, owner_id, tick)
    if case is None:
        return None
    recommendation = next(
        (
            item
            for item in ledger.recommendations
            if item.case_ref == case.case_ref and item.actionable
        ),
        None,
    )
    if recommendation is not None:
        action = (
            MediationAct.RECOMMEND_RESTITUTION
            if recommendation.terms
            else MediationAct.PROPOSE_COMPROMISE
        )
        return ParsedMediationRelation(
            act=action,
            case_ref=case.case_ref,
            revision=recommendation.revision,
            subject_token=case.subject_token,
            action_token=recommendation.action_token,
            item_token=recommendation.item_token,
            quantity=recommendation.quantity,
            terms=recommendation.terms[:_MAX_RECIPE_TERMS],
            window_first_tick=recommendation.window_first_tick,
            window_last_tick=recommendation.window_last_tick,
        )
    account_count = _case_account_count(ledger, case.case_ref)
    if case.last_tick == tick and account_count == 0:
        return ParsedMediationRelation(
            act=MediationAct.HEAR_DISPUTE,
            case_ref=case.case_ref,
            revision=0,
            subject_token=case.subject_token,
            claim_token="heard_claim",
        )
    if case.last_tick == tick and account_count == 1:
        return ParsedMediationRelation(
            act=MediationAct.REQUEST_ACCOUNTS,
            case_ref=case.case_ref,
            revision=0,
            subject_token=case.subject_token,
            claim_token="request_account",
        )
    if case.last_tick == tick and account_count >= 2 and identity is not None:
        for account in sorted(
            (
                item
                for item in ledger.accounts
                if item.case_ref == case.case_ref and item.active
            ),
            key=lambda item: item.account_id,
        ):
            strength = _authority_strength(authority, account.actor_id)
            if strength is None or strength < 0.6:
                continue
            target = _counterpart_entity_for(identity, account.actor_id)
            if target is None:
                continue
            return ParsedMediationRelation(
                act=MediationAct.VOUCH,
                case_ref=case.case_ref,
                revision=0,
                subject_token=case.subject_token,
                claim_token=account.claim_token,
                target_entity=target,
            )
    return ParsedMediationRelation(
        act=MediationAct.MEDIATE,
        case_ref=case.case_ref,
        revision=0,
        subject_token=case.subject_token,
    )


def _counterpart_entity_for(
    identity: OwnerSafeSocialIdentity, agent_id: AgentId
) -> EntityId | None:
    if identity.owner_id == agent_id:
        return identity.owner_entity_id
    for binding in identity.counterparts:
        if binding.agent_id == agent_id:
            return binding.entity_id
    return None


def _selected_command_relations(
    command: object,
) -> tuple[CommunicationRelation, ...]:
    utterance = getattr(command, "utterance", None)
    content = getattr(utterance, "content", None)
    relations = getattr(content, "relations", ())
    return tuple(relations)


def mediation_communicate_utterance(
    command: object,
    *,
    owner_id: AgentId,
    tick: int,
    observation: Observation,
    identity: OwnerSafeSocialIdentity | None,
    ledger: object | None,
    mode: object | None,
    authority: Sequence[object] = (),
    act: MediationAct | None = None,
    parsed: ParsedMediationRelation | None = None,
    policy: MediationPolicy | None = None,
) -> object:
    """Stamp an existing Talk/Ask/Tell with one selected mediation relation.

    Only selected, already-admissible speech is decorated. If the resulting
    atom or relation list exceeds an existing capacity, the command is returned
    unchanged: no truncated terms and no spurious successful act.
    """
    if getattr(mode, "value", None) != "deterministic":
        return command
    if type(observation) is not Observation or observation.tick != tick:
        return command
    if not _is_communication_command(command):
        return command
    if type(ledger) is not MediationLedger or not ledger.has_content:
        return command
    if identity is None or ledger.owner_id != owner_id:
        return command
    selected = parsed
    if selected is None:
        selected = _select_mediation_speech(
            ledger,
            owner_id,
            tick,
            authority,
            identity,
        )
        if selected is None:
            return command
        if act is not None and selected.act is not act:
            return command
    try:
        relation = encode_mediation_relation(
            act=selected.act,
            response_kind=selected.response_kind,
            role_kind=selected.role_kind,
            case_ref=selected.case_ref,
            revision=selected.revision,
            subject_token=selected.subject_token,
            claim_token=selected.claim_token,
            action_token=selected.action_token,
            proposed_entity=selected.proposed_entity,
            target_entity=selected.target_entity,
            item_token=selected.item_token,
            project_token=selected.project_token,
            quantity=selected.quantity,
            terms=selected.terms,
            accepted_terms=selected.accepted_terms,
            undertaking_token=selected.undertaking_token,
            recommendation_ref=selected.recommendation_ref,
            recommendation_revision=selected.recommendation_revision,
            new_case_ref=selected.new_case_ref,
            withdraws_id=selected.withdraws_id,
            window_first_tick=selected.window_first_tick,
            window_last_tick=selected.window_last_tick,
            function_token=selected.function_token,
            context_key=selected.context_key,
        )
    except (TypeError, ValueError):
        _LOG.warning("mediation_speech_rejected reason=%s", "recipe_capacity")
        return command
    relations = (
        *_selected_command_relations(command),
        relation,
        policy_marker_relation(),
    )
    if len(relations) > _MAX_RELATIONS:
        _LOG.warning("mediation_speech_rejected reason=%s", "relation_capacity")
        return command
    utterance = origin_utterance(
        text="mediation",
        speaker_id=identity.owner_entity_id,
        communication_id=(f"mediation-{owner_id.value}-{tick}-{selected.case_ref[:8]}"),
        relations=relations,
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    _LOG.debug(
        "mediation_speech_selected owner_id=%s tick=%s kind=%s relation_count=%s",
        owner_id.value,
        tick,
        (
            selected.act.value
            if selected.act is not None
            else (
                selected.response_kind.value
                if selected.response_kind is not None
                else (
                    selected.role_kind.value
                    if selected.role_kind is not None
                    else "unknown"
                )
            )
        ),
        len(relations),
    )
    typed = cast(Any, command)
    return typed.__class__(
        recipient_id=typed.recipient_id,
        utterance=utterance,
    )
