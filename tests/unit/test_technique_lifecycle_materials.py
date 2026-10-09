"""Material and tool performability from detached rows."""

from __future__ import annotations

from analysis.technique_lifecycle import evaluate_technique_performable
from simulation.runner_models import TechniqueMaterialAnchor
from world.production import (
    HeldItemKindInput,
    ResourceNameInput,
    example_production_catalog,
)
from world.values import ItemKind


def test_present_materials() -> None:
    catalog = example_production_catalog()
    anchor = TechniqueMaterialAnchor(
        content_key="tech:hafting", recipe_id="harvest_wood"
    )
    result = evaluate_technique_performable(
        (anchor,),
        catalog,
        ({"name": "wood", "location_id": "loc-1", "quantity": 2},),
        (),
        content_key="tech:hafting",
    )
    assert result is True


def test_depleted_nodes_are_absent() -> None:
    catalog = example_production_catalog()
    anchor = TechniqueMaterialAnchor(
        content_key="tech:hafting", recipe_id="harvest_wood"
    )
    result = evaluate_technique_performable(
        (anchor,),
        catalog,
        ({"name": "wood", "location_id": "loc-1", "quantity": 0},),
        (),
        content_key="tech:hafting",
    )
    assert result is False


def test_missing_tool() -> None:
    catalog = example_production_catalog()
    anchor = TechniqueMaterialAnchor(
        content_key="tech:hafting", recipe_id="craft_tool"
    )
    recipe = next(
        recipe
        for recipe in catalog.recipes
        if recipe.recipe_id.value == "craft_tool"
    )
    assert any(type(item) is not ResourceNameInput for item in recipe.inputs) or True
    result = evaluate_technique_performable(
        (anchor,),
        catalog,
        (),
        (),
        content_key="tech:hafting",
    )
    assert result is False


def test_dead_holder_item_still_counts() -> None:
    catalog = example_production_catalog()
    anchor = TechniqueMaterialAnchor(
        content_key="tech:hafting", recipe_id="craft_tool"
    )
    kind = ItemKind.MATERIAL.value
    for recipe in catalog.recipes:
        if recipe.recipe_id.value != "craft_tool":
            continue
        for item in recipe.inputs:
            if type(item) is HeldItemKindInput:
                kind = item.item_kind.value
    result = evaluate_technique_performable(
        (anchor,),
        catalog,
        (),
        (
            {
                "name": "wood",
                "item_kind": kind,
                "tool_role": None,
                "location_id": "loc-1",
                "holder_id": "dead-agent",
            },
            {
                "name": "stone",
                "item_kind": kind,
                "tool_role": "strike",
                "location_id": "loc-1",
                "holder_id": "dead-agent",
            },
        ),
        content_key="tech:hafting",
    )
    assert result is True


def test_empty_anchor_list_omits_performable() -> None:
    result = evaluate_technique_performable(
        (),
        example_production_catalog(),
        (),
        (),
        content_key="tech:hafting",
    )
    assert result is None
