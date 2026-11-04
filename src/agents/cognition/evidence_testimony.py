"""Closed owner-scoped evidence and testimony vocabulary and identity grammar.

Evidence is one owner's belief about a source, its provenance, an optional
chain of custody, the owner's confidence, the owner's interpretation, and the
contradictions that owner retains. It is never truth, proof, authenticity, an
objective evidence registry, a verifier, an authenticator, a witness authority,
or a binding finding. Witnesses may misremember, records may be wrong, and
artifacts may be misinterpreted; the ledger keeps the owner's version.

This module defines only frozen vocabulary, identity minters, bounded policy
values, and stable error codes. Later evidence code consumes these definitions
so no implementer invents source kinds, id prefixes, or limits while writing
the ledger.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from itertools import pairwise
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final, NoReturn, cast

from agents.models import AgentId

if TYPE_CHECKING:
    from agents.cognition.evidence_testimony_communication import EvidenceFrame

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.evidence_testimony")

EVIDENCE_TESTIMONY_POLICY_VERSION: Final[str] = "evidence-testimony.v1"
EVIDENCE_TESTIMONY_CONTEXT_ID: Final[str] = "legal_disputes"
EVIDENCE_TESTIMONY_REQUIRED_RUNNER_SCHEMA: Final[str] = "runner-config-v56"
EVIDENCE_TESTIMONY_IS_CAPABILITY_FLAG: Final[bool] = False

EVIDENCE_ID_HEX_LEN: Final[int] = 16
EVIDENCE_SEPARATOR: Final[str] = "\x1f"

EVIDENCE_SOURCE_ID_PREFIX: Final[str] = "evs-"
EVIDENCE_TESTIMONY_ID_PREFIX: Final[str] = "evw-"
EVIDENCE_ITEM_ID_PREFIX: Final[str] = "evi-"
EVIDENCE_CUSTODY_ID_PREFIX: Final[str] = "evc-"
EVIDENCE_CONTRADICTION_ID_PREFIX: Final[str] = "evx-"
EVIDENCE_EVALUATION_ID_PREFIX: Final[str] = "eva-"

EVIDENCE_SOURCE_NAMESPACE: Final[str] = "evidence-source"
EVIDENCE_TESTIMONY_NAMESPACE: Final[str] = "evidence-testimony"
EVIDENCE_ITEM_NAMESPACE: Final[str] = "evidence-item"
EVIDENCE_CUSTODY_NAMESPACE: Final[str] = "evidence-custody"
EVIDENCE_CONTRADICTION_NAMESPACE: Final[str] = "evidence-contradiction"
EVIDENCE_EVALUATION_NAMESPACE: Final[str] = "evidence-evaluation"

_EVIDENCE_REFERENCE_MAX_LEN: Final[int] = 128
_HEX64_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")


class EvidenceSourceKind(StrEnum):
    """Closed source kind one owner believes evidence comes from."""

    WITNESS_TESTIMONY = "witness_testimony"
    WRITTEN_RECORD = "written_record"
    ARTIFACT = "artifact"
    PHYSICAL_STATE = "physical_state"
    PRIOR_AGREEMENT = "prior_agreement"
    REPUTATION = "reputation"
    REMEMBERED_EVENT = "remembered_event"
    UNKNOWN = "unknown"


class EvidenceProvenanceChannel(StrEnum):
    """Closed owner-visible channel through which a source reached the owner."""

    DIRECT_OBSERVATION = "direct_observation"
    COMMUNICATED = "communicated"
    REMEMBERED = "remembered"
    RECORDED = "recorded"
    DERIVED = "derived"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class EvidenceReferenceKind(StrEnum):
    """Closed owner-visible anchor kind. No world body or event store is carried."""

    OBSERVED_OCCURRENCE = "observed_occurrence"
    OBSERVED_COMMUNICATION = "observed_communication"
    MEMORY_TRACE = "memory_trace"
    RECONSTRUCTED_MEMORY = "reconstructed_memory"
    ARTIFACT = "artifact"
    DURABLE_RECORD = "durable_record"
    REPOSITORY_ENTRY = "repository_entry"
    COMMITMENT = "commitment"
    REPUTATION_RECORD = "reputation_record"
    RELATIONSHIP_RECORD = "relationship_record"
    OFFICE_RECORD = "office_record"
    INSTITUTION_RECORD = "institution_record"
    ORGANIZATION_RECORD = "organization_record"
    RULE_RECORD = "rule_record"
    MEDIATION_RECORD = "mediation_record"
    DISPUTE_RECORD = "dispute_record"
    UNKNOWN = "unknown"


class EvidenceTestimonyChannel(StrEnum):
    """Closed testimony channel. Communicated retellings share a root."""

    DIRECT = "direct"
    COMMUNICATED = "communicated"


class EvidenceIntegrityBelief(StrEnum):
    """Closed owner belief about a source's integrity. Never an objective state."""

    INTACT = "intact"
    DAMAGED = "damaged"
    PARTIALLY_LOST = "partially_lost"
    DESTROYED_BELIEF = "destroyed_belief"
    UNCERTAIN = "uncertain"


class EvidenceInterpretationKind(StrEnum):
    """Closed owner interpretation of one source. Never objective meaning."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    AMBIGUOUS = "ambiguous"
    INSUFFICIENT = "insufficient"
    IRRELEVANT = "irrelevant"
    UNKNOWN = "unknown"


class EvidenceItemStatus(StrEnum):
    """Closed owner-local lifecycle status for one interpreted item."""

    ACTIVE = "active"
    RETRACTED = "retracted"
    SUPERSEDED = "superseded"


class EvidenceCustodyRole(StrEnum):
    """Closed role one owner believes a participant played in custody."""

    HOLDER = "holder"
    REPOSITORY_CUSTODIAN = "repository_custodian"
    LOCATION = "location"
    OBSERVER = "observer"


class EvidenceCustodyStatus(StrEnum):
    """Closed owner belief about custody continuity. Never an objective audit."""

    NOT_APPLICABLE = "not_applicable"
    COMPLETE_BELIEF = "complete_belief"
    INCOMPLETE_BELIEF = "incomplete_belief"
    CONFLICTING_BELIEF = "conflicting_belief"
    UNKNOWN = "unknown"


class EvidenceContradictionKind(StrEnum):
    """Closed kind of owner-perceived disagreement between two references."""

    TESTIMONY_CONFLICT = "testimony_conflict"
    MEMORY_CONFLICT = "memory_conflict"
    RECORD_CONFLICT = "record_conflict"
    ARTIFACT_CONFLICT = "artifact_conflict"
    CUSTODY_CONFLICT = "custody_conflict"
    TEMPORAL_CONFLICT = "temporal_conflict"
    INTERPRETATION_CONFLICT = "interpretation_conflict"
    PROVENANCE_CONFLICT = "provenance_conflict"


class EvidenceContradictionStatus(StrEnum):
    """Closed owner preference among two retained, disagreeing references."""

    UNRESOLVED = "unresolved"
    OWNER_PREFERS_FIRST = "owner_prefers_first"
    OWNER_PREFERS_SECOND = "owner_prefers_second"
    WITHDRAWN = "withdrawn"


class EvidenceTrustBasis(StrEnum):
    """Closed owner-relative basis used to evaluate evidence."""

    DIRECT_EXPERIENCE = "direct_experience"
    RELATIONSHIP_TRUST = "relationship_trust"
    REPUTATION = "reputation"
    ROLE_AUTHORITY = "role_authority"
    RULE_AUTHORITY = "rule_authority"
    INSTITUTION_MEMBERSHIP = "institution_membership"
    NONE = "none"
    UNKNOWN = "unknown"


class EvidenceEvaluationKind(StrEnum):
    """Closed owner evaluation of one interpreted item. Never a truth verdict."""

    CORROBORATED = "corroborated"
    CONTESTED = "contested"
    UNCORROBORATED = "uncorroborated"
    EXCLUDED_BY_OWNER = "excluded_by_owner"
    UNKNOWN = "unknown"


class EvidenceReportKind(StrEnum):
    """Closed detached-analysis report kind. Analysis never feeds cognition."""

    SUMMARY = "summary"
    CANDIDATE = "candidate"
    ITEM = "item"
    CONTRADICTION = "contradiction"
    CUSTODY = "custody"
    LINEAGE = "lineage"


EVIDENCE_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "evidence_invalid_input",
        "evidence_invalid_id",
        "evidence_invalid_record",
        "evidence_owner_mismatch",
        "evidence_tick_mismatch",
        "evidence_unknown_reference",
        "evidence_duplicate_id",
        "evidence_limit_exceeded",
        "evidence_policy_not_locked",
        "evidence_forbidden_field",
        "evidence_untrusted_frame",
        "evidence_invalid_confidence",
        "evidence_chain_conflict",
    }
)

EVIDENCE_FORBIDDEN_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "truth",
        "verified",
        "authenticated",
        "authentic",
        "forged",
        "fake",
        "proof",
        "certainty",
        "verdict",
        "guilt",
        "guilty",
        "liable",
        "liability",
        "true_owner",
        "winner",
    }
)

EVIDENCE_NOTICE_REASONS: Final[frozenset[str]] = frozenset(
    {
        "evidence_truncated",
        "evidence_chain_incomplete",
        "evidence_reference_unknown",
        "evidence_contradiction_retained",
        "evidence_trust_basis_missing",
        "evidence_testimony_root_shared",
        "evidence_item_retracted",
    }
)


class EvidenceError(ValueError):
    """Stable-code evidence contract violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        if code not in EVIDENCE_ERROR_CODES:
            raise ValueError("evidence_invalid_error_code")
        self.code: str = code
        super().__init__(code)


def _fail(code: str) -> NoReturn:
    raise EvidenceError(code)


@dataclass(frozen=True, slots=True)
class EvidencePolicy:
    """Locked owner-local evidence cognition bounds.

    Every value is part of the accepted contract. Any deviation is a programming
    error and fails closed with ``evidence_policy_not_locked``.
    """

    version: str = EVIDENCE_TESTIMONY_POLICY_VERSION
    max_sources: int = 64
    max_testimony: int = 64
    max_items: int = 128
    max_custody_links_per_source: int = 16
    max_contradictions: int = 64
    max_evaluations: int = 128
    max_total_records: int = 640
    max_notices: int = 16
    max_frame_chars: int = 768
    max_frame_relations: int = 32
    max_subject_token: int = 128
    trust_weight_direct_experience: int = 5000
    trust_weight_relationship: int = 2500
    trust_weight_reputation: int = 2000
    trust_weight_role_authority: int = 500
    neutral_confidence: float = 0.5
    confidence_quantum: float = 0.000001

    def __post_init__(self) -> None:
        for name, expected in _LOCKED_POLICY_VALUES.items():
            actual = getattr(self, name)
            if type(actual) is not type(expected) or actual != expected:
                _fail("evidence_policy_not_locked")


_LOCKED_POLICY_VALUES: Final[Mapping[str, str | int | float]] = MappingProxyType(
    {
        "version": EVIDENCE_TESTIMONY_POLICY_VERSION,
        "max_sources": 64,
        "max_testimony": 64,
        "max_items": 128,
        "max_custody_links_per_source": 16,
        "max_contradictions": 64,
        "max_evaluations": 128,
        "max_total_records": 640,
        "max_notices": 16,
        "max_frame_chars": 768,
        "max_frame_relations": 32,
        "max_subject_token": 128,
        "trust_weight_direct_experience": 5000,
        "trust_weight_relationship": 2500,
        "trust_weight_reputation": 2000,
        "trust_weight_role_authority": 500,
        "neutral_confidence": 0.5,
        "confidence_quantum": 0.000001,
    }
)

_DEFAULT_POLICY: Final[EvidencePolicy] = EvidencePolicy()
_LOG.debug(
    "evidence_contract_initialized policy_version=%s",
    EVIDENCE_TESTIMONY_POLICY_VERSION,
)


def default_evidence_policy() -> EvidencePolicy:
    """Return the single locked evidence policy instance."""

    return _DEFAULT_POLICY


def require_evidence_policy(policy: object | None) -> EvidencePolicy:
    """Require the locked evidence policy, installing the default when absent."""

    if policy is None:
        return _DEFAULT_POLICY
    if type(policy) is not EvidencePolicy:
        _fail("evidence_invalid_input")
    return policy


def _require_text(value: object, code: str) -> str:
    if type(value) is not str or not value:
        _fail(code)
    return value


def _require_reference(value: object, code: str = "evidence_invalid_input") -> str:
    reference = _require_text(value, code)
    if len(reference) > _EVIDENCE_REFERENCE_MAX_LEN:
        _fail(code)
    return reference


def _require_enum[EnumT: StrEnum](value: object, enum_type: type[EnumT]) -> EnumT:
    if type(value) is not enum_type:
        _fail("evidence_invalid_input")
    return value


def _require_digest(value: object, code: str = "evidence_invalid_id") -> str:
    if type(value) is not str or _HEX64_PATTERN.match(value) is None:
        _fail(code)
    return value


def _require_ordinal(value: object) -> int:
    if type(value) is not int or value < 0:
        _fail("evidence_invalid_input")
    return value


def _require_tick(value: object) -> int:
    if type(value) is not int or value < 0:
        _fail("evidence_invalid_input")
    return value


def _digest(*parts: str) -> str:
    payload = EVIDENCE_SEPARATOR.join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _short_digest(*parts: str) -> str:
    return _digest(*parts)[:EVIDENCE_ID_HEX_LEN]


def _prefix_pattern(prefix: str) -> re.Pattern[str]:
    return re.compile(rf"^{prefix}[0-9a-f]{{{EVIDENCE_ID_HEX_LEN}}}$")


_SOURCE_ID_PATTERN: Final[re.Pattern[str]] = _prefix_pattern(EVIDENCE_SOURCE_ID_PREFIX)
_TESTIMONY_ID_PATTERN: Final[re.Pattern[str]] = _prefix_pattern(
    EVIDENCE_TESTIMONY_ID_PREFIX
)
_ITEM_ID_PATTERN: Final[re.Pattern[str]] = _prefix_pattern(EVIDENCE_ITEM_ID_PREFIX)
_CUSTODY_ID_PATTERN: Final[re.Pattern[str]] = _prefix_pattern(
    EVIDENCE_CUSTODY_ID_PREFIX
)
_CONTRADICTION_ID_PATTERN: Final[re.Pattern[str]] = _prefix_pattern(
    EVIDENCE_CONTRADICTION_ID_PREFIX
)
_EVALUATION_ID_PATTERN: Final[re.Pattern[str]] = _prefix_pattern(
    EVIDENCE_EVALUATION_ID_PREFIX
)
_ANCHOR_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^(?:{EVIDENCE_SOURCE_ID_PREFIX}|{EVIDENCE_TESTIMONY_ID_PREFIX})"
    rf"[0-9a-f]{{{EVIDENCE_ID_HEX_LEN}}}$"
)
_EVIDENCE_LOCAL_REF_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^(?:{EVIDENCE_SOURCE_ID_PREFIX}|{EVIDENCE_TESTIMONY_ID_PREFIX}|"
    rf"{EVIDENCE_ITEM_ID_PREFIX}|{EVIDENCE_CUSTODY_ID_PREFIX})"
    rf"[0-9a-f]{{{EVIDENCE_ID_HEX_LEN}}}$"
)


def _require_evidence_anchor_id(value: object) -> str:
    if type(value) is not str or _ANCHOR_ID_PATTERN.match(value) is None:
        _fail("evidence_invalid_id")
    return value


def evidence_source_id(
    owner_id: str,
    source_kind: str,
    reference_kind: str,
    reference_id: str,
    ordinal: int,
) -> str:
    """Mint one owner-local evidence source id from its typed anchor."""

    owner = _require_text(owner_id, "evidence_invalid_input")
    kind = _require_enum(source_kind, EvidenceSourceKind)
    anchor_kind = _require_enum(reference_kind, EvidenceReferenceKind)
    anchor = _require_reference(reference_id)
    anchor_ordinal = _require_ordinal(ordinal)
    body = _short_digest(
        EVIDENCE_SOURCE_NAMESPACE,
        owner,
        kind.value,
        anchor_kind.value,
        anchor,
        str(anchor_ordinal),
    )
    return f"{EVIDENCE_SOURCE_ID_PREFIX}{body}"


def evidence_testimony_id(
    owner_id: str,
    speaker_id: str,
    channel: str,
    root_ref: str,
    ordinal: int,
) -> str:
    """Mint one owner-local witness-statement id from attributed provenance."""

    owner = _require_text(owner_id, "evidence_invalid_input")
    speaker = _require_reference(speaker_id)
    testimony_channel = _require_enum(channel, EvidenceTestimonyChannel)
    root = _require_reference(root_ref)
    statement_ordinal = _require_ordinal(ordinal)
    body = _short_digest(
        EVIDENCE_TESTIMONY_NAMESPACE,
        owner,
        speaker,
        testimony_channel.value,
        root,
        str(statement_ordinal),
    )
    return f"{EVIDENCE_TESTIMONY_ID_PREFIX}{body}"


def evidence_item_id(
    owner_id: str,
    source_id: str,
    interpretation: str,
    ordinal: int,
) -> str:
    """Mint one owner-local interpreted-item id from an anchor and stance.

    The anchor is either an evidence source id (``evs-``) or a witness-statement
    id (``evw-``). An item always hangs off exactly one of them.
    """

    owner = _require_text(owner_id, "evidence_invalid_input")
    source = _require_evidence_anchor_id(source_id)
    stance = _require_enum(interpretation, EvidenceInterpretationKind)
    item_ordinal = _require_ordinal(ordinal)
    body = _short_digest(
        EVIDENCE_ITEM_NAMESPACE,
        owner,
        source,
        stance.value,
        str(item_ordinal),
    )
    return f"{EVIDENCE_ITEM_ID_PREFIX}{body}"


def evidence_custody_id(
    owner_id: str,
    source_id: str,
    link_index: int,
    role: str,
    subject_token: str,
    tick: int,
) -> str:
    """Mint one owner-local custody-link id inside one source's belief chain."""

    owner = _require_text(owner_id, "evidence_invalid_input")
    source = require_evidence_source_id(source_id)
    index = _require_ordinal(link_index)
    custody_role = _require_enum(role, EvidenceCustodyRole)
    subject = _require_text(subject_token, "evidence_invalid_input")
    if len(subject) > _DEFAULT_POLICY.max_subject_token:
        _fail("evidence_limit_exceeded")
    absolute_tick = _require_tick(tick)
    body = _short_digest(
        EVIDENCE_CUSTODY_NAMESPACE,
        owner,
        source,
        str(index),
        custody_role.value,
        subject,
        str(absolute_tick),
    )
    return f"{EVIDENCE_CUSTODY_ID_PREFIX}{body}"


def evidence_contradiction_id(
    owner_id: str,
    first_ref: str,
    second_ref: str,
    kind: str,
    ordinal: int,
) -> str:
    """Mint one owner-local contradiction id from its ordered reference pair."""

    owner = _require_text(owner_id, "evidence_invalid_input")
    first = _require_reference(first_ref)
    second = _require_reference(second_ref)
    contradiction_kind = _require_enum(kind, EvidenceContradictionKind)
    contradiction_ordinal = _require_ordinal(ordinal)
    body = _short_digest(
        EVIDENCE_CONTRADICTION_NAMESPACE,
        owner,
        first,
        second,
        contradiction_kind.value,
        str(contradiction_ordinal),
    )
    return f"{EVIDENCE_CONTRADICTION_ID_PREFIX}{body}"


def evidence_evaluation_id(
    owner_id: str,
    item_id: str,
    basis_csv: str,
    ordinal: int,
) -> str:
    """Mint one owner-local evaluation id from an item, basis set, and ordinal."""

    owner = _require_text(owner_id, "evidence_invalid_input")
    item = require_evidence_item_id(item_id)
    basis = _require_text(basis_csv, "evidence_invalid_input")
    if len(basis) > _DEFAULT_POLICY.max_subject_token:
        _fail("evidence_limit_exceeded")
    evaluation_ordinal = _require_ordinal(ordinal)
    body = _short_digest(
        EVIDENCE_EVALUATION_NAMESPACE,
        owner,
        item,
        basis,
        str(evaluation_ordinal),
    )
    return f"{EVIDENCE_EVALUATION_ID_PREFIX}{body}"


def _require_prefix(value: object, pattern: re.Pattern[str]) -> str:
    if type(value) is not str or pattern.match(value) is None:
        _fail("evidence_invalid_id")
    return value


def require_evidence_source_id(value: object) -> str:
    return _require_prefix(value, _SOURCE_ID_PATTERN)


def require_evidence_testimony_id(value: object) -> str:
    return _require_prefix(value, _TESTIMONY_ID_PATTERN)


def require_evidence_item_id(value: object) -> str:
    return _require_prefix(value, _ITEM_ID_PATTERN)


def require_evidence_custody_id(value: object) -> str:
    return _require_prefix(value, _CUSTODY_ID_PATTERN)


def require_evidence_contradiction_id(value: object) -> str:
    return _require_prefix(value, _CONTRADICTION_ID_PATTERN)


def require_evidence_evaluation_id(value: object) -> str:
    return _require_prefix(value, _EVALUATION_ID_PATTERN)


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

_CONFIDENCE_QUANTUM: Final[Decimal] = Decimal("0.000001")
_REASON_CODE_MAX: Final[int] = 64
_MAX_NOTICES: Final[int] = 16
_FORBIDDEN_OBJECT_TYPES: Final[frozenset[str]] = frozenset(
    {
        "WorldEvent",
        "WorldState",
        "PhysicalRules",
        "MetricDocument",
        "AgentCommand",
        "EventStore",
        "WorldEngine",
        "Observation",
    }
)


def _normalize_owner(value: object) -> str:
    if type(value) is AgentId:
        return value.value
    if type(value) is str and value:
        return value
    _fail("evidence_invalid_record")


def _quantize_confidence(value: object) -> float:
    """Quantize owner confidence to the locked quantum, never a truth probability."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail("evidence_invalid_confidence")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        _fail("evidence_invalid_confidence")
    quantized = Decimal(str(number)).quantize(
        _CONFIDENCE_QUANTUM, rounding=ROUND_HALF_UP
    )
    return 0.0 if quantized == 0 else float(quantized)


def _require_optional_reference(value: object) -> str | None:
    if value is None:
        return None
    return _require_reference(value)


def _require_bool(value: object) -> bool:
    if type(value) is not bool:
        _fail("evidence_invalid_record")
    return value


def _require_reason_code(value: object) -> str:
    if type(value) is not str or len(value) > _REASON_CODE_MAX:
        _fail("evidence_invalid_record")
    return value


def _require_evidence_local_ref(value: object) -> str:
    if type(value) is not str or _EVIDENCE_LOCAL_REF_PATTERN.match(value) is None:
        _fail("evidence_invalid_id")
    return value


def _require_evidence_contradiction_ref(value: object) -> str:
    if type(value) is not str or _CONTRADICTION_ID_PATTERN.match(value) is None:
        _fail("evidence_invalid_id")
    return value


def _require_local_refs(value: object) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        _fail("evidence_invalid_record")
    references: list[str] = []
    for item in value:
        reference = _require_evidence_local_ref(item)
        if reference in references:
            _fail("evidence_duplicate_id")
        references.append(reference)
    return tuple(sorted(references))


def _require_contradiction_refs(value: object) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        _fail("evidence_invalid_record")
    references: list[str] = []
    for item in value:
        reference = _require_evidence_contradiction_ref(item)
        if reference in references:
            _fail("evidence_duplicate_id")
        references.append(reference)
    return tuple(sorted(references))


def _validate_notices(value: object) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        _fail("evidence_invalid_record")
    notices: list[str] = []
    for notice in value:
        if type(notice) is not str or notice not in EVIDENCE_NOTICE_REASONS:
            _fail("evidence_invalid_record")
        if notice not in notices:
            notices.append(notice)
    if len(notices) > _MAX_NOTICES:
        _fail("evidence_invalid_record")
    return tuple(sorted(notices))


def _validate_bases(value: object) -> tuple[EvidenceTrustBasis, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        _fail("evidence_invalid_record")
    bases: list[EvidenceTrustBasis] = []
    for item in value:
        basis = _require_enum(item, EvidenceTrustBasis)
        if basis in bases:
            _fail("evidence_invalid_record")
        bases.append(basis)
    if not bases:
        _fail("evidence_invalid_record")
    ordered = tuple(sorted(bases, key=lambda basis: basis.value))
    if EvidenceTrustBasis.UNKNOWN in ordered and len(ordered) > 1:
        _fail("evidence_invalid_record")
    if EvidenceTrustBasis.NONE in ordered and len(ordered) > 1:
        _fail("evidence_invalid_record")
    return ordered


def _reject_forbidden_fields(model: type[object]) -> None:
    if not is_dataclass(model):
        return
    for field in fields(model):
        if field.name in EVIDENCE_FORBIDDEN_FIELD_NAMES:
            _fail("evidence_forbidden_field")


def _reject_forbidden_value(value: object) -> None:
    if type(value).__name__ in _FORBIDDEN_OBJECT_TYPES:
        _fail("evidence_forbidden_field")


@dataclass(frozen=True, slots=True)
class EvidenceSource:
    """One owner belief about where a piece of evidence came from."""

    source_id: str
    owner_id: str
    source_kind: EvidenceSourceKind
    reference_kind: EvidenceReferenceKind
    reference_id: str
    provenance: EvidenceProvenanceChannel
    tick: int
    ordinal: int
    confidence: float
    integrity: EvidenceIntegrityBelief = EvidenceIntegrityBelief.UNCERTAIN
    correlation_id: str | None = None
    actor_id: str | None = None
    root_ref: str | None = None
    independently_evidenced: bool = False

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        owner = _normalize_owner(self.owner_id)
        object.__setattr__(self, "owner_id", owner)
        source_kind = _require_enum(self.source_kind, EvidenceSourceKind)
        reference_kind = _require_enum(self.reference_kind, EvidenceReferenceKind)
        reference_id = _require_reference(self.reference_id)
        ordinal = _require_ordinal(self.ordinal)
        source_id = require_evidence_source_id(self.source_id)
        if source_id != evidence_source_id(
            owner, source_kind, reference_kind, reference_id, ordinal
        ):
            _fail("evidence_invalid_id")
        provenance = _require_enum(self.provenance, EvidenceProvenanceChannel)
        integrity = _require_enum(self.integrity, EvidenceIntegrityBelief)
        if reference_kind is EvidenceReferenceKind.UNKNOWN and provenance not in {
            EvidenceProvenanceChannel.UNKNOWN,
            EvidenceProvenanceChannel.DERIVED,
        }:
            _fail("evidence_invalid_record")
        if provenance is EvidenceProvenanceChannel.RECORDED and source_kind not in {
            EvidenceSourceKind.WRITTEN_RECORD,
            EvidenceSourceKind.ARTIFACT,
        }:
            _fail("evidence_invalid_record")
        independent = _require_bool(self.independently_evidenced)
        if independent and provenance is EvidenceProvenanceChannel.COMMUNICATED:
            _fail("evidence_invalid_record")
        object.__setattr__(self, "source_kind", source_kind)
        object.__setattr__(self, "reference_kind", reference_kind)
        object.__setattr__(self, "reference_id", reference_id)
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "integrity", integrity)
        object.__setattr__(self, "tick", _require_tick(self.tick))
        object.__setattr__(self, "ordinal", ordinal)
        object.__setattr__(self, "confidence", _quantize_confidence(self.confidence))
        object.__setattr__(
            self, "correlation_id", _require_optional_reference(self.correlation_id)
        )
        object.__setattr__(self, "actor_id", _require_optional_reference(self.actor_id))
        object.__setattr__(self, "root_ref", _require_optional_reference(self.root_ref))
        object.__setattr__(self, "independently_evidenced", independent)


@dataclass(frozen=True, slots=True)
class EvidenceWitnessStatement:
    """One owner belief about what a speaker said and how it reached the owner."""

    testimony_id: str
    owner_id: str
    speaker_id: str
    subject_token: str
    channel: EvidenceTestimonyChannel
    confidence: float
    provenance: EvidenceProvenanceChannel
    tick: int
    ordinal: int
    root_ref: str | None = None
    independently_evidenced: bool = False
    source_id: str | None = None
    context_ref: str | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        owner = _normalize_owner(self.owner_id)
        object.__setattr__(self, "owner_id", owner)
        speaker = _require_reference(self.speaker_id)
        subject = _require_reference(self.subject_token)
        if len(subject) > _DEFAULT_POLICY.max_subject_token:
            _fail("evidence_limit_exceeded")
        channel = _require_enum(self.channel, EvidenceTestimonyChannel)
        provenance = _require_enum(self.provenance, EvidenceProvenanceChannel)
        root_ref = _require_optional_reference(self.root_ref)
        if channel is EvidenceTestimonyChannel.COMMUNICATED:
            if root_ref is None:
                _fail("evidence_invalid_record")
            if _require_bool(self.independently_evidenced):
                _fail("evidence_invalid_record")
        elif root_ref is not None:
            _fail("evidence_invalid_record")
        ordinal = _require_ordinal(self.ordinal)
        testimony_id = require_evidence_testimony_id(self.testimony_id)
        if testimony_id != evidence_testimony_id(
            owner, speaker, channel, root_ref or "-", ordinal
        ):
            _fail("evidence_invalid_id")
        source_id = self.source_id
        if source_id is not None:
            source_id = require_evidence_source_id(source_id)
        object.__setattr__(self, "testimony_id", testimony_id)
        object.__setattr__(self, "speaker_id", speaker)
        object.__setattr__(self, "subject_token", subject)
        object.__setattr__(self, "channel", channel)
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "root_ref", root_ref)
        object.__setattr__(self, "tick", _require_tick(self.tick))
        object.__setattr__(self, "ordinal", ordinal)
        object.__setattr__(self, "confidence", _quantize_confidence(self.confidence))
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(
            self, "context_ref", _require_optional_reference(self.context_ref)
        )
        object.__setattr__(
            self,
            "independently_evidenced",
            _require_bool(self.independently_evidenced),
        )


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """One owner interpretation of a source or witness statement."""

    item_id: str
    owner_id: str
    interpretation: EvidenceInterpretationKind
    subject_token: str
    confidence: float
    tick: int
    status: EvidenceItemStatus
    provenance: EvidenceProvenanceChannel
    reason_code: str
    ordinal: int
    source_id: str | None = None
    testimony_id: str | None = None
    contradiction_refs: tuple[str, ...] = ()
    context_ref: str | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        owner = _normalize_owner(self.owner_id)
        object.__setattr__(self, "owner_id", owner)
        interpretation = _require_enum(self.interpretation, EvidenceInterpretationKind)
        subject = _require_reference(self.subject_token)
        if len(subject) > _DEFAULT_POLICY.max_subject_token:
            _fail("evidence_limit_exceeded")
        status = _require_enum(self.status, EvidenceItemStatus)
        provenance = _require_enum(self.provenance, EvidenceProvenanceChannel)
        reason_code = _require_reason_code(self.reason_code)
        source_id = self.source_id
        testimony_id = self.testimony_id
        if (source_id is None) == (testimony_id is None):
            _fail("evidence_invalid_record")
        if source_id is not None:
            source_id = require_evidence_source_id(source_id)
        if testimony_id is not None:
            testimony_id = require_evidence_testimony_id(testimony_id)
        if status is EvidenceItemStatus.RETRACTED and not reason_code:
            _fail("evidence_invalid_record")
        ordinal = _require_ordinal(self.ordinal)
        anchor = cast(str, source_id if source_id is not None else testimony_id)
        item_id = require_evidence_item_id(self.item_id)
        if item_id != evidence_item_id(owner, anchor, interpretation, ordinal):
            _fail("evidence_invalid_id")
        object.__setattr__(self, "item_id", item_id)
        object.__setattr__(self, "interpretation", interpretation)
        object.__setattr__(self, "subject_token", subject)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "reason_code", reason_code)
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "testimony_id", testimony_id)
        object.__setattr__(
            self,
            "contradiction_refs",
            _require_contradiction_refs(self.contradiction_refs),
        )
        object.__setattr__(self, "tick", _require_tick(self.tick))
        object.__setattr__(self, "ordinal", ordinal)
        object.__setattr__(self, "confidence", _quantize_confidence(self.confidence))
        object.__setattr__(
            self, "context_ref", _require_optional_reference(self.context_ref)
        )


@dataclass(frozen=True, slots=True)
class EvidenceCustodyLink:
    """One owner belief about one link in a source's chain of custody."""

    custody_id: str
    owner_id: str
    source_id: str
    link_index: int
    role: EvidenceCustodyRole
    subject_token: str
    provenance: EvidenceProvenanceChannel
    integrity: EvidenceIntegrityBelief
    witnessed: bool
    tick: int
    holder_token: str | None = None
    custodian_token: str | None = None
    location_token: str | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        owner = _normalize_owner(self.owner_id)
        object.__setattr__(self, "owner_id", owner)
        source_id = require_evidence_source_id(self.source_id)
        link_index = _require_ordinal(self.link_index)
        role = _require_enum(self.role, EvidenceCustodyRole)
        subject = _require_reference(self.subject_token)
        if len(subject) > _DEFAULT_POLICY.max_subject_token:
            _fail("evidence_limit_exceeded")
        provenance = _require_enum(self.provenance, EvidenceProvenanceChannel)
        integrity = _require_enum(self.integrity, EvidenceIntegrityBelief)
        witnessed = _require_bool(self.witnessed)
        holder = _require_optional_reference(self.holder_token)
        custodian = _require_optional_reference(self.custodian_token)
        location = _require_optional_reference(self.location_token)
        if role is EvidenceCustodyRole.HOLDER:
            if holder is None or custodian is not None:
                _fail("evidence_invalid_record")
        elif role is EvidenceCustodyRole.REPOSITORY_CUSTODIAN:
            if custodian is None:
                _fail("evidence_invalid_record")
        elif role is EvidenceCustodyRole.LOCATION:
            if location is None:
                _fail("evidence_invalid_record")
        elif role is EvidenceCustodyRole.OBSERVER and not witnessed:
            _fail("evidence_invalid_record")
        custody_id = require_evidence_custody_id(self.custody_id)
        if custody_id != evidence_custody_id(
            owner, source_id, link_index, role, subject, self.tick
        ):
            _fail("evidence_invalid_id")
        object.__setattr__(self, "custody_id", custody_id)
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "link_index", link_index)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "subject_token", subject)
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "integrity", integrity)
        object.__setattr__(self, "witnessed", witnessed)
        object.__setattr__(self, "tick", _require_tick(self.tick))
        object.__setattr__(self, "holder_token", holder)
        object.__setattr__(self, "custodian_token", custodian)
        object.__setattr__(self, "location_token", location)


@dataclass(frozen=True, slots=True)
class EvidenceContradiction:
    """Two retained, disagreeing owner-local references. Never a truth finding."""

    contradiction_id: str
    owner_id: str
    first_ref: str
    second_ref: str
    kind: EvidenceContradictionKind
    status: EvidenceContradictionStatus
    provenance: EvidenceProvenanceChannel
    tick: int
    ordinal: int
    context_ref: str | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        owner = _normalize_owner(self.owner_id)
        object.__setattr__(self, "owner_id", owner)
        first = _require_evidence_local_ref(self.first_ref)
        second = _require_evidence_local_ref(self.second_ref)
        if first == second:
            _fail("evidence_invalid_record")
        kind = _require_enum(self.kind, EvidenceContradictionKind)
        status = _require_enum(self.status, EvidenceContradictionStatus)
        provenance = _require_enum(self.provenance, EvidenceProvenanceChannel)
        ordinal = _require_ordinal(self.ordinal)
        contradiction_id = require_evidence_contradiction_id(self.contradiction_id)
        if contradiction_id != evidence_contradiction_id(
            owner, first, second, kind, ordinal
        ):
            _fail("evidence_invalid_id")
        object.__setattr__(self, "contradiction_id", contradiction_id)
        object.__setattr__(self, "first_ref", first)
        object.__setattr__(self, "second_ref", second)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "tick", _require_tick(self.tick))
        object.__setattr__(self, "ordinal", ordinal)
        object.__setattr__(
            self, "context_ref", _require_optional_reference(self.context_ref)
        )


@dataclass(frozen=True, slots=True)
class EvidenceEvaluation:
    """One owner evaluation of an interpreted item using owner-local trust."""

    evaluation_id: str
    owner_id: str
    item_id: str
    bases: tuple[EvidenceTrustBasis, ...]
    confidence: float
    kind: EvidenceEvaluationKind
    provenance: EvidenceProvenanceChannel
    tick: int
    ordinal: int
    relationship_ref: str | None = None
    reputation_ref: str | None = None
    rule_ref: str | None = None
    office_ref: str | None = None
    institution_ref: str | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        owner = _normalize_owner(self.owner_id)
        object.__setattr__(self, "owner_id", owner)
        item_id = require_evidence_item_id(self.item_id)
        bases = _validate_bases(self.bases)
        kind = _require_enum(self.kind, EvidenceEvaluationKind)
        provenance = _require_enum(self.provenance, EvidenceProvenanceChannel)
        ordinal = _require_ordinal(self.ordinal)
        basis_csv = ",".join(basis.value for basis in bases)
        evaluation_id = require_evidence_evaluation_id(self.evaluation_id)
        if evaluation_id != evidence_evaluation_id(owner, item_id, basis_csv, ordinal):
            _fail("evidence_invalid_id")
        object.__setattr__(self, "evaluation_id", evaluation_id)
        object.__setattr__(self, "item_id", item_id)
        object.__setattr__(self, "bases", bases)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "tick", _require_tick(self.tick))
        object.__setattr__(self, "ordinal", ordinal)
        object.__setattr__(self, "confidence", _quantize_confidence(self.confidence))
        object.__setattr__(
            self, "relationship_ref", _require_optional_reference(self.relationship_ref)
        )
        object.__setattr__(
            self, "reputation_ref", _require_optional_reference(self.reputation_ref)
        )
        object.__setattr__(self, "rule_ref", _require_optional_reference(self.rule_ref))
        object.__setattr__(
            self, "office_ref", _require_optional_reference(self.office_ref)
        )
        object.__setattr__(
            self,
            "institution_ref",
            _require_optional_reference(self.institution_ref),
        )


def _ordered_records(value: object) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        _fail("evidence_invalid_record")
    return tuple(value)


@dataclass(frozen=True, slots=True)
class EvidenceLedger:
    """One owner's evidence beliefs. ``None`` means the mode is off."""

    owner_id: str
    sources: tuple[EvidenceSource, ...] = ()
    custody_links: tuple[EvidenceCustodyLink, ...] = ()
    testimony: tuple[EvidenceWitnessStatement, ...] = ()
    items: tuple[EvidenceItem, ...] = ()
    contradictions: tuple[EvidenceContradiction, ...] = ()
    evaluations: tuple[EvidenceEvaluation, ...] = ()
    notices: tuple[str, ...] = ()
    policy_version: str = EVIDENCE_TESTIMONY_POLICY_VERSION
    observation_start_tick: int | None = None
    observation_end_tick: int | None = None
    observation_count: int = 0
    pruned_source_count: int = 0
    pruned_testimony_count: int = 0
    pruned_item_count: int = 0
    pruned_custody_count: int = 0
    pruned_contradiction_count: int = 0
    pruned_evaluation_count: int = 0

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        owner = _normalize_owner(self.owner_id)
        object.__setattr__(self, "owner_id", owner)
        if self.policy_version != EVIDENCE_TESTIMONY_POLICY_VERSION:
            _fail("evidence_policy_not_locked")
        sources = _ordered_records(self.sources)
        custody_links = _ordered_records(self.custody_links)
        testimony = _ordered_records(self.testimony)
        items = _ordered_records(self.items)
        contradictions = _ordered_records(self.contradictions)
        evaluations = _ordered_records(self.evaluations)
        for collection, model, id_field in (
            (sources, EvidenceSource, "source_id"),
            (custody_links, EvidenceCustodyLink, "custody_id"),
            (testimony, EvidenceWitnessStatement, "testimony_id"),
            (items, EvidenceItem, "item_id"),
            (contradictions, EvidenceContradiction, "contradiction_id"),
            (evaluations, EvidenceEvaluation, "evaluation_id"),
        ):
            seen: set[str] = set()
            for row in collection:
                _reject_forbidden_value(row)
                if type(row) is not model:
                    _fail("evidence_invalid_record")
                identifier = getattr(row, id_field)
                if identifier in seen:
                    _fail("evidence_duplicate_id")
                seen.add(identifier)
                if row.owner_id != owner:
                    _fail("evidence_owner_mismatch")

        source_ids = {row.source_id for row in sources}
        testimony_ids = {row.testimony_id for row in testimony}
        item_ids = {row.item_id for row in items}
        custody_ids = {row.custody_id for row in custody_links}
        contradiction_ids = {row.contradiction_id for row in contradictions}
        local_refs = source_ids | testimony_ids | item_ids | custody_ids

        for row in testimony:
            if row.source_id is not None and row.source_id not in source_ids:
                _fail("evidence_unknown_reference")
        for row in items:
            if row.source_id is not None and row.source_id not in source_ids:
                _fail("evidence_unknown_reference")
            if row.testimony_id is not None and row.testimony_id not in testimony_ids:
                _fail("evidence_unknown_reference")
            for reference in row.contradiction_refs:
                if reference not in contradiction_ids:
                    _fail("evidence_unknown_reference")
        for row in custody_links:
            if row.source_id not in source_ids:
                _fail("evidence_unknown_reference")
        for row in contradictions:
            if row.first_ref not in local_refs or row.second_ref not in local_refs:
                _fail("evidence_unknown_reference")
        for row in evaluations:
            if row.item_id not in item_ids:
                _fail("evidence_unknown_reference")

        custody_by_source: dict[str, list[EvidenceCustodyLink]] = {}
        for row in custody_links:
            custody_by_source.setdefault(row.source_id, []).append(row)
        for chain in custody_by_source.values():
            indices: set[int] = set()
            previous_tick = -1
            for row in sorted(chain, key=lambda link: link.link_index):
                if row.link_index in indices:
                    _fail("evidence_chain_conflict")
                indices.add(row.link_index)
                if row.tick < previous_tick:
                    _fail("evidence_chain_conflict")
                previous_tick = row.tick

        start = self.observation_start_tick
        end = self.observation_end_tick
        if start is not None:
            start = _require_tick(start)
        if end is not None:
            end = _require_tick(end)
        if start is not None and end is not None and end < start:
            _fail("evidence_tick_mismatch")
        object.__setattr__(self, "observation_start_tick", start)
        object.__setattr__(self, "observation_end_tick", end)
        object.__setattr__(
            self, "observation_count", _require_ordinal(self.observation_count)
        )
        for name in (
            "pruned_source_count",
            "pruned_testimony_count",
            "pruned_item_count",
            "pruned_custody_count",
            "pruned_contradiction_count",
            "pruned_evaluation_count",
        ):
            object.__setattr__(self, name, _require_ordinal(getattr(self, name)))
        object.__setattr__(
            self, "sources", tuple(sorted(sources, key=lambda row: row.source_id))
        )
        object.__setattr__(
            self,
            "custody_links",
            tuple(
                sorted(
                    custody_links,
                    key=lambda row: (row.source_id, row.link_index, row.custody_id),
                )
            ),
        )
        object.__setattr__(
            self,
            "testimony",
            tuple(sorted(testimony, key=lambda row: row.testimony_id)),
        )
        object.__setattr__(
            self, "items", tuple(sorted(items, key=lambda row: row.item_id))
        )
        object.__setattr__(
            self,
            "contradictions",
            tuple(sorted(contradictions, key=lambda row: row.contradiction_id)),
        )
        object.__setattr__(
            self,
            "evaluations",
            tuple(sorted(evaluations, key=lambda row: row.evaluation_id)),
        )
        object.__setattr__(self, "notices", _validate_notices(self.notices))
        _LOG.debug(
            "evidence_ledger_validated sources=%s testimony=%s items=%s "
            "contradictions=%s evaluations=%s",
            len(sources),
            len(testimony),
            len(items),
            len(contradictions),
            len(evaluations),
        )

    @property
    def enabled(self) -> bool:
        return True

    @property
    def has_content(self) -> bool:
        return bool(
            self.sources
            or self.custody_links
            or self.testimony
            or self.items
            or self.contradictions
            or self.evaluations
        )

    @property
    def coverage(self) -> str:
        if any(
            (
                self.pruned_source_count,
                self.pruned_testimony_count,
                self.pruned_item_count,
                self.pruned_custody_count,
                self.pruned_contradiction_count,
                self.pruned_evaluation_count,
            )
        ):
            return "partial"
        if "evidence_truncated" in self.notices:
            return "partial"
        return "complete"

    @property
    def active_items(self) -> tuple[EvidenceItem, ...]:
        return tuple(
            item for item in self.items if item.status is EvidenceItemStatus.ACTIVE
        )

    @property
    def custody_gap_count(self) -> int:
        return sum(
            build_custody_chain(self, source.source_id).gap_count
            for source in self.sources
        )

    @property
    def custody_conflict_count(self) -> int:
        return sum(
            build_custody_chain(self, source.source_id).conflict_count
            for source in self.sources
        )


def empty_evidence_ledger(owner_id: str | AgentId, *, tick: int = 0) -> EvidenceLedger:
    """Return an enabled-but-empty ledger for one owner."""

    absolute_tick = _require_tick(tick)
    return EvidenceLedger(
        owner_id=_normalize_owner(owner_id),
        observation_start_tick=absolute_tick,
        observation_end_tick=absolute_tick,
    )


def require_owner_evidence(
    value: object | None,
    owner_id: object,
    *,
    field_name: str = "evidence",
) -> EvidenceLedger | None:
    """Reject a foreign or mistyped evidence ledger. ``None`` passes."""

    if value is None:
        return None
    owner = _normalize_owner(owner_id)
    if type(value) is not EvidenceLedger:
        _LOG.warning("evidence_carry_rejected field=%s reason=invalid_type", field_name)
        raise TypeError(f"{field_name} must be EvidenceLedger")
    if value.owner_id != owner:
        _LOG.error(
            "evidence_validation_failed field=%s reason_code=owner_mismatch",
            field_name,
        )
        _fail("evidence_owner_mismatch")
    return value


def _record_material(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _record_material(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, (tuple, list)):
        return [_record_material(item) for item in value]
    return value


def evidence_ledger_digest(ledger: EvidenceLedger) -> str:
    """Return a canonical digest over sorted, bounded ledger records."""

    if type(ledger) is not EvidenceLedger:
        raise TypeError("ledger must be EvidenceLedger")
    payload = json.dumps(
        _record_material(ledger),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _prune_note(notices: list[str]) -> None:
    if "evidence_truncated" not in notices:
        notices.append("evidence_truncated")


def enforce_evidence_limits(
    ledger: EvidenceLedger, policy: EvidencePolicy | None = None
) -> EvidenceLedger:
    """Apply every policy cap deterministically, with explicit notices.

    Overflow drops in the documented order (evaluations, contradictions,
    custody links, items, testimony, sources), each sorted by stable id, then
    cascades to dependent rows. Truncation never silently drops a row.
    """

    if type(ledger) is not EvidenceLedger:
        raise TypeError("ledger must be EvidenceLedger")
    limits = require_evidence_policy(policy)

    pruned = {
        "source": ledger.pruned_source_count,
        "testimony": ledger.pruned_testimony_count,
        "item": ledger.pruned_item_count,
        "custody": ledger.pruned_custody_count,
        "contradiction": ledger.pruned_contradiction_count,
        "evaluation": ledger.pruned_evaluation_count,
    }
    notices = list(ledger.notices)

    def _cap(rows: Sequence[Any], maximum: int, name: str) -> list[Any]:
        ordered = sorted(rows, key=lambda row: _record_id(row))
        if len(ordered) <= maximum:
            return list(ordered)
        pruned[name] += len(ordered) - maximum
        _prune_note(notices)
        return ordered[:maximum]

    evaluations = _cap(ledger.evaluations, limits.max_evaluations, "evaluation")
    contradictions = _cap(
        ledger.contradictions, limits.max_contradictions, "contradiction"
    )
    custody = _cap(
        ledger.custody_links,
        limits.max_custody_links_per_source * max(1, len(ledger.sources)),
        "custody",
    )
    items = _cap(ledger.items, limits.max_items, "item")
    testimony = _cap(ledger.testimony, limits.max_testimony, "testimony")
    sources = _cap(ledger.sources, limits.max_sources, "source")

    def _cascade() -> None:
        nonlocal evaluations, contradictions, custody, items, testimony, sources
        source_ids = {row.source_id for row in sources}
        testimony_kept = [
            row
            for row in testimony
            if row.source_id is None or row.source_id in source_ids
        ]
        pruned["testimony"] += len(testimony) - len(testimony_kept)
        testimony = testimony_kept
        testimony_ids = {row.testimony_id for row in testimony}
        items_kept = [
            row
            for row in items
            if (row.source_id is None or row.source_id in source_ids)
            and (row.testimony_id is None or row.testimony_id in testimony_ids)
        ]
        pruned["item"] += len(items) - len(items_kept)
        items = items_kept
        custody_kept = [row for row in custody if row.source_id in source_ids]
        pruned["custody"] += len(custody) - len(custody_kept)
        custody = custody_kept
        local_ids = (
            source_ids
            | testimony_ids
            | {row.item_id for row in items}
            | {row.custody_id for row in custody}
        )
        contradiction_kept = [
            row
            for row in contradictions
            if row.first_ref in local_ids and row.second_ref in local_ids
        ]
        pruned["contradiction"] += len(contradictions) - len(contradiction_kept)
        contradictions = contradiction_kept
        contradiction_ids = {row.contradiction_id for row in contradictions}
        item_ids = {row.item_id for row in items}
        evaluation_kept = [row for row in evaluations if row.item_id in item_ids]
        pruned["evaluation"] += len(evaluations) - len(evaluation_kept)
        evaluations = evaluation_kept
        sanitized: list[EvidenceItem] = []
        for row in items:
            kept_refs = tuple(
                reference
                for reference in row.contradiction_refs
                if reference in contradiction_ids
            )
            if kept_refs != row.contradiction_refs:
                row = EvidenceItem(
                    item_id=row.item_id,
                    owner_id=row.owner_id,
                    interpretation=row.interpretation,
                    subject_token=row.subject_token,
                    confidence=row.confidence,
                    tick=row.tick,
                    status=row.status,
                    provenance=row.provenance,
                    reason_code=row.reason_code,
                    ordinal=row.ordinal,
                    source_id=row.source_id,
                    testimony_id=row.testimony_id,
                    contradiction_refs=kept_refs,
                    context_ref=row.context_ref,
                )
            sanitized.append(row)
        items = sanitized

    _cascade()
    total = (
        len(sources)
        + len(custody)
        + len(testimony)
        + len(items)
        + len(contradictions)
        + len(evaluations)
    )
    if total > limits.max_total_records:
        _prune_note(notices)
        for name, rows in (
            ("evaluation", evaluations),
            ("contradiction", contradictions),
            ("custody", custody),
            ("item", items),
            ("testimony", testimony),
            ("source", sources),
        ):
            if total <= limits.max_total_records:
                break
            ordered = sorted(rows, key=lambda row: _record_id(row))
            drop = min(len(ordered), total - limits.max_total_records)
            pruned[name] += drop
            rows[:] = ordered[: len(ordered) - drop]
            total -= drop
        _cascade()

    if any(pruned[name] for name in pruned):
        _LOG.warning(
            "evidence_truncated sources=%s testimony=%s items=%s custody=%s "
            "contradictions=%s evaluations=%s",
            pruned["source"],
            pruned["testimony"],
            pruned["item"],
            pruned["custody"],
            pruned["contradiction"],
            pruned["evaluation"],
        )

    return EvidenceLedger(
        owner_id=ledger.owner_id,
        sources=tuple(sources),
        custody_links=tuple(custody),
        testimony=tuple(testimony),
        items=tuple(items),
        contradictions=tuple(contradictions),
        evaluations=tuple(evaluations),
        notices=tuple(notices),
        policy_version=ledger.policy_version,
        observation_start_tick=ledger.observation_start_tick,
        observation_end_tick=ledger.observation_end_tick,
        observation_count=ledger.observation_count,
        pruned_source_count=pruned["source"],
        pruned_testimony_count=pruned["testimony"],
        pruned_item_count=pruned["item"],
        pruned_custody_count=pruned["custody"],
        pruned_contradiction_count=pruned["contradiction"],
        pruned_evaluation_count=pruned["evaluation"],
    )


def _record_id(row: object) -> str:
    for attribute in (
        "source_id",
        "testimony_id",
        "item_id",
        "custody_id",
        "contradiction_id",
        "evaluation_id",
    ):
        value = getattr(row, attribute, None)
        if isinstance(value, str):
            return value
    return ""


# ---------------------------------------------------------------------------
# Owner-visible inputs and deterministic collection
# ---------------------------------------------------------------------------

_OBSERVED_SOURCE_KIND: Final[Mapping[str, EvidenceSourceKind]] = MappingProxyType(
    {
        EvidenceReferenceKind.ARTIFACT.value: EvidenceSourceKind.ARTIFACT,
        EvidenceReferenceKind.DURABLE_RECORD.value: EvidenceSourceKind.WRITTEN_RECORD,
        EvidenceReferenceKind.OBSERVED_OCCURRENCE.value: (
            EvidenceSourceKind.PHYSICAL_STATE
        ),
        EvidenceReferenceKind.OBSERVED_COMMUNICATION.value: (
            EvidenceSourceKind.WITNESS_TESTIMONY
        ),
        EvidenceReferenceKind.REPOSITORY_ENTRY.value: EvidenceSourceKind.WRITTEN_RECORD,
    }
)

_FRAME_ACT_ORDER: Final[tuple[str, ...]] = (
    "assert_source",
    "cite_record",
    "testify",
    "claim_custody",
    "interpret",
    "contradict",
    "retract",
)


@dataclass(frozen=True, slots=True)
class EvidenceObservedReference:
    """One owner-visible observed anchor. Carries no observation body."""

    reference_kind: EvidenceReferenceKind = EvidenceReferenceKind.OBSERVED_OCCURRENCE
    reference_id: str = ""
    tick: int = 0
    integrity: EvidenceIntegrityBelief = EvidenceIntegrityBelief.UNCERTAIN
    correlation_id: str | None = None
    actor_id: str | None = None
    holder_token: str | None = None
    custodian_token: str | None = None
    location_token: str | None = None
    ordinal: int = 0
    owner_id: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceRememberedReference:
    """One owner-local recalled trace plus an opaque correlation token."""

    memory_id: str = ""
    source_event_id: str | None = None
    tick: int = 0
    confidence: float = 0.5
    reconstruction_id: str | None = None
    ordinal: int = 0
    owner_id: str | None = None


@dataclass(frozen=True, slots=True)
class EvidencePriorAgreement:
    """One owner-local commitment used as a prior-agreement source."""

    local_ref: str = ""
    parties: tuple[str, ...] = ()
    kind: str = "commitment"
    tick: int = 0
    confidence: float = 0.5
    ordinal: int = 0
    owner_id: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceReputationInput:
    """One owner-relative reputation band, never a shared score."""

    target_token: str = ""
    band: str = "unknown"
    confidence: float = 0.5
    tick: int = 0
    ordinal: int = 0
    owner_id: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceOwnerContext:
    """Owner-relative trust inputs. Never a peer ledger or a global score."""

    relationship_trust: tuple[tuple[str, float], ...] = ()
    reputation_bands: tuple[tuple[str, str], ...] = ()
    governing_rule_ids: tuple[str, ...] = ()
    office_refs: tuple[str, ...] = ()
    institution_refs: tuple[str, ...] = ()


def _check_input_owner(value: object, owner: str) -> None:
    input_owner = getattr(value, "owner_id", None)
    if input_owner is None:
        return
    if _normalize_owner(input_owner) != owner:
        _fail("evidence_owner_mismatch")


def _append_notice(notices: list[str], reason: str) -> None:
    if reason not in notices and len(notices) < _MAX_NOTICES:
        notices.append(reason)


def _reference_source_kind(reference_kind: EvidenceReferenceKind) -> EvidenceSourceKind:
    return _OBSERVED_SOURCE_KIND.get(reference_kind.value, EvidenceSourceKind.UNKNOWN)


def evidence_source_kind_for_reference(
    reference_kind: EvidenceReferenceKind,
) -> EvidenceSourceKind:
    """Map one owner-visible reference kind to a closed source kind."""

    return _reference_source_kind(_require_enum(reference_kind, EvidenceReferenceKind))


def _next_ordinal(rows: Sequence[object]) -> int:
    return len(rows)


def _find_source(
    sources: Sequence[EvidenceSource], reference: str
) -> EvidenceSource | None:
    for row in sources:
        if row.source_id == reference:
            return row
    for row in sources:
        if row.reference_id == reference:
            return row
    return None


def _find_item(items: Sequence[EvidenceItem], reference: str) -> EvidenceItem | None:
    for row in items:
        if row.item_id == reference:
            return row
    return None


def _item_by_id(items: Sequence[EvidenceItem], item_id: str) -> EvidenceItem | None:
    for row in items:
        if row.item_id == item_id:
            return row
    return None


def _custody_link_index(custody: Sequence[EvidenceCustodyLink], source_id: str) -> int:
    return sum(1 for row in custody if row.source_id == source_id)


def apply_evidence_update(
    ledger: EvidenceLedger,
    *,
    owner_id: str | AgentId,
    tick: int,
    frames: Sequence[EvidenceFrame] = (),
    observed: Sequence[EvidenceObservedReference] = (),
    remembered: Sequence[EvidenceRememberedReference] = (),
    prior_agreements: Sequence[EvidencePriorAgreement] = (),
    reputation: Sequence[EvidenceReputationInput] = (),
) -> EvidenceLedger:
    """Apply owner-visible inputs to one owner's ledger deterministically.

    The function is pure: it never reads world state, an event store, a command,
    another owner's ledger, or a peer belief store. Frames are already parsed
    and attributed by the caller.
    """

    from agents.cognition.evidence_testimony_communication import (
        EVIDENCE_CONFIDENCE_BANDS,
        EvidenceAct,
    )

    if type(ledger) is not EvidenceLedger:
        raise TypeError("ledger must be EvidenceLedger")
    owner = _normalize_owner(owner_id)
    if owner != ledger.owner_id:
        _fail("evidence_owner_mismatch")
    absolute_tick = _require_tick(tick)
    for sequence in (observed, remembered, prior_agreements, reputation):
        if isinstance(sequence, (str, bytes)) or not isinstance(
            sequence, (tuple, list)
        ):
            _fail("evidence_invalid_record")

    sources = list(ledger.sources)
    custody = list(ledger.custody_links)
    testimony = list(ledger.testimony)
    items = list(ledger.items)
    contradictions = list(ledger.contradictions)
    evaluations = list(ledger.evaluations)
    notices = list(ledger.notices)

    for observed_item in observed:
        if type(observed_item) is not EvidenceObservedReference:
            _fail("evidence_invalid_record")
        _check_input_owner(observed_item, owner)
        reference_kind = _require_enum(
            observed_item.reference_kind, EvidenceReferenceKind
        )
        provenance = EvidenceProvenanceChannel.DIRECT_OBSERVATION
        reference_id = observed_item.reference_id
        source_kind = _reference_source_kind(reference_kind)
        if type(reference_id) is not str or not reference_id:
            reference_kind = EvidenceReferenceKind.UNKNOWN
            source_kind = EvidenceSourceKind.UNKNOWN
            reference_id = f"unknown-{len(sources)}"
            provenance = EvidenceProvenanceChannel.DERIVED
            _append_notice(notices, "evidence_reference_unknown")
        ordinal = _next_ordinal(sources)
        source = EvidenceSource(
            source_id=evidence_source_id(
                owner, source_kind, reference_kind, reference_id, ordinal
            ),
            owner_id=owner,
            source_kind=source_kind,
            reference_kind=reference_kind,
            reference_id=reference_id,
            correlation_id=observed_item.correlation_id,
            provenance=provenance,
            tick=_require_tick(observed_item.tick),
            actor_id=observed_item.actor_id,
            confidence=_quantize_confidence(0.5),
            integrity=_require_enum(observed_item.integrity, EvidenceIntegrityBelief),
            ordinal=ordinal,
        )
        sources.append(source)
        for role, token in (
            (EvidenceCustodyRole.HOLDER, observed_item.holder_token),
            (EvidenceCustodyRole.REPOSITORY_CUSTODIAN, observed_item.custodian_token),
            (EvidenceCustodyRole.LOCATION, observed_item.location_token),
        ):
            if token is None:
                continue
            index = _custody_link_index(custody, source.source_id)
            custody.append(
                EvidenceCustodyLink(
                    custody_id=evidence_custody_id(
                        owner,
                        source.source_id,
                        index,
                        role,
                        source.reference_id,
                        absolute_tick,
                    ),
                    owner_id=owner,
                    source_id=source.source_id,
                    link_index=index,
                    role=role,
                    subject_token=source.reference_id,
                    provenance=provenance,
                    integrity=source.integrity,
                    witnessed=role is EvidenceCustodyRole.OBSERVER,
                    tick=absolute_tick,
                    holder_token=token if role is EvidenceCustodyRole.HOLDER else None,
                    custodian_token=(
                        token
                        if role is EvidenceCustodyRole.REPOSITORY_CUSTODIAN
                        else None
                    ),
                    location_token=(
                        token if role is EvidenceCustodyRole.LOCATION else None
                    ),
                )
            )

    for remembered_item in remembered:
        if type(remembered_item) is not EvidenceRememberedReference:
            _fail("evidence_invalid_record")
        _check_input_owner(remembered_item, owner)
        memory_id = _require_reference(remembered_item.memory_id)
        reference_kind = (
            EvidenceReferenceKind.RECONSTRUCTED_MEMORY
            if remembered_item.reconstruction_id is not None
            else EvidenceReferenceKind.MEMORY_TRACE
        )
        ordinal = _next_ordinal(sources)
        sources.append(
            EvidenceSource(
                source_id=evidence_source_id(
                    owner,
                    EvidenceSourceKind.REMEMBERED_EVENT,
                    reference_kind,
                    memory_id,
                    ordinal,
                ),
                owner_id=owner,
                source_kind=EvidenceSourceKind.REMEMBERED_EVENT,
                reference_kind=reference_kind,
                reference_id=memory_id,
                correlation_id=remembered_item.source_event_id,
                provenance=EvidenceProvenanceChannel.REMEMBERED,
                tick=_require_tick(remembered_item.tick),
                confidence=_quantize_confidence(remembered_item.confidence),
                integrity=EvidenceIntegrityBelief.UNCERTAIN,
                ordinal=ordinal,
            )
        )

    for agreement_item in prior_agreements:
        if type(agreement_item) is not EvidencePriorAgreement:
            _fail("evidence_invalid_record")
        _check_input_owner(agreement_item, owner)
        local_ref = _require_reference(agreement_item.local_ref)
        ordinal = _next_ordinal(sources)
        sources.append(
            EvidenceSource(
                source_id=evidence_source_id(
                    owner,
                    EvidenceSourceKind.PRIOR_AGREEMENT,
                    EvidenceReferenceKind.COMMITMENT,
                    local_ref,
                    ordinal,
                ),
                owner_id=owner,
                source_kind=EvidenceSourceKind.PRIOR_AGREEMENT,
                reference_kind=EvidenceReferenceKind.COMMITMENT,
                reference_id=local_ref,
                provenance=EvidenceProvenanceChannel.REMEMBERED,
                tick=_require_tick(agreement_item.tick),
                confidence=_quantize_confidence(agreement_item.confidence),
                integrity=EvidenceIntegrityBelief.UNCERTAIN,
                ordinal=ordinal,
            )
        )

    for reputation_item in reputation:
        if type(reputation_item) is not EvidenceReputationInput:
            _fail("evidence_invalid_record")
        _check_input_owner(reputation_item, owner)
        target = _require_reference(reputation_item.target_token)
        ordinal = _next_ordinal(sources)
        sources.append(
            EvidenceSource(
                source_id=evidence_source_id(
                    owner,
                    EvidenceSourceKind.REPUTATION,
                    EvidenceReferenceKind.REPUTATION_RECORD,
                    target,
                    ordinal,
                ),
                owner_id=owner,
                source_kind=EvidenceSourceKind.REPUTATION,
                reference_kind=EvidenceReferenceKind.REPUTATION_RECORD,
                reference_id=target,
                provenance=EvidenceProvenanceChannel.INFERRED,
                tick=_require_tick(reputation_item.tick),
                confidence=_quantize_confidence(reputation_item.confidence),
                integrity=EvidenceIntegrityBelief.UNCERTAIN,
                ordinal=ordinal,
            )
        )

    ordered_frames = sorted(
        frames,
        key=lambda frame: (
            _FRAME_ACT_ORDER.index(getattr(getattr(frame, "act", None), "value", ""))
            if getattr(getattr(frame, "act", None), "value", "") in _FRAME_ACT_ORDER
            else len(_FRAME_ACT_ORDER)
        ),
    )
    for frame in ordered_frames:
        if type(frame).__name__ != "EvidenceFrame":
            _fail("evidence_invalid_record")
        act = frame.act
        band = frame.confidence_band
        if band is None:
            _fail("evidence_untrusted_frame")
        confidence = EVIDENCE_CONFIDENCE_BANDS[band]
        subject = cast(str, frame.subject_token)
        if act is EvidenceAct.ASSERT_SOURCE:
            reference_kind = cast(EvidenceReferenceKind, frame.reference_kind)
            reference_id = cast(str, frame.reference_id)
            source_kind = cast(EvidenceSourceKind, frame.source_kind)
            ordinal = _next_ordinal(sources)
            sources.append(
                EvidenceSource(
                    source_id=evidence_source_id(
                        owner, source_kind, reference_kind, reference_id, ordinal
                    ),
                    owner_id=owner,
                    source_kind=source_kind,
                    reference_kind=reference_kind,
                    reference_id=reference_id,
                    provenance=EvidenceProvenanceChannel.COMMUNICATED,
                    tick=absolute_tick,
                    confidence=confidence,
                    integrity=EvidenceIntegrityBelief.UNCERTAIN,
                    ordinal=ordinal,
                )
            )
        elif act is EvidenceAct.CITE_RECORD:
            reference_id = cast(str, frame.reference_id)
            ordinal = _next_ordinal(sources)
            sources.append(
                EvidenceSource(
                    source_id=evidence_source_id(
                        owner,
                        EvidenceSourceKind.WRITTEN_RECORD,
                        EvidenceReferenceKind.DURABLE_RECORD,
                        reference_id,
                        ordinal,
                    ),
                    owner_id=owner,
                    source_kind=EvidenceSourceKind.WRITTEN_RECORD,
                    reference_kind=EvidenceReferenceKind.DURABLE_RECORD,
                    reference_id=reference_id,
                    provenance=EvidenceProvenanceChannel.RECORDED,
                    tick=absolute_tick,
                    confidence=confidence,
                    integrity=EvidenceIntegrityBelief.UNCERTAIN,
                    ordinal=ordinal,
                )
            )
        elif act is EvidenceAct.TESTIFY:
            speaker = cast(str, frame.witness_id)
            channel = cast(EvidenceTestimonyChannel, frame.testimony_channel)
            root_ref = frame.root_ref
            ordinal = _next_ordinal(testimony)
            testimony_id = evidence_testimony_id(
                owner, speaker, channel, root_ref or "-", ordinal
            )
            source_kind = EvidenceSourceKind.WITNESS_TESTIMONY
            reference_kind = (
                EvidenceReferenceKind.OBSERVED_OCCURRENCE
                if channel is EvidenceTestimonyChannel.DIRECT
                else EvidenceReferenceKind.OBSERVED_COMMUNICATION
            )
            reference_id = root_ref if root_ref is not None else testimony_id
            source_ordinal = _next_ordinal(sources)
            source = EvidenceSource(
                source_id=evidence_source_id(
                    owner, source_kind, reference_kind, reference_id, source_ordinal
                ),
                owner_id=owner,
                source_kind=source_kind,
                reference_kind=reference_kind,
                reference_id=reference_id,
                provenance=(
                    EvidenceProvenanceChannel.DIRECT_OBSERVATION
                    if channel is EvidenceTestimonyChannel.DIRECT
                    else EvidenceProvenanceChannel.COMMUNICATED
                ),
                tick=absolute_tick,
                actor_id=speaker,
                confidence=confidence,
                integrity=EvidenceIntegrityBelief.UNCERTAIN,
                root_ref=root_ref,
                ordinal=source_ordinal,
                independently_evidenced=(channel is EvidenceTestimonyChannel.DIRECT),
            )
            sources.append(source)
            testimony.append(
                EvidenceWitnessStatement(
                    testimony_id=testimony_id,
                    owner_id=owner,
                    speaker_id=speaker,
                    subject_token=subject,
                    channel=channel,
                    root_ref=root_ref,
                    independently_evidenced=(
                        channel is EvidenceTestimonyChannel.DIRECT
                    ),
                    confidence=confidence,
                    provenance=(
                        EvidenceProvenanceChannel.DIRECT_OBSERVATION
                        if channel is EvidenceTestimonyChannel.DIRECT
                        else EvidenceProvenanceChannel.COMMUNICATED
                    ),
                    tick=absolute_tick,
                    source_id=source.source_id,
                    ordinal=ordinal,
                )
            )
        elif act is EvidenceAct.CLAIM_CUSTODY:
            reference = cast(str, frame.reference_id)
            found_source = _find_source(sources, reference)
            if found_source is None:
                _append_notice(notices, "evidence_reference_unknown")
                continue
            role = cast(EvidenceCustodyRole, frame.custody_role)
            token = (
                frame.counterparty_token
                if role is EvidenceCustodyRole.HOLDER
                else frame.location_token
                if role is EvidenceCustodyRole.LOCATION
                else frame.custodian_token
            )
            index = _custody_link_index(custody, found_source.source_id)
            custody.append(
                EvidenceCustodyLink(
                    custody_id=evidence_custody_id(
                        owner,
                        found_source.source_id,
                        index,
                        role,
                        found_source.reference_id,
                        absolute_tick,
                    ),
                    owner_id=owner,
                    source_id=found_source.source_id,
                    link_index=index,
                    role=role,
                    subject_token=found_source.reference_id,
                    provenance=EvidenceProvenanceChannel.COMMUNICATED,
                    integrity=EvidenceIntegrityBelief.UNCERTAIN,
                    witnessed=role is EvidenceCustodyRole.OBSERVER,
                    tick=absolute_tick,
                    holder_token=(
                        token if role is EvidenceCustodyRole.HOLDER else None
                    ),
                    custodian_token=(
                        token
                        if role is EvidenceCustodyRole.REPOSITORY_CUSTODIAN
                        else None
                    ),
                    location_token=(
                        token if role is EvidenceCustodyRole.LOCATION else None
                    ),
                )
            )
        elif act is EvidenceAct.INTERPRET:
            reference = cast(str, frame.reference_id)
            testimony_row = next(
                (row for row in testimony if row.testimony_id == reference), None
            )
            found_source = (
                None
                if testimony_row is not None
                or reference.startswith(EVIDENCE_TESTIMONY_ID_PREFIX)
                else _find_source(sources, reference)
            )
            if found_source is None and testimony_row is None:
                _append_notice(notices, "evidence_reference_unknown")
                continue
            interpretation = cast(EvidenceInterpretationKind, frame.interpretation)
            anchor = (
                found_source.source_id
                if found_source is not None
                else cast(EvidenceWitnessStatement, testimony_row).testimony_id
            )
            ordinal = _next_ordinal(items)
            items.append(
                EvidenceItem(
                    item_id=evidence_item_id(owner, anchor, interpretation, ordinal),
                    owner_id=owner,
                    source_id=(
                        found_source.source_id if found_source is not None else None
                    ),
                    testimony_id=(None if found_source is not None else anchor),
                    interpretation=interpretation,
                    subject_token=subject,
                    confidence=confidence,
                    tick=absolute_tick,
                    status=EvidenceItemStatus.ACTIVE,
                    provenance=EvidenceProvenanceChannel.COMMUNICATED,
                    reason_code="",
                    ordinal=ordinal,
                )
            )
        elif act is EvidenceAct.CONTRADICT:
            first = cast(str, frame.first_ref)
            second = cast(str, frame.second_ref)
            known = (
                {row.source_id for row in sources}
                | {row.testimony_id for row in testimony}
                | {row.item_id for row in items}
                | {row.custody_id for row in custody}
            )
            if first not in known or second not in known:
                _append_notice(notices, "evidence_reference_unknown")
                continue
            ordinal = _next_ordinal(contradictions)
            contradictions.append(
                EvidenceContradiction(
                    contradiction_id=evidence_contradiction_id(
                        owner,
                        first,
                        second,
                        cast(EvidenceContradictionKind, frame.contradiction_kind),
                        ordinal,
                    ),
                    owner_id=owner,
                    first_ref=first,
                    second_ref=second,
                    kind=cast(EvidenceContradictionKind, frame.contradiction_kind),
                    status=EvidenceContradictionStatus.UNRESOLVED,
                    provenance=EvidenceProvenanceChannel.DERIVED,
                    tick=absolute_tick,
                    ordinal=ordinal,
                )
            )
        elif act is EvidenceAct.RETRACT:
            reference = cast(str, frame.reference_id)
            existing = _find_item(items, reference)
            if existing is None:
                _append_notice(notices, "evidence_reference_unknown")
                continue
            items[items.index(existing)] = EvidenceItem(
                item_id=existing.item_id,
                owner_id=owner,
                source_id=existing.source_id,
                testimony_id=existing.testimony_id,
                interpretation=existing.interpretation,
                subject_token=existing.subject_token,
                confidence=existing.confidence,
                tick=existing.tick,
                status=EvidenceItemStatus.RETRACTED,
                provenance=existing.provenance,
                contradiction_refs=existing.contradiction_refs,
                context_ref=existing.context_ref,
                reason_code="owner_retracted",
                ordinal=existing.ordinal,
            )
            _append_notice(notices, "evidence_item_retracted")

    updated = EvidenceLedger(
        owner_id=owner,
        sources=tuple(sources),
        custody_links=tuple(custody),
        testimony=tuple(testimony),
        items=tuple(items),
        contradictions=tuple(contradictions),
        evaluations=tuple(evaluations),
        notices=tuple(notices),
        policy_version=ledger.policy_version,
        observation_start_tick=ledger.observation_start_tick or absolute_tick,
        observation_end_tick=absolute_tick,
        observation_count=_require_ordinal(ledger.observation_count + 1),
        pruned_source_count=ledger.pruned_source_count,
        pruned_testimony_count=ledger.pruned_testimony_count,
        pruned_item_count=ledger.pruned_item_count,
        pruned_custody_count=ledger.pruned_custody_count,
        pruned_contradiction_count=ledger.pruned_contradiction_count,
        pruned_evaluation_count=ledger.pruned_evaluation_count,
    )
    _LOG.info(
        "evidence_update_applied tick=%s sources=%s testimony=%s items=%s "
        "contradictions=%s",
        absolute_tick,
        len(updated.sources),
        len(updated.testimony),
        len(updated.items),
        len(updated.contradictions),
    )
    return enforce_evidence_limits(updated)


def record_evidence_utterance(
    ledger: EvidenceLedger,
    command: object,
    *,
    owner_id: str | AgentId,
    tick: int,
) -> EvidenceLedger:
    """Retain at most one owner-authored ``ev_v1`` frame from a selected command."""

    from agents.cognition.evidence_testimony_communication import (
        EVIDENCE_FRAME_SUBJECT,
        evidence_frame_party_matches,
        parse_evidence_frame_relation,
    )

    if type(ledger) is not EvidenceLedger:
        raise TypeError("ledger must be EvidenceLedger")
    owner = _normalize_owner(owner_id)
    utterance = getattr(command, "utterance", None)
    content = getattr(utterance, "content", None)
    relations = tuple(getattr(content, "relations", ()) or ())
    frame = None
    for relation in relations:
        if getattr(relation, "subject", None) != EVIDENCE_FRAME_SUBJECT:
            continue
        frame = parse_evidence_frame_relation(relation)
        break
    if frame is None:
        return ledger
    declared = getattr(utterance, "declared", None)
    speaker = getattr(declared, "immediate_source_id", None)
    speaker_value = speaker if type(speaker) is str else getattr(speaker, "value", None)
    if speaker_value != owner:
        _LOG.warning("evidence_frame_skipped reason=foreign_actor")
        return ledger
    if not evidence_frame_party_matches(frame, speaker):
        _LOG.warning("evidence_frame_foreign_witness")
        return ledger
    return apply_evidence_update(ledger, owner_id=owner, tick=tick, frames=(frame,))


# ---------------------------------------------------------------------------
# Provenance and chain-of-custody beliefs
# ---------------------------------------------------------------------------

_CUSTODY_SOURCE_KINDS: Final[frozenset[EvidenceSourceKind]] = frozenset(
    {
        EvidenceSourceKind.ARTIFACT,
        EvidenceSourceKind.WRITTEN_RECORD,
        EvidenceSourceKind.PHYSICAL_STATE,
    }
)


@dataclass(frozen=True, slots=True)
class EvidenceProvenanceSummary:
    """One owner-visible provenance summary. Never an objective audit claim."""

    source_id: str
    channel: EvidenceProvenanceChannel
    root_ref: str | None
    opaque_correlation_present: bool
    attributed_actor: str | None
    independent_root: bool
    tick: int


@dataclass(frozen=True, slots=True)
class EvidenceCustodyChain:
    """One owner belief about a source's custody continuity."""

    source_id: str
    status: EvidenceCustodyStatus
    links: tuple[EvidenceCustodyLink, ...]
    first_tick: int | None
    last_tick: int | None
    gap_count: int
    conflict_count: int


def _require_source(ledger: EvidenceLedger, source_id: object) -> EvidenceSource:
    reference = require_evidence_source_id(source_id)
    for row in ledger.sources:
        if row.source_id == reference:
            return row
    _fail("evidence_unknown_reference")


def derive_provenance_summary(
    ledger: EvidenceLedger, source_id: str
) -> EvidenceProvenanceSummary:
    """Return the owner-visible provenance summary for one source."""

    if type(ledger) is not EvidenceLedger:
        raise TypeError("ledger must be EvidenceLedger")
    source = _require_source(ledger, source_id)
    return EvidenceProvenanceSummary(
        source_id=source.source_id,
        channel=source.provenance,
        root_ref=source.root_ref,
        opaque_correlation_present=source.correlation_id is not None,
        attributed_actor=source.actor_id,
        independent_root=source.independently_evidenced,
        tick=source.tick,
    )


def derive_all_provenance(
    ledger: EvidenceLedger,
) -> tuple[EvidenceProvenanceSummary, ...]:
    """Return one provenance summary per source, ordered by source id."""

    if type(ledger) is not EvidenceLedger:
        raise TypeError("ledger must be EvidenceLedger")
    return tuple(
        derive_provenance_summary(ledger, source.source_id) for source in ledger.sources
    )


def build_custody_chain(ledger: EvidenceLedger, source_id: str) -> EvidenceCustodyChain:
    """Derive one source's custody belief chain without synthesizing links."""

    if type(ledger) is not EvidenceLedger:
        raise TypeError("ledger must be EvidenceLedger")
    source = _require_source(ledger, source_id)
    links = tuple(
        sorted(
            (
                link
                for link in ledger.custody_links
                if link.source_id == source.source_id
            ),
            key=lambda link: (link.link_index, link.tick, link.custody_id),
        )
    )
    if source.source_kind not in _CUSTODY_SOURCE_KINDS:
        return EvidenceCustodyChain(
            source_id=source.source_id,
            status=EvidenceCustodyStatus.NOT_APPLICABLE,
            links=links,
            first_tick=None,
            last_tick=None,
            gap_count=0,
            conflict_count=0,
        )
    if not links:
        return EvidenceCustodyChain(
            source_id=source.source_id,
            status=EvidenceCustodyStatus.UNKNOWN,
            links=(),
            first_tick=None,
            last_tick=None,
            gap_count=0,
            conflict_count=0,
        )

    gap_count = 0
    expected_index = 0
    for link in links:
        if link.link_index != expected_index:
            gap_count += max(1, link.link_index - expected_index)
        expected_index = link.link_index + 1
    for previous, current in pairwise(links):
        if current.tick > previous.tick + 1:
            gap_count += current.tick - previous.tick - 1

    conflict_count = 0
    by_tick: dict[int, list[EvidenceCustodyLink]] = {}
    for link in links:
        by_tick.setdefault(link.tick, []).append(link)
    for group in by_tick.values():
        if len(group) < 2:
            continue
        for attribute in ("holder_token", "custodian_token", "location_token"):
            values = {
                getattr(link, attribute)
                for link in group
                if getattr(link, attribute) is not None
            }
            if len(values) > 1:
                conflict_count += 1

    if conflict_count:
        status = EvidenceCustodyStatus.CONFLICTING_BELIEF
    elif gap_count:
        status = EvidenceCustodyStatus.INCOMPLETE_BELIEF
    else:
        status = EvidenceCustodyStatus.COMPLETE_BELIEF

    if status is EvidenceCustodyStatus.INCOMPLETE_BELIEF:
        _LOG.warning("evidence_chain_incomplete source_count=%s", 1)
    _LOG.debug(
        "evidence_chain_status status=%s link_count=%s",
        status.value,
        len(links),
    )
    return EvidenceCustodyChain(
        source_id=source.source_id,
        status=status,
        links=links,
        first_tick=links[0].tick,
        last_tick=links[-1].tick,
        gap_count=gap_count,
        conflict_count=conflict_count,
    )


def apply_custody_links(
    ledger: EvidenceLedger,
    pending: Sequence[EvidenceCustodyLink],
    *,
    owner_id: str | AgentId | None = None,
) -> EvidenceLedger:
    """Append validated owner-matching custody links without repairing gaps."""

    if type(ledger) is not EvidenceLedger:
        raise TypeError("ledger must be EvidenceLedger")
    owner = ledger.owner_id if owner_id is None else _normalize_owner(owner_id)
    if owner != ledger.owner_id:
        _fail("evidence_owner_mismatch")
    if isinstance(pending, (str, bytes)) or not isinstance(pending, (tuple, list)):
        _fail("evidence_invalid_record")
    links = list(ledger.custody_links)
    source_ids = {source.source_id for source in ledger.sources}
    for link in pending:
        if type(link) is not EvidenceCustodyLink:
            _fail("evidence_invalid_record")
        if link.owner_id != owner:
            _fail("evidence_owner_mismatch")
        if link.source_id not in source_ids:
            _fail("evidence_unknown_reference")
        links.append(link)
    return EvidenceLedger(
        owner_id=ledger.owner_id,
        sources=ledger.sources,
        custody_links=tuple(links),
        testimony=ledger.testimony,
        items=ledger.items,
        contradictions=ledger.contradictions,
        evaluations=ledger.evaluations,
        notices=ledger.notices,
        policy_version=ledger.policy_version,
        observation_start_tick=ledger.observation_start_tick,
        observation_end_tick=ledger.observation_end_tick,
        observation_count=ledger.observation_count,
        pruned_source_count=ledger.pruned_source_count,
        pruned_testimony_count=ledger.pruned_testimony_count,
        pruned_item_count=ledger.pruned_item_count,
        pruned_custody_count=ledger.pruned_custody_count,
        pruned_contradiction_count=ledger.pruned_contradiction_count,
        pruned_evaluation_count=ledger.pruned_evaluation_count,
    )


# ---------------------------------------------------------------------------
# Owner-relative evaluation and retained contradictions
# ---------------------------------------------------------------------------

_REPUTATION_BAND_CONFIDENCE: Final[Mapping[str, float]] = MappingProxyType(
    {
        "trusted": 0.8,
        "reliable": 0.7,
        "neutral": 0.5,
        "uncertain": 0.4,
        "unreliable": 0.2,
        "distrusted": 0.1,
        "unknown": 0.5,
    }
)
_AUTHORITY_BASIS_CONFIDENCE: Final[float] = 0.75
_OPPOSING_INTERPRETATIONS: Final[frozenset[EvidenceInterpretationKind]] = frozenset(
    {EvidenceInterpretationKind.SUPPORTS, EvidenceInterpretationKind.CONTRADICTS}
)
_ACTIVE_CONTRADICTION_STATUSES: Final[frozenset[EvidenceContradictionStatus]] = (
    frozenset(
        {
            EvidenceContradictionStatus.UNRESOLVED,
            EvidenceContradictionStatus.OWNER_PREFERS_FIRST,
            EvidenceContradictionStatus.OWNER_PREFERS_SECOND,
        }
    )
)


def _evaluation_counterparty(ledger: EvidenceLedger, item: EvidenceItem) -> str | None:
    if item.source_id is not None:
        for source in ledger.sources:
            if source.source_id == item.source_id:
                return source.actor_id
        return None
    if item.testimony_id is not None:
        for statement in ledger.testimony:
            if statement.testimony_id == item.testimony_id:
                return statement.speaker_id
    return None


def _evaluation_bases(
    ledger: EvidenceLedger,
    item: EvidenceItem,
    counterparty: str | None,
    context: EvidenceOwnerContext,
) -> tuple[tuple[EvidenceTrustBasis, str | None], ...]:
    relationship = dict(context.relationship_trust)
    reputation = dict(context.reputation_bands)
    bases: list[tuple[EvidenceTrustBasis, str | None]] = []
    source = next(
        (row for row in ledger.sources if row.source_id == item.source_id), None
    )
    if source is not None and (
        source.provenance is EvidenceProvenanceChannel.DIRECT_OBSERVATION
    ):
        bases.append((EvidenceTrustBasis.DIRECT_EXPERIENCE, None))
    if counterparty is not None and counterparty in relationship:
        bases.append((EvidenceTrustBasis.RELATIONSHIP_TRUST, counterparty))
    if counterparty is not None and counterparty in reputation:
        bases.append((EvidenceTrustBasis.REPUTATION, counterparty))
    if (
        source is not None
        and source.reference_kind is EvidenceReferenceKind.OFFICE_RECORD
        and context.office_refs
    ):
        bases.append((EvidenceTrustBasis.ROLE_AUTHORITY, context.office_refs[0]))
    if (
        source is not None
        and source.reference_kind is EvidenceReferenceKind.RULE_RECORD
        and context.governing_rule_ids
    ):
        bases.append((EvidenceTrustBasis.RULE_AUTHORITY, context.governing_rule_ids[0]))
    if (
        source is not None
        and source.reference_kind is EvidenceReferenceKind.INSTITUTION_RECORD
        and context.institution_refs
    ):
        bases.append(
            (
                EvidenceTrustBasis.INSTITUTION_MEMBERSHIP,
                context.institution_refs[0],
            )
        )
    return tuple(bases)


def _blend_confidence(
    policy: EvidencePolicy,
    item: EvidenceItem,
    bases: Sequence[tuple[EvidenceTrustBasis, str | None]],
    context: EvidenceOwnerContext,
) -> tuple[float, tuple[EvidenceTrustBasis, ...]]:
    relationship = dict(context.relationship_trust)
    reputation = dict(context.reputation_bands)
    weights: dict[EvidenceTrustBasis, int] = {
        EvidenceTrustBasis.DIRECT_EXPERIENCE: (policy.trust_weight_direct_experience),
        EvidenceTrustBasis.RELATIONSHIP_TRUST: policy.trust_weight_relationship,
        EvidenceTrustBasis.REPUTATION: policy.trust_weight_reputation,
        EvidenceTrustBasis.ROLE_AUTHORITY: policy.trust_weight_role_authority,
        EvidenceTrustBasis.RULE_AUTHORITY: policy.trust_weight_role_authority,
        EvidenceTrustBasis.INSTITUTION_MEMBERSHIP: (policy.trust_weight_role_authority),
    }
    values: dict[EvidenceTrustBasis, float] = {
        EvidenceTrustBasis.DIRECT_EXPERIENCE: item.confidence,
    }
    for basis, reference in bases:
        if basis is EvidenceTrustBasis.RELATIONSHIP_TRUST and reference is not None:
            values[basis] = _quantize_confidence(relationship[reference])
        elif basis is EvidenceTrustBasis.REPUTATION and reference is not None:
            values[basis] = _REPUTATION_BAND_CONFIDENCE.get(reputation[reference], 0.5)
        elif basis is not EvidenceTrustBasis.DIRECT_EXPERIENCE:
            values[basis] = _AUTHORITY_BASIS_CONFIDENCE
    if not bases:
        return policy.neutral_confidence, (EvidenceTrustBasis.NONE,)
    total_weight = 0
    total = 0.0
    for basis, _reference in bases:
        weight = weights[basis]
        total_weight += weight
        total += weight * values[basis]
    if total_weight == 0:
        return policy.neutral_confidence, tuple(basis for basis, _reference in bases)
    return (
        _quantize_confidence(total / float(total_weight)),
        tuple(basis for basis, _reference in bases),
    )


def _contradiction_touches(
    contradictions: Sequence[EvidenceContradiction], item_id: str
) -> bool:
    return any(
        row.status in _ACTIVE_CONTRADICTION_STATUSES
        and item_id in {row.first_ref, row.second_ref}
        for row in contradictions
    )


def _root_of(ledger: EvidenceLedger, item: EvidenceItem) -> str | None:
    if item.testimony_id is not None:
        for statement in ledger.testimony:
            if statement.testimony_id == item.testimony_id:
                return statement.root_ref
    if item.source_id is not None:
        for source in ledger.sources:
            if source.source_id == item.source_id:
                return source.root_ref
    return None


def _is_corroborated(ledger: EvidenceLedger, item: EvidenceItem) -> bool:
    own_root = _root_of(ledger, item)
    own_anchor = item.source_id or item.testimony_id
    for other in ledger.items:
        if other.item_id == item.item_id or other.status is not (
            EvidenceItemStatus.ACTIVE
        ):
            continue
        if other.subject_token != item.subject_token:
            continue
        if {
            item.interpretation,
            other.interpretation,
        } == _OPPOSING_INTERPRETATIONS:
            continue
        other_anchor = other.source_id or other.testimony_id
        if other_anchor == own_anchor:
            continue
        other_root = _root_of(ledger, other)
        if own_root is not None and other_root is not None and own_root == other_root:
            continue
        return True
    return False


def _require_ledger_owner(ledger: EvidenceLedger, owner_id: object) -> str:
    owner = _normalize_owner(owner_id)
    if owner != ledger.owner_id:
        _fail("evidence_owner_mismatch")
    return owner


def evaluate_evidence(
    ledger: EvidenceLedger,
    *,
    owner_id: str | AgentId,
    tick: int,
    context: EvidenceOwnerContext,
) -> EvidenceLedger:
    """Evaluate each active item using only the owner's own trust inputs."""

    if type(ledger) is not EvidenceLedger:
        raise TypeError("ledger must be EvidenceLedger")
    if type(context) is not EvidenceOwnerContext:
        raise TypeError("context must be EvidenceOwnerContext")
    owner = _require_ledger_owner(ledger, owner_id)
    absolute_tick = _require_tick(tick)
    policy = _DEFAULT_POLICY
    evaluated = {row.item_id for row in ledger.evaluations if row.tick == absolute_tick}
    evaluations = list(ledger.evaluations)
    notices = list(ledger.notices)
    counts = {"corroborated": 0, "contested": 0}

    for item in ledger.items:
        if item.item_id in evaluated:
            continue
        counterparty = _evaluation_counterparty(ledger, item)
        base_entries = _evaluation_bases(ledger, item, counterparty, context)
        confidence, bases = _blend_confidence(policy, item, base_entries, context)
        if bases == (EvidenceTrustBasis.NONE,):
            _append_notice(notices, "evidence_trust_basis_missing")
        if item.status is EvidenceItemStatus.RETRACTED:
            kind = EvidenceEvaluationKind.EXCLUDED_BY_OWNER
        elif _contradiction_touches(ledger.contradictions, item.item_id):
            kind = EvidenceEvaluationKind.CONTESTED
            counts["contested"] += 1
        elif _is_corroborated(ledger, item):
            kind = EvidenceEvaluationKind.CORROBORATED
            counts["corroborated"] += 1
        else:
            kind = EvidenceEvaluationKind.UNCORROBORATED
        reference_by_basis = {basis: reference for basis, reference in base_entries}
        ordinal = len(evaluations)
        evaluations.append(
            EvidenceEvaluation(
                evaluation_id=evidence_evaluation_id(
                    owner,
                    item.item_id,
                    ",".join(basis.value for basis in bases),
                    ordinal,
                ),
                owner_id=owner,
                item_id=item.item_id,
                bases=bases,
                confidence=confidence,
                kind=kind,
                provenance=EvidenceProvenanceChannel.DERIVED,
                tick=absolute_tick,
                relationship_ref=reference_by_basis.get(
                    EvidenceTrustBasis.RELATIONSHIP_TRUST
                ),
                reputation_ref=reference_by_basis.get(EvidenceTrustBasis.REPUTATION),
                rule_ref=reference_by_basis.get(EvidenceTrustBasis.RULE_AUTHORITY),
                office_ref=reference_by_basis.get(EvidenceTrustBasis.ROLE_AUTHORITY),
                institution_ref=reference_by_basis.get(
                    EvidenceTrustBasis.INSTITUTION_MEMBERSHIP
                ),
                ordinal=ordinal,
            )
        )

    _LOG.info(
        "evidence_evaluated items=%s corroborated=%s contested=%s",
        len(evaluations),
        counts["corroborated"],
        counts["contested"],
    )
    return enforce_evidence_limits(
        EvidenceLedger(
            owner_id=ledger.owner_id,
            sources=ledger.sources,
            custody_links=ledger.custody_links,
            testimony=ledger.testimony,
            items=ledger.items,
            contradictions=ledger.contradictions,
            evaluations=tuple(evaluations),
            notices=tuple(notices),
            policy_version=ledger.policy_version,
            observation_start_tick=ledger.observation_start_tick,
            observation_end_tick=ledger.observation_end_tick,
            observation_count=ledger.observation_count,
            pruned_source_count=ledger.pruned_source_count,
            pruned_testimony_count=ledger.pruned_testimony_count,
            pruned_item_count=ledger.pruned_item_count,
            pruned_custody_count=ledger.pruned_custody_count,
            pruned_contradiction_count=ledger.pruned_contradiction_count,
            pruned_evaluation_count=ledger.pruned_evaluation_count,
        )
    )


def _source_of(ledger: EvidenceLedger, item: EvidenceItem) -> EvidenceSource | None:
    if item.source_id is None:
        return None
    return next(
        (row for row in ledger.sources if row.source_id == item.source_id), None
    )


def _opposing(first: EvidenceItem, second: EvidenceItem) -> bool:
    return {first.interpretation, second.interpretation} == _OPPOSING_INTERPRETATIONS


def detect_evidence_contradictions(
    ledger: EvidenceLedger,
    *,
    owner_id: str | AgentId,
    tick: int,
) -> EvidenceLedger:
    """Detect and retain owner-perceived contradictions. Never reconcile them."""

    if type(ledger) is not EvidenceLedger:
        raise TypeError("ledger must be EvidenceLedger")
    owner = _require_ledger_owner(ledger, owner_id)
    absolute_tick = _require_tick(tick)
    contradictions = list(ledger.contradictions)
    existing = {(row.first_ref, row.second_ref, row.kind) for row in contradictions}
    notices = list(ledger.notices)
    items = list(ledger.items)
    new_refs: dict[str, list[str]] = {}

    def _add(first_ref: str, second_ref: str, kind: EvidenceContradictionKind) -> None:
        key = (first_ref, second_ref, kind)
        if key in existing:
            return
        existing.add(key)
        ordinal = len(contradictions)
        row = EvidenceContradiction(
            contradiction_id=evidence_contradiction_id(
                owner, first_ref, second_ref, kind, ordinal
            ),
            owner_id=owner,
            first_ref=first_ref,
            second_ref=second_ref,
            kind=kind,
            status=EvidenceContradictionStatus.UNRESOLVED,
            provenance=EvidenceProvenanceChannel.DERIVED,
            tick=absolute_tick,
            ordinal=ordinal,
        )
        contradictions.append(row)
        _append_notice(notices, "evidence_contradiction_retained")
        _LOG.warning("evidence_contradiction_retained kind=%s", kind.value)
        for reference in (first_ref, second_ref):
            if reference.startswith(EVIDENCE_ITEM_ID_PREFIX):
                new_refs.setdefault(reference, []).append(row.contradiction_id)

    active = [item for item in items if item.status is EvidenceItemStatus.ACTIVE]
    for index, first in enumerate(active):
        for second in active[index + 1 :]:
            if first.subject_token != second.subject_token:
                continue
            if not _opposing(first, second):
                continue
            if (first.source_id or first.testimony_id) == (
                second.source_id or second.testimony_id
            ):
                _add(
                    first.item_id,
                    second.item_id,
                    EvidenceContradictionKind.INTERPRETATION_CONFLICT,
                )
                continue
            if first.testimony_id is not None and second.testimony_id is not None:
                first_root = _root_of(ledger, first)
                second_root = _root_of(ledger, second)
                if (
                    first_root is not None
                    and second_root is not None
                    and first_root == second_root
                ):
                    _append_notice(notices, "evidence_testimony_root_shared")
                    _add(
                        first.item_id,
                        second.item_id,
                        EvidenceContradictionKind.PROVENANCE_CONFLICT,
                    )
                else:
                    _add(
                        first.item_id,
                        second.item_id,
                        EvidenceContradictionKind.TESTIMONY_CONFLICT,
                    )
                continue
            first_source = _source_of(ledger, first)
            second_source = _source_of(ledger, second)
            kinds = {
                first_source.source_kind if first_source is not None else None,
                second_source.source_kind if second_source is not None else None,
            }
            if EvidenceSourceKind.WRITTEN_RECORD in kinds:
                _add(
                    first.item_id,
                    second.item_id,
                    EvidenceContradictionKind.RECORD_CONFLICT,
                )
            elif EvidenceSourceKind.REMEMBERED_EVENT in kinds:
                _add(
                    first.item_id,
                    second.item_id,
                    EvidenceContradictionKind.MEMORY_CONFLICT,
                )

    by_tick: dict[tuple[int, str], list[EvidenceCustodyLink]] = {}
    for link in ledger.custody_links:
        by_tick.setdefault((link.tick, link.source_id), []).append(link)
    for group in by_tick.values():
        for index, first_link in enumerate(group):
            for second_link in group[index + 1 :]:
                disagreement = any(
                    getattr(first_link, attribute) is not None
                    and getattr(second_link, attribute) is not None
                    and getattr(first_link, attribute)
                    != getattr(second_link, attribute)
                    for attribute in (
                        "holder_token",
                        "custodian_token",
                        "location_token",
                    )
                )
                if disagreement:
                    _add(
                        first_link.custody_id,
                        second_link.custody_id,
                        EvidenceContradictionKind.CUSTODY_CONFLICT,
                    )

    if new_refs:
        updated_items: list[EvidenceItem] = []
        for item in items:
            refs = new_refs.get(item.item_id)
            if refs is None:
                updated_items.append(item)
                continue
            merged = tuple(sorted({*item.contradiction_refs, *refs}))
            updated_items.append(
                EvidenceItem(
                    item_id=item.item_id,
                    owner_id=item.owner_id,
                    source_id=item.source_id,
                    testimony_id=item.testimony_id,
                    interpretation=item.interpretation,
                    subject_token=item.subject_token,
                    confidence=item.confidence,
                    tick=item.tick,
                    status=item.status,
                    provenance=item.provenance,
                    contradiction_refs=merged,
                    context_ref=item.context_ref,
                    reason_code=item.reason_code,
                    ordinal=item.ordinal,
                )
            )
        items = updated_items

    return enforce_evidence_limits(
        EvidenceLedger(
            owner_id=ledger.owner_id,
            sources=ledger.sources,
            custody_links=ledger.custody_links,
            testimony=ledger.testimony,
            items=tuple(items),
            contradictions=tuple(contradictions),
            evaluations=ledger.evaluations,
            notices=tuple(notices),
            policy_version=ledger.policy_version,
            observation_start_tick=ledger.observation_start_tick,
            observation_end_tick=ledger.observation_end_tick,
            observation_count=ledger.observation_count,
            pruned_source_count=ledger.pruned_source_count,
            pruned_testimony_count=ledger.pruned_testimony_count,
            pruned_item_count=ledger.pruned_item_count,
            pruned_custody_count=ledger.pruned_custody_count,
            pruned_contradiction_count=ledger.pruned_contradiction_count,
            pruned_evaluation_count=ledger.pruned_evaluation_count,
        )
    )


def set_contradiction_preference(
    ledger: EvidenceLedger,
    contradiction_id: str,
    status: EvidenceContradictionStatus,
    *,
    owner_id: str | AgentId,
) -> EvidenceLedger:
    """Record an explicit, revisable owner preference without deleting a side."""

    if type(ledger) is not EvidenceLedger:
        raise TypeError("ledger must be EvidenceLedger")
    _require_ledger_owner(ledger, owner_id)
    reference = require_evidence_contradiction_id(contradiction_id)
    chosen = _require_enum(status, EvidenceContradictionStatus)
    rows: list[EvidenceContradiction] = []
    found = False
    changed = False
    for row in ledger.contradictions:
        if row.contradiction_id != reference:
            rows.append(row)
            continue
        found = True
        if row.status is chosen:
            rows.append(row)
            continue
        changed = True
        rows.append(
            EvidenceContradiction(
                contradiction_id=row.contradiction_id,
                owner_id=row.owner_id,
                first_ref=row.first_ref,
                second_ref=row.second_ref,
                kind=row.kind,
                status=chosen,
                provenance=row.provenance,
                tick=row.tick,
                context_ref=row.context_ref,
                ordinal=row.ordinal,
            )
        )
    if not found:
        _fail("evidence_unknown_reference")
    notices = list(ledger.notices)
    if changed:
        _append_notice(notices, "evidence_contradiction_retained")
    return EvidenceLedger(
        owner_id=ledger.owner_id,
        sources=ledger.sources,
        custody_links=ledger.custody_links,
        testimony=ledger.testimony,
        items=ledger.items,
        contradictions=tuple(rows),
        evaluations=ledger.evaluations,
        notices=tuple(notices),
        policy_version=ledger.policy_version,
        observation_start_tick=ledger.observation_start_tick,
        observation_end_tick=ledger.observation_end_tick,
        observation_count=ledger.observation_count,
        pruned_source_count=ledger.pruned_source_count,
        pruned_testimony_count=ledger.pruned_testimony_count,
        pruned_item_count=ledger.pruned_item_count,
        pruned_custody_count=ledger.pruned_custody_count,
        pruned_contradiction_count=ledger.pruned_contradiction_count,
        pruned_evaluation_count=ledger.pruned_evaluation_count,
    )


def evidence_confidence_bias(ledger: EvidenceLedger, subject_token: str) -> float:
    """Return a bounded owner-relative confidence bias in ``[-0.25, 0.25]``."""

    if type(ledger) is not EvidenceLedger:
        raise TypeError("ledger must be EvidenceLedger")
    item_ids = {
        item.item_id for item in ledger.items if item.subject_token == subject_token
    }
    values = [row.confidence for row in ledger.evaluations if row.item_id in item_ids]
    if not values:
        return 0.0
    average = sum(values) / len(values)
    bias = (average - 0.5) * 0.5
    return max(-0.25, min(0.25, round(bias, 6)))


def evidence_contradiction_penalty(ledger: EvidenceLedger, subject_token: str) -> float:
    """Return a bounded owner-relative contradiction penalty in ``[0.0, 0.5]``."""

    if type(ledger) is not EvidenceLedger:
        raise TypeError("ledger must be EvidenceLedger")
    item_ids = {
        item.item_id for item in ledger.items if item.subject_token == subject_token
    }
    count = sum(
        1
        for row in ledger.contradictions
        if row.status in _ACTIVE_CONTRADICTION_STATUSES
        and ({row.first_ref, row.second_ref} & item_ids)
    )
    return min(0.5, 0.25 * count)


def evidence_case_summary(ledger: EvidenceLedger) -> str:
    """Return a counts-only owner case summary. Never a verdict or a score."""

    if type(ledger) is not EvidenceLedger:
        raise TypeError("ledger must be EvidenceLedger")
    return (
        f"sources={len(ledger.sources)} testimony={len(ledger.testimony)} "
        f"items={len(ledger.items)} contradictions={len(ledger.contradictions)} "
        f"evaluations={len(ledger.evaluations)}"
    )


__all__ = [
    "EVIDENCE_CONTRADICTION_ID_PREFIX",
    "EVIDENCE_CONTRADICTION_NAMESPACE",
    "EVIDENCE_CUSTODY_ID_PREFIX",
    "EVIDENCE_CUSTODY_NAMESPACE",
    "EVIDENCE_ERROR_CODES",
    "EVIDENCE_EVALUATION_ID_PREFIX",
    "EVIDENCE_EVALUATION_NAMESPACE",
    "EVIDENCE_FORBIDDEN_FIELD_NAMES",
    "EVIDENCE_ID_HEX_LEN",
    "EVIDENCE_ITEM_ID_PREFIX",
    "EVIDENCE_ITEM_NAMESPACE",
    "EVIDENCE_NOTICE_REASONS",
    "EVIDENCE_SEPARATOR",
    "EVIDENCE_SOURCE_ID_PREFIX",
    "EVIDENCE_SOURCE_NAMESPACE",
    "EVIDENCE_TESTIMONY_CONTEXT_ID",
    "EVIDENCE_TESTIMONY_ID_PREFIX",
    "EVIDENCE_TESTIMONY_IS_CAPABILITY_FLAG",
    "EVIDENCE_TESTIMONY_NAMESPACE",
    "EVIDENCE_TESTIMONY_POLICY_VERSION",
    "EVIDENCE_TESTIMONY_REQUIRED_RUNNER_SCHEMA",
    "EvidenceContradiction",
    "EvidenceContradictionKind",
    "EvidenceContradictionStatus",
    "EvidenceCustodyLink",
    "EvidenceCustodyRole",
    "EvidenceCustodyStatus",
    "EvidenceError",
    "EvidenceEvaluation",
    "EvidenceEvaluationKind",
    "EvidenceIntegrityBelief",
    "EvidenceInterpretationKind",
    "EvidenceItem",
    "EvidenceItemStatus",
    "EvidenceLedger",
    "EvidencePolicy",
    "EvidenceProvenanceChannel",
    "EvidenceReferenceKind",
    "EvidenceReportKind",
    "EvidenceSource",
    "EvidenceSourceKind",
    "EvidenceTestimonyChannel",
    "EvidenceTrustBasis",
    "EvidenceWitnessStatement",
    "default_evidence_policy",
    "empty_evidence_ledger",
    "enforce_evidence_limits",
    "evidence_contradiction_id",
    "evidence_custody_id",
    "evidence_evaluation_id",
    "evidence_item_id",
    "evidence_ledger_digest",
    "evidence_source_id",
    "evidence_testimony_id",
    "require_evidence_contradiction_id",
    "require_evidence_custody_id",
    "require_evidence_evaluation_id",
    "require_evidence_item_id",
    "require_evidence_policy",
    "require_evidence_source_id",
    "require_evidence_testimony_id",
    "require_owner_evidence",
]
