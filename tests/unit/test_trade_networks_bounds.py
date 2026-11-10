# mypy: ignore-errors
"""Trade-network caps, truncation, and bounded rows."""

from __future__ import annotations

from types import SimpleNamespace

from hypothesis import given
from hypothesis import strategies as st

from analysis.trade_networks_analysis import harvest_trade_networks_analysis
from analysis.trade_networks_contract import TradeCoverage
from analysis.trade_networks_policy import default_trade_networks_analysis_policy
from world.events import Given, ItemCrafted
from world.identifiers import EntityId, EventId, RecipeId

POLICY = default_trade_networks_analysis_policy()


def _event(token: str, details: object, *, tick: int, origin: str):
    return SimpleNamespace(
        event_id=EventId(token),
        tick=tick,
        sequence=0,
        actor_id=EntityId("body-a"),
        details=details,
        occurrence=SimpleNamespace(origin_location_id=EntityId(origin)),
    )


def _events(count: int, *, tick: int = 0):
    events = []
    for ordinal in range(count):
        origin = f"loc-{ordinal * 2}"
        destination = f"loc-{ordinal * 2 + 1}"
        events.append(
            _event(
                f"evt-c-{ordinal}",
                ItemCrafted(
                    recipe_id=RecipeId("cook_food"),
                    created_item_id=EntityId(f"item-{ordinal}"),
                    resulting_holder_id=EntityId("body-a"),
                    duration_ticks=1,
                ),
                tick=tick,
                origin=origin,
            )
        )
        events.append(
            _event(
                f"evt-g-{ordinal}",
                Given(
                    recipient_id=EntityId(f"body-{ordinal + 2}"),
                    item_id=EntityId(f"item-{ordinal}"),
                ),
                tick=tick + 1,
                origin=destination,
            )
        )
    return events


def test_each_cap_truncates_and_notices() -> None:
    policy = type(POLICY)(
        max_transfer_rows=3,
        max_corridors=2,
        max_networks=1,
        max_locations=2,
        max_lineage_edges=1,
    )
    analysis = harvest_trade_networks_analysis(
        events=_events(8),
        policy=policy,
        recipe_item_kinds={"cook_food": "food"},
    )
    assert analysis.transfer_count <= 3
    assert analysis.corridor_count <= 2
    assert analysis.network_count <= 1
    assert len(analysis.locations) <= 2
    assert len(analysis.lineage) <= 1
    assert "trade_networks_transfer_truncated" in analysis.notices
    assert "trade_networks_corridor_truncated" in analysis.notices
    assert "trade_networks_network_truncated" in analysis.notices
    assert "trade_networks_location_truncated" in analysis.notices
    assert analysis.coverage is TradeCoverage.PARTIAL


def test_rows_are_sorted_after_truncation() -> None:
    policy = type(POLICY)(max_corridors=3)
    analysis = harvest_trade_networks_analysis(
        events=_events(10),
        policy=policy,
        recipe_item_kinds={"cook_food": "food"},
    )
    keys = [(row.window_index, row.corridor_token) for row in analysis.corridors]
    assert keys == sorted(keys)


tick_strategy = st.integers(min_value=0, max_value=200)


@given(count=st.integers(min_value=0, max_value=12), tick=tick_strategy)
def test_analysis_rows_never_exceed_declared_caps(count: int, tick: int) -> None:
    policy = type(POLICY)(
        max_transfer_rows=4,
        max_corridors=3,
        max_networks=2,
        max_locations=3,
        max_lineage_edges=2,
    )
    analysis = harvest_trade_networks_analysis(
        events=_events(count, tick=tick),
        policy=policy,
        recipe_item_kinds={"cook_food": "food"},
    )
    assert analysis.transfer_count <= 4
    assert analysis.corridor_count <= 3
    assert analysis.network_count <= 2
    assert len(analysis.locations) <= 3
    assert len(analysis.lineage) <= 2
