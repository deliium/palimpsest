"""Closed measure vocabulary for societal-resilience time series."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from analysis.resilience_windows import (
    WindowCoverage,
    WindowReason,
    WindowSpec,
)

__all__ = [
    "RESILIENCE_DIMENSION_ORDER",
    "Measure",
    "MeasureScope",
    "OwnerCoverage",
    "ResilienceDimension",
    "SeriesCell",
    "SeriesPanel",
    "floor_milli",
    "measure_delta",
    "sort_measures",
]

RESILIENCE_DIMENSION_ORDER: Final[tuple[str, ...]] = (
    "population_recovery",
    "migration",
    "resource_recovery",
    "institution_continuity",
    "knowledge_retention",
    "technology_loss",
    "cooperation",
    "inequality",
    "trade_network_recovery",
    "infrastructure_recovery",
)


class ResilienceDimension(StrEnum):
    """Fixed ten-lane order; never a composite score."""

    POPULATION_RECOVERY = "population_recovery"
    MIGRATION = "migration"
    RESOURCE_RECOVERY = "resource_recovery"
    INSTITUTION_CONTINUITY = "institution_continuity"
    KNOWLEDGE_RETENTION = "knowledge_retention"
    TECHNOLOGY_LOSS = "technology_loss"
    COOPERATION = "cooperation"
    INEQUALITY = "inequality"
    TRADE_NETWORK_RECOVERY = "trade_network_recovery"
    INFRASTRUCTURE_RECOVERY = "infrastructure_recovery"


@dataclass(frozen=True, slots=True)
class MeasureScope:
    """Optional typed scope leaf; never arbitrary labels."""

    kind: str
    key: str

    def __post_init__(self) -> None:
        if type(self.kind) is not str or not self.kind:
            raise ValueError("resilience_scope_invalid")
        if type(self.key) is not str or not self.key:
            raise ValueError("resilience_scope_invalid")


@dataclass(frozen=True, slots=True)
class Measure:
    """One typed integer/null measure with optional baseline delta."""

    metric: str
    unit: str
    value: int | None
    scope: MeasureScope | None = None
    numerator: int | None = None
    denominator: int | None = None
    delta_from_baseline: int | None = None
    reason: str | None = None
    delta_reason: str | None = None

    def __post_init__(self) -> None:
        if type(self.metric) is not str or not self.metric:
            raise ValueError("resilience_measure_invalid")
        if type(self.unit) is not str or not self.unit:
            raise ValueError("resilience_measure_invalid")
        for name in (
            "value",
            "numerator",
            "denominator",
            "delta_from_baseline",
        ):
            raw = getattr(self, name)
            if raw is None:
                continue
            if isinstance(raw, bool) or type(raw) is not int:
                raise ValueError("resilience_measure_invalid")
        if self.scope is not None and type(self.scope) is not MeasureScope:
            raise ValueError("resilience_measure_invalid")


@dataclass(frozen=True, slots=True)
class OwnerCoverage:
    """Owner-lane coverage metadata; never a numerical measure."""

    eligible_owners: int
    observed_owners: int

    def __post_init__(self) -> None:
        for name in ("eligible_owners", "observed_owners"):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise ValueError("resilience_owner_coverage_invalid")
        if self.observed_owners > self.eligible_owners:
            raise ValueError("resilience_owner_coverage_invalid")


@dataclass(frozen=True, slots=True)
class SeriesCell:
    """One aligned window or immediate cell for a single dimension."""

    window_index: int | None
    status: WindowCoverage
    reason: WindowReason | None
    expected_ticks: int
    observed_ticks: int
    measures: tuple[Measure, ...]
    owner_coverage: OwnerCoverage | None = None

    def __post_init__(self) -> None:
        if self.window_index is not None and (
            isinstance(self.window_index, bool) or type(self.window_index) is not int
        ):
            raise ValueError("resilience_cell_invalid")
        if type(self.status) is not WindowCoverage:
            raise ValueError("resilience_cell_invalid")
        if self.reason is not None and type(self.reason) is not WindowReason:
            raise ValueError("resilience_cell_invalid")
        if type(self.measures) is not tuple:
            raise ValueError("resilience_cell_invalid")


@dataclass(frozen=True, slots=True)
class SeriesPanel:
    """Nine window cells plus optional immediate cell for one dimension."""

    dimension: ResilienceDimension
    windows: tuple[SeriesCell, ...]
    immediate: SeriesCell | None = None

    def __post_init__(self) -> None:
        if type(self.dimension) is not ResilienceDimension:
            raise ValueError("resilience_panel_invalid")
        if len(self.windows) != 9:
            raise ValueError("resilience_panel_invalid")


def floor_milli(numerator: int, denominator: int) -> int | None:
    """Nonnegative milli ratio; null at zero denominator."""

    if isinstance(numerator, bool) or type(numerator) is not int or numerator < 0:
        raise ValueError("resilience_ratio_invalid")
    if (
        isinstance(denominator, bool)
        or type(denominator) is not int
        or denominator < 0
    ):
        raise ValueError("resilience_ratio_invalid")
    if denominator == 0:
        return None
    return (1000 * numerator) // denominator


def measure_delta(
    current: int | None, baseline: int | None, *, allowed: bool
) -> int | None:
    """Signed current-minus-baseline when both sides and allowance qualify."""

    if not allowed or current is None or baseline is None:
        return None
    return current - baseline


def sort_measures(measures: tuple[Measure, ...]) -> tuple[Measure, ...]:
    """Stable metric then scope-key ordering."""

    return tuple(
        sorted(
            measures,
            key=lambda item: (
                item.metric,
                "" if item.scope is None else item.scope.kind,
                "" if item.scope is None else item.scope.key,
            ),
        )
    )


def cell_from_window(
    window: WindowSpec,
    *,
    measures: tuple[Measure, ...],
    owner_coverage: OwnerCoverage | None = None,
) -> SeriesCell:
    """Lift a WindowSpec into a SeriesCell with sorted measures."""

    return SeriesCell(
        window_index=window.index,
        status=window.coverage,
        reason=window.reason,
        expected_ticks=window.expected_ticks,
        observed_ticks=window.observed_ticks,
        measures=sort_measures(measures),
        owner_coverage=owner_coverage,
    )
