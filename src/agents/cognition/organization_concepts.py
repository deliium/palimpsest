"""Closed owner-scoped organization concept vocabulary.

An organization is a belief one agent holds about a recurring collective
structure; it is never an objective entity. This module defines only the frozen
vocabulary, identity grammar, policy bounds, and error codes that later
organization code consumes. It creates no objective organization entity, roster,
treasury, registry, command, or permission. All organization activity remains
ordinary agent commands, speech, records, roles, and recognized procedures.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final, NoReturn

from agents.models import AgentId

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.organization_concepts"
)

ORGANIZATION_CONCEPT_POLICY_VERSION: Final[str] = "organization-concepts.v1"
ORGANIZATION_CONCEPT_ID_PREFIX: Final[str] = "orgc-"
ORGANIZATION_ANALYTICAL_ID_PREFIX: Final[str] = "org-"
ORGANIZATION_PUBLICATION_ID_PREFIX: Final[str] = "org-edge-"
ORGANIZATION_ID_HEX_LEN: Final[int] = 16

_CONCEPT_NAMESPACE: Final[str] = "palimpsest.organization.concept.v1"
_LINEAGE_NAMESPACE: Final[str] = "palimpsest.organization.lineage.v1"
_CONCEPT_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{ORGANIZATION_CONCEPT_ID_PREFIX}[0-9a-f]{{{ORGANIZATION_ID_HEX_LEN}}}$"
)
_ANALYTICAL_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{ORGANIZATION_ANALYTICAL_ID_PREFIX}[0-9a-f]{{{ORGANIZATION_ID_HEX_LEN}}}$"
)
_PUBLICATION_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{ORGANIZATION_PUBLICATION_ID_PREFIX}[0-9a-f]{{{ORGANIZATION_ID_HEX_LEN}}}$"
)
_LABEL_WORD_PATTERN: Final[re.Pattern[str]] = re.compile(r"[a-z0-9]+")


class OrganizationStatus(StrEnum):
    """Closed owner-local lifecycle status for one organization concept."""

    CANDIDATE = "candidate"
    RECOGNIZED = "recognized"
    DISPUTED = "disputed"
    DISSOLVED = "dissolved"
    RETIRED = "retired"


class OrganizationMembershipStatus(StrEnum):
    """Closed perceived membership status; membership is never a partition."""

    EXPLICIT = "explicit"
    PERCEIVED = "perceived"
    DISPUTED = "disputed"
    UNKNOWN = "unknown"
    FORMER = "former"


class OrganizationTemporalScope(StrEnum):
    """Closed claim about how long a perceived membership is expected to last."""

    ONGOING = "ongoing"
    TEMPORARY = "temporary"
    UNKNOWN = "unknown"


class OrganizationEvidenceChannel(StrEnum):
    """Closed provenance channel for one organization belief contribution."""

    OBSERVED = "observed"
    COMMUNICATED = "communicated"
    REMEMBERED = "remembered"
    RECORDED = "recorded"


class OrganizationMembershipBasis(StrEnum):
    """Closed basis on which an owner believes someone belongs."""

    SELF_IDENTIFICATION = "self_identification"
    PARTICIPATION = "participation"
    ROLE_OCCUPANCY = "role_occupancy"
    COLLECTIVE_PARTICIPATION = "collective_participation"
    COMMUNICATED_CLAIM = "communicated_claim"
    RECORD_REFERENCE = "record_reference"
    INFERENCE = "inference"


class OrganizationIdentityStance(StrEnum):
    """Closed owner stance toward its own affiliation with a concept."""

    MEMBER = "member"
    AFFILIATED = "affiliated"
    OUTSIDE = "outside"
    UNKNOWN = "unknown"


class OrganizationConceptualization(StrEnum):
    """Closed degree to which an owner holds a name for the structure."""

    NONE = "none"
    NAMED_USUAL = "named_usual"
    NAMED_CUSTOM = "named_custom"


class OrganizationGoalKind(StrEnum):
    """Closed reference kind for a believed shared goal."""

    COLLECTIVE_PROJECT = "collective_project"
    PUBLIC_GOOD = "public_good"
    RESOURCE_ALLOCATION = "resource_allocation"
    MIGRATION = "migration"
    SHARED_DEFENSE = "shared_defense"
    STORAGE = "storage"
    NORM_ENFORCEMENT = "norm_enforcement"
    UNKNOWN = "unknown"


class OrganizationResourceKind(StrEnum):
    """Closed reference kind for a believed shared resource."""

    REPOSITORY = "repository"
    ARTIFACT = "artifact"
    STORED_RESOURCE = "stored_resource"
    SHELTER = "shelter"
    TERRITORY = "territory"
    UNKNOWN = "unknown"


class OrganizationProcedureKind(StrEnum):
    """Closed reference kind for a believed recognized procedure."""

    INSTITUTION_CONCEPT = "institution_concept"
    SOCIAL_CONVENTION = "social_convention"
    UNKNOWN = "unknown"


class OrganizationRecordKind(StrEnum):
    """Closed reference kind for a believed record of the structure."""

    ARTIFACT = "artifact"
    REPOSITORY = "repository"
    UNKNOWN = "unknown"


class OrganizationCommitmentRole(StrEnum):
    """Closed owner-side role in a believed internal commitment."""

    DEBTOR = "debtor"
    CREDITOR = "creditor"


class OrganizationRevisionKind(StrEnum):
    """Closed reason for one owner-local concept revision."""

    MEMBERSHIP_REVISED = "membership_revised"
    ROLE_REVISED = "role_revised"
    GOAL_REVISED = "goal_revised"
    RESOURCE_REVISED = "resource_revised"
    PROCEDURE_REVISED = "procedure_revised"
    RECORD_REVISED = "record_revised"
    COMMITMENT_REVISED = "commitment_revised"
    IDENTITY_REVISED = "identity_revised"
    CONTINUED = "continued"
    SPLIT = "split"
    MERGED = "merged"
    DISSOLVED = "dissolved"
    REVIVED = "revived"


class OrganizationLineageKind(StrEnum):
    """Closed forward-only lineage relation kind."""

    CONTINUED = "continued"
    TRANSFORMED = "transformed"
    SPLIT = "split"
    MERGE = "merge"
    DISSOLVED = "dissolved"
    EMERGED = "emerged"


ORGANIZATION_CONCEPT_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "organization_invalid_owner",
        "organization_invalid_id",
        "organization_invalid_status",
        "organization_invalid_member",
        "organization_duplicate_member",
        "organization_unknown_anchor",
        "organization_tick_regression",
        "organization_cap_exceeded",
        "organization_foreign_ledger",
        "organization_forbidden_label",
        "organization_invalid_temporal_scope",
        "organization_invalid_lineage",
        "organization_lineage_cycle",
        "organization_policy_mismatch",
        "organization_invalid_claim",
    }
)

FORBIDDEN_ORGANIZATION_LABEL_TOKENS: Final[frozenset[str]] = frozenset(
    {
        "army",
        "bank",
        "bureau",
        "church",
        "company",
        "corporation",
        "court",
        "department",
        "empire",
        "firm",
        "government",
        "guild",
        "ministry",
        "nation",
        "party",
        "police",
        "polity",
        "religion",
        "state",
        "treasury",
        "tribe",
        "university",
    }
)


class OrganizationConceptError(ValueError):
    """Stable-code organization contract violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        if code not in ORGANIZATION_CONCEPT_ERROR_CODES:
            raise ValueError("organization_invalid_error_code")
        self.code: str = code
        super().__init__(code)


def _fail(code: str) -> NoReturn:
    raise OrganizationConceptError(code)


@dataclass(frozen=True, slots=True)
class OrganizationConceptPolicy:
    """Locked owner-local organization cognition bounds.

    Every value is part of the accepted contract. Any deviation is a programming
    error and fails closed.
    """

    max_concepts: int = 16
    max_members: int = 32
    max_roles: int = 16
    max_goals: int = 16
    max_resources: int = 16
    max_procedures: int = 16
    max_records: int = 16
    max_commitments: int = 16
    max_identities: int = 8
    max_evidence: int = 64
    max_snapshots: int = 64
    max_revisions: int = 32
    max_lineage: int = 32
    recognition_min_members: int = 2
    recognition_min_channels: int = 2
    recognition_min_evidence: int = 3
    recognition_floor: float = 0.45
    retire_floor: float = 0.12
    window_ticks: int = 100
    temporary_default_ticks: int = 16
    merge_jaccard: float = 0.5
    split_containment: float = 0.4

    def __post_init__(self) -> None:
        for name, expected in _LOCKED_POLICY_VALUES.items():
            actual = getattr(self, name)
            if type(actual) is not type(expected) or actual != expected:
                _fail("organization_policy_mismatch")


_LOCKED_POLICY_VALUES: Final[Mapping[str, int | float]] = MappingProxyType(
    {
        "max_concepts": 16,
        "max_members": 32,
        "max_roles": 16,
        "max_goals": 16,
        "max_resources": 16,
        "max_procedures": 16,
        "max_records": 16,
        "max_commitments": 16,
        "max_identities": 8,
        "max_evidence": 64,
        "max_snapshots": 64,
        "max_revisions": 32,
        "max_lineage": 32,
        "recognition_min_members": 2,
        "recognition_min_channels": 2,
        "recognition_min_evidence": 3,
        "recognition_floor": 0.45,
        "retire_floor": 0.12,
        "window_ticks": 100,
        "temporary_default_ticks": 16,
        "merge_jaccard": 0.5,
        "split_containment": 0.4,
    }
)

_DEFAULT_POLICY: Final[OrganizationConceptPolicy] = OrganizationConceptPolicy()


def default_organization_concept_policy() -> OrganizationConceptPolicy:
    """Return the single locked policy instance."""

    return _DEFAULT_POLICY


def _require_text(value: object, code: str) -> str:
    if type(value) is not str or not value:
        _fail(code)
    return value


def require_organization_tick(value: object) -> int:
    """Require an exact non-negative tick; booleans are rejected."""

    if type(value) is not int or value < 0:
        _fail("organization_tick_regression")
    return value


def _require_identifiers(values: object, code: str) -> tuple[str, ...]:
    if type(values) is not list and type(values) is not tuple:
        _fail(code)
    items = tuple(values)
    if not items:
        _fail(code)
    for item in items:
        if type(item) is not str or not item:
            _fail(code)
    return items


def _require_unique_members(values: Sequence[str]) -> tuple[str, ...]:
    members = _require_identifiers(values, "organization_invalid_member")
    if len(set(members)) != len(members):
        _fail("organization_duplicate_member")
    return tuple(sorted(members))


def _require_unique_anchors(values: Sequence[str]) -> tuple[str, ...]:
    anchors = _require_identifiers(values, "organization_unknown_anchor")
    return tuple(sorted(set(anchors)))


def _digest(namespace: str, material: Sequence[str]) -> str:
    payload = "\x1f".join((namespace, *material))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:ORGANIZATION_ID_HEX_LEN]


def organization_concept_id(
    owner_id: str,
    creation_tick: int,
    founding_member_ids: Sequence[str],
    structural_anchors: Sequence[str],
) -> str:
    """Mint one owner-local concept id from creation evidence.

    The id is content-addressed exactly once; continuation inherits it and split
    children or merge results mint new ids from their own creation evidence.
    """

    owner = _require_text(owner_id, "organization_invalid_owner")
    tick = require_organization_tick(creation_tick)
    members = _require_unique_members(founding_member_ids)
    anchors = _require_unique_anchors(structural_anchors)
    body = _digest(
        _CONCEPT_NAMESPACE,
        (owner, str(tick), *members, "|", *anchors),
    )
    return f"{ORGANIZATION_CONCEPT_ID_PREFIX}{body}"


def organization_lineage_id(
    owner_id: str,
    kind: str,
    tick: int,
    from_ids: Sequence[str],
    to_ids: Sequence[str],
) -> str:
    """Mint one owner-local lineage edge id from its endpoints and kind."""

    owner = _require_text(owner_id, "organization_invalid_owner")
    lineage_kind = _require_text(kind, "organization_invalid_lineage")
    lineage_tick = require_organization_tick(tick)
    sources = require_organization_concept_ids(from_ids, "organization_invalid_lineage")
    targets = require_organization_concept_ids(to_ids, "organization_invalid_lineage")
    body = _digest(
        _LINEAGE_NAMESPACE,
        (owner, lineage_kind, str(lineage_tick), *sources, "|", *targets),
    )
    return f"{ORGANIZATION_CONCEPT_ID_PREFIX}{body}"


def require_organization_concept_id(
    value: object, code: str = "organization_invalid_id"
) -> str:
    """Require an owner-local ``orgc-`` identity."""

    if type(value) is not str or _CONCEPT_ID_PATTERN.match(value) is None:
        _fail(code)
    return value


def require_organization_concept_ids(
    values: object, code: str = "organization_invalid_id"
) -> tuple[str, ...]:
    """Require a non-empty sequence of owner-local ``orgc-`` identities."""

    items = _require_identifiers(values, code)
    for item in items:
        require_organization_concept_id(item, code)
    return tuple(sorted(set(items)))


def require_organization_analytical_id(
    value: object, code: str = "organization_invalid_id"
) -> str:
    """Require a detached analytical ``org-`` identity."""

    if type(value) is not str or _ANALYTICAL_ID_PATTERN.match(value) is None:
        _fail(code)
    return value


def require_organization_publication_id(
    value: object, code: str = "organization_invalid_id"
) -> str:
    """Require a published ``org-edge-`` lineage identity."""

    if type(value) is not str or _PUBLICATION_ID_PATTERN.match(value) is None:
        _fail(code)
    return value


def organization_label_is_forbidden(label: str) -> bool:
    """Return whether a label contains a hard-coded organization class token."""

    if type(label) is not str:
        _fail("organization_forbidden_label")
    return bool(
        set(_LABEL_WORD_PATTERN.findall(label.casefold()))
        & FORBIDDEN_ORGANIZATION_LABEL_TOKENS
    )


def require_organization_label(label: str) -> str:
    """Require an ordinary private label that names no hard-coded class."""

    if type(label) is not str or not label.strip():
        _fail("organization_forbidden_label")
    if organization_label_is_forbidden(label):
        _fail("organization_forbidden_label")
    return label.strip()


# ---------------------------------------------------------------------------
# Bounded owner-scoped belief records
# ---------------------------------------------------------------------------

FORBIDDEN_ORGANIZATION_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "government",
        "church",
        "corporation",
        "army",
        "university",
        "guild",
        "state",
        "nation",
        "polity",
        "empire",
        "tribe",
        "treasury",
        "bank",
        "court",
        "police",
        "party",
        "religion",
        "ministry",
        "department",
        "firm",
        "company",
        "organization_type",
        "authoritative_leader",
        "current_decision",
        "membership_roster",
        "global_registry",
    }
)

ORGANIZATION_NOTICE_CODES: Final[frozenset[str]] = frozenset(
    {
        "foreign_owner",
        "missing_institution",
        "missing_office",
        "unresolved_anchor",
        "history_truncated",
        "membership_conflict",
        "temporary_expired",
    }
)

_LABEL_TOKEN_MAX_LEN: Final[int] = 32
_LABEL_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_REASON_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]*$")
_HEX64_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_QUANTUM: Final[Decimal] = Decimal("0.000001")
_ACTIVE_STATUSES: Final[frozenset[OrganizationStatus]] = frozenset(
    {OrganizationStatus.CANDIDATE, OrganizationStatus.RECOGNIZED}
)


def _ordered_unique(items: object, code: str) -> tuple[str, ...]:
    if not isinstance(items, (list, tuple)):
        _fail(code)
    values = tuple(items)
    for item in values:
        if type(item) is not str or not item:
            _fail(code)
    if len(set(values)) != len(values):
        _fail("organization_duplicate_member" if code.endswith("members") else code)
    return tuple(sorted(values))


def _require_id(value: object) -> str:
    return _require_text(value, "organization_invalid_id")


def _require_hex64(value: object) -> str:
    if type(value) is not str or _HEX64_PATTERN.match(value) is None:
        _fail("organization_invalid_id")
    return value


def _require_reason_token(value: object) -> str:
    if type(value) is not str or _REASON_TOKEN_PATTERN.match(value) is None:
        _fail("organization_invalid_status")
    return value


def _require_enum(value: object, enum_type: type[StrEnum], code: str) -> StrEnum:
    if type(value) is not enum_type:
        _fail(code)
    return value


def _require_bool(value: object) -> bool:
    if type(value) is not bool:
        _fail("organization_invalid_status")
    return value


def _require_unit(value: object) -> float:
    if type(value) is not float:
        _fail("organization_invalid_status")
    if value != value or value in (float("inf"), float("-inf")):
        _fail("organization_invalid_status")
    quantized = float(Decimal(str(value)).quantize(_QUANTUM, rounding=ROUND_HALF_UP))
    if quantized < 0.0 or quantized > 1.0:
        _fail("organization_invalid_status")
    return quantized


def _require_count(value: object) -> int:
    if type(value) is not int or value < 0:
        _fail("organization_invalid_status")
    return value


def _require_label_token(value: object) -> str | None:
    if value is None:
        return None
    if type(value) is not str:
        _fail("organization_forbidden_label")
    if len(value) > _LABEL_TOKEN_MAX_LEN or _LABEL_TOKEN_PATTERN.match(value) is None:
        _fail("organization_forbidden_label")
    if organization_label_is_forbidden(value):
        _fail("organization_forbidden_label")
    return value


def _reject_forbidden_fields(cls: type[object]) -> None:
    names = set(getattr(cls, "__dataclass_fields__", {}))
    if names & FORBIDDEN_ORGANIZATION_FIELD_NAMES:
        _fail("organization_forbidden_label")


def _require_owner_id(value: object) -> AgentId:
    if type(value) is not AgentId:
        _fail("organization_invalid_owner")
    return value


def _require_span(first_tick: object, last_tick: object) -> tuple[int, int]:
    first = require_organization_tick(first_tick)
    last = require_organization_tick(last_tick)
    if last < first:
        _fail("organization_tick_regression")
    return first, last


def _ordered_channels(values: object) -> tuple[OrganizationEvidenceChannel, ...]:
    if not isinstance(values, (list, tuple)):
        _fail("organization_invalid_status")
    items: list[OrganizationEvidenceChannel] = []
    for value in values:
        channel = _require_enum(
            value, OrganizationEvidenceChannel, "organization_invalid_status"
        )
        if channel not in items:
            items.append(channel)  # type: ignore[arg-type]
    return tuple(sorted(items, key=lambda item: item.value))


@dataclass(frozen=True, slots=True)
class OrganizationEvidence:
    """One bounded piece of owner-local organization evidence."""

    evidence_id: str
    ordinal: int
    channel: OrganizationEvidenceChannel
    ref: str
    tick: int
    anchor_digest: str
    actor_id: str | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(self, "evidence_id", _require_id(self.evidence_id))
        object.__setattr__(self, "ref", _require_id(self.ref))
        object.__setattr__(self, "ordinal", _require_count(self.ordinal))
        object.__setattr__(
            self,
            "channel",
            _require_enum(
                self.channel, OrganizationEvidenceChannel, "organization_invalid_status"
            ),
        )
        object.__setattr__(self, "tick", require_organization_tick(self.tick))
        object.__setattr__(self, "anchor_digest", _require_hex64(self.anchor_digest))
        if self.actor_id is not None:
            object.__setattr__(self, "actor_id", _require_id(self.actor_id))


@dataclass(frozen=True, slots=True)
class OrganizationMemberBelief:
    """One perceived member of a believed organization."""

    member_id: str
    status: OrganizationMembershipStatus
    basis: OrganizationMembershipBasis
    temporal_scope: OrganizationTemporalScope
    first_tick: int
    last_tick: int
    strength: float
    channels: tuple[OrganizationEvidenceChannel, ...]
    independently_evidenced: bool
    evidence_refs: tuple[str, ...] = ()
    expires_tick: int | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(self, "member_id", _require_id(self.member_id))
        object.__setattr__(
            self,
            "status",
            _require_enum(
                self.status,
                OrganizationMembershipStatus,
                "organization_invalid_status",
            ),
        )
        object.__setattr__(
            self,
            "basis",
            _require_enum(
                self.basis, OrganizationMembershipBasis, "organization_invalid_status"
            ),
        )
        scope = _require_enum(
            self.temporal_scope,
            OrganizationTemporalScope,
            "organization_invalid_temporal_scope",
        )
        first, last = _require_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "temporal_scope", scope)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        object.__setattr__(self, "strength", _require_unit(self.strength))
        object.__setattr__(self, "channels", _ordered_channels(self.channels))
        object.__setattr__(
            self,
            "independently_evidenced",
            _require_bool(self.independently_evidenced),
        )
        refs = _ordered_unique(self.evidence_refs, "organization_invalid_member")
        object.__setattr__(self, "evidence_refs", refs)
        if scope is OrganizationTemporalScope.TEMPORARY:
            if self.expires_tick is None:
                _fail("organization_invalid_temporal_scope")
            expires = require_organization_tick(self.expires_tick)
            if expires < first:
                _fail("organization_invalid_temporal_scope")
            object.__setattr__(self, "expires_tick", expires)
        elif self.expires_tick is not None:
            _fail("organization_invalid_temporal_scope")


@dataclass(frozen=True, slots=True)
class OrganizationRoleBelief:
    """One believed role, referencing an owner-local office identity."""

    office_id: str
    function: str
    context_key: str
    occupant_ids: tuple[str, ...]
    status: OrganizationStatus
    first_tick: int
    last_tick: int
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(self, "office_id", _require_id(self.office_id))
        object.__setattr__(self, "function", _require_id(self.function))
        object.__setattr__(self, "context_key", _require_id(self.context_key))
        object.__setattr__(
            self,
            "occupant_ids",
            _ordered_unique(self.occupant_ids, "organization_invalid_member"),
        )
        object.__setattr__(
            self,
            "status",
            _require_enum(
                self.status, OrganizationStatus, "organization_invalid_status"
            ),
        )
        first, last = _require_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        object.__setattr__(
            self,
            "evidence_refs",
            _ordered_unique(self.evidence_refs, "organization_unknown_anchor"),
        )


@dataclass(frozen=True, slots=True)
class OrganizationGoalBelief:
    """One believed shared goal, referencing an objective or owner-local anchor."""

    anchor_kind: OrganizationGoalKind
    anchor_id: str
    status: OrganizationStatus
    first_tick: int
    last_tick: int
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self,
            "anchor_kind",
            _require_enum(
                self.anchor_kind, OrganizationGoalKind, "organization_invalid_status"
            ),
        )
        object.__setattr__(self, "anchor_id", _require_id(self.anchor_id))
        object.__setattr__(
            self,
            "status",
            _require_enum(
                self.status, OrganizationStatus, "organization_invalid_status"
            ),
        )
        first, last = _require_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        object.__setattr__(
            self,
            "evidence_refs",
            _ordered_unique(self.evidence_refs, "organization_unknown_anchor"),
        )


@dataclass(frozen=True, slots=True)
class OrganizationResourceBelief:
    """One believed shared resource reference; never an owned pool."""

    resource_kind: OrganizationResourceKind
    anchor_id: str
    access_belief: str
    first_tick: int
    last_tick: int
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self,
            "resource_kind",
            _require_enum(
                self.resource_kind,
                OrganizationResourceKind,
                "organization_invalid_status",
            ),
        )
        object.__setattr__(self, "anchor_id", _require_id(self.anchor_id))
        object.__setattr__(
            self, "access_belief", _require_reason_token(self.access_belief)
        )
        first, last = _require_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        object.__setattr__(
            self,
            "evidence_refs",
            _ordered_unique(self.evidence_refs, "organization_unknown_anchor"),
        )


@dataclass(frozen=True, slots=True)
class OrganizationProcedureBelief:
    """One believed recognized procedure, referencing owner-local evidence."""

    procedure_kind: OrganizationProcedureKind
    anchor_id: str
    recurrence: int
    status: OrganizationStatus
    first_tick: int
    last_tick: int
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self,
            "procedure_kind",
            _require_enum(
                self.procedure_kind,
                OrganizationProcedureKind,
                "organization_invalid_status",
            ),
        )
        object.__setattr__(self, "anchor_id", _require_id(self.anchor_id))
        object.__setattr__(self, "recurrence", _require_count(self.recurrence))
        object.__setattr__(
            self,
            "status",
            _require_enum(
                self.status, OrganizationStatus, "organization_invalid_status"
            ),
        )
        first, last = _require_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        object.__setattr__(
            self,
            "evidence_refs",
            _ordered_unique(self.evidence_refs, "organization_unknown_anchor"),
        )


@dataclass(frozen=True, slots=True)
class OrganizationRecordBelief:
    """One believed record reference; integrity and custody stay beliefs."""

    record_kind: OrganizationRecordKind
    anchor_id: str
    integrity: float
    custody_belief: str
    first_tick: int
    last_tick: int
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self,
            "record_kind",
            _require_enum(
                self.record_kind, OrganizationRecordKind, "organization_invalid_status"
            ),
        )
        object.__setattr__(self, "anchor_id", _require_id(self.anchor_id))
        object.__setattr__(self, "integrity", _require_unit(self.integrity))
        object.__setattr__(
            self, "custody_belief", _require_reason_token(self.custody_belief)
        )
        first, last = _require_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        object.__setattr__(
            self,
            "evidence_refs",
            _ordered_unique(self.evidence_refs, "organization_unknown_anchor"),
        )


@dataclass(frozen=True, slots=True)
class OrganizationCommitmentBelief:
    """One believed internal commitment reference; never enforced debt."""

    commitment_id: str
    role: OrganizationCommitmentRole
    counterpart_id: str
    commitment_kind: str
    status: OrganizationStatus
    first_tick: int
    last_tick: int
    evidence_refs: tuple[str, ...] = ()
    due_tick: int | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(self, "commitment_id", _require_id(self.commitment_id))
        object.__setattr__(
            self,
            "role",
            _require_enum(
                self.role, OrganizationCommitmentRole, "organization_invalid_status"
            ),
        )
        object.__setattr__(self, "counterpart_id", _require_id(self.counterpart_id))
        object.__setattr__(
            self, "commitment_kind", _require_reason_token(self.commitment_kind)
        )
        object.__setattr__(
            self,
            "status",
            _require_enum(
                self.status, OrganizationStatus, "organization_invalid_status"
            ),
        )
        first, last = _require_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        object.__setattr__(
            self,
            "evidence_refs",
            _ordered_unique(self.evidence_refs, "organization_unknown_anchor"),
        )
        if self.due_tick is not None:
            object.__setattr__(
                self, "due_tick", require_organization_tick(self.due_tick)
            )


@dataclass(frozen=True, slots=True)
class OrganizationIdentityBelief:
    """One believed identity label and stance for the structure."""

    label_token: str | None
    conceptualization: OrganizationConceptualization
    stance: OrganizationIdentityStance
    first_tick: int
    last_tick: int
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(self, "label_token", _require_label_token(self.label_token))
        object.__setattr__(
            self,
            "conceptualization",
            _require_enum(
                self.conceptualization,
                OrganizationConceptualization,
                "organization_invalid_status",
            ),
        )
        object.__setattr__(
            self,
            "stance",
            _require_enum(
                self.stance, OrganizationIdentityStance, "organization_invalid_status"
            ),
        )
        if (
            self.conceptualization is OrganizationConceptualization.NONE
            and self.label_token is not None
        ):
            _fail("organization_forbidden_label")
        if (
            self.conceptualization is OrganizationConceptualization.NAMED_CUSTOM
            and self.label_token is None
        ):
            _fail("organization_forbidden_label")
        first, last = _require_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        object.__setattr__(
            self,
            "evidence_refs",
            _ordered_unique(self.evidence_refs, "organization_unknown_anchor"),
        )


def _anchor_keys(prefix: str, values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(values))


def _window_anchor_ids(values: object) -> tuple[str, ...]:
    return _ordered_unique(values, "organization_unknown_anchor")


@dataclass(frozen=True, slots=True)
class OrganizationWindowRecord:
    """One bounded structural snapshot of a believed organization."""

    window_index: int
    tick: int
    status: OrganizationStatus
    temporal_scope: OrganizationTemporalScope
    member_ids: tuple[str, ...]
    role_anchor_ids: tuple[str, ...]
    goal_anchor_ids: tuple[str, ...]
    resource_anchor_ids: tuple[str, ...]
    procedure_anchor_ids: tuple[str, ...]
    record_anchor_ids: tuple[str, ...]
    commitment_ids: tuple[str, ...]
    structural_signature: str
    evidence_count: int
    identity_token: str | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(self, "window_index", _require_count(self.window_index))
        object.__setattr__(self, "tick", require_organization_tick(self.tick))
        object.__setattr__(
            self,
            "status",
            _require_enum(
                self.status, OrganizationStatus, "organization_invalid_status"
            ),
        )
        object.__setattr__(
            self,
            "temporal_scope",
            _require_enum(
                self.temporal_scope,
                OrganizationTemporalScope,
                "organization_invalid_temporal_scope",
            ),
        )
        for name in (
            "member_ids",
            "role_anchor_ids",
            "goal_anchor_ids",
            "resource_anchor_ids",
            "procedure_anchor_ids",
            "record_anchor_ids",
            "commitment_ids",
        ):
            object.__setattr__(self, name, _window_anchor_ids(getattr(self, name)))
        object.__setattr__(
            self, "structural_signature", _require_hex64(self.structural_signature)
        )
        object.__setattr__(self, "evidence_count", _require_count(self.evidence_count))
        object.__setattr__(
            self, "identity_token", _require_label_token(self.identity_token)
        )


@dataclass(frozen=True, slots=True)
class OrganizationRevisionRecord:
    """One bounded owner-local concept revision receipt."""

    revision_id: str
    kind: OrganizationRevisionKind
    tick: int
    before_digest: str
    after_digest: str
    reason_code: str

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(self, "revision_id", _require_id(self.revision_id))
        object.__setattr__(
            self,
            "kind",
            _require_enum(
                self.kind, OrganizationRevisionKind, "organization_invalid_status"
            ),
        )
        object.__setattr__(self, "tick", require_organization_tick(self.tick))
        object.__setattr__(self, "before_digest", _require_hex64(self.before_digest))
        object.__setattr__(self, "after_digest", _require_hex64(self.after_digest))
        object.__setattr__(self, "reason_code", _require_reason_token(self.reason_code))


@dataclass(frozen=True, slots=True)
class OrganizationLineageRecord:
    """One forward-only owner-local lineage edge."""

    lineage_id: str
    kind: OrganizationLineageKind
    tick: int
    from_ids: tuple[str, ...]
    to_ids: tuple[str, ...]
    evidence_digest: str

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "lineage_id", require_organization_concept_id(self.lineage_id)
        )
        object.__setattr__(
            self,
            "kind",
            _require_enum(
                self.kind, OrganizationLineageKind, "organization_invalid_lineage"
            ),
        )
        object.__setattr__(self, "tick", require_organization_tick(self.tick))
        object.__setattr__(
            self,
            "from_ids",
            require_organization_concept_ids(
                self.from_ids, "organization_invalid_lineage"
            ),
        )
        object.__setattr__(
            self,
            "to_ids",
            require_organization_concept_ids(
                self.to_ids, "organization_invalid_lineage"
            ),
        )
        object.__setattr__(
            self, "evidence_digest", _require_hex64(self.evidence_digest)
        )


def _canonical_value(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, AgentId):
        return value.value
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return {
            name: _canonical_value(getattr(value, name))
            for name in sorted(value.__dataclass_fields__)
        }
    return value


def organization_concept_digest(concept: object) -> str:
    """Return the canonical content digest of one organization concept."""

    payload = json.dumps(
        _canonical_value(concept),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _active_goal_count(concept: OrganizationConcept) -> int:
    return sum(1 for goal in concept.goals if goal.status in _ACTIVE_STATUSES)


def _has_successor(concept: OrganizationConcept) -> bool:
    for record in concept.lineage:
        if concept.organization_id not in record.from_ids:
            continue
        if record.kind in (
            OrganizationLineageKind.SPLIT,
            OrganizationLineageKind.MERGE,
            OrganizationLineageKind.TRANSFORMED,
        ):
            return True
    return False


@dataclass(frozen=True, slots=True)
class OrganizationConcept:
    """One owner's belief about a recurring collective structure."""

    organization_id: str
    owner_id: AgentId
    creation_tick: int
    inception_digest: str
    status: OrganizationStatus
    temporal_scope: OrganizationTemporalScope
    strength: float
    member_evidence_count: int
    structural_channel_count: int
    first_tick: int
    last_tick: int
    members: tuple[OrganizationMemberBelief, ...] = ()
    roles: tuple[OrganizationRoleBelief, ...] = ()
    goals: tuple[OrganizationGoalBelief, ...] = ()
    resources: tuple[OrganizationResourceBelief, ...] = ()
    procedures: tuple[OrganizationProcedureBelief, ...] = ()
    records: tuple[OrganizationRecordBelief, ...] = ()
    commitments: tuple[OrganizationCommitmentBelief, ...] = ()
    identities: tuple[OrganizationIdentityBelief, ...] = ()
    snapshots: tuple[OrganizationWindowRecord, ...] = ()
    revisions: tuple[OrganizationRevisionRecord, ...] = ()
    lineage: tuple[OrganizationLineageRecord, ...] = ()
    predecessor_ids: tuple[str, ...] = ()
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self,
            "organization_id",
            require_organization_concept_id(self.organization_id),
        )
        object.__setattr__(self, "owner_id", _require_owner_id(self.owner_id))
        object.__setattr__(
            self, "creation_tick", require_organization_tick(self.creation_tick)
        )
        object.__setattr__(
            self, "inception_digest", _require_hex64(self.inception_digest)
        )
        object.__setattr__(
            self,
            "status",
            _require_enum(
                self.status, OrganizationStatus, "organization_invalid_status"
            ),
        )
        object.__setattr__(
            self,
            "temporal_scope",
            _require_enum(
                self.temporal_scope,
                OrganizationTemporalScope,
                "organization_invalid_temporal_scope",
            ),
        )
        object.__setattr__(self, "strength", _require_unit(self.strength))
        object.__setattr__(
            self, "member_evidence_count", _require_count(self.member_evidence_count)
        )
        object.__setattr__(
            self,
            "structural_channel_count",
            _require_count(self.structural_channel_count),
        )
        first, last = _require_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)

        caps = {
            "members": _DEFAULT_POLICY.max_members,
            "roles": _DEFAULT_POLICY.max_roles,
            "goals": _DEFAULT_POLICY.max_goals,
            "resources": _DEFAULT_POLICY.max_resources,
            "procedures": _DEFAULT_POLICY.max_procedures,
            "records": _DEFAULT_POLICY.max_records,
            "commitments": _DEFAULT_POLICY.max_commitments,
            "identities": _DEFAULT_POLICY.max_identities,
            "snapshots": _DEFAULT_POLICY.max_snapshots,
            "revisions": _DEFAULT_POLICY.max_revisions,
            "lineage": _DEFAULT_POLICY.max_lineage,
        }
        expected_types = {
            "members": OrganizationMemberBelief,
            "roles": OrganizationRoleBelief,
            "goals": OrganizationGoalBelief,
            "resources": OrganizationResourceBelief,
            "procedures": OrganizationProcedureBelief,
            "records": OrganizationRecordBelief,
            "commitments": OrganizationCommitmentBelief,
            "identities": OrganizationIdentityBelief,
            "snapshots": OrganizationWindowRecord,
            "revisions": OrganizationRevisionRecord,
            "lineage": OrganizationLineageRecord,
        }
        for name, cap in caps.items():
            values = getattr(self, name)
            if not isinstance(values, (list, tuple)):
                _fail("organization_invalid_status")
            items = tuple(values)
            for item in items:
                if type(item) is not expected_types[name]:
                    _fail("organization_invalid_status")
            if len(items) > cap:
                _fail("organization_cap_exceeded")
            object.__setattr__(self, name, items)

        self._validate_members()
        self._validate_aspects()
        object.__setattr__(
            self,
            "predecessor_ids",
            require_organization_concept_ids(
                self.predecessor_ids, "organization_invalid_lineage"
            )
            if self.predecessor_ids
            else (),
        )
        object.__setattr__(self, "notices", self._validate_notices(self.notices))
        self._validate_history()
        self._validate_status()

    def _validate_members(self) -> None:
        seen: set[str] = set()
        previous: str | None = None
        for member in self.members:
            if member.member_id in seen:
                _fail("organization_duplicate_member")
            if previous is not None and member.member_id < previous:
                _fail("organization_duplicate_member")
            seen.add(member.member_id)
            previous = member.member_id

    def _validate_aspects(self) -> None:
        for name, key in (
            ("roles", "office_id"),
            ("goals", "anchor_id"),
            ("resources", "anchor_id"),
            ("procedures", "anchor_id"),
            ("records", "anchor_id"),
            ("commitments", "commitment_id"),
        ):
            seen: set[str] = set()
            previous: str | None = None
            for item in getattr(self, name):
                value = getattr(item, key)
                if value in seen:
                    _fail("organization_unknown_anchor")
                if previous is not None and value < previous:
                    _fail("organization_unknown_anchor")
                seen.add(value)
                previous = value
        previous_label: str | None = None
        for identity in self.identities:
            token = identity.label_token or ""
            if previous_label is not None and token < previous_label:
                _fail("organization_forbidden_label")
            previous_label = token

    @staticmethod
    def _validate_notices(values: object) -> tuple[str, ...]:
        if not isinstance(values, (list, tuple)):
            _fail("organization_invalid_status")
        checked: list[str] = []
        for item in values:
            if type(item) is not str or item not in ORGANIZATION_NOTICE_CODES:
                _fail("organization_invalid_status")
            if item not in checked:
                checked.append(item)
        return tuple(sorted(checked))

    def _validate_history(self) -> None:
        previous_tick = -1
        previous_index = -1
        for snapshot in self.snapshots:
            if snapshot.tick < previous_tick:
                _fail("organization_tick_regression")
            if snapshot.window_index <= previous_index:
                _fail("organization_tick_regression")
            previous_tick = snapshot.tick
            previous_index = snapshot.window_index
        previous_tick = -1
        for revision in self.revisions:
            if revision.tick < previous_tick:
                _fail("organization_tick_regression")
            previous_tick = revision.tick
        previous_tick = -1
        for record in self.lineage:
            if record.tick < previous_tick:
                _fail("organization_tick_regression")
            if self.organization_id not in record.from_ids:
                _fail("organization_invalid_lineage")
            previous_tick = record.tick
        for predecessor in self.predecessor_ids:
            if predecessor == self.organization_id:
                _fail("organization_invalid_lineage")

    def _validate_status(self) -> None:
        active_members = sum(
            1
            for member in self.members
            if member.status is not OrganizationMembershipStatus.FORMER
        )
        disputed_member = any(
            member.status is OrganizationMembershipStatus.DISPUTED
            for member in self.members
        )
        if self.status is OrganizationStatus.RECOGNIZED:
            if active_members < _DEFAULT_POLICY.recognition_min_members:
                _fail("organization_invalid_status")
            if self.structural_channel_count < _DEFAULT_POLICY.recognition_min_channels:
                _fail("organization_invalid_status")
            if disputed_member:
                _fail("organization_invalid_status")
        if self.status is OrganizationStatus.DISPUTED and not disputed_member:
            _fail("organization_invalid_status")
        if self.status is OrganizationStatus.DISSOLVED:
            if _active_goal_count(self) > 0 or _has_successor(self):
                _fail("organization_invalid_status")
        if self.status is OrganizationStatus.RETIRED:
            if _active_goal_count(self) > 0 and not _has_successor(self):
                _fail("organization_invalid_status")
        if self.structural_channel_count > 7:
            _fail("organization_invalid_status")

    @property
    def active(self) -> bool:
        return self.status in _ACTIVE_STATUSES

    @property
    def member_ids(self) -> tuple[str, ...]:
        return tuple(member.member_id for member in self.members)

    def as_window(self, window_index: int) -> OrganizationWindowRecord:
        """Project this concept into one bounded structural window record."""

        return OrganizationWindowRecord(
            window_index=window_index,
            tick=self.last_tick,
            status=self.status,
            temporal_scope=self.temporal_scope,
            member_ids=self.member_ids,
            role_anchor_ids=_anchor_keys(
                "role", tuple(role.office_id for role in self.roles)
            ),
            goal_anchor_ids=_anchor_keys(
                "goal", tuple(goal.anchor_id for goal in self.goals)
            ),
            resource_anchor_ids=_anchor_keys(
                "resource", tuple(item.anchor_id for item in self.resources)
            ),
            procedure_anchor_ids=_anchor_keys(
                "procedure", tuple(item.anchor_id for item in self.procedures)
            ),
            record_anchor_ids=_anchor_keys(
                "record", tuple(item.anchor_id for item in self.records)
            ),
            commitment_ids=_anchor_keys(
                "commitment", tuple(item.commitment_id for item in self.commitments)
            ),
            identity_token=next(
                (item.label_token for item in self.identities if item.label_token),
                None,
            ),
            structural_signature=organization_concept_digest(
                (
                    self.organization_id,
                    self.member_ids,
                    tuple(goal.anchor_id for goal in self.goals),
                    tuple(role.office_id for role in self.roles),
                )
            ),
            evidence_count=self.member_evidence_count,
        )


@dataclass(frozen=True, slots=True)
class OrganizationConceptLedger:
    """One owner's organization beliefs. ``None`` means the mode is off."""

    owner_id: AgentId
    concepts: tuple[OrganizationConcept, ...] = ()
    lineage: tuple[OrganizationLineageRecord, ...] = ()
    notices: tuple[str, ...] = ()
    policy_version: str = ORGANIZATION_CONCEPT_POLICY_VERSION

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(self, "owner_id", _require_owner_id(self.owner_id))
        if self.policy_version != ORGANIZATION_CONCEPT_POLICY_VERSION:
            _fail("organization_policy_mismatch")
        if not isinstance(self.concepts, (list, tuple)):
            _fail("organization_invalid_status")
        concepts = tuple(self.concepts)
        seen: set[str] = set()
        previous: str | None = None
        for concept in concepts:
            if type(concept) is not OrganizationConcept:
                _fail("organization_invalid_status")
            if concept.owner_id != self.owner_id:
                _fail("organization_foreign_ledger")
            if concept.organization_id in seen:
                _fail("organization_invalid_status")
            if previous is not None and concept.organization_id < previous:
                _fail("organization_invalid_status")
            seen.add(concept.organization_id)
            previous = concept.organization_id
        if len(concepts) > _DEFAULT_POLICY.max_concepts:
            _fail("organization_cap_exceeded")
        for concept in concepts:
            for predecessor in concept.predecessor_ids:
                if predecessor not in seen:
                    _fail("organization_invalid_lineage")
        if not isinstance(self.lineage, (list, tuple)):
            _fail("organization_invalid_status")
        lineage = tuple(self.lineage)
        if len(lineage) > _DEFAULT_POLICY.max_lineage:
            _fail("organization_cap_exceeded")
        previous_tick = -1
        for record in lineage:
            if type(record) is not OrganizationLineageRecord:
                _fail("organization_invalid_lineage")
            if record.tick < previous_tick:
                _fail("organization_tick_regression")
            for endpoint in (*record.from_ids, *record.to_ids):
                if endpoint not in seen:
                    _fail("organization_invalid_lineage")
            previous_tick = record.tick
        _ensure_acyclic(lineage)
        object.__setattr__(self, "concepts", concepts)
        object.__setattr__(self, "lineage", lineage)
        object.__setattr__(
            self,
            "notices",
            OrganizationConcept._validate_notices(self.notices),
        )
        _LOG.debug(
            "organization_concept_ledger_constructed owner_id=%s concept_count=%s "
            "lineage_count=%s policy_version=%s",
            self.owner_id.value,
            len(self.concepts),
            len(self.lineage),
            self.policy_version,
        )


def _ensure_acyclic(lineage: Sequence[OrganizationLineageRecord]) -> None:
    edges: dict[str, set[str]] = {}
    for record in lineage:
        for source in record.from_ids:
            for target in record.to_ids:
                if source == target:
                    continue
                edges.setdefault(source, set()).add(target)
    visiting: set[str] = set()
    settled: set[str] = set()

    def visit(node: str) -> None:
        if node in settled:
            return
        if node in visiting:
            _fail("organization_lineage_cycle")
        visiting.add(node)
        for target in sorted(edges.get(node, ())):
            visit(target)
        visiting.discard(node)
        settled.add(node)

    for node in sorted(edges):
        visit(node)


def empty_organization_concept_ledger(
    owner_id: AgentId,
    policy: OrganizationConceptPolicy | None = None,
) -> OrganizationConceptLedger:
    """Return an enabled-but-empty ledger for one owner."""

    if policy is not None and type(policy) is not OrganizationConceptPolicy:
        _fail("organization_policy_mismatch")
    return OrganizationConceptLedger(owner_id=owner_id)


def require_owner_organization_concepts(
    ledger: object,
    owner_id: AgentId,
    *,
    field_name: str,
) -> None:
    """Reject a foreign or mistyped organization ledger. ``None`` passes."""

    if ledger is None:
        return
    if type(owner_id) is not AgentId:
        _fail("organization_invalid_owner")
    if type(ledger) is not OrganizationConceptLedger:
        _LOG.warning("organization_carry_rejected reason=%s", "invalid_type")
        raise TypeError(f"{field_name} must be OrganizationConceptLedger")
    if ledger.owner_id != owner_id:
        _LOG.error(
            "organization_concept_validation_failed field=%s reason_code=%s",
            field_name,
            "owner_mismatch",
        )
        raise OrganizationConceptError("organization_foreign_ledger")


# ---------------------------------------------------------------------------
# Deterministic owner-local formation
# ---------------------------------------------------------------------------

_FORBIDDEN_INPUT_SYMBOLS: Final[tuple[str, ...]] = (
    "WorldState",
    "WorldEvent",
    "PhysicalRules",
    "AgentBody",
    "WorldEngine",
    "ActionSubmission",
    "AgentCommand",
    "MetricDocument",
)

_MEMBER_STATUS_PRECEDENCE: Final[Mapping[OrganizationMembershipStatus, int]] = (
    MappingProxyType(
        {
            OrganizationMembershipStatus.UNKNOWN: 1,
            OrganizationMembershipStatus.PERCEIVED: 2,
            OrganizationMembershipStatus.FORMER: 3,
            OrganizationMembershipStatus.EXPLICIT: 4,
            OrganizationMembershipStatus.DISPUTED: 5,
        }
    )
)

_BASIS_STRENGTH: Final[Mapping[OrganizationMembershipBasis, float]] = MappingProxyType(
    {
        OrganizationMembershipBasis.SELF_IDENTIFICATION: 0.9,
        OrganizationMembershipBasis.PARTICIPATION: 0.5,
        OrganizationMembershipBasis.ROLE_OCCUPANCY: 0.6,
        OrganizationMembershipBasis.COLLECTIVE_PARTICIPATION: 0.5,
        OrganizationMembershipBasis.COMMUNICATED_CLAIM: 0.4,
        OrganizationMembershipBasis.RECORD_REFERENCE: 0.4,
        OrganizationMembershipBasis.INFERENCE: 0.2,
    }
)

_OFFICE_STATUS_MAP: Final[Mapping[str, OrganizationStatus]] = MappingProxyType(
    {
        "proposed": OrganizationStatus.CANDIDATE,
        "recognized": OrganizationStatus.RECOGNIZED,
        "contested": OrganizationStatus.DISPUTED,
        "vacant": OrganizationStatus.CANDIDATE,
        "retired": OrganizationStatus.RETIRED,
    }
)

_INSTITUTION_STATUS_MAP: Final[Mapping[str, OrganizationStatus]] = MappingProxyType(
    {
        "emerging": OrganizationStatus.CANDIDATE,
        "recognized": OrganizationStatus.RECOGNIZED,
        "contested": OrganizationStatus.DISPUTED,
        "decayed": OrganizationStatus.DISSOLVED,
        "retired": OrganizationStatus.RETIRED,
        "dissolved": OrganizationStatus.DISSOLVED,
    }
)

_ACTIVE_GROUP_STANCES: Final[frozenset[str]] = frozenset({"we", "our_group"})


@dataclass(slots=True)
class _MemberAccumulator:
    member_id: str
    status: OrganizationMembershipStatus
    basis: OrganizationMembershipBasis
    scope: OrganizationTemporalScope
    expires_tick: int | None
    strength: float
    first_tick: int
    last_tick: int
    channels: set[OrganizationEvidenceChannel] = field(default_factory=set)
    evidence_refs: set[str] = field(default_factory=set)
    independently_evidenced: bool = False


@dataclass(slots=True)
class _EvidenceBundle:
    members: dict[str, _MemberAccumulator] = field(default_factory=dict)
    roles: dict[str, OrganizationRoleBelief] = field(default_factory=dict)
    goals: dict[str, OrganizationGoalBelief] = field(default_factory=dict)
    resources: dict[str, OrganizationResourceBelief] = field(default_factory=dict)
    procedures: dict[str, OrganizationProcedureBelief] = field(default_factory=dict)
    records: dict[str, OrganizationRecordBelief] = field(default_factory=dict)
    commitments: dict[str, OrganizationCommitmentBelief] = field(default_factory=dict)
    identities: dict[str, OrganizationIdentityBelief] = field(default_factory=dict)
    notices: set[str] = field(default_factory=set)

    @property
    def empty(self) -> bool:
        return not (
            self.members
            or self.roles
            or self.goals
            or self.resources
            or self.procedures
            or self.records
            or self.commitments
            or self.identities
        )


def _quantized(value: float) -> float:
    clamped = 0.0 if value < 0.0 else (1.0 if value > 1.0 else value)
    return float(Decimal(str(clamped)).quantize(_QUANTUM, rounding=ROUND_HALF_UP))


def _sort_token(value: object) -> str:
    token = getattr(value, "value", value)
    return token if type(token) is str else ""


def _evidence_ref(source: str, ref: str) -> str:
    payload = f"organization-evidence.v1|{source}|{ref}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _add_member(
    bundle: _EvidenceBundle,
    *,
    member_id: object,
    status: OrganizationMembershipStatus,
    basis: OrganizationMembershipBasis,
    channel: OrganizationEvidenceChannel,
    tick: int,
    source: str,
    ref: str,
    independent: bool,
    scope: OrganizationTemporalScope = OrganizationTemporalScope.ONGOING,
    expires_tick: int | None = None,
) -> None:
    value = getattr(member_id, "value", member_id)
    if type(value) is not str or not value:
        return
    evidence_id = _evidence_ref(source, ref)
    strength = _BASIS_STRENGTH[basis]
    current = bundle.members.get(value)
    if current is None:
        bundle.members[value] = _MemberAccumulator(
            member_id=value,
            status=status,
            basis=basis,
            scope=scope,
            expires_tick=expires_tick,
            strength=strength,
            first_tick=tick,
            last_tick=tick,
            channels={channel},
            evidence_refs={evidence_id},
            independently_evidenced=independent,
        )
        return
    if _MEMBER_STATUS_PRECEDENCE[status] >= _MEMBER_STATUS_PRECEDENCE[current.status]:
        current.status = status
        current.basis = basis
    current.last_tick = tick
    current.channels.add(channel)
    current.evidence_refs.add(evidence_id)
    current.strength = _quantized(max(current.strength, strength))
    current.independently_evidenced = current.independently_evidenced or independent
    if scope is OrganizationTemporalScope.TEMPORARY:
        current.scope = scope
        current.expires_tick = expires_tick


def _map_office_status(value: object) -> OrganizationStatus:
    token = getattr(value, "value", value)
    if type(token) is not str:
        return OrganizationStatus.CANDIDATE
    return _OFFICE_STATUS_MAP.get(token, OrganizationStatus.CANDIDATE)


def _map_institution_status(value: object) -> OrganizationStatus:
    token = getattr(value, "value", value)
    if type(token) is not str:
        return OrganizationStatus.CANDIDATE
    return _INSTITUTION_STATUS_MAP.get(token, OrganizationStatus.CANDIDATE)


def _collect_group_membership(
    bundle: _EvidenceBundle, ledger: object, tick: int
) -> None:
    for belief in sorted(
        getattr(ledger, "beliefs", ()), key=lambda item: getattr(item, "belief_id", "")
    ):
        stance = getattr(getattr(belief, "stance", None), "value", None)
        status = getattr(getattr(belief, "status", None), "value", None)
        if stance not in _ACTIVE_GROUP_STANCES or status != "active":
            continue
        for member_id in getattr(belief, "member_ids", ()):
            _add_member(
                bundle,
                member_id=member_id,
                status=OrganizationMembershipStatus.PERCEIVED,
                basis=OrganizationMembershipBasis.PARTICIPATION,
                channel=OrganizationEvidenceChannel.OBSERVED,
                tick=tick,
                source="group",
                ref=str(getattr(belief, "belief_id", "")),
                independent=bool(getattr(belief, "social_evidence", False)),
            )


def _collect_offices(bundle: _EvidenceBundle, ledger: object, tick: int) -> None:
    for office in sorted(
        getattr(ledger, "concepts", ()), key=lambda item: getattr(item, "office_id", "")
    ):
        status = _map_office_status(getattr(office, "status", None))
        if status is OrganizationStatus.RETIRED:
            continue
        office_id = str(getattr(office, "office_id", ""))
        function = getattr(office, "function", None)
        function_token = getattr(function, "value", "unknown")
        occupants = tuple(
            getattr(claim, "occupant_id", None)
            for claim in getattr(office, "occupants", ())
            if getattr(getattr(claim, "status", None), "value", "vacant") != "vacant"
        )
        occupant_ids = tuple(
            sorted({item.value for item in occupants if item is not None})
        )
        bundle.roles[office_id] = OrganizationRoleBelief(
            office_id=office_id,
            function=str(function_token),
            context_key=str(getattr(office, "context_key", office_id)),
            occupant_ids=occupant_ids,
            status=status,
            first_tick=require_organization_tick(getattr(office, "first_tick", tick)),
            last_tick=tick,
        )
        for occupant in occupant_ids:
            _add_member(
                bundle,
                member_id=occupant,
                status=OrganizationMembershipStatus.PERCEIVED,
                basis=OrganizationMembershipBasis.ROLE_OCCUPANCY,
                channel=OrganizationEvidenceChannel.OBSERVED,
                tick=tick,
                source="office",
                ref=office_id,
                independent=True,
            )


def _collect_institutions(bundle: _EvidenceBundle, ledger: object, tick: int) -> None:
    for concept in sorted(
        getattr(ledger, "concepts", ()),
        key=lambda item: getattr(item, "concept_id", ""),
    ):
        recurrence = float(getattr(concept, "procedure_recurrence", 0.0))
        concept_id = str(getattr(concept, "concept_id", ""))
        label = getattr(concept, "label_token", None)
        if label and not bundle.identities:
            try:
                bundle.identities["institution"] = OrganizationIdentityBelief(
                    label_token=label,
                    conceptualization=OrganizationConceptualization.NAMED_USUAL,
                    stance=OrganizationIdentityStance.UNKNOWN,
                    first_tick=tick,
                    last_tick=tick,
                )
            except OrganizationConceptError:
                bundle.notices.add("unresolved_anchor")
        if recurrence <= 0.0:
            continue
        bundle.procedures[concept_id] = OrganizationProcedureBelief(
            procedure_kind=OrganizationProcedureKind.INSTITUTION_CONCEPT,
            anchor_id=concept_id,
            recurrence=max(1, round(recurrence * 10)),
            status=_map_institution_status(getattr(concept, "status", None)),
            first_tick=require_organization_tick(getattr(concept, "first_tick", tick)),
            last_tick=tick,
        )


def _collect_conventions(bundle: _EvidenceBundle, ledger: object, tick: int) -> None:
    for belief in sorted(
        getattr(ledger, "beliefs", ()), key=lambda item: getattr(item, "belief_id", "")
    ):
        belief_id = str(getattr(belief, "belief_id", ""))
        repetition = int(getattr(belief, "repetition_count", 0))
        bundle.procedures[f"convention:{belief_id}"] = OrganizationProcedureBelief(
            procedure_kind=OrganizationProcedureKind.SOCIAL_CONVENTION,
            anchor_id=belief_id,
            recurrence=max(1, repetition),
            status=OrganizationStatus.RECOGNIZED,
            first_tick=require_organization_tick(
                getattr(belief, "first_tick", None) or tick
            ),
            last_tick=tick,
        )


def _collect_decisions(bundle: _EvidenceBundle, ledger: object, tick: int) -> None:
    for proposal in sorted(
        getattr(ledger, "proposals", ()),
        key=lambda item: getattr(item, "proposal_id", ""),
    ):
        status = getattr(getattr(proposal, "status", None), "value", None)
        if status != "active":
            continue
        anchor_id = str(getattr(proposal, "proposal_ref", ""))
        bundle.goals[anchor_id] = OrganizationGoalBelief(
            anchor_kind=OrganizationGoalKind.COLLECTIVE_PROJECT,
            anchor_id=anchor_id,
            status=OrganizationStatus.CANDIDATE,
            first_tick=require_organization_tick(getattr(proposal, "first_tick", tick)),
            last_tick=tick,
        )
    for position in sorted(
        getattr(ledger, "positions", ()),
        key=lambda item: getattr(item, "position_id", ""),
    ):
        if not bool(getattr(position, "active", True)):
            continue
        actor_id = getattr(position, "actor_id", None)
        _add_member(
            bundle,
            member_id=actor_id,
            status=OrganizationMembershipStatus.PERCEIVED,
            basis=OrganizationMembershipBasis.COLLECTIVE_PARTICIPATION,
            channel=OrganizationEvidenceChannel.OBSERVED,
            tick=tick,
            source="collective",
            ref=str(getattr(position, "position_id", "")),
            independent=bool(getattr(position, "independently_evidenced", False)),
        )


def _collect_commitments(
    bundle: _EvidenceBundle, ledger: object, owner_id: AgentId, tick: int
) -> None:
    for interpretation in sorted(
        getattr(ledger, "interpretations", ()),
        key=lambda item: int(getattr(item, "local_id", 0)),
    ):
        status_token = getattr(interpretation, "status", "open")
        if status_token in {"fulfilled", "withdrawn", "void"}:
            continue
        local_id = int(getattr(interpretation, "local_id", 0))
        commitment_id = f"commitment-{local_id}"
        debtor = str(getattr(interpretation, "debtor_id", ""))
        creditor = str(getattr(interpretation, "creditor_id", ""))
        role = (
            OrganizationCommitmentRole.DEBTOR
            if debtor == owner_id.value
            else OrganizationCommitmentRole.CREDITOR
        )
        counterpart = creditor if role is OrganizationCommitmentRole.DEBTOR else debtor
        due_tick = getattr(interpretation, "due_tick", None)
        bundle.commitments[commitment_id] = OrganizationCommitmentBelief(
            commitment_id=commitment_id,
            role=role,
            counterpart_id=counterpart or "unknown",
            commitment_kind=str(getattr(interpretation, "kind", "unspecified"))[:32]
            or "unspecified",
            status=OrganizationStatus.CANDIDATE,
            first_tick=require_organization_tick(
                getattr(interpretation, "created_tick", tick)
            ),
            last_tick=tick,
            due_tick=None if due_tick is None else int(due_tick),
        )
        _add_member(
            bundle,
            member_id=counterpart,
            status=OrganizationMembershipStatus.UNKNOWN,
            basis=OrganizationMembershipBasis.INFERENCE,
            channel=OrganizationEvidenceChannel.OBSERVED,
            tick=tick,
            source="commitment",
            ref=commitment_id,
            independent=False,
        )


def _collect_observation(
    bundle: _EvidenceBundle, observation: object, tick: int
) -> None:
    observer_id = getattr(observation, "observer_id", None)
    for project in sorted(
        getattr(observation, "collective_projects", ()),
        key=lambda item: _sort_token(getattr(item, "project_id", None)),
    ):
        project_id = getattr(project, "project_id", None)
        if project_id is None:
            continue
        bundle.goals[project_id.value] = OrganizationGoalBelief(
            anchor_kind=OrganizationGoalKind.COLLECTIVE_PROJECT,
            anchor_id=project_id.value,
            status=OrganizationStatus.RECOGNIZED,
            first_tick=tick,
            last_tick=tick,
        )
        for contribution in getattr(project, "contributions", ()):
            _add_member(
                bundle,
                member_id=getattr(contribution, "actor_id", None),
                status=OrganizationMembershipStatus.PERCEIVED,
                basis=OrganizationMembershipBasis.PARTICIPATION,
                channel=OrganizationEvidenceChannel.OBSERVED,
                tick=tick,
                source="project",
                ref=project_id.value,
                independent=bool(getattr(contribution, "accepted", False)),
            )
    for repository in sorted(
        getattr(observation, "repositories", ()),
        key=lambda item: _sort_token(getattr(item, "repository_id", None)),
    ):
        repository_id = getattr(repository, "repository_id", None)
        if repository_id is None:
            continue
        bundle.resources[repository_id.value] = OrganizationResourceBelief(
            resource_kind=OrganizationResourceKind.REPOSITORY,
            anchor_id=repository_id.value,
            access_belief="observed",
            first_tick=tick,
            last_tick=tick,
        )
    for artifact in sorted(
        getattr(observation, "artifacts", ()),
        key=lambda item: _sort_token(getattr(item, "entity_id", None)),
    ):
        artifact_id = getattr(artifact, "entity_id", None)
        if artifact_id is None:
            continue
        integrity_value = getattr(artifact, "integrity", None)
        integrity = 0.5
        token = getattr(integrity_value, "value", None)
        if token in {"intact", "complete", "sound"}:
            integrity = 1.0
        elif token in {"damaged", "partial", "fragmentary"}:
            integrity = 0.25
        bundle.records[artifact_id.value] = OrganizationRecordBelief(
            record_kind=OrganizationRecordKind.ARTIFACT,
            anchor_id=artifact_id.value,
            integrity=_quantized(integrity),
            custody_belief="observed",
            first_tick=tick,
            last_tick=tick,
        )
    for body in sorted(
        getattr(observation, "visible_bodies", ()),
        key=lambda item: _sort_token(getattr(item, "entity_id", None)),
    ):
        entity_id = getattr(body, "entity_id", None)
        if entity_id is None or entity_id == observer_id:
            continue
        _add_member(
            bundle,
            member_id=entity_id,
            status=OrganizationMembershipStatus.PERCEIVED,
            basis=OrganizationMembershipBasis.INFERENCE,
            channel=OrganizationEvidenceChannel.OBSERVED,
            tick=tick,
            source="copresence",
            ref=entity_id.value,
            independent=False,
        )
    _collect_claims(bundle, observation, tick)


def _collect_claims(bundle: _EvidenceBundle, observation: object, tick: int) -> None:
    from agents.cognition.organization_communication import (
        parse_organization_claim_relation,
    )

    observer_id = getattr(observation, "observer_id", None)
    for communication in sorted(
        getattr(observation, "communications", ()),
        key=lambda item: _sort_token(
            getattr(getattr(item, "provenance", None), "source_event_id", None)
        ),
    ):
        if getattr(communication, "listener_id", None) != observer_id:
            continue
        content = getattr(getattr(communication, "utterance", None), "content", None)
        if content is None:
            continue
        speaker = getattr(communication, "speaker_id", None)
        speaker_id = getattr(speaker, "value", "")
        for relation in getattr(content, "relations", ()):
            claim = parse_organization_claim_relation(relation)
            if claim is None:
                continue
            authored = speaker == observer_id
            if claim.predicate == "organization_leave":
                status = OrganizationMembershipStatus.FORMER
            elif claim.predicate == "organization_dispute":
                status = OrganizationMembershipStatus.DISPUTED
            elif authored:
                status = OrganizationMembershipStatus.EXPLICIT
            else:
                status = OrganizationMembershipStatus.PERCEIVED
            scope = (
                OrganizationTemporalScope.TEMPORARY
                if claim.expires_tick is not None
                else OrganizationTemporalScope.ONGOING
            )
            _add_member(
                bundle,
                member_id=speaker_id,
                status=status,
                basis=(
                    OrganizationMembershipBasis.SELF_IDENTIFICATION
                    if authored
                    else OrganizationMembershipBasis.COMMUNICATED_CLAIM
                ),
                channel=OrganizationEvidenceChannel.COMMUNICATED,
                tick=tick,
                source="claim",
                ref=speaker_id,
                independent=not authored,
                scope=scope,
                expires_tick=claim.expires_tick,
            )
            if claim.label_token is not None:
                bundle.identities["claim"] = OrganizationIdentityBelief(
                    label_token=claim.label_token,
                    conceptualization=OrganizationConceptualization.NAMED_CUSTOM,
                    stance=claim.stance,
                    first_tick=tick,
                    last_tick=tick,
                )


def _collect_evidence(
    *,
    owner_id: AgentId,
    tick: int,
    observation: object,
    institution_concepts: object | None,
    offices: object | None,
    group_formation: object | None,
    collective_decisions: object | None,
    structured_commitments: object | None,
    social_conventions: object | None,
) -> _EvidenceBundle:
    bundle = _EvidenceBundle()
    if group_formation is None:
        bundle.notices.add("membership_conflict")
    else:
        _collect_group_membership(bundle, group_formation, tick)
    if offices is None:
        bundle.notices.add("missing_office")
    else:
        _collect_offices(bundle, offices, tick)
    if institution_concepts is None:
        bundle.notices.add("missing_institution")
    else:
        _collect_institutions(bundle, institution_concepts, tick)
    if social_conventions is not None:
        _collect_conventions(bundle, social_conventions, tick)
    if collective_decisions is not None:
        _collect_decisions(bundle, collective_decisions, tick)
    if structured_commitments is not None:
        _collect_commitments(bundle, structured_commitments, owner_id, tick)
    if observation is not None:
        _collect_observation(bundle, observation, tick)
    return bundle


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _concept_member_ids(concept: OrganizationConcept) -> set[str]:
    return {
        member.member_id
        for member in concept.members
        if member.status is not OrganizationMembershipStatus.FORMER
    }


def _concept_anchor_ids(concept: OrganizationConcept) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                *(role.office_id for role in concept.roles),
                *(goal.anchor_id for goal in concept.goals),
                *(item.anchor_id for item in concept.resources),
                *(item.anchor_id for item in concept.procedures),
                *(item.anchor_id for item in concept.records),
            }
        )
    )


def _bundle_member_ids(bundle: _EvidenceBundle) -> set[str]:
    return {
        member_id
        for member_id, item in bundle.members.items()
        if item.status is not OrganizationMembershipStatus.FORMER
    }


def _matches(
    concept: OrganizationConcept, bundle: _EvidenceBundle, policy: object
) -> bool:
    concept_members = _concept_member_ids(concept)
    new_members = _bundle_member_ids(bundle)
    if not concept_members or not new_members:
        return False
    overlap = _jaccard(concept_members, new_members)
    merge_jaccard = float(getattr(policy, "merge_jaccard", 0.5))
    if overlap >= merge_jaccard:
        return True
    shared_roles = set(bundle.roles) & {role.office_id for role in concept.roles}
    if shared_roles:
        return True
    shared_goals = set(bundle.goals) & {goal.anchor_id for goal in concept.goals}
    if shared_goals:
        return True
    shared_procedures = {item.anchor_id for item in bundle.procedures.values()} & {
        item.anchor_id for item in concept.procedures
    }
    if shared_procedures:
        return True
    labels = {
        item.label_token for item in bundle.identities.values() if item.label_token
    }
    concept_labels = {
        item.label_token for item in concept.identities if item.label_token
    }
    if labels & concept_labels and bool(concept_members & new_members):
        return True
    return False


def _accumulate_prior(bundle: _EvidenceBundle, concept: OrganizationConcept) -> None:
    for member in concept.members:
        bundle.members[member.member_id] = _MemberAccumulator(
            member_id=member.member_id,
            status=member.status,
            basis=member.basis,
            scope=member.temporal_scope,
            expires_tick=member.expires_tick,
            strength=member.strength,
            first_tick=member.first_tick,
            last_tick=member.last_tick,
            channels=set(member.channels),
            evidence_refs=set(member.evidence_refs),
            independently_evidenced=member.independently_evidenced,
        )
    for role in concept.roles:
        bundle.roles[role.office_id] = role
    for goal in concept.goals:
        bundle.goals[goal.anchor_id] = goal
    for resource in concept.resources:
        bundle.resources[resource.anchor_id] = resource
    for procedure in concept.procedures:
        bundle.procedures[f"{procedure.procedure_kind.value}:{procedure.anchor_id}"] = (
            procedure
        )
    for record in concept.records:
        bundle.records[record.anchor_id] = record
    for commitment in concept.commitments:
        bundle.commitments[commitment.commitment_id] = commitment
    for index, identity in enumerate(concept.identities):
        bundle.identities[f"prior:{index}"] = identity


def _merge_aspects(target: dict[str, Any], extra: dict[str, Any]) -> None:
    for key, incoming in extra.items():
        existing = target.get(key)
        if existing is None:
            target[key] = incoming
            continue
        target[key] = replace(
            incoming, first_tick=min(existing.first_tick, incoming.first_tick)
        )


def _accumulate_new(bundle: _EvidenceBundle, extra: _EvidenceBundle) -> None:
    for member_id, item in extra.members.items():
        current = bundle.members.get(member_id)
        if current is None:
            bundle.members[member_id] = item
            continue
        if (
            _MEMBER_STATUS_PRECEDENCE[item.status]
            >= _MEMBER_STATUS_PRECEDENCE[current.status]
        ):
            current.status = item.status
            current.basis = item.basis
        current.first_tick = min(current.first_tick, item.first_tick)
        current.last_tick = max(current.last_tick, item.last_tick)
        current.strength = _quantized(max(current.strength, item.strength))
        current.channels |= item.channels
        current.evidence_refs |= item.evidence_refs
        current.independently_evidenced = (
            current.independently_evidenced or item.independently_evidenced
        )
        if item.scope is OrganizationTemporalScope.TEMPORARY:
            current.scope = item.scope
            current.expires_tick = item.expires_tick
        else:
            current.scope = OrganizationTemporalScope.ONGOING
            current.expires_tick = None
    _merge_aspects(bundle.roles, extra.roles)
    _merge_aspects(bundle.goals, extra.goals)
    _merge_aspects(bundle.resources, extra.resources)
    _merge_aspects(bundle.procedures, extra.procedures)
    _merge_aspects(bundle.records, extra.records)
    _merge_aspects(bundle.commitments, extra.commitments)
    bundle.identities.update(extra.identities)
    bundle.notices |= extra.notices


def _member_record(
    accumulator: _MemberAccumulator, tick: int
) -> OrganizationMemberBelief:
    first = min(accumulator.first_tick, tick)
    last = max(accumulator.last_tick, tick)
    expires = accumulator.expires_tick
    if expires is not None and expires < first:
        expires = first
    return OrganizationMemberBelief(
        member_id=accumulator.member_id,
        status=accumulator.status,
        basis=accumulator.basis,
        temporal_scope=accumulator.scope,
        first_tick=first,
        last_tick=last,
        strength=_quantized(accumulator.strength),
        channels=tuple(sorted(accumulator.channels, key=lambda item: item.value)),
        independently_evidenced=accumulator.independently_evidenced,
        evidence_refs=tuple(sorted(accumulator.evidence_refs)),
        expires_tick=expires,
    )


def _aspect_records(
    bundle: _EvidenceBundle, tick: int
) -> tuple[
    tuple[OrganizationMemberBelief, ...],
    tuple[OrganizationRoleBelief, ...],
    tuple[OrganizationGoalBelief, ...],
    tuple[OrganizationResourceBelief, ...],
    tuple[OrganizationProcedureBelief, ...],
    tuple[OrganizationRecordBelief, ...],
    tuple[OrganizationCommitmentBelief, ...],
    tuple[OrganizationIdentityBelief, ...],
]:
    members = tuple(
        _member_record(bundle.members[key], tick) for key in sorted(bundle.members)
    )
    roles = tuple(bundle.roles[key] for key in sorted(bundle.roles))
    goals = tuple(bundle.goals[key] for key in sorted(bundle.goals))
    resources = tuple(bundle.resources[key] for key in sorted(bundle.resources))
    procedures = tuple(bundle.procedures[key] for key in sorted(bundle.procedures))
    records = tuple(bundle.records[key] for key in sorted(bundle.records))
    commitments = tuple(bundle.commitments[key] for key in sorted(bundle.commitments))
    by_identity: dict[tuple[str, str, str], OrganizationIdentityBelief] = {}
    for key in sorted(bundle.identities):
        identity = bundle.identities[key]
        identity_key = (
            identity.conceptualization.value,
            identity.stance.value,
            identity.label_token or "",
        )
        existing = by_identity.get(identity_key)
        if existing is None or identity.first_tick < existing.first_tick:
            by_identity[identity_key] = identity
    identities = tuple(by_identity[key] for key in sorted(by_identity))
    return (
        members,
        roles,
        goals,
        resources,
        procedures,
        records,
        commitments,
        identities,
    )


def _structural_channel_count(
    roles: tuple[OrganizationRoleBelief, ...],
    goals: tuple[OrganizationGoalBelief, ...],
    resources: tuple[OrganizationResourceBelief, ...],
    procedures: tuple[OrganizationProcedureBelief, ...],
    records: tuple[OrganizationRecordBelief, ...],
    commitments: tuple[OrganizationCommitmentBelief, ...],
    identities: tuple[OrganizationIdentityBelief, ...],
) -> int:
    return sum(
        1
        for family in (
            roles,
            goals,
            resources,
            procedures,
            records,
            commitments,
            identities,
        )
        if family
    )


def _derive_status(
    *,
    members: tuple[OrganizationMemberBelief, ...],
    structural_channels: int,
    member_evidence_count: int,
    strength: float,
    policy: OrganizationConceptPolicy,
) -> OrganizationStatus:
    active = [
        member
        for member in members
        if member.status is not OrganizationMembershipStatus.FORMER
    ]
    disputed = any(
        member.status is OrganizationMembershipStatus.DISPUTED for member in members
    )
    if disputed:
        return OrganizationStatus.DISPUTED
    if (
        len(active) >= policy.recognition_min_members
        and structural_channels >= policy.recognition_min_channels
        and member_evidence_count >= policy.recognition_min_evidence
        and strength >= policy.recognition_floor
    ):
        return OrganizationStatus.RECOGNIZED
    return OrganizationStatus.CANDIDATE


def _member_content(member: OrganizationMemberBelief) -> object:
    return {
        "member_id": member.member_id,
        "status": member.status.value,
        "basis": member.basis.value,
        "temporal_scope": member.temporal_scope.value,
        "expires_tick": member.expires_tick,
        "strength": member.strength,
        "channels": [channel.value for channel in member.channels],
        "independently_evidenced": member.independently_evidenced,
    }


def _aspect_content(item: object) -> object:
    fields = getattr(item, "__dataclass_fields__", {})
    return {
        name: _canonical_value(getattr(item, name))
        for name in sorted(fields)
        if name not in {"last_tick", "evidence_refs"}
    }


def _revision_id(organization_id: str, tick: int) -> str:
    payload = f"organization-revision.v1|{organization_id}|{tick}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _content_payload(concept: OrganizationConcept) -> object:
    return {
        "organization_id": concept.organization_id,
        "creation_tick": concept.creation_tick,
        "status": concept.status.value,
        "temporal_scope": concept.temporal_scope.value,
        "members": [_member_content(member) for member in concept.members],
        "roles": [_aspect_content(item) for item in concept.roles],
        "goals": [_aspect_content(item) for item in concept.goals],
        "resources": [_aspect_content(item) for item in concept.resources],
        "procedures": [_aspect_content(item) for item in concept.procedures],
        "records": [_aspect_content(item) for item in concept.records],
        "commitments": [_aspect_content(item) for item in concept.commitments],
        "identities": [_aspect_content(item) for item in concept.identities],
    }


def _content_digest(concept: OrganizationConcept) -> str:
    payload = json.dumps(
        _content_payload(concept),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _materialize(
    *,
    organization_id: str,
    owner_id: AgentId,
    creation_tick: int,
    inception_digest: str,
    tick: int,
    bundle: _EvidenceBundle,
    policy: OrganizationConceptPolicy,
    prior: OrganizationConcept | None,
) -> OrganizationConcept:
    members, roles, goals, resources, procedures, records, commitments, identities = (
        _aspect_records(bundle, tick)
    )
    channels = _structural_channel_count(
        roles, goals, resources, procedures, records, commitments, identities
    )
    active_strengths = [
        member.strength
        for member in members
        if member.status is not OrganizationMembershipStatus.FORMER
    ]
    mean_support = (
        sum(active_strengths) / len(active_strengths) if active_strengths else 0.0
    )
    coverage = min(1.0, channels / 3.0)
    strength = _quantized((mean_support + coverage) / 2.0)
    evidence_count = sum(len(member.evidence_refs) for member in members)
    status: OrganizationStatus = _derive_status(
        members=members,
        structural_channels=channels,
        member_evidence_count=evidence_count,
        strength=strength,
        policy=policy,
    )
    active_members = [
        member
        for member in members
        if member.status is not OrganizationMembershipStatus.FORMER
    ]
    has_other_evidence = bool(
        roles or goals or resources or procedures or records or commitments
    )
    dissolved_goals: tuple[OrganizationGoalBelief, ...] = goals
    if not active_members and not has_other_evidence:
        status = OrganizationStatus.DISSOLVED
        dissolved_goals = tuple(
            replace(goal, status=OrganizationStatus.DISSOLVED) for goal in goals
        )
    first_tick = min((member.first_tick for member in members), default=tick)
    if prior is not None:
        first_tick = min(prior.first_tick, first_tick)
    draft = OrganizationConcept(
        organization_id=organization_id,
        owner_id=owner_id,
        creation_tick=creation_tick,
        inception_digest=inception_digest,
        status=status,
        temporal_scope=(
            OrganizationTemporalScope.TEMPORARY
            if any(
                member.temporal_scope is OrganizationTemporalScope.TEMPORARY
                for member in members
            )
            else OrganizationTemporalScope.ONGOING
        ),
        strength=strength,
        member_evidence_count=evidence_count,
        structural_channel_count=channels,
        first_tick=first_tick,
        last_tick=tick,
        members=members,
        roles=roles,
        goals=dissolved_goals,
        resources=resources,
        procedures=procedures,
        records=records,
        commitments=commitments,
        identities=identities,
    )
    digest = _content_digest(draft)
    lineage = list(prior.lineage if prior is not None else ())
    revisions = list(prior.revisions if prior is not None else ())
    snapshots = list(prior.snapshots if prior is not None else ())
    if prior is None:
        lineage.append(
            OrganizationLineageRecord(
                lineage_id=organization_lineage_id(
                    owner_id.value,
                    "emerged",
                    tick,
                    (organization_id,),
                    (organization_id,),
                ),
                kind=OrganizationLineageKind.EMERGED,
                tick=tick,
                from_ids=(organization_id,),
                to_ids=(organization_id,),
                evidence_digest=digest,
            )
        )
    else:
        previous_digest = _content_digest(prior)
        if previous_digest != digest:
            kind = (
                OrganizationRevisionKind.CONTINUED
                if prior.status is status
                else OrganizationRevisionKind.MEMBERSHIP_REVISED
            )
            revisions.append(
                OrganizationRevisionRecord(
                    revision_id=_revision_id(organization_id, tick),
                    kind=kind,
                    tick=tick,
                    before_digest=previous_digest,
                    after_digest=digest,
                    reason_code="observed",
                )
            )
            lineage.append(
                OrganizationLineageRecord(
                    lineage_id=organization_lineage_id(
                        owner_id.value,
                        "transformed",
                        tick,
                        (organization_id,),
                        (organization_id,),
                    ),
                    kind=OrganizationLineageKind.TRANSFORMED,
                    tick=tick,
                    from_ids=(organization_id,),
                    to_ids=(organization_id,),
                    evidence_digest=digest,
                )
            )
        elif not lineage:
            lineage.append(
                OrganizationLineageRecord(
                    lineage_id=organization_lineage_id(
                        owner_id.value,
                        "continued",
                        tick,
                        (organization_id,),
                        (organization_id,),
                    ),
                    kind=OrganizationLineageKind.CONTINUED,
                    tick=tick,
                    from_ids=(organization_id,),
                    to_ids=(organization_id,),
                    evidence_digest=digest,
                )
            )
    notices = set(bundle.notices)
    snapshots = _append_window(snapshots, draft, tick, policy, notices)
    revisions = _trim_revisions(revisions, policy.max_revisions)
    lineage = _trim_lineage(lineage, policy.max_lineage)
    return OrganizationConcept(
        organization_id=draft.organization_id,
        owner_id=draft.owner_id,
        creation_tick=draft.creation_tick,
        inception_digest=draft.inception_digest,
        status=draft.status,
        temporal_scope=draft.temporal_scope,
        strength=draft.strength,
        member_evidence_count=draft.member_evidence_count,
        structural_channel_count=draft.structural_channel_count,
        first_tick=draft.first_tick,
        last_tick=draft.last_tick,
        members=draft.members,
        roles=draft.roles,
        goals=draft.goals,
        resources=draft.resources,
        procedures=draft.procedures,
        records=draft.records,
        commitments=draft.commitments,
        identities=draft.identities,
        snapshots=tuple(snapshots),
        revisions=tuple(revisions),
        lineage=tuple(lineage),
        predecessor_ids=prior.predecessor_ids if prior is not None else (),
        notices=tuple(sorted(notices)),
    )


def _append_window(
    snapshots: list[OrganizationWindowRecord],
    concept: OrganizationConcept,
    tick: int,
    policy: OrganizationConceptPolicy,
    notices: set[str],
) -> list[OrganizationWindowRecord]:
    index = (snapshots[-1].window_index + 1) if snapshots else 0
    signature = organization_concept_digest(
        (
            tuple(member.member_id for member in concept.members),
            tuple(role.office_id for role in concept.roles),
            tuple(goal.anchor_id for goal in concept.goals),
            tuple(item.anchor_id for item in concept.resources),
            tuple(item.anchor_id for item in concept.procedures),
            tuple(item.anchor_id for item in concept.records),
        )
    )
    changed = not snapshots or snapshots[-1].structural_signature != signature
    if not changed and tick % policy.window_ticks != 0:
        return snapshots
    record = OrganizationWindowRecord(
        window_index=index,
        tick=tick,
        status=concept.status,
        temporal_scope=concept.temporal_scope,
        member_ids=tuple(member.member_id for member in concept.members),
        role_anchor_ids=tuple(role.office_id for role in concept.roles),
        goal_anchor_ids=tuple(goal.anchor_id for goal in concept.goals),
        resource_anchor_ids=tuple(item.anchor_id for item in concept.resources),
        procedure_anchor_ids=tuple(item.anchor_id for item in concept.procedures),
        record_anchor_ids=tuple(item.anchor_id for item in concept.records),
        commitment_ids=tuple(item.commitment_id for item in concept.commitments),
        structural_signature=signature,
        evidence_count=concept.member_evidence_count,
        identity_token=next(
            (item.label_token for item in concept.identities if item.label_token), None
        ),
    )
    if not snapshots:
        return [record]
    if snapshots[-1].structural_signature == signature:
        return snapshots
    updated = [*snapshots, record]
    if len(updated) > policy.max_snapshots:
        notices.add("history_truncated")
        updated = updated[-policy.max_snapshots :]
    return updated


def _trim_revisions(
    revisions: list[OrganizationRevisionRecord], cap: int
) -> list[OrganizationRevisionRecord]:
    if len(revisions) > cap:
        return revisions[-cap:]
    return revisions


def _trim_lineage(
    lineage: list[OrganizationLineageRecord], cap: int
) -> list[OrganizationLineageRecord]:
    if len(lineage) > cap:
        return lineage[-cap:]
    return lineage


def _age_concept(
    concept: OrganizationConcept, tick: int, policy: OrganizationConceptPolicy
) -> OrganizationConcept:
    if concept.status in (OrganizationStatus.DISSOLVED, OrganizationStatus.RETIRED):
        return concept
    idle = tick - concept.last_tick
    if idle >= 2 * policy.window_ticks:
        goals = tuple(
            replace(goal, status=OrganizationStatus.DISSOLVED)
            if goal.status in _ACTIVE_STATUSES
            else goal
            for goal in concept.goals
        )
        return replace(
            concept,
            status=OrganizationStatus.RETIRED,
            goals=goals,
        )
    if idle >= policy.window_ticks and _active_goal_count(concept) == 0:
        goals = tuple(
            replace(goal, status=OrganizationStatus.DISSOLVED) for goal in concept.goals
        )
        return replace(
            concept,
            status=OrganizationStatus.DISSOLVED,
            goals=goals,
        )
    return concept


def _expire_concept(
    concept: OrganizationConcept, tick: int, notices: set[str]
) -> OrganizationConcept:
    if concept.status in (OrganizationStatus.DISSOLVED, OrganizationStatus.RETIRED):
        return concept
    members: list[OrganizationMemberBelief] = []
    expired = False
    for member in concept.members:
        if (
            member.temporal_scope is OrganizationTemporalScope.TEMPORARY
            and member.expires_tick is not None
            and tick >= member.expires_tick
            and member.status is not OrganizationMembershipStatus.FORMER
        ):
            members.append(replace(member, status=OrganizationMembershipStatus.FORMER))
            expired = True
        else:
            members.append(member)
    if not expired:
        return concept
    notices.add("temporary_expired")
    active = [
        member
        for member in members
        if member.status is not OrganizationMembershipStatus.FORMER
    ]
    status: OrganizationStatus = concept.status
    goals = concept.goals
    if not active:
        status = OrganizationStatus.DISSOLVED
        goals = tuple(
            replace(goal, status=OrganizationStatus.DISSOLVED) for goal in goals
        )
    return replace(
        concept,
        members=tuple(members),
        status=status,
        goals=goals,
        last_tick=max(concept.last_tick, tick),
    )


def _apply_expiry(bundle: _EvidenceBundle, tick: int, notices: set[str]) -> None:
    for member in bundle.members.values():
        if (
            member.scope is OrganizationTemporalScope.TEMPORARY
            and member.expires_tick is not None
            and tick >= member.expires_tick
        ):
            member.status = OrganizationMembershipStatus.FORMER
            notices.add("temporary_expired")


def _new_ids(owner_id: AgentId, tick: int, bundle: _EvidenceBundle) -> tuple[str, str]:
    members = tuple(sorted(_bundle_member_ids(bundle)))
    anchors = tuple(
        sorted(
            {
                *bundle.roles,
                *bundle.goals,
                *bundle.resources,
                *(item.anchor_id for item in bundle.procedures.values()),
                *(item.anchor_id for item in bundle.records.values()),
            }
        )
    )
    if not members:
        members = ("unknown",)
    if not anchors:
        anchors = ("anchor",)
    organization_id = organization_concept_id(owner_id.value, tick, members, anchors)
    inception = hashlib.sha256(
        f"organization-inception.v1|{organization_id}|{tick}".encode()
    ).hexdigest()
    return organization_id, inception


def _resolve_owner(owner_id: object) -> AgentId:
    if type(owner_id) is AgentId:
        return owner_id
    if type(owner_id) is str:
        try:
            return AgentId(owner_id)
        except ValueError:
            _fail("organization_invalid_owner")
    _fail("organization_invalid_owner")


def _resolve_observation(observation: object) -> object:
    if observation is None:
        return None
    root = type(observation).__name__
    if observation.__class__.__module__.startswith("world"):
        for symbol in _FORBIDDEN_INPUT_SYMBOLS:
            if root == symbol:
                _fail("organization_invalid_status")
    return observation


def apply_organization_concept_update(
    *,
    owner_id: str,
    tick: int,
    observation: object,
    prior: OrganizationConceptLedger | None,
    institution_concepts: object | None,
    offices: object | None,
    group_formation: object | None,
    collective_decisions: object | None,
    structured_commitments: object | None,
    social_conventions: object | None,
    policy: OrganizationConceptPolicy,
) -> OrganizationConceptLedger:
    """Refresh one owner's organization beliefs from owner-local evidence."""

    owner = _resolve_owner(owner_id)
    current_tick = require_organization_tick(tick)
    if type(policy) is not OrganizationConceptPolicy:
        _fail("organization_policy_mismatch")
    if prior is not None and type(prior) is not OrganizationConceptLedger:
        _fail("organization_foreign_ledger")
    if prior is not None and prior.owner_id != owner:
        _fail("organization_foreign_ledger")
    observation = _resolve_observation(observation)
    evidence = _collect_evidence(
        owner_id=owner,
        tick=current_tick,
        observation=observation,
        institution_concepts=institution_concepts,
        offices=offices,
        group_formation=group_formation,
        collective_decisions=collective_decisions,
        structured_commitments=structured_commitments,
        social_conventions=social_conventions,
    )
    notices = set(evidence.notices)
    carried = tuple(prior.concepts) if prior is not None else ()
    ledger_lineage: list[OrganizationLineageRecord] = (
        list(prior.lineage) if prior is not None else []
    )
    matched = [concept for concept in carried if _matches(concept, evidence, policy)]
    concepts: list[OrganizationConcept] = []
    if len(matched) >= 2:
        merged_bundle = _EvidenceBundle()
        for concept in matched:
            _accumulate_prior(merged_bundle, concept)
        _accumulate_new(merged_bundle, evidence)
        _apply_expiry(merged_bundle, current_tick, notices)
        organization_id, inception = _new_ids(owner, current_tick, merged_bundle)
        successor = _materialize(
            organization_id=organization_id,
            owner_id=owner,
            creation_tick=current_tick,
            inception_digest=inception,
            tick=current_tick,
            bundle=merged_bundle,
            policy=policy,
            prior=None,
        )
        successor = replace(
            successor,
            predecessor_ids=tuple(
                sorted(concept.organization_id for concept in matched)
            ),
        )
        concepts.append(successor)
        ledger_lineage.append(
            OrganizationLineageRecord(
                lineage_id=organization_lineage_id(
                    owner.value,
                    "merge",
                    current_tick,
                    tuple(sorted(concept.organization_id for concept in matched)),
                    (successor.organization_id,),
                ),
                kind=OrganizationLineageKind.MERGE,
                tick=current_tick,
                from_ids=tuple(sorted(concept.organization_id for concept in matched)),
                to_ids=(successor.organization_id,),
                evidence_digest=_content_digest(successor),
            )
        )
        for concept in matched:
            transferred = tuple(
                replace(goal, status=OrganizationStatus.DISSOLVED)
                for goal in concept.goals
            )
            concepts.append(
                replace(
                    concept,
                    status=OrganizationStatus.RETIRED,
                    goals=transferred,
                    notices=tuple(sorted({*concept.notices, "membership_conflict"})),
                )
            )
        concepts.extend(concept for concept in carried if concept not in matched)
        concepts = list(
            {concept.organization_id: concept for concept in concepts}.values()
        )
    elif len(matched) == 1:
        concept = matched[0]
        concept_bundle = _EvidenceBundle()
        _accumulate_prior(concept_bundle, concept)
        _accumulate_new(concept_bundle, evidence)
        _apply_expiry(concept_bundle, current_tick, notices)
        prior_members = _concept_member_ids(concept)
        new_members = _bundle_member_ids(evidence)
        shares_anchor = bool(
            set(_concept_anchor_ids(concept))
            & {
                *evidence.roles,
                *evidence.goals,
                *(item.anchor_id for item in evidence.procedures.values()),
            }
        )
        if (
            prior_members
            and new_members
            and not (prior_members & new_members)
            and len(prior_members) >= policy.recognition_min_members
            and len(new_members) >= policy.recognition_min_members
            and shares_anchor
        ):
            retained = _EvidenceBundle()
            for member_id in sorted(prior_members):
                if member_id in concept_bundle.members:
                    retained.members[member_id] = concept_bundle.members[member_id]
            for role_key, role_value in concept_bundle.roles.items():
                retained.roles[role_key] = role_value
            for goal_key, goal_value in concept_bundle.goals.items():
                retained.goals[goal_key] = goal_value
            first_id, first_inception = _new_ids(owner, current_tick, retained)
            second_id, second_inception = _new_ids(owner, current_tick, evidence)
            first_child = _materialize(
                organization_id=first_id,
                owner_id=owner,
                creation_tick=current_tick,
                inception_digest=first_inception,
                tick=current_tick,
                bundle=retained,
                policy=policy,
                prior=None,
            )
            second_child = _materialize(
                organization_id=second_id,
                owner_id=owner,
                creation_tick=current_tick,
                inception_digest=second_inception,
                tick=current_tick,
                bundle=evidence,
                policy=policy,
                prior=None,
            )
            first_child = replace(
                first_child, predecessor_ids=(concept.organization_id,)
            )
            second_child = replace(
                second_child, predecessor_ids=(concept.organization_id,)
            )
            ledger_lineage.append(
                OrganizationLineageRecord(
                    lineage_id=organization_lineage_id(
                        owner.value,
                        "split",
                        current_tick,
                        (concept.organization_id,),
                        (first_id, second_id),
                    ),
                    kind=OrganizationLineageKind.SPLIT,
                    tick=current_tick,
                    from_ids=(concept.organization_id,),
                    to_ids=(first_id, second_id),
                    evidence_digest=_content_digest(second_child),
                )
            )
            concepts.extend((first_child, second_child))
            concepts.append(
                replace(
                    concept,
                    status=OrganizationStatus.RETIRED,
                    goals=tuple(
                        replace(goal, status=OrganizationStatus.DISSOLVED)
                        for goal in concept.goals
                    ),
                )
            )
            concepts.extend(
                item
                for item in carried
                if item.organization_id != concept.organization_id
            )
        else:
            updated = _materialize(
                organization_id=concept.organization_id,
                owner_id=owner,
                creation_tick=concept.creation_tick,
                inception_digest=concept.inception_digest,
                tick=current_tick,
                bundle=concept_bundle,
                policy=policy,
                prior=concept,
            )
            if (
                updated.status is OrganizationStatus.DISSOLVED
                and concept.status is not OrganizationStatus.DISSOLVED
            ):
                ledger_lineage.append(
                    OrganizationLineageRecord(
                        lineage_id=organization_lineage_id(
                            owner.value,
                            "dissolved",
                            current_tick,
                            (concept.organization_id,),
                            (concept.organization_id,),
                        ),
                        kind=OrganizationLineageKind.DISSOLVED,
                        tick=current_tick,
                        from_ids=(concept.organization_id,),
                        to_ids=(concept.organization_id,),
                        evidence_digest=_content_digest(updated),
                    )
                )
            concepts.append(updated)
            concepts.extend(
                _age_concept(item, current_tick, policy)
                for item in carried
                if item.organization_id != concept.organization_id
            )
    else:
        if _bundle_member_ids(evidence):
            organization_id, inception = _new_ids(owner, current_tick, evidence)
            _apply_expiry(evidence, current_tick, notices)
            concepts.append(
                _materialize(
                    organization_id=organization_id,
                    owner_id=owner,
                    creation_tick=current_tick,
                    inception_digest=inception,
                    tick=current_tick,
                    bundle=evidence,
                    policy=policy,
                    prior=None,
                )
            )
        concepts.extend(
            _age_concept(
                _expire_concept(item, current_tick, notices), current_tick, policy
            )
            for item in carried
        )
    if not concepts and not carried:
        _LOG.debug(
            "organization_update owner_id=%s concepts=%s created=%s merged=%s "
            "split=%s dissolved=%s tick=%s",
            owner.value,
            len(concepts),
            0,
            0,
            0,
            0,
            current_tick,
        )
        return OrganizationConceptLedger(owner_id=owner, notices=tuple(sorted(notices)))
    concepts.sort(key=lambda item: item.organization_id)
    if len(concepts) > policy.max_concepts:
        notices.add("history_truncated")
        concepts = sorted(
            concepts, key=lambda item: (item.last_tick, item.organization_id)
        )[-policy.max_concepts :]
        concepts.sort(key=lambda item: item.organization_id)
    ledger_lineage = _trim_lineage(ledger_lineage, policy.max_lineage)
    ledger = OrganizationConceptLedger(
        owner_id=owner,
        concepts=tuple(concepts),
        lineage=tuple(ledger_lineage),
        notices=tuple(sorted(notices)),
    )
    _LOG.debug(
        "organization_update owner_id=%s concepts=%s created=%s merged=%s "
        "split=%s dissolved=%s tick=%s",
        owner.value,
        len(ledger.concepts),
        sum(1 for item in concepts if item.creation_tick == current_tick),
        len(matched) if len(matched) >= 2 else 0,
        1
        if len(matched) == 1
        and any(
            record.kind is OrganizationLineageKind.SPLIT and record.tick == current_tick
            for record in ledger.lineage
        )
        else 0,
        sum(1 for item in concepts if item.status is OrganizationStatus.DISSOLVED),
        current_tick,
    )
    return ledger
