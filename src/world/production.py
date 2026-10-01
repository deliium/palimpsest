"""Opt-in production recipes. The catalog is configuration, not world state.

Agents never receive this module's transformation table. ``WorldEngine`` is
the only reader that turns a recipe id into materials, duration, and outputs.
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final, Literal

from world.identifiers import EntityId, RecipeId
from world.values import ItemKind, ItemLoad

_LOG: Final[logging.Logger] = logging.getLogger("world.production")

SHELTER_EXPOSURE_BONUS_COEFFICIENT: Final[float] = 0.25
TOOL_DURATION_REDUCTION: Final[int] = 1
MINIMUM_PRODUCTION_DURATION: Final[int] = 1
INITIAL_SHELTER_INTEGRITY: Final[float] = 0.75
REPAIR_INTEGRITY_DELTA: Final[float] = 0.25
INITIAL_STORE_INTEGRITY: Final[float] = 1.0
INITIAL_STORE_QUANTITY: Final[int] = 1
STORE_QUANTITY_DELTA: Final[int] = 1
HARVEST_SUCCESS_PROBABILITY: Final[float] = 0.80
CRAFT_SUCCESS_PROBABILITY: Final[float] = 0.70
CERTAIN_SUCCESS_PROBABILITY: Final[float] = 1.0
EXAMPLE_ITEM_LOAD: Final[int] = 1

__all__ = [
    "CERTAIN_SUCCESS_PROBABILITY",
    "CRAFT_SUCCESS_PROBABILITY",
    "EXAMPLE_ITEM_LOAD",
    "HARVEST_SUCCESS_PROBABILITY",
    "INITIAL_SHELTER_INTEGRITY",
    "INITIAL_STORE_INTEGRITY",
    "INITIAL_STORE_QUANTITY",
    "MINIMUM_PRODUCTION_DURATION",
    "REPAIR_INTEGRITY_DELTA",
    "SHELTER_EXPOSURE_BONUS_COEFFICIENT",
    "STORE_QUANTITY_DELTA",
    "TOOL_DURATION_REDUCTION",
    "HeldItemKindInput",
    "HeldItemNameInput",
    "ItemProduct",
    "ProductionAction",
    "ProductionCatalog",
    "ProductionInput",
    "ProductionJob",
    "ProductionOutput",
    "ProductionRecipe",
    "RepairProduct",
    "ResourceNameInput",
    "ShelterProduct",
    "StoreProduct",
    "Structure",
    "StructureKind",
    "ToolMark",
    "ToolRole",
    "example_production_catalog",
    "production_catalog_digest",
    "require_production_command_fields",
]


class ProductionAction(StrEnum):
    """Closed production actions. There is no profession or technology tier."""

    HARVEST = "harvest"
    CRAFT = "craft"
    BUILD = "build"
    REPAIR = "repair"
    STORE = "store"


class ToolRole(StrEnum):
    """Role mark on a crafted tool. It is not a field on ``Item``."""

    STRIKE = "strike"


class StructureKind(StrEnum):
    SHELTER = "shelter"
    STORE = "store"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "production_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    return ValueError(f"{field_name}: {code}")


def require_production_command_fields(
    *,
    class_name: str,
    class_action: str,
    action: object,
    recipe_id: object,
) -> RecipeId:
    """Reject a foreign recipe id or an action token that misses the class."""
    if type(action) is not str or action != class_action:
        raise _fail(f"{class_name}.action", "action_token_mismatch")
    if type(recipe_id) is not RecipeId:
        raise _fail(f"{class_name}.recipe_id", "foreign_recipe_id")
    return recipe_id


def _exact_duration(field_name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 1:
        raise _fail(field_name, "duration_below_one")
    return value


def _probability(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "probability_out_of_range")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise _fail(field_name, "probability_out_of_range")
    return 0.0 if number == 0.0 else number


def _unit(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "integrity_out_of_range")
    number = float(value)
    if number < 0.0 or number > 1.0 or number != number:
        raise _fail(field_name, "integrity_out_of_range")
    return 0.0 if number == 0.0 else number


def _nonneg_int(field_name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise _fail(field_name, "quantity_invalid")
    return value


def _positive_delta(field_name: str, value: object) -> float:
    number = _unit(field_name, value)
    if number <= 0.0:
        raise _fail(field_name, "integrity_out_of_range")
    return number


@dataclass(frozen=True, slots=True)
class ResourceNameInput:
    """Named resource present at the actor's location."""

    name: str
    kind: Literal["resource_name"] = field(default="resource_name", init=False)

    def __post_init__(self) -> None:
        name = self.name
        if type(name) is not str or not name or name != name.strip():
            raise _fail("ResourceNameInput.name", "invalid_input")


@dataclass(frozen=True, slots=True)
class HeldItemNameInput:
    """One held item whose name token matches."""

    name: str
    kind: Literal["held_name"] = field(default="held_name", init=False)

    def __post_init__(self) -> None:
        name = self.name
        if type(name) is not str or not name or name != name.strip():
            raise _fail("HeldItemNameInput.name", "invalid_input")


@dataclass(frozen=True, slots=True)
class HeldItemKindInput:
    """One held item of an exact kind."""

    item_kind: ItemKind
    kind: Literal["held_kind"] = field(default="held_kind", init=False)

    def __post_init__(self) -> None:
        if type(self.item_kind) is not ItemKind:
            raise _fail("HeldItemKindInput.item_kind", "invalid_input")


ProductionInput = ResourceNameInput | HeldItemNameInput | HeldItemKindInput


@dataclass(frozen=True, slots=True)
class ItemProduct:
    """Created portable item. Tool role is not stored on ``Item``."""

    item_kind: ItemKind
    name: str
    load: ItemLoad
    tool_role: ToolRole | None = None
    kind: Literal["item"] = field(default="item", init=False)

    def __post_init__(self) -> None:
        if type(self.item_kind) is not ItemKind:
            raise _fail("ItemProduct.item_kind", "invalid_output")
        if type(self.name) is not str or not self.name:
            raise _fail("ItemProduct.name", "invalid_output")
        if type(self.load) is not ItemLoad:
            raise _fail("ItemProduct.load", "invalid_output")
        if self.tool_role is not None and type(self.tool_role) is not ToolRole:
            raise _fail("ItemProduct.tool_role", "invalid_output")
        if self.tool_role is not None and self.item_kind is not ItemKind.TOOL:
            raise _fail("ItemProduct.tool_role", "invalid_output")


@dataclass(frozen=True, slots=True)
class ShelterProduct:
    structure_kind: StructureKind
    initial_integrity: float = INITIAL_SHELTER_INTEGRITY
    kind: Literal["shelter"] = field(default="shelter", init=False)

    def __post_init__(self) -> None:
        if self.structure_kind is not StructureKind.SHELTER:
            raise _fail("ShelterProduct.structure_kind", "invalid_output")
        object.__setattr__(
            self,
            "initial_integrity",
            _unit("ShelterProduct.initial_integrity", self.initial_integrity),
        )


@dataclass(frozen=True, slots=True)
class RepairProduct:
    integrity_delta: float = REPAIR_INTEGRITY_DELTA
    kind: Literal["repair"] = field(default="repair", init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "integrity_delta",
            _positive_delta("RepairProduct.integrity_delta", self.integrity_delta),
        )


@dataclass(frozen=True, slots=True)
class StoreProduct:
    quantity_delta: int = STORE_QUANTITY_DELTA
    initial_integrity: float = INITIAL_STORE_INTEGRITY
    initial_stored_quantity: int = INITIAL_STORE_QUANTITY
    kind: Literal["store"] = field(default="store", init=False)

    def __post_init__(self) -> None:
        quantity = _nonneg_int("StoreProduct.quantity_delta", self.quantity_delta)
        if quantity < 1:
            raise _fail("StoreProduct.quantity_delta", "quantity_invalid")
        object.__setattr__(self, "quantity_delta", quantity)
        object.__setattr__(
            self,
            "initial_integrity",
            _unit("StoreProduct.initial_integrity", self.initial_integrity),
        )
        initial_qty = _nonneg_int(
            "StoreProduct.initial_stored_quantity", self.initial_stored_quantity
        )
        if initial_qty < 1:
            raise _fail("StoreProduct.initial_stored_quantity", "quantity_invalid")
        object.__setattr__(self, "initial_stored_quantity", initial_qty)


ProductionOutput = ItemProduct | ShelterProduct | RepairProduct | StoreProduct


def _inputs_match(action: ProductionAction, inputs: Sequence[object]) -> bool:
    if not inputs:
        return False
    if action is ProductionAction.HARVEST:
        return all(type(item) is ResourceNameInput for item in inputs)
    if action is ProductionAction.CRAFT:
        return all(type(item) is HeldItemNameInput for item in inputs)
    if action in (ProductionAction.BUILD, ProductionAction.REPAIR):
        return all(type(item) is HeldItemKindInput for item in inputs)
    if action is ProductionAction.STORE:
        return all(type(item) is HeldItemKindInput for item in inputs)
    return False


def _output_matches(action: ProductionAction, output: object) -> bool:
    if action in (ProductionAction.HARVEST, ProductionAction.CRAFT):
        return type(output) is ItemProduct
    if action is ProductionAction.BUILD:
        return type(output) is ShelterProduct
    if action is ProductionAction.REPAIR:
        return type(output) is RepairProduct
    if action is ProductionAction.STORE:
        return type(output) is StoreProduct
    return False


@dataclass(frozen=True, slots=True)
class ProductionRecipe:
    """One configured transformation. Beliefs store only the recipe id."""

    recipe_id: RecipeId
    action: ProductionAction
    duration_ticks: int
    success_probability: float
    inputs: tuple[ProductionInput, ...]
    output: ProductionOutput
    tool_role: ToolRole | None = None

    def __post_init__(self) -> None:
        if type(self.recipe_id) is not RecipeId:
            raise _fail("ProductionRecipe.recipe_id", "foreign_recipe_id")
        if type(self.action) is not ProductionAction:
            raise _fail("ProductionRecipe.action", "action_token_mismatch")
        object.__setattr__(
            self,
            "duration_ticks",
            _exact_duration("ProductionRecipe.duration_ticks", self.duration_ticks),
        )
        object.__setattr__(
            self,
            "success_probability",
            _probability(
                "ProductionRecipe.success_probability", self.success_probability
            ),
        )
        if not isinstance(self.inputs, tuple) or not _inputs_match(
            self.action, self.inputs
        ):
            raise _fail("ProductionRecipe.inputs", "input_action_mismatch")
        if not _output_matches(self.action, self.output):
            raise _fail("ProductionRecipe.output", "output_action_mismatch")
        if self.tool_role is not None and type(self.tool_role) is not ToolRole:
            raise _fail("ProductionRecipe.tool_role", "invalid_output")
        if self.tool_role is not None:
            if self.action is not ProductionAction.CRAFT:
                raise _fail("ProductionRecipe.tool_role", "action_token_mismatch")
            output = self.output
            if (
                type(output) is not ItemProduct
                or output.tool_role is not self.tool_role
            ):
                raise _fail("ProductionRecipe.tool_role", "invalid_output")
        elif type(self.output) is ItemProduct and self.output.tool_role is not None:
            raise _fail("ProductionRecipe.tool_role", "invalid_output")


def production_catalog_digest(recipe_ids: Sequence[str]) -> str:
    """SHA-256 of the canonical sorted recipe-id list. Not ``hash()``."""
    payload = "\n".join(sorted(recipe_ids)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class ProductionCatalog:
    """Immutable recipe table. An empty catalog is the disabled default."""

    recipes: tuple[ProductionRecipe, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.recipes, tuple):
            raise _fail("ProductionCatalog.recipes", "invalid_catalog")
        seen: set[RecipeId] = set()
        for recipe in self.recipes:
            if type(recipe) is not ProductionRecipe:
                raise _fail("ProductionCatalog.recipes", "invalid_catalog")
            if recipe.recipe_id in seen:
                raise _fail("ProductionCatalog.recipes", "duplicate_recipe_id")
            seen.add(recipe.recipe_id)
        digest = production_catalog_digest(
            tuple(recipe.recipe_id.value for recipe in self.recipes)
        )
        _LOG.debug(
            "production_catalog_built recipe_count=%s digest=%s",
            len(self.recipes),
            digest,
        )

    def recipe(self, recipe_id: RecipeId) -> ProductionRecipe | None:
        if type(recipe_id) is not RecipeId:
            raise _fail("ProductionCatalog.recipe", "foreign_recipe_id")
        for recipe in self.recipes:
            if recipe.recipe_id == recipe_id:
                return recipe
        return None

    @property
    def recipe_count(self) -> int:
        return len(self.recipes)


@dataclass(frozen=True, slots=True)
class Structure:
    """Location-attached structure. No coordinates."""

    entity_id: EntityId
    location_id: EntityId
    kind: StructureKind
    integrity: float
    stored_quantity: int

    def __post_init__(self) -> None:
        if type(self.entity_id) is not EntityId:
            raise _fail("Structure.entity_id", "invalid_structure")
        if type(self.location_id) is not EntityId:
            raise _fail("Structure.location_id", "invalid_structure")
        if type(self.kind) is not StructureKind:
            raise _fail("Structure.kind", "invalid_structure")
        object.__setattr__(
            self, "integrity", _unit("Structure.integrity", self.integrity)
        )
        object.__setattr__(
            self,
            "stored_quantity",
            _nonneg_int("Structure.stored_quantity", self.stored_quantity),
        )


@dataclass(frozen=True, slots=True)
class ProductionJob:
    """Pending craft whose result arrives on a later tick."""

    actor_id: EntityId
    recipe_id: RecipeId
    due_tick: int
    created_item_id: EntityId
    duration_ticks: int

    def __post_init__(self) -> None:
        if type(self.actor_id) is not EntityId:
            raise _fail("ProductionJob.actor_id", "invalid_job")
        if type(self.recipe_id) is not RecipeId:
            raise _fail("ProductionJob.recipe_id", "foreign_recipe_id")
        if type(self.created_item_id) is not EntityId:
            raise _fail("ProductionJob.created_item_id", "invalid_job")
        object.__setattr__(
            self,
            "due_tick",
            _nonneg_int("ProductionJob.due_tick", self.due_tick),
        )
        object.__setattr__(
            self,
            "duration_ticks",
            _exact_duration("ProductionJob.duration_ticks", self.duration_ticks),
        )


@dataclass(frozen=True, slots=True)
class ToolMark:
    """Production-fold role for a crafted tool. Not an ``Item`` field."""

    item_id: EntityId
    role: ToolRole

    def __post_init__(self) -> None:
        if type(self.item_id) is not EntityId:
            raise _fail("ToolMark.item_id", "invalid_tool_mark")
        if type(self.role) is not ToolRole:
            raise _fail("ToolMark.role", "invalid_tool_mark")


def example_production_catalog() -> ProductionCatalog:
    """The six locked recipes and nothing else."""
    load = ItemLoad(EXAMPLE_ITEM_LOAD)
    return ProductionCatalog(
        (
            ProductionRecipe(
                recipe_id=RecipeId("harvest_wood"),
                action=ProductionAction.HARVEST,
                duration_ticks=MINIMUM_PRODUCTION_DURATION,
                success_probability=HARVEST_SUCCESS_PROBABILITY,
                inputs=(ResourceNameInput("wood"),),
                output=ItemProduct(ItemKind.MATERIAL, "wood", load),
            ),
            ProductionRecipe(
                recipe_id=RecipeId("harvest_stone"),
                action=ProductionAction.HARVEST,
                duration_ticks=MINIMUM_PRODUCTION_DURATION,
                success_probability=HARVEST_SUCCESS_PROBABILITY,
                inputs=(ResourceNameInput("stone"),),
                output=ItemProduct(ItemKind.MATERIAL, "stone", load),
            ),
            ProductionRecipe(
                recipe_id=RecipeId("craft_tool"),
                action=ProductionAction.CRAFT,
                duration_ticks=2,
                success_probability=CRAFT_SUCCESS_PROBABILITY,
                inputs=(HeldItemNameInput("wood"), HeldItemNameInput("stone")),
                output=ItemProduct(
                    ItemKind.TOOL, "tool", load, tool_role=ToolRole.STRIKE
                ),
                tool_role=ToolRole.STRIKE,
            ),
            ProductionRecipe(
                recipe_id=RecipeId("build_shelter"),
                action=ProductionAction.BUILD,
                duration_ticks=MINIMUM_PRODUCTION_DURATION,
                success_probability=CERTAIN_SUCCESS_PROBABILITY,
                inputs=(HeldItemKindInput(ItemKind.MATERIAL),),
                output=ShelterProduct(StructureKind.SHELTER),
            ),
            ProductionRecipe(
                recipe_id=RecipeId("repair_shelter"),
                action=ProductionAction.REPAIR,
                duration_ticks=MINIMUM_PRODUCTION_DURATION,
                success_probability=CERTAIN_SUCCESS_PROBABILITY,
                inputs=(HeldItemKindInput(ItemKind.MATERIAL),),
                output=RepairProduct(),
            ),
            ProductionRecipe(
                recipe_id=RecipeId("store_food"),
                action=ProductionAction.STORE,
                duration_ticks=MINIMUM_PRODUCTION_DURATION,
                success_probability=CERTAIN_SUCCESS_PROBABILITY,
                inputs=(HeldItemKindInput(ItemKind.FOOD),),
                output=StoreProduct(),
            ),
        )
    )
