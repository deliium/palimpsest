"""Provenance ledger writes and channel carry helpers."""

from __future__ import annotations

import pytest

from agents.cognition.configuration import build_cognitive_loop
from agents.cognition.developmental_learning import (
    DevelopmentalDomainId,
    DevelopmentalKnowledgeEntry,
    DevelopmentalKnowledgeLedger,
    DevelopmentalSourceId,
    empty_developmental_knowledge_ledger,
    upsert_developmental_entry,
)
from agents.cognition.models import SubjectiveSnapshot
from agents.models import AgentId
from simulation.agent_runtime import AgentRuntime
from simulation.runner_models import example_developmental_learning_spec


def _entry(
    *,
    concept: str = "loc:alpha",
    tick: int = 1,
) -> DevelopmentalKnowledgeEntry:
    return DevelopmentalKnowledgeEntry(
        domain_id=DevelopmentalDomainId.LOCATIONS,
        concept_key=concept,
        source_id=DevelopmentalSourceId.OBSERVATION,
        confidence=0.5,
        acquired_tick=tick,
        evidence_refs=(f"evt:{tick}",),
    )


def test_upsert_rejects_empty_evidence() -> None:
    with pytest.raises(ValueError, match="provenance_required"):
        DevelopmentalKnowledgeEntry(
            domain_id=DevelopmentalDomainId.LOCATIONS,
            concept_key="loc:x",
            source_id=DevelopmentalSourceId.OBSERVATION,
            confidence=0.1,
            acquired_tick=0,
            evidence_refs=(),
        )


def test_upsert_and_deterministic_eviction() -> None:
    owner = AgentId("learner-evict")
    ledger = empty_developmental_knowledge_ledger(owner, max_entries_per_domain=2)
    ledger = upsert_developmental_entry(ledger, _entry(concept="a", tick=1))
    ledger = upsert_developmental_entry(ledger, _entry(concept="b", tick=2))
    ledger = upsert_developmental_entry(ledger, _entry(concept="c", tick=3))
    keys = {row.concept_key for row in ledger.entries}
    assert keys == {"b", "c"}


def test_twin_run_ledger_bytes_identical() -> None:
    owner = AgentId("twin")
    a = empty_developmental_knowledge_ledger(owner, max_entries_per_domain=8)
    b = empty_developmental_knowledge_ledger(owner, max_entries_per_domain=8)
    for tick, concept in enumerate(("x", "y", "z"), start=1):
        entry = _entry(concept=concept, tick=tick)
        a = upsert_developmental_entry(a, entry)
        b = upsert_developmental_entry(b, entry)
    assert a.entries == b.entries


def test_loop_prepare_carries_empty_ledger_when_channel_on() -> None:
    from types import SimpleNamespace

    spec = example_developmental_learning_spec()
    loop = build_cognitive_loop(developmental_learning_spec=spec)
    owner = AgentId("carry-1")
    snapshot = SubjectiveSnapshot(
        owner_id=owner,
        revision=0,
        memories=(),
        legacy_beliefs=(),
        semantic_beliefs=(),
    )
    loop_input = SimpleNamespace(
        agent_id=owner,
        snapshot=snapshot,
        observation=SimpleNamespace(tick=0),
    )
    prepared = loop._prepare_developmental_knowledge(loop_input)  # type: ignore[arg-type]
    assert type(prepared) is DevelopmentalKnowledgeLedger
    assert prepared.entries == ()
    assert prepared.owner_id == owner


def test_loop_prepare_channel_off_returns_none() -> None:
    from types import SimpleNamespace

    loop = build_cognitive_loop()
    owner = AgentId("off-1")
    loop_input = SimpleNamespace(
        agent_id=owner,
        snapshot=None,
        observation=object(),
    )
    assert loop._prepare_developmental_knowledge(loop_input) is None  # type: ignore[arg-type]


def test_runtime_commit_developmental_knowledge() -> None:
    owner = AgentId("rt-1")
    ledger = upsert_developmental_entry(
        empty_developmental_knowledge_ledger(owner), _entry()
    )

    class _Agent:
        agent_id = owner

    class _Loop:
        _developmental_learning_spec = example_developmental_learning_spec()

    class _StandIn:
        def __init__(self) -> None:
            self._agent = _Agent()
            self._loop = _Loop()
            self._developmental_knowledge = None

    stand = _StandIn()
    AgentRuntime._commit_developmental_knowledge(stand, ledger, 3)  # type: ignore[arg-type]
    assert stand._developmental_knowledge is ledger

    off = _StandIn()
    off._loop._developmental_learning_spec = None  # type: ignore[attr-defined]
    AgentRuntime._commit_developmental_knowledge(off, ledger, 3)  # type: ignore[arg-type]
    assert off._developmental_knowledge is None
