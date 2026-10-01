"""Observer projection of production stays coordinate-free."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from observer.adapt import adapt_events
from observer.contracts import ObserverEvent, ObserverWorldState
from observer.layout import catalog_from_mapping
from observer.project import project_frame
from observer.version import OBSERVER_PROTOCOL_VERSION
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from simulation.observer_facts import ObjectiveFacts, scene_from_facts
from tests.physical_helpers import (
    PhysicalWorldFixture,
    physical_config,
    two_location_fixture,
)
from tests.simulation_helpers import alive_body, make_item, make_resource
from world.actions import Build, Craft, Harvest, Repair, Store, Wait
from world.identifiers import EntityId, RecipeId
from world.production import example_production_catalog
from world.values import ItemKind, ResourceKind

pytestmark = pytest.mark.unit

_FORBIDDEN = frozenset(
    {"screen_x", "screen_y", "pixels", "sprite", "animation", "dx", "dy"}
)
_LAYOUT = catalog_from_mapping(
    {
        "schema_version": "observer-layout-v1",
        "layout_id": "production-empty",
        "locations": [],
    }
)


def _names(value: object) -> set[str]:
    slots = getattr(type(value), "__slots__", ())
    return {str(item) for item in slots}


def test_production_projection_has_no_coordinates() -> None:
    catalog = example_production_catalog()
    base = two_location_fixture(item_on_ground=False)
    fixture = PhysicalWorldFixture(
        world_id=base.world_id,
        locations=base.locations,
        bodies=(
            alive_body(
                "body-1",
                inventory=(
                    EntityId("wood-1"),
                    EntityId("stone-1"),
                    EntityId("mat-1"),
                    EntityId("mat-2"),
                    EntityId("food-1"),
                ),
            ),
            alive_body("body-2"),
        ),
        items=(
            make_item(
                "wood-1",
                name="wood",
                kind=ItemKind.MATERIAL,
                location_id=None,
                holder_id="body-1",
            ),
            make_item(
                "stone-1",
                name="stone",
                kind=ItemKind.MATERIAL,
                location_id=None,
                holder_id="body-1",
            ),
            make_item(
                "mat-1",
                name="plank",
                kind=ItemKind.MATERIAL,
                location_id=None,
                holder_id="body-1",
            ),
            make_item(
                "mat-2",
                name="plank",
                kind=ItemKind.MATERIAL,
                location_id=None,
                holder_id="body-1",
            ),
            make_item(
                "food-1",
                name="ration",
                kind=ItemKind.FOOD,
                location_id=None,
                holder_id="body-1",
            ),
        ),
        resources=(
            make_resource(
                "res-wood",
                name="wood",
                kind=ResourceKind.MATERIAL,
                location_id="loc-1",
                quantity=2.0,
                maximum_quantity=5.0,
                regeneration_per_tick=0.0,
            ),
        ),
        weather=base.weather,
        registrations=base.registrations,
    )
    commands = (
        Harvest(RecipeId("harvest_wood"), EntityId("res-wood")),
        Craft(RecipeId("craft_tool")),
        Wait(),
        Build(RecipeId("build_shelter")),
        None,
        Store(RecipeId("store_food"), EntityId("food-1")),
    )
    engine: WorldEngine | None = None
    for seed in range(1, 40):
        candidate = WorldEngine(
            config=physical_config(seed),
            bootstrap=fixture.as_bootstrap(),
            production_catalog=catalog,
        )
        repair_id: EntityId | None = None
        for command in commands:
            if command is None:
                repair_id = next(iter(candidate._snapshot.world.state.structures))
                command = Repair(RecipeId("repair_shelter"), repair_id)
            batch = candidate.observe()
            candidate.resolve_tick(
                (ActionSubmission(batch.token, AgentId("agent-1"), command),)
            )
        kinds = {event.details.kind for event in candidate._snapshot.event_history}
        if {
            "resource_harvested",
            "craft_started",
            "item_crafted",
            "structure_built",
            "structure_repaired",
            "item_stored",
        } <= kinds:
            engine = candidate
            break
    assert engine is not None
    state = engine._snapshot.world.state
    for event in engine._snapshot.event_history:
        assert _names(event).isdisjoint(_FORBIDDEN)
        assert _names(event.details).isdisjoint(_FORBIDDEN)
    assert _names(state).isdisjoint(_FORBIDDEN)
    facts = ObjectiveFacts(
        run_id=engine.run_id.value,
        world_id=engine.world_id.value,
        tick=engine._snapshot.tick.value,
        revision=engine._snapshot.world.state.revision.value,
        locations=tuple(state.locations.values()),
        bodies=tuple(state.bodies.values()),
        items=tuple(state.items.values()),
        resources=tuple(state.resources.values()),
        weather=tuple(state.weather.values()),
        registrations=engine._registrations,
        structures=tuple(state.structures.values()),
    )
    frame = project_frame(
        scene_from_facts(facts),
        _LAYOUT,
        mode="live",
        events=adapt_events(engine._snapshot.event_history),
    )
    assert frame.protocol_version == OBSERVER_PROTOCOL_VERSION
    semantic = {event.type for event in frame.events or ()}
    assert {
        "RESOURCE_HARVESTED",
        "CRAFT_STARTED",
        "ITEM_CRAFTED",
        "STRUCTURE_BUILT",
        "STRUCTURE_REPAIRED",
        "ITEM_STORED",
    } <= semantic
    assert {item.location_id for item in frame.world.structures} == {"loc-1"}
    assert all(
        item.presentation is not None
        and item.presentation.icon_key == item.kind
        for item in frame.world.structures
    )
    wood = next(item for item in frame.world.resources if item.name == "wood")
    assert wood.presentation is not None
    assert wood.presentation.icon_key == "wood"
    empty = ObserverWorldState(tick=0, revision=0)
    assert empty.structures == ()
    moved = ObserverEvent(
        protocol_version=OBSERVER_PROTOCOL_VERSION,
        type="AGENT_WAITED",
        domain_kind="wait",
        event_id="evt-wait",
        tick=0,
        sequence=0,
    )
    mapping = moved.public_mapping()
    assert "recipe_id" not in mapping
    assert "structure_id" not in mapping
