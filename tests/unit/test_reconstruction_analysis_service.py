"""Experiment analysis service joins objective and subjective evidence."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from analysis.memory_drift import evidence_from_reconstructed_memory
from analysis.models import ObjectiveLinkStatus, SubjectiveDerivationEdge
from analysis.service import MemoryDriftAnalysisService
from analysis.sources import InMemoryMemoryEvidenceSource, InMemoryObjectiveEventSource
from memory.models import (
    ConceptMention,
    MemoryId,
    MemoryLineage,
    MemoryProvenance,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
    ReconstructedMemory,
    ReconstructionId,
)
from world.events import Waited, make_replayable_event
from world.identifiers import EventId, RequestId, WorldId, WorldRevision

pytestmark = pytest.mark.unit


def _root(*, observed: str | None = "evt-1") -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId("m-root"),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(1),
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept="gate"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(tags=("yard",)),
        emotional_salience=0.5,
        confidence=0.9,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=1,
            observed_source_id=None if observed is None else EventId(observed),
        ),
        created_tick=1,
        source_tick=1,
        last_access_tick=1,
        access_count=0,
        lineage=MemoryLineage(),
    )


def _derived(root: MemoryTrace) -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId("m-derived"),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(1),
        concepts=(
            ConceptMention(mention_id=MentionId("c-1"), concept="gate"),
            ConceptMention(mention_id=MentionId("c-2"), concept="rust"),
        ),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=0.2,
        confidence=0.5,
        provenance=root.provenance,
        created_tick=2,
        source_tick=1,
        last_access_tick=2,
        access_count=0,
        lineage=MemoryLineage(
            supersedes_memory_id=root.memory_id,
            generation=1,
            source_memory_ids=(root.memory_id,),
            reconstruction_id=ReconstructionId("recon-1"),
        ),
    )


def test_analyze_memory_drift_reports_per_step_and_cumulative() -> None:
    root = _root()
    derived = _derived(root)
    reconstructed = ReconstructedMemory(
        reconstruction_id=ReconstructionId("recon-1"),
        owner_id=AgentId("agent-1"),
        narrative="gate with rust",
        concepts=derived.concepts,
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        confidence=0.5,
        emotional_salience=0.2,
        source_memory_ids=(root.memory_id,),
        generation=1,
        reconstructed_at_tick=2,
        policy_id="recall",
        policy_version="1",
        used_provider=False,
        fallback_used=False,
    )
    evidence = evidence_from_reconstructed_memory(
        run_id="run-1", reconstructed=reconstructed
    )
    event = make_replayable_event(
        event_id=EventId("evt-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=1,
        sequence=0,
        request_id=RequestId("r-1"),
        resulting_revision=WorldRevision(2),
        details=Waited(),
        actor_id=None,
    )
    service = MemoryDriftAnalysisService(
        memory=InMemoryMemoryEvidenceSource(
            traces=(root, derived),
            reconstructions=(evidence,),
            derivation_edges=(
                SubjectiveDerivationEdge(
                    derived_memory_id="m-derived",
                    source_memory_id="m-root",
                    ordinal=0,
                    reconstruction_id="recon-1",
                ),
            ),
        ),
        events=InMemoryObjectiveEventSource([event]),
    )
    report = service.analyze_memory_drift(
        experiment_id="exp-1",
        run_id="run-1",
        owner_id="agent-1",
    )
    assert report.linked_count == 1
    assert report.unlinked_count == 0
    assert len(report.chains) == 1
    assert len(report.steps) >= 2
    assert len(report.cumulative) == 1
    assert report.chains[0].objective_link is ObjectiveLinkStatus.LINKED
    assert any("rust" in step.delta.added_concepts for step in report.steps)
    assert "rust" in report.cumulative[0].added_concepts


def test_analyze_memory_drift_marks_missing_objective_unlinked(
    caplog: pytest.LogCaptureFixture,
) -> None:
    root = _root(observed="evt-missing")
    service = MemoryDriftAnalysisService(
        memory=InMemoryMemoryEvidenceSource(traces=(root,)),
        events=InMemoryObjectiveEventSource([]),
    )
    with caplog.at_level(logging.WARNING, logger="analysis.service"):
        report = service.analyze_memory_drift(
            experiment_id="exp-1",
            run_id="run-1",
            owner_id="agent-1",
        )
    assert report.unlinked_count == 1
    assert report.linked_count == 0
    assert report.chains[0].objective_link is ObjectiveLinkStatus.UNLINKED
    assert any(
        record.msg == "memory_drift_unlinked_source" for record in caplog.records
    )


def test_analyze_memory_drift_absent_source_is_not_invented() -> None:
    root = _root(observed=None)
    service = MemoryDriftAnalysisService(
        memory=InMemoryMemoryEvidenceSource(traces=(root,)),
        events=InMemoryObjectiveEventSource([]),
    )
    report = service.analyze_memory_drift(
        experiment_id="exp-1",
        run_id="run-1",
        owner_id="agent-1",
    )
    assert report.absent_source_count == 1
    assert report.chains[0].objective_link is ObjectiveLinkStatus.ABSENT
    assert report.chains[0].nodes[0].kind.value == "root_trace"
