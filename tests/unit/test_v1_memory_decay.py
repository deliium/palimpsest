"""Deterministic retention decay and soft-forget tests."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from memory.models import (
    ConceptMention,
    MemoryId,
    MemoryProvenance,
    MemoryRetentionPolicy,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
)
from memory.scoring import retention_strength, should_forget
from world.identifiers import WorldRevision


def _trace(*, created_tick: int = 0, expires: int | None = None) -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId("m-1"),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(0),
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept="note"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=0.0,
        confidence=1.0,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=created_tick,
        ),
        created_tick=created_tick,
        source_tick=created_tick,
        last_access_tick=created_tick,
        access_count=0,
        expires_at_tick=expires,
    )


def test_retention_half_life_boundaries() -> None:
    assert retention_strength(
        created_tick=0, current_tick=0, half_life_ticks=10
    ) == pytest.approx(1.0)
    assert retention_strength(
        created_tick=0, current_tick=10, half_life_ticks=10
    ) == pytest.approx(0.5)
    assert retention_strength(
        created_tick=0, current_tick=20, half_life_ticks=10
    ) == pytest.approx(0.25)


def test_should_forget_threshold_and_expiry() -> None:
    policy = MemoryRetentionPolicy(
        policy_id="default",
        version="1",
        half_life_ticks=10,
        forget_threshold=0.3,
    )
    fresh = _trace(created_tick=0)
    assert should_forget(fresh, current_tick=5, policy=policy) is False
    assert should_forget(fresh, current_tick=30, policy=policy) is True
    expired = _trace(created_tick=0, expires=4)
    assert should_forget(expired, current_tick=4, policy=policy) is True
