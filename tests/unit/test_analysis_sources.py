"""In-memory evidence sources enforce run/owner scope on derivation edges."""

from __future__ import annotations

import pytest

from analysis.evidence import EvidenceStage, ScopedMemoryTrace
from analysis.models import SubjectiveDerivationEdge
from analysis.sources import (
    InMemoryMemoryEvidenceSource,
    ManifestConstrainedMemoryEvidenceSource,
)
from memory.models import (
    AgentId,
    ConceptMention,
    MemoryId,
    MemoryProvenance,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
)
from simulation.evidence import EvidenceHighWaterMarks, build_evidence_manifest
from world.identifiers import EntityId, WorldRevision


def _trace(*, memory_id: str, owner_id: str, kind: MemorySourceKind) -> MemoryTrace:
    speaker = None
    if kind is MemorySourceKind.COMMUNICATED:
        speaker = EntityId("body-speaker")
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId(owner_id),
        world_revision=WorldRevision(1),
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept="gate"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(tags=()),
        emotional_salience=0.1,
        confidence=0.9,
        provenance=MemoryProvenance(
            kind=kind,
            source_tick=0,
            speaker_id=speaker,
        ),
        created_tick=0,
        source_tick=0,
        last_access_tick=0,
        access_count=0,
    )


def test_derivation_edges_are_filtered_by_run_and_owner() -> None:
    edge_a = SubjectiveDerivationEdge(
        run_id="run-a",
        owner_id="agent-1",
        derived_memory_id="m-2",
        source_memory_id="m-1",
        ordinal=0,
    )
    edge_b = SubjectiveDerivationEdge(
        run_id="run-b",
        owner_id="agent-1",
        derived_memory_id="m-4",
        source_memory_id="m-3",
        ordinal=0,
    )
    edge_other_owner = SubjectiveDerivationEdge(
        run_id="run-a",
        owner_id="agent-2",
        derived_memory_id="m-6",
        source_memory_id="m-5",
        ordinal=0,
    )
    source = InMemoryMemoryEvidenceSource(
        derivation_edges=(edge_a, edge_b, edge_other_owner)
    )
    assert source.derivation_edges(run_id="run-a", owner_id="agent-1") == (edge_a,)
    assert source.derivation_edges(run_id="run-b", owner_id="agent-1") == (edge_b,)
    assert source.derivation_edges(run_id="run-a", owner_id="agent-2") == (
        edge_other_owner,
    )
    assert source.derivation_edges(run_id="run-missing", owner_id="agent-1") == ()


def test_subjective_derivation_edge_requires_scope_fields() -> None:
    with pytest.raises(TypeError):
        SubjectiveDerivationEdge(  # type: ignore[call-arg]
            derived_memory_id="m-2",
            source_memory_id="m-1",
            ordinal=0,
        )


def test_scoped_traces_filter_by_run_and_owner() -> None:
    trace = _trace(
        memory_id="m-1",
        owner_id="agent-1",
        kind=MemorySourceKind.DIRECT_OBSERVATION,
    )
    scoped = ScopedMemoryTrace(
        run_id="run-a",
        owner_id="agent-1",
        evidence_stage=EvidenceStage.DIRECT_TRACE,
        trace=trace,
    )
    other = ScopedMemoryTrace(
        run_id="run-b",
        owner_id="agent-1",
        evidence_stage=EvidenceStage.DIRECT_TRACE,
        trace=_trace(
            memory_id="m-2",
            owner_id="agent-1",
            kind=MemorySourceKind.DIRECT_OBSERVATION,
        ),
    )
    source = InMemoryMemoryEvidenceSource(scoped_traces=(scoped, other))
    assert source.traces(run_id="run-a", owner_id="agent-1") == (trace,)
    assert source.traces(run_id="run-b", owner_id="agent-1")[0].memory_id.value == "m-2"
    assert source.traces(run_id="run-a", owner_id="agent-2") == ()


def test_manifest_constrained_memory_source_clamps_direct_traces() -> None:
    traces = (
        _trace(
            memory_id="m-1",
            owner_id="agent-1",
            kind=MemorySourceKind.DIRECT_OBSERVATION,
        ),
        _trace(
            memory_id="m-2",
            owner_id="agent-1",
            kind=MemorySourceKind.DIRECT_OBSERVATION,
        ),
        _trace(
            memory_id="m-3",
            owner_id="agent-1",
            kind=MemorySourceKind.COMMUNICATED,
        ),
    )
    scoped = tuple(
        ScopedMemoryTrace(
            run_id="run-a",
            owner_id="agent-1",
            evidence_stage=EvidenceStage.DIRECT_TRACE,
            trace=trace,
        )
        for trace in traces
    )
    inner = InMemoryMemoryEvidenceSource(scoped_traces=scoped)
    manifest = build_evidence_manifest(
        run_id="run-a",
        objective_commit_hash="a" * 64,
        high_water=EvidenceHighWaterMarks(
            direct_memories=1,
            communicated_memories=1,
            reconstructions=0,
            beliefs=0,
            relationships=0,
            goals=0,
            resolutions=0,
            truth_specs=0,
        ),
    )
    constrained = ManifestConstrainedMemoryEvidenceSource(inner, manifest)
    result = constrained.traces(run_id="run-a", owner_id="agent-1")
    assert [item.memory_id.value for item in result] == ["m-1", "m-3"]
