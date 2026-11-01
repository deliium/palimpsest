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
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final, NoReturn

from agents.cognition.organization_concepts import ORGANIZATION_ID_HEX_LEN

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
