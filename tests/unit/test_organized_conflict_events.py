# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined,no-untyped-def,no-untyped-call,call-overload,index,type-arg,unused-ignore"
from __future__ import annotations

from types import SimpleNamespace

from analysis.organized_conflict_events import (
    build_conflict_windows,
    conflict_agent_token,
    conflict_event_rows_from_events,
    conflict_location_token,
)
from analysis.organized_conflict_policy import (
    default_organized_conflict_analysis_policy,
)
from world.identifiers import EntityId

POLICY = default_organized_conflict_analysis_policy()


def _event(kind: str, *, tick: int, actor: str | None = None, **details: object):
    return SimpleNamespace(
        tick=tick,
        actor_id=None if actor is None else EntityId(actor),
        details=SimpleNamespace(kind=kind, **details),
    )


def test_attack_flee_death_and_help_rows() -> None:
    events = (
        _event(
            "attack",
            tick=1,
            actor="body-a",
            target_id=EntityId("body-b"),
            hit=True,
            damage=12,
        ),
        _event(
            "flee",
            tick=2,
            actor="body-b",
            threat_id=EntityId("body-a"),
            success=True,
            destination_id=EntityId("place-b"),
        ),
        _event(
            "died",
            tick=3,
            body_id=EntityId("body-b"),
            death_cause=SimpleNamespace(value="attack"),
        ),
        _event(
            "help",
            tick=4,
            actor="body-c",
            target_id=EntityId("body-b"),
            health_delta=5.0,
        ),
    )
    rows = conflict_event_rows_from_events(events, policy=POLICY)
    assert [row.event_class for row in rows] == [
        "attack",
        "retreat",
        "death",
        "assistance",
    ]
    assert rows[0].success is True and rows[0].magnitude == 12
    assert rows[1].location_token == conflict_location_token(EntityId("place-b"))


def test_capture_and_structure_opposition_rows() -> None:
    events = (
        _event("take", tick=1, actor="body-a", item_id=EntityId("food")),
        _event(
            "give",
            tick=2,
            actor="body-a",
            recipient_id=EntityId("body-b"),
            item_id=EntityId("food"),
        ),
        _event(
            "public_good_opposed",
            tick=3,
            actor="body-a",
            project_id=EntityId("store"),
            status="completed",
            integrity_millis=400,
        ),
    )
    rows = conflict_event_rows_from_events(events, policy=POLICY)
    assert [row.event_class for row in rows] == [
        "custody_capture",
        "custody_transfer",
        "structure_opposition",
    ]
    assert rows[2].magnitude == 400


def test_corpse_capture_and_non_attack_death_are_mapped() -> None:
    events = (
        _event(
            "taken_from_corpse",
            tick=1,
            item_id=EntityId("food"),
            source_body_id=EntityId("body-dead"),
            resulting_holder_id=EntityId("body-a"),
        ),
        _event(
            "died",
            tick=2,
            body_id=EntityId("body-b"),
            death_cause=SimpleNamespace(value="lifespan"),
        ),
    )
    rows = conflict_event_rows_from_events(events, policy=POLICY)
    assert [row.event_class for row in rows] == ["custody_capture"]


def test_movement_and_co_movement_rows() -> None:
    events = (
        _event("move", tick=1, actor="body-a", destination_id=EntityId("place-b")),
        _event(
            "journey_arrived",
            tick=2,
            participant_body_ids=(EntityId("body-a"), EntityId("body-b")),
            destination_location_id=EntityId("place-c"),
        ),
        _event(
            "contact_recorded", tick=3, actor="body-a", location_id=EntityId("place-c")
        ),
    )
    rows = conflict_event_rows_from_events(events, policy=POLICY)
    assert [row.event_class for row in rows] == [
        "movement",
        "co_movement",
        "co_movement",
        "contact",
    ]


def test_tokens_are_stable_and_opaque() -> None:
    entity = EntityId("body-a")
    assert conflict_agent_token(entity) == conflict_agent_token(entity)
    assert conflict_agent_token(entity) != conflict_agent_token(EntityId("body-b"))
    assert len(conflict_agent_token(entity)) == 16
    rows = conflict_event_rows_from_events(
        (
            _event(
                "attack", tick=1, actor="body-a", target_id=EntityId("body-b"), hit=True
            ),
        ),
        policy=POLICY,
    )
    assert rows[0].actor_token == conflict_agent_token(entity)
    assert "body-a" not in repr(rows[0])


def test_windows_are_deterministic() -> None:
    events = tuple(
        _event(
            "attack", tick=tick, actor="body-a", target_id=EntityId("body-b"), hit=True
        )
        for tick in (0, 1, 6, 7, 12)
    )
    rows = conflict_event_rows_from_events(events, policy=POLICY)
    windows = build_conflict_windows(rows, POLICY)
    assert [tuple(row.tick for row in window) for window in windows] == [
        (0, 1),
        (6, 7),
        (12,),
    ]
    assert build_conflict_windows((), POLICY) == ()
