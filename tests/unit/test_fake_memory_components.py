"""Deterministic fake embedder and logical tick source."""

from __future__ import annotations

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


@pytest.mark.asyncio
async def test_fake_memory_service_rejects_duplicate_memory_ids() -> None:
    service = FakeMemoryService(
        MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
    )
    trace = MemoryTrace(
        memory_id=MemoryId("m-1"),
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
    await service.apply(MemoryMutationBatch(writes=(trace,)))
    with pytest.raises(MemoryServiceError, match="conflict"):
        await service.apply(MemoryMutationBatch(writes=(trace,)))
    stored = await service.get(MemoryId("m-1"))
    assert stored is not None
    assert stored.access_count == 0
