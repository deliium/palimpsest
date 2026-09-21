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
from tests.fakes.scripted_reconstructor import DriftEdit, ScriptedDriftReconstructor
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


@given(
    source_ids=st.lists(
        st.from_regex(r"m-[a-z0-9]{1,8}", fullmatch=True),
        min_size=1,
        max_size=5,
        unique=True,
    ),
    generation=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=40, deadline=None)
def test_derived_lineage_preserves_ordered_unique_sources(
    source_ids: list[str], generation: int
) -> None:
    from memory.models import MemoryLineage, ReconstructionId

    sources = tuple(MemoryId(item) for item in source_ids)
    lineage = MemoryLineage(
        supersedes_memory_id=sources[0],
        source_memory_ids=sources,
        generation=generation,
        reconstruction_id=ReconstructionId("recon-prop"),
    )
    assert lineage.source_memory_ids == sources
    assert lineage.supersedes_memory_id == sources[0]


_CONCEPT = st.from_regex(r"[a-z]{3,8}", fullmatch=True)
_EDIT = st.builds(
    DriftEdit,
    remove_concepts=st.frozensets(_CONCEPT, max_size=2),
    mutate_concepts=st.dictionaries(_CONCEPT, _CONCEPT, max_size=2),
    add_concepts=st.lists(_CONCEPT, max_size=2).map(tuple),
    remove_context_tags=st.frozensets(_CONCEPT, max_size=1),
    add_context_tags=st.lists(_CONCEPT, max_size=2).map(tuple),
    narrative_suffix=st.just(""),
    confidence_delta=st.floats(
        min_value=-0.2, max_value=0.0, allow_nan=False, allow_infinity=False
    ),
    salience_delta=st.floats(
        min_value=-0.2, max_value=0.0, allow_nan=False, allow_infinity=False
    ),
)


@given(edits=st.lists(_EDIT, min_size=1, max_size=4))
@settings(max_examples=30, deadline=None)
def test_bounded_edit_sequences_are_deterministic_and_measurable(
    edits: list[DriftEdit],
) -> None:
    from analysis.memory_drift import compare_fact_sets, project_reconstructed_memory
    from analysis.models import FactAvailability, StructuredFactSet
    from memory.models import (
        MemoryRecallContext,
        MemoryReconstructionPolicy,
        MemorySourceKind,
        RecallEvidence,
        RecallSourceEvidence,
        ReconstructionId,
    )

    async def _run() -> None:
        reconstructor = ScriptedDriftReconstructor(edits)
        evidence = RecallEvidence(
            owner_id=AgentId("agent-1"),
            current_tick=3,
            reconstruction_id=ReconstructionId("recon-prop"),
            policy=MemoryReconstructionPolicy(policy_id="recall", version="1"),
            sources=(
                RecallSourceEvidence(
                    memory_id=MemoryId("m-1"),
                    owner_id=AgentId("agent-1"),
                    rank=1,
                    score=1.0,
                    concepts=(
                        ConceptMention(mention_id=MentionId("c-1"), concept="alpha"),
                        ConceptMention(mention_id=MentionId("c-2"), concept="beta"),
                    ),
                    entities=(),
                    relations=(),
                    context=MemorySituationContext(tags=("tag",)),
                    emotional_salience=0.5,
                    confidence=0.8,
                    source_confidence=0.8,
                    episode_age_ticks=0,
                    storage_age_ticks=0,
                    generation=0,
                    provenance_kind=MemorySourceKind.DIRECT_OBSERVATION,
                ),
            ),
            beliefs=(),
            recall_context=MemoryRecallContext(),
        )
        first = await reconstructor.reconstruct(evidence)
        reconstructor.reset()
        second = await reconstructor.reconstruct(evidence)
        assert first.concepts == second.concepts
        assert first.confidence == second.confidence
        assert first.narrative == second.narrative
        before = StructuredFactSet(
            concepts=frozenset({"alpha", "beta"}),
            entity_ids=frozenset(),
            entity_labels=frozenset(),
            relations=frozenset(),
            context_tags=frozenset({"tag"}),
            location_id=None,
            confidence=0.8,
            salience=0.5,
            narrative_fingerprint=None,
            availability=FactAvailability.PRESENT,
            projector_version="1",
        )
        after = project_reconstructed_memory(first)
        delta = compare_fact_sets(before, after)
        expected = reconstructor.expected_episode_after(evidence, steps=1)
        assert set(expected.concepts) == set(after.concepts)
        assert delta.comparison_status.value == "complete"

    __import__("asyncio").run(_run())
