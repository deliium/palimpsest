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
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final, NoReturn

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
    """Mint one owner-local interpreted-item id from a source and stance."""

    owner = _require_text(owner_id, "evidence_invalid_input")
    source = require_evidence_source_id(source_id)
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
    "EvidenceContradictionKind",
    "EvidenceContradictionStatus",
    "EvidenceCustodyRole",
    "EvidenceCustodyStatus",
    "EvidenceError",
    "EvidenceEvaluationKind",
    "EvidenceIntegrityBelief",
    "EvidenceInterpretationKind",
    "EvidenceItemStatus",
    "EvidencePolicy",
    "EvidenceProvenanceChannel",
    "EvidenceReferenceKind",
    "EvidenceReportKind",
    "EvidenceSourceKind",
    "EvidenceTestimonyChannel",
    "EvidenceTrustBasis",
    "default_evidence_policy",
    "evidence_contradiction_id",
    "evidence_custody_id",
    "evidence_evaluation_id",
    "evidence_item_id",
    "evidence_source_id",
    "evidence_testimony_id",
    "require_evidence_contradiction_id",
    "require_evidence_custody_id",
    "require_evidence_evaluation_id",
    "require_evidence_item_id",
    "require_evidence_policy",
    "require_evidence_source_id",
    "require_evidence_testimony_id",
]
