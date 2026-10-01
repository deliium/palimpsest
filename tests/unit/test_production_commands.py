"""Production commands come only from supported recipe beliefs."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from agents.cognition.deliberation import (
    _DIRECTION_TIE_RANK,
    CommandPlanner,
)
from agents.cognition.models import (
    ActionDirection,
    CognitiveLoopInput,
    ImaginedFuture,
    IntentionCode,
    InternalAgentState,
    MotivationCode,
    PossibleFutures,
    SelectedIntention,
    SituationClaimCode,
)
from agents.cognition.production import (
    RecipeBelief,
    RecipeBeliefSet,
    compile_production_command,
)
from agents.cognition.production_selection import select_production_recipe
from agents.models import AgentId
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from tests.physical_helpers import physical_config, two_location_fixture
from tests.simulation_helpers import alive_body, make_item
from world.actions import Craft, Drink, Harvest, Search, Wait
from world.identifiers import EntityId, RecipeId, WorldId, WorldRevision
from world.observations import Observation, ObservedResource
from world.production import example_production_catalog
from world.values import ItemKind, ResourceKind

pytestmark = pytest.mark.unit

_OWNER = AgentId("agent-1")


def _observation(*, resources: tuple[object, ...] = ()) -> Observation:
    return Observation(
        observer_id=EntityId("body-1"),
        world_id=WorldId("world-1"),
        revision=WorldRevision(1),
        tick=1,
        resources=resources,  # type: ignore[arg-type]
    )


def _beliefs(*pairs: tuple[str, bool]) -> RecipeBeliefSet:
    return RecipeBeliefSet(
        _OWNER,
        tuple(
            RecipeBelief(RecipeId(recipe_id), supported)
            for recipe_id, supported in pairs
        ),
    )


def _input(observation: Observation | None = None) -> CognitiveLoopInput:
    return CognitiveLoopInput(
        agent_id=_OWNER,
        observation=_observation() if observation is None else observation,
        internal_state=InternalAgentState(owner_id=_OWNER),
    )


def _selected(direction: ActionDirection) -> SelectedIntention:
    return SelectedIntention(
        owner_id=_OWNER,
        intention=IntentionCode.WAIT,
        source_motive=MotivationCode.WAIT,
        confidence=0.8,
        selected_future_id="future-1",
        direction=direction,
        appraisal_future_ids=("future-1",),
    )


def _futures(direction: ActionDirection) -> PossibleFutures:
    return PossibleFutures(
        owner_id=_OWNER,
        futures=(
            ImaginedFuture(
                future_id="future-1",
                claim_codes=(SituationClaimCode.IDLE,),
                confidence=1.0,
                direction=direction,
            ),
        ),
        confidence=1.0,
    )


def test_disabled_directions_and_tie_ranks_stay_closed() -> None:
    assert set(_DIRECTION_TIE_RANK) == set(ActionDirection)
    assert ActionDirection.SEARCH.value == "search"
    assert "harvest" not in {item.value for item in ActionDirection}


@pytest.mark.asyncio
async def test_disabled_planner_keeps_the_search_command() -> None:
    without = await CommandPlanner().plan(
        _input(), _selected(ActionDirection.SEARCH), _futures(ActionDirection.SEARCH)
    )
    explicit = await CommandPlanner().plan(
        _input(),
        _selected(ActionDirection.SEARCH),
        _futures(ActionDirection.SEARCH),
        recipe_beliefs=None,
    )
    assert type(without.command) is Search
    assert type(explicit.command) is Search
    assert without.command.target_id == explicit.command.target_id


@pytest.mark.asyncio
async def test_supported_false_recipe_is_submitted_and_unknown_id_waits(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.production")
    gold = await CommandPlanner().plan(
        _input(),
        _selected(ActionDirection.SEARCH),
        _futures(ActionDirection.SEARCH),
        recipe_beliefs=_beliefs(("craft_gold", True)),
    )
    assert type(gold.command) is Craft
    assert gold.command.recipe_id == RecipeId("craft_gold")
    assert "production_command_selected" in caplog.text

    waiting = await CommandPlanner().plan(
        _input(),
        _selected(ActionDirection.SEARCH),
        _futures(ActionDirection.SEARCH),
        recipe_beliefs=_beliefs(("craft_gold", False)),
    )
    assert type(waiting.command) is Wait
    assert "unsupported" in caplog.text


def test_visible_wood_compiles_harvest_and_a_drink_veto_wins() -> None:
    observation = _observation(
        resources=(
            ObservedResource(
                entity_id=EntityId("res-wood"),
                name="wood",
                kind=ResourceKind.MATERIAL,
                quantity=2.0,
                unit="unit",
            ),
        )
    )
    harvested = compile_production_command(
        _beliefs(("harvest_wood", True)), observation
    )
    assert type(harvested) is Harvest
    assert harvested.resource_id == EntityId("res-wood")
    kept = compile_production_command(
        _beliefs(("craft_tool", True)),
        observation,
        vetoed=True,
    )
    assert kept is None
    drink = Drink(source_id=EntityId("res-water"))
    from agents.cognition.deliberation import _with_production_command

    assert (
        _with_production_command(
            drink,
            beliefs=_beliefs(("craft_tool", True)),
            observation=observation,
            selected_recipe_id=None,
        )
        is drink
    )


def test_scripted_craft_still_resolves_without_beliefs() -> None:
    fixture = two_location_fixture(item_on_ground=False)
    items = (
        make_item(
            "item-wood",
            name="wood",
            kind=ItemKind.MATERIAL,
            location_id=None,
            holder_id="body-1",
        ),
        make_item(
            "item-stone",
            name="stone",
            kind=ItemKind.MATERIAL,
            location_id=None,
            holder_id="body-1",
        ),
    )
    bodies = (
        alive_body(
            "body-1",
            inventory=(EntityId("item-wood"), EntityId("item-stone")),
        ),
        alive_body("body-2"),
    )
    from tests.physical_helpers import PhysicalWorldFixture

    world = PhysicalWorldFixture(
        world_id=fixture.world_id,
        locations=fixture.locations,
        bodies=bodies,
        items=items,
        resources=fixture.resources,
        weather=fixture.weather,
        registrations=fixture.registrations,
    )
    engine = WorldEngine(
        config=physical_config(1),
        bootstrap=world.as_bootstrap(),
        production_catalog=example_production_catalog(),
    )
    batch = engine.observe()
    applied = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token, AgentId("agent-1"), Craft(RecipeId("craft_tool"))
            ),
        )
    )
    assert applied.resolutions[0].status is ActionResolutionStatus.APPLIED
    other = WorldEngine(
        config=physical_config(1),
        bootstrap=world.as_bootstrap(),
        production_catalog=example_production_catalog(),
    )
    rejected = other.resolve_tick(
        (
            ActionSubmission(
                other.observe().token,
                AgentId("agent-1"),
                Craft(RecipeId("craft_gold")),
            ),
        )
    )
    assert rejected.resolutions[0].status is ActionResolutionStatus.REJECTED
    assert not any(
        type(record.event.details).__name__ == "CraftStarted"
        for record in rejected.events
    )


def test_held_food_is_not_required_for_false_craft() -> None:
    empty = compile_production_command(_beliefs(), _observation())
    assert empty is None
    missing = compile_production_command(
        _beliefs(("harvest_wood", True)), _observation()
    )
    assert type(missing) is Wait
    item = SimpleNamespace(
        entity_id=EntityId("food-1"),
        kind=ItemKind.FOOD,
        placement=SimpleNamespace(value="held_by_self"),
    )
    observation = SimpleNamespace(items=(item,), resources=(), structures=())
    stored = compile_production_command(_beliefs(("store_food", True)), observation)
    assert type(stored).__name__ == "Store"
    assert stored.item_id == EntityId("food-1")


class _Provider:
    def __init__(self, recipe_id: str) -> None:
        self._recipe_id = recipe_id

    async def generate(self, request: object) -> object:
        from agents.cognition.production_selection import ProductionSelectionOutput

        output = ProductionSelectionOutput(recipe_id=self._recipe_id)
        return type("Result", (), {"output": output})()


@pytest.mark.asyncio
async def test_provider_may_choose_only_a_supported_recipe_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.production")
    beliefs = _beliefs(("craft_tool", True), ("harvest_wood", True))
    chosen = await select_production_recipe(
        beliefs,
        allow_provider=True,
        provider=_Provider("harvest_wood"),
        tick=1,
    )
    assert chosen.fallback_used is False
    assert chosen.recipe_id == RecipeId("harvest_wood")
    rejected = await select_production_recipe(
        beliefs,
        allow_provider=True,
        provider=_Provider("craft_gold"),
        tick=1,
    )
    assert rejected.fallback_used is True
    assert rejected.recipe_id is None
    assert "production_llm_rejected" in caplog.text
    assert "foreign_id" in caplog.text
    off = await select_production_recipe(
        beliefs, allow_provider=False, provider=_Provider("harvest_wood"), tick=1
    )
    assert off.recipe_id is None
    assert off.fallback_used is False
