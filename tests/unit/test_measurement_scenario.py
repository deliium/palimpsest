# mypy: ignore-errors

"""Four-arm measurement opportunity scenario without forced emergence."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from experiments.measurement_scenario import measurement_instruments_scenario
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    RUNNER_SCHEMA_VERSION_V57,
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_item, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit


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
        seed=11,
        stochastic_identity="measurement-scenario",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-measurement"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=bodies,
            weather=(make_weather(),),
        ),
        agents=agents,
        max_ticks=64,
    )


def test_four_closed_arms_share_world_and_seed() -> None:
    definition = measurement_instruments_scenario(_base())
    assert [row.condition_id for row in definition.conditions] == [
        "measurement-absent",
        "measurement-unbiased",
        "measurement-biased",
        "measurement-damaged",
    ]
    configs = [row.runner_config for row in definition.conditions]
    assert {config.seed for config in configs} == {11}
    assert configs[0].schema_version == RUNNER_SCHEMA_VERSION_V56
    assert configs[0].measurement_instruments is None
    assert all(
        config.schema_version == RUNNER_SCHEMA_VERSION_V57 for config in configs[1:]
    )
    items = [
        tuple(item.entity_id for item in config.scenario.items) for config in configs
    ]
    assert len(set(items)) == 1
    biased = configs[2].measurement_instruments.instruments[0]
    unbiased = configs[1].measurement_instruments.instruments[0]
    damaged = configs[3].measurement_instruments.instruments[0]
    assert biased.intrinsic_bias_milli == 5000
    assert unbiased.intrinsic_bias_milli == 0
    assert damaged.damage_milli == 750


def test_full_inventory_is_rejected_without_mutation() -> None:
    base = _base()
    from dataclasses import replace

    from world.values import ItemKind

    crowded = base.scenario.bodies[0]
    existing = make_item(
        "item-existing",
        name="Existing",
        kind=ItemKind.GENERIC,
        location_id=None,
        holder_id="body-1",
    )
    tight = replace(
        crowded,
        carry_capacity=replace(crowded.carry_capacity, value=1),
        inventory=(existing.entity_id,),
    )
    with pytest.raises(ValueError, match="carry_capacity"):
        measurement_instruments_scenario(
            replace(
                base,
                scenario=replace(
                    base.scenario,
                    bodies=(tight, base.scenario.bodies[1]),
                    items=(existing,),
                ),
            )
        )


@pytest.mark.asyncio
async def test_every_arm_builds_a_real_runner_with_complete_holdings() -> None:
    base = _base()
    before_items = tuple(item.entity_id for item in base.scenario.items)
    before_bodies = tuple(body.inventory for body in base.scenario.bodies)
    definition = measurement_instruments_scenario(base, max_ticks=64)
    assert tuple(item.entity_id for item in base.scenario.items) == before_items
    assert tuple(body.inventory for body in base.scenario.bodies) == before_bodies

    configs = [row.runner_config for row in definition.conditions]
    shared_items = {
        tuple(item.entity_id for item in config.scenario.items)
        for config in configs
    }
    assert len(shared_items) == 1
    for index, config in enumerate(configs):
        runner = await SimulationRunner.from_config(
            config,
            run_id=RunId(f"run-measurement-arm-{index}"),
            factories=RunnerDependencyFactories(),
        )
        async with runner:
            pass
        items = {item.entity_id: item for item in config.scenario.items}
        for founder in config.agents[:2]:
            body = next(
                row
                for row in config.scenario.bodies
                if row.entity_id == founder.entity_id
            )
            additions = [
                item_id
                for item_id in body.inventory
                if items[item_id].name.startswith("measurement")
            ]
            assert len(additions) == 2
            assert sum(items[item_id].load.value for item_id in additions) == 2
            for item_id in additions:
                assert items[item_id].holder_id == founder.entity_id

