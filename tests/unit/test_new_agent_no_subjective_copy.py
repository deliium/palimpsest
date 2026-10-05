"""Prove mid-run agents do not inherit bootstrap subjective content."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import (
    AgentId,
    Goal,
    GoalId,
    GoalOutcome,
    GoalOutcomeKind,
    GoalStatus,
)
from experiments.catalog import base_runner_config_from_scenario
from simulation.models import RunId
from simulation.new_agent_initialization import (
    BlankSlateStoreCounts,
    assert_blank_slate_subjective_state,
)
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V24,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_population_lifecycle_spec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.new_agent_no_subjective_copy")


@pytest.mark.asyncio
async def test_mid_run_agent_blank_slate_despite_bootstrap_goals() -> None:
    _LOG.debug("case_id=mid_run_blank_slate_despite_bootstrap_goals")
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    bootstrap_goal = Goal(
        goal_id=GoalId("goal-bootstrap"),
        owner_id=agent_id,
        description="bootstrap-only",
        priority=0.5,
        status=GoalStatus.ACTIVE,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.ACHIEVE_CODE, outcome_code="bootstrap"
        ),
    )
    config = replace(
        base_runner_config_from_scenario(
            seed=19,
            stochastic_identity="cmp-no-subj-copy",
            scenario=WorldScenarioSpec(
                world_id=WorldId("world-no-copy"),
                revision=WorldRevision(0),
                physical_rules=non_lethal_physical_rules(),
                locations=(make_location(body_capacity=8),),
                bodies=(body,),
                weather=(make_weather(),),
            ),
            agents=(
                AgentRunnerSpec(
                    agent_id=agent_id,
                    entity_id=body.entity_id,
                    cognition=AgentCognitionSpec(agent_id=agent_id),
                    initial_goals=(bootstrap_goal,),
                ),
            ),
            max_ticks=12,
        ),
        schema_version=RUNNER_SCHEMA_VERSION_V24,
        mortality_mode=MortalityMode.DISABLED,
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=example_population_lifecycle_spec(
            lifespan_ticks=40,
            max_population=4,
            policy_id="fixed_interval_entry",
        ),
    )
    runner = await SimulationRunner.from_config(
        config, run_id=RunId("run-no-subj-copy")
    )
    assert runner.runtimes[0].agent.goals == (bootstrap_goal,)
    for _ in range(6):
        await runner.run_tick()
    assert len(runner.runtimes) == 2
    entrant = runner.runtimes[1]
    assert entrant.agent.goals == ()
    assert_blank_slate_subjective_state(
        entrant.agent_id, BlankSlateStoreCounts()
    )
