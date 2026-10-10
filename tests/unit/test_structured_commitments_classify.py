"""Speech labels stay separate from each owner's terms."""

from __future__ import annotations

import pytest

from analysis.structured_commitments import (
    CommitmentLedgerSnapshot,
    classify_commitment_speech,
)
from world.effects import ActionCause
from world.events import (
    EVENT_SCHEMA_REPLAY_V17,
    CommitmentDeclared,
    Given,
    OccurrenceContext,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision


def _event(details: object, *, tick: int, sequence: int, actor: str):
    return make_physical_replayable_event(
        event_id=EventId(f"evt-{tick}-{sequence}"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=tick,
        sequence=sequence,
        cause=ActionCause(
            request_id=RequestId(f"req-{sequence}"),
            actor_id=EntityId(actor),
        ),
        resulting_revision=WorldRevision(0),
        details=details,  # type: ignore[arg-type]
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=EVENT_SCHEMA_REPLAY_V17,
    )


def _speech():
    return CommitmentDeclared(
        EntityId("body-a"),
        EntityId("body-b"),
        "future_exchange",
        "propose",
        "counterparty",
        "none",
        2,
        "by_tick",
        "material",
        8,
        "food",
    )


def _row(owner: str, *, item_kind: str = "material", status: str = "open"):
    return CommitmentLedgerSnapshot(
        owner,
        ("evt-1-1",),
        "future_exchange",
        item_kind,
        "none",
        2,
        "counterparty",
        "by_tick",
        status,
    )


def test_channel_off_is_an_empty_list() -> None:
    assert classify_commitment_speech((), as_of_tick=1) == ()


def test_speech_only_and_unformed_owner() -> None:
    views = classify_commitment_speech(
        (_event(_speech(), tick=1, sequence=1, actor="body-a"),),
        as_of_tick=1,
        owner_ids=("owner-a",),
    )
    assert len(views) == 1
    view = views[0]
    assert view.world_enforcement is False
    assert view.institution == "none"
    assert view.divergent is False
    assert view.interpretations[0].status == "unformed"
    assert dict(view.speech)["kind"] == "future_exchange"
    assert view.item_moves == ()


def test_fulfilled_partial_divergent_and_forgotten() -> None:
    given = _event(
        Given(EntityId("body-a"), EntityId("item-1"), EntityId("body-a")),
        tick=2,
        sequence=1,
        actor="body-b",
    )
    events = (_event(_speech(), tick=1, sequence=1, actor="body-a"), given)
    fulfilled = classify_commitment_speech(
        events,
        as_of_tick=2,
        ledgers=(_row("owner-a", status="fulfilled"),),
    )[0]
    assert fulfilled.fulfillment == (("fulfilled", 1),)
    assert fulfilled.item_moves[0].item_id == "item-1"
    assert fulfilled.item_moves[0].actor_id == "body-b"
    partial = classify_commitment_speech(
        events,
        as_of_tick=2,
        ledgers=(_row("owner-a", status="partial"),),
    )[0]
    assert partial.fulfillment == (("partial", 1),)
    split = classify_commitment_speech(
        events,
        as_of_tick=2,
        ledgers=(
            _row("owner-a", item_kind="material", status="open"),
            _row("owner-b", item_kind="food", status="forgotten"),
        ),
    )[0]
    assert split.divergent is True
    assert split.forgotten_split is True


def test_world_enforcement_cannot_be_true() -> None:
    view = classify_commitment_speech(
        (_event(_speech(), tick=1, sequence=1, actor="body-a"),),
        as_of_tick=1,
    )[0]
    with pytest.raises(ValueError, match="world_enforcement"):
        object.__setattr__(view, "world_enforcement", True)
        view.__post_init__()
