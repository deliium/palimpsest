"""Deterministic fake embedder and logical tick source."""

from __future__ import annotations

from typing import cast

import pytest

from agents.models import AgentId
from memory.errors import MemoryServiceError
from memory.models import (
    ConceptMention,
    MemoryId,
    MemoryMutationBatch,
    MemoryProvenance,
    MemoryRunId,
    MemoryScope,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
)
from tests.fakes.memory import FakeEmbedder, FakeLogicalTickSource, FakeMemoryService
from world.identifiers import WorldRevision

pytestmark = pytest.mark.unit


def test_fake_embedder_is_deterministic_and_metadata_only() -> None:
    embedder = FakeEmbedder(vectors={"campfire": (1.0, 0.0), "river": (0.0, 1.0)})
    first = embedder.embed("campfire")
    second = embedder.embed("campfire")
    assert first == second
    assert first.vector == (1.0, 0.0)
    assert all("1.0" not in repr(call) for call in embedder.calls)
    assert [call.status for call in embedder.calls] == ["ok", "ok"]
    with pytest.raises(ValueError, match="unknown_embed_key"):
        embedder.embed("missing")
    with pytest.raises(ValueError, match="dimension_mismatch"):
        embedder.embed("campfire", dimension=3)


def test_fake_logical_tick_source_advances_without_wall_clock() -> None:
    clock = FakeLogicalTickSource(initial=2)
    assert clock.current() == 2
    assert clock.advance(3) == 5
    assert "datetime" not in repr(clock).lower()
    with pytest.raises(ValueError):
        FakeLogicalTickSource(initial=-1)


def _trace(memory_id: str = "m-1") -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(0),
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept="gate"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=0.5,
        confidence=0.9,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=1,
        ),
        created_tick=1,
        source_tick=1,
        last_access_tick=1,
        access_count=0,
    )


@pytest.mark.asyncio
async def test_fake_memory_service_rejects_duplicate_memory_ids() -> None:
    service = FakeMemoryService(
        MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
    )
    trace = _trace()
    await service.apply(MemoryMutationBatch(writes=(trace,)))
    with pytest.raises(MemoryServiceError, match="conflict"):
        await service.apply(MemoryMutationBatch(writes=(trace,)))
    stored = await service.get(MemoryId("m-1"))
    assert stored is not None
    assert stored.access_count == 0


async def test_fake_selected_forgetting_is_scoped_non_destructive_and_idempotent(
) -> None:
    service = FakeMemoryService(
        MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
    )
    first, second = _trace(), _trace("m-2")
    await service.apply(MemoryMutationBatch(writes=(first, second)))

    count = await service.forget_selected_ids(
        (first.memory_id, MemoryId("missing"), first.memory_id), tick=3
    )

    assert count == 1
    assert await service.snapshot() == (second,)
    stored = await service.get(first.memory_id)
    assert stored is not None
    assert stored.forgotten_at_tick == 3
    assert first.forgotten_at_tick is None
    assert await service.forget_selected_ids((first.memory_id,), tick=4) == 0
    assert (await service.get(first.memory_id)) == stored
    assert service.calls[-1].operation == "forget_selected"
    assert service.calls[-1].write_count == 0


@pytest.mark.parametrize("tick", [-1, True, 1.0, "3", 0])
async def test_fake_selected_forgetting_rejects_invalid_or_premature_ticks(
    tick: object,
) -> None:
    service = FakeMemoryService(
        MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
    )
    trace = _trace()
    await service.apply(MemoryMutationBatch(writes=(trace,)))
    with pytest.raises(MemoryServiceError, match="invalid_request"):
        await service.forget_selected_ids((trace.memory_id,), tick=cast(int, tick))
    assert await service.snapshot() == (trace,)
