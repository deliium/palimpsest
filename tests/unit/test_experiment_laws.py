"""Private experiment law catalog."""

from __future__ import annotations

import pytest

from world._experiment_laws import ExperimentLaw, ExperimentLawCatalog
from world.experimentation import (
    ExperimentDeltaKind,
    ExperimentHarmBand,
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)
from world.identifiers import EntityId, RecipeId
from world.models import Item, Resource
from world.production import (
    ItemProduct,
    ProductionAction,
    ProductionCatalog,
    ResourceNameInput,
    ToolMark,
    ToolRole,
    example_production_catalog,
)
from world.values import ItemKind, ItemLoad, ResourceKind


def _item(kind: ItemKind = ItemKind.MATERIAL) -> Item:
    return Item(
        entity_id=EntityId("item-1"),
        name="wood",
        kind=kind,
        load=ItemLoad(1),
        holder_id=EntityId("body-1"),
    )


def _resource() -> Resource:
    return Resource(
        entity_id=EntityId("res-1"),
        name="wood",
        kind=ResourceKind.MATERIAL,
        location_id=EntityId("loc-1"),
        quantity=1.0,
        maximum_quantity=4.0,
        regeneration_per_tick=0.0,
    )


def _law(**overrides: object) -> ExperimentLaw:
    payload: dict[str, object] = {
        "operator": ExperimentOperator.COMBINE,
        "operand_a_kind": "item:material",
        "operand_b_kind": "resource:material",
        "process_token": ExperimentProcessToken.NONE,
        "outcome_class": ExperimentOutcomeClass.SUCCESS,
        "delta": ExperimentDeltaKind.NONE,
        "product_id": "",
        "harm_band": ExperimentHarmBand.NONE,
        "public_technique_token": "",
    }
    payload.update(overrides)
    return ExperimentLaw(
        operator=payload["operator"],  # type: ignore[arg-type]
        operand_a_kind=str(payload["operand_a_kind"]),
        operand_b_kind=str(payload["operand_b_kind"]),
        process_token=payload["process_token"],  # type: ignore[arg-type]
        outcome_class=payload["outcome_class"],  # type: ignore[arg-type]
        delta=payload["delta"],  # type: ignore[arg-type]
        product_id=str(payload["product_id"]),
        harm_band=payload["harm_band"],  # type: ignore[arg-type]
        public_technique_token=str(payload["public_technique_token"]),
    )


def test_prefixed_match() -> None:
    catalog = ExperimentLawCatalog((_law(),), ProductionCatalog())
    result = catalog.evaluate(
        operator=ExperimentOperator.COMBINE,
        operand_a=_item(),
        operand_b=_resource(),
        process_token=ExperimentProcessToken.NONE,
    )
    assert result.matched is True
    assert result.outcome_class is ExperimentOutcomeClass.SUCCESS


def test_unprefixed_rejected() -> None:
    with pytest.raises(ValueError, match="experiment_law_operand_unprefixed"):
        _law(operand_a_kind="material")


def test_type_mismatch_is_failure() -> None:
    catalog = ExperimentLawCatalog(
        (_law(operand_a_kind="tool:strike", operand_b_kind="item:material"),),
        ProductionCatalog(),
    )
    result = catalog.evaluate(
        operator=ExperimentOperator.COMBINE,
        operand_a=_item(),
        operand_b=_item(),
        process_token=ExperimentProcessToken.NONE,
    )
    assert result.matched is False
    assert result.outcome_class is ExperimentOutcomeClass.FAILURE
    assert result.delta is ExperimentDeltaKind.NONE


def test_unlisted_is_failure() -> None:
    catalog = ExperimentLawCatalog((_law(),), ProductionCatalog())
    result = catalog.evaluate(
        operator=ExperimentOperator.APPLY_TOOL,
        operand_a=ToolMark(item_id=EntityId("tool-1"), role=ToolRole.STRIKE),
        operand_b=_item(),
        process_token=ExperimentProcessToken.NONE,
    )
    assert result.outcome_class is ExperimentOutcomeClass.FAILURE
    assert result.delta is ExperimentDeltaKind.NONE


def test_duplicate_rejected() -> None:
    law = _law()
    with pytest.raises(ValueError, match="experiment_law_duplicate"):
        ExperimentLawCatalog((law, law), ProductionCatalog())


def test_harm_band_required() -> None:
    with pytest.raises(ValueError, match="experiment_law_harm_band_invalid"):
        _law(
            outcome_class=ExperimentOutcomeClass.HARM,
            delta=ExperimentDeltaKind.APPLY_HARM_BAND,
            harm_band=ExperimentHarmBand.NONE,
        )


def test_unknown_product_rejected() -> None:
    with pytest.raises(ValueError, match="experiment_law_unknown_product"):
        ExperimentLawCatalog(
            (
                _law(
                    delta=ExperimentDeltaKind.EMIT_CATALOG_PRODUCT,
                    product_id="missing",
                ),
            ),
            example_production_catalog(),
        )


def test_known_product_allowed() -> None:
    catalog = ExperimentLawCatalog(
        (
            _law(
                delta=ExperimentDeltaKind.EMIT_CATALOG_PRODUCT,
                product_id="harvest_wood",
            ),
        ),
        example_production_catalog(),
    )
    result = catalog.evaluate(
        operator=ExperimentOperator.COMBINE,
        operand_a=_item(),
        operand_b=_resource(),
        process_token=ExperimentProcessToken.NONE,
    )
    assert result.product_id == "harvest_wood"


def test_catalog_recipe_shape_unchanged() -> None:
    recipe = example_production_catalog().recipe(RecipeId("harvest_wood"))
    assert recipe is not None
    assert recipe.action is ProductionAction.HARVEST
    assert type(recipe.output) is ItemProduct
    assert type(recipe.inputs[0]) is ResourceNameInput
