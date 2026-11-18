# mypy: ignore-errors

"""Runtime composition: owner command binding and committed predictive state."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition.scientific_model_binding import (
    bind_scientific_model_execution,
)
from agents.cognition.scientific_models import (
    ModelExecutionComparability,
    ScientificModelLedger,
)
from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from experiments.scientific_hypotheses_scenario import (
    scientific_hypotheses_scenario,
)
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    RunnerStopPolicy,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from tests.unit.test_scientific_models_lifecycle import (
    _observation,
    _production_case,
)
from world.actions import Experiment
from world.environment import Season
from world.experimentation import ExperimentOperator, ExperimentProcessToken
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules
from world.production import example_production_catalog

pytestmark = pytest.mark.unit


def _command(
    *,
    operand: str = "wheat",
    operator: ExperimentOperator = ExperimentOperator.COMBINE,
    process: ExperimentProcessToken = ExperimentProcessToken.HARVEST,
) -> Experiment:
    return Experiment(
        operator=operator,
        operand_a_id=EntityId(operand),
        process_token=process,
    )


def _bound(comparability: ModelExecutionComparability):
    ledger, _ = _production_case()
    case = next(
        row
        for row in ledger.pending_cases
        if row.target_kind.value == "production_outcome"
    )
    observation = _observation(case.issued_observation_tick + 1, include_self=True)
    return bind_scientific_model_execution(
        ledger,
        _command(),
        tick=case.issued_observation_tick + 1,
        observation=observation,
    )


def test_matching_effective_experiment_is_bound_once() -> None:
    ledger, _ = _production_case()
    case = next(
        row
        for row in ledger.pending_cases
        if row.target_kind.value == "production_outcome"
    )
    tick = case.issued_observation_tick + 1
    observation = _observation(tick, include_self=True)
    bound = bind_scientific_model_execution(
        ledger, _command(), tick=tick, observation=observation
    )
    assert len(bound.bindings) == 1
    assert bound.bindings[0].case_id == case.case_id
    assert bound.bindings[0].comparability is ModelExecutionComparability.COMPARABLE
    again = bind_scientific_model_execution(
        bound, _command(), tick=tick, observation=observation
    )
    assert len(again.bindings) == 1
    assert again.cases == bound.cases


def test_original_pre_loop_command_is_not_bound() -> None:
    ledger, _ = _production_case()
    case = next(
        row
        for row in ledger.pending_cases
        if row.target_kind.value == "production_outcome"
    )
    tick = case.issued_observation_tick + 1
    observation = _observation(tick, include_self=True)
    for command in (
        _command(operand="barley"),
        _command(operator=ExperimentOperator.VARY_PROCESS),
        _command(process=ExperimentProcessToken.CRAFT),
        object(),
    ):
        bound = bind_scientific_model_execution(
            ledger, command, tick=tick, observation=observation
        )
        assert bound.bindings == ()


def test_changed_and_unknown_conditions_are_recorded() -> None:
    ledger, _ = _production_case()
    case = next(
        row
        for row in ledger.pending_cases
        if row.target_kind.value == "production_outcome"
    )
    tick = case.issued_observation_tick + 1
    changed = bind_scientific_model_execution(
        ledger,
        _command(),
        tick=tick,
        observation=_observation(tick, season=Season.WINTER, include_self=True),
    )
    assert (
        changed.bindings[0].comparability
        is ModelExecutionComparability.CHANGED_CONDITIONS
    )
    unknown = bind_scientific_model_execution(
        ledger,
        _command(),
        tick=tick,
        observation=_observation(tick, season=None, include_self=True),
    )
    assert (
        unknown.bindings[0].comparability
        is ModelExecutionComparability.UNKNOWN_CONDITIONS
    )


def test_binding_requires_the_exact_owner_and_issue_tick() -> None:
    ledger, _ = _production_case()
    case = next(
        row
        for row in ledger.pending_cases
        if row.target_kind.value == "production_outcome"
    )
    wrong_tick = bind_scientific_model_execution(
        ledger,
        _command(),
        tick=case.issued_observation_tick,
        observation=_observation(case.issued_observation_tick, include_self=True),
    )
    assert wrong_tick.bindings == ()
    with pytest.raises(ValueError, match="invalid_type"):
        bind_scientific_model_execution(
            object(),  # type: ignore[arg-type]
            _command(),
            tick=case.issued_observation_tick + 1,
            observation=_observation(case.issued_observation_tick + 1),
        )


def _base():
    bodies = (alive_body("body-1"), alive_body("body-2"))
    agents = tuple(
        AgentRunnerSpec(
            agent_id=AgentId(f"agent-{index + 1}"),
            entity_id=bodies[index].entity_id,
            cognition=AgentCognitionSpec(agent_id=AgentId(f"agent-{index + 1}")),
        )
        for index in range(2)
    )
    return base_runner_config_from_scenario(
        seed=41,
        stochastic_identity="scientific-model-runtime",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-scientific-model-runtime"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=bodies,
            weather=(make_weather(),),
        ),
        agents=agents,
        max_ticks=1,
    )


def _arm(condition_id: str):
    definition = scientific_hypotheses_scenario(_base(), max_ticks=64)
    config = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == condition_id
    )
    config = replace(
        config,
        agents=tuple(
            replace(
                agent,
                cognition=replace(
                    agent.cognition,
                    production_catalog=example_production_catalog(),
                ),
            )
            for agent in config.agents
        ),
    )
    return replace(config, stop_policy=RunnerStopPolicy(max_ticks=1))


@pytest.mark.asyncio
async def test_science_arm_commits_owner_predictive_state() -> None:
    runner = await SimulationRunner.from_config(
        _arm("science-enabled"),
        run_id=RunId("run-scientific-model-runtime"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        await runner.run()
    ledgers = [
        runtime._loop.scientific_model_ledger_if_present()
        for runtime in runner.runtimes
    ]
    assert all(type(ledger) is ScientificModelLedger for ledger in ledgers)
    assert [ledger.owner_id.value for ledger in ledgers] == [
        "agent-1",
        "agent-2",
    ]


@pytest.mark.asyncio
async def test_science_off_arm_never_carries_predictive_state() -> None:
    runner = await SimulationRunner.from_config(
        _arm("science-baseline"),
        run_id=RunId("run-scientific-model-baseline"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        await runner.run()
    assert all(
        runtime._loop.scientific_model_ledger_if_present() is None
        for runtime in runner.runtimes
    )
