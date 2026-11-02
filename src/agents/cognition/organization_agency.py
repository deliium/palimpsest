"""Closed owner-scoped organization collective-agency vocabulary.

A collective decision is an owner-scoped belief about a recognized collective
process: a proposal, the discussion around it, support and opposition,
abstention, amendments, a believed recognized procedure, a recorded outcome, and
each expected actor's individual implementation or compliance. It is never an
organization will, never an objective actor, and never a command source. Every
physical effect remains an ordinary agent command admitted by ``WorldEngine``.

This module defines only the frozen vocabulary, identity grammar, policy bounds,
and error codes that later collective-agency code consumes. It creates no
organization actor, roster, treasury, resource pool, registry, executor, global
``OrganizationLLM``, or independent cognition engine.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final, NoReturn, cast

from agents.cognition.organization_concepts import (
    FORBIDDEN_ORGANIZATION_FIELD_NAMES,
    ORGANIZATION_ID_HEX_LEN,
    OrganizationStatus,
    require_organization_concept_id,
)
from agents.cognition.organization_operations import (
    FORBIDDEN_OPERATION_FIELD_NAMES,
    OrganizationAuthorityBasis,
    OrganizationOperationDomain,
)
from agents.models import AgentId

if TYPE_CHECKING:  # pragma: no cover - typing only
    from agents.cognition.organization_agency_communication import (
        OrganizationAgencyClaim,
    )

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.organization_agency")

ORGANIZATION_AGENCY_POLICY_VERSION: Final[str] = "organization-agency.v1"
ORGANIZATION_AGENCY_ANALYSIS_POLICY_VERSION: Final[str] = (
    "organization-agency-analysis.v1"
)

ORGANIZATION_PROPOSAL_ID_PREFIX: Final[str] = "orgp-"
ORGANIZATION_AMENDMENT_ID_PREFIX: Final[str] = "orgpm-"
ORGANIZATION_COLLECTIVE_DECISION_ID_PREFIX: Final[str] = "orgcd-"
ORGANIZATION_IMPLEMENTATION_ID_PREFIX: Final[str] = "orgci-"
ORGANIZATION_AGENCY_EVIDENCE_ID_PREFIX: Final[str] = "orgcev-"
ORGANIZATION_PUBLICATION_DECISION_ID_PREFIX: Final[str] = "orgcpd-"
ORGANIZATION_PUBLICATION_IMPLEMENTATION_ID_PREFIX: Final[str] = "orgcpi-"

_PROPOSAL_NAMESPACE: Final[str] = "palimpsest.organization.agency.proposal.v1"
_AMENDMENT_NAMESPACE: Final[str] = "palimpsest.organization.agency.amendment.v1"
_DECISION_NAMESPACE: Final[str] = (
    "palimpsest.organization.agency.collective-decision.v1"
)
_IMPLEMENTATION_NAMESPACE: Final[str] = (
    "palimpsest.organization.agency.implementation.v1"
)
_EVIDENCE_NAMESPACE: Final[str] = "palimpsest.organization.agency.evidence.v1"
_PUBLICATION_DECISION_NAMESPACE: Final[str] = (
    "palimpsest.organization.agency.publication-decision.v1"
)
_PUBLICATION_IMPLEMENTATION_NAMESPACE: Final[str] = (
    "palimpsest.organization.agency.publication-implementation.v1"
)
_REF_NAMESPACE: Final[str] = "palimpsest.organization.agency.ref.v1"

_PROPOSAL_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{ORGANIZATION_PROPOSAL_ID_PREFIX}[0-9a-f]{{{ORGANIZATION_ID_HEX_LEN}}}$"
)
_AMENDMENT_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{ORGANIZATION_AMENDMENT_ID_PREFIX}[0-9a-f]{{{ORGANIZATION_ID_HEX_LEN}}}$"
)
_DECISION_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{ORGANIZATION_COLLECTIVE_DECISION_ID_PREFIX}"
    rf"[0-9a-f]{{{ORGANIZATION_ID_HEX_LEN}}}$"
)
_IMPLEMENTATION_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{ORGANIZATION_IMPLEMENTATION_ID_PREFIX}"
    rf"[0-9a-f]{{{ORGANIZATION_ID_HEX_LEN}}}$"
)
_EVIDENCE_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{ORGANIZATION_AGENCY_EVIDENCE_ID_PREFIX}"
    rf"[0-9a-f]{{{ORGANIZATION_ID_HEX_LEN}}}$"
)
_PUBLICATION_DECISION_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{ORGANIZATION_PUBLICATION_DECISION_ID_PREFIX}"
    rf"[0-9a-f]{{{ORGANIZATION_ID_HEX_LEN}}}$"
)
_PUBLICATION_IMPLEMENTATION_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{ORGANIZATION_PUBLICATION_IMPLEMENTATION_ID_PREFIX}"
    rf"[0-9a-f]{{{ORGANIZATION_ID_HEX_LEN}}}$"
)
_REF_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^[0-9a-f]{{{ORGANIZATION_ID_HEX_LEN}}}$"
)

ORGANIZATION_AGENCY_REF_NAMESPACES: Final[frozenset[str]] = frozenset(
    {
        "proposal",
        "terms",
        "procedure",
        "target",
        "actor",
        "decision",
    }
)


class OrganizationAgencyTopic(StrEnum):
    """Closed subject of one collective proposal."""

    RESOURCE_USE = "resource_use"
    STORAGE = "storage"
    RECORD_KEEPING = "record_keeping"
    MEMBERSHIP = "membership"
    ROLE = "role"
    PROCEDURE = "procedure"
    COMMITMENT = "commitment"
    OTHER = "other"


class OrganizationAgencyProposalStatus(StrEnum):
    """Closed owner-local lifecycle status for one proposal belief."""

    DRAFT = "draft"
    ACTIVE = "active"
    AMENDED = "amended"
    WITHDRAWN = "withdrawn"
    DECIDED = "decided"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class OrganizationAgencyPositionStance(StrEnum):
    """Closed believed stance one participant holds toward a proposal."""

    SUPPORT = "support"
    OPPOSE = "oppose"
    ABSTAIN = "abstain"
    AMEND = "amend"
    WITHDRAW = "withdraw"
    UNKNOWN = "unknown"


class OrganizationAgencyRecognition(StrEnum):
    """Closed owner belief about whether a proposal reached a recognized process."""

    RECOGNIZED = "recognized"
    CONTESTED = "contested"
    UNRECOGNIZED = "unrecognized"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class OrganizationAgencyImplementationStatus(StrEnum):
    """Closed per-actor compliance belief for one collective decision."""

    PENDING = "pending"
    IMPLEMENTED = "implemented"
    PARTIAL = "partial"
    UNIMPLEMENTED = "unimplemented"
    OBSTRUCTED = "obstructed"
    REFUSED = "refused"
    SABOTAGED = "sabotaged"
    CONTRARY = "contrary"
    UNKNOWN = "unknown"
    EXPIRED = "expired"


class OrganizationAgencyImplementationMode(StrEnum):
    """Closed channel through which implementation can be believed."""

    PHYSICAL = "physical"
    TESTIMONIAL = "testimonial"


class OrganizationAgencyReportKind(StrEnum):
    """Closed explicit testimony about one actor's implementation."""

    IMPLEMENTED = "implemented"
    PARTIAL = "partial"
    UNIMPLEMENTED = "unimplemented"
    REFUSAL = "refusal"
    SABOTAGE = "sabotage"


class OrganizationAgencyProvenance(StrEnum):
    """Closed provenance code for one agency record or attribution."""

    SELF_AUTHORED = "self_authored"
    COMMUNICATED = "communicated"
    PROCEDURE_RECOGNIZED = "procedure_recognized"
    OBSERVED_EFFECT = "observed_effect"
    DECLARED_REFUSAL = "declared_refusal"
    CONTRARY_EFFECT = "contrary_effect"
    DECLARED_SABOTAGE = "declared_sabotage"
    CONTESTED = "contested"
    UNRECOGNIZED = "unrecognized"
    EXPIRED = "expired"
    ORPHANED = "orphaned"
    UNKNOWN = "unknown"


class OrganizationAgencyEffect(StrEnum):
    """Closed real observation kind a proposal can require or an actor produce."""

    GIVE = "give"
    ITEM_STORED = "item_stored"
    ARTIFACT_CREATED = "artifact_created"
    ARTIFACT_MODIFIED = "artifact_modified"
    ARTIFACT_DESTROYED = "artifact_destroyed"
    REPOSITORY_MEMBER_DEPOSITED = "repository_member_deposited"
    REPOSITORY_MEMBER_RETRIEVED = "repository_member_retrieved"
    REPOSITORY_ESTABLISHED = "repository_established"
    REPOSITORY_MAINTAINED = "repository_maintained"
    STRUCTURE_BUILT = "structure_built"
    STRUCTURE_REPAIRED = "structure_repaired"
    RESOURCE_HARVESTED = "resource_harvested"
    ITEM_CRAFTED = "item_crafted"
    PROJECT_CONTRIBUTED = "project_contributed"
    PUBLIC_GOOD_MAINTAINED = "public_good_maintained"
    PUBLIC_GOOD_OPPOSED = "public_good_opposed"
    PUBLIC_GOOD_BENEFIT = "public_good_benefit"
    HELP = "help"
    FEED = "feed"
    TRANSPORT = "transport"
    MOVE = "move"
    ATTACK = "attack"
    COMMITMENT_DECLARED = "commitment_declared"
    EXCHANGE_COMPLETED = "exchange_completed"
    NONE = "none"


ORGANIZATION_AGENCY_EFFECTS: Final[frozenset[str]] = frozenset(
    {
        "give",
        "item_stored",
        "artifact_created",
        "artifact_modified",
        "artifact_destroyed",
        "repository_member_deposited",
        "repository_member_retrieved",
        "repository_established",
        "repository_maintained",
        "structure_built",
        "structure_repaired",
        "resource_harvested",
        "item_crafted",
        "project_contributed",
        "public_good_maintained",
        "public_good_opposed",
        "public_good_benefit",
        "help",
        "feed",
        "transport",
        "move",
        "attack",
        "commitment_declared",
        "exchange_completed",
        "none",
    }
)

ORGANIZATION_AGENCY_CONTRARY_EFFECTS: Final[frozenset[str]] = frozenset(
    {
        "attack",
        "artifact_destroyed",
        "artifact_damaged",
        "artifact_partially_lost",
        "public_good_opposed",
        "take",
        "drop",
    }
)

_NON_DESTRUCTIVE_EFFECTS: Final[frozenset[str]] = (
    ORGANIZATION_AGENCY_EFFECTS - ORGANIZATION_AGENCY_CONTRARY_EFFECTS
)

ORGANIZATION_AGENCY_DOMAIN_EFFECTS: Final[
    Mapping[OrganizationOperationDomain, frozenset[str]]
] = MappingProxyType(
    {
        OrganizationOperationDomain.RESOURCE_CONTROL: frozenset(
            {"give", "item_stored", "resource_harvested", "none"}
        ),
        OrganizationOperationDomain.STORAGE: frozenset(
            {
                "item_stored",
                "repository_member_deposited",
                "repository_established",
                "repository_maintained",
                "none",
            }
        ),
        OrganizationOperationDomain.RECORD_KEEPING: frozenset(
            {
                "artifact_created",
                "artifact_modified",
                "repository_member_deposited",
                "repository_member_retrieved",
                "none",
            }
        ),
        OrganizationOperationDomain.MEMBERSHIP_ADMISSION: frozenset({"none"}),
        OrganizationOperationDomain.MEMBERSHIP_DEPARTURE: frozenset({"none"}),
        OrganizationOperationDomain.ROLE_ASSIGNMENT: frozenset({"none"}),
        OrganizationOperationDomain.PROCEDURE_ACTION: _NON_DESTRUCTIVE_EFFECTS,
        OrganizationOperationDomain.INTERNAL_COMMITMENT: frozenset(
            {
                "commitment_declared",
                "give",
                "help",
                "feed",
                "transport",
                "none",
            }
        ),
    }
)

ORGANIZATION_AGENCY_TARGET_KINDS: Final[frozenset[str]] = frozenset(
    {
        "item",
        "resource",
        "artifact",
        "structure",
        "repository",
        "collective_project",
        "commitment",
        "location",
        "agent",
        "none",
        "unknown",
    }
)

ORGANIZATION_AGENCY_NOTICE_CODES: Final[frozenset[str]] = frozenset(
    {
        "proposal_expired",
        "amendment_out_of_order",
        "procedure_unresolved",
        "target_unresolved",
        "agency_truncated",
        "implementation_truncated",
        "refusal_unverified",
        "sabotage_unverified",
        "orphaned_concept",
        "foreign_owner",
        "malformed_claim",
    }
)

ORGANIZATION_AGENCY_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "organization_agency_invalid",
        "organization_agency_policy_mismatch",
        "organization_agency_foreign_ledger",
        "organization_agency_cap_exceeded",
        "organization_agency_unknown_concept",
        "organization_agency_unknown_proposal",
        "organization_agency_unknown_decision",
        "organization_agency_tick_regression",
        "organization_agency_invalid_ref",
        "organization_agency_duplicate_record",
        "organization_agency_invalid_transition",
        "organization_agency_unresolved_procedure",
    }
)

FORBIDDEN_AGENCY_FIELD_NAMES: Final[frozenset[str]] = (
    FORBIDDEN_OPERATION_FIELD_NAMES
    | FORBIDDEN_ORGANIZATION_FIELD_NAMES
    | frozenset(
        {
            "will",
            "volition",
            "intent",
            "consensus",
            "quorum",
            "majority",
            "binding",
            "enforce",
            "permission",
            "command",
            "organization_llm",
            "global_prompt",
            "collective_prompt",
            "sabotage_intent",
        }
    )
)


class OrganizationAgencyError(ValueError):
    """Stable-code collective-agency violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        if code not in ORGANIZATION_AGENCY_ERROR_CODES:
            raise ValueError("organization_agency_invalid")
        self.code: str = code
        super().__init__(code)


def _fail(code: str) -> NoReturn:
    raise OrganizationAgencyError(code)


@dataclass(frozen=True, slots=True)
class OrganizationAgencyPolicy:
    """Locked owner-local collective-agency bounds.

    Every value is part of the accepted contract. Any deviation is a programming
    error and fails closed. The module constant
    ``ORGANIZATION_AGENCY_POLICY_VERSION`` is authoritative.
    """

    max_concepts: int = 16
    max_proposals: int = 32
    max_positions: int = 64
    max_amendments: int = 32
    max_decisions: int = 32
    max_implementations: int = 64
    max_expected_actors: int = 16
    max_evidence_per_record: int = 8
    max_total_records: int = 256
    max_total_evidence: int = 256
    max_owner_support: int = 32
    max_contest: int = 32
    max_revision: int = 9999
    proposal_window_ticks: int = 16
    implementation_window_ticks: int = 32
    recognition_min_supporters: int = 1
    procedure_min_recurrence: int = 2
    max_decision_implementations: int = 32

    def __post_init__(self) -> None:
        for name, expected in _LOCKED_AGENCY_POLICY_VALUES.items():
            actual = getattr(self, name)
            if type(actual) is not type(expected) or actual != expected:
                _fail("organization_agency_policy_mismatch")


_LOCKED_AGENCY_POLICY_VALUES: Final[Mapping[str, int]] = MappingProxyType(
    {
        "max_concepts": 16,
        "max_proposals": 32,
        "max_positions": 64,
        "max_amendments": 32,
        "max_decisions": 32,
        "max_implementations": 64,
        "max_expected_actors": 16,
        "max_evidence_per_record": 8,
        "max_total_records": 256,
        "max_total_evidence": 256,
        "max_owner_support": 32,
        "max_contest": 32,
        "max_revision": 9999,
        "proposal_window_ticks": 16,
        "implementation_window_ticks": 32,
        "recognition_min_supporters": 1,
        "procedure_min_recurrence": 2,
        "max_decision_implementations": 32,
    }
)

_DEFAULT_AGENCY_POLICY: Final[OrganizationAgencyPolicy] = OrganizationAgencyPolicy()
_POLICY_MILESTONE_LOGGED: bool = False


def default_organization_agency_policy() -> OrganizationAgencyPolicy:
    """Return the single locked collective-agency policy instance."""

    global _POLICY_MILESTONE_LOGGED
    if not _POLICY_MILESTONE_LOGGED:
        _POLICY_MILESTONE_LOGGED = True
        _LOG.debug(
            "organization_agency_policy mode=contract domains=%s cap_concepts=%s",
            len(OrganizationOperationDomain),
            _DEFAULT_AGENCY_POLICY.max_concepts,
        )
    return _DEFAULT_AGENCY_POLICY


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


def require_organization_agency_tick(value: object) -> int:
    """Require an exact non-negative tick; booleans are rejected."""

    if type(value) is not int or value < 0:
        _fail("organization_agency_tick_regression")
    return value


def _require_ordinal(value: object) -> int:
    if type(value) is not int or value < 0:
        _fail("organization_agency_invalid")
    return value


def _digest(namespace: str, material: tuple[str, ...]) -> str:
    payload = "\x1f".join((namespace, *material))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:ORGANIZATION_ID_HEX_LEN]


def organization_proposal_id(
    owner_id: str,
    organization_id: str,
    proposal_ref: str,
) -> str:
    """Mint one owner-local ``orgp-`` proposal id from its public material."""

    body = _digest(
        _PROPOSAL_NAMESPACE,
        (
            _require_text(owner_id, "organization_agency_invalid"),
            _require_text(organization_id, "organization_agency_invalid"),
            require_organization_agency_ref(proposal_ref),
        ),
    )
    return f"{ORGANIZATION_PROPOSAL_ID_PREFIX}{body}"


def organization_amendment_id(
    owner_id: str,
    organization_id: str,
    proposal_id: str,
    revision: int,
    terms_ref: str,
) -> str:
    """Mint one owner-local ``orgpm-`` amendment id from its material."""

    body = _digest(
        _AMENDMENT_NAMESPACE,
        (
            _require_text(owner_id, "organization_agency_invalid"),
            _require_text(organization_id, "organization_agency_invalid"),
            require_organization_proposal_id(proposal_id),
            str(require_organization_agency_tick(revision)),
            require_organization_agency_ref(terms_ref),
        ),
    )
    return f"{ORGANIZATION_AMENDMENT_ID_PREFIX}{body}"


def organization_collective_decision_id(
    owner_id: str,
    organization_id: str,
    proposal_id: str,
    revision: int,
    recognition: str,
    tick: int,
) -> str:
    """Mint one owner-local ``orgcd-`` collective decision id."""

    body = _digest(
        _DECISION_NAMESPACE,
        (
            _require_text(owner_id, "organization_agency_invalid"),
            _require_text(organization_id, "organization_agency_invalid"),
            require_organization_proposal_id(proposal_id),
            str(require_organization_agency_tick(revision)),
            _material_token(recognition, "organization_agency_invalid"),
            str(require_organization_agency_tick(tick)),
        ),
    )
    return f"{ORGANIZATION_COLLECTIVE_DECISION_ID_PREFIX}{body}"


def organization_implementation_id(
    owner_id: str,
    organization_id: str,
    decision_id: str,
    actor_id: str,
    mode: str,
    tick: int,
) -> str:
    """Mint one owner-local ``orgci-`` implementation record id."""

    body = _digest(
        _IMPLEMENTATION_NAMESPACE,
        (
            _require_text(owner_id, "organization_agency_invalid"),
            _require_text(organization_id, "organization_agency_invalid"),
            require_organization_collective_decision_id(decision_id),
            _require_text(actor_id, "organization_agency_invalid"),
            _material_token(mode, "organization_agency_invalid"),
            str(require_organization_agency_tick(tick)),
        ),
    )
    return f"{ORGANIZATION_IMPLEMENTATION_ID_PREFIX}{body}"


def organization_agency_evidence_id(
    owner_id: str,
    organization_id: str,
    source: str,
    tick: int,
    ordinal: int,
    ref: str,
) -> str:
    """Mint one owner-local ``orgcev-`` agency evidence id."""

    body = _digest(
        _EVIDENCE_NAMESPACE,
        (
            _require_text(owner_id, "organization_agency_invalid"),
            _require_text(organization_id, "organization_agency_invalid"),
            _material_token(source, "organization_agency_invalid"),
            str(require_organization_agency_tick(tick)),
            str(_require_ordinal(ordinal)),
            _require_text(ref, "organization_agency_invalid"),
        ),
    )
    return f"{ORGANIZATION_AGENCY_EVIDENCE_ID_PREFIX}{body}"


def organization_publication_decision_id(
    organization_id: str,
    decision_ref: str,
    tick: int,
    ordinal: int,
    content_digest: str,
) -> str:
    """Mint one deterministic published ``orgcpd-`` decision id."""

    body = _digest(
        _PUBLICATION_DECISION_NAMESPACE,
        (
            _require_text(organization_id, "organization_agency_invalid"),
            require_organization_agency_ref(decision_ref),
            str(require_organization_agency_tick(tick)),
            str(_require_ordinal(ordinal)),
            _require_text(content_digest, "organization_agency_invalid"),
        ),
    )
    return f"{ORGANIZATION_PUBLICATION_DECISION_ID_PREFIX}{body}"


def organization_publication_implementation_id(
    organization_id: str,
    decision_id: str,
    actor_ref: str,
    tick: int,
    ordinal: int,
    content_digest: str,
) -> str:
    """Mint one deterministic published ``orgcpi-`` implementation id."""

    body = _digest(
        _PUBLICATION_IMPLEMENTATION_NAMESPACE,
        (
            _require_text(organization_id, "organization_agency_invalid"),
            require_organization_publication_decision_id(decision_id),
            require_organization_agency_ref(actor_ref),
            str(require_organization_agency_tick(tick)),
            str(_require_ordinal(ordinal)),
            _require_text(content_digest, "organization_agency_invalid"),
        ),
    )
    return f"{ORGANIZATION_PUBLICATION_IMPLEMENTATION_ID_PREFIX}{body}"


def organization_agency_ref(value: str, *, namespace: str) -> str:
    """Return a bounded 16-hex reference for one agency frame field.

    ``namespace`` must be exactly ``proposal``, ``terms``, ``procedure``,
    ``target``, ``actor``, or ``decision``. The reference is computed from public
    material, never from an owner id, an owner-local id, or a member set.
    """

    if (
        type(namespace) is not str
        or namespace not in ORGANIZATION_AGENCY_REF_NAMESPACES
    ):
        _fail("organization_agency_invalid_ref")
    text = _require_text(value, "organization_agency_invalid_ref")
    return hashlib.sha256(
        "\x1f".join((_REF_NAMESPACE, namespace, text)).encode("utf-8")
    ).hexdigest()[:ORGANIZATION_ID_HEX_LEN]


def require_organization_proposal_id(
    value: object, code: str = "organization_agency_invalid"
) -> str:
    """Require an owner-local ``orgp-`` proposal identity."""

    if type(value) is not str or _PROPOSAL_ID_PATTERN.match(value) is None:
        _fail(code)
    return value


def require_organization_amendment_id(
    value: object, code: str = "organization_agency_invalid"
) -> str:
    """Require an owner-local ``orgpm-`` amendment identity."""

    if type(value) is not str or _AMENDMENT_ID_PATTERN.match(value) is None:
        _fail(code)
    return value


def require_organization_collective_decision_id(
    value: object, code: str = "organization_agency_invalid"
) -> str:
    """Require an owner-local ``orgcd-`` collective decision identity."""

    if type(value) is not str or _DECISION_ID_PATTERN.match(value) is None:
        _fail(code)
    return value


def require_organization_implementation_id(
    value: object, code: str = "organization_agency_invalid"
) -> str:
    """Require an owner-local ``orgci-`` implementation identity."""

    if type(value) is not str or _IMPLEMENTATION_ID_PATTERN.match(value) is None:
        _fail(code)
    return value


def require_organization_agency_evidence_id(
    value: object, code: str = "organization_agency_invalid"
) -> str:
    """Require an owner-local ``orgcev-`` agency evidence identity."""

    if type(value) is not str or _EVIDENCE_ID_PATTERN.match(value) is None:
        _fail(code)
    return value


def require_organization_publication_decision_id(
    value: object, code: str = "organization_agency_invalid"
) -> str:
    """Require a published ``orgcpd-`` decision identity."""

    if type(value) is not str or _PUBLICATION_DECISION_ID_PATTERN.match(value) is None:
        _fail(code)
    return value


def require_organization_publication_implementation_id(
    value: object, code: str = "organization_agency_invalid"
) -> str:
    """Require a published ``orgcpi-`` implementation identity."""

    if (
        type(value) is not str
        or _PUBLICATION_IMPLEMENTATION_ID_PATTERN.match(value) is None
    ):
        _fail(code)
    return value


def require_organization_agency_ref(
    value: object, code: str = "organization_agency_invalid_ref"
) -> str:
    """Require a bounded 16-hex agency reference."""

    if type(value) is not str or _REF_PATTERN.match(value) is None:
        _fail(code)
    return value


# ---------------------------------------------------------------------------
# Bounded owner-scoped collective-agency records
# ---------------------------------------------------------------------------

_NONE_TARGET_KINDS: Final[frozenset[str]] = frozenset({"none", "unknown"})
_AGENCY_STATUSES: Final[frozenset[OrganizationStatus]] = frozenset(
    {
        OrganizationStatus.CANDIDATE,
        OrganizationStatus.RECOGNIZED,
        OrganizationStatus.DISPUTED,
        OrganizationStatus.DISSOLVED,
        OrganizationStatus.RETIRED,
    }
)


def _reject_forbidden_fields(cls: type[object]) -> None:
    names = set(getattr(cls, "__dataclass_fields__", {}))
    if names & FORBIDDEN_AGENCY_FIELD_NAMES:
        _fail("organization_agency_invalid")


def _require_owner_id(value: object) -> AgentId:
    if type(value) is not AgentId:
        _fail("organization_agency_invalid")
    return value


def _require_enum(
    value: object, enum_type: type[StrEnum], code: str = "organization_agency_invalid"
) -> StrEnum:
    if type(value) is not enum_type:
        _fail(code)
    return value


def _require_count(value: object) -> int:
    if type(value) is not int or value < 0:
        _fail("organization_agency_invalid")
    return value


def _require_bounded_count(value: object, lower: int, upper: int) -> int:
    count = _require_count(value)
    if count < lower or count > upper:
        _fail("organization_agency_cap_exceeded")
    return count


def _require_ref_or_none(value: object) -> str | None:
    if value is None:
        return None
    return require_organization_agency_ref(value)


def _require_target(kind: object, ref: object) -> tuple[str, str | None]:
    if type(kind) is not str or kind not in ORGANIZATION_AGENCY_TARGET_KINDS:
        _fail("organization_agency_invalid")
    target_ref = _require_ref_or_none(ref)
    if kind in _NONE_TARGET_KINDS:
        if target_ref is not None:
            _fail("organization_agency_invalid")
    elif target_ref is None:
        _fail("organization_agency_invalid")
    return kind, target_ref


def _require_actor_tuple(values: object, cap: int) -> tuple[AgentId, ...]:
    if not isinstance(values, (list, tuple)):
        _fail("organization_agency_invalid")
    actors: list[AgentId] = []
    for value in values:
        if type(value) is not AgentId:
            _fail("organization_agency_invalid")
        if value in actors:
            _fail("organization_agency_duplicate_record")
        actors.append(value)
    if len(actors) > cap:
        _fail("organization_agency_cap_exceeded")
    return tuple(sorted(actors, key=lambda item: item.value))


def _require_evidence_refs(
    values: object, cap: int, code: str = "organization_agency_invalid"
) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        _fail(code)
    refs = tuple(values)
    for item in refs:
        require_organization_agency_evidence_id(item, code)
    if len(set(refs)) != len(refs):
        _fail("organization_agency_duplicate_record")
    if len(refs) > cap:
        _fail("organization_agency_cap_exceeded")
    return tuple(sorted(refs))


def _require_notices(values: object) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        _fail("organization_agency_invalid")
    notices = tuple(values)
    for notice in notices:
        if type(notice) is not str or notice not in ORGANIZATION_AGENCY_NOTICE_CODES:
            _fail("organization_agency_invalid")
    if len(set(notices)) != len(notices):
        _fail("organization_agency_duplicate_record")
    return tuple(sorted(notices))


def _require_tick(value: object) -> int:
    return require_organization_agency_tick(value)


def _require_span(first_tick: object, last_tick: object) -> tuple[int, int]:
    first = _require_tick(first_tick)
    last = _require_tick(last_tick)
    if last < first:
        _fail("organization_agency_tick_regression")
    return first, last


def _require_effect(value: object) -> OrganizationAgencyEffect:
    effect = _require_enum(value, OrganizationAgencyEffect)
    assert isinstance(effect, OrganizationAgencyEffect)
    return effect


def _require_mode_for_effect(
    mode: object, effect: OrganizationAgencyEffect
) -> OrganizationAgencyImplementationMode:
    implementation_mode = _require_enum(mode, OrganizationAgencyImplementationMode)
    expected = (
        OrganizationAgencyImplementationMode.TESTIMONIAL
        if effect is OrganizationAgencyEffect.NONE
        else OrganizationAgencyImplementationMode.PHYSICAL
    )
    if implementation_mode is not expected:
        _fail("organization_agency_invalid")
    return implementation_mode


def _require_domain_effect(
    domain: object, effect: object
) -> tuple[OrganizationOperationDomain, OrganizationAgencyEffect]:
    operation_domain = _require_enum(domain, OrganizationOperationDomain)
    assert isinstance(operation_domain, OrganizationOperationDomain)
    agency_effect = _require_effect(effect)
    if agency_effect.value not in ORGANIZATION_AGENCY_DOMAIN_EFFECTS[operation_domain]:
        _fail("organization_agency_invalid")
    return operation_domain, agency_effect


@dataclass(frozen=True, slots=True)
class OrganizationProposal:
    """One owner belief about a proposed collective action."""

    proposal_id: str
    organization_id: str
    proposal_ref: str
    topic: OrganizationAgencyTopic
    domain: OrganizationOperationDomain
    effect: OrganizationAgencyEffect
    implementation_mode: OrganizationAgencyImplementationMode
    target_kind: str
    target_ref: str | None
    procedure_ref: str | None
    expected_actors: tuple[AgentId, ...]
    quantity: int
    revision: int
    terms_ref: str
    status: OrganizationAgencyProposalStatus
    opened_tick: int
    deadline_tick: int
    first_tick: int
    last_tick: int
    support_count: int = 0
    oppose_count: int = 0
    abstain_count: int = 0
    contest_count: int = 0
    evidence_refs: tuple[str, ...] = ()
    notices: tuple[str, ...] = ()
    authority_basis: OrganizationAuthorityBasis = (
        OrganizationAuthorityBasis.SELF_AUTHORED
    )
    provenance_code: OrganizationAgencyProvenance = OrganizationAgencyProvenance.UNKNOWN

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "proposal_id", require_organization_proposal_id(self.proposal_id)
        )
        object.__setattr__(
            self,
            "organization_id",
            require_organization_concept_id(self.organization_id),
        )
        object.__setattr__(
            self, "proposal_ref", require_organization_agency_ref(self.proposal_ref)
        )
        object.__setattr__(
            self, "topic", _require_enum(self.topic, OrganizationAgencyTopic)
        )
        domain, effect = _require_domain_effect(self.domain, self.effect)
        object.__setattr__(self, "domain", domain)
        object.__setattr__(self, "effect", effect)
        object.__setattr__(
            self,
            "implementation_mode",
            _require_mode_for_effect(self.implementation_mode, effect),
        )
        target_kind, target_ref = _require_target(self.target_kind, self.target_ref)
        object.__setattr__(self, "target_kind", target_kind)
        object.__setattr__(self, "target_ref", target_ref)
        object.__setattr__(
            self, "procedure_ref", _require_ref_or_none(self.procedure_ref)
        )
        object.__setattr__(
            self,
            "expected_actors",
            _require_actor_tuple(
                self.expected_actors, _DEFAULT_AGENCY_POLICY.max_expected_actors
            ),
        )
        object.__setattr__(
            self,
            "quantity",
            _require_bounded_count(self.quantity, 1, 8),
        )
        object.__setattr__(
            self,
            "revision",
            _require_bounded_count(
                self.revision, 1, _DEFAULT_AGENCY_POLICY.max_revision
            ),
        )
        object.__setattr__(
            self, "terms_ref", require_organization_agency_ref(self.terms_ref)
        )
        object.__setattr__(
            self,
            "status",
            _require_enum(self.status, OrganizationAgencyProposalStatus),
        )
        opened = _require_tick(self.opened_tick)
        deadline = _require_tick(self.deadline_tick)
        if deadline < opened:
            _fail("organization_agency_tick_regression")
        first, last = _require_span(self.first_tick, self.last_tick)
        if opened < first:
            _fail("organization_agency_tick_regression")
        object.__setattr__(self, "opened_tick", opened)
        object.__setattr__(self, "deadline_tick", deadline)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        for name in (
            "support_count",
            "oppose_count",
            "abstain_count",
            "contest_count",
        ):
            object.__setattr__(
                self,
                name,
                _require_bounded_count(
                    getattr(self, name), 0, _DEFAULT_AGENCY_POLICY.max_owner_support
                ),
            )
        object.__setattr__(
            self,
            "evidence_refs",
            _require_evidence_refs(
                self.evidence_refs, _DEFAULT_AGENCY_POLICY.max_evidence_per_record
            ),
        )
        object.__setattr__(self, "notices", _require_notices(self.notices))
        object.__setattr__(
            self,
            "authority_basis",
            _require_enum(self.authority_basis, OrganizationAuthorityBasis),
        )
        object.__setattr__(
            self,
            "provenance_code",
            _require_enum(self.provenance_code, OrganizationAgencyProvenance),
        )


@dataclass(frozen=True, slots=True)
class OrganizationPosition:
    """One believed stance one participant holds toward a proposal revision."""

    proposal_id: str
    revision: int
    actor_id: AgentId
    stance: OrganizationAgencyPositionStance
    authority_basis: OrganizationAuthorityBasis
    evidence_refs: tuple[str, ...] = ()
    disputed: bool = False
    tick: int = 0
    refused: bool = False

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "proposal_id", require_organization_proposal_id(self.proposal_id)
        )
        object.__setattr__(
            self,
            "revision",
            _require_bounded_count(
                self.revision, 1, _DEFAULT_AGENCY_POLICY.max_revision
            ),
        )
        object.__setattr__(self, "actor_id", _require_owner_id(self.actor_id))
        object.__setattr__(
            self, "stance", _require_enum(self.stance, OrganizationAgencyPositionStance)
        )
        object.__setattr__(
            self,
            "authority_basis",
            _require_enum(self.authority_basis, OrganizationAuthorityBasis),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            _require_evidence_refs(
                self.evidence_refs, _DEFAULT_AGENCY_POLICY.max_evidence_per_record
            ),
        )
        if type(self.disputed) is not bool:
            _fail("organization_agency_invalid")
        if type(self.refused) is not bool:
            _fail("organization_agency_invalid")
        object.__setattr__(self, "tick", _require_tick(self.tick))


@dataclass(frozen=True, slots=True)
class OrganizationAmendment:
    """One believed in-order amendment to an active proposal."""

    amendment_id: str
    proposal_id: str
    from_revision: int
    to_revision: int
    terms_ref: str
    domain: OrganizationOperationDomain
    effect: OrganizationAgencyEffect
    target_kind: str
    target_ref: str | None
    procedure_ref: str | None
    amended_tick: int
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "amendment_id", require_organization_amendment_id(self.amendment_id)
        )
        object.__setattr__(
            self, "proposal_id", require_organization_proposal_id(self.proposal_id)
        )
        from_revision = _require_bounded_count(
            self.from_revision, 1, _DEFAULT_AGENCY_POLICY.max_revision - 1
        )
        to_revision = _require_bounded_count(
            self.to_revision, 2, _DEFAULT_AGENCY_POLICY.max_revision
        )
        if to_revision != from_revision + 1:
            _fail("organization_agency_invalid_transition")
        object.__setattr__(self, "from_revision", from_revision)
        object.__setattr__(self, "to_revision", to_revision)
        object.__setattr__(
            self, "terms_ref", require_organization_agency_ref(self.terms_ref)
        )
        domain, effect = _require_domain_effect(self.domain, self.effect)
        object.__setattr__(self, "domain", domain)
        object.__setattr__(self, "effect", effect)
        target_kind, target_ref = _require_target(self.target_kind, self.target_ref)
        object.__setattr__(self, "target_kind", target_kind)
        object.__setattr__(self, "target_ref", target_ref)
        object.__setattr__(
            self, "procedure_ref", _require_ref_or_none(self.procedure_ref)
        )
        object.__setattr__(self, "amended_tick", _require_tick(self.amended_tick))
        object.__setattr__(
            self,
            "evidence_refs",
            _require_evidence_refs(
                self.evidence_refs, _DEFAULT_AGENCY_POLICY.max_evidence_per_record
            ),
        )


@dataclass(frozen=True, slots=True)
class OrganizationCollectiveDecision:
    """One owner belief about a recorded collective decision."""

    decision_id: str
    organization_id: str
    proposal_id: str
    revision: int
    procedure_ref: str | None
    recognition: OrganizationAgencyRecognition
    authority_basis: OrganizationAuthorityBasis
    support_count: int
    oppose_count: int
    abstain_count: int
    contest_count: int
    implementation_mode: OrganizationAgencyImplementationMode
    effect: OrganizationAgencyEffect
    target_kind: str
    target_ref: str | None
    expected_actors: tuple[AgentId, ...]
    quantity: int
    decided_tick: int
    window_end_tick: int
    implementation_status: OrganizationAgencyImplementationStatus = (
        OrganizationAgencyImplementationStatus.PENDING
    )
    provenance_code: OrganizationAgencyProvenance = OrganizationAgencyProvenance.UNKNOWN
    evidence_refs: tuple[str, ...] = ()
    resolved: bool = True
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self,
            "decision_id",
            require_organization_collective_decision_id(self.decision_id),
        )
        object.__setattr__(
            self,
            "organization_id",
            require_organization_concept_id(self.organization_id),
        )
        object.__setattr__(
            self, "proposal_id", require_organization_proposal_id(self.proposal_id)
        )
        object.__setattr__(
            self,
            "revision",
            _require_bounded_count(
                self.revision, 1, _DEFAULT_AGENCY_POLICY.max_revision
            ),
        )
        object.__setattr__(
            self, "procedure_ref", _require_ref_or_none(self.procedure_ref)
        )
        object.__setattr__(
            self,
            "recognition",
            _require_enum(self.recognition, OrganizationAgencyRecognition),
        )
        object.__setattr__(
            self,
            "authority_basis",
            _require_enum(self.authority_basis, OrganizationAuthorityBasis),
        )
        for name in (
            "support_count",
            "oppose_count",
            "abstain_count",
            "contest_count",
        ):
            object.__setattr__(
                self,
                name,
                _require_bounded_count(
                    getattr(self, name), 0, _DEFAULT_AGENCY_POLICY.max_owner_support
                ),
            )
        effect = _require_effect(self.effect)
        object.__setattr__(self, "effect", effect)
        object.__setattr__(
            self,
            "implementation_mode",
            _require_mode_for_effect(self.implementation_mode, effect),
        )
        target_kind, target_ref = _require_target(self.target_kind, self.target_ref)
        object.__setattr__(self, "target_kind", target_kind)
        object.__setattr__(self, "target_ref", target_ref)
        object.__setattr__(
            self,
            "expected_actors",
            _require_actor_tuple(
                self.expected_actors, _DEFAULT_AGENCY_POLICY.max_expected_actors
            ),
        )
        object.__setattr__(
            self, "quantity", _require_bounded_count(self.quantity, 1, 8)
        )
        decided = _require_tick(self.decided_tick)
        window_end = _require_tick(self.window_end_tick)
        if window_end < decided:
            _fail("organization_agency_tick_regression")
        object.__setattr__(self, "decided_tick", decided)
        object.__setattr__(self, "window_end_tick", window_end)
        object.__setattr__(
            self,
            "implementation_status",
            _require_enum(
                self.implementation_status, OrganizationAgencyImplementationStatus
            ),
        )
        object.__setattr__(
            self,
            "provenance_code",
            _require_enum(self.provenance_code, OrganizationAgencyProvenance),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            _require_evidence_refs(
                self.evidence_refs, _DEFAULT_AGENCY_POLICY.max_evidence_per_record
            ),
        )
        if type(self.resolved) is not bool:
            _fail("organization_agency_invalid")
        if self.resolved is not (target_kind not in _NONE_TARGET_KINDS):
            _fail("organization_agency_invalid")
        object.__setattr__(self, "notices", _require_notices(self.notices))


@dataclass(frozen=True, slots=True)
class OrganizationImplementation:
    """One owner belief about one expected actor's implementation."""

    implementation_id: str
    decision_id: str
    actor_id: AgentId
    status: OrganizationAgencyImplementationStatus
    effect: OrganizationAgencyEffect
    observed_tick: int
    provenance_code: OrganizationAgencyProvenance
    evidence_refs: tuple[str, ...] = ()
    resolved: bool = False

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self,
            "implementation_id",
            require_organization_implementation_id(self.implementation_id),
        )
        object.__setattr__(
            self,
            "decision_id",
            require_organization_collective_decision_id(self.decision_id),
        )
        object.__setattr__(self, "actor_id", _require_owner_id(self.actor_id))
        object.__setattr__(
            self,
            "status",
            _require_enum(self.status, OrganizationAgencyImplementationStatus),
        )
        object.__setattr__(self, "effect", _require_effect(self.effect))
        object.__setattr__(self, "observed_tick", _require_tick(self.observed_tick))
        object.__setattr__(
            self,
            "provenance_code",
            _require_enum(self.provenance_code, OrganizationAgencyProvenance),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            _require_evidence_refs(
                self.evidence_refs, _DEFAULT_AGENCY_POLICY.max_evidence_per_record
            ),
        )
        if type(self.resolved) is not bool:
            _fail("organization_agency_invalid")


@dataclass(frozen=True, slots=True)
class OrganizationAgencyConcept:
    """One owner's collective-agency beliefs about one existing concept."""

    organization_id: str
    owner_id: AgentId
    status: OrganizationStatus
    first_tick: int
    last_tick: int
    proposals: tuple[OrganizationProposal, ...] = ()
    positions: tuple[OrganizationPosition, ...] = ()
    amendments: tuple[OrganizationAmendment, ...] = ()
    decisions: tuple[OrganizationCollectiveDecision, ...] = ()
    implementations: tuple[OrganizationImplementation, ...] = ()
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self,
            "organization_id",
            require_organization_concept_id(self.organization_id),
        )
        object.__setattr__(self, "owner_id", _require_owner_id(self.owner_id))
        status = _require_enum(self.status, OrganizationStatus)
        if status not in _AGENCY_STATUSES:
            _fail("organization_agency_invalid")
        object.__setattr__(self, "status", status)
        first, last = _require_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)

        proposals = _ordered_records(
            self.proposals,
            OrganizationProposal,
            key=lambda item: (item.opened_tick, item.proposal_id),
        )
        positions = _ordered_records(
            self.positions,
            OrganizationPosition,
            key=lambda item: (
                item.tick,
                item.proposal_id,
                item.revision,
                item.actor_id.value,
                item.stance.value,
            ),
            unique=False,
        )
        amendments = _ordered_records(
            self.amendments,
            OrganizationAmendment,
            key=lambda item: (item.amended_tick, item.amendment_id),
        )
        decisions = _ordered_records(
            self.decisions,
            OrganizationCollectiveDecision,
            key=lambda item: (item.decided_tick, item.decision_id),
        )
        implementations = _ordered_records(
            self.implementations,
            OrganizationImplementation,
            key=lambda item: (
                item.observed_tick,
                item.decision_id,
                item.actor_id.value,
            ),
        )

        proposal_by_id = {item.proposal_id: item for item in proposals}
        decision_ids = {item.decision_id for item in decisions}
        for proposal in proposals:
            if not (first <= proposal.first_tick <= last):
                _fail("organization_agency_tick_regression")
        for position in positions:
            owner_proposal = proposal_by_id.get(position.proposal_id)
            if owner_proposal is None:
                _fail("organization_agency_unknown_proposal")
            if position.revision > owner_proposal.revision:
                _fail("organization_agency_invalid_transition")
        amendments_by_proposal: dict[str, list[OrganizationAmendment]] = {}
        for amendment in amendments:
            amended_proposal = proposal_by_id.get(amendment.proposal_id)
            if amended_proposal is None:
                _fail("organization_agency_unknown_proposal")
            amendments_by_proposal.setdefault(amendment.proposal_id, []).append(
                amendment
            )
        for proposal in proposals:
            revisions = sorted(
                item.to_revision
                for item in amendments_by_proposal.get(proposal.proposal_id, ())
            )
            expected = revisions[-1] if revisions else 1
            if proposal.revision != expected:
                _fail("organization_agency_invalid_transition")
        for decision in decisions:
            decided_proposal = proposal_by_id.get(decision.proposal_id)
            if decided_proposal is None:
                _fail("organization_agency_unknown_proposal")
            if decision.revision > decided_proposal.revision:
                _fail("organization_agency_invalid_transition")
            if decision.organization_id != self.organization_id:
                _fail("organization_agency_foreign_ledger")
        for implementation in implementations:
            if implementation.decision_id not in decision_ids:
                _fail("organization_agency_unknown_decision")

        object.__setattr__(self, "proposals", proposals)
        object.__setattr__(self, "positions", positions)
        object.__setattr__(self, "amendments", amendments)
        object.__setattr__(self, "decisions", decisions)
        object.__setattr__(self, "implementations", implementations)
        object.__setattr__(self, "notices", _require_notices(self.notices))


def _ordered_records[RecordT](
    values: object,
    record_type: type[RecordT],
    *,
    key: Callable[[RecordT], Any],
    unique: bool = True,
) -> tuple[RecordT, ...]:
    if not isinstance(values, (list, tuple)):
        _fail("organization_agency_invalid")
    items = tuple(values)
    for item in items:
        if type(item) is not record_type:
            _fail("organization_agency_invalid")
    ordered = tuple(sorted(items, key=key))
    if unique:
        identifiers = {
            getattr(item, _RECORD_ID_FIELDS[record_type.__name__]) for item in ordered
        }
        if len(identifiers) != len(ordered):
            _fail("organization_agency_duplicate_record")
    return ordered


_RECORD_ID_FIELDS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "OrganizationProposal": "proposal_id",
        "OrganizationPosition": "proposal_id",
        "OrganizationAmendment": "amendment_id",
        "OrganizationCollectiveDecision": "decision_id",
        "OrganizationImplementation": "implementation_id",
    }
)


@dataclass(frozen=True, slots=True)
class OrganizationAgencyLedger:
    """One owner's collective-agency beliefs. ``None`` means the mode is off."""

    owner_id: AgentId
    concepts: tuple[OrganizationAgencyConcept, ...] = ()
    notices: tuple[str, ...] = ()
    policy_version: str = ORGANIZATION_AGENCY_POLICY_VERSION

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(self, "owner_id", _require_owner_id(self.owner_id))
        if self.policy_version != ORGANIZATION_AGENCY_POLICY_VERSION:
            _fail("organization_agency_policy_mismatch")
        if not isinstance(self.concepts, (list, tuple)):
            _fail("organization_agency_invalid")
        concepts = tuple(self.concepts)
        seen: set[str] = set()
        previous: str | None = None
        for concept in concepts:
            if type(concept) is not OrganizationAgencyConcept:
                _fail("organization_agency_invalid")
            if concept.owner_id != self.owner_id:
                _fail("organization_agency_foreign_ledger")
            if concept.organization_id in seen:
                _fail("organization_agency_duplicate_record")
            if previous is not None and concept.organization_id < previous:
                _fail("organization_agency_invalid")
            seen.add(concept.organization_id)
            previous = concept.organization_id
        if len(concepts) > _DEFAULT_AGENCY_POLICY.max_concepts:
            _fail("organization_agency_cap_exceeded")
        proposal_ids: set[str] = set()
        decision_ids: set[str] = set()
        implementation_ids: set[str] = set()
        total_records = 0
        total_evidence = 0
        for concept in concepts:
            for proposal in concept.proposals:
                if proposal.proposal_id in proposal_ids:
                    _fail("organization_agency_duplicate_record")
                proposal_ids.add(proposal.proposal_id)
            for decision in concept.decisions:
                if decision.decision_id in decision_ids:
                    _fail("organization_agency_duplicate_record")
                decision_ids.add(decision.decision_id)
            for implementation in concept.implementations:
                if implementation.implementation_id in implementation_ids:
                    _fail("organization_agency_duplicate_record")
                implementation_ids.add(implementation.implementation_id)
            total_records += (
                len(concept.proposals)
                + len(concept.positions)
                + len(concept.amendments)
                + len(concept.decisions)
                + len(concept.implementations)
            )
            total_evidence += _concept_evidence_count(concept)
        if len(proposal_ids) > _DEFAULT_AGENCY_POLICY.max_proposals:
            _fail("organization_agency_cap_exceeded")
        if len(decision_ids) > _DEFAULT_AGENCY_POLICY.max_decisions:
            _fail("organization_agency_cap_exceeded")
        if len(implementation_ids) > _DEFAULT_AGENCY_POLICY.max_implementations:
            _fail("organization_agency_cap_exceeded")
        if total_records > _DEFAULT_AGENCY_POLICY.max_total_records:
            _fail("organization_agency_cap_exceeded")
        if total_evidence > _DEFAULT_AGENCY_POLICY.max_total_evidence:
            _fail("organization_agency_cap_exceeded")
        object.__setattr__(self, "concepts", concepts)
        object.__setattr__(self, "notices", _require_notices(self.notices))
        _LOG.debug(
            "organization_agency_ledger_constructed owner_id=%s concepts=%s "
            "proposals=%s decisions=%s implementations=%s",
            self.owner_id.value,
            len(self.concepts),
            len(proposal_ids),
            len(decision_ids),
            len(implementation_ids),
        )


def _concept_evidence_count(concept: OrganizationAgencyConcept) -> int:
    count = 0
    for family in (
        concept.proposals,
        concept.positions,
        concept.amendments,
        concept.decisions,
        concept.implementations,
    ):
        for record in family:
            count += len(record.evidence_refs)
    return count


def empty_organization_agency_ledger(
    owner_id: object, policy: object | None = None
) -> OrganizationAgencyLedger:
    """Return an empty owner ledger; an empty ledger is not ``None``."""

    owner = _require_owner_id(owner_id)
    if policy is not None and type(policy) is not OrganizationAgencyPolicy:
        _fail("organization_agency_policy_mismatch")
    return OrganizationAgencyLedger(owner_id=owner)


def require_owner_organization_agency(
    ledger: object, owner_id: object, field_name: str = "organization_agency"
) -> OrganizationAgencyLedger | None:
    """Require an owner-local agency ledger or ``None``; never a peer ledger."""

    owner = _require_owner_id(owner_id)
    if ledger is None:
        return None
    if type(ledger) is not OrganizationAgencyLedger:
        _fail("organization_agency_invalid")
    if ledger.owner_id != owner:
        _fail("organization_agency_foreign_ledger")
    return ledger


_TOPIC_BY_DOMAIN: Final[
    Mapping[OrganizationOperationDomain, OrganizationAgencyTopic]
] = MappingProxyType(
    {
        OrganizationOperationDomain.RESOURCE_CONTROL: (
            OrganizationAgencyTopic.RESOURCE_USE
        ),
        OrganizationOperationDomain.STORAGE: OrganizationAgencyTopic.STORAGE,
        OrganizationOperationDomain.RECORD_KEEPING: (
            OrganizationAgencyTopic.RECORD_KEEPING
        ),
        OrganizationOperationDomain.MEMBERSHIP_ADMISSION: (
            OrganizationAgencyTopic.MEMBERSHIP
        ),
        OrganizationOperationDomain.MEMBERSHIP_DEPARTURE: (
            OrganizationAgencyTopic.MEMBERSHIP
        ),
        OrganizationOperationDomain.ROLE_ASSIGNMENT: (OrganizationAgencyTopic.ROLE),
        OrganizationOperationDomain.PROCEDURE_ACTION: (
            OrganizationAgencyTopic.PROCEDURE
        ),
        OrganizationOperationDomain.INTERNAL_COMMITMENT: (
            OrganizationAgencyTopic.COMMITMENT
        ),
    }
)


def _target_kind_for_effect(effect: OrganizationAgencyEffect) -> str:
    if effect in (
        OrganizationAgencyEffect.GIVE,
        OrganizationAgencyEffect.HELP,
        OrganizationAgencyEffect.FEED,
        OrganizationAgencyEffect.TRANSPORT,
        OrganizationAgencyEffect.ATTACK,
        OrganizationAgencyEffect.COMMITMENT_DECLARED,
        OrganizationAgencyEffect.PUBLIC_GOOD_BENEFIT,
    ):
        return "agent"
    if effect in (
        OrganizationAgencyEffect.ITEM_STORED,
        OrganizationAgencyEffect.RESOURCE_HARVESTED,
        OrganizationAgencyEffect.ITEM_CRAFTED,
        OrganizationAgencyEffect.EXCHANGE_COMPLETED,
    ):
        return "item"
    if effect in (
        OrganizationAgencyEffect.ARTIFACT_CREATED,
        OrganizationAgencyEffect.ARTIFACT_MODIFIED,
        OrganizationAgencyEffect.ARTIFACT_DESTROYED,
    ):
        return "artifact"
    if effect in (
        OrganizationAgencyEffect.REPOSITORY_MEMBER_DEPOSITED,
        OrganizationAgencyEffect.REPOSITORY_MEMBER_RETRIEVED,
        OrganizationAgencyEffect.REPOSITORY_ESTABLISHED,
        OrganizationAgencyEffect.REPOSITORY_MAINTAINED,
    ):
        return "repository"
    if effect in (
        OrganizationAgencyEffect.STRUCTURE_BUILT,
        OrganizationAgencyEffect.STRUCTURE_REPAIRED,
    ):
        return "structure"
    if effect in (
        OrganizationAgencyEffect.PROJECT_CONTRIBUTED,
        OrganizationAgencyEffect.PUBLIC_GOOD_MAINTAINED,
        OrganizationAgencyEffect.PUBLIC_GOOD_OPPOSED,
    ):
        return "collective_project"
    if effect is OrganizationAgencyEffect.MOVE:
        return "location"
    return "none"


def _peer_target(
    effect: OrganizationAgencyEffect, target_ref: str | None
) -> tuple[str, str | None]:
    if target_ref is None:
        return "none", None
    kind = _target_kind_for_effect(effect)
    if kind == "none":
        return "unknown", None
    return kind, target_ref


def _require_owner_safe_observation(observation: object) -> None:
    module = type(observation).__module__
    if module.startswith(("world._", "simulation.engine", "persistence", "api")):
        _fail("organization_agency_invalid")


def _speaker_member_match(speaker_value: str, member_id: str) -> bool:
    return (
        speaker_value == member_id or speaker_value.removeprefix("body-") == member_id
    )


def _claim_evidence_ref(
    owner: AgentId,
    organization_id: str,
    tick: int,
    ordinal: int,
    material: str,
) -> str:
    return organization_agency_evidence_id(
        owner.value, organization_id, "communication", tick, ordinal, material
    )


def _merge_evidence(
    existing: Sequence[str], additions: Sequence[str], cap: int
) -> tuple[str, ...]:
    merged = tuple(sorted(set((*existing, *additions))))
    if len(merged) > cap:
        return merged[-cap:]
    return merged


def _trim_records[RecordT](
    records: list[RecordT], cap: int, key: Callable[[RecordT], Any]
) -> tuple[list[RecordT], bool]:
    if len(records) <= cap:
        return records, False
    ordered = sorted(records, key=key)
    return ordered[-cap:], True


class _WorkConcept:
    __slots__ = (
        "amendments",
        "decisions",
        "implementations",
        "notices",
        "organization_id",
        "owner_id",
        "positions",
        "proposals",
        "status",
    )

    def __init__(
        self,
        organization_id: str,
        owner_id: AgentId,
        status: OrganizationStatus,
    ) -> None:
        self.organization_id = organization_id
        self.owner_id = owner_id
        self.status = status
        self.proposals: list[OrganizationProposal] = []
        self.positions: list[OrganizationPosition] = []
        self.amendments: list[OrganizationAmendment] = []
        self.decisions: list[OrganizationCollectiveDecision] = []
        self.implementations: list[OrganizationImplementation] = []
        self.notices: set[str] = set()


def _procedure_is_recognized(
    concept: object, proposal: OrganizationProposal, policy: OrganizationAgencyPolicy
) -> bool:
    if proposal.procedure_ref is None:
        return False
    for procedure in getattr(concept, "procedures", ()):
        if procedure.status is not OrganizationStatus.RECOGNIZED:
            continue
        if procedure.recurrence < policy.procedure_min_recurrence:
            continue
        if (
            organization_agency_ref(
                cast(Any, procedure).anchor_id, namespace="procedure"
            )
            == proposal.procedure_ref
        ):
            return True
    return False


def _position_counts(
    positions: Sequence[OrganizationPosition], revision: int
) -> tuple[int, int, int, int]:
    latest: dict[str, OrganizationPosition] = {}
    for item in sorted(
        positions,
        key=lambda value: (value.tick, value.actor_id.value, value.stance.value),
    ):
        if item.revision != revision:
            continue
        latest[item.actor_id.value] = item
    support = sum(
        1
        for item in latest.values()
        if item.stance is OrganizationAgencyPositionStance.SUPPORT
    )
    oppose = sum(
        1
        for item in latest.values()
        if item.stance is OrganizationAgencyPositionStance.OPPOSE
    )
    abstain = sum(
        1
        for item in latest.values()
        if item.stance is OrganizationAgencyPositionStance.ABSTAIN
    )
    contested_support = sum(
        1
        for item in latest.values()
        if item.stance is OrganizationAgencyPositionStance.SUPPORT and item.disputed
    )
    return support, oppose, abstain, oppose + contested_support


def _recognition_for(
    proposal: OrganizationProposal,
    *,
    procedure_recognized: bool,
    support: int,
    contest: int,
    policy: OrganizationAgencyPolicy,
) -> OrganizationAgencyRecognition:
    if (
        support >= policy.recognition_min_supporters
        and contest == 0
        and procedure_recognized
    ):
        return OrganizationAgencyRecognition.RECOGNIZED
    if support >= policy.recognition_min_supporters and (
        procedure_recognized or contest > 0
    ):
        return OrganizationAgencyRecognition.CONTESTED
    return OrganizationAgencyRecognition.UNRECOGNIZED


def _provenance_for(
    recognition: OrganizationAgencyRecognition,
) -> OrganizationAgencyProvenance:
    if recognition is OrganizationAgencyRecognition.RECOGNIZED:
        return OrganizationAgencyProvenance.PROCEDURE_RECOGNIZED
    if recognition is OrganizationAgencyRecognition.CONTESTED:
        return OrganizationAgencyProvenance.CONTESTED
    if recognition is OrganizationAgencyRecognition.EXPIRED:
        return OrganizationAgencyProvenance.EXPIRED
    return OrganizationAgencyProvenance.UNRECOGNIZED


def _decision_authority(
    proposal: OrganizationProposal, recognition: OrganizationAgencyRecognition
) -> OrganizationAuthorityBasis:
    if proposal.authority_basis is OrganizationAuthorityBasis.SELF_AUTHORED:
        return OrganizationAuthorityBasis.SELF_AUTHORED
    if recognition in (
        OrganizationAgencyRecognition.RECOGNIZED,
        OrganizationAgencyRecognition.CONTESTED,
    ):
        return OrganizationAuthorityBasis.DECISION_BELIEF
    if proposal.procedure_ref is not None:
        return OrganizationAuthorityBasis.PROCEDURE_BELIEF
    return OrganizationAuthorityBasis.UNKNOWN


def apply_organization_agency_update(
    *,
    owner_id: AgentId,
    tick: int,
    observation: object,
    prior: object | None,
    organization_concepts: object | None,
    policy: OrganizationAgencyPolicy | None = None,
) -> OrganizationAgencyLedger:
    """Materialize one owner's collective-agency sidecar ledger."""

    from agents.cognition.organization_agency_communication import (
        OrganizationAgencyAct,
        parse_organization_agency_claim_relation,
    )
    from agents.cognition.organization_concepts import OrganizationConceptLedger

    owner = _require_owner_id(owner_id)
    active_policy = _DEFAULT_AGENCY_POLICY if policy is None else policy
    if type(active_policy) is not OrganizationAgencyPolicy:
        _fail("organization_agency_policy_mismatch")
    current_tick = _require_tick(tick)
    if prior is not None:
        if type(prior) is not OrganizationAgencyLedger:
            raise TypeError("prior must be OrganizationAgencyLedger or None")
        if prior.owner_id != owner:
            _fail("organization_agency_foreign_ledger")
    if organization_concepts is not None:
        if type(organization_concepts) is not OrganizationConceptLedger:
            raise TypeError(
                "organization_concepts must be OrganizationConceptLedger or None"
            )
        if organization_concepts.owner_id != owner:
            _fail("organization_agency_foreign_ledger")
    if organization_concepts is None:
        return empty_organization_agency_ledger(owner, active_policy)

    _require_owner_safe_observation(observation)
    observer_id = getattr(observation, "observer_id", None)
    if type(observer_id) is AgentId and observer_id != owner:
        _fail("organization_agency_foreign_ledger")

    concept_by_id = {
        concept.organization_id: concept for concept in organization_concepts.concepts
    }
    prior_by_id = (
        {}
        if prior is None
        else {concept.organization_id: concept for concept in prior.concepts}
    )
    work: dict[str, _WorkConcept] = {}
    for concept_ref in sorted(set(concept_by_id) | set(prior_by_id)):
        concept = concept_by_id.get(concept_ref)
        previous = prior_by_id.get(concept_ref)
        if concept is not None:
            status = concept.status
        elif previous is not None:
            status = previous.status
        else:
            continue
        work_concept = _WorkConcept(concept_ref, owner, status)
        if previous is not None:
            work_concept.proposals.extend(previous.proposals)
            work_concept.positions.extend(previous.positions)
            work_concept.amendments.extend(previous.amendments)
            work_concept.decisions.extend(previous.decisions)
            work_concept.implementations.extend(previous.implementations)
            work_concept.notices.update(previous.notices)
        work[concept_ref] = work_concept

    ledger_notices: set[str] = set(() if prior is None else prior.notices)

    # -- collect delivered, owner-addressed claims -------------------------
    collected: list[tuple[str, int, OrganizationAgencyClaim]] = []
    for communication in getattr(observation, "communications", ()) or ():
        listener = getattr(communication, "listener_id", None)
        listener_value = getattr(listener, "value", None)
        if (
            listener_value is None
            or str(listener_value).removeprefix("body-") != owner.value
        ):
            continue
        speaker = getattr(communication, "speaker_id", None)
        speaker_value = None if speaker is None else getattr(speaker, "value", None)
        if not speaker_value or speaker_value == owner.value:
            continue
        utterance = getattr(communication, "utterance", None)
        content = getattr(utterance, "content", None)
        relations = () if content is None else tuple(content.relations)
        for ordinal, relation in enumerate(relations):
            claim = parse_organization_agency_claim_relation(relation)
            if claim is None:
                continue
            collected.append((speaker_value, ordinal, claim))
    collected.sort(
        key=lambda item: (
            item[0],
            getattr(item[2], "proposal_ref", None) or "",
            item[2].act.value,
            getattr(item[2], "revision", None) or 0,
            item[1],
        )
    )

    force_recognize: set[tuple[str, int]] = set()

    def _find_proposal(
        proposal_ref: str | None, revision: int | None
    ) -> tuple[str, OrganizationProposal] | None:
        matches: list[tuple[str, OrganizationProposal]] = []
        for organization_id in sorted(work):
            for candidate in work[organization_id].proposals:
                if candidate.proposal_ref != proposal_ref:
                    continue
                if revision is not None and candidate.revision != revision:
                    continue
                matches.append((organization_id, candidate))
        if not matches:
            return None
        matches.sort(key=lambda item: (-item[1].revision, item[0]))
        return matches[0]

    def _resolve_concept_for_speaker(speaker_value: str) -> str | None:
        candidates: list[tuple[int, str]] = []
        for organization_id in sorted(work):
            concept = concept_by_id.get(organization_id)
            if concept is None:
                continue
            overlap = sum(
                1
                for member in concept.members
                if _speaker_member_match(speaker_value, member.member_id)
            )
            if overlap:
                candidates.append((overlap, organization_id))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (-item[0], item[1]))
        return candidates[0][1]

    for speaker_value, ordinal, claim in collected:
        organization_id: str | None = None
        resolved = _find_proposal(
            claim.proposal_ref,
            (
                None
                if claim.act
                in (OrganizationAgencyAct.PROPOSE, OrganizationAgencyAct.AMEND)
                else claim.revision
            ),
        )
        if claim.act is OrganizationAgencyAct.PROPOSE:
            if resolved is not None:
                organization_id, proposal = resolved
            else:
                organization_id = _resolve_concept_for_speaker(speaker_value)
                if organization_id is None:
                    ledger_notices.add("orphaned_concept")
                    continue
                work_concept = work[organization_id]
                domain = claim.domain
                effect = claim.effect
                assert domain is not None and effect is not None
                if effect.value not in ORGANIZATION_AGENCY_DOMAIN_EFFECTS[domain]:
                    ledger_notices.add("malformed_claim")
                    continue
                opened = current_tick
                deadline = current_tick + active_policy.proposal_window_ticks
                ref = claim.proposal_ref
                assert ref is not None
                proposal = OrganizationProposal(
                    proposal_id=organization_proposal_id(
                        owner.value, organization_id, ref
                    ),
                    organization_id=organization_id,
                    proposal_ref=ref,
                    topic=_TOPIC_BY_DOMAIN[domain],
                    domain=domain,
                    effect=effect,
                    implementation_mode=(
                        OrganizationAgencyImplementationMode.TESTIMONIAL
                        if effect is OrganizationAgencyEffect.NONE
                        else OrganizationAgencyImplementationMode.PHYSICAL
                    ),
                    target_kind=_peer_target(effect, claim.target_ref)[0],
                    target_ref=_peer_target(effect, claim.target_ref)[1],
                    procedure_ref=claim.procedure_ref,
                    expected_actors=(owner,),
                    quantity=1,
                    revision=1,
                    terms_ref=claim.terms_ref or "",
                    status=OrganizationAgencyProposalStatus.ACTIVE,
                    opened_tick=opened,
                    deadline_tick=deadline,
                    first_tick=current_tick,
                    last_tick=current_tick,
                    authority_basis=OrganizationAuthorityBasis.OBSERVATION,
                    provenance_code=OrganizationAgencyProvenance.COMMUNICATED,
                )
                work_concept.proposals.append(proposal)
                continue
        elif resolved is None:
            ledger_notices.add("orphaned_concept")
            continue
        else:
            organization_id, proposal = resolved

        work_concept = work[organization_id]
        evidence = _claim_evidence_ref(
            owner,
            organization_id,
            current_tick,
            ordinal,
            "|".join(
                (
                    claim.act.value,
                    claim.proposal_ref or "",
                    claim.stance,
                    claim.report_kind.value if claim.report_kind is not None else "",
                )
            ),
        )

        if claim.act is OrganizationAgencyAct.PROPOSE:
            updated = replace(
                proposal,
                evidence_refs=_merge_evidence(
                    proposal.evidence_refs,
                    (evidence,),
                    active_policy.max_evidence_per_record,
                ),
                last_tick=max(proposal.last_tick, current_tick),
            )
            work_concept.proposals = [
                updated if item.proposal_id == proposal.proposal_id else item
                for item in work_concept.proposals
            ]
            continue

        if proposal.status in (
            OrganizationAgencyProposalStatus.WITHDRAWN,
            OrganizationAgencyProposalStatus.EXPIRED,
        ):
            continue

        if claim.act in (
            OrganizationAgencyAct.SUPPORT,
            OrganizationAgencyAct.OPPOSE,
            OrganizationAgencyAct.ABSTAIN,
            OrganizationAgencyAct.WITHDRAW,
            OrganizationAgencyAct.REFUSE,
            OrganizationAgencyAct.RECOGNIZE,
        ):
            if claim.act is OrganizationAgencyAct.SUPPORT:
                stance = OrganizationAgencyPositionStance.SUPPORT
            elif claim.act is OrganizationAgencyAct.OPPOSE:
                stance = OrganizationAgencyPositionStance.OPPOSE
            elif claim.act is OrganizationAgencyAct.ABSTAIN:
                stance = OrganizationAgencyPositionStance.ABSTAIN
            elif claim.act is OrganizationAgencyAct.WITHDRAW:
                stance = OrganizationAgencyPositionStance.WITHDRAW
            elif claim.act is OrganizationAgencyAct.REFUSE:
                stance = OrganizationAgencyPositionStance.WITHDRAW
            else:
                stance = (
                    OrganizationAgencyPositionStance.SUPPORT
                    if claim.stance == "recognized"
                    else OrganizationAgencyPositionStance.OPPOSE
                )
            actor_id = AgentId(speaker_value.removeprefix("body-"))
            dispute = claim.act is OrganizationAgencyAct.OPPOSE
            work_concept.positions = [
                item
                for item in work_concept.positions
                if not (
                    item.proposal_id == proposal.proposal_id
                    and item.revision == proposal.revision
                    and item.actor_id == actor_id
                )
            ]
            work_concept.positions.append(
                OrganizationPosition(
                    proposal_id=proposal.proposal_id,
                    revision=proposal.revision,
                    actor_id=actor_id,
                    stance=stance,
                    authority_basis=OrganizationAuthorityBasis.OBSERVATION,
                    evidence_refs=(evidence,),
                    disputed=dispute,
                    tick=current_tick,
                    refused=claim.act is OrganizationAgencyAct.REFUSE,
                )
            )
            if (
                claim.act is OrganizationAgencyAct.RECOGNIZE
                and claim.stance == "recognized"
            ):
                force_recognize.add((proposal.proposal_id, proposal.revision))
            if claim.act is OrganizationAgencyAct.WITHDRAW:
                if speaker_value.removeprefix("body-") == owner.value and not any(
                    item.proposal_id == proposal.proposal_id
                    for item in work_concept.decisions
                ):
                    updated = replace(
                        proposal,
                        status=OrganizationAgencyProposalStatus.WITHDRAWN,
                        last_tick=max(proposal.last_tick, current_tick),
                    )
                    work_concept.proposals = [
                        updated if item.proposal_id == proposal.proposal_id else item
                        for item in work_concept.proposals
                    ]
            continue

        if claim.act is OrganizationAgencyAct.AMEND:
            if current_tick > proposal.deadline_tick:
                work_concept.notices.add("proposal_expired")
                ledger_notices.add("proposal_expired")
                continue
            if claim.revision != proposal.revision + 1:
                work_concept.notices.add("amendment_out_of_order")
                continue
            domain = claim.domain
            effect = claim.effect
            if domain is None or effect is None:
                continue
            amendment = OrganizationAmendment(
                amendment_id=organization_amendment_id(
                    owner.value,
                    organization_id,
                    proposal.proposal_id,
                    claim.revision,
                    claim.terms_ref or "",
                ),
                proposal_id=proposal.proposal_id,
                from_revision=proposal.revision,
                to_revision=claim.revision,
                terms_ref=claim.terms_ref or "",
                domain=domain,
                effect=effect,
                target_kind=_peer_target(effect, claim.target_ref)[0],
                target_ref=_peer_target(effect, claim.target_ref)[1],
                procedure_ref=claim.procedure_ref,
                amended_tick=current_tick,
                evidence_refs=(evidence,),
            )
            work_concept.amendments.append(amendment)
            actor_id = AgentId(speaker_value.removeprefix("body-"))
            work_concept.positions = [
                item
                for item in work_concept.positions
                if not (
                    item.proposal_id == proposal.proposal_id
                    and item.revision == claim.revision
                    and item.actor_id == actor_id
                )
            ]
            work_concept.positions.append(
                OrganizationPosition(
                    proposal_id=proposal.proposal_id,
                    revision=claim.revision,
                    actor_id=actor_id,
                    stance=OrganizationAgencyPositionStance.AMEND,
                    authority_basis=OrganizationAuthorityBasis.OBSERVATION,
                    evidence_refs=(evidence,),
                    tick=current_tick,
                )
            )
            updated = replace(
                proposal,
                revision=claim.revision,
                terms_ref=claim.terms_ref or proposal.terms_ref,
                domain=domain,
                effect=effect,
                implementation_mode=(
                    OrganizationAgencyImplementationMode.TESTIMONIAL
                    if effect is OrganizationAgencyEffect.NONE
                    else OrganizationAgencyImplementationMode.PHYSICAL
                ),
                target_kind=_peer_target(effect, claim.target_ref)[0],
                target_ref=_peer_target(effect, claim.target_ref)[1],
                procedure_ref=claim.procedure_ref,
                status=OrganizationAgencyProposalStatus.AMENDED,
                support_count=0,
                oppose_count=0,
                abstain_count=0,
                contest_count=0,
                last_tick=max(proposal.last_tick, current_tick),
                evidence_refs=_merge_evidence(
                    proposal.evidence_refs,
                    (evidence,),
                    active_policy.max_evidence_per_record,
                ),
            )
            work_concept.proposals = [
                updated if item.proposal_id == proposal.proposal_id else item
                for item in work_concept.proposals
            ]
            continue

        # report: evidence only
        updated = replace(
            proposal,
            evidence_refs=_merge_evidence(
                proposal.evidence_refs,
                (evidence,),
                active_policy.max_evidence_per_record,
            ),
            last_tick=max(proposal.last_tick, current_tick),
        )
        work_concept.proposals = [
            updated if item.proposal_id == proposal.proposal_id else item
            for item in work_concept.proposals
        ]

    # -- recognize or expire once per tick ---------------------------------
    for organization_id in sorted(work):
        work_concept = work[organization_id]
        concept = concept_by_id.get(organization_id)
        proposals: list[OrganizationProposal] = []
        for proposal in sorted(
            work_concept.proposals,
            key=lambda item: (item.opened_tick, item.proposal_id),
        ):
            if proposal.status in (
                OrganizationAgencyProposalStatus.WITHDRAWN,
                OrganizationAgencyProposalStatus.DECIDED,
                OrganizationAgencyProposalStatus.EXPIRED,
            ):
                proposals.append(proposal)
                continue
            support, oppose, abstain, contest = _position_counts(
                work_concept.positions, proposal.revision
            )
            proposal = replace(
                proposal,
                support_count=support,
                oppose_count=oppose,
                abstain_count=abstain,
                contest_count=contest,
            )
            procedure_recognized = concept is not None and _procedure_is_recognized(
                concept, proposal, active_policy
            )
            closed = current_tick >= proposal.deadline_tick
            forced = (proposal.proposal_id, proposal.revision) in force_recognize
            if (
                closed
                and support < active_policy.recognition_min_supporters
                and not forced
            ):
                proposal = replace(
                    proposal,
                    status=OrganizationAgencyProposalStatus.EXPIRED,
                    last_tick=max(proposal.last_tick, current_tick),
                )
                work_concept.notices.add("proposal_expired")
                ledger_notices.add("proposal_expired")
                proposals.append(proposal)
                continue
            if not closed and not forced:
                proposals.append(proposal)
                continue
            recognition = _recognition_for(
                proposal,
                procedure_recognized=procedure_recognized,
                support=support,
                contest=contest,
                policy=active_policy,
            )
            existing = next(
                (
                    item
                    for item in work_concept.decisions
                    if item.proposal_id == proposal.proposal_id
                    and item.revision == proposal.revision
                ),
                None,
            )
            if existing is None:
                decided = OrganizationCollectiveDecision(
                    decision_id=organization_collective_decision_id(
                        owner.value,
                        organization_id,
                        proposal.proposal_id,
                        proposal.revision,
                        recognition,
                        current_tick,
                    ),
                    organization_id=organization_id,
                    proposal_id=proposal.proposal_id,
                    revision=proposal.revision,
                    procedure_ref=proposal.procedure_ref,
                    recognition=recognition,
                    authority_basis=_decision_authority(proposal, recognition),
                    support_count=support,
                    oppose_count=oppose,
                    abstain_count=abstain,
                    contest_count=contest,
                    implementation_mode=proposal.implementation_mode,
                    effect=proposal.effect,
                    target_kind=proposal.target_kind,
                    target_ref=proposal.target_ref,
                    expected_actors=proposal.expected_actors,
                    quantity=proposal.quantity,
                    decided_tick=current_tick,
                    window_end_tick=(
                        current_tick + active_policy.implementation_window_ticks
                    ),
                    provenance_code=_provenance_for(recognition),
                    resolved=proposal.target_kind not in _NONE_TARGET_KINDS,
                )
                work_concept.decisions.append(decided)
                _LOG.info(
                    "organization_agency_decision_recorded owner_id=%s "
                    "recognition=%s supporters=%s opponents=%s abstainers=%s",
                    owner.value,
                    recognition.value,
                    support,
                    oppose,
                    abstain,
                )
            else:
                decided = existing
            proposal = replace(
                proposal,
                status=OrganizationAgencyProposalStatus.DECIDED,
                support_count=decided.support_count,
                oppose_count=decided.oppose_count,
                abstain_count=decided.abstain_count,
                contest_count=decided.contest_count,
                last_tick=max(proposal.last_tick, current_tick),
            )
            proposals.append(proposal)
        work_concept.proposals = proposals

    # -- assemble bounded concepts -----------------------------------------
    concepts: list[OrganizationAgencyConcept] = []
    for organization_id in sorted(work):
        work_concept = work[organization_id]
        work_concept.proposals, truncated = _trim_records(
            work_concept.proposals,
            active_policy.max_proposals,
            key=lambda item: (item.opened_tick, item.proposal_id),
        )
        if truncated:
            work_concept.notices.add("agency_truncated")
            ledger_notices.add("agency_truncated")
        work_concept.positions, truncated = _trim_records(
            work_concept.positions,
            active_policy.max_positions,
            key=lambda item: (
                item.tick,
                item.proposal_id,
                item.revision,
                item.actor_id.value,
            ),
        )
        if truncated:
            work_concept.notices.add("agency_truncated")
            ledger_notices.add("agency_truncated")
        work_concept.amendments, truncated = _trim_records(
            work_concept.amendments,
            active_policy.max_amendments,
            key=lambda item: (item.amended_tick, item.amendment_id),
        )
        if truncated:
            work_concept.notices.add("agency_truncated")
            ledger_notices.add("agency_truncated")
        work_concept.decisions, truncated = _trim_records(
            work_concept.decisions,
            active_policy.max_decisions,
            key=lambda item: (item.decided_tick, item.decision_id),
        )
        if truncated:
            work_concept.notices.add("agency_truncated")
            ledger_notices.add("agency_truncated")
        work_concept.implementations, truncated = _trim_records(
            work_concept.implementations,
            active_policy.max_implementations,
            key=lambda item: (
                item.observed_tick,
                item.decision_id,
                item.actor_id.value,
            ),
        )
        if truncated:
            work_concept.notices.add("implementation_truncated")
            ledger_notices.add("implementation_truncated")

        first_ticks = [1]
        last_ticks = [current_tick]
        for item in work_concept.proposals:
            first_ticks.append(item.first_tick)
            last_ticks.append(item.last_tick)
        for position_item in work_concept.positions:
            first_ticks.append(position_item.tick)
            last_ticks.append(position_item.tick)
        concepts.append(
            OrganizationAgencyConcept(
                organization_id=organization_id,
                owner_id=owner,
                status=work_concept.status,
                first_tick=min(first_ticks),
                last_tick=max(last_ticks),
                proposals=tuple(work_concept.proposals),
                positions=tuple(work_concept.positions),
                amendments=tuple(work_concept.amendments),
                decisions=tuple(work_concept.decisions),
                implementations=tuple(work_concept.implementations),
                notices=tuple(sorted(work_concept.notices)),
            )
        )

    return OrganizationAgencyLedger(
        owner_id=owner,
        concepts=tuple(concepts),
        notices=tuple(sorted(ledger_notices)),
    )


def _agency_tick(observation: object) -> int:
    tick = getattr(observation, "tick", None)
    if type(tick) is int and tick >= 0:
        return tick
    return 0


def _concept_status_map(organization_concepts: object) -> dict[str, OrganizationStatus]:
    return {
        concept.organization_id: concept.status
        for concept in getattr(organization_concepts, "concepts", ())
    }


def _concept_by_id(organization_concepts: object) -> dict[str, object]:
    return {
        concept.organization_id: concept
        for concept in getattr(organization_concepts, "concepts", ())
    }


def _primary_effect(domain: OrganizationOperationDomain) -> OrganizationAgencyEffect:
    if domain is OrganizationOperationDomain.INTERNAL_COMMITMENT:
        return OrganizationAgencyEffect.COMMITMENT_DECLARED
    if domain is OrganizationOperationDomain.RESOURCE_CONTROL:
        return OrganizationAgencyEffect.GIVE
    if domain is OrganizationOperationDomain.STORAGE:
        return OrganizationAgencyEffect.ITEM_STORED
    if domain is OrganizationOperationDomain.RECORD_KEEPING:
        return OrganizationAgencyEffect.ARTIFACT_CREATED
    return OrganizationAgencyEffect.NONE


def _concept_procedure(concept: object) -> object | None:
    recognized = [
        procedure
        for procedure in getattr(concept, "procedures", ())
        if procedure.status is OrganizationStatus.RECOGNIZED
    ]
    if not recognized:
        return None
    from typing import cast

    return cast(object, min(recognized, key=lambda item: item.anchor_id))


def _concept_domain(concept: object) -> tuple[OrganizationOperationDomain, str | None]:
    if getattr(concept, "commitments", ()):
        return OrganizationOperationDomain.INTERNAL_COMMITMENT, None
    resources = getattr(concept, "resources", ())
    if resources:
        contested = any(
            resource.access_belief in ("claimed", "contested", "shared_use")
            for resource in resources
        )
        if contested:
            resource = min(resources, key=lambda item: item.anchor_id)
            return (
                OrganizationOperationDomain.RESOURCE_CONTROL,
                resource.anchor_id,
            )
        resource = min(resources, key=lambda item: item.anchor_id)
        return OrganizationOperationDomain.STORAGE, resource.anchor_id
    records = getattr(concept, "records", ())
    if records:
        record = min(records, key=lambda item: item.anchor_id)
        return OrganizationOperationDomain.RECORD_KEEPING, record.anchor_id
    if _concept_procedure(concept) is not None:
        return OrganizationOperationDomain.PROCEDURE_ACTION, None
    return OrganizationOperationDomain.PROCEDURE_ACTION, None


def _expected_actors(
    concept: object, policy: OrganizationAgencyPolicy
) -> tuple[AgentId, ...]:
    values = [
        AgentId(member.member_id.removeprefix("body-"))
        for member in getattr(concept, "members", ())
    ]
    unique = tuple(
        sorted(
            {value.value: value for value in values}.values(),
            key=lambda item: item.value,
        )
    )
    return unique[: min(4, policy.max_expected_actors)]


def generate_organization_agency_proposal(
    ledger: object,
    observation: object,
    identity: object,
    organization_concepts: object | None,
    policy: OrganizationAgencyPolicy | None = None,
) -> OrganizationAgencyLedger:
    """Append at most one deterministic owner proposal per qualifying concept."""

    if type(ledger) is not OrganizationAgencyLedger:
        return cast(OrganizationAgencyLedger, ledger)
    if organization_concepts is None:
        return ledger
    active_policy = _DEFAULT_AGENCY_POLICY if policy is None else policy
    if type(active_policy) is not OrganizationAgencyPolicy:
        _fail("organization_agency_policy_mismatch")
    tick = _agency_tick(observation)
    status_by_id = _concept_status_map(organization_concepts)
    concepts_by_id = _concept_by_id(organization_concepts)
    updated: list[OrganizationAgencyConcept] = []
    generated = 0
    for agency_concept in ledger.concepts:
        status = status_by_id.get(agency_concept.organization_id)
        if status in (OrganizationStatus.DISSOLVED, OrganizationStatus.RETIRED):
            updated.append(agency_concept)
            continue
        if status not in (
            OrganizationStatus.CANDIDATE,
            OrganizationStatus.RECOGNIZED,
            OrganizationStatus.DISPUTED,
        ):
            updated.append(agency_concept)
            continue
        if any(
            proposal.status
            in (
                OrganizationAgencyProposalStatus.ACTIVE,
                OrganizationAgencyProposalStatus.AMENDED,
            )
            for proposal in agency_concept.proposals
        ):
            updated.append(agency_concept)
            continue
        source = concepts_by_id.get(agency_concept.organization_id)
        if source is None:
            updated.append(agency_concept)
            continue
        if len(agency_concept.proposals) >= active_policy.max_proposals:
            updated.append(agency_concept)
            continue
        domain, anchor = _concept_domain(source)
        effect = _primary_effect(domain)
        procedure = _concept_procedure(source)
        proposal_ref = organization_agency_ref(
            "|".join(
                (
                    domain.value,
                    effect.value,
                    anchor or "",
                    getattr(procedure, "anchor_id", "") or "",
                    tick.__str__(),
                )
            ),
            namespace="proposal",
        )
        target_kind, target_ref = (
            ("none", None)
            if anchor is None
            else ("item", organization_agency_ref(anchor, namespace="target"))
        )
        terms_ref = organization_agency_ref(proposal_ref, namespace="terms")
        built = OrganizationProposal(
            proposal_id=organization_proposal_id(
                ledger.owner_id.value, agency_concept.organization_id, proposal_ref
            ),
            organization_id=agency_concept.organization_id,
            proposal_ref=proposal_ref,
            topic=_TOPIC_BY_DOMAIN[domain],
            domain=domain,
            effect=effect,
            implementation_mode=(
                OrganizationAgencyImplementationMode.TESTIMONIAL
                if effect is OrganizationAgencyEffect.NONE
                else OrganizationAgencyImplementationMode.PHYSICAL
            ),
            target_kind=target_kind,
            target_ref=target_ref,
            procedure_ref=(
                None
                if procedure is None
                else organization_agency_ref(
                    cast(Any, procedure).anchor_id, namespace="procedure"
                )
            ),
            expected_actors=_expected_actors(source, active_policy),
            quantity=1,
            revision=1,
            terms_ref=terms_ref,
            status=OrganizationAgencyProposalStatus.ACTIVE,
            opened_tick=tick,
            deadline_tick=tick + active_policy.proposal_window_ticks,
            first_tick=tick,
            last_tick=tick,
            authority_basis=OrganizationAuthorityBasis.SELF_AUTHORED,
            provenance_code=OrganizationAgencyProvenance.SELF_AUTHORED,
        )
        updated.append(
            replace(
                agency_concept,
                proposals=tuple((*agency_concept.proposals, built)),
                last_tick=max(agency_concept.last_tick, tick),
            )
        )
        generated += 1
        _LOG.info(
            "organization_agency_proposal_generated owner_id=%s organization_id=%s "
            "domain=%s",
            ledger.owner_id.value,
            agency_concept.organization_id,
            domain.value,
        )
    if not generated:
        return ledger
    return OrganizationAgencyLedger(
        owner_id=ledger.owner_id,
        concepts=tuple(updated),
        notices=ledger.notices,
    )


def appraise_organization_agency_position(
    ledger: object,
    observation: object,
    identity: object,
    organization_concepts: object | None,
    policy: OrganizationAgencyPolicy | None = None,
) -> OrganizationAgencyLedger:
    """Append one deterministic owner position per active proposal revision."""

    if type(ledger) is not OrganizationAgencyLedger:
        return cast(OrganizationAgencyLedger, ledger)
    if organization_concepts is None:
        return ledger
    active_policy = _DEFAULT_AGENCY_POLICY if policy is None else policy
    if type(active_policy) is not OrganizationAgencyPolicy:
        _fail("organization_agency_policy_mismatch")
    tick = _agency_tick(observation)
    concepts_by_id = _concept_by_id(organization_concepts)
    updated: list[OrganizationAgencyConcept] = []
    for agency_concept in ledger.concepts:
        source = concepts_by_id.get(agency_concept.organization_id)
        if source is None:
            updated.append(agency_concept)
            continue
        positions = list(agency_concept.positions)
        proposals = list(agency_concept.proposals)
        for index, proposal in enumerate(proposals):
            if proposal.status not in (
                OrganizationAgencyProposalStatus.ACTIVE,
                OrganizationAgencyProposalStatus.AMENDED,
            ):
                continue
            owner_present = any(
                item.proposal_id == proposal.proposal_id
                and item.revision == proposal.revision
                and item.actor_id == ledger.owner_id
                for item in positions
            )
            if owner_present:
                continue
            if ledger.owner_id not in proposal.expected_actors:
                members = {
                    AgentId(member.member_id.removeprefix("body-"))
                    for member in getattr(source, "members", ())
                }
                if ledger.owner_id not in members:
                    continue
            procedure_recognized = (
                proposal.procedure_ref is not None
                and _procedure_is_recognized(source, proposal, active_policy)
            )
            if proposal.target_kind == "unknown" or proposal.procedure_ref is None:
                stance = OrganizationAgencyPositionStance.ABSTAIN
                authority = OrganizationAuthorityBasis.UNKNOWN
            elif (
                any(
                    resource.access_belief in ("claimed", "exclusive", "private")
                    for resource in getattr(source, "resources", ())
                )
                and proposal.domain is OrganizationOperationDomain.RESOURCE_CONTROL
            ):
                stance = OrganizationAgencyPositionStance.OPPOSE
                authority = OrganizationAuthorityBasis.SELF_AUTHORED
            elif procedure_recognized:
                stance = OrganizationAgencyPositionStance.SUPPORT
                authority = OrganizationAuthorityBasis.PROCEDURE_BELIEF
            else:
                stance = OrganizationAgencyPositionStance.ABSTAIN
                authority = OrganizationAuthorityBasis.UNKNOWN
            positions.append(
                OrganizationPosition(
                    proposal_id=proposal.proposal_id,
                    revision=proposal.revision,
                    actor_id=ledger.owner_id,
                    stance=stance,
                    authority_basis=authority,
                    tick=tick,
                )
            )
            proposals[index] = proposal
        updated.append(
            replace(
                agency_concept,
                positions=tuple(positions),
                last_tick=max(agency_concept.last_tick, tick),
            )
        )
    return OrganizationAgencyLedger(
        owner_id=ledger.owner_id,
        concepts=tuple(updated),
        notices=ledger.notices,
    )


_TERMINAL_IMPLEMENTATION_STATUSES: Final[
    frozenset[OrganizationAgencyImplementationStatus]
] = frozenset(
    {
        OrganizationAgencyImplementationStatus.IMPLEMENTED,
        OrganizationAgencyImplementationStatus.REFUSED,
        OrganizationAgencyImplementationStatus.SABOTAGED,
        OrganizationAgencyImplementationStatus.EXPIRED,
    }
)


def aggregate_organization_agency_decision(
    decision: OrganizationCollectiveDecision,
    implementations: Sequence[OrganizationImplementation],
    *,
    tick: int | None = None,
    dissolved: bool = False,
) -> OrganizationAgencyImplementationStatus:
    """Fold per-actor implementations into one decision-level status."""

    if type(decision) is not OrganizationCollectiveDecision:
        raise TypeError("decision must be OrganizationCollectiveDecision")
    statuses = [item.status for item in implementations]
    if dissolved:
        return OrganizationAgencyImplementationStatus.EXPIRED
    if any(
        status
        in (
            OrganizationAgencyImplementationStatus.REFUSED,
            OrganizationAgencyImplementationStatus.SABOTAGED,
            OrganizationAgencyImplementationStatus.CONTRARY,
        )
        for status in statuses
    ):
        return OrganizationAgencyImplementationStatus.OBSTRUCTED
    expected = len(decision.expected_actors)
    if (
        expected
        and len(statuses) >= expected
        and all(
            status is OrganizationAgencyImplementationStatus.IMPLEMENTED
            for status in statuses
        )
    ):
        return OrganizationAgencyImplementationStatus.IMPLEMENTED
    if any(
        status
        in (
            OrganizationAgencyImplementationStatus.IMPLEMENTED,
            OrganizationAgencyImplementationStatus.PARTIAL,
        )
        for status in statuses
    ):
        return OrganizationAgencyImplementationStatus.PARTIAL
    closed = tick is not None and tick >= decision.window_end_tick
    if (
        closed
        and expected
        and len(statuses) >= expected
        and all(
            status is OrganizationAgencyImplementationStatus.UNIMPLEMENTED
            for status in statuses
        )
    ):
        return OrganizationAgencyImplementationStatus.UNIMPLEMENTED
    if closed and any(
        status is OrganizationAgencyImplementationStatus.UNIMPLEMENTED
        for status in statuses
    ):
        return OrganizationAgencyImplementationStatus.UNIMPLEMENTED
    if not statuses or all(
        status
        in (
            OrganizationAgencyImplementationStatus.PENDING,
            OrganizationAgencyImplementationStatus.UNKNOWN,
        )
        for status in statuses
    ):
        return OrganizationAgencyImplementationStatus.PENDING
    return OrganizationAgencyImplementationStatus.UNKNOWN


def _occurrence_window_tick(occurrence: object) -> int | None:
    provenance = getattr(occurrence, "provenance", None)
    source_tick = getattr(provenance, "source_tick", None)
    if type(source_tick) is int:
        return source_tick
    tick = getattr(occurrence, "tick", None)
    if type(tick) is int:
        return tick
    return None


def track_organization_agency_implementation(
    ledger: object,
    observation: object,
    identity: object,
    policy: OrganizationAgencyPolicy | None = None,
) -> OrganizationAgencyLedger:
    """Track per-actor implementation from observed effects and testimony."""

    from agents.cognition.organization_agency_actions import (
        organization_agency_actor_value,
        organization_agency_contrary_effect,
        organization_agency_occurrence_matches,
    )
    from agents.cognition.organization_agency_communication import (
        OrganizationAgencyAct,
        parse_organization_agency_claim_relation,
    )

    if type(ledger) is not OrganizationAgencyLedger:
        return cast(OrganizationAgencyLedger, ledger)
    active_policy = _DEFAULT_AGENCY_POLICY if policy is None else policy
    if type(active_policy) is not OrganizationAgencyPolicy:
        _fail("organization_agency_policy_mismatch")
    tick = _agency_tick(observation)
    occurrences = tuple(getattr(observation, "occurrences", ()) or ())
    communications = tuple(getattr(observation, "communications", ()) or ())

    observed_actors: set[str] = set()
    for occurrence in occurrences:
        observed_actor = organization_agency_actor_value(occurrence)
        if observed_actor is not None:
            observed_actors.add(observed_actor)
    reports: dict[str, set[str]] = {}
    for communication in communications:
        speaker = getattr(communication, "speaker_id", None)
        speaker_value = getattr(speaker, "value", None)
        if speaker_value is None:
            continue
        speaker_actor = str(speaker_value).removeprefix("body-")
        utterance = getattr(communication, "utterance", None)
        content = getattr(utterance, "content", None)
        relations = () if content is None else tuple(content.relations)
        for relation in relations:
            claim = parse_organization_agency_claim_relation(relation)
            if claim is None:
                continue
            if claim.act is OrganizationAgencyAct.REFUSE:
                reports.setdefault(speaker_actor, set()).add("refusal")
            elif (
                claim.act is OrganizationAgencyAct.REPORT
                and claim.report_kind is not None
            ):
                reports.setdefault(speaker_actor, set()).add(claim.report_kind.value)

    updated: list[OrganizationAgencyConcept] = []
    for agency_concept in ledger.concepts:
        dissolved = agency_concept.status in (
            OrganizationStatus.DISSOLVED,
            OrganizationStatus.RETIRED,
        )
        implementations = list(agency_concept.implementations)
        decisions = list(agency_concept.decisions)
        notices = set(agency_concept.notices)
        for index, decision in enumerate(decisions):
            if decision.implementation_status in _TERMINAL_IMPLEMENTATION_STATUSES:
                continue
            by_actor = {
                item.actor_id.value: item
                for item in implementations
                if item.decision_id == decision.decision_id
            }
            for actor in decision.expected_actors:
                actor_value = actor.value
                window_occurrences = [
                    occurrence
                    for occurrence in occurrences
                    if organization_agency_actor_value(occurrence) == actor_value
                    and (
                        _occurrence_window_tick(occurrence) is None
                        or decision.decided_tick
                        <= (_occurrence_window_tick(occurrence) or 0)
                        <= decision.window_end_tick
                    )
                ]
                matching = [
                    occurrence
                    for occurrence in window_occurrences
                    if organization_agency_occurrence_matches(decision, occurrence)
                ]
                contrary = [
                    occurrence
                    for occurrence in window_occurrences
                    if organization_agency_contrary_effect(
                        getattr(occurrence, "kind", None),
                        getattr(occurrence, "public_facts", None),
                    )
                ]
                actor_reports = reports.get(actor_value, set())
                prior_position = any(
                    item.proposal_id == decision.proposal_id
                    and item.revision == decision.revision
                    and item.actor_id.value == actor_value
                    and (
                        item.stance
                        in (
                            OrganizationAgencyPositionStance.OPPOSE,
                            OrganizationAgencyPositionStance.WITHDRAW,
                        )
                        or item.refused
                    )
                    for item in agency_concept.positions
                )
                if dissolved:
                    status = OrganizationAgencyImplementationStatus.EXPIRED
                    provenance = OrganizationAgencyProvenance.EXPIRED
                    noticed = False
                elif "refusal" in actor_reports:
                    status = OrganizationAgencyImplementationStatus.REFUSED
                    provenance = OrganizationAgencyProvenance.DECLARED_REFUSAL
                    noticed = False
                elif contrary and (
                    prior_position or "sabotage" in actor_reports or len(contrary) >= 2
                ):
                    status = OrganizationAgencyImplementationStatus.SABOTAGED
                    provenance = OrganizationAgencyProvenance.DECLARED_SABOTAGE
                    noticed = False
                elif contrary:
                    status = OrganizationAgencyImplementationStatus.CONTRARY
                    provenance = OrganizationAgencyProvenance.CONTRARY_EFFECT
                    noticed = False
                elif decision.implementation_mode is (
                    OrganizationAgencyImplementationMode.PHYSICAL
                ):
                    if len(matching) >= decision.quantity:
                        status = OrganizationAgencyImplementationStatus.IMPLEMENTED
                        provenance = OrganizationAgencyProvenance.OBSERVED_EFFECT
                    elif matching:
                        status = OrganizationAgencyImplementationStatus.PARTIAL
                        provenance = OrganizationAgencyProvenance.OBSERVED_EFFECT
                    elif tick >= decision.window_end_tick and (
                        actor_value in observed_actors
                    ):
                        status = OrganizationAgencyImplementationStatus.UNIMPLEMENTED
                        provenance = OrganizationAgencyProvenance.UNKNOWN
                    else:
                        status = OrganizationAgencyImplementationStatus.UNKNOWN
                        provenance = OrganizationAgencyProvenance.UNKNOWN
                    noticed = False
                else:
                    if "implemented" in actor_reports:
                        status = OrganizationAgencyImplementationStatus.IMPLEMENTED
                        provenance = OrganizationAgencyProvenance.SELF_AUTHORED
                        noticed = False
                    elif "partial" in actor_reports:
                        status = OrganizationAgencyImplementationStatus.PARTIAL
                        provenance = OrganizationAgencyProvenance.UNKNOWN
                        noticed = False
                    elif "sabotage" in actor_reports:
                        status = OrganizationAgencyImplementationStatus.CONTRARY
                        provenance = OrganizationAgencyProvenance.CONTRARY_EFFECT
                        noticed = True
                    elif tick >= decision.window_end_tick and (
                        actor_value in observed_actors
                    ):
                        status = OrganizationAgencyImplementationStatus.UNIMPLEMENTED
                        provenance = OrganizationAgencyProvenance.UNKNOWN
                        noticed = False
                    else:
                        status = OrganizationAgencyImplementationStatus.UNKNOWN
                        provenance = OrganizationAgencyProvenance.UNKNOWN
                        noticed = False
                if noticed:
                    notices.add("sabotage_unverified")
                if "refusal" in actor_reports and contrary:
                    notices.add("refusal_unverified")
                implementation_id = organization_implementation_id(
                    ledger.owner_id.value,
                    agency_concept.organization_id,
                    decision.decision_id,
                    actor_value,
                    decision.implementation_mode.value,
                    tick,
                )
                evidence = organization_agency_evidence_id(
                    ledger.owner_id.value,
                    agency_concept.organization_id,
                    "observation",
                    tick,
                    0,
                    "|".join((decision.decision_id, actor_value, status.value)),
                )
                record = OrganizationImplementation(
                    implementation_id=implementation_id,
                    decision_id=decision.decision_id,
                    actor_id=actor,
                    status=status,
                    effect=decision.effect,
                    observed_tick=tick,
                    provenance_code=provenance,
                    evidence_refs=(evidence,),
                    resolved=status
                    in (
                        OrganizationAgencyImplementationStatus.IMPLEMENTED,
                        OrganizationAgencyImplementationStatus.PARTIAL,
                        OrganizationAgencyImplementationStatus.REFUSED,
                        OrganizationAgencyImplementationStatus.SABOTAGED,
                        OrganizationAgencyImplementationStatus.CONTRARY,
                        OrganizationAgencyImplementationStatus.UNIMPLEMENTED,
                        OrganizationAgencyImplementationStatus.EXPIRED,
                    ),
                )
                implementations = [
                    item
                    for item in implementations
                    if not (
                        item.decision_id == decision.decision_id
                        and item.actor_id == actor
                    )
                ]
                implementations.append(record)
                by_actor[actor_value] = record
            aggregate = aggregate_organization_agency_decision(
                decision,
                tuple(by_actor.values()),
                tick=tick,
                dissolved=dissolved,
            )
            decisions[index] = replace(decision, implementation_status=aggregate)
            _LOG.info(
                "organization_agency_implementation_status owner_id=%s "
                "decision_id=%s status=%s",
                ledger.owner_id.value,
                decision.decision_id,
                aggregate.value,
            )
        updated.append(
            replace(
                agency_concept,
                implementations=tuple(implementations),
                decisions=tuple(decisions),
                notices=tuple(sorted(notices)),
            )
        )
    return OrganizationAgencyLedger(
        owner_id=ledger.owner_id,
        concepts=tuple(updated),
        notices=ledger.notices,
    )


__all__ = [
    "FORBIDDEN_AGENCY_FIELD_NAMES",
    "ORGANIZATION_AGENCY_ANALYSIS_POLICY_VERSION",
    "ORGANIZATION_AGENCY_CONTRARY_EFFECTS",
    "ORGANIZATION_AGENCY_DOMAIN_EFFECTS",
    "ORGANIZATION_AGENCY_EFFECTS",
    "ORGANIZATION_AGENCY_ERROR_CODES",
    "ORGANIZATION_AGENCY_EVIDENCE_ID_PREFIX",
    "ORGANIZATION_AGENCY_NOTICE_CODES",
    "ORGANIZATION_AGENCY_POLICY_VERSION",
    "ORGANIZATION_AGENCY_REF_NAMESPACES",
    "ORGANIZATION_AGENCY_TARGET_KINDS",
    "ORGANIZATION_AMENDMENT_ID_PREFIX",
    "ORGANIZATION_COLLECTIVE_DECISION_ID_PREFIX",
    "ORGANIZATION_IMPLEMENTATION_ID_PREFIX",
    "ORGANIZATION_PROPOSAL_ID_PREFIX",
    "ORGANIZATION_PUBLICATION_DECISION_ID_PREFIX",
    "ORGANIZATION_PUBLICATION_IMPLEMENTATION_ID_PREFIX",
    "OrganizationAgencyConcept",
    "OrganizationAgencyEffect",
    "OrganizationAgencyError",
    "OrganizationAgencyImplementationMode",
    "OrganizationAgencyImplementationStatus",
    "OrganizationAgencyLedger",
    "OrganizationAgencyPolicy",
    "OrganizationAgencyPositionStance",
    "OrganizationAgencyProposalStatus",
    "OrganizationAgencyProvenance",
    "OrganizationAgencyRecognition",
    "OrganizationAgencyReportKind",
    "OrganizationAgencyTopic",
    "OrganizationAmendment",
    "OrganizationAuthorityBasis",
    "OrganizationCollectiveDecision",
    "OrganizationImplementation",
    "OrganizationOperationDomain",
    "OrganizationPosition",
    "OrganizationProposal",
    "default_organization_agency_policy",
    "empty_organization_agency_ledger",
    "organization_agency_evidence_id",
    "organization_agency_ref",
    "organization_amendment_id",
    "organization_collective_decision_id",
    "organization_implementation_id",
    "organization_proposal_id",
    "organization_publication_decision_id",
    "organization_publication_implementation_id",
    "require_organization_agency_evidence_id",
    "require_organization_agency_ref",
    "require_organization_agency_tick",
    "require_organization_amendment_id",
    "require_organization_collective_decision_id",
    "require_organization_implementation_id",
    "require_organization_proposal_id",
    "require_organization_publication_decision_id",
    "require_organization_publication_implementation_id",
    "require_owner_organization_agency",
]
