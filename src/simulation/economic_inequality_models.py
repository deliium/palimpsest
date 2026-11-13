"""Canonical sibling document for completed-run economic inequality."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from world.identifiers import require_stable_id

__all__ = [
    "ECONOMIC_INEQUALITY_POLICY_VERSION",
    "ECONOMIC_INEQUALITY_PUBLICATION_PREFIX",
    "ECONOMIC_INEQUALITY_SNAPSHOT_VERSION",
    "MAX_ECONOMIC_INEQUALITY_COHORT_ROWS",
    "MAX_ECONOMIC_INEQUALITY_DIMENSION_ROWS",
    "MAX_ECONOMIC_INEQUALITY_SNAPSHOT_BYTES",
    "MAX_ECONOMIC_INEQUALITY_SOCIETY_ROWS",
    "EconomicCohortRecord",
    "EconomicDimensionRecord",
    "EconomicInequalitySnapshot",
    "EconomicInequalitySummaryRecord",
    "EconomicSocietyRecord",
    "empty_economic_inequality_snapshot",
]

ECONOMIC_INEQUALITY_SNAPSHOT_VERSION: Final[str] = "economic-inequality-snapshot-v1"
ECONOMIC_INEQUALITY_POLICY_VERSION: Final[str] = "economic-inequality.v1"
ECONOMIC_INEQUALITY_PUBLICATION_PREFIX: Final[str] = "econ-pub-"
MAX_ECONOMIC_INEQUALITY_DIMENSION_ROWS: Final[int] = 4_096
MAX_ECONOMIC_INEQUALITY_COHORT_ROWS: Final[int] = 1_024
MAX_ECONOMIC_INEQUALITY_SOCIETY_ROWS: Final[int] = 2_048
MAX_ECONOMIC_INEQUALITY_SNAPSHOT_BYTES: Final[int] = 8_388_608
ECONOMIC_INEQUALITY_MAX_WINDOWS: Final[int] = 512

_DIMENSIONS = frozenset(
    {
        "resource_possession",
        "productive_tool_access",
        "infrastructure_access",
        "storage_access",
        "credit_relationship",
        "organizational_resource_control",
    }
)
_MEASURES = frozenset(
    {
        "observed_item_count",
        "observed_tool_count",
        "accessible_infrastructure_count",
        "accessible_storage_count",
        "claimed_principal_quantity",
        "observed_repayment_quantity",
        "claimed_relationship_count",
        "claimed_resource_control_count",
        "claimed_storage_control_count",
    }
)
_COVERAGE = frozenset({"complete", "partial", "missing"})
_AVAILABILITY = frozenset(
    {"available", "insufficient_samples", "unavailable"}
)
_TRENDS = frozenset(
    {"rising", "falling", "stable", "insufficient_samples", "unavailable"}
)


def _fail() -> ValueError:
    return ValueError("economic_inequality_snapshot_invalid")


def _count(value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise _fail()
    return value


def _optional_count(value: object) -> int | None:
    if value is None:
        return None
    return _count(value)


def _token(value: object) -> str:
    if type(value) is not str or not value:
        raise _fail()
    return require_stable_id("token", value)


def _window(value: object) -> int:
    number = _count(value)
    if number >= ECONOMIC_INEQUALITY_MAX_WINDOWS:
        raise _fail()
    return number


def _enum(value: object, allowed: frozenset[str]) -> str:
    if type(value) is not str or value not in allowed:
        raise _fail()
    return value


def _shares(value: object) -> tuple[int, ...]:
    if type(value) is not tuple or len(value) != 5:
        raise _fail()
    for share in value:
        if _count(share) > 1_000:
            raise _fail()
    return value


@dataclass(frozen=True, slots=True)
class EconomicInequalitySummaryRecord:
    dimension_row_count: int
    cohort_row_count: int
    society_row_count: int
    window_count: int
    owner_count: int
    observed_owner_count: int
    overlap_member_count: int
    coverage: str
    evidence_coverage: str
    dimension_coverage: str
    comparison_coverage: str
    truncated: bool

    def __post_init__(self) -> None:
        for name in (
            "dimension_row_count",
            "cohort_row_count",
            "society_row_count",
            "window_count",
            "owner_count",
            "observed_owner_count",
            "overlap_member_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        for name in (
            "coverage",
            "evidence_coverage",
            "dimension_coverage",
            "comparison_coverage",
        ):
            object.__setattr__(self, name, _enum(getattr(self, name), _COVERAGE))
        if type(self.truncated) is not bool:
            raise _fail()


@dataclass(frozen=True, slots=True)
class EconomicDimensionRecord:
    dimension: str
    measure: str
    window_index: int
    window_tick: int
    owner_count: int
    observed_owner_count: int
    minimum: int | None
    p25: int | None
    median: int | None
    p75: int | None
    maximum: int | None
    iqr: int | None
    dispersion: int | None
    bin_shares_milli: tuple[int, ...]
    gini_milli: int | None
    theil_t_milli: int | None
    atkinson_eps_1_milli: int | None
    top_share_milli: int | None
    availability: str
    coverage: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "dimension", _enum(self.dimension, _DIMENSIONS))
        object.__setattr__(self, "measure", _enum(self.measure, _MEASURES))
        object.__setattr__(self, "window_index", _window(self.window_index))
        object.__setattr__(self, "window_tick", _count(self.window_tick))
        for name in ("owner_count", "observed_owner_count"):
            object.__setattr__(self, name, _count(getattr(self, name)))
        for name in (
            "minimum",
            "p25",
            "median",
            "p75",
            "maximum",
            "iqr",
            "dispersion",
            "gini_milli",
            "theil_t_milli",
            "atkinson_eps_1_milli",
            "top_share_milli",
        ):
            object.__setattr__(self, name, _optional_count(getattr(self, name)))
        object.__setattr__(
            self, "bin_shares_milli", _shares(self.bin_shares_milli)
        )
        object.__setattr__(
            self, "availability", _enum(self.availability, _AVAILABILITY)
        )
        object.__setattr__(self, "coverage", _enum(self.coverage, _COVERAGE))


@dataclass(frozen=True, slots=True)
class EconomicCohortRecord:
    cohort_token: str
    generation_index: int
    window_index: int
    owner_count: int
    comparable: bool
    gini_milli: int | None
    median_milli: int | None
    iqr_milli: int | None
    trend: str
    availability: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "cohort_token", _token(self.cohort_token))
        for name in ("generation_index", "window_index", "owner_count"):
            object.__setattr__(self, name, _count(getattr(self, name)))
        if type(self.comparable) is not bool:
            raise _fail()
        for name in ("gini_milli", "median_milli", "iqr_milli"):
            object.__setattr__(self, name, _optional_count(getattr(self, name)))
        object.__setattr__(self, "trend", _enum(self.trend, _TRENDS))
        object.__setattr__(
            self, "availability", _enum(self.availability, _AVAILABILITY)
        )


@dataclass(frozen=True, slots=True)
class EconomicSocietyRecord:
    society_token: str
    window_index: int
    owner_count: int
    comparable: bool
    gini_milli: int | None
    median_milli: int | None
    iqr_milli: int | None
    trend: str
    availability: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "society_token", _token(self.society_token))
        for name in ("window_index", "owner_count"):
            object.__setattr__(self, name, _count(getattr(self, name)))
        if type(self.comparable) is not bool:
            raise _fail()
        for name in ("gini_milli", "median_milli", "iqr_milli"):
            object.__setattr__(self, name, _optional_count(getattr(self, name)))
        object.__setattr__(self, "trend", _enum(self.trend, _TRENDS))
        object.__setattr__(
            self, "availability", _enum(self.availability, _AVAILABILITY)
        )


@dataclass(frozen=True, slots=True)
class EconomicInequalitySnapshot:
    run_id: str
    schema_version: str
    policy_version: str
    summary: EconomicInequalitySummaryRecord
    dimensions: tuple[EconomicDimensionRecord, ...] = ()
    cohorts: tuple[EconomicCohortRecord, ...] = ()
    societies: tuple[EconomicSocietyRecord, ...] = ()
    digest: str = ""
    publication_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", require_stable_id("run_id", self.run_id))
        if self.schema_version != ECONOMIC_INEQUALITY_SNAPSHOT_VERSION:
            raise ValueError("economic_inequality_snapshot_version")
        if self.policy_version != ECONOMIC_INEQUALITY_POLICY_VERSION:
            raise ValueError("economic_inequality_snapshot_version")
        if type(self.summary) is not EconomicInequalitySummaryRecord:
            raise _fail()
        for name, row_type, cap in (
            (
                "dimensions",
                EconomicDimensionRecord,
                MAX_ECONOMIC_INEQUALITY_DIMENSION_ROWS,
            ),
            (
                "cohorts",
                EconomicCohortRecord,
                MAX_ECONOMIC_INEQUALITY_COHORT_ROWS,
            ),
            (
                "societies",
                EconomicSocietyRecord,
                MAX_ECONOMIC_INEQUALITY_SOCIETY_ROWS,
            ),
        ):
            values = getattr(self, name)
            if type(values) is not tuple or len(values) > cap:
                raise _fail()
            seen: set[tuple[str, ...]] = set()
            for row in values:
                if type(row) is not row_type:
                    raise _fail()
                identity: tuple[str, ...]
                if isinstance(row, EconomicDimensionRecord):
                    identity = (
                        row.dimension,
                        str(row.window_index),
                        row.measure,
                    )
                elif isinstance(row, EconomicCohortRecord):
                    identity = (row.cohort_token, str(row.window_index))
                else:
                    identity = (row.society_token, str(row.window_index))
                if identity in seen:
                    raise _fail()
                seen.add(identity)
        if type(self.digest) is not str or type(self.publication_id) is not str:
            raise _fail()


def empty_economic_inequality_snapshot(
    run_id: str,
) -> EconomicInequalitySnapshot:
    """Return one empty missing-coverage snapshot."""

    return EconomicInequalitySnapshot(
        run_id=run_id,
        schema_version=ECONOMIC_INEQUALITY_SNAPSHOT_VERSION,
        policy_version=ECONOMIC_INEQUALITY_POLICY_VERSION,
        summary=EconomicInequalitySummaryRecord(
            dimension_row_count=0,
            cohort_row_count=0,
            society_row_count=0,
            window_count=0,
            owner_count=0,
            observed_owner_count=0,
            overlap_member_count=0,
            coverage="missing",
            evidence_coverage="missing",
            dimension_coverage="missing",
            comparison_coverage="missing",
            truncated=False,
        ),
    )
