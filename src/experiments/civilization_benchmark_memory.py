"""Bounded v55 compositions for benchmark cases 05-07 (memory and records)."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Final

from agents.models import AgentId
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
    V3_BENCH_05_MEMORY_LAYERS,
    V3_BENCH_06_RECORD_AFTER_WITNESSES,
    V3_BENCH_07_FALSE_RECORD,
)
from experiments.interventions import (
    MilestoneInterventionArbiter,
    MilestoneOverride,
)
from simulation.new_agent_initialization import (
    SPECIES_DEFAULT_DEVELOPMENTAL_V1,
    NewAgentInitializationSpec,
    default_new_agent_initialization_spec,
)
from simulation.runner_models import (
    SimulationRunnerConfig,
    example_durable_records_spec,
    example_historical_memory_layers_spec,
)
from world.actions import Inscribe
from world.artifacts import ArtifactContent, ArtifactKind, DurableRecordGenre

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.civilization_benchmark_memory"
)

MEMORY_BENCHMARK_IDS: Final[tuple[str, ...]] = (
    V3_BENCH_05_MEMORY_LAYERS,
    V3_BENCH_06_RECORD_AFTER_WITNESSES,
    V3_BENCH_07_FALSE_RECORD,
)

_ACCURATE_MARK: Final[str] = "proposition_water_at_crossroads"
_FALSE_MARK: Final[str] = "proposition_grain_is_poisoned"


def _learner_initializer() -> NewAgentInitializationSpec:
    return replace(
        default_new_agent_initialization_spec(),
        species_defaults_id=SPECIES_DEFAULT_DEVELOPMENTAL_V1,
    )


def build_memory_benchmark(
    scenario_id: str,
    *,
    seed: int | None = None,
    profile: V3BenchmarkProfile = V3BenchmarkProfile.SMOKE,
    lane: V3BenchmarkLane = V3BenchmarkLane.RESEARCH,
) -> V3BenchmarkScenarioBuild:
    """Materialize one Phase 3 memory/record case."""
    if scenario_id not in MEMORY_BENCHMARK_IDS:
        raise V3BenchmarkError(
            "unknown_scenario", f"not a memory benchmark: {scenario_id!r}"
        )
    build = build_v3_benchmark_scenario(
        scenario_id, seed=seed, profile=profile, lane=lane
    )
    base = build.arms[0].config
    if scenario_id == V3_BENCH_05_MEMORY_LAYERS:
        config = replace(
            base,
            historical_memory_layers=example_historical_memory_layers_spec(),
        )
    else:
        config = replace(
            base,
            historical_memory_layers=example_historical_memory_layers_spec(),
            durable_records=example_durable_records_spec(),
            new_agent_initialization=_learner_initializer(),
        )
    arms = tuple(replace(arm, config=config) for arm in build.arms)
    result = replace(build, arms=arms)
    _LOG.debug(
        "memory_benchmark_built scenario_id=%s layers=%s records=%s",
        scenario_id,
        result.arms[0].config.historical_memory_layers is not None,
        result.arms[0].config.durable_records is not None,
    )
    return result


def _inscribe_command(scenario_id: str) -> Inscribe:
    mark = _FALSE_MARK if scenario_id == V3_BENCH_07_FALSE_RECORD else _ACCURATE_MARK
    return Inscribe(
        kind=ArtifactKind.RECORD,
        content=ArtifactContent(marks=(mark,)),
        record_genre=DurableRecordGenre.CHRONICLE,
    )


def memory_benchmark_arbiter(
    scenario_id: str, config: SimulationRunnerConfig
) -> MilestoneInterventionArbiter | None:
    """One legal inscription by the first founder; no meaning is installed."""
    if scenario_id not in {
        V3_BENCH_06_RECORD_AFTER_WITNESSES,
        V3_BENCH_07_FALSE_RECORD,
    }:
        return None
    assert config.agents
    founder = AgentId(config.agents[0].agent_id.value)
    milestone = MilestoneOverride(
        milestone_id="v3-bench-inscribe-record",
        tick=0,
        agent_id=founder,
        build_command=lambda: _inscribe_command(scenario_id),
    )
    return MilestoneInterventionArbiter((milestone,), override_budget=1)


__all__ = [
    "MEMORY_BENCHMARK_IDS",
    "build_memory_benchmark",
    "memory_benchmark_arbiter",
]
