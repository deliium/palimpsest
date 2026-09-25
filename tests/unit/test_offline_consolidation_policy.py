"""Deterministic offline episodic consolidation policy."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from memory.consolidation import plan_offline_consolidation
from memory.models import (
    ConceptMention,
    MemoryId,
    MemoryProvenance,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
    default_offline_consolidation_policy,
)
from world.identifiers import EntityId, WorldRevision

_OWNER = AgentId("agent-1")


def _trace(
    *,
    memory_id: str,
    concepts: tuple[str, ...],
    confidence: float = 0.9,
    salience: float = 0.6,
    created_tick: int = 0,
    access_count: int = 1,
    owner: str = "agent-1",
    communicated: bool = False,
) -> MemoryTrace:
    mentions = tuple(
        ConceptMention(mention_id=MentionId(f"{memory_id}-c{index}"), concept=concept)
        for index, concept in enumerate(concepts)
    )
    if communicated:
        provenance = MemoryProvenance(
            kind=MemorySourceKind.COMMUNICATED,
            source_tick=created_tick,
            speaker_id=EntityId("speaker-1"),
        )
    else:
        provenance = MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=created_tick,
        )
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId(owner),
        world_revision=WorldRevision(0),
        concepts=mentions,
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=salience,
        confidence=confidence,
        provenance=provenance,
        created_tick=created_tick,
        source_tick=created_tick,
        last_access_tick=created_tick,
        access_count=access_count,
    )


def test_identical_inputs_select_identically() -> None:
    traces = (
        _trace(memory_id="m-b", concepts=("path", "water", "night", "only-b")),
        _trace(memory_id="m-a", concepts=("path", "water", "night", "only-a")),
    )
    policy = default_offline_consolidation_policy()
    first = plan_offline_consolidation(
        owner_id=_OWNER, tick=2, traces=traces, policy=policy
    )
    second = plan_offline_consolidation(
        owner_id=_OWNER, tick=2, traces=tuple(reversed(traces)), policy=policy
    )
    assert first[1] == second[1]


def test_similar_episodes_merge_gist_and_belief_candidate() -> None:
    left = _trace(memory_id="m-a", concepts=("path", "water", "night", "only-a"))
    right = _trace(memory_id="m-b", concepts=("path", "water", "night", "only-b"))
    _candidate, selection = plan_offline_consolidation(
        owner_id=_OWNER,
        tick=2,
        traces=(left, right),
        policy=default_offline_consolidation_policy(),
    )
    assert len(selection.merge_groups) == 1
    assert len(selection.derived_traces) == 1
    gist = selection.derived_traces[0]
    gist_concepts = {item.concept for item in gist.concepts}
    assert gist_concepts == {"path", "water", "night"}
    assert "only-a" not in gist_concepts
    assert "only-b" not in gist_concepts
    assert gist.lineage.generation == 1
    assert gist.lineage.source_memory_ids == (MemoryId("m-a"), MemoryId("m-b"))
    assert left.memory_id not in selection.soft_forget_ids
    assert selection.belief_source_ids == (MemoryId("m-a"), MemoryId("m-b"))
    assert left.forgotten_at_tick is None
    assert right.forgotten_at_tick is None


def test_low_retention_trace_is_selected_for_soft_forget() -> None:
    stale = _trace(
        memory_id="m-old",
        concepts=("dust",),
        confidence=0.01,
        salience=0.0,
        created_tick=0,
        access_count=0,
    )
    _candidate, selection = plan_offline_consolidation(
        owner_id=_OWNER,
        tick=40,
        traces=(stale,),
        policy=default_offline_consolidation_policy(),
    )
    assert selection.soft_forget_ids == (stale.memory_id,)
    assert selection.derived_traces == ()
    assert selection.merge_groups == ()
    assert stale.concepts[0].concept == "dust"


def test_isolated_false_memory_is_not_rewritten() -> None:
    false = _trace(
        memory_id="m-false",
        concepts=("the-well-is-dry",),
        communicated=True,
    )
    _candidate, selection = plan_offline_consolidation(
        owner_id=_OWNER,
        tick=1,
        traces=(false,),
        policy=default_offline_consolidation_policy(),
    )
    assert selection.derived_traces == ()
    assert selection.merge_groups == ()
    assert selection.belief_source_ids == ()
    assert false.concepts[0].concept == "the-well-is-dry"
    assert false.provenance.kind is MemorySourceKind.COMMUNICATED


def test_foreign_owner_is_rejected() -> None:
    foreign = _trace(memory_id="m-x", concepts=("gate",), owner="agent-2")
    with pytest.raises(ValueError, match="owner_mismatch"):
        plan_offline_consolidation(
            owner_id=_OWNER,
            tick=1,
            traces=(foreign,),
            policy=default_offline_consolidation_policy(),
        )
