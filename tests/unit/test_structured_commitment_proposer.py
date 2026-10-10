"""The proposer speaks a commitment and does not collect it."""

from __future__ import annotations

from types import SimpleNamespace

from agents.cognition.structured_commitments import propose_commitment_command
from world.actions import Attack, DeclareCommitment, Give, Wait
from world.identifiers import EntityId, EventId
from world.observations import (
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
)
from world.values import ItemKind


def _occurrence(kind: str, actor: str, other: str, facts: dict):
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=1,
            source_event_id=EventId("evt-1"),
        ),
        kind=kind,
        audience_role=ObservationAudienceRole.ACTOR,
        actor_id=EntityId(actor),
        other_entity_id=EntityId(other),
        public_facts=facts,
    )


def _obs(occurrences, tick: int = 2):
    return SimpleNamespace(
        occurrences=occurrences,
        tick=tick,
        observer_id=EntityId("body-a"),
    )


def test_post_give_proposal_and_accept_copy_perception() -> None:
    proposed = propose_commitment_command(
        Wait(),
        _obs(
            (
                _occurrence(
                    "give",
                    "body-a",
                    "body-b",
                    {"kind": "give", "item_kind": "food", "item_id": "food-1"},
                ),
            )
        ),
        channel_on=True,
        horizon_ticks=8,
        owner_entity_id=EntityId("body-a"),
    )
    assert type(proposed) is DeclareCommitment
    assert proposed.commitment_kind == "future_exchange"
    assert proposed.act == "propose"
    assert proposed.now_item_kind is ItemKind.FOOD
    assert proposed.item_kind is ItemKind.MATERIAL
    assert proposed.due_tick == 10
    assert type(proposed) is not Give
    assert type(proposed) is not Attack
    heard = propose_commitment_command(
        Wait(),
        _obs(
            (
                _occurrence(
                    "commitment_declared",
                    "body-b",
                    "body-a",
                    {
                        "kind": "promise",
                        "act": "propose",
                        "owed_by": "self",
                        "item_kind": "material",
                        "service": "none",
                        "quantity": 1,
                        "due_kind": "none",
                        "due_tick": None,
                        "now_item_kind": None,
                    },
                ),
            )
        ),
        channel_on=True,
        horizon_ticks=8,
        owner_entity_id=EntityId("body-a"),
    )
    assert type(heard) is DeclareCommitment
    assert heard.act == "accept"
    assert heard.commitment_kind == "promise"
    assert heard.item_kind is ItemKind.MATERIAL
    assert type(heard) is not Give


def test_channel_off_keeps_the_ranked_command() -> None:
    waiting = Wait()
    assert (
        propose_commitment_command(
            waiting,
            _obs(
                (
                    _occurrence(
                        "give",
                        "body-a",
                        "body-b",
                        {"item_kind": "food"},
                    ),
                )
            ),
            channel_on=False,
            horizon_ticks=8,
            owner_entity_id=EntityId("body-a"),
        )
        is waiting
    )
