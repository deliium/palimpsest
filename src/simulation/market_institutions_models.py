"""Canonical bounded ``market-institutions-snapshot-v1`` models and caps."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "MARKET_INSTITUTIONS_ARTIFACT_MAX_BYTES",
    "MARKET_INSTITUTIONS_MAX_GATHERINGS",
    "MARKET_INSTITUTIONS_MAX_LINEAGE",
    "MARKET_INSTITUTIONS_MAX_MARKETS",
    "MARKET_INSTITUTIONS_MAX_RECORDS",
    "MARKET_INSTITUTIONS_MAX_ROLES",
    "MARKET_INSTITUTIONS_MAX_VENUES",
    "MARKET_INSTITUTIONS_MAX_WINDOWS",
    "MARKET_INSTITUTIONS_PUBLICATION_PREFIX",
    "MARKET_INSTITUTIONS_SNAPSHOT_POLICY",
    "MARKET_INSTITUTIONS_SNAPSHOT_VERSION",
    "MarketCandidateRecord",
    "MarketExpectationRecord",
    "MarketGatheringRecord",
    "MarketInstitutionsSnapshot",
    "MarketInstitutionsSummaryRecord",
    "MarketLineageRecord",
    "MarketRecordAnchorRecord",
    "MarketRoleRecord",
    "MarketVenueRecord",
    "empty_market_institutions_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.market_institutions_models"
)

MARKET_INSTITUTIONS_SNAPSHOT_VERSION: Final[str] = "market-institutions-snapshot-v1"
MARKET_INSTITUTIONS_SNAPSHOT_POLICY: Final[str] = "market-institutions.v1"
MARKET_INSTITUTIONS_PUBLICATION_PREFIX: Final[str] = "mkt-pub-"

MARKET_INSTITUTIONS_MAX_VENUES: Final[int] = 4_096
MARKET_INSTITUTIONS_MAX_GATHERINGS: Final[int] = 4_096
MARKET_INSTITUTIONS_MAX_EXPECTATIONS: Final[int] = 2_048
MARKET_INSTITUTIONS_MAX_ROLES: Final[int] = 2_048
MARKET_INSTITUTIONS_MAX_RECORDS: Final[int] = 2_048
MARKET_INSTITUTIONS_MAX_MARKETS: Final[int] = 1_024
MARKET_INSTITUTIONS_MAX_LINEAGE: Final[int] = 16_384
MARKET_INSTITUTIONS_MAX_WINDOWS: Final[int] = 512
MARKET_INSTITUTIONS_ARTIFACT_MAX_BYTES: Final[int] = 8_388_608


def _count(value: object) -> int:
    return require_exact_nonneg_int("count", value)


def _token(value: object) -> str:
    if type(value) is not str or not value:
        raise ValueError("market_institutions_artifact_invalid")
    return require_stable_id("token", value)


def _coverage(value: object) -> str:
    token = getattr(value, "value", value)
    if token not in {"complete", "partial", "missing"}:
        raise ValueError("market_institutions_artifact_invalid")
    return token


@dataclass(frozen=True, slots=True)
class MarketVenueRecord:
    venue_id: str
    window_index: int
    location_id: str
    exchange_count: int
    proposal_count: int
    withdrawn_count: int
    distinct_party_count: int
    distinct_actor_count: int
    active_window_count: int
    recurrence_milli: int
    status: str
    market_like: bool
    coverage: str

    def __post_init__(self) -> None:
        _token(self.venue_id)
        for name in (
            "window_index",
            "exchange_count",
            "proposal_count",
            "withdrawn_count",
            "distinct_party_count",
            "distinct_actor_count",
            "active_window_count",
            "recurrence_milli",
        ):
            _count(getattr(self, name))
        if self.status not in {
            "single_gathering",
            "recurring_gathering",
            "market_like_persistent",
            "dormant",
        }:
            raise ValueError("market_institutions_artifact_invalid")
        if type(self.market_like) is not bool:
            raise ValueError("market_institutions_artifact_invalid")
        object.__setattr__(self, "coverage", _coverage(self.coverage))


@dataclass(frozen=True, slots=True)
class MarketGatheringRecord:
    venue_id: str
    window_index: int
    location_id: str
    exchange_count: int
    proposal_count: int
    withdrawn_count: int
    distinct_party_count: int
    status: str
    coverage: str

    def __post_init__(self) -> None:
        _token(self.venue_id)
        for name in (
            "window_index",
            "exchange_count",
            "proposal_count",
            "withdrawn_count",
            "distinct_party_count",
        ):
            _count(getattr(self, name))
        if self.status not in {"gathering", "below_threshold"}:
            raise ValueError("market_institutions_artifact_invalid")
        object.__setattr__(self, "coverage", _coverage(self.coverage))


@dataclass(frozen=True, slots=True)
class MarketExpectationRecord:
    venue_id: str
    window_index: int
    owner_token: str
    expectation: str
    cadence: str
    interval_ticks: int | None
    phase_tick: int | None
    schedule_window_index: int | None
    confidence_milli: int
    evidence_count: int
    alignment: str
    coverage: str

    def __post_init__(self) -> None:
        _token(self.venue_id)
        _token(self.owner_token)
        _count(self.window_index)
        for name in ("interval_ticks", "phase_tick", "schedule_window_index"):
            value = getattr(self, name)
            if value is not None:
                _count(value)
        _count(self.confidence_milli)
        if self.confidence_milli > 1_000:
            raise ValueError("market_institutions_artifact_invalid")
        _count(self.evidence_count)
        if self.alignment not in {
            "consistent",
            "unresolved",
            "inconsistent",
            "not_applicable",
        }:
            raise ValueError("market_institutions_artifact_invalid")
        object.__setattr__(self, "coverage", _coverage(self.coverage))


@dataclass(frozen=True, slots=True)
class MarketRoleRecord:
    venue_id: str
    window_index: int
    actor_token: str
    role_kind: str
    role_basis: str
    recognized: bool
    exchange_count: int
    counterparty_count: int
    active_window_count: int
    coverage: str

    def __post_init__(self) -> None:
        _token(self.venue_id)
        _token(self.actor_token)
        _count(self.window_index)
        if type(self.recognized) is not bool:
            raise ValueError("market_institutions_artifact_invalid")
        for name in ("exchange_count", "counterparty_count", "active_window_count"):
            _count(getattr(self, name))
        object.__setattr__(self, "coverage", _coverage(self.coverage))


@dataclass(frozen=True, slots=True)
class MarketRecordAnchorRecord:
    venue_id: str
    window_index: int
    record_kind: str
    anchor_token: str
    owner_row_count: int
    coverage: str

    def __post_init__(self) -> None:
        _token(self.venue_id)
        _token(self.anchor_token)
        _count(self.window_index)
        _count(self.owner_row_count)
        object.__setattr__(self, "coverage", _coverage(self.coverage))


@dataclass(frozen=True, slots=True)
class MarketCandidateRecord:
    market_id: str
    window_index: int
    venue_ids: tuple[str, ...]
    exchange_count: int
    distinct_party_count: int
    coverage: str

    def __post_init__(self) -> None:
        _token(self.market_id)
        _count(self.window_index)
        venue_ids = tuple(self.venue_ids)
        if not venue_ids:
            raise ValueError("market_institutions_artifact_invalid")
        for venue_id in venue_ids:
            _token(venue_id)
        object.__setattr__(self, "venue_ids", venue_ids)
        _count(self.exchange_count)
        _count(self.distinct_party_count)
        object.__setattr__(self, "coverage", _coverage(self.coverage))


@dataclass(frozen=True, slots=True)
class MarketLineageRecord:
    window_index: int
    market_id: str
    venue_ids: tuple[str, ...]
    party_count: int
    status: str
    previous_market_ids: tuple[str, ...]
    next_market_ids: tuple[str, ...]
    rerouted: bool
    sustained: bool
    coverage: str

    def __post_init__(self) -> None:
        _count(self.window_index)
        _token(self.market_id)
        venue_ids = tuple(self.venue_ids)
        for value in venue_ids:
            _token(value)
        object.__setattr__(self, "venue_ids", venue_ids)
        _count(self.party_count)
        if self.status not in {
            "emerged",
            "continued",
            "transformed",
            "split",
            "merge",
            "dissolved",
        }:
            raise ValueError("market_institutions_artifact_invalid")
        for name in ("previous_market_ids", "next_market_ids"):
            values = tuple(getattr(self, name))
            for value in values:
                _token(value)
            object.__setattr__(self, name, values)
        if type(self.rerouted) is not bool or type(self.sustained) is not bool:
            raise ValueError("market_institutions_artifact_invalid")
        object.__setattr__(self, "coverage", _coverage(self.coverage))


@dataclass(frozen=True, slots=True)
class MarketInstitutionsSummaryRecord:
    window_tick: int
    venue_count: int
    gathering_count: int
    market_like_venue_count: int
    recurring_venue_count: int
    expected_venue_count: int
    market_count: int
    expectation_row_count: int
    role_row_count: int
    record_anchor_count: int
    emerged_count: int
    continued_count: int
    transformed_count: int
    split_count: int
    merge_count: int
    dissolved_count: int
    sustained_market_count: int
    lineage_edge_count: int
    coverage: str
    truncated: bool

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            if name in {"coverage", "truncated"}:
                continue
            _count(getattr(self, name))
        object.__setattr__(self, "coverage", _coverage(self.coverage))
        if type(self.truncated) is not bool:
            raise ValueError("market_institutions_artifact_invalid")


@dataclass(frozen=True, slots=True)
class MarketInstitutionsSnapshot:
    run_id: str
    schema_version: str
    policy_version: str
    summary: MarketInstitutionsSummaryRecord
    venues: tuple[MarketVenueRecord, ...]
    gatherings: tuple[MarketGatheringRecord, ...]
    expectations: tuple[MarketExpectationRecord, ...]
    roles: tuple[MarketRoleRecord, ...]
    records: tuple[MarketRecordAnchorRecord, ...]
    markets: tuple[MarketCandidateRecord, ...]
    lineage: tuple[MarketLineageRecord, ...]
    digest: str = ""
    publication_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "run_id", require_stable_id("run_id", self.run_id)
        )
        if self.schema_version != MARKET_INSTITUTIONS_SNAPSHOT_VERSION:
            raise ValueError("market_institutions_artifact_version")
        if self.policy_version != MARKET_INSTITUTIONS_SNAPSHOT_POLICY:
            raise ValueError("market_institutions_artifact_version")
        if type(self.summary) is not MarketInstitutionsSummaryRecord:
            raise ValueError("market_institutions_artifact_invalid")
        for name, row_type, cap in (
            ("venues", MarketVenueRecord, MARKET_INSTITUTIONS_MAX_VENUES),
            ("gatherings", MarketGatheringRecord, MARKET_INSTITUTIONS_MAX_GATHERINGS),
            (
                "expectations",
                MarketExpectationRecord,
                MARKET_INSTITUTIONS_MAX_EXPECTATIONS,
            ),
            ("roles", MarketRoleRecord, MARKET_INSTITUTIONS_MAX_ROLES),
            ("records", MarketRecordAnchorRecord, MARKET_INSTITUTIONS_MAX_RECORDS),
            ("markets", MarketCandidateRecord, MARKET_INSTITUTIONS_MAX_MARKETS),
            ("lineage", MarketLineageRecord, MARKET_INSTITUTIONS_MAX_LINEAGE),
        ):
            values = getattr(self, name)
            if type(values) is not tuple:
                raise ValueError("market_institutions_artifact_invalid")
            if len(values) > cap:
                raise ValueError("market_institutions_artifact_cap_exceeded")
            for row in values:
                if type(row) is not row_type:
                    raise ValueError("market_institutions_artifact_invalid")
        if type(self.digest) is not str or type(self.publication_id) is not str:
            raise ValueError("market_institutions_artifact_invalid")


def empty_market_institutions_snapshot(
    run_id: str,
    *,
    digest: str = "",
    publication_id: str = "",
) -> MarketInstitutionsSnapshot:
    """Return one empty canonical snapshot."""

    return MarketInstitutionsSnapshot(
        run_id=run_id,
        schema_version=MARKET_INSTITUTIONS_SNAPSHOT_VERSION,
        policy_version=MARKET_INSTITUTIONS_SNAPSHOT_POLICY,
        summary=MarketInstitutionsSummaryRecord(
            window_tick=0,
            venue_count=0,
            gathering_count=0,
            market_like_venue_count=0,
            recurring_venue_count=0,
            expected_venue_count=0,
            market_count=0,
            expectation_row_count=0,
            role_row_count=0,
            record_anchor_count=0,
            emerged_count=0,
            continued_count=0,
            transformed_count=0,
            split_count=0,
            merge_count=0,
            dissolved_count=0,
            sustained_market_count=0,
            lineage_edge_count=0,
            coverage="missing",
            truncated=False,
        ),
        venues=(),
        gatherings=(),
        expectations=(),
        roles=(),
        records=(),
        markets=(),
        lineage=(),
        digest=digest,
        publication_id=publication_id,
    )
