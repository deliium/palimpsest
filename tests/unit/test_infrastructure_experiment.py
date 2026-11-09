"""Registration smoke for off-gate experiment ``infrastructure_networks@1``."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from agents.models import AgentId
from experiments import (
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    experiment_infrastructure_networks,
)
from experiments.catalog import base_runner_config_from_scenario
from experiments.models import ExperimentDefinition
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from simulation.models import SimulationRunConfig
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    SimulationRunnerConfig,
    WorldScenarioSpec,
)
from tests.simulation_helpers import (
    alive_body,
    connected_locations,
    make_item,
    make_weather,
)
from world._infrastructure import effective_travel_duration
from world._skills import (
    ObjectiveSkillLedger,
    SkillDomain,
    default_objective_skill_policy,
)
from world.actions import ContributeCollectiveProject, StartCollectiveProject, Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.infrastructure import InfrastructureKind
from world.models import non_lethal_physical_rules
from world.values import ItemKind

pytestmark = pytest.mark.unit


def _base() -> SimulationRunnerConfig:
    locations = connected_locations(("loc-a", "Camp"), ("loc-b", "Field"))
    alice = alive_body("body-a", location_id="loc-a", carry_capacity=16)
    return base_runner_config_from_scenario(
        seed=56,
        stochastic_identity="cmp-infra-networks",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-infra-exp"),
            revision=WorldRevision(0),
            physical_rules=non_lethal_physical_rules(),
            locations=locations,
            bodies=(alice,),
            weather=(
                make_weather(location_id="loc-a"),
                make_weather(location_id="loc-b"),
            ),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=AgentId("agent-1"),
                entity_id=alice.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-1")),
            ),
        ),
        max_ticks=24,
    )


def _definition() -> ExperimentDefinition:
    return experiment_infrastructure_networks(_base())


def _arm(arm_id: str) -> SimulationRunnerConfig:
    return next(
        item.runner_config
        for item in _definition().conditions
        if item.condition_id == arm_id
    )


def test_infrastructure_networks_registered_off_v1_gate(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="experiments.catalog")
    gate = Path("tests/unit/test_v1_regression_gate.py").read_text(encoding="utf-8")
    definition = _definition()
    assert "infrastructure_networks@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert "infrastructure_networks@1" not in gate
    assert definition.experiment_id == "infrastructure_networks@1"
    assert [item.condition_id for item in definition.conditions] == [
        "infra-channel-off",
        "infra-treatment",
    ]
    assert (
        "experiment_registered experiment_id=infrastructure_networks@1 arms=2"
        in caplog.text
    )
    off = _arm("infra-channel-off")
    on = _arm("infra-treatment")
    assert off.schema_version == RUNNER_SCHEMA_VERSION_V56
    assert on.schema_version == RUNNER_SCHEMA_VERSION_V56
    assert off.collective_projects is not None
    assert on.collective_projects is not None
    assert off.v4_capability_flags.infrastructure_networks is False
    assert on.v4_capability_flags.infrastructure_networks is True
    assert "supply_chains" not in on.v4_capability_flags.enabled_names()
    outcome = on.agents[0].initial_goals[0].outcome
    assert outcome is not None
    assert outcome.outcome_code == "collective_project:start:road"


def test_treatment_completes_road_with_travel_effect() -> None:
    stones = tuple(
        make_item(
            f"stone-{index}",
            name="stone",
            kind=ItemKind.MATERIAL,
            location_id=None,
            holder_id="body-a",
        )
        for index in range(1, 4)
    )
    inventory = tuple(item.entity_id for item in stones)
    locations = connected_locations(("loc-a", "Camp"), ("loc-b", "Field"))
    body = alive_body(
        "body-a", location_id="loc-a", inventory=inventory, carry_capacity=16
    )
    skill_ids = (body.entity_id,)
    ledger = ObjectiveSkillLedger.bootstrap(skill_ids).apply_summed_deltas(
        {body.entity_id: {SkillDomain.BUILDING: 1.0}}
    )
    engine = WorldEngine(
        config=SimulationRunConfig(
            seed=56, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=WorldBootstrap(
            world_id=WorldId("world-infra-treatment"),
            revision=WorldRevision(0),
            locations=locations,
            bodies=(body,),
            items=stones,
            weather=tuple(
                make_weather(location_id=loc.entity_id.value) for loc in locations
            ),
            registrations=(
                AgentRegistration(AgentId("agent-1"), body.entity_id),
            ),
        ),
        collective_projects_active=True,
        infrastructure_networks_active=True,
        skill_policy=default_objective_skill_policy(),
        skill_entity_ids=skill_ids,
        skill_ledger=ledger,
    )
    agent = AgentId("agent-1")

    def step(command: object) -> None:
        batch = engine.observe()
        engine.resolve_tick(
            (ActionSubmission(token=batch.token, agent_id=agent, command=command),)
        )

    step(StartCollectiveProject("road", target_location_id=EntityId("loc-b")))
    project_id = next(iter(engine._snapshot.world.state.collective_projects))
    for item in stones:
        step(ContributeCollectiveProject(project_id, item.entity_id))
    for _ in range(5):
        step(ContributeCollectiveProject(project_id))
    step(Wait())
    assets = engine._snapshot.world.state.infrastructure
    assert assets is not None
    roads = [
        asset
        for asset in assets.values()
        if asset.kind is InfrastructureKind.ROAD
    ]
    assert len(roads) == 1
    assert roads[0].endpoint_location_id == EntityId("loc-b")
    duration = effective_travel_duration(
        assets,
        origin_id=EntityId("loc-a"),
        destination_id=EntityId("loc-b"),
        base_duration=3,
    )
    assert duration == 2


def test_control_flag_keeps_infrastructure_inert() -> None:
    off = _arm("infra-channel-off")
    assert off.v4_capability_flags.infrastructure_networks is False
    locations = connected_locations(("loc-a", "Camp"), ("loc-b", "Field"))
    body = alive_body("body-a", location_id="loc-a")
    engine = WorldEngine(
        config=SimulationRunConfig(
            seed=56, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=WorldBootstrap(
            world_id=WorldId("world-infra-control"),
            revision=WorldRevision(0),
            locations=locations,
            bodies=(body,),
            weather=tuple(
                make_weather(location_id=loc.entity_id.value) for loc in locations
            ),
            registrations=(
                AgentRegistration(AgentId("agent-1"), body.entity_id),
            ),
        ),
        collective_projects_active=True,
        infrastructure_networks_active=False,
    )
    batch = engine.observe()
    engine.resolve_tick(
        (
            ActionSubmission(
                token=batch.token,
                agent_id=AgentId("agent-1"),
                command=StartCollectiveProject(
                    "road", target_location_id=EntityId("loc-b")
                ),
            ),
        )
    )
    assert engine._snapshot.world.state.infrastructure is None
    assert engine._snapshot.world.state.collective_projects == {}
