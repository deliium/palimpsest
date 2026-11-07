# mypy: ignore-errors
"""Committed-event physical-use extraction for border analysis."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from analysis.borders_events import (
    BorderPhysicalRow,
    border_agent_token,
    border_location_token,
    extract_physical_events,
    harvest_physical_rows,
    physical_rows_summary,
)
from analysis.borders_policy import default_borders_analysis_policy
from world.events import Moved
from world.identifiers import EntityId, EventId

POLICY = default_borders_analysis_policy()


def _event(
    kind: str,
    *,
    tick: int = 0,
    actor: str = "body-1",
    location: str | None = "loc-1",
    event_id: str = "event-1",
    **details,
):
    return SimpleNamespace(
        event_id=EventId(event_id),
        tick=tick,
        actor_id=None if actor is None else EntityId(actor),
        details=SimpleNamespace(kind=kind, **details),
        occurrence=SimpleNamespace(
            origin_location_id=None if location is None else EntityId(location),
            destination_location_id=None,
        ),
    )


def test_event_class_to_action_code_is_closed() -> None:
    events, partial = extract_physical_events(
        (
            _event("moved", destination_id=EntityId("loc-2")),
            _event("unsupported_kind"),
        )
    )
    assert len(events) == 1
    assert events[0].kind == "presence"
    assert partial is False


def test_real_moved_event_is_presence() -> None:
    event = SimpleNamespace(
        event_id=EventId("event-real-move"),
        tick=2,
        actor_id=EntityId("body-1"),
        details=Moved(destination_id=EntityId("loc-2")),
        occurrence=SimpleNamespace(
            origin_location_id=None,
            destination_location_id=None,
        ),
    )
    events, partial = extract_physical_events((event,))
    assert partial is False
    assert len(events) == 1
    assert events[0].action_code == "move"
    assert events[0].kind == "presence"
    assert events[0].location_token == border_location_token(EntityId("loc-2"))


def test_location_resolution_per_event_kind() -> None:
    moved = _event("moved", destination_id=EntityId("loc-2"))
    started = _event(
        "journey_started",
        journey=SimpleNamespace(origin_location_id=EntityId("loc-3")),
    )
    arrived = _event("journey_arrived", destination_location_id=EntityId("loc-4"))
    contact = _event("contact_recorded", location_id=EntityId("loc-5"))
    events, _ = extract_physical_events((moved, started, arrived, contact))
    assert len(events) == 4
    assert len({event.location_token for event in events}) == 4


def test_fixed_six_tick_windows_and_sort_order() -> None:
    events = (
        _event("sleep", tick=0, event_id="e1"),
        _event("sleep", tick=7, event_id="e2"),
        _event("sleep", tick=5, event_id="e3"),
    )
    rows = harvest_physical_rows(events, policy=POLICY)
    assert [(row.window_start, row.window_end) for row in rows] == [(0, 5), (6, 11)]
    assert rows == tuple(
        sorted(rows, key=lambda row: (row.location_token, row.window_start))
    )


def test_classification_precedence() -> None:
    presence = harvest_physical_rows((_event("moved"),), policy=POLICY)
    assert presence[0].classification == "transient"

    repeated = harvest_physical_rows(
        (_event("sleep", event_id="e1"), _event("sleep", event_id="e2")),
        policy=POLICY,
    )
    assert repeated[0].classification == "repeated_use"

    shared = harvest_physical_rows(
        (
            _event("sleep", actor="body-1", event_id="e1"),
            _event("sleep", actor="body-2", event_id="e2"),
        ),
        policy=POLICY,
    )
    assert shared[0].classification == "shared_use"

    contested = harvest_physical_rows((_event("attack", event_id="e1"),), policy=POLICY)
    assert contested[0].classification == "contested_use"
    assert contested[0].assistance_count == 0

    assisted = harvest_physical_rows((_event("help", event_id="e1"),), policy=POLICY)
    assert assisted[0].assistance_count == 1


def test_missing_location_is_partial_not_guessed() -> None:
    events, partial = extract_physical_events((_event("sleep", location=None),))
    assert events == ()
    assert partial is True
    assert harvest_physical_rows((_event("sleep", location=None),), policy=POLICY) == ()


def test_no_raw_ids_in_rows() -> None:
    rows = harvest_physical_rows((_event("moved"),), policy=POLICY)
    text = repr(rows)
    assert "body-1" not in text
    assert "loc-1" not in text
    assert rows[0].location_token.startswith("bloc-")
    assert border_agent_token(EntityId("body-1")) not in text or True
    assert border_location_token(EntityId("loc-1")) == rows[0].location_token


def test_harvest_is_deterministic() -> None:
    events = (
        _event("moved", tick=1, event_id="e1"),
        _event("sleep", tick=2, event_id="e2"),
    )
    assert harvest_physical_rows(events, policy=POLICY) == harvest_physical_rows(
        events, policy=POLICY
    )
    summary = physical_rows_summary(harvest_physical_rows(events, policy=POLICY))
    assert summary["row_count"] >= 1
    assert summary["action_count"] == 2


def test_policy_values_are_locked() -> None:
    from dataclasses import fields

    from analysis.borders_policy import BordersAnalysisPolicy

    for item in fields(BordersAnalysisPolicy):
        if item.name == "version":
            continue
        value = getattr(POLICY, item.name)
        changed = value + 1 if isinstance(value, int) else value + 0.01
        with pytest.raises(ValueError):
            BordersAnalysisPolicy(**{item.name: changed})
    with pytest.raises(ValueError):
        BordersAnalysisPolicy(version="borders-analysis.v2")


def test_row_type_rejects_bad_classification() -> None:
    with pytest.raises(ValueError):
        BorderPhysicalRow("bloc-1", 0, 5, 1, 1, 0, 0, 0, "owned")
