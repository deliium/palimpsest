"""V1 regression gate: catalog A-E + reference scenario under V2 scaffolding.

Network-free, DB-free unit path. Short tick counts; deterministic fakes.
"""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from experiments.catalog import (
    base_runner_config_from_scenario,
    experiment_a_memory_v1_arms,
    experiment_b_imagination,
    experiment_c_mortality,
    experiment_d_drives,
    experiment_e_false_story,
    v1_regression_profile,
)
from experiments.coordinator import ExperimentCoordinator
from experiments.models import ExperimentSeedMatrix
from experiments.reference_scenario import (
    REFERENCE_SCENARIO_ID,
    build_reference_scenario,
)
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
)
from simulation.runner_serialization import runner_config_fingerprint
from tests.reference_scenario_helpers import run_reference_scenario
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit

_LOG = logging.getLogger("tests.v1_regression_gate")

_CATALOG_BUILDERS = (
    ("experiment-a-memory", experiment_a_memory_v1_arms),
    ("experiment-b-imagination", experiment_b_imagination),
    ("experiment-c-mortality", experiment_c_mortality),
    ("experiment-d-drives", experiment_d_drives),
    ("experiment-e-false-story", experiment_e_false_story),
)


def _short_base(*, seed: int = 11, max_ticks: int = 1):
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=seed,
        stochastic_identity="cmp-v1-regression",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-1"),
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


@pytest.mark.asyncio
@pytest.mark.parametrize("experiment_id,builder", _CATALOG_BUILDERS)
async def test_catalog_experiment_executes_flags_off(
    experiment_id: str, builder: object
) -> None:
    base = _short_base()
    definition = builder(  # type: ignore[operator]
        base,
        seed_matrix=ExperimentSeedMatrix(seeds=(base.seed,), replicates_per_seed=1),
    )
    _LOG.info(
        "v1_regression_gate_start experiment_id=%s condition_count=%s max_ticks=%s",
        experiment_id,
        len(definition.conditions),
        base.stop_policy.max_ticks,
    )
    for condition in definition.conditions:
        assert condition.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V4
        v1_regression_profile(condition.runner_config)
        _LOG.debug(
            "v1_regression_gate_condition experiment_id=%s condition_id=%s "
            "config_fingerprint_prefix=%s",
            experiment_id,
            condition.condition_id,
            runner_config_fingerprint(condition.runner_config)[:12],
        )
    results = await ExperimentCoordinator(definition).run_all()
    assert len(results) == len(definition.conditions)
    for arm in results:
        assert arm.runner_result.ticks_committed == 1
        v1_regression_profile(arm.assignment.runner_config)
    _LOG.info(
        "v1_regression_gate_end experiment_id=%s arm_count=%s",
        experiment_id,
        len(results),
    )


@pytest.mark.asyncio
async def test_reference_scenario_short_horizon_flags_off() -> None:
    bundle = build_reference_scenario(
        seed=13,
        stochastic_identity="cmp-v1-ref-gate",
        max_ticks=4,
        death_tick=1,
    )
    assert bundle.scenario_id == REFERENCE_SCENARIO_ID
    v1_regression_profile(bundle.config)
    assert bundle.config.schema_version == RUNNER_SCHEMA_VERSION_V4
    _LOG.info(
        "v1_regression_gate_reference_start max_ticks=%s "
        "config_fingerprint_prefix=%s",
        bundle.config.stop_policy.max_ticks,
        runner_config_fingerprint(bundle.config)[:12],
    )
    outcome = await run_reference_scenario(
        run_id="run-v1-ref-gate",
        seed=13,
        max_ticks=4,
        death_tick=1,
    )
    assert outcome.result.ticks_committed == 4
    assert outcome.result.stop_reason is not None
    assert outcome.result.stop_reason.value == "max_ticks"
    v1_regression_profile(outcome.bundle.config)
    _LOG.info(
        "v1_regression_gate_reference_end ticks_committed=%s",
        outcome.result.ticks_committed,
    )


@pytest.mark.asyncio
async def test_flags_off_single_runner_constructs_and_runs() -> None:
    config = v1_regression_profile(_short_base(max_ticks=2))
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-v1-gate-solo")
    ) as runner:
        result = await runner.run()
    assert result.ticks_committed == 2


def test_goal_management_always_on_not_capability_flag() -> None:
    """Hierarchical GoalManager is production cognition config, not a V2 flag."""
    from agents.cognition import (
        CognitionGoalManagementMode,
        production_cognition_config,
    )

    config = v1_regression_profile(_short_base())
    assert config.capability_flags.enabled_names() == ()
    assert config.cognition_trace.enabled is False
    cognition = production_cognition_config()
    assert cognition.goal_management_mode is CognitionGoalManagementMode.ENABLED
    assert not hasattr(config, "goal_management_enabled")
    assert "goal_management" not in config.capability_flags.__dataclass_fields__


def test_short_term_emotional_state_is_owned_capability_flag_default_off() -> None:
    """V2 short-term emotion is gated by the owned capability flag (default off)."""
    from agents.cognition import (
        CognitionEmotionalStateMode,
        production_cognition_config,
    )

    config = v1_regression_profile(_short_base())
    assert config.capability_flags.short_term_emotional_state is False
    assert "short_term_emotional_state" in config.capability_flags.__dataclass_fields__
    cognition = production_cognition_config()
    assert cognition.emotional_state_mode is CognitionEmotionalStateMode.PASSTHROUGH


@pytest.mark.asyncio
async def test_flags_off_runner_uses_emotional_passthrough() -> None:
    from agents.cognition.emotion import PassthroughEmotionalStateAppraiser

    config = v1_regression_profile(_short_base(max_ticks=2))
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-v1-emotion-off")
    ) as runner:
        loop = runner.runtimes[0]._loop
        assert type(loop._emotional_state) is PassthroughEmotionalStateAppraiser
        result = await runner.run()
    assert result.ticks_committed == 2