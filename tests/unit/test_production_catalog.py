"""Production catalog and command contracts stay closed and fail closed."""

from __future__ import annotations

import hashlib
import logging

import pytest

from world.actions import (
    Build,
    Craft,
    Harvest,
    Repair,
    Store,
    require_agent_command,
)
from world.identifiers import EntityId, RecipeId
from world.production import (
    CRAFT_SUCCESS_PROBABILITY,
    HARVEST_SUCCESS_PROBABILITY,
    HeldItemKindInput,
    HeldItemNameInput,
    ItemProduct,
    ProductionAction,
    ProductionCatalog,
    ProductionRecipe,
    ResourceNameInput,
    ShelterProduct,
    Structure,
    StructureKind,
    ToolRole,
    example_production_catalog,
    production_catalog_digest,
)
from world.values import ItemKind, ItemLoad


def _digest(ids: list[str]) -> str:
    payload = "\n".join(sorted(ids)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_recipe_id_pattern_and_foreign_rejection(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR, logger="world.production")
    assert RecipeId("harvest_wood").value == "harvest_wood"
    assert RecipeId("a").value == "a"
    assert RecipeId("a" + ("b" * 31)).value == "a" + ("b" * 31)
    for foreign in ("", "A", "1wood", "harvest-wood", "a" + ("b" * 32), "Wood"):
        with pytest.raises(ValueError, match="foreign_recipe_id"):
            RecipeId(foreign)
    assert any(
        "field=RecipeId.value" in record.getMessage()
        and "reason_code=foreign_recipe_id" in record.getMessage()
        for record in caplog.records
    )


def test_example_catalog_is_exactly_the_six_locked_recipes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="world.production")
    catalog = example_production_catalog()
    assert catalog.recipe_count == 6
    ids = [recipe.recipe_id.value for recipe in catalog.recipes]
    assert ids == [
        "harvest_wood",
        "harvest_stone",
        "craft_tool",
        "build_shelter",
        "repair_shelter",
        "store_food",
    ]
    digest = production_catalog_digest(ids)
    assert digest == _digest(ids)
    assert any(
        "recipe_count=6" in record.getMessage()
        and f"digest={digest}" in record.getMessage()
        for record in caplog.records
        if record.levelno == logging.DEBUG
    )
    assert not any(
        record.levelno == logging.INFO and "wood" in record.getMessage()
        for record in caplog.records
    )

    wood = catalog.recipe(RecipeId("harvest_wood"))
    stone = catalog.recipe(RecipeId("harvest_stone"))
    tool = catalog.recipe(RecipeId("craft_tool"))
    shelter = catalog.recipe(RecipeId("build_shelter"))
    repair = catalog.recipe(RecipeId("repair_shelter"))
    store = catalog.recipe(RecipeId("store_food"))
    assert wood is not None and stone is not None
    assert tool is not None and shelter is not None
    assert repair is not None and store is not None
    assert wood.action is ProductionAction.HARVEST
    assert wood.duration_ticks == 1
    assert wood.success_probability == HARVEST_SUCCESS_PROBABILITY
    assert wood.inputs == (ResourceNameInput("wood"),)
    assert wood.output == ItemProduct(ItemKind.MATERIAL, "wood", ItemLoad(1))
    assert stone.inputs == (ResourceNameInput("stone"),)
    assert stone.output == ItemProduct(ItemKind.MATERIAL, "stone", ItemLoad(1))
    assert tool.action is ProductionAction.CRAFT
    assert tool.duration_ticks == 2
    assert tool.success_probability == CRAFT_SUCCESS_PROBABILITY
    assert tool.tool_role is ToolRole.STRIKE
    assert tool.inputs == (HeldItemNameInput("wood"), HeldItemNameInput("stone"))
    assert tool.output == ItemProduct(
        ItemKind.TOOL, "tool", ItemLoad(1), tool_role=ToolRole.STRIKE
    )
    assert shelter.action is ProductionAction.BUILD
    assert shelter.success_probability == 1.0
    assert shelter.inputs == (HeldItemKindInput(ItemKind.MATERIAL),)
    assert shelter.output == ShelterProduct(StructureKind.SHELTER)
    assert shelter.output.initial_integrity == 0.75
    assert repair.action is ProductionAction.REPAIR
    assert repair.output.integrity_delta == 0.25
    assert store.action is ProductionAction.STORE
    assert store.inputs == (HeldItemKindInput(ItemKind.FOOD),)
    assert store.output.quantity_delta == 1
    assert store.output.initial_integrity == 1.0
    assert store.output.initial_stored_quantity == 1
    assert catalog.recipe(RecipeId("craft_gold")) is None


def test_catalog_rejects_duplicates_duration_and_probability(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR, logger="world.production")
    recipe = example_production_catalog().recipes[0]
    with pytest.raises(ValueError, match="duplicate_recipe_id"):
        ProductionCatalog((recipe, recipe))
    with pytest.raises(ValueError, match="duration_below_one"):
        ProductionRecipe(
            recipe_id=RecipeId("harvest_wood"),
            action=ProductionAction.HARVEST,
            duration_ticks=0,
            success_probability=0.8,
            inputs=(ResourceNameInput("wood"),),
            output=ItemProduct(ItemKind.MATERIAL, "wood", ItemLoad(1)),
        )
    with pytest.raises(ValueError, match="probability_out_of_range"):
        ProductionRecipe(
            recipe_id=RecipeId("harvest_wood"),
            action=ProductionAction.HARVEST,
            duration_ticks=1,
            success_probability=1.1,
            inputs=(ResourceNameInput("wood"),),
            output=ItemProduct(ItemKind.MATERIAL, "wood", ItemLoad(1)),
        )
    messages = [record.getMessage() for record in caplog.records]
    assert any("reason_code=duplicate_recipe_id" in message for message in messages)
    assert any("reason_code=duration_below_one" in message for message in messages)
    empty = ProductionCatalog(())
    assert empty.recipe_count == 0


def test_commands_reject_foreign_ids_and_action_tokens() -> None:
    recipe_id = RecipeId("harvest_wood")
    resource_id = EntityId("resource-1")
    structure_id = EntityId("structure-1")
    item_id = EntityId("item-1")
    harvest = require_agent_command(Harvest(recipe_id, resource_id))
    assert type(harvest) is Harvest
    assert harvest.kind == "harvest"
    assert require_agent_command(Craft(RecipeId("craft_tool"))).kind == "craft"
    assert require_agent_command(Build(RecipeId("build_shelter"))).kind == "build"
    assert (
        require_agent_command(Repair(RecipeId("repair_shelter"), structure_id)).kind
        == "repair"
    )
    assert require_agent_command(Store(RecipeId("store_food"), item_id)).kind == "store"
    with pytest.raises(TypeError, match="raw mappings"):
        require_agent_command({"kind": "harvest", "recipe_id": "harvest_wood"})
    with pytest.raises(ValueError, match="foreign_recipe_id"):
        Harvest("harvest_wood", resource_id)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="action_token_mismatch"):
        Harvest(recipe_id, resource_id, action="craft")
    with pytest.raises(ValueError, match="action_token_mismatch"):
        Craft(RecipeId("craft_tool"), action="build")
    with pytest.raises(TypeError, match="EntityId"):
        Store(RecipeId("store_food"), "item-1")  # type: ignore[arg-type]


def test_structure_has_no_coordinates_and_tool_kind_exists() -> None:
    structure = Structure(
        entity_id=EntityId("structure-1"),
        location_id=EntityId("loc-1"),
        kind=StructureKind.SHELTER,
        integrity=0.75,
        stored_quantity=0,
    )
    assert not hasattr(structure, "screen_x")
    assert "pixels" not in structure.__slots__
    assert ItemKind.TOOL.value == "tool"
    assert {kind.value for kind in ItemKind} >= {
        "food",
        "water",
        "material",
        "medical",
        "generic",
        "tool",
    }
    with pytest.raises(ValueError, match="integrity_out_of_range"):
        Structure(
            entity_id=EntityId("structure-1"),
            location_id=EntityId("loc-1"),
            kind=StructureKind.STORE,
            integrity=1.1,
            stored_quantity=0,
        )
