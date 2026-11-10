# mypy: ignore-errors

"""Supply-chain activation, tool-assisted harvesting, and local planning."""

from __future__ import annotations

import dataclasses
import logging
from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest

from agents.cognition.configuration import CognitionLoopConfig
from agents.cognition.production import (
    RecipeBelief,
    RecipeBeliefSet,
    compile_production_command,
    production_stage_priority,
)
from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation import compatibility
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V56,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    AgentCognitionSpec,
    AgentRunnerSpec,
    V4CapabilityFlags,
    WorldScenarioSpec,
)
from simulation.v4_architecture import V4_CAPABILITY_FLAGS
from tests.physical_helpers import physical_config, two_location_fixture
from tests.simulation_helpers import (
    alive_body,
    make_item,
    make_location,
    make_resource,
    make_weather,
)
from world._state import World, rebuild_world_state
from world.actions import Build, Craft, Harvest
from world.events import ResourceHarvested
from world.identifiers import EntityId, RecipeId, WorldId, WorldRevision
from world.models import default_physical_rules
from world.production import (
    ProductionCatalog,
    ToolMark,
    ToolRole,
    example_production_catalog,
)
from world.supply_chain import (
    SUPPLY_CHAIN_HARVEST_TOOL_PROBABILITY_GAIN,
    harvest_tool_probability_gain,
    supply_chain_production_catalog,
    validate_production_chain_catalog,
)
from world.values import ItemKind, ResourceKind

pytestmark = pytest.mark.unit

_GRAIN = EntityId("res-grain")
_TOOL = EntityId("item-tool")
_HARVEST_GRAIN = RecipeId("harvest_grain")


def _fixture(*, grain: bool = True, tool: bool = False):
    base = two_location_fixture(item_on_ground=False)
    resources = base.resources
    if grain:
        resource = make_resource(
            _GRAIN.value,
            name="grain",
            kind=ResourceKind.FOOD,
            location_id="loc-1",
            quantity=3.0,
            maximum_quantity=5.0,
            regeneration_per_tick=0.0,
        )
        resources = (*resources, resource)
    items = ()
    inventory: tuple[EntityId, ...] = ()
    if tool:
        item = make_item(
            _TOOL.value,
            name="fine_tool",
            kind=ItemKind.TOOL,
            location_id=None,
            holder_id="body-1",
        )
        items = (item,)
        inventory = (_TOOL,)
    bodies = (
        alive_body("body-1", inventory=inventory),
        alive_body("body-2"),
    )
    return dataclasses.replace(
        base,
        resources=resources,  # type: ignore[arg-type]
        items=items,
        bodies=bodies,
    )


def _engine(
    fixture,
    *,
    catalog: ProductionCatalog | None = None,
    supply: bool = False,
    seed: int = 7,
) -> WorldEngine:
    return WorldEngine(
        config=physical_config(seed),
        bootstrap=fixture.as_bootstrap(),
        production_catalog=catalog,
        supply_chains_active=supply,
    )


def _act(engine: WorldEngine, agent: str, command: object):
    batch = engine.observe()
    return engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId(agent), command),)  # type: ignore[arg-type]
    )


def _observation(
    *,
    resources: tuple[object, ...] = (),
    items: tuple[object, ...] = (),
    structures: tuple[object, ...] = (),
) -> SimpleNamespace:
    return SimpleNamespace(
        resources=resources, items=items, structures=structures, occurrences=()
    )


def _resource(name: str, entity_id: str = "res-1") -> SimpleNamespace:
    return SimpleNamespace(entity_id=EntityId(entity_id), name=name, quantity=2.0)


def _held(entity_id: str, kind: ItemKind) -> SimpleNamespace:
    return SimpleNamespace(
        entity_id=EntityId(entity_id),
        kind=kind,
        placement=SimpleNamespace(value="held_by_self"),
    )


def _beliefs(*recipe_ids: str) -> RecipeBeliefSet:
    return RecipeBeliefSet(
        AgentId("agent-1"),
        tuple(RecipeBelief(RecipeId(value)) for value in recipe_ids),
    )


def test_flag_is_owned_counts_are_seven() -> None:
    assert "supply_chains" in compatibility.V4_OWNED_CAPABILITY_FLAGS
    assert len(compatibility.V4_OWNED_CAPABILITY_FLAGS) == 7
    flags = V4CapabilityFlags(supply_chains=True)
    assert flags.owned_enabled_names() == ("supply_chains",)
    assert flags.unimplemented_enabled_names() == ()
    assert "supply_chains" in V4_CAPABILITY_FLAGS


def test_flag_requires_v56() -> None:
    assert RUNNER_SCHEMA_VERSION_V56 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert "runner-config-v57" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    config = replace(
        _base_config(RUNNER_SCHEMA_VERSION_V4),
    )
    assert config.schema_version == RUNNER_SCHEMA_VERSION_V4
    with pytest.raises(ValueError, match="code=v4_capability_requires_v56"):
        replace(config, v4_capability_flags=V4CapabilityFlags(supply_chains=True))


def test_engine_rejects_missing_catalog_when_active(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.ERROR, logger="simulation.engine"):
        with pytest.raises(ValueError, match="supply_chain_catalog_missing"):
            _engine(_fixture(), catalog=None, supply=True)
    assert "supply_chain_activation_rejected" in caplog.text


def test_engine_rejects_legacy_catalog_when_active() -> None:
    with pytest.raises(ValueError, match="supply_chain_catalog_no_chain"):
        _engine(_fixture(), catalog=example_production_catalog(), supply=True)


def test_engine_accepts_extended_catalog() -> None:
    catalog = supply_chain_production_catalog(example_production_catalog())
    engine = _engine(_fixture(), catalog=catalog, supply=True)
    assert engine._supply_chains_active is True


def test_engine_inactive_does_not_validate() -> None:
    engine = _engine(_fixture(), catalog=ProductionCatalog(), supply=False)
    assert engine._supply_chains_active is False


def test_runner_passes_flag_to_engine() -> None:
    external = supply_chain_production_catalog(example_production_catalog())
    assert validate_production_chain_catalog(external).edge_count == 8
    config = _v56_config_with_catalog(external)
    runner = _run(SimulationRunner.from_config(config, run_id=_run_id("supply")))
    assert runner.engine._supply_chains_active is True
    assert (
        runner.engine._production_catalog is not None
        and runner.engine._production_catalog.recipe_count == 12
    )


def test_restore_preserves_activation_signature() -> None:
    import inspect

    parameters = inspect.signature(WorldEngine.restore_from_snapshot).parameters
    assert "supply_chains_active" in parameters
    component = inspect.signature(WorldEngine.restore_from_verified_batches).parameters
    assert "supply_chains_active" in component


def test_other_v4_flag_still_fails_closed() -> None:
    import asyncio

    from simulation.runner import RunnerConstructionError

    config = replace(_v56_config(), v4_capability_flags=V4CapabilityFlags(science=True))
    with pytest.raises(RunnerConstructionError):
        asyncio.run(SimulationRunner.from_config(config, run_id=_run_id("science")))


def test_no_runner_config_v57_added() -> None:
    assert "runner-config-v57" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS


def test_harvest_probability_gain_with_strike_tool() -> None:
    state = rebuild_world_state(
        _fixture(tool=True).as_state(),
        tool_marks={_TOOL: ToolMark(_TOOL, ToolRole.STRIKE)},
    )
    recipe = next(
        recipe
        for recipe in supply_chain_production_catalog(
            example_production_catalog()
        ).recipes
        if recipe.recipe_id == _HARVEST_GRAIN
    )
    assert (
        harvest_tool_probability_gain(state, EntityId("body-1"), recipe)
        == SUPPLY_CHAIN_HARVEST_TOOL_PROBABILITY_GAIN
    )


def test_harvest_probability_gain_without_tool() -> None:
    state = _fixture(tool=False).as_state()
    recipe = next(
        recipe
        for recipe in supply_chain_production_catalog(
            example_production_catalog()
        ).recipes
        if recipe.recipe_id == _HARVEST_GRAIN
    )
    assert harvest_tool_probability_gain(state, EntityId("body-1"), recipe) == 0.0


def test_probability_gain_ignored_for_craft() -> None:
    state = rebuild_world_state(
        _fixture(tool=True).as_state(),
        tool_marks={_TOOL: ToolMark(_TOOL, ToolRole.STRIKE)},
    )
    recipe = next(
        recipe
        for recipe in supply_chain_production_catalog(
            example_production_catalog()
        ).recipes
        if recipe.recipe_id.value == "craft_plank"
    )
    assert harvest_tool_probability_gain(state, EntityId("body-1"), recipe) == 0.0


def test_probability_clamped_to_one(caplog: pytest.LogCaptureFixture) -> None:
    catalog = supply_chain_production_catalog(example_production_catalog())
    fixture = _fixture(tool=True)
    engine = _engine(fixture, catalog=catalog, supply=True)
    marked = rebuild_world_state(
        engine._snapshot.world.state,
        tool_marks={_TOOL: ToolMark(_TOOL, ToolRole.STRIKE)},
    )
    engine._snapshot = dataclasses.replace(
        engine._snapshot,
        world=World(engine._snapshot.world.world_id, marked),
    )
    with caplog.at_level(logging.DEBUG):
        result = _act(engine, "agent-1", Harvest(_HARVEST_GRAIN, _GRAIN))
    details = [
        record.event.details
        for record in result.events
        if type(record.event.details) is ResourceHarvested
    ]
    assert details and details[0].success is True
    assert "harvest_tool_assist gain=0.1" in caplog.text
    assert "production_success_draw" not in caplog.text
    assert engine._snapshot.world.state.items  # tool is not consumed


def test_plan_prefers_harvest_over_craft() -> None:
    observation = _observation(resources=(_resource("grain"),))
    command = compile_production_command(
        _beliefs("craft_plank", "harvest_grain"),
        observation,
        supply_chains_active=True,
    )
    assert type(command) is Harvest


def test_plan_orders_craft_before_build() -> None:
    observation = _observation(
        resources=(_resource("grain"),),
        items=(_held("mat-1", ItemKind.MATERIAL),),
    )
    command = compile_production_command(
        _beliefs("build_shelter", "craft_plank"),
        observation,
        supply_chains_active=True,
    )
    assert type(command) is Craft


def test_plan_tie_breaks_on_recipe_id() -> None:
    observation = _observation(
        resources=(_resource("grain", "res-grain"), _resource("wood", "res-wood"))
    )
    command = compile_production_command(
        _beliefs("harvest_wood", "harvest_grain"),
        observation,
        supply_chains_active=True,
    )
    assert type(command) is Harvest
    assert command.recipe_id == _HARVEST_GRAIN


def test_selected_recipe_overrides_stage_order() -> None:
    observation = _observation(resources=(_resource("grain"),))
    command = compile_production_command(
        _beliefs("harvest_grain", "craft_plank"),
        observation,
        selected_recipe_id=RecipeId("craft_plank"),
        supply_chains_active=True,
    )
    assert type(command) is Craft


def test_veto_returns_none() -> None:
    assert (
        compile_production_command(
            _beliefs("harvest_grain"),
            _observation(resources=(_resource("grain"),)),
            vetoed=True,
            supply_chains_active=True,
        )
        is None
    )


def test_inactive_flag_preserves_legacy_order() -> None:
    observation = _observation(
        resources=(_resource("grain"),),
        items=(_held("mat-1", ItemKind.MATERIAL),),
    )
    beliefs = _beliefs("build_shelter", "harvest_grain")
    legacy = compile_production_command(beliefs, observation)
    assert type(legacy) is Build
    chained = compile_production_command(
        beliefs, observation, supply_chains_active=True
    )
    assert type(chained) is Harvest


def test_loop_config_validates_activation() -> None:
    config = CognitionLoopConfig(supply_chains_active=True)
    assert config.supply_chains_active is True
    with pytest.raises(TypeError):
        CognitionLoopConfig(supply_chains_active=1)  # type: ignore[arg-type]


def test_production_stage_priority_is_total() -> None:
    assert production_stage_priority(RecipeId("harvest_grain")) == 0
    assert production_stage_priority(RecipeId("craft_plank")) == 1
    assert production_stage_priority(RecipeId("build_shelter")) == 2
    assert production_stage_priority(RecipeId("repair_shelter")) == 3
    assert production_stage_priority(RecipeId("store_food")) == 4
    assert production_stage_priority(RecipeId("mill_grain")) == 5


def _run_id(value: str):
    from simulation.models import RunId

    return RunId(f"run-supply-{value}")


def _run(awaitable: Any) -> Any:
    import asyncio

    return asyncio.run(awaitable)


def _base_config(schema_version: str):
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    config = base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="cmp-supply-chain",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-supply"),
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
    return replace(config, schema_version=schema_version)


def _v56_config():
    return _base_config(RUNNER_SCHEMA_VERSION_V56)


def _v56_config_with_catalog(catalog: ProductionCatalog):
    config = _v56_config()
    agent = config.agents[0]
    return replace(
        config,
        agents=(
            replace(
                agent,
                cognition=replace(agent.cognition, production_catalog=catalog),
            ),
        ),
        v4_capability_flags=V4CapabilityFlags(supply_chains=True),
    )
