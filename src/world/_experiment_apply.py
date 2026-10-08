"""Apply a closed experiment delta. Laws stay in ``world._experiment_laws``."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Final

from world._experiment_laws import ExperimentLawCatalog
from world._state import WorldState, rebuild_world_state
from world.events import ExperimentResolved
from world.experimentation import (
    DiscoveryMode,
    ExperimentDeltaKind,
    ExperimentHarmBand,
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)
from world.identifiers import EntityId
from world.models import AgentBody, Item, LifeStatus, Resource, copy_body
from world.production import ItemProduct, ProductionCatalog, ToolMark
from world.values import Health, clamp_need, round_physical

_LOG: Final = logging.getLogger("world._experiment_apply")


@dataclass(frozen=True, slots=True)
class ExperimentApplication:
    details: ExperimentResolved
    next_state: WorldState
    mutates: bool


def require_experiment_catalog(value: object) -> ExperimentLawCatalog | None:
    if value is None:
        return None
    if type(value) is not ExperimentLawCatalog:
        raise TypeError("experiment_catalog must be ExperimentLawCatalog or None")
    return value


def resolve_experiment(
    state: WorldState,
    *,
    actor_id: EntityId,
    operator: ExperimentOperator,
    operand_a_id: EntityId,
    operand_b_id: EntityId | None,
    process_token: ExperimentProcessToken,
    hypothesis_id: str,
    catalog: ExperimentLawCatalog,
    rules_hunger_damage: float,
    rules_attack_damage_min: int,
    tick: int,
    request_token: str,
    log: bool = True,
) -> ExperimentApplication:
    """Match one law and apply its predeclared delta. No RNG."""
    actor = state.bodies[actor_id]
    operand_a = _reachable_operand(state, actor, operand_a_id)
    operand_b = (
        None
        if operand_b_id is None
        else _reachable_operand(state, actor, operand_b_id)
    )
    missing = operand_a is None or (
        operand_b_id is not None and operand_b is None
    )
    if missing:
        result_class = ExperimentOutcomeClass.FAILURE
        delta = ExperimentDeltaKind.NONE
        product_id = ""
        harm_band = ExperimentHarmBand.NONE
    else:
        law = catalog.evaluate(
            operator=operator,
            operand_a=operand_a,
            operand_b=operand_b,
            process_token=process_token,
        )
        result_class = law.outcome_class
        delta = law.delta
        product_id = law.product_id
        harm_band = law.harm_band
    mode = (
        DiscoveryMode.DELIBERATE
        if hypothesis_id
        else DiscoveryMode.ACCIDENTAL
    )
    next_state, created_id, health_delta, resulting_health, applied = _apply_delta(
        state,
        actor=actor,
        operand_a_id=operand_a_id,
        operand_a=operand_a,
        delta=delta,
        product_id=product_id,
        harm_band=harm_band,
        hunger_damage=rules_hunger_damage,
        attack_damage_min=rules_attack_damage_min,
        tick=tick,
        request_token=request_token,
        catalog=catalog.production_catalog,
    )
    if not applied:
        delta = ExperimentDeltaKind.NONE
        if result_class is not ExperimentOutcomeClass.FAILURE:
            result_class = ExperimentOutcomeClass.FAILURE
        created_id = None
        health_delta = 0.0
        resulting_health = None
        next_state = state
    details = ExperimentResolved(
        operator=operator.value,
        operand_a_id=operand_a_id,
        operand_b_id=operand_b_id,
        process_token=process_token.value,
        outcome_class=result_class.value,
        delta=delta.value,
        discovery_mode=mode.value,
        product_id=product_id if applied else "",
        health_delta=health_delta,
        resulting_health=resulting_health,
        created_item_id=created_id,
    )
    if log:
        _LOG.info(
            "experiment_resolved actor_id=%s operator=%s outcome_class=%s delta=%s",
            actor_id.value,
            operator.value,
            details.outcome_class,
            details.delta,
        )
    return ExperimentApplication(
        details=details,
        next_state=next_state,
        mutates=next_state is not state,
    )


def project_experiment_resolved(
    state: WorldState,
    details: ExperimentResolved,
    *,
    actor_id: EntityId | None,
    production_catalog: ProductionCatalog | None,
) -> WorldState:
    """Replay the recorded delta. Do not re-evaluate laws."""
    if actor_id is None or actor_id not in state.bodies:
        raise ValueError("experiment_actor_missing")
    delta = ExperimentDeltaKind(details.delta)
    if delta is ExperimentDeltaKind.NONE:
        return state
    if delta is ExperimentDeltaKind.CONSUME_OPERAND:
        return _consume(state, details.operand_a_id)
    if delta in {
        ExperimentDeltaKind.EMIT_CATALOG_PRODUCT,
        ExperimentDeltaKind.PARTIAL_EMIT,
    }:
        if details.created_item_id is None or production_catalog is None:
            raise ValueError("experiment_emit_incomplete")
        return _emit_item(
            state,
            actor_id=actor_id,
            product_id=details.product_id,
            created_id=details.created_item_id,
            catalog=production_catalog,
        )
    if details.resulting_health is None:
        raise ValueError("experiment_harm_incomplete")
    return _set_health(state, actor_id, details.resulting_health)


def _reachable_operand(
    state: WorldState, actor: AgentBody, entity_id: EntityId
) -> object | None:
    entity = _lookup(state, entity_id)
    if entity is None or not _reachable(state, actor, entity):
        return None
    return entity


def _lookup(state: WorldState, entity_id: EntityId) -> object | None:
    if entity_id in state.items:
        return state.items[entity_id]
    if entity_id in state.resources:
        return state.resources[entity_id]
    if entity_id in state.tool_marks:
        return state.tool_marks[entity_id]
    return None


def _reachable(state: WorldState, actor: AgentBody, entity: object) -> bool:
    if type(entity) is Item:
        return (
            entity.holder_id == actor.entity_id
            or entity.location_id == actor.location_id
        )
    if type(entity) is Resource:
        return entity.location_id == actor.location_id
    if type(entity) is ToolMark:
        item = state.items.get(entity.item_id)
        return item is not None and _reachable(state, actor, item)
    return False


def _apply_delta(
    state: WorldState,
    *,
    actor: AgentBody,
    operand_a_id: EntityId,
    operand_a: object | None,
    delta: ExperimentDeltaKind,
    product_id: str,
    harm_band: ExperimentHarmBand,
    hunger_damage: float,
    attack_damage_min: int,
    tick: int,
    request_token: str,
    catalog: ProductionCatalog,
) -> tuple[WorldState, EntityId | None, float, float | None, bool]:
    missing_operand = operand_a is None
    harmless = delta is not ExperimentDeltaKind.APPLY_HARM_BAND
    if delta is ExperimentDeltaKind.NONE or (missing_operand and harmless):
        return state, None, 0.0, None, delta is ExperimentDeltaKind.NONE
    if delta is ExperimentDeltaKind.CONSUME_OPERAND:
        if operand_a is None:
            return state, None, 0.0, None, False
        try:
            return _consume(state, operand_a_id), None, 0.0, None, True
        except ValueError:
            _LOG.debug(
                "experiment_admission_rejected reason_code=experiment_consume_failed"
            )
            return state, None, 0.0, None, False
    if delta in {
        ExperimentDeltaKind.EMIT_CATALOG_PRODUCT,
        ExperimentDeltaKind.PARTIAL_EMIT,
    }:
        created_id = _created_id(
            tick=tick,
            actor_id=actor.entity_id,
            product_id=product_id,
            request_token=request_token,
            existing=state.items,
        )
        try:
            next_state = _emit_item(
                state,
                actor_id=actor.entity_id,
                product_id=product_id,
                created_id=created_id,
                catalog=catalog,
            )
        except ValueError:
            _LOG.debug(
                "experiment_admission_rejected reason_code=experiment_emit_failed"
            )
            return state, None, 0.0, None, False
        return next_state, created_id, 0.0, None, True
    if delta is ExperimentDeltaKind.APPLY_HARM_BAND:
        amount = (
            hunger_damage
            if harm_band is ExperimentHarmBand.MINOR
            else float(attack_damage_min)
        )
        resulting = clamp_need(round_physical(actor.health.value - amount))
        next_state = _set_health(state, actor.entity_id, resulting)
        health_delta = round_physical(resulting - actor.health.value)
        return next_state, None, health_delta, resulting, True
    return state, None, 0.0, None, False


def _created_id(
    *,
    tick: int,
    actor_id: EntityId,
    product_id: str,
    request_token: str,
    existing: Mapping[EntityId, Item],
) -> EntityId:
    stem = f"exp-{tick}-{actor_id.value}-{product_id}"
    if len(stem) > 128 or EntityId(stem) in existing:
        stem = f"exp-{tick}-{request_token}"
    return EntityId(stem[:128])


def _consume(state: WorldState, entity_id: EntityId) -> WorldState:
    if entity_id in state.items:
        item = state.items[entity_id]
        items = dict(state.items)
        items.pop(entity_id)
        marks = dict(state.tool_marks)
        marks.pop(entity_id, None)
        bodies = dict(state.bodies)
        if item.holder_id is not None and item.holder_id in bodies:
            holder = bodies[item.holder_id]
            bodies[item.holder_id] = copy_body(
                holder,
                inventory=tuple(
                    held for held in holder.inventory if held != entity_id
                ),
            )
        return rebuild_world_state(
            state, items=items, bodies=bodies, tool_marks=marks
        )
    if entity_id in state.resources:
        resource = state.resources[entity_id]
        if resource.quantity <= 0.0:
            raise ValueError("experiment_resource_empty")
        quantity = round_physical(max(0.0, resource.quantity - 1.0))
        resources = dict(state.resources)
        resources[entity_id] = replace(resource, quantity=quantity)
        return rebuild_world_state(state, resources=resources)
    if entity_id in state.tool_marks:
        return _consume(state, state.tool_marks[entity_id].item_id)
    raise ValueError("experiment_operand_missing")


def _emit_item(
    state: WorldState,
    *,
    actor_id: EntityId,
    product_id: str,
    created_id: EntityId,
    catalog: ProductionCatalog,
) -> WorldState:
    from world.identifiers import RecipeId

    recipe = catalog.recipe(RecipeId(product_id))
    if recipe is None or type(recipe.output) is not ItemProduct:
        raise ValueError("experiment_product_not_item")
    output = recipe.output
    created = Item(
        entity_id=created_id,
        name=output.name,
        kind=output.item_kind,
        load=output.load,
        holder_id=actor_id,
    )
    items = dict(state.items)
    items[created_id] = created
    bodies = dict(state.bodies)
    actor = bodies[actor_id]
    bodies[actor_id] = copy_body(
        actor, inventory=(*actor.inventory, created_id)
    )
    marks = dict(state.tool_marks)
    if output.tool_role is not None:
        marks[created_id] = ToolMark(created_id, output.tool_role)
    return rebuild_world_state(
        state, items=items, bodies=bodies, tool_marks=marks
    )


def _set_health(state: WorldState, actor_id: EntityId, resulting: float) -> WorldState:
    bodies = dict(state.bodies)
    actor = bodies[actor_id]
    if resulting <= 0.0:
        bodies[actor_id] = copy_body(
            actor, health=Health(0.0), life_status=LifeStatus.DEAD
        )
    else:
        bodies[actor_id] = copy_body(actor, health=Health(resulting))
    return rebuild_world_state(state, bodies=bodies)
