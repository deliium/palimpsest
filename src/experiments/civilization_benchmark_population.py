"""Bounded v55 compositions for benchmark cases 01-04.

These recipes add only owned, exact run-level specs to the Phase 1 atomic base.
They never seed subjective content, assign caregivers/teachers, or schedule a
social role; the mechanism lane remains a declared opportunity, not a result.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Final

from experiments.civilization_benchmark_base import (
    V3BenchmarkScenarioBuild,
    build_v3_benchmark_scenario,
)
from experiments.civilization_benchmark_models import (
    V3BenchmarkError,
    V3BenchmarkLane,
    V3BenchmarkProfile,
)
from experiments.civilization_benchmark_suite import (
    V3_BENCH_01_BLANK_SLATE,
    V3_BENCH_02_DEPENDENT_CARE,
    V3_BENCH_03_INTERGENERATIONAL_TEACHING,
    V3_BENCH_04_CULTURAL_MUTATION,
)
from simulation.new_agent_initialization import (
    SPECIES_DEFAULT_DEVELOPMENTAL_V1,
    NewAgentInitializationSpec,
    default_new_agent_initialization_spec,
)
from simulation.runner_models import (
    example_dependency_care_spec,
    example_developmental_learning_spec,
    example_mentorship_spec,
)

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.civilization_benchmark_population"
)

POPULATION_BENCHMARK_IDS: Final[tuple[str, ...]] = (
    V3_BENCH_01_BLANK_SLATE,
    V3_BENCH_02_DEPENDENT_CARE,
    V3_BENCH_03_INTERGENERATIONAL_TEACHING,
    V3_BENCH_04_CULTURAL_MUTATION,
)


def _developmental_initializer() -> NewAgentInitializationSpec:
    return replace(
        default_new_agent_initialization_spec(),
        species_defaults_id=SPECIES_DEFAULT_DEVELOPMENTAL_V1,
    )


def build_population_benchmark(
    scenario_id: str,
    *,
    seed: int | None = None,
    profile: V3BenchmarkProfile = V3BenchmarkProfile.SMOKE,
    lane: V3BenchmarkLane = V3BenchmarkLane.RESEARCH,
) -> V3BenchmarkScenarioBuild:
    """Materialize one Phase 3 population/culture case."""
    if scenario_id not in POPULATION_BENCHMARK_IDS:
        raise V3BenchmarkError(
            "unknown_scenario", f"not a population benchmark: {scenario_id!r}"
        )
    build = build_v3_benchmark_scenario(
        scenario_id, seed=seed, profile=profile, lane=lane
    )
    if scenario_id == V3_BENCH_02_DEPENDENT_CARE:
        config = replace(
            build.arms[0].config,
            dependency_care=example_dependency_care_spec(),
        )
    elif scenario_id == V3_BENCH_03_INTERGENERATIONAL_TEACHING:
        config = replace(
            build.arms[0].config,
            developmental_learning=example_developmental_learning_spec(),
            mentorship=example_mentorship_spec(),
            new_agent_initialization=_developmental_initializer(),
        )
    elif scenario_id == V3_BENCH_04_CULTURAL_MUTATION:
        config = replace(
            build.arms[0].config,
            new_agent_initialization=_developmental_initializer(),
        )
    else:
        config = build.arms[0].config
    arms = tuple(
        replace(arm, config=config)
        for arm in build.arms
    )
    result = replace(build, arms=arms)
    _LOG.debug(
        "population_benchmark_built scenario_id=%s lane=%s profile=%s "
        "dependency_care=%s developmental_learning=%s mentorship=%s",
        scenario_id,
        lane.value,
        profile.value,
        result.arms[0].config.dependency_care is not None,
        result.arms[0].config.developmental_learning is not None,
        result.arms[0].config.mentorship is not None,
    )
    return result


__all__ = ["POPULATION_BENCHMARK_IDS", "build_population_benchmark"]
