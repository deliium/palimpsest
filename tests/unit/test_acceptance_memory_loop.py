"""Cognitive loop folds observed completions into acceptance memory."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from agents.cognition.acceptance_memory import received_count_for
from agents.cognition.configuration import build_cognitive_loop
from agents.models import AgentId
from world.identifiers import EntityId, EventId
from world.observations import (
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
)
from world.values import ItemKind


def _occurrence(*, tick: int, give: str, take: str) -> ObservedOccurrence:
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=tick,
            source_event_id=EventId(f"event-{give}"),
        ),
        kind="exchange_completed",
        audience_role=ObservationAudienceRole.WITNESS,
        actor_id=EntityId("body-b"),
        other_entity_id=EntityId("body-a"),
        public_facts={
            "kind": "exchange_completed",
            "give_item_ids": (give,),
            "take_item_ids": (take,),
            "give_item_kinds": (ItemKind.GENERIC.value,),
            "take_item_kinds": (ItemKind.FOOD.value,),
        },
    )


def _observation(
    *, tick: int, occurrences: tuple[ObservedOccurrence, ...]
) -> Observation:
    """Minimal owner-scoped stand-in: the fold reads only tick and occurrences."""
    return cast(
        Observation,
        SimpleNamespace(tick=tick, occurrences=occurrences),
    )


def test_fold_applies_completion_and_skips_repeat() -> None:
    loop = build_cognitive_loop(
        resource_exchange_profile_active=True,
        acceptance_window_ticks=8,
        subjective_valuation_active=True,
    )
    owner = AgentId("agent-a")
    observation = _observation(
        tick=4,
        occurrences=(_occurrence(tick=4, give="pebble", take="bread"),),
    )
    ledger = loop._fold_acceptance_memory(observation, None, owner_id=owner)
    assert received_count_for(ledger, ItemKind.GENERIC) == 1
    assert received_count_for(ledger, ItemKind.FOOD) == 1
    again = loop._fold_acceptance_memory(
        observation,
        SimpleNamespace(acceptance_memories=ledger),
        owner_id=owner,
    )
    assert received_count_for(again, ItemKind.GENERIC) == 1


def test_fold_ignores_events_outside_the_window() -> None:
    loop = build_cognitive_loop(
        resource_exchange_profile_active=True,
        acceptance_window_ticks=2,
    )
    observation = _observation(
        tick=10,
        occurrences=(_occurrence(tick=1, give="pebble", take="bread"),),
    )
    ledger = loop._fold_acceptance_memory(
        observation, None, owner_id=AgentId("agent-a")
    )
    assert ledger is not None
    assert ledger.rows == ()


def test_channel_off_does_not_fold() -> None:
    loop = build_cognitive_loop(resource_exchange_profile_active=False)
    observation = _observation(
        tick=4,
        occurrences=(_occurrence(tick=4, give="pebble", take="bread"),),
    )
    assert (
        loop._fold_acceptance_memory(observation, None, owner_id=AgentId("agent-a"))
        is None
    )
