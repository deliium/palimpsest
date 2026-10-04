"""Unit tests for benchmark scenarios 4-6 (ToM + deception/reputation)."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from experiments.benchmark_scenarios import build_benchmark_scenario
from experiments.benchmark_smoke import run_benchmark_smoke
from experiments.benchmark_suite import (
    BENCH_04_TOM_SOCIAL_FAILURE,
    BENCH_05_TOM_COOPERATION,
    BENCH_06_DECEPTION_REPUTATION,
)
from experiments.catalog import base_runner_config_from_scenario
from experiments.models import ExperimentSeedMatrix
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V9,
    RUNNER_SCHEMA_VERSION_V10,
    AgentCognitionSpec,
    AgentRunnerSpec,
    CommunicationStrategyMode,
    ReputationMode,
    WorldScenarioSpec,
)
from simulation.runner_serialization import scenario_fingerprint
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _base(*, max_ticks: int = 4, seed: int = 13):
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=seed,
        stochastic_identity="cmp-bench-social",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-bench-social"),
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


def test_bench_04_and_05_share_world_seed_matrix() -> None:
    matrix = ExperimentSeedMatrix(seeds=(13, 17))
    base = _base(seed=13)
    failure = build_benchmark_scenario(
        BENCH_04_TOM_SOCIAL_FAILURE, base, seed_matrix=matrix
    )
    coop = build_benchmark_scenario(
        BENCH_05_TOM_COOPERATION, base, seed_matrix=matrix
    )
    assert [item.condition_id for item in failure.definition.conditions] == [
        "l-enabled",
        "l-disabled",
    ]
    assert [item.condition_id for item in coop.definition.conditions] == [
        "l-enabled",
        "l-disabled",
    ]
    assert failure.definition.seed_matrix == coop.definition.seed_matrix
    enabled_f = failure.definition.conditions[0].runner_config
    enabled_c = coop.definition.conditions[0].runner_config
    assert enabled_f.capability_flags.advanced_social_inference is True
    assert enabled_c.capability_flags.advanced_social_inference is True
    assert scenario_fingerprint(enabled_f) == scenario_fingerprint(enabled_c)
    assert enabled_f.seed == enabled_c.seed
    assert enabled_f.stochastic_identity == enabled_c.stochastic_identity
    # Never invent wrong/corrected ToM catalog arms.
    ids = {item.condition_id for item in failure.definition.conditions}
    assert "l-wrong" not in ids and "l-corrected" not in ids


def test_bench_06_composes_strategy_and_reputation() -> None:
    result = build_benchmark_scenario(BENCH_06_DECEPTION_REPUTATION, _base())
    by_id = {item.condition_id: item for item in result.definition.conditions}
    assert set(by_id) == {
        "o-strategy-reputation",
        "o-strategy-only",
        "q-disabled",
    }
    combo = by_id["o-strategy-reputation"].runner_config
    strategy_only = by_id["o-strategy-only"].runner_config
    disabled = by_id["q-disabled"].runner_config
    assert combo.schema_version == RUNNER_SCHEMA_VERSION_V10
    assert (
        combo.agents[0].cognition.communication_strategy_mode
        is CommunicationStrategyMode.DETERMINISTIC
    )
    assert combo.agents[0].cognition.reputation_mode is ReputationMode.DETERMINISTIC
    assert strategy_only.schema_version == RUNNER_SCHEMA_VERSION_V9
    assert (
        strategy_only.agents[0].cognition.reputation_mode is ReputationMode.DISABLED
    )
    assert disabled.agents[0].cognition.reputation_mode is ReputationMode.DISABLED
    # o-enabled alone is not this suite's reputation arm.
    assert "o-enabled" not in by_id


@pytest.mark.asyncio
async def test_bench_04_through_06_smoke_availability() -> None:
    for scenario_id in (
        BENCH_04_TOM_SOCIAL_FAILURE,
        BENCH_05_TOM_COOPERATION,
        BENCH_06_DECEPTION_REPUTATION,
    ):
        smoke = await run_benchmark_smoke(scenario_id, _base(), tick_budget=4)
        assert smoke.ran is True
        assert smoke.ticks <= 4
        assert smoke.metrics_available
        assert all(
            item.status
            in {"present", "partial", "assemblable", "absent", "unknown", "declared"}
            for item in smoke.metrics_available
        )
