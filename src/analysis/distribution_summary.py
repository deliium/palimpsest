"""Deterministic distribution and confidence-interval helpers.

Log-free. Callers log counts only. Unknown/NA samples are dropped — never
coerced to zero.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy import stats

from analysis.numerical import quantize_float, require_finite

__all__ = [
    "DistributionSummary",
    "IntervalMethod",
    "summarize_distribution",
    "proportion_confidence_interval",
]

IntervalMethod = str  # "percentile" | "binomial_exact"


@dataclass(frozen=True, slots=True)
class DistributionSummary:
    """Quantized distribution summary over a finite sample."""

    n: int
    mean: float | None
    std_sample: float | None
    median: float | None
    p05: float | None
    p95: float | None
    interval_low: float | None
    interval_high: float | None
    interval_method: IntervalMethod
    dropped_non_finite: int


def summarize_distribution(
    values: Sequence[object],
    *,
    interval_method: IntervalMethod = "percentile",
) -> DistributionSummary:
    """Sorted finite sample → n/mean/std/median/p05/p95 + interval."""
    finite: list[float] = []
    dropped = 0
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            dropped += 1
            continue
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            dropped += 1
            continue
        finite.append(number)
    finite.sort()
    n = len(finite)
    if n == 0:
        return DistributionSummary(
            n=0,
            mean=None,
            std_sample=None,
            median=None,
            p05=None,
            p95=None,
            interval_low=None,
            interval_high=None,
            interval_method=interval_method,
            dropped_non_finite=dropped,
        )
    arr = np.asarray(finite, dtype=np.float64)
    mean = quantize_float(require_finite(float(arr.mean())))
    if n >= 2:
        std = quantize_float(require_finite(float(arr.std(ddof=1))))
    else:
        std = None
    median = quantize_float(require_finite(float(np.median(arr))))
    p05 = quantize_float(require_finite(float(np.percentile(arr, 5))))
    p95 = quantize_float(require_finite(float(np.percentile(arr, 95))))
    if interval_method != "percentile":
        raise ValueError("interval_method: unsupported")
    return DistributionSummary(
        n=n,
        mean=mean,
        std_sample=std,
        median=median,
        p05=p05,
        p95=p95,
        interval_low=p05,
        interval_high=p95,
        interval_method=interval_method,
        dropped_non_finite=dropped,
    )


def proportion_confidence_interval(
    successes: int,
    trials: int,
    *,
    confidence: float = 0.95,
) -> tuple[float, float, IntervalMethod]:
    """SciPy exact Clopper–Pearson binomial interval for rate-like keys."""
    if type(successes) is not int or type(trials) is not int:
        raise TypeError("proportion_ci: invalid_counts")
    if successes < 0 or trials <= 0 or successes > trials:
        raise ValueError("proportion_ci: invalid_counts")
    low, high = stats.binomtest(successes, trials).proportion_ci(
        confidence_level=confidence, method="exact"
    )
    return (
        quantize_float(require_finite(float(low))),
        quantize_float(require_finite(float(high))),
        "binomial_exact",
    )
