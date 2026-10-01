"""Engine resolution for the opt-in production catalog."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from tests.physical_helpers import (
    PhysicalWorldFixture,
    physical_config,
    two_location_fixture,
)
from tests.simulation_helpers import alive_body, make_item, make_resource
from world._production import (
    adjusted_production_probability,
    complete_due_jobs,
    effective_duration,
)
from world._skills import default_objective_skill_policy
from world._state import rebuild_world_state
from world.actions import Attack, Build, Craft, Harvest, Move, Repair, Search, Store
from world.events import (
    CraftStarted,
    ItemCrafted,
    ItemStored,
    ResourceHarvested,
    StructureBuilt,
    StructureRepaired,
)
from world.identifiers import EntityId, RecipeId
from world.models import LifeStatus, copy_body, default_physical_rules
from world.production import (
    CERTAIN_SUCCESS_PROBABILITY,
    CRAFT_SUCCESS_PROBABILITY,
    HARVEST_SUCCESS_PROBABILITY,
    ProductionCatalog,
    ProductionJob,
    ToolMark,
    ToolRole,
    example_production_catalog,
)
from world.values import Health, ItemKind, ResourceKind

pytestmark = pytest.mark.unit

_WOOD = RecipeId("harvest_wood")
_TOOL = RecipeId("craft_tool")
_SHELTER = RecipeId("build_shelter")
_REPAIR = RecipeId("repair_shelter")
_STORE = RecipeId("store_food")
_PRODUCTION = (
    ResourceHarvested,
    CraftStarted,
    ItemCrafted,
    StructureBuilt,
    StructureRepaired,
    ItemStored,
)


def _fixture(
    *,
    resources: tuple[object, ...] | None = None,
    items: tuple[object, ...] | None = None,
    bodies: tuple[object, ...] | None = None,
) -> PhysicalWorldFixture:
    base = two_location_fixture(item_on_ground=False)
    return PhysicalWorldFixture(
        world_id=base.world_id,
        locations=base.locations,
        bodies=base.bodies if bodies is None else bodies,  # type: ignore[arg-type]
        items=() if items is None else items,  # type: ignore[arg-type]
        resources=base.resources if resources is None else resources,  # type: ignore[arg-type]
        weather=base.weather,
        registrations=base.registrations,
    )


def _wood_resource(*, quantity: float = 2.0) -> object:
    return make_resource(
        "res-wood",
        name="wood",
        kind=ResourceKind.MATERIAL,
        location_id="loc-1",
        quantity=quantity,
        maximum_quantity=5.0,
        regeneration_per_tick=0.0,
    )


def _held(
    entity_id: str,
    name: str,
    kind: ItemKind = ItemKind.MATERIAL,
) -> object:
    return make_item(
        entity_id,
        name=name,
        kind=kind,
        location_id=None,
        holder_id="body-1",
    )


def _crafter(*item_ids: str) -> tuple[object, ...]:
    return (
        alive_body(
            "body-1",
            inventory=tuple(EntityId(item_id) for item_id in item_ids),
        ),
        alive_body("body-2"),
    )


def _engine(
    fixture: PhysicalWorldFixture,
    *,
    seed: int = 1,
    catalog: ProductionCatalog | None = None,
    rules: object | None = None,
    skill: bool = False,
) -> WorldEngine:
    kwargs: dict[str, object] = {}
    if catalog is not None:
        kwargs["production_catalog"] = catalog
    if skill:
        kwargs["skill_policy"] = default_objective_skill_policy()
        kwargs["skill_entity_ids"] = (EntityId("body-1"),)
    return WorldEngine(
        config=physical_config(seed, rules=rules),  # type: ignore[arg-type]
        bootstrap=fixture.as_bootstrap(),
        **kwargs,
    )


def _act(engine: WorldEngine, agent: str, command: object):
    batch = engine.observe()
    return engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId(agent), command),)  # type: ignore[arg-type]
    )


def _kinds(result: object) -> list[object]:
    return [
        record.event.details
        for record in result.events  # type: ignore[attr-defined]
        if type(record.event.details) in _PRODUCTION
    ]


def _craft_fixture(*pairs: tuple[str, str]) -> PhysicalWorldFixture:
    items = tuple(_held(entity_id, name) for entity_id, name in pairs)
    return _fixture(
        items=items,
        bodies=_crafter(*(entity_id for entity_id, _name in pairs)),
    )


def test_empty_catalog_rejects_without_a_draw(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fixture = _fixture(resources=(_wood_resource(),))
    engine = _engine(fixture, catalog=ProductionCatalog())
    with caplog.at_level(logging.DEBUG):
        result = _act(engine, "agent-1", Harvest(_WOOD, EntityId("res-wood")))
    assert result.resolutions[0].status is ActionResolutionStatus.REJECTED
    assert _kinds(result) == []
    assert "production_success_draw" not in caplog.text
    assert "production_disabled" in caplog.text
    assert all(record.event.schema_version == 5 for record in result.events)

    left = _act(
        _engine(fixture, seed=4, catalog=ProductionCatalog()),
        "agent-1",
        Search(),
    )
    right = _act(_engine(fixture, seed=4), "agent-1", Search())
    assert left.events[0].event.details.success == right.events[0].event.details.success


def test_harvest_emits_success_and_failure_without_logging_probability(
    caplog: pytest.LogCaptureFixture,
) -> None:
    saw_success = False
    saw_failure = False
    with caplog.at_level(logging.INFO, logger="simulation.engine"):
        for seed in range(1, 40):
            engine = _engine(
                _fixture(resources=(_wood_resource(),)),
                seed=seed,
                catalog=example_production_catalog(),
            )
            result = _act(engine, "agent-1", Harvest(_WOOD, EntityId("res-wood")))
            details = _kinds(result)
            assert len(details) == 1
            harvested = details[0]
            assert type(harvested) is ResourceHarvested
            assert harvested.duration_ticks == 1
            assert result.events[0].event.schema_version == 6
            inventory = engine._snapshot.world.state.bodies[
                EntityId("body-1")
            ].inventory
            if harvested.success:
                saw_success = True
                assert harvested.created_item_id in inventory
                assert harvested.resulting_resource_quantity == 1.0
            else:
                saw_failure = True
                assert harvested.created_item_id is None
                assert inventory == ()
                assert harvested.resulting_resource_quantity == 2.0
            if saw_success and saw_failure:
                break
    assert saw_success and saw_failure
    committed = [
        record.message
        for record in caplog.records
        if record.levelno == logging.INFO
        and record.message.startswith("production_event_committed ")
    ]
    assert committed
    assert all("0.80" not in message and "0.70" not in message for message in committed)


def test_scripted_craft_resolves_without_beliefs_and_unknown_recipe_rejects() -> None:
    fixture = _craft_fixture(("item-wood", "wood"), ("item-stone", "stone"))
    engine = _engine(fixture, catalog=example_production_catalog())
    unknown = _act(engine, "agent-1", Craft(RecipeId("craft_gold")))
    assert unknown.resolutions[0].status is ActionResolutionStatus.REJECTED
    assert _kinds(unknown) == []

    applied = _engine(fixture, catalog=example_production_catalog())
    result = _act(applied, "agent-1", Craft(_TOOL))
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    started = _kinds(result)[0]
    assert type(started) is CraftStarted
    assert started.duration_ticks == 2


def test_missing_materials_and_pending_craft(caplog: pytest.LogCaptureFixture) -> None:
    empty = _engine(
        _fixture(resources=(_wood_resource(quantity=0.0),)),
        catalog=example_production_catalog(),
    )
    with caplog.at_level(logging.WARNING, logger="world._production"):
        missing = _act(empty, "agent-1", Harvest(_WOOD, EntityId("res-wood")))
    assert missing.resolutions[0].status is ActionResolutionStatus.REJECTED
    assert "materials_unavailable" in caplog.text
    assert _kinds(missing) == []

    engine = None
    for seed in range(1, 40):
        candidate = _engine(
            _craft_fixture(("item-wood", "wood"), ("item-stone", "stone")),
            seed=seed,
            catalog=example_production_catalog(),
        )
        started = _act(candidate, "agent-1", Craft(_TOOL))
        details = _kinds(started)
        if type(details[0]) is CraftStarted and details[0].success:
            engine = candidate
            assert details[0].duration_ticks == 2
            assert EntityId("item-wood") not in engine._snapshot.world.state.items
            break
    assert engine is not None
    with caplog.at_level(logging.WARNING, logger="world._production"):
        busy = _act(engine, "agent-1", Move(EntityId("loc-2")))
    assert busy.resolutions[0].status is ActionResolutionStatus.REJECTED
    assert "actor_busy" in caplog.text
    crafted = [details for details in _kinds(busy) if type(details) is ItemCrafted]
    assert len(crafted) == 1
    assert crafted[0].resulting_holder_id == EntityId("body-1")
    assert engine._snapshot.world.state.production_jobs == {}
    tool_id = crafted[0].created_item_id
    assert engine._snapshot.world.state.tool_marks[tool_id].role is ToolRole.STRIKE


def test_dead_actor_drops_a_due_job() -> None:
    rules = replace(
        default_physical_rules(),
        attack_hit_probability=1.0,
        attack_damage_min=100,
        attack_damage_max_exclusive=101,
    )
    engine = None
    for seed in range(1, 40):
        candidate = _engine(
            _craft_fixture(("item-wood", "wood"), ("item-stone", "stone")),
            seed=seed,
            catalog=example_production_catalog(),
            rules=rules,
        )
        started = _act(candidate, "agent-1", Craft(_TOOL))
        if _kinds(started) and _kinds(started)[0].success:
            engine = candidate
            break
    assert engine is not None
    killed = _act(engine, "agent-2", Attack(EntityId("body-1")))
    assert killed.resolutions[0].status is ActionResolutionStatus.APPLIED
    assert not any(type(details) is ItemCrafted for details in _kinds(killed))
    state = engine._snapshot.world.state
    assert EntityId("body-1") not in state.production_jobs
    assert state.bodies[EntityId("body-1")].life_status is LifeStatus.DEAD


def test_strike_tool_reduces_craft_duration_to_one() -> None:
    recipe = example_production_catalog().recipe(_TOOL)
    assert recipe is not None
    state = _craft_fixture(
        ("item-wood", "wood"),
        ("item-stone", "stone"),
        ("item-tool", "tool"),
    ).as_state()
    marked = rebuild_world_state(
        state,
        tool_marks={
            EntityId("item-tool"): ToolMark(EntityId("item-tool"), ToolRole.STRIKE)
        },
    )
    assert effective_duration(state, EntityId("body-1"), recipe) == 2
    assert effective_duration(marked, EntityId("body-1"), recipe) == 1


def test_shelter_repair_and_store() -> None:
    items = (
        _held("mat-1", "wood"),
        _held("mat-2", "stone"),
        _held("mat-3", "plank"),
        _held("food-1", "ration", ItemKind.FOOD),
    )
    body = alive_body(
        "body-1",
        inventory=(
            EntityId("mat-1"),
            EntityId("mat-2"),
            EntityId("mat-3"),
            EntityId("food-1"),
        ),
    )
    engine = _engine(
        _fixture(items=items, bodies=(body, alive_body("body-2"))),
        catalog=example_production_catalog(),
    )
    built = _act(engine, "agent-1", Build(_SHELTER))
    shelter = _kinds(built)[0]
    assert type(shelter) is StructureBuilt
    assert shelter.resulting_integrity == 0.75
    shelter_factor = engine._snapshot.world.state.locations[
        EntityId("loc-1")
    ].shelter_factor
    assert shelter_factor.value == 0.0
    duplicate = _act(engine, "agent-1", Build(_SHELTER))
    assert duplicate.resolutions[0].status is ActionResolutionStatus.REJECTED
    assert _kinds(duplicate) == []

    repaired = _act(engine, "agent-1", Repair(_REPAIR, shelter.structure_id))
    repair = _kinds(repaired)[0]
    assert type(repair) is StructureRepaired
    assert repair.resulting_integrity == 1.0
    intact = _act(engine, "agent-1", Repair(_REPAIR, shelter.structure_id))
    assert intact.resolutions[0].status is ActionResolutionStatus.REJECTED
    assert _kinds(intact) == []

    stored = _act(engine, "agent-1", Store(_STORE, EntityId("food-1")))
    deposit = _kinds(stored)
    assert len(deposit) == 1
    assert type(deposit[0]) is ItemStored
    assert deposit[0].resulting_stored_quantity == 1
    assert not any(type(details) is StructureBuilt for details in deposit)

    again = _engine(
        _fixture(
            items=(
                _held("food-2", "meal", ItemKind.FOOD),
                _held("food-3", "meal", ItemKind.FOOD),
            ),
            bodies=(
                alive_body(
                    "body-1",
                    inventory=(EntityId("food-2"), EntityId("food-3")),
                ),
                alive_body("body-2"),
            ),
        ),
        catalog=example_production_catalog(),
    )
    first = _act(again, "agent-1", Store(_STORE, EntityId("food-2")))
    second = _act(again, "agent-1", Store(_STORE, EntityId("food-3")))
    assert type(_kinds(first)[0]) is ItemStored
    stored_again = _kinds(second)[0]
    assert type(stored_again) is ItemStored
    assert stored_again.resulting_stored_quantity == 2
    assert stored_again.structure_id == _kinds(first)[0].structure_id
    stores = [
        structure
        for structure in again._snapshot.world.state.structures.values()
        if structure.kind.value == "store"
    ]
    assert len(stores) == 1


def test_shelter_changes_exposure_without_writing_the_location() -> None:
    sheltered = _engine(
        _fixture(
            items=(_held("mat-1", "wood"),),
            bodies=_crafter("mat-1"),
        ),
        catalog=example_production_catalog(),
    )
    _act(sheltered, "agent-1", Build(_SHELTER))
    location = sheltered._snapshot.world.state.locations[EntityId("loc-1")]
    assert location.shelter_factor.value == 0.0
    sheltered_temp = sheltered._snapshot.world.state.bodies[
        EntityId("body-1")
    ].temperature.value
    bare = _engine(_fixture())
    _act(bare, "agent-1", Search())
    bare_temp = bare._snapshot.world.state.bodies[EntityId("body-1")].temperature.value
    assert sheltered_temp != bare_temp


def test_skill_level_zero_preserves_recipe_probability() -> None:
    assert (
        adjusted_production_probability(
            CRAFT_SUCCESS_PROBABILITY, level=0.0, probability_gain=0.5
        )
        == CRAFT_SUCCESS_PROBABILITY
    )
    assert (
        adjusted_production_probability(
            CERTAIN_SUCCESS_PROBABILITY, level=4.0, probability_gain=0.5
        )
        == CERTAIN_SUCCESS_PROBABILITY
    )
    gained = adjusted_production_probability(
        HARVEST_SUCCESS_PROBABILITY, level=1.0, probability_gain=0.5
    )
    assert gained == pytest.approx(1.0)
    fixture = _fixture(resources=(_wood_resource(),))
    catalog = example_production_catalog()
    for seed in (1, 2, 3, 7, 11):
        plain = _act(
            _engine(fixture, seed=seed, catalog=catalog),
            "agent-1",
            Harvest(_WOOD, EntityId("res-wood")),
        )
        skilled = _act(
            _engine(fixture, seed=seed, catalog=catalog, skill=True),
            "agent-1",
            Harvest(_WOOD, EntityId("res-wood")),
        )
        assert _kinds(plain)[0].success == _kinds(skilled)[0].success


def test_dead_job_completion_emits_nothing() -> None:
    fixture = _craft_fixture(("item-wood", "wood"))
    actor = EntityId("body-1")
    base = fixture.as_state()
    state = rebuild_world_state(
        base,
        bodies={
            **dict(base.bodies),
            actor: copy_body(
                base.bodies[actor],
                health=Health(0.0),
                life_status=LifeStatus.DEAD,
            ),
        },
        production_jobs={
            actor: ProductionJob(
                actor_id=actor,
                recipe_id=_TOOL,
                due_tick=1,
                created_item_id=EntityId("item-due"),
                duration_ticks=2,
            )
        },
    )
    completed, details = complete_due_jobs(
        state, tick=1, catalog=example_production_catalog()
    )
    assert details == ()
    assert completed.production_jobs == {}
    assert EntityId("item-due") not in completed.items
