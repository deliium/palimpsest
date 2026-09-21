"""Owner-bound memory, beliefs, and communication envelopes."""

from __future__ import annotations

import pytest

from agents.models import Agent, AgentId
from memory.models import (
    ConceptMention,
    MemoryId,
    MemoryProvenance,
    MemorySituationContext,
    MemorySourceKind,
    MemoryStore,
    MemoryTrace,
    MentionId,
)
from social.models import CommunicationEnvelope, EnvelopeId
from world.identifiers import EntityId, WorldRevision


def _trace(
    *,
    memory_id: str = "m-1",
    owner: str = "agent-1",
    concept: str = "hello",
    tick: int = 0,
) -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId(owner),
        world_revision=WorldRevision(0),
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


def test_memory_snapshots_are_detached_and_owner_bound() -> None:
    owner = AgentId("agent-1")
    concepts = [ConceptMention(mention_id=MentionId("c-1"), concept="hello")]
    store = MemoryStore(owner)
    store.write(
        MemoryTrace(
            memory_id=MemoryId("m-1"),
            owner_id=owner,
            world_revision=WorldRevision(0),
            concepts=tuple(concepts),
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
    )
    concepts.clear()
    snapshot = store.snapshot()
    assert snapshot[0].concepts[0].concept == "hello"
    with pytest.raises(AttributeError):
        snapshot[0].concepts[0].concept = "mutated"  # type: ignore[misc]


def test_cross_owner_memory_write_fails() -> None:
    from memory.models import OwnershipError

    store = MemoryStore(AgentId("agent-1"))
    foreign = _trace(owner="agent-2", concept="secret")
    with pytest.raises(OwnershipError, match="does not match"):
        store.write(foreign)


def test_owner_id_cannot_be_reassigned() -> None:
    store = MemoryStore(AgentId("agent-1"))
    with pytest.raises(AttributeError):
        store.owner_id = AgentId("agent-2")  # type: ignore[misc]
    record = _trace()
    with pytest.raises(AttributeError):
        record.owner_id = AgentId("agent-2")  # type: ignore[misc]


def test_memory_payloads_are_not_shared_across_stores() -> None:
    first = MemoryStore(AgentId("agent-1"))
    second = MemoryStore(AgentId("agent-2"))
    first.write(_trace(memory_id="m-1", owner="agent-1", concept="shared"))
    second.write(_trace(memory_id="m-2", owner="agent-2", concept="shared"))
    assert first.snapshot()[0].concepts[0].concept == "shared"
    assert second.snapshot()[0].concepts[0].concept == "shared"
    assert first.snapshot()[0] is not second.snapshot()[0]


def test_envelope_rejects_agent_and_memory_traces() -> None:
    owner = AgentId("agent-1")
    record = _trace(owner=owner.value, concept="x")
    with pytest.raises(TypeError, match="unsupported domain content type"):
        CommunicationEnvelope(
            envelope_id=EnvelopeId("e-1"),
            sender_id=owner,
            recipient_id=AgentId("agent-2"),
            payload={"memory": record},
        )
    with pytest.raises(TypeError, match="unsupported domain content type"):
        CommunicationEnvelope(
            envelope_id=EnvelopeId("e-2"),
            sender_id=owner,
            recipient_id=AgentId("agent-2"),
            payload={"agent": Agent(agent_id=owner, name="Ada", goals=())},
        )


def test_envelope_payload_is_frozen_and_rejects_entity_wrappers() -> None:
    envelope = CommunicationEnvelope(
        envelope_id=EnvelopeId("e-1"),
        sender_id=AgentId("agent-1"),
        recipient_id=AgentId("agent-2"),
        payload={"text": "hi", "about": ["topic"]},
    )
    assert envelope.payload["about"] == ("topic",)
    with pytest.raises(TypeError):
        envelope.payload["text"] = "mutated"  # type: ignore[index]
    with pytest.raises(TypeError, match="unsupported domain content type"):
        CommunicationEnvelope(
            envelope_id=EnvelopeId("e-3"),
            sender_id=AgentId("agent-1"),
            recipient_id=AgentId("agent-2"),
            payload={"entity": EntityId("ent-1")},
        )
