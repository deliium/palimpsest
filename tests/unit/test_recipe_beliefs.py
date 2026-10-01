"""Recipe beliefs stay owner-scoped and never receive the catalog."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from agents.cognition.configuration import CognitionLoopConfig
from agents.cognition.production import (
    ProductionKnowledgeMode,
    RecipeBeliefSet,
    empty_recipe_beliefs,
    update_recipe_beliefs,
)
from agents.models import AgentId
from simulation.run_control import AgentRuntimeCheckpoint
from tests.unit.test_identity_runtime import _runtime
from world.identifiers import RecipeId

pytestmark = pytest.mark.unit


class WorldState:
    """Type-name stand-in. The updater must not import the real world state."""


class ProductionCatalog:
    """Type-name stand-in. The updater must not import the real catalog."""


def _occurrence(recipe_id: object) -> SimpleNamespace:
    return SimpleNamespace(public_facts={"recipe_id": recipe_id})


def _speech(predicate: str, obj: str, *, relations: int = 1) -> SimpleNamespace:
    relation = SimpleNamespace(predicate=predicate, object=obj)
    content = SimpleNamespace(relations=tuple(relation for _index in range(relations)))
    return SimpleNamespace(
        action_kind="tell",
        utterance=SimpleNamespace(content=content),
    )


def test_witnessed_and_taught_ids_are_stored_without_a_catalog(
    caplog: pytest.LogCaptureFixture,
) -> None:
    owner = AgentId("agent-1")
    observation = SimpleNamespace(
        occurrences=(_occurrence("harvest_wood"), _occurrence("not an id")),
        communications=(
            _speech("recipe", "craft_gold"),
            _speech("instruct", "crafting"),
        ),
    )
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.production"):
        beliefs = update_recipe_beliefs(
            None,
            owner_id=owner,
            observation=observation,
            seed_ids=(RecipeId("build_shelter"),),
        )
    assert beliefs.owner_id == owner
    assert tuple(item.recipe_id.value for item in beliefs.beliefs) == (
        "build_shelter",
        "craft_gold",
        "harvest_wood",
    )
    assert all(item.supported for item in beliefs.beliefs)
    assert "recipe_belief_updated" in caplog.text
    assert "recipe_count=3" in caplog.text
    assert "instruct_not_recipe" in caplog.text
    assert "foreign_recipe_id" in caplog.text
    assert "catalog" not in caplog.text


def test_world_state_catalog_and_other_owners_are_rejected() -> None:
    owner = AgentId("agent-1")
    with pytest.raises(TypeError):
        update_recipe_beliefs(WorldState(), owner_id=owner)
    with pytest.raises(TypeError):
        update_recipe_beliefs(None, owner_id=owner, observation=ProductionCatalog())
    foreign = RecipeBeliefSet(AgentId("agent-2"))
    with pytest.raises(TypeError, match="owner_mismatch"):
        update_recipe_beliefs(foreign, owner_id=owner)
    multiple = SimpleNamespace(
        occurrences=(),
        communications=(_speech("recipe", "craft_tool", relations=2),),
    )
    beliefs = update_recipe_beliefs(
        empty_recipe_beliefs(owner), owner_id=owner, observation=multiple
    )
    assert beliefs.beliefs == ()


def test_disabled_mode_builds_no_set_and_checkpoint_carries_deterministic_beliefs() -> (
    None
):
    assert (
        CognitionLoopConfig().production_knowledge_mode
        is ProductionKnowledgeMode.DISABLED
    )
    runtime, _reader = _runtime()
    owner = runtime.agent_id
    seeded = update_recipe_beliefs(
        None, owner_id=owner, seed_ids=("store_food",)
    )
    runtime._loop._production_knowledge_mode = ProductionKnowledgeMode.DISABLED
    runtime._commit_recipe_beliefs(seeded, 1)
    assert runtime._recipe_beliefs is None
    runtime._loop._production_knowledge_mode = ProductionKnowledgeMode.DETERMINISTIC
    runtime._commit_recipe_beliefs(seeded, 2)
    exported = runtime.export_runtime_checkpoint()
    assert type(exported) is AgentRuntimeCheckpoint
    assert exported.recipe_beliefs == seeded
    fresh, _reader = _runtime()
    fresh.restore_runtime_checkpoint(exported)
    assert fresh._recipe_beliefs == seeded
