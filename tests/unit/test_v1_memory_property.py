"""Hypothesis proofs for episodic memory scoring determinism."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agents.models import AgentId
from memory.models import (
    ConceptMention,
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
    quantize_score,
)
from memory.scoring import rank_traces
from world.identifiers import WorldRevision

pytestmark = pytest.mark.unit


def _trace(memory_id: str, *, tick: int, salience: float) -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(0),
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept="signal"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=salience,
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


@given(
    ticks=st.lists(st.integers(min_value=0, max_value=50), min_size=2, max_size=6),
    saliences=st.lists(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=2,
        max_size=6,
    ),
)
@settings(max_examples=40, deadline=None)
def test_rank_traces_is_insertion_order_independent(
    ticks: list[int], saliences: list[float]
) -> None:
    n = min(len(ticks), len(saliences))
    traces = tuple(
        _trace(f"m-{index}", tick=ticks[index], salience=saliences[index])
        for index in range(n)
    )
    policy = MemoryScoringPolicy(
        policy_id="prop",
        version="1",
        weights=MemoryScoreWeights(recency=1.0, emotional_salience=1.0),
    )
    forward, count_a = rank_traces(
        traces,
        policy=policy,
        current_tick=max(ticks[:n]) + 1,
        filters=MemoryQueryFilters(),
        context=MemoryQueryContext(),
        query_embedding=None,
        embeddings={},
        limit=n,
    )
    reverse, count_b = rank_traces(
        tuple(reversed(traces)),
        policy=policy,
        current_tick=max(ticks[:n]) + 1,
        filters=MemoryQueryFilters(),
        context=MemoryQueryContext(),
        query_embedding=None,
        embeddings={},
        limit=n,
    )
    assert count_a == count_b == n
    assert [hit.trace.memory_id.value for hit in forward] == [
        hit.trace.memory_id.value for hit in reverse
    ]
    assert [hit.score for hit in forward] == [hit.score for hit in reverse]


@given(
    value=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=50, deadline=None)
def test_quantize_score_is_idempotent(value: float) -> None:
    once = quantize_score(value)
    assert once == quantize_score(once)
    assert 0.0 <= once <= 1.0
