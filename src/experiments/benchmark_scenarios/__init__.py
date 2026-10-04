"""Thin benchmark scenario builders over existing catalog arms.

Locked condition-id mapping (must match the V2 benchmark suite catalog):

| scenario_id | condition / composition |
| --- | --- |
| bench-01-seasonal-planning | ``u-learned`` vs ``u-naive`` |
| bench-02-memory-interference | ``a-reconstructive-v2`` vs ``a-reconstructive`` (shared seed) |
| bench-03-reflection-revision | ``g-deterministic`` vs ``g-disabled`` |
| bench-04-tom-social-failure | ``l-enabled`` (shared seed with #5; not a new ToM catalog arm) |
| bench-05-tom-cooperation | ``l-enabled`` (same world/seed matrix as #4) |
| bench-06-deception-reputation | custom runner-config-v10 strategy+reputation; ``q-disabled`` / strategy-only controls |
| bench-07-skill-specialization | ``r-enabled`` and/or ``t-enabled`` vs disabled peers |
| bench-08-territorial | ``v-scarce`` vs ``v-abundant`` |
| bench-09-social-clusters | ``w-enabled`` vs ``w-disabled`` |
| bench-10-norms | ``x-enabled`` vs ``x-disabled`` |
| bench-11-conventions | ``y-enabled`` vs ``y-disabled`` |
| bench-12-artifacts | ``artifact_channel`` vs ``memory_only`` |
| bench-13-naming-drift | ``aa-enabled`` vs ``aa-disabled`` |
| bench-14-rumor-narrative | ``ab-enabled`` vs ``ab-disabled`` |
| bench-15-architecture-matrix | ``ac-<architecture_id>`` arms |
| bench-16-forked-intervention | ``ResearchInterventionKind.COMMUNICATION_REMOVE`` fork |

Task 2 wires callable slots that fail closed until Tasks 4–11 install concrete
builders. Concrete modules under this package must wrap catalog helpers — they
must not invent WorldEngine semantics.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final, Protocol

from experiments.benchmark_suite import (
    BENCHMARK_SCENARIO_IDS,
    get_benchmark_scenario,
)
from experiments.models import ExperimentDefinition, ExperimentSeedMatrix
from simulation.runner_models import SimulationRunnerConfig
from world.identifiers import require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("experiments.benchmark_scenarios")

__all__ = [
    "BenchmarkBuildResult",
    "BenchmarkBuilderError",
    "BenchmarkScenarioBuilder",
    "build_benchmark_scenario",
    "is_benchmark_builder_implemented",
    "register_benchmark_builder",
    "registered_benchmark_builders",
    "uninstall_benchmark_builder",
]


class BenchmarkBuilderError(ValueError):
    """Fail-closed builder errors with a stable reason code."""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        detail = message or code
        super().__init__(detail)
        if code == "builder_not_implemented":
            _LOG.error("builder_not_implemented scenario_id=%s", message or "")
        else:
            _LOG.error("benchmark_builder_failed reason_code=%s", code)


@dataclass(frozen=True, slots=True)
class BenchmarkBuildResult:
    """Built experiment definition plus optional matrix factor labels."""

    scenario_id: str
    definition: ExperimentDefinition
    matrix_factors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_stable_id("scenario_id", self.scenario_id)
        if type(self.definition) is not ExperimentDefinition:
            raise TypeError("definition must be ExperimentDefinition")
        if isinstance(self.matrix_factors, (set, frozenset)):
            raise TypeError("matrix_factors must be ordered")
        factors = tuple(self.matrix_factors)
        for item in factors:
            if type(item) is not str or not item:
                raise TypeError("matrix_factors entries must be non-empty str")
        object.__setattr__(self, "matrix_factors", factors)


class BenchmarkScenarioBuilder(Protocol):
    """Callable that composes an ``ExperimentDefinition`` for one scenario."""

    def __call__(
        self,
        base: SimulationRunnerConfig,
        *,
        seed_matrix: ExperimentSeedMatrix | None = None,
    ) -> BenchmarkBuildResult: ...


def _fail_closed(scenario_id: str) -> BenchmarkScenarioBuilder:
    def _builder(
        base: SimulationRunnerConfig,
        *,
        seed_matrix: ExperimentSeedMatrix | None = None,
    ) -> BenchmarkBuildResult:
        del base, seed_matrix
        raise BenchmarkBuilderError("builder_not_implemented", scenario_id)

    return _builder


_BUILDERS: dict[str, BenchmarkScenarioBuilder] = {
    scenario_id: _fail_closed(scenario_id) for scenario_id in BENCHMARK_SCENARIO_IDS
}
_IMPLEMENTED: set[str] = set()


def register_benchmark_builder(
    scenario_id: str,
    builder: BenchmarkScenarioBuilder,
    *,
    implemented: bool = True,
) -> None:
    """Install or replace a builder slot (used by concrete modules and tests)."""
    require_stable_id("scenario_id", scenario_id)
    if scenario_id not in BENCHMARK_SCENARIO_IDS:
        raise BenchmarkBuilderError(
            "unknown_scenario_id",
            f"unknown scenario_id={scenario_id}",
        )
    if not callable(builder):
        raise BenchmarkBuilderError("invalid_builder", "builder must be callable")
    _BUILDERS[scenario_id] = builder
    if implemented:
        _IMPLEMENTED.add(scenario_id)
    else:
        _IMPLEMENTED.discard(scenario_id)
    _LOG.debug(
        "benchmark_builder_registered scenario_id=%s implemented=%s",
        scenario_id,
        implemented,
    )


def registered_benchmark_builders() -> Mapping[str, BenchmarkScenarioBuilder]:
    """Read-only view of builder slots (includes fail-closed stubs)."""
    return _BUILDERS


def is_benchmark_builder_implemented(scenario_id: str) -> bool:
    """Return True when a concrete builder has been installed for the id."""
    require_stable_id("scenario_id", scenario_id)
    return scenario_id in _IMPLEMENTED


def uninstall_benchmark_builder(scenario_id: str) -> None:
    """Restore the fail-closed stub for a scenario slot."""
    register_benchmark_builder(
        scenario_id,
        _fail_closed(scenario_id),
        implemented=False,
    )


def build_benchmark_scenario(
    scenario_id: str,
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> BenchmarkBuildResult:
    """Build one scenario via its registered slot; fail closed if unimplemented."""
    require_stable_id("scenario_id", scenario_id)
    if scenario_id not in _BUILDERS:
        raise BenchmarkBuilderError(
            "unknown_scenario_id",
            f"unknown scenario_id={scenario_id}",
        )
    # Touch the suite registry so unknown ids fail with suite codes first.
    get_benchmark_scenario(scenario_id)
    builder = _BUILDERS[scenario_id]
    result = builder(base, seed_matrix=seed_matrix)
    if type(result) is not BenchmarkBuildResult:
        raise BenchmarkBuilderError(
            "invalid_build_result",
            "builder must return BenchmarkBuildResult",
        )
    if result.scenario_id != scenario_id:
        raise BenchmarkBuilderError(
            "scenario_id_mismatch",
            f"builder returned scenario_id={result.scenario_id}",
        )
    condition_ids = ",".join(item.condition_id for item in result.definition.conditions)
    max_ticks = get_benchmark_scenario(scenario_id).max_ticks
    _LOG.info(
        "benchmark_scenario_built scenario_id=%s condition_ids=%s max_ticks=%s",
        scenario_id,
        condition_ids,
        max_ticks,
    )
    for agent in result.definition.conditions[0].runner_config.agents:
        cognition = agent.cognition
        _LOG.debug(
            "benchmark_builder_modes scenario_id=%s memory_mode=%s "
            "reflection_mode=%s",
            scenario_id,
            cognition.memory_mode.value,
            cognition.reflection_mode.value,
        )
    return result


def _load_concrete_builders() -> None:
    """Import concrete builder modules so they self-register."""
    from experiments.benchmark_scenarios import (  # noqa: F401
        cognition_scenarios as _cognition,
        skill_scenarios as _skill,
        social_scenarios as _social,
    )

    del _cognition, _social, _skill


_load_concrete_builders()
