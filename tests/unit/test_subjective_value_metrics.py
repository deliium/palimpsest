"""Known answers for exchange metric families. Channel off stays empty."""

from __future__ import annotations

import pytest

from analysis.specifications import (
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    metric_specification,
)
from analysis.subjective_value import ExchangeLedgerSnapshot
from analysis.subjective_value_metrics import (
    _document,
    assemble_subjective_value_metrics,
)
from world.effects import ActionCause
from world.events import (
    EVENT_SCHEMA_REPLAY_V18,
    ExchangeCompleted,
    ExchangeProposed,
    OccurrenceContext,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision


def test_family_count_is_94() -> None:
    assert METRIC_FAMILY_COUNT == 136
    assert MetricFamilyId.EXCHANGE_RESERVATION_DIVERGENCE.value == (
        "exchange_reservation_divergence"
    )


def test_channel_off_harvest_is_empty() -> None:
    assert (
        assemble_subjective_value_metrics(
            (),
            run_id="run-1",
            input_revision="rev-1",
            spec=None,
            as_of_tick=1,
        )
        == ()
    )


def test_rows_keep_eight_and_three_and_kind_counts() -> None:
    docs = assemble_subjective_value_metrics(
        (_event(_offer(), 1), _event(_completed(), 2)),
        run_id="run-1",
        input_revision="rev-1",
        spec=object(),
        as_of_tick=2,
        ledgers=(
            ExchangeLedgerSnapshot("alice", "tool", 8),
            ExchangeLedgerSnapshot("bob", "tool", 3),
        ),
    )
    by_family = {doc.metric_family: doc.values for doc in docs}
    reservations = by_family["exchange_reservation_divergence"]["reservations"]
    assert reservations == "alice:tool:8,bob:tool:3"
    assert by_family["exchange_realized_bundles"]["kind_counts"] == "food:3,tool:1"
    assert by_family["exchange_negotiation_path"]["complete_count"] == 1
    for values in by_family.values():
        assert "price" not in values


def test_price_field_fails() -> None:
    spec = metric_specification(MetricFamilyId.EXCHANGE_REALIZED_BUNDLES)
    with pytest.raises(ValueError, match="price field"):
        _document(
            spec,
            "run-1",
            "rev-1",
            {"price": 1, "layer": "research_inference"},
            observed=0,
        )


def _offer() -> ExchangeProposed:
    return ExchangeProposed(
        EntityId("body-a"),
        EntityId("body-b"),
        "offer",
        (EntityId("tool-1"),),
        (EntityId("food-1"), EntityId("food-2"), EntityId("food-3")),
    )


def _completed() -> ExchangeCompleted:
    return ExchangeCompleted(
        EntityId("body-a"),
        EntityId("body-b"),
        "accept",
        (EntityId("tool-1"),),
        (EntityId("food-1"), EntityId("food-2"), EntityId("food-3")),
        ("tool",),
        ("food", "food", "food"),
    )


def _event(details: object, tick: int):
    return make_physical_replayable_event(
        event_id=EventId(f"evt-{tick}-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=tick,
        sequence=1,
        cause=ActionCause(
            request_id=RequestId(f"req-{tick}"),
            actor_id=EntityId("body-a"),
        ),
        resulting_revision=WorldRevision(tick),
        details=details,  # type: ignore[arg-type]
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=EVENT_SCHEMA_REPLAY_V18,
    )
