"""Bounded canonical ``organization-snapshot-v2`` artifact.

``simulation`` owns this schema and never imports ``analysis``. The artifact
publishes objective aggregate rows plus analytical candidates; owner-scoped claim
detail stays in the detached analysis layer. No owner id, ``orgc-`` id, label,
speech body, memory content, or resource balance appears here.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, NoReturn, cast

from world.identifiers import require_exact_nonneg_int

__all__ = [
    "MAX_CANDIDATE_OPERATIONS",
    "MAX_PAGE_ROWS",
    "MAX_RESPONSE_BYTES",
    "MAX_SNAPSHOT_BYTES",
    "MAX_SNAPSHOT_CANDIDATES",
    "MAX_SNAPSHOT_EDGES",
    "MAX_SNAPSHOT_MEMBERS",
    "MAX_SNAPSHOT_OBJECTIVE_ROWS",
    "MAX_SNAPSHOT_OPERATIONS",
    "MAX_SNAPSHOT_WINDOWS",
    "ORGANIZATION_OPERATION_ACTS",
    "ORGANIZATION_OPERATION_ANCHOR_KINDS",
    "ORGANIZATION_OPERATION_AUTHORITY_BASES",
    "ORGANIZATION_OPERATION_DOMAINS",
    "ORGANIZATION_OPERATION_OUTCOMES",
    "ORGANIZATION_OPERATION_PROVENANCE_CODES",
    "ORGANIZATION_OPERATION_TARGET_KINDS",
    "ORGANIZATION_SNAPSHOT_POLICY_VERSION",
    "ORGANIZATION_SNAPSHOT_SCHEMA_VERSION",
    "ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1",
    "ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V2",
    "SUPPORTED_ORGANIZATION_SNAPSHOT_SCHEMAS",
    "OrganizationArtifactError",
    "OrganizationCandidateRecord",
    "OrganizationCollectiveDecisionRecord",
    "OrganizationCoverage",
    "OrganizationImplementationRecord",
    "OrganizationLineageEdgeRecord",
    "OrganizationMemberRecord",
    "OrganizationObjectiveRow",
    "OrganizationOperationRecord",
    "OrganizationSnapshot",
    "OrganizationSnapshotRef",
    "OrganizationStructuralKind",
    "OrganizationStructuralRecord",
    "OrganizationWindowRecord",
    "empty_organization_snapshot",
    "organization_publication_operation_id",
    "require_collective_decision_publication_id",
    "require_implementation_publication_id",
    "require_operation_id",
    "require_organization_id",
    "require_publication_id",
    "upgrade_organization_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.organization_models")

ORGANIZATION_SNAPSHOT_SCHEMA_VERSION: Final[str] = "organization-snapshot-v3"
ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1: Final[str] = "organization-snapshot-v1"
ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V2: Final[str] = "organization-snapshot-v2"
SUPPORTED_ORGANIZATION_SNAPSHOT_SCHEMAS: Final[tuple[str, ...]] = (
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1,
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V2,
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
)
ORGANIZATION_SNAPSHOT_POLICY_VERSION: Final[str] = "organization-analysis.v1"

MAX_SNAPSHOT_BYTES: Final[int] = 4 * 1024 * 1024
MAX_SNAPSHOT_CANDIDATES: Final[int] = 2048
MAX_SNAPSHOT_MEMBERS: Final[int] = 512
MAX_SNAPSHOT_EDGES: Final[int] = 16384
MAX_SNAPSHOT_WINDOWS: Final[int] = 512
MAX_SNAPSHOT_OBJECTIVE_ROWS: Final[int] = 4096
MAX_CANDIDATE_OPERATIONS: Final[int] = 64
MAX_CANDIDATE_COLLECTIVE_DECISIONS: Final[int] = 64
MAX_DECISION_IMPLEMENTATIONS: Final[int] = 32
MAX_SNAPSHOT_COLLECTIVE_DECISIONS: Final[int] = 4096
MAX_SNAPSHOT_COLLECTIVE_IMPLEMENTATIONS: Final[int] = 8192
MAX_SNAPSHOT_OPERATIONS: Final[int] = 4096
MAX_RESPONSE_BYTES: Final[int] = 2 * 1024 * 1024
MAX_PAGE_ROWS: Final[int] = 500

ORGANIZATION_ID_PREFIX: Final[str] = "org-"
PUBLICATION_ID_PREFIX: Final[str] = "org-edge-"
OPERATION_ID_PREFIX: Final[str] = "orgop-"
COLLECTIVE_DECISION_PUBLICATION_PREFIX: Final[str] = "orgcpd-"
IMPLEMENTATION_PUBLICATION_PREFIX: Final[str] = "orgcpi-"
_ID_HEX_CHARS: Final[int] = 16

_ORGANIZATION_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^org-[0-9a-f]{{{_ID_HEX_CHARS}}}$"
)
_PUBLICATION_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^org-edge-[0-9a-f]{{{_ID_HEX_CHARS}}}$"
)
_OPERATION_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^orgop-[0-9a-f]{{{_ID_HEX_CHARS}}}$"
)
_COLLECTIVE_DECISION_PUBLICATION_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^orgcpd-[0-9a-f]{{{_ID_HEX_CHARS}}}$"
)
_IMPLEMENTATION_PUBLICATION_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^orgcpi-[0-9a-f]{{{_ID_HEX_CHARS}}}$"
)
_ACTOR_REF_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{16}$")
_SAFE_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

PROVENANCE_CODES: Final[frozenset[str]] = frozenset(
    {
        "ok",
        "member_list_truncated",
        "history_truncated",
        "lane_absent",
        "operations_truncated",
        "operation_anchor_unresolved",
        "operation_expired",
        "collective_agency_truncated",
        "collective_decision_unrecognized",
        "collective_implementation_incomplete",
        "collective_implementation_expired",
        "collective_sabotage_attributed",
    }
)
CANDIDATE_STATUSES: Final[frozenset[str]] = frozenset(
    {"recognized", "partial", "disputed", "fragmented", "temporary", "dissolved"}
)
MEMBERSHIP_STATUSES: Final[frozenset[str]] = frozenset(
    {"explicit", "perceived", "disputed", "unknown", "former"}
)
TEMPORAL_SCOPES: Final[frozenset[str]] = frozenset({"ongoing", "temporary", "unknown"})
LINEAGE_KINDS: Final[frozenset[str]] = frozenset(
    {"continued", "transformed", "split", "merge", "dissolved", "emerged"}
)

ORGANIZATION_OPERATION_DOMAINS: Final[frozenset[str]] = frozenset(
    {
        "resource_control",
        "storage",
        "record_keeping",
        "membership_admission",
        "membership_departure",
        "role_assignment",
        "procedure_action",
        "internal_commitment",
    }
)
ORGANIZATION_OPERATION_ACTS: Final[frozenset[str]] = frozenset(
    {
        "admit",
        "depart",
        "assign",
        "remove",
        "authorize_control",
        "revoke_control",
        "invoke_procedure",
        "declare_commitment",
        "fulfill_commitment",
        "record_decision",
    }
)
ORGANIZATION_OPERATION_AUTHORITY_BASES: Final[frozenset[str]] = frozenset(
    {
        "self_authored",
        "role_belief",
        "decision_belief",
        "procedure_belief",
        "record_reference",
        "observation",
        "unknown",
    }
)
ORGANIZATION_OPERATION_PROVENANCE_CODES: Final[frozenset[str]] = frozenset(
    {
        "self_authored",
        "role_authorized",
        "decision_supported",
        "procedure_recognized",
        "observed_effect",
        "unknown_authority",
        "contested",
        "expired",
        "orphaned",
    }
)
ORGANIZATION_OPERATION_OUTCOMES: Final[frozenset[str]] = frozenset(
    {"observed", "attempted", "completed", "blocked", "unknown"}
)
ORGANIZATION_AGENCY_RECOGNITIONS: Final[frozenset[str]] = frozenset(
    {"recognized", "contested", "unrecognized", "expired", "unknown"}
)
ORGANIZATION_AGENCY_IMPLEMENTATION_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "pending",
        "implemented",
        "partial",
        "unimplemented",
        "obstructed",
        "refused",
        "sabotaged",
        "contrary",
        "unknown",
        "expired",
    }
)
ORGANIZATION_AGENCY_MODES: Final[frozenset[str]] = frozenset(
    {"physical", "testimonial"}
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
ORGANIZATION_OPERATION_TARGET_KINDS: Final[frozenset[str]] = frozenset(
    {"member", "office", "anchor", "none"}
)
ORGANIZATION_OPERATION_ANCHOR_KINDS: Final[frozenset[str]] = frozenset(
    {
        "item",
        "resource",
        "artifact",
        "structure",
        "repository",
        "collective_project",
        "commitment",
        "owner_local",
        "unknown",
    }
)
_CONTROL_STANCES: Final[frozenset[str]] = frozenset(
    {"claimed", "recognized", "shared", "disputed", "former", "unknown"}
)
_ADMISSION_STANCES: Final[frozenset[str]] = frozenset(
    {"admitted", "claimed", "self_joined", "denied", "disputed", "former", "unknown"}
)
_DEPARTURE_STANCES: Final[frozenset[str]] = frozenset(
    {"resigned", "expelled", "departed", "disputed", "unknown"}
)
_ASSIGNMENT_STANCES: Final[frozenset[str]] = frozenset(
    {"assigned", "claimed", "disputed", "removed", "vacant", "unknown"}
)
_COMMITMENT_STANCES: Final[frozenset[str]] = frozenset(
    {
        "declared",
        "accepted",
        "fulfilled",
        "violated",
        "disputed",
        "forgotten",
        "unknown",
    }
)
_PROCEDURE_STANCES: Final[frozenset[str]] = frozenset(
    {"claimed", "disputed", "unknown"}
)
_DECISION_STANCES: Final[frozenset[str]] = frozenset(
    {"supported", "contested", "unknown"}
)
_OPERATION_STANCES_BY_ACT: Final[dict[str, frozenset[str]]] = {
    "admit": _ADMISSION_STANCES,
    "depart": _DEPARTURE_STANCES,
    "assign": _ASSIGNMENT_STANCES,
    "remove": _ASSIGNMENT_STANCES,
    "authorize_control": _CONTROL_STANCES,
    "revoke_control": _CONTROL_STANCES,
    "invoke_procedure": _PROCEDURE_STANCES,
    "declare_commitment": _COMMITMENT_STANCES,
    "fulfill_commitment": _COMMITMENT_STANCES,
    "record_decision": _DECISION_STANCES,
}
_OBJECTIVE_ANCHOR_KINDS: Final[frozenset[str]] = frozenset(
    {
        "item",
        "resource",
        "artifact",
        "structure",
        "repository",
        "collective_project",
        "commitment",
    }
)


class OrganizationStructuralKind(StrEnum):
    """Closed structural anchor family in the published artifact."""

    ROLE = "role"
    GOAL = "goal"
    RESOURCE = "resource"
    PROCEDURE = "procedure"
    RECORD = "record"
    COMMITMENT = "commitment"
    IDENTITY = "identity"


class OrganizationArtifactError(ValueError):
    """Fail-closed artifact error with a stable reason code only."""

    def __init__(self, code: str) -> None:
        self.code: str = code
        super().__init__(code)


def _fail(code: str) -> NoReturn:
    raise OrganizationArtifactError(code)


def _tick(name: str, value: object) -> int:
    try:
        return require_exact_nonneg_int(name, value)
    except (TypeError, ValueError) as exc:
        raise OrganizationArtifactError("organization_invalid_value") from exc


def _string(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        _fail("organization_invalid_value")
    return value


def _optional_string(name: str, value: object) -> str | None:
    if value is None:
        return None
    return _string(name, value)


def _safe_token(name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or not _SAFE_TOKEN_PATTERN.match(value)
        or ".." in value
    ):
        _fail("organization_invalid_value")
    return value


def _sorted_ids(name: str, values: object) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (list, tuple)):
        _fail("organization_invalid_value")
    items = tuple(_string(name, value) for value in cast("list[object]", values))
    if len(set(items)) != len(items) or items != tuple(sorted(items)):
        _fail("organization_invalid_value")
    return items


def require_organization_id(value: object) -> str:
    """Validate an exact ``org-`` plus 16 lowercase hex characters id."""
    if not isinstance(value, str) or not _ORGANIZATION_ID_PATTERN.match(value):
        _fail("organization_invalid_value")
    return value


_PUBLICATION_OPERATION_NAMESPACE: Final[str] = (
    "palimpsest.organization.publication-operation.v1"
)


def organization_publication_operation_id(
    organization_id: str,
    domain: str,
    tick: int,
    ordinal: int,
    content_digest: str,
) -> str:
    """Mint one deterministic published ``orgop-`` id from visible content.

    This mirrors the owner-side minter in
    ``agents.cognition.organization_operations`` so publication can stay free of
    a cognition dependency while producing the same identity.
    """
    import hashlib

    if type(tick) is not int or tick < 0:
        _fail("organization_operation_tick_regression")
    if type(ordinal) is not int or ordinal < 0:
        _fail("organization_invalid_value")
    material = (
        _PUBLICATION_OPERATION_NAMESPACE,
        _string("organization_id", organization_id),
        _string("domain", domain),
        str(tick),
        str(ordinal),
        _string("content_digest", content_digest),
    )
    body = hashlib.sha256("\x1f".join(material).encode("utf-8")).hexdigest()[
        :_ID_HEX_CHARS
    ]
    return f"{OPERATION_ID_PREFIX}{body}"


def require_collective_decision_publication_id(value: object) -> str:
    if (
        type(value) is not str
        or _COLLECTIVE_DECISION_PUBLICATION_PATTERN.match(value) is None
    ):
        _fail("organization_invalid_value")
    return value


def require_implementation_publication_id(value: object) -> str:
    if (
        type(value) is not str
        or _IMPLEMENTATION_PUBLICATION_PATTERN.match(value) is None
    ):
        _fail("organization_invalid_value")
    return value


def require_operation_id(value: object) -> str:
    """Validate an exact ``orgop-`` plus 16 lowercase hex characters id."""
    if not isinstance(value, str) or not _OPERATION_ID_PATTERN.match(value):
        _fail("organization_invalid_value")
    return value


def require_publication_id(value: object) -> str:
    """Validate an exact ``org-edge-`` plus 16 lowercase hex characters id."""
    if not isinstance(value, str) or not _PUBLICATION_ID_PATTERN.match(value):
        _fail("organization_invalid_value")
    return value


def require_snapshot_digest(value: object) -> str:
    """Validate a 64-character lowercase SHA-256 digest."""
    if not isinstance(value, str) or len(value) != 64:
        _fail("organization_invalid_value")
    if any(character not in "0123456789abcdef" for character in value):
        _fail("organization_invalid_value")
    return value


@dataclass(frozen=True, slots=True)
class OrganizationSnapshotRef:
    publication_id: str
    snapshot_digest: str
    schema_version: str
    run_id: str
    generated_tick: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "publication_id", require_publication_id(self.publication_id)
        )
        object.__setattr__(
            self, "snapshot_digest", require_snapshot_digest(self.snapshot_digest)
        )
        if self.schema_version not in SUPPORTED_ORGANIZATION_SNAPSHOT_SCHEMAS:
            _fail("organization_invalid_value")
        object.__setattr__(self, "run_id", _safe_token("run_id", self.run_id))
        object.__setattr__(
            self, "generated_tick", _tick("generated_tick", self.generated_tick)
        )


@dataclass(frozen=True, slots=True)
class OrganizationMemberRecord:
    member_id: str
    status: str
    basis: str
    temporal_scope: str
    first_tick: int
    last_tick: int
    strength: float
    owner_support_count: int
    expires_tick: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "member_id", _string("member_id", self.member_id))
        if self.status not in MEMBERSHIP_STATUSES:
            _fail("organization_invalid_value")
        object.__setattr__(self, "basis", _string("basis", self.basis))
        if self.temporal_scope not in TEMPORAL_SCOPES:
            _fail("organization_invalid_value")
        first = _tick("first_tick", self.first_tick)
        last = _tick("last_tick", self.last_tick)
        if last < first:
            _fail("organization_invalid_value")
        if self.expires_tick is not None:
            object.__setattr__(
                self, "expires_tick", _tick("expires_tick", self.expires_tick)
            )
        if type(self.strength) is not float or not (0.0 <= self.strength <= 1.0):
            _fail("organization_invalid_value")
        object.__setattr__(
            self,
            "owner_support_count",
            require_exact_nonneg_int("owner_support_count", self.owner_support_count),
        )


@dataclass(frozen=True, slots=True)
class OrganizationStructuralRecord:
    kind: str
    anchor_id: str
    status: str
    first_tick: int
    last_tick: int
    resolved: bool = True

    def __post_init__(self) -> None:
        try:
            kind = OrganizationStructuralKind(self.kind)
        except ValueError as exc:
            raise OrganizationArtifactError("organization_invalid_value") from exc
        object.__setattr__(self, "kind", kind.value)
        object.__setattr__(self, "anchor_id", _string("anchor_id", self.anchor_id))
        object.__setattr__(self, "status", _string("status", self.status))
        first = _tick("first_tick", self.first_tick)
        last = _tick("last_tick", self.last_tick)
        if last < first:
            _fail("organization_invalid_value")
        if type(self.resolved) is not bool:
            _fail("organization_invalid_value")


@dataclass(frozen=True, slots=True)
class OrganizationOperationRecord:
    """One published operation belief with provenance and no owner-local ids."""

    operation_id: str
    domain: str
    act: str
    stance: str
    authority_basis: str
    provenance_code: str
    outcome: str
    command_kind: str
    target_kind: str
    anchor_kind: str
    anchor_id: str | None
    tick: int
    first_tick: int
    last_tick: int
    support_count: int
    contest_count: int
    resolved: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "operation_id", require_operation_id(self.operation_id)
        )
        if self.domain not in ORGANIZATION_OPERATION_DOMAINS:
            _fail("organization_invalid_value")
        if self.act not in ORGANIZATION_OPERATION_ACTS:
            _fail("organization_invalid_value")
        stances = _OPERATION_STANCES_BY_ACT[self.act]
        if self.stance not in stances:
            _fail("organization_invalid_value")
        if self.authority_basis not in ORGANIZATION_OPERATION_AUTHORITY_BASES:
            _fail("organization_invalid_value")
        if self.provenance_code not in ORGANIZATION_OPERATION_PROVENANCE_CODES:
            _fail("organization_invalid_value")
        if self.outcome not in ORGANIZATION_OPERATION_OUTCOMES:
            _fail("organization_invalid_value")
        command_kind = _safe_token("command_kind", self.command_kind)
        object.__setattr__(self, "command_kind", command_kind)
        if self.target_kind not in ORGANIZATION_OPERATION_TARGET_KINDS:
            _fail("organization_invalid_value")
        if self.anchor_kind not in ORGANIZATION_OPERATION_ANCHOR_KINDS:
            _fail("organization_invalid_value")
        if self.anchor_kind in _OBJECTIVE_ANCHOR_KINDS:
            object.__setattr__(self, "anchor_id", _string("anchor_id", self.anchor_id))
        elif self.anchor_id is not None:
            _fail("organization_invalid_value")
        first = _tick("first_tick", self.first_tick)
        last = _tick("last_tick", self.last_tick)
        if last < first:
            _fail("organization_invalid_value")
        tick = _tick("tick", self.tick)
        if tick < first or tick > last:
            _fail("organization_invalid_value")
        object.__setattr__(
            self, "support_count", _tick("support_count", self.support_count)
        )
        object.__setattr__(
            self, "contest_count", _tick("contest_count", self.contest_count)
        )
        if type(self.resolved) is not bool:
            _fail("organization_invalid_value")
        if self.resolved is (self.anchor_kind == "unknown"):
            _fail("organization_invalid_value")

    @property
    def contested(self) -> bool:
        return self.stance == "disputed" or self.contest_count > 0


@dataclass(frozen=True, slots=True)
class OrganizationImplementationRecord:
    """One published per-actor implementation belief; never a raw agent id."""

    implementation_id: str
    decision_id: str
    actor_ref: str
    status: str
    effect: str
    observed_tick: int
    provenance_code: str
    resolved: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "implementation_id",
            require_implementation_publication_id(self.implementation_id),
        )
        object.__setattr__(
            self,
            "decision_id",
            require_collective_decision_publication_id(self.decision_id),
        )
        if (
            type(self.actor_ref) is not str
            or _ACTOR_REF_PATTERN.match(self.actor_ref) is None
        ):
            _fail("organization_invalid_value")
        if self.status not in ORGANIZATION_AGENCY_IMPLEMENTATION_STATUSES:
            _fail("organization_invalid_value")
        object.__setattr__(self, "effect", _safe_token("effect", self.effect))
        object.__setattr__(
            self, "observed_tick", _tick("observed_tick", self.observed_tick)
        )
        if self.provenance_code not in ORGANIZATION_OPERATION_PROVENANCE_CODES:
            _fail("organization_invalid_value")
        if type(self.resolved) is not bool:
            _fail("organization_invalid_value")


@dataclass(frozen=True, slots=True)
class OrganizationCollectiveDecisionRecord:
    """One published collective decision belief with per-actor implementations."""

    decision_id: str
    organization_id: str
    proposal_ref: str
    revision: int
    procedure_ref: str | None
    recognition: str
    authority_basis: str
    support_count: int
    oppose_count: int
    abstain_count: int
    contest_count: int
    implementation_mode: str
    effect: str
    target_kind: str
    target_ref: str | None
    decided_tick: int
    window_end_tick: int
    implementation_status: str
    provenance_code: str
    resolved: bool
    implementations: tuple[OrganizationImplementationRecord, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "decision_id",
            require_collective_decision_publication_id(self.decision_id),
        )
        object.__setattr__(
            self, "organization_id", require_organization_id(self.organization_id)
        )
        if _ACTOR_REF_PATTERN.match(_string("proposal_ref", self.proposal_ref)) is None:
            _fail("organization_invalid_value")
        object.__setattr__(self, "revision", _tick("revision", self.revision))
        if self.procedure_ref is not None and (
            _ACTOR_REF_PATTERN.match(_string("procedure_ref", self.procedure_ref))
            is None
        ):
            _fail("organization_invalid_value")
        if self.recognition not in ORGANIZATION_AGENCY_RECOGNITIONS:
            _fail("organization_invalid_value")
        if self.authority_basis not in ORGANIZATION_OPERATION_AUTHORITY_BASES:
            _fail("organization_invalid_value")
        for name in (
            "support_count",
            "oppose_count",
            "abstain_count",
            "contest_count",
        ):
            object.__setattr__(self, name, _tick(name, getattr(self, name)))
        if self.implementation_mode not in ORGANIZATION_AGENCY_MODES:
            _fail("organization_invalid_value")
        object.__setattr__(self, "effect", _safe_token("effect", self.effect))
        if self.target_kind not in ORGANIZATION_AGENCY_TARGET_KINDS:
            _fail("organization_invalid_value")
        if self.target_kind in ("none", "unknown"):
            if self.target_ref is not None:
                _fail("organization_invalid_value")
        elif _ACTOR_REF_PATTERN.match(_string("target_ref", self.target_ref)) is None:
            _fail("organization_invalid_value")
        decided = _tick("decided_tick", self.decided_tick)
        window_end = _tick("window_end_tick", self.window_end_tick)
        if window_end < decided:
            _fail("organization_invalid_value")
        if (
            self.implementation_status
            not in ORGANIZATION_AGENCY_IMPLEMENTATION_STATUSES
        ):
            _fail("organization_invalid_value")
        if self.provenance_code not in (
            ORGANIZATION_OPERATION_PROVENANCE_CODES | PROVENANCE_CODES
        ):
            _fail("organization_invalid_value")
        if type(self.resolved) is not bool:
            _fail("organization_invalid_value")
        if self.resolved is (self.target_kind == "unknown"):
            _fail("organization_invalid_value")
        implementations = tuple(self.implementations)
        if len(implementations) > MAX_DECISION_IMPLEMENTATIONS:
            _fail("organization_size_limit")
        seen: set[str] = set()
        for implementation in implementations:
            if type(implementation) is not OrganizationImplementationRecord:
                _fail("organization_invalid_value")
            if implementation.decision_id != self.decision_id:
                _fail("organization_invalid_value")
            if implementation.implementation_id in seen:
                _fail("organization_duplicate_operation")
            seen.add(implementation.implementation_id)
        object.__setattr__(
            self,
            "implementations",
            tuple(
                sorted(
                    implementations,
                    key=lambda item: (
                        item.observed_tick,
                        item.actor_ref,
                        item.implementation_id,
                    ),
                )
            ),
        )


@dataclass(frozen=True, slots=True)
class OrganizationCandidateRecord:
    organization_id: str
    creation_tick: int
    first_tick: int
    last_tick: int
    status: str
    temporal_scope: str
    self_identified: bool
    members: tuple[OrganizationMemberRecord, ...] = ()
    structure: tuple[OrganizationStructuralRecord, ...] = ()
    window_indexes: tuple[int, ...] = ()
    operations: tuple[OrganizationOperationRecord, ...] = ()
    collective_decisions: tuple[OrganizationCollectiveDecisionRecord, ...] = ()
    collective_proposal_count: int = 0
    collective_amendment_count: int = 0
    collective_support_count: int = 0
    collective_oppose_count: int = 0
    collective_abstain_count: int = 0
    collective_decision_count: int = 0
    collective_implementation_count: int = 0
    unimplemented_decision_count: int = 0
    contested_decision_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "organization_id", require_organization_id(self.organization_id)
        )
        object.__setattr__(
            self, "creation_tick", _tick("creation_tick", self.creation_tick)
        )
        first = _tick("first_tick", self.first_tick)
        last = _tick("last_tick", self.last_tick)
        if last < first:
            _fail("organization_invalid_value")
        if self.status not in CANDIDATE_STATUSES:
            _fail("organization_invalid_value")
        if self.temporal_scope not in TEMPORAL_SCOPES:
            _fail("organization_invalid_value")
        if type(self.self_identified) is not bool:
            _fail("organization_invalid_value")
        members = tuple(self.members)
        if len(members) > MAX_SNAPSHOT_MEMBERS:
            _fail("organization_size_limit")
        seen_members: set[str] = set()
        for member in members:
            if type(member) is not OrganizationMemberRecord:
                _fail("organization_invalid_value")
            if member.member_id in seen_members:
                _fail("organization_duplicate_member")
            seen_members.add(member.member_id)
        object.__setattr__(
            self, "members", tuple(sorted(members, key=lambda item: item.member_id))
        )
        structure = tuple(self.structure)
        seen_structure: set[tuple[str, str]] = set()
        for item in structure:
            if type(item) is not OrganizationStructuralRecord:
                _fail("organization_invalid_value")
            key = (item.kind, item.anchor_id)
            if key in seen_structure:
                _fail("organization_invalid_value")
            seen_structure.add(key)
        object.__setattr__(
            self,
            "structure",
            tuple(sorted(structure, key=lambda item: (item.kind, item.anchor_id))),
        )
        indexes = tuple(self.window_indexes)
        if indexes != tuple(sorted(set(indexes))):
            _fail("organization_invalid_value")
        object.__setattr__(self, "window_indexes", indexes)
        operations = tuple(self.operations)
        if len(operations) > MAX_CANDIDATE_OPERATIONS:
            _fail("organization_size_limit")
        seen_operations: set[str] = set()
        for operation in operations:
            if type(operation) is not OrganizationOperationRecord:
                _fail("organization_invalid_value")
            if operation.operation_id in seen_operations:
                _fail("organization_duplicate_operation")
            seen_operations.add(operation.operation_id)
        object.__setattr__(
            self,
            "operations",
            tuple(
                sorted(
                    operations,
                    key=lambda item: (item.tick, item.domain, item.operation_id),
                )
            ),
        )
        decisions = tuple(self.collective_decisions)
        if len(decisions) > MAX_CANDIDATE_COLLECTIVE_DECISIONS:
            _fail("organization_size_limit")
        seen_decisions: set[str] = set()
        for decision in decisions:
            if type(decision) is not OrganizationCollectiveDecisionRecord:
                _fail("organization_invalid_value")
            if decision.organization_id != self.organization_id:
                _fail("organization_invalid_value")
            if decision.decision_id in seen_decisions:
                _fail("organization_duplicate_operation")
            seen_decisions.add(decision.decision_id)
        object.__setattr__(
            self,
            "collective_decisions",
            tuple(
                sorted(
                    decisions,
                    key=lambda item: (item.decided_tick, item.decision_id),
                )
            ),
        )
        for name in (
            "collective_proposal_count",
            "collective_amendment_count",
            "collective_support_count",
            "collective_oppose_count",
            "collective_abstain_count",
            "collective_decision_count",
            "collective_implementation_count",
            "unimplemented_decision_count",
            "contested_decision_count",
        ):
            _tick(name, getattr(self, name))
        if self.collective_decision_count != len(decisions):
            _fail("organization_invalid_value")
        if self.collective_implementation_count != sum(
            len(item.implementations) for item in decisions
        ):
            _fail("organization_invalid_value")
        if self.contested_decision_count != sum(
            1 for item in decisions if item.recognition == "contested"
        ):
            _fail("organization_invalid_value")
        if self.unimplemented_decision_count != sum(
            1 for item in decisions if item.implementation_status == "unimplemented"
        ):
            _fail("organization_invalid_value")

    @property
    def member_count(self) -> int:
        return len(self.members)

    def count(self, kind: OrganizationStructuralKind) -> int:
        return sum(1 for item in self.structure if item.kind == kind.value)

    @property
    def structural_channel_count(self) -> int:
        return len({item.kind for item in self.structure})

    @property
    def operation_count(self) -> int:
        return len(self.operations)

    @property
    def contested_operation_count(self) -> int:
        return sum(1 for operation in self.operations if operation.contested)


@dataclass(frozen=True, slots=True)
class OrganizationWindowRecord:
    window_index: int
    start_tick: int
    end_tick: int
    candidate_ids: tuple[str, ...]
    member_count: int
    overlap_member_count: int
    lane_presence: tuple[tuple[str, bool], ...] = ()
    operation_count: int = 0
    contested_operation_count: int = 0
    collective_decision_count: int = 0
    collective_implementation_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "window_index", _tick("window_index", self.window_index)
        )
        start = _tick("start_tick", self.start_tick)
        end = _tick("end_tick", self.end_tick)
        if end < start:
            _fail("organization_invalid_value")
        ids = tuple(require_organization_id(item) for item in self.candidate_ids)
        if len(set(ids)) != len(ids):
            _fail("organization_duplicate_candidate")
        object.__setattr__(self, "candidate_ids", tuple(sorted(ids)))
        object.__setattr__(
            self, "member_count", _tick("member_count", self.member_count)
        )
        object.__setattr__(
            self,
            "overlap_member_count",
            _tick("overlap_member_count", self.overlap_member_count),
        )
        lanes = tuple(self.lane_presence)
        for name, value in lanes:
            _string("lane", name)
            if type(value) is not bool:
                _fail("organization_invalid_value")
        object.__setattr__(self, "lane_presence", tuple(sorted(lanes)))
        object.__setattr__(
            self, "operation_count", _tick("operation_count", self.operation_count)
        )
        object.__setattr__(
            self,
            "contested_operation_count",
            _tick("contested_operation_count", self.contested_operation_count),
        )
        object.__setattr__(
            self,
            "collective_decision_count",
            _tick("collective_decision_count", self.collective_decision_count),
        )
        object.__setattr__(
            self,
            "collective_implementation_count",
            _tick(
                "collective_implementation_count",
                self.collective_implementation_count,
            ),
        )


@dataclass(frozen=True, slots=True)
class OrganizationLineageEdgeRecord:
    kind: str
    tick: int
    from_id: str | None = None
    to_id: str | None = None
    jaccard: float | None = None
    containment: float | None = None

    def __post_init__(self) -> None:
        if self.kind not in LINEAGE_KINDS:
            _fail("organization_invalid_value")
        object.__setattr__(self, "tick", _tick("tick", self.tick))
        for name in ("from_id", "to_id"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, require_organization_id(value))
        if self.kind == "emerged" and self.from_id is not None:
            _fail("organization_unknown_candidate")
        if self.kind == "dissolved" and self.to_id is not None:
            _fail("organization_unknown_candidate")
        for name in ("jaccard", "containment"):
            value = getattr(self, name)
            if value is not None:
                if type(value) is not float or not (0.0 <= value <= 1.0):
                    _fail("organization_invalid_value")


@dataclass(frozen=True, slots=True)
class OrganizationObjectiveRow:
    window_index: int
    tick: int
    member_count: int
    role_count: int
    goal_count: int
    resource_count: int
    procedure_count: int
    record_count: int
    commitment_count: int
    identity_count: int
    resolved_anchor_count: int
    unresolved_anchor_count: int
    operation_action_count: int = 0
    collective_decision_count: int = 0
    collective_implementation_count: int = 0

    def __post_init__(self) -> None:
        for name in (
            "window_index",
            "tick",
            "member_count",
            "role_count",
            "goal_count",
            "resource_count",
            "procedure_count",
            "record_count",
            "commitment_count",
            "identity_count",
            "resolved_anchor_count",
            "unresolved_anchor_count",
            "operation_action_count",
            "collective_decision_count",
            "collective_implementation_count",
        ):
            _tick(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class OrganizationCoverage:
    observed: int
    expected: int
    ratio: float | None

    def __post_init__(self) -> None:
        observed = require_exact_nonneg_int("observed", self.observed)
        expected = require_exact_nonneg_int("expected", self.expected)
        if observed > expected:
            raise OrganizationArtifactError("organization_invalid_coverage")
        if expected == 0:
            ratio = None
        else:
            ratio = observed / expected
            if self.ratio is not None and abs(self.ratio - ratio) > 1e-9:
                raise OrganizationArtifactError("organization_invalid_coverage")
        if self.ratio is not None and not (0.0 <= self.ratio <= 1.0):
            raise OrganizationArtifactError("organization_invalid_coverage")
        object.__setattr__(self, "observed", observed)
        object.__setattr__(self, "expected", expected)
        object.__setattr__(self, "ratio", ratio)


@dataclass(frozen=True, slots=True)
class OrganizationSnapshot:
    schema_version: str
    policy_version: str
    run_id: str
    input_revision: str
    generated_tick: int
    publication_id: str
    coverage: OrganizationCoverage
    windows: tuple[OrganizationWindowRecord, ...] = ()
    candidates: tuple[OrganizationCandidateRecord, ...] = ()
    edges: tuple[OrganizationLineageEdgeRecord, ...] = ()
    objective_rows: tuple[OrganizationObjectiveRow, ...] = ()
    provenance_code: str = "ok"

    def __post_init__(self) -> None:
        if self.schema_version not in SUPPORTED_ORGANIZATION_SNAPSHOT_SCHEMAS:
            _fail("organization_invalid_value")
        if self.policy_version != ORGANIZATION_SNAPSHOT_POLICY_VERSION:
            _fail("organization_invalid_value")
        object.__setattr__(self, "run_id", _safe_token("run_id", self.run_id))
        object.__setattr__(
            self, "input_revision", _safe_token("input_revision", self.input_revision)
        )
        object.__setattr__(
            self, "generated_tick", _tick("generated_tick", self.generated_tick)
        )
        if self.publication_id != "":
            require_publication_id(self.publication_id)
        if type(self.coverage) is not OrganizationCoverage:
            _fail("organization_invalid_coverage")
        candidates = tuple(self.candidates)
        if len(candidates) > MAX_SNAPSHOT_CANDIDATES:
            _fail("organization_size_limit")
        seen: set[str] = set()
        for candidate in candidates:
            if type(candidate) is not OrganizationCandidateRecord:
                _fail("organization_invalid_value")
            if candidate.organization_id in seen:
                _fail("organization_duplicate_candidate")
            seen.add(candidate.organization_id)
        object.__setattr__(
            self,
            "candidates",
            tuple(sorted(candidates, key=lambda item: item.organization_id)),
        )
        operation_ids: set[str] = set()
        total_operations = 0
        decision_ids: set[str] = set()
        implementation_ids: set[str] = set()
        total_decisions = 0
        total_implementations = 0
        for candidate in candidates:
            for operation in candidate.operations:
                if operation.operation_id in operation_ids:
                    _fail("organization_duplicate_operation")
                operation_ids.add(operation.operation_id)
            total_operations += len(candidate.operations)
            for decision in candidate.collective_decisions:
                if decision.decision_id in decision_ids:
                    _fail("organization_duplicate_operation")
                decision_ids.add(decision.decision_id)
                for implementation in decision.implementations:
                    if implementation.implementation_id in implementation_ids:
                        _fail("organization_duplicate_operation")
                    implementation_ids.add(implementation.implementation_id)
                total_implementations += len(decision.implementations)
            total_decisions += len(candidate.collective_decisions)
        if total_operations > MAX_SNAPSHOT_OPERATIONS:
            _fail("organization_size_limit")
        if total_decisions > MAX_SNAPSHOT_COLLECTIVE_DECISIONS:
            _fail("organization_size_limit")
        if total_implementations > MAX_SNAPSHOT_COLLECTIVE_IMPLEMENTATIONS:
            _fail("organization_size_limit")
        windows = tuple(self.windows)
        if len(windows) > MAX_SNAPSHOT_WINDOWS:
            _fail("organization_size_limit")
        for window in windows:
            if type(window) is not OrganizationWindowRecord:
                _fail("organization_invalid_value")
            for candidate_id in window.candidate_ids:
                if candidate_id not in seen:
                    _fail("organization_unknown_candidate")
        object.__setattr__(
            self, "windows", tuple(sorted(windows, key=lambda item: item.window_index))
        )
        edges = tuple(self.edges)
        if len(edges) > MAX_SNAPSHOT_EDGES:
            _fail("organization_size_limit")
        for edge in edges:
            if type(edge) is not OrganizationLineageEdgeRecord:
                _fail("organization_invalid_value")
            for endpoint in (edge.from_id, edge.to_id):
                if endpoint is not None and endpoint not in seen:
                    _fail("organization_unknown_candidate")
        object.__setattr__(self, "edges", edges)
        rows = tuple(self.objective_rows)
        if len(rows) > MAX_SNAPSHOT_OBJECTIVE_ROWS:
            _fail("organization_size_limit")
        for row in rows:
            if type(row) is not OrganizationObjectiveRow:
                _fail("organization_invalid_value")
        object.__setattr__(self, "objective_rows", rows)
        if self.provenance_code not in PROVENANCE_CODES:
            _fail("organization_invalid_value")


def upgrade_organization_snapshot(
    snapshot: OrganizationSnapshot,
) -> OrganizationSnapshot:
    """Lift a v1 or v2 snapshot to v3 without mutating the input."""
    from dataclasses import replace

    if type(snapshot) is not OrganizationSnapshot:
        _fail("organization_invalid_value")
    if snapshot.schema_version == ORGANIZATION_SNAPSHOT_SCHEMA_VERSION:
        return snapshot
    if snapshot.schema_version not in (
        ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1,
        ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V2,
    ):
        _fail("organization_invalid_value")
    return replace(snapshot, schema_version=ORGANIZATION_SNAPSHOT_SCHEMA_VERSION)


def empty_organization_snapshot(
    run_id: str, input_revision: str, generated_tick: int
) -> OrganizationSnapshot:
    """Return an absent-but-valid snapshot shell for one completed run."""
    return OrganizationSnapshot(
        schema_version=ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
        policy_version=ORGANIZATION_SNAPSHOT_POLICY_VERSION,
        run_id=run_id,
        input_revision=input_revision,
        generated_tick=generated_tick,
        publication_id="",
        coverage=OrganizationCoverage(observed=0, expected=0, ratio=None),
    )
