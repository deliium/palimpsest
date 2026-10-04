"""Full 16-scenario smoke gate for the V2 benchmark suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.models import AgentId
from experiments.benchmark_scenarios import (
    is_benchmark_builder_implemented,
    registered_benchmark_builders,
)
from experiments.benchmark_smoke import run_benchmark_smoke
from experiments.benchmark_suite import (
    BENCHMARK_SCENARIO_IDS,
    registered_benchmark_scenario_ids,
)
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

_REPO_ROOT = Path(__file__).resolve().parents[2]
_V1_GATE = _REPO_ROOT / "tests" / "unit" / "test_v1_regression_gate.py"


def _base(*, max_ticks: int = 4, seed: int = 41):
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=seed,
        stochastic_identity="cmp-bench-suite-smoke",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-bench-suite-smoke"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body,),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=max_ticks,
    )


def test_all_sixteen_builders_implemented() -> None:
    ids = registered_benchmark_scenario_ids()
    assert ids == BENCHMARK_SCENARIO_IDS
    assert len(ids) == 16
    builders = registered_benchmark_builders()
    assert set(builders) == set(ids)
    for scenario_id in ids:
        assert is_benchmark_builder_implemented(scenario_id) is True


@pytest.mark.asyncio
async def test_full_suite_smoke_availability_only() -> None:
    base = _base()
    for scenario_id in BENCHMARK_SCENARIO_IDS:
        smoke = await run_benchmark_smoke(scenario_id, base, tick_budget=4)
        assert smoke.scenario_id == scenario_id
        assert smoke.ran is True
        assert smoke.ticks <= 4
        assert smoke.arm_count >= 2
        assert smoke.metrics_available
        for item in smoke.metrics_available:
            assert item.status in {
                "present",
                "partial",
                "assemblable",
                "absent",
                "unknown",
                "declared",
            }
            lowered = item.measurable_output.lower()
            assert "must emerge" not in lowered
            assert "must form" not in lowered
            assert "group_must_form" not in lowered
            assert "society_formed" not in lowered


def test_v1_regression_gate_does_not_import_benchmark_suite() -> None:
    source = _V1_GATE.read_text(encoding="utf-8")
    assert "benchmark_suite" not in source
    assert "benchmark_scenarios" not in source
    assert "benchmark_smoke" not in source
    assert "bench-" not in source
    assert "observer-graphical-v2" not in source
