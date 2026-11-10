"""Closed multi-stage production-chain contract and mechanics helpers.

The legacy six-recipe catalog is immutable. Chain recipes live here and are
appended only when a scenario explicitly selects the supply-chain catalog. This
module is configuration-derived and never reads or mutates ``WorldState`` during
validation.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from world.identifiers import RecipeId
from world.production import (
    HeldItemKindInput,
    HeldItemNameInput,
    ItemProduct,
    ProductionAction,
    ProductionCatalog,
    ProductionInput,
    ProductionOutput,
    ProductionRecipe,
    RepairProduct,
    ResourceNameInput,
    ShelterProduct,
    StoreProduct,
    ToolRole,
)
from world.values import ItemKind, ItemLoad

_LOG: Final[logging.Logger] = logging.getLogger("world.supply_chain")

SUPPLY_CHAIN_POLICY_VERSION: Final[str] = "supply-chains.v1"
SUPPLY_CHAIN_HARVEST_TOOL_PROBABILITY_GAIN: Final[float] = 0.10
SUPPLY_CHAIN_MAX_STAGE_DEPTH: Final[int] = 8

_PRODUCTION_ACTIONS: Final[frozenset[str]] = frozenset(
    {"harvest", "craft", "build", "repair", "store"}
)
_OUTPUT_KINDS: Final[frozenset[str]] = frozenset(
    {"food", "water", "material", "medical", "generic", "tool", "structure", "storage"}
)
_ITEM_OUTPUT_KINDS: Final[frozenset[str]] = frozenset(
    {"food", "water", "material", "medical", "generic", "tool"}
)

__all__ = [
    "SUPPLY_CHAIN_HARVEST_TOOL_PROBABILITY_GAIN",
    "SUPPLY_CHAIN_MAX_STAGE_DEPTH",
    "SUPPLY_CHAIN_POLICY_VERSION",
    "SUPPLY_CHAIN_RECIPES",
    "SupplyChainContractError",
    "SupplyChainSummary",
    "SupplyStageSpec",
    "harvest_tool_probability_gain",
    "production_chain_stages",
    "supply_chain_production_catalog",
    "validate_production_chain_catalog",
]


class SupplyChainContractError(ValueError):
    """Closed chain-contract failure carrying a safe reason code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"supply_chain_contract_error: {code}")


def _sorted_names(field_name: str, values: object) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise _contract(field_name, "invalid_stage")
    names: set[str] = set()
    for value in values:
        if type(value) is not str or not value or value != value.strip():
            raise _contract(field_name, "invalid_stage")
        names.add(value)
    return tuple(sorted(names))


@dataclass(frozen=True, slots=True)
class SupplyStageSpec:
    """One objective stage derived from a ``ProductionRecipe``."""

    recipe_id: str
    action: str
    resource_input_names: tuple[str, ...]
    item_input_names: tuple[str, ...]
    input_kinds: tuple[str, ...]
    output_name: str
    output_kind: str
    skill_domain: str | None
    tool_role: str | None
    requires_tool: bool

    def __post_init__(self) -> None:
        if type(self.recipe_id) is not str or not self.recipe_id:
            raise _contract("recipe_id", "invalid_stage")
        if type(self.action) is not str or self.action not in _PRODUCTION_ACTIONS:
            raise _contract("action", "invalid_stage")
        object.__setattr__(
            self,
            "resource_input_names",
            _sorted_names("resource_input_names", self.resource_input_names),
        )
        object.__setattr__(
            self,
            "item_input_names",
            _sorted_names("item_input_names", self.item_input_names),
        )
        object.__setattr__(
            self, "input_kinds", _sorted_names("input_kinds", self.input_kinds)
        )
        if type(self.output_name) is not str or not self.output_name:
            raise _contract("output_name", "invalid_stage")
        if type(self.output_kind) is not str or self.output_kind not in _OUTPUT_KINDS:
            raise _contract("output_kind", "invalid_stage")
        for field_name in ("skill_domain", "tool_role"):
            value = getattr(self, field_name)
            if value is not None and (type(value) is not str or not value):
                raise _contract(field_name, "invalid_stage")
        if type(self.requires_tool) is not bool:
            raise _contract("requires_tool", "invalid_stage")


@dataclass(frozen=True, slots=True)
class SupplyChainSummary:
    """Validated stage, edge, and depth counts. Never a ranking."""

    stage_count: int
    item_stage_count: int
    edge_count: int
    max_depth: int
    policy_version: str


def _contract(field_name: str, code: str) -> SupplyChainContractError:
    _LOG.warning(
        "supply_chain_catalog_invalid field=%s code=%s stage_count=0 edge_count=0",
        field_name,
        code,
    )
    return SupplyChainContractError(code)


def _item_product_tokens(output: ItemProduct) -> tuple[str, str]:
    return output.name, output.item_kind.value


def production_chain_stages(
    catalog: ProductionCatalog,
) -> tuple[SupplyStageSpec, ...]:
    """Derive typed stages from a catalog without flattening input kinds."""
    if type(catalog) is not ProductionCatalog:
        raise TypeError("catalog must be ProductionCatalog")
    stages: list[SupplyStageSpec] = []
    for recipe in catalog.recipes:
        stages.append(_stage_for(recipe))
    summary = validate_production_chain_catalog(catalog, require_chain=False)
    _LOG.debug(
        "supply_chain_stages_built stage_count=%s edge_count=%s max_depth=%s policy=%s",
        summary.stage_count,
        summary.edge_count,
        summary.max_depth,
        SUPPLY_CHAIN_POLICY_VERSION,
    )
    return tuple(stages)


def _stage_for(recipe: ProductionRecipe) -> SupplyStageSpec:
    resource_names: list[str] = []
    item_names: list[str] = []
    kinds: list[str] = []
    for spec in recipe.inputs:
        if type(spec) is ResourceNameInput:
            resource_names.append(spec.name)
        elif type(spec) is HeldItemNameInput:
            item_names.append(spec.name)
        elif type(spec) is HeldItemKindInput:
            kinds.append(spec.item_kind.value)
    output = recipe.output
    if type(output) is ItemProduct:
        output_name, output_kind = _item_product_tokens(output)
    elif type(output) is ShelterProduct:
        output_name, output_kind = "shelter", "structure"
    elif type(output) is RepairProduct:
        output_name, output_kind = "repair", "structure"
    elif type(output) is StoreProduct:
        output_name, output_kind = "store", "storage"
    else:
        raise _contract("output", "invalid_stage")
    return SupplyStageSpec(
        recipe_id=recipe.recipe_id.value,
        action=recipe.action.value,
        resource_input_names=tuple(resource_names),
        item_input_names=tuple(item_names),
        input_kinds=tuple(kinds),
        output_name=output_name,
        output_kind=output_kind,
        skill_domain=_SKILL_DOMAINS.get(recipe.recipe_id.value),
        tool_role=None if recipe.tool_role is None else recipe.tool_role.value,
        requires_tool=output_kind == "tool",
    )


_SKILL_DOMAINS: Final[Mapping[str, str]] = {
    "craft_tool": "crafting",
    "build_shelter": "building",
    "repair_shelter": "building",
    "mill_grain": "crafting",
    "bake_bread": "crafting",
    "craft_plank": "crafting",
    "craft_tool_head": "crafting",
    "assemble_tool": "crafting",
}


def validate_production_chain_catalog(
    catalog: ProductionCatalog,
    *,
    require_chain: bool = True,
) -> SupplyChainSummary:
    """Validate acyclicity and count item dependencies. Pure and bounded."""
    if type(catalog) is not ProductionCatalog:
        raise TypeError("catalog must be ProductionCatalog")
    stages = tuple(_stage_for(recipe) for recipe in catalog.recipes)
    item_stages = tuple(
        stage for stage in stages if stage.output_kind in _ITEM_OUTPUT_KINDS
    )
    producer_by_name: dict[str, SupplyStageSpec] = {}
    for stage in item_stages:
        producer_by_name.setdefault(stage.output_name, stage)
    edge_count = 0
    adjacency: dict[str, set[str]] = {}
    for stage in item_stages:
        targets = adjacency.setdefault(stage.output_name, set())
        for input_name in stage.item_input_names:
            if input_name not in producer_by_name:
                continue
            edge_count += 1
            if input_name != stage.output_name:
                targets.add(input_name)
    if require_chain and not stages:
        raise _contract("catalog", "supply_chain_catalog_empty")
    if require_chain and edge_count == 0:
        raise _contract("catalog", "supply_chain_catalog_no_chain")
    if _has_cycle(producer_by_name, adjacency):
        raise _contract("catalog", "supply_chain_catalog_cycle")
    max_depth = _max_depth(producer_by_name, adjacency)
    return SupplyChainSummary(
        stage_count=len(stages),
        item_stage_count=len(item_stages),
        edge_count=edge_count,
        max_depth=min(max_depth, SUPPLY_CHAIN_MAX_STAGE_DEPTH),
        policy_version=SUPPLY_CHAIN_POLICY_VERSION,
    )


def _has_cycle(
    producer_by_name: Mapping[str, SupplyStageSpec],
    adjacency: Mapping[str, set[str]],
) -> bool:
    colour: dict[str, int] = {}

    def visit(start: str) -> bool:
        stack: list[tuple[str, bool]] = [(start, False)]
        while stack:
            node, exiting = stack.pop()
            if exiting:
                colour[node] = 2
                continue
            state = colour.get(node, 0)
            if state == 1:
                return True
            if state == 2:
                continue
            colour[node] = 1
            stack.append((node, True))
            for parent in sorted(adjacency.get(node, ()), reverse=True):
                if parent not in producer_by_name:
                    continue
                if colour.get(parent, 0) == 1:
                    return True
                if colour.get(parent, 0) == 0:
                    stack.append((parent, False))
        return False

    for name in sorted(producer_by_name):
        if colour.get(name, 0) == 0 and visit(name):
            return True
    return False


def _max_depth(
    producer_by_name: Mapping[str, SupplyStageSpec],
    adjacency: Mapping[str, set[str]],
) -> int:
    depths: dict[str, int] = {}
    for name in sorted(producer_by_name):
        _depth_of(name, producer_by_name, adjacency, depths)
    return max(depths.values(), default=0)


def _depth_of(
    name: str,
    producer_by_name: Mapping[str, SupplyStageSpec],
    adjacency: Mapping[str, set[str]],
    depths: dict[str, int],
) -> int:
    cached = depths.get(name)
    if cached is not None:
        return cached
    parents = [
        parent for parent in adjacency.get(name, ()) if parent in producer_by_name
    ]
    if not parents:
        depths[name] = 1
        return 1
    depth = 1 + max(
        _depth_of(parent, producer_by_name, adjacency, depths) for parent in parents
    )
    depths[name] = depth
    return depth


def supply_chain_production_catalog(
    base: ProductionCatalog,
) -> ProductionCatalog:
    """Append the closed chain recipes after the base recipes, order preserved."""
    if type(base) is not ProductionCatalog:
        raise TypeError("base must be ProductionCatalog")
    existing = {recipe.recipe_id.value for recipe in base.recipes}
    for recipe in SUPPLY_CHAIN_RECIPES:
        if recipe.recipe_id.value in existing:
            _LOG.warning(
                "supply_chain_recipe_collision recipe_id=%s",
                recipe.recipe_id.value,
            )
            raise SupplyChainContractError("supply_chain_recipe_collision")
    combined = ProductionCatalog(tuple(base.recipes) + SUPPLY_CHAIN_RECIPES)
    _LOG.debug(
        "supply_chain_catalog_extended base_stages=%s added_stages=%s total_stages=%s",
        len(base.recipes),
        len(SUPPLY_CHAIN_RECIPES),
        combined.recipe_count,
    )
    return combined


def harvest_tool_probability_gain(
    state: object,
    actor_id: object,
    recipe: ProductionRecipe,
) -> float:
    """Return the flag-independent STRIKE-tool bonus for a harvest recipe."""
    if recipe.action is not ProductionAction.HARVEST:
        return 0.0
    bodies = getattr(state, "bodies", None)
    marks = getattr(state, "tool_marks", None)
    if not isinstance(bodies, Mapping) or not isinstance(marks, Mapping):
        return 0.0
    actor = bodies.get(actor_id)
    if actor is None:
        return 0.0
    for item_id in getattr(actor, "inventory", ()):
        mark = marks.get(item_id)
        if mark is not None and getattr(mark, "role", None) is ToolRole.STRIKE:
            return SUPPLY_CHAIN_HARVEST_TOOL_PROBABILITY_GAIN
    return 0.0


def _recipe(
    recipe_id: str,
    action: ProductionAction,
    duration_ticks: int,
    success_probability: float,
    *,
    inputs: tuple[ProductionInput, ...],
    output: ProductionOutput,
    tool_role: ToolRole | None = None,
) -> ProductionRecipe:
    return ProductionRecipe(
        recipe_id=RecipeId(recipe_id),
        action=action,
        duration_ticks=duration_ticks,
        success_probability=success_probability,
        inputs=inputs,
        output=output,
        tool_role=tool_role,
    )


_LOAD = ItemLoad(1)

SUPPLY_CHAIN_RECIPES: Final[tuple[ProductionRecipe, ...]] = (
    _recipe(
        "harvest_grain",
        ProductionAction.HARVEST,
        2,
        0.90,
        inputs=(ResourceNameInput("grain"),),
        output=ItemProduct(ItemKind.FOOD, "grain", _LOAD, tool_role=None),
    ),
    _recipe(
        "mill_grain",
        ProductionAction.CRAFT,
        2,
        0.85,
        inputs=(HeldItemNameInput("grain"),),
        output=ItemProduct(ItemKind.MATERIAL, "flour", _LOAD, tool_role=None),
    ),
    _recipe(
        "bake_bread",
        ProductionAction.CRAFT,
        3,
        0.80,
        inputs=(HeldItemNameInput("flour"),),
        output=ItemProduct(ItemKind.FOOD, "bread", _LOAD, tool_role=None),
    ),
    _recipe(
        "craft_plank",
        ProductionAction.CRAFT,
        2,
        0.90,
        inputs=(HeldItemNameInput("wood"),),
        output=ItemProduct(ItemKind.MATERIAL, "plank", _LOAD, tool_role=None),
    ),
    _recipe(
        "craft_tool_head",
        ProductionAction.CRAFT,
        2,
        0.90,
        inputs=(HeldItemNameInput("stone"),),
        output=ItemProduct(ItemKind.MATERIAL, "tool_head", _LOAD, tool_role=None),
    ),
    _recipe(
        "assemble_tool",
        ProductionAction.CRAFT,
        3,
        0.85,
        inputs=(HeldItemNameInput("plank"), HeldItemNameInput("tool_head")),
        output=ItemProduct(
            ItemKind.TOOL, "fine_tool", _LOAD, tool_role=ToolRole.STRIKE
        ),
        tool_role=ToolRole.STRIKE,
    ),
)
