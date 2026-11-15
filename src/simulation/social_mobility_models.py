"""Canonical sibling document for completed-run social mobility."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from world.identifiers import require_stable_id

__all__ = [
    "MAX_SOCIAL_MOBILITY_DOMAIN_ROWS",
    "MAX_SOCIAL_MOBILITY_GENERATION_ROWS",
    "MAX_SOCIAL_MOBILITY_LAG_ROWS",
    "MAX_SOCIAL_MOBILITY_SNAPSHOT_BYTES",
    "SOCIAL_MOBILITY_POLICY_VERSION",
    "SOCIAL_MOBILITY_PUBLICATION_PREFIX",
    "SOCIAL_MOBILITY_SNAPSHOT_VERSION",
    "SocialMobilityCoverageRecord",
    "SocialMobilityDomainRecord",
    "SocialMobilityGenerationRecord",
    "SocialMobilityLagRecord",
    "SocialMobilitySnapshot",
    "SocialMobilitySummaryRecord",
    "empty_social_mobility_snapshot",
]

SOCIAL_MOBILITY_SNAPSHOT_VERSION: Final[str] = "social-mobility-snapshot-v1"
SOCIAL_MOBILITY_POLICY_VERSION: Final[str] = "social-mobility.v1"
SOCIAL_MOBILITY_PUBLICATION_PREFIX: Final[str] = "socmob-pub-"
MAX_SOCIAL_MOBILITY_DOMAIN_ROWS: Final[int] = 4_096
MAX_SOCIAL_MOBILITY_GENERATION_ROWS: Final[int] = 1_024
MAX_SOCIAL_MOBILITY_LAG_ROWS: Final[int] = 2_048
MAX_SOCIAL_MOBILITY_SNAPSHOT_BYTES: Final[int] = 8_388_608
SOCIAL_MOBILITY_MAX_WINDOWS: Final[int] = 512

_DOMAINS = frozenset(
    {
        "resources",
        "skills",
        "social_influence",
        "organization_roles",
        "educational_access",
        "productive_assets",
    }
)
_MEASURES = frozenset(
    {
        "observed_resource_item_count",
        "known_technique_count",
        "inbound_communication_partner_count",
        "held_organization_role_count",
        "educational_access_receipt_count",
        "observed_productive_asset_count",
    }
)
_COVERAGE = frozenset({"complete", "partial", "missing"})
_AVAILABILITY = frozenset({"available", "insufficient_samples", "unavailable"})
_PERSISTENCE = frozenset(
    {"persistent", "mobile", "insufficient_samples", "unavailable"}
)


def _fail() -> ValueError:
    return ValueError("social_mobility_snapshot_invalid")


def _count(value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise _fail()
    return value


def _milli(value: object) -> int:
    number = _count(value)
    if number > 1_000:
        raise _fail()
    return number


def _signed_milli(value: object) -> int:
    if (
        isinstance(value, bool)
        or type(value) is not int
        or not -1_000 <= value <= 1_000
    ):
        raise _fail()
    return value


def _window(value: object) -> int:
    number = _count(value)
    if number >= SOCIAL_MOBILITY_MAX_WINDOWS:
        raise _fail()
    return number


def _enum(value: object, allowed: frozenset[str]) -> str:
    if type(value) is not str or value not in allowed:
        raise _fail()
    return value


def _bool(value: object) -> bool:
    if type(value) is not bool:
        raise _fail()
    return value


@dataclass(frozen=True, slots=True)
class SocialMobilitySummaryRecord:
    domain_row_count: int
    generation_row_count: int
    lag_row_count: int
    window_count: int
    owner_count: int
    generation_count: int
    genealogy_edge_count: int
    pair_count: int
    resolved_pair_count: int
    unresolved_pair_count: int
    domain_available_count: int
    coverage: str
    evidence_coverage: str
    domain_coverage: str
    generation_coverage: str
    truncated: bool

    def __post_init__(self) -> None:
        for name in (
            "domain_row_count",
            "generation_row_count",
            "lag_row_count",
            "window_count",
            "owner_count",
            "generation_count",
            "genealogy_edge_count",
            "pair_count",
            "resolved_pair_count",
            "unresolved_pair_count",
            "domain_available_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        if self.resolved_pair_count + self.unresolved_pair_count != self.pair_count:
            raise _fail()
        for name in (
            "coverage",
            "evidence_coverage",
            "domain_coverage",
            "generation_coverage",
        ):
            object.__setattr__(self, name, _enum(getattr(self, name), _COVERAGE))
        object.__setattr__(self, "truncated", _bool(self.truncated))


@dataclass(frozen=True, slots=True)
class SocialMobilityDomainRecord:
    window_index: int
    window_tick: int
    domain: str
    measure: str
    pair_count: int
    resolved_pair_count: int
    rank_correlation_milli: int
    same_bin_share_milli: int
    upward_share_milli: int
    downward_share_milli: int
    mean_absolute_rank_change_milli: int
    persistence_direction: str
    coverage: str
    availability: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_index", _window(self.window_index))
        object.__setattr__(self, "window_tick", _count(self.window_tick))
        object.__setattr__(self, "domain", _enum(self.domain, _DOMAINS))
        object.__setattr__(self, "measure", _enum(self.measure, _MEASURES))
        for name in ("pair_count", "resolved_pair_count"):
            object.__setattr__(self, name, _count(getattr(self, name)))
        if self.resolved_pair_count > self.pair_count:
            raise _fail()
        object.__setattr__(
            self, "rank_correlation_milli", _signed_milli(self.rank_correlation_milli)
        )
        for name in (
            "same_bin_share_milli",
            "upward_share_milli",
            "downward_share_milli",
            "mean_absolute_rank_change_milli",
        ):
            object.__setattr__(self, name, _milli(getattr(self, name)))
        for name in ("persistence_direction",):
            object.__setattr__(self, name, _enum(getattr(self, name), _PERSISTENCE))
        object.__setattr__(self, "coverage", _enum(self.coverage, _COVERAGE))
        object.__setattr__(
            self, "availability", _enum(self.availability, _AVAILABILITY)
        )


@dataclass(frozen=True, slots=True)
class SocialMobilityGenerationRecord:
    window_index: int
    window_tick: int
    generation_index: int
    owner_count: int
    pair_count: int
    comparable: bool
    same_bin_share_milli: int
    upward_share_milli: int
    downward_share_milli: int
    coverage: str
    availability: str

    def __post_init__(self) -> None:
        for name in ("window_index", "generation_index"):
            object.__setattr__(self, name, _window(getattr(self, name)))
        object.__setattr__(self, "window_tick", _count(self.window_tick))
        for name in ("owner_count", "pair_count"):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(self, "comparable", _bool(self.comparable))
        for name in (
            "same_bin_share_milli",
            "upward_share_milli",
            "downward_share_milli",
        ):
            object.__setattr__(self, name, _milli(getattr(self, name)))
        object.__setattr__(self, "coverage", _enum(self.coverage, _COVERAGE))
        object.__setattr__(
            self, "availability", _enum(self.availability, _AVAILABILITY)
        )


@dataclass(frozen=True, slots=True)
class SocialMobilityLagRecord:
    window_index: int
    window_tick: int
    generation_lag: int
    pair_count: int
    comparable: bool
    same_bin_share_milli: int
    upward_share_milli: int
    downward_share_milli: int
    coverage: str
    availability: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_index", _window(self.window_index))
        object.__setattr__(self, "window_tick", _count(self.window_tick))
        lag = _count(self.generation_lag)
        if not 1 <= lag <= 4:
            raise _fail()
        object.__setattr__(self, "pair_count", _count(self.pair_count))
        object.__setattr__(self, "comparable", _bool(self.comparable))
        for name in (
            "same_bin_share_milli",
            "upward_share_milli",
            "downward_share_milli",
        ):
            object.__setattr__(self, name, _milli(getattr(self, name)))
        object.__setattr__(self, "coverage", _enum(self.coverage, _COVERAGE))
        object.__setattr__(
            self, "availability", _enum(self.availability, _AVAILABILITY)
        )


@dataclass(frozen=True, slots=True)
class SocialMobilityCoverageRecord:
    window_index: int
    window_tick: int
    generation_count: int
    owner_count: int
    genealogy_edge_count: int
    pair_count: int
    resolved_pair_count: int
    unresolved_pair_count: int
    domain_available_count: int
    truncated: bool
    coverage: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_index", _window(self.window_index))
        object.__setattr__(self, "window_tick", _count(self.window_tick))
        for name in (
            "generation_count",
            "owner_count",
            "genealogy_edge_count",
            "pair_count",
            "resolved_pair_count",
            "unresolved_pair_count",
            "domain_available_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        if self.resolved_pair_count + self.unresolved_pair_count != self.pair_count:
            raise _fail()
        object.__setattr__(self, "truncated", _bool(self.truncated))
        object.__setattr__(self, "coverage", _enum(self.coverage, _COVERAGE))


@dataclass(frozen=True, slots=True)
class SocialMobilitySnapshot:
    run_id: str
    schema_version: str
    policy_version: str
    summary: SocialMobilitySummaryRecord
    domains: tuple[SocialMobilityDomainRecord, ...] = ()
    generations: tuple[SocialMobilityGenerationRecord, ...] = ()
    lags: tuple[SocialMobilityLagRecord, ...] = ()
    coverage: tuple[SocialMobilityCoverageRecord, ...] = ()
    digest: str = ""
    publication_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", require_stable_id("run_id", self.run_id))
        if self.schema_version != SOCIAL_MOBILITY_SNAPSHOT_VERSION:
            raise ValueError("social_mobility_snapshot_version")
        if self.policy_version != SOCIAL_MOBILITY_POLICY_VERSION:
            raise ValueError("social_mobility_snapshot_version")
        if type(self.summary) is not SocialMobilitySummaryRecord:
            raise _fail()
        for name, row_type, cap, identity in (
            (
                "domains",
                SocialMobilityDomainRecord,
                MAX_SOCIAL_MOBILITY_DOMAIN_ROWS,
                lambda row: (str(row.window_index), row.domain),
            ),
            (
                "generations",
                SocialMobilityGenerationRecord,
                MAX_SOCIAL_MOBILITY_GENERATION_ROWS,
                lambda row: (str(row.window_index), str(row.generation_index)),
            ),
            (
                "lags",
                SocialMobilityLagRecord,
                MAX_SOCIAL_MOBILITY_LAG_ROWS,
                lambda row: (str(row.window_index), str(row.generation_lag)),
            ),
            (
                "coverage",
                SocialMobilityCoverageRecord,
                1,
                lambda row: (str(row.window_index),),
            ),
        ):
            values = getattr(self, name)
            if type(values) is not tuple or len(values) > cap:
                raise _fail()
            seen: set[tuple[str, ...]] = set()
            for row in values:
                if type(row) is not row_type:
                    raise _fail()
                key = identity(row)
                if key in seen:
                    raise _fail()
                seen.add(key)
        if type(self.digest) is not str or type(self.publication_id) is not str:
            raise _fail()


def empty_social_mobility_snapshot(run_id: str) -> SocialMobilitySnapshot:
    """Return one empty missing-coverage snapshot."""

    return SocialMobilitySnapshot(
        run_id=run_id,
        schema_version=SOCIAL_MOBILITY_SNAPSHOT_VERSION,
        policy_version=SOCIAL_MOBILITY_POLICY_VERSION,
        summary=SocialMobilitySummaryRecord(
            domain_row_count=0,
            generation_row_count=0,
            lag_row_count=0,
            window_count=0,
            owner_count=0,
            generation_count=0,
            genealogy_edge_count=0,
            pair_count=0,
            resolved_pair_count=0,
            unresolved_pair_count=0,
            domain_available_count=0,
            coverage="missing",
            evidence_coverage="missing",
            domain_coverage="missing",
            generation_coverage="missing",
            truncated=False,
        ),
    )
