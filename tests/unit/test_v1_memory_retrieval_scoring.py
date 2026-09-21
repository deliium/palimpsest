"""Deterministic episodic memory scoring tests."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from memory.models import (
    AccessHistoryMode,
    ConceptMention,
    EntityMention,
    MemoryEmbedding,
    MemoryId,
    MemoryProvenance,
    MemoryQueryContext,
    MemoryQueryFilters,
    MemoryScoreWeights,
    MemoryScoringPolicy,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
)
from memory.scoring import cosine_similarity, matches_filters, rank_traces
from world.identifiers import EntityId, WorldRevision


def _trace(
    *,
    memory_id: str,
    created_tick: int,
    salience: float = 0.0,
    access_count: int = 0,
    concept: str = "gate",
    location: str | None = None,
    entity: str | None = None,
    embedding: MemoryEmbedding | None = None,
) -> MemoryTrace:
    entities = ()
    if entity is not None:
        entities = (
            EntityMention(
                mention_id=MentionId("e-1"),
                label="body",
                entity_id=EntityId(entity),
            ),
        )
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(0),
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept=concept),),
        entities=entities,
        relations=(),
        context=MemorySituationContext(
            location_id=None if location is None else EntityId(location),
            tags=("camp",),
        ),
        emotional_salience=salience,
        confidence=1.0,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=created_tick,
        ),
        created_tick=created_tick,
        source_tick=created_tick,
        last_access_tick=created_tick,
        access_count=access_count,
        embedding=embedding,
    )


def test_cosine_similarity_known_vectors() -> None:
    assert cosine_similarity((1.0, 0.0), (1.0, 0.0)) == pytest.approx(1.0)
    assert cosine_similarity((1.0, 0.0), (-1.0, 0.0)) == pytest.approx(0.0)
    assert cosine_similarity((1.0, 0.0), (0.0, 1.0)) == pytest.approx(0.5)


def test_structured_filters_before_limit() -> None:
    traces = (
        _trace(memory_id="m-old", created_tick=0, concept="gate"),
        _trace(memory_id="m-new", created_tick=5, concept="gate"),
        _trace(memory_id="m-other", created_tick=9, concept="river"),
    )
    policy = MemoryScoringPolicy(
        policy_id="default",
        version="1",
        weights=MemoryScoreWeights(recency=1.0),
    )
    hits, candidates = rank_traces(
        traces,
        policy=policy,
        current_tick=10,
        filters=MemoryQueryFilters(concepts=("gate",)),
        context=MemoryQueryContext(),
        query_embedding=None,
        embeddings=None,
        limit=1,
    )
    assert candidates == 2
    assert len(hits) == 1
    assert hits[0].trace.memory_id.value == "m-new"


def test_score_components_and_tie_break() -> None:
    policy = MemoryScoringPolicy(
        policy_id="default",
        version="1",
        weights=MemoryScoreWeights(
            recency=1.0,
            emotional_salience=1.0,
            access_history=1.0,
        ),
        access_history_mode=AccessHistoryMode.NOVELTY,
    )
    traces = (
        _trace(memory_id="m-b", created_tick=5, salience=1.0, access_count=0),
        _trace(memory_id="m-a", created_tick=5, salience=1.0, access_count=0),
    )
    hits, _ = rank_traces(
        traces,
        policy=policy,
        current_tick=5,
        filters=MemoryQueryFilters(),
        context=MemoryQueryContext(),
        query_embedding=None,
        embeddings=None,
        limit=10,
    )
    assert [hit.trace.memory_id.value for hit in hits] == ["m-a", "m-b"]


def test_semantic_ranking_uses_embeddings() -> None:
    policy = MemoryScoringPolicy(
        policy_id="default",
        version="1",
        weights=MemoryScoreWeights(semantic_relevance=1.0),
        embedding_dimension=2,
    )
    near = MemoryEmbedding(vector=(1.0, 0.0), model="fake", version="1")
    far = MemoryEmbedding(vector=(0.0, 1.0), model="fake", version="1")
    traces = (
        _trace(memory_id="m-far", created_tick=0, embedding=far),
        _trace(memory_id="m-near", created_tick=0, embedding=near),
    )
    hits, _ = rank_traces(
        traces,
        policy=policy,
        current_tick=0,
        filters=MemoryQueryFilters(),
        context=MemoryQueryContext(),
        query_embedding=near,
        embeddings={
            "m-far": far,
            "m-near": near,
        },
        limit=2,
    )
    assert hits[0].trace.memory_id.value == "m-near"


def test_matches_filters_require_active() -> None:
    forgotten = _trace(memory_id="m-1", created_tick=0)
    from dataclasses import replace

    forgotten = replace(forgotten, forgotten_at_tick=3)
    assert matches_filters(forgotten, MemoryQueryFilters(require_active=True)) is False
    assert matches_filters(forgotten, MemoryQueryFilters(require_active=False)) is True
