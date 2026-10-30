"""Bounded organization claims carried inside existing speech.

Explicit and disputed membership must be self-authored, so an owner expresses a
claim through ordinary ``Talk``/``Tell``. The claim travels as one closed
``CommunicationRelation`` atom; delivery proves that speech happened and never
proves that an organization exists, that a member belongs, or that a label is
shared. No command, event, observer semantic type, or free-text payload is
added.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, replace
from typing import Any, Final, NoReturn, cast

from agents.cognition.organization_concepts import (
    OrganizationConceptError,
    OrganizationConceptLedger,
    OrganizationIdentityStance,
    OrganizationStatus,
    organization_label_is_forbidden,
)
from world.communications import CommunicationRelation

__all__ = [
    "ORGANIZATION_COMMUNICATION_POLICY_VERSION",
    "ORGANIZATION_FRAME_SUBJECT",
    "ORGANIZATION_PREDICATES",
    "OrganizationClaim",
    "OrganizationClaimError",
    "encode_organization_claim",
    "organization_claim_relation",
    "organization_communicate_utterance",
    "parse_organization_claim",
    "parse_organization_claim_relation",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.organization_communication"
)

ORGANIZATION_COMMUNICATION_POLICY_VERSION: Final[str] = "organization-communication.v1"
ORGANIZATION_FRAME_SUBJECT: Final[str] = "org_v1"
ORGANIZATION_PREDICATES: Final[tuple[str, ...]] = (
    "organization_claim",
    "organization_affirm",
    "organization_dispute",
    "organization_leave",
)
_LABEL_TOKEN_MAX_LEN: Final[int] = 32
_LABEL_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_DIGITS_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9]+$")
_MAX_FRAME_CHARS: Final[int] = 128
_MAX_RELATIONS: Final[int] = 32
_NONE_TOKEN: Final[str] = "none"

_CLAIM_ERROR_CODE: Final[str] = "organization_invalid_claim"


class OrganizationClaimError(OrganizationConceptError):
    """Malformed organization claim; the rejected text is never echoed."""

    __slots__ = ()

    def __init__(self) -> None:
        OrganizationConceptError.__init__(self, _CLAIM_ERROR_CODE)


def _fail() -> NoReturn:
    raise OrganizationClaimError()


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


def _require_expires(value: object) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 0:
        _fail()
    return value


@dataclass(frozen=True, slots=True)
class OrganizationClaim:
    """One closed self-authored organization claim."""

    predicate: str
    stance: OrganizationIdentityStance
    label_token: str | None = None
    expires_tick: int | None = None

    def __post_init__(self) -> None:
        if type(self.predicate) is not str or self.predicate not in (
            ORGANIZATION_PREDICATES
        ):
            _fail()
        if type(self.stance) is not OrganizationIdentityStance:
            _fail()
        object.__setattr__(self, "label_token", _require_label_token(self.label_token))
        object.__setattr__(self, "expires_tick", _require_expires(self.expires_tick))
        if (
            self.stance is OrganizationIdentityStance.OUTSIDE
            and self.expires_tick is not None
        ):
            _fail()


def encode_organization_claim(claim: OrganizationClaim) -> str:
    """Encode one claim into the bounded ``org_v1`` frame."""

    if type(claim) is not OrganizationClaim:
        raise TypeError("claim must be OrganizationClaim")
    label = _NONE_TOKEN if claim.label_token is None else claim.label_token
    expires = _NONE_TOKEN if claim.expires_tick is None else str(claim.expires_tick)
    return (
        f"{ORGANIZATION_FRAME_SUBJECT}:{claim.predicate}:{label}:"
        f"{claim.stance.value}:{expires}"
    )


def parse_organization_claim(text: str) -> OrganizationClaim:
    """Parse one strict ``org_v1`` frame; malformed text fails closed."""

    if type(text) is not str:
        _fail()
    if len(text) > _MAX_FRAME_CHARS:
        _fail()
    if any(character in text for character in "\n\r\t "):
        _fail()
    parts = text.split(":")
    if len(parts) != 5:
        _fail()
    subject, predicate, label, stance_token, expires_token = parts
    if subject != ORGANIZATION_FRAME_SUBJECT:
        _fail()
    if predicate not in ORGANIZATION_PREDICATES:
        _fail()
    try:
        stance = OrganizationIdentityStance(stance_token)
    except ValueError:
        _fail()
    label_token = None if label == _NONE_TOKEN else _require_label_token(label)
    if expires_token == _NONE_TOKEN:
        expires_tick = None
    elif _DIGITS_PATTERN.match(expires_token) is None:
        _fail()
    else:
        expires_tick = _require_expires(int(expires_token))
    return OrganizationClaim(
        predicate=predicate,
        stance=stance,
        label_token=label_token,
        expires_tick=expires_tick,
    )


def organization_claim_relation(claim: OrganizationClaim) -> CommunicationRelation:
    """Build one bounded relation atom for a claim."""

    if type(claim) is not OrganizationClaim:
        raise TypeError("claim must be OrganizationClaim")
    frame = encode_organization_claim(claim).split(":", 2)[2]
    return CommunicationRelation(
        subject=ORGANIZATION_FRAME_SUBJECT,
        predicate=claim.predicate,
        object=frame,
    )


def parse_organization_claim_relation(
    relation: object,
) -> OrganizationClaim | None:
    """Parse one organization relation; unrelated or malformed atoms are ``None``."""

    if type(relation) is not CommunicationRelation:
        raise TypeError("relation must be CommunicationRelation")
    if relation.subject != ORGANIZATION_FRAME_SUBJECT:
        return None
    if relation.predicate not in ORGANIZATION_PREDICATES:
        return None
    try:
        return parse_organization_claim(
            f"{ORGANIZATION_FRAME_SUBJECT}:{relation.predicate}:{relation.object}"
        )
    except OrganizationClaimError:
        return None


def _is_expressible(command: object) -> bool:
    from world.actions import Talk, Tell

    return type(command) in {Talk, Tell}


def _select_claim(ledger: OrganizationConceptLedger) -> OrganizationClaim | None:
    for concept in ledger.concepts:
        if concept.status in (OrganizationStatus.DISSOLVED, OrganizationStatus.RETIRED):
            continue
        for identity in concept.identities:
            if concept.status is OrganizationStatus.DISPUTED:
                return OrganizationClaim(
                    predicate="organization_dispute",
                    stance=identity.stance,
                    label_token=identity.label_token,
                )
            if identity.stance in (
                OrganizationIdentityStance.MEMBER,
                OrganizationIdentityStance.AFFILIATED,
            ):
                return OrganizationClaim(
                    predicate="organization_claim",
                    stance=identity.stance,
                    label_token=identity.label_token,
                )
            if identity.stance is OrganizationIdentityStance.OUTSIDE:
                return OrganizationClaim(
                    predicate="organization_leave",
                    stance=identity.stance,
                    label_token=identity.label_token,
                )
            return OrganizationClaim(
                predicate="organization_affirm",
                stance=identity.stance,
                label_token=identity.label_token,
            )
    return None


def organization_communicate_utterance(
    command: object, ledger: object | None
) -> object:
    """Attach at most one ``org_v1`` relation to an already-selected utterance.

    The command type, recipient, delivery, and every existing relation are
    preserved. A disabled, empty, or claim-free ledger returns the command
    unchanged.
    """

    if type(ledger) is not OrganizationConceptLedger:
        return command
    if not ledger.concepts:
        return command
    if not _is_expressible(command):
        return command
    claim = _select_claim(ledger)
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
        relation.subject == ORGANIZATION_FRAME_SUBJECT
        or relation.predicate in ORGANIZATION_PREDICATES
        for relation in relations
    ):
        return command
    if len(relations) >= _MAX_RELATIONS:
        return command
    updated_content = replace(
        content, relations=(*relations, organization_claim_relation(claim))
    )
    updated_utterance = replace(utterance, content=updated_content)
    _LOG.debug(
        "organization_claim predicate=%s stance=%s",
        claim.predicate,
        claim.stance.value,
    )
    typed = cast(Any, command)
    return typed.__class__(
        recipient_id=typed.recipient_id,
        utterance=updated_utterance,
    )
