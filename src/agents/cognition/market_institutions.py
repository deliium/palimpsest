"""Closed owner-scoped market-like institution vocabulary.

A market-like institution is one owner's belief about repeated exchange at a
logical location: observed venue activity, an expectation that meetings recur,
optional schedules, broker-like role claims, and opaque exchange-record anchors.
It is never a global Market object, never an authoritative price, and never a
money, credit, debt, allocation, or enforcement mechanism.

This module owns the frozen contract, identity grammar, policy bounds, caps, and
the owner-scoped ledger. Every physical effect remains an ordinary agent command
admitted by ``WorldEngine``.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Final, NoReturn

from agents.models import AgentId
from world.identifiers import EntityId

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.market_institutions")

MARKET_INSTITUTIONS_POLICY_VERSION: Final[str] = "market-institutions.v1"
MARKET_BELIEF_PREFIX: Final[str] = "mktb-"
MARKET_BELIEF_HEX_LEN: Final[int] = 16
MARKET_LABEL_MAX_LEN: Final[int] = 32
MARKET_LABEL_PATTERN: Final[str] = r"^[a-z0-9][a-z0-9_-]*$"
MARKET_ANCHOR_MAX_LEN: Final[int] = 64
MARKET_ANCHOR_PATTERN: Final[str] = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$"
MARKET_OFFICE_REF_PATTERN: Final[str] = rf"^[0-9a-f]{{{MARKET_BELIEF_HEX_LEN}}}$"
MARKET_ORGANIZATION_REF_PATTERN: Final[str] = (
    rf"^orgc-[0-9a-f]{{{MARKET_BELIEF_HEX_LEN}}}$"
)
MARKET_WINDOW_TICKS: Final[int] = 32
MARKET_MAX_WINDOWS: Final[int] = 512

_LABEL_RE: Final[re.Pattern[str]] = re.compile(MARKET_LABEL_PATTERN)
_ANCHOR_RE: Final[re.Pattern[str]] = re.compile(MARKET_ANCHOR_PATTERN)
_OFFICE_REF_RE: Final[re.Pattern[str]] = re.compile(MARKET_OFFICE_REF_PATTERN)
_ORGANIZATION_REF_RE: Final[re.Pattern[str]] = re.compile(
    MARKET_ORGANIZATION_REF_PATTERN
)
_DIGEST_RE: Final[re.Pattern[str]] = re.compile(
    rf"^[0-9a-f]{{{MARKET_BELIEF_HEX_LEN}}}$"
)

MARKET_NOTICE_CODES: Final[frozenset[str]] = frozenset(
    {
        "market_venue_stale",
        "market_ledger_truncated",
        "market_role_unresolved",
        "market_venue_unresolved",
    }
)

MARKET_FORBIDDEN_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "price",
        "rate",
        "money",
        "currency",
        "numeraire",
        "clearing_price",
        "bid",
        "ask",
        "spread",
        "fee",
        "commission",
        "tax",
        "debt",
        "credit_limit",
        "market_score",
        "ranking",
        "severity",
        "recommendation",
        "allocation",
        "quota",
        "central_planner",
    }
)


class MarketExpectation(StrEnum):
    """Closed owner expectation that exchange meetings recur at a venue."""

    NONE = "none"
    WEAK = "weak"
    EXPECTED = "expected"
    STRONG = "strong"


class MarketCadence(StrEnum):
    """Closed social cadence belief; never a world timer or calendar."""

    SINGLE_OCCURRENCE = "single_occurrence"
    RECURRING_INTERVAL = "recurring_interval"
    PERIODIC_WINDOW = "periodic_window"
    UNKNOWN = "unknown"


class MarketVenueStatus(StrEnum):
    """Closed owner-local venue lifecycle status (no score or ranking)."""

    EMERGING = "emerging"
    EXPECTED = "expected"
    PERSISTENT = "persistent"
    DECLINING = "declining"
    DORMANT = "dormant"


class MarketRoleKind(StrEnum):
    """Closed broker-like role vocabulary; brokers never exist as actors."""

    BROKER = "broker"
    HOST = "host"
    ORGANIZER = "organizer"
    UNKNOWN = "unknown"


class MarketRoleBasis(StrEnum):
    """Closed basis for a role claim; recognition needs office/organization."""

    OBSERVED_PARTICIPATION = "observed_participation"
    CLAIMED = "claimed"
    OFFICE = "office"
    ORGANIZATION = "organization"


class MarketRecordKind(StrEnum):
    """Closed opaque exchange-record reference kinds."""

    EXCHANGE_RECORD = "exchange_record"
    ATTENDANCE_RECORD = "attendance_record"
    AGREEMENT_RECORD = "agreement_record"
    UNKNOWN = "unknown"


class MarketScheduleSource(StrEnum):
    """Closed provenance of a schedule belief; never objective truth."""

    OBSERVED = "observed"
    COMMUNICATED = "communicated"
    SELF_AUTHORED = "self_authored"


class MarketInstitutionError(ValueError):
    """Stable market-institution contract failure with a safe reason code."""

    @property
    def reason_code(self) -> str:
        return str(self.args[0]) if self.args else "market_institution_invalid"


def _fail(code: str) -> NoReturn:
    _LOG.error("market_institution_contract_invalid reason_code=%s", code)
    raise MarketInstitutionError(code)


def _reject_forbidden_fields(cls: type[object]) -> None:
    names = set(getattr(cls, "__dataclass_fields__", {}))
    if names & MARKET_FORBIDDEN_FIELD_NAMES:
        _fail("market_institution_forbidden_field")


def _require_owner_id(value: object) -> AgentId:
    if type(value) is not AgentId:
        _fail("market_institution_invalid_owner")
    return value


def _require_entity_id(value: object, code: str) -> EntityId:
    if type(value) is not EntityId:
        _fail(code)
    return value


def _require_tick(value: object) -> int:
    if type(value) is not int or value < 0:
        _fail("market_institution_invalid_tick")
    return value


def _require_count(value: object) -> int:
    if type(value) is not int or value < 0:
        _fail("market_institution_invalid_count")
    return value


def _require_span(first_tick: object, last_tick: object) -> tuple[int, int]:
    first = _require_tick(first_tick)
    last = _require_tick(last_tick)
    if last < first:
        _fail("market_institution_tick_regression")
    return first, last


def _require_enum(value: object, enum_type: type[StrEnum]) -> StrEnum:
    if type(value) is not enum_type:
        _fail("market_institution_invalid_enum")
    return value


def _require_label(value: object) -> str:
    if type(value) is not str or len(value) > MARKET_LABEL_MAX_LEN:
        _fail("market_institution_invalid_label")
    if _LABEL_RE.match(value) is None:
        _fail("market_institution_invalid_label")
    return value


def _require_anchor(value: object) -> str:
    if type(value) is not str or len(value) > MARKET_ANCHOR_MAX_LEN:
        _fail("market_institution_invalid_anchor")
    if _ANCHOR_RE.match(value) is None:
        _fail("market_institution_invalid_anchor")
    return value


def _require_office_ref(value: object) -> str:
    if type(value) is not str or _OFFICE_REF_RE.match(value) is None:
        _fail("market_institution_invalid_role_ref")
    return value


def _require_organization_ref(value: object) -> str:
    if type(value) is not str or _ORGANIZATION_REF_RE.match(value) is None:
        _fail("market_institution_invalid_role_ref")
    return value


def _require_belief_id(value: object) -> str:
    if (
        type(value) is not str
        or not value.startswith(MARKET_BELIEF_PREFIX)
        or _DIGEST_RE.match(value[len(MARKET_BELIEF_PREFIX) :]) is None
    ):
        _fail("market_institution_invalid_venue_id")
    return value


def _digest16(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:MARKET_BELIEF_HEX_LEN]


def market_venue_belief_id(
    *,
    owner_id: AgentId,
    location_id: EntityId,
    creation_tick: int,
) -> str:
    """Mint one deterministic owner-local ``mktb-`` venue belief id."""

    owner = _require_owner_id(owner_id)
    location = _require_entity_id(location_id, "market_institution_invalid_venue_id")
    tick = _require_tick(creation_tick)
    body = _digest16(
        f"{owner.value}\x1fmktb\x1f{location.value}\x1f{tick}"
    )
    return f"{MARKET_BELIEF_PREFIX}{body}"


def require_market_belief_id(value: object) -> str:
    """Require one exact ``mktb-`` belief id."""

    return _require_belief_id(value)


def market_venue_analysis_id(location_token: str) -> str:
    """Mint one deterministic analysis venue id from a location token."""

    if type(location_token) is not str or not location_token:
        _fail("market_institution_invalid_venue_id")
    return f"mkt-ven-{_digest16(f'palimpsest.market.venue.v1\x1f{location_token}')}"


def market_cluster_id(venue_ids: Sequence[str]) -> str:
    """Mint one deterministic market id from a sorted venue-id set."""

    if isinstance(venue_ids, (str, bytes)) or not isinstance(venue_ids, Sequence):
        _fail("market_institution_invalid_venue_id")
    values = tuple(sorted(set(venue_ids)))
    if not values:
        _fail("market_institution_invalid_venue_id")
    for value in values:
        _require_belief_id_or_analysis(value)
    return f"mktc-{_digest16('palimpsest.market.cluster.v1\x1f' + ','.join(values))}"


def _require_belief_id_or_analysis(value: object) -> str:
    if type(value) is not str:
        _fail("market_institution_invalid_venue_id")
    if value.startswith(MARKET_BELIEF_PREFIX):
        return _require_belief_id(value)
    if value.startswith("mkt-ven-") and _DIGEST_RE.match(value[8:]) is not None:
        return value
    _fail("market_institution_invalid_venue_id")


@dataclass(frozen=True, slots=True)
class MarketInstitutionPolicy:
    """Locked owner-local market institution bounds."""

    max_venues: int = 8
    max_observations_per_venue: int = 64
    max_schedules_per_venue: int = 4
    max_roles_per_venue: int = 8
    max_records_per_venue: int = 8
    max_counterparties_per_observation: int = 16
    max_notices: int = 8
    max_evidence_per_observation: int = 8
    decline_after_ticks: int = 64
    dormant_after_ticks: int = 128
    expected_min_observations: int = 2
    strong_min_observations: int = 2
    strong_min_confidence_milli: int = 500
    persistent_min_ticks: int = 3
    persistent_min_windows: int = 2

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        for name, expected in MARKET_INSTITUTION_LOCKED_POLICY.items():
            actual = getattr(self, name)
            if type(actual) is not int or actual != expected:
                _fail("market_institution_policy_mismatch")


MARKET_INSTITUTION_LOCKED_POLICY: Final[Mapping[str, int]] = MappingProxyType(
    {
        "max_venues": 8,
        "max_observations_per_venue": 64,
        "max_schedules_per_venue": 4,
        "max_roles_per_venue": 8,
        "max_records_per_venue": 8,
        "max_counterparties_per_observation": 16,
        "max_notices": 8,
        "max_evidence_per_observation": 8,
        "decline_after_ticks": 64,
        "dormant_after_ticks": 128,
        "expected_min_observations": 2,
        "strong_min_observations": 2,
        "strong_min_confidence_milli": 500,
        "persistent_min_ticks": 3,
        "persistent_min_windows": 2,
    }
)

_DEFAULT_POLICY: Final[MarketInstitutionPolicy] = MarketInstitutionPolicy()


def default_market_institution_policy() -> MarketInstitutionPolicy:
    """Return the single locked market institution policy instance."""

    return _DEFAULT_POLICY


@dataclass(frozen=True, slots=True)
class MarketVenueObservation:
    """One owner-observed exchange aggregate for a source tick."""

    tick: int
    source_tick: int
    counterparty_ids: tuple[EntityId, ...]
    exchange_count: int
    proposal_count: int
    withdrawn_count: int
    digest: str

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        tick = _require_tick(self.tick)
        source = _require_tick(self.source_tick)
        if source > tick:
            _fail("market_institution_invalid_evidence")
        exchange = _require_count(self.exchange_count)
        proposal = _require_count(self.proposal_count)
        withdrawn = _require_count(self.withdrawn_count)
        if not isinstance(self.counterparty_ids, (list, tuple)):
            _fail("market_institution_invalid_counterparty")
        parties = tuple(self.counterparty_ids)
        for party in parties:
            if type(party) is not EntityId:
                _fail("market_institution_invalid_counterparty")
        party_values = tuple(sorted({party.value for party in parties}))
        if len(party_values) != len(parties):
            _fail("market_institution_invalid_counterparty")
        if exchange > 0 and not party_values:
            _fail("market_institution_invalid_counterparty")
        if len(party_values) > _DEFAULT_POLICY.max_counterparties_per_observation:
            _fail("market_institution_cap_exceeded")
        if type(self.digest) is not str or _DIGEST_RE.match(self.digest) is None:
            _fail("market_institution_invalid_digest")
        object.__setattr__(
            self,
            "counterparty_ids",
            tuple(EntityId(value) for value in party_values),
        )
        object.__setattr__(self, "tick", tick)
        object.__setattr__(self, "source_tick", source)
        object.__setattr__(self, "exchange_count", exchange)
        object.__setattr__(self, "proposal_count", proposal)
        object.__setattr__(self, "withdrawn_count", withdrawn)


def market_observation_digest(
    *,
    venue_id: str,
    source_tick: int,
    counterparty_ids: Sequence[EntityId],
    exchange_count: int,
    proposal_count: int,
    withdrawn_count: int,
) -> str:
    """Return the deterministic observation identity digest."""

    parties = ",".join(
        sorted({party.value for party in counterparty_ids if type(party) is EntityId})
    )
    return _digest16(
        "market-observation\x1f"
        + venue_id
        + "\x1f"
        + str(source_tick)
        + "\x1f"
        + parties
        + "\x1f"
        + str(exchange_count)
        + "\x1f"
        + str(proposal_count)
        + "\x1f"
        + str(withdrawn_count)
    )


@dataclass(frozen=True, slots=True)
class MarketMeetingExpectation:
    """Bounded owner expectation derived only from own observations."""

    level: MarketExpectation
    evidence_count: int
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "level", _require_enum(self.level, MarketExpectation)
        )
        object.__setattr__(self, "evidence_count", _require_count(self.evidence_count))
        first, last = _require_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)


@dataclass(frozen=True, slots=True)
class MarketScheduleBelief:
    """One owner's social schedule belief; never a world timer."""

    cadence: MarketCadence
    interval_ticks: int | None
    phase_tick: int | None
    window_index: int | None
    confidence_milli: int
    source: MarketScheduleSource
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        cadence = _require_enum(self.cadence, MarketCadence)
        _require_enum(self.source, MarketScheduleSource)
        if (
            type(self.confidence_milli) is not int
            or not 0 <= self.confidence_milli <= 1000
        ):
            _fail("market_institution_invalid_confidence")
        first, last = _require_span(self.first_tick, self.last_tick)
        if cadence is MarketCadence.RECURRING_INTERVAL:
            if (
                type(self.interval_ticks) is not int
                or not 1 <= self.interval_ticks <= 512
            ):
                _fail("market_institution_invalid_schedule")
            if type(self.phase_tick) is not int or not 0 <= self.phase_tick <= 511:
                _fail("market_institution_invalid_schedule")
            if self.window_index is not None:
                _fail("market_institution_invalid_schedule")
        elif cadence is MarketCadence.PERIODIC_WINDOW:
            if type(self.window_index) is not int or not 0 <= self.window_index <= 511:
                _fail("market_institution_invalid_schedule")
            if self.interval_ticks is not None or self.phase_tick is not None:
                _fail("market_institution_invalid_schedule")
        else:
            if (
                self.interval_ticks is not None
                or self.phase_tick is not None
                or self.window_index is not None
            ):
                _fail("market_institution_invalid_schedule")
        object.__setattr__(self, "cadence", cadence)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)


def market_schedule_is_active(schedule: object, tick: object) -> bool:
    """Return whether a schedule belief predicts activity at ``tick``."""

    if type(schedule) is not MarketScheduleBelief:
        raise TypeError("schedule must be MarketScheduleBelief")
    current = _require_tick(tick)
    if schedule.cadence is MarketCadence.RECURRING_INTERVAL:
        assert schedule.interval_ticks is not None
        assert schedule.phase_tick is not None
        return (current - schedule.phase_tick) % schedule.interval_ticks == 0
    if schedule.cadence is MarketCadence.PERIODIC_WINDOW:
        return current // MARKET_WINDOW_TICKS == schedule.window_index
    return False


@dataclass(frozen=True, slots=True)
class MarketRoleClaim:
    """One broker-like owner role belief; recognition needs an objective basis."""

    role_kind: MarketRoleKind
    basis: MarketRoleBasis
    actor_id: EntityId
    office_ref: str | None
    organization_ref: str | None
    recognized: bool
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        role_kind = _require_enum(self.role_kind, MarketRoleKind)
        basis = _require_enum(self.basis, MarketRoleBasis)
        actor = _require_entity_id(
            self.actor_id, "market_institution_invalid_role_ref"
        )
        if type(self.recognized) is not bool:
            _fail("market_institution_invalid_role_ref")
        if self.office_ref is not None:
            _require_office_ref(self.office_ref)
        if self.organization_ref is not None:
            _require_organization_ref(self.organization_ref)
        if basis in (MarketRoleBasis.OBSERVED_PARTICIPATION, MarketRoleBasis.CLAIMED):
            if self.office_ref is not None or self.organization_ref is not None:
                _fail("market_institution_invalid_role_ref")
            if self.recognized:
                _fail("market_institution_invalid_role_ref")
        if self.recognized:
            if basis is MarketRoleBasis.OFFICE and self.office_ref is None:
                _fail("market_institution_invalid_role_ref")
            if basis is MarketRoleBasis.ORGANIZATION and self.organization_ref is None:
                _fail("market_institution_invalid_role_ref")
        first, last = _require_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "role_kind", role_kind)
        object.__setattr__(self, "basis", basis)
        object.__setattr__(self, "actor_id", actor)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)


@dataclass(frozen=True, slots=True)
class MarketRecordRef:
    """One opaque reference to an existing durable exchange record."""

    record_kind: MarketRecordKind
    anchor: str
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "record_kind", _require_enum(self.record_kind, MarketRecordKind)
        )
        object.__setattr__(self, "anchor", _require_anchor(self.anchor))
        first, last = _require_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)


@dataclass(frozen=True, slots=True)
class MarketVenueBelief:
    """One owner's bounded belief about exchange at a logical location."""

    venue_id: str
    owner_id: AgentId
    location_id: EntityId
    label_token: str
    status: MarketVenueStatus
    first_tick: int
    last_tick: int
    observations: tuple[MarketVenueObservation, ...]
    expectation: MarketMeetingExpectation
    schedules: tuple[MarketScheduleBelief, ...]
    roles: tuple[MarketRoleClaim, ...]
    records: tuple[MarketRecordRef, ...]
    notices: tuple[str, ...]

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(self, "venue_id", _require_belief_id(self.venue_id))
        owner = _require_owner_id(self.owner_id)
        location = _require_entity_id(
            self.location_id, "market_institution_invalid_venue_id"
        )
        label = _require_label(self.label_token)
        status = _require_enum(self.status, MarketVenueStatus)
        first, last = _require_span(self.first_tick, self.last_tick)
        for name in ("observations", "schedules", "roles", "records"):
            if not isinstance(getattr(self, name), (list, tuple)):
                _fail("market_institution_invalid_ledger")
        observations = tuple(self.observations)
        schedules = tuple(self.schedules)
        roles = tuple(self.roles)
        records = tuple(self.records)
        for observation in observations:
            if type(observation) is not MarketVenueObservation:
                _fail("market_institution_invalid_ledger")
        for schedule in schedules:
            if type(schedule) is not MarketScheduleBelief:
                _fail("market_institution_invalid_ledger")
        for role in roles:
            if type(role) is not MarketRoleClaim:
                _fail("market_institution_invalid_ledger")
        for record in records:
            if type(record) is not MarketRecordRef:
                _fail("market_institution_invalid_ledger")
        if type(self.expectation) is not MarketMeetingExpectation:
            _fail("market_institution_invalid_ledger")
        object.__setattr__(self, "owner_id", owner)
        object.__setattr__(self, "location_id", location)
        object.__setattr__(self, "label_token", label)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        object.__setattr__(self, "observations", observations)
        object.__setattr__(self, "schedules", schedules)
        object.__setattr__(self, "roles", roles)
        object.__setattr__(self, "records", records)
        object.__setattr__(self, "notices", _validate_notices(self.notices))


@dataclass(frozen=True, slots=True)
class MarketInstitutionLedger:
    """One owner's market-like institution beliefs. ``None`` means off."""

    owner_id: AgentId
    venues: tuple[MarketVenueBelief, ...] = ()
    notices: tuple[str, ...] = ()
    policy_version: str = MARKET_INSTITUTIONS_POLICY_VERSION

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        owner = _require_owner_id(self.owner_id)
        if self.policy_version != MARKET_INSTITUTIONS_POLICY_VERSION:
            _fail("market_institution_policy_mismatch")
        if not isinstance(self.venues, (list, tuple)):
            _fail("market_institution_invalid_ledger")
        venues = tuple(self.venues)
        seen: set[str] = set()
        for venue in venues:
            if type(venue) is not MarketVenueBelief:
                _fail("market_institution_invalid_ledger")
            if venue.owner_id != owner:
                _fail("market_institution_foreign_ledger")
            if venue.venue_id in seen:
                _fail("market_institution_duplicate_venue")
            seen.add(venue.venue_id)
        if len(venues) > _DEFAULT_POLICY.max_venues:
            _fail("market_institution_cap_exceeded")
        object.__setattr__(self, "owner_id", owner)
        object.__setattr__(self, "venues", venues)
        object.__setattr__(self, "notices", _validate_notices(self.notices))


def _validate_notices(values: object) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        _fail("market_institution_invalid_ledger")
    items = tuple(values)
    for item in items:
        if type(item) is not str or item not in MARKET_NOTICE_CODES:
            _fail("market_institution_invalid_ledger")
    return tuple(sorted(set(items))[: _DEFAULT_POLICY.max_notices])


def empty_market_institutions(owner_id: AgentId) -> MarketInstitutionLedger:
    """Return an enabled-but-empty market institution ledger for one owner."""

    return MarketInstitutionLedger(owner_id=owner_id)


def require_owner_market_institutions(
    ledger: object,
    owner_id: AgentId,
    *,
    field_name: str = "ledger",
) -> None:
    """Reject a foreign or mistyped ledger. ``None`` passes."""

    if ledger is None:
        return
    if type(owner_id) is not AgentId:
        _fail("market_institution_invalid_owner")
    if type(ledger) is not MarketInstitutionLedger:
        _LOG.error(
            "market_institution_carry_rejected field=%s reason_code=invalid_type",
            field_name,
        )
        raise TypeError(f"{field_name} must be MarketInstitutionLedger")
    if ledger.owner_id != owner_id:
        _LOG.error(
            "market_institution_carry_rejected field=%s reason_code=foreign_ledger",
            field_name,
        )
        _fail("market_institution_foreign_ledger")


def validate_market_institution_caps(ledger: object) -> None:
    """Validate every policy cap on one ledger; raise on overflow."""

    if type(ledger) is not MarketInstitutionLedger:
        raise TypeError("ledger must be MarketInstitutionLedger")
    policy = _DEFAULT_POLICY
    if len(ledger.venues) > policy.max_venues:
        _fail("market_institution_cap_exceeded")
    for venue in ledger.venues:
        if len(venue.observations) > policy.max_observations_per_venue:
            _fail("market_institution_cap_exceeded")
        if len(venue.schedules) > policy.max_schedules_per_venue:
            _fail("market_institution_cap_exceeded")
        if len(venue.roles) > policy.max_roles_per_venue:
            _fail("market_institution_cap_exceeded")
        if len(venue.records) > policy.max_records_per_venue:
            _fail("market_institution_cap_exceeded")
        for observation in venue.observations:
            if (
                len(observation.counterparty_ids)
                > policy.max_counterparties_per_observation
            ):
                _fail("market_institution_cap_exceeded")


# ---------------------------------------------------------------------------
# Owner-only evidence fold
# ---------------------------------------------------------------------------

_ATTEMPT_KINDS: Final[frozenset[str]] = frozenset(
    {"exchange_proposed", "exchange_withdrawn"}
)
_COMPLETION_KIND: Final[str] = "exchange_completed"


@dataclass(slots=True)
class _Aggregate:
    exchange_count: int = 0
    proposal_count: int = 0
    withdrawn_count: int = 0
    counterparties: set[str] = field(default_factory=set)


def _occurrence_kind(occurrence: object) -> str:
    facts = getattr(occurrence, "public_facts", {}) or {}
    kind = facts.get("kind")
    if type(kind) is str:
        return kind
    value = getattr(occurrence, "kind", None)
    return value if type(value) is str else ""


def _own_counterparty(
    occurrence: object, owner_value: str
) -> str | None:
    actor = getattr(occurrence, "actor_id", None)
    other = getattr(occurrence, "other_entity_id", None)
    actor_value = getattr(actor, "value", None)
    other_value = getattr(other, "value", None)
    if actor_value == owner_value and type(other_value) is str:
        return other_value
    if other_value == owner_value and type(actor_value) is str:
        return actor_value
    return None


def _collect_owner_exchange_aggregates(
    *,
    observer_value: str,
    tick: int,
    location_id: EntityId,
    observation: object,
    notices: set[str],
    policy: MarketInstitutionPolicy,
) -> dict[int, _Aggregate]:
    aggregates: dict[int, _Aggregate] = {}
    for occurrence in getattr(observation, "occurrences", ()):
        kind = _occurrence_kind(occurrence)
        if kind != _COMPLETION_KIND and kind not in _ATTEMPT_KINDS:
            continue
        counterparty = _own_counterparty(occurrence, observer_value)
        if counterparty is None:
            continue
        provenance = getattr(occurrence, "provenance", None)
        source_tick = getattr(provenance, "source_tick", None)
        if type(source_tick) is not int or source_tick < 0:
            continue
        if source_tick > tick:
            _fail("market_institution_invalid_evidence")
        if tick - source_tick > 1:
            notices.add("market_venue_stale")
            continue
        aggregate = aggregates.setdefault(source_tick, _Aggregate())
        if kind == _COMPLETION_KIND:
            aggregate.exchange_count += 1
            aggregate.counterparties.add(counterparty)
        elif kind == "exchange_proposed":
            aggregate.proposal_count += 1
        else:
            aggregate.withdrawn_count += 1
    for aggregate in aggregates.values():
        if (
            len(aggregate.counterparties)
            > policy.max_counterparties_per_observation
        ):
            kept = sorted(aggregate.counterparties)[
                : policy.max_counterparties_per_observation
            ]
            aggregate.counterparties = set(kept)
            notices.add("market_ledger_truncated")
    return aggregates


def _observation_location(observation: object) -> EntityId | None:
    body = getattr(observation, "self_body", None)
    location = getattr(body, "location_id", None)
    return location if type(location) is EntityId else None


def _observation_entity_value(observation: object, owner: AgentId) -> str:
    observer = getattr(observation, "observer_id", None)
    value = getattr(observer, "value", None)
    if type(value) is str and value:
        return value
    body = getattr(observation, "self_body", None)
    entity = getattr(body, "entity_id", None)
    value = getattr(entity, "value", None)
    if type(value) is str and value:
        return value
    return owner.value


def _build_observation(
    *, tick: int, source_tick: int, venue_id: str, aggregate: _Aggregate
) -> MarketVenueObservation:
    parties = tuple(EntityId(value) for value in sorted(aggregate.counterparties))
    digest = market_observation_digest(
        venue_id=venue_id,
        source_tick=source_tick,
        counterparty_ids=parties,
        exchange_count=aggregate.exchange_count,
        proposal_count=aggregate.proposal_count,
        withdrawn_count=aggregate.withdrawn_count,
    )
    return MarketVenueObservation(
        tick=tick,
        source_tick=source_tick,
        counterparty_ids=parties,
        exchange_count=aggregate.exchange_count,
        proposal_count=aggregate.proposal_count,
        withdrawn_count=aggregate.withdrawn_count,
        digest=digest,
    )


def _role_ref_resolves(
    claim: MarketRoleClaim,
    *,
    offices: object | None,
    organization_concepts: object | None,
) -> bool:
    if claim.basis is MarketRoleBasis.OFFICE:
        if claim.office_ref is None:
            return False
        concepts = getattr(offices, "concepts", None)
        if concepts is None:
            return False
        return any(
            getattr(concept, "role_signature", None) == claim.office_ref
            for concept in concepts
        )
    if claim.basis is MarketRoleBasis.ORGANIZATION:
        if claim.organization_ref is None:
            return False
        concepts = getattr(organization_concepts, "concepts", None)
        if concepts is None:
            return False
        return any(
            getattr(concept, "organization_id", None) == claim.organization_ref
            for concept in concepts
        )
    return False


def _reconcile_roles(
    roles: Sequence[MarketRoleClaim],
    *,
    tick: int,
    offices: object | None,
    organization_concepts: object | None,
    notices: set[str],
) -> tuple[MarketRoleClaim, ...]:
    reconciled: list[MarketRoleClaim] = []
    for role in roles:
        recognized = _role_ref_resolves(
            role, offices=offices, organization_concepts=organization_concepts
        )
        if role.basis in (MarketRoleBasis.OFFICE, MarketRoleBasis.ORGANIZATION):
            if not recognized:
                notices.add("market_role_unresolved")
        if recognized != role.recognized:
            role = replace(role, recognized=recognized)
        reconciled.append(role)
    return tuple(reconciled)


def _expectation_for(
    observations: Sequence[MarketVenueObservation],
    schedules: Sequence[MarketScheduleBelief],
    *,
    tick: int,
    policy: MarketInstitutionPolicy,
) -> MarketMeetingExpectation:
    count = len(observations)
    first = observations[0].source_tick if observations else tick
    last = observations[-1].source_tick if observations else tick
    level = MarketExpectation.NONE
    if count >= policy.strong_min_observations and any(
        schedule.confidence_milli >= policy.strong_min_confidence_milli
        for schedule in schedules
    ):
        level = MarketExpectation.STRONG
    elif count >= policy.expected_min_observations:
        level = MarketExpectation.EXPECTED
    elif count > 0:
        level = MarketExpectation.WEAK
    return MarketMeetingExpectation(
        level=level,
        evidence_count=count,
        first_tick=first,
        last_tick=max(last, first),
    )


def _status_for(
    observations: Sequence[MarketVenueObservation],
    *,
    tick: int,
    policy: MarketInstitutionPolicy,
) -> MarketVenueStatus:
    if not observations:
        return MarketVenueStatus.EMERGING
    last_tick = max(item.source_tick for item in observations)
    idle = tick - last_tick
    if idle >= policy.dormant_after_ticks:
        return MarketVenueStatus.DORMANT
    if idle >= policy.decline_after_ticks:
        return MarketVenueStatus.DECLINING
    distinct_ticks = {item.source_tick for item in observations}
    distinct_windows = {
        item.source_tick // MARKET_WINDOW_TICKS for item in observations
    }
    if (
        len(distinct_ticks) >= policy.persistent_min_ticks
        and len(distinct_windows) >= policy.persistent_min_windows
    ):
        return MarketVenueStatus.PERSISTENT
    if len(observations) >= policy.expected_min_observations:
        return MarketVenueStatus.EXPECTED
    return MarketVenueStatus.EMERGING


def _merge_observation(
    previous: tuple[MarketVenueObservation, ...],
    incoming: MarketVenueObservation,
) -> tuple[MarketVenueObservation, ...]:
    kept = [
        item for item in previous if item.source_tick != incoming.source_tick
    ]
    existing = next(
        (item for item in previous if item.source_tick == incoming.source_tick),
        None,
    )
    if existing is not None:
        incoming = replace(incoming, tick=existing.tick)
    kept.append(incoming)
    kept.sort(key=lambda item: (item.source_tick, item.tick, item.digest))
    return tuple(kept)


def _merge_schedules(
    previous: Sequence[MarketScheduleBelief],
    incoming: Sequence[MarketScheduleBelief],
) -> tuple[MarketScheduleBelief, ...]:
    merged: dict[tuple[str, object, object, object], MarketScheduleBelief] = {}
    for schedule in (*previous, *incoming):
        key = (
            schedule.cadence.value,
            schedule.interval_ticks,
            schedule.phase_tick,
            schedule.window_index,
        )
        existing = merged.get(key)
        if existing is None or schedule.last_tick >= existing.last_tick:
            merged[key] = schedule
    return tuple(merged.values())


def _merge_roles(
    previous: Sequence[MarketRoleClaim],
    incoming: Sequence[MarketRoleClaim],
) -> tuple[MarketRoleClaim, ...]:
    merged: dict[tuple[str, str], MarketRoleClaim] = {}
    for role in (*previous, *incoming):
        key = (role.actor_id.value, role.role_kind.value)
        existing = merged.get(key)
        if existing is None:
            merged[key] = role
            continue
        first = min(existing.first_tick, role.first_tick)
        last = max(existing.last_tick, role.last_tick)
        preferred = role if role.recognized and not existing.recognized else existing
        merged[key] = replace(preferred, first_tick=first, last_tick=last)
    return tuple(merged.values())


def _merge_records(
    previous: Sequence[MarketRecordRef],
    incoming: Sequence[MarketRecordRef],
) -> tuple[MarketRecordRef, ...]:
    merged: dict[tuple[str, str], MarketRecordRef] = {}
    for record in (*previous, *incoming):
        key = (record.record_kind.value, record.anchor)
        existing = merged.get(key)
        if existing is None:
            merged[key] = record
        else:
            merged[key] = replace(
                existing,
                first_tick=min(existing.first_tick, record.first_tick),
                last_tick=max(existing.last_tick, record.last_tick),
            )
    return tuple(merged.values())


def _trim_venue(
    venue: MarketVenueBelief,
    *,
    notices: set[str],
    policy: MarketInstitutionPolicy,
) -> MarketVenueBelief:
    observations = tuple(
        sorted(
            venue.observations,
            key=lambda item: (item.source_tick, item.tick, item.digest),
        )[-policy.max_observations_per_venue :]
    )
    schedules = tuple(
        sorted(
            venue.schedules,
            key=lambda item: (
                item.last_tick,
                item.cadence.value,
                -1 if item.interval_ticks is None else item.interval_ticks,
                -1 if item.phase_tick is None else item.phase_tick,
                -1 if item.window_index is None else item.window_index,
            ),
        )[-policy.max_schedules_per_venue :]
    )
    roles = tuple(
        sorted(
            venue.roles,
            key=lambda item: (
                item.last_tick,
                item.actor_id.value,
                item.role_kind.value,
            ),
        )[-policy.max_roles_per_venue :]
    )
    records = tuple(
        sorted(
            venue.records,
            key=lambda item: (item.last_tick, item.record_kind.value, item.anchor),
        )[-policy.max_records_per_venue :]
    )
    if (
        len(observations) != len(venue.observations)
        or len(schedules) != len(venue.schedules)
        or len(roles) != len(venue.roles)
        or len(records) != len(venue.records)
    ):
        notices.add("market_ledger_truncated")
    return replace(
        venue,
        observations=observations,
        schedules=schedules,
        roles=roles,
        records=records,
        notices=tuple(sorted(notices)),
    )


def _fold_communication_claims(
    *,
    observation: object,
    observer_value: str,
    tick: int,
    venues: Sequence[MarketVenueBelief],
    notices: set[str],
) -> dict[
    str,
    tuple[
        list[MarketScheduleBelief],
        list[MarketRoleClaim],
        list[MarketRecordRef],
        list[MarketMeetingExpectation],
    ],
]:
    """Fold inbound ``mkt_v1`` frames into owner venue beliefs."""

    from agents.cognition.market_institutions_communication import (
        parse_market_claim_relation,
    )

    by_label = {venue.label_token: venue for venue in venues}
    folded: dict[
        str,
        tuple[
            list[MarketScheduleBelief],
            list[MarketRoleClaim],
            list[MarketRecordRef],
            list[MarketMeetingExpectation],
        ],
    ] = {}
    for communication in getattr(observation, "communications", ()):
        speaker = getattr(communication, "speaker_id", None)
        listener = getattr(communication, "listener_id", None)
        speaker_value = getattr(speaker, "value", None)
        listener_value = getattr(listener, "value", None)
        if observer_value not in {speaker_value, listener_value}:
            continue
        utterance = getattr(communication, "utterance", None)
        content = getattr(utterance, "content", None)
        relations = getattr(content, "relations", ())
        for relation in relations:
            try:
                claim = parse_market_claim_relation(relation)
            except MarketInstitutionError:
                continue
            if claim is None:
                continue
            venue = by_label.get(claim.label_token)
            if venue is None:
                notices.add("market_venue_unresolved")
                continue
            schedule, role, record, expectation = folded.setdefault(
                venue.venue_id, ([], [], [], [])
            )
            source = (
                MarketScheduleSource.SELF_AUTHORED
                if speaker_value == observer_value
                else MarketScheduleSource.COMMUNICATED
            )
            if claim.cadence in (
                MarketCadence.RECURRING_INTERVAL,
                MarketCadence.PERIODIC_WINDOW,
            ):
                schedule.append(
                    MarketScheduleBelief(
                        cadence=claim.cadence,
                        interval_ticks=claim.interval_ticks,
                        phase_tick=claim.phase_tick,
                        window_index=claim.window_index,
                        confidence_milli=1000
                        if source is MarketScheduleSource.SELF_AUTHORED
                        else 500,
                        source=source,
                        first_tick=tick,
                        last_tick=tick,
                    )
                )
            if claim.role_kind is not MarketRoleKind.UNKNOWN:
                role.append(
                    MarketRoleClaim(
                        role_kind=claim.role_kind,
                        basis=MarketRoleBasis.CLAIMED,
                        actor_id=EntityId(
                            speaker_value
                            if type(speaker_value) is str
                            else observer_value
                        ),
                        office_ref=None,
                        organization_ref=None,
                        recognized=False,
                        first_tick=tick,
                        last_tick=tick,
                    )
                )
            if claim.anchor is not None:
                record.append(
                    MarketRecordRef(
                        record_kind=MarketRecordKind.EXCHANGE_RECORD,
                        anchor=claim.anchor,
                        first_tick=tick,
                        last_tick=tick,
                    )
                )
            if claim.expectation is not MarketExpectation.NONE:
                level = claim.expectation
                if (
                    source is MarketScheduleSource.COMMUNICATED
                    and level is MarketExpectation.STRONG
                ):
                    level = MarketExpectation.EXPECTED
                expectation.append(
                    MarketMeetingExpectation(
                        level=level,
                        evidence_count=venue.expectation.evidence_count,
                        first_tick=venue.expectation.first_tick,
                        last_tick=tick,
                    )
                )
    return folded


def _raise_expectation(
    base: MarketMeetingExpectation,
    claims: Sequence[MarketMeetingExpectation],
) -> MarketMeetingExpectation:
    order = {
        MarketExpectation.NONE: 0,
        MarketExpectation.WEAK: 1,
        MarketExpectation.EXPECTED: 2,
        MarketExpectation.STRONG: 3,
    }
    if not claims:
        return base
    strongest = max(claims, key=lambda item: order[item.level])
    if order[strongest.level] <= order[base.level]:
        return replace(base, last_tick=max(base.last_tick, strongest.last_tick))
    return replace(
        base,
        level=strongest.level,
        first_tick=min(base.first_tick, strongest.first_tick),
        last_tick=max(base.last_tick, strongest.last_tick),
    )


def apply_market_institution_update(
    *,
    owner_id: AgentId,
    tick: int,
    observation: object,
    prior: object | None,
    offices: object | None = None,
    organization_concepts: object | None = None,
    policy: MarketInstitutionPolicy | None = None,
) -> MarketInstitutionLedger:
    """Materialize one owner's market institution ledger from own evidence."""

    owner = _require_owner_id(owner_id)
    current_tick = _require_tick(tick)
    active_policy = _DEFAULT_POLICY if policy is None else policy
    if type(active_policy) is not MarketInstitutionPolicy:
        _fail("market_institution_policy_mismatch")
    if prior is not None:
        if type(prior) is not MarketInstitutionLedger:
            raise TypeError("prior must be MarketInstitutionLedger or None")
        if prior.owner_id != owner:
            _fail("market_institution_foreign_ledger")
    location = _observation_location(observation)
    observer_value = _observation_entity_value(observation, owner)

    notices: set[str] = set()
    aggregates: dict[int, _Aggregate] = {}
    if location is not None:
        aggregates = _collect_owner_exchange_aggregates(
            observer_value=observer_value,
            tick=current_tick,
            location_id=location,
            observation=observation,
            notices=notices,
            policy=active_policy,
        )

    prior_venues = {} if prior is None else {v.venue_id: v for v in prior.venues}
    venues: list[MarketVenueBelief] = []
    matched_venue_id: str | None = None
    if location is not None:
        for venue_id, venue in prior_venues.items():
            if venue.location_id == location:
                matched_venue_id = venue_id
                break

    if aggregates:
        if matched_venue_id is None:
            if any(a.exchange_count > 0 for a in aggregates.values()):
                if location is None:
                    raise MarketInstitutionError(
                        "market_institution_invalid_evidence"
                    )
                matched_venue_id = market_venue_belief_id(
                    owner_id=owner,
                    location_id=location,
                    creation_tick=current_tick,
                )
        if matched_venue_id is not None:
            base = prior_venues.get(matched_venue_id)
            observations: tuple[MarketVenueObservation, ...] = (
                () if base is None else base.observations
            )
            for source_tick in sorted(aggregates):
                incoming = _build_observation(
                    tick=current_tick,
                    source_tick=source_tick,
                    venue_id=matched_venue_id,
                    aggregate=aggregates[source_tick],
                )
                observations = _merge_observation(observations, incoming)
            if base is None:
                assert location is not None
                venue = MarketVenueBelief(
                    venue_id=matched_venue_id,
                    owner_id=owner,
                    location_id=location,
                    label_token=f"venue-{matched_venue_id[5:13]}",
                    status=MarketVenueStatus.EMERGING,
                    first_tick=current_tick,
                    last_tick=current_tick,
                    observations=observations,
                    expectation=MarketMeetingExpectation(
                        level=MarketExpectation.NONE,
                        evidence_count=0,
                        first_tick=current_tick,
                        last_tick=current_tick,
                    ),
                    schedules=(),
                    roles=(),
                    records=(),
                    notices=(),
                )
            else:
                venue = replace(base, observations=observations)
            first_tick = min(
                venue.first_tick,
                *(item.source_tick for item in observations),
            )
            expectation = _expectation_for(
                observations,
                venue.schedules,
                tick=current_tick,
                policy=active_policy,
            )
            status = _status_for(
                observations, tick=current_tick, policy=active_policy
            )
            venue = replace(
                venue,
                first_tick=first_tick,
                last_tick=max(venue.last_tick, current_tick),
                expectation=expectation,
                status=status,
            )
            prior_venues[matched_venue_id] = venue

    folded = _fold_communication_claims(
        observation=observation,
        observer_value=observer_value,
        tick=current_tick,
        venues=tuple(prior_venues.values()),
        notices=notices,
    )

    for venue_id in sorted(prior_venues):
        base = prior_venues[venue_id]
        schedules_in, roles_in, records_in, expectation_in = folded.get(
            venue_id, ([], [], [], [])
        )
        schedules = _merge_schedules(base.schedules, schedules_in)
        roles = _merge_roles(base.roles, roles_in)
        records = _merge_records(base.records, records_in)
        roles = _reconcile_roles(
            roles,
            tick=current_tick,
            offices=offices,
            organization_concepts=organization_concepts,
            notices=notices,
        )
        objective = _expectation_for(
            base.observations,
            schedules,
            tick=current_tick,
            policy=active_policy,
        )
        expectation = _raise_expectation(objective, expectation_in)
        status = _status_for(
            base.observations, tick=current_tick, policy=active_policy
        )
        if expectation.level is MarketExpectation.STRONG:
            if status is MarketVenueStatus.EMERGING:
                status = MarketVenueStatus.EXPECTED
        venue_notices = set(base.notices)
        venue_notices.update(notices)
        last_tick = base.last_tick
        if schedules_in or roles_in or records_in or expectation_in:
            last_tick = max(last_tick, current_tick)
        venue = replace(
            base,
            schedules=schedules,
            roles=roles,
            records=records,
            expectation=expectation,
            status=status,
            last_tick=last_tick,
            notices=tuple(sorted(venue_notices)),
        )
        venues.append(_trim_venue(venue, notices=notices, policy=active_policy))

    venues.sort(key=lambda item: (item.last_tick, item.venue_id))
    if len(venues) > active_policy.max_venues:
        venues = venues[-active_policy.max_venues :]
        notices.add("market_ledger_truncated")

    ledger = MarketInstitutionLedger(
        owner_id=owner,
        venues=tuple(venues),
        notices=tuple(sorted(notices)),
        policy_version=MARKET_INSTITUTIONS_POLICY_VERSION,
    )
    _LOG.debug(
        "market_institution_update venues=%s observations=%s notices=%s tick=%s",
        len(ledger.venues),
        sum(len(venue.observations) for venue in ledger.venues),
        len(ledger.notices),
        current_tick,
    )
    return ledger


__all__ = [
    "MARKET_ANCHOR_MAX_LEN",
    "MARKET_ANCHOR_PATTERN",
    "MARKET_BELIEF_HEX_LEN",
    "MARKET_BELIEF_PREFIX",
    "MARKET_FORBIDDEN_FIELD_NAMES",
    "MARKET_INSTITUTIONS_POLICY_VERSION",
    "MARKET_INSTITUTION_LOCKED_POLICY",
    "MARKET_LABEL_MAX_LEN",
    "MARKET_LABEL_PATTERN",
    "MARKET_MAX_WINDOWS",
    "MARKET_NOTICE_CODES",
    "MARKET_WINDOW_TICKS",
    "MarketCadence",
    "MarketExpectation",
    "MarketInstitutionError",
    "MarketInstitutionLedger",
    "MarketInstitutionPolicy",
    "MarketMeetingExpectation",
    "MarketRecordKind",
    "MarketRecordRef",
    "MarketRoleBasis",
    "MarketRoleClaim",
    "MarketRoleKind",
    "MarketScheduleBelief",
    "MarketScheduleSource",
    "MarketVenueBelief",
    "MarketVenueObservation",
    "MarketVenueStatus",
    "apply_market_institution_update",
    "default_market_institution_policy",
    "empty_market_institutions",
    "market_cluster_id",
    "market_observation_digest",
    "market_schedule_is_active",
    "market_venue_analysis_id",
    "market_venue_belief_id",
    "require_market_belief_id",
    "require_owner_market_institutions",
    "validate_market_institution_caps",
]
