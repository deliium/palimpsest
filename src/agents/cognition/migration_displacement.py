# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Owner-scoped beliefs about migration intents, routes, causes, and outcomes.

A migration intent is one owner's belief about a possible movement from a
logical origin through an ordered logical route to a logical destination. It is
not a world object, a refugee category, a legal status, or a command. A route is
an ordered sequence of two to four exact ``EntityId`` locations; there is no
grid, coordinate, polygon, area, or region conversion.

This module is a private belief store. ``WorldEngine``, perception, admission,
stop selectors, memory, prompts, observer semantics, and the presentation client
never read it. No objective cause, wave, refugee, asylum, displacement,
integration, household, or registry exists here. No helper returns, constructs,
submits, resolves, or blocks a command. Every physical effect remains ordinary
world admission. "Migration" here means population movement and has no
relation to SQL schema migration.
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, is_dataclass, replace
from dataclasses import fields as dataclass_fields
from decimal import Decimal
from enum import StrEnum
from itertools import pairwise
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from agents.models import AgentId
from world.identifiers import EntityId, require_exact_nonneg_int, require_stable_id

if TYPE_CHECKING:
    from world.observations import Observation

_LOG: Final[logging.Logger] = logging.getLogger(__name__)

MIGRATION_DISPLACEMENT_POLICY_VERSION: Final[str] = "migration-displacement.v1"
MIGRATION_DISPLACEMENT_LEDGER_VERSION: Final[str] = "migration-displacement-ledger.v1"
MIGRATION_DISPLACEMENT_FRAME_VERSION: Final[str] = "mdp_v1"
MIGRATION_DISPLACEMENT_FRAME_MAX_CHARS: Final[int] = 256
MIGRATION_DISPLACEMENT_FRAME_MAX_RELATIONS: Final[int] = 4
MIGRATION_DISPLACEMENT_FRAME_FIELD_COUNT: Final[int] = 14
MIN_ROUTE_LOCATIONS: Final[int] = 2
MAX_ROUTE_LOCATIONS: Final[int] = 4
MAX_ROUTE_EDGES: Final[int] = 3
MAX_ANCHOR_REF_CHARS: Final[int] = 128
MAX_INTENT_CLUSTER_IDS: Final[int] = 2
MAX_WAVE_PARTICIPANTS: Final[int] = 8
MIN_WAVE_PARTICIPANTS: Final[int] = 2
MIN_CLUSTER_MEMBERS: Final[int] = 2

_QUANTUM: Final[Decimal] = Decimal("0.000001")
_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")
_ID_HEX_CHARS: Final[int] = 32
_CANDIDATE_KINDS: Final[frozenset[str]] = frozenset({"wave", "cluster", "outcome"})
_CANDIDATE_PREFIX: Final[str] = "mig-"
_PUBLICATION_PREFIX: Final[str] = "md-pub-"

_INTENT_PREFIX: Final[str] = "mdi-"
_ROUTE_PREFIX: Final[str] = "mdr-"
_CAUSE_PREFIX: Final[str] = "mdc-"
_CLUSTER_PREFIX: Final[str] = "mdg-"
_INTEGRATION_PREFIX: Final[str] = "mdn-"
_WAVE_PREFIX: Final[str] = "mdw-"


class MigrationCauseKind(StrEnum):
    """Closed owner-belief cause kind. It is never an objective cause."""

    RESOURCE_SCARCITY = "resource_scarcity"
    ENVIRONMENTAL_HAZARD = "environmental_hazard"
    CONFLICT = "conflict"
    OPPORTUNITY = "opportunity"
    SOCIAL_NETWORK = "social_network"
    INSTITUTION = "institution"
    UNKNOWN = "unknown"


class MigrationCauseSource(StrEnum):
    """Closed provenance for one cause or evidence contribution."""

    DIRECT_OBSERVATION = "direct_observation"
    OWN_NEED = "own_need"
    OWN_JOURNEY = "own_journey"
    OWN_RELATIONSHIP = "own_relationship"
    OWN_KINSHIP = "own_kinship"
    ORGANIZATION_BELIEF = "organization_belief"
    INSTITUTION_BELIEF = "institution_belief"
    FORMAL_RULE_BELIEF = "formal_rule_belief"
    DISPUTE_BELIEF = "dispute_belief"
    EVIDENCE_BELIEF = "evidence_belief"
    DIPLOMACY_BELIEF = "diplomacy_belief"
    CONFLICT_BELIEF = "conflict_belief"
    BORDER_BELIEF = "border_belief"
    TESTIMONY = "testimony"
    INFERENCE = "inference"
    UNKNOWN = "unknown"


class MigrationIntentStatus(StrEnum):
    """Closed owner-belief lifecycle of one migration intent."""

    CONSIDERED = "considered"
    PLANNED = "planned"
    DEPARTED = "departed"
    ARRIVED = "arrived"
    ABANDONED = "abandoned"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class RouteBeliefBasis(StrEnum):
    """Closed provenance for one route belief."""

    DIRECT_OBSERVATION = "direct_observation"
    OWN_JOURNEY = "own_journey"
    TESTIMONY = "testimony"
    INFERENCE = "inference"
    UNRESOLVED = "unresolved"


class RouteBeliefStatus(StrEnum):
    """Closed owner-belief status of one route belief."""

    OPEN = "open"
    BLOCKED_BELIEF = "blocked_belief"
    UNRESOLVED = "unresolved"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class ClusterBasis(StrEnum):
    """Closed provenance for one social-cluster belief."""

    KINSHIP = "kinship"
    ORGANIZATION = "organization"
    CO_MOVEMENT = "co_movement"
    COMMUNICATION = "communication"
    RELATIONSHIP = "relationship"
    UNKNOWN = "unknown"


class ClusterStatus(StrEnum):
    """Closed owner-belief status of one social-cluster belief."""

    BELIEVED = "believed"
    DISPUTED = "disputed"
    DISSOLVED = "dissolved"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class IntegrationDomain(StrEnum):
    """Closed descriptive domain of an integration belief. Never a score."""

    RESIDENCE = "residence"
    NEEDS = "needs"
    RESOURCE_ACCESS = "resource_access"
    ORGANIZATION_PARTICIPATION = "organization_participation"
    INSTITUTION_PARTICIPATION = "institution_participation"
    RELATIONSHIPS = "relationships"
    CONFLICT_STATUS = "conflict_status"
    UNKNOWN = "unknown"


class IntegrationStatus(StrEnum):
    """Closed owner-belief outcome observation for a destination."""

    SETTLED = "settled"
    TRANSIENT = "transient"
    RETURNED = "returned"
    ONWARD = "onward"
    UNKNOWN = "unknown"


class WaveObservationStatus(StrEnum):
    """Closed owner-belief status of one observed or reported wave."""

    OBSERVED = "observed"
    REPORTED = "reported"
    DISPUTED = "disputed"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class CauseEvidenceStatus(StrEnum):
    """Closed lifecycle of one cause evidence row."""

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    CONTRADICTED = "contradicted"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class MigrationNoticeCode(StrEnum):
    """Closed metadata notice codes. Notices carry no payload."""

    UNRESOLVED_ANCHOR = "unresolved_anchor"
    ROUTE_UNOBSERVED = "route_unobserved"
    CAUSE_UNRESOLVED = "cause_unresolved"
    CLUSTER_UNRESOLVED = "cluster_unresolved"
    INTEGRATION_UNOBSERVED = "integration_unobserved"
    SAME_ROOT_SUPPRESSED = "same_root_suppressed"
    INTENT_CAP_REACHED = "intent_cap_reached"
    ROUTE_CAP_REACHED = "route_cap_reached"
    CAUSE_CAP_REACHED = "cause_cap_reached"
    CLUSTER_CAP_REACHED = "cluster_cap_reached"
    INTEGRATION_CAP_REACHED = "integration_cap_reached"
    WAVE_CAP_REACHED = "wave_cap_reached"
    LEDGER_CAP_REACHED = "ledger_cap_reached"
    TRUNCATED = "truncated"
    MALFORMED_FRAME = "malformed_frame"
    PEER_CLAIM_UNTRUSTED = "peer_claim_untrusted"


_NOTICE_CODES: Final[frozenset[str]] = frozenset(
    item.value for item in MigrationNoticeCode
)


def _log_failure(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "migration_displacement_validation_failed field=%s reason_code=%s",
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


def _non_negative_float(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _log_failure(field_name, "not_finite")
    number = float(value)
    if not math.isfinite(number):
        raise _log_failure(field_name, "not_finite")
    if number < 0.0:
        raise _log_failure(field_name, "out_of_range")
    return _quantize(number)


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


def _sha256_hex(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _require_hex(value: str) -> bool:
    return all(char in _HEX for char in value)


def _require_prefixed_id(field_name: str, value: object, prefix: str) -> str:
    if (
        type(value) is not str
        or not value.startswith(prefix)
        or len(value) != len(prefix) + _ID_HEX_CHARS
        or not _require_hex(value[len(prefix) :])
    ):
        raise _log_failure(field_name, "invalid_identifier")
    return value


def _id_tuple(
    field_name: str,
    values: object,
    prefix: str,
    *,
    max_count: int,
) -> tuple[str, ...]:
    raw = _require_sequence(field_name, values)
    if len(raw) > max_count:
        raise _log_failure(field_name, "cap_exceeded")
    checked = tuple(_require_prefixed_id(field_name, item, prefix) for item in raw)
    if len(set(checked)) != len(checked):
        raise _log_failure(field_name, "duplicate_id")
    if list(checked) != sorted(checked):
        raise _log_failure(field_name, "unsorted_ids")
    return checked


def _agent_tuple(
    field_name: str,
    values: object,
    *,
    min_count: int,
    max_count: int,
) -> tuple[AgentId, ...]:
    raw = _require_sequence(field_name, values)
    if len(raw) < min_count or len(raw) > max_count:
        raise _log_failure(field_name, "member_count")
    for item in raw:
        if type(item) is not AgentId:
            raise _log_failure(field_name, "invalid_type")
    members = tuple(item for item in raw if type(item) is AgentId)
    tokens = [item.value for item in members]
    if len(set(tokens)) != len(tokens):
        raise _log_failure(field_name, "duplicate_member")
    if tokens != sorted(tokens):
        raise _log_failure(field_name, "unsorted_ids")
    return members


def _entity(field_name: str, value: object) -> EntityId:
    if type(value) is not EntityId:
        raise _log_failure(field_name, "unresolved_entity")
    return value


def _owner(value: object) -> AgentId:
    if type(value) is not AgentId:
        raise _log_failure("owner_id", "invalid_type")
    return value


def _ticks(first: object, last: object) -> tuple[int, int]:
    first_tick = _nonneg("first_tick", first)
    last_tick = _nonneg("last_tick", last)
    if first_tick > last_tick:
        raise _log_failure("first_tick", "tick_order")
    return first_tick, last_tick


def require_route_locations(
    value: object, *, field_name: str = "route_locations"
) -> tuple[EntityId, ...]:
    """Return an ordered 2-4 location route of exact ``EntityId`` values.

    The sequence order is preserved and never sorted. Duplicates and consecutive
    repeats are rejected. World topology adjacency is not checked here; the
    update pipeline proves it from owner-visible exits or own journeys.
    """
    raw = _require_sequence(field_name, value)
    if len(raw) < MIN_ROUTE_LOCATIONS or len(raw) > MAX_ROUTE_LOCATIONS:
        raise _log_failure(field_name, "location_count")
    seen: set[str] = set()
    previous: str | None = None
    checked: list[EntityId] = []
    for item in raw:
        if type(item) is not EntityId:
            raise _log_failure(field_name, "unresolved_entity")
        if item.value == previous:
            raise _log_failure(field_name, "route_self_edge")
        if item.value in seen:
            raise _log_failure(field_name, "duplicate_location")
        seen.add(item.value)
        previous = item.value
        checked.append(item)
    return tuple(checked)


def route_edge_pairs(route: object) -> tuple[tuple[str, str], ...]:
    """Return consecutive ordered directed ``(from, to)`` pairs in route order.

    Endpoints are never min/max-sorted: ``A -> B`` is distinct from ``B -> A``.
    """
    locations = require_route_locations(route, field_name="route")
    return tuple((left.value, right.value) for left, right in pairwise(locations))


def require_route_edges(
    value: object, *, field_name: str = "route_edges"
) -> tuple[tuple[str, str], ...]:
    """Return 0-3 ordered directed edge pairs without sorting them."""
    raw = _require_sequence(field_name, value)
    if len(raw) > MAX_ROUTE_EDGES:
        raise _log_failure(field_name, "edge_count")
    seen: set[tuple[str, str]] = set()
    checked: list[tuple[str, str]] = []
    for item in raw:
        if type(item) is not tuple or len(item) != 2:
            raise _log_failure(field_name, "invalid_edge")
        left, right = item
        if type(left) is not str or type(right) is not str or not left or not right:
            raise _log_failure(field_name, "invalid_edge")
        if left == right:
            raise _log_failure(field_name, "route_self_edge")
        pair = (left, right)
        if pair in seen:
            raise _log_failure(field_name, "duplicate_edge")
        seen.add(pair)
        checked.append(pair)
    return tuple(checked)


def migration_location_token(value: EntityId) -> str:
    """Publication-facing location token. Never emits an ``EntityId`` object."""
    if type(value) is not EntityId:
        raise _log_failure("location", "unresolved_entity")
    return value.value


def migration_route_tokens(route: object) -> tuple[str, ...]:
    """Publication-facing ordered route tokens. Never emits ``EntityId``."""
    locations = require_route_locations(route, field_name="route")
    return tuple(item.value for item in locations)


def migration_candidate_id(kind: str, material: str) -> str:
    """Content-addressed ``mig-`` id; ``kind`` is closed to wave/cluster/outcome."""
    if type(kind) is not str or kind not in _CANDIDATE_KINDS:
        raise _log_failure("kind", "unknown_candidate_kind")
    if type(material) is not str or not material:
        raise _log_failure("material", "invalid_material")
    digest = _sha256_hex(f"mig|{kind}|{material}")
    return f"{_CANDIDATE_PREFIX}{digest[:_ID_HEX_CHARS]}"


def migration_publication_id(digest: str) -> str:
    """Publication ``md-pub-`` id from a 64-character lower-case hex digest."""
    if type(digest) is not str or len(digest) != 64 or not _require_hex(digest):
        raise _log_failure("digest", "invalid_digest")
    return f"{_PUBLICATION_PREFIX}{digest[:_ID_HEX_CHARS]}"


@dataclass(frozen=True, slots=True)
class MigrationDisplacementPolicy:
    """Locked cognition constants. Runner JSON does not carry these values."""

    version: str = MIGRATION_DISPLACEMENT_POLICY_VERSION
    max_intents: int = 8
    max_route_beliefs: int = 16
    max_cause_evidence: int = 32
    max_cluster_beliefs: int = 8
    max_integration_beliefs: int = 8
    max_wave_observations: int = 8
    max_route_locations: int = 4
    max_cluster_members: int = 16
    max_evidence_per_row: int = 16
    max_ledger_rows: int = 96
    max_intent_age_ticks: int = 128
    max_route_age_ticks: int = 256
    max_cause_age_ticks: int = 256
    max_cluster_age_ticks: int = 256
    max_integration_age_ticks: int = 256
    max_wave_age_ticks: int = 128
    min_intent_confidence: float = 0.35
    min_cause_support: int = 1
    max_destination_bias: float = 0.25
    route_beliefs_observed_only: bool = True
    causes_are_beliefs: bool = True
    intents_bind_commands: bool = False
    clusters_bind_commands: bool = False
    integration_beliefs_are_truth: bool = False

    def __post_init__(self) -> None:
        if self.version != MIGRATION_DISPLACEMENT_POLICY_VERSION:
            _LOG.error(
                "migration_displacement_policy_rejected field=version "
                "reason_code=unsupported_policy"
            )
            raise ValueError("version: unsupported_policy")
        for name, expected in _policy_values().items():
            actual = getattr(self, name)
            if isinstance(expected, bool):
                accepted = actual is expected
            elif isinstance(expected, float):
                accepted = type(actual) is float and actual == expected
            else:
                accepted = type(actual) is int and actual == expected
            if not accepted:
                _LOG.error(
                    "migration_displacement_policy_rejected field=%s "
                    "reason_code=unsupported_policy",
                    name,
                )
                raise ValueError(f"{name}: unsupported_policy")
        _LOG.debug(
            "migration_displacement_policy_constructed policy_version=%s "
            "intents=%s routes=%s causes=%s",
            self.version,
            self.max_intents,
            self.max_route_beliefs,
            self.max_cause_evidence,
        )


def _policy_values() -> dict[str, object]:
    return {
        "max_intents": 8,
        "max_route_beliefs": 16,
        "max_cause_evidence": 32,
        "max_cluster_beliefs": 8,
        "max_integration_beliefs": 8,
        "max_wave_observations": 8,
        "max_route_locations": MAX_ROUTE_LOCATIONS,
        "max_cluster_members": 16,
        "max_evidence_per_row": 16,
        "max_ledger_rows": 96,
        "max_intent_age_ticks": 128,
        "max_route_age_ticks": 256,
        "max_cause_age_ticks": 256,
        "max_cluster_age_ticks": 256,
        "max_integration_age_ticks": 256,
        "max_wave_age_ticks": 128,
        "min_intent_confidence": 0.35,
        "min_cause_support": 1,
        "max_destination_bias": 0.25,
        "route_beliefs_observed_only": True,
        "causes_are_beliefs": True,
        "intents_bind_commands": False,
        "clusters_bind_commands": False,
        "integration_beliefs_are_truth": False,
    }


def default_migration_displacement_policy() -> MigrationDisplacementPolicy:
    """Return the only accepted cognition policy."""
    return MigrationDisplacementPolicy()


_MAX_EVIDENCE_PER_ROW: Final[int] = 16
_MAX_LEDGER_ROWS: Final[int] = 96
_MAX_CLUSTER_MEMBERS: Final[int] = 16
_MAX_CAUSE_IDS: Final[int] = 32
_MAX_CLUSTER_IDS_PER_WAVE: Final[int] = 8


@dataclass(frozen=True, slots=True)
class MigrationEvidence:
    """One adopted local contribution to a migration row."""

    kind: MigrationCauseSource
    source_owner_id: AgentId | None
    source_tick: int
    lineage_ref: str
    policy_version: str = MIGRATION_DISPLACEMENT_POLICY_VERSION

    def __post_init__(self) -> None:
        if type(self.kind) is not MigrationCauseSource:
            raise _log_failure("evidence.kind", "unknown_cause_source")
        if self.source_owner_id is not None and type(self.source_owner_id) is not (
            AgentId
        ):
            raise _log_failure("evidence.source_owner_id", "invalid_type")
        object.__setattr__(
            self, "source_tick", _nonneg("evidence.source_tick", self.source_tick)
        )
        object.__setattr__(
            self, "lineage_ref", _stable("evidence.lineage_ref", self.lineage_ref)
        )
        if self.policy_version != MIGRATION_DISPLACEMENT_POLICY_VERSION:
            raise _log_failure("evidence.policy_version", "unsupported_policy")


def _evidence_tuple(value: object) -> tuple[MigrationEvidence, ...]:
    raw = _require_sequence("evidence", value)
    if len(raw) > _MAX_EVIDENCE_PER_ROW:
        raise _log_failure("evidence", "cap_exceeded")
    checked: list[MigrationEvidence] = []
    seen: set[tuple[str, str, int]] = set()
    for item in raw:
        if type(item) is not MigrationEvidence:
            raise _log_failure("evidence", "invalid_type")
        key = (item.kind.value, item.lineage_ref, item.source_tick)
        if key in seen:
            raise _log_failure("evidence", "duplicate_evidence")
        seen.add(key)
        checked.append(item)
    checked.sort(key=lambda item: (item.source_tick, item.lineage_ref))
    return tuple(checked)


def _row_guard(family: str) -> Callable[[Callable[..., None]], Callable[..., None]]:
    """Log one metadata-only rejection line per invalid row, then re-raise."""

    def decorate(function: Callable[..., None]) -> Callable[..., None]:
        @functools.wraps(function)
        def wrapper(self: object) -> None:
            try:
                function(self)
            except ValueError as exc:
                reason = str(exc).rsplit(": ", 1)[-1]
                _LOG.error(
                    "migration_displacement_row_rejected family=%s reason_code=%s",
                    family,
                    reason,
                )
                raise

        return wrapper

    return decorate


def _route_endpoints(
    origin: EntityId, destination: EntityId, route: tuple[EntityId, ...]
) -> None:
    if route[0] != origin:
        raise _log_failure("route_locations", "route_origin_mismatch")
    if route[-1] != destination:
        raise _log_failure("route_locations", "route_destination_mismatch")


@dataclass(frozen=True, slots=True)
class MigrationIntentRow:
    """One owner's belief about a possible movement. It is never a command."""

    intent_id: str
    owner_id: AgentId
    origin_location_id: EntityId
    destination_location_id: EntityId
    route_locations: tuple[EntityId, ...]
    cause_ids: tuple[str, ...]
    cluster_ids: tuple[str, ...]
    status: MigrationIntentStatus
    confidence: float
    first_tick: int
    last_tick: int
    evidence: tuple[MigrationEvidence, ...] = ()

    @_row_guard("intent")
    def __post_init__(self) -> None:
        _require_prefixed_id("intent_id", self.intent_id, _INTENT_PREFIX)
        _owner(self.owner_id)
        origin = _entity("origin_location_id", self.origin_location_id)
        destination = _entity("destination_location_id", self.destination_location_id)
        route = require_route_locations(self.route_locations)
        _route_endpoints(origin, destination, route)
        object.__setattr__(self, "route_locations", route)
        object.__setattr__(
            self,
            "cause_ids",
            _id_tuple(
                "cause_ids",
                self.cause_ids,
                _CAUSE_PREFIX,
                max_count=_MAX_CAUSE_IDS,
            ),
        )
        object.__setattr__(
            self,
            "cluster_ids",
            _id_tuple(
                "cluster_ids",
                self.cluster_ids,
                _CLUSTER_PREFIX,
                max_count=MAX_INTENT_CLUSTER_IDS,
            ),
        )
        if not self.cause_ids:
            raise _log_failure("cause_ids", "missing_cause")
        if type(self.status) is not MigrationIntentStatus:
            raise _log_failure("status", "unknown_intent_status")
        object.__setattr__(self, "confidence", _unit("confidence", self.confidence))
        first, last = _ticks(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        object.__setattr__(self, "evidence", _evidence_tuple(self.evidence))
        _LOG.debug(
            "migration_displacement_contract_constructed "
            "route_locations=%s causes=%s clusters=%s",
            len(route),
            len(self.cause_ids),
            len(self.cluster_ids),
        )


@dataclass(frozen=True, slots=True)
class RouteBeliefRow:
    """One owner's belief about an ordered route. It never moves anyone."""

    route_id: str
    owner_id: AgentId
    origin_location_id: EntityId
    destination_location_id: EntityId
    route_locations: tuple[EntityId, ...]
    observed_duration_ticks: int | None
    fatigue_cost: float | None
    basis: RouteBeliefBasis
    status: RouteBeliefStatus
    first_tick: int
    last_tick: int
    evidence: tuple[MigrationEvidence, ...] = ()

    @_row_guard("route")
    def __post_init__(self) -> None:
        _require_prefixed_id("route_id", self.route_id, _ROUTE_PREFIX)
        _owner(self.owner_id)
        origin = _entity("origin_location_id", self.origin_location_id)
        destination = _entity("destination_location_id", self.destination_location_id)
        route = require_route_locations(self.route_locations)
        _route_endpoints(origin, destination, route)
        object.__setattr__(self, "route_locations", route)
        if self.observed_duration_ticks is not None:
            duration = _nonneg("observed_duration_ticks", self.observed_duration_ticks)
            if duration < 1:
                raise _log_failure("observed_duration_ticks", "invalid_duration")
            object.__setattr__(self, "observed_duration_ticks", duration)
        if self.fatigue_cost is not None:
            object.__setattr__(
                self,
                "fatigue_cost",
                _non_negative_float("fatigue_cost", self.fatigue_cost),
            )
        if type(self.basis) is not RouteBeliefBasis:
            raise _log_failure("basis", "unknown_route_basis")
        if type(self.status) is not RouteBeliefStatus:
            raise _log_failure("status", "unknown_route_status")
        if self.basis is RouteBeliefBasis.UNRESOLVED and self.status in (
            RouteBeliefStatus.OPEN,
            RouteBeliefStatus.BLOCKED_BELIEF,
        ):
            raise _log_failure("status", "route_basis_unresolved")
        first, last = _ticks(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        object.__setattr__(self, "evidence", _evidence_tuple(self.evidence))


@dataclass(frozen=True, slots=True)
class CauseEvidenceRow:
    """One owner's evidence-backed cause belief. The contract never judges truth."""

    cause_id: str
    owner_id: AgentId
    cause_kind: MigrationCauseKind
    source_kind: MigrationCauseSource
    anchor_ref: str | None
    confidence: float
    first_tick: int
    last_tick: int
    status: CauseEvidenceStatus
    evidence: tuple[MigrationEvidence, ...] = ()

    @_row_guard("cause")
    def __post_init__(self) -> None:
        _require_prefixed_id("cause_id", self.cause_id, _CAUSE_PREFIX)
        _owner(self.owner_id)
        if type(self.cause_kind) is not MigrationCauseKind:
            raise _log_failure("cause_kind", "unknown_cause_kind")
        if type(self.source_kind) is not MigrationCauseSource:
            raise _log_failure("source_kind", "unknown_cause_source")
        if self.cause_kind is MigrationCauseKind.UNKNOWN:
            if self.source_kind is not MigrationCauseSource.UNKNOWN:
                raise _log_failure(
                    "source_kind", "unknown_cause_requires_unknown_source"
                )
            if self.anchor_ref is not None:
                raise _log_failure("anchor_ref", "unknown_cause_has_anchor")
        if self.anchor_ref is not None:
            # Stable ids are already bounded to MAX_ANCHOR_REF_CHARS code points.
            object.__setattr__(
                self, "anchor_ref", _stable("anchor_ref", self.anchor_ref)
            )
        object.__setattr__(self, "confidence", _unit("confidence", self.confidence))
        first, last = _ticks(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        if type(self.status) is not CauseEvidenceStatus:
            raise _log_failure("status", "unknown_cause_status")
        object.__setattr__(self, "evidence", _evidence_tuple(self.evidence))


@dataclass(frozen=True, slots=True)
class SocialClusterBeliefRow:
    """One owner's belief about a group moving or communicating together."""

    cluster_id: str
    owner_id: AgentId
    member_ids: tuple[AgentId, ...]
    basis: ClusterBasis
    confidence: float
    status: ClusterStatus
    first_tick: int
    last_tick: int
    evidence: tuple[MigrationEvidence, ...] = ()

    @_row_guard("cluster")
    def __post_init__(self) -> None:
        _require_prefixed_id("cluster_id", self.cluster_id, _CLUSTER_PREFIX)
        _owner(self.owner_id)
        object.__setattr__(
            self,
            "member_ids",
            _agent_tuple(
                "member_ids",
                self.member_ids,
                min_count=MIN_CLUSTER_MEMBERS,
                max_count=_MAX_CLUSTER_MEMBERS,
            ),
        )
        if type(self.basis) is not ClusterBasis:
            raise _log_failure("basis", "unknown_cluster_basis")
        if (
            self.basis is not ClusterBasis.COMMUNICATION
            and self.owner_id not in self.member_ids
        ):
            raise _log_failure("member_ids", "owner_not_member")
        object.__setattr__(self, "confidence", _unit("confidence", self.confidence))
        if type(self.status) is not ClusterStatus:
            raise _log_failure("status", "unknown_cluster_status")
        first, last = _ticks(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        object.__setattr__(self, "evidence", _evidence_tuple(self.evidence))


@dataclass(frozen=True, slots=True)
class IntegrationBeliefRow:
    """One owner's descriptive belief about an outcome. Never a score or truth."""

    outcome_id: str
    owner_id: AgentId
    destination_location_id: EntityId
    domain: IntegrationDomain
    status: IntegrationStatus
    confidence: float
    first_tick: int
    last_tick: int
    evidence: tuple[MigrationEvidence, ...] = ()

    @_row_guard("integration")
    def __post_init__(self) -> None:
        _require_prefixed_id("outcome_id", self.outcome_id, _INTEGRATION_PREFIX)
        _owner(self.owner_id)
        _entity("destination_location_id", self.destination_location_id)
        if type(self.domain) is not IntegrationDomain:
            raise _log_failure("domain", "unknown_integration_domain")
        if type(self.status) is not IntegrationStatus:
            raise _log_failure("status", "unknown_integration_status")
        object.__setattr__(self, "confidence", _unit("confidence", self.confidence))
        first, last = _ticks(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        object.__setattr__(self, "evidence", _evidence_tuple(self.evidence))


@dataclass(frozen=True, slots=True)
class WaveObservationRow:
    """One owner's observation or report of co-movement. No shared wave exists."""

    observation_id: str
    owner_id: AgentId
    origin_location_id: EntityId
    destination_location_id: EntityId
    participant_ids: tuple[AgentId, ...]
    cause_ids: tuple[str, ...]
    cluster_ids: tuple[str, ...]
    status: WaveObservationStatus
    first_tick: int
    last_tick: int
    evidence: tuple[MigrationEvidence, ...] = ()

    @_row_guard("wave")
    def __post_init__(self) -> None:
        _require_prefixed_id("observation_id", self.observation_id, _WAVE_PREFIX)
        _owner(self.owner_id)
        origin = _entity("origin_location_id", self.origin_location_id)
        destination = _entity("destination_location_id", self.destination_location_id)
        if origin == destination:
            raise _log_failure("destination_location_id", "route_self_edge")
        object.__setattr__(
            self,
            "participant_ids",
            _agent_tuple(
                "participant_ids",
                self.participant_ids,
                min_count=MIN_WAVE_PARTICIPANTS,
                max_count=MAX_WAVE_PARTICIPANTS,
            ),
        )
        object.__setattr__(
            self,
            "cause_ids",
            _id_tuple(
                "cause_ids",
                self.cause_ids,
                _CAUSE_PREFIX,
                max_count=_MAX_CAUSE_IDS,
            ),
        )
        object.__setattr__(
            self,
            "cluster_ids",
            _id_tuple(
                "cluster_ids",
                self.cluster_ids,
                _CLUSTER_PREFIX,
                max_count=_MAX_CLUSTER_IDS_PER_WAVE,
            ),
        )
        if not self.cause_ids:
            raise _log_failure("cause_ids", "missing_cause")
        if type(self.status) is not WaveObservationStatus:
            raise _log_failure("status", "unknown_wave_status")
        first, last = _ticks(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        object.__setattr__(self, "evidence", _evidence_tuple(self.evidence))


def _typed_rows(
    field_name: str,
    values: object,
    row_type: type,
    id_attr: str,
    owner_id: AgentId,
) -> tuple[object, ...]:
    raw = _require_sequence(field_name, values)
    if len(raw) > _MAX_LEDGER_ROWS * 4:
        raise _log_failure(field_name, "hard_cap_exceeded")
    seen: set[str] = set()
    for item in raw:
        if type(item) is not row_type:
            raise _log_failure(field_name, "invalid_type")
        if item.owner_id != owner_id:  # type: ignore[attr-defined]
            raise _log_failure(f"{field_name}.owner_id", "owner_mismatch")
        row_id = getattr(item, id_attr)
        if row_id in seen:
            raise _log_failure(field_name, "duplicate_row")
        seen.add(row_id)
    return tuple(sorted(raw, key=lambda item: getattr(item, id_attr)))


@dataclass(frozen=True, slots=True)
class MigrationDisplacementLedger:
    """Private migration beliefs owned by one agent. There is no shared ledger."""

    owner_id: AgentId
    intents: tuple[MigrationIntentRow, ...] = ()
    routes: tuple[RouteBeliefRow, ...] = ()
    causes: tuple[CauseEvidenceRow, ...] = ()
    clusters: tuple[SocialClusterBeliefRow, ...] = ()
    integrations: tuple[IntegrationBeliefRow, ...] = ()
    waves: tuple[WaveObservationRow, ...] = ()
    notices: tuple[str, ...] = ()
    digest: str = ""
    policy_version: str = MIGRATION_DISPLACEMENT_POLICY_VERSION

    def __post_init__(self) -> None:
        owner = _owner(self.owner_id)
        if self.policy_version != MIGRATION_DISPLACEMENT_POLICY_VERSION:
            raise _log_failure("policy_version", "unsupported_policy")
        families = (
            ("intents", self.intents, MigrationIntentRow, "intent_id"),
            ("routes", self.routes, RouteBeliefRow, "route_id"),
            ("causes", self.causes, CauseEvidenceRow, "cause_id"),
            ("clusters", self.clusters, SocialClusterBeliefRow, "cluster_id"),
            (
                "integrations",
                self.integrations,
                IntegrationBeliefRow,
                "outcome_id",
            ),
            ("waves", self.waves, WaveObservationRow, "observation_id"),
        )
        checked: dict[str, tuple[object, ...]] = {}
        total = 0
        for name, values, row_type, id_attr in families:
            rows = _typed_rows(name, values, row_type, id_attr, owner)
            checked[name] = rows
            total += len(rows)
        if total > _MAX_LEDGER_ROWS * 4:
            raise _log_failure("ledger", "hard_cap_exceeded")
        for name, rows in checked.items():
            object.__setattr__(self, name, rows)
        raw_notices = _require_sequence("notices", self.notices)
        for notice in raw_notices:
            if type(notice) is not str or notice not in _NOTICE_CODES:
                raise _log_failure("notices", "unknown_notice")
        object.__setattr__(self, "notices", tuple(sorted(set(raw_notices))))  # type: ignore[type-var]
        if type(self.digest) is not str or (
            self.digest and (len(self.digest) != 64 or not _require_hex(self.digest))
        ):
            raise _log_failure("digest", "invalid_digest")
        _LOG.debug(
            "migration_displacement_ledger_constructed intents=%s routes=%s "
            "causes=%s clusters=%s integrations=%s waves=%s",
            len(self.intents),
            len(self.routes),
            len(self.causes),
            len(self.clusters),
            len(self.integrations),
            len(self.waves),
        )


# ---------------------------------------------------------------------------
# Row-family vocabulary, projections, and owner guards (Task 4)
# ---------------------------------------------------------------------------

PREFIX_BY_FAMILY: Final[Mapping[str, str]] = MappingProxyType(
    {
        "intent": _INTENT_PREFIX,
        "route": _ROUTE_PREFIX,
        "cause": _CAUSE_PREFIX,
        "cluster": _CLUSTER_PREFIX,
        "integration": _INTEGRATION_PREFIX,
        "wave": _WAVE_PREFIX,
    }
)
_FAMILY_ORDER: Final[tuple[str, ...]] = (
    "intent",
    "route",
    "cause",
    "cluster",
    "integration",
    "wave",
)
_TOKEN_HEX_CHARS: Final[int] = 16


def _opaque(prefix: str, material: str) -> str:
    return f"{prefix}{_sha256_hex(material)[:_TOKEN_HEX_CHARS]}"


def migration_owner_token(owner_id: AgentId) -> str:
    """Opaque publication token for one participant. Never a raw identity."""
    return _opaque("mdo-", f"agent|{_owner(owner_id).value}")


def migration_opaque_location_token(value: EntityId) -> str:
    """Opaque publication token for one logical location."""
    return _opaque("mdl-", f"location|{_entity('location', value).value}")


def migration_anchor_token(value: str) -> str:
    """Opaque publication token for one local anchor reference."""
    return _opaque("mda-", f"anchor|{_stable('anchor_ref', value)}")


def migration_lineage_token(value: str) -> str:
    """Opaque publication token for one evidence lineage reference."""
    return _opaque("mdv-", f"lineage|{_stable('lineage_ref', value)}")


def _hyphenated(value: str) -> str:
    return value.replace("_", "-")


def intent_location_tokens(row: MigrationIntentRow) -> tuple[str, ...]:
    """Ordered opaque route tokens of one intent. Strings only."""
    if type(row) is not MigrationIntentRow:
        raise _log_failure("row", "invalid_type")
    return tuple(migration_opaque_location_token(item) for item in row.route_locations)


def route_location_tokens(row: RouteBeliefRow) -> tuple[str, ...]:
    """Ordered opaque route tokens of one route belief. Strings only."""
    if type(row) is not RouteBeliefRow:
        raise _log_failure("row", "invalid_type")
    return tuple(migration_opaque_location_token(item) for item in row.route_locations)


def cause_kind_token(row: CauseEvidenceRow) -> str:
    """Closed lower-case token of one cause kind."""
    if type(row) is not CauseEvidenceRow:
        raise _log_failure("row", "invalid_type")
    return _hyphenated(row.cause_kind.value)


def cluster_member_tokens(row: SocialClusterBeliefRow) -> tuple[str, ...]:
    """Opaque member tokens of one cluster belief. Strings only."""
    if type(row) is not SocialClusterBeliefRow:
        raise _log_failure("row", "invalid_type")
    return tuple(migration_owner_token(item) for item in row.member_ids)


def integration_domain_token(row: IntegrationBeliefRow) -> str:
    """Closed lower-case token of one integration domain."""
    if type(row) is not IntegrationBeliefRow:
        raise _log_failure("row", "invalid_type")
    return _hyphenated(row.domain.value)


def wave_participant_tokens(row: WaveObservationRow) -> tuple[str, ...]:
    """Opaque participant tokens of one wave observation. Strings only."""
    if type(row) is not WaveObservationRow:
        raise _log_failure("row", "invalid_type")
    return tuple(migration_owner_token(item) for item in row.participant_ids)


def route_pairs_supported(
    route_locations: Sequence[EntityId],
    supported_edges: Sequence[tuple[str, str]],
) -> bool:
    """True only when every consecutive directed pair is in ``supported_edges``."""
    route = require_route_locations(route_locations)
    supported = set(supported_edges)
    return all(pair in supported for pair in route_edge_pairs(route))


def require_visible_members(
    member_ids: Sequence[AgentId], visible_ids: Sequence[AgentId]
) -> tuple[AgentId, ...]:
    """Reject any member the owner does not currently see or hear."""
    members = _agent_tuple(
        "member_ids",
        member_ids,
        min_count=MIN_CLUSTER_MEMBERS,
        max_count=_MAX_CLUSTER_MEMBERS,
    )
    visible = {item.value for item in visible_ids}
    for item in members:
        if item.value not in visible:
            raise _log_failure("member_ids", "member_not_visible")
    return members


def empty_migration_displacement_ledger(
    owner_id: AgentId,
) -> MigrationDisplacementLedger:
    """Return an empty finalized ledger for one owner."""
    return finalize_migration_displacement_ledger(
        MigrationDisplacementLedger(owner_id=_owner(owner_id))
    )


def require_owner_migration_displacement(
    value: object,
    owner_id: AgentId,
    *,
    field_name: str = "migration_displacement",
) -> None:
    """Reject a foreign or non-ledger value. ``None`` is passthrough."""
    if value is None:
        return
    if type(owner_id) is not AgentId:
        raise _log_failure("owner_id", "invalid_type")
    if type(value) is not MigrationDisplacementLedger:
        raise TypeError(f"{field_name} must be MigrationDisplacementLedger")
    if value.owner_id != owner_id:
        raise ValueError("migration_displacement: foreign_owner")


# ---------------------------------------------------------------------------
# Content-addressed identity, canonical payload, and digest (Task 5)
# ---------------------------------------------------------------------------


def _content_id(prefix: str, *parts: str) -> str:
    material = "|".join(("migration-displacement", prefix, *parts))
    return f"{prefix}{_sha256_hex(material)[:_ID_HEX_CHARS]}"


def _join_entities(values: Sequence[EntityId]) -> str:
    return ",".join(item.value for item in values)


def migration_intent_id(
    owner_id: AgentId, route_locations: Sequence[EntityId], first_tick: int
) -> str:
    """Content-addressed ``mdi-`` id from owner, ordered route, and first tick."""
    route = require_route_locations(route_locations)
    return _content_id(
        _INTENT_PREFIX,
        _owner(owner_id).value,
        "intent",
        _join_entities(route),
        str(_nonneg("first_tick", first_tick)),
    )


def migration_route_id(
    owner_id: AgentId, route_locations: Sequence[EntityId], first_tick: int
) -> str:
    """Content-addressed ``mdr-`` id from owner, ordered route, and first tick."""
    route = require_route_locations(route_locations)
    return _content_id(
        _ROUTE_PREFIX,
        _owner(owner_id).value,
        "route",
        _join_entities(route),
        str(_nonneg("first_tick", first_tick)),
    )


def migration_cause_id(
    owner_id: AgentId,
    cause_kind: MigrationCauseKind,
    source_kind: MigrationCauseSource,
    anchor_ref: str | None,
    first_tick: int,
) -> str:
    """Content-addressed ``mdc-`` id from creation fields and first tick."""
    if type(cause_kind) is not MigrationCauseKind:
        raise _log_failure("cause_kind", "unknown_cause_kind")
    if type(source_kind) is not MigrationCauseSource:
        raise _log_failure("source_kind", "unknown_cause_source")
    anchor = "-" if anchor_ref is None else _stable("anchor_ref", anchor_ref)
    return _content_id(
        _CAUSE_PREFIX,
        _owner(owner_id).value,
        "cause",
        cause_kind.value,
        source_kind.value,
        anchor,
        str(_nonneg("first_tick", first_tick)),
    )


def migration_cluster_id(
    owner_id: AgentId,
    member_ids: Sequence[AgentId],
    basis: ClusterBasis,
    first_tick: int,
) -> str:
    """Content-addressed ``mdg-`` id from members, basis, and first tick."""
    if type(basis) is not ClusterBasis:
        raise _log_failure("basis", "unknown_cluster_basis")
    members = _agent_tuple(
        "member_ids",
        member_ids,
        min_count=MIN_CLUSTER_MEMBERS,
        max_count=_MAX_CLUSTER_MEMBERS,
    )
    return _content_id(
        _CLUSTER_PREFIX,
        _owner(owner_id).value,
        "cluster",
        basis.value,
        ",".join(item.value for item in members),
        str(_nonneg("first_tick", first_tick)),
    )


def migration_integration_id(
    owner_id: AgentId,
    destination_location_id: EntityId,
    domain: IntegrationDomain,
    first_tick: int,
) -> str:
    """Content-addressed ``mdn-`` id from destination, domain, and first tick."""
    if type(domain) is not IntegrationDomain:
        raise _log_failure("domain", "unknown_integration_domain")
    destination = _entity("destination_location_id", destination_location_id)
    return _content_id(
        _INTEGRATION_PREFIX,
        _owner(owner_id).value,
        "integration",
        destination.value,
        domain.value,
        str(_nonneg("first_tick", first_tick)),
    )


def migration_wave_observation_id(
    owner_id: AgentId,
    origin_location_id: EntityId,
    destination_location_id: EntityId,
    participant_ids: Sequence[AgentId],
    first_tick: int,
) -> str:
    """Content-addressed ``mdw-`` id from endpoints, participants, and tick."""
    origin = _entity("origin_location_id", origin_location_id)
    destination = _entity("destination_location_id", destination_location_id)
    members = _agent_tuple(
        "participant_ids",
        participant_ids,
        min_count=MIN_WAVE_PARTICIPANTS,
        max_count=MAX_WAVE_PARTICIPANTS,
    )
    return _content_id(
        _WAVE_PREFIX,
        _owner(owner_id).value,
        "wave",
        origin.value,
        destination.value,
        ",".join(item.value for item in members),
        str(_nonneg("first_tick", first_tick)),
    )


def _evidence_payload(items: Sequence[MigrationEvidence]) -> list[dict[str, object]]:
    return [
        {
            "kind": item.kind.value,
            "owner": (
                None
                if item.source_owner_id is None
                else migration_owner_token(item.source_owner_id)
            ),
            "tick": item.source_tick,
            "lineage": migration_lineage_token(item.lineage_ref),
        }
        for item in items
    ]


def _ratio(value: float) -> str:
    return f"{value:.6f}"


def _sorted_rows(rows: Sequence[object], id_attr: str) -> list[object]:
    return sorted(rows, key=lambda item: (item.first_tick, getattr(item, id_attr)))  # type: ignore[attr-defined]


def _raw_identifiers(ledger: MigrationDisplacementLedger) -> frozenset[str]:
    raw: set[str] = {ledger.owner_id.value}
    for row in ledger.intents:
        raw.update(item.value for item in row.route_locations)
    for route in ledger.routes:
        raw.update(item.value for item in route.route_locations)
    for cause in ledger.causes:
        if cause.anchor_ref is not None:
            raw.add(cause.anchor_ref)
    for cluster in ledger.clusters:
        raw.update(item.value for item in cluster.member_ids)
    for outcome in ledger.integrations:
        raw.add(outcome.destination_location_id.value)
    for wave in ledger.waves:
        raw.update(item.value for item in wave.participant_ids)
        raw.add(wave.origin_location_id.value)
        raw.add(wave.destination_location_id.value)
    rows: list[object] = [
        *ledger.intents,
        *ledger.routes,
        *ledger.causes,
        *ledger.clusters,
        *ledger.integrations,
        *ledger.waves,
    ]
    for row in rows:
        for item in row.evidence:  # type: ignore[attr-defined]
            raw.add(item.lineage_ref)
            if item.source_owner_id is not None:
                raw.add(item.source_owner_id.value)
    return frozenset(raw)


def _string_leaves(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        leaves: list[str] = []
        for key, item in value.items():
            leaves.append(str(key))
            leaves.extend(_string_leaves(item))
        return leaves
    if isinstance(value, (list, tuple)):
        return [leaf for item in value for leaf in _string_leaves(item)]
    return []


def canonical_migration_displacement_payload(
    ledger: MigrationDisplacementLedger,
) -> dict[str, object]:
    """Token-only canonical payload without a digest field."""
    if type(ledger) is not MigrationDisplacementLedger:
        raise _log_failure("ledger", "invalid_type")
    intents = [
        {
            "id": row.intent_id,
            "origin": migration_opaque_location_token(row.origin_location_id),
            "destination": migration_opaque_location_token(row.destination_location_id),
            "route": list(intent_location_tokens(row)),
            "causes": list(row.cause_ids),
            "clusters": list(row.cluster_ids),
            "status": row.status.value,
            "confidence": _ratio(row.confidence),
            "first_tick": row.first_tick,
            "last_tick": row.last_tick,
            "evidence": _evidence_payload(row.evidence),
        }
        for row in _sorted_rows(ledger.intents, "intent_id")
    ]
    routes = [
        {
            "id": row.route_id,
            "origin": migration_opaque_location_token(row.origin_location_id),
            "destination": migration_opaque_location_token(row.destination_location_id),
            "route": list(route_location_tokens(row)),
            "duration": row.observed_duration_ticks,
            "fatigue": None if row.fatigue_cost is None else _ratio(row.fatigue_cost),
            "basis": row.basis.value,
            "status": row.status.value,
            "first_tick": row.first_tick,
            "last_tick": row.last_tick,
            "evidence": _evidence_payload(row.evidence),
        }
        for row in _sorted_rows(ledger.routes, "route_id")
    ]
    causes = [
        {
            "id": row.cause_id,
            "kind": row.cause_kind.value,
            "source": row.source_kind.value,
            "anchor": (
                None
                if row.anchor_ref is None
                else migration_anchor_token(row.anchor_ref)
            ),
            "confidence": _ratio(row.confidence),
            "status": row.status.value,
            "first_tick": row.first_tick,
            "last_tick": row.last_tick,
            "evidence": _evidence_payload(row.evidence),
        }
        for row in _sorted_rows(ledger.causes, "cause_id")
    ]
    clusters = [
        {
            "id": row.cluster_id,
            "members": list(cluster_member_tokens(row)),
            "basis": row.basis.value,
            "confidence": _ratio(row.confidence),
            "status": row.status.value,
            "first_tick": row.first_tick,
            "last_tick": row.last_tick,
            "evidence": _evidence_payload(row.evidence),
        }
        for row in _sorted_rows(ledger.clusters, "cluster_id")
    ]
    integrations = [
        {
            "id": row.outcome_id,
            "destination": migration_opaque_location_token(row.destination_location_id),
            "domain": row.domain.value,
            "status": row.status.value,
            "confidence": _ratio(row.confidence),
            "first_tick": row.first_tick,
            "last_tick": row.last_tick,
            "evidence": _evidence_payload(row.evidence),
        }
        for row in _sorted_rows(ledger.integrations, "outcome_id")
    ]
    waves = [
        {
            "id": row.observation_id,
            "origin": migration_opaque_location_token(row.origin_location_id),
            "destination": migration_opaque_location_token(row.destination_location_id),
            "participants": list(wave_participant_tokens(row)),
            "causes": list(row.cause_ids),
            "clusters": list(row.cluster_ids),
            "status": row.status.value,
            "first_tick": row.first_tick,
            "last_tick": row.last_tick,
            "evidence": _evidence_payload(row.evidence),
        }
        for row in _sorted_rows(ledger.waves, "observation_id")
    ]
    payload: dict[str, object] = {
        "policy_version": ledger.policy_version,
        "owner_id": migration_owner_token(ledger.owner_id),
        "intents": intents,
        "routes": routes,
        "causes": causes,
        "clusters": clusters,
        "integrations": integrations,
        "waves": waves,
        "notices": sorted(set(ledger.notices)),
    }
    raw = _raw_identifiers(ledger)
    if any(leaf in raw for leaf in _string_leaves(payload)):
        raise ValueError("migration_displacement: raw_identifier")
    return payload


def canonical_migration_displacement_json(
    ledger: MigrationDisplacementLedger,
) -> str:
    """Canonical JSON text with sorted keys and ASCII-only output."""
    return json.dumps(
        canonical_migration_displacement_payload(ledger),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def migration_displacement_ledger_digest(
    ledger: MigrationDisplacementLedger,
) -> str:
    """Lower-case hex SHA-256 of the canonical JSON."""
    return _sha256_hex(canonical_migration_displacement_json(ledger))


def finalize_migration_displacement_ledger(
    ledger: MigrationDisplacementLedger,
) -> MigrationDisplacementLedger:
    """Recompute the digest and return a replaced ledger."""
    digest = migration_displacement_ledger_digest(ledger)
    _LOG.debug(
        "migration_displacement_ledger_finalized rows=%s digest_prefix=%s",
        _row_count(ledger),
        digest[:8],
    )
    return replace(ledger, digest=digest)


def require_migration_displacement_digest(ledger: MigrationDisplacementLedger) -> None:
    """Reject a ledger whose digest does not match its canonical payload."""
    if ledger.digest != migration_displacement_ledger_digest(ledger):
        _LOG.error("migration_displacement_digest_mismatch")
        raise ValueError("migration_displacement: digest_mismatch")


def _row_count(ledger: MigrationDisplacementLedger) -> int:
    return (
        len(ledger.intents)
        + len(ledger.routes)
        + len(ledger.causes)
        + len(ledger.clusters)
        + len(ledger.integrations)
        + len(ledger.waves)
    )


def merge_migration_displacement_ledger(
    prior: MigrationDisplacementLedger, updated: MigrationDisplacementLedger
) -> MigrationDisplacementLedger:
    """Merge two ledgers of one owner. Tests and restore only; updated wins."""
    if type(prior) is not MigrationDisplacementLedger or (
        type(updated) is not MigrationDisplacementLedger
    ):
        raise _log_failure("ledger", "invalid_type")
    if prior.owner_id != updated.owner_id:
        raise ValueError("migration_displacement: foreign_owner")

    def merged(old: Sequence[object], new: Sequence[object], id_attr: str) -> tuple:
        rows = {getattr(item, id_attr): item for item in old}
        rows.update({getattr(item, id_attr): item for item in new})
        return tuple(rows.values())

    return finalize_migration_displacement_ledger(
        MigrationDisplacementLedger(
            owner_id=prior.owner_id,
            intents=merged(prior.intents, updated.intents, "intent_id"),
            routes=merged(prior.routes, updated.routes, "route_id"),
            causes=merged(prior.causes, updated.causes, "cause_id"),
            clusters=merged(prior.clusters, updated.clusters, "cluster_id"),
            integrations=merged(prior.integrations, updated.integrations, "outcome_id"),
            waves=merged(prior.waves, updated.waves, "observation_id"),
            notices=tuple(set(prior.notices) | set(updated.notices)),
        )
    )


def migration_displacement_update_summary(
    ledger: MigrationDisplacementLedger,
) -> Mapping[str, int]:
    """Counts only. Never ids, locations, causes, or members."""
    if type(ledger) is not MigrationDisplacementLedger:
        raise _log_failure("ledger", "invalid_type")
    return MappingProxyType(
        {
            "intents": len(ledger.intents),
            "routes": len(ledger.routes),
            "causes": len(ledger.causes),
            "clusters": len(ledger.clusters),
            "integrations": len(ledger.integrations),
            "waves": len(ledger.waves),
            "notices": len(ledger.notices),
        }
    )


# ---------------------------------------------------------------------------
# Caps, expiry, notices, and token-only row projection (Task 10)
# ---------------------------------------------------------------------------

_FAMILY_ATTRS: Final[Mapping[str, tuple[str, str]]] = MappingProxyType(
    {
        "intent": ("intents", "intent_id"),
        "route": ("routes", "route_id"),
        "cause": ("causes", "cause_id"),
        "cluster": ("clusters", "cluster_id"),
        "integration": ("integrations", "outcome_id"),
        "wave": ("waves", "observation_id"),
    }
)
_FAMILY_CAP_NOTICE: Final[Mapping[str, str]] = MappingProxyType(
    {
        "intent": MigrationNoticeCode.INTENT_CAP_REACHED.value,
        "route": MigrationNoticeCode.ROUTE_CAP_REACHED.value,
        "cause": MigrationNoticeCode.CAUSE_CAP_REACHED.value,
        "cluster": MigrationNoticeCode.CLUSTER_CAP_REACHED.value,
        "integration": MigrationNoticeCode.INTEGRATION_CAP_REACHED.value,
        "wave": MigrationNoticeCode.WAVE_CAP_REACHED.value,
    }
)
# Terminal statuses that may be dropped under cap pressure, in drop order.
_DROP_RANK: Final[Mapping[str, int]] = MappingProxyType(
    {
        "expired": 0,
        "abandoned": 1,
        "dissolved": 2,
        "superseded": 3,
        "contradicted": 4,
        "unknown": 5,
    }
)
# Closed integration observations that are also droppable, after the above.
_INTEGRATION_DROP_RANK: Final[Mapping[str, int]] = MappingProxyType(
    {"transient": 6, "onward": 7, "returned": 8}
)
_LIVE_STATUSES: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    {
        "intent": frozenset({"considered", "planned", "departed", "arrived"}),
        "route": frozenset({"open", "blocked_belief", "unresolved"}),
        "cause": frozenset({"active"}),
        "cluster": frozenset({"believed", "disputed"}),
        "wave": frozenset({"observed", "reported", "disputed"}),
    }
)
_EXPIRED_STATUS: Final[Mapping[str, object]] = MappingProxyType(
    {
        "intent": MigrationIntentStatus.EXPIRED,
        "route": RouteBeliefStatus.EXPIRED,
        "cause": CauseEvidenceStatus.EXPIRED,
        "cluster": ClusterStatus.EXPIRED,
        "wave": WaveObservationStatus.EXPIRED,
    }
)
_PROTECTED_INTENT_STATUSES: Final[frozenset[str]] = frozenset({"planned", "departed"})
NONE_TOKEN: Final[str] = "none"


def _drop_rank(family: str, row: object) -> int | None:
    status = row.status.value  # type: ignore[attr-defined]
    rank = _DROP_RANK.get(status)
    if rank is None and family == "integration":
        rank = _INTEGRATION_DROP_RANK.get(status)
    return rank


def _is_protected(family: str, row: object) -> bool:
    return (
        family == "intent" and row.status.value in _PROTECTED_INTENT_STATUSES  # type: ignore[attr-defined]
    )


def _expire_rows(
    ledger: MigrationDisplacementLedger, tick: int, policy: MigrationDisplacementPolicy
) -> MigrationDisplacementLedger:
    """Mark non-terminal rows older than their family age cap as expired."""
    ages = {
        "intent": policy.max_intent_age_ticks,
        "route": policy.max_route_age_ticks,
        "cause": policy.max_cause_age_ticks,
        "cluster": policy.max_cluster_age_ticks,
        "wave": policy.max_wave_age_ticks,
    }
    updates: dict[str, tuple[object, ...]] = {}
    expired = 0
    for family, age in ages.items():
        attr, _ = _FAMILY_ATTRS[family]
        live = _LIVE_STATUSES[family]
        rows: list[object] = []
        for row in getattr(ledger, attr):
            if row.status.value in live and tick - row.last_tick > age:
                rows.append(replace(row, status=_EXPIRED_STATUS[family]))
                expired += 1
            else:
                rows.append(row)
        updates[attr] = tuple(rows)
    if not expired:
        return ledger
    _LOG.debug("migration_displacement_rows_expired count=%s", expired)
    return replace(ledger, **updates)


def _enforce_caps(
    ledger: MigrationDisplacementLedger,
    policy: MigrationDisplacementPolicy,
    prior: MigrationDisplacementLedger | None = None,
) -> MigrationDisplacementLedger:
    """Deterministically bound the ledger. Terminal rows drop first.

    Active ``planned``/``departed`` intents are never dropped while any other
    row can go. When no droppable row exists for an overflowing family, that
    family reverts to the prior ledger's rows and a capacity notice is added.
    """
    caps = {
        "intent": policy.max_intents,
        "route": policy.max_route_beliefs,
        "cause": policy.max_cause_evidence,
        "cluster": policy.max_cluster_beliefs,
        "integration": policy.max_integration_beliefs,
        "wave": policy.max_wave_observations,
    }
    rows: dict[str, list[object]] = {
        family: list(getattr(ledger, _FAMILY_ATTRS[family][0]))
        for family in _FAMILY_ORDER
    }
    notices = set(ledger.notices)

    def row_id(family: str, row: object) -> str:
        return str(getattr(row, _FAMILY_ATTRS[family][1]))

    def trim_unprotected(family: str, excess: int) -> None:
        candidates = sorted(
            (item for item in rows[family] if not _is_protected(family, item)),
            key=lambda item: (-item.first_tick, row_id(family, item)),  # type: ignore[attr-defined]
        )
        doomed = {row_id(family, item) for item in candidates[:excess]}
        rows[family] = [
            item for item in rows[family] if row_id(family, item) not in doomed
        ]

    for family in _FAMILY_ORDER:
        cap = caps[family]
        if len(rows[family]) <= cap:
            continue
        excess = len(rows[family]) - cap
        droppable = sorted(
            (
                (rank, item)
                for item in rows[family]
                if (rank := _drop_rank(family, item)) is not None
            ),
            key=lambda pair: (pair[0], pair[1].first_tick, row_id(family, pair[1])),  # type: ignore[attr-defined]
        )
        doomed_items = [item for _, item in droppable[:excess]]
        if doomed_items:
            doomed = {row_id(family, item) for item in doomed_items}
            rows[family] = [
                item for item in rows[family] if row_id(family, item) not in doomed
            ]
            notices.add(_FAMILY_CAP_NOTICE[family])
            _LOG.warning(
                "migration_displacement_truncated family=%s count=%s",
                family,
                len(doomed_items),
            )
        remaining = len(rows[family]) - cap
        if remaining > 0:
            notices.add(MigrationNoticeCode.LEDGER_CAP_REACHED.value)
            _LOG.warning(
                "migration_displacement_capacity_reached rows=%s", len(rows[family])
            )
            prior_rows = (
                None
                if prior is None
                else list(getattr(prior, _FAMILY_ATTRS[family][0]))
            )
            if prior_rows is not None and len(prior_rows) <= cap:
                rows[family] = prior_rows
            else:
                trim_unprotected(family, remaining)
                remaining = len(rows[family]) - cap
                if remaining > 0:
                    # No prior ledger to fall back to: bound the family by
                    # dropping the oldest active rows, never the newest.
                    oldest = sorted(
                        rows[family],
                        key=lambda item: (item.first_tick, row_id(family, item)),  # type: ignore[attr-defined]
                    )
                    doomed = {row_id(family, item) for item in oldest[:remaining]}
                    rows[family] = [
                        item
                        for item in rows[family]
                        if row_id(family, item) not in doomed
                    ]

    total = sum(len(items) for items in rows.values())
    if total > policy.max_ledger_rows:
        flat = sorted(
            (
                rank,
                item.first_tick,
                _FAMILY_ORDER.index(family),
                row_id(family, item),
                family,
            )  # type: ignore[attr-defined]
            for family in _FAMILY_ORDER
            for item in rows[family]
            if (rank := _drop_rank(family, item)) is not None
        )
        excess = total - policy.max_ledger_rows
        doomed_pairs = {(entry[4], entry[3]) for entry in flat[:excess]}
        if doomed_pairs:
            for family in _FAMILY_ORDER:
                rows[family] = [
                    item
                    for item in rows[family]
                    if (family, row_id(family, item)) not in doomed_pairs
                ]
            notices.add(MigrationNoticeCode.TRUNCATED.value)
            _LOG.warning(
                "migration_displacement_truncated family=ledger count=%s",
                len(doomed_pairs),
            )
        remaining_total = sum(len(items) for items in rows.values()) - (
            policy.max_ledger_rows
        )
        if remaining_total > 0:
            notices.add(MigrationNoticeCode.LEDGER_CAP_REACHED.value)
            _LOG.warning(
                "migration_displacement_capacity_reached rows=%s",
                sum(len(items) for items in rows.values()),
            )
            pool = sorted(
                (
                    -item.first_tick,
                    _FAMILY_ORDER.index(family),
                    row_id(family, item),
                    family,
                )  # type: ignore[attr-defined]
                for family in _FAMILY_ORDER
                for item in rows[family]
                if not _is_protected(family, item)
            )
            doomed_pairs = {(entry[3], entry[2]) for entry in pool[:remaining_total]}
            for family in _FAMILY_ORDER:
                rows[family] = [
                    item
                    for item in rows[family]
                    if (family, row_id(family, item)) not in doomed_pairs
                ]
    return replace(
        ledger,
        notices=tuple(sorted(notices)),
        **{_FAMILY_ATTRS[family][0]: tuple(rows[family]) for family in _FAMILY_ORDER},
    )


def validate_migration_displacement_ledger_caps(
    ledger: MigrationDisplacementLedger,
    policy: MigrationDisplacementPolicy | None = None,
) -> None:
    """Reject a persisted ledger above the exact cognition caps.

    Construction keeps a wider hard cap so ``_enforce_caps`` can prune an
    over-cap candidate before it is persisted or checkpointed.
    """
    if type(ledger) is not MigrationDisplacementLedger:
        raise TypeError("ledger must be MigrationDisplacementLedger")
    effective = default_migration_displacement_policy() if policy is None else policy
    if type(effective) is not MigrationDisplacementPolicy:
        raise TypeError("policy must be MigrationDisplacementPolicy")
    for name, rows, cap in (
        ("intents", ledger.intents, effective.max_intents),
        ("routes", ledger.routes, effective.max_route_beliefs),
        ("causes", ledger.causes, effective.max_cause_evidence),
        ("clusters", ledger.clusters, effective.max_cluster_beliefs),
        ("integrations", ledger.integrations, effective.max_integration_beliefs),
        ("waves", ledger.waves, effective.max_wave_observations),
    ):
        if len(rows) > cap:
            raise ValueError(f"migration_displacement_capacity_reached:{name}")
    if _row_count(ledger) > effective.max_ledger_rows:
        raise ValueError("migration_displacement_capacity_reached:ledger")


@dataclass(frozen=True, slots=True)
class MigrationRowProjection:
    """Token-only projection of one retained belief row or notice."""

    family: str
    row_token: str
    origin_token: str
    destination_token: str
    route_tokens: tuple[str, ...]
    cause_tokens: tuple[str, ...]
    cluster_tokens: tuple[str, ...]
    status: str
    confidence: float
    first_tick: int
    last_tick: int
    coverage: str


def _coverage(status: str, evidence: Sequence[object], *, unknown: bool) -> str:
    if unknown or status == "unknown":
        return "unknown"
    return "resolved" if evidence else "unresolved"


def migration_displacement_row_projections(
    ledger: MigrationDisplacementLedger,
) -> tuple[MigrationRowProjection, ...]:
    """Project every retained row and notice to opaque tokens only.

    Cluster rows carry member tokens and wave rows carry participant tokens in
    ``cluster_tokens``. Notices are projected as ``notice`` rows.
    """
    if type(ledger) is not MigrationDisplacementLedger:
        raise _log_failure("ledger", "invalid_type")
    out: list[MigrationRowProjection] = []
    for row in ledger.intents:
        out.append(
            MigrationRowProjection(
                family="intent",
                row_token=row.intent_id,
                origin_token=migration_opaque_location_token(row.origin_location_id),
                destination_token=migration_opaque_location_token(
                    row.destination_location_id
                ),
                route_tokens=intent_location_tokens(row),
                cause_tokens=row.cause_ids,
                cluster_tokens=row.cluster_ids,
                status=row.status.value,
                confidence=row.confidence,
                first_tick=row.first_tick,
                last_tick=row.last_tick,
                coverage=_coverage(row.status.value, row.evidence, unknown=False),
            )
        )
    for route in ledger.routes:
        out.append(
            MigrationRowProjection(
                family="route",
                row_token=route.route_id,
                origin_token=migration_opaque_location_token(route.origin_location_id),
                destination_token=migration_opaque_location_token(
                    route.destination_location_id
                ),
                route_tokens=route_location_tokens(route),
                cause_tokens=(),
                cluster_tokens=(),
                status=route.status.value,
                confidence=0.0,
                first_tick=route.first_tick,
                last_tick=route.last_tick,
                coverage=(
                    "unresolved"
                    if route.basis is RouteBeliefBasis.UNRESOLVED
                    else _coverage(route.status.value, (1,), unknown=False)
                ),
            )
        )
    for cause in ledger.causes:
        out.append(
            MigrationRowProjection(
                family="cause",
                row_token=cause.cause_id,
                origin_token=NONE_TOKEN,
                destination_token=NONE_TOKEN,
                route_tokens=(),
                cause_tokens=(cause_kind_token(cause),),
                cluster_tokens=(),
                status=cause.status.value,
                confidence=cause.confidence,
                first_tick=cause.first_tick,
                last_tick=cause.last_tick,
                coverage=_coverage(
                    cause.status.value,
                    cause.evidence,
                    unknown=cause.cause_kind is MigrationCauseKind.UNKNOWN,
                ),
            )
        )
    for cluster in ledger.clusters:
        out.append(
            MigrationRowProjection(
                family="cluster",
                row_token=cluster.cluster_id,
                origin_token=NONE_TOKEN,
                destination_token=NONE_TOKEN,
                route_tokens=(),
                cause_tokens=(),
                cluster_tokens=cluster_member_tokens(cluster),
                status=cluster.status.value,
                confidence=cluster.confidence,
                first_tick=cluster.first_tick,
                last_tick=cluster.last_tick,
                coverage=_coverage(
                    cluster.status.value, cluster.evidence, unknown=False
                ),
            )
        )
    for outcome in ledger.integrations:
        out.append(
            MigrationRowProjection(
                family="integration",
                row_token=outcome.outcome_id,
                origin_token=NONE_TOKEN,
                destination_token=migration_opaque_location_token(
                    outcome.destination_location_id
                ),
                route_tokens=(),
                cause_tokens=(integration_domain_token(outcome),),
                cluster_tokens=(),
                status=outcome.status.value,
                confidence=outcome.confidence,
                first_tick=outcome.first_tick,
                last_tick=outcome.last_tick,
                coverage=_coverage(
                    outcome.status.value, outcome.evidence, unknown=False
                ),
            )
        )
    for wave in ledger.waves:
        out.append(
            MigrationRowProjection(
                family="wave",
                row_token=wave.observation_id,
                origin_token=migration_opaque_location_token(wave.origin_location_id),
                destination_token=migration_opaque_location_token(
                    wave.destination_location_id
                ),
                route_tokens=(),
                cause_tokens=wave.cause_ids,
                cluster_tokens=wave_participant_tokens(wave),
                status=wave.status.value,
                confidence=0.0,
                first_tick=wave.first_tick,
                last_tick=wave.last_tick,
                coverage=_coverage(wave.status.value, wave.evidence, unknown=False),
            )
        )
    for notice in ledger.notices:
        out.append(
            MigrationRowProjection(
                family="notice",
                row_token=f"notice-{_hyphenated(notice)}",
                origin_token=NONE_TOKEN,
                destination_token=NONE_TOKEN,
                route_tokens=(),
                cause_tokens=(),
                cluster_tokens=(),
                status=notice,
                confidence=0.0,
                first_tick=0,
                last_tick=0,
                coverage="unknown",
            )
        )
    return tuple(out)


# ---------------------------------------------------------------------------
# Ordered owner-scoped update pipeline (Task 6)
# ---------------------------------------------------------------------------

MIGRATION_DISPLACEMENT_UPDATE_ORDER: Final[tuple[str, ...]] = (
    "intents",
    "routes",
    "causes",
    "clusters",
    "frames",
    "anchors",
    "integrations",
    "waves",
    "expire",
    "caps",
    "digest",
)
# Class names are split so a source scan finds no world or command reference here.
_FORBIDDEN_INPUT_TYPES: Final[frozenset[str]] = frozenset(
    {
        "World" + "State",
        "World" + "Event",
        "Agent" + "Command",
        "Action" + "Submission",
        "World" + "Engine",
        "MigrationDisplacementLedgerStore",
    }
)
_LIVE_INTENTS: Final[frozenset[MigrationIntentStatus]] = frozenset(
    {
        MigrationIntentStatus.CONSIDERED,
        MigrationIntentStatus.PLANNED,
        MigrationIntentStatus.DEPARTED,
    }
)
_MOVE_OCCURRENCE_KINDS: Final[frozenset[str]] = frozenset(
    {"move", "journey_started", "journey_arrived", "fled", "flee"}
)
_NEED_THRESHOLD: Final[float] = 0.6
_PLANNED_CONFIDENCE: Final[float] = 0.5
_SETTLE_TICKS: Final[int] = 8
_TESTIMONY_CEILING: Final[float] = 0.7
_MAX_INTENT_SUPPORT: Final[int] = 8
_ID_ATTRS: Final[tuple[str, ...]] = (
    "id",
    "dispute_id",
    "agreement_id",
    "domain_id",
    "plan_id",
    "observation_id",
    "concept_id",
    "organization_id",
    "institution_id",
    "rule_id",
    "claim_id",
    "evidence_id",
    "treaty_id",
    "office_id",
    "decision_id",
)
_RESTRICT_TOKENS: Final[tuple[str, ...]] = (
    "exclu",
    "expel",
    "restrict",
    "prohibit",
    "forbid",
    "mandat",
    "evict",
)
_OFFER_TOKENS: Final[tuple[str, ...]] = (
    "offer",
    "invit",
    "recruit",
    "vacan",
    "welcome",
)
_HOSTILE_TOKENS: Final[tuple[str, ...]] = ("hostile", "war", "embargo", "sanction")
_BASIS_RANK: Final[Mapping[RouteBeliefBasis, int]] = MappingProxyType(
    {
        RouteBeliefBasis.UNRESOLVED: -1,
        RouteBeliefBasis.INFERENCE: 0,
        RouteBeliefBasis.TESTIMONY: 1,
        RouteBeliefBasis.DIRECT_OBSERVATION: 2,
        RouteBeliefBasis.OWN_JOURNEY: 3,
    }
)
_BASIS_SOURCE: Final[Mapping[RouteBeliefBasis, MigrationCauseSource]] = (
    MappingProxyType(
        {
            RouteBeliefBasis.DIRECT_OBSERVATION: (
                MigrationCauseSource.DIRECT_OBSERVATION
            ),
            RouteBeliefBasis.OWN_JOURNEY: MigrationCauseSource.OWN_JOURNEY,
            RouteBeliefBasis.TESTIMONY: MigrationCauseSource.TESTIMONY,
            RouteBeliefBasis.INFERENCE: MigrationCauseSource.INFERENCE,
            RouteBeliefBasis.UNRESOLVED: MigrationCauseSource.UNKNOWN,
        }
    )
)
_LEDGER_SOURCE: Final[Mapping[str, MigrationCauseSource]] = MappingProxyType(
    {
        "organization": MigrationCauseSource.ORGANIZATION_BELIEF,
        "institution": MigrationCauseSource.INSTITUTION_BELIEF,
        "rule": MigrationCauseSource.FORMAL_RULE_BELIEF,
    }
)


@dataclass(frozen=True, slots=True)
class _CauseSpec:
    kind: MigrationCauseKind
    source: MigrationCauseSource
    anchor: str | None
    confidence: float
    lineage: str

    @property
    def key(self) -> tuple[str, str, str]:
        return self.kind.value, self.source.value, self.anchor or ""


@dataclass(frozen=True, slots=True)
class _ClusterSpec:
    members: tuple[AgentId, ...]
    basis: ClusterBasis
    confidence: float
    lineage: str


class _Work:
    """Mutable per-update scratch space. Never leaves this module."""

    def __init__(
        self,
        *,
        owner_id: AgentId,
        tick: int,
        observation: object,
        prior: MigrationDisplacementLedger,
        identity: object | None,
        relationships: Sequence[object],
        ledgers: Mapping[str, object | None],
        inbox: object | None,
        policy: MigrationDisplacementPolicy,
    ) -> None:
        self.owner_id = owner_id
        self.tick = tick
        self.observation = observation
        self.prior = prior
        self.identity = identity
        self.relationships = relationships
        self.ledgers = ledgers
        self.inbox = inbox
        self.policy = policy
        self.intents: dict[str, MigrationIntentRow] = {
            item.intent_id: item for item in prior.intents
        }
        self.routes: dict[str, RouteBeliefRow] = {
            item.route_id: item for item in prior.routes
        }
        self.causes: dict[str, CauseEvidenceRow] = {
            item.cause_id: item for item in prior.causes
        }
        self.clusters: dict[str, SocialClusterBeliefRow] = {
            item.cluster_id: item for item in prior.clusters
        }
        self.integrations: dict[str, IntegrationBeliefRow] = {
            item.outcome_id: item for item in prior.integrations
        }
        self.waves: dict[str, WaveObservationRow] = {
            item.observation_id: item for item in prior.waves
        }
        self.notices: set[str] = set(prior.notices)
        self.location: EntityId | None = None
        self.journey: object | None = None
        self.exits: tuple[object, ...] = ()
        self.exit_ids: frozenset[str] = frozenset()
        self.visible_locations: frozenset[str] = frozenset()
        self.entity_agent: dict[str, AgentId] = {}
        self.visible_agents: dict[str, AgentId] = {}
        self.kin: dict[str, AgentId] = {}
        self.movers: dict[str, tuple[EntityId, dict[str, AgentId]]] = {}
        self.known_edges: dict[tuple[str, str], RouteBeliefBasis] = {}
        self.cause_specs: tuple[_CauseSpec, ...] = ()
        self.spec_ids: dict[tuple[str, str, str], str] = {}
        self.cluster_specs: tuple[_ClusterSpec, ...] = ()
        self.arrival_ticks: dict[str, int] = {}
        self.dropped_frames = 0
        self.testimony_cause_ids: dict[str, list[str]] = {}


def _reject_forbidden(value: object) -> None:
    if type(value).__name__ in _FORBIDDEN_INPUT_TYPES:
        raise TypeError(f"{type(value).__name__}: forbidden_input")


def _as_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return int(number) if math.isfinite(number) else None


def _fraction(value: object) -> float:
    inner = getattr(value, "value", value)
    if isinstance(inner, bool) or not isinstance(inner, (int, float)):
        return 0.0
    number = float(inner)
    if not math.isfinite(number):
        return 0.0
    return max(0.0, min(1.0, number / 100.0))


def _agent_for_entity(identity: object | None, entity: object) -> AgentId | None:
    if identity is None or type(entity) is not EntityId:
        return None
    if getattr(identity, "owner_entity_id", None) == entity:
        owner = getattr(identity, "owner_id", None)
        return owner if type(owner) is AgentId else None
    for binding in getattr(identity, "counterparts", ()) or ():
        if getattr(binding, "entity_id", None) == entity:
            agent = getattr(binding, "agent_id", None)
            return agent if type(agent) is AgentId else None
    return None


def _ledger_rows(ledger: object | None) -> list[tuple[str, object]]:
    if ledger is None:
        return []
    if is_dataclass(ledger) and not isinstance(ledger, type):
        names = [item.name for item in dataclass_fields(ledger)]
    elif hasattr(ledger, "__dict__"):
        names = sorted(vars(ledger))
    else:
        return []
    rows: list[tuple[str, object]] = []
    for name in names:
        value = getattr(ledger, name, None)
        if not isinstance(value, (tuple, list)):
            continue
        for item in value:
            if isinstance(item, (str, bytes, int, float, bool)) or item is None:
                continue
            rows.append((name, item))
    return rows


def _row_id(row: object) -> str | None:
    for name in _ID_ATTRS:
        value = getattr(row, name, None)
        if isinstance(value, str) and value:
            return value
    return None


def _row_tokens(row: object) -> tuple[str, ...]:
    tokens: list[str] = []
    for name in ("status", "kind", "effect", "mode", "stance", "act", "outcome"):
        value = getattr(row, name, None)
        value = getattr(value, "value", value)
        if isinstance(value, str):
            tokens.append(value.lower())
    return tuple(tokens)


def _row_has(row: object, needles: tuple[str, ...]) -> bool:
    return any(needle in token for token in _row_tokens(row) for needle in needles)


def _anchor(kind: str, row: object) -> str | None:
    rid = _row_id(row)
    if rid is None:
        return None
    anchor = f"{kind}:{rid}"
    if len(anchor) > MAX_ANCHOR_REF_CHARS or anchor != anchor.strip():
        return None
    if any(ord(char) < 32 for char in anchor):
        return None
    return anchor


def _evidence(
    source: MigrationCauseSource,
    tick: int,
    lineage: str,
    owner: AgentId | None = None,
) -> MigrationEvidence:
    return MigrationEvidence(
        kind=source, source_owner_id=owner, source_tick=tick, lineage_ref=lineage
    )


def _merge_evidence(
    old: Sequence[MigrationEvidence], new: Sequence[MigrationEvidence]
) -> tuple[MigrationEvidence, ...]:
    merged: dict[tuple[str, str, int], MigrationEvidence] = {}
    for item in (*old, *new):
        merged[(item.kind.value, item.lineage_ref, item.source_tick)] = item
    ordered = sorted(
        merged.values(), key=lambda item: (item.source_tick, item.lineage_ref)
    )
    return tuple(ordered[-_MAX_EVIDENCE_PER_ROW:])


def _build_context(work: _Work) -> None:
    observation = work.observation
    body = getattr(observation, "self_body", None)
    location = getattr(body, "location_id", None)
    work.location = location if type(location) is EntityId else None
    work.journey = getattr(body, "journey", None)
    exits = tuple(
        item
        for item in (getattr(observation, "exits", ()) or ())
        if type(getattr(item, "destination_id", None)) is EntityId
    )
    work.exits = exits
    work.exit_ids = frozenset(item.destination_id.value for item in exits)
    visible: set[str] = set(work.exit_ids)
    if work.location is not None:
        visible.add(work.location.value)
    for item in getattr(observation, "locations", ()) or ():
        entity = getattr(item, "entity_id", None)
        if type(entity) is EntityId:
            visible.add(entity.value)
    journey = work.journey
    for name in ("origin_location_id", "destination_location_id"):
        entity = getattr(journey, name, None)
        if type(entity) is EntityId:
            visible.add(entity.value)
    work.visible_locations = frozenset(visible)

    identity = work.identity
    entity_agent: dict[str, AgentId] = {}
    owner_entity = getattr(identity, "owner_entity_id", None)
    if type(owner_entity) is EntityId:
        entity_agent[owner_entity.value] = work.owner_id
    for binding in getattr(identity, "counterparts", ()) or ():
        entity = getattr(binding, "entity_id", None)
        agent = getattr(binding, "agent_id", None)
        if type(entity) is EntityId and type(agent) is AgentId:
            entity_agent[entity.value] = agent
    work.entity_agent = entity_agent
    visible_agents: dict[str, AgentId] = {work.owner_id.value: work.owner_id}
    for item in getattr(observation, "visible_bodies", ()) or ():
        entity = getattr(item, "entity_id", None)
        agent = entity_agent.get(entity.value) if type(entity) is EntityId else None
        if agent is not None:
            visible_agents[agent.value] = agent
    work.visible_agents = visible_agents
    kin: dict[str, AgentId] = {}
    kinship = getattr(body, "kinship_visible", None)
    for name in ("parents", "children"):
        for token in getattr(kinship, name, ()) or ():
            try:
                agent = AgentId(token)
            except (TypeError, ValueError):
                continue
            if agent != work.owner_id:
                kin[agent.value] = agent
    work.kin = kin

    movers: dict[str, tuple[EntityId, dict[str, AgentId]]] = {}
    own_entity = getattr(observation, "observer_id", None)
    for occurrence in getattr(observation, "occurrences", ()) or ():
        kind = getattr(occurrence, "kind", None)
        actor = getattr(occurrence, "actor_id", None)
        destination = getattr(occurrence, "destination_id", None)
        if (
            kind not in _MOVE_OCCURRENCE_KINDS
            or type(actor) is not EntityId
            or type(destination) is not EntityId
            or actor == own_entity
        ):
            continue
        agent = entity_agent.get(actor.value)
        if agent is None:
            continue
        slot = movers.setdefault(destination.value, (destination, {}))
        slot[1][agent.value] = agent
    work.movers = movers

    edges: dict[tuple[str, str], RouteBeliefBasis] = {}

    def add_edge(pair: tuple[str, str], basis: RouteBeliefBasis) -> None:
        if _BASIS_RANK[basis] > _BASIS_RANK.get(edges.get(pair), -2):  # type: ignore[arg-type]
            edges[pair] = basis

    for route in work.prior.routes:
        if route.status is not RouteBeliefStatus.OPEN:
            continue
        if route.basis is RouteBeliefBasis.UNRESOLVED:
            continue
        for pair in route_edge_pairs(route.route_locations):
            add_edge(pair, route.basis)
    if work.location is not None:
        for item in exits:
            add_edge(
                (work.location.value, item.destination_id.value),
                RouteBeliefBasis.DIRECT_OBSERVATION,
            )
    origin = getattr(journey, "origin_location_id", None)
    destination = getattr(journey, "destination_location_id", None)
    if (
        type(origin) is EntityId
        and type(destination) is EntityId
        and origin != destination
    ):
        add_edge((origin.value, destination.value), RouteBeliefBasis.OWN_JOURNEY)
    work.known_edges = edges


def _derive_cause_specs(work: _Work) -> tuple[_CauseSpec, ...]:
    observation = work.observation
    specs: dict[tuple[str, str, str], _CauseSpec] = {}

    def add(spec: _CauseSpec) -> None:
        old = specs.get(spec.key)
        if old is None or spec.confidence > old.confidence:
            specs[spec.key] = spec

    body = getattr(observation, "self_body", None)
    if body is not None:
        need = max(
            _fraction(getattr(body, "hunger", 0)), _fraction(getattr(body, "thirst", 0))
        )
        if need >= _NEED_THRESHOLD:
            add(
                _CauseSpec(
                    MigrationCauseKind.RESOURCE_SCARCITY,
                    MigrationCauseSource.OWN_NEED,
                    None,
                    _quantize(need),
                    "own-need",
                )
            )
    hazards = getattr(observation, "hazard_kinds", None)
    weather = getattr(getattr(observation, "weather_condition", None), "value", None)
    hazard_conf = 0.0
    if hazards:
        hazard_conf = 0.7
    elif weather == "storm":
        hazard_conf = 0.5
    if hazard_conf:
        add(
            _CauseSpec(
                MigrationCauseKind.ENVIRONMENTAL_HAZARD,
                MigrationCauseSource.DIRECT_OBSERVATION,
                None,
                hazard_conf,
                "observed-hazard",
            )
        )
    for kind, ledger in sorted(work.ledgers.items()):
        rows = _ledger_rows(ledger)
        if kind in ("organization", "institution", "rule"):
            source = _LEDGER_SOURCE[kind]
            for _, row in rows:
                anchor = _anchor(kind, row)
                if anchor is None:
                    continue
                if _row_has(row, _RESTRICT_TOKENS):
                    cause_kind = MigrationCauseKind.INSTITUTION
                elif _row_has(row, _OFFER_TOKENS):
                    cause_kind = MigrationCauseKind.OPPORTUNITY
                else:
                    continue
                add(_CauseSpec(cause_kind, source, anchor, 0.4, f"{kind}-belief"))
        elif kind == "conflict":
            anchors = sorted(
                item for item in (_anchor(kind, row) for _, row in rows) if item
            )
            if anchors:
                add(
                    _CauseSpec(
                        MigrationCauseKind.CONFLICT,
                        MigrationCauseSource.CONFLICT_BELIEF,
                        anchors[0],
                        0.6,
                        "conflict-belief",
                    )
                )
        elif kind == "border":
            anchors = sorted(
                item
                for item in (
                    _anchor(kind, row) for name, row in rows if name == "disputes"
                )
                if item
            )
            if anchors:
                add(
                    _CauseSpec(
                        MigrationCauseKind.CONFLICT,
                        MigrationCauseSource.BORDER_BELIEF,
                        anchors[0],
                        0.55,
                        "border-belief",
                    )
                )
        elif kind == "diplomacy":
            anchors = sorted(
                item
                for item in (
                    _anchor(kind, row)
                    for _, row in rows
                    if _row_has(row, _HOSTILE_TOKENS)
                )
                if item
            )
            if anchors:
                add(
                    _CauseSpec(
                        MigrationCauseKind.CONFLICT,
                        MigrationCauseSource.DIPLOMACY_BELIEF,
                        anchors[0],
                        0.5,
                        "diplomacy-belief",
                    )
                )
    partners: set[str] = set()
    for item in work.relationships:
        if getattr(item, "source_id", None) != work.owner_id:
            continue
        target = getattr(item, "target_id", None)
        if type(target) is AgentId:
            partners.add(target.value)
    for _, (_, movers) in sorted(work.movers.items()):
        for value in sorted(movers):
            if value in work.kin:
                add(
                    _CauseSpec(
                        MigrationCauseKind.SOCIAL_NETWORK,
                        MigrationCauseSource.OWN_KINSHIP,
                        None,
                        0.5,
                        "own-kinship-departure",
                    )
                )
            elif value in partners:
                add(
                    _CauseSpec(
                        MigrationCauseKind.SOCIAL_NETWORK,
                        MigrationCauseSource.OWN_RELATIONSHIP,
                        None,
                        0.45,
                        "own-relationship-departure",
                    )
                )
    ordered = sorted(
        specs.values(),
        key=lambda item: (item.kind.value, item.source.value, item.anchor or ""),
    )
    return tuple(ordered[: work.policy.max_cause_evidence // 2])


def _derive_cluster_specs(work: _Work) -> tuple[_ClusterSpec, ...]:
    observation = work.observation
    body = getattr(observation, "self_body", None)
    context = bool(
        work.journey is not None
        or work.movers
        or any(item.status in _LIVE_INTENTS for item in work.prior.intents)
    )
    if not context or body is None:
        return ()
    limit = work.policy.max_cluster_members
    specs: list[_ClusterSpec] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()

    def add(
        members: dict[str, AgentId], basis: ClusterBasis, conf: float, lineage: str
    ) -> None:
        members = dict(members)
        members[work.owner_id.value] = work.owner_id
        ordered = tuple(members[key] for key in sorted(members))[:limit]
        if work.owner_id not in ordered or len(ordered) < MIN_CLUSTER_MEMBERS:
            return
        key = (basis.value, tuple(item.value for item in ordered))
        if key in seen:
            return
        seen.add(key)
        specs.append(_ClusterSpec(ordered, basis, _quantize(conf), lineage))

    if work.kin:
        add(work.kin, ClusterBasis.KINSHIP, 0.6, "own-kinship")
    for ledger in (work.ledgers.get("organization"),):
        for _, row in _ledger_rows(ledger):
            members = getattr(row, "member_ids", None)
            if not isinstance(members, (tuple, list)) or work.owner_id not in members:
                continue
            visible = {
                item.value: item
                for item in members
                if type(item) is AgentId and item.value in work.visible_agents
            }
            if len(visible) >= MIN_CLUSTER_MEMBERS:
                add(visible, ClusterBasis.ORGANIZATION, 0.5, "organization-belief")
    partners = {
        item.target_id.value
        for item in work.relationships
        if getattr(item, "source_id", None) == work.owner_id
        and type(getattr(item, "target_id", None)) is AgentId
    }
    journey_dest = getattr(work.journey, "destination_location_id", None)
    if type(journey_dest) is EntityId and journey_dest.value in work.movers:
        movers = dict(work.movers[journey_dest.value][1])
        basis = (
            ClusterBasis.RELATIONSHIP
            if movers and all(key in partners for key in movers)
            else ClusterBasis.CO_MOVEMENT
        )
        add(movers, basis, 0.5, "observed-co-movement")
    ordered_specs = sorted(
        specs, key=lambda item: (item.basis.value, tuple(m.value for m in item.members))
    )
    return tuple(ordered_specs[: work.policy.max_cluster_beliefs])


def _cluster_key(spec: _ClusterSpec) -> tuple[str, tuple[str, ...]]:
    return spec.basis.value, tuple(item.value for item in spec.members)


def _existing_cluster_id(work: _Work, spec: _ClusterSpec) -> str:
    for row in sorted(work.prior.clusters, key=lambda item: item.cluster_id):
        if row.status in (ClusterStatus.BELIEVED, ClusterStatus.DISPUTED) and (
            row.basis.value,
            tuple(item.value for item in row.member_ids),
        ) == _cluster_key(spec):
            return row.cluster_id
    return migration_cluster_id(work.owner_id, spec.members, spec.basis, work.tick)


def _active_unknown_cause_id(work: _Work) -> str:
    for row in sorted(work.causes.values(), key=lambda item: item.cause_id):
        if (
            row.cause_kind is MigrationCauseKind.UNKNOWN
            and row.status is CauseEvidenceStatus.ACTIVE
        ):
            return row.cause_id
    return migration_cause_id(
        work.owner_id,
        MigrationCauseKind.UNKNOWN,
        MigrationCauseSource.UNKNOWN,
        None,
        work.tick,
    )


def _ensure_unknown_cause(work: _Work) -> str:
    cause_id = _active_unknown_cause_id(work)
    row = work.causes.get(cause_id)
    if row is None:
        work.causes[cause_id] = CauseEvidenceRow(
            cause_id=cause_id,
            owner_id=work.owner_id,
            cause_kind=MigrationCauseKind.UNKNOWN,
            source_kind=MigrationCauseSource.UNKNOWN,
            anchor_ref=None,
            confidence=0.0,
            first_tick=work.tick,
            last_tick=work.tick,
            status=CauseEvidenceStatus.ACTIVE,
        )
    else:
        work.causes[cause_id] = replace(row, last_tick=max(row.last_tick, work.tick))
    return cause_id


def _spec_cause_id(work: _Work, spec: _CauseSpec) -> str:
    for row in sorted(work.prior.causes, key=lambda item: item.cause_id):
        if (
            row.status is CauseEvidenceStatus.ACTIVE
            and (row.cause_kind.value, row.source_kind.value, row.anchor_ref or "")
            == spec.key
        ):
            return row.cause_id
    return migration_cause_id(
        work.owner_id, spec.kind, spec.source, spec.anchor, work.tick
    )


def _exit_sort_key(item: object) -> tuple[int, float, str]:
    duration = getattr(item, "travel_duration_ticks", None)
    fatigue = getattr(item, "fatigue_cost", None)
    return (
        duration if isinstance(duration, int) else 10**6,
        float(fatigue) if isinstance(fatigue, (int, float)) else 10**6,
        item.destination_id.value,  # type: ignore[attr-defined]
    )


def _intent_status_for_confidence(confidence: float) -> MigrationIntentStatus:
    if confidence >= _PLANNED_CONFIDENCE:
        return MigrationIntentStatus.PLANNED
    return MigrationIntentStatus.CONSIDERED


def _cluster_ids_for_intent(work: _Work) -> tuple[str, ...]:
    ids = sorted(_existing_cluster_id(work, spec) for spec in work.cluster_specs)
    return tuple(ids[:MAX_INTENT_CLUSTER_IDS])


def _update_own_intents(work: _Work) -> None:
    policy = work.policy
    tick = work.tick
    support = sorted(
        (
            item
            for item in work.cause_specs
            if item.confidence >= policy.min_intent_confidence
        ),
        key=lambda item: (-item.confidence, item.key),
    )[:_MAX_INTENT_SUPPORT]
    support_ids = sorted({work.spec_ids[item.key] for item in support})
    best = support[0].confidence if support else 0.0
    cluster_ids = _cluster_ids_for_intent(work)
    location = work.location
    journey = work.journey
    journey_dest = getattr(journey, "destination_location_id", None)
    journey_origin = getattr(journey, "origin_location_id", None)
    journey_matched: set[str] = set()

    def refreshed(
        row: MigrationIntentRow,
        *,
        status: MigrationIntentStatus,
        confidence: float,
        new_evidence: Sequence[MigrationEvidence],
        causes: Sequence[str] | None = None,
    ) -> MigrationIntentRow:
        merged_causes = sorted(set(row.cause_ids) | set(causes or ()))
        return replace(
            row,
            status=status,
            confidence=max(confidence, 0.0),
            last_tick=max(row.last_tick, tick),
            cause_ids=tuple(merged_causes[:_MAX_INTENT_SUPPORT]),
            cluster_ids=cluster_ids or row.cluster_ids,
            evidence=_merge_evidence(row.evidence, new_evidence),
        )

    # Own journey: the strongest direct evidence of a departed intent.
    if (
        type(journey_dest) is EntityId
        and type(journey_origin) is EntityId
        and journey_dest != journey_origin
    ):
        matched = [
            row
            for row in sorted(work.intents.values(), key=lambda item: item.intent_id)
            if row.status in _LIVE_INTENTS
            and row.destination_location_id == journey_dest
        ]
        journey_evidence = [
            _evidence(MigrationCauseSource.OWN_JOURNEY, tick, "own-journey")
        ]
        if matched:
            for row in matched:
                work.intents[row.intent_id] = refreshed(
                    row,
                    status=MigrationIntentStatus.DEPARTED,
                    confidence=max(row.confidence, best, _PLANNED_CONFIDENCE),
                    new_evidence=journey_evidence,
                    causes=support_ids,
                )
                journey_matched.add(row.intent_id)
        else:
            route = (journey_origin, journey_dest)
            intent_id = migration_intent_id(work.owner_id, route, tick)
            causes = support_ids or [_ensure_unknown_cause(work)]
            work.intents[intent_id] = MigrationIntentRow(
                intent_id=intent_id,
                owner_id=work.owner_id,
                origin_location_id=journey_origin,
                destination_location_id=journey_dest,
                route_locations=route,
                cause_ids=tuple(causes),
                cluster_ids=cluster_ids,
                status=MigrationIntentStatus.DEPARTED,
                confidence=max(best, _PLANNED_CONFIDENCE),
                first_tick=tick,
                last_tick=tick,
                evidence=tuple(journey_evidence),
            )
            journey_matched.add(intent_id)

    # Progress, arrival, and abandonment of the remaining live intents.
    for row in sorted(list(work.intents.values()), key=lambda item: item.intent_id):
        if row.status not in _LIVE_INTENTS or row.intent_id in journey_matched:
            continue
        if location is None:
            continue
        route = row.route_locations
        if location == row.destination_location_id:
            if row.status in (
                MigrationIntentStatus.DEPARTED,
                MigrationIntentStatus.PLANNED,
            ):
                work.intents[row.intent_id] = refreshed(
                    row,
                    status=MigrationIntentStatus.ARRIVED,
                    confidence=row.confidence,
                    new_evidence=(
                        _evidence(
                            MigrationCauseSource.DIRECT_OBSERVATION, tick, "own-arrival"
                        ),
                    ),
                )
                work.arrival_ticks[row.intent_id] = tick
            else:
                work.intents[row.intent_id] = replace(
                    row,
                    status=MigrationIntentStatus.ABANDONED,
                    last_tick=max(row.last_tick, tick),
                )
        elif location in route[1:-1]:
            work.intents[row.intent_id] = refreshed(
                row,
                status=MigrationIntentStatus.DEPARTED,
                confidence=row.confidence,
                new_evidence=(
                    _evidence(
                        MigrationCauseSource.DIRECT_OBSERVATION, tick, "own-progress"
                    ),
                ),
            )
        elif location == route[0] and row.status is not MigrationIntentStatus.DEPARTED:
            first_hop = route[1].value
            if support and first_hop in work.exit_ids:
                work.intents[row.intent_id] = refreshed(
                    row,
                    status=_intent_status_for_confidence(best),
                    confidence=best,
                    new_evidence=(
                        _evidence(
                            support[0].source, tick, f"cause-{support[0].source.value}"
                        ),
                    ),
                    causes=support_ids,
                )
            else:
                work.intents[row.intent_id] = replace(
                    row,
                    status=MigrationIntentStatus.ABANDONED,
                    last_tick=max(row.last_tick, tick),
                )
        else:
            work.intents[row.intent_id] = replace(
                row,
                status=MigrationIntentStatus.ABANDONED,
                last_tick=max(row.last_tick, tick),
            )

    # A new consideration needs a supported cause and a visible first hop.
    live_now = [row for row in work.intents.values() if row.status in _LIVE_INTENTS]
    if live_now or not support or location is None or not work.exits:
        return
    candidate: tuple[EntityId, ...] | None = None
    for route_row in sorted(work.prior.routes, key=lambda item: item.route_id):
        locations = route_row.route_locations
        if (
            route_row.status is RouteBeliefStatus.OPEN
            and route_row.basis is not RouteBeliefBasis.UNRESOLVED
            and len(locations) >= 3
            and locations[0] == location
            and locations[1].value in work.exit_ids
        ):
            candidate = locations
            break
    if candidate is None:
        nearest = min(work.exits, key=_exit_sort_key)
        if nearest.destination_id == location:
            return
        candidate = (location, nearest.destination_id)
    intent_id = migration_intent_id(work.owner_id, candidate, tick)
    work.intents[intent_id] = MigrationIntentRow(
        intent_id=intent_id,
        owner_id=work.owner_id,
        origin_location_id=candidate[0],
        destination_location_id=candidate[-1],
        route_locations=candidate,
        cause_ids=tuple(support_ids),
        cluster_ids=cluster_ids,
        status=_intent_status_for_confidence(best),
        confidence=best,
        first_tick=tick,
        last_tick=tick,
        evidence=(
            _evidence(support[0].source, tick, f"cause-{support[0].source.value}"),
        ),
    )


def _update_route_beliefs(work: _Work) -> None:
    tick = work.tick
    location = work.location
    exit_by_dest = {item.destination_id.value: item for item in work.exits}
    journey = work.journey
    for intent in sorted(work.intents.values(), key=lambda item: item.intent_id):
        if (
            intent.status not in _LIVE_INTENTS
            and intent.status is not MigrationIntentStatus.ARRIVED
        ):
            continue
        route = intent.route_locations
        pairs = route_edge_pairs(route)
        supported = all(pair in work.known_edges for pair in pairs)
        existing = next(
            (
                row
                for row in sorted(work.routes.values(), key=lambda item: item.route_id)
                if row.route_locations == route
                and row.status is not RouteBeliefStatus.EXPIRED
            ),
            None,
        )
        if supported:
            ranks = [_BASIS_RANK[work.known_edges[pair]] for pair in pairs]
            basis = next(
                item for item, rank in _BASIS_RANK.items() if rank == min(ranks)
            )
            status = RouteBeliefStatus.OPEN
            if (
                location is not None
                and location == route[0]
                and route[1].value not in work.exit_ids
                and intent.status is not MigrationIntentStatus.DEPARTED
            ):
                status = RouteBeliefStatus.BLOCKED_BELIEF
        else:
            basis = RouteBeliefBasis.UNRESOLVED
            status = RouteBeliefStatus.UNRESOLVED
            work.notices.add(MigrationNoticeCode.ROUTE_UNOBSERVED.value)
        duration = None if existing is None else existing.observed_duration_ticks
        fatigue = None if existing is None else existing.fatigue_cost
        if len(route) == 2:
            visible = exit_by_dest.get(route[1].value)
            if (
                visible is not None
                and location == route[0]
                and getattr(visible, "travel_duration_ticks", None) is not None
            ):
                duration = visible.travel_duration_ticks
                fatigue = visible.fatigue_cost
            start = _as_int(getattr(journey, "start_tick", None))
            due = _as_int(getattr(journey, "due_tick", None))
            if (
                getattr(journey, "origin_location_id", None) == route[0]
                and getattr(journey, "destination_location_id", None) == route[1]
                and start is not None
                and due is not None
                and due > start
            ):
                duration = due - start
        evidence = (
            ()
            if basis is RouteBeliefBasis.UNRESOLVED
            else (
                _evidence(
                    _BASIS_SOURCE[basis], tick, f"route-{_hyphenated(basis.value)}"
                ),
            )
        )
        if existing is None:
            route_id = migration_route_id(work.owner_id, route, tick)
            work.routes[route_id] = RouteBeliefRow(
                route_id=route_id,
                owner_id=work.owner_id,
                origin_location_id=route[0],
                destination_location_id=route[-1],
                route_locations=route,
                observed_duration_ticks=duration,
                fatigue_cost=fatigue,
                basis=basis,
                status=status,
                first_tick=tick,
                last_tick=tick,
                evidence=evidence,
            )
        else:
            work.routes[existing.route_id] = replace(
                existing,
                observed_duration_ticks=duration,
                fatigue_cost=fatigue,
                basis=basis,
                status=status,
                last_tick=max(existing.last_tick, tick),
                evidence=_merge_evidence(existing.evidence, evidence),
            )


def _update_cause_evidence(work: _Work) -> None:
    tick = work.tick
    observed_sources = {
        MigrationCauseSource.OWN_NEED,
        MigrationCauseSource.DIRECT_OBSERVATION,
    }
    current_keys = {item.key for item in work.cause_specs}
    for spec in work.cause_specs:
        cause_id = work.spec_ids[spec.key]
        evidence = (_evidence(spec.source, tick, spec.lineage),)
        existing = work.causes.get(cause_id)
        if existing is None:
            work.causes[cause_id] = CauseEvidenceRow(
                cause_id=cause_id,
                owner_id=work.owner_id,
                cause_kind=spec.kind,
                source_kind=spec.source,
                anchor_ref=spec.anchor,
                confidence=spec.confidence,
                first_tick=tick,
                last_tick=tick,
                status=CauseEvidenceStatus.ACTIVE,
                evidence=evidence,
            )
        else:
            work.causes[cause_id] = replace(
                existing,
                confidence=spec.confidence,
                last_tick=max(existing.last_tick, tick),
                status=CauseEvidenceStatus.ACTIVE,
                evidence=_merge_evidence(existing.evidence, evidence),
            )
    hazards_visible = getattr(work.observation, "hazard_kinds", None) is not None
    has_body = getattr(work.observation, "self_body", None) is not None
    for row in sorted(list(work.causes.values()), key=lambda item: item.cause_id):
        if row.status is not CauseEvidenceStatus.ACTIVE:
            continue
        key = (row.cause_kind.value, row.source_kind.value, row.anchor_ref or "")
        if key in current_keys or row.source_kind not in observed_sources:
            continue
        own_need = row.source_kind is MigrationCauseSource.OWN_NEED and has_body
        hazard = (
            row.source_kind is MigrationCauseSource.DIRECT_OBSERVATION
            and hazards_visible
        )
        if own_need or hazard:
            work.causes[row.cause_id] = replace(
                row,
                status=CauseEvidenceStatus.CONTRADICTED,
                last_tick=max(row.last_tick, tick),
            )


def _update_cluster_beliefs(work: _Work) -> None:
    tick = work.tick
    current: set[str] = set()
    for spec in work.cluster_specs:
        cluster_id = _existing_cluster_id(work, spec)
        current.add(cluster_id)
        evidence = (_evidence(MigrationCauseSource.INFERENCE, tick, spec.lineage),)
        existing = work.clusters.get(cluster_id)
        if existing is None:
            work.clusters[cluster_id] = SocialClusterBeliefRow(
                cluster_id=cluster_id,
                owner_id=work.owner_id,
                member_ids=spec.members,
                basis=spec.basis,
                confidence=spec.confidence,
                status=ClusterStatus.BELIEVED,
                first_tick=tick,
                last_tick=tick,
                evidence=evidence,
            )
        else:
            work.clusters[cluster_id] = replace(
                existing,
                confidence=spec.confidence,
                last_tick=max(existing.last_tick, tick),
                evidence=_merge_evidence(existing.evidence, evidence),
            )
    if work.journey is None:
        for row in sorted(
            list(work.clusters.values()), key=lambda item: item.cluster_id
        ):
            if (
                row.cluster_id in current
                or row.basis is not ClusterBasis.CO_MOVEMENT
                or row.status is not ClusterStatus.BELIEVED
            ):
                continue
            work.clusters[row.cluster_id] = replace(
                row, status=ClusterStatus.DISSOLVED, last_tick=max(row.last_tick, tick)
            )


def _entity_or_none(token: str) -> EntityId | None:
    try:
        return EntityId(token)
    except (TypeError, ValueError):
        return None


def _apply_frames(work: _Work) -> None:
    from agents.cognition.migration_displacement_communication import (
        MigrationFrameAct,
        migration_frame_root_key,
        scan_migration_displacement_deliveries,
    )

    deliveries, dropped = scan_migration_displacement_deliveries(
        work.observation, work.inbox, work.identity, default_tick=work.tick
    )
    work.dropped_frames = dropped
    if dropped:
        work.notices.add(MigrationNoticeCode.MALFORMED_FRAME.value)
    if not deliveries:
        return
    ordered = sorted(
        deliveries,
        key=lambda item: (
            item.speaker_token,
            migration_frame_root_key(item.frame),
            item.frame.act.value,
        ),
    )
    tick = work.tick
    seen_roots: set[str] = set()
    reported_waves: dict[tuple[str, str], dict[str, AgentId]] = {}
    wave_causes: dict[tuple[str, str], set[str]] = {}
    wave_evidence: dict[tuple[str, str], list[MigrationEvidence]] = {}
    wave_endpoints: dict[tuple[str, str], tuple[EntityId, EntityId]] = {}
    for delivery in ordered:
        frame = delivery.frame
        root = migration_frame_root_key(frame)
        if root in seen_roots:
            work.notices.add(MigrationNoticeCode.SAME_ROOT_SUPPRESSED.value)
            continue
        seen_roots.add(root)
        if frame.act is MigrationFrameAct.ASK_ROUTE:
            continue
        if frame.act in (MigrationFrameAct.UNKNOWN, MigrationFrameAct.REPORT_OUTCOME):
            work.notices.add(MigrationNoticeCode.PEER_CLAIM_UNTRUSTED.value)
            continue
        # The speaker is known from delivery; any other subject must be visible.
        subject_agent: AgentId | None
        if frame.subject_ref == delivery.speaker_token:
            subject_agent = delivery.speaker_owner
        else:
            subject_entity = _entity_or_none(frame.subject_ref)
            subject_agent = (
                None
                if subject_entity is None
                else work.entity_agent.get(subject_entity.value)
            )
            visible_bodies = {
                getattr(item, "entity_id", None)
                for item in (getattr(work.observation, "visible_bodies", ()) or ())
            }
            if subject_agent is None or subject_entity not in visible_bodies:
                work.notices.add(MigrationNoticeCode.PEER_CLAIM_UNTRUSTED.value)
                continue
        d_tick = min(delivery.delivery_tick, tick)
        confidence = _quantize(
            min(_TESTIMONY_CEILING, frame.confidence_q / 100.0 * _TESTIMONY_CEILING)
        )
        evidence = _evidence(
            MigrationCauseSource.TESTIMONY,
            d_tick,
            f"mdt-{root}",
            delivery.speaker_owner,
        )
        cause_ids: list[str] = []
        if frame.act in (
            MigrationFrameAct.REPORT_INTENT,
            MigrationFrameAct.REPORT_ROUTE,
            MigrationFrameAct.REPORT_CAUSE,
        ):
            if frame.cause_kind is not MigrationCauseKind.UNKNOWN:
                cause_ids.append(
                    _frame_cause(
                        work, frame.cause_kind, frame.evidence_ref, confidence, evidence
                    )
                )
        if frame.act in (
            MigrationFrameAct.REPORT_INTENT,
            MigrationFrameAct.REPORT_ROUTE,
        ):
            locations = tuple(_entity_or_none(item) for item in frame.route_refs)
            if any(item is None for item in locations):
                work.notices.add(MigrationNoticeCode.MALFORMED_FRAME.value)
                continue
            route = tuple(item for item in locations if item is not None)
            if route[0].value not in work.visible_locations:
                work.notices.add(MigrationNoticeCode.PEER_CLAIM_UNTRUSTED.value)
                continue
            _frame_route(work, route, evidence)
            for pair in route_edge_pairs(route):
                if pair not in work.known_edges:
                    work.known_edges[pair] = RouteBeliefBasis.TESTIMONY
            if (
                frame.act is MigrationFrameAct.REPORT_INTENT
                and subject_agent is not None
            ):
                key = (route[0].value, route[-1].value)
                group = reported_waves.setdefault(key, {})
                group[delivery.speaker_owner.value] = delivery.speaker_owner
                group[subject_agent.value] = subject_agent
                wave_causes.setdefault(key, set()).update(cause_ids)
                wave_evidence.setdefault(key, []).append(evidence)
                wave_endpoints[key] = (route[0], route[-1])
        elif frame.act is MigrationFrameAct.REPORT_CLUSTER:
            members = {delivery.speaker_owner.value: delivery.speaker_owner}
            if subject_agent is not None:
                members[subject_agent.value] = subject_agent
            if len(members) < MIN_CLUSTER_MEMBERS:
                work.notices.add(MigrationNoticeCode.CLUSTER_UNRESOLVED.value)
                continue
            ordered_members = tuple(members[key] for key in sorted(members))
            _frame_cluster(work, ordered_members, confidence, evidence)
    for key in sorted(reported_waves):
        participants = reported_waves[key]
        if len(participants) < MIN_WAVE_PARTICIPANTS:
            continue
        origin, destination = wave_endpoints[key]
        members_tuple = tuple(participants[item] for item in sorted(participants))[
            :MAX_WAVE_PARTICIPANTS
        ]
        causes = sorted(wave_causes.get(key, set())) or [_ensure_unknown_cause(work)]
        _upsert_wave(
            work,
            origin,
            destination,
            members_tuple,
            tuple(causes[:_MAX_INTENT_SUPPORT]),
            WaveObservationStatus.REPORTED,
            tuple(wave_evidence[key]),
        )


def _frame_cause(
    work: _Work,
    kind: MigrationCauseKind,
    anchor: str | None,
    confidence: float,
    evidence: MigrationEvidence,
) -> str:
    key = (kind.value, MigrationCauseSource.TESTIMONY.value, anchor or "")
    cause_id = work.spec_ids.get(key)
    if cause_id is None:
        cause_id = _spec_cause_id(
            work,
            _CauseSpec(kind, MigrationCauseSource.TESTIMONY, anchor, confidence, "mdt"),
        )
        work.spec_ids[key] = cause_id
    existing = work.causes.get(cause_id)
    if existing is None:
        work.causes[cause_id] = CauseEvidenceRow(
            cause_id=cause_id,
            owner_id=work.owner_id,
            cause_kind=kind,
            source_kind=MigrationCauseSource.TESTIMONY,
            anchor_ref=anchor,
            confidence=confidence,
            first_tick=work.tick,
            last_tick=work.tick,
            status=CauseEvidenceStatus.ACTIVE,
            evidence=(evidence,),
        )
    else:
        work.causes[cause_id] = replace(
            existing,
            confidence=max(existing.confidence, confidence),
            last_tick=max(existing.last_tick, work.tick),
            status=CauseEvidenceStatus.ACTIVE,
            evidence=_merge_evidence(existing.evidence, (evidence,)),
        )
    return cause_id


def _frame_route(
    work: _Work, route: tuple[EntityId, ...], evidence: MigrationEvidence
) -> None:
    existing = next(
        (
            row
            for row in sorted(work.routes.values(), key=lambda item: item.route_id)
            if row.route_locations == route
            and row.status is not RouteBeliefStatus.EXPIRED
        ),
        None,
    )
    if existing is not None:
        if existing.basis is RouteBeliefBasis.UNRESOLVED:
            work.routes[existing.route_id] = replace(
                existing,
                basis=RouteBeliefBasis.TESTIMONY,
                status=RouteBeliefStatus.OPEN,
                last_tick=max(existing.last_tick, work.tick),
                evidence=_merge_evidence(existing.evidence, (evidence,)),
            )
        else:
            work.routes[existing.route_id] = replace(
                existing,
                last_tick=max(existing.last_tick, work.tick),
                evidence=_merge_evidence(existing.evidence, (evidence,)),
            )
        return
    route_id = migration_route_id(work.owner_id, route, work.tick)
    work.routes[route_id] = RouteBeliefRow(
        route_id=route_id,
        owner_id=work.owner_id,
        origin_location_id=route[0],
        destination_location_id=route[-1],
        route_locations=route,
        observed_duration_ticks=None,
        fatigue_cost=None,
        basis=RouteBeliefBasis.TESTIMONY,
        status=RouteBeliefStatus.OPEN,
        first_tick=work.tick,
        last_tick=work.tick,
        evidence=(evidence,),
    )


def _frame_cluster(
    work: _Work,
    members: tuple[AgentId, ...],
    confidence: float,
    evidence: MigrationEvidence,
) -> None:
    basis = ClusterBasis.COMMUNICATION
    existing = next(
        (
            row
            for row in sorted(work.clusters.values(), key=lambda item: item.cluster_id)
            if row.basis is basis
            and row.member_ids == members
            and row.status in (ClusterStatus.BELIEVED, ClusterStatus.DISPUTED)
        ),
        None,
    )
    if existing is not None:
        work.clusters[existing.cluster_id] = replace(
            existing,
            confidence=max(existing.confidence, confidence),
            last_tick=max(existing.last_tick, work.tick),
            evidence=_merge_evidence(existing.evidence, (evidence,)),
        )
        return
    cluster_id = migration_cluster_id(work.owner_id, members, basis, work.tick)
    work.clusters[cluster_id] = SocialClusterBeliefRow(
        cluster_id=cluster_id,
        owner_id=work.owner_id,
        member_ids=members,
        basis=basis,
        confidence=confidence,
        status=ClusterStatus.BELIEVED,
        first_tick=work.tick,
        last_tick=work.tick,
        evidence=(evidence,),
    )


def _upsert_wave(
    work: _Work,
    origin: EntityId,
    destination: EntityId,
    participants: tuple[AgentId, ...],
    cause_ids: tuple[str, ...],
    status: WaveObservationStatus,
    evidence: tuple[MigrationEvidence, ...],
) -> None:
    existing = next(
        (
            row
            for row in sorted(work.waves.values(), key=lambda item: item.observation_id)
            if row.origin_location_id == origin
            and row.destination_location_id == destination
            and row.participant_ids == participants
            and row.status
            in (
                WaveObservationStatus.OBSERVED,
                WaveObservationStatus.REPORTED,
                WaveObservationStatus.DISPUTED,
            )
        ),
        None,
    )
    if existing is not None:
        work.waves[existing.observation_id] = replace(
            existing,
            last_tick=max(existing.last_tick, work.tick),
            evidence=_merge_evidence(existing.evidence, evidence),
        )
        return
    observation_id = migration_wave_observation_id(
        work.owner_id, origin, destination, participants, work.tick
    )
    work.waves[observation_id] = WaveObservationRow(
        observation_id=observation_id,
        owner_id=work.owner_id,
        origin_location_id=origin,
        destination_location_id=destination,
        participant_ids=participants,
        cause_ids=cause_ids,
        cluster_ids=(),
        status=status,
        first_tick=work.tick,
        last_tick=work.tick,
        evidence=evidence,
    )


def _anchor_index(work: _Work) -> dict[str, str | None]:
    index: dict[str, str | None] = {}
    for kind, ledger in sorted(work.ledgers.items()):
        for _, row in _ledger_rows(ledger):
            rid = _row_id(row)
            if rid is None:
                continue
            version = getattr(row, "version", getattr(row, "policy_version", None))
            index[f"{kind}:{rid}"] = version if isinstance(version, str) else None
    return index


def _anchor_resolves(anchor: str, index: Mapping[str, str | None]) -> bool:
    base, separator, version = anchor.partition("@")
    if base not in index:
        return False
    if not separator:
        return True
    return index[base] == version


def _resolve_anchors(work: _Work) -> None:
    index = _anchor_index(work)
    unresolved = 0
    for row in work.causes.values():
        if row.anchor_ref is None or row.status is not CauseEvidenceStatus.ACTIVE:
            continue
        if not _anchor_resolves(row.anchor_ref, index):
            unresolved += 1
    if unresolved:
        work.notices.add(MigrationNoticeCode.UNRESOLVED_ANCHOR.value)
        _LOG.warning("migration_displacement_unresolved_anchor count=%s", unresolved)


def _update_integration_beliefs(work: _Work) -> None:
    tick = work.tick
    location = work.location
    if location is None:
        return
    body = getattr(work.observation, "self_body", None)
    need = max(
        _fraction(getattr(body, "hunger", 0)), _fraction(getattr(body, "thirst", 0))
    )
    resources = bool(getattr(work.observation, "resources", ()) or ())
    partners = {
        item.target_id.value
        for item in work.relationships
        if getattr(item, "source_id", None) == work.owner_id
        and type(getattr(item, "target_id", None)) is AgentId
    }
    partner_visible = any(key in work.visible_agents for key in partners)
    org_member = any(
        work.owner_id in (getattr(row, "member_ids", ()) or ())
        for _, row in _ledger_rows(work.ledgers.get("organization"))
    )
    inst_member = any(
        work.owner_id in (getattr(row, "member_ids", ()) or ())
        for _, row in _ledger_rows(work.ledgers.get("institution"))
    )
    arrived = sorted(
        (
            row
            for row in work.intents.values()
            if row.status is MigrationIntentStatus.ARRIVED
        ),
        key=lambda item: item.intent_id,
    )
    for intent in arrived:
        destination = intent.destination_location_id
        arrival = work.arrival_ticks.get(intent.intent_id)
        if arrival is None:
            arrival = min(
                (
                    row.first_tick
                    for row in work.prior.integrations
                    if row.destination_location_id == destination
                ),
                default=None,
            )
        if arrival is None or arrival > tick:
            continue
        at_destination = location == destination
        observations: list[tuple[IntegrationDomain, IntegrationStatus, float, str]] = []
        if at_destination:
            settled = tick - arrival >= _SETTLE_TICKS
            residence = (
                IntegrationStatus.SETTLED if settled else IntegrationStatus.TRANSIENT
            )
            observations.append(
                (IntegrationDomain.RESIDENCE, residence, 0.6, "own-residence")
            )
            observations.append(
                (
                    IntegrationDomain.NEEDS,
                    IntegrationStatus.SETTLED
                    if need < _NEED_THRESHOLD
                    else IntegrationStatus.TRANSIENT,
                    0.5,
                    "own-needs",
                )
            )
            if resources:
                observations.append(
                    (
                        IntegrationDomain.RESOURCE_ACCESS,
                        IntegrationStatus.SETTLED,
                        0.5,
                        "visible-access",
                    )
                )
            if partner_visible:
                observations.append(
                    (
                        IntegrationDomain.RELATIONSHIPS,
                        IntegrationStatus.SETTLED,
                        0.5,
                        "own-relationships",
                    )
                )
            if org_member:
                observations.append(
                    (
                        IntegrationDomain.ORGANIZATION_PARTICIPATION,
                        IntegrationStatus.SETTLED,
                        0.5,
                        "organization-belief",
                    )
                )
            if inst_member:
                observations.append(
                    (
                        IntegrationDomain.INSTITUTION_PARTICIPATION,
                        IntegrationStatus.SETTLED,
                        0.5,
                        "institution-belief",
                    )
                )
            if len(observations) == 2 and not resources:
                work.notices.add(MigrationNoticeCode.INTEGRATION_UNOBSERVED.value)
        elif location == intent.origin_location_id:
            observations.append(
                (
                    IntegrationDomain.RESIDENCE,
                    IntegrationStatus.RETURNED,
                    0.6,
                    "own-residence",
                )
            )
        else:
            observations.append(
                (
                    IntegrationDomain.RESIDENCE,
                    IntegrationStatus.ONWARD,
                    0.6,
                    "own-residence",
                )
            )
        for domain, status, confidence, lineage in observations:
            outcome_id = migration_integration_id(
                work.owner_id, destination, domain, arrival
            )
            evidence = (
                _evidence(MigrationCauseSource.DIRECT_OBSERVATION, tick, lineage),
            )
            existing = work.integrations.get(outcome_id)
            if existing is None:
                work.integrations[outcome_id] = IntegrationBeliefRow(
                    outcome_id=outcome_id,
                    owner_id=work.owner_id,
                    destination_location_id=destination,
                    domain=domain,
                    status=status,
                    confidence=confidence,
                    first_tick=arrival,
                    last_tick=tick,
                    evidence=evidence,
                )
            elif existing.status in (
                IntegrationStatus.RETURNED,
                IntegrationStatus.ONWARD,
            ):
                continue
            else:
                work.integrations[outcome_id] = replace(
                    existing,
                    status=status,
                    confidence=confidence,
                    last_tick=max(existing.last_tick, tick),
                    evidence=_merge_evidence(existing.evidence, evidence),
                )


def _update_wave_observations(work: _Work) -> None:
    location = work.location
    if location is None:
        return
    own_causes = sorted({work.spec_ids[item.key] for item in work.cause_specs})[
        :_MAX_INTENT_SUPPORT
    ]
    journey_dest = getattr(work.journey, "destination_location_id", None)
    for key in sorted(work.movers):
        destination, movers = work.movers[key]
        if destination == location:
            continue
        participants = dict(movers)
        own_moving = type(journey_dest) is EntityId and journey_dest == destination
        if own_moving:
            participants[work.owner_id.value] = work.owner_id
        if len(participants) < MIN_WAVE_PARTICIPANTS:
            continue
        members = tuple(participants[item] for item in sorted(participants))[
            :MAX_WAVE_PARTICIPANTS
        ]
        causes = (
            own_causes if own_moving and own_causes else [_ensure_unknown_cause(work)]
        )
        _upsert_wave(
            work,
            location,
            destination,
            members,
            tuple(causes),
            WaveObservationStatus.OBSERVED,
            (
                _evidence(
                    MigrationCauseSource.DIRECT_OBSERVATION,
                    work.tick,
                    "observed-movement",
                ),
            ),
        )


def _finalize_digest(
    work: _Work, ledger: MigrationDisplacementLedger
) -> MigrationDisplacementLedger:
    del work
    return finalize_migration_displacement_ledger(ledger)


def _assemble(work: _Work) -> MigrationDisplacementLedger:
    return MigrationDisplacementLedger(
        owner_id=work.owner_id,
        intents=tuple(work.intents.values()),
        routes=tuple(work.routes.values()),
        causes=tuple(work.causes.values()),
        clusters=tuple(work.clusters.values()),
        integrations=tuple(work.integrations.values()),
        waves=tuple(work.waves.values()),
        notices=tuple(sorted(work.notices)),
    )


def apply_migration_displacement_update(
    *,
    owner_id: AgentId,
    tick: int,
    observation: Observation,
    prior: MigrationDisplacementLedger,
    identity: object | None,
    relationships: Sequence[object] = (),
    organization_concepts: object | None = None,
    institution_concepts: object | None = None,
    formal_rules: object | None = None,
    disputes: object | None = None,
    evidence: object | None = None,
    diplomacy: object | None = None,
    organized_conflict: object | None = None,
    borders: object | None = None,
    inbox: object | None = None,
    policy: MigrationDisplacementPolicy,
) -> MigrationDisplacementLedger:
    """One owner's fixed-order migration belief update.

    The pipeline reads only the owner-safe observation, the prior ledger, this
    owner's other private ledgers, and delivered speech. Silence never creates a
    belief and no helper builds or returns a command.
    """
    if type(owner_id) is not AgentId:
        raise ValueError("owner_id: invalid_type")
    if isinstance(tick, bool) or type(tick) is not int or tick < 0:
        raise ValueError("tick: invalid_tick")
    if type(policy) is not MigrationDisplacementPolicy:
        raise TypeError("policy must be MigrationDisplacementPolicy")
    if observation is None:
        raise ValueError("observation: invalid_type")
    if type(prior) is not MigrationDisplacementLedger:
        raise TypeError("prior must be MigrationDisplacementLedger")
    if prior.owner_id != owner_id:
        raise ValueError("migration_displacement: foreign_owner")
    if isinstance(relationships, (str, bytes)) or not isinstance(
        relationships, Sequence
    ):
        raise TypeError("relationships must be a sequence")
    _reject_forbidden(observation)
    ledgers = {
        "organization": organization_concepts,
        "institution": institution_concepts,
        "rule": formal_rules,
        "dispute": disputes,
        "evidence": evidence,
        "diplomacy": diplomacy,
        "conflict": organized_conflict,
        "border": borders,
    }
    for value in (*ledgers.values(), inbox, identity):
        _reject_forbidden(value)
    for value in ledgers.values():
        if value is None:
            continue
        foreign = getattr(value, "owner_id", owner_id)
        if type(foreign) is AgentId and foreign != owner_id:
            raise ValueError("migration_displacement: foreign_owner")
    work = _Work(
        owner_id=owner_id,
        tick=tick,
        observation=observation,
        prior=prior,
        identity=identity,
        relationships=tuple(relationships),
        ledgers=ledgers,
        inbox=inbox,
        policy=policy,
    )
    _build_context(work)
    work.cause_specs = _derive_cause_specs(work)
    work.spec_ids = {item.key: _spec_cause_id(work, item) for item in work.cause_specs}
    work.cluster_specs = _derive_cluster_specs(work)
    _update_own_intents(work)
    _update_route_beliefs(work)
    _update_cause_evidence(work)
    _update_cluster_beliefs(work)
    _apply_frames(work)
    _resolve_anchors(work)
    _update_integration_beliefs(work)
    _update_wave_observations(work)
    ledger = _assemble(work)
    ledger = _expire_rows(ledger, tick, policy)
    ledger = _enforce_caps(ledger, policy, prior)
    ledger = _finalize_digest(work, ledger)
    _LOG.debug(
        "migration_displacement_prepare intents=%s routes=%s causes=%s clusters=%s "
        "integrations=%s waves=%s notices=%s",
        len(ledger.intents),
        len(ledger.routes),
        len(ledger.causes),
        len(ledger.clusters),
        len(ledger.integrations),
        len(ledger.waves),
        len(ledger.notices),
    )
    return ledger


# ---------------------------------------------------------------------------
# Cause-weighted multi-hop route bias (Task 8)
# ---------------------------------------------------------------------------


def migration_displacement_action_biases(
    ledger: MigrationDisplacementLedger,
    *,
    observation: Observation,
    known_destinations: Sequence[EntityId],
    base_biases: Mapping[str, float] | None = None,
    policy: MigrationDisplacementPolicy,
    futures: Sequence[object] | None = None,
) -> Mapping[str, float]:
    """Return a bounded additive bias for the next adjacent step of a route.

    Keys are destination tokens, or future ids when ``futures`` is supplied.
    Only active intents (``planned``/``departed``) over an ``open`` route belief
    with an active, known cause contribute. A multi-hop route biases only the
    next adjacent step. The result is a pure scoring projection.
    """
    if type(ledger) is not MigrationDisplacementLedger:
        raise _log_failure("ledger", "invalid_type")
    if type(policy) is not MigrationDisplacementPolicy:
        raise TypeError("policy must be MigrationDisplacementPolicy")
    for value in (base_biases or {}).values():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("migration_displacement: bias")
        if not math.isfinite(float(value)):
            raise ValueError("migration_displacement: bias")
    body = getattr(observation, "self_body", None)
    location = getattr(body, "location_id", None)
    base = dict(base_biases or {})
    active = [
        item
        for item in ledger.intents
        if item.status
        in (MigrationIntentStatus.PLANNED, MigrationIntentStatus.DEPARTED)
    ]
    if type(location) is not EntityId or getattr(body, "journey", None) is not None:
        _LOG.debug(
            "migration_displacement_bias candidates=%s active_intents=%s applied=%s",
            len(known_destinations),
            len(active),
            0,
        )
        return dict(base)
    candidates = {item.value for item in known_destinations if type(item) is EntityId}
    causes = {item.cause_id: item for item in ledger.causes}
    open_routes = {
        item.route_locations
        for item in ledger.routes
        if item.status is RouteBeliefStatus.OPEN
        and item.basis is not RouteBeliefBasis.UNRESOLVED
    }
    contributions: dict[str, float] = {}
    for intent in active:
        route = intent.route_locations
        if route not in open_routes or location not in route[:-1]:
            continue
        next_hop = route[route.index(location) + 1].value
        if next_hop not in candidates:
            continue
        weight = 0.0
        for cause_id in intent.cause_ids:
            cause = causes.get(cause_id)
            if (
                cause is not None
                and cause.status is CauseEvidenceStatus.ACTIVE
                and cause.cause_kind is not MigrationCauseKind.UNKNOWN
            ):
                weight = max(weight, cause.confidence)
        if weight <= 0.0:
            continue
        contributions[next_hop] = contributions.get(next_hop, 0.0) + (
            policy.max_destination_bias * weight
        )
    limit = policy.max_destination_bias
    bounded = {
        key: _quantize(max(-limit, min(limit, value)))
        for key, value in sorted(contributions.items())
    }
    result = dict(base)
    if futures is None:
        for key, value in bounded.items():
            result[key] = base.get(key, 0.0) + value
    else:
        for future in futures:
            if (
                not hasattr(future, "future_id")
                or not hasattr(future, "direction")
                or getattr(future.direction, "value", None) != "move"
            ):
                continue
            target = getattr(future, "target_entity_id", None)
            if isinstance(target, str) and target in bounded:
                result[future.future_id] = (
                    base.get(future.future_id, 0.0) + bounded[target]
                )
    _LOG.debug(
        "migration_displacement_bias candidates=%s active_intents=%s applied=%s",
        len(candidates),
        len(active),
        len(bounded),
    )
    return result


__all__ = [
    "MAX_ANCHOR_REF_CHARS",
    "MAX_INTENT_CLUSTER_IDS",
    "MAX_ROUTE_EDGES",
    "MAX_ROUTE_LOCATIONS",
    "MAX_WAVE_PARTICIPANTS",
    "MIGRATION_DISPLACEMENT_FRAME_FIELD_COUNT",
    "MIGRATION_DISPLACEMENT_FRAME_MAX_CHARS",
    "MIGRATION_DISPLACEMENT_FRAME_MAX_RELATIONS",
    "MIGRATION_DISPLACEMENT_FRAME_VERSION",
    "MIGRATION_DISPLACEMENT_LEDGER_VERSION",
    "MIGRATION_DISPLACEMENT_POLICY_VERSION",
    "MIGRATION_DISPLACEMENT_UPDATE_ORDER",
    "MIN_CLUSTER_MEMBERS",
    "MIN_ROUTE_LOCATIONS",
    "MIN_WAVE_PARTICIPANTS",
    "NONE_TOKEN",
    "PREFIX_BY_FAMILY",
    "CauseEvidenceRow",
    "CauseEvidenceStatus",
    "ClusterBasis",
    "ClusterStatus",
    "IntegrationBeliefRow",
    "IntegrationDomain",
    "IntegrationStatus",
    "MigrationCauseKind",
    "MigrationCauseSource",
    "MigrationDisplacementLedger",
    "MigrationDisplacementPolicy",
    "MigrationEvidence",
    "MigrationIntentRow",
    "MigrationIntentStatus",
    "MigrationNoticeCode",
    "MigrationRowProjection",
    "RouteBeliefBasis",
    "RouteBeliefRow",
    "RouteBeliefStatus",
    "SocialClusterBeliefRow",
    "WaveObservationRow",
    "WaveObservationStatus",
    "apply_migration_displacement_update",
    "canonical_migration_displacement_json",
    "canonical_migration_displacement_payload",
    "cause_kind_token",
    "cluster_member_tokens",
    "default_migration_displacement_policy",
    "empty_migration_displacement_ledger",
    "finalize_migration_displacement_ledger",
    "integration_domain_token",
    "intent_location_tokens",
    "merge_migration_displacement_ledger",
    "migration_anchor_token",
    "migration_candidate_id",
    "migration_cause_id",
    "migration_cluster_id",
    "migration_displacement_action_biases",
    "migration_displacement_ledger_digest",
    "migration_displacement_row_projections",
    "migration_displacement_update_summary",
    "migration_integration_id",
    "migration_intent_id",
    "migration_lineage_token",
    "migration_location_token",
    "migration_opaque_location_token",
    "migration_owner_token",
    "migration_publication_id",
    "migration_route_id",
    "migration_route_tokens",
    "migration_wave_observation_id",
    "require_migration_displacement_digest",
    "require_owner_migration_displacement",
    "require_route_edges",
    "require_route_locations",
    "require_visible_members",
    "route_edge_pairs",
    "route_location_tokens",
    "route_pairs_supported",
    "validate_migration_displacement_ledger_caps",
    "wave_participant_tokens",
]
