"""Production resolution. Only the engine samples ``production_success``.

Rules call these helpers with an already-resolved draw. This module does not
import randomness, and it does not call ``adjusted_search_probability``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Final

from world._state import WorldState, rebuild_world_state
from world.actions import Build, Craft, Harvest, Repair, Store
from world.effects import ResolvedProductionEffect
from world.events import (
    CraftStarted,
    ItemCrafted,
    ItemStored,
    ResourceHarvested,
    StructureBuilt,
    StructureRepaired,
)
from world.identifiers import EntityId, RecipeId
from world.models import AgentBody, Item, LifeStatus, copy_body, copy_resource
from world.production import (
    INITIAL_SHELTER_INTEGRITY,
    INITIAL_STORE_INTEGRITY,
    INITIAL_STORE_QUANTITY,
    MINIMUM_PRODUCTION_DURATION,
    REPAIR_INTEGRITY_DELTA,
    SHELTER_EXPOSURE_BONUS_COEFFICIENT,
    STORE_QUANTITY_DELTA,
    TOOL_DURATION_REDUCTION,
    HeldItemKindInput,
    HeldItemNameInput,
    ItemProduct,
    ProductionAction,
    ProductionCatalog,
    ProductionJob,
    ProductionRecipe,
    RepairProduct,
    ResourceNameInput,
    ShelterProduct,
    StoreProduct,
    Structure,
    StructureKind,
    ToolMark,
)
from world.values import clamp_unit_interval, round_physical

_LOG: Final[logging.Logger] = logging.getLogger("world._production")

_SKILL_RECIPES: Final[Mapping[str, str]] = {
    "craft_tool": "crafting",
    "build_shelter": "building",
    "repair_shelter": "building",
}


def skill_domain_for_recipe(recipe_id: RecipeId) -> str | None:
    """Crafting or building, and only for the locked example recipe ids."""
    return _SKILL_RECIPES.get(recipe_id.value)


def adjusted_production_probability(
    base: float, *, level: float, probability_gain: float
) -> float:
    """Scale a recipe probability. Level zero reproduces the recipe base."""
    return clamp_unit_interval(base * (1.0 + probability_gain * level))


def effective_duration(
    state: WorldState, actor_id: EntityId, recipe: ProductionRecipe
) -> int:
    duration = recipe.duration_ticks
    role = recipe.tool_role
    if role is None:
        return duration
    actor = state.bodies[actor_id]
    for item_id in actor.inventory:
        mark = state.tool_marks.get(item_id)
        if mark is not None and mark.role is role:
            return max(MINIMUM_PRODUCTION_DURATION, duration - TOOL_DURATION_REDUCTION)
    return duration


def block_reason(
    state: WorldState,
    actor_id: EntityId,
    command: object,
    recipe: ProductionRecipe | None,
) -> str | None:
    """Return a no-event reason, or None when the attempt can resolve."""
    if recipe is None:
        return "unknown_recipe"
    expected = _action_for(command)
    if expected is None or recipe.action is not expected:
        return "recipe_action_mismatch"
    return _availability(state, actor_id, command, recipe)


def apply_resolved(
    state: WorldState,
    *,
    actor_id: EntityId,
    command: object,
    effect: ResolvedProductionEffect,
    tick: int,
) -> tuple[WorldState, object | None, str | None]:
    """Apply one resolved attempt. Returns state, details, and a reject code."""
    recipe = effect.recipe
    if effect.reason_code is not None or recipe is None:
        code = effect.reason_code or "production_disabled"
        _warn(actor_id, effect.recipe_id, code)
        return state, None, code
    blocked = block_reason(state, actor_id, command, recipe)
    if blocked is not None:
        _warn(actor_id, recipe.recipe_id, blocked)
        return state, None, blocked
    duration = effective_duration(state, actor_id, recipe)
    if recipe.action is ProductionAction.HARVEST:
        return _apply_harvest(state, actor_id, command, effect, recipe, duration)
    if recipe.action is ProductionAction.CRAFT:
        return _apply_craft(state, actor_id, effect, recipe, duration, tick)
    if recipe.action is ProductionAction.BUILD:
        return _apply_build(state, actor_id, effect, recipe, duration)
    if recipe.action is ProductionAction.REPAIR:
        return _apply_repair(state, actor_id, command, effect, recipe, duration)
    return _apply_store(state, actor_id, command, effect, recipe, duration)


def complete_due_jobs(
    state: WorldState,
    *,
    tick: int,
    catalog: ProductionCatalog,
) -> tuple[WorldState, tuple[ItemCrafted, ...]]:
    """Finish due crafts before needs. A dead actor drops the job quietly."""
    if not state.production_jobs:
        return state, ()
    jobs = dict(state.production_jobs)
    items = dict(state.items)
    bodies = dict(state.bodies)
    marks = dict(state.tool_marks)
    details: list[ItemCrafted] = []
    changed = False
    for actor_id, job in tuple(jobs.items()):
        if job.due_tick != tick:
            continue
        changed = True
        del jobs[actor_id]
        actor = bodies.get(actor_id)
        if actor is None or actor.life_status is LifeStatus.DEAD:
            _LOG.debug(
                "production_resolved recipe_id=%s success=%s duration=%s "
                "reason_code=%s",
                job.recipe_id.value,
                False,
                job.duration_ticks,
                "dead_actor",
            )
            continue
        recipe = catalog.recipe(job.recipe_id)
        if recipe is None or type(recipe.output) is not ItemProduct:
            continue
        output = recipe.output
        created = Item(
            entity_id=job.created_item_id,
            name=output.name,
            kind=output.item_kind,
            load=output.load,
            holder_id=actor_id,
        )
        items[created.entity_id] = created
        bodies[actor_id] = copy_body(
            actor, inventory=(*actor.inventory, created.entity_id)
        )
        if output.tool_role is not None:
            marks[created.entity_id] = ToolMark(created.entity_id, output.tool_role)
        crafted = ItemCrafted(
            job.recipe_id,
            job.created_item_id,
            actor_id,
            job.duration_ticks,
        )
        details.append(crafted)
        _LOG.debug(
            "production_resolved recipe_id=%s success=%s duration=%s reason_code=%s",
            job.recipe_id.value,
            True,
            job.duration_ticks,
            "completed",
        )
    if not changed:
        return state, ()
    return (
        rebuild_world_state(
            state,
            items=items,
            bodies=bodies,
            production_jobs=jobs,
            tool_marks=marks,
        ),
        tuple(details),
    )


def shelter_factor_for(state: WorldState, location_id: EntityId, base: float) -> float:
    """Replace only the location shelter term when a shelter structure exists."""
    for structure in state.structures.values():
        if (
            structure.location_id == location_id
            and structure.kind is StructureKind.SHELTER
        ):
            return clamp_unit_interval(
                base + SHELTER_EXPOSURE_BONUS_COEFFICIENT * structure.integrity
            )
    return base


def _warn(actor_id: EntityId, recipe_id: object, code: str) -> None:
    if code not in {
        "actor_busy",
        "materials_unavailable",
        "production_disabled",
    }:
        return
    _LOG.warning(
        "%s actor_id=%s recipe_id=%s",
        code,
        actor_id.value,
        "-" if recipe_id is None else recipe_id.value,
    )


def _recipe_of(command: object) -> RecipeId | None:
    recipe_id = getattr(command, "recipe_id", None)
    if type(recipe_id) is RecipeId:
        return recipe_id
    return None


def _action_for(command: object) -> ProductionAction | None:
    if type(command) is Harvest:
        return ProductionAction.HARVEST
    if type(command) is Craft:
        return ProductionAction.CRAFT
    if type(command) is Build:
        return ProductionAction.BUILD
    if type(command) is Repair:
        return ProductionAction.REPAIR
    if type(command) is Store:
        return ProductionAction.STORE
    return None


def _availability(
    state: WorldState,
    actor_id: EntityId,
    command: object,
    recipe: ProductionRecipe,
) -> str | None:
    actor = state.bodies[actor_id]
    if recipe.action is ProductionAction.HARVEST:
        if type(command) is not Harvest:
            return "recipe_action_mismatch"
        resource = state.resources.get(command.resource_id)
        expected = recipe.inputs[0]
        if (
            resource is None
            or type(expected) is not ResourceNameInput
            or resource.name != expected.name
            or resource.location_id != actor.location_id
            or resource.quantity < 1.0
        ):
            return "materials_unavailable"
        return None
    if recipe.action is ProductionAction.CRAFT:
        if _held_named(state, actor, recipe) is None:
            return "materials_unavailable"
        return None
    if recipe.action is ProductionAction.BUILD:
        if _held_kind(state, actor, recipe) is None:
            return "materials_unavailable"
        if _structure_at(state, actor.location_id, StructureKind.SHELTER) is not None:
            return "shelter_already_present"
        return None
    if recipe.action is ProductionAction.REPAIR:
        if type(command) is not Repair:
            return "recipe_action_mismatch"
        structure = state.structures.get(command.structure_id)
        if (
            structure is None
            or structure.kind is not StructureKind.SHELTER
            or structure.location_id != actor.location_id
            or _held_kind(state, actor, recipe) is None
        ):
            return "materials_unavailable"
        if structure.integrity >= 1.0:
            return "structure_intact"
        return None
    if type(command) is not Store:
        return "recipe_action_mismatch"
    item = state.items.get(command.item_id)
    if (
        item is None
        or item.holder_id != actor_id
        or _held_kind(state, actor, recipe) is None
        or item.entity_id != command.item_id
    ):
        return "materials_unavailable"
    stores = [
        structure
        for structure in state.structures.values()
        if structure.location_id == actor.location_id
        and structure.kind is StructureKind.STORE
    ]
    if len(stores) > 1:
        return "store_already_present"
    return None


def _held_named(
    state: WorldState, actor: AgentBody, recipe: ProductionRecipe
) -> tuple[EntityId, ...] | None:
    remaining = list(actor.inventory)
    chosen: list[EntityId] = []
    for spec in recipe.inputs:
        if type(spec) is not HeldItemNameInput:
            return None
        match = next(
            (
                item_id
                for item_id in remaining
                if item_id in state.items and state.items[item_id].name == spec.name
            ),
            None,
        )
        if match is None:
            return None
        remaining.remove(match)
        chosen.append(match)
    return tuple(chosen)


def _held_kind(
    state: WorldState, actor: AgentBody, recipe: ProductionRecipe
) -> EntityId | None:
    spec = recipe.inputs[0]
    if type(spec) is not HeldItemKindInput:
        return None
    for item_id in actor.inventory:
        item = state.items.get(item_id)
        if item is not None and item.kind is spec.item_kind:
            return item_id
    return None


def _structure_at(
    state: WorldState, location_id: EntityId, kind: StructureKind
) -> Structure | None:
    for structure in state.structures.values():
        if structure.location_id == location_id and structure.kind is kind:
            return structure
    return None


def _consume(
    state: WorldState, actor_id: EntityId, item_ids: tuple[EntityId, ...]
) -> tuple[dict[EntityId, Item], dict[EntityId, AgentBody]]:
    items = dict(state.items)
    bodies = dict(state.bodies)
    actor = bodies[actor_id]
    dropping = set(item_ids)
    for item_id in item_ids:
        del items[item_id]
    kept = tuple(item_id for item_id in actor.inventory if item_id not in dropping)
    bodies[actor_id] = copy_body(actor, inventory=kept)
    return items, bodies


def _log_resolved(recipe_id: RecipeId, success: bool, duration: int, code: str) -> None:
    _LOG.debug(
        "production_resolved recipe_id=%s success=%s duration=%s reason_code=%s",
        recipe_id.value,
        success,
        duration,
        code,
    )


def _apply_harvest(
    state: WorldState,
    actor_id: EntityId,
    command: object,
    effect: ResolvedProductionEffect,
    recipe: ProductionRecipe,
    duration: int,
) -> tuple[WorldState, ResourceHarvested, None]:
    assert type(command) is Harvest
    resource = state.resources[command.resource_id]
    if not effect.success:
        _log_resolved(recipe.recipe_id, False, duration, "harvest_failed")
        return (
            state,
            ResourceHarvested(
                recipe.recipe_id,
                resource.entity_id,
                False,
                duration,
                resource.quantity,
            ),
            None,
        )
    assert effect.created_entity_id is not None
    assert type(recipe.output) is ItemProduct
    resulting = round_physical(max(0.0, resource.quantity - 1.0))
    resources = dict(state.resources)
    resources[resource.entity_id] = copy_resource(resource, quantity=resulting)
    created = Item(
        entity_id=effect.created_entity_id,
        name=recipe.output.name,
        kind=recipe.output.item_kind,
        load=recipe.output.load,
        holder_id=actor_id,
    )
    items = dict(state.items)
    items[created.entity_id] = created
    bodies = dict(state.bodies)
    actor = bodies[actor_id]
    bodies[actor_id] = copy_body(actor, inventory=(*actor.inventory, created.entity_id))
    _log_resolved(recipe.recipe_id, True, duration, "harvested")
    return (
        rebuild_world_state(state, items=items, resources=resources, bodies=bodies),
        ResourceHarvested(
            recipe.recipe_id,
            resource.entity_id,
            True,
            duration,
            resulting,
            created_item_id=created.entity_id,
        ),
        None,
    )


def _apply_craft(
    state: WorldState,
    actor_id: EntityId,
    effect: ResolvedProductionEffect,
    recipe: ProductionRecipe,
    duration: int,
    tick: int,
) -> tuple[WorldState, CraftStarted | ItemCrafted, None]:
    actor = state.bodies[actor_id]
    chosen = _held_named(state, actor, recipe)
    assert chosen is not None
    if not effect.success:
        _log_resolved(recipe.recipe_id, False, duration, "craft_failed")
        return (
            state,
            CraftStarted(recipe.recipe_id, False, duration),
            None,
        )
    items, bodies = _consume(state, actor_id, chosen)
    assert type(recipe.output) is ItemProduct
    if duration > 1:
        assert effect.created_entity_id is not None
        jobs = dict(state.production_jobs)
        jobs[actor_id] = ProductionJob(
            actor_id=actor_id,
            recipe_id=recipe.recipe_id,
            due_tick=tick + 1,
            created_item_id=effect.created_entity_id,
            duration_ticks=duration,
        )
        _log_resolved(recipe.recipe_id, True, duration, "craft_started")
        return (
            rebuild_world_state(
                state, items=items, bodies=bodies, production_jobs=jobs
            ),
            CraftStarted(recipe.recipe_id, True, duration, chosen),
            None,
        )
    assert effect.created_entity_id is not None
    created = Item(
        entity_id=effect.created_entity_id,
        name=recipe.output.name,
        kind=recipe.output.item_kind,
        load=recipe.output.load,
        holder_id=actor_id,
    )
    items[created.entity_id] = created
    holder = bodies[actor_id]
    bodies[actor_id] = copy_body(
        holder, inventory=(*holder.inventory, created.entity_id)
    )
    marks = dict(state.tool_marks)
    if recipe.output.tool_role is not None:
        marks[created.entity_id] = ToolMark(created.entity_id, recipe.output.tool_role)
    _log_resolved(recipe.recipe_id, True, duration, "crafted")
    return (
        rebuild_world_state(state, items=items, bodies=bodies, tool_marks=marks),
        ItemCrafted(
            recipe.recipe_id,
            created.entity_id,
            actor_id,
            duration,
        ),
        None,
    )


def _apply_build(
    state: WorldState,
    actor_id: EntityId,
    effect: ResolvedProductionEffect,
    recipe: ProductionRecipe,
    duration: int,
) -> tuple[WorldState, StructureBuilt, None]:
    actor = state.bodies[actor_id]
    consumed = _held_kind(state, actor, recipe)
    assert consumed is not None
    assert effect.created_entity_id is not None
    assert type(recipe.output) is ShelterProduct
    items, bodies = _consume(state, actor_id, (consumed,))
    structure = Structure(
        entity_id=effect.created_entity_id,
        location_id=actor.location_id,
        kind=StructureKind.SHELTER,
        integrity=recipe.output.initial_integrity or INITIAL_SHELTER_INTEGRITY,
        stored_quantity=0,
    )
    structures = dict(state.structures)
    structures[structure.entity_id] = structure
    _log_resolved(recipe.recipe_id, True, duration, "built")
    return (
        rebuild_world_state(state, items=items, bodies=bodies, structures=structures),
        StructureBuilt(
            recipe.recipe_id,
            structure.entity_id,
            actor.location_id,
            structure.integrity,
            duration,
            consumed,
        ),
        None,
    )


def _apply_repair(
    state: WorldState,
    actor_id: EntityId,
    command: object,
    effect: ResolvedProductionEffect,
    recipe: ProductionRecipe,
    duration: int,
) -> tuple[WorldState, StructureRepaired, None]:
    del effect
    assert type(command) is Repair
    actor = state.bodies[actor_id]
    consumed = _held_kind(state, actor, recipe)
    assert consumed is not None
    assert type(recipe.output) is RepairProduct
    prior = state.structures[command.structure_id]
    integrity = clamp_unit_interval(
        prior.integrity + (recipe.output.integrity_delta or REPAIR_INTEGRITY_DELTA)
    )
    items, bodies = _consume(state, actor_id, (consumed,))
    structures = dict(state.structures)
    structures[prior.entity_id] = Structure(
        entity_id=prior.entity_id,
        location_id=prior.location_id,
        kind=prior.kind,
        integrity=integrity,
        stored_quantity=prior.stored_quantity,
    )
    _log_resolved(recipe.recipe_id, True, duration, "repaired")
    return (
        rebuild_world_state(state, items=items, bodies=bodies, structures=structures),
        StructureRepaired(
            recipe.recipe_id,
            prior.entity_id,
            integrity,
            duration,
            consumed,
        ),
        None,
    )


def _apply_store(
    state: WorldState,
    actor_id: EntityId,
    command: object,
    effect: ResolvedProductionEffect,
    recipe: ProductionRecipe,
    duration: int,
) -> tuple[WorldState, ItemStored, None]:
    assert type(command) is Store
    assert type(recipe.output) is StoreProduct
    actor = state.bodies[actor_id]
    items, bodies = _consume(state, actor_id, (command.item_id,))
    structures = dict(state.structures)
    existing = _structure_at(state, actor.location_id, StructureKind.STORE)
    if existing is None:
        assert effect.created_entity_id is not None
        quantity = recipe.output.initial_stored_quantity or INITIAL_STORE_QUANTITY
        structure = Structure(
            entity_id=effect.created_entity_id,
            location_id=actor.location_id,
            kind=StructureKind.STORE,
            integrity=recipe.output.initial_integrity or INITIAL_STORE_INTEGRITY,
            stored_quantity=quantity,
        )
        structures[structure.entity_id] = structure
        structure_id = structure.entity_id
        resulting = quantity
    else:
        resulting = existing.stored_quantity + (
            recipe.output.quantity_delta or STORE_QUANTITY_DELTA
        )
        structures[existing.entity_id] = Structure(
            entity_id=existing.entity_id,
            location_id=existing.location_id,
            kind=existing.kind,
            integrity=existing.integrity,
            stored_quantity=resulting,
        )
        structure_id = existing.entity_id
    _log_resolved(recipe.recipe_id, True, duration, "stored")
    return (
        rebuild_world_state(state, items=items, bodies=bodies, structures=structures),
        ItemStored(
            recipe.recipe_id,
            structure_id,
            resulting,
            duration,
            command.item_id,
        ),
        None,
    )
