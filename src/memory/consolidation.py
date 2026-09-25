"""Deterministic offline episodic consolidation.

Pure policy: no clock, RNG, logging, or store writes. Belief candidates come
only from :func:`memory.belief_formation.extract_evidence_candidates`. Derived
gists copy fragments that occur in more than one cited source.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Final

from agents.models import AgentId
from memory.belief_formation import (
    DEFAULT_BELIEF_FORMATION_POLICY,
    extract_evidence_candidates,
)
from memory.beliefs import canonical_claim_identity
from memory.dynamics import trace_similarity
from memory.models import (
    OFFLINE_CONSOLIDATION_POLICY_VERSION,
    ConceptMention,
    EntityMention,
    MemoryId,
    MemoryLineage,
    MemoryProvenance,
    MemoryRelation,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
    OfflineConsolidationCandidateSet,
    OfflineConsolidationPolicy,
    OfflineConsolidationReasonCode,
    OfflineConsolidationSelection,
    RelationEndpoint,
    RelationEndpointKind,
    quantize_score,
)
from world.identifiers import EntityId, require_exact_nonneg_int

__all__ = ["plan_offline_consolidation"]

_MAX_TRACES: Final[int] = 256


def plan_offline_consolidation(
    *,
    owner_id: AgentId,
    tick: int,
    traces: Sequence[MemoryTrace],
    policy: OfflineConsolidationPolicy,
) -> tuple[OfflineConsolidationCandidateSet, OfflineConsolidationSelection]:
    """Score owner traces and select merge, strengthen, and soft-forget ids."""
    if type(owner_id) is not AgentId:
        raise TypeError("plan_offline_consolidation: invalid_owner")
    if type(policy) is not OfflineConsolidationPolicy:
        raise TypeError("plan_offline_consolidation: invalid_policy")
    if policy.version != OFFLINE_CONSOLIDATION_POLICY_VERSION:
        raise ValueError("plan_offline_consolidation: unsupported_policy")
    resolved_tick = require_exact_nonneg_int("plan_offline_consolidation.tick", tick)
    if isinstance(traces, (str, bytes)) or not isinstance(traces, Sequence):
        raise TypeError("plan_offline_consolidation.traces: not_ordered_sequence")
    if len(traces) > _MAX_TRACES:
        raise ValueError("plan_offline_consolidation.traces: exceeds_max_length")

    active: list[MemoryTrace] = []
    seen: set[MemoryId] = set()
    for trace in traces:
        if type(trace) is not MemoryTrace:
            raise TypeError("plan_offline_consolidation.traces: invalid_item_type")
        if trace.owner_id != owner_id:
            raise ValueError("plan_offline_consolidation.traces: owner_mismatch")
        if trace.memory_id in seen:
            raise ValueError("plan_offline_consolidation.traces: duplicate_id")
        seen.add(trace.memory_id)
        if trace.forgotten_at_tick is not None:
            continue
        if resolved_tick < trace.created_tick:
            raise ValueError("plan_offline_consolidation.tick: tick_before_created")
        active.append(trace)
    active.sort(key=lambda item: item.memory_id.value)

    scores = {
        trace.memory_id: _retention(trace, tick=resolved_tick) for trace in active
    }
    forget_ids = tuple(
        trace.memory_id
        for trace in active
        if scores[trace.memory_id] < policy.soft_forget_threshold
    )
    forget_set = set(forget_ids)
    survivors = [trace for trace in active if trace.memory_id not in forget_set]
    clusters = _clusters(survivors, threshold=policy.cluster_similarity)
    cluster_members = {memory_id for group in clusters for memory_id in group}
    belief_ids = _belief_source_ids(
        [trace for trace in survivors if trace.memory_id in cluster_members],
        owner_id=owner_id,
    )
    strengthen_ids = tuple(
        trace.memory_id
        for trace in survivors
        if scores[trace.memory_id] >= policy.strengthen_retention_floor
    )
    by_id = {trace.memory_id: trace for trace in survivors}
    derived = tuple(
        _derived_gist(group, traces_by_id=by_id, tick=resolved_tick)
        for group in clusters
    )
    reason_codes = _reason_codes(
        clusters=clusters,
        belief_ids=belief_ids,
        strengthen_ids=strengthen_ids,
        forget_ids=forget_ids,
        survivors=survivors,
        cluster_members=cluster_members,
    )
    candidate_set = OfflineConsolidationCandidateSet(
        owner_id=owner_id,
        tick=resolved_tick,
        policy=policy,
        traces=tuple(active),
        cluster_ids=clusters,
        belief_source_ids=belief_ids,
        strengthen_ids=strengthen_ids,
        soft_forget_ids=forget_ids,
    )
    selection = OfflineConsolidationSelection(
        owner_id=owner_id,
        tick=resolved_tick,
        policy_version=policy.version,
        merge_groups=clusters,
        strengthen_ids=strengthen_ids,
        soft_forget_ids=forget_ids,
        belief_source_ids=belief_ids,
        derived_traces=derived,
        reason_codes=reason_codes,
        used_provider=False,
        fallback_used=False,
    )
    return candidate_set, selection


def _retention(trace: MemoryTrace, *, tick: int) -> float:
    age = tick - trace.created_tick
    age_factor = quantize_score(1.0 / (1.0 + float(age)))
    access_factor = quantize_score(
        float(trace.access_count) / (1.0 + float(trace.access_count))
    )
    raw = (
        0.45 * trace.confidence
        + 0.25 * trace.emotional_salience
        + 0.2 * access_factor
        + 0.1 * age_factor
    )
    return quantize_score(max(0.0, min(1.0, raw)))


def _clusters(
    traces: Sequence[MemoryTrace], *, threshold: float
) -> tuple[tuple[MemoryId, ...], ...]:
    ordered = tuple(sorted(traces, key=lambda item: item.memory_id.value))
    parent = {trace.memory_id: trace.memory_id for trace in ordered}

    def find(memory_id: MemoryId) -> MemoryId:
        while parent[memory_id] != memory_id:
            parent[memory_id] = parent[parent[memory_id]]
            memory_id = parent[memory_id]
        return memory_id

    def unite(left: MemoryId, right: MemoryId) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return
        if left_root.value <= right_root.value:
            parent[right_root] = left_root
        else:
            parent[left_root] = right_root

    for index, left in enumerate(ordered):
        for right in ordered[index + 1 :]:
            similarity = trace_similarity(left, right)
            if similarity >= threshold:
                unite(left.memory_id, right.memory_id)
    groups: dict[MemoryId, list[MemoryId]] = {}
    for trace in ordered:
        root = find(trace.memory_id)
        groups.setdefault(root, []).append(trace.memory_id)
    clusters = [
        tuple(sorted(members, key=lambda item: item.value))
        for members in groups.values()
        if len(members) >= 2
    ]
    clusters.sort(key=lambda group: group[0].value)
    return tuple(clusters)


def _belief_source_ids(
    traces: Sequence[MemoryTrace], *, owner_id: AgentId
) -> tuple[MemoryId, ...]:
    if len(traces) < 2:
        return ()
    candidates = extract_evidence_candidates(
        traces,
        owner_id=owner_id,
        policy=DEFAULT_BELIEF_FORMATION_POLICY,
    )
    grouped: dict[str, set[MemoryId]] = {}
    for candidate in candidates:
        grouped.setdefault(canonical_claim_identity(candidate.claim), set()).add(
            candidate.memory_id
        )
    minimum = DEFAULT_BELIEF_FORMATION_POLICY.min_independent_observations
    selected: set[MemoryId] = set()
    for memory_ids in grouped.values():
        if len(memory_ids) >= minimum:
            selected.update(memory_ids)
    return tuple(sorted(selected, key=lambda item: item.value))


def _reason_codes(
    *,
    clusters: tuple[tuple[MemoryId, ...], ...],
    belief_ids: tuple[MemoryId, ...],
    strengthen_ids: tuple[MemoryId, ...],
    forget_ids: tuple[MemoryId, ...],
    survivors: Sequence[MemoryTrace],
    cluster_members: set[MemoryId],
) -> tuple[OfflineConsolidationReasonCode, ...]:
    codes: list[OfflineConsolidationReasonCode] = []
    if clusters:
        codes.append(OfflineConsolidationReasonCode.REPEATED_PATTERN)
        codes.append(OfflineConsolidationReasonCode.MERGED)
    if belief_ids:
        codes.append(OfflineConsolidationReasonCode.BELIEF_CANDIDATE)
    if strengthen_ids:
        codes.append(OfflineConsolidationReasonCode.STRENGTHENED)
    if forget_ids:
        codes.append(OfflineConsolidationReasonCode.LOW_RETENTION)
        codes.append(OfflineConsolidationReasonCode.SOFT_FORGOTTEN)
    if any(trace.memory_id not in cluster_members for trace in survivors):
        codes.append(OfflineConsolidationReasonCode.ISOLATED)
    return tuple(codes)


def _derived_gist(
    group: tuple[MemoryId, ...],
    *,
    traces_by_id: Mapping[MemoryId, MemoryTrace],
    tick: int,
) -> MemoryTrace:
    sources = tuple(traces_by_id[memory_id] for memory_id in group)
    principal = sources[0]
    concepts = _shared_concepts(sources)
    entities = _shared_entities(sources)
    concept_ids = {item.concept: item.mention_id for item in concepts}
    entity_ids = {_entity_key(item): item.mention_id for item in entities}
    relations = _shared_relations(
        sources, concept_ids=concept_ids, entity_ids=entity_ids
    )
    context = _shared_context(sources)
    confidence = quantize_score(
        sum(item.confidence for item in sources) / float(len(sources))
    )
    salience = quantize_score(
        sum(item.emotional_salience for item in sources) / float(len(sources))
    )
    generation = 1 + max(item.lineage.generation for item in sources)
    digest = hashlib.sha256(
        ",".join(memory_id.value for memory_id in group).encode("utf-8")
    ).hexdigest()[:16]
    provenance = _gist_provenance(principal)
    return MemoryTrace(
        memory_id=MemoryId(f"consol-{tick}-{digest}"),
        owner_id=principal.owner_id,
        world_revision=principal.world_revision,
        concepts=concepts,
        entities=entities,
        relations=relations,
        context=context,
        emotional_salience=salience,
        confidence=confidence,
        provenance=provenance,
        created_tick=tick,
        source_tick=principal.source_tick,
        last_access_tick=tick,
        access_count=0,
        lineage=MemoryLineage(
            supersedes_memory_id=principal.memory_id,
            generation=generation,
            source_memory_ids=group,
        ),
    )


def _gist_provenance(principal: MemoryTrace) -> MemoryProvenance:
    kind = principal.provenance.kind
    if kind is MemorySourceKind.DIRECT_OBSERVATION:
        return MemoryProvenance(
            kind=kind,
            source_tick=principal.source_tick,
        )
    return MemoryProvenance(
        kind=kind,
        source_tick=principal.source_tick,
        speaker_id=principal.provenance.speaker_id,
        transmission=principal.provenance.transmission,
    )


def _shared_concepts(sources: Sequence[MemoryTrace]) -> tuple[ConceptMention, ...]:
    counts: Counter[str] = Counter()
    for trace in sources:
        counts.update({concept.concept for concept in trace.concepts})
    kept = sorted(concept for concept, count in counts.items() if count > 1)
    return tuple(
        ConceptMention(mention_id=MentionId(f"c-{index}"), concept=concept)
        for index, concept in enumerate(kept)
    )


def _entity_key(entity: EntityMention) -> str:
    if entity.entity_id is not None:
        return f"id:{entity.entity_id.value}"
    return f"label:{entity.label}"


def _shared_entities(sources: Sequence[MemoryTrace]) -> tuple[EntityMention, ...]:
    counts: Counter[str] = Counter()
    exemplars: dict[str, EntityMention] = {}
    for trace in sources:
        seen: set[str] = set()
        for entity in trace.entities:
            key = _entity_key(entity)
            seen.add(key)
            exemplars.setdefault(key, entity)
        counts.update(seen)
    kept = sorted(key for key, count in counts.items() if count > 1)
    return tuple(
        EntityMention(
            mention_id=MentionId(f"e-{index}"),
            label=exemplars[key].label,
            entity_id=exemplars[key].entity_id,
        )
        for index, key in enumerate(kept)
    )


def _endpoint_key(
    trace: MemoryTrace, endpoint: RelationEndpoint
) -> tuple[str, str] | None:
    if endpoint.kind is RelationEndpointKind.CONCEPT:
        for concept in trace.concepts:
            if concept.mention_id == endpoint.mention_id:
                return ("concept", concept.concept)
        return None
    for entity in trace.entities:
        if entity.mention_id == endpoint.mention_id:
            return ("entity", _entity_key(entity))
    return None


def _shared_relations(
    sources: Sequence[MemoryTrace],
    *,
    concept_ids: Mapping[str, MentionId],
    entity_ids: Mapping[str, MentionId],
) -> tuple[MemoryRelation, ...]:
    counts: Counter[tuple[tuple[str, str], str, tuple[str, str]]] = Counter()
    for trace in sources:
        seen: set[tuple[tuple[str, str], str, tuple[str, str]]] = set()
        for relation in trace.relations:
            subject = _endpoint_key(trace, relation.subject)
            obj = _endpoint_key(trace, relation.object)
            if subject is None or obj is None:
                continue
            seen.add((subject, relation.predicate, obj))
        counts.update(seen)
    kept = sorted(key for key, count in counts.items() if count > 1)
    relations: list[MemoryRelation] = []
    for index, (subject, predicate, obj) in enumerate(kept):
        subject_id = _kept_mention(
            subject, concept_ids=concept_ids, entity_ids=entity_ids
        )
        object_id = _kept_mention(obj, concept_ids=concept_ids, entity_ids=entity_ids)
        if subject_id is None or object_id is None:
            continue
        relations.append(
            MemoryRelation(
                relation_id=MentionId(f"r-{index}"),
                predicate=predicate,
                subject=RelationEndpoint(
                    kind=_endpoint_kind(subject), mention_id=subject_id
                ),
                object=RelationEndpoint(kind=_endpoint_kind(obj), mention_id=object_id),
            )
        )
    return tuple(relations)


def _endpoint_kind(key: tuple[str, str]) -> RelationEndpointKind:
    if key[0] == "concept":
        return RelationEndpointKind.CONCEPT
    return RelationEndpointKind.ENTITY


def _kept_mention(
    key: tuple[str, str],
    *,
    concept_ids: Mapping[str, MentionId],
    entity_ids: Mapping[str, MentionId],
) -> MentionId | None:
    if key[0] == "concept":
        return concept_ids.get(key[1])
    return entity_ids.get(key[1])


def _shared_context(sources: Sequence[MemoryTrace]) -> MemorySituationContext:
    tag_counts: Counter[str] = Counter()
    location_counts: Counter[str] = Counter()
    locations: dict[str, EntityId] = {}
    for trace in sources:
        tag_counts.update(set(trace.context.tags))
        if trace.context.location_id is not None:
            location_counts.update([trace.context.location_id.value])
            locations.setdefault(
                trace.context.location_id.value, trace.context.location_id
            )
    tags = tuple(sorted(tag for tag, count in tag_counts.items() if count > 1))
    repeated = [value for value, count in location_counts.items() if count > 1]
    location = locations[repeated[0]] if len(repeated) == 1 else None
    return MemorySituationContext(location_id=location, tags=tags)
