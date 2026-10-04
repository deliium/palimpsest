"""Unit tests for benchmark scenario 16 (COMMUNICATION_REMOVE fork)."""

from __future__ import annotations

from agents.models import AgentId
from experiments.benchmark_scenarios import build_benchmark_scenario
from experiments.benchmark_scenarios.fork_scenarios import (
    FORK_CHILD_CONDITION_ID,
    FORK_PARENT_CONDITION_ID,
    communication_remove_intervention,
)
from experiments.benchmark_suite import BENCH_16_FORKED_INTERVENTION
from experiments.catalog import base_runner_config_from_scenario
from simulation.branch_service import apply_research_intervention
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from tests.unit.test_simulation_branch_interventions import _talked
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _base(*, max_ticks: int = 4, seed: int = 37):
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=seed,
        stochastic_identity="cmp-bench-fork",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-bench-fork"),
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


def test_bench_16_builder_parent_child_template() -> None:
    result = build_benchmark_scenario(BENCH_16_FORKED_INTERVENTION, _base())
    assert [item.condition_id for item in result.definition.conditions] == [
        FORK_PARENT_CONDITION_ID,
        FORK_CHILD_CONDITION_ID,
    ]
    parent, child = result.definition.conditions
    assert parent.runner_config.seed == child.runner_config.seed
    assert parent.runner_config.stochastic_identity == child.runner_config.stochastic_identity


def test_bench_16_communication_remove_keeps_parent_events_immutable() -> None:
    result = build_benchmark_scenario(BENCH_16_FORKED_INTERVENTION, _base())
    parent_config = result.definition.conditions[0].runner_config
    parent_events = (_talked(tick=7, event_id="evt-future-talk"),)
    before = tuple(event.event_id.value for event in parent_events)
    intervention = communication_remove_intervention(event_id="evt-future-talk")
    applied = apply_research_intervention(
        parent_config,
        intervention,
        fork_tick=5,
        parent_events=parent_events,
    )
    after = tuple(event.event_id.value for event in parent_events)
    assert before == after
    assert applied.removed_communication is not None
    assert applied.removed_communication["event_id"] == "evt-future-talk"
    assert applied.removed_communication["tick"] == 7
    # Child template retains shared seed/stochastic identity (inherit stream).
    assert applied.runner_config.seed == parent_config.seed
    assert applied.runner_config.stochastic_identity == parent_config.stochastic_identity
