"""Quantized inequality indices and deterministic distribution summaries.

Gini delegates to the existing ``resource_inequality`` formula and quantization
so the new dimension families cannot drift from established output. Theil T,
Atkinson eps=1, and top-share use the same quantized input. Every index is
reported as an integer milli value in ``0..1000``; no float payload escapes.

Nearest-rank quantiles are used. With fewer than ``min_samples`` observed values
the summary keeps its sample count but invents no quantile, index, or share.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Final

from analysis.economic_inequality_contract import (
    EconomicInequalityAvailability,
    EconomicInequalityError,
)
from analysis.objective_metrics import resource_inequality_gini

__all__ = [
    "InequalityDistributionSummary",
    "inequality_bin_shares_milli",
    "inequality_distribution_summary",
    "quantized_atkinson_eps_1",
    "quantized_gini",
    "quantized_theil_t",
    "quantized_top_share",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.economic_inequality.indices"
)

_MILLI: Final[int] = 1_000


@dataclass(frozen=True, slots=True)
class InequalityDistributionSummary:
    """Descriptive distribution; never a wealth claim or rank."""

    status: EconomicInequalityAvailability
    sample_count: int
    minimum: int | None
    p25: int | None
    median: int | None
    p75: int | None
    maximum: int | None
    iqr: int | None
    dispersion: int | None
    bin_shares_milli: tuple[int, ...]

    def __post_init__(self) -> None:
        if type(self.status) is not EconomicInequalityAvailability:
            raise EconomicInequalityError("economic_inequality_invalid_row")
        if (
            isinstance(self.sample_count, bool)
            or type(self.sample_count) is not int
            or self.sample_count < 0
        ):
            raise EconomicInequalityError("economic_inequality_invalid_row")
        for name in ("minimum", "p25", "median", "p75", "maximum", "iqr", "dispersion"):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or type(value) is not int or value < 0
            ):
                raise EconomicInequalityError("economic_inequality_invalid_row")
        if (
            isinstance(self.bin_shares_milli, (str, bytes))
            or not isinstance(self.bin_shares_milli, tuple)
            or len(self.bin_shares_milli) != 5
        ):
            raise EconomicInequalityError("economic_inequality_invalid_row")
        for share in self.bin_shares_milli:
            if (
                isinstance(share, bool)
                or type(share) is not int
                or not 0 <= share <= _MILLI
            ):
                raise EconomicInequalityError("economic_inequality_invalid_row")


def _values(values: object) -> tuple[int, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise EconomicInequalityError("economic_inequality_invalid_input")
    normalized: list[int] = []
    for value in values:
        if isinstance(value, bool) or type(value) is not int or value < 0:
            raise EconomicInequalityError("economic_inequality_invalid_input")
        normalized.append(value)
    return tuple(normalized)


def _nearest_rank(ordered: tuple[int, ...], numerator: int, denominator: int) -> int:
    rank = math.ceil(numerator * len(ordered) / denominator)
    return ordered[max(0, min(rank - 1, len(ordered) - 1))]


def inequality_bin_shares_milli(
    ordered: tuple[int, ...],
) -> tuple[int, int, int, int, int]:
    """Five equal-width bin shares in integer milli using largest remainder."""

    if not ordered:
        return (0, 0, 0, 0, 0)
    low = ordered[0]
    high = ordered[-1]
    if high == low:
        return (0, 0, 0, 0, 0) if high == 0 else (_MILLI, 0, 0, 0, 0)
    span = high - low
    counts = [0, 0, 0, 0, 0]
    for value in ordered:
        index = min(4, ((value - low) * 5) // (span + 1))
        counts[index] += 1
    total = len(ordered)
    exact = [count * _MILLI / total for count in counts]
    floors = [int(value) for value in exact]
    remainder = _MILLI - sum(floors)
    order = sorted(
        range(5), key=lambda index: (-(exact[index] - floors[index]), index)
    )
    for index in order[:remainder]:
        floors[index] += 1
    return (floors[0], floors[1], floors[2], floors[3], floors[4])


def _milli(value: float) -> int:
    if not math.isfinite(value):
        raise EconomicInequalityError("economic_inequality_non_finite")
    return max(0, min(_MILLI, round(value * _MILLI)))


def quantized_gini(values: object) -> int:
    """Quantized Gini in integer milli; delegates to the shared formula."""

    vector = _values(values)
    if not vector:
        raise EconomicInequalityError("economic_inequality_empty_vector")
    return _milli(resource_inequality_gini([float(value) for value in vector]))


def quantized_theil_t(values: object) -> int:
    """Quantized Theil T in integer milli, clamped to the closed range."""

    vector = _values(values)
    if not vector:
        raise EconomicInequalityError("economic_inequality_empty_vector")
    total = sum(vector)
    if total == 0:
        return 0
    mean = total / len(vector)
    contribution = 0.0
    for value in vector:
        if value <= 0:
            continue
        ratio = value / mean
        contribution += ratio * math.log(ratio)
    return _milli(contribution / len(vector))


def quantized_atkinson_eps_1(values: object) -> int:
    """Quantized Atkinson eps=1 in integer milli."""

    vector = _values(values)
    if not vector:
        raise EconomicInequalityError("economic_inequality_empty_vector")
    if max(vector) == 0:
        return 0
    if min(vector) <= 0:
        return _MILLI
    mean = sum(vector) / len(vector)
    geometric = math.exp(
        sum(math.log(value) for value in vector) / len(vector)
    )
    return _milli(1.0 - geometric / mean)


def quantized_top_share(values: object) -> int:
    """Quantized maximum share of the total in integer milli."""

    vector = _values(values)
    if not vector:
        raise EconomicInequalityError("economic_inequality_empty_vector")
    total = sum(vector)
    if total == 0:
        return 0
    return _milli(max(vector) / total)


def inequality_distribution_summary(
    values: object,
    *,
    min_samples: int = 4,
) -> InequalityDistributionSummary:
    """Return the nearest-rank distribution summary for ``values``."""

    vector = _values(values)
    if isinstance(min_samples, bool) or type(min_samples) is not int or min_samples < 1:
        raise EconomicInequalityError("economic_inequality_invalid_input")
    if not vector:
        return InequalityDistributionSummary(
            status=EconomicInequalityAvailability.UNAVAILABLE,
            sample_count=0,
            minimum=None,
            p25=None,
            median=None,
            p75=None,
            maximum=None,
            iqr=None,
            dispersion=None,
            bin_shares_milli=(0, 0, 0, 0, 0),
        )
    ordered = tuple(sorted(vector))
    if len(ordered) < min_samples:
        return InequalityDistributionSummary(
            status=EconomicInequalityAvailability.INSUFFICIENT_SAMPLES,
            sample_count=len(ordered),
            minimum=None,
            p25=None,
            median=None,
            p75=None,
            maximum=None,
            iqr=None,
            dispersion=None,
            bin_shares_milli=(0, 0, 0, 0, 0),
        )
    minimum = ordered[0]
    p25 = _nearest_rank(ordered, 1, 4)
    median = _nearest_rank(ordered, 1, 2)
    p75 = _nearest_rank(ordered, 3, 4)
    maximum = ordered[-1]
    return InequalityDistributionSummary(
        status=EconomicInequalityAvailability.AVAILABLE,
        sample_count=len(ordered),
        minimum=minimum,
        p25=p25,
        median=median,
        p75=p75,
        maximum=maximum,
        iqr=p75 - p25,
        dispersion=maximum - minimum,
        bin_shares_milli=inequality_bin_shares_milli(ordered),
    )
