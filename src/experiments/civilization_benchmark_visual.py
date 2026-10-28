"""Bounded visual integration fixture for the release acceptance workflow.

This fixture is outside the 30-case research registry. Task 17 owns the
controlled opportunity schedule and the eight visual markers; this module only
materializes the same six-founder visual world under a stable recipe identity.
"""

from __future__ import annotations

from typing import Final

from experiments.civilization_benchmark_base import (
    V3BenchmarkBase,
    build_v3_benchmark_base,
)
from experiments.civilization_benchmark_models import (
    V3_VISUAL_BENCHMARK_ID,
    V3BenchmarkProfile,
)
from experiments.civilization_benchmark_suite import V3_BENCH_01_BLANK_SLATE

VISUAL_BENCHMARK_RECIPE_ID: Final[str] = V3_VISUAL_BENCHMARK_ID


def build_v3_visual_benchmark(*, seed: int = 23) -> V3BenchmarkBase:
    """Materialize the bounded visual world (not a research case)."""
    return build_v3_benchmark_base(
        seed=seed,
        profile=V3BenchmarkProfile.VISUAL,
        scenario_id=V3_BENCH_01_BLANK_SLATE,
    )


__all__ = ["VISUAL_BENCHMARK_RECIPE_ID", "build_v3_visual_benchmark"]
