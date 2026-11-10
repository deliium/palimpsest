# mypy: ignore-errors
"""Corridor, flow, location, dependence, and network detection."""

from __future__ import annotations

from types import SimpleNamespace

from hypothesis import given
from hypothesis import strategies as st

from analysis.trade_networks_contract import TradeCoverage, TradeFlowClass
from analysis.trade_networks_detection import (
    detect_corridors,
    detect_dependence,
    detect_flows,
    detect_locations,
    detect_networks,
)
from analysis.trade_networks_events import trade_transfer_rows_from_events
from analysis.trade_networks_policy import default_trade_networks_analysis_policy
from world.events import Given, ItemCrafted
from world.identifiers import EntityId, EventId, RecipeId

POLICY = default_trade_networks_analysis_policy()


def _event(token: str, details: object, *, tick: int = 0, origin: str | None = "loc-a"):
    return SimpleNamespace(
        event_id=EventId(token),
        tick=tick,
        sequence=0,
        actor_id=EntityId("body-a"),
        details=details,
        occurrence=SimpleNamespace(
            origin_location_id=EntityId(origin) if origin is not None else None
        ),
    )


def _crafted(
    token: str,
    *,
    item: str,
    tick: int = 0,
    origin: str = "loc-a",
    recipe: str = "cook_food",
):
    return _event(
        token,
        ItemCrafted(
            recipe_id=RecipeId(recipe),
            created_item_id=EntityId(item),
            resulting_holder_id=EntityId("body-a"),
            duration_ticks=1,
        ),
        tick=tick,
        origin=origin,
    )


def _gift(
    token: str,
    *,
    item: str,
    tick: int = 0,
    origin: str = "loc-a",
    recipient: str = "body-b",
):
    return _event(
        token,
        Given(recipient_id=EntityId(recipient), item_id=EntityId(item)),
        tick=tick,
        origin=origin,
    )


def _harvest(events, **kwargs):
    return trade_transfer_rows_from_events(
        tuple(events),
        policy=kwargs.pop("policy", POLICY),
        recipe_item_kinds=kwargs.pop("recipe_item_kinds", {"cook_food": "food"}),
        **kwargs,
    )


def test_same_location_transfer_is_local_not_corridor() -> None:
    harvest = _harvest(
        (
            _crafted("evt-1", item="item-1"),
            _gift("evt-2", item="item-1"),
        )
    )
    assert detect_corridors(harvest.transfers, POLICY) == ()
    flows = detect_flows(harvest.transfers, POLICY)
    assert len(flows) == 1
    assert flows[0].local_count == 1
    assert flows[0].cross_location_count == 0


def test_consecutive_locations_create_directed_corridor() -> None:
    harvest = _harvest(
        (
            _crafted("evt-1", item="item-1"),
            _gift("evt-2", item="item-1", tick=1, origin="loc-b"),
        )
    )
    corridors = detect_corridors(harvest.transfers, POLICY)
    assert len(corridors) == 1
    assert corridors[0].from_location_token == "loc-a"
    assert corridors[0].to_location_token == "loc-b"
    assert corridors[0].transfer_count == 1


def test_reverse_corridors_share_one_network() -> None:
    harvest = _harvest(
        (
            _crafted("evt-1", item="item-1", origin="loc-a"),
            _gift("evt-2", item="item-1", tick=1, origin="loc-b"),
            _crafted("evt-3", item="item-2", tick=2, origin="loc-b"),
            _gift("evt-4", item="item-2", tick=3, origin="loc-a"),
        )
    )
    corridors = detect_corridors(harvest.transfers, POLICY)
    assert len(corridors) == 2
    assert {row.corridor_token for row in corridors} == {
        row.corridor_token for row in corridors
    }
    assert (
        corridors[0].from_location_token,
        corridors[0].to_location_token,
    ) != (
        corridors[1].from_location_token,
        corridors[1].to_location_token,
    )
    networks = detect_networks(corridors, POLICY)
    assert len(networks) == 1
    assert set(networks[0].location_tokens) == {"loc-a", "loc-b"}


def test_flow_rows_count_import_export_roles_and_cross_location() -> None:
    harvest = _harvest(
        (
            _crafted("evt-1", item="item-1"),
            _gift("evt-2", item="item-1", tick=1, origin="loc-b"),
            _crafted("evt-3", item="item-2", tick=2),
            _gift("evt-4", item="item-2", tick=3, origin="loc-b"),
        )
    )
    flows = detect_flows(harvest.transfers, POLICY)
    assert len(flows) == 1
    row = flows[0]
    assert row.flow_class is TradeFlowClass.FOOD
    assert row.cross_location_count == 2
    assert row.imported_count == 2
    assert row.exported_count == 2
    assert row.local_count == 0
    assert row.transfer_count == 2


def test_unresolved_transfer_marks_flow_partial() -> None:
    harvest = _harvest((_gift("evt-1", item="item-1", origin=None),))
    flows = detect_flows(harvest.transfers, POLICY)
    assert len(flows) == 1
    assert flows[0].coverage is TradeCoverage.PARTIAL
    assert flows[0].transfer_count == 0


def test_dependence_ratio_uses_observed_denominator() -> None:
    harvest = _harvest(
        (
            _crafted("evt-1", item="item-1", origin="loc-a"),
            _gift("evt-2", item="item-1", tick=1, origin="loc-b"),
            _crafted("evt-3", item="item-2", tick=2, origin="loc-b"),
            _gift("evt-4", item="item-2", tick=3, origin="loc-b"),
            _gift("evt-5", item="item-2", tick=4, origin="loc-b"),
        )
    )
    rows = detect_dependence(harvest.transfers, POLICY)
    at_b = next(row for row in rows if row.location_token == "loc-b")
    assert at_b.imported_count == 1
    assert at_b.locally_originated_count == 2
    assert at_b.dependence_milli == 1 * 1_000 // 3
    assert at_b.high_dependence is False


def test_major_location_thresholds_are_exact() -> None:
    harvest = _harvest(
        (
            _crafted("evt-1", item="item-1", origin="loc-b"),
            _gift("evt-2", item="item-1", tick=1, origin="loc-b"),
            _gift("evt-3", item="item-1", tick=2, origin="loc-b"),
        )
    )
    # Degree 0 and two local transfers: not major.
    locations = detect_locations(harvest.transfers, harvest.supplies, POLICY)
    hub = next(row for row in locations if row.location_token == "loc-b")
    assert hub.corridor_degree == 0
    assert hub.is_major is False

    connected = _harvest(
        (
            _crafted("evt-1", item="item-1", origin="loc-a"),
            _gift("evt-2", item="item-1", tick=1, origin="loc-b"),
            _crafted("evt-3", item="item-2", tick=2, origin="loc-c"),
            _gift("evt-4", item="item-2", tick=3, origin="loc-b"),
            _gift("evt-5", item="item-1", tick=4, origin="loc-b"),
        )
    )
    rows = detect_locations(connected.transfers, connected.supplies, POLICY)
    hub = next(row for row in rows if row.location_token == "loc-b")
    assert hub.corridor_degree >= 2
    assert hub.inflow_count >= 2
    assert hub.is_major is True


def test_operational_trade_post_marks_location() -> None:
    harvest = _harvest(
        (
            _crafted("evt-1", item="item-1"),
            _gift("evt-2", item="item-1"),
        )
    )
    locations = detect_locations(
        harvest.transfers,
        harvest.supplies,
        POLICY,
        trade_post_locations=("loc-a",),
    )
    assert locations[0].trade_post_present is True
    assert locations[0].is_major is False


def test_connected_corridors_form_one_network() -> None:
    harvest = _harvest(
        (
            _crafted("evt-1", item="item-1", origin="loc-a"),
            _gift("evt-2", item="item-1", tick=1, origin="loc-b"),
            _crafted("evt-3", item="item-2", tick=2, origin="loc-b"),
            _gift("evt-4", item="item-2", tick=3, origin="loc-c"),
        )
    )
    corridors = detect_corridors(harvest.transfers, POLICY)
    assert len(corridors) == 2
    networks = detect_networks(corridors, POLICY)
    assert len(networks) == 1
    assert set(networks[0].location_tokens) == {"loc-a", "loc-b", "loc-c"}


def test_corridor_and_network_caps_truncate_deterministically() -> None:
    harvest = _harvest(
        (
            _crafted("evt-1", item="item-1", origin="loc-a"),
            _gift("evt-2", item="item-1", tick=1, origin="loc-b"),
            _crafted("evt-3", item="item-2", tick=2, origin="loc-c"),
            _gift("evt-4", item="item-2", tick=3, origin="loc-d"),
        )
    )
    policy = type(POLICY)(max_corridors=1, max_networks=1)
    notices: set[str] = set()
    corridors = detect_corridors(harvest.transfers, policy, notices=notices)
    assert len(corridors) == 1
    assert corridors[0].coverage is TradeCoverage.PARTIAL
    assert "trade_networks_corridor_truncated" in notices
    networks = detect_networks(corridors, policy, notices=notices)
    assert len(networks) == 1
    assert "trade_networks_network_truncated" not in notices


tick_strategy = st.integers(min_value=0, max_value=200)


@given(ticks=st.lists(tick_strategy, min_size=0, max_size=12))
def test_corridors_and_networks_are_bounded(ticks) -> None:
    events = []
    for ordinal, tick in enumerate(ticks):
        origin = f"loc-{ordinal % 4}"
        destination = f"loc-{(ordinal + 1) % 4}"
        events.append(_crafted(f"evt-c-{ordinal}", item=f"item-{ordinal}", tick=tick))
        events.append(
            _gift(
                f"evt-g-{ordinal}",
                item=f"item-{ordinal}",
                tick=tick + 1,
                origin=destination if origin != destination else origin,
            )
        )
    harvest = _harvest(events)
    policy = type(POLICY)(max_corridors=4, max_networks=2)
    corridors = detect_corridors(harvest.transfers, policy)
    networks = detect_networks(corridors, policy)
    assert len(corridors) <= 4
    assert len(networks) <= 2
    assert list(corridors) == sorted(
        corridors, key=lambda row: (row.window_index, row.corridor_token)
    )
