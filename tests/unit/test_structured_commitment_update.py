"""Each owner folds their own commitment observations and nobody collects."""

from __future__ import annotations

from types import SimpleNamespace

from agents.cognition.structured_commitments import (
    apply_structured_commitment_update,
    empty_structured_commitments,
)
from agents.models import AgentId
from world.identifiers import EntityId, EventId
from world.observations import (
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
)


def _occurrence(kind: str, actor: str, other: str, facts: dict, event: str = "evt-1"):
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=1,
            source_event_id=EventId(event),
        ),
        kind=kind,
        audience_role=ObservationAudienceRole.ACTOR,
        actor_id=EntityId(actor),
        other_entity_id=EntityId(other),
        public_facts=facts,
    )


def _speech(**overrides):
    facts = {
        "kind": "future_exchange",
        "act": "propose",
        "owed_by": "counterparty",
        "item_kind": "material",
        "service": "none",
        "quantity": 1,
        "now_item_kind": "food",
        "due_kind": "by_tick",
        "due_tick": 4,
    }
    facts.update(overrides)
    return _occurrence("commitment_declared", "body-a", "body-b", facts)


def _give(actor: str, recipient: str, item_kind: str, event: str):
    return _occurrence(
        "give",
        actor,
        recipient,
        {"kind": "give", "item_kind": item_kind, "item_id": event},
        event,
    )


def _obs(occurrences, *, tick: int = 2, bodies: tuple = (), observer: str = "body-a"):
    return SimpleNamespace(
        occurrences=occurrences,
        visible_bodies=bodies,
        observer_id=EntityId(observer),
        tick=tick,
    )


def _ledger():
    return empty_structured_commitments(AgentId("owner-a"), max_open_interpretations=4)


def test_food_now_stays_open_and_material_later_fulfills() -> None:
    opened = apply_structured_commitment_update(_ledger(), _obs((_speech(),)), tick=1)
    after_food = apply_structured_commitment_update(
        opened, _obs((_give("body-b", "body-a", "food", "evt-food"),)), tick=2
    )
    row = after_food.interpretations[0]
    assert row.now_matched is True
    assert row.matched_quantity == 0
    assert row.status == "open"
    fulfilled = apply_structured_commitment_update(
        after_food,
        _obs((_give("body-b", "body-a", "material", "evt-mat"),)),
        tick=3,
    )
    assert fulfilled.interpretations[0].status == "fulfilled"
    assert fulfilled.interpretations[0].matched_quantity == 1


def test_third_party_give_does_not_count() -> None:
    opened = apply_structured_commitment_update(_ledger(), _obs((_speech(),)), tick=1)
    after = apply_structured_commitment_update(
        opened, _obs((_give("body-c", "body-a", "material", "evt-c"),)), tick=2
    )
    assert after.interpretations[0].matched_quantity == 0
    assert after.interpretations[0].status != "fulfilled"


def test_one_of_two_stays_partial_and_none_does_not_violate() -> None:
    opened = apply_structured_commitment_update(
        _ledger(), _obs((_speech(quantity=2, due_kind="none", due_tick=None),)), tick=1
    )
    partial = apply_structured_commitment_update(
        opened, _obs((_give("body-b", "body-a", "material", "evt-1m"),)), tick=20
    )
    assert partial.interpretations[0].status == "partial"
    assert partial.interpretations[0].matched_quantity == 1


def test_meeting_without_the_later_leg_violates_only_then() -> None:
    opened = apply_structured_commitment_update(
        _ledger(),
        _obs((_speech(due_kind="when_next_colocated", due_tick=None),)),
        tick=1,
    )
    waiting = apply_structured_commitment_update(opened, _obs((), tick=2), tick=2)
    assert waiting.interpretations[0].status != "violated"
    met = apply_structured_commitment_update(
        waiting,
        _obs(
            (),
            tick=3,
            bodies=(SimpleNamespace(entity_id=EntityId("body-b")),),
        ),
        tick=3,
    )
    assert met.interpretations[0].status == "violated"


def test_counterpart_gift_opens_and_a_mismatched_report_disputes() -> None:
    opened = apply_structured_commitment_update(
        _ledger(),
        _obs(
            (
                _speech(
                    due_kind="if_counterpart_gives",
                    due_tick=None,
                    owed_by="self",
                    kind="promise",
                ),
            )
        ),
        tick=1,
    )
    assert opened.interpretations[0].status == "proposed"
    gifted = apply_structured_commitment_update(
        opened, _obs((_give("body-a", "body-b", "food", "evt-now"),)), tick=2
    )
    assert gifted.interpretations[0].status == "open"
    assert gifted.interpretations[0].matched_quantity == 0
    disputed = apply_structured_commitment_update(
        gifted,
        _obs(
            (
                _speech(
                    act="report_fulfilled",
                    item_kind="tool",
                    due_kind="if_counterpart_gives",
                    due_tick=None,
                    owed_by="self",
                    kind="promise",
                ),
            )
        ),
        tick=3,
    )
    assert disputed.interpretations[0].status == "disputed"
    assert disputed.interpretations[0].matched_quantity == 0
    assert disputed.interpretations[0].item_kind == "material"
    assert disputed.interpretations[0].revisions


def test_late_by_tick_violates_without_adding_a_command() -> None:
    opened = apply_structured_commitment_update(_ledger(), _obs((_speech(),)), tick=1)
    late = apply_structured_commitment_update(opened, _obs((), tick=5), tick=5)
    assert late.interpretations[0].status == "violated"


def test_over_cap_keeps_the_older_row_and_a_child_starts_empty() -> None:
    ledger = empty_structured_commitments(
        AgentId("owner-a"), max_open_interpretations=1
    )
    first = apply_structured_commitment_update(ledger, _obs((_speech(),)), tick=1)
    second = apply_structured_commitment_update(
        first,
        _obs((_speech(item_kind="tool"),), tick=2),
        tick=2,
    )
    assert len(second.interpretations) == 1
    assert second.interpretations[0].item_kind == "material"
    child = empty_structured_commitments(AgentId("child-1"))
    assert child.interpretations == ()
    assert child.owner_id != first.owner_id
