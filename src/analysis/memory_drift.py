"""Pure memory-drift comparison and provenance-chain traversal.

Log-free projectors/comparators. Distinguishes unknown/absent objective truth
from contradicted or unsupported subjective additions. Never invents missing
objective sources. Visibility-aware primary baseline prefers agent-visible
projection; authoritative-world gaps are separately labeled.
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Mapping, Sequence
from typing import Final

from analysis.evidence import EvidenceStage
from analysis.models import (
    AGENT_VISIBLE_PROJECTOR_VERSION,
    DRIFT_METRIC_VERSION,
    EVENT_FACT_PROJECTOR_VERSION,
    METRIC_DOCUMENT_SCHEMA_VERSION,
    ChainNodeKind,
    ComparisonStatus,
    DriftDelta,
    FactAvailability,
    MemoryDriftReport,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
    ObjectiveLinkStatus,
    ReconstructionChain,
    ReconstructionChainNode,
    ReconstructionEvidence,
    StructuredFactSet,
    SubjectiveDerivationEdge,
)
from analysis.numerical import library_versions, quantize_float, require_finite
from analysis.specifications import MetricFamilyId, metric_specification
from memory.models import (
    ConceptMention,
    EntityMention,
    MemoryRelation,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    ReconstructedMemory,
    RelationEndpointKind,
)
from world.events import WorldEvent
from world.identifiers import require_stable_id
from world.observations import Observation

__all__ = [
    "AGENT_VISIBLE_PROJECTOR_VERSION",
    "DRIFT_METRIC_VERSION",
    "EVENT_FACT_PROJECTOR_VERSION",
    "build_reconstruction_chains",
    "compare_fact_sets",
    "compute_memory_drift",
    "concept_jaccard_loss",
    "cumulative_drift",
    "dedupe_traces_by_lineage_root",
    "evidence_from_reconstructed_memory",
    "evidence_stage_for_trace",
    "project_agent_visible_observation",
    "project_memory_trace",
    "project_reconstructed_memory",
    "project_reconstruction_evidence",
    "project_world_event",
    "resolve_objective_link",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.memory_drift")

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


def project_agent_visible_observation(observation: Observation) -> StructuredFactSet:
    """Project exact agent-visible observation into structured facts.

    Primary baseline for direct-memory drift. Never invents hidden state.
    """
    if type(observation) is not Observation:
        raise TypeError("project_agent_visible_observation: invalid_type")
    concepts: set[str] = set()
    entity_ids: set[str] = set()
    entity_labels: set[str] = set()
    relations: set[tuple[str, str, str]] = set()
    context_tags: set[str] = set()

    entity_ids.add(observation.observer_id.value)
    location_id: str | None = None
    if observation.self_body is not None:
        entity_ids.add(observation.self_body.entity_id.value)
        location_id = observation.self_body.location_id.value
    for body in observation.visible_bodies:
        entity_ids.add(body.entity_id.value)
    for item in observation.items:
        entity_ids.add(item.entity_id.value)
    for resource in observation.resources:
        entity_ids.add(resource.entity_id.value)
    for exit_item in observation.exits:
        entity_ids.add(exit_item.destination_id.value)
    for occurrence in observation.occurrences:
        concepts.add(occurrence.kind)
        if occurrence.actor_id is not None:
            entity_ids.add(occurrence.actor_id.value)
        if occurrence.other_entity_id is not None:
            entity_ids.add(occurrence.other_entity_id.value)
        if occurrence.destination_id is not None:
            entity_ids.add(occurrence.destination_id.value)
        if occurrence.success is not None:
            context_tags.add(f"success:{occurrence.success}")
        if occurrence.actor_id is not None and occurrence.other_entity_id is not None:
            relations.add(
                (
                    occurrence.kind,
                    occurrence.actor_id.value,
                    occurrence.other_entity_id.value,
                )
            )
    for message in observation.communications:
        concepts.add(message.action_kind)
        entity_ids.add(message.speaker_id.value)
        entity_ids.add(message.listener_id.value)
        concepts.update(message.utterance.content.concepts)
    if observation.day_phase is not None:
        context_tags.add(f"day_phase:{observation.day_phase.value}")
    if observation.weather_condition is not None:
        context_tags.add(f"weather:{observation.weather_condition.value}")

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
        projector_version=AGENT_VISIBLE_PROJECTOR_VERSION,
    )


def evidence_stage_for_trace(trace: MemoryTrace) -> EvidenceStage:
    """Map a memory trace provenance/lineage to a closed EvidenceStage."""
    if type(trace) is not MemoryTrace:
        raise TypeError("evidence_stage_for_trace: invalid_type")
    if trace.lineage.generation > 0 and trace.lineage.source_memory_ids:
        return EvidenceStage.RECONSOLIDATED_TRACE
    if trace.provenance.kind is MemorySourceKind.COMMUNICATED:
        return EvidenceStage.COMMUNICATED_TRACE
    return EvidenceStage.DIRECT_TRACE


def dedupe_traces_by_lineage_root(
    traces: Sequence[MemoryTrace],
) -> tuple[MemoryTrace, ...]:
    """Keep one corroborating trace per (stage, lineage root); never collapse stages."""
    selected: dict[tuple[str, str], MemoryTrace] = {}
    for trace in traces:
        stage = evidence_stage_for_trace(trace)
        root = (
            trace.lineage.source_memory_ids[0].value
            if trace.lineage.source_memory_ids
            else trace.memory_id.value
        )
        key = (stage.value, root)
        existing = selected.get(key)
        if existing is None:
            selected[key] = trace
            continue
        # Prefer earlier creation, then stable memory id.
        if (trace.created_tick, trace.memory_id.value) < (
            existing.created_tick,
            existing.memory_id.value,
        ):
            selected[key] = trace
    return tuple(
        sorted(
            selected.values(),
            key=lambda item: (item.created_tick, item.memory_id.value),
        )
    )


def concept_jaccard_loss(before: StructuredFactSet, after: StructuredFactSet) -> float | None:
    """1 - Jaccard(concepts) when both sides PRESENT; else None (unknown)."""
    if (
        before.availability is not FactAvailability.PRESENT
        or after.availability is not FactAvailability.PRESENT
    ):
        return None
    union = before.concepts | after.concepts
    if not union:
        return 0.0
    intersection = before.concepts & after.concepts
    jaccard = float(len(intersection)) / float(len(union))
    return quantize_float(require_finite(1.0 - jaccard))


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
    agent_visible_by_source_id: Mapping[str, StructuredFactSet] | None = None,
    include_authoritative_world: bool = True,
) -> tuple[ReconstructionChain, ...]:
    """Traverse ordered derivation edges into immutable reconstruction chains.

    Primary baseline prefers agent-visible projection when provided. Authoritative
    world events remain available for separately labeled gap comparisons when
    ``include_authoritative_world`` is true.
    """
    visible_map = dict(agent_visible_by_source_id or {})
    traces = dedupe_traces_by_lineage_root(traces)
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
        visible = None if observed is None else visible_map.get(observed)
        if visible is not None:
            nodes.append(
                ReconstructionChainNode(
                    kind=ChainNodeKind.AGENT_VISIBLE_PROJECTION,
                    node_id=f"visible:{observed}",
                    generation=0,
                    facts=visible,
                    observed_source_id=observed,
                    objective_link=ObjectiveLinkStatus.NOT_APPLICABLE,
                )
            )
        elif include_authoritative_world:
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


def compute_memory_drift(
    report: MemoryDriftReport,
    *,
    input_revision: str,
) -> MetricDocument:
    """Summarize a MemoryDriftReport into a catalog MetricDocument."""
    started = time.perf_counter()
    if type(report) is not MemoryDriftReport:
        raise TypeError("compute_memory_drift: invalid_report")
    input_revision = require_stable_id("input_revision", input_revision)
    spec = metric_specification(MetricFamilyId.MEMORY_DRIFT)
    chain_count = len(report.chains)
    if chain_count == 0:
        return MetricDocument(
            schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
            metric_family=spec.family_id.value,
            algorithm_version=spec.algorithm_version,
            library_versions=library_versions(),
            run_id=report.run_id,
            input_revision=input_revision,
            evidence_stages=frozenset(spec.evidence_inputs),
            population=spec.population,
            denominator=spec.denominator,
            coverage=None,
            availability=MetricAvailability.ABSENT,
            values={},
            provenance=MetricProvenance(
                source_kind="memory_drift",
                source_ids=(),
                notes_code="no_chains",
            ),
        )

    losses: list[float] = []
    unknown_pairs = 0
    for step in report.steps:
        if step.comparison_label != "primary":
            continue
        loss = concept_jaccard_loss(
            StructuredFactSet(
                concepts=step.delta.retained_concepts | step.delta.lost_concepts,
                entity_ids=frozenset(),
                entity_labels=frozenset(),
                relations=frozenset(),
                context_tags=frozenset(),
                location_id=None,
                confidence=None,
                salience=None,
                narrative_fingerprint=None,
                availability=(
                    FactAvailability.PRESENT
                    if step.delta.comparison_status is ComparisonStatus.COMPLETE
                    else FactAvailability.UNKNOWN
                ),
                projector_version=EVENT_FACT_PROJECTOR_VERSION,
            ),
            StructuredFactSet(
                concepts=step.delta.retained_concepts | step.delta.added_concepts,
                entity_ids=frozenset(),
                entity_labels=frozenset(),
                relations=frozenset(),
                context_tags=frozenset(),
                location_id=None,
                confidence=None,
                salience=None,
                narrative_fingerprint=None,
                availability=(
                    FactAvailability.PRESENT
                    if step.delta.comparison_status is ComparisonStatus.COMPLETE
                    else FactAvailability.UNKNOWN
                ),
                projector_version=EVENT_FACT_PROJECTOR_VERSION,
            ),
        )
        if loss is None:
            unknown_pairs += 1
        else:
            losses.append(loss)

    # Prefer cumulative endpoint losses when step reconstruction is messy.
    if not losses:
        for index, chain in enumerate(report.chains):
            if len(chain.nodes) < 2:
                unknown_pairs += 1
                continue
            loss = concept_jaccard_loss(chain.nodes[0].facts, chain.nodes[-1].facts)
            if loss is None:
                unknown_pairs += 1
            else:
                losses.append(loss)

    if not losses and unknown_pairs > 0:
        availability = MetricAvailability.UNKNOWN
        values: dict[str, object] = {
            "mean_concept_jaccard_loss": None,
            "linked_chain_rate": None,
            "chain_count": chain_count,
            "unlinked_count": report.unlinked_count,
        }
        notes = "unknown_comparisons"
    elif not losses:
        availability = MetricAvailability.ABSENT
        values = {}
        notes = "no_comparable_pairs"
    else:
        mean_loss = quantize_float(
            require_finite(float(sum(losses)) / float(len(losses)))
        )
        linked_rate = quantize_float(
            require_finite(float(report.linked_count) / float(chain_count))
        )
        availability = (
            MetricAvailability.PARTIAL
            if unknown_pairs > 0
            else MetricAvailability.PRESENT
        )
        values = {
            "mean_concept_jaccard_loss": mean_loss,
            "linked_chain_rate": linked_rate,
            "chain_count": chain_count,
            "unlinked_count": report.unlinked_count,
        }
        notes = "ok"

    duration_ms = int((time.perf_counter() - started) * 1000)
    _LOG.debug(
        "memory_drift_metric_complete",
        extra={
            "operation": "compute_memory_drift",
            "run_id": report.run_id,
            "chain_count": chain_count,
            "availability": availability.value,
            "duration_ms": duration_ms,
        },
    )
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=report.run_id,
        input_revision=input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=MetricCoverage(
            observed=len(losses),
            expected=len(losses) + unknown_pairs,
            ratio=(
                None
                if len(losses) + unknown_pairs == 0
                else float(len(losses)) / float(len(losses) + unknown_pairs)
            ),
        ),
        availability=availability,
        values=values,
        provenance=MetricProvenance(
            source_kind="memory_drift",
            source_ids=(),
            notes_code=notes,
        ),
    )
