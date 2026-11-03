"""Closed owner-scoped dispute vocabulary and identity grammar.

A dispute is one owner's belief about attributed claims, counterclaims,
testimony, evidence references, rule interpretations, mediation links, and
proposed or declared resolutions. It is never a court, judge, jury, verdict,
objective truth, justice engine, enforceable settlement, or global dispute
registry.

This module defines only frozen vocabulary, identity minters, bounded policy
values, and stable error codes. Later dispute code consumes these definitions so
a smaller implementer cannot invent case kinds, id prefixes, or limits while
writing the ledger.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass, replace
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final, NoReturn, cast

from agents.models import AgentId

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.legal_disputes")

DISPUTE_POLICY_VERSION: Final[str] = "dispute-resolution.v1"
DISPUTE_ID_HEX_LEN: Final[int] = 16

DISPUTE_CASE_ID_PREFIX: Final[str] = "dsc-"
DISPUTE_CLAIM_ID_PREFIX: Final[str] = "dcl-"
DISPUTE_TESTIMONY_ID_PREFIX: Final[str] = "dts-"
DISPUTE_EVIDENCE_ID_PREFIX: Final[str] = "dev-"
DISPUTE_RULE_REFERENCE_ID_PREFIX: Final[str] = "drf-"
DISPUTE_MEDIATION_REFERENCE_ID_PREFIX: Final[str] = "dmr-"
DISPUTE_AUTHORITY_REFERENCE_ID_PREFIX: Final[str] = "dar-"
DISPUTE_RESOLUTION_ID_PREFIX: Final[str] = "drs-"
DISPUTE_RESPONSE_ID_PREFIX: Final[str] = "drp-"

DISPUTE_CASE_NAMESPACE: Final[str] = "dispute-case"
DISPUTE_CLAIM_NAMESPACE: Final[str] = "dispute-claim"
DISPUTE_TESTIMONY_NAMESPACE: Final[str] = "dispute-testimony"
DISPUTE_EVIDENCE_NAMESPACE: Final[str] = "dispute-evidence"
DISPUTE_RULE_REFERENCE_NAMESPACE: Final[str] = "dispute-rule-reference"
DISPUTE_MEDIATION_REFERENCE_NAMESPACE: Final[str] = "dispute-mediation-reference"
DISPUTE_AUTHORITY_REFERENCE_NAMESPACE: Final[str] = "dispute-authority-reference"
DISPUTE_RESOLUTION_NAMESPACE: Final[str] = "dispute-resolution"
DISPUTE_RESPONSE_NAMESPACE: Final[str] = "dispute-resolution-response"
DISPUTE_SUBJECT_NAMESPACE: Final[str] = "dispute-subject"
DISPUTE_PARTY_SET_NAMESPACE: Final[str] = "dispute-party-set"

_SEPARATOR: Final[str] = "\x1f"
_HEX64_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_REFERENCE_MAX_LEN: Final[int] = 128


def _prefix_pattern(prefix: str) -> re.Pattern[str]:
    return re.compile(rf"^{prefix}[0-9a-f]{{{DISPUTE_ID_HEX_LEN}}}$")


_CASE_ID_PATTERN: Final[re.Pattern[str]] = _prefix_pattern(DISPUTE_CASE_ID_PREFIX)
_CLAIM_ID_PATTERN: Final[re.Pattern[str]] = _prefix_pattern(DISPUTE_CLAIM_ID_PREFIX)
_TESTIMONY_ID_PATTERN: Final[re.Pattern[str]] = _prefix_pattern(
    DISPUTE_TESTIMONY_ID_PREFIX
)
_EVIDENCE_ID_PATTERN: Final[re.Pattern[str]] = _prefix_pattern(
    DISPUTE_EVIDENCE_ID_PREFIX
)
_RULE_REFERENCE_ID_PATTERN: Final[re.Pattern[str]] = _prefix_pattern(
    DISPUTE_RULE_REFERENCE_ID_PREFIX
)
_MEDIATION_REFERENCE_ID_PATTERN: Final[re.Pattern[str]] = _prefix_pattern(
    DISPUTE_MEDIATION_REFERENCE_ID_PREFIX
)
_AUTHORITY_REFERENCE_ID_PATTERN: Final[re.Pattern[str]] = _prefix_pattern(
    DISPUTE_AUTHORITY_REFERENCE_ID_PREFIX
)
_RESOLUTION_ID_PATTERN: Final[re.Pattern[str]] = _prefix_pattern(
    DISPUTE_RESOLUTION_ID_PREFIX
)
_RESPONSE_ID_PATTERN: Final[re.Pattern[str]] = _prefix_pattern(
    DISPUTE_RESPONSE_ID_PREFIX
)


class DisputeKind(StrEnum):
    """Closed dispute subject-matter kinds requested by the feature."""

    CONTESTED_DEBT = "contested_debt"
    OWNERSHIP_CLAIM = "ownership_claim"
    CONTRACT_INTERPRETATION = "contract_interpretation"
    INJURY = "injury"
    BROKEN_PROMISE = "broken_promise"
    RESOURCE_APPROPRIATION = "resource_appropriation"
    OTHER = "other"


class DisputeClaimRole(StrEnum):
    """Closed role one claim plays inside a dispute thread."""

    CLAIM = "claim"
    COUNTERCLAIM = "counterclaim"
    SUPPLEMENTARY = "supplementary"


class DisputeClaimPolarity(StrEnum):
    """Closed stance of one attributed claim. Never a truth finding."""

    AFFIRM = "affirm"
    DENY = "deny"
    UNCERTAIN = "uncertain"


class DisputeClaimKind(StrEnum):
    """Closed proposition kind one party may assert."""

    DEBT_OWED = "debt_owed"
    ITEM_OWNED = "item_owned"
    TERM_MEANING = "term_meaning"
    HARM_CAUSED = "harm_caused"
    PROMISE_BROKEN = "promise_broken"
    RESOURCE_TAKEN = "resource_taken"
    OTHER = "other"


class DisputeSubjectKind(StrEnum):
    """Closed anchor kind a dispute is about."""

    COMMITMENT = "commitment"
    ITEM = "item"
    RESOURCE = "resource"
    ACTION = "action"
    RECORD = "record"
    RELATIONSHIP = "relationship"
    UNSPECIFIED = "unspecified"


class DisputeStatus(StrEnum):
    """Closed owner-local lifecycle status for one dispute belief."""

    OPEN = "open"
    EVIDENCE_GATHERING = "evidence_gathering"
    RULE_CITED = "rule_cited"
    MEDIATION_REFERENCED = "mediation_referenced"
    RESOLUTION_PROPOSED = "resolution_proposed"
    CONTESTED = "contested"
    APPARENTLY_RESOLVED = "apparently_resolved"
    WITHDRAWN = "withdrawn"
    ABANDONED = "abandoned"
    REOPENED = "reopened"
    EXPIRED = "expired"


class DisputeEvidenceChannel(StrEnum):
    """Closed provenance channel for one evidence reference."""

    OBSERVED = "observed"
    COMMUNICATED = "communicated"
    REMEMBERED = "remembered"
    RECORDED = "recorded"
    DERIVED = "derived"
    UNKNOWN = "unknown"


class DisputeEvidenceReferenceKind(StrEnum):
    """Closed owner-visible anchor kind. No world body or event store is carried."""

    OBSERVED_OCCURRENCE = "observed_occurrence"
    OBSERVED_COMMUNICATION = "observed_communication"
    MEMORY_TRACE = "memory_trace"
    RECONSTRUCTED_MEMORY = "reconstructed_memory"
    ARTIFACT = "artifact"
    DURABLE_RECORD = "durable_record"
    REPOSITORY_ENTRY = "repository_entry"
    COMMITMENT = "commitment"
    VALUATION = "valuation"
    MEDIATION_RECORD = "mediation_record"
    RULE_RECORD = "rule_record"
    OFFICE_RECORD = "office_record"
    INSTITUTION_RECORD = "institution_record"
    ORGANIZATION_RECORD = "organization_record"
    UNKNOWN = "unknown"


class DisputeTestimonyChannel(StrEnum):
    """Closed testimony channel. Communicated retellings share a root."""

    DIRECT = "direct"
    COMMUNICATED = "communicated"


class DisputeRuleApplicability(StrEnum):
    """Closed belief about whether a cited rule applies."""

    APPLIES = "applies"
    DOES_NOT_APPLY = "does_not_apply"
    UNCERTAIN = "uncertain"


class DisputeRuleInterpretation(StrEnum):
    """Closed interpretation stance for a cited rule version."""

    LITERAL = "literal"
    NARROW = "narrow"
    BROAD = "broad"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class DisputeRuleReferenceStatus(StrEnum):
    """Closed resolution state of a rule reference against the owner ledger."""

    RESOLVED = "resolved"
    ORPHANED = "orphaned"
    VERSION_MISMATCH = "version_mismatch"
    CONTESTED = "contested"
    RETIRED = "retired"


class DisputeAuthorityKind(StrEnum):
    """Closed authority belief cited by a party. No jurisdiction or judge exists."""

    SELF = "self"
    OFFICE = "office"
    INSTITUTION = "institution"
    ORGANIZATION = "organization"
    COLLECTIVE_DECISION = "collective_decision"
    PROCEDURE = "procedure"
    WRITTEN_RECORD = "written_record"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class DisputeMediationLinkStatus(StrEnum):
    """Closed state of a link to the owner's own mediation ledger."""

    LINKED = "linked"
    STALE = "stale"
    ORPHANED = "orphaned"
    DISPUTED = "disputed"


class DisputeResolutionSource(StrEnum):
    """Closed source of a proposed resolution. None is binding."""

    NEGOTIATED = "negotiated"
    MEDIATOR = "mediator"
    UNILATERAL = "unilateral"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class DisputeResolutionStatus(StrEnum):
    """Closed owner knowledge about a proposed resolution."""

    PROPOSED = "proposed"
    PARTIALLY_ACCEPTED = "partially_accepted"
    APPARENTLY_ACCEPTED = "apparently_accepted"
    CONTESTED = "contested"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"


class DisputeResolutionTermKind(StrEnum):
    """Closed kind of one proposed resolution term. Never executed here."""

    RETURN_ITEM = "return_item"
    TRANSFER_ITEM = "transfer_item"
    PERFORM_SERVICE = "perform_service"
    STOP_ACTION = "stop_action"
    ACKNOWLEDGE = "acknowledge"
    NO_ACTION = "no_action"


class DisputeResolutionResponseKind(StrEnum):
    """Closed per-party declaration about a proposed resolution."""

    ACCEPT = "accept"
    REJECT = "reject"
    COUNTERPROPOSE = "counterpropose"
    DEFER = "defer"
    WITHDRAW = "withdraw"


class DisputeProvenance(StrEnum):
    """Closed provenance for one owner-local dispute record."""

    SELF_ASSERTED = "self_asserted"
    COMMUNICATED = "communicated"
    DERIVED_FROM_MEMORY = "derived_from_memory"
    DERIVED_FROM_RECORD = "derived_from_record"
    DERIVED_FROM_RULE = "derived_from_rule"
    DERIVED_FROM_MEDIATION = "derived_from_mediation"
    DERIVED_FROM_OBSERVATION = "derived_from_observation"
    CONTESTED = "contested"
    ORPHANED = "orphaned"
    UNKNOWN = "unknown"


class DisputeReportKind(StrEnum):
    """Closed speech report kind one actor may assert about a dispute."""

    CLAIM_REPORTED = "claim_reported"
    TESTIMONY_REPORTED = "testimony_reported"
    RESOLUTION_REPORTED = "resolution_reported"
    ACCEPTANCE_REPORTED = "acceptance_reported"
    REJECTION_REPORTED = "rejection_reported"


DISPUTE_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "dispute_invalid_id",
        "dispute_invalid_mode",
        "dispute_invalid_owner",
        "dispute_invalid_subject",
        "dispute_invalid_reference",
        "dispute_invalid_digest",
        "dispute_invalid_ordinal",
        "dispute_invalid_tick",
        "dispute_policy_not_locked",
        "dispute_policy_mismatch",
        "dispute_party_limit",
        "dispute_subject_limit",
        "dispute_forbidden_field",
        "dispute_forbidden_input",
        "dispute_case_limit",
        "dispute_claim_limit",
        "dispute_testimony_limit",
        "dispute_evidence_limit",
        "dispute_rule_reference_limit",
        "dispute_authority_reference_limit",
        "dispute_mediation_reference_limit",
        "dispute_resolution_limit",
        "dispute_response_limit",
        "dispute_term_limit",
        "dispute_record_limit",
        "dispute_truncated",
        "dispute_invalid_ledger",
        "dispute_invalid_record",
        "dispute_owner_mismatch",
        "dispute_unknown_reference",
        "dispute_duplicate_id",
        "dispute_tick_regression",
        "dispute_frame_invalid",
        "dispute_frame_unsupported_command",
        "dispute_resolution_requires_prior_tick",
        "dispute_resolution_window_expired",
        "dispute_action_invalid",
        "dispute_response_invalid",
        "dispute_size_limit",
        "dispute_publication_exists",
        "dispute_cursor_invalid",
    }
)

DISPUTE_FORBIDDEN_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "verdict",
        "judgment",
        "court",
        "judge",
        "jury",
        "jurisdiction",
        "binding",
        "enforce",
        "guilt",
        "liable",
        "liability",
        "damages",
        "sentence",
        "decree",
        "winner",
        "loser",
        "true_owner",
        "objective_claim",
        "justice",
        "arbiter_authority",
        "case_registry",
        "global_dispute_registry",
        "authoritative_resolution",
        "enforced_by_world",
        "settlement_registry",
        "punishment",
        "police",
        "government",
        "sovereign",
        "legal_code",
        "statute",
    }
)


class DisputeError(ValueError):
    """Stable-code dispute contract violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        if code not in DISPUTE_ERROR_CODES:
            raise ValueError("dispute_invalid_error_code")
        self.code: str = code
        super().__init__(code)


def _fail(code: str) -> NoReturn:
    raise DisputeError(code)


@dataclass(frozen=True, slots=True)
class DisputePolicy:
    """Locked owner-local dispute cognition bounds.

    Every value is part of the accepted contract. Any deviation is a programming
    error and fails closed with ``dispute_policy_not_locked``.
    """

    version: str = DISPUTE_POLICY_VERSION
    max_cases: int = 16
    max_claims_per_case: int = 16
    max_testimony_per_case: int = 32
    max_evidence_per_claim: int = 16
    max_rule_references_per_case: int = 8
    max_authority_references_per_case: int = 8
    max_mediation_references_per_case: int = 4
    max_resolutions_per_case: int = 4
    max_responses_per_resolution: int = 8
    max_parties: int = 8
    max_terms_per_resolution: int = 4
    max_total_records: int = 640
    min_testimony_for_corroboration: int = 2
    resolution_window_ticks: int = 64
    max_frame_chars: int = 768
    max_relations: int = 32

    def __post_init__(self) -> None:
        for name, expected in _LOCKED_POLICY_VALUES.items():
            actual = getattr(self, name)
            if type(actual) is not type(expected) or actual != expected:
                _fail("dispute_policy_not_locked")


_LOCKED_POLICY_VALUES: Final[Mapping[str, str | int]] = MappingProxyType(
    {
        "version": DISPUTE_POLICY_VERSION,
        "max_cases": 16,
        "max_claims_per_case": 16,
        "max_testimony_per_case": 32,
        "max_evidence_per_claim": 16,
        "max_rule_references_per_case": 8,
        "max_authority_references_per_case": 8,
        "max_mediation_references_per_case": 4,
        "max_resolutions_per_case": 4,
        "max_responses_per_resolution": 8,
        "max_parties": 8,
        "max_terms_per_resolution": 4,
        "max_total_records": 640,
        "min_testimony_for_corroboration": 2,
        "resolution_window_ticks": 64,
        "max_frame_chars": 768,
        "max_relations": 32,
    }
)

_DEFAULT_POLICY: Final[DisputePolicy] = DisputePolicy()
_LOG.info("dispute_policy_constructed policy_version=%s", DISPUTE_POLICY_VERSION)


def default_dispute_policy() -> DisputePolicy:
    """Return the single locked policy instance."""

    return _DEFAULT_POLICY


def require_dispute_policy(policy: object | None) -> DisputePolicy:
    """Require the locked policy, installing the default when absent."""

    if policy is None:
        return _DEFAULT_POLICY
    if type(policy) is not DisputePolicy:
        _fail("dispute_policy_mismatch")
    return policy


def _require_text(value: object, code: str) -> str:
    if type(value) is not str or not value:
        _fail(code)
    return value


def _require_reference(value: object, code: str = "dispute_invalid_reference") -> str:
    reference = _require_text(value, code)
    if len(reference) > _REFERENCE_MAX_LEN:
        _fail(code)
    return reference


def _require_enum[EnumT: StrEnum](value: object, enum_type: type[EnumT]) -> EnumT:
    if type(value) is not enum_type:
        _fail("dispute_invalid_mode")
    _LOG.debug(
        "dispute_contract_validated name=%s count=%s",
        enum_type.__name__,
        len(enum_type),
    )
    return value


def _require_digest(value: object, code: str = "dispute_invalid_digest") -> str:
    if type(value) is not str or _HEX64_PATTERN.match(value) is None:
        _fail(code)
    return value


def _require_ordinal(value: object) -> int:
    if type(value) is not int or value < 0:
        _fail("dispute_invalid_ordinal")
    return value


def _require_tick(value: object) -> int:
    if type(value) is not int or value < 0:
        _fail("dispute_invalid_tick")
    return value


def _digest(namespace: str, material: Sequence[str]) -> str:
    payload = _SEPARATOR.join((namespace, *material))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _short_digest(namespace: str, material: Sequence[str]) -> str:
    return _digest(namespace, material)[:DISPUTE_ID_HEX_LEN]


def _canonical_json_material(material: Mapping[str, object]) -> str:
    return json.dumps(
        material, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )


def dispute_party_set_digest(party_ids: object) -> str:
    """Return a canonical digest of the sorted, de-duplicated party set.

    Party ids are private references; the digest is portable and carries no
    payload. Empty sets and sets beyond ``max_parties`` fail closed.
    """

    if type(party_ids) is not list and type(party_ids) is not tuple:
        _fail("dispute_party_limit")
    parties: list[str] = []
    for party in party_ids:
        parties.append(_require_reference(party, "dispute_party_limit"))
    unique = sorted(set(parties))
    if not unique:
        _fail("dispute_party_limit")
    if len(unique) > _DEFAULT_POLICY.max_parties:
        _fail("dispute_party_limit")
    return _digest(DISPUTE_PARTY_SET_NAMESPACE, unique)


def dispute_subject_digest(kind: object, subject_token: object) -> str:
    """Return a canonical digest of one subject kind and private token."""

    subject_kind = _require_enum(kind, DisputeSubjectKind)
    token = _require_text(subject_token, "dispute_invalid_subject")
    if len(token) > _DEFAULT_POLICY.max_frame_chars:
        _fail("dispute_subject_limit")
    return _digest(DISPUTE_SUBJECT_NAMESPACE, (subject_kind.value, token))


def dispute_case_ref(subject_token: str, party_ids: Sequence[str]) -> str:
    """Return the portable thread token shared by two discussing owners.

    The initiating party set and subject token define the thread. Later parties
    and a refined case kind do not change the reference, so two owners can keep
    discussing one thread without sharing a ledger or minting an objective case.
    """

    token = _require_text(subject_token, "dispute_invalid_subject")
    if len(token) > _DEFAULT_POLICY.max_frame_chars:
        _fail("dispute_subject_limit")
    parties = dispute_party_set_digest(party_ids)
    return _digest(DISPUTE_CASE_NAMESPACE, (token, parties))


def dispute_case_id(owner_id: str, case_ref: str) -> str:
    """Mint one owner-local dispute-case id from the portable thread token."""

    owner = _require_text(owner_id, "dispute_invalid_owner")
    reference = _require_digest(case_ref)
    body = _short_digest(DISPUTE_CASE_NAMESPACE, (owner, reference))
    return f"{DISPUTE_CASE_ID_PREFIX}{body}"


def dispute_claim_ref(
    case_ref: str,
    claimant_id: str,
    role: str,
    kind: str,
    polarity: str,
    subject_digest: str,
) -> str:
    """Return the portable claim token carried in speech."""

    case = _require_digest(case_ref)
    claimant = _require_reference(claimant_id)
    claim_role = _require_enum(role, DisputeClaimRole)
    claim_kind = _require_enum(kind, DisputeClaimKind)
    claim_polarity = _require_enum(polarity, DisputeClaimPolarity)
    subject = _require_digest(subject_digest)
    return _digest(
        DISPUTE_CLAIM_NAMESPACE,
        (
            case,
            claimant,
            claim_role.value,
            claim_kind.value,
            claim_polarity.value,
            subject,
        ),
    )


def dispute_claim_id(owner_id: str, claim_ref: str) -> str:
    """Mint one owner-local claim id from the portable claim token."""

    owner = _require_text(owner_id, "dispute_invalid_owner")
    reference = _require_digest(claim_ref)
    body = _short_digest(DISPUTE_CLAIM_NAMESPACE, (owner, reference))
    return f"{DISPUTE_CLAIM_ID_PREFIX}{body}"


def dispute_testimony_id(
    owner_id: str,
    case_ref: str,
    claim_ref: str,
    speaker_id: str,
    channel: str,
    root_ref: str,
    tick: int,
) -> str:
    """Mint one owner-local testimony id from attributed provenance."""

    owner = _require_text(owner_id, "dispute_invalid_owner")
    case = _require_digest(case_ref)
    claim = _require_digest(claim_ref)
    speaker = _require_reference(speaker_id)
    testimony_channel = _require_enum(channel, DisputeTestimonyChannel)
    root = _require_reference(root_ref)
    absolute_tick = _require_tick(tick)
    body = _short_digest(
        DISPUTE_TESTIMONY_NAMESPACE,
        (
            owner,
            case,
            claim,
            speaker,
            testimony_channel.value,
            root,
            str(absolute_tick),
        ),
    )
    return f"{DISPUTE_TESTIMONY_ID_PREFIX}{body}"


def dispute_evidence_id(
    owner_id: str,
    case_ref: str,
    claim_ref: str,
    channel: str,
    reference_kind: str,
    reference_id: str,
    ordinal: int,
) -> str:
    """Mint one owner-local evidence reference id from its typed anchor."""

    owner = _require_text(owner_id, "dispute_invalid_owner")
    case = _require_digest(case_ref)
    claim = _require_digest(claim_ref)
    evidence_channel = _require_enum(channel, DisputeEvidenceChannel)
    anchor_kind = _require_enum(reference_kind, DisputeEvidenceReferenceKind)
    anchor = _require_reference(reference_id)
    anchor_ordinal = _require_ordinal(ordinal)
    body = _short_digest(
        DISPUTE_EVIDENCE_NAMESPACE,
        (
            owner,
            case,
            claim,
            evidence_channel.value,
            anchor_kind.value,
            anchor,
            str(anchor_ordinal),
        ),
    )
    return f"{DISPUTE_EVIDENCE_ID_PREFIX}{body}"


def dispute_rule_reference_id(
    owner_id: str,
    case_ref: str,
    system_ref: str,
    rule_id: str,
    version_number: int,
    interpretation: str,
) -> str:
    """Mint one owner-local rule reference id from a formal-rule anchor."""

    owner = _require_text(owner_id, "dispute_invalid_owner")
    case = _require_digest(case_ref)
    system = _require_reference(system_ref)
    rule = _require_reference(rule_id)
    version = _require_ordinal(version_number)
    if version < 1:
        _fail("dispute_invalid_ordinal")
    stance = _require_enum(interpretation, DisputeRuleInterpretation)
    body = _short_digest(
        DISPUTE_RULE_REFERENCE_NAMESPACE,
        (owner, case, system, rule, str(version), stance.value),
    )
    return f"{DISPUTE_RULE_REFERENCE_ID_PREFIX}{body}"


def dispute_authority_reference_id(
    owner_id: str,
    case_ref: str,
    authority_kind: str,
    reference_id: str,
) -> str:
    """Mint one owner-local authority reference id from an existing belief."""

    owner = _require_text(owner_id, "dispute_invalid_owner")
    case = _require_digest(case_ref)
    authority = _require_enum(authority_kind, DisputeAuthorityKind)
    reference = _require_reference(reference_id)
    body = _short_digest(
        DISPUTE_AUTHORITY_REFERENCE_NAMESPACE,
        (owner, case, authority.value, reference),
    )
    return f"{DISPUTE_AUTHORITY_REFERENCE_ID_PREFIX}{body}"


def dispute_mediation_reference_id(
    owner_id: str,
    case_ref: str,
    mediation_case_ref: str,
    recommendation_ref: str,
) -> str:
    """Mint one owner-local link to the owner's own mediation ledger."""

    owner = _require_text(owner_id, "dispute_invalid_owner")
    case = _require_digest(case_ref)
    mediation_case = _require_reference(mediation_case_ref)
    recommendation = _require_reference(recommendation_ref)
    body = _short_digest(
        DISPUTE_MEDIATION_REFERENCE_NAMESPACE,
        (owner, case, mediation_case, recommendation),
    )
    return f"{DISPUTE_MEDIATION_REFERENCE_ID_PREFIX}{body}"


def dispute_resolution_ref(case_ref: str, proposer_id: str, terms_digest: str) -> str:
    """Return the portable resolution token carried in speech."""

    case = _require_digest(case_ref)
    proposer = _require_reference(proposer_id)
    terms = _require_digest(terms_digest)
    return _digest(DISPUTE_RESOLUTION_NAMESPACE, (case, proposer, terms))


def dispute_resolution_id(owner_id: str, resolution_ref: str) -> str:
    """Mint one owner-local proposed-resolution id."""

    owner = _require_text(owner_id, "dispute_invalid_owner")
    reference = _require_digest(resolution_ref)
    body = _short_digest(DISPUTE_RESOLUTION_NAMESPACE, (owner, reference))
    return f"{DISPUTE_RESOLUTION_ID_PREFIX}{body}"


def dispute_response_id(
    owner_id: str,
    resolution_ref: str,
    party_id: str,
    kind: str,
    tick: int,
) -> str:
    """Mint one owner-local per-party resolution response id."""

    owner = _require_text(owner_id, "dispute_invalid_owner")
    resolution = _require_digest(resolution_ref)
    party = _require_reference(party_id)
    response_kind = _require_enum(kind, DisputeResolutionResponseKind)
    absolute_tick = _require_tick(tick)
    body = _short_digest(
        DISPUTE_RESPONSE_NAMESPACE,
        (owner, resolution, party, response_kind.value, str(absolute_tick)),
    )
    return f"{DISPUTE_RESPONSE_ID_PREFIX}{body}"


def _require_prefix(value: object, pattern: re.Pattern[str]) -> str:
    if type(value) is not str or pattern.match(value) is None:
        _fail("dispute_invalid_id")
    return value


def require_dispute_case_id(value: object) -> str:
    return _require_prefix(value, _CASE_ID_PATTERN)


def require_dispute_claim_id(value: object) -> str:
    return _require_prefix(value, _CLAIM_ID_PATTERN)


def require_dispute_testimony_id(value: object) -> str:
    return _require_prefix(value, _TESTIMONY_ID_PATTERN)


def require_dispute_evidence_id(value: object) -> str:
    return _require_prefix(value, _EVIDENCE_ID_PATTERN)


def require_dispute_rule_reference_id(value: object) -> str:
    return _require_prefix(value, _RULE_REFERENCE_ID_PATTERN)


def require_dispute_mediation_reference_id(value: object) -> str:
    return _require_prefix(value, _MEDIATION_REFERENCE_ID_PATTERN)


def require_dispute_authority_reference_id(value: object) -> str:
    return _require_prefix(value, _AUTHORITY_REFERENCE_ID_PATTERN)


def require_dispute_resolution_id(value: object) -> str:
    return _require_prefix(value, _RESOLUTION_ID_PATTERN)


def require_dispute_response_id(value: object) -> str:
    return _require_prefix(value, _RESPONSE_ID_PATTERN)


def require_dispute_claim_ref(value: object) -> str:
    return _require_digest(value)


def require_dispute_resolution_ref(value: object) -> str:
    return _require_digest(value)


def require_dispute_case_ref(value: object) -> str:
    return _require_digest(value)


# ---------------------------------------------------------------------------
# Record vocabulary
# ---------------------------------------------------------------------------

_UNIT_QUANTUM: Final[Decimal] = Decimal("0.000001")
_Draft = dict[str, Any]
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
    }
)

DISPUTE_NOTICE_REASONS: Final[frozenset[str]] = frozenset(
    {
        "dispute_party_mismatch",
        "dispute_invalid_frame",
        "dispute_unknown_reference",
        "dispute_truncated",
        "dispute_terms_mismatch",
        "dispute_resolution_requires_prior_tick",
        "dispute_resolution_window_expired",
        "dispute_case_limit",
        "dispute_claim_limit",
        "dispute_testimony_limit",
        "dispute_evidence_limit",
        "dispute_rule_reference_limit",
        "dispute_authority_reference_limit",
        "dispute_mediation_reference_limit",
        "dispute_resolution_limit",
        "dispute_response_limit",
        "dispute_term_limit",
        "dispute_record_limit",
        "dispute_forbidden_field",
    }
)


def _normalize_owner(value: object) -> str:
    if type(value) is AgentId:
        return value.value
    if type(value) is str and value:
        return value
    _fail("dispute_invalid_owner")


def _quantize_unit(value: object, code: str = "dispute_invalid_record") -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(code)
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        _fail(code)
    quantized = Decimal(str(number)).quantize(_UNIT_QUANTUM, rounding=ROUND_HALF_UP)
    return 0.0 if quantized == 0 else float(quantized)


def _require_optional_reference(value: object) -> str | None:
    if value is None:
        return None
    return _require_reference(value)


def _require_ordered_references(
    value: object,
    *,
    code: str = "dispute_invalid_reference",
    max_items: int | None = None,
) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        _fail(code)
    items: list[str] = []
    for item in value:
        reference = _require_reference(item, code)
        if reference not in items:
            items.append(reference)
    ordered = tuple(sorted(items))
    if max_items is not None and len(ordered) > max_items:
        _fail("dispute_party_limit")
    return ordered


def _require_ordered_ids(
    value: object,
    validator: object,
    code: str,
) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        _fail(code)
    validate = validator
    items: list[str] = []
    for item in value:
        checked = validate(item)  # type: ignore[operator]
        if checked in items:
            _fail("dispute_duplicate_id")
        items.append(checked)
    return tuple(sorted(items))


def _validate_notices(value: object) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        _fail("dispute_invalid_record")
    notices: list[str] = []
    for notice in value:
        if type(notice) is not str or notice not in DISPUTE_NOTICE_REASONS:
            _fail("dispute_invalid_record")
        if notice not in notices:
            notices.append(notice)
    if len(notices) > _MAX_NOTICES:
        _fail("dispute_invalid_record")
    return tuple(sorted(notices))


def _validate_span(first_tick: object, last_tick: object) -> tuple[int, int]:
    first = _require_tick(first_tick)
    last = _require_tick(last_tick)
    if last < first:
        _fail("dispute_invalid_tick")
    return first, last


def _reject_forbidden_fields(model: type[object]) -> None:
    if not is_dataclass(model):
        return
    for field in fields(model):
        if field.name in DISPUTE_FORBIDDEN_FIELD_NAMES:
            _fail("dispute_forbidden_field")


def _reject_forbidden_value(value: object, seen: set[int] | None = None) -> None:
    if value is None or isinstance(value, (str, bytes, bool, int, float)):
        return
    visited = set() if seen is None else seen
    identity = id(value)
    if identity in visited:
        return
    visited.add(identity)
    name = type(value).__name__
    if name in _FORBIDDEN_OBJECT_TYPES or (
        name.endswith("Ledger") and name != "DisputeLedger"
    ):
        _fail("dispute_forbidden_field")
    if is_dataclass(value) and not isinstance(value, type):
        for field in fields(value):
            if field.name in DISPUTE_FORBIDDEN_FIELD_NAMES:
                _fail("dispute_forbidden_field")
            _reject_forbidden_value(getattr(value, field.name), visited)
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            _reject_forbidden_value(key, visited)
            _reject_forbidden_value(item, visited)
        return
    if isinstance(value, (tuple, list, set, frozenset)):
        for item in value:
            _reject_forbidden_value(item, visited)
        return
    attributes = getattr(value, "__dict__", None)
    if isinstance(attributes, Mapping):
        for key, item in attributes.items():
            if key in DISPUTE_FORBIDDEN_FIELD_NAMES:
                _fail("dispute_forbidden_field")
            _reject_forbidden_value(item, visited)


def _record_material(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _record_material(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        return {
            str(key): _record_material(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_record_material(item) for item in value]
    return value


def _terms_sort_key(term: DisputeResolutionTerm) -> tuple[object, ...]:
    return (
        term.term_kind.value,
        term.party_id,
        term.counterparty_id,
        term.item_token or "",
        term.service_token or "",
        term.action_token or "",
        term.quantity,
        -1 if term.due_tick is None else term.due_tick,
    )


def dispute_terms_digest(terms: object) -> str:
    """Return the canonical digest over deterministically sorted terms."""

    if isinstance(terms, (str, bytes)) or not isinstance(terms, (tuple, list)):
        _fail("dispute_invalid_reference")
    checked: list[DisputeResolutionTerm] = []
    for term in terms:
        if type(term) is not DisputeResolutionTerm:
            _fail("dispute_invalid_record")
        checked.append(term)
    ordered = sorted(checked, key=_terms_sort_key)
    material = [_record_material(term) for term in ordered]
    payload = json.dumps(
        material, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DisputeCase:
    """One owner's belief about a dispute thread. No verdict or truth field."""

    case_id: str
    owner_id: str
    case_ref: str
    kind: DisputeKind
    subject_kind: DisputeSubjectKind
    subject_token: str
    subject_digest: str
    context_key: str
    party_ids: tuple[str, ...]
    claimant_ids: tuple[str, ...]
    respondent_ids: tuple[str, ...]
    status: DisputeStatus
    first_tick: int
    last_tick: int
    window_first_tick: int
    window_last_tick: int
    origin_ref: str | None = None
    uncertainty: float = 0.0
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        owner = _normalize_owner(self.owner_id)
        object.__setattr__(self, "owner_id", owner)
        case_id = require_dispute_case_id(self.case_id)
        case_ref = require_dispute_case_ref(self.case_ref)
        if case_id != dispute_case_id(owner, case_ref):
            _fail("dispute_invalid_id")
        object.__setattr__(self, "case_id", case_id)
        object.__setattr__(self, "case_ref", case_ref)
        object.__setattr__(self, "kind", _require_enum(self.kind, DisputeKind))
        object.__setattr__(
            self,
            "subject_kind",
            _require_enum(self.subject_kind, DisputeSubjectKind),
        )
        subject_token = _require_reference(self.subject_token)
        object.__setattr__(self, "subject_token", subject_token)
        subject_digest = _require_digest(self.subject_digest)
        if subject_digest != dispute_subject_digest(self.subject_kind, subject_token):
            _fail("dispute_invalid_subject")
        object.__setattr__(self, "subject_digest", subject_digest)
        object.__setattr__(self, "context_key", _require_reference(self.context_key))
        parties = _require_ordered_references(
            self.party_ids,
            code="dispute_party_limit",
            max_items=_DEFAULT_POLICY.max_parties,
        )
        if owner not in parties or parties.count(owner) != 1:
            _fail("dispute_owner_mismatch")
        object.__setattr__(self, "party_ids", parties)
        claimants = _require_ordered_references(self.claimant_ids)
        respondents = _require_ordered_references(self.respondent_ids)
        if not set(claimants) <= set(parties) or not set(respondents) <= set(parties):
            _fail("dispute_unknown_reference")
        object.__setattr__(self, "claimant_ids", claimants)
        object.__setattr__(self, "respondent_ids", respondents)
        object.__setattr__(self, "status", _require_enum(self.status, DisputeStatus))
        first, last = _validate_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        window_first = _require_tick(self.window_first_tick)
        window_last = _require_tick(self.window_last_tick)
        if window_last < window_first:
            _fail("dispute_invalid_tick")
        object.__setattr__(self, "window_first_tick", window_first)
        object.__setattr__(self, "window_last_tick", window_last)
        object.__setattr__(
            self, "origin_ref", _require_optional_reference(self.origin_ref)
        )
        object.__setattr__(self, "uncertainty", _quantize_unit(self.uncertainty))
        object.__setattr__(self, "notices", _validate_notices(self.notices))

    @property
    def supports_tick(self) -> bool:
        return self.window_first_tick <= self.last_tick <= self.window_last_tick


@dataclass(frozen=True, slots=True)
class DisputeClaim:
    """One attributed claim or counterclaim. Opposing claims coexist."""

    claim_id: str
    claim_ref: str
    case_ref: str
    owner_id: str
    claimant_id: str
    respondent_id: str
    role: DisputeClaimRole
    claim_kind: DisputeClaimKind
    polarity: DisputeClaimPolarity
    subject_kind: DisputeSubjectKind
    subject_token: str
    subject_digest: str
    action_token: str | None
    item_token: str | None
    quantity: int
    terms_digest: str | None
    counters_claim_ref: str | None
    rule_reference_token: str | None
    evidence_ids: tuple[str, ...]
    provenance: DisputeProvenance
    confidence: float
    first_tick: int
    last_tick: int
    active: bool = True
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        owner = _normalize_owner(self.owner_id)
        object.__setattr__(self, "owner_id", owner)
        claim_ref = require_dispute_claim_ref(self.claim_ref)
        case_ref = require_dispute_case_ref(self.case_ref)
        claim_id = require_dispute_claim_id(self.claim_id)
        if claim_id != dispute_claim_id(owner, claim_ref):
            _fail("dispute_invalid_id")
        object.__setattr__(self, "claim_id", claim_id)
        object.__setattr__(self, "claim_ref", claim_ref)
        object.__setattr__(self, "case_ref", case_ref)
        object.__setattr__(self, "claimant_id", _require_reference(self.claimant_id))
        object.__setattr__(
            self, "respondent_id", _require_reference(self.respondent_id)
        )
        object.__setattr__(self, "role", _require_enum(self.role, DisputeClaimRole))
        object.__setattr__(
            self, "claim_kind", _require_enum(self.claim_kind, DisputeClaimKind)
        )
        object.__setattr__(
            self,
            "polarity",
            _require_enum(self.polarity, DisputeClaimPolarity),
        )
        object.__setattr__(
            self,
            "subject_kind",
            _require_enum(self.subject_kind, DisputeSubjectKind),
        )
        subject_token = _require_reference(self.subject_token)
        object.__setattr__(self, "subject_token", subject_token)
        subject_digest = _require_digest(self.subject_digest)
        if subject_digest != dispute_subject_digest(self.subject_kind, subject_token):
            _fail("dispute_invalid_subject")
        object.__setattr__(self, "subject_digest", subject_digest)
        object.__setattr__(
            self, "action_token", _require_optional_reference(self.action_token)
        )
        object.__setattr__(
            self, "item_token", _require_optional_reference(self.item_token)
        )
        quantity = _require_ordinal(self.quantity)
        if quantity > 3:
            _fail("dispute_invalid_ordinal")
        object.__setattr__(self, "quantity", quantity)
        if self.terms_digest is not None:
            object.__setattr__(self, "terms_digest", _require_digest(self.terms_digest))
        if self.counters_claim_ref is not None:
            object.__setattr__(
                self,
                "counters_claim_ref",
                require_dispute_claim_ref(self.counters_claim_ref),
            )
        object.__setattr__(
            self,
            "rule_reference_token",
            _require_optional_reference(self.rule_reference_token),
        )
        object.__setattr__(
            self,
            "evidence_ids",
            _require_ordered_ids(
                self.evidence_ids,
                require_dispute_evidence_id,
                "dispute_invalid_id",
            ),
        )
        object.__setattr__(
            self, "provenance", _require_enum(self.provenance, DisputeProvenance)
        )
        object.__setattr__(self, "confidence", _quantize_unit(self.confidence))
        first, last = _validate_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        if type(self.active) is not bool:
            _fail("dispute_invalid_record")
        if self.role is DisputeClaimRole.COUNTERCLAIM and (
            self.counters_claim_ref is None
        ):
            _fail("dispute_unknown_reference")
        object.__setattr__(self, "notices", _validate_notices(self.notices))

    @property
    def is_counterclaim(self) -> bool:
        return self.role is DisputeClaimRole.COUNTERCLAIM


@dataclass(frozen=True, slots=True)
class DisputeTestimony:
    """One attributed account. Shared roots are not independent corroboration."""

    testimony_id: str
    case_ref: str
    claim_ref: str
    owner_id: str
    speaker_id: str
    channel: DisputeTestimonyChannel
    root_ref: str
    independently_evidenced: bool
    evidence_id: str | None
    tick: int
    provenance: DisputeProvenance
    active: bool = True

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        owner = _normalize_owner(self.owner_id)
        object.__setattr__(self, "owner_id", owner)
        case_ref = require_dispute_case_ref(self.case_ref)
        claim_ref = require_dispute_claim_ref(self.claim_ref)
        testimony_id = require_dispute_testimony_id(self.testimony_id)
        speaker = _require_reference(self.speaker_id)
        channel = _require_enum(self.channel, DisputeTestimonyChannel)
        root = _require_reference(self.root_ref)
        tick = _require_tick(self.tick)
        if testimony_id != dispute_testimony_id(
            owner, case_ref, claim_ref, speaker, channel, root, tick
        ):
            _fail("dispute_invalid_id")
        object.__setattr__(self, "testimony_id", testimony_id)
        object.__setattr__(self, "case_ref", case_ref)
        object.__setattr__(self, "claim_ref", claim_ref)
        object.__setattr__(self, "speaker_id", speaker)
        object.__setattr__(self, "channel", channel)
        object.__setattr__(self, "root_ref", root)
        if type(self.independently_evidenced) is not bool:
            _fail("dispute_invalid_record")
        if (
            channel is DisputeTestimonyChannel.COMMUNICATED
            and self.independently_evidenced
        ):
            _fail("dispute_invalid_record")
        if self.evidence_id is not None:
            object.__setattr__(
                self,
                "evidence_id",
                require_dispute_evidence_id(self.evidence_id),
            )
        object.__setattr__(self, "tick", tick)
        object.__setattr__(
            self, "provenance", _require_enum(self.provenance, DisputeProvenance)
        )
        if type(self.active) is not bool:
            _fail("dispute_invalid_record")


@dataclass(frozen=True, slots=True)
class DisputeEvidence:
    """One typed evidence anchor. Never carries a world body or event store."""

    evidence_id: str
    case_ref: str
    claim_ref: str
    owner_id: str
    channel: DisputeEvidenceChannel
    reference_kind: DisputeEvidenceReferenceKind
    reference_id: str
    tick: int
    actor_id: str | None
    independently_evidenced: bool
    provenance: DisputeProvenance
    active: bool = True

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        owner = _normalize_owner(self.owner_id)
        object.__setattr__(self, "owner_id", owner)
        object.__setattr__(
            self, "evidence_id", require_dispute_evidence_id(self.evidence_id)
        )
        object.__setattr__(self, "case_ref", require_dispute_case_ref(self.case_ref))
        object.__setattr__(self, "claim_ref", require_dispute_claim_ref(self.claim_ref))
        object.__setattr__(
            self,
            "channel",
            _require_enum(self.channel, DisputeEvidenceChannel),
        )
        object.__setattr__(
            self,
            "reference_kind",
            _require_enum(self.reference_kind, DisputeEvidenceReferenceKind),
        )
        object.__setattr__(self, "reference_id", _require_reference(self.reference_id))
        object.__setattr__(self, "tick", _require_tick(self.tick))
        object.__setattr__(self, "actor_id", _require_optional_reference(self.actor_id))
        if type(self.independently_evidenced) is not bool:
            _fail("dispute_invalid_record")
        object.__setattr__(
            self, "provenance", _require_enum(self.provenance, DisputeProvenance)
        )
        if type(self.active) is not bool:
            _fail("dispute_invalid_record")


@dataclass(frozen=True, slots=True)
class DisputeRuleReference:
    """One claim's reference to the owner's own formal-rule ledger."""

    rule_reference_id: str
    case_ref: str
    claim_ref: str
    owner_id: str
    system_ref: str
    rule_id: str
    version_number: int
    constraint_kind: str
    scope_digest: str | None
    applicability: DisputeRuleApplicability
    interpretation: DisputeRuleInterpretation
    status: DisputeRuleReferenceStatus
    provenance: DisputeProvenance
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        owner = _normalize_owner(self.owner_id)
        object.__setattr__(self, "owner_id", owner)
        object.__setattr__(
            self,
            "rule_reference_id",
            require_dispute_rule_reference_id(self.rule_reference_id),
        )
        case_ref = require_dispute_case_ref(self.case_ref)
        claim_ref = require_dispute_claim_ref(self.claim_ref)
        object.__setattr__(self, "case_ref", case_ref)
        object.__setattr__(self, "claim_ref", claim_ref)
        object.__setattr__(self, "system_ref", _require_reference(self.system_ref))
        object.__setattr__(self, "rule_id", _require_reference(self.rule_id))
        number = _require_ordinal(self.version_number)
        if number < 1:
            _fail("dispute_invalid_ordinal")
        object.__setattr__(self, "version_number", number)
        object.__setattr__(
            self, "constraint_kind", _require_reference(self.constraint_kind)
        )
        if self.scope_digest is not None:
            object.__setattr__(self, "scope_digest", _require_digest(self.scope_digest))
        applicability = _require_enum(self.applicability, DisputeRuleApplicability)
        interpretation = _require_enum(self.interpretation, DisputeRuleInterpretation)
        object.__setattr__(self, "applicability", applicability)
        object.__setattr__(self, "interpretation", interpretation)
        if self.rule_reference_id != dispute_rule_reference_id(
            owner,
            case_ref,
            self.system_ref,
            self.rule_id,
            number,
            interpretation,
        ):
            _fail("dispute_invalid_id")
        object.__setattr__(
            self,
            "status",
            _require_enum(self.status, DisputeRuleReferenceStatus),
        )
        object.__setattr__(
            self, "provenance", _require_enum(self.provenance, DisputeProvenance)
        )
        first, last = _validate_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)


@dataclass(frozen=True, slots=True)
class DisputeAuthorityReference:
    """One owner belief citing an existing institutional role or record."""

    authority_reference_id: str
    case_ref: str
    owner_id: str
    authority_kind: DisputeAuthorityKind
    reference_id: str
    strength: float
    uncertainty: float
    provenance: DisputeProvenance
    dissenting: bool
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        owner = _normalize_owner(self.owner_id)
        object.__setattr__(self, "owner_id", owner)
        object.__setattr__(
            self,
            "authority_reference_id",
            require_dispute_authority_reference_id(self.authority_reference_id),
        )
        case_ref = require_dispute_case_ref(self.case_ref)
        object.__setattr__(self, "case_ref", case_ref)
        authority_kind = _require_enum(self.authority_kind, DisputeAuthorityKind)
        object.__setattr__(self, "authority_kind", authority_kind)
        reference = _require_reference(self.reference_id)
        object.__setattr__(self, "reference_id", reference)
        if self.authority_reference_id != dispute_authority_reference_id(
            owner, case_ref, authority_kind, reference
        ):
            _fail("dispute_invalid_id")
        object.__setattr__(self, "strength", _quantize_unit(self.strength))
        object.__setattr__(self, "uncertainty", _quantize_unit(self.uncertainty))
        object.__setattr__(
            self, "provenance", _require_enum(self.provenance, DisputeProvenance)
        )
        if type(self.dissenting) is not bool:
            _fail("dispute_invalid_record")
        first, last = _validate_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)


@dataclass(frozen=True, slots=True)
class DisputeMediationReference:
    """One link to the owner's own mediation ledger. Never a binding decision."""

    mediation_reference_id: str
    case_ref: str
    owner_id: str
    mediation_case_ref: str
    recommendation_ref: str | None
    response_ref: str | None
    outcome_ref: str | None
    link_status: DisputeMediationLinkStatus
    provenance: DisputeProvenance
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        owner = _normalize_owner(self.owner_id)
        object.__setattr__(self, "owner_id", owner)
        object.__setattr__(
            self,
            "mediation_reference_id",
            require_dispute_mediation_reference_id(self.mediation_reference_id),
        )
        case_ref = require_dispute_case_ref(self.case_ref)
        mediation_case_ref = _require_reference(self.mediation_case_ref)
        recommendation_ref = _require_optional_reference(self.recommendation_ref)
        object.__setattr__(self, "case_ref", case_ref)
        object.__setattr__(self, "mediation_case_ref", mediation_case_ref)
        object.__setattr__(self, "recommendation_ref", recommendation_ref)
        object.__setattr__(
            self, "response_ref", _require_optional_reference(self.response_ref)
        )
        object.__setattr__(
            self, "outcome_ref", _require_optional_reference(self.outcome_ref)
        )
        if self.mediation_reference_id != dispute_mediation_reference_id(
            owner,
            case_ref,
            mediation_case_ref,
            "none" if recommendation_ref is None else recommendation_ref,
        ):
            _fail("dispute_invalid_id")
        object.__setattr__(
            self,
            "link_status",
            _require_enum(self.link_status, DisputeMediationLinkStatus),
        )
        object.__setattr__(
            self, "provenance", _require_enum(self.provenance, DisputeProvenance)
        )
        first, last = _validate_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)


@dataclass(frozen=True, slots=True)
class DisputeResolutionTerm:
    """One proposed term. It never executes and never forces a transfer."""

    term_kind: DisputeResolutionTermKind
    party_id: str
    counterparty_id: str
    item_token: str | None = None
    service_token: str | None = None
    action_token: str | None = None
    quantity: int = 0
    due_tick: int | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self,
            "term_kind",
            _require_enum(self.term_kind, DisputeResolutionTermKind),
        )
        object.__setattr__(self, "party_id", _require_reference(self.party_id))
        object.__setattr__(
            self, "counterparty_id", _require_reference(self.counterparty_id)
        )
        object.__setattr__(
            self, "item_token", _require_optional_reference(self.item_token)
        )
        object.__setattr__(
            self,
            "service_token",
            _require_optional_reference(self.service_token),
        )
        object.__setattr__(
            self, "action_token", _require_optional_reference(self.action_token)
        )
        quantity = _require_ordinal(self.quantity)
        if quantity > 3:
            _fail("dispute_invalid_ordinal")
        object.__setattr__(self, "quantity", quantity)
        if self.due_tick is not None:
            object.__setattr__(self, "due_tick", _require_tick(self.due_tick))


@dataclass(frozen=True, slots=True)
class DisputeResolution:
    """One owner belief about a proposed resolution. Never binding."""

    resolution_id: str
    resolution_ref: str
    case_ref: str
    owner_id: str
    proposer_id: str
    source: DisputeResolutionSource
    terms: tuple[DisputeResolutionTerm, ...]
    terms_digest: str
    status: DisputeResolutionStatus
    first_tick: int
    last_tick: int
    expires_tick: int | None
    provenance: DisputeProvenance
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        owner = _normalize_owner(self.owner_id)
        object.__setattr__(self, "owner_id", owner)
        resolution_ref = require_dispute_resolution_ref(self.resolution_ref)
        case_ref = require_dispute_case_ref(self.case_ref)
        resolution_id = require_dispute_resolution_id(self.resolution_id)
        if resolution_id != dispute_resolution_id(owner, resolution_ref):
            _fail("dispute_invalid_id")
        object.__setattr__(self, "resolution_id", resolution_id)
        object.__setattr__(self, "resolution_ref", resolution_ref)
        object.__setattr__(self, "case_ref", case_ref)
        object.__setattr__(self, "proposer_id", _require_reference(self.proposer_id))
        object.__setattr__(
            self, "source", _require_enum(self.source, DisputeResolutionSource)
        )
        if isinstance(self.terms, (str, bytes)) or not isinstance(
            self.terms, (tuple, list)
        ):
            _fail("dispute_invalid_record")
        terms: list[DisputeResolutionTerm] = []
        for term in self.terms:
            if type(term) is not DisputeResolutionTerm:
                _fail("dispute_invalid_record")
            terms.append(term)
        ordered = tuple(sorted(terms, key=_terms_sort_key))
        if len(ordered) > _DEFAULT_POLICY.max_terms_per_resolution:
            _fail("dispute_term_limit")
        object.__setattr__(self, "terms", ordered)
        terms_digest = _require_digest(self.terms_digest)
        if terms_digest != dispute_terms_digest(ordered):
            _fail("dispute_invalid_digest")
        object.__setattr__(self, "terms_digest", terms_digest)
        if resolution_ref != dispute_resolution_ref(
            case_ref, self.proposer_id, terms_digest
        ):
            _fail("dispute_invalid_id")
        object.__setattr__(
            self,
            "status",
            _require_enum(self.status, DisputeResolutionStatus),
        )
        first, last = _validate_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        if self.expires_tick is not None:
            object.__setattr__(self, "expires_tick", _require_tick(self.expires_tick))
        object.__setattr__(
            self, "provenance", _require_enum(self.provenance, DisputeProvenance)
        )
        object.__setattr__(self, "notices", _validate_notices(self.notices))

    @property
    def is_open(self) -> bool:
        return self.status in {
            DisputeResolutionStatus.PROPOSED,
            DisputeResolutionStatus.PARTIALLY_ACCEPTED,
        }


@dataclass(frozen=True, slots=True)
class DisputeResolutionResponse:
    """One party's declaration about a proposed resolution. Not binding."""

    response_id: str
    resolution_id: str
    resolution_ref: str
    case_ref: str
    owner_id: str
    party_id: str
    kind: DisputeResolutionResponseKind
    tick: int
    terms_digest: str
    active: bool
    provenance: DisputeProvenance
    counter_resolution_ref: str | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        owner = _normalize_owner(self.owner_id)
        object.__setattr__(self, "owner_id", owner)
        object.__setattr__(
            self, "response_id", require_dispute_response_id(self.response_id)
        )
        object.__setattr__(
            self, "resolution_id", require_dispute_resolution_id(self.resolution_id)
        )
        resolution_ref = require_dispute_resolution_ref(self.resolution_ref)
        case_ref = require_dispute_case_ref(self.case_ref)
        party_id = _require_reference(self.party_id)
        kind = _require_enum(self.kind, DisputeResolutionResponseKind)
        tick = _require_tick(self.tick)
        if self.response_id != dispute_response_id(
            owner, resolution_ref, party_id, kind, tick
        ):
            _fail("dispute_invalid_id")
        object.__setattr__(self, "resolution_ref", resolution_ref)
        object.__setattr__(self, "case_ref", case_ref)
        object.__setattr__(self, "party_id", party_id)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "tick", tick)
        object.__setattr__(self, "terms_digest", _require_digest(self.terms_digest))
        if type(self.active) is not bool:
            _fail("dispute_invalid_record")
        object.__setattr__(
            self, "provenance", _require_enum(self.provenance, DisputeProvenance)
        )
        if self.counter_resolution_ref is not None:
            object.__setattr__(
                self,
                "counter_resolution_ref",
                require_dispute_resolution_ref(self.counter_resolution_ref),
            )


def _ordered_records(value: object) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        _fail("dispute_invalid_ledger")
    return tuple(value)


@dataclass(frozen=True, slots=True)
class DisputeLedger:
    """One owner's dispute beliefs. ``None`` means the mode is off."""

    owner_id: str
    cases: tuple[DisputeCase, ...] = ()
    claims: tuple[DisputeClaim, ...] = ()
    testimony: tuple[DisputeTestimony, ...] = ()
    evidence: tuple[DisputeEvidence, ...] = ()
    rule_references: tuple[DisputeRuleReference, ...] = ()
    authority_references: tuple[DisputeAuthorityReference, ...] = ()
    mediation_references: tuple[DisputeMediationReference, ...] = ()
    resolutions: tuple[DisputeResolution, ...] = ()
    resolution_responses: tuple[DisputeResolutionResponse, ...] = ()
    notices: tuple[str, ...] = ()
    policy_version: str = DISPUTE_POLICY_VERSION
    first_observed_tick: int | None = None
    last_observed_tick: int | None = None
    observation_count: int = 0
    pruned_case_count: int = 0
    pruned_claim_count: int = 0
    pruned_testimony_count: int = 0
    pruned_evidence_count: int = 0
    pruned_resolution_count: int = 0
    pruned_reference_count: int = 0

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        owner = _normalize_owner(self.owner_id)
        object.__setattr__(self, "owner_id", owner)
        if self.policy_version != DISPUTE_POLICY_VERSION:
            _fail("dispute_policy_mismatch")
        cases = _ordered_records(self.cases)
        claims = _ordered_records(self.claims)
        testimony = _ordered_records(self.testimony)
        evidence = _ordered_records(self.evidence)
        rule_references = _ordered_records(self.rule_references)
        authority_references = _ordered_records(self.authority_references)
        mediation_references = _ordered_records(self.mediation_references)
        resolutions = _ordered_records(self.resolutions)
        responses = _ordered_records(self.resolution_responses)
        for collection, model, _code in (
            (cases, DisputeCase, "dispute_case_limit"),
            (claims, DisputeClaim, "dispute_claim_limit"),
            (testimony, DisputeTestimony, "dispute_testimony_limit"),
            (evidence, DisputeEvidence, "dispute_evidence_limit"),
            (rule_references, DisputeRuleReference, "dispute_rule_reference_limit"),
            (
                authority_references,
                DisputeAuthorityReference,
                "dispute_authority_reference_limit",
            ),
            (
                mediation_references,
                DisputeMediationReference,
                "dispute_mediation_reference_limit",
            ),
            (resolutions, DisputeResolution, "dispute_resolution_limit"),
            (responses, DisputeResolutionResponse, "dispute_response_limit"),
        ):
            seen: set[str] = set()
            for row in collection:
                _reject_forbidden_value(row)
                if type(row) is not model:
                    _fail("dispute_invalid_record")
                identifier = getattr(row, _ID_FIELD_BY_MODEL[model])
                if identifier in seen:
                    _fail("dispute_duplicate_id")
                seen.add(identifier)
                if row.owner_id != owner:
                    _fail("dispute_owner_mismatch")

        cases_by_ref = {case.case_ref: case for case in cases}
        claims_by_ref = {claim.claim_ref: claim for claim in claims}
        evidence_by_id = {row.evidence_id: row for row in evidence}
        resolutions_by_ref = {row.resolution_ref: row for row in resolutions}

        for case in cases:
            _validate_case(case)
        for claim in claims:
            case = cases_by_ref.get(claim.case_ref)
            if case is None:
                _fail("dispute_unknown_reference")
            if claim.claimant_id not in case.party_ids:
                _fail("dispute_unknown_reference")
            if claim.respondent_id not in case.party_ids:
                _fail("dispute_unknown_reference")
            if claim.role is DisputeClaimRole.COUNTERCLAIM:
                countered = claims_by_ref.get(claim.counters_claim_ref or "")
                if countered is None:
                    _fail("dispute_unknown_reference")
                if countered.claimant_id == claim.claimant_id:
                    _fail("dispute_unknown_reference")
            for evidence_id in claim.evidence_ids:
                if evidence_id not in evidence_by_id:
                    _fail("dispute_unknown_reference")
        for row in testimony:
            claim = claims_by_ref.get(row.claim_ref)
            if claim is None or claim.case_ref != row.case_ref:
                _fail("dispute_unknown_reference")
            if row.evidence_id is not None and row.evidence_id not in evidence_by_id:
                _fail("dispute_unknown_reference")
        for row in evidence:
            claim = claims_by_ref.get(row.claim_ref)
            if claim is None or claim.case_ref != row.case_ref:
                _fail("dispute_unknown_reference")
        for row in rule_references:
            claim = claims_by_ref.get(row.claim_ref)
            if claim is None or claim.case_ref != row.case_ref:
                _fail("dispute_unknown_reference")
        for row in authority_references:
            if row.case_ref not in cases_by_ref:
                _fail("dispute_unknown_reference")
        for row in mediation_references:
            if row.case_ref not in cases_by_ref:
                _fail("dispute_unknown_reference")
        for resolution in resolutions:
            case = cases_by_ref.get(resolution.case_ref)
            if case is None:
                _fail("dispute_unknown_reference")
            if resolution.proposer_id not in case.party_ids:
                _fail("dispute_unknown_reference")
            for term in resolution.terms:
                if (
                    term.party_id not in case.party_ids
                    or term.counterparty_id not in case.party_ids
                ):
                    _fail("dispute_unknown_reference")
        active_by_party: dict[tuple[str, str], int] = {}
        for response in responses:
            resolution = resolutions_by_ref.get(response.resolution_ref)
            if resolution is None:
                _fail("dispute_unknown_reference")
            if response.resolution_id != resolution.resolution_id:
                _fail("dispute_unknown_reference")
            if response.case_ref != resolution.case_ref:
                _fail("dispute_unknown_reference")
            if response.terms_digest != resolution.terms_digest:
                _fail("dispute_invalid_digest")
            case = cases_by_ref[resolution.case_ref]
            if response.party_id not in case.party_ids:
                _fail("dispute_unknown_reference")
            if response.active:
                key = (response.resolution_ref, response.party_id)
                active_by_party[key] = active_by_party.get(key, 0) + 1
                if active_by_party[key] > 1:
                    _fail("dispute_invalid_ledger")
            if (
                response.kind is DisputeResolutionResponseKind.COUNTERPROPOSE
                and response.counter_resolution_ref is None
            ):
                _fail("dispute_unknown_reference")
            if (
                response.counter_resolution_ref is not None
                and response.counter_resolution_ref not in resolutions_by_ref
            ):
                _fail("dispute_unknown_reference")

        for value in (*cases, *claims, *testimony, *evidence, *resolutions, *responses):
            _reject_forbidden_value(value)

        first = self.first_observed_tick
        last = self.last_observed_tick
        if (first is None) != (last is None):
            _fail("dispute_invalid_tick")
        if first is not None:
            first_tick = _require_tick(first)
            last_tick = _require_tick(last)
            if last_tick < first_tick:
                _fail("dispute_invalid_tick")
            object.__setattr__(self, "first_observed_tick", first_tick)
            object.__setattr__(self, "last_observed_tick", last_tick)
        if (
            isinstance(self.observation_count, bool)
            or type(self.observation_count) is not int
            or self.observation_count < 0
        ):
            _fail("dispute_invalid_record")
        for name in (
            "pruned_case_count",
            "pruned_claim_count",
            "pruned_testimony_count",
            "pruned_evidence_count",
            "pruned_resolution_count",
            "pruned_reference_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                _fail("dispute_invalid_record")

        object.__setattr__(
            self,
            "cases",
            tuple(sorted(cases, key=lambda row: (row.first_tick, row.case_id))),
        )
        object.__setattr__(
            self,
            "claims",
            tuple(sorted(claims, key=lambda row: (row.first_tick, row.claim_id))),
        )
        object.__setattr__(
            self,
            "testimony",
            tuple(sorted(testimony, key=lambda row: (row.tick, row.testimony_id))),
        )
        object.__setattr__(
            self,
            "evidence",
            tuple(sorted(evidence, key=lambda row: (row.tick, row.evidence_id))),
        )
        object.__setattr__(
            self,
            "rule_references",
            tuple(sorted(rule_references, key=lambda row: row.rule_reference_id)),
        )
        object.__setattr__(
            self,
            "authority_references",
            tuple(
                sorted(
                    authority_references,
                    key=lambda row: row.authority_reference_id,
                )
            ),
        )
        object.__setattr__(
            self,
            "mediation_references",
            tuple(
                sorted(
                    mediation_references,
                    key=lambda row: row.mediation_reference_id,
                )
            ),
        )
        object.__setattr__(
            self,
            "resolutions",
            tuple(
                sorted(resolutions, key=lambda row: (row.first_tick, row.resolution_id))
            ),
        )
        object.__setattr__(
            self,
            "resolution_responses",
            tuple(sorted(responses, key=lambda row: (row.tick, row.response_id))),
        )
        object.__setattr__(self, "notices", _validate_notices(self.notices))
        _LOG.debug(
            "dispute_ledger_validated owner_id=%s cases=%s claims=%s evidence=%s "
            "resolutions=%s",
            owner,
            len(cases),
            len(claims),
            len(evidence),
            len(resolutions),
        )

    @property
    def enabled(self) -> bool:
        return True

    @property
    def has_content(self) -> bool:
        return bool(
            self.cases
            or self.claims
            or self.testimony
            or self.evidence
            or self.rule_references
            or self.authority_references
            or self.mediation_references
            or self.resolutions
            or self.resolution_responses
        )

    @property
    def coverage(self) -> str:
        if any(
            (
                self.pruned_case_count,
                self.pruned_claim_count,
                self.pruned_testimony_count,
                self.pruned_evidence_count,
                self.pruned_resolution_count,
                self.pruned_reference_count,
            )
        ):
            return "partial"
        for row in (*self.cases, *self.claims, *self.resolutions):
            if "dispute_truncated" in cast(Any, row).notices:
                return "partial"
        return "complete"

    @property
    def open_cases(self) -> tuple[DisputeCase, ...]:
        return tuple(
            case
            for case in self.cases
            if case.status
            in {
                DisputeStatus.OPEN,
                DisputeStatus.EVIDENCE_GATHERING,
                DisputeStatus.RULE_CITED,
                DisputeStatus.MEDIATION_REFERENCED,
                DisputeStatus.RESOLUTION_PROPOSED,
                DisputeStatus.CONTESTED,
                DisputeStatus.REOPENED,
            }
        )

    @property
    def counterclaims(self) -> tuple[DisputeClaim, ...]:
        return tuple(
            claim
            for claim in self.claims
            if claim.role is DisputeClaimRole.COUNTERCLAIM
        )


_ID_FIELD_BY_MODEL: Final[Mapping[type[object], str]] = MappingProxyType(
    {
        DisputeCase: "case_id",
        DisputeClaim: "claim_id",
        DisputeTestimony: "testimony_id",
        DisputeEvidence: "evidence_id",
        DisputeRuleReference: "rule_reference_id",
        DisputeAuthorityReference: "authority_reference_id",
        DisputeMediationReference: "mediation_reference_id",
        DisputeResolution: "resolution_id",
        DisputeResolutionResponse: "response_id",
    }
)


def _validate_case(case: DisputeCase) -> None:
    if not case.party_ids:
        _fail("dispute_party_limit")
    if len(case.party_ids) > _DEFAULT_POLICY.max_parties:
        _fail("dispute_party_limit")
    if case.window_last_tick < case.window_first_tick:
        _fail("dispute_invalid_tick")


def empty_dispute_ledger(
    owner_id: str | AgentId, policy: DisputePolicy | None = None
) -> DisputeLedger:
    """Return an enabled-but-empty ledger for one owner."""

    require_dispute_policy(policy)
    return DisputeLedger(owner_id=_normalize_owner(owner_id))


def require_owner_disputes(
    value: object | None,
    owner_id: object,
    *,
    field_name: str,
) -> DisputeLedger | None:
    """Reject a foreign or mistyped dispute ledger. ``None`` passes."""

    if value is None:
        return None
    owner = _normalize_owner(owner_id)
    if type(value) is not DisputeLedger:
        _LOG.warning("dispute_carry_rejected field=%s reason=invalid_type", field_name)
        raise TypeError(f"{field_name} must be DisputeLedger")
    if value.owner_id != owner:
        _LOG.error(
            "dispute_validation_failed field=%s reason_code=owner_mismatch",
            field_name,
        )
        _fail("dispute_owner_mismatch")
    return value


def dispute_ledger_digest(ledger: DisputeLedger) -> str:
    """Return a canonical digest over sorted, bounded ledger records."""

    if type(ledger) is not DisputeLedger:
        raise TypeError("ledger must be DisputeLedger")
    payload = json.dumps(
        _record_material(ledger),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _prune_notice(
    notices: list[str], counts: dict[str, int], name: str, amount: int
) -> None:
    if amount <= 0:
        return
    counts[name] = counts.get(name, 0) + amount
    if "dispute_truncated" not in notices:
        notices.append("dispute_truncated")


def enforce_dispute_limits(
    ledger: DisputeLedger, policy: DisputePolicy | None = None
) -> DisputeLedger:
    """Apply every policy cap deterministically, with explicit notices.

    Truncation never silently drops a row: the matching ``pruned_*`` count grows
    and ``dispute_truncated`` is appended to the bounded notice set.
    """

    if type(ledger) is not DisputeLedger:
        raise TypeError("ledger must be DisputeLedger")
    locked = require_dispute_policy(policy)
    notices = list(ledger.notices)
    counts = {
        "pruned_case_count": ledger.pruned_case_count,
        "pruned_claim_count": ledger.pruned_claim_count,
        "pruned_testimony_count": ledger.pruned_testimony_count,
        "pruned_evidence_count": ledger.pruned_evidence_count,
        "pruned_resolution_count": ledger.pruned_resolution_count,
        "pruned_reference_count": ledger.pruned_reference_count,
    }

    cases: list[Any] = list(ledger.cases)
    if len(cases) > locked.max_cases:
        dropped = cases[locked.max_cases :]
        cases = cases[: locked.max_cases]
        _prune_notice(notices, counts, "pruned_case_count", len(dropped))
    kept_case_refs = {case.case_ref for case in cases}

    def keep_case_rows(rows: Sequence[object]) -> list[object]:
        kept: list[Any] = []
        dropped_count = 0
        for row in rows:
            if getattr(row, "case_ref", None) not in kept_case_refs:
                dropped_count += 1
                continue
            kept.append(row)
        _prune_notice(notices, counts, "pruned_reference_count", dropped_count)
        return kept

    claims = [claim for claim in ledger.claims if claim.case_ref in kept_case_refs]
    _prune_notice(
        notices, counts, "pruned_claim_count", len(ledger.claims) - len(claims)
    )
    claims = _cap_per_case(
        claims,
        case_ref=lambda row: row.case_ref,
        cap=locked.max_claims_per_case,
        notices=notices,
        counts=counts,
        name="pruned_claim_count",
    )
    kept_claim_refs = {claim.claim_ref for claim in claims}

    evidence: list[Any] = [
        row
        for row in ledger.evidence
        if row.case_ref in kept_case_refs and row.claim_ref in kept_claim_refs
    ]
    _prune_notice(
        notices, counts, "pruned_evidence_count", len(ledger.evidence) - len(evidence)
    )
    evidence = _cap_per_case(
        evidence,
        case_ref=lambda row: row.claim_ref,
        cap=locked.max_evidence_per_claim,
        notices=notices,
        counts=counts,
        name="pruned_evidence_count",
    )
    kept_evidence_ids = {row.evidence_id for row in evidence}

    testimony: list[Any] = [
        row
        for row in ledger.testimony
        if row.case_ref in kept_case_refs and row.claim_ref in kept_claim_refs
    ]
    _prune_notice(
        notices,
        counts,
        "pruned_testimony_count",
        len(ledger.testimony) - len(testimony),
    )
    testimony = _cap_per_case(
        testimony,
        case_ref=lambda row: row.case_ref,
        cap=locked.max_testimony_per_case,
        notices=notices,
        counts=counts,
        name="pruned_testimony_count",
    )

    rule_references: list[Any] = _cap_per_case(
        [row for row in ledger.rule_references if row.case_ref in kept_case_refs],
        case_ref=lambda row: row.case_ref,
        cap=locked.max_rule_references_per_case,
        notices=notices,
        counts=counts,
        name="pruned_reference_count",
    )
    authority_references: list[Any] = _cap_per_case(
        [row for row in ledger.authority_references if row.case_ref in kept_case_refs],
        case_ref=lambda row: row.case_ref,
        cap=locked.max_authority_references_per_case,
        notices=notices,
        counts=counts,
        name="pruned_reference_count",
    )
    mediation_references: list[Any] = _cap_per_case(
        [row for row in ledger.mediation_references if row.case_ref in kept_case_refs],
        case_ref=lambda row: row.case_ref,
        cap=locked.max_mediation_references_per_case,
        notices=notices,
        counts=counts,
        name="pruned_reference_count",
    )
    _prune_notice(
        notices,
        counts,
        "pruned_reference_count",
        len(ledger.rule_references)
        + len(ledger.authority_references)
        + len(ledger.mediation_references)
        - len(rule_references)
        - len(authority_references)
        - len(mediation_references),
    )

    resolutions: list[Any] = _cap_per_case(
        [row for row in ledger.resolutions if row.case_ref in kept_case_refs],
        case_ref=lambda row: row.case_ref,
        cap=locked.max_resolutions_per_case,
        notices=notices,
        counts=counts,
        name="pruned_resolution_count",
    )
    kept_resolution_refs = {row.resolution_ref for row in resolutions}
    responses: list[Any] = _cap_per_case(
        [
            row
            for row in ledger.resolution_responses
            if row.case_ref in kept_case_refs
            and row.resolution_ref in kept_resolution_refs
        ],
        case_ref=lambda row: row.resolution_ref,
        cap=locked.max_responses_per_resolution,
        notices=notices,
        counts=counts,
        name="pruned_resolution_count",
    )
    _prune_notice(
        notices,
        counts,
        "pruned_resolution_count",
        len(ledger.resolution_responses) - len(responses),
    )

    sanitized_claims: tuple[Any, ...] = tuple(
        replace(
            claim,
            evidence_ids=tuple(
                evidence_id
                for evidence_id in claim.evidence_ids
                if evidence_id in kept_evidence_ids
            ),
        )
        for claim in claims
    )

    total = (
        len(cases)
        + len(sanitized_claims)
        + len(testimony)
        + len(evidence)
        + len(rule_references)
        + len(authority_references)
        + len(mediation_references)
        + len(resolutions)
        + len(responses)
    )
    if total > locked.max_total_records:
        overflow = total - locked.max_total_records
        for collection, name in (
            ("responses", "pruned_resolution_count"),
            ("authority_references", "pruned_reference_count"),
            ("rule_references", "pruned_reference_count"),
            ("mediation_references", "pruned_reference_count"),
            ("testimony", "pruned_testimony_count"),
            ("evidence", "pruned_evidence_count"),
            ("claims", "pruned_claim_count"),
            ("cases", "pruned_case_count"),
        ):
            values: list[Any] = list(
                {
                    "responses": responses,
                    "authority_references": authority_references,
                    "rule_references": rule_references,
                    "mediation_references": mediation_references,
                    "testimony": testimony,
                    "evidence": evidence,
                    "claims": sanitized_claims,
                    "cases": cases,
                }[collection]
            )
            removed = min(overflow, len(values))
            if removed:
                values = values[: len(values) - removed]
                _prune_notice(notices, counts, name, removed)
                overflow -= removed
            if collection == "responses":
                responses = values
            elif collection == "authority_references":
                authority_references = values
            elif collection == "rule_references":
                rule_references = values
            elif collection == "mediation_references":
                mediation_references = values
            elif collection == "testimony":
                testimony = values
            elif collection == "evidence":
                evidence = values
                kept_evidence_ids = {row.evidence_id for row in evidence}
                sanitized_claims = tuple(
                    replace(
                        claim,
                        evidence_ids=tuple(
                            evidence_id
                            for evidence_id in claim.evidence_ids
                            if evidence_id in kept_evidence_ids
                        ),
                    )
                    for claim in sanitized_claims
                )
            elif collection == "claims":
                sanitized_claims = tuple(values)
            else:
                cases = values
            if overflow <= 0:
                break

    _LOG.debug(
        "dispute_limits_enforced owner_id=%s cases=%s claims=%s truncated=%s",
        ledger.owner_id,
        len(cases),
        len(sanitized_claims),
        counts,
    )
    return DisputeLedger(
        owner_id=ledger.owner_id,
        cases=tuple(cases),
        claims=sanitized_claims,
        testimony=tuple(testimony),
        evidence=tuple(evidence),
        rule_references=tuple(rule_references),
        authority_references=tuple(authority_references),
        mediation_references=tuple(mediation_references),
        resolutions=tuple(resolutions),
        resolution_responses=tuple(responses),
        notices=tuple(notices),
        policy_version=ledger.policy_version,
        first_observed_tick=ledger.first_observed_tick,
        last_observed_tick=ledger.last_observed_tick,
        observation_count=ledger.observation_count,
        pruned_case_count=counts["pruned_case_count"],
        pruned_claim_count=counts["pruned_claim_count"],
        pruned_testimony_count=counts["pruned_testimony_count"],
        pruned_evidence_count=counts["pruned_evidence_count"],
        pruned_resolution_count=counts["pruned_resolution_count"],
        pruned_reference_count=counts["pruned_reference_count"],
    )


def _cap_per_case(
    rows: Sequence[Any],
    *,
    case_ref: Callable[[Any], str],
    cap: int,
    notices: list[str],
    counts: dict[str, int],
    name: str,
) -> list[Any]:
    grouped: dict[str, list[Any]] = {}
    getter = case_ref
    for row in rows:
        key = getter(row)
        grouped.setdefault(key, []).append(row)
    kept: list[Any] = []
    for key in sorted(grouped):
        values = grouped[key]
        kept.extend(values[:cap])
        _prune_notice(notices, counts, name, len(values) - min(len(values), cap))
    return kept


# ---------------------------------------------------------------------------
# Owner-scoped collection
# ---------------------------------------------------------------------------

_ACT_ORDER: Final[Mapping[str, int]] = MappingProxyType(
    {
        "claim": 0,
        "counterclaim": 1,
        "testify": 2,
        "cite_evidence": 3,
        "cite_rule": 4,
        "reference_mediation": 5,
        "propose_resolution": 6,
        "accept_resolution": 7,
        "reject_resolution": 8,
        "withdraw_claim": 9,
    }
)


def _act_order(frame: object) -> int:
    act = getattr(frame, "act", None)
    token = getattr(act, "value", "")
    return _ACT_ORDER.get(token, 10)


def _observation_tick(observation: object) -> int:
    return _require_tick(getattr(observation, "tick", None))


def _context_digest(observation: object) -> str:
    world = getattr(getattr(observation, "world_id", None), "value", "none")
    observer = getattr(getattr(observation, "observer_id", None), "value", "none")
    material = f"dispute-context|{world}|{observer}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _token_of(value: object) -> str | None:
    token = getattr(value, "value", value)
    return token if type(token) is str and token else None


def _entity_to_agent(identity: object | None, entity_token: str) -> str:
    if identity is None:
        return entity_token
    if _token_of(getattr(identity, "owner_entity_id", None)) == entity_token:
        return _normalize_owner(getattr(identity, "owner_id", entity_token))
    for binding in getattr(identity, "counterparts", ()) or ():
        if _token_of(getattr(binding, "entity_id", None)) == entity_token:
            return _normalize_owner(getattr(binding, "agent_id", entity_token))
    return entity_token


def _agent_to_entity(identity: object | None, agent_token: str) -> str:
    if identity is None:
        return agent_token
    owner = _normalize_owner(getattr(identity, "owner_id", ""))
    if owner == agent_token:
        return _token_of(getattr(identity, "owner_entity_id", None)) or agent_token
    for binding in getattr(identity, "counterparts", ()) or ():
        if _normalize_owner(getattr(binding, "agent_id", "")) == agent_token:
            return _token_of(getattr(binding, "entity_id", None)) or agent_token
    return agent_token


def _owner_entity_token(identity: object | None, owner: str) -> str:
    if identity is None:
        return owner
    if _normalize_owner(getattr(identity, "owner_id", "")) != owner:
        return owner
    return _token_of(getattr(identity, "owner_entity_id", None)) or owner


def _reject_forbidden_input(value: object, *, owner: str) -> None:
    if value is None:
        return
    stack: list[object] = [value]
    seen: set[int] = set()
    while stack:
        item = stack.pop()
        if item is None or isinstance(item, (str, bytes, bool, int, float)):
            continue
        identity = id(item)
        if identity in seen:
            continue
        seen.add(identity)
        name = type(item).__name__
        if name in _FORBIDDEN_OBJECT_TYPES:
            _fail("dispute_forbidden_input")
        owner_token = _token_of(getattr(item, "owner_id", None))
        if owner_token is not None and owner_token != owner:
            _fail("dispute_forbidden_input")
        if type(item) is DisputeLedger:
            continue
        if is_dataclass(item) and not isinstance(item, type):
            stack.extend(getattr(item, field.name) for field in fields(item))
        elif isinstance(item, Mapping):
            stack.extend(item.keys())
            stack.extend(item.values())
        elif isinstance(item, (tuple, list, set, frozenset)):
            stack.extend(item)


def _empty_draft(prior: DisputeLedger | None) -> _Draft:
    draft: _Draft = {
        "cases": {},
        "claims": {},
        "testimony": {},
        "evidence": {},
        "rule_references": {},
        "authority_references": {},
        "mediation_references": {},
        "resolutions": {},
        "resolution_responses": {},
    }
    if prior is None:
        return draft
    for name in draft:
        for row in getattr(prior, name):
            identifier = getattr(row, _ID_FIELD_BY_MODEL[type(row)])
            draft[name][identifier] = row
    return draft


def _draft_rows(draft: _Draft, name: str) -> tuple[Any, ...]:
    return tuple(draft[name][key] for key in sorted(draft[name]))


def _case_status(
    case: DisputeCase,
    claims: Sequence[DisputeClaim],
    resolutions: Sequence[DisputeResolution],
    responses: Sequence[DisputeResolutionResponse],
    tick: int,
) -> DisputeStatus:
    relevant_claims = tuple(
        claim for claim in claims if claim.case_ref == case.case_ref
    )
    active = tuple(claim for claim in relevant_claims if claim.active)
    if not relevant_claims:
        if resolutions or case.status is DisputeStatus.EVIDENCE_GATHERING:
            return DisputeStatus.EVIDENCE_GATHERING
        return DisputeStatus.ABANDONED
    if not active:
        return DisputeStatus.WITHDRAWN
    relevant_resolutions = tuple(
        row for row in resolutions if row.case_ref == case.case_ref
    )
    latest: DisputeResolution | None = None
    for resolution in relevant_resolutions:
        if latest is None or (resolution.first_tick, resolution.resolution_id) > (
            latest.first_tick,
            latest.resolution_id,
        ):
            latest = resolution
    if latest is not None:
        status = _resolution_status(
            latest,
            responses,
            case.party_ids,
            tick,
        )
        if status is DisputeResolutionStatus.APPARENTLY_ACCEPTED:
            if any(claim.first_tick > latest.first_tick for claim in active):
                return DisputeStatus.REOPENED
            return DisputeStatus.APPARENTLY_RESOLVED
        if status is DisputeResolutionStatus.CONTESTED:
            return DisputeStatus.CONTESTED
        if status in (
            DisputeResolutionStatus.PROPOSED,
            DisputeResolutionStatus.PARTIALLY_ACCEPTED,
        ):
            return DisputeStatus.RESOLUTION_PROPOSED
    if tick > case.window_last_tick:
        return DisputeStatus.EXPIRED
    for claim in active:
        for other in active:
            if (
                claim.claimant_id != other.claimant_id
                and claim.polarity is not other.polarity
                and claim.counters_claim_ref is not None
            ):
                return DisputeStatus.CONTESTED
    return DisputeStatus.OPEN


def _resolution_status(
    resolution: DisputeResolution,
    responses: Sequence[DisputeResolutionResponse],
    party_ids: Sequence[str],
    tick: int,
) -> DisputeResolutionStatus:
    active = tuple(
        row
        for row in responses
        if row.resolution_ref == resolution.resolution_ref and row.active
    )
    if resolution.status is DisputeResolutionStatus.SUPERSEDED:
        return DisputeResolutionStatus.SUPERSEDED
    if any(
        row.kind is DisputeResolutionResponseKind.WITHDRAW
        and row.party_id == resolution.proposer_id
        for row in active
    ):
        return DisputeResolutionStatus.WITHDRAWN
    if resolution.expires_tick is not None and tick > resolution.expires_tick:
        return DisputeResolutionStatus.EXPIRED
    if any(
        row.kind
        in (
            DisputeResolutionResponseKind.REJECT,
            DisputeResolutionResponseKind.COUNTERPROPOSE,
        )
        for row in active
    ):
        return DisputeResolutionStatus.CONTESTED
    accepted = {
        row.party_id
        for row in active
        if row.kind is DisputeResolutionResponseKind.ACCEPT
    }
    if accepted and set(party_ids) <= accepted:
        return DisputeResolutionStatus.APPARENTLY_ACCEPTED
    if accepted:
        return DisputeResolutionStatus.PARTIALLY_ACCEPTED
    return DisputeResolutionStatus.PROPOSED


def _refresh_draft(
    draft: _Draft,
    *,
    owner: str,
    tick: int,
    prior: DisputeLedger | None,
) -> DisputeLedger:
    evidence = _draft_rows(draft, "evidence")
    by_claim: dict[str, list[str]] = {}
    for row in evidence:
        by_claim.setdefault(row.claim_ref, []).append(row.evidence_id)
    for key, claim in list(draft["claims"].items()):
        replacement = replace(
            claim,
            evidence_ids=tuple(sorted(by_claim.get(claim.claim_ref, ()))),
        )
        if claim.active and replacement.last_tick < tick:
            replacement = replace(replacement, last_tick=tick)
        draft["claims"][key] = replacement
    claims = _draft_rows(draft, "claims")
    resolutions = _draft_rows(draft, "resolutions")
    responses = _draft_rows(draft, "resolution_responses")
    for key, resolution in list(draft["resolutions"].items()):
        if resolution.status is DisputeResolutionStatus.SUPERSEDED:
            continue
        resolution_status = _resolution_status(
            resolution,
            responses,
            _case_parties(draft, resolution.case_ref),
            tick,
        )
        draft["resolutions"][key] = replace(resolution, status=resolution_status)
    resolutions = _draft_rows(draft, "resolutions")
    for key, case in list(draft["cases"].items()):
        case_claims = tuple(
            claim for claim in claims if claim.case_ref == case.case_ref
        )
        case_resolutions = tuple(
            row for row in resolutions if row.case_ref == case.case_ref
        )
        status = _case_status(case, case_claims, case_resolutions, responses, tick)
        draft["cases"][key] = replace(
            case,
            status=status,
            last_tick=max(case.last_tick, tick),
            claimant_ids=tuple(
                sorted({case.owner_id} | {claim.claimant_id for claim in case_claims})
            ),
            respondent_ids=tuple(
                sorted(
                    set(case.party_ids) - {claim.claimant_id for claim in case_claims}
                )
            ),
        )
    first = prior.first_observed_tick if prior is not None else None
    last = prior.last_observed_tick if prior is not None else None
    count = prior.observation_count if prior is not None else 0
    if last != tick:
        count += 1
        last = tick
    if first is None:
        first = tick
    return DisputeLedger(
        owner_id=owner,
        cases=_draft_rows(draft, "cases"),
        claims=_draft_rows(draft, "claims"),
        testimony=_draft_rows(draft, "testimony"),
        evidence=evidence,
        rule_references=_draft_rows(draft, "rule_references"),
        authority_references=_draft_rows(draft, "authority_references"),
        mediation_references=_draft_rows(draft, "mediation_references"),
        resolutions=_draft_rows(draft, "resolutions"),
        resolution_responses=_draft_rows(draft, "resolution_responses"),
        notices=tuple(draft.get("notices", ())),
        policy_version=(
            prior.policy_version if prior is not None else DISPUTE_POLICY_VERSION
        ),
        first_observed_tick=first,
        last_observed_tick=last,
        observation_count=count,
        pruned_case_count=prior.pruned_case_count if prior is not None else 0,
        pruned_claim_count=prior.pruned_claim_count if prior is not None else 0,
        pruned_testimony_count=(
            prior.pruned_testimony_count if prior is not None else 0
        ),
        pruned_evidence_count=(prior.pruned_evidence_count if prior is not None else 0),
        pruned_resolution_count=(
            prior.pruned_resolution_count if prior is not None else 0
        ),
        pruned_reference_count=(
            prior.pruned_reference_count if prior is not None else 0
        ),
    )


def _case_parties(draft: _Draft, case_ref: str) -> tuple[str, ...]:
    for case in draft["cases"].values():
        if case.case_ref == case_ref:
            return tuple(case.party_ids)
    return ()


def _notice(draft: _Draft, reason: str) -> None:
    notices = draft.setdefault("notices", [])
    assert isinstance(notices, list)
    if reason not in notices:
        notices.append(reason)


def _get_case_by_ref(draft: _Draft, case_ref: str) -> DisputeCase | None:
    for case in draft["cases"].values():
        if case.case_ref == case_ref:
            return cast(DisputeCase, case)
    return None


def _get_claim_by_ref(draft: _Draft, claim_ref: str) -> DisputeClaim | None:
    for claim in draft["claims"].values():
        if claim.claim_ref == claim_ref:
            return cast(DisputeClaim, claim)
    return None


def _get_resolution_by_ref(
    draft: _Draft, resolution_ref: str
) -> DisputeResolution | None:
    for resolution in draft["resolutions"].values():
        if resolution.resolution_ref == resolution_ref:
            return cast(DisputeResolution, resolution)
    return None


def _ensure_case(
    draft: _Draft,
    *,
    owner: str,
    case_ref: str,
    kind: DisputeKind,
    subject_kind: DisputeSubjectKind,
    subject_token: str,
    subject_digest: str,
    context_key: str,
    party_ids: Sequence[str],
    claimant_id: str,
    respondent_id: str,
    tick: int,
    policy: DisputePolicy,
) -> DisputeCase:
    existing = _get_case_by_ref(draft, case_ref)
    if existing is not None:
        refined = kind if existing.kind is DisputeKind.OTHER else existing.kind
        updated = replace(
            existing,
            kind=refined,
            last_tick=max(existing.last_tick, tick),
            claimant_ids=tuple(sorted({*existing.claimant_ids, claimant_id})),
            respondent_ids=tuple(sorted({*existing.respondent_ids, respondent_id})),
        )
        draft["cases"][updated.case_id] = updated
        return updated
    parties = tuple(sorted(set(party_ids)))
    case = DisputeCase(
        case_id=dispute_case_id(owner, case_ref),
        owner_id=owner,
        case_ref=case_ref,
        kind=kind,
        subject_kind=subject_kind,
        subject_token=subject_token,
        subject_digest=subject_digest,
        context_key=context_key,
        party_ids=parties,
        claimant_ids=(claimant_id,),
        respondent_ids=(respondent_id,),
        status=DisputeStatus.OPEN,
        first_tick=tick,
        last_tick=tick,
        window_first_tick=tick,
        window_last_tick=tick + policy.resolution_window_ticks,
    )
    draft["cases"][case.case_id] = case
    return case


def _add_evidence(
    draft: _Draft,
    *,
    owner: str,
    case_ref: str,
    claim_ref: str,
    channel: DisputeEvidenceChannel,
    reference_kind: DisputeEvidenceReferenceKind,
    reference_id: str,
    tick: int,
    actor_id: str | None,
    independently_evidenced: bool,
    provenance: DisputeProvenance,
) -> DisputeEvidence:
    ordinal = sum(
        1
        for row in draft["evidence"].values()
        if row.case_ref == case_ref and row.claim_ref == claim_ref
    )
    evidence = DisputeEvidence(
        evidence_id=dispute_evidence_id(
            owner,
            case_ref,
            claim_ref,
            channel,
            reference_kind,
            reference_id,
            ordinal,
        ),
        case_ref=case_ref,
        claim_ref=claim_ref,
        owner_id=owner,
        channel=channel,
        reference_kind=reference_kind,
        reference_id=reference_id,
        tick=tick,
        actor_id=actor_id,
        independently_evidenced=independently_evidenced,
        provenance=provenance,
    )
    draft["evidence"][evidence.evidence_id] = evidence
    return evidence


def _apply_claim_frame(
    draft: _Draft,
    frame: Any,
    *,
    owner: str,
    speaker: str,
    respondent: str,
    tick: int,
    context_key: str,
    policy: DisputePolicy,
    communication: object | None,
) -> None:
    role = frame.role
    kind = frame.kind
    subject_kind = frame.subject_kind
    subject_token = frame.subject_token
    polarity = frame.polarity
    if (
        role is None
        or kind is None
        or subject_kind is None
        or subject_token is None
        or polarity is None
    ):
        _notice(draft, "dispute_invalid_frame")
        return
    if owner not in {speaker, respondent}:
        _notice(draft, "dispute_unknown_reference")
        return
    if role is DisputeClaimRole.COUNTERCLAIM:
        countered = _get_claim_by_ref(draft, frame.claim_ref or "")
        if countered is None or countered.claimant_id == speaker:
            _notice(draft, "dispute_unknown_reference")
            return
        counters_ref = countered.claim_ref
    else:
        counters_ref = None
    subject_digest = dispute_subject_digest(subject_kind, subject_token)
    party_ids = sorted({speaker, respondent})
    case_ref = dispute_case_ref(subject_token, party_ids)
    claim_kind = DisputeClaimKind(
        {
            DisputeKind.CONTESTED_DEBT: "debt_owed",
            DisputeKind.OWNERSHIP_CLAIM: "item_owned",
            DisputeKind.CONTRACT_INTERPRETATION: "term_meaning",
            DisputeKind.INJURY: "harm_caused",
            DisputeKind.BROKEN_PROMISE: "promise_broken",
            DisputeKind.RESOURCE_APPROPRIATION: "resource_taken",
        }.get(kind, "other")
    )
    claim_ref = dispute_claim_ref(
        case_ref, speaker, role, claim_kind, polarity, subject_digest
    )
    existing = _get_claim_by_ref(draft, claim_ref)
    _ensure_case(
        draft,
        owner=owner,
        case_ref=case_ref,
        kind=kind,
        subject_kind=subject_kind,
        subject_token=subject_token,
        subject_digest=subject_digest,
        context_key=context_key,
        party_ids=party_ids,
        claimant_id=speaker,
        respondent_id=respondent,
        tick=tick,
        policy=policy,
    )
    claim = DisputeClaim(
        claim_id=dispute_claim_id(owner, claim_ref),
        claim_ref=claim_ref,
        case_ref=case_ref,
        owner_id=owner,
        claimant_id=speaker,
        respondent_id=respondent,
        role=role,
        claim_kind=claim_kind,
        polarity=polarity,
        subject_kind=subject_kind,
        subject_token=subject_token,
        subject_digest=subject_digest,
        action_token=getattr(frame, "action_token", None),
        item_token=(subject_token if subject_kind is DisputeSubjectKind.ITEM else None),
        quantity=0,
        terms_digest=None,
        counters_claim_ref=counters_ref,
        rule_reference_token=(
            existing.rule_reference_token if existing is not None else None
        ),
        evidence_ids=(),
        provenance=(
            DisputeProvenance.SELF_ASSERTED
            if speaker == owner
            else DisputeProvenance.COMMUNICATED
        ),
        confidence=1.0 if speaker == owner else 0.7,
        first_tick=existing.first_tick if existing is not None else tick,
        last_tick=tick,
        active=True,
    )
    draft["claims"][claim.claim_id] = claim
    if communication is not None:
        source_event = _token_of(
            getattr(getattr(communication, "provenance", None), "source_event_id", None)
        )
        if source_event is not None:
            _add_evidence(
                draft,
                owner=owner,
                case_ref=case_ref,
                claim_ref=claim_ref,
                channel=DisputeEvidenceChannel.COMMUNICATED,
                reference_kind=DisputeEvidenceReferenceKind.OBSERVED_COMMUNICATION,
                reference_id=source_event,
                tick=tick,
                actor_id=speaker,
                independently_evidenced=False,
                provenance=DisputeProvenance.DERIVED_FROM_OBSERVATION,
            )


def _apply_frame(
    draft: _Draft,
    frame: Any,
    *,
    owner: str,
    speaker: str,
    respondent: str,
    tick: int,
    context_key: str,
    policy: DisputePolicy,
    communication: object | None = None,
) -> None:
    act = getattr(frame, "act", None)
    token = getattr(act, "value", "")
    if token in ("claim", "counterclaim"):
        _apply_claim_frame(
            draft,
            frame,
            owner=owner,
            speaker=speaker,
            respondent=respondent,
            tick=tick,
            context_key=context_key,
            policy=policy,
            communication=communication,
        )
        return
    case_ref = getattr(frame, "case_ref", None)
    claim_ref = getattr(frame, "claim_ref", None)
    if token == "testify":
        claim = _get_claim_by_ref(draft, claim_ref or "")
        if claim is None:
            _notice(draft, "dispute_unknown_reference")
            return
        channel = (
            DisputeTestimonyChannel.DIRECT
            if getattr(frame, "direct", False)
            else DisputeTestimonyChannel.COMMUNICATED
        )
        root_ref = getattr(frame, "root_ref", None)
        if root_ref is None:
            _notice(draft, "dispute_invalid_frame")
            return
        shared_root = any(
            row.claim_ref == claim.claim_ref
            and row.root_ref == root_ref
            and row.speaker_id != speaker
            for row in draft["testimony"].values()
        )
        testimony = DisputeTestimony(
            testimony_id=dispute_testimony_id(
                owner,
                claim.case_ref,
                claim.claim_ref,
                speaker,
                channel,
                root_ref,
                tick,
            ),
            case_ref=claim.case_ref,
            claim_ref=claim.claim_ref,
            owner_id=owner,
            speaker_id=speaker,
            channel=channel,
            root_ref=root_ref,
            independently_evidenced=(
                channel is DisputeTestimonyChannel.DIRECT and not shared_root
            ),
            evidence_id=None,
            tick=tick,
            provenance=(
                DisputeProvenance.SELF_ASSERTED
                if speaker == owner
                else DisputeProvenance.COMMUNICATED
            ),
        )
        draft["testimony"][testimony.testimony_id] = testimony
        return
    if token == "cite_evidence":
        claim = _get_claim_by_ref(draft, claim_ref or "")
        reference = getattr(frame, "evidence_ref", None)
        if claim is None or reference is None or "@" not in reference:
            _notice(draft, "dispute_unknown_reference")
            return
        kind_token, reference_id = reference.split("@", 1)
        try:
            reference_kind = DisputeEvidenceReferenceKind(kind_token)
        except ValueError:
            _notice(draft, "dispute_unknown_reference")
            return
        if not reference_id:
            _notice(draft, "dispute_unknown_reference")
            return
        _add_evidence(
            draft,
            owner=owner,
            case_ref=claim.case_ref,
            claim_ref=claim.claim_ref,
            channel=DisputeEvidenceChannel.COMMUNICATED,
            reference_kind=reference_kind,
            reference_id=reference_id,
            tick=tick,
            actor_id=speaker,
            independently_evidenced=False,
            provenance=DisputeProvenance.COMMUNICATED,
        )
        return
    if token == "cite_rule":
        claim = _get_claim_by_ref(draft, claim_ref or "")
        if claim is None:
            _notice(draft, "dispute_unknown_reference")
            return
        draft["claims"][claim.claim_id] = replace(
            claim,
            rule_reference_token=getattr(frame, "rule_ref", None),
            last_tick=tick,
        )
        return
    if token == "reference_mediation":
        case = _get_case_by_ref(draft, case_ref or "")
        mediation_ref = getattr(frame, "mediation_ref", None)
        if case is None or mediation_ref is None:
            _notice(draft, "dispute_unknown_reference")
            return
        link = DisputeMediationReference(
            mediation_reference_id=dispute_mediation_reference_id(
                owner, case.case_ref, mediation_ref, "none"
            ),
            case_ref=case.case_ref,
            owner_id=owner,
            mediation_case_ref=mediation_ref,
            recommendation_ref=None,
            response_ref=None,
            outcome_ref=None,
            link_status=DisputeMediationLinkStatus.ORPHANED,
            provenance=DisputeProvenance.COMMUNICATED,
            first_tick=tick,
            last_tick=tick,
        )
        draft["mediation_references"][link.mediation_reference_id] = link
        return
    if token == "propose_resolution":
        case = _get_case_by_ref(draft, case_ref or "")
        if case is None:
            _notice(draft, "dispute_unknown_reference")
            return
        terms = tuple(getattr(frame, "terms", ()))
        terms_digest = getattr(frame, "terms_digest", None)
        resolution_ref = getattr(frame, "resolution_ref", None)
        if terms_digest is None or resolution_ref is None:
            _notice(draft, "dispute_invalid_frame")
            return
        if dispute_terms_digest(terms) != terms_digest:
            _notice(draft, "dispute_terms_mismatch")
            return
        if resolution_ref != dispute_resolution_ref(
            case.case_ref, speaker, terms_digest
        ):
            _notice(draft, "dispute_invalid_frame")
            return
        linked_result = any(
            row.case_ref == case.case_ref
            and row.link_status is DisputeMediationLinkStatus.LINKED
            and row.recommendation_ref is not None
            for row in draft["mediation_references"].values()
        )
        for resolution in list(draft["resolutions"].values()):
            if (
                resolution.case_ref == case.case_ref
                and resolution.proposer_id == speaker
                and resolution.status is DisputeResolutionStatus.PROPOSED
            ):
                draft["resolutions"][resolution.resolution_id] = replace(
                    resolution, status=DisputeResolutionStatus.SUPERSEDED
                )
        resolution = DisputeResolution(
            resolution_id=dispute_resolution_id(owner, resolution_ref),
            resolution_ref=resolution_ref,
            case_ref=case.case_ref,
            owner_id=owner,
            proposer_id=speaker,
            source=(
                DisputeResolutionSource.MEDIATOR
                if linked_result
                else DisputeResolutionSource.UNILATERAL
            ),
            terms=terms,
            terms_digest=terms_digest,
            status=DisputeResolutionStatus.PROPOSED,
            first_tick=tick,
            last_tick=tick,
            expires_tick=tick + policy.resolution_window_ticks,
            provenance=(
                DisputeProvenance.SELF_ASSERTED
                if speaker == owner
                else DisputeProvenance.COMMUNICATED
            ),
        )
        draft["resolutions"][resolution.resolution_id] = resolution
        return
    if token in ("accept_resolution", "reject_resolution"):
        resolution = _get_resolution_by_ref(
            draft, getattr(frame, "resolution_ref", "") or ""
        )
        if resolution is None:
            _notice(draft, "dispute_unknown_reference")
            return
        digest = getattr(frame, "terms_digest", None)
        if digest != resolution.terms_digest:
            _notice(draft, "dispute_terms_mismatch")
            return
        if resolution.first_tick == tick and resolution.proposer_id != speaker:
            _notice(draft, "dispute_resolution_requires_prior_tick")
            return
        case = _get_case_by_ref(draft, resolution.case_ref)
        if case is None or speaker not in case.party_ids:
            _notice(draft, "dispute_unknown_reference")
            return
        kind = (
            DisputeResolutionResponseKind.ACCEPT
            if token == "accept_resolution"
            else DisputeResolutionResponseKind.REJECT
        )
        for response in list(draft["resolution_responses"].values()):
            if (
                response.resolution_ref == resolution.resolution_ref
                and response.party_id == speaker
                and response.active
            ):
                draft["resolution_responses"][response.response_id] = replace(
                    response, active=False
                )
        response = DisputeResolutionResponse(
            response_id=dispute_response_id(
                owner, resolution.resolution_ref, speaker, kind, tick
            ),
            resolution_id=resolution.resolution_id,
            resolution_ref=resolution.resolution_ref,
            case_ref=resolution.case_ref,
            owner_id=owner,
            party_id=speaker,
            kind=kind,
            tick=tick,
            terms_digest=resolution.terms_digest,
            active=True,
            provenance=(
                DisputeProvenance.SELF_ASSERTED
                if speaker == owner
                else DisputeProvenance.COMMUNICATED
            ),
        )
        draft["resolution_responses"][response.response_id] = response
        return
    if token == "withdraw_claim":
        claim = _get_claim_by_ref(draft, claim_ref or "")
        if claim is None or claim.claimant_id != speaker:
            _notice(draft, "dispute_unknown_reference")
            return
        draft["claims"][claim.claim_id] = replace(
            claim,
            active=False,
            provenance=DisputeProvenance.SELF_ASSERTED,
            last_tick=tick,
        )
        return
    _notice(draft, "dispute_invalid_frame")


def _commitment_case_kind(kind_token: str) -> DisputeKind | None:
    if kind_token in {"debt", "future_exchange"}:
        return DisputeKind.CONTESTED_DEBT
    if kind_token in {"promise", "conditional_agreement", "service_obligation"}:
        return DisputeKind.BROKEN_PROMISE
    return None


def _collect_commitments(
    draft: _Draft,
    *,
    owner: str,
    tick: int,
    context_key: str,
    structured_commitments: object | None,
    retrieved_memory_context: object | None,
    policy: DisputePolicy,
) -> None:
    memory_ids = {
        _token_of(memory_id)
        for memory_id in getattr(retrieved_memory_context, "memory_ids", ()) or ()
    }
    for interpretation in getattr(structured_commitments, "interpretations", ()) or ():
        status = getattr(interpretation, "status", None)
        if status not in {"disputed", "violated", "partial"}:
            continue
        kind_token = getattr(interpretation, "kind", None)
        if type(kind_token) is not str:
            continue
        case_kind = _commitment_case_kind(kind_token)
        if case_kind is None:
            continue
        local_id = getattr(interpretation, "local_id", None)
        if type(local_id) is not int:
            continue
        parties = tuple(getattr(interpretation, "parties", ()) or ())
        debtor = getattr(interpretation, "debtor_id", None)
        creditor = getattr(interpretation, "creditor_id", None)
        respondent = creditor if debtor == owner else debtor
        if type(respondent) is not str or respondent == owner:
            continue
        subject_token = f"commitment-{local_id}"
        subject_kind = DisputeSubjectKind.COMMITMENT
        subject_digest = dispute_subject_digest(subject_kind, subject_token)
        party_ids = sorted({owner, respondent, *parties})
        case_ref = dispute_case_ref(subject_token, party_ids)
        _ensure_case(
            draft,
            owner=owner,
            case_ref=case_ref,
            kind=case_kind,
            subject_kind=subject_kind,
            subject_token=subject_token,
            subject_digest=subject_digest,
            context_key=context_key,
            party_ids=party_ids,
            claimant_id=owner,
            respondent_id=respondent,
            tick=tick,
            policy=policy,
        )
        claim_kind = (
            DisputeClaimKind.DEBT_OWED
            if case_kind is DisputeKind.CONTESTED_DEBT
            else DisputeClaimKind.PROMISE_BROKEN
        )
        claim_ref = dispute_claim_ref(
            case_ref,
            owner,
            DisputeClaimRole.CLAIM,
            claim_kind,
            DisputeClaimPolarity.AFFIRM,
            subject_digest,
        )
        existing = _get_claim_by_ref(draft, claim_ref)
        claim = DisputeClaim(
            claim_id=dispute_claim_id(owner, claim_ref),
            claim_ref=claim_ref,
            case_ref=case_ref,
            owner_id=owner,
            claimant_id=owner,
            respondent_id=respondent,
            role=DisputeClaimRole.CLAIM,
            claim_kind=claim_kind,
            polarity=DisputeClaimPolarity.AFFIRM,
            subject_kind=subject_kind,
            subject_token=subject_token,
            subject_digest=subject_digest,
            action_token=None,
            item_token=getattr(interpretation, "item_kind", None),
            quantity=0,
            terms_digest=None,
            counters_claim_ref=None,
            rule_reference_token=(
                existing.rule_reference_token if existing is not None else None
            ),
            evidence_ids=(),
            provenance=DisputeProvenance.DERIVED_FROM_MEMORY,
            confidence=float(getattr(interpretation, "confidence", 0.5) or 0.5),
            first_tick=existing.first_tick if existing is not None else tick,
            last_tick=tick,
            active=True,
        )
        draft["claims"][claim.claim_id] = claim
        _add_evidence(
            draft,
            owner=owner,
            case_ref=case_ref,
            claim_ref=claim_ref,
            channel=DisputeEvidenceChannel.DERIVED,
            reference_kind=DisputeEvidenceReferenceKind.COMMITMENT,
            reference_id=f"commitment:{local_id}",
            tick=tick,
            actor_id=owner,
            independently_evidenced=True,
            provenance=DisputeProvenance.DERIVED_FROM_MEMORY,
        )
        for trace_id in getattr(interpretation, "memory_trace_ids", ()) or ():
            if trace_id in memory_ids:
                _add_evidence(
                    draft,
                    owner=owner,
                    case_ref=case_ref,
                    claim_ref=claim_ref,
                    channel=DisputeEvidenceChannel.REMEMBERED,
                    reference_kind=DisputeEvidenceReferenceKind.MEMORY_TRACE,
                    reference_id=trace_id,
                    tick=tick,
                    actor_id=owner,
                    independently_evidenced=True,
                    provenance=DisputeProvenance.DERIVED_FROM_MEMORY,
                )


def _collect_mediation_cases(
    draft: _Draft,
    *,
    owner: str,
    tick: int,
    context_key: str,
    mediation: object | None,
    policy: DisputePolicy,
) -> None:
    for mediation_case in getattr(mediation, "cases", ()) or ():
        party_tokens = {
            _normalize_owner(getattr(party, "value", party))
            for party in getattr(mediation_case, "party_ids", ()) or ()
        }
        if owner not in party_tokens:
            continue
        subject_token = getattr(mediation_case, "subject_token", None)
        if type(subject_token) is not str or not subject_token:
            continue
        party_ids = sorted({owner, *party_tokens})
        subject_kind = DisputeSubjectKind.UNSPECIFIED
        subject_digest = dispute_subject_digest(subject_kind, subject_token)
        case_ref = dispute_case_ref(subject_token, party_ids)
        respondents = tuple(party for party in party_ids if party != owner)
        _ensure_case(
            draft,
            owner=owner,
            case_ref=case_ref,
            kind=DisputeKind.OTHER,
            subject_kind=subject_kind,
            subject_token=subject_token,
            subject_digest=subject_digest,
            context_key=context_key,
            party_ids=party_ids,
            claimant_id=owner,
            respondent_id=respondents[0] if respondents else owner,
            tick=tick,
            policy=policy,
        )
        case = _get_case_by_ref(draft, case_ref)
        if case is not None:
            draft["cases"][case.case_id] = replace(
                case, status=DisputeStatus.EVIDENCE_GATHERING
            )


def _collect_observation_evidence(
    draft: _Draft,
    *,
    owner: str,
    tick: int,
    observation: object,
) -> None:
    claims = tuple(draft["claims"].values())
    for occurrence in getattr(observation, "occurrences", ()) or ():
        source_event = _token_of(
            getattr(getattr(occurrence, "provenance", None), "source_event_id", None)
        )
        if source_event is None:
            continue
        actor = _token_of(getattr(occurrence, "actor_id", None))
        other = _token_of(getattr(occurrence, "other_entity_id", None))
        kind = getattr(occurrence, "kind", None)
        for claim in claims:
            if not claim.active:
                continue
            if not (
                claim.subject_token in {actor, other}
                or (claim.action_token is not None and claim.action_token == kind)
            ):
                continue
            _add_evidence(
                draft,
                owner=owner,
                case_ref=claim.case_ref,
                claim_ref=claim.claim_ref,
                channel=DisputeEvidenceChannel.OBSERVED,
                reference_kind=DisputeEvidenceReferenceKind.OBSERVED_OCCURRENCE,
                reference_id=source_event,
                tick=tick,
                actor_id=actor,
                independently_evidenced=True,
                provenance=DisputeProvenance.DERIVED_FROM_OBSERVATION,
            )


def _collect_valuation_evidence(
    draft: _Draft,
    *,
    owner: str,
    tick: int,
    subjective_valuations: object | None,
) -> None:
    rows = tuple(getattr(subjective_valuations, "judgment_rows", ()) or ())
    if not rows:
        return
    for claim in tuple(draft["claims"].values()):
        if not claim.active or claim.claim_kind not in {
            DisputeClaimKind.ITEM_OWNED,
            DisputeClaimKind.RESOURCE_TAKEN,
        }:
            continue
        row = rows[0]
        item_kind = _token_of(getattr(row, "item_kind", None)) or "unknown"
        _add_evidence(
            draft,
            owner=owner,
            case_ref=claim.case_ref,
            claim_ref=claim.claim_ref,
            channel=DisputeEvidenceChannel.REMEMBERED,
            reference_kind=DisputeEvidenceReferenceKind.VALUATION,
            reference_id=f"valuation:{item_kind}:{getattr(row, 'tick', tick)}",
            tick=tick,
            actor_id=owner,
            independently_evidenced=True,
            provenance=DisputeProvenance.DERIVED_FROM_MEMORY,
        )


def apply_dispute_update(
    owner_id: AgentId | str,
    tick: int,
    observation: object,
    prior: DisputeLedger | None,
    *,
    identity: object | None = None,
    retrieved_memory_context: object | None = None,
    structured_commitments: object | None = None,
    subjective_valuations: object | None = None,
    mediation: object | None = None,
    formal_rules: object | None = None,
    offices: object | None = None,
    institution_concepts: object | None = None,
    organization_concepts: object | None = None,
    collective_decisions: object | None = None,
    policy: DisputePolicy | None = None,
) -> DisputeLedger:
    """Derive one owner's dispute beliefs from owner-visible evidence.

    The update reads only the owner observation, the owner identity projection,
    and prepared same-owner ledgers. It never reads a peer dispute ledger, world
    state, event store, command, analysis row, or published snapshot, and it
    never returns or submits a command.
    """

    from agents.cognition.legal_dispute_communication import (
        DISPUTE_FRAME_SUBJECT,
        dispute_frame_party_matches,
        parse_dispute_frame_relation,
    )

    owner = _normalize_owner(owner_id)
    absolute_tick = _observation_tick(observation)
    if tick != absolute_tick:
        _fail("dispute_invalid_tick")
    locked = require_dispute_policy(policy)
    _reject_forbidden_input(observation, owner=owner)
    for value in (
        retrieved_memory_context,
        structured_commitments,
        subjective_valuations,
        mediation,
        formal_rules,
        offices,
        institution_concepts,
        organization_concepts,
        collective_decisions,
        prior,
    ):
        _reject_forbidden_input(value, owner=owner)
    if prior is not None:
        require_owner_disputes(prior, owner, field_name="prior")
        if prior.policy_version != DISPUTE_POLICY_VERSION:
            _fail("dispute_policy_mismatch")

    draft = _empty_draft(prior)
    draft["notices"] = list(prior.notices if prior is not None else ())
    context_key = _context_digest(observation)
    owner_entity = _owner_entity_token(identity, owner)
    frames: list[tuple[tuple[Any, ...], Any, Any]] = []
    for index, communication in enumerate(
        getattr(observation, "communications", ()) or ()
    ):
        listener = _token_of(getattr(communication, "listener_id", None))
        if listener != owner_entity:
            continue
        speaker_entity = _token_of(getattr(communication, "speaker_id", None))
        if speaker_entity is None:
            continue
        speaker = _entity_to_agent(identity, speaker_entity)
        if speaker == owner:
            continue
        relations = getattr(getattr(communication, "utterance", None), "content", None)
        for relation_index, relation in enumerate(
            getattr(relations, "relations", ()) or ()
        ):
            if getattr(relation, "subject", None) != DISPUTE_FRAME_SUBJECT:
                continue
            frame = parse_dispute_frame_relation(relation)
            if frame is None:
                _notice(draft, "dispute_invalid_frame")
                continue
            if frame.party_ref is not None and not dispute_frame_party_matches(
                frame, speaker_entity
            ):
                _notice(draft, "dispute_party_mismatch")
                continue
            frames.append(
                (
                    (
                        _act_order(frame),
                        getattr(frame, "case_ref", "") or "",
                        getattr(frame, "claim_ref", "") or "",
                        index,
                        relation_index,
                    ),
                    frame,
                    communication,
                )
            )
    for _order, frame, communication in sorted(frames, key=lambda item: item[0]):
        _apply_frame(
            draft,
            frame,
            owner=owner,
            speaker=_entity_to_agent(
                identity, _token_of(getattr(communication, "speaker_id", None)) or ""
            ),
            respondent=owner,
            tick=absolute_tick,
            context_key=context_key,
            policy=locked,
            communication=communication,
        )
    _collect_commitments(
        draft,
        owner=owner,
        tick=absolute_tick,
        context_key=context_key,
        structured_commitments=structured_commitments,
        retrieved_memory_context=retrieved_memory_context,
        policy=locked,
    )
    _collect_mediation_cases(
        draft,
        owner=owner,
        tick=absolute_tick,
        context_key=context_key,
        mediation=mediation,
        policy=locked,
    )
    _collect_observation_evidence(
        draft,
        owner=owner,
        tick=absolute_tick,
        observation=observation,
    )
    _collect_valuation_evidence(
        draft,
        owner=owner,
        tick=absolute_tick,
        subjective_valuations=subjective_valuations,
    )
    ledger = _refresh_draft(draft, owner=owner, tick=absolute_tick, prior=prior)
    ledger = enforce_dispute_limits(ledger, locked)
    _LOG.debug(
        "dispute_update owner=%s cases=%s claims=%s evidence=%s",
        owner,
        len(ledger.cases),
        len(ledger.claims),
        len(ledger.evidence),
    )
    return ledger


def record_dispute_utterance(
    ledger: DisputeLedger,
    *,
    owner_id: AgentId | str,
    tick: int,
    command: object,
    identity: object | None = None,
    policy: DisputePolicy | None = None,
) -> DisputeLedger:
    """Record the owner's own selected ``dsp_v1`` declaration. Never mints a command."""

    from agents.cognition.legal_dispute_communication import (
        DISPUTE_FRAME_SUBJECT,
        dispute_frame_party_matches,
        parse_dispute_frame_relation,
    )

    if type(ledger) is not DisputeLedger:
        raise TypeError("ledger must be DisputeLedger")
    owner = _normalize_owner(owner_id)
    if ledger.owner_id != owner:
        _fail("dispute_owner_mismatch")
    absolute_tick = _require_tick(tick)
    locked = require_dispute_policy(policy)
    utterance = getattr(command, "utterance", None)
    content = getattr(utterance, "content", None)
    frame: Any = None
    found = False
    for relation in getattr(content, "relations", ()) or ():
        if getattr(relation, "subject", None) != DISPUTE_FRAME_SUBJECT:
            continue
        found = True
        frame = parse_dispute_frame_relation(relation)
        break
    if not found:
        return ledger
    draft = _empty_draft(ledger)
    draft["notices"] = list(ledger.notices)
    if frame is None:
        _notice(draft, "dispute_invalid_frame")
        return _refresh_draft(draft, owner=owner, tick=absolute_tick, prior=ledger)
    owner_entity = _owner_entity_token(identity, owner)
    if frame.party_ref is not None and not dispute_frame_party_matches(
        frame, owner_entity
    ):
        _notice(draft, "dispute_party_mismatch")
        return _refresh_draft(draft, owner=owner, tick=absolute_tick, prior=ledger)
    recipient_entity = _token_of(getattr(command, "recipient_id", None))
    respondent = (
        _entity_to_agent(identity, recipient_entity)
        if recipient_entity is not None
        else owner
    )
    _apply_frame(
        draft,
        frame,
        owner=owner,
        speaker=owner,
        respondent=respondent,
        tick=absolute_tick,
        context_key=_context_digest_for_owner(owner),
        policy=locked,
    )
    updated = _refresh_draft(draft, owner=owner, tick=absolute_tick, prior=ledger)
    return enforce_dispute_limits(updated, locked)


def _context_digest_for_owner(owner: str) -> str:
    material = f"dispute-context|owner|{owner}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Legal-reasoning references and deliberation hooks
# ---------------------------------------------------------------------------

_AUTHORITY_CHANNEL_KIND: Final[Mapping[str, DisputeAuthorityKind]] = MappingProxyType(
    {
        "role": DisputeAuthorityKind.OFFICE,
        "institution": DisputeAuthorityKind.INSTITUTION,
        "norm": DisputeAuthorityKind.CUSTOM,
        "relationship": DisputeAuthorityKind.CUSTOM,
        "reputation": DisputeAuthorityKind.CUSTOM,
    }
)


def _split_rule_token(token: str) -> tuple[str, int]:
    if "@" not in token:
        return token, 1
    rule_id, version_text = token.rsplit("@", 1)
    try:
        version = int(version_text)
    except ValueError:
        return rule_id, 1
    if version < 1:
        return rule_id, 1
    return rule_id, version


def _rule_applicability(
    claim: DisputeClaim, constraint_kind: str, scope_digest: str | None
) -> DisputeRuleApplicability:
    if (
        claim.claim_kind is DisputeClaimKind.RESOURCE_TAKEN
        and constraint_kind == "prohibition"
    ):
        return DisputeRuleApplicability.APPLIES
    if (
        claim.claim_kind is DisputeClaimKind.DEBT_OWED
        and constraint_kind == "obligation"
    ):
        return DisputeRuleApplicability.APPLIES
    if claim.claim_kind is DisputeClaimKind.TERM_MEANING:
        if scope_digest is not None and scope_digest == claim.subject_digest:
            return DisputeRuleApplicability.APPLIES
        return DisputeRuleApplicability.UNCERTAIN
    return DisputeRuleApplicability.UNCERTAIN


def _rule_interpretation(
    claim: DisputeClaim, ledger: DisputeLedger
) -> DisputeRuleInterpretation:
    evidence_kinds = {
        row.reference_kind
        for row in ledger.evidence
        if row.claim_ref == claim.claim_ref and row.active
    }
    if evidence_kinds & {
        DisputeEvidenceReferenceKind.DURABLE_RECORD,
        DisputeEvidenceReferenceKind.REPOSITORY_ENTRY,
        DisputeEvidenceReferenceKind.ARTIFACT,
    }:
        return DisputeRuleInterpretation.LITERAL
    if evidence_kinds & {
        DisputeEvidenceReferenceKind.INSTITUTION_RECORD,
        DisputeEvidenceReferenceKind.OFFICE_RECORD,
    }:
        return DisputeRuleInterpretation.CUSTOM
    return DisputeRuleInterpretation.UNKNOWN


def derive_rule_references(
    ledger: DisputeLedger,
    *,
    formal_rules: object | None,
    owner_id: AgentId | str,
    policy: DisputePolicy | None = None,
) -> DisputeLedger:
    """Resolve each cited rule against the owner's own formal-rule ledger."""

    if type(ledger) is not DisputeLedger:
        raise TypeError("ledger must be DisputeLedger")
    owner = _normalize_owner(owner_id)
    if ledger.owner_id != owner:
        _fail("dispute_owner_mismatch")
    locked = require_dispute_policy(policy)
    _reject_forbidden_input(formal_rules, owner=owner)
    rules = {
        getattr(rule, "rule_id", None): rule
        for rule in getattr(formal_rules, "rules", ()) or ()
    }
    references: dict[str, DisputeRuleReference] = {
        row.rule_reference_id: row for row in ledger.rule_references
    }
    for claim in ledger.claims:
        if not claim.active or claim.rule_reference_token is None:
            continue
        rule_id, version_number = _split_rule_token(claim.rule_reference_token)
        rule = rules.get(rule_id)
        system_ref = getattr(rule, "system_id", "unknown")
        constraint_kind = "unknown"
        scope_digest: str | None = None
        status = DisputeRuleReferenceStatus.ORPHANED
        version = None
        if rule is not None:
            versions = tuple(getattr(rule, "versions", ()) or ())
            if 1 <= version_number <= len(versions):
                candidate = versions[version_number - 1]
                if getattr(candidate, "version_number", None) == version_number:
                    version = candidate
                else:
                    status = DisputeRuleReferenceStatus.VERSION_MISMATCH
            else:
                status = DisputeRuleReferenceStatus.VERSION_MISMATCH
            if version is not None:
                constraint_kind = getattr(
                    getattr(version, "constraint", None), "value", "unknown"
                )
                scope = getattr(version, "scope", None)
                scope_digest = getattr(scope, "digest", None)
                rule_status = getattr(rule, "status", None)
                if getattr(rule_status, "value", None) == "retired":
                    status = DisputeRuleReferenceStatus.RETIRED
                elif getattr(rule_status, "value", None) == "contested":
                    status = DisputeRuleReferenceStatus.CONTESTED
                else:
                    status = DisputeRuleReferenceStatus.RESOLVED
        interpretation = _rule_interpretation(claim, ledger)
        reference = DisputeRuleReference(
            rule_reference_id=dispute_rule_reference_id(
                owner,
                claim.case_ref,
                system_ref,
                rule_id,
                version_number,
                interpretation,
            ),
            case_ref=claim.case_ref,
            claim_ref=claim.claim_ref,
            owner_id=owner,
            system_ref=system_ref,
            rule_id=rule_id,
            version_number=version_number,
            constraint_kind=constraint_kind,
            scope_digest=scope_digest,
            applicability=_rule_applicability(claim, constraint_kind, scope_digest),
            interpretation=interpretation,
            status=status,
            provenance=(
                DisputeProvenance.DERIVED_FROM_RULE
                if status
                in (
                    DisputeRuleReferenceStatus.RESOLVED,
                    DisputeRuleReferenceStatus.RETIRED,
                )
                else DisputeProvenance.ORPHANED
            ),
            first_tick=claim.first_tick,
            last_tick=claim.last_tick,
        )
        references[reference.rule_reference_id] = reference
    updated = replace(ledger, rule_references=tuple(references.values()))
    updated = enforce_dispute_limits(updated, locked)
    _LOG.debug(
        "dispute_reasoning_rules owner=%s references=%s",
        owner,
        len(updated.rule_references),
    )
    return updated


def _authority_strength(value: object) -> float:
    try:
        return _quantize_unit(value)
    except DisputeError:
        return 0.0


def _dissenting_office(concept: object) -> bool:
    status = getattr(getattr(concept, "status", None), "value", None)
    if status == "disputed":
        return True
    for occupant in getattr(concept, "occupants", ()) or ():
        if getattr(getattr(occupant, "status", None), "value", None) in {
            "opposed",
            "disputed",
        }:
            return True
    return False


def _collect_office_authorities(
    ledger: DisputeLedger,
    offices: object | None,
    owner: str,
) -> list[DisputeAuthorityReference]:
    references: list[DisputeAuthorityReference] = []
    for concept in getattr(offices, "concepts", ()) or ():
        if getattr(getattr(concept, "function", None), "value", None) != (
            "conflict_mediation"
        ):
            continue
        office_id = getattr(concept, "office_id", None)
        if type(office_id) is not str:
            continue
        context_key = getattr(concept, "context_key", None)
        strength = max(
            _authority_strength(getattr(concept, "endorsement_strength", 0.0)),
            _authority_strength(getattr(concept, "expectation_strength", 0.0)),
        )
        for case in ledger.cases:
            if context_key is not None and context_key != case.context_key:
                continue
            references.append(
                DisputeAuthorityReference(
                    authority_reference_id=dispute_authority_reference_id(
                        owner, case.case_ref, DisputeAuthorityKind.OFFICE, office_id
                    ),
                    case_ref=case.case_ref,
                    owner_id=owner,
                    authority_kind=DisputeAuthorityKind.OFFICE,
                    reference_id=office_id,
                    strength=strength,
                    uncertainty=_quantize_unit(1.0 - strength),
                    provenance=DisputeProvenance.DERIVED_FROM_OBSERVATION,
                    dissenting=_dissenting_office(concept),
                    first_tick=case.first_tick,
                    last_tick=case.last_tick,
                )
            )
    return references


def _collect_institution_authorities(
    ledger: DisputeLedger,
    institution_concepts: object | None,
    owner: str,
) -> list[DisputeAuthorityReference]:
    references: list[DisputeAuthorityReference] = []
    for concept in getattr(institution_concepts, "concepts", ()) or ():
        status = getattr(getattr(concept, "status", None), "value", None)
        if status not in {"recognized", "candidate"}:
            continue
        concept_id = getattr(concept, "concept_id", None)
        if type(concept_id) is not str:
            continue
        anchors = set(getattr(concept, "anchor_digests", ()) or ())
        legitimacy = _authority_strength(getattr(concept, "legitimacy_belief", 0.0))
        expectation = _authority_strength(getattr(concept, "social_expectation", 0.0))
        strength = _quantize_unit(0.5 * legitimacy + 0.5 * expectation)
        for case in ledger.cases:
            if case.subject_digest not in anchors:
                continue
            references.append(
                DisputeAuthorityReference(
                    authority_reference_id=dispute_authority_reference_id(
                        owner,
                        case.case_ref,
                        DisputeAuthorityKind.INSTITUTION,
                        concept_id,
                    ),
                    case_ref=case.case_ref,
                    owner_id=owner,
                    authority_kind=DisputeAuthorityKind.INSTITUTION,
                    reference_id=concept_id,
                    strength=strength,
                    uncertainty=_quantize_unit(1.0 - strength),
                    provenance=DisputeProvenance.DERIVED_FROM_OBSERVATION,
                    dissenting=status == "candidate",
                    first_tick=case.first_tick,
                    last_tick=case.last_tick,
                )
            )
    return references


def _collect_organization_authorities(
    ledger: DisputeLedger,
    organization_concepts: object | None,
    owner: str,
) -> list[DisputeAuthorityReference]:
    references: list[DisputeAuthorityReference] = []
    for concept in getattr(organization_concepts, "concepts", ()) or ():
        organization_id = getattr(concept, "organization_id", None)
        if type(organization_id) is not str:
            continue
        if not (
            getattr(concept, "procedures", ())
            or getattr(concept, "records", ())
            or getattr(concept, "roles", ())
        ):
            continue
        strength = _authority_strength(getattr(concept, "strength", 0.0))
        for case in ledger.cases:
            references.append(
                DisputeAuthorityReference(
                    authority_reference_id=dispute_authority_reference_id(
                        owner,
                        case.case_ref,
                        DisputeAuthorityKind.ORGANIZATION,
                        organization_id,
                    ),
                    case_ref=case.case_ref,
                    owner_id=owner,
                    authority_kind=DisputeAuthorityKind.ORGANIZATION,
                    reference_id=organization_id,
                    strength=strength,
                    uncertainty=_quantize_unit(1.0 - strength),
                    provenance=DisputeProvenance.DERIVED_FROM_OBSERVATION,
                    dissenting=False,
                    first_tick=case.first_tick,
                    last_tick=case.last_tick,
                )
            )
    return references


def _collect_collective_authorities(
    ledger: DisputeLedger,
    collective_decisions: object | None,
    owner: str,
) -> list[DisputeAuthorityReference]:
    references: list[DisputeAuthorityReference] = []
    proposals = tuple(getattr(collective_decisions, "proposals", ()) or ())
    for case in ledger.cases:
        claim_actions = {
            claim.action_token
            for claim in ledger.claims
            if claim.case_ref == case.case_ref and claim.action_token is not None
        }
        for proposal in proposals:
            action = getattr(proposal, "action_token", None)
            if action not in claim_actions:
                continue
            reference_id = getattr(proposal, "proposal_ref", None)
            if type(reference_id) is not str:
                continue
            references.append(
                DisputeAuthorityReference(
                    authority_reference_id=dispute_authority_reference_id(
                        owner,
                        case.case_ref,
                        DisputeAuthorityKind.COLLECTIVE_DECISION,
                        reference_id,
                    ),
                    case_ref=case.case_ref,
                    owner_id=owner,
                    authority_kind=DisputeAuthorityKind.COLLECTIVE_DECISION,
                    reference_id=reference_id,
                    strength=0.5,
                    uncertainty=0.5,
                    provenance=DisputeProvenance.DERIVED_FROM_RECORD,
                    dissenting=False,
                    first_tick=case.first_tick,
                    last_tick=case.last_tick,
                )
            )
    return references


def _collect_record_authorities(
    ledger: DisputeLedger, owner: str
) -> list[DisputeAuthorityReference]:
    references: list[DisputeAuthorityReference] = []
    for evidence in ledger.evidence:
        if evidence.reference_kind is DisputeEvidenceReferenceKind.REPOSITORY_ENTRY:
            kind = DisputeAuthorityKind.PROCEDURE
        elif evidence.reference_kind in {
            DisputeEvidenceReferenceKind.DURABLE_RECORD,
            DisputeEvidenceReferenceKind.ARTIFACT,
        }:
            kind = DisputeAuthorityKind.WRITTEN_RECORD
        else:
            continue
        references.append(
            DisputeAuthorityReference(
                authority_reference_id=dispute_authority_reference_id(
                    owner, evidence.case_ref, kind, evidence.reference_id
                ),
                case_ref=evidence.case_ref,
                owner_id=owner,
                authority_kind=kind,
                reference_id=evidence.reference_id,
                strength=0.5,
                uncertainty=0.5,
                provenance=DisputeProvenance.DERIVED_FROM_RECORD,
                dissenting=False,
                first_tick=evidence.tick,
                last_tick=evidence.tick,
            )
        )
    return references


def _collect_mediator_authorities(
    ledger: DisputeLedger,
    mediation: object | None,
    offices: object | None,
    institution_concepts: object | None,
    owner: str,
) -> list[DisputeAuthorityReference]:
    from agents.cognition.mediation import appraise_mediation_authority

    references: list[DisputeAuthorityReference] = []
    recommendations = tuple(getattr(mediation, "recommendations", ()) or ())
    for case in ledger.cases:
        mediator_token: str | None = None
        for recommendation in sorted(
            recommendations,
            key=lambda row: (
                getattr(row, "case_ref", ""),
                getattr(row, "revision", 0),
            ),
        ):
            candidate = getattr(recommendation, "originator_id", None)
            if candidate is None:
                candidate = getattr(recommendation, "proposed_actor_id", None)
            token = _token_of(candidate)
            if token is not None:
                mediator_token = token
                break
        if mediator_token is None:
            continue
        if mediator_token == owner:
            kind = DisputeAuthorityKind.SELF
            references.append(
                DisputeAuthorityReference(
                    authority_reference_id=dispute_authority_reference_id(
                        owner, case.case_ref, kind, owner
                    ),
                    case_ref=case.case_ref,
                    owner_id=owner,
                    authority_kind=kind,
                    reference_id=owner,
                    strength=1.0,
                    uncertainty=0.0,
                    provenance=DisputeProvenance.SELF_ASSERTED,
                    dissenting=False,
                    first_tick=case.first_tick,
                    last_tick=case.last_tick,
                )
            )
            continue
        appraisal = appraise_mediation_authority(
            AgentId(owner),
            AgentId(mediator_token),
            case.context_key,
            office_concepts=offices,
            institution_concepts=institution_concepts,
        )
        for component in appraisal.components:
            if not getattr(component, "available", False):
                continue
            channel = getattr(getattr(component, "channel", None), "value", "")
            kind = _AUTHORITY_CHANNEL_KIND.get(channel, DisputeAuthorityKind.UNKNOWN)
            reference_id = f"{mediator_token}:{channel}"
            references.append(
                DisputeAuthorityReference(
                    authority_reference_id=dispute_authority_reference_id(
                        owner, case.case_ref, kind, reference_id
                    ),
                    case_ref=case.case_ref,
                    owner_id=owner,
                    authority_kind=kind,
                    reference_id=reference_id,
                    strength=_authority_strength(getattr(component, "strength", 0.0)),
                    uncertainty=_authority_strength(
                        getattr(component, "uncertainty", 0.0)
                    ),
                    provenance=DisputeProvenance.DERIVED_FROM_MEDIATION,
                    dissenting=getattr(component, "dissenting", False) is True,
                    first_tick=case.first_tick,
                    last_tick=case.last_tick,
                )
            )
    return references


def derive_authority_references(
    ledger: DisputeLedger,
    *,
    owner_id: AgentId | str,
    offices: object | None,
    institution_concepts: object | None,
    organization_concepts: object | None,
    collective_decisions: object | None,
    mediation: object | None,
    tick: int,
    policy: DisputePolicy | None = None,
) -> DisputeLedger:
    """Cite existing institutional-role beliefs. No permission is granted."""

    if type(ledger) is not DisputeLedger:
        raise TypeError("ledger must be DisputeLedger")
    owner = _normalize_owner(owner_id)
    if ledger.owner_id != owner:
        _fail("dispute_owner_mismatch")
    locked = require_dispute_policy(policy)
    _ = _require_tick(tick)
    for value in (
        offices,
        institution_concepts,
        organization_concepts,
        collective_decisions,
        mediation,
    ):
        _reject_forbidden_input(value, owner=owner)
    references: dict[str, DisputeAuthorityReference] = {
        row.authority_reference_id: row for row in ledger.authority_references
    }
    for reference in (
        *_collect_office_authorities(ledger, offices, owner),
        *_collect_institution_authorities(ledger, institution_concepts, owner),
        *_collect_organization_authorities(ledger, organization_concepts, owner),
        *_collect_collective_authorities(ledger, collective_decisions, owner),
        *_collect_record_authorities(ledger, owner),
        *_collect_mediator_authorities(
            ledger, mediation, offices, institution_concepts, owner
        ),
    ):
        references[reference.authority_reference_id] = reference
    updated = replace(ledger, authority_references=tuple(references.values()))
    updated = enforce_dispute_limits(updated, locked)
    _LOG.debug(
        "dispute_reasoning_authorities owner=%s references=%s",
        owner,
        len(updated.authority_references),
    )
    return updated


def _mediation_case_status_token(mediation_case: object) -> str:
    return getattr(getattr(mediation_case, "status", None), "value", "unknown")


def _recommendation_term(recommendation: object) -> DisputeResolutionTerm:
    action_token = getattr(recommendation, "action_token", None)
    targets = tuple(getattr(recommendation, "target_ids", ()) or ())
    proposed = getattr(recommendation, "proposed_actor_id", None)
    party = _token_of(proposed) or "unknown"
    counterparty = (_token_of(targets[0]) if targets else None) or party
    if action_token == "give":
        kind = DisputeResolutionTermKind.TRANSFER_ITEM
    elif action_token is None:
        kind = DisputeResolutionTermKind.NO_ACTION
    else:
        kind = DisputeResolutionTermKind.PERFORM_SERVICE
    return DisputeResolutionTerm(
        term_kind=kind,
        party_id=party,
        counterparty_id=counterparty,
        item_token=getattr(recommendation, "item_token", None),
        service_token=(
            action_token if kind is DisputeResolutionTermKind.PERFORM_SERVICE else None
        ),
        action_token=action_token,
        quantity=0,
    )


def link_mediation_references(
    ledger: DisputeLedger,
    *,
    mediation: object | None,
    owner_id: AgentId | str,
    tick: int,
    policy: DisputePolicy | None = None,
) -> DisputeLedger:
    """Link the owner's own mediation cases as beliefs, never as decisions."""

    if type(ledger) is not DisputeLedger:
        raise TypeError("ledger must be DisputeLedger")
    owner = _normalize_owner(owner_id)
    if ledger.owner_id != owner:
        _fail("dispute_owner_mismatch")
    locked = require_dispute_policy(policy)
    absolute_tick = _require_tick(tick)
    _reject_forbidden_input(mediation, owner=owner)
    mediation_cases = tuple(getattr(mediation, "cases", ()) or ())
    recommendations = tuple(getattr(mediation, "recommendations", ()) or ())
    responses = tuple(getattr(mediation, "responses", ()) or ())
    outcomes = tuple(getattr(mediation, "outcomes", ()) or ())
    links: dict[str, DisputeMediationReference] = {
        row.mediation_reference_id: row for row in ledger.mediation_references
    }
    resolutions: dict[str, DisputeResolution] = {
        row.resolution_id: row for row in ledger.resolutions
    }
    for case in ledger.cases:
        match = None
        for mediation_case in sorted(
            mediation_cases, key=lambda row: getattr(row, "case_id", "")
        ):
            case_ref = getattr(mediation_case, "case_ref", None)
            if any(
                link.case_ref == case.case_ref and link.mediation_case_ref == case_ref
                for link in links.values()
            ):
                match = mediation_case
                break
            if getattr(
                mediation_case, "subject_token", None
            ) == case.subject_token and set(
                _token_of(party) or ""
                for party in getattr(mediation_case, "party_ids", ()) or ()
            ) & set(case.party_ids):
                match = mediation_case
                break
        if match is None:
            continue
        mediation_case_ref = getattr(match, "case_ref", None)
        if type(mediation_case_ref) is not str:
            continue
        case_recommendations = tuple(
            row
            for row in recommendations
            if getattr(row, "case_ref", None) == mediation_case_ref
        )
        recommendation = None
        for row in case_recommendations:
            if recommendation is None or getattr(row, "revision", 0) > getattr(
                recommendation, "revision", 0
            ):
                recommendation = row
        response = None
        for row in responses:
            if getattr(row, "case_ref", None) != mediation_case_ref:
                continue
            if response is None or getattr(row, "tick", 0) >= getattr(
                response, "tick", 0
            ):
                response = row
        outcome = None
        for row in outcomes:
            if getattr(row, "case_ref", None) != mediation_case_ref:
                continue
            if outcome is None or getattr(row, "tick", 0) >= getattr(
                outcome, "tick", 0
            ):
                outcome = row
        recommendation_id = (
            None
            if recommendation is None
            else getattr(recommendation, "recommendation_id", None)
        )
        status_token = _mediation_case_status_token(match)
        if status_token == "disputed":
            link_status = DisputeMediationLinkStatus.DISPUTED
        elif status_token in {"stale", "retired", "abandoned"}:
            link_status = DisputeMediationLinkStatus.STALE
        else:
            link_status = DisputeMediationLinkStatus.LINKED
        link = DisputeMediationReference(
            mediation_reference_id=dispute_mediation_reference_id(
                owner,
                case.case_ref,
                mediation_case_ref,
                "none" if recommendation_id is None else recommendation_id,
            ),
            case_ref=case.case_ref,
            owner_id=owner,
            mediation_case_ref=mediation_case_ref,
            recommendation_ref=recommendation_id,
            response_ref=(
                None if response is None else getattr(response, "response_id", None)
            ),
            outcome_ref=(
                None if outcome is None else getattr(outcome, "outcome_id", None)
            ),
            link_status=link_status,
            provenance=DisputeProvenance.DERIVED_FROM_MEDIATION,
            first_tick=case.first_tick,
            last_tick=max(case.last_tick, absolute_tick),
        )
        links[link.mediation_reference_id] = link
        if recommendation is not None:
            proposer = _token_of(
                getattr(recommendation, "originator_id", None)
            ) or _token_of(getattr(recommendation, "proposed_actor_id", None))
            if proposer is not None:
                term = _recommendation_term(recommendation)
                terms = (term,)
                terms_digest = dispute_terms_digest(terms)
                resolution_ref = dispute_resolution_ref(
                    case.case_ref, proposer, terms_digest
                )
                resolution = DisputeResolution(
                    resolution_id=dispute_resolution_id(owner, resolution_ref),
                    resolution_ref=resolution_ref,
                    case_ref=case.case_ref,
                    owner_id=owner,
                    proposer_id=proposer,
                    source=DisputeResolutionSource.MEDIATOR,
                    terms=terms,
                    terms_digest=terms_digest,
                    status=DisputeResolutionStatus.PROPOSED,
                    first_tick=case.first_tick,
                    last_tick=absolute_tick,
                    expires_tick=absolute_tick + locked.resolution_window_ticks,
                    provenance=DisputeProvenance.DERIVED_FROM_MEDIATION,
                )
                resolutions.setdefault(resolution.resolution_id, resolution)
    updated = replace(
        ledger,
        mediation_references=tuple(links.values()),
        resolutions=tuple(resolutions.values()),
    )
    updated = enforce_dispute_limits(updated, locked)
    _LOG.debug(
        "dispute_reasoning_mediation owner=%s links=%s resolutions=%s",
        owner,
        len(updated.mediation_references),
        len(updated.resolutions),
    )
    return updated


def derive_case_status(
    case: DisputeCase,
    claims: Sequence[DisputeClaim],
    resolutions: Sequence[DisputeResolution],
    responses: Sequence[DisputeResolutionResponse],
    tick: int,
) -> DisputeStatus:
    """Derive the owner-local lifecycle. Never returns an unhedged ``resolved``."""

    if type(case) is not DisputeCase:
        raise TypeError("case must be DisputeCase")
    absolute_tick = _require_tick(tick)
    return _case_status(case, claims, resolutions, responses, absolute_tick)


def dispute_direction_preference(
    ledger: DisputeLedger,
    *,
    owner_id: AgentId | str,
    tick: int,
) -> dict[str, float]:
    """Return a bounded hint to keep talking about open claims."""

    if type(ledger) is not DisputeLedger:
        raise TypeError("ledger must be DisputeLedger")
    owner = _normalize_owner(owner_id)
    if ledger.owner_id != owner:
        _fail("dispute_owner_mismatch")
    _ = _require_tick(tick)
    open_cases = {case.case_ref for case in ledger.open_cases}
    open_claims = tuple(
        claim
        for claim in ledger.claims
        if claim.active and claim.case_ref in open_cases
    )
    if not open_claims:
        return {}
    bonus = min(0.25, 0.05 * len(open_claims))
    return {"ask": bonus, "communicate": bonus, "tell": bonus}


def dispute_response_penalties(
    ledger: DisputeLedger,
    *,
    owner_id: AgentId | str,
    resolution_ref: str | None = None,
    tick: int | None = None,
) -> dict[str, float]:
    """Return a bounded penalty for accepting an unknown or expired resolution."""

    if type(ledger) is not DisputeLedger:
        raise TypeError("ledger must be DisputeLedger")
    owner = _normalize_owner(owner_id)
    if ledger.owner_id != owner:
        _fail("dispute_owner_mismatch")
    absolute_tick = 0 if tick is None else _require_tick(tick)
    if resolution_ref is None:
        return {}
    resolution = next(
        (row for row in ledger.resolutions if row.resolution_ref == resolution_ref),
        None,
    )
    if resolution is None:
        return {"accept": -0.2}
    if resolution.expires_tick is not None and absolute_tick > resolution.expires_tick:
        return {"accept": -0.2}
    return {}


def dispute_case_summary(
    case: DisputeCase,
    claims: Sequence[DisputeClaim],
    resolutions: Sequence[DisputeResolution],
) -> dict[str, int]:
    """Return deterministic count-only analysis handoff fields."""

    if type(case) is not DisputeCase:
        raise TypeError("case must be DisputeCase")
    case_claims = tuple(claim for claim in claims if claim.case_ref == case.case_ref)
    case_resolutions = tuple(
        row for row in resolutions if row.case_ref == case.case_ref
    )
    return {
        "active_claim_count": sum(1 for claim in case_claims if claim.active),
        "active_resolution_count": sum(1 for row in case_resolutions if row.is_open),
        "claim_count": len(case_claims),
        "counterclaim_count": sum(
            1 for claim in case_claims if claim.role is DisputeClaimRole.COUNTERCLAIM
        ),
        "resolution_count": len(case_resolutions),
    }


# ---------------------------------------------------------------------------
# Proposed resolutions and per-party declarations
# ---------------------------------------------------------------------------


def _require_known_case(ledger: DisputeLedger, case_ref: str) -> DisputeCase:
    for case in ledger.cases:
        if case.case_ref == case_ref:
            return case
    _fail("dispute_unknown_reference")


def propose_dispute_resolution(
    ledger: DisputeLedger,
    *,
    owner_id: AgentId | str,
    case_ref: str,
    proposer_id: str,
    source: str,
    terms: Sequence[DisputeResolutionTerm],
    tick: int,
    expires_tick: int | None = None,
    policy: DisputePolicy | None = None,
) -> DisputeLedger:
    """Propose one owner-local resolution. It is never binding."""

    if type(ledger) is not DisputeLedger:
        raise TypeError("ledger must be DisputeLedger")
    owner = _normalize_owner(owner_id)
    if ledger.owner_id != owner:
        _fail("dispute_owner_mismatch")
    absolute_tick = _require_tick(tick)
    locked = require_dispute_policy(policy)
    case = _require_known_case(ledger, require_dispute_case_ref(case_ref))
    proposer = _require_reference(proposer_id)
    if type(source) is DisputeResolutionSource:
        source_kind = source
    elif type(source) is str:
        try:
            source_kind = DisputeResolutionSource(source)
        except ValueError:
            _fail("dispute_invalid_mode")
    else:
        _fail("dispute_invalid_mode")
    if type(proposer) is str and proposer != owner and proposer not in case.party_ids:
        if source_kind is not DisputeResolutionSource.MEDIATOR:
            _fail("dispute_unknown_reference")
    if isinstance(terms, (str, bytes)) or not isinstance(terms, (tuple, list)):
        _fail("dispute_term_limit")
    checked_terms: list[DisputeResolutionTerm] = []
    for term in terms:
        if type(term) is not DisputeResolutionTerm:
            _fail("dispute_invalid_record")
        checked_terms.append(term)
    if len(checked_terms) > locked.max_terms_per_resolution:
        _fail("dispute_term_limit")
    ordered_terms = tuple(sorted(checked_terms, key=_terms_sort_key))
    terms_digest = dispute_terms_digest(ordered_terms)
    resolution_ref = dispute_resolution_ref(case.case_ref, proposer, terms_digest)
    resolution_id = dispute_resolution_id(owner, resolution_ref)
    expires = (
        absolute_tick + locked.resolution_window_ticks
        if expires_tick is None
        else _require_tick(expires_tick)
    )
    draft = _empty_draft(ledger)
    draft["notices"] = list(ledger.notices)
    for key, existing in list(draft["resolutions"].items()):
        if (
            existing.case_ref == case.case_ref
            and existing.proposer_id == proposer
            and existing.status is DisputeResolutionStatus.PROPOSED
            and existing.resolution_id != resolution_id
        ):
            draft["resolutions"][key] = replace(
                existing, status=DisputeResolutionStatus.SUPERSEDED
            )
    existing = draft["resolutions"].get(resolution_id)
    if existing is not None and type(existing) is DisputeResolution:
        resolution = replace(existing, last_tick=max(existing.last_tick, absolute_tick))
    else:
        resolution = DisputeResolution(
            resolution_id=resolution_id,
            resolution_ref=resolution_ref,
            case_ref=case.case_ref,
            owner_id=owner,
            proposer_id=proposer,
            source=source_kind,
            terms=ordered_terms,
            terms_digest=terms_digest,
            status=DisputeResolutionStatus.PROPOSED,
            first_tick=absolute_tick,
            last_tick=absolute_tick,
            expires_tick=expires,
            provenance=DisputeProvenance.SELF_ASSERTED,
        )
    draft["resolutions"][resolution_id] = resolution
    updated = _refresh_draft(draft, owner=owner, tick=absolute_tick, prior=ledger)
    return enforce_dispute_limits(updated, locked)


def _find_resolution(ledger: DisputeLedger, resolution_ref: str) -> DisputeResolution:
    for resolution in ledger.resolutions:
        if resolution.resolution_ref == resolution_ref:
            return resolution
    _fail("dispute_unknown_reference")


def record_dispute_resolution_response(
    ledger: DisputeLedger,
    *,
    owner_id: AgentId | str,
    resolution_ref: str,
    party_id: str,
    kind: str,
    tick: int,
    terms_digest: str,
    verified_speaker: str | None = None,
    counter_resolution_ref: str | None = None,
    policy: DisputePolicy | None = None,
) -> DisputeLedger:
    """Record one party's accept, reject, counter, defer, or withdraw."""

    if type(ledger) is not DisputeLedger:
        raise TypeError("ledger must be DisputeLedger")
    owner = _normalize_owner(owner_id)
    if ledger.owner_id != owner:
        _fail("dispute_owner_mismatch")
    absolute_tick = _require_tick(tick)
    locked = require_dispute_policy(policy)
    resolution = _find_resolution(
        ledger, require_dispute_resolution_ref(resolution_ref)
    )
    party = _require_reference(party_id)
    if verified_speaker is not None and party != verified_speaker:
        draft = _empty_draft(ledger)
        draft["notices"] = [*ledger.notices, "dispute_party_mismatch"]
        return _refresh_draft(draft, owner=owner, tick=absolute_tick, prior=ledger)
    if verified_speaker is None and party != owner:
        draft = _empty_draft(ledger)
        draft["notices"] = [*ledger.notices, "dispute_party_mismatch"]
        return _refresh_draft(draft, owner=owner, tick=absolute_tick, prior=ledger)
    if _require_digest(terms_digest) != resolution.terms_digest:
        draft = _empty_draft(ledger)
        draft["notices"] = [*ledger.notices, "dispute_terms_mismatch"]
        return _refresh_draft(draft, owner=owner, tick=absolute_tick, prior=ledger)
    if resolution.first_tick == absolute_tick and resolution.proposer_id != party:
        draft = _empty_draft(ledger)
        draft["notices"] = [
            *ledger.notices,
            "dispute_resolution_requires_prior_tick",
        ]
        return _refresh_draft(draft, owner=owner, tick=absolute_tick, prior=ledger)
    kind_value = (
        kind
        if type(kind) is DisputeResolutionResponseKind
        else DisputeResolutionResponseKind(str(kind))
    )
    if (
        kind_value is DisputeResolutionResponseKind.COUNTERPROPOSE
        and counter_resolution_ref is None
    ):
        _fail("dispute_response_invalid")
    if counter_resolution_ref is not None:
        _find_resolution(ledger, require_dispute_resolution_ref(counter_resolution_ref))
    draft = _empty_draft(ledger)
    draft["notices"] = list(ledger.notices)
    if kind_value is DisputeResolutionResponseKind.WITHDRAW and (
        party != resolution.proposer_id
    ):
        for key, response in list(draft["resolution_responses"].items()):
            if (
                response.resolution_ref == resolution.resolution_ref
                and response.party_id == party
                and response.active
            ):
                draft["resolution_responses"][key] = replace(response, active=False)
        updated = _refresh_draft(draft, owner=owner, tick=absolute_tick, prior=ledger)
        return enforce_dispute_limits(updated, locked)
    for key, response in list(draft["resolution_responses"].items()):
        if (
            response.resolution_ref == resolution.resolution_ref
            and response.party_id == party
            and response.active
        ):
            draft["resolution_responses"][key] = replace(response, active=False)
    response = DisputeResolutionResponse(
        response_id=dispute_response_id(
            owner, resolution.resolution_ref, party, kind_value, absolute_tick
        ),
        resolution_id=resolution.resolution_id,
        resolution_ref=resolution.resolution_ref,
        case_ref=resolution.case_ref,
        owner_id=owner,
        party_id=party,
        kind=kind_value,
        tick=absolute_tick,
        terms_digest=resolution.terms_digest,
        active=True,
        provenance=DisputeProvenance.SELF_ASSERTED,
        counter_resolution_ref=(
            None
            if counter_resolution_ref is None
            else require_dispute_resolution_ref(counter_resolution_ref)
        ),
    )
    draft["resolution_responses"][response.response_id] = response
    updated = _refresh_draft(draft, owner=owner, tick=absolute_tick, prior=ledger)
    return enforce_dispute_limits(updated, locked)


def expire_dispute_resolutions(
    ledger: DisputeLedger,
    tick: int,
    policy: DisputePolicy | None = None,
) -> DisputeLedger:
    """Mark open resolutions expired after their bounded window."""

    if type(ledger) is not DisputeLedger:
        raise TypeError("ledger must be DisputeLedger")
    owner = ledger.owner_id
    absolute_tick = _require_tick(tick)
    locked = require_dispute_policy(policy)
    draft = _empty_draft(ledger)
    draft["notices"] = list(ledger.notices)
    for key, resolution in list(draft["resolutions"].items()):
        if (
            resolution.status
            in (
                DisputeResolutionStatus.PROPOSED,
                DisputeResolutionStatus.PARTIALLY_ACCEPTED,
            )
            and resolution.expires_tick is not None
            and absolute_tick > resolution.expires_tick
        ):
            draft["resolutions"][key] = replace(
                resolution, status=DisputeResolutionStatus.EXPIRED
            )
    updated = _refresh_draft(draft, owner=owner, tick=absolute_tick, prior=ledger)
    return enforce_dispute_limits(updated, locked)


def supersede_dispute_resolutions(
    ledger: DisputeLedger,
    *,
    owner_id: AgentId | str,
    resolution_ref: str,
    superseded_by_ref: str,
    tick: int,
    policy: DisputePolicy | None = None,
) -> DisputeLedger:
    """Mark one older proposal superseded by a newer proposal."""

    if type(ledger) is not DisputeLedger:
        raise TypeError("ledger must be DisputeLedger")
    owner = _normalize_owner(owner_id)
    if ledger.owner_id != owner:
        _fail("dispute_owner_mismatch")
    absolute_tick = _require_tick(tick)
    locked = require_dispute_policy(policy)
    older = _find_resolution(ledger, require_dispute_resolution_ref(resolution_ref))
    newer = _find_resolution(ledger, require_dispute_resolution_ref(superseded_by_ref))
    if older.case_ref != newer.case_ref:
        _fail("dispute_unknown_reference")
    draft = _empty_draft(ledger)
    draft["notices"] = list(ledger.notices)
    draft["resolutions"][older.resolution_id] = replace(
        older, status=DisputeResolutionStatus.SUPERSEDED
    )
    updated = _refresh_draft(draft, owner=owner, tick=absolute_tick, prior=ledger)
    return enforce_dispute_limits(updated, locked)


def compile_dispute_undertaking(
    ledger: DisputeLedger,
    *,
    owner_id: AgentId | str,
    tick: int,
    identity: object,
    inventory: object,
    mediation: object,
) -> tuple[DisputeResolution, object] | None:
    """Compile only the exact apparently accepted mediation undertaking.

    Every supported path delegates to ``compile_mediation_undertaking``; this
    helper never constructs an ``AgentCommand`` itself.
    """

    from agents.cognition.mediation import MediationLedger
    from agents.cognition.mediation_actions import compile_mediation_undertaking

    if type(ledger) is not DisputeLedger:
        raise TypeError("ledger must be DisputeLedger")
    owner = _normalize_owner(owner_id)
    if ledger.owner_id != owner:
        _fail("dispute_owner_mismatch")
    absolute_tick = _require_tick(tick)
    if type(mediation) is not MediationLedger:
        return None
    recommendations = {
        getattr(row, "recommendation_id", None): row
        for row in mediation.recommendations
    }
    for resolution in sorted(ledger.resolutions, key=lambda row: row.resolution_id):
        if resolution.status is not DisputeResolutionStatus.APPARENTLY_ACCEPTED:
            continue
        match_terms = tuple(
            term
            for term in resolution.terms
            if term.term_kind
            in (
                DisputeResolutionTermKind.TRANSFER_ITEM,
                DisputeResolutionTermKind.RETURN_ITEM,
            )
            and term.party_id == owner
        )
        if len(match_terms) != 1:
            continue
        term = match_terms[0]
        if term.item_token is None or term.counterparty_id == owner:
            continue
        recommendation_id = None
        for link in ledger.mediation_references:
            if (
                link.case_ref == resolution.case_ref
                and link.link_status is DisputeMediationLinkStatus.LINKED
                and link.recommendation_ref is not None
            ):
                recommendation_id = link.recommendation_ref
                break
        if recommendation_id is None:
            continue
        recommendation = recommendations.get(recommendation_id)
        if recommendation is None:
            continue
        if getattr(recommendation, "action_token", None) != "give":
            continue
        targets = tuple(getattr(recommendation, "target_ids", ()) or ())
        if not targets or _token_of(targets[0]) != term.counterparty_id:
            continue
        if getattr(recommendation, "item_token", None) != term.item_token:
            continue
        try:
            compiled = compile_mediation_undertaking(
                mediation,
                owner_id=AgentId(owner),
                tick=absolute_tick,
                identity=identity,  # type: ignore[arg-type]
                inventory=inventory,  # type: ignore[arg-type]
            )
        except (TypeError, ValueError):
            _LOG.debug("dispute_undertaking_skipped reason=%s", "unsupported_terms")
            return None
        if compiled is None:
            return None
        selected, command = compiled
        if getattr(selected, "recommendation_id", None) != recommendation_id:
            return None
        return resolution, command
    return None
