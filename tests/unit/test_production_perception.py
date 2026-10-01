"""Structures and recipe ids are visible facts, not a recipe table."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from tests.physical_helpers import (
    PhysicalWorldFixture,
    physical_config,
    two_location_fixture,
)
from tests.simulation_helpers import alive_body, make_item
from world.actions import Build, Wait
from world.identifiers import EntityId, RecipeId
from world.production import StructureKind, example_production_catalog
from world.values import ItemKind, UnitInterval

pytestmark = pytest.mark.unit

_SHELTER = RecipeId("build_shelter")


def _world(*, visible: bool = True) -> PhysicalWorldFixture:
    base = two_location_fixture(item_on_ground=False)
    locations = base.locations
    if not visible:
        locations = tuple(
            replace(location, visibility_factor=UnitInterval(0.0))
            for location in base.locations
        )
    material = make_item(
        "mat-1",
        name="wood",
        kind=ItemKind.MATERIAL,
        location_id=None,
        holder_id="body-1",
    )
    return PhysicalWorldFixture(
        world_id=base.world_id,
        locations=locations,
        bodies=(
            alive_body("body-1", inventory=(EntityId("mat-1"),)),
            alive_body("body-2"),
        ),
        items=(material,),
        resources=base.resources,
        weather=base.weather,
        registrations=base.registrations,
    )


def _engine(fixture: PhysicalWorldFixture) -> WorldEngine:
    return WorldEngine(
        config=physical_config(1),
        bootstrap=fixture.as_bootstrap(),
        production_catalog=example_production_catalog(),
    )


def _act(engine: WorldEngine, agent: str, command: object):
    batch = engine.observe()
    return engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId(agent), command),)  # type: ignore[arg-type]
    )


def test_visible_shelter_and_recipe_id_reach_actor_and_bystander(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _engine(_world())
    _act(engine, "agent-1", Build(_SHELTER))
    with caplog.at_level(logging.DEBUG, logger="world._perception"):
        batch = engine.observe()
    actor = batch.for_observer(EntityId("body-1"))
    bystander = batch.for_observer(EntityId("body-2"))
    assert not hasattr(actor, "recipes")
    assert len(actor.structures) == 1
    seen = actor.structures[0]
    assert seen.location_id == EntityId("loc-1")
    assert seen.kind is StructureKind.SHELTER
    assert seen.integrity == 0.75
    assert seen.stored_quantity == 0
    assert bystander.structures == actor.structures
    produced = [
        occurrence
        for occurrence in actor.occurrences
        if occurrence.kind == "structure_built"
    ]
    assert len(produced) == 1
    assert produced[0].public_facts["recipe_id"] == "build_shelter"
    assert "duration_ticks" not in produced[0].public_facts
    assert "success_probability" not in produced[0].public_facts
    heard = [
        occurrence
        for occurrence in bystander.occurrences
        if occurrence.kind == "structure_built"
    ]
    assert heard[0].public_facts["recipe_id"] == "build_shelter"
    assert "actor_id" not in heard[0].public_facts
    assert "production_observed" in caplog.text
    assert "recipe_id=build_shelter" in caplog.text
    assert "structure_count=1" in caplog.text


def test_low_visibility_hides_structures_but_the_actor_keeps_the_recipe() -> None:
    engine = _engine(_world(visible=False))
    _act(engine, "agent-1", Build(_SHELTER))
    batch = engine.observe()
    actor = batch.for_observer(EntityId("body-1"))
    bystander = batch.for_observer(EntityId("body-2"))
    assert actor.structures == ()
    assert bystander.structures == ()
    actor_facts = [
        occurrence.public_facts
        for occurrence in actor.occurrences
        if occurrence.kind == "structure_built"
    ]
    assert actor_facts[0]["recipe_id"] == "build_shelter"
    assert not any(
        occurrence.kind == "structure_built" for occurrence in bystander.occurrences
    )


def test_non_production_facts_omit_recipe_id() -> None:
    engine = _engine(_world())
    _act(engine, "agent-1", Wait())
    batch = engine.observe()
    actor = batch.for_observer(EntityId("body-1"))
    waited = next(item for item in actor.occurrences if item.kind == "wait")
    assert "recipe_id" not in waited.public_facts
    assert waited.public_facts["kind"] == "wait"
