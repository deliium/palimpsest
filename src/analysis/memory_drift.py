"""Pure memory-drift comparison and provenance-chain traversal.

Log-free. Distinguishes unknown/absent objective truth from contradicted or
unsupported subjective additions. Never invents missing objective sources.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Final

from analysis.models import (
    DRIFT_METRIC_VERSION,
    EVENT_FACT_PROJECTOR_VERSION,
    ChainNodeKind,
    ComparisonStatus,
    DriftDelta,
    FactAvailability,
    ObjectiveLinkStatus,
    ReconstructionChain,
    ReconstructionChainNode,
    ReconstructionEvidence,
    StructuredFactSet,
    SubjectiveDerivationEdge,
)
from memory.models import (
    ConceptMention,
    EntityMention,
    MemoryRelation,
    MemorySituationContext,
    MemoryTrace,
    ReconstructedMemory,
    RelationEndpointKind,
)
from world.events import WorldEvent

__all__ = [
    "DRIFT_METRIC_VERSION",
    "EVENT_FACT_PROJECTOR_VERSION",
    "build_reconstruction_chains",
    "compare_fact_sets",
    "cumulative_drift",
    "evidence_from_reconstructed_memory",
    "project_memory_trace",
    "project_reconstructed_memory",
    "project_reconstruction_evidence",
    "project_world_event",
    "resolve_objective_link",
]

_EMPTY_FACTS: Final[StructuredFactSet] = StructuredFactSet(
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
    projector_version=EVENT_FACT_PROJECTOR_VERSION,
)


def project_world_event(event: WorldEvent) -> StructuredFactSet:
    """Versioned event-kind projector into a comparable structured fact set."""
    if type(event) is not WorldEvent:
        raise TypeError("project_world_event: invalid_type")
    details = event.details
    kind = event.event_type
    concepts = {kind}
    entity_ids: set[str] = set()
    entity_labels: set[str] = set()
    if event.actor_id is not None:
        entity_ids.add(event.actor_id.value)
    if event.target_id is not None:
        entity_ids.add(event.target_id.value)
    for attr in (
        "destination_id",
        "item_id",
        "recipient_id",
        "threat_id",
        "created_item_id",
        "resulting_location_id",
        "resulting_holder_id",
    ):
        value = getattr(details, attr, None)
        entity_value = getattr(value, "value", None)
        if type(entity_value) is str and entity_value:
            entity_ids.add(entity_value)

    relations: set[tuple[str, str, str]] = set()
    if event.actor_id is not None and event.target_id is not None:
        relations.add((kind, event.actor_id.value, event.target_id.value))

    location_id: str | None = None
    if event.occurrence is not None and event.occurrence.origin_location_id is not None:
        location_id = event.occurrence.origin_location_id.value

    context_tags: set[str] = set()
    success = getattr(details, "success", None)
    if type(success) is bool:
        context_tags.add(f"success:{success}")

    return StructuredFactSet(
        concepts=frozenset(concepts),
        entity_ids=frozenset(entity_ids),
        entity_labels=frozenset(entity_labels),
        relations=frozenset(relations),
        context_tags=frozenset(context_tags),
        location_id=location_id,
        confidence=None,
        salience=None,
        narrative_fingerprint=None,
        availability=FactAvailability.PRESENT,
        projector_version=EVENT_FACT_PROJECTOR_VERSION,
    )


def project_memory_trace(trace: MemoryTrace) -> StructuredFactSet:
    """Project a stored subjective trace into structured facts."""
    if type(trace) is not MemoryTrace:
        raise TypeError("project_memory_trace: invalid_type")
    return _project_mentions(
        concepts=trace.concepts,
        entities=trace.entities,
        relations=trace.relations,
        context=trace.context,
        confidence=trace.confidence,
        salience=trace.emotional_salience,
        narrative_fingerprint=None,
        availability=FactAvailability.PRESENT,
    )


def project_reconstructed_memory(value: ReconstructedMemory) -> StructuredFactSet:
    """Project a reconstructed episode into structured facts."""
    if type(value) is not ReconstructedMemory:
        raise TypeError("project_reconstructed_memory: invalid_type")
    fingerprint = hashlib.sha256(value.narrative.encode("utf-8")).hexdigest()
    return _project_mentions(
        concepts=value.concepts,
        entities=value.entities,
        relations=value.relations,
        context=value.context,
        confidence=value.confidence,
        salience=value.emotional_salience,
        narrative_fingerprint=fingerprint,
        availability=FactAvailability.PRESENT,
    )


def project_reconstruction_evidence(
    evidence: ReconstructionEvidence,
) -> StructuredFactSet:
    """Project analysis reconstruction evidence into structured facts."""
    if type(evidence) is not ReconstructionEvidence:
        raise TypeError("project_reconstruction_evidence: invalid_type")
    if not evidence.content_available:
        return StructuredFactSet(
            concepts=frozenset(),
            entity_ids=frozenset(),
            entity_labels=frozenset(),
            relations=frozenset(),
            context_tags=frozenset(),
            location_id=None,
            confidence=None,
            salience=None,
            narrative_fingerprint=evidence.narrative_fingerprint,
            availability=FactAvailability.UNKNOWN,
            projector_version=EVENT_FACT_PROJECTOR_VERSION,
        )
    return StructuredFactSet(
        concepts=frozenset(evidence.concepts),
        entity_ids=frozenset(evidence.entity_ids),
        entity_labels=frozenset(evidence.entity_labels),
        relations=frozenset(evidence.relations),
        context_tags=frozenset(evidence.context_tags),
        location_id=evidence.location_id,
        confidence=float(evidence.confidence),
        salience=float(evidence.emotional_salience),
        narrative_fingerprint=evidence.narrative_fingerprint,
        availability=FactAvailability.PRESENT,
        projector_version=EVENT_FACT_PROJECTOR_VERSION,
    )


def evidence_from_reconstructed_memory(
    *,
    run_id: str,
    reconstructed: ReconstructedMemory,
) -> ReconstructionEvidence:
    """Build analysis evidence from a domain reconstructed episode."""
    if type(reconstructed) is not ReconstructedMemory:
        raise TypeError("evidence_from_reconstructed_memory: invalid_type")
    entity_ids = tuple(
        item.entity_id.value
        for item in reconstructed.entities
        if item.entity_id is not None
    )
    entity_labels = tuple(item.label for item in reconstructed.entities)
    relations = tuple(
        (
            relation.predicate,
            _endpoint_key(
                relation.subject.kind,
                relation.subject.mention_id.value,
                concepts=reconstructed.concepts,
                entities=reconstructed.entities,
            ),
            _endpoint_key(
                relation.object.kind,
                relation.object.mention_id.value,
                concepts=reconstructed.concepts,
                entities=reconstructed.entities,
            ),
        )
        for relation in reconstructed.relations
    )
    fingerprint = hashlib.sha256(reconstructed.narrative.encode("utf-8")).hexdigest()
    return ReconstructionEvidence(
        reconstruction_id=reconstructed.reconstruction_id.value,
        run_id=run_id,
        owner_id=reconstructed.owner_id.value,
        source_memory_ids=tuple(item.value for item in reconstructed.source_memory_ids),
        concepts=tuple(item.concept for item in reconstructed.concepts),
        entity_ids=entity_ids,
        entity_labels=entity_labels,
        relations=relations,
        context_tags=reconstructed.context.tags,
        location_id=(
            None
            if reconstructed.context.location_id is None
            else reconstructed.context.location_id.value
        ),
        confidence=reconstructed.confidence,
        emotional_salience=reconstructed.emotional_salience,
        generation=reconstructed.generation,
        created_tick=reconstructed.reconstructed_at_tick,
        policy_id=reconstructed.policy_id,
        policy_version=reconstructed.policy_version,
        narrative_fingerprint=fingerprint,
        content_available=True,
    )


def resolve_objective_link(
    *,
    observed_source_id: str | None,
    events_by_id: Mapping[str, WorldEvent],
) -> tuple[ObjectiveLinkStatus, StructuredFactSet | None]:
    """Correlate opaque source id to an objective event without inventing."""
    if observed_source_id is None:
        return ObjectiveLinkStatus.ABSENT, None
    event = events_by_id.get(observed_source_id)
    if event is None:
        return ObjectiveLinkStatus.UNLINKED, None
    return ObjectiveLinkStatus.LINKED, project_world_event(event)


def compare_fact_sets(
    before: StructuredFactSet,
    after: StructuredFactSet,
    *,
    provenance_continuous: bool = True,
) -> DriftDelta:
    """Pure structured comparison; never treats unknown as contradiction."""
    if type(before) is not StructuredFactSet:
        raise TypeError("compare_fact_sets: invalid_before")
    if type(after) is not StructuredFactSet:
        raise TypeError("compare_fact_sets: invalid_after")

    if (
        before.availability is FactAvailability.UNKNOWN
        and after.availability is FactAvailability.UNKNOWN
    ):
        status = ComparisonStatus.BOTH_UNKNOWN
    elif before.availability is FactAvailability.UNKNOWN:
        status = ComparisonStatus.BEFORE_UNKNOWN
    elif after.availability is FactAvailability.UNKNOWN:
        status = ComparisonStatus.AFTER_UNKNOWN
    else:
        status = ComparisonStatus.COMPLETE

    before_known = before.availability is FactAvailability.PRESENT
    after_known = after.availability is FactAvailability.PRESENT

    before_concepts = before.concepts if before_known else frozenset()
    after_concepts = after.concepts if after_known else frozenset()
    before_entities = before.entity_ids if before_known else frozenset()
    after_entities = after.entity_ids if after_known else frozenset()
    before_relations = before.relations if before_known else frozenset()
    after_relations = after.relations if after_known else frozenset()
    before_tags = before.context_tags if before_known else frozenset()
    after_tags = after.context_tags if after_known else frozenset()

    retained_concepts = before_concepts & after_concepts
    lost_concepts = before_concepts - after_concepts
    added_concepts = after_concepts - before_concepts

    retained_entity_ids = before_entities & after_entities
    lost_entity_ids = before_entities - after_entities
    added_entity_ids = after_entities - before_entities

    retained_relations = before_relations & after_relations
    lost_relations = before_relations - after_relations
    added_relations = after_relations - before_relations

    retained_tags = before_tags & after_tags
    lost_tags = before_tags - after_tags
    added_tags = after_tags - before_tags

    # Unsupported additions require a known prior; unknown priors never invent
    # contradictions. Contradicted grounding = shared labels with diverging ids.
    if status is ComparisonStatus.COMPLETE and before_known:
        unsupported = added_concepts
    else:
        unsupported = frozenset()

    contradicted: set[str] = set()
    if before_known and after_known:
        before_label_map = {label: label for label in before.entity_labels}
        after_label_map = {label: label for label in after.entity_labels}
        shared_labels = set(before_label_map) & set(after_label_map)
        # Entity id present before, absent after, while a new id appears with
        # overlapping relation predicates is treated as contradiction candidate
        # when both sides are known and ids diverge for the same retained label set.
        if before.entity_ids and after.entity_ids:
            if before.entity_ids.isdisjoint(after.entity_ids) and shared_labels:
                contradicted.update(before.entity_ids | after.entity_ids)

    location_changed = False
    if before_known and after_known:
        location_changed = before.location_id != after.location_id

    confidence_delta: float | None = None
    if before.confidence is not None and after.confidence is not None:
        confidence_delta = after.confidence - before.confidence
    salience_delta: float | None = None
    if before.salience is not None and after.salience is not None:
        salience_delta = after.salience - before.salience

    canonical_equal = (
        status is ComparisonStatus.COMPLETE
        and before.concepts == after.concepts
        and before.entity_ids == after.entity_ids
        and before.entity_labels == after.entity_labels
        and before.relations == after.relations
        and before.context_tags == after.context_tags
        and before.location_id == after.location_id
        and before.confidence == after.confidence
        and before.salience == after.salience
        and before.narrative_fingerprint == after.narrative_fingerprint
    )

    return DriftDelta(
        retained_concepts=retained_concepts,
        lost_concepts=lost_concepts if before_known else frozenset(),
        added_concepts=added_concepts if after_known else frozenset(),
        retained_entity_ids=retained_entity_ids,
        lost_entity_ids=lost_entity_ids if before_known else frozenset(),
        added_entity_ids=added_entity_ids if after_known else frozenset(),
        retained_relations=retained_relations,
        lost_relations=lost_relations if before_known else frozenset(),
        added_relations=added_relations if after_known else frozenset(),
        retained_context_tags=retained_tags,
        lost_context_tags=lost_tags if before_known else frozenset(),
        added_context_tags=added_tags if after_known else frozenset(),
        location_changed=location_changed,
        confidence_delta=confidence_delta,
        salience_delta=salience_delta,
        provenance_continuous=provenance_continuous,
        canonical_equal=canonical_equal,
        unsupported_concepts=unsupported,
        contradicted_entity_ids=frozenset(contradicted),
        comparison_status=status,
    )


def cumulative_drift(
    first: StructuredFactSet,
    last: StructuredFactSet,
    *,
    provenance_continuous: bool,
) -> DriftDelta:
    """Endpoint cumulative comparison from the first chain node to the last."""
    return compare_fact_sets(
        first,
        last,
        provenance_continuous=provenance_continuous,
    )


def build_reconstruction_chains(
    *,
    traces: Sequence[MemoryTrace],
    reconstructions: Sequence[ReconstructionEvidence],
    edges: Sequence[SubjectiveDerivationEdge],
    events_by_id: Mapping[str, WorldEvent],
) -> tuple[ReconstructionChain, ...]:
    """Traverse ordered derivation edges into immutable reconstruction chains."""
    traces_by_id = {trace.memory_id.value: trace for trace in traces}
    reconstructions_by_id = {item.reconstruction_id: item for item in reconstructions}

    children: dict[str, list[SubjectiveDerivationEdge]] = {}
    for edge in edges:
        children.setdefault(edge.source_memory_id, []).append(edge)
    for _source_id, source_edges in children.items():
        source_edges.sort(key=lambda item: (item.ordinal, item.derived_memory_id))

    roots = [
        trace
        for trace in traces
        if not trace.lineage.source_memory_ids and trace.lineage.generation == 0
    ]
    roots.sort(key=lambda item: (item.created_tick, item.memory_id.value))

    chains: list[ReconstructionChain] = []
    for root in roots:
        observed = (
            None
            if root.provenance.observed_source_id is None
            else root.provenance.observed_source_id.value
        )
        link, objective_facts = resolve_objective_link(
            observed_source_id=observed,
            events_by_id=events_by_id,
        )
        nodes: list[ReconstructionChainNode] = []
        if link is ObjectiveLinkStatus.LINKED and objective_facts is not None:
            nodes.append(
                ReconstructionChainNode(
                    kind=ChainNodeKind.OBJECTIVE_EVENT,
                    node_id=observed or root.memory_id.value,
                    generation=0,
                    facts=objective_facts,
                    observed_source_id=observed,
                    objective_link=link,
                )
            )
        elif link is ObjectiveLinkStatus.UNLINKED:
            nodes.append(
                ReconstructionChainNode(
                    kind=ChainNodeKind.OBJECTIVE_EVENT,
                    node_id=observed or root.memory_id.value,
                    generation=0,
                    facts=_EMPTY_FACTS,
                    observed_source_id=observed,
                    objective_link=link,
                )
            )

        nodes.append(
            ReconstructionChainNode(
                kind=ChainNodeKind.ROOT_TRACE,
                node_id=root.memory_id.value,
                generation=root.lineage.generation,
                facts=project_memory_trace(root),
                observed_source_id=observed,
                objective_link=link,
            )
        )
        _append_descendants(
            nodes=nodes,
            source_memory_id=root.memory_id.value,
            children=children,
            traces_by_id=traces_by_id,
            reconstructions_by_id=reconstructions_by_id,
            observed_source_id=observed,
            visited=set(),
        )
        chains.append(
            ReconstructionChain(
                root_memory_id=root.memory_id.value,
                observed_source_id=observed,
                objective_link=link,
                nodes=tuple(nodes),
            )
        )
    return tuple(chains)


def _append_descendants(
    *,
    nodes: list[ReconstructionChainNode],
    source_memory_id: str,
    children: Mapping[str, list[SubjectiveDerivationEdge]],
    traces_by_id: Mapping[str, MemoryTrace],
    reconstructions_by_id: Mapping[str, ReconstructionEvidence],
    observed_source_id: str | None,
    visited: set[str],
) -> None:
    if source_memory_id in visited:
        return
    visited.add(source_memory_id)
    for edge in children.get(source_memory_id, ()):
        if edge.derived_memory_id in visited:
            continue
        if edge.reconstruction_id is not None:
            evidence = reconstructions_by_id.get(edge.reconstruction_id)
            if evidence is not None:
                nodes.append(
                    ReconstructionChainNode(
                        kind=ChainNodeKind.RECONSTRUCTION,
                        node_id=edge.reconstruction_id,
                        generation=evidence.generation,
                        facts=project_reconstruction_evidence(evidence),
                        observed_source_id=observed_source_id,
                        objective_link=ObjectiveLinkStatus.NOT_APPLICABLE,
                    )
                )
            else:
                nodes.append(
                    ReconstructionChainNode(
                        kind=ChainNodeKind.RECONSTRUCTION,
                        node_id=edge.reconstruction_id,
                        generation=0,
                        facts=_EMPTY_FACTS,
                        observed_source_id=observed_source_id,
                        objective_link=ObjectiveLinkStatus.NOT_APPLICABLE,
                    )
                )
        derived = traces_by_id.get(edge.derived_memory_id)
        if derived is None:
            nodes.append(
                ReconstructionChainNode(
                    kind=ChainNodeKind.DERIVED_TRACE,
                    node_id=edge.derived_memory_id,
                    generation=0,
                    facts=_EMPTY_FACTS,
                    observed_source_id=observed_source_id,
                    objective_link=ObjectiveLinkStatus.NOT_APPLICABLE,
                )
            )
            continue
        nodes.append(
            ReconstructionChainNode(
                kind=ChainNodeKind.DERIVED_TRACE,
                node_id=derived.memory_id.value,
                generation=derived.lineage.generation,
                facts=project_memory_trace(derived),
                observed_source_id=observed_source_id,
                objective_link=ObjectiveLinkStatus.NOT_APPLICABLE,
            )
        )
        _append_descendants(
            nodes=nodes,
            source_memory_id=derived.memory_id.value,
            children=children,
            traces_by_id=traces_by_id,
            reconstructions_by_id=reconstructions_by_id,
            observed_source_id=observed_source_id,
            visited=visited,
        )


def _project_mentions(
    *,
    concepts: Sequence[ConceptMention],
    entities: Sequence[EntityMention],
    relations: Sequence[MemoryRelation],
    context: MemorySituationContext,
    confidence: float,
    salience: float,
    narrative_fingerprint: str | None,
    availability: FactAvailability,
) -> StructuredFactSet:
    concept_values = frozenset(item.concept for item in concepts)
    entity_ids = frozenset(
        item.entity_id.value for item in entities if item.entity_id is not None
    )
    entity_labels = frozenset(item.label for item in entities)
    relation_values = frozenset(
        (
            relation.predicate,
            _endpoint_key(
                relation.subject.kind,
                relation.subject.mention_id.value,
                concepts=concepts,
                entities=entities,
            ),
            _endpoint_key(
                relation.object.kind,
                relation.object.mention_id.value,
                concepts=concepts,
                entities=entities,
            ),
        )
        for relation in relations
    )
    return StructuredFactSet(
        concepts=concept_values,
        entity_ids=entity_ids,
        entity_labels=entity_labels,
        relations=relation_values,
        context_tags=frozenset(context.tags),
        location_id=None if context.location_id is None else context.location_id.value,
        confidence=float(confidence),
        salience=float(salience),
        narrative_fingerprint=narrative_fingerprint,
        availability=availability,
        projector_version=EVENT_FACT_PROJECTOR_VERSION,
    )


def _endpoint_key(
    kind: RelationEndpointKind,
    mention_id: str,
    *,
    concepts: Sequence[ConceptMention],
    entities: Sequence[EntityMention],
) -> str:
    if kind is RelationEndpointKind.CONCEPT:
        for concept in concepts:
            if concept.mention_id.value == mention_id:
                return f"concept:{concept.concept}"
        return f"concept:{mention_id}"
    for entity in entities:
        if entity.mention_id.value == mention_id:
            if entity.entity_id is not None:
                return f"entity:{entity.entity_id.value}"
            return f"label:{entity.label}"
    return f"entity:{mention_id}"
