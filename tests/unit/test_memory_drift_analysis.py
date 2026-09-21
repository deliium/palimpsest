"""Pure memory-drift projection and comparison tests."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from analysis.memory_drift import (
    build_reconstruction_chains,
    compare_fact_sets,
    evidence_from_reconstructed_memory,
    project_memory_trace,
    project_world_event,
    resolve_objective_link,
)
from analysis.models import (
    ComparisonStatus,
    FactAvailability,
    ObjectiveLinkStatus,
    SubjectiveDerivationEdge,
)
from memory.models import (
    ConceptMention,
    EntityMention,
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
from world.events import Moved, Waited, make_replayable_event
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision

pytestmark = __import__("pytest").mark.unit


def _root_trace(
    *,
    memory_id: str = "m-root",
    concepts: tuple[str, ...] = ("gate",),
    observed_source_id: str | None = "evt-1",
    confidence: float = 0.9,
) -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(1),
        concepts=tuple(
            ConceptMention(mention_id=MentionId(f"c-{index}"), concept=item)
            for index, item in enumerate(concepts, start=1)
        ),
        entities=(
            EntityMention(
                mention_id=MentionId("e-1"),
                label="door",
                entity_id=EntityId("ent-door"),
            ),
        ),
        relations=(),
        context=MemorySituationContext(tags=("yard",)),
        emotional_salience=0.4,
        confidence=confidence,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=1,
            observed_source_id=(
                None if observed_source_id is None else EventId(observed_source_id)
            ),
        ),
        created_tick=1,
        source_tick=1,
        last_access_tick=1,
        access_count=0,
        lineage=MemoryLineage(),
    )


def test_project_world_event_and_trace_are_comparable() -> None:
    event = make_replayable_event(
        event_id=EventId("evt-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=1,
        sequence=0,
        request_id=RequestId("r-1"),
        resulting_revision=WorldRevision(2),
        details=Moved(
            destination_id=EntityId("loc-2"),
            resulting_location_id=EntityId("loc-2"),
        ),
        actor_id=EntityId("body-1"),
    )
    facts = project_world_event(event)
    assert facts.availability is FactAvailability.PRESENT
    assert "move" in facts.concepts
    assert "body-1" in facts.entity_ids
    assert "loc-2" in facts.entity_ids

    trace = _root_trace()
    trace_facts = project_memory_trace(trace)
    delta = compare_fact_sets(facts, trace_facts)
    assert delta.comparison_status is ComparisonStatus.COMPLETE
    assert "gate" in delta.added_concepts
    assert "move" in delta.lost_concepts
    assert "gate" in delta.unsupported_concepts


def test_unknown_objective_is_not_treated_as_contradiction() -> None:
    unknown = project_world_event(
        make_replayable_event(
            event_id=EventId("evt-x"),
            run_id="run-1",
            world_id=WorldId("world-1"),
            tick=0,
            sequence=0,
            request_id=RequestId("r-x"),
            resulting_revision=WorldRevision(1),
            details=Waited(),
            actor_id=None,
        )
    )
    # Force unknown availability for the missing-source case.
    from analysis.models import StructuredFactSet

    before = StructuredFactSet(
        concepts=frozenset(),
        entity_ids=frozenset(),
        entity_labels=frozenset(),
        relations=frozenset(),
        context_tags=frozenset(),
        location_id=None,
        confidence=None,
        salience=None,
        narrative_fingerprint=None,
        availability=FactAvailability.UNKNOWN,
        projector_version="1",
    )
    after = project_memory_trace(_root_trace())
    delta = compare_fact_sets(before, after)
    assert delta.comparison_status is ComparisonStatus.BEFORE_UNKNOWN
    assert delta.unsupported_concepts == frozenset()
    assert delta.lost_concepts == frozenset()
    assert "gate" in delta.added_concepts
    assert unknown.availability is FactAvailability.PRESENT


def test_resolve_objective_link_distinguishes_absent_unlinked_linked() -> None:
    event = make_replayable_event(
        event_id=EventId("evt-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=0,
        sequence=0,
        request_id=RequestId("r-1"),
        resulting_revision=WorldRevision(1),
        details=Waited(),
        actor_id=None,
    )
    events = {event.event_id.value: event}
    status_absent, facts_absent = resolve_objective_link(
        observed_source_id=None, events_by_id=events
    )
    assert status_absent is ObjectiveLinkStatus.ABSENT
    assert facts_absent is None
    status, facts = resolve_objective_link(
        observed_source_id="evt-missing", events_by_id=events
    )
    assert status is ObjectiveLinkStatus.UNLINKED
    assert facts is None
    status, facts = resolve_objective_link(
        observed_source_id="evt-1", events_by_id=events
    )
    assert status is ObjectiveLinkStatus.LINKED
    assert facts is not None


def test_build_reconstruction_chains_traverses_ordered_edges() -> None:
    root = _root_trace()
    derived = MemoryTrace(
        memory_id=MemoryId("m-derived"),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(1),
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept="gate"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=0.3,
        confidence=0.6,
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
    reconstructed = ReconstructedMemory(
        reconstruction_id=ReconstructionId("recon-1"),
        owner_id=AgentId("agent-1"),
        narrative="remembered gate",
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept="gate"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        confidence=0.6,
        emotional_salience=0.3,
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
    chains = build_reconstruction_chains(
        traces=(root, derived),
        reconstructions=(evidence,),
        edges=(
            SubjectiveDerivationEdge(
                derived_memory_id="m-derived",
                source_memory_id="m-root",
                ordinal=0,
                reconstruction_id="recon-1",
            ),
        ),
        events_by_id={event.event_id.value: event},
    )
    assert len(chains) == 1
    kinds = [node.kind.value for node in chains[0].nodes]
    assert kinds == [
        "objective_event",
        "root_trace",
        "reconstruction",
        "derived_trace",
    ]
    assert chains[0].objective_link is ObjectiveLinkStatus.LINKED


def test_compare_fact_sets_detects_relation_and_context_mutations() -> None:
    from analysis.models import StructuredFactSet

    before = StructuredFactSet(
        concepts=frozenset({"gate"}),
        entity_ids=frozenset({"ent-door"}),
        entity_labels=frozenset({"door"}),
        relations=frozenset({("near", "door", "latch")}),
        context_tags=frozenset({"evening"}),
        location_id="loc-1",
        confidence=0.9,
        salience=0.5,
        narrative_fingerprint="a" * 64,
        availability=FactAvailability.PRESENT,
        projector_version="1",
    )
    after = StructuredFactSet(
        concepts=frozenset({"gate", "rust"}),
        entity_ids=frozenset({"ent-door"}),
        entity_labels=frozenset({"door"}),
        relations=frozenset({("beside", "door", "hinge")}),
        context_tags=frozenset({"night"}),
        location_id="loc-2",
        confidence=0.6,
        salience=0.2,
        narrative_fingerprint="b" * 64,
        availability=FactAvailability.PRESENT,
        projector_version="1",
    )
    delta = compare_fact_sets(before, after)
    assert "rust" in delta.added_concepts
    assert ("near", "door", "latch") in delta.lost_relations
    assert ("beside", "door", "hinge") in delta.added_relations
    assert "evening" in delta.lost_context_tags
    assert "night" in delta.added_context_tags
    assert delta.location_changed is True
    assert delta.confidence_delta == pytest.approx(-0.3)
    assert delta.canonical_equal is False


def test_identical_fact_sets_are_canonically_equal() -> None:
    from analysis.models import StructuredFactSet

    facts = StructuredFactSet(
        concepts=frozenset({"gate"}),
        entity_ids=frozenset(),
        entity_labels=frozenset(),
        relations=frozenset(),
        context_tags=frozenset({"yard"}),
        location_id=None,
        confidence=0.5,
        salience=0.5,
        narrative_fingerprint=None,
        availability=FactAvailability.PRESENT,
        projector_version="1",
    )
    delta = compare_fact_sets(facts, facts)
    assert delta.canonical_equal is True
    assert delta.added_concepts == frozenset()
    assert delta.lost_concepts == frozenset()
