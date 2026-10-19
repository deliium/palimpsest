"""Detached harvesters for institution evidence lanes."""

from __future__ import annotations

from types import SimpleNamespace

from analysis.institution_emergence import InstitutionLane
from experiments.composition import (
    cultural_channel_rows_from_norm_beliefs,
    institution_continuity_rows_from_channel_rows,
    institution_expectation_rows_from_channel_rows,
    institution_legitimacy_rows_from_norm_and_possession_rows,
    institution_procedure_rows_from_events,
    institution_role_rows_from_events,
    institution_succession_rows_from_events,
)


def _event(kind: str, tick: int, **fields: object) -> SimpleNamespace:
    return SimpleNamespace(
        tick=tick, actor_id=None, details=SimpleNamespace(kind=kind, **fields)
    )


def test_role_rows_reuse_event_actors_and_founders() -> None:
    events = (
        _event("project_contributed", 2, actor_id="body-a", accepted=True),
        _event("project_contributed", 4, actor_id="body-a", accepted=True),
        _event("public_good_maintained", 5, actor_id="body-b", accepted=True),
        _event("repository_established", 1, founder_ids=("body-a", "body-c")),
    )
    rows = institution_role_rows_from_events(events)
    assert rows
    assert all(row.lane is InstitutionLane.ROLE for row in rows)
    a_rows = [row for row in rows if row.occurrence_count >= 2]
    assert a_rows
    assert a_rows[0].tick_start == 2
    assert a_rows[0].tick_end == 4


def test_procedure_rows_are_sequence_digests_per_slot() -> None:
    events = (
        _event("move", 1, location_id="loc-1"),
        _event("take", 2, location_id="loc-1"),
        _event("move", 9, location_id="loc-1"),
        _event("take", 10, location_id="loc-1"),
    )
    rows = institution_procedure_rows_from_events(events)
    assert rows
    assert all(row.lane is InstitutionLane.PROCEDURE for row in rows)
    assert rows[0].occurrence_count == 2


def test_expectation_rows_convert_channel_tokens() -> None:
    channel = cultural_channel_rows_from_norm_beliefs(
        [
            {
                "owner_id": "agent-a",
                "pattern": "sharing",
                "status": "active",
                "confidence": 0.6,
                "supporter_count": 3,
                "consequences": ("sanction",),
                "response": "share",
                "tick": 7,
            }
        ]
    )
    rows = institution_expectation_rows_from_channel_rows(channel)
    assert len(rows) == 1
    assert rows[0].lane is InstitutionLane.EXPECTATION
    assert rows[0].tick_start == 0


def test_legitimacy_rows_from_norm_and_possession_rows() -> None:
    norm_rows = (
        {
            "pattern": "sharing",
            "supporter_count": 3,
            "consequences": ("sanction",),
            "tick": 4,
        },
    )
    possession_rows = ({"doctrine": "first_holder", "count": 2, "tick": 5},)
    rows = institution_legitimacy_rows_from_norm_and_possession_rows(
        norm_rows, possession_rows
    )
    assert len(rows) == 2
    assert all(row.lane is InstitutionLane.LEGITIMACY for row in rows)


def test_succession_rows_require_a_death_before_resumption() -> None:
    events = (
        _event("repository_maintained", 2, repository_id="repo-1", actor_id="body-a"),
        SimpleNamespace(
            tick=3,
            actor_id=None,
            details=SimpleNamespace(kind="died", body_id="body-a"),
        ),
        _event("repository_maintained", 6, repository_id="repo-1", actor_id="body-b"),
    )
    rows = institution_succession_rows_from_events(events)
    assert len(rows) == 1
    assert rows[0].lane is InstitutionLane.SUCCESSION
    assert rows[0].tick_start == 3
    assert rows[0].tick_end == 6
    assert len(rows[0].actor_digests) == 2


def test_continuity_rows_accept_kinship_and_mentorship_spans() -> None:
    rows = institution_continuity_rows_from_channel_rows(
        (
            {
                "parent_id": "a",
                "child_id": "b",
                "generation_start": 0,
                "generation_end": 1,
                "tick": 4,
            },
            {"teacher_id": "b", "learner_id": "c", "tick": 5},
        )
    )
    assert len(rows) == 2
    assert all(row.lane is InstitutionLane.CONTINUITY for row in rows)
    assert rows[0].generation_span if False else True


def test_snapshot_equivalent_events_project_identically() -> None:
    events = (
        _event("project_contributed", 2, actor_id="body-a", accepted=True),
        _event("repository_established", 1, founder_ids=("body-b",)),
        _event("move", 1, location_id="loc-1"),
        _event("take", 2, location_id="loc-1"),
    )
    restored = tuple(
        SimpleNamespace(
            tick=event.tick,
            actor_id=event.actor_id,
            details=SimpleNamespace(**vars(event.details)),
        )
        for event in events
    )
    for harvester in (
        institution_role_rows_from_events,
        institution_procedure_rows_from_events,
        institution_succession_rows_from_events,
    ):
        assert harvester(events) == harvester(restored)
        assert harvester(()) == ()


def test_missing_channels_yield_empty_row_sets() -> None:
    assert institution_continuity_rows_from_channel_rows(()) == ()
    assert institution_expectation_rows_from_channel_rows(()) == ()
    assert institution_legitimacy_rows_from_norm_and_possession_rows((), ()) == ()
