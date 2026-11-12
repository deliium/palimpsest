"""Owner-scoped price expectations. These numbers are not a world price and no
owner reads another owner's ledger.

One owner forms a bounded expectation for an ``(item_kind, unit)`` pair from its
own valuation, its own observed completed exchanges, and quoted offers it
received. There is no global price table, no canonical price, and no money,
credit, or debt object. Every value is frozen and owner-local.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final, NoReturn

from agents.cognition.acceptance_memory import AcceptanceMemoryLedger
from agents.cognition.subjective_value import SubjectiveValuationLedger
from agents.models import AgentId
from world.identifiers import EntityId
from world.values import ItemKind

__all__ = [
    "EMERGENT_PRICES_POLICY_VERSION",
    "EMERGENT_PRICE_LOCKED_POLICY",
    "EMERGENT_PRICE_NOTICE_CODES",
    "PRICE_BELIEF_HEX_LEN",
    "PRICE_BELIEF_PREFIX",
    "PRICE_CONFIDENCE_MAX_MILLI",
    "PRICE_FORBIDDEN_FIELD_NAMES",
    "PRICE_MAX_NOTICES",
    "PRICE_MAX_ROWS",
    "PRICE_MAX_UNITS",
    "PRICE_RATIO_MAX_MILLI",
    "EmergentPriceError",
    "EmergentPriceLedger",
    "EmergentPricePolicy",
    "PriceExpectationLevel",
    "PriceExpectationRow",
    "PriceObservation",
    "PriceQuote",
    "PriceQuoteDirection",
    "PriceQuoteSource",
    "PriceUnitSource",
    "apply_emergent_price_update",
    "canonical_exchange_pair",
    "default_emergent_price_policy",
    "empty_emergent_prices",
    "price_belief_id",
    "price_observation_digest",
    "price_venue_token",
    "quote_direction_for",
    "require_owner_emergent_prices",
    "require_price_belief_id",
    "validate_emergent_price_caps",
]

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.emergent_prices")

EMERGENT_PRICES_POLICY_VERSION: Final[str] = "emergent-prices.v1"
PRICE_BELIEF_PREFIX: Final[str] = "prcb-"
PRICE_BELIEF_HEX_LEN: Final[int] = 16
PRICE_MAX_UNITS: Final[int] = 8
PRICE_MAX_ROWS: Final[int] = 32
PRICE_MAX_NOTICES: Final[int] = 8
PRICE_RATIO_MAX_MILLI: Final[int] = 64_000
PRICE_CONFIDENCE_MAX_MILLI: Final[int] = 1_000
PRICE_MAX_COUNTERPARTIES: Final[int] = 8
PRICE_WINDOW_TICKS: Final[int] = 32
PRICE_MAX_WINDOWS: Final[int] = 512
PRICE_VENUE_PREFIX: Final[str] = "mkt-ven-"
PRICE_NONE_TOKEN: Final[str] = "none"


class PriceUnitSource(StrEnum):
    """Closed source of one owner unit candidate."""

    OWNER_REFERENCE = "owner_reference"
    OBSERVED_MEDIUM = "observed_medium"
    EXCHANGE_COUNTERPART = "exchange_counterpart"
    QUOTED = "quoted"
    UNKNOWN = "unknown"


class PriceQuoteDirection(StrEnum):
    """Closed direction of one quoted offer."""

    GIVE_FOR_UNIT = "give_for_unit"
    UNIT_FOR_GIVE = "unit_for_give"


class PriceQuoteSource(StrEnum):
    """Closed provenance of one quote."""

    OBSERVED_OFFER = "observed_offer"
    COMMUNICATED = "communicated"
    SELF_AUTHORED = "self_authored"


class PriceExpectationLevel(StrEnum):
    """Closed qualitative expectation level; never a score or rank."""

    NONE = "none"
    WEAK = "weak"
    EXPECTED = "expected"
    STRONG = "strong"


EMERGENT_PRICE_NOTICE_CODES: Final[frozenset[str]] = frozenset(
    {
        "price_ledger_truncated",
        "price_unit_unresolved",
        "price_valuation_stale",
        "price_quote_malformed",
        "price_evidence_unpaired",
    }
)

PRICE_FORBIDDEN_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "price",
        "canonical_price",
        "price_index",
        "clearing_price",
        "rate",
        "money",
        "currency",
        "numeraire",
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
        "unit_of_account",
        "medium_of_exchange",
        "store_of_value",
    }
)


class EmergentPriceError(ValueError):
    """Fail-closed owner price error; ``args[0]`` is a stable reason code."""

    @property
    def reason_code(self) -> str:
        if not self.args:
            return "price_invalid_policy"
        return str(self.args[0])


def _fail(code: str) -> NoReturn:
    _LOG.error("emergent_price_invalid reason_code=%s", code)
    raise EmergentPriceError(code)


def _digest16(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:PRICE_BELIEF_HEX_LEN]


def _reject_forbidden_fields(cls: type[object]) -> None:
    names = set(getattr(cls, "__dataclass_fields__", {}))
    if names & PRICE_FORBIDDEN_FIELD_NAMES:
        _fail("price_invalid_policy")


def _require_owner_id(value: object) -> AgentId:
    if type(value) is not AgentId:
        _fail("price_invalid_identifier")
    return value


def _require_tick(value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        _fail("price_invalid_identifier")
    return value


def _require_count(value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        _fail("price_invalid_identifier")
    return value


def _require_span(first_tick: object, last_tick: object) -> tuple[int, int]:
    first = _require_tick(first_tick)
    last = _require_tick(last_tick)
    if last < first:
        _fail("price_invalid_identifier")
    return first, last


def _require_enum(value: object, enum_type: type[StrEnum]) -> StrEnum:
    if type(value) is not enum_type:
        _fail("price_invalid_enum")
    return value


def _require_item_kind(value: object) -> ItemKind:
    if type(value) is not ItemKind:
        _fail("price_invalid_unit")
    return value


def _require_ratio(value: object, *, maximum: int, code: str) -> int:
    if isinstance(value, bool) or type(value) is not int or not 0 <= value <= maximum:
        _fail(code)
    return value


def _require_digest(value: object) -> str:
    if (
        type(value) is not str
        or len(value) != PRICE_BELIEF_HEX_LEN
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail("price_invalid_identifier")
    return value


def _unit_token(unit_kind: ItemKind | None) -> str:
    return PRICE_NONE_TOKEN if unit_kind is None else unit_kind.value


def price_belief_id(
    owner_id: AgentId, item_kind: ItemKind, unit_token: str
) -> str:
    """Mint one deterministic owner-local ``prcb-`` belief id."""

    owner = _require_owner_id(owner_id)
    item = _require_item_kind(item_kind)
    if type(unit_token) is not str or not unit_token:
        _fail("price_invalid_unit")
    return PRICE_BELIEF_PREFIX + _digest16(
        "palimpsest.price.belief.v1\x1f"
        + owner.value
        + "|"
        + item.value
        + "|"
        + unit_token
    )


def require_price_belief_id(value: object) -> str:
    """Validate one exact owner-local ``prcb-`` id."""

    if (
        type(value) is not str
        or not value.startswith(PRICE_BELIEF_PREFIX)
        or len(value) != len(PRICE_BELIEF_PREFIX) + PRICE_BELIEF_HEX_LEN
        or any(
            character not in "0123456789abcdef"
            for character in value[len(PRICE_BELIEF_PREFIX) :]
        )
    ):
        _fail("price_invalid_identifier")
    return value


def price_venue_token(location_token: str) -> str:
    """Mint the analysis-compatible ``mkt-ven-`` token for one location."""

    if type(location_token) is not str or not location_token:
        _fail("price_invalid_unit")
    digest = hashlib.sha256(f"venue\x1f{location_token}".encode()).hexdigest()
    return f"{PRICE_VENUE_PREFIX}{digest[:PRICE_BELIEF_HEX_LEN]}"


@dataclass(frozen=True, slots=True)
class EmergentPricePolicy:
    """Locked owner-local price expectation bounds."""

    max_rows: int = 32
    max_observations_per_row: int = 32
    max_quotes_per_row: int = 8
    max_counterparties: int = 8
    max_units: int = 8
    max_notices: int = 8
    stale_after_ticks: int = 64
    expected_min_observations: int = 2
    strong_min_confidence_milli: int = 750
    quote_min_confidence_milli: int = 250
    medium_min_received: int = 2
    ratio_max_milli: int = 64_000
    confidence_base_per_evidence: int = 150
    confidence_base_cap: int = 600

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        for name, expected in EMERGENT_PRICE_LOCKED_POLICY.items():
            actual = getattr(self, name)
            if (
                isinstance(actual, bool)
                or type(actual) is not int
                or actual != expected
            ):
                _fail("price_invalid_policy")


EMERGENT_PRICE_LOCKED_POLICY: Final[Mapping[str, int]] = MappingProxyType(
    {
        "max_rows": PRICE_MAX_ROWS,
        "max_observations_per_row": 32,
        "max_quotes_per_row": 8,
        "max_counterparties": PRICE_MAX_COUNTERPARTIES,
        "max_units": PRICE_MAX_UNITS,
        "max_notices": PRICE_MAX_NOTICES,
        "stale_after_ticks": 64,
        "expected_min_observations": 2,
        "strong_min_confidence_milli": 750,
        "quote_min_confidence_milli": 250,
        "medium_min_received": 2,
        "ratio_max_milli": PRICE_RATIO_MAX_MILLI,
        "confidence_base_per_evidence": 150,
        "confidence_base_cap": 600,
    }
)

_DEFAULT_POLICY: Final[EmergentPricePolicy] = EmergentPricePolicy()


def default_emergent_price_policy() -> EmergentPricePolicy:
    """Return the single locked price expectation policy instance."""

    return _DEFAULT_POLICY


def _require_policy(value: object) -> EmergentPricePolicy:
    if type(value) is not EmergentPricePolicy:
        _fail("price_invalid_policy")
    return value


@dataclass(frozen=True, slots=True)
class PriceObservation:
    """One owner-observed exchange aggregate for a source tick and unit pair."""

    source_tick: int
    item_kind: ItemKind
    unit_kind: ItemKind
    counterparty_ids: tuple[EntityId, ...]
    exchange_count: int
    proposed_count: int
    withdrawn_count: int
    observed_ratio_milli: int | None
    digest: str

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        source = _require_tick(self.source_tick)
        item = _require_item_kind(self.item_kind)
        unit = _require_item_kind(self.unit_kind)
        if item is unit:
            _fail("price_invalid_unit")
        if isinstance(self.counterparty_ids, (str, bytes)) or not isinstance(
            self.counterparty_ids, (list, tuple)
        ):
            _fail("price_invalid_identifier")
        parties = tuple(self.counterparty_ids)
        for party in parties:
            if type(party) is not EntityId:
                _fail("price_invalid_identifier")
        values = tuple(sorted({party.value for party in parties}))
        if len(values) != len(parties):
            _fail("price_invalid_identifier")
        exchange = _require_count(self.exchange_count)
        proposed = _require_count(self.proposed_count)
        withdrawn = _require_count(self.withdrawn_count)
        if exchange > 0 and not values:
            _fail("price_invalid_identifier")
        if len(values) > PRICE_MAX_COUNTERPARTIES:
            _fail("price_invalid_policy")
        ratio = self.observed_ratio_milli
        if ratio is not None:
            ratio = _require_ratio(
                ratio, maximum=PRICE_RATIO_MAX_MILLI, code="price_invalid_ratio"
            )
        object.__setattr__(self, "source_tick", source)
        object.__setattr__(self, "item_kind", item)
        object.__setattr__(self, "unit_kind", unit)
        object.__setattr__(
            self, "counterparty_ids", tuple(EntityId(value) for value in values)
        )
        object.__setattr__(self, "exchange_count", exchange)
        object.__setattr__(self, "proposed_count", proposed)
        object.__setattr__(self, "withdrawn_count", withdrawn)
        object.__setattr__(self, "observed_ratio_milli", ratio)
        object.__setattr__(self, "digest", _require_digest(self.digest))


def canonical_exchange_pair(
    give_kinds: Sequence[ItemKind], take_kinds: Sequence[ItemKind]
) -> tuple[ItemKind, ItemKind] | None:
    """Return the canonical ``(item_kind, unit_kind)`` pair for one offer.

    A pair exists only when each side is homogeneous in exactly one distinct
    kind. Heterogeneous and same-kind sides return ``None`` and never invent a
    ratio.
    """

    if not give_kinds or not take_kinds:
        return None
    give = set(give_kinds)
    take = set(take_kinds)
    if len(give) != 1 or len(take) != 1:
        return None
    give_kind = next(iter(give))
    take_kind = next(iter(take))
    if give_kind is take_kind:
        return None
    if give_kind.value < take_kind.value:
        return give_kind, take_kind
    return take_kind, give_kind


def quote_direction_for(
    *,
    item_kind: ItemKind,
    unit_kind: ItemKind,
    give_kinds: Sequence[ItemKind],
) -> PriceQuoteDirection:
    """Return the actor-relative direction for a canonical price pair."""

    if item_kind not in give_kinds:
        return PriceQuoteDirection.UNIT_FOR_GIVE
    return PriceQuoteDirection.GIVE_FOR_UNIT


def price_observation_digest(
    *,
    source_tick: int,
    item_kind: ItemKind,
    unit_kind: ItemKind,
    counterparty_ids: Sequence[EntityId],
    exchange_count: int,
    proposed_count: int,
    withdrawn_count: int,
    observed_ratio_milli: int | None,
) -> str:
    """Return the deterministic observation identity digest."""

    parties = ",".join(
        sorted({party.value for party in counterparty_ids if type(party) is EntityId})
    )
    ratio = PRICE_NONE_TOKEN if observed_ratio_milli is None else str(
        observed_ratio_milli
    )
    return _digest16(
        "price-observation\x1f"
        + str(source_tick)
        + "\x1f"
        + item_kind.value
        + "\x1f"
        + unit_kind.value
        + "\x1f"
        + parties
        + "\x1f"
        + str(exchange_count)
        + "\x1f"
        + str(proposed_count)
        + "\x1f"
        + str(withdrawn_count)
        + "\x1f"
        + ratio
    )


def make_price_observation(
    *,
    source_tick: int,
    item_kind: ItemKind,
    unit_kind: ItemKind,
    counterparty_ids: Sequence[EntityId],
    exchange_count: int,
    proposed_count: int,
    withdrawn_count: int,
    observed_ratio_milli: int | None,
) -> PriceObservation:
    """Build one validated observation with its canonical digest."""

    digest = price_observation_digest(
        source_tick=source_tick,
        item_kind=item_kind,
        unit_kind=unit_kind,
        counterparty_ids=counterparty_ids,
        exchange_count=exchange_count,
        proposed_count=proposed_count,
        withdrawn_count=withdrawn_count,
        observed_ratio_milli=observed_ratio_milli,
    )
    return PriceObservation(
        source_tick=source_tick,
        item_kind=item_kind,
        unit_kind=unit_kind,
        counterparty_ids=tuple(counterparty_ids),
        exchange_count=exchange_count,
        proposed_count=proposed_count,
        withdrawn_count=withdrawn_count,
        observed_ratio_milli=observed_ratio_milli,
        digest=digest,
    )


@dataclass(frozen=True, slots=True)
class PriceQuote:
    """One observed or communicated quoted offer for an item and unit."""

    item_kind: ItemKind
    unit_kind: ItemKind
    venue_id: str
    direction: PriceQuoteDirection
    counterparty_id: EntityId | None
    ratio_milli: int
    confidence_milli: int
    source: PriceQuoteSource
    source_tick: int
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        if type(self.venue_id) is not str or not self.venue_id:
            _fail("price_invalid_identifier")
        object.__setattr__(
            self, "direction", _require_enum(self.direction, PriceQuoteDirection)
        )
        object.__setattr__(self, "source", _require_enum(self.source, PriceQuoteSource))
        if (
            self.counterparty_id is not None
            and type(self.counterparty_id) is not EntityId
        ):
            _fail("price_invalid_identifier")
        _require_ratio(
            self.ratio_milli, maximum=PRICE_RATIO_MAX_MILLI, code="price_invalid_ratio"
        )
        confidence = _require_ratio(
            self.confidence_milli,
            maximum=PRICE_CONFIDENCE_MAX_MILLI,
            code="price_invalid_confidence",
        )
        source_tick = _require_tick(self.source_tick)
        first, last = _require_span(self.first_tick, self.last_tick)
        object.__setattr__(self, "confidence_milli", confidence)
        object.__setattr__(self, "source_tick", source_tick)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        object.__setattr__(self, "item_kind", _require_item_kind(self.item_kind))
        object.__setattr__(self, "unit_kind", _require_item_kind(self.unit_kind))
        if self.item_kind is self.unit_kind:
            _fail("price_invalid_unit")


@dataclass(frozen=True, slots=True)
class PriceExpectationRow:
    """One owner expectation for an item kind and its unit candidate."""

    item_kind: ItemKind
    unit_kind: ItemKind | None
    unit_source: PriceUnitSource
    expected_ratio_milli: int
    confidence_milli: int
    level: PriceExpectationLevel
    valuation_reservation: int
    observation_count: int
    quote_count: int
    first_tick: int
    last_tick: int
    observations: tuple[PriceObservation, ...]
    quotes: tuple[PriceQuote, ...]
    row_id: str

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        item = _require_item_kind(self.item_kind)
        if self.unit_kind is not None:
            object.__setattr__(self, "unit_kind", _require_item_kind(self.unit_kind))
        object.__setattr__(
            self, "unit_source", _require_enum(self.unit_source, PriceUnitSource)
        )
        ratio = _require_ratio(
            self.expected_ratio_milli,
            maximum=PRICE_RATIO_MAX_MILLI,
            code="price_invalid_ratio",
        )
        confidence = _require_ratio(
            self.confidence_milli,
            maximum=PRICE_CONFIDENCE_MAX_MILLI,
            code="price_invalid_confidence",
        )
        object.__setattr__(
            self, "level", _require_enum(self.level, PriceExpectationLevel)
        )
        reservation = _require_count(self.valuation_reservation)
        if reservation > 16:
            _fail("price_invalid_policy")
        observations = self._rows(self.observations, PriceObservation)
        quotes = self._rows(self.quotes, PriceQuote)
        if len(observations) > PRICE_MAX_ROWS:
            _fail("price_invalid_policy")
        if len(quotes) > PRICE_MAX_ROWS:
            _fail("price_invalid_policy")
        exchange_ticks = tuple(row.source_tick for row in observations)
        if exchange_ticks != tuple(sorted(set(exchange_ticks))):
            _fail("price_invalid_identifier")
        quote_ticks = tuple(row.source_tick for row in quotes)
        if quote_ticks != tuple(sorted(set(quote_ticks))):
            _fail("price_invalid_identifier")
        first, last = _require_span(self.first_tick, self.last_tick)
        if len(observations) != self.observation_count:
            _fail("price_invalid_identifier")
        if len(quotes) != self.quote_count:
            _fail("price_invalid_identifier")
        row_id = require_price_belief_id(self.row_id)
        object.__setattr__(self, "item_kind", item)
        object.__setattr__(self, "expected_ratio_milli", ratio)
        object.__setattr__(self, "confidence_milli", confidence)
        object.__setattr__(self, "valuation_reservation", reservation)
        object.__setattr__(self, "observations", observations)
        object.__setattr__(self, "quotes", quotes)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        object.__setattr__(self, "row_id", row_id)

    @staticmethod
    def _rows[T](values: object, row_type: type[T]) -> tuple[T, ...]:
        if isinstance(values, (str, bytes)) or not isinstance(values, (list, tuple)):
            _fail("price_invalid_identifier")
        rows = tuple(values)
        for row in rows:
            if type(row) is not row_type:
                _fail("price_invalid_identifier")
        return rows


def _validate_notices(values: object) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (list, tuple)):
        _fail("price_invalid_policy")
    items = tuple(values)
    for item in items:
        if type(item) is not str or item not in EMERGENT_PRICE_NOTICE_CODES:
            _fail("price_invalid_policy")
    return tuple(sorted(set(items))[:PRICE_MAX_NOTICES])


@dataclass(frozen=True, slots=True)
class EmergentPriceLedger:
    """One owner's price expectation rows. ``None`` means price mode is off."""

    owner_id: AgentId
    rows: tuple[PriceExpectationRow, ...] = ()
    notices: tuple[str, ...] = ()
    policy_version: str = EMERGENT_PRICES_POLICY_VERSION

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        owner = _require_owner_id(self.owner_id)
        if self.policy_version != EMERGENT_PRICES_POLICY_VERSION:
            _fail("price_invalid_policy")
        if isinstance(self.rows, (str, bytes)) or not isinstance(
            self.rows, (list, tuple)
        ):
            _fail("price_invalid_policy")
        rows = tuple(self.rows)
        seen: set[str] = set()
        for row in rows:
            if type(row) is not PriceExpectationRow:
                _fail("price_invalid_identifier")
            if row.row_id in seen:
                _fail("price_invalid_identifier")
            seen.add(row.row_id)
        if len(rows) > PRICE_MAX_ROWS:
            _fail("price_invalid_policy")
        object.__setattr__(self, "owner_id", owner)
        object.__setattr__(self, "rows", rows)
        object.__setattr__(self, "notices", _validate_notices(self.notices))


def empty_emergent_prices(owner_id: AgentId) -> EmergentPriceLedger:
    """Return an enabled-but-empty price ledger for one owner."""

    if type(owner_id) is not AgentId:
        _fail("price_invalid_identifier")
    return EmergentPriceLedger(owner_id=owner_id)


def require_owner_emergent_prices(
    value: object | None,
    owner_id: AgentId,
    *,
    field_name: str = "emergent_prices",
) -> None:
    """Reject a foreign or mistyped ledger. ``None`` passes."""

    if value is None:
        return
    if type(owner_id) is not AgentId:
        _fail("price_invalid_identifier")
    if type(value) is not EmergentPriceLedger:
        _LOG.error(
            "emergent_price_carry_rejected field=%s reason=invalid_type",
            field_name,
        )
        raise TypeError(f"{field_name} must be EmergentPriceLedger or None")
    if value.owner_id != owner_id:
        _LOG.error("emergent_price_carry_rejected field=%s reason=foreign", field_name)
        _fail("price_invalid_identifier")


def validate_emergent_price_caps(ledger: object, policy: object | None = None) -> None:
    """Validate every policy cap on one ledger; raise on overflow."""

    if type(ledger) is not EmergentPriceLedger:
        raise TypeError("ledger must be EmergentPriceLedger")
    active = _DEFAULT_POLICY if policy is None else _require_policy(policy)
    if len(ledger.rows) > active.max_rows:
        _fail("price_invalid_policy")
    for row in ledger.rows:
        if len(row.observations) > active.max_observations_per_row:
            _fail("price_invalid_policy")
        if len(row.quotes) > active.max_quotes_per_row:
            _fail("price_invalid_policy")
        for observation in row.observations:
            if len(observation.counterparty_ids) > active.max_counterparties:
                _fail("price_invalid_policy")
    if len(ledger.notices) > active.max_notices:
        _fail("price_invalid_policy")


def _valuation_reservations(
    valuations: SubjectiveValuationLedger | None,
) -> dict[ItemKind, int]:
    if valuations is None:
        return {}
    if type(valuations) is not SubjectiveValuationLedger:
        _fail("price_invalid_policy")
    return {row.item_kind: row.reservation for row in valuations.kind_rows}


def _valuation_ticks(
    valuations: SubjectiveValuationLedger | None,
) -> tuple[int, ...]:
    if valuations is None:
        return ()
    return tuple(row.tick for row in valuations.kind_rows)


def _valuation_references(
    valuations: SubjectiveValuationLedger | None,
) -> dict[ItemKind, ItemKind]:
    if valuations is None:
        return {}
    return {row.item_kind: row.reference_kind for row in valuations.kind_rows}


def _unit_candidates(
    *,
    observations: Sequence[PriceObservation],
    quotes: Sequence[PriceQuote],
    reservations: Mapping[ItemKind, int],
    references: Mapping[ItemKind, ItemKind],
    acceptance: AcceptanceMemoryLedger | None,
    policy: EmergentPricePolicy,
) -> tuple[tuple[ItemKind, PriceUnitSource], ...]:
    candidates: list[tuple[ItemKind, PriceUnitSource]] = []
    for kind, reservation in sorted(
        reservations.items(), key=lambda item: item[0].value
    ):
        if reservation == 1:
            candidates.append(
                (references.get(kind, kind), PriceUnitSource.OWNER_REFERENCE)
            )
    if acceptance is not None:
        if type(acceptance) is not AcceptanceMemoryLedger:
            _fail("price_invalid_policy")
        medium = [
            row
            for row in acceptance.rows
            if row.received_count >= policy.medium_min_received
        ]
        medium.sort(key=lambda row: (-row.received_count, row.item_kind.value))
        for row in medium:
            candidates.append((row.item_kind, PriceUnitSource.OBSERVED_MEDIUM))
    for observation in observations:
        candidates.append((observation.unit_kind, PriceUnitSource.EXCHANGE_COUNTERPART))
    for quote in quotes:
        candidates.append((quote.unit_kind, PriceUnitSource.EXCHANGE_COUNTERPART))
        if quote.source is PriceQuoteSource.COMMUNICATED:
            candidates.append((quote.unit_kind, PriceUnitSource.QUOTED))
    deduplicated: list[tuple[ItemKind, PriceUnitSource]] = []
    seen: set[tuple[ItemKind, PriceUnitSource]] = set()
    for kind, source in candidates:
        key = (kind, source)
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(key)
        if len(deduplicated) >= policy.max_units:
            break
    return tuple(deduplicated)


def _merge_observations(
    prior: Sequence[PriceObservation],
    incoming: Sequence[PriceObservation],
    *,
    item_kind: ItemKind,
    unit_kind: ItemKind,
    policy: EmergentPricePolicy,
) -> tuple[PriceObservation, ...]:
    merged: dict[int, PriceObservation] = {}
    for row in (*prior, *incoming):
        if row.item_kind is not item_kind or row.unit_kind is not unit_kind:
            continue
        existing = merged.get(row.source_tick)
        if existing is None:
            merged[row.source_tick] = row
    rows = tuple(
        sorted(merged.values(), key=lambda row: (row.source_tick, row.digest))
    )
    return rows[-policy.max_observations_per_row :]


def _merge_quotes(
    prior: Sequence[PriceQuote],
    incoming: Sequence[PriceQuote],
    *,
    item_kind: ItemKind,
    unit_kind: ItemKind,
    policy: EmergentPricePolicy,
) -> tuple[PriceQuote, ...]:
    merged: dict[tuple[str, PriceQuoteDirection, int], PriceQuote] = {}
    for row in sorted(
        (*prior, *incoming),
        key=lambda item: (
            item.source_tick,
            item.venue_id,
            item.direction.value,
            item.ratio_milli,
        ),
    ):
        if row.item_kind is not item_kind or row.unit_kind is not unit_kind:
            continue
        key = (row.venue_id, row.direction, row.source_tick)
        if key in merged:
            continue
        merged[key] = row
    rows = tuple(
        sorted(
            merged.values(),
            key=lambda row: (
                row.source_tick,
                row.venue_id,
                row.direction.value,
                row.ratio_milli,
            ),
        )
    )
    return rows[-policy.max_quotes_per_row :]


def _weighted_lower_median(samples: Sequence[tuple[int, int]]) -> int:
    ordered = sorted(samples, key=lambda item: item[0])
    total = sum(weight for _ratio, weight in ordered)
    target = (total - 1) // 2
    cumulative = 0
    for ratio, weight in ordered:
        cumulative += weight
        if cumulative > target:
            return ratio
    return ordered[-1][0]


def _confidence(
    *,
    evidence: int,
    ratios: Sequence[int],
    policy: EmergentPricePolicy,
) -> int:
    base = min(
        policy.confidence_base_cap,
        evidence * policy.confidence_base_per_evidence,
    )
    if ratios:
        spread = max(ratios) - min(ratios)
        dispersion = spread * 1_000 // max(1, max(ratios))
    else:
        dispersion = 0
    agreement = 1_000 - min(1_000, dispersion)
    return min(1_000, base + agreement * (1_000 - base) // 2_000)


def _level(
    *,
    observation_count: int,
    confidence_milli: int,
    policy: EmergentPricePolicy,
) -> PriceExpectationLevel:
    if observation_count == 0:
        return PriceExpectationLevel.NONE
    if observation_count < policy.expected_min_observations:
        return PriceExpectationLevel.WEAK
    if confidence_milli >= policy.strong_min_confidence_milli:
        return PriceExpectationLevel.STRONG
    return PriceExpectationLevel.EXPECTED


def apply_emergent_price_update(
    *,
    owner_id: AgentId,
    tick: int,
    observations: tuple[PriceObservation, ...] = (),
    observed_quotes: tuple[PriceQuote, ...] = (),
    prior: EmergentPriceLedger | None,
    valuations: SubjectiveValuationLedger | None,
    acceptance: AcceptanceMemoryLedger | None,
    policy: EmergentPricePolicy | None = None,
) -> EmergentPriceLedger:
    """Materialize one owner's price expectations from own evidence only."""

    owner = _require_owner_id(owner_id)
    current_tick = _require_tick(tick)
    active = _DEFAULT_POLICY if policy is None else _require_policy(policy)
    if prior is not None:
        if type(prior) is not EmergentPriceLedger:
            raise TypeError("prior must be EmergentPriceLedger or None")
        if prior.owner_id != owner:
            _fail("price_invalid_identifier")
    if isinstance(observations, (str, bytes)) or not isinstance(observations, Sequence):
        _fail("price_invalid_identifier")
    if isinstance(observed_quotes, (str, bytes)) or not isinstance(
        observed_quotes, Sequence
    ):
        _fail("price_invalid_identifier")
    for observation in observations:
        if type(observation) is not PriceObservation:
            _fail("price_invalid_identifier")
    for quote in observed_quotes:
        if type(quote) is not PriceQuote:
            _fail("price_invalid_identifier")

    prior_rows = () if prior is None else prior.rows
    reservations = _valuation_reservations(valuations)
    notices: set[str] = set()
    if prior is not None:
        notices.update(prior.notices)

    unit_candidates = list(
        _unit_candidates(
            observations=observations,
            quotes=observed_quotes,
            reservations=reservations,
            references=_valuation_references(valuations),
            acceptance=acceptance,
            policy=active,
        )
    )
    prior_pairs: dict[tuple[ItemKind, ItemKind], PriceUnitSource] = {}
    for prior_row in prior_rows:
        if prior_row.unit_kind is None:
            continue
        prior_pairs.setdefault(
            (prior_row.item_kind, prior_row.unit_kind), prior_row.unit_source
        )
    seen_candidates = set(unit_candidates)
    for (pair_item, pair_unit), pair_source in sorted(
        prior_pairs.items(), key=lambda item: (item[0][0].value, item[0][1].value)
    ):
        if len(unit_candidates) >= active.max_units:
            break
        candidate = (pair_unit, pair_source)
        if candidate in seen_candidates:
            continue
        if pair_item is pair_unit:
            continue
        seen_candidates.add(candidate)
        unit_candidates.append(candidate)
    if not unit_candidates:
        notices.add("price_unit_unresolved")

    _SOURCE_RANK: Mapping[PriceUnitSource, int] = MappingProxyType(
        {
            PriceUnitSource.OWNER_REFERENCE: 0,
            PriceUnitSource.OBSERVED_MEDIUM: 1,
            PriceUnitSource.EXCHANGE_COUNTERPART: 2,
            PriceUnitSource.QUOTED: 3,
            PriceUnitSource.UNKNOWN: 4,
        }
    )
    preferred_units: dict[ItemKind, PriceUnitSource] = {}
    for candidate_unit, candidate_source in unit_candidates:
        current = preferred_units.get(candidate_unit)
        if current is None or _SOURCE_RANK[candidate_source] < _SOURCE_RANK[current]:
            preferred_units[candidate_unit] = candidate_source
    resolved_units = tuple(
        sorted(preferred_units.items(), key=lambda item: item[0].value)
    )

    rows: list[PriceExpectationRow] = []
    item_kinds = (
        {row.item_kind for row in observations}
        | {row.item_kind for row in observed_quotes}
        | {prior_row.item_kind for prior_row in prior_rows}
    )
    for item_kind in sorted(item_kinds, key=lambda kind: kind.value):
        item_reservation = reservations.get(item_kind, 0)
        for unit_kind, unit_source in resolved_units:
            if unit_kind is item_kind:
                continue
            prior_observations = tuple(
                row
                for prior_row in prior_rows
                if prior_row.item_kind is item_kind
                and prior_row.unit_kind is unit_kind
                for row in prior_row.observations
            )
            prior_quotes = tuple(
                row
                for prior_row in prior_rows
                if prior_row.item_kind is item_kind
                and prior_row.unit_kind is unit_kind
                for row in prior_row.quotes
            )
            merged_observations = _merge_observations(
                prior_observations,
                tuple(
                    row
                    for row in observations
                    if row.item_kind is item_kind and row.unit_kind is unit_kind
                ),
                item_kind=item_kind,
                unit_kind=unit_kind,
                policy=active,
            )
            merged_quotes = _merge_quotes(
                prior_quotes,
                tuple(
                    row
                    for row in observed_quotes
                    if row.item_kind is item_kind and row.unit_kind is unit_kind
                ),
                item_kind=item_kind,
                unit_kind=unit_kind,
                policy=active,
            )
            evidence_keys = {
                row.source_tick
                for row in (*prior_observations, *observations)
                if row.item_kind is item_kind and row.unit_kind is unit_kind
            }
            if len(evidence_keys) > active.max_observations_per_row:
                notices.add("price_ledger_truncated")
            quote_keys = {
                (row.venue_id, row.direction, row.source_tick)
                for row in (*prior_quotes, *observed_quotes)
                if row.item_kind is item_kind and row.unit_kind is unit_kind
            }
            if len(quote_keys) > active.max_quotes_per_row:
                notices.add("price_ledger_truncated")
            samples: list[tuple[int, int]] = []
            ratios: list[int] = []
            if reservations.get(unit_kind) == 1 and item_kind in reservations:
                valuation_ratio = min(
                    active.ratio_max_milli, item_reservation * 1_000
                )
                samples.append((valuation_ratio, 1))
                ratios.append(valuation_ratio)
            for observation in merged_observations:
                if observation.observed_ratio_milli is None:
                    notices.add("price_evidence_unpaired")
                    continue
                weight = max(1, observation.exchange_count)
                samples.append((observation.observed_ratio_milli, weight))
                ratios.append(observation.observed_ratio_milli)
            for quote in merged_quotes:
                if quote.confidence_milli < active.quote_min_confidence_milli:
                    continue
                samples.append((quote.ratio_milli, 1))
                ratios.append(quote.ratio_milli)
            if not samples:
                continue
            expected = _weighted_lower_median(samples)
            contributing_quotes = sum(
                1
                for quote in merged_quotes
                if quote.confidence_milli >= active.quote_min_confidence_milli
            )
            confidence = _confidence(
                evidence=len(merged_observations) + contributing_quotes,
                ratios=ratios,
                policy=active,
            )
            ticks = [row.source_tick for row in merged_observations]
            ticks.extend(row.source_tick for row in merged_quotes)
            first_tick = min(ticks)
            last_tick = max(ticks)
            level = _level(
                observation_count=len(merged_observations),
                confidence_milli=confidence,
                policy=active,
            )
            if level is PriceExpectationLevel.STRONG and any(
                quote.source is PriceQuoteSource.COMMUNICATED
                for quote in merged_quotes
            ):
                level = PriceExpectationLevel.EXPECTED
            rows.append(
                PriceExpectationRow(
                    item_kind=item_kind,
                    unit_kind=unit_kind,
                    unit_source=unit_source,
                    expected_ratio_milli=expected,
                    confidence_milli=confidence,
                    level=level,
                    valuation_reservation=item_reservation,
                    observation_count=len(merged_observations),
                    quote_count=len(merged_quotes),
                    first_tick=first_tick,
                    last_tick=last_tick,
                    observations=merged_observations,
                    quotes=merged_quotes,
                    row_id=price_belief_id(owner, item_kind, _unit_token(unit_kind)),
                )
            )

    valuation_ticks = _valuation_ticks(valuations)
    if (
        valuation_ticks
        and current_tick - max(valuation_ticks) > active.stale_after_ticks
    ):
        notices.add("price_valuation_stale")

    rows.sort(
        key=lambda row: (
            row.item_kind.value,
            _unit_token(row.unit_kind),
            row.unit_source.value,
        )
    )
    if len(rows) > active.max_rows:
        rows = rows[: active.max_rows]
        notices.add("price_ledger_truncated")
    ledger = EmergentPriceLedger(
        owner_id=owner,
        rows=tuple(rows),
        notices=tuple(sorted(notices)),
        policy_version=EMERGENT_PRICES_POLICY_VERSION,
    )
    validate_emergent_price_caps(ledger, active)
    _LOG.debug(
        "price_ledger_updated owner=<redacted> rows=%s truncated=%s",
        len(ledger.rows),
        "price_ledger_truncated" in ledger.notices,
    )
    return ledger
