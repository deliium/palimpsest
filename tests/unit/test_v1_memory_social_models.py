"""Memory, belief, and relationship subjective models."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agents.models import AgentId
from memory.models import (
    Belief,
    BeliefId,
    BeliefStore,
    ConceptMention,
    MemoryId,
    MemoryProvenance,
    MemorySituationContext,
    MemorySourceKind,
    MemoryStore,
    MemoryTrace,
    MentionId,
    OwnershipError,
)
from social.models import Relationship, RelationshipId
from world.identifiers import WorldRevision

_AGENT_IDS = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=24,
)
_CONCEPTS = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=12,
)


def _trace(
    *,
    memory_id: str = "m-1",
    owner: str = "agent-1",
    revision: int = 0,
    concept: str = "note",
    tick: int = 0,
) -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId(owner),
        world_revision=WorldRevision(revision),
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept=concept),),
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


@given(owner=_AGENT_IDS, foreign=_AGENT_IDS, concept=_CONCEPTS)
@settings(max_examples=30, deadline=None)
def test_property_cross_owner_memory_write_fails(
    owner: str, foreign: str, concept: str
) -> None:
    if owner == foreign:
        return
    store = MemoryStore(AgentId(owner))
    record = _trace(owner=foreign, concept=concept)
    with pytest.raises(OwnershipError, match="does not match"):
        store.write(record)


def test_memory_store_preserves_insertion_order_and_last_write_wins() -> None:
    owner = AgentId("agent-1")
    store = MemoryStore(owner)
    store.write(_trace(memory_id="m-1", revision=0, concept="one", tick=0))
    store.write(_trace(memory_id="m-2", revision=1, concept="two", tick=1))
    store.write(_trace(memory_id="m-1", revision=2, concept="three", tick=2))
    snapshot = store.snapshot()
    assert [trace.memory_id for trace in snapshot] == [
        MemoryId("m-1"),
        MemoryId("m-2"),
    ]
    assert snapshot[0].concepts[0].concept == "three"
    assert snapshot[0].world_revision == WorldRevision(2)


def test_memory_trace_rejects_duplicate_and_overlapping_mention_ids() -> None:
    with pytest.raises(ValueError, match="duplicate_mention_id"):
        MemoryTrace(
            memory_id=MemoryId("m-1"),
            owner_id=AgentId("agent-1"),
            world_revision=WorldRevision(0),
            concepts=(
                ConceptMention(mention_id=MentionId("c-1"), concept="a"),
                ConceptMention(mention_id=MentionId("c-1"), concept="b"),
            ),
            entities=(),
            relations=(),
            context=MemorySituationContext(),
            emotional_salience=0.0,
            confidence=1.0,
            provenance=MemoryProvenance(
                kind=MemorySourceKind.DIRECT_OBSERVATION,
                source_tick=0,
            ),
            created_tick=0,
            source_tick=0,
            last_access_tick=0,
            access_count=0,
        )


def test_memory_trace_repr_omits_payload_text() -> None:
    trace = _trace(concept="secret-label")
    rendered = repr(trace)
    assert "secret-label" not in rendered
    assert "concept_count=1" in rendered


def test_belief_requires_confidence_and_evidence_tuple() -> None:
    belief = Belief(
        belief_id=BeliefId("b-1"),
        owner_id=AgentId("agent-1"),
        proposition="the gate is open",
        confidence=0.5,
        evidence_memory_ids=(MemoryId("m-1"),),
    )
    assert belief.evidence_memory_ids == (MemoryId("m-1"),)
    with pytest.raises(ValueError, match=r"\[0.0, 1.0\]"):
        Belief(
            belief_id=BeliefId("b-1"),
            owner_id=AgentId("agent-1"),
            proposition="x",
            confidence=2.0,
            evidence_memory_ids=(),
        )
    with pytest.raises(TypeError, match="ordered sequence"):
        Belief(
            belief_id=BeliefId("b-1"),
            owner_id=AgentId("agent-1"),
            proposition="x",
            confidence=0.1,
            evidence_memory_ids={MemoryId("m-1")},  # type: ignore[arg-type]
        )


def test_relationship_rejects_self_links_and_invalid_affinity() -> None:
    with pytest.raises(ValueError, match="cannot link an agent to itself"):
        Relationship(
            relationship_id=RelationshipId("rel-1"),
            source_id=AgentId("agent-1"),
            target_id=AgentId("agent-1"),
            kind="ally",
            affinity=0.5,
        )
    with pytest.raises(ValueError, match=r"\[-1.0, 1.0\]"):
        Relationship(
            relationship_id=RelationshipId("rel-1"),
            source_id=AgentId("agent-1"),
            target_id=AgentId("agent-2"),
            kind="ally",
            affinity=1.5,
        )


def test_belief_store_validates_owner() -> None:
    store = BeliefStore(AgentId("agent-1"))
    store.write(
        Belief(
            belief_id=BeliefId("b-1"),
            owner_id=AgentId("agent-1"),
            proposition="safe",
            confidence=0.9,
            evidence_memory_ids=(),
        )
    )
    with pytest.raises(OwnershipError):
        store.write(
            Belief(
                belief_id=BeliefId("b-2"),
                owner_id=AgentId("agent-2"),
                proposition="unsafe",
                confidence=0.1,
                evidence_memory_ids=(),
            )
        )
    assert len(store.snapshot()) == 1
