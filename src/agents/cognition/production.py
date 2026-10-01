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
from world.identifiers import RecipeId

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
