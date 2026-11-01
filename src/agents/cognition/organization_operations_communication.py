"""Bounded organization operation claims carried inside existing speech.

Operational acts must be socially expressible without granting authority. An
owner therefore states an admission, departure, assignment, control, procedure,
or commitment claim through ordinary ``Talk``/``Tell``. The claim travels as one
closed ``org_op_v1`` relation atom; delivery proves that speech happened and
never proves membership, authority, control, or that a decision occurred. No
command, event, observer semantic type, or free-text payload is added, and the
V4-03 ``org_v1`` frame is unchanged.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any, Final, NoReturn, cast

from agents.cognition.organization_concepts import organization_label_is_forbidden
from agents.cognition.organization_operations import (
    ORGANIZATION_ANCHOR_KINDS,
    OrganizationAdmissionBelief,
    OrganizationAdmissionStance,
    OrganizationAssignmentBelief,
    OrganizationAssignmentStance,
    OrganizationCommitmentOperationBelief,
    OrganizationCommitmentStance,
    OrganizationControlBelief,
    OrganizationControlStance,
    OrganizationDepartureBelief,
    OrganizationDepartureStance,
    OrganizationOperationAct,
    OrganizationOperationError,
    OrganizationOperationLedger,
    OrganizationOperationOutcome,
    OrganizationProcedureActionBelief,
    organization_operation_ref,
    require_organization_operation_ref,
)
from world.communications import CommunicationRelation

__all__ = [
    "ORGANIZATION_OPERATION_COMMUNICATION_POLICY_VERSION",
    "ORGANIZATION_OPERATION_FRAME_SUBJECT",
    "ORGANIZATION_OPERATION_PREDICATES",
    "OrganizationOperationClaim",
    "encode_organization_operation_claim",
    "organization_operation_claim_relation",
    "organization_operation_communicate_utterance",
    "parse_organization_operation_claim",
    "parse_organization_operation_claim_relation",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.organization_operations_communication"
)

ORGANIZATION_OPERATION_COMMUNICATION_POLICY_VERSION: Final[str] = (
    "organization-operations-communication.v1"
)
ORGANIZATION_OPERATION_FRAME_SUBJECT: Final[str] = "org_op_v1"
ORGANIZATION_OPERATION_PREDICATES: Final[Mapping[OrganizationOperationAct, str]] = (
    MappingProxyType(
        {
            OrganizationOperationAct.ADMIT: "org_admit",
            OrganizationOperationAct.DEPART: "org_depart",
            OrganizationOperationAct.ASSIGN: "org_assign",
            OrganizationOperationAct.REMOVE: "org_remove",
            OrganizationOperationAct.AUTHORIZE_CONTROL: "org_authorize",
            OrganizationOperationAct.REVOKE_CONTROL: "org_revoke",
            OrganizationOperationAct.INVOKE_PROCEDURE: "org_invoke",
            OrganizationOperationAct.DECLARE_COMMITMENT: "org_commit",
            OrganizationOperationAct.FULFILL_COMMITMENT: "org_fulfill",
            OrganizationOperationAct.RECORD_DECISION: "org_record",
        }
    )
)
_PREDICATE_TO_ACT: Final[Mapping[str, OrganizationOperationAct]] = MappingProxyType(
    {predicate: act for act, predicate in ORGANIZATION_OPERATION_PREDICATES.items()}
)

_LABEL_TOKEN_MAX_LEN: Final[int] = 32
_LABEL_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_DIGITS_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9]+$")
_MAX_FRAME_CHARS: Final[int] = 256
_MAX_RELATIONS: Final[int] = 32
_NONE_TOKEN: Final[str] = "none"

_CONTROL_STANCES: Final[frozenset[str]] = frozenset(
    member.value for member in OrganizationControlStance
)
_ADMISSION_STANCES: Final[frozenset[str]] = frozenset(
    member.value for member in OrganizationAdmissionStance
)
_DEPARTURE_STANCES: Final[frozenset[str]] = frozenset(
    member.value for member in OrganizationDepartureStance
)
_ASSIGNMENT_STANCES: Final[frozenset[str]] = frozenset(
    member.value for member in OrganizationAssignmentStance
)
_COMMITMENT_STANCES: Final[frozenset[str]] = frozenset(
    member.value for member in OrganizationCommitmentStance
)

_STANCES_BY_ACT: Final[Mapping[OrganizationOperationAct, frozenset[str]]] = (
    MappingProxyType(
        {
            OrganizationOperationAct.ADMIT: _ADMISSION_STANCES,
            OrganizationOperationAct.DEPART: _DEPARTURE_STANCES,
            OrganizationOperationAct.ASSIGN: _ASSIGNMENT_STANCES,
            OrganizationOperationAct.REMOVE: _ASSIGNMENT_STANCES,
            OrganizationOperationAct.AUTHORIZE_CONTROL: _CONTROL_STANCES,
            OrganizationOperationAct.REVOKE_CONTROL: _CONTROL_STANCES,
            OrganizationOperationAct.INVOKE_PROCEDURE: _CONTROL_STANCES,
            OrganizationOperationAct.DECLARE_COMMITMENT: _COMMITMENT_STANCES,
            OrganizationOperationAct.FULFILL_COMMITMENT: _COMMITMENT_STANCES,
            OrganizationOperationAct.RECORD_DECISION: frozenset(
                {
                    OrganizationControlStance.CLAIMED.value,
                    OrganizationControlStance.DISPUTED.value,
                    OrganizationControlStance.UNKNOWN.value,
                }
            ),
        }
    )
)


def _fail() -> NoReturn:
    raise OrganizationOperationError("organization_operation_invalid")


def _require_label_token(value: object) -> str | None:
    if value is None:
        return None
    if type(value) is not str:
        _fail()
    if len(value) > _LABEL_TOKEN_MAX_LEN or _LABEL_TOKEN_PATTERN.match(value) is None:
        _fail()
    if organization_label_is_forbidden(value):
        _fail()
    return value


def _require_optional_ref(value: object) -> str | None:
    if value is None:
        return None
    return require_organization_operation_ref(value)


def _require_expires(value: object) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 0:
        _fail()
    return value


@dataclass(frozen=True, slots=True)
class OrganizationOperationClaim:
    """One closed self-authored operational claim."""

    act: OrganizationOperationAct
    stance: str
    label_token: str | None = None
    target_ref: str | None = None
    anchor_kind: str = "unknown"
    anchor_ref: str | None = None
    authority_ref: str | None = None
    expires_tick: int | None = None

    def __post_init__(self) -> None:
        if type(self.act) is not OrganizationOperationAct:
            _fail()
        if type(self.stance) is not str or self.stance not in _STANCES_BY_ACT[
            self.act
        ]:
            _fail()
        object.__setattr__(self, "label_token", _require_label_token(self.label_token))
        object.__setattr__(
            self, "target_ref", _require_optional_ref(self.target_ref)
        )
        if (
            type(self.anchor_kind) is not str
            or self.anchor_kind not in ORGANIZATION_ANCHOR_KINDS
        ):
            _fail()
        object.__setattr__(
            self, "anchor_ref", _require_optional_ref(self.anchor_ref)
        )
        object.__setattr__(
            self, "authority_ref", _require_optional_ref(self.authority_ref)
        )
        object.__setattr__(self, "expires_tick", _require_expires(self.expires_tick))
        if self.act is not OrganizationOperationAct.ADMIT:
            if self.expires_tick is not None:
                _fail()
        if self.anchor_kind == "unknown":
            if self.anchor_ref is not None:
                _fail()
        elif self.anchor_ref is None:
            _fail()


def encode_organization_operation_claim(claim: OrganizationOperationClaim) -> str:
    """Encode one claim into the bounded ``org_op_v1`` frame."""

    if type(claim) is not OrganizationOperationClaim:
        raise TypeError("claim must be OrganizationOperationClaim")
    predicate = ORGANIZATION_OPERATION_PREDICATES[claim.act]
    label = _NONE_TOKEN if claim.label_token is None else claim.label_token
    target = _NONE_TOKEN if claim.target_ref is None else claim.target_ref
    anchor = _NONE_TOKEN if claim.anchor_ref is None else claim.anchor_ref
    authority = _NONE_TOKEN if claim.authority_ref is None else claim.authority_ref
    expiry = _NONE_TOKEN if claim.expires_tick is None else str(claim.expires_tick)
    return (
        f"{ORGANIZATION_OPERATION_FRAME_SUBJECT}:{predicate}:{label}:{target}:"
        f"{claim.anchor_kind}:{anchor}:{authority}:{claim.stance}:{expiry}"
    )


def parse_organization_operation_claim(text: str) -> OrganizationOperationClaim:
    """Parse one strict ``org_op_v1`` frame; malformed text fails closed."""

    if type(text) is not str:
        _fail()
    if len(text) > _MAX_FRAME_CHARS:
        _fail()
    if any(character.isspace() or ord(character) < 32 for character in text):
        _fail()
    parts = text.split(":")
    if len(parts) != 9:
        _fail()
    (
        subject,
        predicate,
        label,
        target,
        anchor_kind,
        anchor_ref,
        authority,
        stance,
        expires,
    ) = parts
    if subject != ORGANIZATION_OPERATION_FRAME_SUBJECT:
        _fail()
    act = _PREDICATE_TO_ACT.get(predicate)
    if act is None:
        _fail()
    if stance not in _STANCES_BY_ACT[act]:
        _fail()
    label_token = None if label == _NONE_TOKEN else _require_label_token(label)
    target_ref = (
        None if target == _NONE_TOKEN else require_organization_operation_ref(target)
    )
    if anchor_kind not in ORGANIZATION_ANCHOR_KINDS:
        _fail()
    anchor = (
        None
        if anchor_ref == _NONE_TOKEN
        else require_organization_operation_ref(anchor_ref)
    )
    authority_ref = (
        None
        if authority == _NONE_TOKEN
        else require_organization_operation_ref(authority)
    )
    if expires == _NONE_TOKEN:
        expires_tick = None
    elif _DIGITS_PATTERN.match(expires) is None:
        _fail()
    else:
        expires_tick = _require_expires(int(expires))
    return OrganizationOperationClaim(
        act=act,
        stance=stance,
        label_token=label_token,
        target_ref=target_ref,
        anchor_kind=anchor_kind,
        anchor_ref=anchor,
        authority_ref=authority_ref,
        expires_tick=expires_tick,
    )


def organization_operation_claim_relation(
    claim: OrganizationOperationClaim,
) -> CommunicationRelation:
    """Build one bounded relation atom for an operational claim."""

    if type(claim) is not OrganizationOperationClaim:
        raise TypeError("claim must be OrganizationOperationClaim")
    frame = encode_organization_operation_claim(claim).split(":", 2)[2]
    return CommunicationRelation(
        subject=ORGANIZATION_OPERATION_FRAME_SUBJECT,
        predicate=ORGANIZATION_OPERATION_PREDICATES[claim.act],
        object=frame,
    )


def parse_organization_operation_claim_relation(
    relation: object,
) -> OrganizationOperationClaim | None:
    """Parse one operation relation; unrelated or malformed atoms are ``None``."""

    if type(relation) is not CommunicationRelation:
        raise TypeError("relation must be CommunicationRelation")
    if relation.subject != ORGANIZATION_OPERATION_FRAME_SUBJECT:
        return None
    if relation.predicate not in _PREDICATE_TO_ACT:
        return None
    try:
        return parse_organization_operation_claim(
            f"{ORGANIZATION_OPERATION_FRAME_SUBJECT}:"
            f"{relation.predicate}:{relation.object}"
        )
    except OrganizationOperationError:
        return None


def _is_expressible(command: object) -> bool:
    from world.actions import Talk, Tell

    return type(command) in {Talk, Tell}


def _claim_for_control(
    record: OrganizationControlBelief,
) -> tuple[int, str, int, OrganizationOperationClaim]:
    act = (
        OrganizationOperationAct.REVOKE_CONTROL
        if record.stance is OrganizationControlStance.FORMER
        else OrganizationOperationAct.AUTHORIZE_CONTROL
    )
    anchor_ref = (
        None
        if record.anchor_kind == "unknown"
        else organization_operation_ref(record.anchor_id, namespace="anchor")
    )
    claim = OrganizationOperationClaim(
        act=act,
        stance=record.stance.value,
        anchor_kind=record.anchor_kind,
        anchor_ref=anchor_ref,
    )
    priority = 2 if record.stance is OrganizationControlStance.RECOGNIZED else 3
    return priority, record.anchor_kind, record.last_tick, claim


def _claim_for_admission(
    record: OrganizationAdmissionBelief,
) -> tuple[int, str, int, OrganizationOperationClaim]:
    unresolved = record.stance in (
        OrganizationAdmissionStance.CLAIMED,
        OrganizationAdmissionStance.UNKNOWN,
    )
    claim = OrganizationOperationClaim(
        act=OrganizationOperationAct.ADMIT,
        stance=record.stance.value,
        target_ref=organization_operation_ref(record.member_id, namespace="target"),
        anchor_kind="member",
        anchor_ref=organization_operation_ref(record.member_id, namespace="anchor"),
        expires_tick=record.expires_tick,
    )
    if record.stance is OrganizationAdmissionStance.DISPUTED:
        priority = 0
    elif unresolved:
        priority = 1
    else:
        priority = 3
    return priority, "member", record.last_tick, claim


def _claim_for_departure(
    record: OrganizationDepartureBelief,
) -> tuple[int, str, int, OrganizationOperationClaim]:
    claim = OrganizationOperationClaim(
        act=OrganizationOperationAct.DEPART,
        stance=record.stance.value,
        target_ref=organization_operation_ref(record.member_id, namespace="target"),
        anchor_kind="member",
        anchor_ref=organization_operation_ref(record.member_id, namespace="anchor"),
    )
    priority = 0 if record.stance is OrganizationDepartureStance.DISPUTED else 3
    return priority, "member", record.last_tick, claim


def _claim_for_assignment(
    record: OrganizationAssignmentBelief,
) -> tuple[int, str, int, OrganizationOperationClaim]:
    act = (
        OrganizationOperationAct.REMOVE
        if record.stance is OrganizationAssignmentStance.REMOVED
        else OrganizationOperationAct.ASSIGN
    )
    claim = OrganizationOperationClaim(
        act=act,
        stance=record.stance.value,
        target_ref=organization_operation_ref(
            record.occupant_id, namespace="target"
        ),
        anchor_kind="unknown",
        anchor_ref=None,
        authority_ref=organization_operation_ref(
            record.office_id, namespace="role_signature"
        ),
    )
    priority = 0 if record.stance is OrganizationAssignmentStance.DISPUTED else 3
    return priority, record.office_id, record.last_tick, claim


def _claim_for_procedure(
    record: OrganizationProcedureActionBelief,
) -> tuple[int, str, int, OrganizationOperationClaim]:
    claim = OrganizationOperationClaim(
        act=OrganizationOperationAct.INVOKE_PROCEDURE,
        stance=OrganizationControlStance.RECOGNIZED.value,
        anchor_kind="unknown",
        anchor_ref=None,
    )
    priority = (
        2
        if record.outcome
        in (
            OrganizationOperationOutcome.OBSERVED,
            OrganizationOperationOutcome.COMPLETED,
        )
        else 3
    )
    return priority, record.procedure_ref, record.last_tick, claim


def _claim_for_commitment(
    record: OrganizationCommitmentOperationBelief,
) -> tuple[int, str, int, OrganizationOperationClaim]:
    act = (
        OrganizationOperationAct.FULFILL_COMMITMENT
        if record.stance is OrganizationCommitmentStance.FULFILLED
        else OrganizationOperationAct.DECLARE_COMMITMENT
    )
    claim = OrganizationOperationClaim(
        act=act,
        stance=record.stance.value,
        target_ref=organization_operation_ref(
            record.counterpart_id, namespace="target"
        ),
        anchor_kind="unknown",
        anchor_ref=None,
        authority_ref=organization_operation_ref(
            record.commitment_id, namespace="decision_content"
        ),
    )
    priority = 0 if record.stance is OrganizationCommitmentStance.DISPUTED else 3
    return priority, record.commitment_id, record.last_tick, claim


def _select_operation_claim(
    ledger: OrganizationOperationLedger,
) -> OrganizationOperationClaim | None:
    """Select one deterministic operational claim, or ``None``."""

    candidates: list[
        tuple[int, str, int, OrganizationOperationClaim]
    ] = []
    for concept in ledger.concepts:
        for record in concept.controls:
            candidates.append(_claim_for_control(record))
        for record in concept.admissions:
            candidates.append(_claim_for_admission(record))
        for record in concept.departures:
            candidates.append(_claim_for_departure(record))
        for record in concept.assignments:
            candidates.append(_claim_for_assignment(record))
        for record in concept.procedures:
            candidates.append(_claim_for_procedure(record))
        for record in concept.commitments:
            candidates.append(_claim_for_commitment(record))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    return candidates[0][3]


def organization_operation_communicate_utterance(
    command: object, ledger: object | None
) -> object:
    """Attach at most one ``org_op_v1`` relation to an already-selected utterance.

    The command type, recipient, delivery, and every existing relation are
    preserved. A disabled, empty, or claim-free ledger returns the command
    unchanged.
    """

    if type(ledger) is not OrganizationOperationLedger:
        return command
    if not ledger.concepts:
        return command
    if not _is_expressible(command):
        return command
    claim = _select_operation_claim(ledger)
    if claim is None:
        return command
    utterance = getattr(command, "utterance", None)
    if utterance is None:
        return command
    content = getattr(utterance, "content", None)
    if content is None:
        return command
    relations = tuple(getattr(content, "relations", ()))
    if any(
        relation.subject == ORGANIZATION_OPERATION_FRAME_SUBJECT
        or relation.predicate
        in {predicate for predicate in _PREDICATE_TO_ACT}
        for relation in relations
    ):
        return command
    if len(relations) >= _MAX_RELATIONS:
        _LOG.warning(
            "organization_operation_claim_skipped reason=relation_cap"
        )
        return command
    updated_content = replace(
        content, relations=(*relations, organization_operation_claim_relation(claim))
    )
    updated_utterance = replace(utterance, content=updated_content)
    _LOG.debug(
        "organization_operation_claim act=%s stance=%s",
        claim.act.value,
        claim.stance,
    )
    typed = cast(Any, command)
    return typed.__class__(
        recipient_id=typed.recipient_id,
        utterance=updated_utterance,
    )
