"""Unit tests for experiment coordinator ordering."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario, experiment_a_memory
from experiments.coordinator import ExperimentCoordinator, materialize_assignments
from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V14,
    RUNNER_SCHEMA_VERSION_V22,
    AgentCognitionSpec,
    AgentRunnerSpec,
    CognitionTraceDetail,
    CognitionTraceSpec,
    CognitiveBudgetLimits,
    CognitiveBudgetMode,
    ExperimentAssignmentRef,
    V2CapabilityFlags,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.environment import scarcity_scenario_dynamics
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _base():
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=1,
        stochastic_identity="cmp-coord",
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
        max_ticks=1,
    )


def test_materialize_assignments_order() -> None:
    definition = experiment_a_memory(
        _base(),
        seed_matrix=ExperimentSeedMatrix(seeds=(1, 2), replicates_per_seed=2),
    )
    assignments = materialize_assignments(definition)
    assert len(assignments) == 12  # 3 conditions x 2 seeds x 2 replicates
    keys = [
        (a.condition_ordinal, a.seed_ordinal, a.replicate_index) for a in assignments
    ]
    assert keys == sorted(keys)


@pytest.mark.asyncio
async def test_coordinator_runs_all_arms() -> None:
    definition = experiment_a_memory(
        _base(),
        seed_matrix=ExperimentSeedMatrix(seeds=(3,), replicates_per_seed=1),
    )
    coordinator = ExperimentCoordinator(definition)
    results = await coordinator.run_all()
    assert len(results) == 3
    assert {item.assignment.condition_id for item in results} == {
        "a-reference",
        "a-reconstructive",
        "a-reconstructive-v2",
    }
    assert all(item.runner_result.ticks_committed == 1 for item in results)


def test_materialize_assignments_preserves_v2_fields() -> None:
    base = _base()
    limits = CognitiveBudgetLimits(
        max_llm_calls_per_tick=0,
        max_tokens_per_tick=0,
        max_imagination_branches=2,
        max_planning_depth=1,
        max_recalled_memories=2,
        max_tom_targets=1,
        reflection_interval_ticks=16,
        timeout_seconds=0.0,
    )
    rich = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V22,
        environmental_dynamics=scarcity_scenario_dynamics(),
        artifacts_enabled=True,
        cognition_trace=CognitionTraceSpec(
            enabled=True,
            detail=CognitionTraceDetail.SUMMARY,
        ),
        capability_flags=V2CapabilityFlags(advanced_social_inference=True),
        experiment=ExperimentAssignmentRef(
            experiment_id="matrix-preserve",
            condition_id="arm-budget",
            replicate_index=0,
            seed_ordinal=0,
        ),
        agents=(
            replace(
                base.agents[0],
                cognition=replace(
                    base.agents[0].cognition,
                    cognitive_budget_mode=CognitiveBudgetMode.ENFORCED,
                    cognitive_budget_limits=limits,
                ),
            ),
        ),
    )
    # Pair with a second arm that differs only by ToM flag off for definition rules.
    control = replace(
        rich,
        schema_version=RUNNER_SCHEMA_VERSION_V14,
        capability_flags=V2CapabilityFlags(),
        agents=(
            replace(
                rich.agents[0],
                cognition=replace(
                    rich.agents[0].cognition,
                    cognitive_budget_mode=CognitiveBudgetMode.DISABLED,
                    cognitive_budget_limits=None,
                ),
            ),
        ),
    )
    definition = ExperimentDefinition(
        experiment_id="matrix-preserve-fields",
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=ExperimentSeedMatrix(seeds=(99,)),
        conditions=(
            ExperimentCondition(
                condition_id="arm-budget",
                label_code="budget",
                runner_config=rich,
            ),
            ExperimentCondition(
                condition_id="arm-control",
                label_code="control",
                runner_config=control,
            ),
        ),
        paired_world_group="matrix-preserve-world",
    )
    assignments = materialize_assignments(definition)
    budget_arm = next(a for a in assignments if a.condition_id == "arm-budget")
    assert budget_arm.runner_config.seed == 99
    assert budget_arm.runner_config.environmental_dynamics is not None
    assert budget_arm.runner_config.artifacts_enabled is True
    assert budget_arm.runner_config.cognition_trace.enabled is True
    assert budget_arm.runner_config.capability_flags.advanced_social_inference is True
    assert budget_arm.runner_config.experiment is not None
    assert (
        budget_arm.runner_config.agents[0].cognition.cognitive_budget_mode
        is CognitiveBudgetMode.ENFORCED
    )
    assert (
        budget_arm.runner_config.agents[0].cognition.cognitive_budget_limits
        == limits
    )
