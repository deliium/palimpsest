"""Owner-scoped delegation and representation beliefs.

Representation is one owner's belief that some agent may act or speak for a
principal. It is never authority, permission, legitimacy, or truth. Recognition
is derived from this owner's own observations, speech, support, opposition, and
read-only owner sidecars; it never grants a command or a world capability.

Analytical identity prefixes belong to ``analysis`` and must not be imported
here: analysis depends on exported rows, never on live cognition.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass, replace
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from types import MappingProxyType, SimpleNamespace
from typing import Any, Final, NoReturn, cast

__all__ = [
    "REPRESENTATION_CONFLICT_ID_PREFIX",
    "REPRESENTATION_ID_HEX_LEN",
    "REPRESENTATION_MANDATE_ID_PREFIX",
    "REPRESENTATION_POLICY_VERSION",
    "REPRESENTATION_POSITION_ID_PREFIX",
    "REPRESENTATION_REVOCATION_ID_PREFIX",
    "RepresentationConflict",
    "RepresentationConflictKind",
    "RepresentationDurationKind",
    "RepresentationError",
    "RepresentationLedger",
    "RepresentationMandate",
    "RepresentationPolicy",
    "RepresentationPosition",
    "RepresentationPositionStance",
    "RepresentationPrincipalKind",
    "RepresentationProvenance",
    "RepresentationRecognitionBasis",
    "RepresentationRevocation",
    "RepresentationRevocationKind",
    "RepresentationScopeKind",
    "RepresentationStatus",
    "default_representation_policy",
    "observation_region_anchors",
    "require_representation_id",
    "require_representation_scope_subject",
    "require_representation_token",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.delegation_representation"
)

REPRESENTATION_POLICY_VERSION: Final[str] = "delegation-representation.v1"
REPRESENTATION_ID_HEX_LEN: Final[int] = 16
REPRESENTATION_SEPARATOR: Final[str] = "\x1f"

REPRESENTATION_MANDATE_ID_PREFIX: Final[str] = "rmd-"
REPRESENTATION_POSITION_ID_PREFIX: Final[str] = "rmp-"
REPRESENTATION_REVOCATION_ID_PREFIX: Final[str] = "rmv-"
REPRESENTATION_CONFLICT_ID_PREFIX: Final[str] = "rmx-"

_MANDATE_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^rmd-[0-9a-f]{16}$")
_POSITION_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^rmp-[0-9a-f]{16}$")
_REVOCATION_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^rmv-[0-9a-f]{16}$")
_CONFLICT_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^rmx-[0-9a-f]{16}$")
_SCOPE_SUBJECT_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9_.:-]{1,32}$")
_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]*$")
_ORGANIZATION_CONCEPT_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^orgc-[0-9a-f]{16}$"
)
_CONFIDENCE_QUANTUM: Final[Decimal] = Decimal("0.000001")
_FORBIDDEN_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "truth",
        "verified",
        "legitimate",
        "authority",
        "permission",
        "allowed",
        "winner",
        "proxy",
        "mandate_valid",
    }
)


class RepresentationPrincipalKind(StrEnum):
    """Closed principal kinds. None creates an objective collective."""

    AGENT = "agent"
    ORGANIZATION = "organization"
    SETTLEMENT = "settlement"
    COALITION = "coalition"
    UNKNOWN = "unknown"


class RepresentationScopeKind(StrEnum):
    """Closed scope beliefs. No scope value is a permission."""

    SPEAK_FOR = "speak_for"
    NEGOTIATE = "negotiate"
    CARRY_MESSAGE = "carry_message"
    COORDINATE_PROJECT = "coordinate_project"
    TRANSACT = "transact"
    DECIDE = "decide"
    UNKNOWN = "unknown"


class RepresentationDurationKind(StrEnum):
    """Closed duration beliefs with deterministic expiry."""

    SINGLE_ACT = "single_act"
    OCCASION = "occasion"
    UNTIL_TICK = "until_tick"
    UNTIL_REVOKED = "until_revoked"
    UNKNOWN = "unknown"


class RepresentationStatus(StrEnum):
    """Closed derived status for one mandate."""

    CLAIMED = "claimed"
    RECOGNIZED = "recognized"
    CONTESTED = "contested"
    REJECTED = "rejected"
    REVOKED = "revoked"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"
    UNKNOWN = "unknown"


class RepresentationProvenance(StrEnum):
    """Closed provenance channel for one retained belief row."""

    SELF_DECLARED = "self_declared"
    PRINCIPAL_DECLARED = "principal_declared"
    COMMUNICATED = "communicated"
    WITNESSED_ACT = "witnessed_act"
    WRITTEN_RECORD = "written_record"
    OFFICE_BELIEF = "office_belief"
    COLLECTIVE_DECISION = "collective_decision"
    PROCEDURE_BELIEF = "procedure_belief"
    UNKNOWN = "unknown"


class RepresentationPositionStance(StrEnum):
    """Closed position stance. Opposition is legal and retained."""

    SUPPORT = "support"
    OPPOSE = "oppose"
    ABSTAIN = "abstain"
    UNKNOWN = "unknown"


class RepresentationRevocationKind(StrEnum):
    """Closed revocation kinds."""

    PRINCIPAL_REVOKED = "principal_revoked"
    REPRESENTATIVE_RESIGNED = "representative_resigned"
    COLLECTIVE_DECISION_REVOKED = "collective_decision_revoked"
    SCOPE_EXPIRED = "scope_expired"
    OFFICE_LOST = "office_lost"
    CONTESTED = "contested"
    UNKNOWN = "unknown"


class RepresentationRecognitionBasis(StrEnum):
    """Closed derived recognition basis. Never a legitimacy finding."""

    PRINCIPAL_DECLARATION = "principal_declaration"
    INDEPENDENT_SUPPORT = "independent_support"
    OFFICE_AUTHORITY = "office_authority"
    COLLECTIVE_DECISION = "collective_decision"
    WRITTEN_AUTHORIZATION = "written_authorization"
    NONE = "none"
    UNKNOWN = "unknown"


class RepresentationConflictKind(StrEnum):
    """Closed conflict kinds. Conflicts coexist and are never reconciled."""

    DUPLICATE_MANDATE = "duplicate_mandate"
    CONTRADICTORY_SCOPE = "contradictory_scope"
    CONFLICTING_PRINCIPAL = "conflicting_principal"
    REVOCATION_DISPUTE = "revocation_dispute"
    UNKNOWN = "unknown"


_REPRESENTATION_POLICY_VALUES: Final[Mapping[str, object]] = MappingProxyType(
    {
        "recognition_min_independent_roots": 2,
        "max_mandates": 32,
        "max_positions_per_mandate": 32,
        "max_revocations_per_mandate": 8,
        "max_conflicts_per_mandate": 8,
        "max_evidence_refs": 8,
        "max_decision_refs": 8,
        "max_office_refs": 8,
        "max_rule_refs": 8,
        "max_region_anchors": 16,
        "max_total_records": 320,
        "max_frame_chars": 384,
    }
)


@dataclass(frozen=True, slots=True)
class RepresentationPolicy:
    """Locked delegation-representation policy. Any change fails closed."""

    recognition_min_independent_roots: int = 2
    max_mandates: int = 32
    max_positions_per_mandate: int = 32
    max_revocations_per_mandate: int = 8
    max_conflicts_per_mandate: int = 8
    max_evidence_refs: int = 8
    max_decision_refs: int = 8
    max_office_refs: int = 8
    max_rule_refs: int = 8
    max_region_anchors: int = 16
    max_total_records: int = 320
    max_frame_chars: int = 384

    def __post_init__(self) -> None:
        for field in fields(type(self)):
            if field.name in _FORBIDDEN_FIELD_NAMES:
                raise RepresentationError("representation_policy_not_locked")
            if getattr(self, field.name) != _REPRESENTATION_POLICY_VALUES[field.name]:
                raise RepresentationError("representation_policy_not_locked")


def default_representation_policy() -> RepresentationPolicy:
    """Return the one locked policy value."""

    return RepresentationPolicy()


class RepresentationError(ValueError):
    """Stable-code representation violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str) -> NoReturn:
    raise RepresentationError(code)


def _digest(*parts: object) -> str:
    payload = REPRESENTATION_SEPARATOR.join(str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[
        :REPRESENTATION_ID_HEX_LEN
    ]


def require_representation_id(value: object, prefix: str) -> str:
    """Validate one owner-local record id against its closed prefix."""

    patterns = {
        REPRESENTATION_MANDATE_ID_PREFIX: _MANDATE_ID_PATTERN,
        REPRESENTATION_POSITION_ID_PREFIX: _POSITION_ID_PATTERN,
        REPRESENTATION_REVOCATION_ID_PREFIX: _REVOCATION_ID_PATTERN,
        REPRESENTATION_CONFLICT_ID_PREFIX: _CONFLICT_ID_PATTERN,
    }
    pattern = patterns.get(prefix)
    if pattern is None:
        _fail("representation_invalid_id")
    if type(value) is not str or pattern.match(value) is None:
        _fail("representation_invalid_id")
    return value


def require_representation_token(value: object, *, max_chars: int) -> str:
    """Validate one bounded opaque token. Never free text."""

    if (
        type(value) is not str
        or not value
        or len(value) > max_chars
        or value != value.strip()
        or _TOKEN_PATTERN.match(value) is None
    ):
        _fail("representation_invalid_token")
    return value


def require_representation_scope_subject(value: object) -> str:
    """Validate a lowercase bounded scope subject. ``none`` is reserved."""

    if (
        type(value) is not str
        or _SCOPE_SUBJECT_PATTERN.match(value) is None
        or value == "none"
    ):
        _fail("representation_invalid_scope")
    return value


def representation_mandate_id(
    owner_id: str,
    tick: int,
    principal_kind: RepresentationPrincipalKind,
    principal_ref: str | None,
    representative_id: str,
    scope_kind: RepresentationScopeKind,
    scope_subject: str | None,
    duration_kind: RepresentationDurationKind,
) -> str:
    """Mint a deterministic owner-local mandate id from creation evidence."""

    return REPRESENTATION_MANDATE_ID_PREFIX + _digest(
        "palimpsest.representation.mandate.v1",
        owner_id,
        tick,
        principal_kind.value,
        principal_ref or "none",
        representative_id,
        scope_kind.value,
        scope_subject or "none",
        duration_kind.value,
    )


def representation_position_id(
    owner_id: str,
    mandate_id: str,
    actor_id: str,
    tick: int,
    stance: RepresentationPositionStance,
    ordinal: int,
) -> str:
    """Mint a deterministic position id for one stance event."""

    return REPRESENTATION_POSITION_ID_PREFIX + _digest(
        "palimpsest.representation.position.v1",
        owner_id,
        mandate_id,
        actor_id,
        tick,
        stance.value,
        ordinal,
    )


def representation_revocation_id(
    owner_id: str,
    mandate_id: str,
    actor_id: str,
    tick: int,
    kind: RepresentationRevocationKind,
    ordinal: int,
) -> str:
    """Mint a deterministic revocation id for one revocation request."""

    return REPRESENTATION_REVOCATION_ID_PREFIX + _digest(
        "palimpsest.representation.revocation.v1",
        owner_id,
        mandate_id,
        actor_id,
        tick,
        kind.value,
        ordinal,
    )


def representation_conflict_id(
    owner_id: str,
    mandate_ids: tuple[str, ...],
    kind: RepresentationConflictKind,
    tick: int,
) -> str:
    """Mint a deterministic conflict id for one unordered mandate set."""

    return REPRESENTATION_CONFLICT_ID_PREFIX + _digest(
        "palimpsest.representation.conflict.v1",
        owner_id,
        REPRESENTATION_SEPARATOR.join(sorted(mandate_ids)),
        kind.value,
        tick,
    )


def _require_exact_bool(value: object, code: str) -> bool:
    if type(value) is not bool:
        _fail(code)
    return value


def _require_tick(value: object, code: str) -> int:
    if type(value) is not int or isinstance(value, bool) or value < 0:
        _fail(code)
    return value


def _quantize_confidence(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail("representation_invalid_confidence")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        _fail("representation_invalid_confidence")
    quantized = Decimal(str(number)).quantize(
        _CONFIDENCE_QUANTUM, rounding=ROUND_HALF_UP
    )
    result = float(quantized)
    return 0.0 if result == 0.0 else result


def _require_enum[EnumT: StrEnum](
    value: object, enum_type: type[EnumT], code: str
) -> EnumT:
    if type(value) is not enum_type:
        _fail(code)
    return value


def _require_ordered_tuple(value: object, code: str) -> tuple[object, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        _fail(code)
    return tuple(value)


def _require_bool(value: object) -> bool:
    return _require_exact_bool(value, "representation_invalid_record")


def _require_optional_token(value: object, *, max_chars: int = 128) -> str | None:
    if value is None:
        return None
    return require_representation_token(value, max_chars=max_chars)


def _require_local_evidence_ref(value: object) -> str:
    if type(value) is not str or not value.startswith(("evs-", "evw-", "evi-", "evc-")):
        _fail("representation_unknown_reference")
    return value


def _require_hex64(value: object) -> str:
    if type(value) is not str or len(value) != 64:
        _fail("representation_unknown_reference")
    if any(character not in "0123456789abcdef" for character in value):
        _fail("representation_unknown_reference")
    return value


def _require_rule_ref(value: object) -> str:
    if type(value) is not str or re.fullmatch(r"frl-[0-9a-f]{16}", value) is None:
        _fail("representation_unknown_reference")
    return value


def _require_sorted_unique(values: object, *, cap: int, code: str) -> tuple[str, ...]:
    items = _require_ordered_tuple(values, code)
    if len(items) > cap:
        _fail("representation_limit_exceeded")
    normalized = tuple(sorted({str(item) for item in items}))
    if len(normalized) != len(items):
        _fail(code)
    return normalized


def _reject_forbidden_fields(model: type[Any]) -> None:
    for field in fields(model):
        if field.name in _FORBIDDEN_FIELD_NAMES:
            _fail("representation_invalid_record")


@dataclass(frozen=True, slots=True)
class RepresentationMandate:
    """One owner's belief that a representative may act for a principal."""

    mandate_id: str
    principal_kind: RepresentationPrincipalKind
    principal_ref: str | None
    representative_id: str
    scope_kind: RepresentationScopeKind
    scope_subject: str | None
    duration_kind: RepresentationDurationKind
    start_tick: int
    end_tick: int | None
    provenance: RepresentationProvenance
    attributed_actor_id: str | None
    evidence_refs: tuple[str, ...]
    decision_refs: tuple[str, ...]
    office_refs: tuple[str, ...]
    rule_refs: tuple[str, ...]
    confidence: float
    principal_resolved: bool
    principal_declared: bool
    office_basis: bool
    decision_basis: bool
    written_basis: bool
    revoked: bool
    expired: bool
    superseded: bool
    status: RepresentationStatus
    recognition_basis: RepresentationRecognitionBasis
    revision: int

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        mandate_id = require_representation_id(
            self.mandate_id, REPRESENTATION_MANDATE_ID_PREFIX
        )
        principal_kind = _require_enum(
            self.principal_kind,
            RepresentationPrincipalKind,
            "representation_invalid_principal",
        )
        scope_kind = _require_enum(
            self.scope_kind, RepresentationScopeKind, "representation_invalid_scope"
        )
        duration_kind = _require_enum(
            self.duration_kind,
            RepresentationDurationKind,
            "representation_invalid_duration",
        )
        provenance = _require_enum(
            self.provenance,
            RepresentationProvenance,
            "representation_invalid_provenance",
        )
        status = _require_enum(
            self.status, RepresentationStatus, "representation_invalid_status"
        )
        basis = _require_enum(
            self.recognition_basis,
            RepresentationRecognitionBasis,
            "representation_invalid_status",
        )
        principal_ref = _require_optional_token(self.principal_ref)
        representative_id = require_representation_token(
            self.representative_id, max_chars=128
        )
        if principal_kind is RepresentationPrincipalKind.AGENT:
            if principal_ref is None:
                _fail("representation_invalid_principal")
            if principal_ref == representative_id:
                _fail("representation_invalid_principal")
        elif principal_kind in {
            RepresentationPrincipalKind.ORGANIZATION,
            RepresentationPrincipalKind.COALITION,
        }:
            if (
                principal_ref is None
                or _ORGANIZATION_CONCEPT_PATTERN.match(principal_ref) is None
            ):
                _fail("representation_invalid_principal")
        elif principal_kind is RepresentationPrincipalKind.SETTLEMENT:
            if principal_ref is None:
                _fail("representation_invalid_principal")
        else:
            if principal_ref is not None:
                _fail("representation_invalid_principal")
        if scope_kind is RepresentationScopeKind.UNKNOWN:
            if self.scope_subject is not None:
                _fail("representation_invalid_scope")
            scope_subject = None
        else:
            scope_subject = (
                None
                if self.scope_subject is None
                else require_representation_scope_subject(self.scope_subject)
            )
        start_tick = _require_tick(self.start_tick, "representation_invalid_record")
        end_tick = (
            None
            if self.end_tick is None
            else _require_tick(self.end_tick, "representation_invalid_duration")
        )
        if duration_kind is RepresentationDurationKind.SINGLE_ACT:
            if end_tick != start_tick:
                _fail("representation_invalid_duration")
        elif duration_kind is RepresentationDurationKind.OCCASION:
            if end_tick is None or end_tick < start_tick:
                _fail("representation_invalid_duration")
        elif duration_kind is RepresentationDurationKind.UNTIL_TICK:
            if end_tick is None or end_tick < start_tick:
                _fail("representation_invalid_duration")
        else:
            if end_tick is not None:
                _fail("representation_invalid_duration")
        attributed = _require_optional_token(self.attributed_actor_id)
        evidence_refs = _require_sorted_unique(
            self.evidence_refs,
            cap=default_representation_policy().max_evidence_refs,
            code="representation_invalid_record",
        )
        for ref in evidence_refs:
            _require_local_evidence_ref(ref)
        decision_refs = _require_sorted_unique(
            self.decision_refs,
            cap=default_representation_policy().max_decision_refs,
            code="representation_invalid_record",
        )
        for ref in decision_refs:
            _require_hex64(ref)
        office_refs = _require_sorted_unique(
            self.office_refs,
            cap=default_representation_policy().max_office_refs,
            code="representation_invalid_record",
        )
        for ref in office_refs:
            _require_hex64(ref)
        rule_refs = _require_sorted_unique(
            self.rule_refs,
            cap=default_representation_policy().max_rule_refs,
            code="representation_invalid_record",
        )
        for ref in rule_refs:
            _require_rule_ref(ref)
        principal_resolved = _require_bool(self.principal_resolved)
        principal_declared = _require_bool(self.principal_declared)
        office_basis = _require_bool(self.office_basis)
        decision_basis = _require_bool(self.decision_basis)
        written_basis = _require_bool(self.written_basis)
        revoked = _require_bool(self.revoked)
        expired = _require_bool(self.expired)
        superseded = _require_bool(self.superseded)
        if sum((revoked, expired, superseded)) > 1:
            _fail("representation_invalid_status")
        terminal_status = (
            RepresentationStatus.REVOKED
            if revoked
            else RepresentationStatus.EXPIRED
            if expired
            else RepresentationStatus.SUPERSEDED
            if superseded
            else None
        )
        if terminal_status is not None and status is not terminal_status:
            _fail("representation_invalid_status")
        if terminal_status is None and status in {
            RepresentationStatus.REVOKED,
            RepresentationStatus.EXPIRED,
            RepresentationStatus.SUPERSEDED,
        }:
            _fail("representation_invalid_status")
        if principal_kind is RepresentationPrincipalKind.UNKNOWN:
            if principal_resolved:
                _fail("representation_invalid_principal")
        revision = self.revision
        if type(revision) is not int or isinstance(revision, bool) or revision < 0:
            _fail("representation_invalid_record")
        object.__setattr__(self, "mandate_id", mandate_id)
        object.__setattr__(self, "principal_kind", principal_kind)
        object.__setattr__(self, "principal_ref", principal_ref)
        object.__setattr__(self, "representative_id", representative_id)
        object.__setattr__(self, "scope_kind", scope_kind)
        object.__setattr__(self, "scope_subject", scope_subject)
        object.__setattr__(self, "duration_kind", duration_kind)
        object.__setattr__(self, "start_tick", start_tick)
        object.__setattr__(self, "end_tick", end_tick)
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "attributed_actor_id", attributed)
        object.__setattr__(self, "evidence_refs", evidence_refs)
        object.__setattr__(self, "decision_refs", decision_refs)
        object.__setattr__(self, "office_refs", office_refs)
        object.__setattr__(self, "rule_refs", rule_refs)
        object.__setattr__(self, "confidence", _quantize_confidence(self.confidence))
        object.__setattr__(self, "principal_resolved", principal_resolved)
        object.__setattr__(self, "principal_declared", principal_declared)
        object.__setattr__(self, "office_basis", office_basis)
        object.__setattr__(self, "decision_basis", decision_basis)
        object.__setattr__(self, "written_basis", written_basis)
        object.__setattr__(self, "revoked", revoked)
        object.__setattr__(self, "expired", expired)
        object.__setattr__(self, "superseded", superseded)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "recognition_basis", basis)
        object.__setattr__(self, "revision", revision)


@dataclass(frozen=True, slots=True)
class RepresentationPosition:
    """One active or historical support/opposition/abstention belief."""

    position_id: str
    mandate_id: str
    actor_id: str
    stance: RepresentationPositionStance
    root_ref: str | None
    provenance: RepresentationProvenance
    tick: int
    active: bool

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self,
            "position_id",
            require_representation_id(
                self.position_id, REPRESENTATION_POSITION_ID_PREFIX
            ),
        )
        object.__setattr__(
            self,
            "mandate_id",
            require_representation_id(
                self.mandate_id, REPRESENTATION_MANDATE_ID_PREFIX
            ),
        )
        object.__setattr__(
            self,
            "actor_id",
            require_representation_token(self.actor_id, max_chars=128),
        )
        object.__setattr__(
            self,
            "stance",
            _require_enum(
                self.stance,
                RepresentationPositionStance,
                "representation_invalid_record",
            ),
        )
        object.__setattr__(self, "root_ref", _require_optional_token(self.root_ref))
        object.__setattr__(
            self,
            "provenance",
            _require_enum(
                self.provenance,
                RepresentationProvenance,
                "representation_invalid_provenance",
            ),
        )
        object.__setattr__(
            self, "tick", _require_tick(self.tick, "representation_invalid_record")
        )
        object.__setattr__(self, "active", _require_bool(self.active))


@dataclass(frozen=True, slots=True)
class RepresentationRevocation:
    """One retained revocation request. Never a deletion."""

    revocation_id: str
    mandate_id: str
    actor_id: str
    kind: RepresentationRevocationKind
    provenance: RepresentationProvenance
    tick: int
    contested: bool

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self,
            "revocation_id",
            require_representation_id(
                self.revocation_id, REPRESENTATION_REVOCATION_ID_PREFIX
            ),
        )
        object.__setattr__(
            self,
            "mandate_id",
            require_representation_id(
                self.mandate_id, REPRESENTATION_MANDATE_ID_PREFIX
            ),
        )
        object.__setattr__(
            self,
            "actor_id",
            require_representation_token(self.actor_id, max_chars=128),
        )
        object.__setattr__(
            self,
            "kind",
            _require_enum(
                self.kind,
                RepresentationRevocationKind,
                "representation_invalid_record",
            ),
        )
        object.__setattr__(
            self,
            "provenance",
            _require_enum(
                self.provenance,
                RepresentationProvenance,
                "representation_invalid_provenance",
            ),
        )
        object.__setattr__(
            self, "tick", _require_tick(self.tick, "representation_invalid_record")
        )
        object.__setattr__(self, "contested", _require_bool(self.contested))


@dataclass(frozen=True, slots=True)
class RepresentationConflict:
    """One retained unresolved conflict among mandates."""

    conflict_id: str
    mandate_ids: tuple[str, ...]
    kind: RepresentationConflictKind
    status: str
    tick: int

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self,
            "conflict_id",
            require_representation_id(
                self.conflict_id, REPRESENTATION_CONFLICT_ID_PREFIX
            ),
        )
        mandate_ids = _require_ordered_tuple(
            self.mandate_ids, "representation_invalid_record"
        )
        if len(mandate_ids) < 1:
            _fail("representation_invalid_record")
        normalized = tuple(
            sorted(
                {
                    require_representation_id(item, REPRESENTATION_MANDATE_ID_PREFIX)
                    for item in mandate_ids
                }
            )
        )
        if len(normalized) != len(mandate_ids):
            _fail("representation_invalid_record")
        kind = _require_enum(
            self.kind,
            RepresentationConflictKind,
            "representation_invalid_record",
        )
        if kind is not RepresentationConflictKind.REVOCATION_DISPUTE:
            if len(normalized) < 2:
                _fail("representation_invalid_record")
        object.__setattr__(self, "mandate_ids", normalized)
        object.__setattr__(self, "kind", kind)
        if self.status != "unresolved":
            _fail("representation_invalid_record")
        object.__setattr__(
            self, "tick", _require_tick(self.tick, "representation_invalid_record")
        )


def _ordered_records(value: object) -> tuple[object, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        _fail("representation_invalid_record")
    return tuple(value)


def _require_owner_id(value: object) -> str:
    token = getattr(value, "value", value)
    return require_representation_token(token, max_chars=128)


@dataclass(frozen=True, slots=True)
class RepresentationLedger:
    """One owner's representation beliefs. ``None`` means the mode is off."""

    owner_id: str
    mandates: tuple[RepresentationMandate, ...] = ()
    positions: tuple[RepresentationPosition, ...] = ()
    revocations: tuple[RepresentationRevocation, ...] = ()
    conflicts: tuple[RepresentationConflict, ...] = ()
    region_anchors: tuple[str, ...] = ()
    notices: tuple[str, ...] = ()
    policy_version: str = REPRESENTATION_POLICY_VERSION
    first_tick: int = 0
    last_tick: int = 0
    pruned_mandates: int = 0
    pruned_positions: int = 0
    pruned_revocations: int = 0
    pruned_conflicts: int = 0
    coverage: str = "complete"

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        owner = _require_owner_id(self.owner_id)
        if self.policy_version != REPRESENTATION_POLICY_VERSION:
            _fail("representation_policy_version_mismatch")
        mandates = _ordered_records(self.mandates)
        positions = _ordered_records(self.positions)
        revocations = _ordered_records(self.revocations)
        conflicts = _ordered_records(self.conflicts)
        mandate_by_id: dict[str, RepresentationMandate] = {}
        for row in mandates:
            if type(row) is not RepresentationMandate:
                _fail("representation_invalid_record")
            if row.mandate_id in mandate_by_id:
                _fail("representation_duplicate_id")
            mandate_by_id[row.mandate_id] = row
        position_ids: set[str] = set()
        for row in positions:
            if type(row) is not RepresentationPosition:
                _fail("representation_invalid_record")
            if row.position_id in position_ids:
                _fail("representation_duplicate_id")
            position_ids.add(row.position_id)
            if row.mandate_id not in mandate_by_id:
                _fail("representation_unknown_reference")
        revocation_ids: set[str] = set()
        for row in revocations:
            if type(row) is not RepresentationRevocation:
                _fail("representation_invalid_record")
            if row.revocation_id in revocation_ids:
                _fail("representation_duplicate_id")
            revocation_ids.add(row.revocation_id)
            if row.mandate_id not in mandate_by_id:
                _fail("representation_unknown_reference")
        conflict_ids: set[str] = set()
        for row in conflicts:
            if type(row) is not RepresentationConflict:
                _fail("representation_invalid_record")
            if row.conflict_id in conflict_ids:
                _fail("representation_duplicate_id")
            conflict_ids.add(row.conflict_id)
            for mandate_id in row.mandate_ids:
                if mandate_id not in mandate_by_id:
                    _fail("representation_unknown_reference")
        anchors = _require_sorted_unique(
            self.region_anchors,
            cap=default_representation_policy().max_region_anchors,
            code="representation_invalid_record",
        )
        first_tick = _require_tick(self.first_tick, "representation_invalid_record")
        last_tick = _require_tick(self.last_tick, "representation_invalid_record")
        if last_tick < first_tick:
            _fail("representation_tick_regression")
        for item in (*mandates, *positions, *revocations, *conflicts):
            tick = getattr(item, "tick", getattr(item, "start_tick", 0))
            if tick < first_tick or tick > last_tick:
                _fail("representation_tick_regression")
        notices = _require_ordered_tuple(self.notices, "representation_invalid_record")
        normalized_notices = tuple(
            sorted(
                {require_representation_token(item, max_chars=64) for item in notices}
            )
        )
        for name in (
            "pruned_mandates",
            "pruned_positions",
            "pruned_revocations",
            "pruned_conflicts",
        ):
            value = getattr(self, name)
            if type(value) is not int or isinstance(value, bool) or value < 0:
                _fail("representation_invalid_record")
        if self.coverage not in {"complete", "partial"}:
            _fail("representation_invalid_record")
        if (
            self.pruned_mandates
            or self.pruned_positions
            or self.pruned_revocations
            or self.pruned_conflicts
            or "representation_truncated" in normalized_notices
        ) and self.coverage != "partial":
            _fail("representation_invalid_record")
        object.__setattr__(self, "owner_id", owner)
        object.__setattr__(
            self,
            "mandates",
            tuple(sorted(mandates, key=lambda row: (row.start_tick, row.mandate_id))),
        )
        object.__setattr__(
            self,
            "positions",
            tuple(sorted(positions, key=lambda row: (row.tick, row.position_id))),
        )
        object.__setattr__(
            self,
            "revocations",
            tuple(sorted(revocations, key=lambda row: (row.tick, row.revocation_id))),
        )
        object.__setattr__(
            self,
            "conflicts",
            tuple(sorted(conflicts, key=lambda row: (row.tick, row.conflict_id))),
        )
        object.__setattr__(self, "region_anchors", anchors)
        object.__setattr__(self, "notices", normalized_notices)
        object.__setattr__(self, "first_tick", first_tick)
        object.__setattr__(self, "last_tick", last_tick)
        view = SimpleNamespace(
            owner_id=owner,
            positions=tuple(
                sorted(positions, key=lambda row: (row.tick, row.position_id))
            ),
        )
        for mandate in mandates:
            mandate = cast(RepresentationMandate, mandate)
            support = _position_roots(
                view, mandate.mandate_id, RepresentationPositionStance.SUPPORT
            )
            opposition = _position_roots(
                view, mandate.mandate_id, RepresentationPositionStance.OPPOSE
            )
            status, basis = appraise_representation_recognition(
                principal_kind=mandate.principal_kind,
                principal_resolved=mandate.principal_resolved,
                principal_declared=mandate.principal_declared,
                support_roots=support,
                opposition_roots=opposition,
                office_basis=mandate.office_basis,
                decision_basis=mandate.decision_basis,
                written_basis=mandate.written_basis,
                revoked=mandate.revoked,
                expired=mandate.expired,
                superseded=mandate.superseded,
            )
            if mandate.status is not status or mandate.recognition_basis is not basis:
                _fail("representation_status_mismatch")


def empty_representation_ledger(
    owner_id: object, *, tick: int = 0
) -> RepresentationLedger:
    """Return one enabled-but-empty ledger."""

    owner = getattr(owner_id, "value", owner_id)
    if type(owner) is not str or not owner:
        _fail("representation_invalid_owner")
    return RepresentationLedger(owner_id=owner, first_tick=tick, last_tick=tick)


def require_owner_representation(ledger: object, owner_id: object) -> None:
    """Reject a foreign or mistyped ledger. ``None`` passes."""

    if ledger is None:
        return
    owner = getattr(owner_id, "value", owner_id)
    if type(ledger) is not RepresentationLedger:
        raise TypeError("representation must be RepresentationLedger")
    if type(owner) is not str or ledger.owner_id != owner:
        _fail("representation_invalid_owner")


def representation_ledger_digest(ledger: RepresentationLedger) -> str:
    """Return a canonical digest over one owner's representation beliefs."""

    if type(ledger) is not RepresentationLedger:
        raise TypeError("ledger must be RepresentationLedger")
    payload = [
        ledger.owner_id,
        ledger.policy_version,
        str(ledger.first_tick),
        str(ledger.last_tick),
        ledger.coverage,
        REPRESENTATION_SEPARATOR.join(ledger.region_anchors),
        REPRESENTATION_SEPARATOR.join(ledger.notices),
        (
            f"{ledger.pruned_mandates}:{ledger.pruned_positions}:"
            f"{ledger.pruned_revocations}:{ledger.pruned_conflicts}"
        ),
    ]
    for row in ledger.mandates:
        payload.append(
            REPRESENTATION_SEPARATOR.join(
                (
                    row.mandate_id,
                    row.principal_kind.value,
                    row.principal_ref or "none",
                    row.representative_id,
                    row.scope_kind.value,
                    row.scope_subject or "none",
                    row.duration_kind.value,
                    str(row.start_tick),
                    "none" if row.end_tick is None else str(row.end_tick),
                    row.provenance.value,
                    row.attributed_actor_id or "none",
                    ",".join(row.evidence_refs),
                    ",".join(row.decision_refs),
                    ",".join(row.office_refs),
                    ",".join(row.rule_refs),
                    f"{row.confidence:.6f}",
                    str(row.principal_resolved),
                    str(row.principal_declared),
                    str(row.office_basis),
                    str(row.decision_basis),
                    str(row.written_basis),
                    str(row.revoked),
                    str(row.expired),
                    str(row.superseded),
                    row.status.value,
                    row.recognition_basis.value,
                    str(row.revision),
                )
            )
        )
    for position in ledger.positions:
        payload.append(
            REPRESENTATION_SEPARATOR.join(
                (
                    position.position_id,
                    position.mandate_id,
                    position.actor_id,
                    position.stance.value,
                    position.root_ref or "none",
                    position.provenance.value,
                    str(position.tick),
                    str(position.active),
                )
            )
        )
    for revocation in ledger.revocations:
        payload.append(
            REPRESENTATION_SEPARATOR.join(
                (
                    revocation.revocation_id,
                    revocation.mandate_id,
                    revocation.actor_id,
                    revocation.kind.value,
                    revocation.provenance.value,
                    str(revocation.tick),
                    str(revocation.contested),
                )
            )
        )
    for conflict in ledger.conflicts:
        payload.append(
            REPRESENTATION_SEPARATOR.join(
                (
                    conflict.conflict_id,
                    ",".join(conflict.mandate_ids),
                    conflict.kind.value,
                    conflict.status,
                    str(conflict.tick),
                )
            )
        )
    return hashlib.sha256(
        REPRESENTATION_SEPARATOR.join(payload).encode("utf-8")
    ).hexdigest()


def _subject_key(mandate: RepresentationMandate) -> tuple[object, ...]:
    return (
        mandate.principal_kind,
        mandate.principal_ref,
        mandate.scope_kind,
        mandate.scope_subject,
    )


def _active_positions(
    ledger: RepresentationLedger,
) -> tuple[RepresentationPosition, ...]:
    return tuple(row for row in ledger.positions if row.active)


def _position_roots(
    ledger: object, mandate_id: str, stance: RepresentationPositionStance
) -> tuple[str, ...]:
    owner = str(getattr(ledger, "owner_id", ""))
    roots: set[str] = set()
    for row in getattr(ledger, "positions", ()):
        if row.mandate_id != mandate_id or row.stance is not stance:
            continue
        if not row.active:
            continue
        if row.actor_id == owner:
            continue
        roots.add(row.root_ref or f"actor:{row.actor_id}")
    return tuple(sorted(roots))


def appraise_representation_recognition(
    *,
    principal_kind: RepresentationPrincipalKind,
    principal_resolved: bool,
    principal_declared: bool,
    support_roots: tuple[str, ...],
    opposition_roots: tuple[str, ...],
    office_basis: bool,
    decision_basis: bool,
    written_basis: bool,
    revoked: bool,
    expired: bool,
    superseded: bool,
) -> tuple[RepresentationStatus, RepresentationRecognitionBasis]:
    """Derive one status and basis from retained owner beliefs only."""

    if superseded:
        return RepresentationStatus.SUPERSEDED, RepresentationRecognitionBasis.NONE
    if revoked:
        return RepresentationStatus.REVOKED, RepresentationRecognitionBasis.NONE
    if expired:
        return RepresentationStatus.EXPIRED, RepresentationRecognitionBasis.NONE
    if principal_kind is RepresentationPrincipalKind.UNKNOWN:
        return RepresentationStatus.UNKNOWN, RepresentationRecognitionBasis.NONE
    if not principal_resolved:
        return RepresentationStatus.CLAIMED, RepresentationRecognitionBasis.NONE
    if principal_declared:
        return (
            RepresentationStatus.RECOGNIZED,
            RepresentationRecognitionBasis.PRINCIPAL_DECLARATION,
        )
    support = len(set(support_roots))
    opposition = len(set(opposition_roots))
    if office_basis and support >= 1:
        return (
            RepresentationStatus.RECOGNIZED,
            RepresentationRecognitionBasis.OFFICE_AUTHORITY,
        )
    if decision_basis and support >= 1:
        return (
            RepresentationStatus.RECOGNIZED,
            RepresentationRecognitionBasis.COLLECTIVE_DECISION,
        )
    if written_basis and support >= 1:
        return (
            RepresentationStatus.RECOGNIZED,
            RepresentationRecognitionBasis.WRITTEN_AUTHORIZATION,
        )
    if support >= 2 and opposition < support:
        return (
            RepresentationStatus.RECOGNIZED,
            RepresentationRecognitionBasis.INDEPENDENT_SUPPORT,
        )
    if opposition and support == 0:
        return RepresentationStatus.REJECTED, RepresentationRecognitionBasis.NONE
    if opposition > support and opposition >= 1:
        return RepresentationStatus.REJECTED, RepresentationRecognitionBasis.NONE
    if opposition and support:
        return RepresentationStatus.CONTESTED, RepresentationRecognitionBasis.NONE
    return RepresentationStatus.CLAIMED, RepresentationRecognitionBasis.NONE


def _derive_mandate(
    ledger: object,
    mandate: RepresentationMandate,
    *,
    principal_resolved: bool | None = None,
    office_basis: bool | None = None,
    decision_basis: bool | None = None,
    written_basis: bool | None = None,
    office_refs: tuple[str, ...] | None = None,
    decision_refs: tuple[str, ...] | None = None,
    rule_refs: tuple[str, ...] | None = None,
    revoked: bool | None = None,
    expired: bool | None = None,
    superseded: bool | None = None,
) -> RepresentationMandate:
    resolved = (
        mandate.principal_resolved if principal_resolved is None else principal_resolved
    )
    office = mandate.office_basis if office_basis is None else office_basis
    decision = mandate.decision_basis if decision_basis is None else decision_basis
    written = mandate.written_basis if written_basis is None else written_basis
    support = _position_roots(
        ledger, mandate.mandate_id, RepresentationPositionStance.SUPPORT
    )
    opposition = _position_roots(
        ledger, mandate.mandate_id, RepresentationPositionStance.OPPOSE
    )
    status, basis = appraise_representation_recognition(
        principal_kind=mandate.principal_kind,
        principal_resolved=resolved,
        principal_declared=mandate.principal_declared,
        support_roots=support,
        opposition_roots=opposition,
        office_basis=office,
        decision_basis=decision,
        written_basis=written,
        revoked=mandate.revoked if revoked is None else revoked,
        expired=mandate.expired if expired is None else expired,
        superseded=mandate.superseded if superseded is None else superseded,
    )
    return RepresentationMandate(
        mandate_id=mandate.mandate_id,
        principal_kind=mandate.principal_kind,
        principal_ref=mandate.principal_ref,
        representative_id=mandate.representative_id,
        scope_kind=mandate.scope_kind,
        scope_subject=mandate.scope_subject,
        duration_kind=mandate.duration_kind,
        start_tick=mandate.start_tick,
        end_tick=mandate.end_tick,
        provenance=mandate.provenance,
        attributed_actor_id=mandate.attributed_actor_id,
        evidence_refs=mandate.evidence_refs,
        decision_refs=(
            mandate.decision_refs if decision_refs is None else decision_refs
        ),
        office_refs=mandate.office_refs if office_refs is None else office_refs,
        rule_refs=mandate.rule_refs if rule_refs is None else rule_refs,
        confidence=mandate.confidence,
        principal_resolved=resolved,
        principal_declared=mandate.principal_declared,
        office_basis=office,
        decision_basis=decision,
        written_basis=written,
        revoked=mandate.revoked if revoked is None else revoked,
        expired=mandate.expired if expired is None else expired,
        superseded=mandate.superseded if superseded is None else superseded,
        status=status,
        recognition_basis=basis,
        revision=mandate.revision,
    )


def representation_status(
    ledger: RepresentationLedger, mandate_id: str
) -> RepresentationStatus:
    """Return the derived status for one mandate id."""

    for mandate in ledger.mandates:
        if mandate.mandate_id == mandate_id:
            return mandate.status
    _fail("representation_unknown_mandate")


def _limit(
    ledger: RepresentationLedger, policy: RepresentationPolicy
) -> RepresentationLedger:
    mandates = list(ledger.mandates)
    positions = list(ledger.positions)
    revocations = list(ledger.revocations)
    conflicts = list(ledger.conflicts)
    notices = set(ledger.notices)
    pruned_mandates = ledger.pruned_mandates
    pruned_positions = ledger.pruned_positions
    pruned_revocations = ledger.pruned_revocations
    pruned_conflicts = ledger.pruned_conflicts

    def drop_mandate(mandate_id: str) -> None:
        nonlocal pruned_positions, pruned_revocations, pruned_conflicts
        mandates[:] = [row for row in mandates if row.mandate_id != mandate_id]
        kept = [row for row in positions if row.mandate_id != mandate_id]
        pruned_positions += len(positions) - len(kept)
        positions[:] = kept
        kept_revocations = [row for row in revocations if row.mandate_id != mandate_id]
        pruned_revocations += len(revocations) - len(kept_revocations)
        revocations[:] = kept_revocations
        kept_conflicts = [row for row in conflicts if mandate_id not in row.mandate_ids]
        pruned_conflicts += len(conflicts) - len(kept_conflicts)
        conflicts[:] = kept_conflicts

    terminal = [
        row
        for row in sorted(mandates, key=lambda row: (row.start_tick, row.mandate_id))
        if row.status
        in {
            RepresentationStatus.SUPERSEDED,
            RepresentationStatus.EXPIRED,
        }
    ]
    unresolved = [
        row for row in sorted(conflicts, key=lambda row: (row.tick, row.conflict_id))
    ]
    droppable = [
        row
        for row in sorted(mandates, key=lambda row: (row.start_tick, row.mandate_id))
        if row.status
        in {
            RepresentationStatus.CLAIMED,
            RepresentationStatus.CONTESTED,
            RepresentationStatus.REJECTED,
        }
        and not any(
            position.mandate_id == row.mandate_id
            and position.active
            and position.stance is RepresentationPositionStance.SUPPORT
            for position in positions
        )
    ]
    while len(mandates) > policy.max_mandates and terminal:
        drop_mandate(terminal.pop(0).mandate_id)
        pruned_mandates += 1
        notices.add("representation_truncated")
    while len(mandates) > policy.max_mandates and droppable:
        drop_mandate(droppable.pop(0).mandate_id)
        pruned_mandates += 1
        notices.add("representation_truncated")
    while len(conflicts) > policy.max_conflicts_per_mandate and unresolved:
        removed = unresolved.pop(0)
        conflicts = [row for row in conflicts if row != removed]
        pruned_conflicts += 1
        notices.add("representation_truncated")
    if len(mandates) > policy.max_mandates:
        notices.add("representation_capacity_reached")
    per_mandate_positions: dict[str, int] = {}
    kept_positions: list[RepresentationPosition] = []
    for position in positions:
        count = per_mandate_positions.get(position.mandate_id, 0)
        if count >= policy.max_positions_per_mandate:
            pruned_positions += 1
            notices.add("representation_truncated")
            continue
        per_mandate_positions[position.mandate_id] = count + 1
        kept_positions.append(position)
    positions = kept_positions
    per_mandate_revocations: dict[str, int] = {}
    kept_revocations = []
    for revocation in revocations:
        count = per_mandate_revocations.get(revocation.mandate_id, 0)
        if count >= policy.max_revocations_per_mandate:
            pruned_revocations += 1
            notices.add("representation_truncated")
            continue
        per_mandate_revocations[revocation.mandate_id] = count + 1
        kept_revocations.append(revocation)
    revocations = kept_revocations
    total = len(mandates) + len(positions) + len(revocations) + len(conflicts)
    while total > policy.max_total_records and droppable:
        drop_mandate(droppable.pop(0).mandate_id)
        pruned_mandates += 1
        notices.add("representation_truncated")
        total = len(mandates) + len(positions) + len(revocations) + len(conflicts)
    if total > policy.max_total_records:
        notices.add("representation_capacity_reached")
    coverage = (
        "partial"
        if any(
            (
                pruned_mandates,
                pruned_positions,
                pruned_revocations,
                pruned_conflicts,
            )
        )
        or "representation_truncated" in notices
        else "complete"
    )
    return RepresentationLedger(
        owner_id=ledger.owner_id,
        mandates=tuple(mandates),
        positions=tuple(positions),
        revocations=tuple(revocations),
        conflicts=tuple(conflicts),
        region_anchors=ledger.region_anchors,
        notices=tuple(notices),
        policy_version=ledger.policy_version,
        first_tick=ledger.first_tick,
        last_tick=ledger.last_tick,
        pruned_mandates=pruned_mandates,
        pruned_positions=pruned_positions,
        pruned_revocations=pruned_revocations,
        pruned_conflicts=pruned_conflicts,
        coverage=coverage,
    )


def enforce_representation_limits(
    ledger: RepresentationLedger, *, policy: RepresentationPolicy | None = None
) -> RepresentationLedger:
    """Apply deterministic, recognition-preserving truncation."""

    if type(ledger) is not RepresentationLedger:
        raise TypeError("ledger must be RepresentationLedger")
    active = policy or default_representation_policy()
    if type(active) is not RepresentationPolicy:
        raise TypeError("policy must be RepresentationPolicy")
    limited = _limit(ledger, active)
    if limited.coverage == "partial" and limited.pruned_mandates:
        _LOG.warning(
            "representation_truncated mandates=%d positions=%d",
            limited.pruned_mandates,
            limited.pruned_positions,
        )
    return limited


def _collective_ids(organization_concepts: object | None) -> frozenset[str]:
    if organization_concepts is None:
        return frozenset()
    return frozenset(
        str(getattr(concept, "organization_id", ""))
        for concept in getattr(organization_concepts, "concepts", ())
        if getattr(concept, "organization_id", None)
    )


def _office_ids(offices: object | None) -> frozenset[str]:
    if offices is None:
        return frozenset()
    return frozenset(
        str(getattr(office, "office_id", ""))
        for office in getattr(offices, "offices", ())
        if getattr(office, "office_id", None)
    )


def _decision_ids(collective_decisions: object | None) -> frozenset[str]:
    if collective_decisions is None:
        return frozenset()
    return frozenset(
        str(getattr(proposal, "proposal_id", ""))
        for proposal in getattr(collective_decisions, "proposals", ())
        if getattr(proposal, "proposal_id", None)
    )


def _derive_all(
    mandates: Mapping[str, RepresentationMandate],
    positions: Mapping[str, RepresentationPosition],
    owner: str,
) -> dict[str, RepresentationMandate]:
    view = SimpleNamespace(owner_id=owner, positions=tuple(positions.values()))
    return {key: _derive_mandate(view, mandate) for key, mandate in mandates.items()}


def resolve_representation_principal(
    *,
    mandate: RepresentationMandate,
    organization_concepts: object | None,
    region_anchors: Sequence[str],
) -> bool:
    """Resolve one principal against this owner's own anchors only."""

    if type(mandate) is not RepresentationMandate:
        raise TypeError("mandate must be RepresentationMandate")
    if mandate.principal_kind is RepresentationPrincipalKind.AGENT:
        return mandate.principal_ref is not None
    if mandate.principal_kind in {
        RepresentationPrincipalKind.ORGANIZATION,
        RepresentationPrincipalKind.COALITION,
    }:
        return mandate.principal_ref in _collective_ids(organization_concepts)
    if mandate.principal_kind is RepresentationPrincipalKind.SETTLEMENT:
        return mandate.principal_ref in set(region_anchors)
    return False


def observation_region_anchors(observation: object | None) -> tuple[str, ...]:
    """Return owner-visible region anchors without exposing private helpers."""

    return _observation_region_anchors(observation)


def _observation_region_anchors(observation: object | None) -> tuple[str, ...]:
    if observation is None:
        return ()
    anchors: set[str] = set()
    regional = getattr(observation, "regional_context", None)
    region_id = getattr(regional, "region_id", None)
    if type(region_id) is str and region_id:
        anchors.add(region_id)
    self_body = getattr(observation, "self_body", None)
    journey = getattr(self_body, "journey", None)
    for name in ("origin_region_id", "destination_region_id"):
        value = getattr(journey, name, None)
        if type(value) is str and value:
            anchors.add(value)
    for exit_ in getattr(observation, "exits", ()):
        value = getattr(exit_, "destination_region_id", None)
        if type(value) is str and value:
            anchors.add(value)
    return tuple(sorted(anchors))


def _upsert_position(
    positions: dict[str, RepresentationPosition],
    *,
    owner_id: str,
    mandate_id: str,
    actor_id: str,
    stance: RepresentationPositionStance,
    provenance: RepresentationProvenance,
    tick: int,
    root_ref: str | None,
) -> None:
    for key, row in tuple(positions.items()):
        if row.mandate_id == mandate_id and row.actor_id == actor_id and row.active:
            positions[key] = replace(row, active=False)
    ordinal = len(positions)
    position_id = representation_position_id(
        owner_id, mandate_id, actor_id, tick, stance, ordinal
    )
    positions[position_id] = RepresentationPosition(
        position_id=position_id,
        mandate_id=mandate_id,
        actor_id=actor_id,
        stance=stance,
        root_ref=root_ref,
        provenance=provenance,
        tick=tick,
        active=True,
    )


def _frame_key(frame: object) -> tuple[object, ...]:
    return tuple(
        getattr(frame, name, None)
        for name in (
            "act",
            "mandate_ref",
            "principal_kind",
            "principal_ref",
            "representative_ref",
            "scope_kind",
            "scope_subject",
            "duration_kind",
            "end_tick",
            "provenance",
            "revision",
            "actor_ref",
        )
    )


_FORBIDDEN_OBJECT_TYPES: Final[frozenset[str]] = frozenset(
    {
        "WorldEvent",
        "WorldState",
        "PhysicalRules",
        "MetricDocument",
        "AgentCommand",
        "EventStore",
        "WorldEngine",
        "ActionSubmission",
    }
)


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
            _fail("representation_forbidden_input")
        owner_token = getattr(item, "owner_id", None)
        owner_value = getattr(owner_token, "value", owner_token)
        if type(owner_value) is str and owner_value and owner_value != owner:
            _fail("representation_forbidden_input")
        if type(item) is RepresentationLedger:
            continue
        if is_dataclass(item) and not isinstance(item, type):
            stack.extend(getattr(item, field.name) for field in fields(item))
        elif isinstance(item, Mapping):
            stack.extend(item.keys())
            stack.extend(item.values())
        elif isinstance(item, (tuple, list, set, frozenset)):
            stack.extend(item)


def _mandate_draft(
    *,
    owner_id: str,
    tick: int,
    principal_kind: RepresentationPrincipalKind,
    principal_ref: str | None,
    representative_id: str,
    scope_kind: RepresentationScopeKind,
    scope_subject: str | None,
    duration_kind: RepresentationDurationKind,
    end_tick: int | None,
    provenance: RepresentationProvenance,
    attributed_actor_id: str | None,
    principal_declared: bool = False,
    confidence: float = 0.5,
    revision: int = 0,
) -> RepresentationMandate:
    mandate_id = representation_mandate_id(
        owner_id,
        tick,
        principal_kind,
        principal_ref,
        representative_id,
        scope_kind,
        scope_subject,
        duration_kind,
    )
    status, basis = appraise_representation_recognition(
        principal_kind=principal_kind,
        principal_resolved=(principal_kind is not RepresentationPrincipalKind.UNKNOWN),
        principal_declared=principal_declared,
        support_roots=(),
        opposition_roots=(),
        office_basis=False,
        decision_basis=False,
        written_basis=False,
        revoked=False,
        expired=False,
        superseded=False,
    )
    return RepresentationMandate(
        mandate_id=mandate_id,
        principal_kind=principal_kind,
        principal_ref=principal_ref,
        representative_id=representative_id,
        scope_kind=scope_kind,
        scope_subject=scope_subject,
        duration_kind=duration_kind,
        start_tick=tick,
        end_tick=end_tick,
        provenance=provenance,
        attributed_actor_id=attributed_actor_id,
        evidence_refs=(),
        decision_refs=(),
        office_refs=(),
        rule_refs=(),
        confidence=confidence,
        principal_resolved=(principal_kind is not RepresentationPrincipalKind.UNKNOWN),
        principal_declared=principal_declared,
        office_basis=False,
        decision_basis=False,
        written_basis=False,
        revoked=False,
        expired=False,
        superseded=False,
        status=status,
        recognition_basis=basis,
        revision=revision,
    )


def _office_refs_for(offices: object | None, representative_id: str) -> tuple[str, ...]:
    if offices is None:
        return ()
    refs: set[str] = set()
    for office in getattr(offices, "offices", ()):
        for claim in getattr(office, "occupants", ()):
            occupant = getattr(getattr(claim, "occupant_id", None), "value", None)
            status = getattr(getattr(claim, "status", None), "value", None)
            if occupant == representative_id and status in {
                "candidate",
                "preferred",
                "recognized",
            }:
                office_id = getattr(office, "office_id", None)
                if type(office_id) is str:
                    refs.add(office_id)
    return tuple(sorted(refs))


def _decision_refs_for(
    collective_decisions: object | None,
    principal_ref: str | None,
    representative_id: str,
) -> tuple[str, ...]:
    if collective_decisions is None:
        return ()
    refs: set[str] = set()
    positions = tuple(getattr(collective_decisions, "positions", ()))
    for proposal in getattr(collective_decisions, "proposals", ()):
        proposal_id = getattr(proposal, "proposal_id", None)
        if type(proposal_id) is not str or len(proposal_id) != 64:
            continue
        supporters = {
            getattr(getattr(position, "actor_id", None), "value", None)
            for position in positions
            if getattr(position, "proposal_ref", None)
            == getattr(proposal, "proposal_ref", None)
            and getattr(getattr(position, "stance", None), "value", None) == "support"
        }
        if principal_ref is not None and principal_ref not in supporters:
            continue
        implemented = any(
            getattr(getattr(outcome, "actor_id", None), "value", None)
            == representative_id
            and getattr(getattr(outcome, "kind", None), "value", None)
            in {"adopted", "effected", "attempted"}
            and getattr(outcome, "proposal_ref", None)
            == getattr(proposal, "proposal_ref", None)
            for outcome in getattr(collective_decisions, "outcomes", ())
        )
        if implemented or representative_id in supporters:
            refs.add(proposal_id)
    return tuple(sorted(refs))


def _written_rule_refs_for(
    formal_rules: object | None, scope_subject: str | None
) -> tuple[str, ...]:
    if formal_rules is None:
        return ()
    refs: set[str] = set()
    for rule in getattr(formal_rules, "rules", ()):
        status = getattr(getattr(rule, "status", None), "value", None)
        if status not in {"documented", "recognized_enforcement"}:
            continue
        versions = getattr(rule, "versions", ())
        written = getattr(versions[-1], "written", None) if versions else None
        if written is None:
            continue
        representation_status = getattr(getattr(written, "status", None), "value", None)
        if representation_status in {None, "missing"}:
            continue
        if scope_subject is not None:
            action_token = getattr(rule, "action_token", None)
            if action_token != scope_subject:
                continue
        rule_id = getattr(rule, "rule_id", None)
        if type(rule_id) is str:
            refs.add(rule_id)
    return tuple(sorted(refs))


def resolve_representation_bases(
    ledger: RepresentationLedger,
    *,
    organization_concepts: object | None,
    offices: object | None = None,
    collective_decisions: object | None = None,
    formal_rules: object | None = None,
    tick: int,
) -> RepresentationLedger:
    """Resolve principals and read-only recognition bases for one ledger."""

    if type(ledger) is not RepresentationLedger:
        raise TypeError("ledger must be RepresentationLedger")
    if type(tick) is not int or isinstance(tick, bool) or tick < 0:
        _fail("representation_invalid_record")
    notices = set(ledger.notices)
    policy = default_representation_policy()
    mandates: list[RepresentationMandate] = []
    for mandate in ledger.mandates:
        resolved = resolve_representation_principal(
            mandate=mandate,
            organization_concepts=organization_concepts,
            region_anchors=ledger.region_anchors,
        )
        if (
            mandate.principal_kind
            in {
                RepresentationPrincipalKind.ORGANIZATION,
                RepresentationPrincipalKind.COALITION,
            }
            and not resolved
        ):
            notices.add("representation_unresolved_principal")
        if (
            mandate.principal_kind is RepresentationPrincipalKind.SETTLEMENT
            and not resolved
        ):
            notices.add("representation_region_unavailable")
        office_refs = _office_refs_for(offices, mandate.representative_id)
        decision_refs = _decision_refs_for(
            collective_decisions,
            mandate.principal_ref,
            mandate.representative_id,
        )
        rule_refs = _written_rule_refs_for(formal_rules, mandate.scope_subject)
        if (
            len(office_refs) > policy.max_office_refs
            or len(decision_refs) > policy.max_decision_refs
            or len(rule_refs) > policy.max_rule_refs
        ):
            notices.add("representation_reference_truncated")
        mandates.append(
            _derive_mandate(
                ledger,
                mandate,
                principal_resolved=resolved,
                office_basis=bool(office_refs),
                decision_basis=bool(decision_refs),
                written_basis=bool(rule_refs),
                office_refs=office_refs[: policy.max_office_refs],
                decision_refs=decision_refs[: policy.max_decision_refs],
                rule_refs=rule_refs[: policy.max_rule_refs],
            )
        )
    return RepresentationLedger(
        owner_id=ledger.owner_id,
        mandates=tuple(mandates),
        positions=ledger.positions,
        revocations=ledger.revocations,
        conflicts=ledger.conflicts,
        region_anchors=ledger.region_anchors,
        notices=tuple(notices),
        policy_version=ledger.policy_version,
        first_tick=ledger.first_tick,
        last_tick=max(ledger.last_tick, tick),
        pruned_mandates=ledger.pruned_mandates,
        pruned_positions=ledger.pruned_positions,
        pruned_revocations=ledger.pruned_revocations,
        pruned_conflicts=ledger.pruned_conflicts,
        coverage=ledger.coverage,
    )


def detect_representation_conflicts(
    ledger: RepresentationLedger,
) -> tuple[RepresentationConflict, ...]:
    """Detect retained, unresolved conflicts. Never reconcile them."""

    if type(ledger) is not RepresentationLedger:
        raise TypeError("ledger must be RepresentationLedger")
    pairs: dict[tuple[str, ...], RepresentationConflictKind] = {}
    active = [
        row
        for row in ledger.mandates
        if row.status
        not in {
            RepresentationStatus.REVOKED,
            RepresentationStatus.EXPIRED,
            RepresentationStatus.SUPERSEDED,
        }
    ]
    for index, first in enumerate(active):
        for second in active[index + 1 :]:
            ids = tuple(sorted((first.mandate_id, second.mandate_id)))
            if (
                _subject_key(first) == _subject_key(second)
                and first.representative_id != second.representative_id
            ):
                pairs[ids] = RepresentationConflictKind.DUPLICATE_MANDATE
            if (
                first.principal_kind is second.principal_kind
                and first.principal_ref == second.principal_ref
                and first.representative_id == second.representative_id
                and first.scope_kind is second.scope_kind
                and (first.scope_subject is None) != (second.scope_subject is None)
            ):
                pairs[ids] = RepresentationConflictKind.CONTRADICTORY_SCOPE
            if (
                first.representative_id == second.representative_id
                and first.scope_subject == second.scope_subject
                and (
                    first.principal_kind is not second.principal_kind
                    or first.principal_ref != second.principal_ref
                )
            ):
                pairs[ids] = RepresentationConflictKind.CONFLICTING_PRINCIPAL
    conflicts: dict[str, RepresentationConflict] = {}
    for ids, kind in sorted(pairs.items()):
        tick = max(row.start_tick for row in active if row.mandate_id in ids)
        conflict_id = representation_conflict_id(ledger.owner_id, ids, kind, tick)
        conflicts[conflict_id] = RepresentationConflict(
            conflict_id=conflict_id,
            mandate_ids=ids,
            kind=kind,
            status="unresolved",
            tick=tick,
        )
    for revocation in ledger.revocations:
        if not revocation.contested:
            continue
        mandate = next(
            (row for row in ledger.mandates if row.mandate_id == revocation.mandate_id),
            None,
        )
        if mandate is None:
            continue
        conflict_id = representation_conflict_id(
            ledger.owner_id,
            (mandate.mandate_id,),
            RepresentationConflictKind.REVOCATION_DISPUTE,
            revocation.tick,
        )
        conflicts[conflict_id] = RepresentationConflict(
            conflict_id=conflict_id,
            mandate_ids=(mandate.mandate_id,),
            kind=RepresentationConflictKind.REVOCATION_DISPUTE,
            status="unresolved",
            tick=revocation.tick,
        )
    return tuple(conflicts[key] for key in sorted(conflicts))


def expire_representation_mandates(
    ledger: RepresentationLedger, *, tick: int
) -> RepresentationLedger:
    """Mark deterministic expiry at the boundary tick. Rows are retained."""

    if type(ledger) is not RepresentationLedger:
        raise TypeError("ledger must be RepresentationLedger")
    if type(tick) is not int or isinstance(tick, bool) or tick < 0:
        _fail("representation_invalid_record")
    notices = set(ledger.notices)
    mandates = []
    for mandate in ledger.mandates:
        expired = mandate.expired
        if (
            mandate.duration_kind is not RepresentationDurationKind.UNTIL_REVOKED
            and mandate.duration_kind is not RepresentationDurationKind.UNKNOWN
            and mandate.end_tick is not None
            and mandate.end_tick <= tick
        ):
            expired = True
            notices.add("representation_expired")
        mandates.append(_derive_mandate(ledger, mandate, expired=expired))
    return RepresentationLedger(
        owner_id=ledger.owner_id,
        mandates=tuple(mandates),
        positions=ledger.positions,
        revocations=ledger.revocations,
        conflicts=ledger.conflicts,
        region_anchors=ledger.region_anchors,
        notices=tuple(notices),
        policy_version=ledger.policy_version,
        first_tick=ledger.first_tick,
        last_tick=max(ledger.last_tick, tick),
        pruned_mandates=ledger.pruned_mandates,
        pruned_positions=ledger.pruned_positions,
        pruned_revocations=ledger.pruned_revocations,
        pruned_conflicts=ledger.pruned_conflicts,
        coverage=ledger.coverage,
    )


def apply_representation_revocation(
    ledger: RepresentationLedger,
    *,
    tick: int,
    mandate_id: str,
    actor_id: str,
    kind: RepresentationRevocationKind,
    provenance: RepresentationProvenance,
    collective_decisions: object | None = None,
    offices: object | None = None,
) -> RepresentationLedger:
    """Retain one authorized revocation or one contested revocation attempt."""

    if type(ledger) is not RepresentationLedger:
        raise TypeError("ledger must be RepresentationLedger")
    if type(kind) is not RepresentationRevocationKind:
        raise TypeError("kind must be RepresentationRevocationKind")
    mandate = next(
        (row for row in ledger.mandates if row.mandate_id == mandate_id), None
    )
    if mandate is None:
        return replace(
            ledger,
            notices=tuple(sorted({*ledger.notices, "representation_unknown_mandate"})),
        )
    authorized = False
    if kind is RepresentationRevocationKind.PRINCIPAL_REVOKED:
        authorized = (
            mandate.principal_kind is RepresentationPrincipalKind.AGENT
            and mandate.principal_ref == actor_id
        )
    elif kind is RepresentationRevocationKind.REPRESENTATIVE_RESIGNED:
        authorized = mandate.representative_id == actor_id
    elif kind is RepresentationRevocationKind.COLLECTIVE_DECISION_REVOKED:
        decision_ids = _decision_ids(collective_decisions)
        authorized = bool(mandate.decision_refs) and (
            collective_decisions is None
            or any(ref in decision_ids for ref in mandate.decision_refs)
        )
    elif kind is RepresentationRevocationKind.OFFICE_LOST:
        authorized = bool(mandate.office_refs) and (
            offices is None
            or not any(ref in _office_ids(offices) for ref in mandate.office_refs)
        )
    contested = not authorized
    ordinal = sum(1 for row in ledger.revocations if row.mandate_id == mandate_id)
    revocation_id = representation_revocation_id(
        ledger.owner_id, mandate_id, actor_id, tick, kind, ordinal
    )
    existing = next(
        (row for row in ledger.revocations if row.revocation_id == revocation_id),
        None,
    )
    revocations = ledger.revocations
    if existing is None:
        revocations = tuple(
            sorted(
                (
                    *ledger.revocations,
                    RepresentationRevocation(
                        revocation_id=revocation_id,
                        mandate_id=mandate_id,
                        actor_id=actor_id,
                        kind=kind,
                        provenance=provenance,
                        tick=tick,
                        contested=contested,
                    ),
                ),
                key=lambda row: (row.tick, row.revocation_id),
            )
        )
    notices = set(ledger.notices)
    if contested:
        notices.add("representation_revocation_unauthorized")
        mandates = ledger.mandates
    else:
        notices.add("representation_revoked")
        mandates = tuple(
            _derive_mandate(ledger, row, revoked=True)
            if row.mandate_id == mandate_id
            else row
            for row in ledger.mandates
        )
    updated = RepresentationLedger(
        owner_id=ledger.owner_id,
        mandates=mandates,
        positions=ledger.positions,
        revocations=revocations,
        conflicts=ledger.conflicts,
        region_anchors=ledger.region_anchors,
        notices=tuple(notices),
        policy_version=ledger.policy_version,
        first_tick=ledger.first_tick,
        last_tick=max(ledger.last_tick, tick),
        pruned_mandates=ledger.pruned_mandates,
        pruned_positions=ledger.pruned_positions,
        pruned_revocations=ledger.pruned_revocations,
        pruned_conflicts=ledger.pruned_conflicts,
        coverage=ledger.coverage,
    )
    conflicts = detect_representation_conflicts(updated)
    if conflicts != updated.conflicts:
        updated = replace(
            updated,
            conflicts=conflicts,
            notices=tuple(sorted({*updated.notices, "representation_conflict"})),
        )
    return updated


def supersede_representation_mandates(
    ledger: RepresentationLedger,
) -> RepresentationLedger:
    """Supersede older non-recognized mandates; keep recognized coexistence."""

    if type(ledger) is not RepresentationLedger:
        raise TypeError("ledger must be RepresentationLedger")
    recognized = [
        row for row in ledger.mandates if row.status is RepresentationStatus.RECOGNIZED
    ]
    superseded_ids: set[str] = set()
    for current in recognized:
        for older in ledger.mandates:
            if (
                older.mandate_id != current.mandate_id
                and older.status
                in {
                    RepresentationStatus.CLAIMED,
                    RepresentationStatus.CONTESTED,
                    RepresentationStatus.REJECTED,
                }
                and _subject_key(older) == _subject_key(current)
                and older.representative_id != current.representative_id
            ):
                superseded_ids.add(older.mandate_id)
    if not superseded_ids:
        return ledger
    mandates = tuple(
        _derive_mandate(ledger, row, superseded=True)
        if row.mandate_id in superseded_ids
        else row
        for row in ledger.mandates
    )
    return replace(
        ledger,
        mandates=mandates,
        notices=tuple(sorted({*ledger.notices, "representation_superseded"})),
    )


def apply_representation_update(
    *,
    owner_id: object,
    tick: int,
    observation: object | None,
    prior: RepresentationLedger | None,
    frames: Sequence[object] = (),
    organization_concepts: object | None = None,
    collective_decisions: object | None = None,
    offices: object | None = None,
    formal_rules: object | None = None,
    policy: RepresentationPolicy | None = None,
) -> RepresentationLedger:
    """Apply one owner's verified speech and anchors to its representation ledger."""

    owner = getattr(owner_id, "value", owner_id)
    if type(owner) is not str or not owner:
        _fail("representation_invalid_owner")
    if type(tick) is not int or isinstance(tick, bool) or tick < 0:
        _fail("representation_invalid_record")
    if prior is not None:
        require_owner_representation(prior, owner)
    active = policy or default_representation_policy()
    if type(active) is not RepresentationPolicy:
        raise TypeError("policy must be RepresentationPolicy")
    _reject_forbidden_input(observation, owner=owner)
    _reject_forbidden_input(organization_concepts, owner=owner)
    _reject_forbidden_input(collective_decisions, owner=owner)
    _reject_forbidden_input(offices, owner=owner)
    _reject_forbidden_input(formal_rules, owner=owner)

    from agents.cognition.delegation_representation_communication import (
        RepresentationAct,
        representation_frames_from_observation,
    )

    base = prior or empty_representation_ledger(owner, tick=tick)
    notices = set(base.notices)
    anchors = set(base.region_anchors)
    observed = _observation_region_anchors(observation)
    if len(anchors | set(observed)) > active.max_region_anchors:
        notices.add("representation_region_anchor_truncated")
    anchors = set(sorted(anchors | set(observed))[: active.max_region_anchors])

    collected: list[object] = list(frames)
    if observation is not None:
        collected.extend(
            representation_frames_from_observation(observation, owner_id=owner)
        )
    unique: dict[tuple[object, ...], object] = {}
    for frame in collected:
        if type(frame) is not type(None) and hasattr(frame, "act"):
            unique.setdefault(_frame_key(frame), frame)
    ordered_frames = tuple(
        unique[key] for key in sorted(unique, key=lambda item: tuple(map(str, item)))
    )

    mandates: dict[str, RepresentationMandate] = {
        row.mandate_id: row for row in base.mandates
    }
    positions: dict[str, RepresentationPosition] = {
        row.position_id: row for row in base.positions
    }
    revocations = {row.revocation_id: row for row in base.revocations}
    conflicts = {row.conflict_id: row for row in base.conflicts}
    current_owner = owner

    for frame in ordered_frames:
        act = getattr(frame, "act", None)
        actor = getattr(frame, "actor_ref", None) or getattr(
            frame, "representative_ref", None
        )
        if actor is None:
            notices.add("representation_frame_dropped")
            continue
        mandate_ref = getattr(frame, "mandate_ref", None)
        if act in {RepresentationAct.CLAIM, RepresentationAct.DELEGATE}:
            principal_kind = getattr(frame, "principal_kind", None)
            if principal_kind is None:
                notices.add("representation_frame_dropped")
                continue
            principal_ref = getattr(frame, "principal_ref", None)
            representative = getattr(frame, "representative_ref", None)
            scope_kind = getattr(frame, "scope_kind", None)
            duration_kind = getattr(frame, "duration_kind", None)
            provenance = getattr(frame, "provenance", None)
            if (
                representative is None
                or scope_kind is None
                or duration_kind is None
                or provenance is None
            ):
                notices.add("representation_frame_dropped")
                continue
            if act is RepresentationAct.CLAIM:
                representative = actor
            if act is RepresentationAct.DELEGATE:
                if actor != principal_ref or representative == principal_ref:
                    notices.add("representation_party_mismatch")
                    continue
            equivalent = next(
                (
                    row
                    for row in mandates.values()
                    if row.principal_kind is principal_kind
                    and row.principal_ref == principal_ref
                    and row.representative_id == representative
                    and row.scope_kind is scope_kind
                    and row.scope_subject == getattr(frame, "scope_subject", None)
                    and row.duration_kind is duration_kind
                    and row.status
                    not in {
                        RepresentationStatus.REVOKED,
                        RepresentationStatus.EXPIRED,
                        RepresentationStatus.SUPERSEDED,
                    }
                ),
                None,
            )
            if equivalent is not None:
                mandates[equivalent.mandate_id] = replace(
                    equivalent,
                    principal_declared=(
                        True
                        if act is RepresentationAct.DELEGATE
                        else equivalent.principal_declared
                    ),
                    revision=max(equivalent.revision, getattr(frame, "revision", 0))
                    + 1,
                )
                notices.add("representation_duplicate_claim")
                continue
            draft = _mandate_draft(
                owner_id=current_owner,
                tick=tick,
                principal_kind=principal_kind,
                principal_ref=principal_ref,
                representative_id=representative,
                scope_kind=scope_kind,
                scope_subject=getattr(frame, "scope_subject", None),
                duration_kind=duration_kind,
                end_tick=getattr(frame, "end_tick", None),
                provenance=provenance,
                attributed_actor_id=actor,
                principal_declared=act is RepresentationAct.DELEGATE,
                revision=getattr(frame, "revision", 0),
            )
            if draft.mandate_id in mandates:
                prior_row = mandates[draft.mandate_id]
                mandates[draft.mandate_id] = replace(
                    prior_row,
                    revision=max(prior_row.revision, draft.revision) + 1,
                )
                notices.add("representation_duplicate_claim")
            else:
                mandates[draft.mandate_id] = draft
            continue
        if mandate_ref is None or mandate_ref not in mandates:
            notices.add("representation_unknown_mandate")
            continue
        mandate = mandates[mandate_ref]
        if act in {
            RepresentationAct.SUPPORT,
            RepresentationAct.OPPOSE,
            RepresentationAct.ABSTAIN,
        }:
            stance = {
                RepresentationAct.SUPPORT: RepresentationPositionStance.SUPPORT,
                RepresentationAct.OPPOSE: RepresentationPositionStance.OPPOSE,
                RepresentationAct.ABSTAIN: RepresentationPositionStance.ABSTAIN,
            }[act]
            _upsert_position(
                positions,
                owner_id=current_owner,
                mandate_id=mandate_ref,
                actor_id=actor,
                stance=stance,
                provenance=getattr(frame, "provenance", None)
                or RepresentationProvenance.COMMUNICATED,
                tick=tick,
                root_ref=None,
            )
        elif act in {RepresentationAct.ACCEPT, RepresentationAct.REJECT}:
            stance = (
                RepresentationPositionStance.SUPPORT
                if act is RepresentationAct.ACCEPT
                else RepresentationPositionStance.OPPOSE
            )
            if (
                act is RepresentationAct.ACCEPT
                and mandate.principal_kind is RepresentationPrincipalKind.AGENT
                and mandate.principal_ref == actor
            ):
                mandates[mandate_ref] = replace(mandate, principal_declared=True)
                provenance = RepresentationProvenance.PRINCIPAL_DECLARED
            else:
                provenance = RepresentationProvenance.COMMUNICATED
            _upsert_position(
                positions,
                owner_id=current_owner,
                mandate_id=mandate_ref,
                actor_id=actor,
                stance=stance,
                provenance=provenance,
                tick=tick,
                root_ref=None,
            )
        elif act in {RepresentationAct.REVOKE, RepresentationAct.RESIGN}:
            kind = (
                RepresentationRevocationKind.PRINCIPAL_REVOKED
                if act is RepresentationAct.REVOKE
                else RepresentationRevocationKind.REPRESENTATIVE_RESIGNED
            )
            provisional = RepresentationLedger(
                owner_id=current_owner,
                mandates=tuple(
                    _derive_all(mandates, positions, current_owner).values()
                ),
                positions=tuple(positions.values()),
                revocations=tuple(revocations.values()),
                conflicts=tuple(conflicts.values()),
                region_anchors=tuple(sorted(anchors)),
                notices=tuple(notices),
                first_tick=base.first_tick,
                last_tick=max(base.last_tick, tick),
            )
            updated = apply_representation_revocation(
                provisional,
                tick=tick,
                mandate_id=mandate_ref,
                actor_id=actor,
                kind=kind,
                provenance=getattr(frame, "provenance", None)
                or RepresentationProvenance.COMMUNICATED,
                collective_decisions=collective_decisions,
                offices=offices,
            )
            mandates = {row.mandate_id: row for row in updated.mandates}
            positions = {row.position_id: row for row in updated.positions}
            revocations = {row.revocation_id: row for row in updated.revocations}
            conflicts = {row.conflict_id: row for row in updated.conflicts}
            notices = set(updated.notices)
        elif act is RepresentationAct.REPORT:
            if mandate_ref not in mandates:
                principal_kind = getattr(frame, "principal_kind", None)
                scope_kind = getattr(frame, "scope_kind", None)
                duration_kind = getattr(frame, "duration_kind", None)
                representative = getattr(frame, "representative_ref", None)
                if (
                    principal_kind is None
                    or scope_kind is None
                    or duration_kind is None
                    or representative is None
                ):
                    notices.add("representation_frame_dropped")
                    continue
                mandates[mandate_ref] = _mandate_draft(
                    owner_id=current_owner,
                    tick=tick,
                    principal_kind=principal_kind,
                    principal_ref=getattr(frame, "principal_ref", None),
                    representative_id=representative,
                    scope_kind=scope_kind,
                    scope_subject=getattr(frame, "scope_subject", None),
                    duration_kind=duration_kind,
                    end_tick=getattr(frame, "end_tick", None),
                    provenance=RepresentationProvenance.COMMUNICATED,
                    attributed_actor_id=actor,
                )
    provisional = RepresentationLedger(
        owner_id=current_owner,
        mandates=tuple(_derive_all(mandates, positions, current_owner).values()),
        positions=tuple(positions.values()),
        revocations=tuple(revocations.values()),
        conflicts=tuple(conflicts.values()),
        region_anchors=tuple(sorted(anchors)),
        notices=tuple(notices),
        policy_version=base.policy_version,
        first_tick=base.first_tick,
        last_tick=max(base.last_tick, tick),
        pruned_mandates=base.pruned_mandates,
        pruned_positions=base.pruned_positions,
        pruned_revocations=base.pruned_revocations,
        pruned_conflicts=base.pruned_conflicts,
        coverage=base.coverage,
    )
    resolved = resolve_representation_bases(
        provisional,
        organization_concepts=organization_concepts,
        offices=offices,
        collective_decisions=collective_decisions,
        formal_rules=formal_rules,
        tick=tick,
    )
    expired = expire_representation_mandates(resolved, tick=tick)
    superseded = supersede_representation_mandates(expired)
    detected_conflicts = detect_representation_conflicts(superseded)
    if detected_conflicts:
        notices = {*superseded.notices, "representation_conflict"}
    else:
        notices = set(superseded.notices)
    updated = replace(
        superseded,
        conflicts=detected_conflicts,
        notices=tuple(sorted(notices)),
    )
    return enforce_representation_limits(updated, policy=active)


def record_representation_utterance(
    ledger: RepresentationLedger,
    command: object,
    *,
    owner_id: object,
    tick: int,
    organization_concepts: object | None = None,
    collective_decisions: object | None = None,
    offices: object | None = None,
    formal_rules: object | None = None,
    policy: RepresentationPolicy | None = None,
) -> RepresentationLedger:
    """Record the owner's own speech frames after command selection."""

    from agents.cognition.delegation_representation_communication import (
        parse_representation_frame_relation,
    )

    if type(ledger) is not RepresentationLedger:
        raise TypeError("ledger must be RepresentationLedger")
    owner = getattr(owner_id, "value", owner_id)
    if type(owner) is not str:
        _fail("representation_invalid_owner")
    require_owner_representation(ledger, owner)
    utterance = getattr(command, "utterance", None)
    declared = getattr(utterance, "declared", None)
    speaker = getattr(declared, "immediate_source_id", None)
    if speaker is None:
        return ledger
    speaker_value = getattr(speaker, "value", speaker)
    if speaker_value != owner:
        return ledger
    content = getattr(utterance, "content", None)
    frames = []
    for relation in getattr(content, "relations", ()):
        frame = parse_representation_frame_relation(
            getattr(relation, "subject", ""),
            getattr(relation, "predicate", ""),
            getattr(relation, "object", ""),
        )
        if frame is not None:
            frames.append(replace(frame, actor_ref=owner))
    if not frames:
        return ledger
    return apply_representation_update(
        owner_id=owner,
        tick=tick,
        observation=None,
        prior=ledger,
        frames=tuple(frames),
        organization_concepts=organization_concepts,
        collective_decisions=collective_decisions,
        offices=offices,
        formal_rules=formal_rules,
        policy=policy,
    )


@dataclass(frozen=True, slots=True)
class RepresentationStandingSummary:
    """Read-only projection for a later diplomacy plan. Never a permission."""

    principal_kind: RepresentationPrincipalKind
    principal_ref: str | None
    recognized_representatives: tuple[str, ...]
    contested_representatives: tuple[str, ...]
    revoked_count: int
    active_scope_kinds: tuple[RepresentationScopeKind, ...]
    coverage: str


def representation_standing_summary(
    ledger: RepresentationLedger,
    *,
    principal_kind: RepresentationPrincipalKind,
    principal_ref: str | None,
) -> RepresentationStandingSummary:
    """Summarize one principal's standing for researchers and later plans."""

    if type(ledger) is not RepresentationLedger:
        raise TypeError("ledger must be RepresentationLedger")
    related = [
        row
        for row in ledger.mandates
        if row.principal_kind is principal_kind and row.principal_ref == principal_ref
    ]
    recognized = tuple(
        sorted(
            {
                row.representative_id
                for row in related
                if row.status is RepresentationStatus.RECOGNIZED
            }
        )
    )
    contested = tuple(
        sorted(
            {
                row.representative_id
                for row in related
                if row.status is RepresentationStatus.CONTESTED
            }
        )
    )
    revoked_count = sum(
        1 for row in related if row.status is RepresentationStatus.REVOKED
    )
    scopes = tuple(
        sorted(
            {
                row.scope_kind
                for row in related
                if row.status is RepresentationStatus.RECOGNIZED
            },
            key=lambda item: item.value,
        )
    )
    return RepresentationStandingSummary(
        principal_kind=principal_kind,
        principal_ref=principal_ref,
        recognized_representatives=recognized,
        contested_representatives=contested,
        revoked_count=revoked_count,
        active_scope_kinds=scopes,
        coverage=ledger.coverage,
    )
