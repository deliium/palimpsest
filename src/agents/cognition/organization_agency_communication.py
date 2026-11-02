"""Bounded collective-agency claims carried inside existing speech.

A proposal, a position, an amendment, a recognition claim, a refusal, and an
implementation report must be socially expressible without granting authority.
An owner therefore states them through ordinary ``Talk``/``Tell``. The claim
travels as one closed ``org_ca_v1`` relation atom; delivery proves that speech
happened and never proves that an organization decided, commanded, or acted.

No command, event, observer semantic type, or free-text payload is added, and
the V4-03 ``org_v1`` and V4-04 ``org_op_v1`` frames are unchanged.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final, NoReturn, cast

from agents.cognition.organization_agency import (
    ORGANIZATION_AGENCY_DOMAIN_EFFECTS,
    ORGANIZATION_AGENCY_EFFECTS,
    OrganizationAgencyEffect,
    OrganizationAgencyError,
    OrganizationAgencyLedger,
    OrganizationAgencyPositionStance,
    OrganizationAgencyProposalStatus,
    OrganizationAgencyReportKind,
    require_organization_agency_ref,
)
from agents.cognition.organization_operations import OrganizationOperationDomain
from world.communications import CommunicationRelation

__all__ = [
    "ORGANIZATION_AGENCY_COMMUNICATION_POLICY_VERSION",
    "ORGANIZATION_AGENCY_FRAME_SUBJECT",
    "ORGANIZATION_AGENCY_PREDICATES",
    "OrganizationAgencyAct",
    "OrganizationAgencyClaim",
    "encode_organization_agency_claim",
    "organization_agency_claim_relation",
    "organization_agency_communicate_utterance",
    "parse_organization_agency_claim",
    "parse_organization_agency_claim_relation",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.organization_agency_communication"
)

ORGANIZATION_AGENCY_COMMUNICATION_POLICY_VERSION: Final[str] = (
    "organization-agency-communication.v1"
)
ORGANIZATION_AGENCY_FRAME_SUBJECT: Final[str] = "org_ca_v1"


class OrganizationAgencyAct(StrEnum):
    """Closed collective-agency speech act."""

    PROPOSE = "propose"
    SUPPORT = "support"
    OPPOSE = "oppose"
    ABSTAIN = "abstain"
    AMEND = "amend"
    WITHDRAW = "withdraw"
    RECOGNIZE = "recognize"
    REFUSE = "refuse"
    REPORT = "report"


ORGANIZATION_AGENCY_PREDICATES: Final[Mapping[OrganizationAgencyAct, str]] = (
    MappingProxyType(
        {
            OrganizationAgencyAct.PROPOSE: "org_ca_propose",
            OrganizationAgencyAct.SUPPORT: "org_ca_support",
            OrganizationAgencyAct.OPPOSE: "org_ca_oppose",
            OrganizationAgencyAct.ABSTAIN: "org_ca_abstain",
            OrganizationAgencyAct.AMEND: "org_ca_amend",
            OrganizationAgencyAct.WITHDRAW: "org_ca_withdraw",
            OrganizationAgencyAct.RECOGNIZE: "org_ca_recognize",
            OrganizationAgencyAct.REFUSE: "org_ca_refuse",
            OrganizationAgencyAct.REPORT: "org_ca_report",
        }
    )
)
_PREDICATE_TO_ACT: Final[Mapping[str, OrganizationAgencyAct]] = MappingProxyType(
    {predicate: act for act, predicate in ORGANIZATION_AGENCY_PREDICATES.items()}
)
_ACT_TO_PREDICATE: Final[Mapping[OrganizationAgencyAct, str]] = MappingProxyType(
    {act: predicate for act, predicate in ORGANIZATION_AGENCY_PREDICATES.items()}
)

_MAX_FRAME_CHARS: Final[int] = 384
_MAX_RELATIONS: Final[int] = 32
_NONE_TOKEN: Final[str] = "none"
_DIGITS_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9]+$")

_DOMAIN_TOKENS: Final[frozenset[str]] = frozenset(
    member.value for member in OrganizationOperationDomain
)
_EFFECT_TOKENS: Final[frozenset[str]] = ORGANIZATION_AGENCY_EFFECTS
_REPORT_TOKENS: Final[frozenset[str]] = frozenset(
    member.value for member in OrganizationAgencyReportKind
)
_STANCE_TOKENS: Final[frozenset[str]] = frozenset(
    member.value for member in OrganizationAgencyPositionStance
)

_STANCE_BY_ACT: Final[Mapping[OrganizationAgencyAct, frozenset[str]]] = (
    MappingProxyType(
        {
            OrganizationAgencyAct.PROPOSE: frozenset({_NONE_TOKEN}),
            OrganizationAgencyAct.SUPPORT: frozenset({"support"}),
            OrganizationAgencyAct.OPPOSE: frozenset({"oppose"}),
            OrganizationAgencyAct.ABSTAIN: frozenset({"abstain"}),
            OrganizationAgencyAct.AMEND: frozenset({_NONE_TOKEN}),
            OrganizationAgencyAct.WITHDRAW: frozenset({"withdraw"}),
            OrganizationAgencyAct.RECOGNIZE: frozenset(
                {"recognized", "unrecognized"}
            ),
            OrganizationAgencyAct.REFUSE: frozenset({"refuse"}),
            OrganizationAgencyAct.REPORT: frozenset({_NONE_TOKEN}),
        }
    )
)


def _fail() -> NoReturn:
    raise OrganizationAgencyError("organization_agency_invalid")


def _require_optional_ref(value: object) -> str | None:
    if value is None:
        return None
    return require_organization_agency_ref(value)


def _require_optional_domain(value: object) -> OrganizationOperationDomain | None:
    if value is None:
        return None
    if type(value) is OrganizationOperationDomain:
        return value
    if type(value) is str and value in _DOMAIN_TOKENS:
        return OrganizationOperationDomain(value)
    _fail()


def _require_optional_effect(value: object) -> OrganizationAgencyEffect | None:
    if value is None:
        return None
    if type(value) is OrganizationAgencyEffect:
        return value
    if type(value) is str and value in _EFFECT_TOKENS:
        return OrganizationAgencyEffect(value)
    _fail()


def _require_optional_report(value: object) -> OrganizationAgencyReportKind | None:
    if value is None:
        return None
    if type(value) is OrganizationAgencyReportKind:
        return value
    if type(value) is str and value in _REPORT_TOKENS:
        return OrganizationAgencyReportKind(value)
    _fail()


def _require_optional_revision(value: object) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 1 or value > 9999:
        _fail()
    return value


def _require_domain_effect(
    domain: OrganizationOperationDomain | None,
    effect: OrganizationAgencyEffect | None,
) -> None:
    if domain is None or effect is None:
        return
    if effect.value not in ORGANIZATION_AGENCY_DOMAIN_EFFECTS[domain]:
        _fail()


@dataclass(frozen=True, slots=True)
class OrganizationAgencyClaim:
    """One closed self-authored collective-agency claim."""

    act: OrganizationAgencyAct
    proposal_ref: str | None = None
    procedure_ref: str | None = None
    domain: OrganizationOperationDomain | None = None
    effect: OrganizationAgencyEffect | None = None
    target_ref: str | None = None
    revision: int | None = None
    terms_ref: str | None = None
    stance: str = _NONE_TOKEN
    report_kind: OrganizationAgencyReportKind | None = None

    def __post_init__(self) -> None:
        if type(self.act) is not OrganizationAgencyAct:
            _fail()
        object.__setattr__(
            self, "proposal_ref", _require_optional_ref(self.proposal_ref)
        )
        object.__setattr__(
            self, "procedure_ref", _require_optional_ref(self.procedure_ref)
        )
        domain = _require_optional_domain(self.domain)
        effect = _require_optional_effect(self.effect)
        _require_domain_effect(domain, effect)
        object.__setattr__(self, "domain", domain)
        object.__setattr__(self, "effect", effect)
        object.__setattr__(self, "target_ref", _require_optional_ref(self.target_ref))
        object.__setattr__(
            self, "revision", _require_optional_revision(self.revision)
        )
        object.__setattr__(self, "terms_ref", _require_optional_ref(self.terms_ref))
        if type(self.stance) is not str or self.stance not in _STANCE_BY_ACT[self.act]:
            _fail()
        object.__setattr__(
            self, "report_kind", _require_optional_report(self.report_kind)
        )
        self._require_act_fields()

    def _require_act_fields(self) -> None:
        act = self.act
        if act is OrganizationAgencyAct.PROPOSE:
            if (
                self.proposal_ref is None
                or self.domain is None
                or self.effect is None
                or self.revision is None
                or self.terms_ref is None
            ):
                _fail()
        elif act in (
            OrganizationAgencyAct.SUPPORT,
            OrganizationAgencyAct.OPPOSE,
            OrganizationAgencyAct.ABSTAIN,
            OrganizationAgencyAct.WITHDRAW,
            OrganizationAgencyAct.REFUSE,
        ):
            if self.proposal_ref is None or self.revision is None:
                _fail()
        elif act is OrganizationAgencyAct.AMEND:
            if (
                self.proposal_ref is None
                or self.revision is None
                or self.revision < 2
                or self.terms_ref is None
                or self.domain is None
                or self.effect is None
            ):
                _fail()
        elif act is OrganizationAgencyAct.RECOGNIZE:
            if (
                self.proposal_ref is None
                or self.revision is None
                or self.procedure_ref is None
            ):
                _fail()
        elif act is OrganizationAgencyAct.REPORT:
            if (
                self.proposal_ref is None
                or self.revision is None
                or self.report_kind is None
            ):
                _fail()
        if act is not OrganizationAgencyAct.REPORT and self.report_kind is not None:
            _fail()


def encode_organization_agency_claim(claim: OrganizationAgencyClaim) -> str:
    """Encode one claim into the bounded ``org_ca_v1`` frame."""

    if type(claim) is not OrganizationAgencyClaim:
        raise TypeError("claim must be OrganizationAgencyClaim")
    predicate = _ACT_TO_PREDICATE[claim.act]
    fields = (
        _NONE_TOKEN if claim.proposal_ref is None else claim.proposal_ref,
        _NONE_TOKEN if claim.procedure_ref is None else claim.procedure_ref,
        _NONE_TOKEN if claim.domain is None else claim.domain.value,
        _NONE_TOKEN if claim.effect is None else claim.effect.value,
        _NONE_TOKEN if claim.target_ref is None else claim.target_ref,
        _NONE_TOKEN if claim.revision is None else str(claim.revision),
        _NONE_TOKEN if claim.terms_ref is None else claim.terms_ref,
        claim.stance,
        _NONE_TOKEN if claim.report_kind is None else claim.report_kind.value,
    )
    return f"{ORGANIZATION_AGENCY_FRAME_SUBJECT}:{predicate}:" + ":".join(fields)


def parse_organization_agency_claim(text: str) -> OrganizationAgencyClaim:
    """Parse one strict ``org_ca_v1`` frame; malformed text fails closed."""

    if type(text) is not str:
        _fail()
    if len(text) > _MAX_FRAME_CHARS:
        _fail()
    if any(character.isspace() or ord(character) < 32 for character in text):
        _fail()
    parts = text.split(":")
    if len(parts) != 11:
        _fail()
    (
        subject,
        predicate,
        proposal_ref,
        procedure_ref,
        domain,
        effect,
        target_ref,
        revision,
        terms_ref,
        stance,
        report_kind,
    ) = parts
    if subject != ORGANIZATION_AGENCY_FRAME_SUBJECT:
        _fail()
    act = _PREDICATE_TO_ACT.get(predicate)
    if act is None:
        _fail()
    if stance not in _STANCE_BY_ACT[act]:
        _fail()
    if revision == _NONE_TOKEN:
        revision_value = None
    elif _DIGITS_PATTERN.match(revision) is None:
        _fail()
    else:
        revision_value = _require_optional_revision(int(revision))
    return OrganizationAgencyClaim(
        act=act,
        proposal_ref=(
            None
            if proposal_ref == _NONE_TOKEN
            else require_organization_agency_ref(proposal_ref)
        ),
        procedure_ref=(
            None
            if procedure_ref == _NONE_TOKEN
            else require_organization_agency_ref(procedure_ref)
        ),
        domain=(
            None
            if domain == _NONE_TOKEN
            else _require_optional_domain(domain)
        ),
        effect=(
            (
                OrganizationAgencyEffect.NONE
                if act
                in (OrganizationAgencyAct.PROPOSE, OrganizationAgencyAct.AMEND)
                else None
            )
            if effect == _NONE_TOKEN
            else _require_optional_effect(effect)
        ),
        target_ref=(
            None
            if target_ref == _NONE_TOKEN
            else require_organization_agency_ref(target_ref)
        ),
        revision=revision_value,
        terms_ref=(
            None
            if terms_ref == _NONE_TOKEN
            else require_organization_agency_ref(terms_ref)
        ),
        stance=stance,
        report_kind=(
            None
            if report_kind == _NONE_TOKEN
            else _require_optional_report(report_kind)
        ),
    )


def organization_agency_claim_relation(
    claim: OrganizationAgencyClaim,
) -> CommunicationRelation:
    """Build one bounded relation atom for a collective-agency claim."""

    if type(claim) is not OrganizationAgencyClaim:
        raise TypeError("claim must be OrganizationAgencyClaim")
    frame = encode_organization_agency_claim(claim).split(":", 2)[2]
    return CommunicationRelation(
        subject=ORGANIZATION_AGENCY_FRAME_SUBJECT,
        predicate=_ACT_TO_PREDICATE[claim.act],
        object=frame,
    )


def parse_organization_agency_claim_relation(
    relation: object,
) -> OrganizationAgencyClaim | None:
    """Parse one agency relation; unrelated or malformed atoms are ``None``."""

    if type(relation) is not CommunicationRelation:
        raise TypeError("relation must be CommunicationRelation")
    if relation.subject != ORGANIZATION_AGENCY_FRAME_SUBJECT:
        return None
    if relation.predicate not in _PREDICATE_TO_ACT:
        return None
    try:
        return parse_organization_agency_claim(
            f"{ORGANIZATION_AGENCY_FRAME_SUBJECT}:"
            f"{relation.predicate}:{relation.object}"
        )
    except OrganizationAgencyError:
        _LOG.warning("organization_agency_claim_parse_failed reason=invalid_frame")
        return None


def _is_expressible(command: object) -> bool:
    from world.actions import Talk, Tell

    return type(command) in {Talk, Tell}


def _select_claim(ledger: OrganizationAgencyLedger) -> OrganizationAgencyClaim | None:
    """Select one deterministic claim from an owner ledger, or ``None``."""

    active = [
        proposal
        for concept in ledger.concepts
        for proposal in concept.proposals
        if proposal.status
        in (
            OrganizationAgencyProposalStatus.ACTIVE,
            OrganizationAgencyProposalStatus.AMENDED,
        )
    ]
    if active:
        proposal = min(active, key=lambda item: (item.opened_tick, item.proposal_id))
        return OrganizationAgencyClaim(
            act=OrganizationAgencyAct.PROPOSE,
            proposal_ref=proposal.proposal_ref,
            procedure_ref=proposal.procedure_ref,
            domain=proposal.domain,
            effect=proposal.effect,
            target_ref=proposal.target_ref,
            revision=proposal.revision,
            terms_ref=proposal.terms_ref,
        )
    positions = [
        position
        for concept in ledger.concepts
        for position in concept.positions
        if position.stance
        in (
            OrganizationAgencyPositionStance.SUPPORT,
            OrganizationAgencyPositionStance.OPPOSE,
            OrganizationAgencyPositionStance.ABSTAIN,
            OrganizationAgencyPositionStance.WITHDRAW,
        )
    ]
    if not positions:
        return None
    latest = max(
        positions,
        key=lambda item: (
            item.tick,
            item.proposal_id,
            item.revision,
            item.actor_id.value,
        ),
    )
    proposal = next(
        proposal
        for concept in ledger.concepts
        for proposal in concept.proposals
        if proposal.proposal_id == latest.proposal_id
    )
    act = OrganizationAgencyAct(latest.stance.value)
    return OrganizationAgencyClaim(
        act=act,
        proposal_ref=proposal.proposal_ref,
        revision=latest.revision,
    )


def organization_agency_communicate_utterance(
    command: object, claims: object | None
) -> object:
    """Attach at most one ``org_ca_v1`` relation to an already-selected utterance.

    ``claims`` may be an owner ``OrganizationAgencyLedger`` or one
    ``OrganizationAgencyClaim``. The command type, recipient, delivery, and every
    existing relation are preserved.
    """

    if type(claims) is OrganizationAgencyLedger:
        if not claims.concepts:
            return command
        claim = _select_claim(claims)
    elif type(claims) is OrganizationAgencyClaim:
        claim = claims
    else:
        return command
    if claim is None:
        return command
    if not _is_expressible(command):
        return command
    utterance = getattr(command, "utterance", None)
    if utterance is None:
        return command
    content = getattr(utterance, "content", None)
    if content is None:
        return command
    relations = tuple(getattr(content, "relations", ()))
    if any(
        relation.subject == ORGANIZATION_AGENCY_FRAME_SUBJECT
        or relation.predicate in _PREDICATE_TO_ACT
        for relation in relations
    ):
        return command
    if len(relations) >= _MAX_RELATIONS:
        _LOG.warning("organization_agency_claim_skipped reason=relation_cap")
        return command
    updated_content = replace(
        content, relations=(*relations, organization_agency_claim_relation(claim))
    )
    updated_utterance = replace(utterance, content=updated_content)
    _LOG.debug(
        "organization_agency_communicated act=%s stance=%s",
        claim.act.value,
        claim.stance,
    )
    typed = cast(Any, command)
    return typed.__class__(
        recipient_id=typed.recipient_id,
        utterance=updated_utterance,
    )
