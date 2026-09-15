"""Memory, belief, and relationship subjective models."""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agents.models import AgentId
from memory.models import (
    Belief,
    BeliefId,
    BeliefStore,
    MemoryId,
    MemoryStore,
    MemoryTrace,
    OwnershipError,
)
from social.models import Relationship, RelationshipId
from world.identifiers import WorldRevision

_AGENT_IDS = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=24,
)
_CONTENTS = st.dictionaries(
    keys=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N")),
        min_size=1,
        max_size=12,
    ),
    values=st.one_of(st.booleans(), st.integers(-100, 100), st.text(max_size=24)),
    max_size=3,
)


@given(owner=_AGENT_IDS, foreign=_AGENT_IDS, content=_CONTENTS)
@settings(max_examples=30, deadline=None)
def test_property_cross_owner_memory_write_fails(
    owner: str, foreign: str, content: dict[str, Any]
) -> None:
    if owner == foreign:
        return
    store = MemoryStore(AgentId(owner))
    record = MemoryTrace(
        memory_id=MemoryId("m-1"),
        owner_id=AgentId(foreign),
        world_revision=WorldRevision(0),
        content=content,
    )
    with pytest.raises(OwnershipError, match="does not match"):
        store.write(record)


def test_memory_store_preserves_insertion_order_and_last_write_wins() -> None:
    owner = AgentId("agent-1")
    store = MemoryStore(owner)
    store.write(
        MemoryTrace(
            memory_id=MemoryId("m-1"),
            owner_id=owner,
            world_revision=WorldRevision(0),
            content={"n": 1},
        )
    )
    store.write(
        MemoryTrace(
            memory_id=MemoryId("m-2"),
            owner_id=owner,
            world_revision=WorldRevision(1),
            content={"n": 2},
        )
    )
    store.write(
        MemoryTrace(
            memory_id=MemoryId("m-1"),
            owner_id=owner,
            world_revision=WorldRevision(2),
            content={"n": 3},
        )
    )
    snapshot = store.snapshot()
    assert [trace.memory_id for trace in snapshot] == [
        MemoryId("m-1"),
        MemoryId("m-2"),
    ]
    assert snapshot[0].content["n"] == 3
    assert snapshot[0].world_revision == WorldRevision(2)


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
