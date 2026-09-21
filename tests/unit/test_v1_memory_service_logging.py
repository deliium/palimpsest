"""Metadata-only logging proofs for the in-memory MemoryService boundary."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from memory.models import (
    ConceptMention,
    MemoryId,
    MemoryMutationBatch,
    MemoryProvenance,
    MemoryQueryContext,
    MemoryQueryFilters,
    MemoryRetrieveRequest,
    MemoryRunId,
    MemoryScope,
    MemoryScoreWeights,
    MemoryScoringPolicy,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
    diagnostic_projection,
)
from memory.service import InMemoryMemoryService, MemoryServiceError
from world.identifiers import WorldRevision

pytestmark = pytest.mark.unit


def _trace(*, memory_id: str = "m-1", concept: str = "campfire") -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(0),
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept=concept),),
        entities=(),
        relations=(),
        context=MemorySituationContext(tags=("night",)),
        emotional_salience=0.4,
        confidence=0.8,
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
async def test_memory_service_logs_are_metadata_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = InMemoryMemoryService(
        MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
    )
    policy = MemoryScoringPolicy(
        policy_id="default",
        version="1",
        weights=MemoryScoreWeights(recency=1.0),
    )
    secret_concept = "secret-campfire-fragment"
    with caplog.at_level(logging.DEBUG, logger="memory.service"):
        await service.apply(
            MemoryMutationBatch(writes=(_trace(concept=secret_concept),))
        )
        await service.retrieve(
            MemoryRetrieveRequest(
                current_tick=2,
                scoring_policy=policy,
                filters=MemoryQueryFilters(concepts=(secret_concept,)),
                context=MemoryQueryContext(tags=("night",)),
                limit=5,
            )
        )
        with pytest.raises(MemoryServiceError):
            await service.apply(
                MemoryMutationBatch(writes=(_trace(memory_id="m-1", concept="dup"),))
            )

    blob = "\n".join(
        f"{record.getMessage()} {record.__dict__}" for record in caplog.records
    )
    assert "memory_retrieve_complete" in blob
    assert "memory_apply" in blob
    assert secret_concept not in blob
    assert "night" not in blob
    assert "vector" not in blob.lower()
    assert "[0." not in blob


def test_diagnostic_projection_rejects_payload_keys() -> None:
    safe = diagnostic_projection(
        {
            "operation": "retrieve",
            "run_id": "run-1",
            "owner_id": "agent-1",
            "tick": 2,
            "candidate_count": 1,
            "result_count": 1,
            "enabled_components": ["recency"],
        }
    )
    assert safe["operation"] == "retrieve"
    with pytest.raises(ValueError, match="disallowed_key"):
        diagnostic_projection({"operation": "retrieve", "query_text": "campfire"})
    with pytest.raises(ValueError, match="disallowed_key"):
        diagnostic_projection({"embedding": [0.1, 0.2]})
