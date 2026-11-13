# mypy: ignore-errors
"""Property bounds for committed-event possession and access extraction."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from analysis.economic_inequality_events import (
    harvest_economic_inequality_evidence,
)
from analysis.economic_inequality_policy import (
    EconomicInequalityAnalysisPolicy,
)
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

_WORLD = WorldId("world-economic-inequality-properties")


def _crafted(index: int, owner: str, tick: int) -> WorldEvent:
    details = ItemCrafted(
        recipe_id=RecipeId("craft"),
        created_item_id=EntityId(f"item-{index}"),
        resulting_holder_id=EntityId(owner),
        duration_ticks=1,
    )
    return WorldEvent(
        event_id=EventId(f"evt-{index}"),
        run_id="run-properties",
        world_id=_WORLD,
        tick=tick,
        sequence=index,
        request_id=RequestId(f"req-{index}"),
        resulting_revision=WorldRevision(tick),
        schema_version=6,
        details=details,
        actor_id=EntityId(owner),
        target_id=target_id_for_details(details),
        cause=ActionCause(RequestId(f"req-{index}"), EntityId(owner)),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-a")),
    )


@settings(max_examples=25, deadline=None)
@given(
    owners=st.lists(
        st.sampled_from(["body-a", "body-b", "body-c"]),
        min_size=0,
        max_size=12,
    ),
    ticks=st.lists(st.integers(min_value=0, max_value=200), min_size=0, max_size=12),
)
def test_rows_are_bounded_and_counts_are_consistent(
    owners: list[str], ticks: list[int]
) -> None:
    limit = min(len(owners), len(ticks))
    events = [_crafted(index, owners[index], ticks[index]) for index in range(limit)]
    harvest = harvest_economic_inequality_evidence(
        events, recipe_output_kinds={"craft": "tool"}
    )
    for row in harvest.possession_rows:
        assert row.observed_item_count >= 0
        assert row.observed_tool_count >= 0
        assert row.observed_tool_count <= row.observed_item_count
        assert row.unknown_kind_count >= 0
        assert row.window_index == row.tick // 32 or row.window_index == 0
    for row in harvest.access_rows:
        assert row.accessible_infrastructure_count >= 0
        assert row.accessible_storage_count >= 0
    assert harvest.owner_count <= len(set(owners))


def test_owner_cap_takes_a_deterministic_prefix() -> None:
    policy = EconomicInequalityAnalysisPolicy(max_owners=2)
    events = [
        _crafted(index, owner, tick=0)
        for index, owner in enumerate(("body-c", "body-a", "body-b"))
    ]
    harvest = harvest_economic_inequality_evidence(
        events, policy=policy, recipe_output_kinds={"craft": "tool"}
    )
    assert harvest.owner_count == 2
    assert len({row.owner_token for row in harvest.possession_rows}) == 2
    assert "economic_inequality_owners_truncated" in harvest.notices
