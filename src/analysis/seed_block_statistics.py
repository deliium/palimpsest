"""Reusable repeated-seed Student-t numerical policy."""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from scipy import stats

DEFAULT_CONFIDENCE: Final[float] = 0.95


@dataclass(frozen=True, slots=True)
class StudentTInterval:
    mean: float | None
    sample_sd: float | None
    standard_error: float | None
    df: int | None
    low: float | None
    high: float | None
    status: str


def student_t_interval(
    values: Sequence[float], *, confidence: float = DEFAULT_CONFIDENCE
) -> StudentTInterval:
    """Pointwise two-sided Student-t interval over distinct seed-block means."""
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError("values must be an ordered sequence")
    samples = tuple(float(value) for value in values)
    for sample in samples:
        if not math.isfinite(sample):
            raise ValueError("values must be finite")
    n = len(samples)
    if n == 0:
        return StudentTInterval(
            None, None, None, None, None, None, "insufficient_independent_seeds"
        )
    mean = statistics.fmean(samples)
    if n == 1:
        return StudentTInterval(
            mean, None, None, None, None, None, "insufficient_independent_seeds"
        )
    sd = statistics.stdev(samples)
    df = n - 1
    se = sd / math.sqrt(n)
    if sd == 0.0:
        return StudentTInterval(mean, sd, se, df, mean, mean, "present")
    margin = float(stats.t.ppf((1.0 + confidence) / 2.0, df)) * se
    return StudentTInterval(
        mean, sd, se, df, mean - margin, mean + margin, "present"
    )


__all__ = ["DEFAULT_CONFIDENCE", "StudentTInterval", "student_t_interval"]
