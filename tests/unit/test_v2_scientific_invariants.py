"""Network-free V2 scientific invariants completion gate.

Keeps the V1 regression gate untouched. Asserts composition/import pins only —
no emergence mandates.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from experiments.benchmark_scenarios import is_benchmark_builder_implemented
from experiments.benchmark_suite import (
    BENCHMARK_SCENARIO_COUNT,
    BENCHMARK_SCENARIO_IDS,
    list_benchmark_scenarios,
)
from experiments.catalog import v1_regression_profile
from experiments.observer_graphical_scenario import OBSERVER_GRAPHICAL_SCENARIO_ID
from simulation.runner_models import V2CapabilityFlags

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_LOG = logging.getLogger("tests.v2_scientific_invariants")


def test_v2_scientific_invariants_ok() -> None:
    # Flags-off V1 profile remains the default write shape.
    from agents.models import AgentId
    from experiments.catalog import base_runner_config_from_scenario
    from simulation.runner_models import (
        AgentCognitionSpec,
        AgentRunnerSpec,
        WorldScenarioSpec,
    )
    from tests.simulation_helpers import alive_body, make_location, make_weather
    from world.identifiers import WorldId, WorldRevision
    from world.models import default_physical_rules

    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    base = base_runner_config_from_scenario(
        seed=1,
        stochastic_identity="cmp-v2-invariants",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v2-inv"),
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
        max_ticks=2,
    )
    profiled = v1_regression_profile(base)
    assert profiled.capability_flags == V2CapabilityFlags()
    assert profiled.capability_flags.multi_hop_testimony_tracking is False

    # Suite registry complete; builders implemented; off V1 gate.
    assert len(BENCHMARK_SCENARIO_IDS) == BENCHMARK_SCENARIO_COUNT == 16
    for scenario_id in BENCHMARK_SCENARIO_IDS:
        assert is_benchmark_builder_implemented(scenario_id) is True
    for spec in list_benchmark_scenarios():
        assert spec.off_v1_gate is True
        assert OBSERVER_GRAPHICAL_SCENARIO_ID not in spec.scenario_id

    # Recording replay proof path remains importable (contract pointer).
    recording_test = (
        _ROOT / "tests" / "integration" / "test_llm_recording_replay.py"
    )
    assert recording_test.is_file()

    # Branch compare + matrix CLI + Research UI mount helpers exist.
    from simulation.branch_compare import compare_branch_timelines
    from experiments.matrix_expand import expand_matrix
    from api.research_static import mount_research_ui, research_ui_configured

    assert callable(compare_branch_timelines)
    assert callable(expand_matrix)
    assert callable(mount_research_ui)
    assert callable(research_ui_configured)

    # Scale docs / harness pin (no new BLAS thresholds here).
    scale_plan = _ROOT / ".ai-factory" / "plans" / "v2-long-experiment-scalability.md"
    scale_tests = _ROOT / "tests" / "benchmarks" / "test_long_run_scale.py"
    assert scale_plan.is_file() or scale_tests.is_file()
    if scale_tests.is_file():
        text = scale_tests.read_text(encoding="utf-8")
        assert "pytest.mark.scale" in text

    # Suite never enables unowned multi_hop_testimony_tracking.
    for spec in list_benchmark_scenarios():
        for mode in spec.configuration.required_modes:
            assert "multi_hop_testimony_tracking" not in mode

    # V1 gate source stays free of suite identifiers.
    gate = (_ROOT / "tests" / "unit" / "test_v1_regression_gate.py").read_text(
        encoding="utf-8"
    )
    assert "benchmark_suite" not in gate
    assert "bench-" not in gate
    assert OBSERVER_GRAPHICAL_SCENARIO_ID not in gate

    _LOG.info("v2_scientific_invariants_ok")


def test_subjective_objective_separation_pin() -> None:
    """Cognition never imports analysis; analysis stays read-only of domain."""
    cognition = _ROOT / "src" / "agents" / "cognition"
    for path in cognition.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "import analysis" not in text
        assert "from analysis" not in text
