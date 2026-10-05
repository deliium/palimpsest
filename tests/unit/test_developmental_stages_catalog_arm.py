"""Off-gate Experiment AG for developmental stages on runner-config-v26."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from experiments import (
    developmental_stages_profile,
    experiment_ag_developmental_stages,
    v3_scaffolding_profile,
)
from experiments.catalog import base_runner_config_from_scenario
from observer.version import SEMANTIC_EVENT_TYPES
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V24,
    RUNNER_SCHEMA_VERSION_V25,
    RUNNER_SCHEMA_VERSION_V26,
    AgentCognitionSpec,
    AgentRunnerSpec,
    SkillLearningMode,
    V3CapabilityFlags,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.effects import DeathCause
from world.events import Died, LifecycleStageChanged
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.developmental_stages_catalog_arm")


def _base():
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=131,
        stochastic_identity="cmp-ag-developmental",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-ag-developmental"),
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
            ),
        ),
        max_ticks=28,
    )


def test_ag_profile_requires_v26_and_developmental_children() -> None:
    definition = experiment_ag_developmental_stages(_base(), max_ticks=12)
    assert definition.experiment_id == "experiment-ag-developmental-stages"
    gradual_off = next(
        item
        for item in definition.conditions
        if item.condition_id == "ag-gradual-aging-off"
    )
    assert gradual_off.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V26
    assert developmental_stages_profile(gradual_off.runner_config) is gradual_off.runner_config
    lifecycle = gradual_off.runner_config.population_lifecycle
    assert lifecycle is not None
    stage_ids = tuple(item.stage_id.value for item in lifecycle.stage_thresholds)
    assert stage_ids == ("dependent", "learning", "independent", "elder")
    dependent = next(
        effect
        for effect in lifecycle.stage_capability_effects
        if effect.stage_id.value == "dependent"
    )
    assert dependent.denied_command_kinds == ("attack", "harvest")
    elder = next(
        effect
        for effect in lifecycle.stage_capability_effects
        if effect.stage_id.value == "elder"
    )
    independent = next(
        effect
        for effect in lifecycle.stage_capability_effects
        if effect.stage_id.value == "independent"
    )
    assert elder.denied_command_kinds == ()
    assert independent.denied_command_kinds == ()
    off = definition.conditions[0].runner_config
    assert v3_scaffolding_profile(off) is off
    with pytest.raises(ValueError, match="v3_scaffolding_flags_enabled"):
        v3_scaffolding_profile(gradual_off.runner_config)


def test_ag_arms_cover_gradual_and_skill_modes() -> None:
    definition = experiment_ag_developmental_stages(_base(), max_ticks=10)
    by_id = {item.condition_id: item.runner_config for item in definition.conditions}
    assert set(by_id) == {
        "ag-developmental-off",
        "ag-gradual-aging-off",
        "ag-gradual-aging-on",
        "ag-skill-learning-on",
    }
    assert by_id["ag-gradual-aging-off"].population_lifecycle is not None
    assert (
        by_id["ag-gradual-aging-off"].population_lifecycle.gradual_aging.intra_stage_interpolation
        is False
    )
    assert (
        by_id["ag-gradual-aging-on"].population_lifecycle.gradual_aging.intra_stage_interpolation
        is True
    )
    skill = by_id["ag-skill-learning-on"].agents[0].cognition.skill_learning_mode
    assert skill is SkillLearningMode.DETERMINISTIC
    skill_off = by_id["ag-gradual-aging-off"].agents[0].cognition.skill_learning_mode
    assert skill_off is SkillLearningMode.DISABLED
    # AE/AF schema pins unchanged by AG presence.
    assert RUNNER_SCHEMA_VERSION_V24 != RUNNER_SCHEMA_VERSION_V26
    assert RUNNER_SCHEMA_VERSION_V25 != RUNNER_SCHEMA_VERSION_V26
    assert len(SEMANTIC_EVENT_TYPES) == 41


@pytest.mark.asyncio
async def test_ag_on_arm_crosses_stages_and_assigned_eol() -> None:
    definition = experiment_ag_developmental_stages(_base(), max_ticks=28)
    on = next(
        item
        for item in definition.conditions
        if item.condition_id == "ag-gradual-aging-off"
    )
    _LOG.info(
        "case_id=ag_on_arm experiment_id=%s schema_version=%s",
        definition.experiment_id,
        on.runner_config.schema_version,
    )
    async with await SimulationRunner.from_config(
        on.runner_config, run_id=RunId("run-ag-on")
    ) as runner:
        await runner.run()
        assert on.runner_config.v3_capability_flags == V3CapabilityFlags(
            generational_population=True
        )
        stages = [
            event.details.new_stage
            for event in runner.engine._snapshot.event_history
            if type(event.details) is LifecycleStageChanged
        ]
        deaths = [
            event.details
            for event in runner.engine._snapshot.event_history
            if type(event.details) is Died
        ]
        assigned = runner.engine.lifecycle_records[0].assigned_lifespan_ticks
        _LOG.debug(
            "case_id=ag_on_arm stage_transitions=%s death_count=%s assigned=%s",
            stages,
            len(deaths),
            assigned,
        )
        assert "learning" in stages or "independent" in stages or "elder" in stages
        assert any(death.death_cause is DeathCause.LIFESPAN for death in deaths)
        assert 16 <= assigned <= 24
