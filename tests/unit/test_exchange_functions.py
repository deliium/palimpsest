"""Exchange-function counts stay numeric and unnamed."""

from __future__ import annotations

from analysis.exchange_functions import FORBIDDEN_KEYS, classify_exchange_functions
from simulation.runner_models import example_resource_exchange_profile_spec
from world.events import (
    EVENT_SCHEMA_REPLAY_V18,
    ActionCause,
    ExchangeCompleted,
    OccurrenceContext,
    WorldEvent,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision


def _event(
    event_id: str, details: object, *, tick: int, target_id: EntityId
) -> WorldEvent:
    request = RequestId(f"r-{event_id}")
    return WorldEvent(
        event_id=EventId(event_id),
        run_id="run-av",
        world_id=WorldId("world-av"),
        tick=tick,
        sequence=0,
        request_id=request,
        resulting_revision=WorldRevision(tick + 1),
        schema_version=EVENT_SCHEMA_REPLAY_V18,
        details=details,  # type: ignore[arg-type]
        actor_id=EntityId("body-a"),
        target_id=target_id,
        cause=ActionCause(request, EntityId("body-a")),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
    )


def _completed(
    event_id: str,
    *,
    tick: int,
    actor: str,
    other: str,
    give: tuple[tuple[str, str], ...],
    take: tuple[tuple[str, str], ...],
) -> WorldEvent:
    return _event(
        event_id,
        ExchangeCompleted(
            actor_id=EntityId(actor),
            counterparty_id=EntityId(other),
            act="accept",
            give_item_ids=tuple(EntityId(item_id) for item_id, _kind in give),
            take_item_ids=tuple(EntityId(item_id) for item_id, _kind in take),
            give_item_kinds=tuple(kind for _item_id, kind in give),
            take_item_kinds=tuple(kind for _item_id, kind in take),
        ),
        tick=tick,
        target_id=EntityId(other),
    )


def test_absent_spec_is_empty() -> None:
    views = classify_exchange_functions((), spec=None)
    assert views.acceptance_share == ()


def test_later_trade_and_quote_counts() -> None:
    events = (
        _completed(
            "swap-1",
            tick=1,
            actor="body-a",
            other="body-b",
            give=(("pebble", "generic"),),
            take=(("bread", "food"),),
        ),
        _completed(
            "swap-2",
            tick=2,
            actor="body-b",
            other="body-c",
            give=(("pebble", "generic"),),
            take=(("axe", "tool"),),
        ),
    )
    views = classify_exchange_functions(
        events, spec=example_resource_exchange_profile_spec()
    )
    generic = next(row for row in views.acquisition_fate if row.item_kind == "generic")
    assert generic.later_transferred_count >= 1
    assert generic.consumed_count == 0
    share = next(row for row in views.acceptance_share if row.item_kind == "generic")
    assert share.kind_present_count >= 2
    quote_generic = next(
        row for row in views.quote_homogeneity if row.item_kind == "generic"
    )
    quote_food = next(row for row in views.quote_homogeneity if row.item_kind == "food")
    assert quote_generic.homogeneous_side_count >= 1
    assert quote_food.homogeneous_side_count >= 1
    for row in (
        *views.acceptance_share,
        *views.acquisition_fate,
        *views.quote_homogeneity,
    ):
        assert not (set(row.__dataclass_fields__) & FORBIDDEN_KEYS)
