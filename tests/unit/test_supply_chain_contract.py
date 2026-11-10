# mypy: ignore-errors

"""Supply-chain contract: stages, validation, and the closed chain catalog."""

from __future__ import annotations

import dataclasses
import logging

import pytest

import world
from analysis.supply_chain_contract import (
    NONE_TOKEN,
    SUPPLY_BOTTLENECK_PREFIX,
    SUPPLY_CHAIN_ANALYSIS_POLICY_VERSION,
    SUPPLY_CHAIN_ERROR_CODES,
    SUPPLY_CHAIN_PREFIX,
    SUPPLY_EDGE_PREFIX,
    SUPPLY_FORBIDDEN_KEYS,
    SUPPLY_STAGE_PREFIX,
    SupplyBottleneckKind,
    SupplyChainError,
    SupplyCoverage,
    SupplyEdgeKind,
    SupplyLayer,
    SupplyNodeKind,
    analysis_supply_token,
    canonical_supply_pair,
)
from analysis.supply_chain_policy import (
    BOTTLENECK_DEMAND_MIN,
    BOTTLENECK_MIN_EVENTS,
    BOTTLENECK_SHARE_MILLI,
    BOTTLENECK_SHORTFALL_MILLI,
    CHAIN_OVERLAP_MILLI,
    LOW_SKILL_LEVEL,
    MAX_CHAIN_DEPTH,
    SupplyChainAnalysisPolicy,
    default_supply_chain_analysis_policy,
    window_bounds,
    window_index_for_tick,
)
from world.identifiers import RecipeId
from world.production import (
    HeldItemKindInput,
    HeldItemNameInput,
    ItemProduct,
    ProductionAction,
    ProductionCatalog,
    ProductionRecipe,
    ResourceNameInput,
    ShelterProduct,
    StructureKind,
    ToolRole,
    example_production_catalog,
    production_catalog_digest,
)
from world.supply_chain import (
    SUPPLY_CHAIN_MAX_STAGE_DEPTH,
    SUPPLY_CHAIN_POLICY_VERSION,
    SUPPLY_CHAIN_RECIPES,
    SupplyChainContractError,
    SupplyStageSpec,
    production_chain_stages,
    supply_chain_production_catalog,
    validate_production_chain_catalog,
)
from world.values import ItemKind, ItemLoad

pytestmark = pytest.mark.unit

_LOAD = ItemLoad(1)


def _item_recipe(
    recipe_id: str, inputs: tuple[object, ...], output_name: str
) -> ProductionRecipe:
    return ProductionRecipe(
        recipe_id=RecipeId(recipe_id),
        action=ProductionAction.CRAFT,
        duration_ticks=1,
        success_probability=1.0,
        inputs=inputs,  # type: ignore[arg-type]
        output=ItemProduct(ItemKind.MATERIAL, output_name, _LOAD),
    )


def test_stage_spec_rejects_unknown_action() -> None:
    with pytest.raises(SupplyChainContractError) as excinfo:
        SupplyStageSpec(
            recipe_id="x",
            action="smelt",
            resource_input_names=(),
            item_input_names=(),
            input_kinds=(),
            output_name="x",
            output_kind="material",
            skill_domain=None,
            tool_role=None,
            requires_tool=False,
        )
    assert excinfo.value.code == "invalid_stage"


def test_harvest_stage_separates_resource_inputs() -> None:
    stages = production_chain_stages(example_production_catalog())
    harvest = next(stage for stage in stages if stage.recipe_id == "harvest_wood")
    assert harvest.action == "harvest"
    assert harvest.resource_input_names == ("wood",)
    assert harvest.item_input_names == ()
    assert harvest.input_kinds == ()


def test_kind_inputs_are_not_item_edges() -> None:
    stages = production_chain_stages(example_production_catalog())
    build = next(stage for stage in stages if stage.recipe_id == "build_shelter")
    assert build.input_kinds == ("material",)
    assert build.item_input_names == ()
    assert build.output_name == "shelter"
    assert build.output_kind == "structure"


def test_legacy_catalog_validates_with_two_edges() -> None:
    summary = validate_production_chain_catalog(example_production_catalog())
    assert summary.stage_count == 6
    assert summary.item_stage_count == 3
    assert summary.edge_count == 2
    assert summary.max_depth == 2
    assert summary.policy_version == SUPPLY_CHAIN_POLICY_VERSION


def test_validation_rejects_cycle() -> None:
    a = _item_recipe("craft_a", (HeldItemNameInput("b"),), "a")
    b = _item_recipe("craft_b", (HeldItemNameInput("a"),), "b")
    with pytest.raises(SupplyChainContractError) as excinfo:
        validate_production_chain_catalog(ProductionCatalog((a, b)))
    assert excinfo.value.code == "supply_chain_catalog_cycle"


def test_validation_rejects_no_chain() -> None:
    shelter = ProductionRecipe(
        recipe_id=RecipeId("build_shelter"),
        action=ProductionAction.BUILD,
        duration_ticks=1,
        success_probability=1.0,
        inputs=(HeldItemKindInput(ItemKind.MATERIAL),),
        output=ShelterProduct(StructureKind.SHELTER),
    )
    with pytest.raises(SupplyChainContractError) as excinfo:
        validate_production_chain_catalog(ProductionCatalog((shelter,)))
    assert excinfo.value.code == "supply_chain_catalog_no_chain"


def test_validation_accepts_multi_stage_catalog() -> None:
    first = _item_recipe("craft_one", (HeldItemNameInput("wood"),), "one")
    second = _item_recipe("craft_two", (HeldItemNameInput("one"),), "two")
    summary = validate_production_chain_catalog(ProductionCatalog((first, second)))
    assert summary.edge_count == 1
    assert summary.max_depth == 2


def test_summary_max_depth_is_capped() -> None:
    recipes: list[ProductionRecipe] = [
        _item_recipe("craft_00", (HeldItemNameInput("wood"),), "n0")
    ]
    for index in range(1, 12):
        recipes.append(
            _item_recipe(
                f"craft_{index:02d}",
                (HeldItemNameInput(f"n{index - 1}"),),
                f"n{index}",
            )
        )
    summary = validate_production_chain_catalog(ProductionCatalog(tuple(recipes)))
    assert summary.max_depth == SUPPLY_CHAIN_MAX_STAGE_DEPTH


def test_stage_spec_is_frozen() -> None:
    stage = production_chain_stages(example_production_catalog())[0]
    assert dataclasses.is_dataclass(stage)
    with pytest.raises(dataclasses.FrozenInstanceError):
        stage.recipe_id = "other"  # type: ignore[misc]


def test_non_item_output_tokens() -> None:
    stages = {
        stage.recipe_id: stage
        for stage in production_chain_stages(example_production_catalog())
    }
    assert (
        stages["build_shelter"].output_name,
        stages["build_shelter"].output_kind,
    ) == (
        "shelter",
        "structure",
    )
    assert (
        stages["repair_shelter"].output_name,
        stages["repair_shelter"].output_kind,
    ) == (
        "repair",
        "structure",
    )
    assert (stages["store_food"].output_name, stages["store_food"].output_kind) == (
        "store",
        "storage",
    )


def test_empty_catalog_is_only_rejected_when_required() -> None:
    assert (
        validate_production_chain_catalog(
            ProductionCatalog(), require_chain=False
        ).stage_count
        == 0
    )
    with pytest.raises(SupplyChainContractError) as excinfo:
        validate_production_chain_catalog(ProductionCatalog(), require_chain=True)
    assert excinfo.value.code == "supply_chain_catalog_empty"


def test_legacy_default_catalog_is_unchanged() -> None:
    catalog = example_production_catalog()
    ids = [recipe.recipe_id.value for recipe in catalog.recipes]
    assert len(ids) == 6
    assert ids == [
        "harvest_wood",
        "harvest_stone",
        "craft_tool",
        "build_shelter",
        "repair_shelter",
        "store_food",
    ]
    assert production_catalog_digest(ids) == production_catalog_digest(tuple(ids))


def test_extension_adds_six_recipes() -> None:
    extended = supply_chain_production_catalog(example_production_catalog())
    assert extended.recipe_count == 12
    assert tuple(recipe.recipe_id.value for recipe in SUPPLY_CHAIN_RECIPES) == (
        "harvest_grain",
        "mill_grain",
        "bake_bread",
        "craft_plank",
        "craft_tool_head",
        "assemble_tool",
    )


def test_extension_preserves_base_order() -> None:
    base = example_production_catalog()
    extended = supply_chain_production_catalog(base)
    assert extended.recipes[: base.recipe_count] == base.recipes
    assert extended.recipes[base.recipe_count :] == SUPPLY_CHAIN_RECIPES


def test_extension_rejects_collision(caplog: pytest.LogCaptureFixture) -> None:
    base = example_production_catalog()
    with caplog.at_level(logging.WARNING, logger="world.supply_chain"):
        with pytest.raises(SupplyChainContractError) as excinfo:
            supply_chain_production_catalog(
                ProductionCatalog(
                    (*tuple(base.recipes), SUPPLY_CHAIN_RECIPES[0])
                )
            )
    assert excinfo.value.code == "supply_chain_recipe_collision"
    assert "recipe_id=harvest_grain" in caplog.text


def test_extended_catalog_is_acyclic() -> None:
    summary = validate_production_chain_catalog(
        supply_chain_production_catalog(example_production_catalog())
    )
    assert summary.edge_count == 8
    assert summary.max_depth == 3


def test_chain_depth_reaches_three() -> None:
    summary = validate_production_chain_catalog(
        supply_chain_production_catalog(example_production_catalog())
    )
    assert summary.max_depth >= 3


def test_tool_output_carries_strike_role() -> None:
    catalog = supply_chain_production_catalog(example_production_catalog())
    tool = catalog.recipe(RecipeId("assemble_tool"))
    assert tool is not None
    assert tool.tool_role is ToolRole.STRIKE
    assert type(tool.output) is ItemProduct
    assert tool.output.tool_role is ToolRole.STRIKE


def test_harvest_recipe_uses_resource_input() -> None:
    harvest = next(
        recipe
        for recipe in SUPPLY_CHAIN_RECIPES
        if recipe.recipe_id.value == "harvest_grain"
    )
    assert harvest.action is ProductionAction.HARVEST
    assert harvest.inputs == (ResourceNameInput("grain"),)


def test_skill_domains_cover_new_craft_recipes() -> None:
    stages = {
        stage.recipe_id: stage
        for stage in production_chain_stages(
            supply_chain_production_catalog(example_production_catalog())
        )
    }
    for recipe_id in (
        "mill_grain",
        "bake_bread",
        "craft_plank",
        "craft_tool_head",
        "assemble_tool",
    ):
        assert stages[recipe_id].skill_domain == "crafting"


def test_world_facade_exports_supply_chain() -> None:
    for name in (
        "SUPPLY_CHAIN_POLICY_VERSION",
        "SupplyStageSpec",
        "SupplyChainSummary",
        "production_chain_stages",
        "validate_production_chain_catalog",
        "supply_chain_production_catalog",
        "harvest_tool_probability_gain",
    ):
        assert name in world.__all__
        assert hasattr(world, name)


def test_policy_defaults() -> None:
    policy = default_supply_chain_analysis_policy()
    assert policy.window_ticks == 32
    assert policy.max_windows == 512
    assert policy.max_evidence_rows == 200_000
    assert policy.max_stages == 4_096
    assert policy.max_edges == 16_384
    assert policy.max_chains == 4_096
    assert policy.max_bottlenecks == 4_096
    assert policy.max_locations == 4_096
    assert policy.max_organizations == 2_048
    assert policy.max_lineage_edges == 16_384


def test_policy_rejects_bool_as_int() -> None:
    with pytest.raises(SupplyChainError) as excinfo:
        SupplyChainAnalysisPolicy(window_ticks=True)  # type: ignore[arg-type]
    assert excinfo.value.reason_code == "supply_chain_invalid_policy"


def test_policy_cap_ranges() -> None:
    assert SupplyChainAnalysisPolicy(window_ticks=8).window_ticks == 8
    assert SupplyChainAnalysisPolicy(window_ticks=256).window_ticks == 256
    for invalid in (7, 257, 0, -1, 1.5, "32"):
        with pytest.raises(SupplyChainError):
            SupplyChainAnalysisPolicy(window_ticks=invalid)  # type: ignore[arg-type]
    assert SupplyChainAnalysisPolicy(max_edges=1).max_edges == 1
    with pytest.raises(SupplyChainError):
        SupplyChainAnalysisPolicy(max_edges=16_385)


def test_error_codes_are_closed() -> None:
    assert len(SUPPLY_CHAIN_ERROR_CODES) == 16
    assert "supply_chain_layer_leak" in SUPPLY_CHAIN_ERROR_CODES


def test_tokens_are_deterministic() -> None:
    first = analysis_supply_token(SUPPLY_STAGE_PREFIX, "window-0-phase")
    second = analysis_supply_token(SUPPLY_STAGE_PREFIX, "window-0-phase")
    other = analysis_supply_token(SUPPLY_STAGE_PREFIX, "window-1-phase")
    assert first == second
    assert first != other
    assert first.startswith(SUPPLY_STAGE_PREFIX)
    assert len(first) == len("sc-stage-") + 16


def test_token_rejects_unknown_prefix() -> None:
    with pytest.raises(SupplyChainError) as excinfo:
        analysis_supply_token("sc-unknown-", "payload")
    assert excinfo.value.reason_code == "supply_chain_invalid_token"


def test_window_math_matches_floor_division() -> None:
    policy = default_supply_chain_analysis_policy()
    assert window_index_for_tick(0, policy) == 0
    assert window_index_for_tick(31, policy) == 0
    assert window_index_for_tick(32, policy) == 1
    assert window_bounds(1, policy) == (32, 64)
    with pytest.raises(SupplyChainError):
        window_index_for_tick(-1, policy)
    with pytest.raises(SupplyChainError):
        window_bounds(512, policy)


def test_forbidden_keys_include_optimizer_terms() -> None:
    for key in ("price", "quota", "allocation", "optimizer", "severity", "rank"):
        assert key in SUPPLY_FORBIDDEN_KEYS


def test_pair_is_order_independent() -> None:
    assert canonical_supply_pair("b", "a") == ("a", "b")
    assert canonical_supply_pair("a", "b") == ("a", "b")
    with pytest.raises(SupplyChainError):
        canonical_supply_pair("a", "a")


def test_edge_kinds_are_closed_to_ten() -> None:
    assert len(SupplyEdgeKind) == 10
    assert len(SupplyBottleneckKind) == 7
    assert len(SupplyNodeKind) == 9
    assert len(SupplyLayer) == 3
    assert {item.value for item in SupplyCoverage} == {
        "complete",
        "partial",
        "missing",
    }
    assert NONE_TOKEN == "-"
    assert SUPPLY_EDGE_PREFIX == "sc-edge-"
    assert SUPPLY_CHAIN_PREFIX == "sc-chain-"
    assert SUPPLY_BOTTLENECK_PREFIX == "sc-neck-"
    assert SUPPLY_CHAIN_ANALYSIS_POLICY_VERSION == "supply-chains.v1"
    assert BOTTLENECK_MIN_EVENTS == 3
    assert BOTTLENECK_SHARE_MILLI == 750
    assert BOTTLENECK_SHORTFALL_MILLI == 250
    assert BOTTLENECK_DEMAND_MIN == 3
    assert CHAIN_OVERLAP_MILLI == 500
    assert LOW_SKILL_LEVEL == 0.125
    assert MAX_CHAIN_DEPTH == 8
