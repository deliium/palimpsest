# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Owner-scoped beliefs about sets of logical locations.

A domain is one owner's belief that a sorted set of logical ``EntityId``
locations belongs to it. A boundary is the set of observed adjacency pairs with
exactly one endpoint inside that set. There is no objective border, country
owner, territory registry, grid cell, coordinate, polygon, or area.

This module is a private belief store. ``WorldEngine``, perception, admission,
stop selectors, memory, prompts, observer semantics, and the presentation client never
read it. No helper here returns, constructs, submits, resolves, or blocks an
``AgentCommand``. Every physical effect remains ordinary world admission.
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from dataclasses import replace as dataclasses_replace
from decimal import Decimal
from enum import StrEnum
from typing import Final

from agents.models import AgentId
from world.identifiers import EntityId, require_exact_nonneg_int, require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.borders")

BORDERS_POLICY_VERSION: Final[str] = "borders-claims.v1"
BORDERS_LEDGER_VERSION: Final[str] = "borders-ledger.v1"
MAX_LOCATIONS_PER_DOMAIN: Final[int] = 8
MAX_BOUNDARY_EDGES_PER_DOMAIN: Final[int] = 32
MAX_ANCHOR_REF_CHARS: Final[int] = 128
MAX_COUNTERPARTY_REF_CHARS: Final[int] = 128
MAX_PROVISIONS: Final[int] = 5
MAX_CONTESTED_LOCATIONS: Final[int] = 8

_QUANTUM: Final[Decimal] = Decimal("0.000001")
_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")

_ANCHOR_KINDS: Final[frozenset[str]] = frozenset(
    {"organization", "settlement", "agent", "unknown"}
)
_FORBIDDEN_INPUT_TYPES: Final[frozenset[str]] = frozenset(
    {"WorldState", "WorldEvent", "PhysicalRules", "AgentBody"}
)


class DomainClaimStatus(StrEnum):
    """Closed owner-belief status of one domain claim."""

    CLAIMED = "claimed"
    RECOGNIZED = "recognized"
    DISPUTED = "disputed"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class BoundaryBasis(StrEnum):
    """Closed provenance for one boundary belief."""

    OWN_CLAIM = "own_claim"
    DIRECT_OBSERVATION = "direct_observation"
    TESTIMONY = "testimony"
    AGREEMENT = "agreement"
    UNRESOLVED = "unresolved"


class BoundaryStatus(StrEnum):
    """Closed belief status for a boundary or recognition row."""

    RECOGNIZED = "recognized"
    UNRESOLVED = "unresolved"
    DISPUTED = "disputed"


class AccessExpectationMode(StrEnum):
    """Closed descriptive access expectation. It never grants or denies access."""

    OPEN = "open"
    RESTRICTED = "restricted"
    PERMISSION_EXPECTED = "permission_expected"
    UNKNOWN = "unknown"


class AccessSubjectKind(StrEnum):
    """Closed subject kind for an access expectation."""

    SELF_AGENT = "self_agent"
    OTHER_AGENT = "other_agent"
    ORGANIZATION = "organization"
    UNKNOWN = "unknown"


class AccessExpectationStatus(StrEnum):
    """Closed lifecycle for an access expectation row."""

    EXPECTED = "expected"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class CounterpartyKind(StrEnum):
    """Closed counterparty kind. No country or sovereignty kind exists."""

    AGENT = "agent"
    ORGANIZATION = "organization"
    SETTLEMENT = "settlement"
    UNKNOWN = "unknown"


class AgreementAct(StrEnum):
    """Closed speech acts of a border agreement exchange."""

    CLAIM_DOMAIN = "claim_domain"
    PROPOSE = "propose"
    ACCEPT = "accept"
    REJECT = "reject"
    WITHDRAW = "withdraw"
    RECOGNIZE = "recognize"
    EXPECT_ACCESS = "expect_access"
    DISPUTE_DOMAIN = "dispute_domain"


class AgreementStatus(StrEnum):
    """Closed owner-belief status of a border agreement."""

    PROPOSED = "proposed"
    APPARENT_ACCEPTANCE = "apparent_acceptance"
    RECOGNIZED = "recognized"
    DISPUTED = "disputed"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"


class AgreementProvision(StrEnum):
    """Closed descriptive provision. It is not an obligation or permission."""

    PASSAGE = "passage"
    NON_ENTRY = "non_entry"
    SHARED_USE = "shared_use"
    TERRITORIAL_ACKNOWLEDGEMENT = "territorial_acknowledgement"
    UNKNOWN = "unknown"


class BorderDisputeStatus(StrEnum):
    """Closed lifecycle for a retained border dispute."""

    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class BorderNoticeCode(StrEnum):
    """Closed metadata notice codes. Notices carry no payload."""

    UNRESOLVED_ANCHOR = "unresolved_anchor"
    OVERLAP_DETECTED = "overlap_detected"
    BOUNDARY_UNOBSERVED = "boundary_unobserved"
    DOMAIN_CAP_REACHED = "domain_cap_reached"
    AGREEMENT_CAP_REACHED = "agreement_cap_reached"
    ACCESS_CAP_REACHED = "access_cap_reached"
    DISPUTE_CAP_REACHED = "dispute_cap_reached"
    EVIDENCE_CAP_REACHED = "evidence_cap_reached"
    LEDGER_CAP_REACHED = "ledger_cap_reached"
    TRUNCATED = "truncated"
    MALFORMED_FRAME = "malformed_frame"
    PEER_CLAIM_UNTRUSTED = "peer_claim_untrusted"


def _log_failure(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "borders_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    return ValueError(f"{field_name}: {code}")


def _require_sequence(field_name: str, values: object) -> tuple[object, ...]:
    if isinstance(values, (str, bytes, set, frozenset, Mapping)) or not isinstance(
        values, Sequence
    ):
        raise _log_failure(field_name, "invalid_type")
    return tuple(values)


def _quantize(value: float) -> float:
    steps = round(value / 1e-6)
    quantized = float(Decimal(steps) * _QUANTUM)
    return 0.0 if quantized == 0.0 else quantized


def _unit(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _log_failure(field_name, "not_finite")
    number = float(value)
    if not math.isfinite(number):
        raise _log_failure(field_name, "not_finite")
    if number < 0.0 or number > 1.0:
        raise _log_failure(field_name, "out_of_range")
    quantized = _quantize(number)
    if quantized < 0.0 or quantized > 1.0:
        raise _log_failure(field_name, "out_of_range")
    return quantized


def _nonneg(field_name: str, value: object) -> int:
    try:
        return require_exact_nonneg_int(field_name, value)
    except ValueError as exc:
        raise _log_failure(field_name, "invalid_tick") from exc


def _stable(field_name: str, value: object) -> str:
    try:
        return require_stable_id(field_name, value)
    except ValueError as exc:
        raise _log_failure(field_name, "invalid_identifier") from exc


def _bounded_ref(field_name: str, value: object) -> str:
    text = _stable(field_name, value)
    if len(text) > MAX_ANCHOR_REF_CHARS:
        raise _log_failure(field_name, "too_long")
    return text


def _sha256_hex(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _short_token(prefix: str, material: str) -> str:
    return f"{prefix}{_sha256_hex(material)[:16]}"


def _require_token(field_name: str, value: object, prefix: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith(prefix)
        or len(value) != len(prefix) + 16
        or any(char not in _HEX for char in value[len(prefix) :])
    ):
        raise _log_failure(field_name, "invalid_identifier")
    return value


def require_location_set(
    value: object, *, field_name: str = "locations"
) -> tuple[EntityId, ...]:
    """Return 1-8 sorted exact ``EntityId`` values.

    Input is unordered. Duplicates are rejected rather than silently merged so
    that a caller cannot hide an ambiguous location set.
    """
    raw = _require_sequence(field_name, value)
    if len(raw) < 1 or len(raw) > MAX_LOCATIONS_PER_DOMAIN:
        raise _log_failure(field_name, "location_count")
    seen: set[str] = set()
    for item in raw:
        if type(item) is not EntityId:
            raise _log_failure(field_name, "unresolved_entity")
        if item.value in seen:
            raise _log_failure(field_name, "duplicate_location")
        seen.add(item.value)
    ordered = tuple(sorted(raw, key=lambda item: item.value))  # type: ignore[arg-type]
    return ordered


def boundary_edge(a: EntityId, b: EntityId) -> tuple[str, str]:
    """Return the canonical sorted endpoint pair, rejecting a self-edge."""
    if type(a) is not EntityId or type(b) is not EntityId:
        raise _log_failure("boundary_edge", "unresolved_entity")
    if a == b:
        raise _log_failure("boundary_edge", "boundary_self_edge")
    return (a.value, b.value) if a.value < b.value else (b.value, a.value)


def require_boundary_edges(
    value: object, *, field_name: str = "boundary_edges"
) -> tuple[tuple[str, str], ...]:
    """Return 0-32 canonical sorted endpoint pairs."""
    raw = _require_sequence(field_name, value)
    if len(raw) > MAX_BOUNDARY_EDGES_PER_DOMAIN:
        raise _log_failure(field_name, "edge_count")
    seen: set[tuple[str, str]] = set()
    checked: list[tuple[str, str]] = []
    for item in raw:
        if type(item) is not tuple or len(item) != 2:
            raise _log_failure(field_name, "invalid_edge")
        left, right = item
        if type(left) is not str or type(right) is not str:
            raise _log_failure(field_name, "invalid_edge")
        if left == right:
            raise _log_failure(field_name, "boundary_self_edge")
        if left > right:
            raise _log_failure(field_name, "non_canonical_edge")
        pair = (left, right)
        if pair in seen:
            raise _log_failure(field_name, "duplicate_edge")
        seen.add(pair)
        checked.append(pair)
    checked.sort()
    return tuple(checked)


def domain_location_tokens(domain: TerritorialDomainClaim) -> tuple[str, ...]:
    """Publication-facing location tokens. Never emits ``EntityId`` objects."""
    if type(domain) is not TerritorialDomainClaim:
        raise _log_failure("domain", "invalid_type")
    return tuple(item.value for item in domain.location_ids)


def domain_edge_tokens(
    domain: TerritorialDomainClaim,
) -> tuple[tuple[str, str], ...]:
    """Publication-facing boundary edge tokens. Never emits ``EntityId``."""
    if type(domain) is not TerritorialDomainClaim:
        raise _log_failure("domain", "invalid_type")
    return tuple(domain.boundary_edges)


def domain_claim_token_id(
    owner_id: AgentId, location_tokens: Sequence[str]
) -> str:
    """Content-addressed ``bdc-`` id from an owner and sorted location tokens."""
    if type(owner_id) is not AgentId:
        raise _log_failure("owner_id", "invalid_type")
    raw = _require_sequence("location_tokens", location_tokens)
    if len(raw) < 1 or len(raw) > MAX_LOCATIONS_PER_DOMAIN:
        raise _log_failure("location_tokens", "location_count")
    tokens: list[str] = []
    for item in raw:
        if type(item) is not str:
            raise _log_failure("location_tokens", "invalid_identifier")
        token = _stable("location_token", item)
        if token in tokens:
            raise _log_failure("location_tokens", "duplicate_location")
        tokens.append(token)
    tokens.sort()
    material = f"bdc|{owner_id.value}|{'|'.join(tokens)}"
    return _short_token("bdc-", material)


def domain_claim_id(
    owner_id: AgentId, location_ids: Sequence[EntityId]
) -> str:
    """Content-addressed ``bdc-`` id from an owner and a location set."""
    ordered = require_location_set(location_ids, field_name="location_ids")
    return domain_claim_token_id(owner_id, tuple(item.value for item in ordered))


def boundary_recognition_id(
    owner_id: AgentId, domain_id: str, basis: BoundaryBasis
) -> str:
    """Content-addressed ``bdr-`` id for one recognition basis."""
    if type(owner_id) is not AgentId:
        raise _log_failure("owner_id", "invalid_type")
    domain = _require_token("domain_id", domain_id, "bdc-")
    if type(basis) is not BoundaryBasis:
        raise _log_failure("basis", "unknown_basis")
    material = f"bdr|{owner_id.value}|{domain}|{basis.value}"
    return _short_token("bdr-", material)


def access_expectation_id(
    owner_id: AgentId,
    domain_id: str,
    subject_kind: AccessSubjectKind,
    subject_ref: str | None,
) -> str:
    """Content-addressed ``bdx-`` id for one access expectation."""
    if type(owner_id) is not AgentId:
        raise _log_failure("owner_id", "invalid_type")
    domain = _require_token("domain_id", domain_id, "bdc-")
    if type(subject_kind) is not AccessSubjectKind:
        raise _log_failure("subject_kind", "unknown_subject_kind")
    ref = "-" if subject_ref is None else _bounded_ref("subject_ref", subject_ref)
    material = f"bdx|{owner_id.value}|{domain}|{subject_kind.value}|{ref}"
    return _short_token("bdx-", material)


def border_agreement_id(
    owner_id: AgentId,
    domain_id: str,
    counterparty_kind: CounterpartyKind,
    counterparty_ref: str | None,
) -> str:
    """Content-addressed ``bda-`` id for one border agreement."""
    if type(owner_id) is not AgentId:
        raise _log_failure("owner_id", "invalid_type")
    domain = _require_token("domain_id", domain_id, "bdc-")
    if type(counterparty_kind) is not CounterpartyKind:
        raise _log_failure("counterparty_kind", "unknown_counterparty_kind")
    ref = (
        "-"
        if counterparty_ref is None
        else _bounded_ref("counterparty_ref", counterparty_ref)
    )
    material = f"bda|{owner_id.value}|{domain}|{counterparty_kind.value}|{ref}"
    return _short_token("bda-", material)


def border_dispute_id(
    owner_id: AgentId,
    domain_id: str,
    counterparty_kind: CounterpartyKind,
    counterparty_ref: str | None,
) -> str:
    """Content-addressed ``bdd-`` id for one border dispute."""
    if type(owner_id) is not AgentId:
        raise _log_failure("owner_id", "invalid_type")
    domain = _require_token("domain_id", domain_id, "bdc-")
    if type(counterparty_kind) is not CounterpartyKind:
        raise _log_failure("counterparty_kind", "unknown_counterparty_kind")
    ref = (
        "-"
        if counterparty_ref is None
        else _bounded_ref("counterparty_ref", counterparty_ref)
    )
    material = f"bdd|{owner_id.value}|{domain}|{counterparty_kind.value}|{ref}"
    return _short_token("bdd-", material)


@dataclass(frozen=True, slots=True)
class BorderEvidence:
    """One adopted local contribution to a border row."""

    kind: BoundaryBasis
    source_owner_id: AgentId | None
    source_tick: int
    lineage_ref: str
    policy_version: str = BORDERS_POLICY_VERSION

    def __post_init__(self) -> None:
        if type(self.kind) is not BoundaryBasis:
            raise _log_failure("evidence.kind", "unknown_basis")
        if self.source_owner_id is not None and (
            type(self.source_owner_id) is not AgentId
        ):
            raise _log_failure("evidence.source_owner_id", "invalid_type")
        object.__setattr__(
            self, "source_tick", _nonneg("evidence.source_tick", self.source_tick)
        )
        object.__setattr__(
            self, "lineage_ref", _stable("evidence.lineage_ref", self.lineage_ref)
        )
        if self.policy_version != BORDERS_POLICY_VERSION:
            raise _log_failure("evidence.policy_version", "unsupported_policy")


@dataclass(frozen=True, slots=True)
class TerritorialDomainClaim:
    """One owner's belief about one sorted set of logical locations."""

    domain_id: str
    owner_id: AgentId
    location_ids: tuple[EntityId, ...]
    boundary_edges: tuple[tuple[str, str], ...]
    anchor_kind: str | None
    anchor_ref: str | None
    status: DomainClaimStatus
    strength: float
    first_tick: int
    last_tick: int
    evidence: tuple[BorderEvidence, ...] = ()
    observed_edges: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _log_failure("owner_id", "invalid_type")
        ordered = require_location_set(self.location_ids, field_name="location_ids")
        object.__setattr__(self, "location_ids", ordered)
        expected = domain_claim_token_id(
            self.owner_id, tuple(item.value for item in ordered)
        )
        if self.domain_id != expected:
            raise _log_failure("domain_id", "domain_id_mismatch")
        object.__setattr__(
            self,
            "boundary_edges",
            require_boundary_edges(self.boundary_edges, field_name="boundary_edges"),
        )
        object.__setattr__(
            self,
            "observed_edges",
            require_boundary_edges(
                self.observed_edges, field_name="observed_edges"
            ),
        )
        if self.anchor_kind is not None:
            if (
                type(self.anchor_kind) is not str
                or self.anchor_kind not in _ANCHOR_KINDS
            ):
                raise _log_failure("anchor_kind", "unknown_anchor_kind")
            if self.anchor_kind == "unknown":
                if self.anchor_ref is not None:
                    raise _log_failure("anchor_ref", "unexpected_anchor_ref")
            else:
                if self.anchor_ref is None:
                    raise _log_failure("anchor_ref", "missing_anchor_ref")
                object.__setattr__(
                    self,
                    "anchor_ref",
                    _bounded_ref("anchor_ref", self.anchor_ref),
                )
        elif self.anchor_ref is not None:
            raise _log_failure("anchor_ref", "unexpected_anchor_ref")
        if type(self.status) is not DomainClaimStatus:
            raise _log_failure("status", "unknown_domain_status")
        object.__setattr__(self, "strength", _unit("strength", self.strength))
        first = _nonneg("first_tick", self.first_tick)
        last = _nonneg("last_tick", self.last_tick)
        if first > last:
            raise _log_failure("first_tick", "tick_order")
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        object.__setattr__(self, "evidence", _evidence_tuple(self.evidence))
        _LOG.debug(
            "borders_contract_constructed locations=%s edges=%s",
            len(self.location_ids),
            len(self.boundary_edges),
        )


def _evidence_tuple(value: object) -> tuple[BorderEvidence, ...]:
    raw = _require_sequence("evidence", value)
    checked: list[BorderEvidence] = []
    seen: set[tuple[str, str, int]] = set()
    for item in raw:
        if type(item) is not BorderEvidence:
            raise _log_failure("evidence", "invalid_type")
        key = (item.kind.value, item.lineage_ref, item.source_tick)
        if key in seen:
            raise _log_failure("evidence", "duplicate_evidence")
        seen.add(key)
        checked.append(item)
    if len(checked) > BordersPolicy().max_evidence_per_row:
        raise _log_failure("evidence", "cap_exceeded")
    return tuple(checked)


@dataclass(frozen=True, slots=True)
class BoundaryRecognition:
    """One owner's belief about boundary edges of one domain."""

    domain_id: str
    boundary_edges: tuple[tuple[str, str], ...]
    basis: BoundaryBasis
    status: BoundaryStatus
    evidence: tuple[BorderEvidence, ...] = ()

    def __post_init__(self) -> None:
        _require_token("domain_id", self.domain_id, "bdc-")
        object.__setattr__(
            self,
            "boundary_edges",
            require_boundary_edges(self.boundary_edges, field_name="boundary_edges"),
        )
        if type(self.basis) is not BoundaryBasis:
            raise _log_failure("basis", "unknown_basis")
        if type(self.status) is not BoundaryStatus:
            raise _log_failure("status", "unknown_boundary_status")
        object.__setattr__(self, "evidence", _evidence_tuple(self.evidence))


@dataclass(frozen=True, slots=True)
class AccessExpectation:
    """A descriptive expectation. It grants nothing and blocks nothing."""

    expectation_id: str
    domain_id: str
    subject_kind: AccessSubjectKind
    subject_ref: str | None
    mode: AccessExpectationMode
    status: AccessExpectationStatus
    evidence: tuple[BorderEvidence, ...] = ()

    def __post_init__(self) -> None:
        _require_token("domain_id", self.domain_id, "bdc-")
        if type(self.subject_kind) is not AccessSubjectKind:
            raise _log_failure("subject_kind", "unknown_subject_kind")
        if self.subject_kind in (
            AccessSubjectKind.SELF_AGENT,
            AccessSubjectKind.UNKNOWN,
        ):
            if self.subject_ref is not None:
                raise _log_failure("subject_ref", "unexpected_subject_ref")
        else:
            if self.subject_ref is None:
                raise _log_failure("subject_ref", "missing_subject_ref")
            object.__setattr__(
                self, "subject_ref", _bounded_ref("subject_ref", self.subject_ref)
            )
        if type(self.mode) is not AccessExpectationMode:
            raise _log_failure("mode", "unknown_access_mode")
        if type(self.status) is not AccessExpectationStatus:
            raise _log_failure("status", "unknown_access_status")
        _require_token("expectation_id", self.expectation_id, "bdx-")
        object.__setattr__(self, "evidence", _evidence_tuple(self.evidence))


@dataclass(frozen=True, slots=True)
class BorderAgreement:
    """An owner's belief about a border agreement. It binds nobody."""

    agreement_id: str
    domain_id: str
    counterparty_kind: CounterpartyKind
    counterparty_ref: str | None
    provisions: tuple[AgreementProvision, ...]
    status: AgreementStatus
    recognition: BoundaryStatus
    effective_tick: int | None = None
    expiry_tick: int | None = None
    evidence: tuple[BorderEvidence, ...] = ()

    def __post_init__(self) -> None:
        _require_token("domain_id", self.domain_id, "bdc-")
        if type(self.counterparty_kind) is not CounterpartyKind:
            raise _log_failure("counterparty_kind", "unknown_counterparty_kind")
        if self.counterparty_kind is CounterpartyKind.UNKNOWN:
            if self.counterparty_ref is not None:
                raise _log_failure("counterparty_ref", "unexpected_counterparty_ref")
        else:
            if self.counterparty_ref is None:
                raise _log_failure("counterparty_ref", "missing_counterparty_ref")
            object.__setattr__(
                self,
                "counterparty_ref",
                _bounded_ref("counterparty_ref", self.counterparty_ref),
            )
        raw = _require_sequence("provisions", self.provisions)
        if len(raw) < 1 or len(raw) > MAX_PROVISIONS:
            raise _log_failure("provisions", "provision_count")
        checked: list[AgreementProvision] = []
        for item in raw:
            if type(item) is not AgreementProvision:
                raise _log_failure("provisions", "unknown_provision")
            if item in checked:
                raise _log_failure("provisions", "duplicate_provision")
            checked.append(item)
        checked.sort(key=lambda item: item.value)
        object.__setattr__(self, "provisions", tuple(checked))
        if type(self.status) is not AgreementStatus:
            raise _log_failure("status", "unknown_agreement_status")
        if type(self.recognition) is not BoundaryStatus:
            raise _log_failure("recognition", "unknown_boundary_status")
        if self.effective_tick is not None:
            object.__setattr__(
                self, "effective_tick", _nonneg("effective_tick", self.effective_tick)
            )
        if self.expiry_tick is not None:
            object.__setattr__(
                self, "expiry_tick", _nonneg("expiry_tick", self.expiry_tick)
            )
        if (
            self.effective_tick is not None
            and self.expiry_tick is not None
            and self.effective_tick > self.expiry_tick
        ):
            raise _log_failure("effective_tick", "tick_order")
        object.__setattr__(self, "evidence", _evidence_tuple(self.evidence))


@dataclass(frozen=True, slots=True)
class BorderDispute:
    """A retained disagreement about locations. No verdict or winner exists."""

    dispute_id: str
    domain_id: str
    counterparty_kind: CounterpartyKind
    counterparty_ref: str | None
    contested_location_ids: tuple[EntityId, ...]
    status: BorderDisputeStatus
    evidence: tuple[BorderEvidence, ...] = ()

    def __post_init__(self) -> None:
        _require_token("domain_id", self.domain_id, "bdc-")
        if type(self.counterparty_kind) is not CounterpartyKind:
            raise _log_failure("counterparty_kind", "unknown_counterparty_kind")
        if self.counterparty_kind is CounterpartyKind.UNKNOWN:
            if self.counterparty_ref is not None:
                raise _log_failure("counterparty_ref", "unexpected_counterparty_ref")
        else:
            if self.counterparty_ref is None:
                raise _log_failure("counterparty_ref", "missing_counterparty_ref")
            object.__setattr__(
                self,
                "counterparty_ref",
                _bounded_ref("counterparty_ref", self.counterparty_ref),
            )
        ordered = require_location_set(
            self.contested_location_ids, field_name="contested_location_ids"
        )
        if len(ordered) > MAX_CONTESTED_LOCATIONS:
            raise _log_failure("contested_location_ids", "location_count")
        object.__setattr__(self, "contested_location_ids", ordered)
        if type(self.status) is not BorderDisputeStatus:
            raise _log_failure("status", "unknown_dispute_status")
        object.__setattr__(self, "evidence", _evidence_tuple(self.evidence))


@dataclass(frozen=True, slots=True)
class BordersPolicy:
    """Locked cognition constants. Runner JSON does not carry these values."""

    version: str = BORDERS_POLICY_VERSION
    min_claim_strength: float = 0.40
    max_domains: int = 8
    max_locations_per_domain: int = 8
    max_boundary_edges_per_domain: int = 32
    max_agreements: int = 8
    max_access_expectations: int = 16
    max_disputes: int = 8
    max_evidence_per_row: int = 32
    max_ledger_rows: int = 128
    max_domain_evidence_age_ticks: int = 256
    max_agreement_age_ticks: int = 128
    min_recognition_parties: int = 2
    agreement_acceptance_min_parties: int = 2
    overlap_min_locations: int = 1
    domain_contiguity_required: bool = True
    boundary_edges_observed_only: bool = True
    access_expectations_bind_commands: bool = False
    agreements_bind_commands: bool = False

    def __post_init__(self) -> None:
        if self.version != BORDERS_POLICY_VERSION:
            _LOG.error(
                "borders_policy_rejected field=version "
                "reason_code=unsupported_policy"
            )
            raise _log_failure("version", "unsupported_policy")
        expected = _policy_values()
        for name, value in expected.items():
            actual = getattr(self, name)
            if isinstance(value, bool):
                if actual is not value:
                    _LOG.error(
                        "borders_policy_rejected field=%s "
                        "reason_code=unsupported_policy",
                        name,
                    )
                    raise _log_failure(name, "unsupported_policy")
            elif isinstance(value, float):
                if _unit(name, actual) != value:
                    _LOG.error(
                        "borders_policy_rejected field=%s "
                        "reason_code=unsupported_policy",
                        name,
                    )
                    raise _log_failure(name, "unsupported_policy")
            else:
                if isinstance(actual, bool) or type(actual) is not int:
                    raise _log_failure(name, "invalid_type")
                if actual != value:
                    _LOG.error(
                        "borders_policy_rejected field=%s "
                        "reason_code=unsupported_policy",
                        name,
                    )
                    raise _log_failure(name, "unsupported_policy")
        _LOG.debug(
            "borders_policy_constructed policy_version=%s domains=%s locations=%s",
            self.version,
            self.max_domains,
            self.max_locations_per_domain,
        )


def _policy_values() -> dict[str, object]:
    return {
        "min_claim_strength": 0.40,
        "max_domains": 8,
        "max_locations_per_domain": MAX_LOCATIONS_PER_DOMAIN,
        "max_boundary_edges_per_domain": MAX_BOUNDARY_EDGES_PER_DOMAIN,
        "max_agreements": 8,
        "max_access_expectations": 16,
        "max_disputes": 8,
        "max_evidence_per_row": 32,
        "max_ledger_rows": 128,
        "max_domain_evidence_age_ticks": 256,
        "max_agreement_age_ticks": 128,
        "min_recognition_parties": 2,
        "agreement_acceptance_min_parties": 2,
        "overlap_min_locations": 1,
        "domain_contiguity_required": True,
        "boundary_edges_observed_only": True,
        "access_expectations_bind_commands": False,
        "agreements_bind_commands": False,
    }


def default_borders_policy() -> BordersPolicy:
    """Return the only accepted cognition policy."""
    return BordersPolicy()


def border_ledger_digest(ledger: BorderLedger) -> str:
    """Canonical SHA-256 over every retained row and notice."""
    if type(ledger) is not BorderLedger:
        raise _log_failure("ledger", "invalid_type")
    lines: list[str] = [f"ledger|{ledger.policy_version}|{ledger.owner_id.value}"]
    for row in ledger.domains:
        edges = ",".join(f"{left}>{right}" for left, right in row.boundary_edges)
        locations = ",".join(item.value for item in row.location_ids)
        lines.append(
            "bdc|{domain}|{owner}|{locations}|{edges}|{anchor_kind}|"
            "{anchor_ref}|{status}|{strength}|{first}|{last}".format(
                domain=row.domain_id,
                owner=row.owner_id.value,
                locations=locations,
                edges=edges,
                anchor_kind=row.anchor_kind or "-",
                anchor_ref=row.anchor_ref or "-",
                status=row.status.value,
                strength=f"{row.strength:.6f}",
                first=row.first_tick,
                last=row.last_tick,
            )
        )
    for row in ledger.recognitions:
        edges = ",".join(f"{left}>{right}" for left, right in row.boundary_edges)
        recognition_id = boundary_recognition_id(
            ledger.owner_id, row.domain_id, row.basis
        )
        lines.append(
            f"bdr|{recognition_id}|{row.domain_id}|{edges}|{row.basis.value}|"
            f"{row.status.value}"
        )
    for row in ledger.access_expectations:
        lines.append(
            "bdx|{id}|{domain}|{subject_kind}|{subject_ref}|{mode}|{status}".format(
                id=row.expectation_id,
                domain=row.domain_id,
                subject_kind=row.subject_kind.value,
                subject_ref=row.subject_ref or "-",
                mode=row.mode.value,
                status=row.status.value,
            )
        )
    for row in ledger.agreements:
        provisions = ",".join(item.value for item in row.provisions)
        lines.append(
            "bda|{id}|{domain}|{kind}|{ref}|{provisions}|{status}|{recognition}|"
            "{effective}|{expiry}".format(
                id=row.agreement_id,
                domain=row.domain_id,
                kind=row.counterparty_kind.value,
                ref=row.counterparty_ref or "-",
                provisions=provisions,
                status=row.status.value,
                recognition=row.recognition.value,
                effective="-" if row.effective_tick is None else row.effective_tick,
                expiry="-" if row.expiry_tick is None else row.expiry_tick,
            )
        )
    for row in ledger.disputes:
        contested = ",".join(item.value for item in row.contested_location_ids)
        lines.append(
            "bdd|{id}|{domain}|{kind}|{ref}|{contested}|{status}".format(
                id=row.dispute_id,
                domain=row.domain_id,
                kind=row.counterparty_kind.value,
                ref=row.counterparty_ref or "-",
                contested=contested,
                status=row.status.value,
            )
        )
    for notice in sorted(ledger.notices):
        lines.append(f"notice|{notice}")
    lines.sort()
    material = "\n".join(lines) + "\n"
    return _sha256_hex(material)


@dataclass(frozen=True, slots=True)
class BorderLedger:
    """Private border beliefs owned by one agent. There is no shared claim."""

    owner_id: AgentId
    domains: tuple[TerritorialDomainClaim, ...] = ()
    recognitions: tuple[BoundaryRecognition, ...] = ()
    access_expectations: tuple[AccessExpectation, ...] = ()
    agreements: tuple[BorderAgreement, ...] = ()
    disputes: tuple[BorderDispute, ...] = ()
    notices: tuple[str, ...] = ()
    digest: str = ""
    policy_version: str = BORDERS_POLICY_VERSION

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _log_failure("owner_id", "invalid_type")
        if self.policy_version != BORDERS_POLICY_VERSION:
            raise _log_failure("policy_version", "unsupported_policy")
        domains = _require_sequence("domains", self.domains)
        recognitions = _require_sequence("recognitions", self.recognitions)
        expectations = _require_sequence(
            "access_expectations", self.access_expectations
        )
        agreements = _require_sequence("agreements", self.agreements)
        disputes = _require_sequence("disputes", self.disputes)
        policy = default_borders_policy()
        if len(domains) > policy.max_ledger_rows * 4:
            raise _log_failure("domains", "hard_cap_exceeded")
        if len(agreements) > policy.max_ledger_rows * 4:
            raise _log_failure("agreements", "hard_cap_exceeded")
        if len(expectations) > policy.max_ledger_rows * 4:
            raise _log_failure("access_expectations", "hard_cap_exceeded")
        if len(disputes) > policy.max_ledger_rows * 4:
            raise _log_failure("disputes", "hard_cap_exceeded")
        total = (
            len(domains)
            + len(recognitions)
            + len(expectations)
            + len(agreements)
            + len(disputes)
        )
        if total > policy.max_ledger_rows * 4:
            raise _log_failure("ledger", "hard_cap_exceeded")

        checked_domains: list[TerritorialDomainClaim] = []
        domain_by_id: dict[str, TerritorialDomainClaim] = {}
        for item in domains:
            if type(item) is not TerritorialDomainClaim:
                raise _log_failure("domains", "invalid_type")
            if item.owner_id != self.owner_id:
                raise _log_failure("domains.owner_id", "owner_mismatch")
            if item.domain_id in domain_by_id:
                raise _log_failure("domains", "duplicate_domain")
            domain_by_id[item.domain_id] = item
            checked_domains.append(item)
        checked_domains.sort(key=lambda item: item.domain_id)

        checked_recognitions: list[BoundaryRecognition] = []
        recognition_keys: set[tuple[str, str]] = set()
        for item in recognitions:
            if type(item) is not BoundaryRecognition:
                raise _log_failure("recognitions", "invalid_type")
            domain = domain_by_id.get(item.domain_id)
            if domain is None:
                raise _log_failure("recognitions.domain_id", "unresolved_domain")
            if not set(item.boundary_edges).issubset(set(domain.boundary_edges)):
                raise _log_failure(
                    "recognitions.boundary_edges", "not_domain_subset"
                )
            key = (item.domain_id, item.basis.value)
            if key in recognition_keys:
                raise _log_failure("recognitions", "duplicate_recognition")
            recognition_keys.add(key)
            checked_recognitions.append(item)
        checked_recognitions.sort(
            key=lambda item: (item.domain_id, item.basis.value)
        )

        checked_expectations: list[AccessExpectation] = []
        expectation_keys: set[tuple[str, str, str]] = set()
        for item in expectations:
            if type(item) is not AccessExpectation:
                raise _log_failure("access_expectations", "invalid_type")
            if item.domain_id not in domain_by_id:
                raise _log_failure(
                    "access_expectations.domain_id", "unresolved_domain"
                )
            expected = access_expectation_id(
                self.owner_id,
                item.domain_id,
                item.subject_kind,
                item.subject_ref,
            )
            if item.expectation_id != expected:
                raise _log_failure(
                    "access_expectations.expectation_id", "expectation_id_mismatch"
                )
            key = (item.domain_id, item.subject_kind.value, item.subject_ref or "-")
            if key in expectation_keys:
                raise _log_failure("access_expectations", "duplicate_expectation")
            expectation_keys.add(key)
            checked_expectations.append(item)
        checked_expectations.sort(
            key=lambda item: (
                item.domain_id,
                item.subject_kind.value,
                item.subject_ref or "",
                item.mode.value,
            )
        )

        checked_agreements: list[BorderAgreement] = []
        agreement_keys: set[tuple[str, str, str]] = set()
        for item in agreements:
            if type(item) is not BorderAgreement:
                raise _log_failure("agreements", "invalid_type")
            if item.domain_id not in domain_by_id:
                raise _log_failure("agreements.domain_id", "unresolved_domain")
            expected = border_agreement_id(
                self.owner_id,
                item.domain_id,
                item.counterparty_kind,
                item.counterparty_ref,
            )
            if item.agreement_id != expected:
                raise _log_failure("agreements.agreement_id", "agreement_id_mismatch")
            key = (
                item.domain_id,
                item.counterparty_kind.value,
                item.counterparty_ref or "-",
            )
            if key in agreement_keys:
                raise _log_failure("agreements", "duplicate_agreement")
            agreement_keys.add(key)
            checked_agreements.append(item)
        checked_agreements.sort(
            key=lambda item: (item.domain_id, item.agreement_id)
        )

        checked_disputes: list[BorderDispute] = []
        dispute_keys: set[tuple[str, str, str]] = set()
        for item in disputes:
            if type(item) is not BorderDispute:
                raise _log_failure("disputes", "invalid_type")
            domain = domain_by_id.get(item.domain_id)
            if domain is None:
                raise _log_failure("disputes.domain_id", "unresolved_domain")
            if not set(item.contested_location_ids).issubset(
                set(domain.location_ids)
            ):
                raise _log_failure(
                    "disputes.contested_location_ids", "not_domain_subset"
                )
            expected = border_dispute_id(
                self.owner_id,
                item.domain_id,
                item.counterparty_kind,
                item.counterparty_ref,
            )
            if item.dispute_id != expected:
                raise _log_failure("disputes.dispute_id", "dispute_id_mismatch")
            key = (
                item.domain_id,
                item.counterparty_kind.value,
                item.counterparty_ref or "-",
            )
            if key in dispute_keys:
                raise _log_failure("disputes", "duplicate_dispute")
            dispute_keys.add(key)
            checked_disputes.append(item)
        checked_disputes.sort(key=lambda item: (item.domain_id, item.dispute_id))

        notices_raw = _require_sequence("notices", self.notices)
        notices: list[str] = []
        for item in notices_raw:
            if type(item) is not str:
                raise _log_failure("notices", "invalid_type")
            try:
                require_stable_id("notice", item)
            except ValueError as exc:
                raise _log_failure("notices", "invalid_type") from exc
            notices.append(item)
        notices.sort()

        object.__setattr__(self, "domains", tuple(checked_domains))
        object.__setattr__(self, "recognitions", tuple(checked_recognitions))
        object.__setattr__(self, "access_expectations", tuple(checked_expectations))
        object.__setattr__(self, "agreements", tuple(checked_agreements))
        object.__setattr__(self, "disputes", tuple(checked_disputes))
        object.__setattr__(self, "notices", tuple(notices))
        computed = border_ledger_digest(self)
        if self.digest in ("", None):
            object.__setattr__(self, "digest", computed)
        elif self.digest != computed:
            raise _log_failure("digest", "digest_mismatch")
        _LOG.debug(
            "borders_ledger_constructed domains=%s agreements=%s disputes=%s",
            len(self.domains),
            len(self.agreements),
            len(self.disputes),
        )


def empty_border_ledger(owner_id: AgentId) -> BorderLedger:
    """Return an empty ledger for one owner."""
    return BorderLedger(owner_id=owner_id)


def border_ledger_is_canonical(ledger: object) -> bool:
    """True when the ledger validates and its digest matches its content."""
    if type(ledger) is not BorderLedger:
        return False
    try:
        return ledger.digest == border_ledger_digest(ledger)
    except (TypeError, ValueError):
        return False


def require_owner_borders(
    ledger: object, owner_id: AgentId, *, field_name: str
) -> None:
    """Reject a foreign or mistyped ledger. ``None`` is passthrough."""
    if ledger is None:
        return
    if type(owner_id) is not AgentId:
        raise _log_failure("owner_id", "invalid_type")
    if type(ledger) is not BorderLedger:
        raise TypeError(f"{field_name} must be BorderLedger")
    if ledger.owner_id != owner_id:
        raise ValueError(f"{field_name} owner_id mismatch")


def border_notice(code: BorderNoticeCode) -> str:
    """Return the stable notice token without any payload."""
    if type(code) is not BorderNoticeCode:
        raise _log_failure("notice", "unknown_notice")
    return code.value


# ---------------------------------------------------------------------------
# Boundary derivation (Task 9)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BoundarySummary:
    """Counts only. Never a claim, a truth, or a score."""

    domain_count: int = 0
    observed_edge_count: int = 0
    unresolved_domain_count: int = 0
    recognized_edge_count: int = 0
    disputed_edge_count: int = 0


def observe_local_edges(
    observation: object,
) -> tuple[tuple[EntityId, EntityId], ...]:
    """Observed adjacency from the owner's current location and visible exits."""
    if observation is None:
        return ()
    self_body = getattr(observation, "self_body", None)
    origin = getattr(self_body, "location_id", None)
    if origin is None:
        location = getattr(observation, "location", None)
        origin = getattr(location, "entity_id", None)
    if type(origin) is not EntityId:
        return ()
    edges: list[tuple[EntityId, EntityId]] = []
    seen: set[tuple[str, str]] = set()
    for exit_item in getattr(observation, "exits", ()) or ():
        destination = getattr(exit_item, "destination_id", None)
        if type(destination) is not EntityId or destination == origin:
            continue
        left, right = (
            (origin.value, destination.value)
            if origin.value < destination.value
            else (destination.value, origin.value)
        )
        pair = (left, right)
        if pair in seen:
            continue
        seen.add(pair)
        edges.append((origin, destination))
    edges.sort(key=lambda pair: tuple(sorted((pair[0].value, pair[1].value))))
    return tuple(edges)


def _canonical_observed_pairs(
    observed_edges: object,
) -> tuple[tuple[str, str], ...]:
    raw = _require_sequence("observed_edges", observed_edges)
    pairs: set[tuple[str, str]] = set()
    for item in raw:
        if type(item) is not tuple or len(item) != 2:
            raise _log_failure("boundary_edge", "invalid_edge")
        left, right = item
        if type(left) is not EntityId or type(right) is not EntityId:
            raise _log_failure("boundary_edge", "unresolved_entity")
        if left == right:
            raise _log_failure("boundary_edge", "boundary_self_edge")
        pair = (
            (left.value, right.value)
            if left.value < right.value
            else (right.value, left.value)
        )
        pairs.add(pair)
    return tuple(sorted(pairs))


def boundary_edges_for_domain(
    location_ids: Sequence[EntityId],
    observed_edges: Sequence[tuple[EntityId, EntityId]],
) -> tuple[tuple[str, str], ...]:
    """Canonical observed pairs crossing exactly one domain endpoint."""
    ordered = require_location_set(location_ids, field_name="location_ids")
    inside = {item.value for item in ordered}
    pairs = _canonical_observed_pairs(observed_edges)
    boundary = [
        pair
        for pair in pairs
        if (pair[0] in inside) != (pair[1] in inside)
    ]
    if len(boundary) > MAX_BOUNDARY_EDGES_PER_DOMAIN:
        raise _log_failure("boundary_edges", "edge_count")
    return tuple(boundary)


def unobserved_domain_locations(
    location_ids: Sequence[EntityId],
    observed_edges: Sequence[tuple[EntityId, EntityId]],
) -> tuple[EntityId, ...]:
    """In-set locations with no observed incident edge."""
    ordered = require_location_set(location_ids, field_name="location_ids")
    pairs = _canonical_observed_pairs(observed_edges)
    touched = {value for pair in pairs for value in pair}
    return tuple(item for item in ordered if item.value not in touched)


def boundary_summary(ledger: BorderLedger) -> BoundarySummary:
    """Counts of domains, edges, and recognition statuses."""
    if type(ledger) is not BorderLedger:
        raise _log_failure("ledger", "invalid_type")
    domains = {item.domain_id: item for item in ledger.domains}
    observed: set[tuple[str, str]] = set()
    for item in ledger.domains:
        observed.update(item.boundary_edges)
    recognized: set[tuple[str, str]] = set()
    disputed: set[tuple[str, str]] = set()
    unresolved_domains: set[str] = set()
    for item in ledger.recognitions:
        if item.status is BoundaryStatus.RECOGNIZED:
            recognized.update(item.boundary_edges)
        elif item.status is BoundaryStatus.DISPUTED:
            disputed.update(item.boundary_edges)
        elif item.status is BoundaryStatus.UNRESOLVED:
            unresolved_domains.add(item.domain_id)
    for domain_id, domain in domains.items():
        if not domain.boundary_edges:
            unresolved_domains.add(domain_id)
    recognized -= disputed
    return BoundarySummary(
        domain_count=len(domains),
        observed_edge_count=len(observed),
        unresolved_domain_count=len(unresolved_domains),
        recognized_edge_count=len(recognized),
        disputed_edge_count=len(disputed),
    )


# ---------------------------------------------------------------------------
# Caps, notices, and metadata-only export (Task 10)
# ---------------------------------------------------------------------------


def _opaque_token(prefix: str, value: str) -> str:
    return _short_token(prefix, value)


def border_owner_token(owner_id: AgentId) -> str:
    if type(owner_id) is not AgentId:
        raise _log_failure("owner_id", "invalid_type")
    return _opaque_token("bown-", owner_id.value)


def border_location_token(entity_id: EntityId) -> str:
    if type(entity_id) is not EntityId:
        raise _log_failure("entity_id", "unresolved_entity")
    return _opaque_token("bloc-", entity_id.value)


def border_anchor_token(value: str) -> str:
    if type(value) is not str:
        raise _log_failure("anchor", "invalid_identifier")
    return _opaque_token("banc-", value)


@dataclass(frozen=True, slots=True)
class BorderExportRow:
    """Metadata-only detached row. Never contains a raw id or body."""

    row_kind: str
    row_id: str
    owner_token: str
    domain_token: str
    location_tokens: tuple[str, ...] = ()
    edge_tokens: tuple[tuple[str, str], ...] = ()
    status: str = ""
    mode: str = ""
    anchor_token: str = ""
    counterparty_token: str = ""
    subject_token: str = ""
    provision_tokens: tuple[str, ...] = ()
    effective_tick: int | None = None
    expiry_tick: int | None = None
    strength: float = 0.0
    basis: str = ""
    recognition: str = ""

    def __post_init__(self) -> None:
        if self.row_kind not in {
            "claim",
            "recognition",
            "access",
            "agreement",
            "dispute",
        }:
            raise _log_failure("row_kind", "unknown_row_kind")
        for name in ("row_id", "owner_token", "domain_token"):
            if type(getattr(self, name)) is not str or not getattr(self, name):
                raise _log_failure(name, "invalid_identifier")
        object.__setattr__(
            self, "location_tokens", tuple(self.location_tokens)
        )
        object.__setattr__(self, "edge_tokens", tuple(self.edge_tokens))
        object.__setattr__(
            self, "provision_tokens", tuple(self.provision_tokens)
        )


def _domain_edges_tokens(
    edges: tuple[tuple[str, str], ...],
) -> tuple[tuple[str, str], ...]:
    return tuple(
        (_opaque_token("bloc-", left), _opaque_token("bloc-", right))
        for left, right in edges
    )


def export_border_rows(ledger: BorderLedger) -> tuple[BorderExportRow, ...]:
    """One metadata-only row per retained belief row."""
    if type(ledger) is not BorderLedger:
        raise _log_failure("ledger", "invalid_type")
    owner_token = border_owner_token(ledger.owner_id)
    rows: list[BorderExportRow] = []
    for item in ledger.domains:
        rows.append(
            BorderExportRow(
                row_kind="claim",
                row_id=item.domain_id,
                owner_token=owner_token,
                domain_token=item.domain_id,
                location_tokens=tuple(
                    border_location_token(location)
                    for location in item.location_ids
                ),
                edge_tokens=_domain_edges_tokens(item.boundary_edges),
                status=item.status.value,
                anchor_token=(
                    ""
                    if item.anchor_ref is None
                    else border_anchor_token(item.anchor_ref)
                ),
                strength=item.strength,
            )
        )
    for item in ledger.recognitions:
        rows.append(
            BorderExportRow(
                row_kind="recognition",
                row_id=boundary_recognition_id(
                    ledger.owner_id, item.domain_id, item.basis
                ),
                owner_token=owner_token,
                domain_token=item.domain_id,
                edge_tokens=_domain_edges_tokens(item.boundary_edges),
                status=item.status.value,
                basis=item.basis.value,
            )
        )
    for item in ledger.access_expectations:
        rows.append(
            BorderExportRow(
                row_kind="access",
                row_id=item.expectation_id,
                owner_token=owner_token,
                domain_token=item.domain_id,
                status=item.status.value,
                mode=item.mode.value,
                subject_token=(
                    ""
                    if item.subject_ref is None
                    else _opaque_token("bsub-", item.subject_ref)
                ),
            )
        )
    for item in ledger.agreements:
        rows.append(
            BorderExportRow(
                row_kind="agreement",
                row_id=item.agreement_id,
                owner_token=owner_token,
                domain_token=item.domain_id,
                status=item.status.value,
                counterparty_token=(
                    ""
                    if item.counterparty_ref is None
                    else _opaque_token("bcp-", item.counterparty_ref)
                ),
                provision_tokens=tuple(
                    provision.value for provision in item.provisions
                ),
                effective_tick=item.effective_tick,
                expiry_tick=item.expiry_tick,
                recognition=item.recognition.value,
            )
        )
    for item in ledger.disputes:
        rows.append(
            BorderExportRow(
                row_kind="dispute",
                row_id=item.dispute_id,
                owner_token=owner_token,
                domain_token=item.domain_id,
                location_tokens=tuple(
                    border_location_token(location)
                    for location in item.contested_location_ids
                ),
                status=item.status.value,
                counterparty_token=(
                    ""
                    if item.counterparty_ref is None
                    else _opaque_token("bcp-", item.counterparty_ref)
                ),
            )
        )
    rows.sort(key=lambda item: (item.row_kind, item.row_id))
    return tuple(rows)


def border_export_digest(rows: Sequence[BorderExportRow]) -> str:
    """Canonical digest of metadata-only export rows."""
    raw = _require_sequence("rows", rows)
    lines: list[str] = []
    for item in raw:
        if type(item) is not BorderExportRow:
            raise _log_failure("rows", "invalid_type")
        lines.append(
            "|".join(
                (
                    item.row_kind,
                    item.row_id,
                    item.owner_token,
                    item.domain_token,
                    ",".join(item.location_tokens),
                    ",".join(f"{a}>{b}" for a, b in item.edge_tokens),
                    item.status,
                    item.mode,
                    item.anchor_token,
                    item.counterparty_token,
                    item.subject_token,
                    ",".join(item.provision_tokens),
                    "-" if item.effective_tick is None else str(item.effective_tick),
                    "-" if item.expiry_tick is None else str(item.expiry_tick),
                    f"{item.strength:.6f}",
                    item.basis,
                    item.recognition,
                )
            )
        )
    lines.sort()
    return _sha256_hex("\n".join(lines) + "\n")


def borders_notice_counts(ledger: BorderLedger) -> tuple[tuple[str, int], ...]:
    """Sorted ``(code, count)`` pairs. Notices contain no payload."""
    if type(ledger) is not BorderLedger:
        raise _log_failure("ledger", "invalid_type")
    counts: dict[str, int] = {}
    for notice in ledger.notices:
        counts[notice] = counts.get(notice, 0) + 1
    return tuple(sorted(counts.items()))


def _evidence_reference_tick(ledger: BorderLedger) -> int:
    ticks = [item.last_tick for item in ledger.domains]
    return max(ticks) if ticks else 0


def _prune_domain_evidence(
    domain: TerritorialDomainClaim, reference_tick: int, policy: BordersPolicy
) -> TerritorialDomainClaim:
    kept = tuple(
        item
        for item in domain.evidence
        if reference_tick - item.source_tick <= policy.max_domain_evidence_age_ticks
    )
    if len(kept) == len(domain.evidence):
        return domain
    ratio = 0.0 if not domain.evidence else len(kept) / len(domain.evidence)
    return dataclasses_replace(
        domain,
        evidence=kept,
        strength=_quantize(domain.strength * ratio),
    )


def validate_border_ledger_caps(
    ledger: BorderLedger, policy: BordersPolicy | None = None
) -> None:
    """Reject a persisted ledger above the exact cognition caps.

    Low-level construction keeps a wider hard cap so ``enforce_borders_limits``
    can prune an over-cap candidate before it is persisted or checkpointed.
    """
    if type(ledger) is not BorderLedger:
        raise TypeError("ledger must be BorderLedger")
    effective = default_borders_policy() if policy is None else policy
    if type(effective) is not BordersPolicy:
        raise TypeError("policy must be BordersPolicy")
    for name, rows, cap in (
        ("domains", ledger.domains, effective.max_domains),
        ("agreements", ledger.agreements, effective.max_agreements),
        (
            "access_expectations",
            ledger.access_expectations,
            effective.max_access_expectations,
        ),
        ("disputes", ledger.disputes, effective.max_disputes),
    ):
        if len(rows) > cap:
            raise ValueError(f"borders_capacity_reached:{name}")
    total = (
        len(ledger.domains)
        + len(ledger.recognitions)
        + len(ledger.access_expectations)
        + len(ledger.agreements)
        + len(ledger.disputes)
    )
    if total > effective.max_ledger_rows:
        raise ValueError("borders_capacity_reached:ledger")


def enforce_borders_limits(
    ledger: BorderLedger, policy: BordersPolicy
) -> BorderLedger:
    """Deterministically prune droppable rows and fail closed on active overflow."""
    if type(ledger) is not BorderLedger:
        raise TypeError("ledger must be BorderLedger")
    if type(policy) is not BordersPolicy:
        raise TypeError("policy must be BordersPolicy")
    reference_tick = _evidence_reference_tick(ledger)
    pruned: set[str] = set()

    domains = [
        _prune_domain_evidence(item, reference_tick, policy)
        for item in ledger.domains
    ]
    if any(
        len(item.evidence) != len(source.evidence)
        for item, source in zip(domains, ledger.domains, strict=True)
    ):
        pruned.add("evidence")

    access_rows = list(ledger.access_expectations)
    if len(access_rows) > policy.max_access_expectations:
        terminal_access = sorted(
            (
                item
                for item in access_rows
                if item.status
                in {
                    AccessExpectationStatus.EXPIRED,
                    AccessExpectationStatus.WITHDRAWN,
                }
            ),
            key=lambda item: item.expectation_id,
        )
        excess = len(access_rows) - policy.max_access_expectations
        for item in terminal_access[:excess]:
            access_rows.remove(item)
        if len(access_rows) > policy.max_access_expectations:
            raise ValueError("borders_capacity_reached")
        if terminal_access:
            pruned.add("access_expectations")

    disputes = list(ledger.disputes)
    if len(disputes) > policy.max_disputes:
        terminal_disputes = sorted(
            (
                item
                for item in disputes
                if item.status
                in {
                    BorderDisputeStatus.WITHDRAWN,
                    BorderDisputeStatus.EXPIRED,
                }
            ),
            key=lambda item: item.dispute_id,
        )
        excess = len(disputes) - policy.max_disputes
        for item in terminal_disputes[:excess]:
            disputes.remove(item)
        if len(disputes) > policy.max_disputes:
            raise ValueError("borders_capacity_reached")
        if terminal_disputes:
            pruned.add("disputes")

    agreements = list(ledger.agreements)
    if len(agreements) > policy.max_agreements:
        terminal_agreements = sorted(
            (
                item
                for item in agreements
                if item.status
                in {
                    AgreementStatus.WITHDRAWN,
                    AgreementStatus.EXPIRED,
                    AgreementStatus.SUPERSEDED,
                }
                or (item.expiry_tick is not None and item.expiry_tick < reference_tick)
            ),
            key=lambda item: item.agreement_id,
        )
        excess = len(agreements) - policy.max_agreements
        for item in terminal_agreements[:excess]:
            agreements.remove(item)
        if len(agreements) > policy.max_agreements:
            raise ValueError("borders_capacity_reached")
        if terminal_agreements:
            pruned.add("agreements")

    expired_domains = sorted(
        (
            item
            for item in domains
            if item.status is DomainClaimStatus.EXPIRED
        ),
        key=lambda item: item.domain_id,
    )
    if expired_domains and len(domains) > policy.max_domains:
        excess = len(domains) - policy.max_domains
        for item in expired_domains[:excess]:
            domains.remove(item)
        pruned.add("domains")
    if len(domains) > policy.max_domains:
        raise ValueError("borders_capacity_reached")

    recognitions = list(ledger.recognitions)
    total = (
        len(domains)
        + len(recognitions)
        + len(access_rows)
        + len(agreements)
        + len(disputes)
    )
    if total > policy.max_ledger_rows:
        # Drop terminal rows in a fixed family order before failing closed.
        while total > policy.max_ledger_rows and access_rows:
            if access_rows[-1].status in {
                AccessExpectationStatus.EXPIRED,
                AccessExpectationStatus.WITHDRAWN,
            }:
                access_rows.pop()
                pruned.add("access_expectations")
                total -= 1
            else:
                break
        while total > policy.max_ledger_rows and disputes:
            if disputes[-1].status in {
                BorderDisputeStatus.WITHDRAWN,
                BorderDisputeStatus.EXPIRED,
            }:
                disputes.pop()
                pruned.add("disputes")
                total -= 1
            else:
                break
        while total > policy.max_ledger_rows and agreements:
            if agreements[-1].status in {
                AgreementStatus.WITHDRAWN,
                AgreementStatus.EXPIRED,
                AgreementStatus.SUPERSEDED,
            }:
                agreements.pop()
                pruned.add("agreements")
                total -= 1
            else:
                break
        while total > policy.max_ledger_rows and recognitions:
            recognitions.pop()
            pruned.add("recognitions")
            total -= 1
        if total > policy.max_ledger_rows:
            raise ValueError("borders_capacity_reached")

    notices = set(ledger.notices)
    for family in sorted(pruned):
        notices.add(f"borders_truncated:{family}")
    return BorderLedger(
        owner_id=ledger.owner_id,
        domains=tuple(domains),
        recognitions=tuple(recognitions),
        access_expectations=tuple(access_rows),
        agreements=tuple(agreements),
        disputes=tuple(disputes),
        notices=tuple(sorted(notices)),
        policy_version=ledger.policy_version,
    )


# ---------------------------------------------------------------------------
# Ordered territorial-domain update pipeline (Task 6)
# ---------------------------------------------------------------------------

_MISSING: Final[object] = object()
_ACT_ORDER: Final[dict[str, int]] = {
    AgreementAct.CLAIM_DOMAIN.value: 0,
    AgreementAct.PROPOSE.value: 1,
    AgreementAct.ACCEPT.value: 2,
    AgreementAct.REJECT.value: 3,
    AgreementAct.RECOGNIZE.value: 4,
    AgreementAct.EXPECT_ACCESS.value: 5,
    AgreementAct.WITHDRAW.value: 6,
    AgreementAct.DISPUTE_DOMAIN.value: 7,
}


def _reject_forbidden_input(value: object) -> None:
    if type(value).__name__ in _FORBIDDEN_INPUT_TYPES:
        raise TypeError(f"{type(value).__name__}: forbidden_input")


def _claimed_locations(
    territorial_claims: object | None, policy: BordersPolicy
) -> list[EntityId]:
    if territorial_claims is None:
        return []
    claims = getattr(territorial_claims, "claims", None)
    if claims is None:
        return []
    locations: dict[str, EntityId] = {}
    for claim in claims:
        target_kind = getattr(claim, "target_kind", None)
        kind_value = getattr(target_kind, "value", None)
        if kind_value not in {"location", "frequent_area"}:
            continue
        strength = getattr(claim, "strength", 0.0)
        if (
            not isinstance(strength, (int, float))
            or strength < policy.min_claim_strength
        ):
            continue
        target = getattr(claim, "target_entity_id", None)
        if type(target) is not EntityId:
            continue
        locations[target.value] = target
    return [locations[key] for key in sorted(locations)]


def _prior_observed_edges(
    prior: BorderLedger,
) -> list[tuple[EntityId, EntityId]]:
    edges: dict[tuple[str, str], tuple[EntityId, EntityId]] = {}
    for domain in prior.domains:
        for left, right in (*domain.boundary_edges, *domain.observed_edges):
            try:
                a = EntityId(left)
                b = EntityId(right)
            except ValueError:
                continue
            key = (a.value, b.value) if a.value < b.value else (b.value, a.value)
            edges[key] = (a, b)
    return [edges[key] for key in sorted(edges)]


def _components(
    locations: Sequence[EntityId],
    observed_edges: Sequence[tuple[EntityId, EntityId]],
    *,
    contiguity_required: bool,
) -> list[tuple[EntityId, ...]]:
    if not locations:
        return []
    values = {item.value: item for item in locations}
    if not contiguity_required:
        return [tuple(sorted(locations, key=lambda item: item.value))]
    adjacency: dict[str, set[str]] = {value: set() for value in values}
    for left, right in observed_edges:
        if left.value in values and right.value in values:
            adjacency[left.value].add(right.value)
            adjacency[right.value].add(left.value)
    seen: set[str] = set()
    components: list[tuple[EntityId, ...]] = []
    for value in sorted(values):
        if value in seen:
            continue
        stack = [value]
        seen.add(value)
        component: list[str] = []
        while stack:
            current = stack.pop()
            component.append(current)
            for neighbour in sorted(adjacency[current]):
                if neighbour not in seen:
                    seen.add(neighbour)
                    stack.append(neighbour)
        components.append(
            tuple(values[item] for item in sorted(component))
        )
    return components


def _internal_observed_edges(
    component: Sequence[EntityId],
    observed_edges: Sequence[tuple[EntityId, EntityId]],
) -> tuple[tuple[str, str], ...]:
    """Retain observed adjacency wholly inside one logical domain."""
    values = {item.value for item in component}
    edges: set[tuple[str, str]] = set()
    for left, right in observed_edges:
        if left.value in values and right.value in values:
            edge = boundary_edge(left, right)
            edges.add(edge)
    return tuple(sorted(edges))


def _own_domain_for_locations(
    domains: Sequence[TerritorialDomainClaim], locations: Sequence[str]
) -> TerritorialDomainClaim | None:
    location_set = set(locations)
    for domain in domains:
        if {item.value for item in domain.location_ids} == location_set:
            return domain
    return None


def _anchor_notices(
    frame: object,
    *,
    identity: object | None,
    organization_concepts: object | None,
    diplomacy: object | None,
    observation: object,
    notices: set[str],
) -> None:
    kind = getattr(frame, "party_kind", None)
    ref = getattr(frame, "party_ref", None)
    if ref is None:
        return
    if getattr(kind, "value", None) == "organization":
        concepts = getattr(organization_concepts, "concepts", ()) or ()
        if not any(
            getattr(item, "organization_id", None) == ref for item in concepts
        ):
            notices.add(BorderNoticeCode.UNRESOLVED_ANCHOR.value)
        return
    if getattr(kind, "value", None) == "settlement":
        regional = getattr(observation, "regional_context", None)
        if getattr(regional, "region_id", None) != ref:
            notices.add(BorderNoticeCode.UNRESOLVED_ANCHOR.value)
        return
    if getattr(kind, "value", None) == "agent":
        if identity is None:
            notices.add(BorderNoticeCode.UNRESOLVED_ANCHOR.value)
            return
        tokens = {
            getattr(getattr(binding, "agent_id", None), "value", None)
            for binding in getattr(identity, "counterparts", ()) or ()
        }
        if ref not in tokens:
            notices.add(BorderNoticeCode.UNRESOLVED_ANCHOR.value)
        return
    if getattr(kind, "value", None) == "diplomacy" or str(ref).startswith("dpg-"):
        versions = getattr(diplomacy, "treaty_versions", ()) or ()
        if not any(
            getattr(item, "treaty_id", None) == ref for item in versions
        ):
            notices.add(BorderNoticeCode.UNRESOLVED_ANCHOR.value)


def apply_borders_update(
    *,
    owner_id: AgentId,
    tick: int,
    observation: object,
    territorial_claims: object | None,
    prior: BorderLedger | None,
    identity: object | None,
    organization_concepts: object | None,
    diplomacy: object | None,
    policy: BordersPolicy,
    inbox: Sequence[object] | None = None,
    world_state: object = _MISSING,
    world_event: object = _MISSING,
) -> BorderLedger:
    """One owner's fixed-order border belief update.

    Peer input is testimony. Silence never creates a claim, agreement,
    recognition, access expectation, or dispute. No branch returns a command.
    """
    if world_state is not _MISSING or world_event is not _MISSING:
        raise TypeError("forbidden_input")
    if type(owner_id) is not AgentId:
        raise ValueError("owner_id: invalid_type")
    if type(tick) is not int or isinstance(tick, bool) or tick < 0:
        raise ValueError("tick: invalid_tick")
    if type(policy) is not BordersPolicy:
        raise TypeError("policy must be BordersPolicy")
    if observation is None:
        raise ValueError("observation: invalid_type")
    _reject_forbidden_input(observation)
    if prior is not None:
        require_owner_borders(prior, owner_id, field_name="prior")
    base = prior if prior is not None else empty_border_ledger(owner_id)

    from agents.cognition.borders_communication import border_frame_deliveries

    notices: set[str] = set()
    observed_edges = list(observe_local_edges(observation))
    observed_edges.extend(_prior_observed_edges(base))
    locations = _claimed_locations(territorial_claims, policy)
    components = _components(
        locations,
        observed_edges,
        contiguity_required=policy.domain_contiguity_required,
    )

    prior_by_set = {
        tuple(item.value for item in domain.location_ids): domain
        for domain in base.domains
        if domain.status is not DomainClaimStatus.EXPIRED
    }
    domains: list[TerritorialDomainClaim] = []
    reused_ids: set[str] = set()
    for component in components:
        key = tuple(item.value for item in component)
        old = prior_by_set.get(key)
        current_observed = _internal_observed_edges(component, observed_edges)
        if old is not None:
            domain = dataclasses_replace(
                old,
                status=DomainClaimStatus.CLAIMED,
                last_tick=max(old.last_tick, tick),
                boundary_edges=tuple(
                    sorted(
                        set(old.boundary_edges)
                        | set(
                            boundary_edges_for_domain(
                                component, observed_edges
                            )
                        )
                    )
                ),
                observed_edges=tuple(
                    sorted(set(old.observed_edges) | set(current_observed))
                ),
            )
        else:
            edges = boundary_edges_for_domain(component, observed_edges)
            domain = TerritorialDomainClaim(
                domain_id=domain_claim_id(owner_id, component),
                owner_id=owner_id,
                location_ids=component,
                boundary_edges=edges,
                anchor_kind=None,
                anchor_ref=None,
                status=DomainClaimStatus.CLAIMED,
                strength=1.0,
                first_tick=tick,
                last_tick=tick,
                observed_edges=current_observed,
            )
        reused_ids.add(domain.domain_id)
        if not domain.boundary_edges:
            notices.add(BorderNoticeCode.BOUNDARY_UNOBSERVED.value)
        domains.append(domain)

    for old in base.domains:
        if old.domain_id in reused_ids:
            continue
        if old.status is DomainClaimStatus.EXPIRED:
            domains.append(old)
            continue
        domains.append(
            dataclasses_replace(
                old,
                status=DomainClaimStatus.EXPIRED,
                last_tick=max(old.last_tick, tick),
            )
        )
    if len(domains) > policy.max_domains:
        # Prefer current components; keep the most recent expired rows only.
        active = [item for item in domains if item.domain_id in reused_ids]
        expired = [item for item in domains if item.domain_id not in reused_ids]
        domains = active + expired[: max(0, policy.max_domains - len(active))]

    deliveries = border_frame_deliveries(
        observation, inbox=inbox, identity=identity
    )
    if not deliveries and _has_border_relations(observation, inbox):
        notices.add(BorderNoticeCode.MALFORMED_FRAME.value)
    ordered = sorted(
        deliveries,
        key=lambda item: (
            _ACT_ORDER.get(getattr(item[1].act, "value", ""), 99),
            item[0],
            item[1].domain_id,
        ),
    )

    peer_claims: dict[tuple[str, str], tuple[str, tuple[str, ...]]] = {}
    agreements: list[BorderAgreement] = list(base.agreements)
    access_rows: list[AccessExpectation] = list(base.access_expectations)
    explicit_disputes: list[BorderDispute] = list(base.disputes)
    recognition_sources: dict[str, set[str]] = {}
    agreement_domains: dict[str, set[str]] = {}

    def counterparty_for(
        frame: object, speaker: str
    ) -> tuple[CounterpartyKind, str]:
        # The speaking party is the only counterparty this owner can verify.
        # A frame-declared party is testimony about someone else and is never
        # promoted to the agreement counterparty.
        del frame
        if not speaker:
            return CounterpartyKind.UNKNOWN, ""
        return CounterpartyKind.AGENT, speaker

    for speaker, frame in ordered:
        domain = _own_domain_for_locations(domains, frame.locations)
        _anchor_notices(
            frame,
            identity=identity,
            organization_concepts=organization_concepts,
            diplomacy=diplomacy,
            observation=observation,
            notices=notices,
        )
        act = frame.act
        if act is AgreementAct.CLAIM_DOMAIN:
            peer_claims[(speaker, frame.domain_id)] = (
                frame.domain_id,
                frame.locations,
            )
            continue
        if act is AgreementAct.PROPOSE:
            if domain is None:
                notices.add(BorderNoticeCode.PEER_CLAIM_UNTRUSTED.value)
                continue
            kind, ref = counterparty_for(frame, speaker)
            provision = (
                frame.provision
                if frame.provision is not None
                else AgreementProvision.UNKNOWN
            )
            proposer = None
            try:
                proposer = AgentId(speaker)
            except (TypeError, ValueError):
                proposer = None
            agreement = BorderAgreement(
                agreement_id=border_agreement_id(
                    owner_id, domain.domain_id, kind, ref
                ),
                domain_id=domain.domain_id,
                counterparty_kind=kind,
                counterparty_ref=ref,
                provisions=(provision,),
                status=AgreementStatus.PROPOSED,
                recognition=BoundaryStatus.UNRESOLVED,
                effective_tick=tick,
                expiry_tick=frame.expiry_tick,
                evidence=(
                    BorderEvidence(
                        kind=BoundaryBasis.TESTIMONY,
                        source_owner_id=proposer,
                        source_tick=tick,
                        lineage_ref=frame.domain_id,
                    ),
                ),
            )
            agreements = [
                item
                for item in agreements
                if item.agreement_id != agreement.agreement_id
            ]
            agreements.append(agreement)
            continue
        if act is AgreementAct.ACCEPT:
            if domain is None:
                continue
            target = _agreement_for_speaker(
                agreements=agreements,
                base=base,
                domain_id=domain.domain_id,
                speaker=speaker,
            )
            if target is None or _proposed_by(target, speaker):
                target = _acceptance_target(
                    agreements=agreements,
                    base=base,
                    domain_id=domain.domain_id,
                    speaker=speaker,
                )
            if target is None:
                continue
            updated = dataclasses_replace(
                target,
                status=AgreementStatus.APPARENT_ACCEPTANCE,
                recognition=BoundaryStatus.RECOGNIZED,
            )
            agreements = [
                updated
                if item.agreement_id == updated.agreement_id
                else item
                for item in agreements
            ]
            if AgreementProvision.TERRITORIAL_ACKNOWLEDGEMENT in target.provisions:
                agreement_domains.setdefault(domain.domain_id, set()).add(speaker)
            continue
        if act in (AgreementAct.REJECT, AgreementAct.WITHDRAW):
            if domain is None:
                continue
            target = _agreement_for_speaker(
                agreements=agreements,
                base=base,
                domain_id=domain.domain_id,
                speaker=speaker,
            )
            if target is None:
                continue
            updated = dataclasses_replace(
                target, status=AgreementStatus.WITHDRAWN
            )
            agreements = [
                updated
                if item.agreement_id == updated.agreement_id
                else item
                for item in agreements
            ]
            continue
        if act is AgreementAct.RECOGNIZE:
            if domain is None:
                continue
            recognition_sources.setdefault(domain.domain_id, set()).add(speaker)
            if any(
                agreement.domain_id == domain.domain_id
                and AgreementProvision.TERRITORIAL_ACKNOWLEDGEMENT
                in agreement.provisions
                and agreement.status
                in {
                    AgreementStatus.APPARENT_ACCEPTANCE,
                    AgreementStatus.RECOGNIZED,
                }
                for agreement in (*agreements, *base.agreements)
            ):
                agreement_domains.setdefault(domain.domain_id, set()).add(speaker)
            continue
        if act is AgreementAct.EXPECT_ACCESS:
            if domain is None:
                continue
            if frame.party_kind is CounterpartyKind.ORGANIZATION:
                subject_kind = AccessSubjectKind.ORGANIZATION
                subject_ref = frame.party_ref
            elif frame.party_kind is CounterpartyKind.AGENT and frame.party_ref:
                subject_kind = AccessSubjectKind.OTHER_AGENT
                subject_ref = frame.party_ref
            else:
                subject_kind = AccessSubjectKind.UNKNOWN
                subject_ref = None
            try:
                row = AccessExpectation(
                    expectation_id=access_expectation_id(
                        owner_id,
                        domain.domain_id,
                        subject_kind,
                        subject_ref,
                    ),
                    domain_id=domain.domain_id,
                    subject_kind=subject_kind,
                    subject_ref=subject_ref,
                    mode=frame.access_mode or AccessExpectationMode.UNKNOWN,
                    status=AccessExpectationStatus.EXPECTED,
                )
            except ValueError:
                notices.add(BorderNoticeCode.MALFORMED_FRAME.value)
                continue
            access_rows = [
                item
                for item in access_rows
                if item.expectation_id != row.expectation_id
            ]
            access_rows.append(row)
            continue
        if act is AgreementAct.DISPUTE_DOMAIN:
            if domain is None:
                continue
            contested = tuple(
                item
                for item in domain.location_ids
                if item.value in set(frame.locations)
            )
            if not contested:
                continue
            kind, ref = counterparty_for(frame, speaker)
            explicit_disputes.append(
                BorderDispute(
                    dispute_id=border_dispute_id(
                        owner_id, domain.domain_id, kind, ref
                    ),
                    domain_id=domain.domain_id,
                    counterparty_kind=kind,
                    counterparty_ref=ref,
                    contested_location_ids=contested,
                    status=BorderDisputeStatus.ACTIVE,
                )
            )

    # Merge retained prior rows with this update.
    agreements = _merge_by_id(base.agreements, agreements)
    access_rows = _merge_by_id(base.access_expectations, access_rows)
    disputes = _merge_by_id(base.disputes, explicit_disputes)

    # Overlap and dispute derivation from retained peer claims.
    disputed_domains: set[str] = set()
    for domain in domains:
        if domain.domain_id not in reused_ids:
            continue
        location_values = {item.value for item in domain.location_ids}
        for (speaker, _), (_, peer_locations) in sorted(peer_claims.items()):
            shared = location_values & set(peer_locations)
            if len(shared) < policy.overlap_min_locations:
                continue
            notices.add(BorderNoticeCode.OVERLAP_DETECTED.value)
            if set(peer_locations) == location_values:
                recognition_sources.setdefault(domain.domain_id, set()).add(
                    speaker
                )
            if _covered_by_agreement(
                domain.domain_id, speaker, agreements
            ):
                continue
            disputed_domains.add(domain.domain_id)
            counterparty_ref = speaker
            try:
                dispute = BorderDispute(
                    dispute_id=border_dispute_id(
                        owner_id,
                        domain.domain_id,
                        CounterpartyKind.AGENT,
                        counterparty_ref,
                    ),
                    domain_id=domain.domain_id,
                    counterparty_kind=CounterpartyKind.AGENT,
                    counterparty_ref=counterparty_ref,
                    contested_location_ids=tuple(
                        item
                        for item in domain.location_ids
                        if item.value in shared
                    ),
                    status=BorderDisputeStatus.ACTIVE,
                )
            except ValueError:
                continue
            disputes = _merge_by_id(disputes, (dispute,))

    # A retained territorial-acknowledgement agreement remains a distinct
    # recognition source on later updates; it is not re-derived from silence.
    for agreement in (*agreements, *base.agreements):
        if (
            agreement.status
            in {
                AgreementStatus.APPARENT_ACCEPTANCE,
                AgreementStatus.RECOGNIZED,
            }
            and AgreementProvision.TERRITORIAL_ACKNOWLEDGEMENT
            in agreement.provisions
            and agreement.counterparty_ref is not None
        ):
            agreement_domains.setdefault(agreement.domain_id, set()).add(
                agreement.counterparty_ref
            )

    # Derive recognition status and rows.
    recognitions: list[BoundaryRecognition] = []
    updated_domains: list[TerritorialDomainClaim] = []
    for domain in domains:
        sources = recognition_sources.get(domain.domain_id, set())
        agreement_sources = agreement_domains.get(domain.domain_id, set())
        distinct_sources = sources | agreement_sources
        disputed = domain.domain_id in disputed_domains
        recognized = (
            not disputed
            and len(distinct_sources) >= policy.min_recognition_parties - 1
        )
        if domain.domain_id in reused_ids:
            if disputed:
                status = DomainClaimStatus.DISPUTED
            elif recognized:
                status = DomainClaimStatus.RECOGNIZED
            else:
                status = DomainClaimStatus.CLAIMED
            domain = dataclasses_replace(domain, status=status)
        updated_domains.append(domain)
        if domain.domain_id not in reused_ids:
            continue
        own_status = (
            BoundaryStatus.DISPUTED
            if disputed
            else BoundaryStatus.RECOGNIZED
            if recognized
            else BoundaryStatus.UNRESOLVED
        )
        recognitions.append(
            BoundaryRecognition(
                domain_id=domain.domain_id,
                boundary_edges=domain.boundary_edges,
                basis=BoundaryBasis.OWN_CLAIM,
                status=own_status,
            )
        )
        if domain.boundary_edges:
            recognitions.append(
                BoundaryRecognition(
                    domain_id=domain.domain_id,
                    boundary_edges=domain.boundary_edges,
                    basis=BoundaryBasis.DIRECT_OBSERVATION,
                    status=(
                        BoundaryStatus.DISPUTED
                        if disputed
                        else BoundaryStatus.RECOGNIZED
                    ),
                )
            )
        if sources:
            recognitions.append(
                BoundaryRecognition(
                    domain_id=domain.domain_id,
                    boundary_edges=domain.boundary_edges,
                    basis=BoundaryBasis.TESTIMONY,
                    status=(
                        BoundaryStatus.DISPUTED
                        if disputed
                        else BoundaryStatus.RECOGNIZED
                    ),
                )
            )
        if agreement_sources:
            recognitions.append(
                BoundaryRecognition(
                    domain_id=domain.domain_id,
                    boundary_edges=domain.boundary_edges,
                    basis=BoundaryBasis.AGREEMENT,
                    status=(
                        BoundaryStatus.DISPUTED
                        if disputed
                        else BoundaryStatus.RECOGNIZED
                    ),
                )
            )
    recognitions = _merge_by_id(recognitions, ())

    # Expire agreements whose declared expiry passed.
    expired_agreements: list[BorderAgreement] = []
    for agreement in agreements:
        if agreement.expiry_tick is not None and agreement.expiry_tick < tick:
            expired_agreements.append(
                dataclasses_replace(
                    agreement, status=AgreementStatus.EXPIRED
                )
            )
        else:
            expired_agreements.append(agreement)
    agreements = expired_agreements

    candidate = BorderLedger(
        owner_id=owner_id,
        domains=tuple(updated_domains),
        recognitions=tuple(recognitions),
        access_expectations=tuple(access_rows),
        agreements=tuple(agreements),
        disputes=tuple(disputes),
        notices=tuple(sorted(notices)),
        policy_version=policy.version,
    )
    try:
        result = enforce_borders_limits(candidate, policy)
        validate_border_ledger_caps(result, policy)
    except ValueError as exc:
        _LOG.error("borders_capacity_reached family=ledger")
        raise ValueError("borders_capacity_reached") from exc
    _LOG.debug(
        "borders_update tick=%s domains=%s agreements=%s disputes=%s notices=%s",
        tick,
        len(result.domains),
        len(result.agreements),
        len(result.disputes),
        len(result.notices),
    )
    return result


def _has_border_relations(
    observation: object, inbox: Sequence[object] | None
) -> bool:
    communications = getattr(observation, "communications", ()) or ()
    for communication in communications:
        content = getattr(getattr(communication, "utterance", None), "content", None)
        for relation in getattr(content, "relations", ()) or ():
            if getattr(relation, "subject", None) == "bdr_v1":
                return True
    for entry in inbox or ():
        content = getattr(getattr(entry, "utterance", None), "content", None)
        for relation in getattr(content, "relations", ()) or ():
            if getattr(relation, "subject", None) == "bdr_v1":
                return True
    return False


def _merge_by_id[RowT](
    rows: Sequence[RowT], updates: Sequence[RowT]
) -> list[RowT]:
    by_id: dict[str, RowT] = {}
    for row in rows:
        key = (
            getattr(row, "domain_id", None),
            getattr(row, "agreement_id", None)
            or getattr(row, "expectation_id", None)
            or getattr(row, "dispute_id", None)
            or getattr(row, "basis", None),
        )
        by_id[repr(key)] = row
    for row in updates:
        key = (
            getattr(row, "domain_id", None),
            getattr(row, "agreement_id", None)
            or getattr(row, "expectation_id", None)
            or getattr(row, "dispute_id", None)
            or getattr(row, "basis", None),
        )
        by_id[repr(key)] = row
    return list(by_id.values())


def _proposed_by(agreement: BorderAgreement, speaker: str) -> bool:
    """Return whether the delivered speaker authored this proposal."""
    return any(
        evidence.source_owner_id is not None
        and evidence.source_owner_id.value == speaker
        for evidence in agreement.evidence
    )


def _agreement_for_speaker(
    *,
    agreements: Sequence[BorderAgreement],
    base: BorderLedger,
    domain_id: str,
    speaker: str,
) -> BorderAgreement | None:
    by_id = {
        agreement.agreement_id: agreement
        for agreement in (*agreements, *base.agreements)
        if agreement.domain_id == domain_id
        and agreement.counterparty_ref == speaker
    }
    return next(iter(by_id.values())) if len(by_id) == 1 else None


def _acceptance_target(
    *,
    agreements: Sequence[BorderAgreement],
    base: BorderLedger,
    domain_id: str,
    speaker: str,
) -> BorderAgreement | None:
    """Find one proposal the speaker may accept without self-acceptance."""
    by_id = {
        agreement.agreement_id: agreement
        for agreement in (*agreements, *base.agreements)
        if agreement.domain_id == domain_id
        and agreement.status is AgreementStatus.PROPOSED
        and not _proposed_by(agreement, speaker)
    }
    return next(iter(by_id.values())) if len(by_id) == 1 else None


def _covered_by_agreement(
    domain_id: str, speaker: str, agreements: Sequence[BorderAgreement]
) -> bool:
    for agreement in agreements:
        if agreement.domain_id != domain_id:
            continue
        if agreement.counterparty_ref != speaker:
            continue
        if agreement.status in {
            AgreementStatus.APPARENT_ACCEPTANCE,
            AgreementStatus.RECOGNIZED,
        } and AgreementProvision.TERRITORIAL_ACKNOWLEDGEMENT in agreement.provisions:
            return True
    return False


__all__ = [
    "BORDERS_LEDGER_VERSION",
    "BORDERS_POLICY_VERSION",
    "MAX_ANCHOR_REF_CHARS",
    "MAX_BOUNDARY_EDGES_PER_DOMAIN",
    "MAX_CONTESTED_LOCATIONS",
    "MAX_COUNTERPARTY_REF_CHARS",
    "MAX_LOCATIONS_PER_DOMAIN",
    "MAX_PROVISIONS",
    "AccessExpectation",
    "AccessExpectationMode",
    "AccessExpectationStatus",
    "AccessSubjectKind",
    "AgreementAct",
    "AgreementProvision",
    "AgreementStatus",
    "BorderAgreement",
    "BorderDispute",
    "BorderDisputeStatus",
    "BorderEvidence",
    "BorderExportRow",
    "BorderLedger",
    "BorderNoticeCode",
    "BordersPolicy",
    "BoundaryBasis",
    "BoundaryRecognition",
    "BoundaryStatus",
    "BoundarySummary",
    "CounterpartyKind",
    "DomainClaimStatus",
    "TerritorialDomainClaim",
    "access_expectation_id",
    "apply_borders_update",
    "border_agreement_id",
    "border_anchor_token",
    "border_dispute_id",
    "border_export_digest",
    "border_ledger_digest",
    "border_ledger_is_canonical",
    "border_location_token",
    "border_notice",
    "border_owner_token",
    "borders_notice_counts",
    "boundary_edge",
    "boundary_edges_for_domain",
    "boundary_recognition_id",
    "boundary_summary",
    "default_borders_policy",
    "domain_claim_id",
    "domain_claim_token_id",
    "domain_edge_tokens",
    "domain_location_tokens",
    "empty_border_ledger",
    "enforce_borders_limits",
    "export_border_rows",
    "observe_local_edges",
    "require_boundary_edges",
    "require_location_set",
    "require_owner_borders",
    "unobserved_domain_locations",
    "validate_border_ledger_caps",
]
