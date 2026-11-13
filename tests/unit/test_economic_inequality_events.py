# mypy: ignore-errors
"""Committed-event extraction of possession and access evidence."""

from __future__ import annotations

import pytest

from analysis.economic_inequality_contract import EconomicInequalityCoverage
from analysis.economic_inequality_events import (
    harvest_economic_inequality_evidence,
)
from world.effects import ActionCause
from world.events import (
    Given,
    InfrastructureConstructed,
    ItemCrafted,
    Moved,
    OccurrenceContext,
    StructureBuilt,
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

pytestmark = pytest.mark.unit

_WORLD = WorldId("world-economic-inequality")


def _event(
    details: object,
    *,
    tick: int = 0,
    sequence: int = 0,
    event_id: str = "evt-1",
    actor: str | None = "body-1",
    origin: str | None = "loc-a",
    schema: int = 6,
) -> WorldEvent:
    return WorldEvent(
        event_id=EventId(event_id),
        run_id="run-economic-inequality",
        world_id=_WORLD,
        tick=tick,
        sequence=sequence,
        request_id=RequestId(f"req-{event_id}"),
        resulting_revision=WorldRevision(tick),
        schema_version=schema,
        details=details,
        actor_id=None if actor is None else EntityId(actor),
        target_id=target_id_for_details(details),
        cause=ActionCause(RequestId(f"req-{event_id}"), EntityId(actor or "body-1")),
        occurrence=(
            None
            if origin is None
            else OccurrenceContext(origin_location_id=EntityId(origin))
        ),
    )


def _crafted(
    item: str,
    recipe: str,
    *,
    tick: int,
    holder: str = "body-1",
    event_id: str | None = None,
) -> WorldEvent:
    return _event(
        ItemCrafted(
            recipe_id=RecipeId(recipe),
            created_item_id=EntityId(item),
            resulting_holder_id=EntityId(holder),
            duration_ticks=1,
        ),
        tick=tick,
        event_id=event_id or f"evt-{item}",
        actor=holder,
    )


def test_possession_tool_storage_and_infrastructure_are_measured() -> None:
    events = [
        _crafted("item-tool", "craft_tool", tick=0),
        _crafted("item-food", "craft_food", tick=1),
        _event(
            StructureBuilt(
                recipe_id=RecipeId("build_store"),
                structure_id=EntityId("structure-store"),
                location_id=EntityId("loc-a"),
                resulting_integrity=1.0,
                duration_ticks=1,
                consumed_item_id=EntityId("item-material"),
            ),
            tick=2,
            event_id="evt-store",
        ),
        _event(
            InfrastructureConstructed(
                asset_id=EntityId("infra-road"),
                asset_kind="road",
                topology="edge",
                status="operational",
                integrity=1.0,
                location_id=EntityId("loc-a"),
                endpoint_location_id=EntityId("loc-b"),
                linked_structure_id=None,
                linked_project_id=EntityId("project-road"),
                tick=3,
            ),
            tick=3,
            event_id="evt-road",
            schema=23,
        ),
        _event(
            Given(
                recipient_id=EntityId("body-2"),
                item_id=EntityId("item-tool"),
                resulting_holder_id=EntityId("body-2"),
            ),
            tick=4,
            event_id="evt-gift",
        ),
    ]
    harvest = harvest_economic_inequality_evidence(
        events,
        recipe_output_kinds={"craft_tool": "tool", "craft_food": "food"},
        recipe_structure_kinds={"build_store": "store"},
    )
    assert harvest.owner_count == 2
    assert len(harvest.possession_rows) == 2
    body_one = harvest.possession_rows[0]
    body_two = harvest.possession_rows[1]
    assert body_one.owner_token != body_two.owner_token
    counts = {
        row.owner_token: (row.observed_item_count, row.observed_tool_count)
        for row in harvest.possession_rows
    }
    assert sorted(counts.values()) == [(1, 0), (1, 1)]
    assert {row.window_index for row in harvest.possession_rows} == {0}

    access = {row.owner_token: row for row in harvest.access_rows}
    located = [row for row in access.values() if row.location_known]
    unlocated = [row for row in access.values() if not row.location_known]
    assert len(located) == 1
    assert located[0].accessible_infrastructure_count == 1
    assert located[0].accessible_storage_count == 1
    assert len(unlocated) == 1
    assert harvest.missing_location_count == 1
    assert harvest.coverage is EconomicInequalityCoverage.PARTIAL
    assert "economic_inequality_missing_location" in harvest.notices


def test_unknown_recipe_output_kind_is_explicit() -> None:
    harvest = harvest_economic_inequality_evidence(
        [_crafted("item-unknown", "mystery_recipe", tick=0)]
    )
    assert harvest.unknown_kind_count == 1
    assert harvest.possession_rows[0].observed_tool_count == 0
    assert "economic_inequality_unknown_item_kind" in harvest.notices


def test_window_snapshots_are_longitudinal() -> None:
    events = [
        _crafted("item-first", "craft", tick=0),
        _event(
            Moved(
                destination_id=EntityId("loc-b"),
                resulting_location_id=EntityId("loc-b"),
                fatigue_delta=0.0,
                resulting_fatigue=0.0,
            ),
            tick=40,
            event_id="evt-move",
        ),
    ]
    harvest = harvest_economic_inequality_evidence(
        events, recipe_output_kinds={"craft": "generic"}
    )
    assert {row.window_index for row in harvest.possession_rows} == {0, 1}
    first = next(
        row for row in harvest.access_rows if row.window_index == 0
    )
    second = next(
        row for row in harvest.access_rows if row.window_index == 1
    )
    assert first.location_known is True
    assert second.location_known is True


def test_empty_event_stream_is_empty_not_zero_filled() -> None:
    harvest = harvest_economic_inequality_evidence([])
    assert harvest.possession_rows == ()
    assert harvest.access_rows == ()
    assert harvest.owner_count == 0


def test_non_world_event_input_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid_input"):
        harvest_economic_inequality_evidence([object()])  # type: ignore[list-item]
