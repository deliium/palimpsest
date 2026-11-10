# mypy: ignore-errors
"""Committed-event extraction of trade transfers and local supply."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from analysis.trade_networks_contract import NONE_TOKEN, TradeCoverage, TradeFlowClass
from analysis.trade_networks_events import trade_transfer_rows_from_events
from analysis.trade_networks_policy import default_trade_networks_analysis_policy
from world.artifacts import ArtifactKind
from world.events import (
    ArtifactCopied,
    ArtifactCreated,
    ArtifactMoved,
    Eaten,
    ExchangeCompleted,
    Given,
    ItemCrafted,
)
from world.identifiers import EntityId, EventId, RecipeId

POLICY = default_trade_networks_analysis_policy()


def _event(
    token: str,
    details: object,
    *,
    tick: int = 0,
    sequence: int = 0,
    actor: str | None = "body-a",
    origin: str | None = "loc-a",
):
    return SimpleNamespace(
        event_id=EventId(token),
        tick=tick,
        sequence=sequence,
        actor_id=None if actor is None else EntityId(actor),
        details=details,
        occurrence=SimpleNamespace(
            origin_location_id=None if origin is None else EntityId(origin)
        ),
    )


def _exchange(
    token: str,
    *,
    tick: int = 0,
    actor: str = "body-a",
    other: str = "body-b",
    give: tuple[tuple[str, str], ...] = (("item-give", "food"),),
    take: tuple[tuple[str, str], ...] = (("item-take", "material"),),
    origin: str = "loc-a",
):
    return _event(
        token,
        ExchangeCompleted(
            actor_id=EntityId(actor),
            counterparty_id=EntityId(other),
            act="accept",
            give_item_ids=tuple(EntityId(item) for item, _ in give),
            take_item_ids=tuple(EntityId(item) for item, _ in take),
            give_item_kinds=tuple(kind for _, kind in give),
            take_item_kinds=tuple(kind for _, kind in take),
        ),
        tick=tick,
        origin=origin,
        actor=actor,
    )


def _gift(
    token: str,
    *,
    item: str = "item-1",
    recipient: str = "body-b",
    tick: int = 0,
    actor: str = "body-a",
    origin: str | None = "loc-a",
):
    return _event(
        token,
        Given(recipient_id=EntityId(recipient), item_id=EntityId(item)),
        tick=tick,
        origin=origin,
        actor=actor,
    )


def test_exchange_creates_two_sided_transfer_rows() -> None:
    harvest = trade_transfer_rows_from_events((_exchange("evt-1"),), policy=POLICY)
    assert harvest.transfer_count == 2
    give = next(row for row in harvest.transfers if row.direction == "give")
    take = next(row for row in harvest.transfers if row.direction == "take")
    assert give.entity_token == "item-give"
    assert give.flow_class is TradeFlowClass.FOOD
    assert give.actor_token == "body-a"
    assert give.counterparty_token == "body-b"
    assert take.entity_token == "item-take"
    assert take.flow_class is TradeFlowClass.MATERIALS
    assert take.actor_token == "body-b"
    assert take.counterparty_token == "body-a"
    assert harvest.coverage is TradeCoverage.PARTIAL
    assert "trade_networks_unresolved_item_origin" in harvest.notices


def test_given_uses_unknown_kind_fallback() -> None:
    harvest = trade_transfer_rows_from_events((_gift("evt-1"),), policy=POLICY)
    assert harvest.transfer_count == 1
    assert harvest.transfers[0].flow_class is TradeFlowClass.OTHER
    assert "trade_networks_unknown_item_kind" in harvest.notices


def test_gift_of_crafted_food_uses_recipe_kind() -> None:
    crafted = _event(
        "evt-0",
        ItemCrafted(
            recipe_id=RecipeId("cook_food"),
            created_item_id=EntityId("item-1"),
            resulting_holder_id=EntityId("body-a"),
            duration_ticks=1,
        ),
    )
    harvest = trade_transfer_rows_from_events(
        (crafted, _gift("evt-1")),
        policy=POLICY,
        recipe_item_kinds={"cook_food": "food"},
    )
    assert harvest.transfers[0].flow_class is TradeFlowClass.FOOD
    assert any(row.source_kind == "craft" for row in harvest.supplies)


def test_item_kind_by_id_overrides_recipe_fallback() -> None:
    crafted = _event(
        "evt-0",
        ItemCrafted(
            recipe_id=RecipeId("cook_food"),
            created_item_id=EntityId("item-1"),
            resulting_holder_id=EntityId("body-a"),
            duration_ticks=1,
        ),
    )
    harvest = trade_transfer_rows_from_events(
        (crafted, _gift("evt-1")),
        policy=POLICY,
        recipe_item_kinds={"cook_food": "food"},
        item_kind_by_id={"item-1": "material"},
    )
    assert harvest.transfers[0].flow_class is TradeFlowClass.MATERIALS


def test_item_trajectory_previous_location_is_consecutive() -> None:
    first = _exchange("evt-1", give=(("item-1", "food"),), take=(("item-x", "food"),))
    second = _gift("evt-2", item="item-1", tick=1, origin="loc-b")
    harvest = trade_transfer_rows_from_events((first, second), policy=POLICY)
    gift = next(row for row in harvest.transfers if row.source_kind == "gift")
    assert gift.previous_location_token == "loc-a"
    assert gift.location_token == "loc-b"


def test_artifact_move_and_copy_are_record_flows() -> None:
    created = _event(
        "evt-1",
        ArtifactCreated(
            artifact_id=EntityId("art-1"),
            artifact_kind=ArtifactKind.NOTE,
            author_id=EntityId("body-a"),
            content_revision=1,
            resulting_location_id=EntityId("loc-a"),
        ),
        origin="loc-a",
    )
    moved = _event(
        "evt-2",
        ArtifactMoved(
            artifact_id=EntityId("art-1"),
            artifact_kind=ArtifactKind.NOTE,
            content_revision=2,
            resulting_location_id=EntityId("loc-b"),
        ),
        tick=1,
        origin="loc-b",
    )
    copied = _event(
        "evt-3",
        ArtifactCopied(
            child_artifact_id=EntityId("art-2"),
            parent_artifact_id=EntityId("art-1"),
            source_artifact_id=EntityId("art-1"),
            fidelity_mode="faithful",
            copy_generation=0,
            content_revision=1,
            record_genre="note",
        ),
        tick=2,
        origin="loc-b",
    )
    harvest = trade_transfer_rows_from_events((created, moved, copied), policy=POLICY)
    records = [row for row in harvest.transfers if row.entity_kind == "artifact"]
    assert len(records) == 1
    assert records[0].flow_class is TradeFlowClass.RECORDS
    assert records[0].previous_location_token == "loc-a"
    assert records[0].location_token == "loc-b"
    copy_supplies = [
        row for row in harvest.supplies if row.source_kind == "artifact_copy"
    ]
    assert len(copy_supplies) == 1
    assert copy_supplies[0].flow_class is TradeFlowClass.RECORDS


def _media_run(*, consumed: bool = False):
    first = _exchange(
        "evt-1",
        actor="body-a",
        other="body-b",
        give=(("item-m", "generic"),),
        take=(("item-x1", "food"),),
        origin="loc-a",
    )
    second = _exchange(
        "evt-2",
        tick=1,
        actor="body-b",
        other="body-c",
        give=(("item-m", "generic"),),
        take=(("item-x2", "food"),),
        origin="loc-b",
    )
    events = [first, second]
    if consumed:
        events.append(
            _event(
                "evt-3",
                Eaten(item_id=EntityId("item-m")),
                tick=2,
                origin="loc-b",
            )
        )
    return tuple(events)


def test_generic_media_requires_two_transfers_and_no_consumption() -> None:
    harvest = trade_transfer_rows_from_events(_media_run(), policy=POLICY)
    media = [row for row in harvest.transfers if row.entity_token == "item-m"]
    assert len(media) == 2
    assert all(row.flow_class is TradeFlowClass.DURABLE_EXCHANGE_MEDIA for row in media)
    assert all(row.consumed is False for row in media)


def test_generic_media_requires_distinct_parties() -> None:
    harvest = trade_transfer_rows_from_events(
        (_gift("evt-1", item="item-m"), _gift("evt-2", item="item-m", tick=1)),
        policy=POLICY,
    )
    assert all(row.flow_class is TradeFlowClass.OTHER for row in harvest.transfers)


def test_consumed_generic_is_never_media() -> None:
    harvest = trade_transfer_rows_from_events(_media_run(consumed=True), policy=POLICY)
    media = [row for row in harvest.transfers if row.entity_token == "item-m"]
    assert all(row.flow_class is TradeFlowClass.OTHER for row in media)
    assert all(row.consumed is True for row in media)


def test_unresolved_origin_marks_partial() -> None:
    harvest = trade_transfer_rows_from_events(
        (_gift("evt-1", origin=None),), policy=POLICY
    )
    assert harvest.transfers[0].previous_location_token == NONE_TOKEN
    assert harvest.transfers[0].location_token == NONE_TOKEN
    assert harvest.coverage is TradeCoverage.PARTIAL


def test_conflicting_item_kind_is_rejected() -> None:
    first = _exchange("evt-1", give=(("item-m", "food"),))
    second = _exchange("evt-2", tick=1, give=(("item-m", "material"),))
    with pytest.raises(ValueError, match="trade_networks_conflicting_item_kind"):
        trade_transfer_rows_from_events((first, second), policy=POLICY)


def test_transfer_cap_truncates_deterministically() -> None:
    policy = type(POLICY)(max_transfer_rows=1)
    harvest = trade_transfer_rows_from_events(_media_run(), policy=policy)
    assert harvest.transfer_count == 1
    assert "trade_networks_transfer_truncated" in harvest.notices
    assert harvest.coverage is TradeCoverage.PARTIAL


def test_duplicate_event_rejected() -> None:
    duplicate = _gift("evt-1")
    with pytest.raises(ValueError, match="trade_networks_duplicate_event"):
        trade_transfer_rows_from_events((duplicate, duplicate), policy=POLICY)


event_ids = st.lists(
    st.tuples(
        st.integers(min_value=0, max_value=50),
        st.integers(min_value=0, max_value=500),
    ),
    min_size=0,
    max_size=20,
    unique_by=lambda pair: pair[1],
)


@given(rows=event_ids)
def test_rows_are_bounded_and_ordered(rows) -> None:
    events = [
        _gift(f"evt-{token}", item=f"item-{token}", tick=tick) for tick, token in rows
    ]
    harvest = trade_transfer_rows_from_events(tuple(events), policy=POLICY)
    assert harvest.transfer_count == len(events)
    keys = [
        (row.tick, row.event_token, row.entity_token, row.direction)
        for row in harvest.transfers
    ]
    assert keys == sorted(keys)
    assert harvest.transfer_count <= POLICY.max_transfer_rows
