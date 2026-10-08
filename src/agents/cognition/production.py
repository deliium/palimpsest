"""Owner-scoped recipe ids. This module does not hold the catalog.

Beliefs store ids and a supported flag. They do not store inputs, durations,
or probabilities. ``ProductionCatalog`` and ``WorldState`` are rejected by
type name and are not imported.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.models import AgentId
from world.actions import (
    AgentCommand,
    Build,
    Craft,
    Harvest,
    Repair,
    Store,
    Wait,
)
from world.identifiers import EntityId, RecipeId
from world.values import ItemKind

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.production")
_RECIPE_ID = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_FORBIDDEN: Final[frozenset[str]] = frozenset({"WorldState", "ProductionCatalog"})
_RECIPE_ACTIONS: Final[frozenset[str]] = frozenset({"talk", "ask", "tell"})


class ProductionKnowledgeMode(StrEnum):
    """Opt-in recipe beliefs. Disabled builds no set.

    This is not a ``V2CapabilityFlags`` slot.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"


@dataclass(frozen=True, slots=True)
class RecipeBelief:
    """One believed recipe id. ``supported`` is not catalog membership."""

    recipe_id: RecipeId
    supported: bool = True

    def __post_init__(self) -> None:
        if type(self.recipe_id) is not RecipeId:
            raise TypeError("RecipeBelief.recipe_id must be RecipeId")
        if type(self.supported) is not bool:
            raise TypeError("RecipeBelief.supported must be bool")


@dataclass(frozen=True, slots=True)
class RecipeBeliefSet:
    """Owner-scoped recipe ids. Another owner's set is rejected."""

    owner_id: AgentId
    beliefs: tuple[RecipeBelief, ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("RecipeBeliefSet.owner_id must be AgentId")
        if isinstance(self.beliefs, (str, bytes)) or not isinstance(
            self.beliefs, tuple
        ):
            raise TypeError("RecipeBeliefSet.beliefs must be a tuple")
        ordered: list[RecipeBelief] = []
        seen: set[str] = set()
        for belief in self.beliefs:
            if type(belief) is not RecipeBelief:
                raise TypeError("RecipeBeliefSet.beliefs entries must be RecipeBelief")
            if belief.recipe_id.value in seen:
                raise ValueError("RecipeBeliefSet.beliefs: duplicate_recipe_id")
            seen.add(belief.recipe_id.value)
            ordered.append(belief)
        ordered.sort(key=lambda item: item.recipe_id.value)
        object.__setattr__(self, "beliefs", tuple(ordered))

    def belief(self, recipe_id: RecipeId) -> RecipeBelief | None:
        if type(recipe_id) is not RecipeId:
            raise TypeError("recipe_id must be RecipeId")
        for belief in self.beliefs:
            if belief.recipe_id == recipe_id:
                return belief
        return None


def empty_recipe_beliefs(owner_id: AgentId) -> RecipeBeliefSet:
    if type(owner_id) is not AgentId:
        raise TypeError("owner_id must be AgentId")
    return RecipeBeliefSet(owner_id)


def require_owner_recipe_beliefs(
    beliefs: object | None, owner_id: AgentId, *, field_name: str
) -> None:
    """Reject a foreign set. ``None`` is the disabled absence."""
    if beliefs is None:
        return
    _reject_forbidden(beliefs)
    if type(beliefs) is not RecipeBeliefSet:
        raise TypeError(f"{field_name} must be RecipeBeliefSet or None")
    if type(owner_id) is not AgentId:
        raise TypeError("owner_id must be AgentId")
    if beliefs.owner_id != owner_id:
        raise TypeError(f"{field_name}: owner_mismatch")


def update_recipe_beliefs(
    beliefs: object | None,
    *,
    owner_id: AgentId,
    observation: object | None = None,
    seed_ids: Sequence[object] = (),
) -> RecipeBeliefSet:
    """Record seed ids and recipe ids witnessed or taught to this owner."""
    _reject_forbidden(beliefs)
    _reject_forbidden(observation)
    if type(owner_id) is not AgentId:
        raise TypeError("owner_id must be AgentId")
    if beliefs is None:
        current = empty_recipe_beliefs(owner_id)
    elif type(beliefs) is not RecipeBeliefSet:
        raise TypeError("beliefs must be RecipeBeliefSet or None")
    elif beliefs.owner_id != owner_id:
        raise TypeError("beliefs: owner_mismatch")
    else:
        current = beliefs
    supported: dict[str, bool] = {
        belief.recipe_id.value: belief.supported for belief in current.beliefs
    }
    for seed in seed_ids:
        _reject_forbidden(seed)
        token = _recipe_token(seed)
        if token is None:
            _LOG.warning("recipe_relation_ignored reason_code=%s", "foreign_recipe_id")
            continue
        supported[token] = True
    if observation is not None:
        _absorb_observation(observation, supported)
    updated = RecipeBeliefSet(
        owner_id,
        tuple(
            RecipeBelief(RecipeId(token), flag)
            for token, flag in supported.items()
        ),
    )
    _LOG.debug(
        "recipe_belief_updated owner_id=%s recipe_count=%s supported_count=%s",
        owner_id.value,
        len(updated.beliefs),
        sum(1 for belief in updated.beliefs if belief.supported),
    )
    return updated


def _reject_forbidden(value: object | None) -> None:
    if value is not None and type(value).__name__ in _FORBIDDEN:
        raise TypeError(f"{type(value).__name__} is not a recipe belief input")


def _recipe_token(value: object) -> str | None:
    if type(value) is RecipeId:
        return value.value
    if type(value) is str and _RECIPE_ID.fullmatch(value) is not None:
        return value
    return None


def _absorb_observation(observation: object, supported: dict[str, bool]) -> None:
    occurrences = getattr(observation, "occurrences", ())
    if not isinstance(occurrences, (str, bytes)) and isinstance(occurrences, Sequence):
        for occurrence in occurrences:
            facts = getattr(occurrence, "public_facts", {})
            if not isinstance(facts, dict) and not hasattr(facts, "get"):
                continue
            token = _recipe_token(facts.get("recipe_id"))
            if facts.get("recipe_id") is None:
                continue
            if token is None:
                _LOG.warning(
                    "recipe_relation_ignored reason_code=%s", "foreign_recipe_id"
                )
                continue
            supported[token] = True
    communications = getattr(observation, "communications", ())
    if isinstance(communications, (str, bytes)) or not isinstance(
        communications, Sequence
    ):
        return
    for communication in communications:
        _absorb_relation(communication, supported)


def _absorb_relation(communication: object, supported: dict[str, bool]) -> None:
    action = getattr(communication, "action_kind", "")
    if action not in _RECIPE_ACTIONS:
        _LOG.warning("recipe_relation_ignored reason_code=%s", "not_recipe")
        return
    content = getattr(getattr(communication, "utterance", None), "content", None)
    relations = tuple(getattr(content, "relations", ()))
    if len(relations) != 1:
        _LOG.warning("recipe_relation_ignored reason_code=%s", "multiple_relations")
        return
    relation = relations[0]
    predicate = getattr(relation, "predicate", "")
    if predicate == "instruct":
        _LOG.warning("recipe_relation_ignored reason_code=%s", "instruct_not_recipe")
        return
    if predicate != "recipe":
        _LOG.warning("recipe_relation_ignored reason_code=%s", "not_recipe")
        return
    token = _recipe_token(getattr(relation, "object", ""))
    if token is None:
        _LOG.warning("recipe_relation_ignored reason_code=%s", "foreign_recipe_id")
        return
    supported[token] = True


def compile_production_command(
    beliefs: object | None,
    observation: object,
    *,
    vetoed: bool = False,
    selected_recipe_id: RecipeId | None = None,
) -> AgentCommand | None:
    """Compile one production command, or leave the existing command alone.

    ``None`` means the caller keeps the command it already chose. ``Wait`` means
    a production attempt was withheld.
    """
    if beliefs is None:
        return None
    _reject_forbidden(beliefs)
    _reject_forbidden(observation)
    if type(beliefs) is not RecipeBeliefSet:
        raise TypeError("beliefs must be RecipeBeliefSet or None")
    if vetoed:
        _LOG.info("production_command_withheld reason_code=%s", "veto")
        return None
    if selected_recipe_id is not None:
        if type(selected_recipe_id) is not RecipeId:
            raise TypeError("selected_recipe_id must be RecipeId")
        belief = beliefs.belief(selected_recipe_id)
        if belief is None or not belief.supported:
            _LOG.info("production_command_withheld reason_code=%s", "unsupported")
            return Wait()
        command = _command_for_recipe(belief.recipe_id, observation)
        if command is None:
            _LOG.info("production_command_withheld reason_code=%s", "no_target")
            return Wait()
        _log_selected(command)
        return command
    supported = tuple(belief for belief in beliefs.beliefs if belief.supported)
    for belief in supported:
        command = _command_for_recipe(belief.recipe_id, observation)
        if command is None:
            continue
        _log_selected(command)
        return command
    if supported:
        _LOG.info("production_command_withheld reason_code=%s", "no_target")
        return Wait()
    if beliefs.beliefs:
        _LOG.info("production_command_withheld reason_code=%s", "unsupported")
        return Wait()
    return None


def _log_selected(command: AgentCommand) -> None:
    recipe_id = getattr(command, "recipe_id", None)
    _LOG.debug(
        "production_command_selected recipe_id=%s command_kind=%s",
        "-" if recipe_id is None else recipe_id.value,
        command.kind,
    )


def _command_for_recipe(
    recipe_id: RecipeId, observation: object
) -> AgentCommand | None:
    token = recipe_id.value
    if token.startswith("harvest_"):
        resource = _named_resource(observation, token.removeprefix("harvest_"))
        if resource is None:
            return None
        return Harvest(recipe_id, resource)
    if token.startswith("craft_"):
        return Craft(recipe_id)
    if token.startswith("build_"):
        if _held_item(observation, ItemKind.MATERIAL) is None:
            return None
        return Build(recipe_id)
    if token.startswith("repair_"):
        material = _held_item(observation, ItemKind.MATERIAL)
        shelter = _structure(observation, "shelter")
        if material is None or shelter is None:
            return None
        integrity = getattr(shelter, "integrity", 1.0)
        if isinstance(integrity, bool) or not isinstance(integrity, (int, float)):
            return None
        if integrity >= 1.0:
            return None
        return Repair(recipe_id, shelter.entity_id)
    if token.startswith("store_"):
        food = _held_item(observation, ItemKind.FOOD)
        if food is None:
            return None
        return Store(recipe_id, food)
    return None


def _named_resource(observation: object, name: str) -> EntityId | None:
    matches: list[EntityId] = []
    for resource in getattr(observation, "resources", ()):
        if getattr(resource, "name", None) != name:
            continue
        quantity = getattr(resource, "quantity", 0.0)
        if isinstance(quantity, bool) or not isinstance(quantity, (int, float)):
            continue
        if quantity < 1.0:
            continue
        entity_id = getattr(resource, "entity_id", None)
        if type(entity_id) is EntityId:
            matches.append(entity_id)
    if not matches:
        return None
    return sorted(matches, key=lambda item: item.value)[0]


def _held_item(observation: object, kind: ItemKind) -> EntityId | None:
    matches: list[EntityId] = []
    for item in getattr(observation, "items", ()):
        if getattr(item, "kind", None) is not kind:
            continue
        placement = getattr(getattr(item, "placement", None), "value", None)
        if placement != "held_by_self":
            continue
        entity_id = getattr(item, "entity_id", None)
        if type(entity_id) is EntityId:
            matches.append(entity_id)
    if not matches:
        return None
    return sorted(matches, key=lambda item: item.value)[0]


def _structure(observation: object, kind: str) -> object | None:
    matches = []
    for structure in getattr(observation, "structures", ()):
        structure_kind = getattr(structure, "kind", None)
        value = getattr(structure_kind, "value", structure_kind)
        if value != kind:
            continue
        matches.append(structure)
    if not matches:
        return None
    return sorted(matches, key=lambda item: item.entity_id.value)[0]


def observed_experiment_operand_ids(observation: object) -> tuple[str, ...]:
    """Sorted entity ids copied from the current observation."""
    found: set[str] = set()
    for name in ("items", "resources", "structures", "artifacts"):
        rows = getattr(observation, name, ())
        if isinstance(rows, (str, bytes)) or not isinstance(rows, tuple | list):
            continue
        for row in rows:
            entity_id = getattr(row, "entity_id", None)
            value = getattr(entity_id, "value", None)
            if type(value) is str and value:
                found.add(value)
    return tuple(sorted(found))
