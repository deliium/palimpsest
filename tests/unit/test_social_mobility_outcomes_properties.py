# mypy: ignore-errors
"""Hypothesis properties for observed social-mobility outcomes."""

from __future__ import annotations

from types import SimpleNamespace

from hypothesis import given, settings
from hypothesis import strategies as st

from analysis.social_mobility_contract import (
    SocialMobilityDomain,
    build_social_mobility_identity_map,
    social_mobility_measures_for,
)
from analysis.social_mobility_outcomes import harvest_social_mobility_outcomes
from world.effects import ActionCause
from world.events import (
    ItemCrafted,
    OccurrenceContext,
    WorldEvent,
    target_id_for_details,
)
from world.identifiers import (
    EntityId,
    EventId,
    RecipeId,
    RequestId,
    WorldId,
    WorldRevision,
)

_WORLD = WorldId("world-social-mobility-outcome-properties")


def _crafted(item: str, recipe: str, *, tick: int, sequence: int) -> WorldEvent:
    details = ItemCrafted(
        recipe_id=RecipeId(recipe),
        created_item_id=EntityId(item),
        resulting_holder_id=EntityId("entity:a"),
        duration_ticks=1,
    )
    return WorldEvent(
        event_id=EventId(f"evt-{tick}-{sequence}"),
        run_id="run-social-mobility",
        world_id=_WORLD,
        tick=tick,
        sequence=sequence,
        request_id=RequestId(f"req-{tick}-{sequence}"),
        resulting_revision=WorldRevision(tick * 100 + sequence),
        schema_version=22,
        details=details,
        actor_id=EntityId("entity:a"),
        target_id=target_id_for_details(details),
        cause=ActionCause(RequestId(f"req-{tick}-{sequence}"), EntityId("entity:a")),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc:a")),
    )


def _identity():
    return build_social_mobility_identity_map(
        runner_config=SimpleNamespace(
            agents=(
                SimpleNamespace(agent_id="agent:a", entity_id=EntityId("entity:a")),
            )
        ),
        events=(),
    )


@settings(max_examples=30, deadline=None)
@given(
    tools=st.integers(min_value=0, max_value=5),
    food=st.integers(min_value=0, max_value=5),
    audits=st.integers(min_value=0, max_value=4),
)
def test_quantities_are_non_negative_and_ordered(
    tools: int, food: int, audits: int
) -> None:
    events = tuple(
        _crafted(f"item-tool-{index}", "craft_tool", tick=index, sequence=index)
        for index in range(tools)
    ) + tuple(
        _crafted(
            f"item-food-{index}",
            "craft_food",
            tick=tools + index,
            sequence=tools + index,
        )
        for index in range(food)
    )
    knowledge = tuple(
        SimpleNamespace(
            owner_id=SimpleNamespace(value="agent:a"),
            active=True,
            content_key=f"technique:{index}",
            acquired_tick=index,
        )
        for index in range(audits)
    )
    harvest = harvest_social_mobility_outcomes(
        events,
        identity_map=_identity(),
        practical_knowledge_audits=knowledge,
        recipe_output_kinds={"craft_tool": "tool", "craft_food": "food"},
    )
    second = harvest_social_mobility_outcomes(
        events,
        identity_map=_identity(),
        practical_knowledge_audits=knowledge,
        recipe_output_kinds={"craft_tool": "tool", "craft_food": "food"},
    )
    assert harvest == second
    assert harvest.rows == tuple(
        sorted(
            harvest.rows,
            key=lambda row: (row.window_index, row.domain.value, row.owner_token),
        )
    )
    for row in harvest.rows:
        assert row.quantity >= 0
        assert social_mobility_measures_for(row.domain) == (row.measure,)
        assert row.domain in set(SocialMobilityDomain)
