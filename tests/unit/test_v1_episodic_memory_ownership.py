"""Owner/run isolation for the in-memory episodic MemoryService."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from memory.models import (
    ConceptMention,
    MemoryAccessReceipt,
    MemoryForgetRequest,
    MemoryId,
    MemoryMutationBatch,
    MemoryProvenance,
    MemoryQueryContext,
    MemoryQueryFilters,
    MemoryRetentionPolicy,
    MemoryRetrieveRequest,
    MemoryRunId,
    MemoryScope,
    MemoryScoreWeights,
    MemoryScoringPolicy,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
)
from memory.service import (
    InMemoryMemoryService,
    MemoryServiceError,
    MemoryServiceErrorCode,
)
from world.identifiers import WorldRevision


def _trace(*, memory_id: str, owner: str, tick: int = 0) -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId(owner),
        world_revision=WorldRevision(0),
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept="note"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=0.0,
        confidence=1.0,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=tick,
        ),
        created_tick=tick,
        source_tick=tick,
        last_access_tick=tick,
        access_count=0,
    )


@pytest.mark.asyncio
async def test_owner_isolation_and_conflict_rejection() -> None:
    service = InMemoryMemoryService(
        MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
    )
    await service.apply(
        MemoryMutationBatch(writes=(_trace(memory_id="m-1", owner="agent-1"),))
    )
    with pytest.raises(MemoryServiceError) as exc:
        await service.apply(
            MemoryMutationBatch(writes=(_trace(memory_id="m-1", owner="agent-1"),))
        )
    assert exc.value.code is MemoryServiceErrorCode.CONFLICT
    with pytest.raises(MemoryServiceError) as exc2:
        await service.apply(
            MemoryMutationBatch(writes=(_trace(memory_id="m-2", owner="agent-2"),))
        )
    assert exc2.value.code is MemoryServiceErrorCode.OWNERSHIP


@pytest.mark.asyncio
async def test_cross_run_same_owner_ids_are_isolated() -> None:
    first = InMemoryMemoryService(
        MemoryScope(run_id=MemoryRunId("run-a"), owner_id=AgentId("agent-1"))
    )
    second = InMemoryMemoryService(
        MemoryScope(run_id=MemoryRunId("run-b"), owner_id=AgentId("agent-1"))
    )
    await first.apply(
        MemoryMutationBatch(writes=(_trace(memory_id="m-1", owner="agent-1"),))
    )
    await second.apply(
        MemoryMutationBatch(writes=(_trace(memory_id="m-1", owner="agent-1"),))
    )
    assert await first.get(MemoryId("m-1")) is not None
    assert await second.get(MemoryId("m-1")) is not None


@pytest.mark.asyncio
async def test_access_idempotent_and_forget() -> None:
    service = InMemoryMemoryService(
        MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
    )
    await service.apply(
        MemoryMutationBatch(writes=(_trace(memory_id="m-1", owner="agent-1"),))
    )
    receipt = MemoryAccessReceipt(
        memory_id=MemoryId("m-1"), access_tick=2, operation_id="op-1"
    )
    first = await service.apply(MemoryMutationBatch(accesses=(receipt,)))
    second = await service.apply(MemoryMutationBatch(accesses=(receipt,)))
    assert first.access_applied_count == 1
    assert second.access_idempotent_count == 1
    trace = await service.get(MemoryId("m-1"))
    assert trace is not None
    assert trace.access_count == 1

    policy = MemoryScoringPolicy(
        policy_id="default",
        version="1",
        weights=MemoryScoreWeights(recency=1.0),
    )
    result = await service.retrieve(
        MemoryRetrieveRequest(current_tick=2, limit=5, scoring_policy=policy)
    )
    assert result.candidate_count == 1
    forgotten = await service.forget(
        MemoryForgetRequest(
            current_tick=100,
            retention_policy=MemoryRetentionPolicy(
                policy_id="default",
                version="1",
                half_life_ticks=1,
                forget_threshold=0.5,
            ),
        )
    )
    assert forgotten.forgotten_count == 1
    active = await service.retrieve(
        MemoryRetrieveRequest(
            current_tick=100,
            limit=5,
            scoring_policy=policy,
            filters=MemoryQueryFilters(require_active=True),
        )
    )
    assert active.candidate_count == 0


@pytest.mark.asyncio
async def test_foreign_owner_adversarial_scores_do_not_leak() -> None:
    """Foreign higher scores with the same memory_id must not leak on retrieve."""
    policy = MemoryScoringPolicy(
        policy_id="default",
        version="1",
        weights=MemoryScoreWeights(emotional_salience=1.0, recency=1.0),
    )
    alice = InMemoryMemoryService(
        MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("alice"))
    )
    bob = InMemoryMemoryService(
        MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("bob"))
    )
    alice_trace = replace(
        _trace(memory_id="shared", owner="alice", tick=1),
        emotional_salience=0.1,
    )
    bob_trace = replace(
        _trace(memory_id="shared", owner="bob", tick=9),
        emotional_salience=1.0,
    )
    await alice.apply(MemoryMutationBatch(writes=(alice_trace,)))
    await bob.apply(MemoryMutationBatch(writes=(bob_trace,)))

    alice_hits = await alice.retrieve(
        MemoryRetrieveRequest(
            current_tick=10,
            scoring_policy=policy,
            filters=MemoryQueryFilters(),
            context=MemoryQueryContext(),
            limit=10,
        )
    )
    assert [hit.trace.memory_id.value for hit in alice_hits.hits] == ["shared"]
    assert alice_hits.hits[0].trace.owner_id.value == "alice"
    assert alice_hits.hits[0].trace.emotional_salience == 0.1
    assert await alice.get(MemoryId("shared")) is not None
    assert (await alice.get(MemoryId("shared"))).owner_id.value == "alice"  # type: ignore[union-attr]
    assert await bob.get(MemoryId("missing-for-alice")) is None


@pytest.mark.asyncio
async def test_atomic_batch_rejects_partial_writes() -> None:
    service = InMemoryMemoryService(
        MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
    )
    await service.apply(
        MemoryMutationBatch(writes=(_trace(memory_id="m-1", owner="agent-1"),))
    )
    with pytest.raises(MemoryServiceError) as exc:
        await service.apply(
            MemoryMutationBatch(
                writes=(
                    _trace(memory_id="m-2", owner="agent-1"),
                    _trace(memory_id="m-1", owner="agent-1"),
                )
            )
        )
    assert exc.value.code is MemoryServiceErrorCode.CONFLICT
    assert await service.get(MemoryId("m-2")) is None
