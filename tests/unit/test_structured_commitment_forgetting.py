"""Forgetting a commitment follows that owner's traces only."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from agents.cognition.memory import build_direct_observation_memory_trace
from agents.cognition.models import MemoryUpdateKind
from agents.cognition.structured_commitments import (
    apply_structured_commitment_update,
    commitment_memory_intents,
    empty_structured_commitments,
    forget_structured_commitments,
    link_structured_commitment_traces,
)
from agents.models import AgentId
from memory.models import MemoryMutationBatch, MemoryRunId, MemoryScope
from memory.service import InMemoryMemoryService
from world.identifiers import EntityId, EventId, WorldRevision
from world.observations import (
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
)


def _speech():
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=1,
            source_event_id=EventId("evt-1"),
        ),
        kind="commitment_declared",
        audience_role=ObservationAudienceRole.ACTOR,
        actor_id=EntityId("body-a"),
        other_entity_id=EntityId("body-b"),
        public_facts={
            "kind": "future_exchange",
            "act": "propose",
            "owed_by": "counterparty",
            "item_kind": "material",
            "service": "none",
            "quantity": 1,
            "now_item_kind": "food",
            "due_kind": "none",
            "due_tick": None,
        },
    )


def _obs(owner: str):
    return SimpleNamespace(
        occurrences=(_speech(),),
        visible_bodies=(),
        observer_id=EntityId(owner),
        tick=1,
        revision=WorldRevision(1),
        locations=(),
    )


def _open(owner: str):
    return apply_structured_commitment_update(
        empty_structured_commitments(AgentId(owner)),
        _obs(owner),
        tick=1,
    )


def _trace(owner: str):
    return build_direct_observation_memory_trace(
        owner_id=AgentId(owner),
        observation_tick=1,
        observation_revision=WorldRevision(1),
        occurrence=_speech(),
        location_id=None,
    )


def test_one_owner_forgets_through_their_memory_service() -> None:
    async def run() -> None:
        left = link_structured_commitment_traces(_open("owner-a"), (_trace("owner-a"),))
        right = link_structured_commitment_traces(
            _open("owner-b"), (_trace("owner-b"),)
        )
        service = InMemoryMemoryService(
            MemoryScope(MemoryRunId("run-forget"), AgentId("owner-a"))
        )
        other = InMemoryMemoryService(
            MemoryScope(MemoryRunId("run-forget"), AgentId("owner-b"))
        )
        await service.apply(MemoryMutationBatch(writes=(_trace("owner-a"),)))
        await other.apply(MemoryMutationBatch(writes=(_trace("owner-b"),)))
        await service.forget_selected_ids((_trace("owner-a").memory_id,), tick=6)
        forgotten_trace = await service.get(_trace("owner-a").memory_id)
        assert forgotten_trace is not None
        assert forgotten_trace.forgotten_at_tick == 6
        forgotten = forget_structured_commitments(left, (forgotten_trace,))
        still = forget_structured_commitments(right, other.sync_snapshot())
        assert forgotten.interpretations[0].status == "forgotten"
        assert forgotten.interpretations[0].item_kind == "unspecified"
        assert forgotten.interpretations[0].revisions[-1].item_kind == "material"
        assert still.interpretations[0].status != "forgotten"
        assert other.sync_snapshot()

    asyncio.run(run())


def test_unlinked_row_stays_open_past_the_horizon() -> None:
    opened = _open("owner-a")
    assert opened.interpretations[0].memory_trace_ids == ()
    later = forget_structured_commitments(opened, ())
    assert later.interpretations[0].status != "forgotten"
    assert later.interpretations[0].item_kind == "material"


def test_adopted_speech_requests_one_write_memory() -> None:
    ledger = _open("owner-a")
    intents = commitment_memory_intents(AgentId("owner-a"), _obs("body-a"), ledger)
    assert len(intents) == 1
    assert intents[0].kind is MemoryUpdateKind.WRITE_MEMORY
    assert intents[0].memory is not None
    assert intents[0].memory.owner_id == AgentId("owner-a")
