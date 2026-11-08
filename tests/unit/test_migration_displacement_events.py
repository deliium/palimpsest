# mypy: ignore-errors
"""Objective movement and integration-evidence extraction."""

from __future__ import annotations

import dataclasses
import logging
from types import SimpleNamespace

import pytest

from analysis.migration_displacement_events import (
    MIGRATION_MOVEMENT_PREFIX,
    MigrationMovementRow,
    migration_agent_token,
    migration_communication_pairs_from_events,
    migration_integration_rows_from_events,
    migration_kinship_pairs_from_events,
    migration_location_token,
    migration_movement_rows_from_events,
    migration_movement_rows_with_coverage,
)
from tests.unit.migration_displacement_analysis_helpers import (
    REV,
    RUN,
    died,
    event,
    flee,
    journey_arrived,
    journey_ended,
    journey_started,
    loc,
    move,
    p,
    transport,
)

pytestmark = pytest.mark.unit


def rows(events, **kwargs):
    return migration_movement_rows_from_events(
        events, run_id=RUN, input_revision=REV, **kwargs
    )


def test_move_transport_and_flee_become_objective_rows() -> None:
    out = rows(
        (
            move(1, "body-1", "loc-a", "loc-b"),
            transport(2, "body-2", "body-3", "loc-a", "loc-c"),
            flee(3, "body-4", "loc-a", "loc-d"),
            flee(4, "body-5", "loc-a", "loc-d", success=False),
        )
    )
    assert {row.relocation_kind for row in out} == {"move", "transport", "flee"}
    assert len(out) == 4  # move + two transport participants + flee
    transported = [row for row in out if row.relocation_kind == "transport"]
    assert {row.group_size for row in transported} == {2}
    assert all(row.arrival_status == "arrived" for row in out)
    assert all(
        row.route_tokens == (row.origin_token, row.destination_token) for row in out
    )


def test_journey_start_arrival_pairs_once() -> None:
    out = rows(
        (
            journey_started(1, "j-1", ("body-1", "body-2"), "loc-a", "loc-b"),
            journey_arrived(4, "j-1", ("body-1", "body-2"), "loc-a", "loc-b"),
        )
    )
    assert len(out) == 2
    assert {row.start_tick for row in out} == {1}
    assert {row.end_tick for row in out} == {4}
    assert {row.arrival_status for row in out} == {"arrived"}
    assert {row.group_size for row in out} == {2}


def test_journey_timeout_and_death_statuses() -> None:
    out = rows(
        (
            journey_started(1, "j-1", ("body-1",), "loc-a", "loc-b"),
            journey_ended(7, "j-1", ("body-1",), "loc-a", "loc-b", "arrival_timeout"),
            journey_started(1, "j-2", ("body-2",), "loc-a", "loc-b"),
            journey_ended(3, "j-2", ("body-2",), "loc-a", "loc-b", "participant_dead"),
            journey_started(1, "j-3", ("body-3",), "loc-a", "loc-b"),
            died(2, "body-3"),
        )
    )
    status = {row.participant_token: row.arrival_status for row in out}
    assert status[p("body-1")] == "timeout"
    assert status[p("body-2")] == "dead"
    assert status[p("body-3")] == "dead"


def test_pending_journey_is_not_an_arrival() -> None:
    out = rows((journey_started(1, "j-1", ("body-1",), "loc-a", "loc-b"),))
    assert [row.arrival_status for row in out] == ["pending"]
    assert out[0].end_tick == out[0].start_tick


def test_partial_boundary_is_explicit() -> None:
    events = (move(1, "body-1", "loc-a", "loc-b"),)
    complete, coverage = migration_movement_rows_with_coverage(
        events,
        run_id=RUN,
        input_revision=REV,
        window_end=10,
        complete_through_boundary=10,
    )
    assert coverage == "complete"
    assert complete[0].coverage == "complete"
    partial, coverage = migration_movement_rows_with_coverage(
        events,
        run_id=RUN,
        input_revision=REV,
        window_end=10,
        complete_through_boundary=5,
    )
    assert coverage == "partial"
    assert partial[0].coverage == "partial"
    _, coverage = migration_movement_rows_with_coverage(
        (), run_id=RUN, input_revision=REV
    )
    assert coverage == "missing"


def test_malformed_event_is_skipped_with_partial_coverage(caplog) -> None:
    bad = event(
        SimpleNamespace(kind="move", destination_id=None), tick=1, actor="body-1"
    )
    with caplog.at_level(logging.WARNING):
        out, coverage = migration_movement_rows_with_coverage(
            (bad, move(2, "body-2", "loc-a", "loc-b")), run_id=RUN, input_revision=REV
        )
    assert coverage == "partial"
    assert len(out) == 1
    assert "migration_movement_event_skipped reason_code=" in caplog.text
    assert "body-1" not in caplog.text


def test_rows_are_sorted_and_deduplicated() -> None:
    first = move(5, "body-2", "loc-a", "loc-b")
    out = rows(
        (
            first,
            move(5, "body-2", "loc-a", "loc-b"),
            move(2, "body-9", "loc-a", "loc-c"),
            move(5, "body-1", "loc-a", "loc-b"),
        )
    )
    assert len(out) == 3
    keys = [(r.start_tick, r.participant_token, r.destination_token) for r in out]
    assert keys == sorted(keys)


def test_rows_contain_no_cause_or_owner_token() -> None:
    names = {field.name for field in dataclasses.fields(MigrationMovementRow)}
    assert not names & {"cause_kind", "owner_token", "classification", "wave_token"}
    assert MIGRATION_MOVEMENT_PREFIX == "mig-move-"


def test_topology_marks_unmapped_locations_partial() -> None:
    out = rows(
        (move(1, "body-1", "loc-a", "loc-b"),),
        region_topology={"loc-a": "region-1"},
    )
    assert out[0].coverage == "partial"


def test_integration_evidence_counts_closed_domains() -> None:
    from world.events import Talked  # noqa: F401  (closed vocabulary check only)

    events = (
        journey_started(1, "j-1", ("body-1",), "loc-a", "loc-b"),
        journey_arrived(3, "j-1", ("body-1",), "loc-a", "loc-b"),
        event(SimpleNamespace(kind="needs_applied", body_id=_eid("body-1")), tick=5),
        event(
            SimpleNamespace(kind="exchange_completed"),
            tick=6,
            actor="body-1",
            target="body-2",
        ),
        event(
            SimpleNamespace(kind="exchange_completed"),
            tick=8,
            actor="body-1",
            target="body-2",
        ),
        event(SimpleNamespace(kind="attack"), tick=9, actor="body-2", target="body-1"),
        event(
            SimpleNamespace(kind="talk", recipient_id=_eid("body-2")),
            tick=7,
            actor="body-1",
        ),
    )
    out = migration_integration_rows_from_events(events, run_id=RUN, input_revision=REV)
    cells = {(r.domain): r for r in out if r.participant_token == p("body-1")}
    assert cells["residence"].evidence_count == 1
    assert cells["needs"].evidence_count == 1
    assert cells["resource_access"].evidence_count == 2
    assert (
        cells["resource_access"].first_tick,
        cells["resource_access"].last_tick,
    ) == (6, 8)
    assert cells["relationships"].evidence_count == 1
    assert cells["conflict_status"].evidence_count == 1
    assert all(r.destination_token == loc("loc-b") for r in cells.values())
    assert "organization_participation" not in cells
    assert "institution_participation" not in cells
    keys = [(r.participant_token, r.destination_token, r.domain) for r in out]
    assert keys == sorted(keys)


def test_integration_evidence_never_infers_from_silence() -> None:
    # Evidence while in transit or before any arrival has no destination.
    events = (
        event(SimpleNamespace(kind="exchange_completed"), tick=1, actor="body-1"),
        journey_started(2, "j-1", ("body-1",), "loc-a", "loc-b"),
        event(SimpleNamespace(kind="exchange_completed"), tick=3, actor="body-1"),
    )
    assert (
        migration_integration_rows_from_events(events, run_id=RUN, input_revision=REV)
        == ()
    )
    assert (
        migration_integration_rows_from_events((), run_id=RUN, input_revision=REV) == ()
    )


def test_tokenization_is_stable() -> None:
    assert migration_agent_token("body-1") == migration_agent_token("body-1")
    assert migration_agent_token("body-1") != migration_agent_token("body-2")
    assert migration_agent_token("x").startswith("mdo-")
    assert migration_location_token("x").startswith("mdl-")
    out = rows(
        (move(1, "body-1", "loc-a", "loc-b"),), entity_to_agent={"body-1": "agent-1"}
    )
    assert out[0].participant_token == migration_agent_token("agent-1")
    assert "body-1" not in repr(out) and "loc-a" not in repr(out)
    first = rows((move(1, "body-1", "loc-a", "loc-b"),))
    again = rows((move(1, "body-1", "loc-a", "loc-b"),))
    assert first == again


def test_kinship_and_communication_pairs_use_committed_events_only() -> None:
    kin = event(
        SimpleNamespace(
            kind="kinship_edge_recorded",
            parent_agent_id="agent-1",
            child_agent_id="agent-2",
            success=True,
        ),
        tick=1,
    )
    talk = event(
        SimpleNamespace(kind="tell", recipient_id=_eid("body-2")),
        tick=2,
        actor="body-1",
    )
    assert migration_kinship_pairs_from_events((kin,)) == (
        tuple(sorted((p("agent-1"), p("agent-2")))),
    )
    assert migration_communication_pairs_from_events((talk,)) == (
        tuple(sorted((p("body-1"), p("body-2")))),
    )


def _eid(value):
    from world.identifiers import EntityId

    return EntityId(value)
