"""Owner-bound memory, beliefs, and communication envelopes."""

from __future__ import annotations

from typing import Any

import pytest

from agents.models import AgentId, AgentState
from memory.models import (
    Belief,
    BeliefId,
    BeliefStore,
    MemoryId,
    MemoryRecord,
    MemoryStore,
    OwnershipError,
)
from social.models import CommunicationEnvelope, EnvelopeId
from world.identifiers import EntityId


def test_memory_snapshots_are_detached_and_owner_bound() -> None:
    owner = AgentId("agent-1")
    source: dict[str, Any] = {"text": "hello", "tags": ["a"]}
    store = MemoryStore(owner)
    store.write(MemoryRecord(memory_id=MemoryId("m-1"), owner_id=owner, content=source))
    source["tags"].append("b")
    snapshot = store.snapshot()
    assert snapshot[0].content["tags"] == ("a",)
    with pytest.raises(TypeError):
        snapshot[0].content["extra"] = "no"  # type: ignore[index]


def test_cross_owner_memory_write_fails() -> None:
    store = MemoryStore(AgentId("agent-1"))
    foreign = MemoryRecord(
        memory_id=MemoryId("m-1"),
        owner_id=AgentId("agent-2"),
        content={"text": "secret"},
    )
    with pytest.raises(OwnershipError, match="does not match"):
        store.write(foreign)


def test_owner_id_cannot_be_reassigned() -> None:
    store = MemoryStore(AgentId("agent-1"))
    with pytest.raises(AttributeError):
        store.owner_id = AgentId("agent-2")  # type: ignore[misc]
    record = MemoryRecord(
        memory_id=MemoryId("m-1"),
        owner_id=AgentId("agent-1"),
        content={},
    )
    with pytest.raises(AttributeError):
        record.owner_id = AgentId("agent-2")  # type: ignore[misc]


def test_memory_payloads_are_not_shared_across_stores() -> None:
    payload: dict[str, Any] = {"note": ["shared"]}
    first = MemoryStore(AgentId("agent-1"))
    second = MemoryStore(AgentId("agent-2"))
    first.write(
        MemoryRecord(
            memory_id=MemoryId("m-1"),
            owner_id=AgentId("agent-1"),
            content=payload,
        )
    )
    second.write(
        MemoryRecord(
            memory_id=MemoryId("m-2"),
            owner_id=AgentId("agent-2"),
            content=payload,
        )
    )
    payload["note"].append("mutated")
    assert first.snapshot()[0].content["note"] == ("shared",)
    assert second.snapshot()[0].content["note"] == ("shared",)


def test_belief_store_validates_owner() -> None:
    store = BeliefStore(AgentId("agent-1"))
    store.write(
        Belief(belief_id=BeliefId("b-1"), owner_id=AgentId("agent-1"), content={"k": 1})
    )
    with pytest.raises(OwnershipError):
        store.write(
            Belief(
                belief_id=BeliefId("b-2"),
                owner_id=AgentId("agent-2"),
                content={"k": 2},
            )
        )
    assert len(store.snapshot()) == 1


def test_envelope_rejects_agent_state_and_memory_records() -> None:
    owner = AgentId("agent-1")
    record = MemoryRecord(memory_id=MemoryId("m-1"), owner_id=owner, content={"t": "x"})
    with pytest.raises(TypeError, match="cannot contain"):
        CommunicationEnvelope(
            envelope_id=EnvelopeId("e-1"),
            sender_id=owner,
            recipient_id=AgentId("agent-2"),
            payload={"memory": record},
        )
    with pytest.raises(TypeError, match="cannot contain"):
        CommunicationEnvelope(
            envelope_id=EnvelopeId("e-2"),
            sender_id=owner,
            recipient_id=AgentId("agent-2"),
            payload={"state": AgentState(owner)},
        )


def test_envelope_payload_is_frozen_and_may_name_identities() -> None:
    source: dict[str, Any] = {"text": "hi", "about": ["topic"]}
    envelope = CommunicationEnvelope(
        envelope_id=EnvelopeId("e-1"),
        sender_id=AgentId("agent-1"),
        recipient_id=AgentId("agent-2"),
        payload={"text": "hi", "about": ["topic"], "entity": EntityId("ent-1")},
    )
    source["about"].append("extra")
    assert envelope.payload["about"] == ("topic",)
    assert envelope.payload["entity"] == EntityId("ent-1")
    with pytest.raises(TypeError):
        envelope.payload["text"] = "mutated"  # type: ignore[index]
