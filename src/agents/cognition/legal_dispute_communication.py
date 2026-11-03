"""Bounded ``dsp_v1`` dispute speech carried inside existing speech.

Claims, counterclaims, testimony, evidence references, rule references,
mediation links, proposed resolutions, and per-party declarations travel as one
closed ``CommunicationRelation`` atom inside ordinary ``Talk``/``Tell``
speech. Delivery proves that speech happened; it never proves truth, a verdict,
a binding settlement, or that a named third party accepted anything.

No command, event, observer semantic type, free-text body, or new relation
subject other than ``dsp_v1`` is added.
"""

from __future__ import annotations

import base64
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final, NoReturn, cast

from agents.cognition.legal_disputes import (
    DisputeClaimPolarity,
    DisputeClaimRole,
    DisputeError,
    DisputeKind,
    DisputePolicy,
    DisputeResolutionTerm,
    DisputeResolutionTermKind,
    DisputeSubjectKind,
    default_dispute_policy,
    dispute_terms_digest,
)
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)

__all__ = [
    "DISPUTE_COMMUNICATION_POLICY_VERSION",
    "DISPUTE_FRAME_SUBJECT",
    "DISPUTE_PREDICATES",
    "DisputeAct",
    "DisputeFrame",
    "dispute_communicate_utterance",
    "dispute_frame_party_matches",
    "dispute_frame_relation",
    "encode_dispute_frame",
    "parse_dispute_frame",
    "parse_dispute_frame_relation",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.legal_dispute_communication"
)

DISPUTE_COMMUNICATION_POLICY_VERSION: Final[str] = "dispute-communication.v1"
DISPUTE_FRAME_SUBJECT: Final[str] = "dsp_v1"

_NONE_TOKEN: Final[str] = "none"
_REF_ENCODING_PREFIX: Final[str] = "r-"
_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@-]*$")
_HEX64_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_DIGITS_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9]+$")
_TOKEN_MAX_LEN: Final[int] = 128
_TERM_FIELD_COUNT: Final[int] = 8
_MAX_TERMS_CHARS: Final[int] = 256
_MAX_TERMS: Final[int] = 4
_FRAME_FIELD_COUNT: Final[int] = 17


class DisputeAct(StrEnum):
    """Closed dispute speech act."""

    CLAIM = "claim"
    COUNTERCLAIM = "counterclaim"
    TESTIFY = "testify"
    CITE_EVIDENCE = "cite_evidence"
    CITE_RULE = "cite_rule"
    REFERENCE_MEDIATION = "reference_mediation"
    PROPOSE_RESOLUTION = "propose_resolution"
    ACCEPT_RESOLUTION = "accept_resolution"
    REJECT_RESOLUTION = "reject_resolution"
    WITHDRAW_CLAIM = "withdraw_claim"


DISPUTE_PREDICATES: Final[Mapping[DisputeAct, str]] = MappingProxyType(
    {
        DisputeAct.CLAIM: "dsp_claim",
        DisputeAct.COUNTERCLAIM: "dsp_counterclaim",
        DisputeAct.TESTIFY: "dsp_testify",
        DisputeAct.CITE_EVIDENCE: "dsp_evidence",
        DisputeAct.CITE_RULE: "dsp_rule",
        DisputeAct.REFERENCE_MEDIATION: "dsp_mediation",
        DisputeAct.PROPOSE_RESOLUTION: "dsp_propose",
        DisputeAct.ACCEPT_RESOLUTION: "dsp_accept",
        DisputeAct.REJECT_RESOLUTION: "dsp_reject",
        DisputeAct.WITHDRAW_CLAIM: "dsp_withdraw",
    }
)
_PREDICATE_TO_ACT: Final[Mapping[str, DisputeAct]] = MappingProxyType(
    {predicate: act for act, predicate in DISPUTE_PREDICATES.items()}
)

_REQUIRED_FIELDS: Final[Mapping[DisputeAct, frozenset[str]]] = MappingProxyType(
    {
        DisputeAct.CLAIM: frozenset(
            {
                "case_ref",
                "role",
                "kind",
                "polarity",
                "party_ref",
                "subject_kind",
                "subject_token",
            }
        ),
        DisputeAct.COUNTERCLAIM: frozenset(
            {
                "case_ref",
                "claim_ref",
                "role",
                "kind",
                "polarity",
                "party_ref",
                "subject_kind",
                "subject_token",
            }
        ),
        DisputeAct.TESTIFY: frozenset(
            {"case_ref", "claim_ref", "party_ref", "direct", "root_ref"}
        ),
        DisputeAct.CITE_EVIDENCE: frozenset({"case_ref", "claim_ref", "evidence_ref"}),
        DisputeAct.CITE_RULE: frozenset({"case_ref", "claim_ref", "rule_ref"}),
        DisputeAct.REFERENCE_MEDIATION: frozenset({"case_ref", "mediation_ref"}),
        DisputeAct.PROPOSE_RESOLUTION: frozenset(
            {"case_ref", "resolution_ref", "terms_digest", "terms"}
        ),
        DisputeAct.ACCEPT_RESOLUTION: frozenset(
            {"case_ref", "resolution_ref", "party_ref", "terms_digest"}
        ),
        DisputeAct.REJECT_RESOLUTION: frozenset(
            {"case_ref", "resolution_ref", "party_ref", "terms_digest"}
        ),
        DisputeAct.WITHDRAW_CLAIM: frozenset({"case_ref", "claim_ref", "party_ref"}),
    }
)


def _policy() -> DisputePolicy:
    return default_dispute_policy()


def _fail() -> NoReturn:
    raise DisputeError("dispute_frame_invalid")


def _require_token(value: object) -> str:
    if type(value) is not str or not value or len(value) > _TOKEN_MAX_LEN:
        _fail()
    if value == _NONE_TOKEN or _TOKEN_PATTERN.match(value) is None:
        _fail()
    return value


def _optional_token(value: object) -> str | None:
    if value is None:
        return None
    return _require_token(value)


def _require_digest(value: object) -> str:
    if type(value) is not str or _HEX64_PATTERN.match(value) is None:
        _fail()
    return value


def _optional_digest(value: object) -> str | None:
    if value is None:
        return None
    return _require_digest(value)


def _encode_ref(reference: str) -> str:
    raw = bytes.fromhex(reference)
    body = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return f"{_REF_ENCODING_PREFIX}{body}"


def _decode_ref(token: str) -> str:
    if token.startswith(_REF_ENCODING_PREFIX):
        body = token[len(_REF_ENCODING_PREFIX) :]
        padding = "=" * (-len(body) % 4)
        try:
            raw = base64.urlsafe_b64decode(body + padding)
        except (ValueError, TypeError):
            _fail()
        reference = raw.hex()
        if len(reference) != 64:
            _fail()
        return reference
    return _require_digest(token)


def _optional_enum[EnumT: StrEnum](
    value: object, enum_type: type[EnumT]
) -> EnumT | None:
    if value is None:
        return None
    if type(value) is enum_type:
        return value
    if type(value) is str and value in {member.value for member in enum_type}:
        return enum_type(value)
    _fail()


def _optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    if type(value) is not bool:
        _fail()
    return value


def _rule_ref_parts(value: object) -> tuple[str, int]:
    if type(value) is not str or value.count("@") != 1:
        _fail()
    rule_id, version_text = value.split("@", 1)
    rule = _require_token(rule_id)
    if _DIGITS_PATTERN.match(version_text) is None:
        _fail()
    version = int(version_text)
    if version < 1:
        _fail()
    return rule, version


def _encode_terms(terms: Sequence[DisputeResolutionTerm]) -> str:
    if not terms:
        return _NONE_TOKEN
    parts: list[str] = []
    for term in terms:
        parts.append(
            ",".join(
                (
                    term.term_kind.value,
                    term.party_id,
                    term.counterparty_id,
                    term.item_token or _NONE_TOKEN,
                    str(term.quantity),
                    term.service_token or _NONE_TOKEN,
                    term.action_token or _NONE_TOKEN,
                    _NONE_TOKEN if term.due_tick is None else str(term.due_tick),
                )
            )
        )
    payload = "|".join(parts)
    if len(payload) > _MAX_TERMS_CHARS:
        _fail()
    return payload


def _decode_terms(payload: str) -> tuple[DisputeResolutionTerm, ...]:
    if payload == _NONE_TOKEN:
        return ()
    if len(payload) > _MAX_TERMS_CHARS:
        _fail()
    terms: list[DisputeResolutionTerm] = []
    for raw in payload.split("|"):
        fields = raw.split(",")
        if len(fields) != _TERM_FIELD_COUNT:
            _fail()
        (
            term_kind,
            party,
            counterparty,
            item,
            quantity,
            service,
            action,
            due,
        ) = fields
        try:
            kind = DisputeResolutionTermKind(term_kind)
        except ValueError:
            _fail()
        if _DIGITS_PATTERN.match(quantity) is None:
            _fail()
        due_tick = None if due == _NONE_TOKEN else int(due)
        terms.append(
            DisputeResolutionTerm(
                term_kind=kind,
                party_id=_require_token(party),
                counterparty_id=_require_token(counterparty),
                item_token=None if item == _NONE_TOKEN else _require_token(item),
                service_token=(
                    None if service == _NONE_TOKEN else _require_token(service)
                ),
                action_token=(
                    None if action == _NONE_TOKEN else _require_token(action)
                ),
                quantity=int(quantity),
                due_tick=due_tick,
            )
        )
    if len(terms) > _MAX_TERMS:
        _fail()
    return tuple(terms)


@dataclass(frozen=True, slots=True)
class DisputeFrame:
    """One closed self-authored dispute speech atom."""

    act: DisputeAct
    case_ref: str | None = None
    claim_ref: str | None = None
    role: DisputeClaimRole | None = None
    kind: DisputeKind | None = None
    polarity: DisputeClaimPolarity | None = None
    party_ref: str | None = None
    subject_kind: DisputeSubjectKind | None = None
    subject_token: str | None = None
    action_token: str | None = None
    evidence_ref: str | None = None
    rule_ref: str | None = None
    mediation_ref: str | None = None
    resolution_ref: str | None = None
    terms_digest: str | None = None
    terms: tuple[DisputeResolutionTerm, ...] = ()
    direct: bool | None = None
    root_ref: str | None = None

    def __post_init__(self) -> None:
        if type(self.act) is not DisputeAct:
            _fail()
        if self.case_ref is not None:
            object.__setattr__(self, "case_ref", _require_digest(self.case_ref))
        for name in ("claim_ref", "resolution_ref", "terms_digest"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _require_digest(value))
        if self.role is not None and type(self.role) is not DisputeClaimRole:
            _fail()
        object.__setattr__(self, "kind", _optional_enum(self.kind, DisputeKind))
        object.__setattr__(
            self,
            "polarity",
            _optional_enum(self.polarity, DisputeClaimPolarity),
        )
        object.__setattr__(
            self,
            "subject_kind",
            _optional_enum(self.subject_kind, DisputeSubjectKind),
        )
        for name in (
            "party_ref",
            "subject_token",
            "action_token",
            "evidence_ref",
            "mediation_ref",
            "root_ref",
        ):
            object.__setattr__(self, name, _optional_token(getattr(self, name)))
        if self.rule_ref is not None:
            object.__setattr__(self, "rule_ref", _require_token(self.rule_ref))
            _rule_ref_parts(self.rule_ref)
        if self.terms_digest is not None:
            object.__setattr__(self, "terms_digest", _require_digest(self.terms_digest))
        if isinstance(self.terms, (str, bytes)) or not isinstance(
            self.terms, (tuple, list)
        ):
            _fail()
        terms: list[DisputeResolutionTerm] = []
        for term in self.terms:
            if type(term) is not DisputeResolutionTerm:
                _fail()
            terms.append(term)
        if len(terms) > _MAX_TERMS:
            _fail()
        object.__setattr__(self, "terms", tuple(terms))
        object.__setattr__(self, "direct", _optional_bool(self.direct))

        for name in _REQUIRED_FIELDS[self.act]:
            if getattr(self, name) is None:
                if name != "terms":
                    _fail()
            elif name == "terms" and not terms:
                _fail()
        if self.act in (DisputeAct.CLAIM, DisputeAct.COUNTERCLAIM):
            if self.role is None or self.kind is None or self.polarity is None:
                _fail()
            if self.subject_kind is None or self.subject_token is None:
                _fail()
        else:
            for name in (
                "role",
                "kind",
                "polarity",
                "subject_kind",
                "subject_token",
                "action_token",
            ):
                if getattr(self, name) is not None:
                    _fail()
        if self.act is DisputeAct.CLAIM and self.role is not DisputeClaimRole.CLAIM:
            _fail()
        if (
            self.act is DisputeAct.COUNTERCLAIM
            and self.role is not DisputeClaimRole.COUNTERCLAIM
        ):
            _fail()
        if self.act is not DisputeAct.COUNTERCLAIM and self.claim_ref is not None:
            if self.act not in (
                DisputeAct.TESTIFY,
                DisputeAct.CITE_EVIDENCE,
                DisputeAct.CITE_RULE,
                DisputeAct.WITHDRAW_CLAIM,
            ):
                _fail()
        if (self.act is DisputeAct.CITE_EVIDENCE) != (self.evidence_ref is not None):
            _fail()
        if (self.act is DisputeAct.CITE_RULE) != (self.rule_ref is not None):
            _fail()
        if (self.act is DisputeAct.REFERENCE_MEDIATION) != (
            self.mediation_ref is not None
        ):
            _fail()
        if self.act in (
            DisputeAct.PROPOSE_RESOLUTION,
            DisputeAct.ACCEPT_RESOLUTION,
            DisputeAct.REJECT_RESOLUTION,
        ):
            if self.resolution_ref is None or self.terms_digest is None:
                _fail()
        else:
            if self.resolution_ref is not None or self.terms_digest is not None:
                _fail()
        if self.act is DisputeAct.PROPOSE_RESOLUTION:
            if not terms:
                _fail()
            if self.terms_digest != dispute_terms_digest(terms):
                _fail()
        elif terms:
            _fail()
        if self.act is DisputeAct.TESTIFY:
            if self.direct is None or self.root_ref is None:
                _fail()
        else:
            if self.direct is not None or self.root_ref is not None:
                _fail()


def encode_dispute_frame(frame: DisputeFrame) -> str:
    """Encode one frame into the bounded 17-field ``dsp_v1`` payload."""

    if type(frame) is not DisputeFrame:
        raise TypeError("frame must be DisputeFrame")
    fields = (
        _NONE_TOKEN if frame.case_ref is None else _encode_ref(frame.case_ref),
        _NONE_TOKEN if frame.claim_ref is None else _encode_ref(frame.claim_ref),
        _NONE_TOKEN if frame.role is None else frame.role.value,
        _NONE_TOKEN if frame.kind is None else frame.kind.value,
        _NONE_TOKEN if frame.polarity is None else frame.polarity.value,
        _NONE_TOKEN if frame.party_ref is None else frame.party_ref,
        (_NONE_TOKEN if frame.subject_kind is None else frame.subject_kind.value),
        _NONE_TOKEN if frame.subject_token is None else frame.subject_token,
        _NONE_TOKEN if frame.action_token is None else frame.action_token,
        _NONE_TOKEN if frame.evidence_ref is None else frame.evidence_ref,
        _NONE_TOKEN if frame.rule_ref is None else frame.rule_ref,
        _NONE_TOKEN if frame.mediation_ref is None else frame.mediation_ref,
        (
            _NONE_TOKEN
            if frame.resolution_ref is None
            else _encode_ref(frame.resolution_ref)
        ),
        (
            _NONE_TOKEN
            if frame.terms_digest is None
            else _encode_ref(frame.terms_digest)
        ),
        _encode_terms(frame.terms),
        (
            _NONE_TOKEN
            if frame.direct is None
            else ("true" if frame.direct else "false")
        ),
        _NONE_TOKEN if frame.root_ref is None else frame.root_ref,
    )
    text = f"{DISPUTE_FRAME_SUBJECT}:{DISPUTE_PREDICATES[frame.act]}:" + ":".join(
        fields
    )
    if len(text) > _policy().max_frame_chars:
        _fail()
    return text


def parse_dispute_frame(text: str) -> DisputeFrame | None:
    """Parse one strict ``dsp_v1`` frame; malformed text returns ``None``."""

    try:
        if type(text) is not str:
            return None
        if len(text) > _policy().max_frame_chars:
            return None
        if any(character.isspace() or ord(character) < 32 for character in text):
            return None
        parts = text.split(":")
        if len(parts) != _FRAME_FIELD_COUNT + 2:
            return None
        (
            subject,
            predicate,
            case_ref,
            claim_ref,
            role,
            kind,
            polarity,
            party_ref,
            subject_kind,
            subject_token,
            action_token,
            evidence_ref,
            rule_ref,
            mediation_ref,
            resolution_ref,
            terms_digest,
            terms,
            direct,
            root_ref,
        ) = parts
        if subject != DISPUTE_FRAME_SUBJECT:
            return None
        act = _PREDICATE_TO_ACT.get(predicate)
        if act is None:
            return None
        decoded_terms = _decode_terms(terms)
        if direct == _NONE_TOKEN:
            direct_value = None
        elif direct == "true":
            direct_value = True
        elif direct == "false":
            direct_value = False
        else:
            return None
        return DisputeFrame(
            act=act,
            case_ref=None if case_ref == _NONE_TOKEN else _decode_ref(case_ref),
            claim_ref=(None if claim_ref == _NONE_TOKEN else _decode_ref(claim_ref)),
            role=(
                None if role == _NONE_TOKEN else _optional_enum(role, DisputeClaimRole)
            ),
            kind=(None if kind == _NONE_TOKEN else _optional_enum(kind, DisputeKind)),
            polarity=(
                None
                if polarity == _NONE_TOKEN
                else _optional_enum(polarity, DisputeClaimPolarity)
            ),
            party_ref=(None if party_ref == _NONE_TOKEN else _require_token(party_ref)),
            subject_kind=(
                None
                if subject_kind == _NONE_TOKEN
                else _optional_enum(subject_kind, DisputeSubjectKind)
            ),
            subject_token=(
                None if subject_token == _NONE_TOKEN else _require_token(subject_token)
            ),
            action_token=(
                None if action_token == _NONE_TOKEN else _require_token(action_token)
            ),
            evidence_ref=(
                None if evidence_ref == _NONE_TOKEN else _require_token(evidence_ref)
            ),
            rule_ref=(None if rule_ref == _NONE_TOKEN else _require_token(rule_ref)),
            mediation_ref=(
                None if mediation_ref == _NONE_TOKEN else _require_token(mediation_ref)
            ),
            resolution_ref=(
                None if resolution_ref == _NONE_TOKEN else _decode_ref(resolution_ref)
            ),
            terms_digest=(
                None if terms_digest == _NONE_TOKEN else _decode_ref(terms_digest)
            ),
            terms=decoded_terms,
            direct=direct_value,
            root_ref=(None if root_ref == _NONE_TOKEN else _require_token(root_ref)),
        )
    except (DisputeError, TypeError, ValueError):
        return None


def dispute_frame_relation(frame: DisputeFrame) -> CommunicationRelation:
    """Build the ``(subject, predicate, object)`` atom for one frame."""

    if type(frame) is not DisputeFrame:
        raise TypeError("frame must be DisputeFrame")
    text = encode_dispute_frame(frame)
    _, predicate, body = text.split(":", 2)
    return CommunicationRelation(
        subject=DISPUTE_FRAME_SUBJECT, predicate=predicate, object=body
    )


def parse_dispute_frame_relation(relation: object) -> DisputeFrame | None:
    """Parse one relation atom; unrelated atoms return ``None``."""

    subject = getattr(relation, "subject", None)
    predicate = getattr(relation, "predicate", None)
    body = getattr(relation, "object", None)
    if subject != DISPUTE_FRAME_SUBJECT:
        return None
    if type(predicate) is not str or predicate not in _PREDICATE_TO_ACT:
        return None
    if type(body) is not str:
        return None
    return parse_dispute_frame(f"{subject}:{predicate}:{body}")


def dispute_frame_party_matches(frame: DisputeFrame, verified_speaker: object) -> bool:
    """Return whether the frame's acting party is the verified speaker."""

    if type(frame) is not DisputeFrame:
        return False
    if type(verified_speaker) is not str or not verified_speaker:
        return False
    return frame.party_ref is not None and frame.party_ref == verified_speaker


def _is_expressible(command: object) -> bool:
    from world.actions import Talk, Tell

    return type(command) in {Talk, Tell}


def _relations(command: object) -> tuple[CommunicationRelation, ...]:
    utterance = getattr(command, "utterance", None)
    content = getattr(utterance, "content", None)
    return tuple(getattr(content, "relations", ()) or ())


def dispute_communicate_utterance(command: object, frame: DisputeFrame) -> object:
    """Attach at most one ``dsp_v1`` relation to an already-selected utterance.

    The command type, recipient, delivery, and every existing relation are
    preserved. No command is created, replaced, or re-targeted.
    """

    if type(frame) is not DisputeFrame:
        raise TypeError("frame must be DisputeFrame")
    if not _is_expressible(command):
        raise DisputeError("dispute_frame_unsupported_command")
    utterance = getattr(command, "utterance", None)
    if utterance is None:
        return command
    content = getattr(utterance, "content", None)
    if content is None:
        return command
    relations = _relations(command)
    if any(
        relation.subject == DISPUTE_FRAME_SUBJECT
        or relation.predicate in _PREDICATE_TO_ACT
        for relation in relations
    ):
        return command
    if len(relations) >= _policy().max_relations:
        _LOG.warning("dispute_frame_skipped reason=relation_limit")
        return command
    try:
        relation = dispute_frame_relation(frame)
    except (DisputeError, TypeError, ValueError):
        _LOG.warning("dispute_frame_skipped reason=invalid_frame")
        return command
    declared = getattr(utterance, "declared", None)
    speaker = getattr(declared, "immediate_source_id", None)
    if speaker is None:
        return command
    updated = origin_utterance(
        text="dispute",
        speaker_id=speaker,
        communication_id=(
            f"dispute-{frame.act.value}-{frame.case_ref[:8]}"
            if frame.case_ref is not None
            else f"dispute-{frame.act.value}"
        ),
        relations=(*relations, relation),
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    _LOG.debug("dispute_frame_encoded act=%s", frame.act.value)
    typed = cast(Any, command)
    return typed.__class__(
        recipient_id=typed.recipient_id,
        utterance=updated,
    )
