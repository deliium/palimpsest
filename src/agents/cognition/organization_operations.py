"""Closed owner-scoped organization operation vocabulary.

An organization operation is a belief one agent holds about a socially
recognized act: who may use or store a resource, who keeps a record, who was
admitted or departed, who holds a role, which procedure was invoked, and which
internal commitment exists. It is never objective organization state, never a
resource pool, and never a command source.

This module defines only the frozen vocabulary, identity grammar, policy bounds,
and error codes that later organization operation code consumes. It creates no
objective organization entity, roster, treasury, registry, command, permission,
or executor. Every physical effect remains an ordinary agent command admitted by
``WorldEngine``; objective custody and storage remain the existing world fields.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Final, NoReturn

from agents.cognition.organization_concepts import (
    FORBIDDEN_ORGANIZATION_FIELD_NAMES,
    ORGANIZATION_ID_HEX_LEN,
    OrganizationCommitmentRole,
    OrganizationTemporalScope,
)
from agents.models import AgentId

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.organization_operations"
)

ORGANIZATION_OPERATION_POLICY_VERSION: Final[str] = "organization-operations.v1"
ORGANIZATION_OPERATION_ANALYSIS_POLICY_VERSION: Final[str] = (
    "organization-operations-analysis.v1"
)

ORGANIZATION_DECISION_ID_PREFIX: Final[str] = "orgd-"
ORGANIZATION_ACTION_ID_PREFIX: Final[str] = "orga-"
ORGANIZATION_PUBLICATION_OPERATION_ID_PREFIX: Final[str] = "orgop-"
ORGANIZATION_OPERATION_EVIDENCE_ID_PREFIX: Final[str] = "orgev-"

_DECISION_NAMESPACE: Final[str] = "palimpsest.organization.decision.v1"
_ACTION_NAMESPACE: Final[str] = "palimpsest.organization.action.v1"
_PUBLICATION_NAMESPACE: Final[str] = "palimpsest.organization.publication-operation.v1"
_EVIDENCE_NAMESPACE: Final[str] = "palimpsest.organization.operation-evidence.v1"
_REF_NAMESPACE: Final[str] = "palimpsest.organization.operation-ref.v1"

_DECISION_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{ORGANIZATION_DECISION_ID_PREFIX}[0-9a-f]{{{ORGANIZATION_ID_HEX_LEN}}}$"
)
_ACTION_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{ORGANIZATION_ACTION_ID_PREFIX}[0-9a-f]{{{ORGANIZATION_ID_HEX_LEN}}}$"
)
_PUBLICATION_OPERATION_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{ORGANIZATION_PUBLICATION_OPERATION_ID_PREFIX}"
    rf"[0-9a-f]{{{ORGANIZATION_ID_HEX_LEN}}}$"
)
_EVIDENCE_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{ORGANIZATION_OPERATION_EVIDENCE_ID_PREFIX}"
    rf"[0-9a-f]{{{ORGANIZATION_ID_HEX_LEN}}}$"
)
_REF_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^[0-9a-f]{{{ORGANIZATION_ID_HEX_LEN}}}$"
)

ORGANIZATION_OPERATION_REF_NAMESPACES: Final[frozenset[str]] = frozenset(
    {
        "target",
        "anchor",
        "role_signature",
        "decision_content",
    }
)


class OrganizationOperationDomain(StrEnum):
    """Closed operational domain; exactly the eight requested primitives."""

    RESOURCE_CONTROL = "resource_control"
    STORAGE = "storage"
    RECORD_KEEPING = "record_keeping"
    MEMBERSHIP_ADMISSION = "membership_admission"
    MEMBERSHIP_DEPARTURE = "membership_departure"
    ROLE_ASSIGNMENT = "role_assignment"
    PROCEDURE_ACTION = "procedure_action"
    INTERNAL_COMMITMENT = "internal_commitment"


class OrganizationOperationAct(StrEnum):
    """Closed recognized act an owner may believe an organization performed."""

    ADMIT = "admit"
    DEPART = "depart"
    ASSIGN = "assign"
    REMOVE = "remove"
    AUTHORIZE_CONTROL = "authorize_control"
    REVOKE_CONTROL = "revoke_control"
    INVOKE_PROCEDURE = "invoke_procedure"
    DECLARE_COMMITMENT = "declare_commitment"
    FULFILL_COMMITMENT = "fulfill_commitment"
    RECORD_DECISION = "record_decision"


class OrganizationControlStance(StrEnum):
    """Closed owner stance toward a believed legitimate control relation."""

    CLAIMED = "claimed"
    RECOGNIZED = "recognized"
    SHARED = "shared"
    DISPUTED = "disputed"
    FORMER = "former"
    UNKNOWN = "unknown"


class OrganizationAdmissionStance(StrEnum):
    """Closed owner stance toward a believed admission; never a permission."""

    ADMITTED = "admitted"
    CLAIMED = "claimed"
    SELF_JOINED = "self_joined"
    DENIED = "denied"
    DISPUTED = "disputed"
    FORMER = "former"
    UNKNOWN = "unknown"


class OrganizationDepartureStance(StrEnum):
    """Closed owner stance toward a believed membership departure."""

    RESIGNED = "resigned"
    EXPELLED = "expelled"
    DEPARTED = "departed"
    DISPUTED = "disputed"
    UNKNOWN = "unknown"


class OrganizationAssignmentStance(StrEnum):
    """Closed owner stance toward a believed role assignment."""

    ASSIGNED = "assigned"
    CLAIMED = "claimed"
    DISPUTED = "disputed"
    REMOVED = "removed"
    VACANT = "vacant"
    UNKNOWN = "unknown"


class OrganizationCommitmentStance(StrEnum):
    """Closed owner stance toward a believed internal commitment."""

    DECLARED = "declared"
    ACCEPTED = "accepted"
    FULFILLED = "fulfilled"
    VIOLATED = "violated"
    DISPUTED = "disputed"
    FORGOTTEN = "forgotten"
    UNKNOWN = "unknown"


class OrganizationAuthorityBasis(StrEnum):
    """Closed reason the owner believes an act was authorized.

    This describes an owner's belief; it is not a permission and is never
    checked by the world.
    """

    SELF_AUTHORED = "self_authored"
    ROLE_BELIEF = "role_belief"
    DECISION_BELIEF = "decision_belief"
    PROCEDURE_BELIEF = "procedure_belief"
    RECORD_REFERENCE = "record_reference"
    OBSERVATION = "observation"
    UNKNOWN = "unknown"


class OrganizationOperationOutcome(StrEnum):
    """Closed believed outcome of one operational act."""

    OBSERVED = "observed"
    ATTEMPTED = "attempted"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class OrganizationOperationProvenance(StrEnum):
    """Closed provenance code for one believed decision or action."""

    SELF_AUTHORED = "self_authored"
    ROLE_AUTHORIZED = "role_authorized"
    DECISION_SUPPORTED = "decision_supported"
    PROCEDURE_RECOGNIZED = "procedure_recognized"
    OBSERVED_EFFECT = "observed_effect"
    UNKNOWN_AUTHORITY = "unknown_authority"
    CONTESTED = "contested"
    EXPIRED = "expired"
    ORPHANED = "orphaned"


ORGANIZATION_LEGITIMACY_DOCTRINES: Final[frozenset[str]] = frozenset(
    {
        "none",
        "group_owns",
        "role_trusteeship",
        "decision_grant",
        "first_claimant_owns",
        "shared_use",
        "unknown",
    }
)

ORGANIZATION_OPERATION_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "organization_operation_invalid",
        "organization_operation_policy_mismatch",
        "organization_operation_foreign_ledger",
        "organization_operation_cap_exceeded",
        "organization_operation_unknown_concept",
        "organization_operation_unknown_decision",
        "organization_operation_tick_regression",
        "organization_operation_invalid_ref",
        "organization_duplicate_operation",
    }
)


class OrganizationOperationError(ValueError):
    """Stable-code organization operation violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        if code not in ORGANIZATION_OPERATION_ERROR_CODES:
            raise ValueError("organization_operation_invalid")
        self.code: str = code
        super().__init__(code)


def _fail(code: str) -> NoReturn:
    raise OrganizationOperationError(code)


@dataclass(frozen=True, slots=True)
class OrganizationOperationPolicy:
    """Locked owner-local organization operation bounds.

    Every value is part of the accepted contract. Any deviation is a programming
    error and fails closed. The policy has no ``version`` field; the module
    constant ``ORGANIZATION_OPERATION_POLICY_VERSION`` is authoritative.
    """

    max_concepts: int = 16
    max_controls: int = 32
    max_admissions: int = 32
    max_departures: int = 32
    max_assignments: int = 16
    max_procedures: int = 16
    max_commitments: int = 16
    max_decisions: int = 32
    max_actions: int = 64
    max_evidence_per_record: int = 8
    max_total_evidence: int = 256
    max_total_records: int = 256
    max_owner_support: int = 32
    max_contest: int = 32

    def __post_init__(self) -> None:
        for name, expected in _LOCKED_OPERATION_POLICY_VALUES.items():
            actual = getattr(self, name)
            if type(actual) is not type(expected) or actual != expected:
                _fail("organization_operation_policy_mismatch")


_LOCKED_OPERATION_POLICY_VALUES: Final[Mapping[str, int]] = MappingProxyType(
    {
        "max_concepts": 16,
        "max_controls": 32,
        "max_admissions": 32,
        "max_departures": 32,
        "max_assignments": 16,
        "max_procedures": 16,
        "max_commitments": 16,
        "max_decisions": 32,
        "max_actions": 64,
        "max_evidence_per_record": 8,
        "max_total_evidence": 256,
        "max_total_records": 256,
        "max_owner_support": 32,
        "max_contest": 32,
    }
)

_DEFAULT_OPERATION_POLICY: Final[OrganizationOperationPolicy] = (
    OrganizationOperationPolicy()
)
_POLICY_MILESTONE_LOGGED: bool = False


def default_organization_operation_policy() -> OrganizationOperationPolicy:
    """Return the single locked operation policy instance."""

    global _POLICY_MILESTONE_LOGGED
    if not _POLICY_MILESTONE_LOGGED:
        _POLICY_MILESTONE_LOGGED = True
        _LOG.debug(
            "organization_operation_policy mode=contract domains=%s cap_concepts=%s",
            len(OrganizationOperationDomain),
            _DEFAULT_OPERATION_POLICY.max_concepts,
        )
    return _DEFAULT_OPERATION_POLICY


def _require_text(value: object, code: str) -> str:
    if type(value) is not str or not value:
        _fail(code)
    return value


def _material_token(value: object, code: str) -> str:
    if isinstance(value, StrEnum):
        return value.value
    if type(value) is not str or not value:
        _fail(code)
    return value


def _optional_material_token(value: object, code: str) -> str:
    if isinstance(value, StrEnum):
        return value.value
    if type(value) is not str:
        _fail(code)
    return value


def require_organization_tick(value: object) -> int:
    """Require an exact non-negative tick; booleans are rejected."""

    if type(value) is not int or value < 0:
        _fail("organization_operation_tick_regression")
    return value


def _digest(namespace: str, material: tuple[str, ...]) -> str:
    payload = "\x1f".join((namespace, *material))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:ORGANIZATION_ID_HEX_LEN]


def organization_decision_id(
    owner_id: str,
    organization_id: str,
    domain: str,
    act: str,
    tick: int,
    actor_id: str,
    target_id: str,
    anchor_kind: str,
    anchor_id: str,
    stance: str,
) -> str:
    """Mint one owner-local ``orgd-`` decision id from its material."""

    body = _digest(
        _DECISION_NAMESPACE,
        (
            _require_text(owner_id, "organization_operation_invalid"),
            _require_text(organization_id, "organization_operation_invalid"),
            _material_token(domain, "organization_operation_invalid"),
            _material_token(act, "organization_operation_invalid"),
            str(require_organization_tick(tick)),
            _require_text(actor_id, "organization_operation_invalid"),
            _optional_material_token(target_id, "organization_operation_invalid"),
            _require_text(anchor_kind, "organization_operation_invalid"),
            _optional_material_token(anchor_id, "organization_operation_invalid"),
            _material_token(stance, "organization_operation_invalid"),
        ),
    )
    return f"{ORGANIZATION_DECISION_ID_PREFIX}{body}"


def organization_action_id(
    owner_id: str,
    organization_id: str,
    decision_id: str,
    tick: int,
    actor_id: str,
    command_kind: str,
    anchor_kind: str,
    anchor_id: str,
) -> str:
    """Mint one owner-local ``orga-`` action id from its observed material."""

    body = _digest(
        _ACTION_NAMESPACE,
        (
            _require_text(owner_id, "organization_operation_invalid"),
            _require_text(organization_id, "organization_operation_invalid"),
            require_organization_decision_id(decision_id),
            str(require_organization_tick(tick)),
            _require_text(actor_id, "organization_operation_invalid"),
            _material_token(command_kind, "organization_operation_invalid"),
            _require_text(anchor_kind, "organization_operation_invalid"),
            _optional_material_token(anchor_id, "organization_operation_invalid"),
        ),
    )
    return f"{ORGANIZATION_ACTION_ID_PREFIX}{body}"


def organization_publication_operation_id(
    organization_id: str,
    domain: str,
    tick: int,
    ordinal: int,
    content_digest: str,
) -> str:
    """Mint one deterministic published ``orgop-`` operation id."""

    if type(ordinal) is not int or ordinal < 0:
        _fail("organization_operation_invalid")
    body = _digest(
        _PUBLICATION_NAMESPACE,
        (
            _require_text(organization_id, "organization_operation_invalid"),
            _material_token(domain, "organization_operation_invalid"),
            str(require_organization_tick(tick)),
            str(ordinal),
            _require_text(content_digest, "organization_operation_invalid"),
        ),
    )
    return f"{ORGANIZATION_PUBLICATION_OPERATION_ID_PREFIX}{body}"


def organization_operation_evidence_id(
    owner_id: str,
    organization_id: str,
    source: str,
    tick: int,
    ordinal: int,
    ref: str,
) -> str:
    """Mint one owner-local ``orgev-`` evidence id from its material."""

    if type(ordinal) is not int or ordinal < 0:
        _fail("organization_operation_invalid")
    body = _digest(
        _EVIDENCE_NAMESPACE,
        (
            _require_text(owner_id, "organization_operation_invalid"),
            _require_text(organization_id, "organization_operation_invalid"),
            _material_token(source, "organization_operation_invalid"),
            str(require_organization_tick(tick)),
            str(ordinal),
            _require_text(ref, "organization_operation_invalid"),
        ),
    )
    return f"{ORGANIZATION_OPERATION_EVIDENCE_ID_PREFIX}{body}"


def organization_operation_ref(value: str, *, namespace: str) -> str:
    """Return a bounded 16-hex reference for one speech frame field.

    ``namespace`` must be exactly ``target``, ``anchor``, ``role_signature``, or
    ``decision_content``. The reference is computed from public material, never
    from an owner-local id or a peer ledger.
    """

    if type(namespace) is not str or namespace not in (
        ORGANIZATION_OPERATION_REF_NAMESPACES
    ):
        _fail("organization_operation_invalid_ref")
    text = _require_text(value, "organization_operation_invalid_ref")
    return hashlib.sha256(
        "\x1f".join((_REF_NAMESPACE, namespace, text)).encode("utf-8")
    ).hexdigest()[:ORGANIZATION_ID_HEX_LEN]


def require_organization_decision_id(
    value: object, code: str = "organization_operation_invalid"
) -> str:
    """Require an owner-local ``orgd-`` decision identity."""

    if type(value) is not str or _DECISION_ID_PATTERN.match(value) is None:
        _fail(code)
    return value


def require_organization_action_id(
    value: object, code: str = "organization_operation_invalid"
) -> str:
    """Require an owner-local ``orga-`` action identity."""

    if type(value) is not str or _ACTION_ID_PATTERN.match(value) is None:
        _fail(code)
    return value


def require_organization_publication_operation_id(
    value: object, code: str = "organization_operation_invalid"
) -> str:
    """Require a published ``orgop-`` operation identity."""

    if (
        type(value) is not str
        or _PUBLICATION_OPERATION_ID_PATTERN.match(value) is None
    ):
        _fail(code)
    return value


def require_organization_operation_evidence_id(
    value: object, code: str = "organization_operation_invalid"
) -> str:
    """Require an owner-local ``orgev-`` evidence identity."""

    if type(value) is not str or _EVIDENCE_ID_PATTERN.match(value) is None:
        _fail(code)
    return value


def require_organization_operation_ref(
    value: object, code: str = "organization_operation_invalid_ref"
) -> str:
    """Require a bounded 16-hex speech-frame reference."""

    if type(value) is not str or _REF_PATTERN.match(value) is None:
        _fail(code)
    return value


# ---------------------------------------------------------------------------
# Bounded owner-scoped operational records
# ---------------------------------------------------------------------------

ORGANIZATION_OPERATION_NOTICE_CODES: Final[frozenset[str]] = frozenset(
    {
        "operations_truncated",
        "operations_orphaned",
        "authority_unresolved",
        "contest_unresolved",
        "operation_expired",
        "operation_anchor_unresolved",
    }
)

ORGANIZATION_ANCHOR_KINDS: Final[frozenset[str]] = frozenset(
    {
        "item",
        "resource",
        "artifact",
        "structure",
        "repository",
        "collective_project",
        "member",
        "unknown",
    }
)

ORGANIZATION_CONTROL_ANCHOR_KINDS: Final[frozenset[str]] = frozenset(
    {
        "item",
        "resource",
        "artifact",
        "structure",
        "repository",
        "unknown",
    }
)

ORGANIZATION_OPERATION_EVIDENCE_SOURCES: Final[frozenset[str]] = frozenset(
    {"observation", "communication", "owner_ledger", "memory"}
)

FORBIDDEN_OPERATION_FIELD_NAMES: Final[frozenset[str]] = (
    FORBIDDEN_ORGANIZATION_FIELD_NAMES
    | frozenset(
        {
            "truth",
            "verified",
            "owner",
            "property",
            "title",
            "deed",
            "permission",
            "ownership",
            "custody",
        }
    )
)

_CONTROL_DOMAINS: Final[frozenset[OrganizationOperationDomain]] = frozenset(
    {
        OrganizationOperationDomain.RESOURCE_CONTROL,
        OrganizationOperationDomain.STORAGE,
        OrganizationOperationDomain.RECORD_KEEPING,
    }
)

_RECORD_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_HEX64_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")


class OrganizationOperationEvidenceSource(StrEnum):
    """Closed provenance channel for one operation evidence item."""

    OBSERVATION = "observation"
    COMMUNICATION = "communication"
    OWNER_LEDGER = "owner_ledger"
    MEMORY = "memory"


class OrganizationDecisionStance(StrEnum):
    """Closed believed support stance for one decision record."""

    SUPPORTED = "supported"
    CONTESTED = "contested"
    UNKNOWN = "unknown"


class OrganizationOperationalStatus(StrEnum):
    """Closed operational sidecar status for one concept reference."""

    ACTIVE = "active"
    DISSOLVED = "dissolved"
    ORPHANED = "orphaned"


def _require_owner_id(value: object) -> AgentId:
    if type(value) is not AgentId:
        _fail("organization_operation_invalid")
    return value


def _require_enum_value(
    value: object, enum_type: type[StrEnum], code: str = (
        "organization_operation_invalid"
    )
) -> StrEnum:
    if type(value) is not enum_type:
        _fail(code)
    return value


def _require_count(value: object) -> int:
    if type(value) is not int or value < 0:
        _fail("organization_operation_invalid")
    return value


def _require_bounded_count(value: object, lower: int, upper: int) -> int:
    count = _require_count(value)
    if count < lower or count > upper:
        _fail("organization_operation_cap_exceeded")
    return count


def _require_hex64(value: object) -> str:
    if type(value) is not str or _HEX64_PATTERN.match(value) is None:
        _fail("organization_operation_invalid")
    return value


def _require_token(value: object, allowed: frozenset[str]) -> str:
    if type(value) is not str or value not in allowed:
        _fail("organization_operation_invalid")
    return value


def _require_span(first_tick: object, last_tick: object) -> tuple[int, int]:
    first = require_organization_tick(first_tick)
    last = require_organization_tick(last_tick)
    if last < first:
        _fail("organization_operation_tick_regression")
    return first, last


def _require_evidence_refs(values: object, cap: int) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        _fail("organization_operation_invalid")
    items = tuple(values)
    for item in items:
        if type(item) is not str or not item:
            _fail("organization_operation_invalid")
    if len(set(items)) != len(items):
        _fail("organization_duplicate_operation")
    if len(items) > cap:
        _fail("organization_operation_cap_exceeded")
    return tuple(sorted(items))


def _reject_operation_forbidden_fields(cls: type[object]) -> None:
    names = set(getattr(cls, "__dataclass_fields__", {}))
    if names & FORBIDDEN_OPERATION_FIELD_NAMES:
        _fail("organization_operation_invalid")


def _require_optional_decision_ref(value: object) -> str | None:
    if value is None:
        return None
    return require_organization_decision_id(value)


def _require_optional_text(value: object) -> str | None:
    if value is None:
        return None
    return _require_text(value, "organization_operation_invalid")


def _validate_support(
    owner_support_count: object, contest_count: object
) -> tuple[int, int]:
    support = _require_bounded_count(
        owner_support_count, 1, _DEFAULT_OPERATION_POLICY.max_owner_support
    )
    contest = _require_bounded_count(
        contest_count, 0, _DEFAULT_OPERATION_POLICY.max_contest
    )
    return support, contest


@dataclass(frozen=True, slots=True)
class OrganizationOperationEvidence:
    """One bounded piece of owner-local operation evidence."""

    evidence_id: str
    ordinal: int
    source: OrganizationOperationEvidenceSource
    ref: str
    tick: int
    anchor_digest: str
    actor_id: str | None = None

    def __post_init__(self) -> None:
        _reject_operation_forbidden_fields(type(self))
        object.__setattr__(
            self,
            "evidence_id",
            require_organization_operation_evidence_id(self.evidence_id),
        )
        object.__setattr__(self, "ordinal", _require_count(self.ordinal))
        object.__setattr__(
            self,
            "source",
            _require_enum_value(
                self.source, OrganizationOperationEvidenceSource
            ),
        )
        object.__setattr__(
            self, "ref", _require_text(self.ref, "organization_operation_invalid")
        )
        object.__setattr__(self, "tick", require_organization_tick(self.tick))
        object.__setattr__(self, "anchor_digest", _require_hex64(self.anchor_digest))
        if self.actor_id is not None:
            object.__setattr__(
                self,
                "actor_id",
                _require_text(self.actor_id, "organization_operation_invalid"),
            )


@dataclass(frozen=True, slots=True)
class OrganizationControlBelief:
    """One believed legitimate control relation; never objective custody."""

    domain: OrganizationOperationDomain
    anchor_kind: str
    anchor_id: str
    stance: OrganizationControlStance
    authority_basis: OrganizationAuthorityBasis
    legitimacy_doctrine: str
    decision_ref: str | None
    role_ref: str | None
    first_tick: int
    last_tick: int
    owner_support_count: int
    contest_count: int
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_operation_forbidden_fields(type(self))
        domain = _require_enum_value(self.domain, OrganizationOperationDomain)
        if domain not in _CONTROL_DOMAINS:
            _fail("organization_operation_invalid")
        object.__setattr__(self, "domain", domain)
        object.__setattr__(
            self,
            "anchor_kind",
            _require_token(self.anchor_kind, ORGANIZATION_CONTROL_ANCHOR_KINDS),
        )
        object.__setattr__(
            self,
            "anchor_id",
            _require_text(self.anchor_id, "organization_operation_invalid"),
        )
        object.__setattr__(
            self,
            "stance",
            _require_enum_value(self.stance, OrganizationControlStance),
        )
        object.__setattr__(
            self,
            "authority_basis",
            _require_enum_value(self.authority_basis, OrganizationAuthorityBasis),
        )
        object.__setattr__(
            self,
            "legitimacy_doctrine",
            _require_token(
                self.legitimacy_doctrine, ORGANIZATION_LEGITIMACY_DOCTRINES
            ),
        )
        object.__setattr__(
            self, "decision_ref", _require_optional_decision_ref(self.decision_ref)
        )
        object.__setattr__(self, "role_ref", _require_optional_text(self.role_ref))
        first, last = _require_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        support, contest = _validate_support(
            self.owner_support_count, self.contest_count
        )
        object.__setattr__(self, "owner_support_count", support)
        object.__setattr__(self, "contest_count", contest)
        object.__setattr__(
            self,
            "evidence_refs",
            _require_evidence_refs(
                self.evidence_refs,
                _DEFAULT_OPERATION_POLICY.max_evidence_per_record,
            ),
        )


@dataclass(frozen=True, slots=True)
class OrganizationAdmissionBelief:
    """One believed admission act; never a permission or world rule."""

    member_id: str
    stance: OrganizationAdmissionStance
    authority_basis: OrganizationAuthorityBasis
    role_ref: str | None
    decision_ref: str | None
    temporal_scope: OrganizationTemporalScope
    expires_tick: int | None
    first_tick: int
    last_tick: int
    owner_support_count: int
    contest_count: int
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_operation_forbidden_fields(type(self))
        object.__setattr__(
            self,
            "member_id",
            _require_text(self.member_id, "organization_operation_invalid"),
        )
        object.__setattr__(
            self,
            "stance",
            _require_enum_value(self.stance, OrganizationAdmissionStance),
        )
        object.__setattr__(
            self,
            "authority_basis",
            _require_enum_value(self.authority_basis, OrganizationAuthorityBasis),
        )
        object.__setattr__(self, "role_ref", _require_optional_text(self.role_ref))
        object.__setattr__(
            self, "decision_ref", _require_optional_decision_ref(self.decision_ref)
        )
        scope = _require_enum_value(
            self.temporal_scope,
            OrganizationTemporalScope,
            "organization_operation_invalid",
        )
        object.__setattr__(self, "temporal_scope", scope)
        first, last = _require_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        if scope is OrganizationTemporalScope.TEMPORARY:
            if self.expires_tick is None:
                _fail("organization_operation_invalid")
            expires = require_organization_tick(self.expires_tick)
            if expires < first:
                _fail("organization_operation_tick_regression")
            object.__setattr__(self, "expires_tick", expires)
        elif self.expires_tick is not None:
            _fail("organization_operation_invalid")
        support, contest = _validate_support(
            self.owner_support_count, self.contest_count
        )
        object.__setattr__(self, "owner_support_count", support)
        object.__setattr__(self, "contest_count", contest)
        object.__setattr__(
            self,
            "evidence_refs",
            _require_evidence_refs(
                self.evidence_refs,
                _DEFAULT_OPERATION_POLICY.max_evidence_per_record,
            ),
        )


@dataclass(frozen=True, slots=True)
class OrganizationDepartureBelief:
    """One believed departure act; departure is not expulsion law."""

    member_id: str
    stance: OrganizationDepartureStance
    authority_basis: OrganizationAuthorityBasis
    decision_ref: str | None
    first_tick: int
    last_tick: int
    owner_support_count: int
    contest_count: int
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_operation_forbidden_fields(type(self))
        object.__setattr__(
            self,
            "member_id",
            _require_text(self.member_id, "organization_operation_invalid"),
        )
        object.__setattr__(
            self,
            "stance",
            _require_enum_value(self.stance, OrganizationDepartureStance),
        )
        object.__setattr__(
            self,
            "authority_basis",
            _require_enum_value(self.authority_basis, OrganizationAuthorityBasis),
        )
        object.__setattr__(
            self, "decision_ref", _require_optional_decision_ref(self.decision_ref)
        )
        first, last = _require_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        support, contest = _validate_support(
            self.owner_support_count, self.contest_count
        )
        object.__setattr__(self, "owner_support_count", support)
        object.__setattr__(self, "contest_count", contest)
        object.__setattr__(
            self,
            "evidence_refs",
            _require_evidence_refs(
                self.evidence_refs,
                _DEFAULT_OPERATION_POLICY.max_evidence_per_record,
            ),
        )


@dataclass(frozen=True, slots=True)
class OrganizationAssignmentBelief:
    """One believed role assignment; never an authority grant."""

    office_id: str
    occupant_id: str
    stance: OrganizationAssignmentStance
    authority_basis: OrganizationAuthorityBasis
    decision_ref: str | None
    first_tick: int
    last_tick: int
    owner_support_count: int
    contest_count: int
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_operation_forbidden_fields(type(self))
        object.__setattr__(
            self,
            "office_id",
            _require_text(self.office_id, "organization_operation_invalid"),
        )
        object.__setattr__(
            self,
            "occupant_id",
            _require_text(self.occupant_id, "organization_operation_invalid"),
        )
        object.__setattr__(
            self,
            "stance",
            _require_enum_value(self.stance, OrganizationAssignmentStance),
        )
        object.__setattr__(
            self,
            "authority_basis",
            _require_enum_value(self.authority_basis, OrganizationAuthorityBasis),
        )
        object.__setattr__(
            self, "decision_ref", _require_optional_decision_ref(self.decision_ref)
        )
        first, last = _require_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        support, contest = _validate_support(
            self.owner_support_count, self.contest_count
        )
        object.__setattr__(self, "owner_support_count", support)
        object.__setattr__(self, "contest_count", contest)
        object.__setattr__(
            self,
            "evidence_refs",
            _require_evidence_refs(
                self.evidence_refs,
                _DEFAULT_OPERATION_POLICY.max_evidence_per_record,
            ),
        )


@dataclass(frozen=True, slots=True)
class OrganizationProcedureActionBelief:
    """One believed recognized procedure act and its observed outcome."""

    procedure_ref: str
    command_kind: str
    actor_id: str
    outcome: OrganizationOperationOutcome
    authority_basis: OrganizationAuthorityBasis
    decision_ref: str | None
    first_tick: int
    last_tick: int
    owner_support_count: int
    contest_count: int
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_operation_forbidden_fields(type(self))
        object.__setattr__(
            self,
            "procedure_ref",
            _require_text(self.procedure_ref, "organization_operation_invalid"),
        )
        if (
            type(self.command_kind) is not str
            or _RECORD_ID_PATTERN.match(self.command_kind) is None
        ):
            _fail("organization_operation_invalid")
        object.__setattr__(
            self,
            "actor_id",
            _require_text(self.actor_id, "organization_operation_invalid"),
        )
        object.__setattr__(
            self,
            "outcome",
            _require_enum_value(self.outcome, OrganizationOperationOutcome),
        )
        object.__setattr__(
            self,
            "authority_basis",
            _require_enum_value(self.authority_basis, OrganizationAuthorityBasis),
        )
        object.__setattr__(
            self, "decision_ref", _require_optional_decision_ref(self.decision_ref)
        )
        first, last = _require_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        support, contest = _validate_support(
            self.owner_support_count, self.contest_count
        )
        object.__setattr__(self, "owner_support_count", support)
        object.__setattr__(self, "contest_count", contest)
        object.__setattr__(
            self,
            "evidence_refs",
            _require_evidence_refs(
                self.evidence_refs,
                _DEFAULT_OPERATION_POLICY.max_evidence_per_record,
            ),
        )


@dataclass(frozen=True, slots=True)
class OrganizationCommitmentOperationBelief:
    """One believed internal commitment state; never enforced debt."""

    commitment_id: str
    role: OrganizationCommitmentRole
    counterpart_id: str
    stance: OrganizationCommitmentStance
    authority_basis: OrganizationAuthorityBasis
    decision_ref: str | None
    due_tick: int | None
    first_tick: int
    last_tick: int
    owner_support_count: int
    contest_count: int
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_operation_forbidden_fields(type(self))
        object.__setattr__(
            self,
            "commitment_id",
            _require_text(self.commitment_id, "organization_operation_invalid"),
        )
        object.__setattr__(
            self, "role", _require_enum_value(self.role, OrganizationCommitmentRole)
        )
        object.__setattr__(
            self,
            "counterpart_id",
            _require_text(self.counterpart_id, "organization_operation_invalid"),
        )
        object.__setattr__(
            self,
            "stance",
            _require_enum_value(self.stance, OrganizationCommitmentStance),
        )
        object.__setattr__(
            self,
            "authority_basis",
            _require_enum_value(self.authority_basis, OrganizationAuthorityBasis),
        )
        object.__setattr__(
            self, "decision_ref", _require_optional_decision_ref(self.decision_ref)
        )
        first, last = _require_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        if self.due_tick is not None:
            object.__setattr__(
                self, "due_tick", require_organization_tick(self.due_tick)
            )
        support, contest = _validate_support(
            self.owner_support_count, self.contest_count
        )
        object.__setattr__(self, "owner_support_count", support)
        object.__setattr__(self, "contest_count", contest)
        object.__setattr__(
            self,
            "evidence_refs",
            _require_evidence_refs(
                self.evidence_refs,
                _DEFAULT_OPERATION_POLICY.max_evidence_per_record,
            ),
        )


@dataclass(frozen=True, slots=True)
class OrganizationDecisionRecord:
    """One owner-local believed operational decision with provenance."""

    decision_id: str
    domain: OrganizationOperationDomain
    act: OrganizationOperationAct
    actor_id: str
    target_id: str | None
    anchor_kind: str
    anchor_id: str
    authority_basis: OrganizationAuthorityBasis
    stance: OrganizationDecisionStance
    support_count: int
    oppose_count: int
    provenance_code: OrganizationOperationProvenance
    tick: int
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_operation_forbidden_fields(type(self))
        object.__setattr__(
            self,
            "decision_id",
            require_organization_decision_id(self.decision_id),
        )
        object.__setattr__(
            self,
            "domain",
            _require_enum_value(self.domain, OrganizationOperationDomain),
        )
        object.__setattr__(
            self, "act", _require_enum_value(self.act, OrganizationOperationAct)
        )
        object.__setattr__(
            self,
            "actor_id",
            _require_text(self.actor_id, "organization_operation_invalid"),
        )
        object.__setattr__(self, "target_id", _require_optional_text(self.target_id))
        object.__setattr__(
            self,
            "anchor_kind",
            _require_token(self.anchor_kind, ORGANIZATION_ANCHOR_KINDS),
        )
        object.__setattr__(
            self,
            "anchor_id",
            _require_text(self.anchor_id, "organization_operation_invalid"),
        )
        object.__setattr__(
            self,
            "authority_basis",
            _require_enum_value(self.authority_basis, OrganizationAuthorityBasis),
        )
        object.__setattr__(
            self, "stance", _require_enum_value(self.stance, OrganizationDecisionStance)
        )
        object.__setattr__(
            self,
            "support_count",
            _require_bounded_count(
                self.support_count, 0, _DEFAULT_OPERATION_POLICY.max_owner_support
            ),
        )
        object.__setattr__(
            self,
            "oppose_count",
            _require_bounded_count(
                self.oppose_count, 0, _DEFAULT_OPERATION_POLICY.max_contest
            ),
        )
        object.__setattr__(
            self,
            "provenance_code",
            _require_enum_value(
                self.provenance_code, OrganizationOperationProvenance
            ),
        )
        object.__setattr__(self, "tick", require_organization_tick(self.tick))
        object.__setattr__(
            self,
            "evidence_refs",
            _require_evidence_refs(
                self.evidence_refs,
                _DEFAULT_OPERATION_POLICY.max_evidence_per_record,
            ),
        )


@dataclass(frozen=True, slots=True)
class OrganizationActionRecord:
    """One owner-local believed action effect with provenance."""

    action_id: str
    decision_id: str | None
    domain: OrganizationOperationDomain
    act: OrganizationOperationAct
    actor_id: str
    command_kind: str
    anchor_kind: str
    anchor_id: str
    outcome: OrganizationOperationOutcome
    provenance_code: OrganizationOperationProvenance
    tick: int
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_operation_forbidden_fields(type(self))
        object.__setattr__(
            self, "action_id", require_organization_action_id(self.action_id)
        )
        object.__setattr__(
            self, "decision_id", _require_optional_decision_ref(self.decision_id)
        )
        object.__setattr__(
            self,
            "domain",
            _require_enum_value(self.domain, OrganizationOperationDomain),
        )
        object.__setattr__(
            self, "act", _require_enum_value(self.act, OrganizationOperationAct)
        )
        object.__setattr__(
            self,
            "actor_id",
            _require_text(self.actor_id, "organization_operation_invalid"),
        )
        if (
            type(self.command_kind) is not str
            or _RECORD_ID_PATTERN.match(self.command_kind) is None
        ):
            _fail("organization_operation_invalid")
        object.__setattr__(
            self,
            "anchor_kind",
            _require_token(self.anchor_kind, ORGANIZATION_ANCHOR_KINDS),
        )
        object.__setattr__(
            self,
            "anchor_id",
            _require_text(self.anchor_id, "organization_operation_invalid"),
        )
        object.__setattr__(
            self,
            "outcome",
            _require_enum_value(self.outcome, OrganizationOperationOutcome),
        )
        object.__setattr__(
            self,
            "provenance_code",
            _require_enum_value(
                self.provenance_code, OrganizationOperationProvenance
            ),
        )
        object.__setattr__(self, "tick", require_organization_tick(self.tick))
        object.__setattr__(
            self,
            "evidence_refs",
            _require_evidence_refs(
                self.evidence_refs,
                _DEFAULT_OPERATION_POLICY.max_evidence_per_record,
            ),
        )


def _validate_notices(values: object) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        _fail("organization_operation_invalid")
    items = tuple(values)
    for item in items:
        if type(item) is not str or item not in ORGANIZATION_OPERATION_NOTICE_CODES:
            _fail("organization_operation_invalid")
    return tuple(sorted(set(items)))


@dataclass(frozen=True, slots=True)
class OrganizationOperationalConcept:
    """Operational sidecar for one existing owner-local ``orgc-`` concept."""

    organization_id: str
    owner_id: AgentId
    status: OrganizationOperationalStatus
    first_tick: int
    last_tick: int
    controls: tuple[OrganizationControlBelief, ...] = ()
    admissions: tuple[OrganizationAdmissionBelief, ...] = ()
    departures: tuple[OrganizationDepartureBelief, ...] = ()
    assignments: tuple[OrganizationAssignmentBelief, ...] = ()
    procedures: tuple[OrganizationProcedureActionBelief, ...] = ()
    commitments: tuple[OrganizationCommitmentOperationBelief, ...] = ()
    decisions: tuple[OrganizationDecisionRecord, ...] = ()
    actions: tuple[OrganizationActionRecord, ...] = ()
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_operation_forbidden_fields(type(self))
        from agents.cognition.organization_concepts import (
            require_organization_concept_id,
        )

        object.__setattr__(
            self,
            "organization_id",
            require_organization_concept_id(self.organization_id),
        )
        object.__setattr__(self, "owner_id", _require_owner_id(self.owner_id))
        object.__setattr__(
            self,
            "status",
            _require_enum_value(self.status, OrganizationOperationalStatus),
        )
        first, last = _require_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        for name, expected_type in (
            ("controls", OrganizationControlBelief),
            ("admissions", OrganizationAdmissionBelief),
            ("departures", OrganizationDepartureBelief),
            ("assignments", OrganizationAssignmentBelief),
            ("procedures", OrganizationProcedureActionBelief),
            ("commitments", OrganizationCommitmentOperationBelief),
            ("decisions", OrganizationDecisionRecord),
            ("actions", OrganizationActionRecord),
        ):
            values = getattr(self, name)
            if not isinstance(values, (list, tuple)):
                _fail("organization_operation_invalid")
            items = tuple(values)
            for item in items:
                if type(item) is not expected_type:
                    _fail("organization_operation_invalid")
            object.__setattr__(self, name, items)

        decision_ids = {record.decision_id for record in self.decisions}
        if len(decision_ids) != len(self.decisions):
            _fail("organization_duplicate_operation")
        action_ids = {record.action_id for record in self.actions}
        if len(action_ids) != len(self.actions):
            _fail("organization_duplicate_operation")
        for record in (
            *self.controls,
            *self.admissions,
            *self.departures,
            *self.assignments,
            *self.procedures,
            *self.commitments,
        ):
            if record.decision_ref is not None and record.decision_ref not in (
                decision_ids
            ):
                _fail("organization_operation_unknown_decision")
        for action in self.actions:
            if action.decision_id is not None and action.decision_id not in (
                decision_ids
            ):
                _fail("organization_operation_unknown_decision")
        previous_tick = -1
        for record in self.decisions:
            if record.tick < previous_tick:
                _fail("organization_operation_tick_regression")
            previous_tick = record.tick
        previous_tick = -1
        for record in self.actions:
            if record.tick < previous_tick:
                _fail("organization_operation_tick_regression")
            previous_tick = record.tick
        object.__setattr__(self, "notices", _validate_notices(self.notices))


@dataclass(frozen=True, slots=True)
class OrganizationOperationLedger:
    """One owner's operational sidecar beliefs. ``None`` means the mode is off."""

    owner_id: AgentId
    concepts: tuple[OrganizationOperationalConcept, ...] = ()
    notices: tuple[str, ...] = ()
    policy_version: str = ORGANIZATION_OPERATION_POLICY_VERSION

    def __post_init__(self) -> None:
        _reject_operation_forbidden_fields(type(self))
        object.__setattr__(self, "owner_id", _require_owner_id(self.owner_id))
        if self.policy_version != ORGANIZATION_OPERATION_POLICY_VERSION:
            _fail("organization_operation_policy_mismatch")
        if not isinstance(self.concepts, (list, tuple)):
            _fail("organization_operation_invalid")
        concepts = tuple(self.concepts)
        seen: set[str] = set()
        previous: str | None = None
        decision_ids: set[str] = set()
        action_ids: set[str] = set()
        total_records = 0
        policy = _DEFAULT_OPERATION_POLICY
        for concept in concepts:
            if type(concept) is not OrganizationOperationalConcept:
                _fail("organization_operation_invalid")
            if concept.owner_id != self.owner_id:
                _fail("organization_operation_foreign_ledger")
            if concept.organization_id in seen:
                _fail("organization_duplicate_operation")
            if previous is not None and concept.organization_id < previous:
                _fail("organization_operation_invalid")
            seen.add(concept.organization_id)
            previous = concept.organization_id
            if len(concept.controls) > policy.max_controls:
                _fail("organization_operation_cap_exceeded")
            per_domain: dict[OrganizationOperationDomain, int] = {}
            for control in concept.controls:
                per_domain[control.domain] = per_domain.get(control.domain, 0) + 1
            if any(count > 16 for count in per_domain.values()):
                _fail("organization_operation_cap_exceeded")
            if len(concept.admissions) > policy.max_admissions:
                _fail("organization_operation_cap_exceeded")
            if len(concept.departures) > policy.max_departures:
                _fail("organization_operation_cap_exceeded")
            if len(concept.assignments) > policy.max_assignments:
                _fail("organization_operation_cap_exceeded")
            if len(concept.procedures) > policy.max_procedures:
                _fail("organization_operation_cap_exceeded")
            if len(concept.commitments) > policy.max_commitments:
                _fail("organization_operation_cap_exceeded")
            if len(concept.decisions) > policy.max_decisions:
                _fail("organization_operation_cap_exceeded")
            if len(concept.actions) > policy.max_actions:
                _fail("organization_operation_cap_exceeded")
            for decision in concept.decisions:
                if decision.decision_id in decision_ids:
                    _fail("organization_duplicate_operation")
                decision_ids.add(decision.decision_id)
            for action in concept.actions:
                if action.action_id in action_ids:
                    _fail("organization_duplicate_operation")
                action_ids.add(action.action_id)
            total_records += sum(
                len(getattr(concept, name))
                for name in (
                    "controls",
                    "admissions",
                    "departures",
                    "assignments",
                    "procedures",
                    "commitments",
                    "decisions",
                    "actions",
                )
            )
        if len(concepts) > policy.max_concepts:
            _fail("organization_operation_cap_exceeded")
        if total_records > policy.max_total_records:
            _fail("organization_operation_cap_exceeded")
        object.__setattr__(self, "concepts", concepts)
        object.__setattr__(self, "notices", _validate_notices(self.notices))
        _LOG.debug(
            "organization_operation_ledger_constructed owner_id=%s concepts=%s "
            "controls=%s admissions=%s departures=%s assignments=%s procedures=%s "
            "commitments=%s decisions=%s actions=%s",
            self.owner_id.value,
            len(self.concepts),
            sum(len(c.controls) for c in self.concepts),
            sum(len(c.admissions) for c in self.concepts),
            sum(len(c.departures) for c in self.concepts),
            sum(len(c.assignments) for c in self.concepts),
            sum(len(c.procedures) for c in self.concepts),
            sum(len(c.commitments) for c in self.concepts),
            sum(len(c.decisions) for c in self.concepts),
            sum(len(c.actions) for c in self.concepts),
        )


def empty_organization_operation_ledger(
    owner_id: AgentId,
    policy: OrganizationOperationPolicy | None = None,
) -> OrganizationOperationLedger:
    """Return an enabled-but-empty operation ledger for one owner."""

    if policy is not None and type(policy) is not OrganizationOperationPolicy:
        _fail("organization_operation_policy_mismatch")
    return OrganizationOperationLedger(owner_id=owner_id)


def require_owner_organization_operations(
    ledger: object,
    owner_id: AgentId,
    *,
    field_name: str,
) -> None:
    """Reject a foreign or mistyped operation ledger. ``None`` passes."""

    if ledger is None:
        return
    if type(owner_id) is not AgentId:
        _fail("organization_operation_invalid")
    if type(ledger) is not OrganizationOperationLedger:
        _LOG.warning("organization_operation_carry_rejected reason=invalid_type")
        raise TypeError(f"{field_name} must be OrganizationOperationLedger")
    if ledger.owner_id != owner_id:
        _LOG.error(
            "organization_operation_validation_failed field=%s reason_code=%s",
            field_name,
            "owner_mismatch",
        )
        _fail("organization_operation_foreign_ledger")


# ---------------------------------------------------------------------------
# Owner-only evidence collection and deterministic materialization
# ---------------------------------------------------------------------------

_SOURCE_KIND_DOMAINS: Final[
    Mapping[str, tuple[OrganizationOperationDomain, OrganizationOperationAct, str]]
] = MappingProxyType(
    {
        "taken": (
            OrganizationOperationDomain.RESOURCE_CONTROL,
            OrganizationOperationAct.AUTHORIZE_CONTROL,
            "take",
        ),
        "taken_from_corpse": (
            OrganizationOperationDomain.RESOURCE_CONTROL,
            OrganizationOperationAct.AUTHORIZE_CONTROL,
            "take",
        ),
        "dropped": (
            OrganizationOperationDomain.RESOURCE_CONTROL,
            OrganizationOperationAct.REVOKE_CONTROL,
            "drop",
        ),
        "given": (
            OrganizationOperationDomain.RESOURCE_CONTROL,
            OrganizationOperationAct.AUTHORIZE_CONTROL,
            "give",
        ),
        "item_stored": (
            OrganizationOperationDomain.STORAGE,
            OrganizationOperationAct.AUTHORIZE_CONTROL,
            "store",
        ),
        "artifact_created": (
            OrganizationOperationDomain.RECORD_KEEPING,
            OrganizationOperationAct.RECORD_DECISION,
            "inscribe",
        ),
        "artifact_modified": (
            OrganizationOperationDomain.RECORD_KEEPING,
            OrganizationOperationAct.RECORD_DECISION,
            "amend",
        ),
        "artifact_annotated": (
            OrganizationOperationDomain.RECORD_KEEPING,
            OrganizationOperationAct.RECORD_DECISION,
            "annotate_record",
        ),
        "artifact_copied": (
            OrganizationOperationDomain.RECORD_KEEPING,
            OrganizationOperationAct.RECORD_DECISION,
            "copy_record",
        ),
        "artifact_moved": (
            OrganizationOperationDomain.RECORD_KEEPING,
            OrganizationOperationAct.AUTHORIZE_CONTROL,
            "transfer_artifact",
        ),
        "repository_established": (
            OrganizationOperationDomain.PROCEDURE_ACTION,
            OrganizationOperationAct.INVOKE_PROCEDURE,
            "establish_repository",
        ),
        "repository_maintained": (
            OrganizationOperationDomain.PROCEDURE_ACTION,
            OrganizationOperationAct.INVOKE_PROCEDURE,
            "maintain_repository",
        ),
        "repository_indexed": (
            OrganizationOperationDomain.PROCEDURE_ACTION,
            OrganizationOperationAct.INVOKE_PROCEDURE,
            "index_repository",
        ),
        "repository_member_deposited": (
            OrganizationOperationDomain.STORAGE,
            OrganizationOperationAct.AUTHORIZE_CONTROL,
            "deposit_record",
        ),
        "repository_member_retrieved": (
            OrganizationOperationDomain.STORAGE,
            OrganizationOperationAct.AUTHORIZE_CONTROL,
            "retrieve_record",
        ),
        "project_contributed": (
            OrganizationOperationDomain.PROCEDURE_ACTION,
            OrganizationOperationAct.INVOKE_PROCEDURE,
            "contribute_collective_project",
        ),
        "public_good_maintained": (
            OrganizationOperationDomain.PROCEDURE_ACTION,
            OrganizationOperationAct.INVOKE_PROCEDURE,
            "maintain_public_good",
        ),
        "public_good_benefit": (
            OrganizationOperationDomain.PROCEDURE_ACTION,
            OrganizationOperationAct.INVOKE_PROCEDURE,
            "use_public_good",
        ),
        "public_good_opposed": (
            OrganizationOperationDomain.PROCEDURE_ACTION,
            OrganizationOperationAct.INVOKE_PROCEDURE,
            "oppose_public_good",
        ),
    }
)

_ACT_DOMAINS: Final[
    Mapping[OrganizationOperationAct, OrganizationOperationDomain]
] = MappingProxyType(
    {
        OrganizationOperationAct.ADMIT: (
            OrganizationOperationDomain.MEMBERSHIP_ADMISSION
        ),
        OrganizationOperationAct.DEPART: (
            OrganizationOperationDomain.MEMBERSHIP_DEPARTURE
        ),
        OrganizationOperationAct.ASSIGN: OrganizationOperationDomain.ROLE_ASSIGNMENT,
        OrganizationOperationAct.REMOVE: OrganizationOperationDomain.ROLE_ASSIGNMENT,
        OrganizationOperationAct.AUTHORIZE_CONTROL: (
            OrganizationOperationDomain.RESOURCE_CONTROL
        ),
        OrganizationOperationAct.REVOKE_CONTROL: (
            OrganizationOperationDomain.RESOURCE_CONTROL
        ),
        OrganizationOperationAct.INVOKE_PROCEDURE: (
            OrganizationOperationDomain.PROCEDURE_ACTION
        ),
        OrganizationOperationAct.DECLARE_COMMITMENT: (
            OrganizationOperationDomain.INTERNAL_COMMITMENT
        ),
        OrganizationOperationAct.FULFILL_COMMITMENT: (
            OrganizationOperationDomain.INTERNAL_COMMITMENT
        ),
        OrganizationOperationAct.RECORD_DECISION: (
            OrganizationOperationDomain.RECORD_KEEPING
        ),
    }
)

_BUNDLE_FAMILIES: Final[tuple[str, ...]] = (
    "controls",
    "admissions",
    "departures",
    "assignments",
    "procedures",
    "commitments",
    "decisions",
    "actions",
)


@dataclass(frozen=True, slots=True)
class _EvidenceBundle:
    controls: tuple[OrganizationControlBelief, ...] = ()
    admissions: tuple[OrganizationAdmissionBelief, ...] = ()
    departures: tuple[OrganizationDepartureBelief, ...] = ()
    assignments: tuple[OrganizationAssignmentBelief, ...] = ()
    procedures: tuple[OrganizationProcedureActionBelief, ...] = ()
    commitments: tuple[OrganizationCommitmentOperationBelief, ...] = ()
    decisions: tuple[OrganizationDecisionRecord, ...] = ()
    actions: tuple[OrganizationActionRecord, ...] = ()
    notices: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _OperationEvidence:
    owner_id: AgentId
    tick: int
    by_concept: tuple[tuple[str, _EvidenceBundle], ...] = ()
    notices: tuple[str, ...] = ()


def _record_tick(value: object) -> int:
    return require_organization_tick(value)


def _claim_domain(act: OrganizationOperationAct, anchor_kind: str) -> (
    OrganizationOperationDomain
):
    if act in (
        OrganizationOperationAct.AUTHORIZE_CONTROL,
        OrganizationOperationAct.REVOKE_CONTROL,
    ) and anchor_kind in ("structure", "repository"):
        return OrganizationOperationDomain.STORAGE
    return _ACT_DOMAINS[act]


def _claim_anchor_material(claim: object) -> tuple[str, str]:
    anchor_kind = getattr(claim, "anchor_kind", "unknown")
    anchor_ref = getattr(claim, "anchor_ref", None)
    if anchor_kind == "unknown" or anchor_ref is None:
        return "unknown", "unknown"
    return anchor_kind, anchor_ref


def _evidence_ref(
    owner_id: AgentId,
    organization_id: str,
    source: str,
    tick: int,
    ordinal: int,
    ref: str,
) -> str:
    return organization_operation_evidence_id(
        owner_id.value, organization_id, source, tick, ordinal, ref
    )


def _position_counts(
    collective_decisions: object | None,
    owner_id: AgentId,
) -> tuple[int, int]:
    if collective_decisions is None:
        return 0, 0
    from agents.cognition.collective_decisions import (
        CollectiveDecisionLedger,
        CollectivePositionStance,
    )

    if type(collective_decisions) is not CollectiveDecisionLedger:
        return 0, 0
    proposals = sorted(
        collective_decisions.proposals, key=lambda item: item.proposal_id
    )
    if not proposals:
        return 0, 0
    proposal = proposals[0]
    supports = 0
    opposes = 0
    for position in collective_decisions.positions:
        if position.proposal_ref != proposal.proposal_ref:
            continue
        if position.revision != proposal.revision or not position.active:
            continue
        if position.stance is CollectivePositionStance.SUPPORT:
            supports += 1
        elif position.stance is CollectivePositionStance.OPPOSE:
            opposes += 1
    return (
        min(supports, _DEFAULT_OPERATION_POLICY.max_owner_support),
        min(opposes, _DEFAULT_OPERATION_POLICY.max_contest),
    )


def _role_authority_match(
    offices: object | None,
    speaker: str,
    authority_ref: str | None,
) -> bool:
    if offices is None or authority_ref is None:
        return False
    from agents.cognition.offices import (
        OfficeConceptLedger,
        OfficeConceptStatus,
        office_role_signature,
    )

    if type(offices) is not OfficeConceptLedger:
        return False
    for concept in offices.concepts:
        if concept.status not in (
            OfficeConceptStatus.RECOGNIZED,
            OfficeConceptStatus.CONTESTED,
        ):
            continue
        signature = office_role_signature(
            concept.function, concept.context_key, concept.duty_kinds
        )
        if organization_operation_ref(signature, namespace="role_signature") != (
            authority_ref
        ):
            continue
        occupant = concept.preferred_occupant
        if occupant is not None and occupant.value == speaker:
            return True
    return False


def _decision_authority_match(
    collective_decisions: object | None,
    authority_ref: str | None,
) -> bool:
    if collective_decisions is None or authority_ref is None:
        return False
    from agents.cognition.collective_decisions import (
        CollectiveDecisionLedger,
        CollectiveProposalStatus,
    )

    if type(collective_decisions) is not CollectiveDecisionLedger:
        return False
    for proposal in collective_decisions.proposals:
        if proposal.status is not CollectiveProposalStatus.SUPPORTED:
            continue
        material = "|".join(
            (
                proposal.topic.value,
                proposal.action_token,
                proposal.target_token or "none",
            )
        )
        if organization_operation_ref(
            material, namespace="decision_content"
        ) == authority_ref:
            return True
    return False


def _claim_authority(
    claim: object,
    *,
    owner_entity: str,
    speaker: str,
    offices: object | None,
    collective_decisions: object | None,
) -> OrganizationAuthorityBasis:
    if speaker == owner_entity:
        return OrganizationAuthorityBasis.SELF_AUTHORED
    authority_ref = getattr(claim, "authority_ref", None)
    if _role_authority_match(offices, speaker, authority_ref):
        return OrganizationAuthorityBasis.ROLE_BELIEF
    if _decision_authority_match(collective_decisions, authority_ref):
        return OrganizationAuthorityBasis.DECISION_BELIEF
    return OrganizationAuthorityBasis.UNKNOWN


def _claim_provenance(
    authority: OrganizationAuthorityBasis,
    *,
    act: OrganizationOperationAct,
    stance: str,
) -> OrganizationOperationProvenance:
    if stance == "disputed":
        return OrganizationOperationProvenance.CONTESTED
    if authority is OrganizationAuthorityBasis.SELF_AUTHORED:
        return OrganizationOperationProvenance.SELF_AUTHORED
    if authority is OrganizationAuthorityBasis.ROLE_BELIEF:
        return OrganizationOperationProvenance.ROLE_AUTHORIZED
    if authority is OrganizationAuthorityBasis.DECISION_BELIEF:
        return OrganizationOperationProvenance.DECISION_SUPPORTED
    if act is OrganizationOperationAct.INVOKE_PROCEDURE:
        return OrganizationOperationProvenance.PROCEDURE_RECOGNIZED
    return OrganizationOperationProvenance.UNKNOWN_AUTHORITY


def _claim_beliefs(
    claim: object,
    *,
    organization_id: str,
    owner_id: AgentId,
    tick: int,
    authority: OrganizationAuthorityBasis,
    decision_ref: str,
) -> dict[str, tuple[object, ...]]:
    act = claim.act
    stance = claim.stance
    target = claim.target_ref or "unknown"
    anchor_kind, anchor_ref = _claim_anchor_material(claim)
    support = 1
    contest = 1 if stance == "disputed" else 0
    ref = _evidence_ref(
        owner_id,
        organization_id,
        "communication",
        tick,
        0,
        "|".join((act.value, stance, target, anchor_ref)),
    )
    common = {
        "authority_basis": authority,
        "decision_ref": decision_ref,
        "first_tick": tick,
        "last_tick": tick,
        "owner_support_count": support,
        "contest_count": contest,
        "evidence_refs": (ref,),
    }
    if act is OrganizationOperationAct.ADMIT:
        temporal = (
            OrganizationTemporalScope.TEMPORARY
            if claim.expires_tick is not None
            else OrganizationTemporalScope.ONGOING
        )
        record = OrganizationAdmissionBelief(
            member_id=target,
            stance=OrganizationAdmissionStance(stance),
            role_ref=None,
            temporal_scope=temporal,
            expires_tick=claim.expires_tick,
            **common,
        )
        return {"admissions": (record,)}
    if act is OrganizationOperationAct.DEPART:
        record = OrganizationDepartureBelief(
            member_id=target,
            stance=OrganizationDepartureStance(stance),
            **common,
        )
        return {"departures": (record,)}
    if act in (
        OrganizationOperationAct.ASSIGN,
        OrganizationOperationAct.REMOVE,
    ):
        record = OrganizationAssignmentBelief(
            office_id=claim.authority_ref or "unknown",
            occupant_id=target,
            stance=OrganizationAssignmentStance(stance),
            **common,
        )
        return {"assignments": (record,)}
    if act in (
        OrganizationOperationAct.AUTHORIZE_CONTROL,
        OrganizationOperationAct.REVOKE_CONTROL,
    ):
        record = OrganizationControlBelief(
            domain=_claim_domain(act, anchor_kind),
            anchor_kind=anchor_kind,
            anchor_id=anchor_ref,
            stance=OrganizationControlStance(stance),
            legitimacy_doctrine=_legitimacy_doctrine(authority),
            role_ref=claim.authority_ref,
            **common,
        )
        return {"controls": (record,)}
    if act is OrganizationOperationAct.INVOKE_PROCEDURE:
        record = OrganizationProcedureActionBelief(
            procedure_ref=anchor_ref,
            command_kind="invoke_procedure",
            actor_id=target,
            outcome=(
                OrganizationOperationOutcome.ATTEMPTED
                if stance != "disputed"
                else OrganizationOperationOutcome.UNKNOWN
            ),
            **common,
        )
        return {"procedures": (record,)}
    if act in (
        OrganizationOperationAct.DECLARE_COMMITMENT,
        OrganizationOperationAct.FULFILL_COMMITMENT,
    ):
        record = OrganizationCommitmentOperationBelief(
            commitment_id=claim.authority_ref or target,
            role=OrganizationCommitmentRole.DEBTOR,
            counterpart_id=target,
            stance=OrganizationCommitmentStance(stance),
            due_tick=None,
            **common,
        )
        return {"commitments": (record,)}
    return {}


def _legitimacy_doctrine(
    authority: OrganizationAuthorityBasis,
) -> str:
    if authority is OrganizationAuthorityBasis.DECISION_BELIEF:
        return "decision_grant"
    if authority is OrganizationAuthorityBasis.ROLE_BELIEF:
        return "role_trusteeship"
    if authority is OrganizationAuthorityBasis.SELF_AUTHORED:
        return "first_claimant_owns"
    if authority is OrganizationAuthorityBasis.OBSERVATION:
        return "shared_use"
    return "unknown"


def _occurrence_anchor(
    occurrence: object,
) -> tuple[str, str]:
    facts = getattr(occurrence, "public_facts", {}) or {}
    kind = getattr(occurrence, "kind", "")

    def _fact_text(name: str) -> str | None:
        value = facts.get(name)
        if type(value) is str and value:
            return value
        if isinstance(value, (tuple, list)) and value:
            first = value[0]
            if type(first) is str and first:
                return first
        return None

    if kind in ("taken", "taken_from_corpse", "dropped"):
        anchor = _fact_text("item_ids") or _fact_text("item_id")
        return ("item", anchor) if anchor else ("unknown", "unknown")
    if kind == "given":
        anchor = _fact_text("item_id") or _fact_text("target_id")
        return ("item", anchor) if anchor else ("unknown", "unknown")
    if kind == "item_stored":
        anchor = _fact_text("target_id")
        if anchor is None:
            destination = getattr(occurrence, "destination_id", None)
            anchor = None if destination is None else destination.value
        return ("structure", anchor) if anchor else ("unknown", "unknown")
    if kind.startswith("artifact_"):
        anchor = _fact_text("artifact_id")
        return ("artifact", anchor) if anchor else ("unknown", "unknown")
    if kind.startswith("repository_"):
        anchor = _fact_text("target_id")
        if anchor is None:
            destination = getattr(occurrence, "destination_id", None)
            anchor = None if destination is None else destination.value
        return ("repository", anchor) if anchor else ("unknown", "unknown")
    if kind == "project_contributed":
        anchor = _fact_text("project_id") or _fact_text("target_id")
        return ("collective_project", anchor) if anchor else ("unknown", "unknown")
    if kind.startswith("public_good_"):
        anchor = _fact_text("target_id") or _fact_text("structure_id")
        return ("structure", anchor) if anchor else ("unknown", "unknown")
    return "unknown", "unknown"


def _concept_matches_occurrence(
    concept: object,
    occurrence: object,
    anchor: tuple[str, str],
) -> bool:
    member_ids = {member.member_id for member in concept.members}
    for field_name in ("actor_id", "other_entity_id", "destination_id"):
        value = getattr(occurrence, field_name, None)
        if value is not None and value.value in member_ids:
            return True
    anchor_kind, anchor_id = anchor
    if anchor_kind == "unknown":
        return False
    for collection in (
        concept.resources,
        concept.procedures,
        concept.records,
    ):
        for item in collection:
            if getattr(item, "anchor_id", None) == anchor_id:
                return True
    return False


def _occurrence_outcome(occurrence: object) -> OrganizationOperationOutcome:
    success = getattr(occurrence, "success", None)
    if success is True:
        return OrganizationOperationOutcome.COMPLETED
    if success is False:
        return OrganizationOperationOutcome.BLOCKED
    if success is None:
        return OrganizationOperationOutcome.OBSERVED
    return OrganizationOperationOutcome.UNKNOWN


def _occurrence_records(
    occurrence: object,
    *,
    organization_id: str,
    owner_id: AgentId,
    tick: int,
) -> tuple[OrganizationDecisionRecord, OrganizationActionRecord] | None:
    kind = getattr(occurrence, "kind", "")
    mapping = _SOURCE_KIND_DOMAINS.get(kind)
    if mapping is None:
        return None
    domain, act, command_kind = mapping
    anchor_kind, anchor_id = _occurrence_anchor(occurrence)
    actor = getattr(occurrence, "actor_id", None)
    actor_id = "unknown" if actor is None else actor.value
    target = getattr(occurrence, "other_entity_id", None)
    target_id = None if target is None else target.value
    outcome = _occurrence_outcome(occurrence)
    decision_id = organization_decision_id(
        owner_id.value,
        organization_id,
        domain.value,
        act.value,
        tick,
        actor_id,
        target_id or "",
        anchor_kind,
        anchor_id,
        OrganizationDecisionStance.SUPPORTED.value,
    )
    action_id = organization_action_id(
        owner_id.value,
        organization_id,
        decision_id,
        tick,
        actor_id,
        command_kind,
        anchor_kind,
        anchor_id,
    )
    ref = _evidence_ref(
        owner_id, organization_id, "observation", tick, 0, kind
    )
    decision = OrganizationDecisionRecord(
        decision_id=decision_id,
        domain=domain,
        act=act,
        actor_id=actor_id,
        target_id=target_id,
        anchor_kind=anchor_kind,
        anchor_id=anchor_id,
        authority_basis=OrganizationAuthorityBasis.OBSERVATION,
        stance=OrganizationDecisionStance.SUPPORTED,
        support_count=0,
        oppose_count=0,
        provenance_code=OrganizationOperationProvenance.OBSERVED_EFFECT,
        tick=tick,
        evidence_refs=(ref,),
    )
    action = OrganizationActionRecord(
        action_id=action_id,
        decision_id=decision_id,
        domain=domain,
        act=act,
        actor_id=actor_id,
        command_kind=command_kind,
        anchor_kind=anchor_kind,
        anchor_id=anchor_id,
        outcome=outcome,
        provenance_code=(
            OrganizationOperationProvenance.OBSERVED_EFFECT
            if outcome
            in (
                OrganizationOperationOutcome.COMPLETED,
                OrganizationOperationOutcome.OBSERVED,
            )
            else OrganizationOperationProvenance.UNKNOWN_AUTHORITY
        ),
        tick=tick,
        evidence_refs=(ref,),
    )
    return decision, action


def _concept_commitment_records(
    concept: object,
    *,
    owner_id: AgentId,
    tick: int,
) -> tuple[OrganizationCommitmentOperationBelief, ...]:
    records: list[OrganizationCommitmentOperationBelief] = []
    for belief in concept.commitments:
        ref = _evidence_ref(
            owner_id,
            concept.organization_id,
            "owner_ledger",
            tick,
            0,
            belief.commitment_id,
        )
        records.append(
            OrganizationCommitmentOperationBelief(
                commitment_id=belief.commitment_id,
                role=belief.role,
                counterpart_id=belief.counterpart_id,
                stance=OrganizationCommitmentStance.DECLARED,
                authority_basis=OrganizationAuthorityBasis.UNKNOWN,
                decision_ref=None,
                due_tick=belief.due_tick,
                first_tick=belief.first_tick,
                last_tick=max(belief.last_tick, tick),
                owner_support_count=1,
                contest_count=0,
                evidence_refs=(ref,),
            )
        )
    return tuple(records)


def _collect_operation_evidence(
    *,
    owner_id: AgentId,
    tick: int,
    observation: object,
    prior: object | None,
    organization_concepts: object | None,
    offices: object | None,
    collective_decisions: object | None,
    structured_commitments: object | None,
    possession_legitimacy: object | None,
    policy: OrganizationOperationPolicy | None = None,
) -> _OperationEvidence:
    """Collect owner-only evidence without materializing the ledger."""

    from agents.cognition.organization_concepts import (
        OrganizationConceptLedger,
        OrganizationStatus,
    )
    from agents.cognition.organization_operations_communication import (
        parse_organization_operation_claim_relation,
    )

    owner = _require_owner_id(owner_id)
    if policy is not None and type(policy) is not OrganizationOperationPolicy:
        _fail("organization_operation_policy_mismatch")
    current_tick = require_organization_tick(tick)
    if prior is not None and type(prior) is not OrganizationOperationLedger:
        _fail("organization_operation_invalid")
    if prior is not None and prior.owner_id != owner:
        _fail("organization_operation_foreign_ledger")
    if organization_concepts is None:
        return _OperationEvidence(owner_id=owner, tick=current_tick)
    if type(organization_concepts) is not OrganizationConceptLedger:
        _fail("organization_operation_invalid")
    if organization_concepts.owner_id != owner:
        _fail("organization_operation_foreign_ledger")

    owner_entity = getattr(observation, "observer_id", None)
    owner_entity_value = (
        owner.value if owner_entity is None else owner_entity.value
    )
    bundles: dict[str, dict[str, list[object]]] = {}
    notices: set[str] = set()

    for concept in sorted(
        organization_concepts.concepts, key=lambda item: item.organization_id
    ):
        if concept.status in (
            OrganizationStatus.DISSOLVED,
            OrganizationStatus.RETIRED,
        ):
            continue
        bundles[concept.organization_id] = {
            family: [] for family in _BUNDLE_FAMILIES
        }

    identity_labels: dict[str, set[str]] = {}
    for concept in organization_concepts.concepts:
        labels = {
            identity.label_token
            for identity in concept.identities
            if identity.label_token is not None
        }
        identity_labels[concept.organization_id] = labels

    def _resolve_concept(label_token: str | None) -> str | None:
        if label_token is not None:
            for organization_id in sorted(identity_labels):
                if label_token in identity_labels[organization_id]:
                    return organization_id
            return None
        active = sorted(bundles)
        return active[0] if len(active) == 1 else None

    concept_by_id = {
        concept.organization_id: concept
        for concept in organization_concepts.concepts
    }

    for concept in organization_concepts.concepts:
        bundle = bundles.get(concept.organization_id)
        if bundle is None:
            continue
        for record in _concept_commitment_records(
            concept, owner_id=owner, tick=current_tick
        ):
            bundle["commitments"].append(record)

    occurrences = getattr(observation, "occurrences", ()) or ()
    for occurrence in occurrences:
        anchor = _occurrence_anchor(occurrence)
        for concept in organization_concepts.concepts:
            bundle = bundles.get(concept.organization_id)
            if bundle is None:
                continue
            if not _concept_matches_occurrence(concept, occurrence, anchor):
                continue
            records = _occurrence_records(
                occurrence,
                organization_id=concept.organization_id,
                owner_id=owner,
                tick=current_tick,
            )
            if records is None:
                continue
            decision, action = records
            bundle["decisions"].append(decision)
            bundle["actions"].append(action)
            if anchor[0] == "unknown":
                notices.add("operation_anchor_unresolved")

    communications = getattr(observation, "communications", ()) or ()
    for communication in communications:
        speaker = getattr(communication, "speaker_id", None)
        listener = getattr(communication, "listener_id", None)
        speaker_value = None if speaker is None else speaker.value
        listener_value = None if listener is None else listener.value
        if owner_entity_value not in (speaker_value, listener_value):
            continue
        utterance = getattr(communication, "utterance", None)
        content = getattr(utterance, "content", None)
        relations = () if content is None else content.relations
        for relation in relations:
            claim = parse_organization_operation_claim_relation(relation)
            if claim is None:
                continue
            organization_id = _resolve_concept(claim.label_token)
            if organization_id is None:
                notices.add("operation_anchor_unresolved")
                continue
            bundle = bundles.get(organization_id)
            if bundle is None:
                continue
            concept = concept_by_id[organization_id]
            authority = _claim_authority(
                claim,
                owner_entity=owner_entity_value,
                speaker=speaker_value or "unknown",
                offices=offices,
                collective_decisions=collective_decisions,
            )
            domain = _claim_domain(claim.act, claim.anchor_kind)
            anchor_kind, anchor_id = _claim_anchor_material(claim)
            support, oppose = _position_counts(collective_decisions, owner)
            decision_id = organization_decision_id(
                owner.value,
                organization_id,
                domain.value,
                claim.act.value,
                current_tick,
                speaker_value or "unknown",
                claim.target_ref or "",
                anchor_kind,
                anchor_id,
                claim.stance,
            )
            stance = (
                OrganizationDecisionStance.CONTESTED
                if claim.stance == "disputed"
                else (
                    OrganizationDecisionStance.SUPPORTED
                    if claim.stance
                    in ("admitted", "assigned", "recognized", "fulfilled", "declared")
                    else OrganizationDecisionStance.UNKNOWN
                )
            )
            provenance = _claim_provenance(
                authority, act=claim.act, stance=claim.stance
            )
            if claim.expires_tick is not None and claim.expires_tick <= current_tick:
                provenance = OrganizationOperationProvenance.EXPIRED
                notices.add("operation_expired")
            ref = _evidence_ref(
                owner,
                organization_id,
                "communication",
                current_tick,
                0,
                "|".join(
                    (
                        claim.act.value,
                        claim.stance,
                        claim.target_ref or "",
                        anchor_id,
                    )
                ),
            )
            decision = OrganizationDecisionRecord(
                decision_id=decision_id,
                domain=domain,
                act=claim.act,
                actor_id=speaker_value or "unknown",
                target_id=claim.target_ref,
                anchor_kind=anchor_kind,
                anchor_id=anchor_id,
                authority_basis=authority,
                stance=stance,
                support_count=support,
                oppose_count=oppose,
                provenance_code=provenance,
                tick=current_tick,
                evidence_refs=(ref,),
            )
            bundle["decisions"].append(decision)
            for family, values in _claim_beliefs(
                claim,
                organization_id=concept.organization_id,
                owner_id=owner,
                tick=current_tick,
                authority=authority,
                decision_ref=decision_id,
            ).items():
                bundle[family].extend(values)

    ordered = tuple(
        (organization_id, _EvidenceBundle(**{
            family: tuple(bundles[organization_id][family])
            for family in _BUNDLE_FAMILIES
        }, notices=tuple(sorted(notices))))
        for organization_id in sorted(bundles)
    )
    evidence = _OperationEvidence(
        owner_id=owner,
        tick=current_tick,
        by_concept=ordered,
        notices=tuple(sorted(notices)),
    )
    _LOG.debug(
        "organization_operation_evidence owner_id=%s concepts=%s decisions=%s "
        "actions=%s tick=%s",
        owner.value,
        len(evidence.by_concept),
        sum(len(bundle.decisions) for _, bundle in evidence.by_concept),
        sum(len(bundle.actions) for _, bundle in evidence.by_concept),
        current_tick,
    )
    return evidence


_STANCE_ORDER: Final[Mapping[str, int]] = MappingProxyType(
    {
        "disputed": 9,
        "recognized": 8,
        "admitted": 8,
        "assigned": 8,
        "shared": 7,
        "claimed": 6,
        "declared": 6,
        "accepted": 6,
        "self_joined": 5,
        "unknown": 4,
        "former": 3,
        "removed": 3,
        "vacant": 3,
        "resigned": 3,
        "expelled": 3,
        "departed": 3,
        "denied": 3,
        "fulfilled": 3,
        "violated": 3,
        "forgotten": 3,
    }
)

_FAMILY_KEYS: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "controls": ("domain", "anchor_kind", "anchor_id"),
        "admissions": ("member_id",),
        "departures": ("member_id",),
        "assignments": ("office_id", "occupant_id"),
        "procedures": ("procedure_ref", "command_kind", "actor_id"),
        "commitments": ("commitment_id", "role", "counterpart_id"),
    }
)

_FAMILY_CAPS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "controls": "max_controls",
        "admissions": "max_admissions",
        "departures": "max_departures",
        "assignments": "max_assignments",
        "procedures": "max_procedures",
        "commitments": "max_commitments",
        "decisions": "max_decisions",
        "actions": "max_actions",
    }
)


def _record_key(record: object, fields: tuple[str, ...]) -> tuple[str, ...]:
    values: list[str] = []
    for name in fields:
        value = getattr(record, name)
        values.append(value.value if isinstance(value, StrEnum) else str(value))
    return tuple(values)


def _record_stance(record: object) -> str:
    stance = getattr(record, "stance", None)
    if isinstance(stance, StrEnum):
        return stance.value
    if type(stance) is str:
        return stance
    return "unknown"


def _merge_family(
    existing: tuple[object, ...],
    incoming: tuple[object, ...],
    *,
    key_fields: tuple[str, ...],
) -> list[object]:
    merged: dict[tuple[str, ...], object] = {}
    order: list[tuple[str, ...]] = []
    for record in (*existing, *incoming):
        key = _record_key(record, key_fields)
        current = merged.get(key)
        if current is None:
            merged[key] = record
            order.append(key)
            continue
        support = min(
            _DEFAULT_OPERATION_POLICY.max_owner_support,
            getattr(current, "owner_support_count", 1)
            + getattr(record, "owner_support_count", 1),
        )
        stance = _record_stance(current)
        other_stance = _record_stance(record)
        contest = getattr(current, "contest_count", 0) + getattr(
            record, "contest_count", 0
        )
        if stance != other_stance:
            stance = "disputed"
            contest = max(1, contest)
        elif stance == "disputed":
            contest = max(1, contest)
        contest = min(_DEFAULT_OPERATION_POLICY.max_contest, contest)
        first = min(
            current.first_tick, record.first_tick
        )
        last = max(current.last_tick, record.last_tick)
        decision_ref = getattr(record, "decision_ref", None) or getattr(
            current, "decision_ref", None
        )
        refs = tuple(
            sorted(
                set(getattr(current, "evidence_refs", ()))
                | set(getattr(record, "evidence_refs", ()))
            )
        )[: _DEFAULT_OPERATION_POLICY.max_evidence_per_record]
        merged[key] = replace(
            current,
            owner_support_count=support,
            contest_count=contest,
            stance=type(current.stance)(stance),
            first_tick=first,
            last_tick=last,
            decision_ref=decision_ref,
            evidence_refs=refs,
        )
    return [merged[key] for key in order]


def _dedupe(records: tuple[object, ...], id_field: str) -> list[object]:
    seen: set[str] = set()
    result: list[object] = []
    for record in records:
        identifier = getattr(record, id_field)
        if identifier in seen:
            continue
        seen.add(identifier)
        result.append(record)
    return result


def _trim_family(
    records: list[object],
    cap: int,
    *,
    tick_field: str,
    key_fields: tuple[str, ...],
) -> tuple[list[object], bool]:
    if len(records) <= cap:
        return records, False
    ordered = sorted(
        records,
        key=lambda item: (getattr(item, tick_field), _record_key(item, key_fields)),
    )
    return ordered[-cap:], True


def _apply_admission_expiry(
    admissions: list[object], tick: int, notices: set[str]
) -> list[object]:
    result: list[object] = []
    for record in admissions:
        if (
            getattr(record, "temporal_scope", None)
            is OrganizationTemporalScope.TEMPORARY
            and getattr(record, "expires_tick", None) is not None
            and record.expires_tick <= tick
        ):
            record = replace(
                record,
                stance=OrganizationAdmissionStance.FORMER,
                contest_count=min(
                    _DEFAULT_OPERATION_POLICY.max_contest,
                    record.contest_count + 1,
                ),
            )
            notices.add("operation_expired")
        result.append(record)
    return result


def _trim_total(
    families: Mapping[str, list[object]],
    *,
    organization_id: str,
    notices: set[str],
) -> dict[str, list[object]]:
    total = sum(len(values) for values in families.values())
    policy = _DEFAULT_OPERATION_POLICY
    if total <= policy.max_total_records:
        return dict(families)
    entries: list[tuple[int, str, str, tuple[str, ...]]] = []
    for family, values in families.items():
        for record in values:
            tick_field = "tick" if family in ("decisions", "actions") else "last_tick"
            key = _family_record_key(family, record)
            entries.append(
                (getattr(record, tick_field), organization_id, family, key)
            )
    drop = total - policy.max_total_records
    entries.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
    drop_keys = {
        (organization_id, family, key)
        for _, organization_id, family, key in entries[:drop]
    }
    trimmed: dict[str, list[object]] = {}
    for family, values in families.items():
        kept: list[object] = []
        for record in values:
            key = _family_record_key(family, record)
            if (organization_id, family, key) in drop_keys:
                continue
            kept.append(record)
        trimmed[family] = kept
    notices.add("operations_truncated")
    return trimmed


def _family_record_key(family: str, record: object) -> tuple[str, ...]:
    if family == "decisions":
        return (record.decision_id,)
    if family == "actions":
        return (record.action_id,)
    return _record_key(record, _FAMILY_KEYS[family])


def apply_organization_operation_update(
    *,
    owner_id: AgentId,
    tick: int,
    observation: object,
    prior: object | None,
    organization_concepts: object | None,
    offices: object | None,
    collective_decisions: object | None,
    structured_commitments: object | None,
    possession_legitimacy: object | None,
    policy: OrganizationOperationPolicy | None = None,
) -> OrganizationOperationLedger:
    """Materialize one owner's operational sidecar ledger."""

    from agents.cognition.organization_concepts import (
        OrganizationConceptLedger,
        OrganizationStatus,
    )

    owner = _require_owner_id(owner_id)
    active_policy = (
        _DEFAULT_OPERATION_POLICY if policy is None else policy
    )
    if type(active_policy) is not OrganizationOperationPolicy:
        _fail("organization_operation_policy_mismatch")
    current_tick = require_organization_tick(tick)
    if prior is not None:
        if type(prior) is not OrganizationOperationLedger:
            raise TypeError("prior must be OrganizationOperationLedger or None")
        if prior.owner_id != owner:
            _fail("organization_operation_foreign_ledger")
    if organization_concepts is not None:
        if type(organization_concepts) is not OrganizationConceptLedger:
            raise TypeError(
                "organization_concepts must be OrganizationConceptLedger or None"
            )
        if organization_concepts.owner_id != owner:
            _fail("organization_operation_foreign_ledger")

    evidence = _collect_operation_evidence(
        owner_id=owner,
        tick=current_tick,
        observation=observation,
        prior=prior,
        organization_concepts=organization_concepts,
        offices=offices,
        collective_decisions=collective_decisions,
        structured_commitments=structured_commitments,
        possession_legitimacy=possession_legitimacy,
        policy=active_policy,
    )
    if organization_concepts is None:
        return empty_organization_operation_ledger(owner, active_policy)

    prior_concepts = {}
    if prior is not None:
        prior_concepts = {
            concept.organization_id: concept for concept in prior.concepts
        }
    evidence_by_id = dict(evidence.by_concept)
    concept_status = {
        concept.organization_id: concept.status
        for concept in organization_concepts.concepts
    }
    ledger_notices: set[str] = set(evidence.notices)
    concepts: list[OrganizationOperationalConcept] = []

    for organization_id in sorted(set(prior_concepts) | set(evidence_by_id)):
        previous = prior_concepts.get(organization_id)
        bundle = evidence_by_id.get(organization_id, _EvidenceBundle())
        families: dict[str, list[object]] = {
            family: [] for family in _BUNDLE_FAMILIES
        }
        if previous is not None:
            for family in _BUNDLE_FAMILIES:
                families[family].extend(getattr(previous, family))
        for family, key_fields in _FAMILY_KEYS.items():
            families[family] = _merge_family(
                tuple(families[family]),
                getattr(bundle, family),
                key_fields=key_fields,
            )
        families["decisions"] = _dedupe(
            (*families["decisions"], *bundle.decisions), "decision_id"
        )
        families["actions"] = _dedupe(
            (*families["actions"], *bundle.actions), "action_id"
        )

        status = OrganizationOperationalStatus.ACTIVE
        notices: set[str] = set(bundle.notices)
        if organization_id not in concept_status:
            status = OrganizationOperationalStatus.ORPHANED
            notices.add("operations_orphaned")
            ledger_notices.add("operations_orphaned")
        elif concept_status[organization_id] in (
            OrganizationStatus.DISSOLVED,
            OrganizationStatus.RETIRED,
        ):
            status = OrganizationOperationalStatus.DISSOLVED

        families["admissions"] = _apply_admission_expiry(
            families["admissions"], current_tick, notices
        )

        for family, cap_name in _FAMILY_CAPS.items():
            if family == "controls":
                continue
            cap = getattr(active_policy, cap_name)
            tick_field = "tick" if family in ("decisions", "actions") else "last_tick"
            if family in ("decisions", "actions"):
                key_fields = (
                    ("decision_id",) if family == "decisions" else ("action_id",)
                )
            else:
                key_fields = _FAMILY_KEYS[family]
            families[family], truncated = _trim_family(
                families[family],
                cap,
                tick_field=tick_field,
                key_fields=key_fields,
            )
            if truncated:
                notices.add("operations_truncated")
                ledger_notices.add("operations_truncated")

        if families["controls"]:
            per_domain: dict[str, list[object]] = {}
            for record in families["controls"]:
                per_domain.setdefault(record.domain.value, []).append(record)
            trimmed_controls: list[object] = []
            for domain in sorted(per_domain):
                values, truncated = _trim_family(
                    per_domain[domain],
                    16,
                    tick_field="last_tick",
                    key_fields=("domain", "anchor_kind", "anchor_id"),
                )
                trimmed_controls.extend(values)
                if truncated:
                    notices.add("operations_truncated")
                    ledger_notices.add("operations_truncated")
            families["controls"], truncated = _trim_family(
                trimmed_controls,
                active_policy.max_controls,
                tick_field="last_tick",
                key_fields=("domain", "anchor_kind", "anchor_id"),
            )
            if truncated:
                notices.add("operations_truncated")
                ledger_notices.add("operations_truncated")

        families = _trim_total(
            families,
            organization_id=organization_id,
            notices=notices,
        )
        if "operations_truncated" in notices:
            ledger_notices.add("operations_truncated")

        remaining_decisions = {
            record.decision_id for record in families["decisions"]
        }
        for family in _FAMILY_KEYS:
            families[family] = [
                replace(record, decision_ref=None)
                if getattr(record, "decision_ref", None) is not None
                and record.decision_ref not in remaining_decisions
                else record
                for record in families[family]
            ]
        rewritten_actions: list[object] = []
        for action in families["actions"]:
            if (
                action.decision_id is not None
                and action.decision_id not in remaining_decisions
            ):
                action = replace(action, decision_id=None)
            rewritten_actions.append(action)
        families["actions"] = rewritten_actions

        if any(
            action.decision_id is None for action in families["actions"]
        ) and bundle.actions:
            ledger_notices.add("operations_orphaned")

        if any(
            getattr(record, "authority_basis", None)
            is OrganizationAuthorityBasis.UNKNOWN
            for family in _BUNDLE_FAMILIES
            for record in families[family]
        ):
            notices.add("authority_unresolved")
            ledger_notices.add("authority_unresolved")
        if any(
            getattr(record, "contest_count", 0) > 0
            for family in _BUNDLE_FAMILIES
            for record in families[family]
        ):
            notices.add("contest_unresolved")
            ledger_notices.add("contest_unresolved")
        if any(
            getattr(record, "anchor_kind", None) == "unknown"
            for record in (
                *families["controls"],
                *families["decisions"],
                *families["actions"],
            )
        ):
            notices.add("operation_anchor_unresolved")
            ledger_notices.add("operation_anchor_unresolved")

        total = sum(len(values) for values in families.values())
        if total == 0:
            continue
        spans = [
            getattr(record, "last_tick", current_tick)
            for family in _BUNDLE_FAMILIES
            for record in families[family]
        ]
        first = (
            previous.first_tick
            if previous is not None
            else min([current_tick, *spans])
        )
        last = max([current_tick, *spans])

        concept = OrganizationOperationalConcept(
            organization_id=organization_id,
            owner_id=owner,
            status=status,
            first_tick=first,
            last_tick=last,
            controls=tuple(families["controls"]),
            admissions=tuple(families["admissions"]),
            departures=tuple(families["departures"]),
            assignments=tuple(families["assignments"]),
            procedures=tuple(families["procedures"]),
            commitments=tuple(families["commitments"]),
            decisions=tuple(families["decisions"]),
            actions=tuple(families["actions"]),
            notices=tuple(sorted(notices)),
        )
        concepts.append(concept)

    concepts.sort(key=lambda item: item.organization_id)
    ledger = OrganizationOperationLedger(
        owner_id=owner,
        concepts=tuple(concepts),
        notices=tuple(sorted(ledger_notices)),
        policy_version=ORGANIZATION_OPERATION_POLICY_VERSION,
    )
    _LOG.debug(
        "organization_operations_update owner_id=%s concepts=%s controls=%s "
        "decisions=%s actions=%s tick=%s",
        owner.value,
        len(ledger.concepts),
        sum(len(item.controls) for item in ledger.concepts),
        sum(len(item.decisions) for item in ledger.concepts),
        sum(len(item.actions) for item in ledger.concepts),
        current_tick,
    )
    return ledger
