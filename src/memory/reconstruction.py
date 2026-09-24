"""Deterministic reconstructive recall orchestration.

Pure evidence normalization and deterministic reconstruction are log-free.
The orchestration boundary emits metadata-only logs (IDs, ticks, counts,
policy versions, reason codes) and never logs evidence or reconstructed
payloads.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Final

from memory.contracts import MemoryReconstructor, MemoryService
from memory.dynamics import reconstruct_v2
from memory.models import (
    ConceptMention,
    EntityMention,
    MemoryAgeSemantics,
    MemoryId,
    MemoryLineage,
    MemoryProvenance,
    MemoryRankedHit,
    MemoryRecallContext,
    MemoryRecallRequest,
    MemoryRecallResult,
    MemoryRelation,
    MemoryRunId,
    MemorySituationContext,
    MemoryTrace,
    PendingSemanticizationIntent,
    RecallEvidence,
    RecallSourceEvidence,
    ReconsolidationIntent,
    ReconstructedMemory,
    ReconstructionRecord,
    validate_reconstructed_memory,
)
from memory.scoring import logical_age_ticks

__all__ = [
    "DeterministicMemoryReconstructor",
    "MemoryRecallOrchestrator",
    "build_recall_evidence",
    "plan_reconsolidation",
]

_LOG: Final[logging.Logger] = logging.getLogger("memory.reconstruction")


class DeterministicMemoryReconstructor:
    """Versioned deterministic reconstructor: projects ranked evidence only.

    Confidence and salience are rank-weighted means over used sources. Concepts,
    entities, relations, and context are merged in source-rank order with
    first-wins mention IDs. No free-form invention and no objective facts.
    """

    async def reconstruct(self, evidence: RecallEvidence) -> ReconstructedMemory:
        if type(evidence) is not RecallEvidence:
            raise TypeError("DeterministicMemoryReconstructor: invalid_evidence")
        if not evidence.sources:
            raise ValueError("DeterministicMemoryReconstructor: empty_sources")

        used = evidence.sources
        source_ids = tuple(item.memory_id for item in used)
        generation = 1 + max(item.generation for item in used)

        weight_total = sum(1.0 / float(item.rank) for item in used)
        confidence = (
            sum(item.confidence * (1.0 / float(item.rank)) for item in used)
            / weight_total
        )
        salience = (
            sum(item.emotional_salience * (1.0 / float(item.rank)) for item in used)
            / weight_total
        )

        concepts = _merge_concepts(used)
        entities = _merge_entities(used)
        relations = _merge_relations(used, concepts=concepts, entities=entities)
        context = _merge_context(used, recall_context=evidence.recall_context)
        narrative = _deterministic_narrative(used)

        if len(narrative) > evidence.policy.max_narrative_chars:
            narrative = narrative[: evidence.policy.max_narrative_chars]

        reconstructed = ReconstructedMemory(
            reconstruction_id=evidence.reconstruction_id,
            owner_id=evidence.owner_id,
            narrative=narrative,
            concepts=concepts,
            entities=entities,
            relations=relations,
            context=context,
            confidence=confidence,
            emotional_salience=salience,
            source_memory_ids=source_ids,
            generation=generation,
            reconstructed_at_tick=evidence.current_tick,
            policy_id=evidence.policy.policy_id,
            policy_version=evidence.policy.version,
            used_provider=False,
            fallback_used=False,
        )
        return validate_reconstructed_memory(reconstructed, evidence=evidence)


def build_recall_evidence(
    *,
    owner_id: object,
    hits: Sequence[MemoryRankedHit],
    request: MemoryRecallRequest,
) -> RecallEvidence:
    """Convert ranked hits plus request beliefs/context into bounded evidence."""
    from agents.models import AgentId

    if type(owner_id) is not AgentId:
        raise TypeError("build_recall_evidence: invalid_owner")
    if type(request) is not MemoryRecallRequest:
        raise TypeError("build_recall_evidence: invalid_request")

    policy = request.reconstruction_policy
    limited_hits = tuple(hits[: policy.max_source_traces])
    sources: list[RecallSourceEvidence] = []
    for index, hit in enumerate(limited_hits, start=1):
        if hit.trace.owner_id != owner_id:
            raise ValueError("build_recall_evidence: owner_mismatch")
        episode_age = logical_age_ticks(
            hit.trace,
            current_tick=request.retrieve.current_tick,
            age_semantics=MemoryAgeSemantics.EPISODE,
        )
        storage_age = logical_age_ticks(
            hit.trace,
            current_tick=request.retrieve.current_tick,
            age_semantics=MemoryAgeSemantics.STORAGE,
        )
        sources.append(
            RecallSourceEvidence(
                memory_id=hit.trace.memory_id,
                owner_id=hit.trace.owner_id,
                rank=index,
                score=hit.score,
                concepts=hit.trace.concepts,
                entities=hit.trace.entities,
                relations=hit.trace.relations,
                context=hit.trace.context,
                emotional_salience=hit.trace.emotional_salience,
                confidence=hit.trace.confidence,
                source_confidence=hit.trace.confidence,
                episode_age_ticks=episode_age,
                storage_age_ticks=storage_age,
                generation=hit.trace.lineage.generation,
                provenance_kind=hit.trace.provenance.kind,
                observed_source_id=hit.trace.provenance.observed_source_id,
            )
        )

    beliefs = tuple(request.beliefs[: policy.max_beliefs])
    for belief in beliefs:
        if belief.owner_id != owner_id:
            raise ValueError("build_recall_evidence: belief_owner_mismatch")

    return RecallEvidence(
        owner_id=owner_id,
        current_tick=request.retrieve.current_tick,
        reconstruction_id=request.reconstruction_id,
        policy=policy,
        sources=tuple(sources),
        beliefs=beliefs,
        recall_context=request.recall_context,
        derived_memory_id=request.derived_memory_id,
    )


def plan_reconsolidation(
    *,
    reconstructed: ReconstructedMemory,
    evidence: RecallEvidence,
    run_id: MemoryRunId,
    source_traces: Mapping[MemoryId, MemoryTrace],
) -> ReconsolidationIntent:
    """Validate append-only reconsolidation intent against pre-existing parents."""
    if evidence.derived_memory_id is None:
        raise ValueError("plan_reconsolidation: missing_derived_id")
    if type(run_id) is not MemoryRunId:
        raise TypeError("plan_reconsolidation: invalid_run_id")

    for source_id in reconstructed.source_memory_ids:
        parent = source_traces.get(source_id)
        if parent is None:
            raise ValueError("plan_reconsolidation: missing_source")
        if parent.owner_id != reconstructed.owner_id:
            raise ValueError("plan_reconsolidation: owner_mismatch")
        if parent.memory_id == evidence.derived_memory_id:
            raise ValueError("plan_reconsolidation: not_fresh")

    expected_generation = 1 + max(
        item.generation for item in evidence.sources
    )
    if reconstructed.generation != expected_generation:
        raise ValueError("plan_reconsolidation: generation_not_dense")

    principal = reconstructed.source_memory_ids[0]
    principal_trace = source_traces[principal]
    record = ReconstructionRecord(
        reconstruction_id=reconstructed.reconstruction_id,
        run_id=run_id,
        owner_id=reconstructed.owner_id,
        source_memory_ids=reconstructed.source_memory_ids,
        reconstructed=reconstructed,
        created_tick=reconstructed.reconstructed_at_tick,
        policy_id=reconstructed.policy_id,
        policy_version=reconstructed.policy_version,
        used_provider=reconstructed.used_provider,
        fallback_used=reconstructed.fallback_used,
        prompt_version=reconstructed.prompt_version,
        schema_version=reconstructed.schema_version,
    )
    derived = MemoryTrace(
        memory_id=evidence.derived_memory_id,
        owner_id=reconstructed.owner_id,
        world_revision=principal_trace.world_revision,
        concepts=reconstructed.concepts,
        entities=reconstructed.entities,
        relations=reconstructed.relations,
        context=reconstructed.context,
        emotional_salience=reconstructed.emotional_salience,
        confidence=reconstructed.confidence,
        provenance=MemoryProvenance(
            kind=principal_trace.provenance.kind,
            source_tick=principal_trace.provenance.source_tick,
            observed_source_id=principal_trace.provenance.observed_source_id,
            speaker_id=principal_trace.provenance.speaker_id,
        ),
        created_tick=reconstructed.reconstructed_at_tick,
        source_tick=principal_trace.source_tick,
        last_access_tick=reconstructed.reconstructed_at_tick,
        access_count=0,
        lineage=MemoryLineage(
            supersedes_memory_id=principal,
            generation=reconstructed.generation,
            source_memory_ids=reconstructed.source_memory_ids,
            reconstruction_id=reconstructed.reconstruction_id,
        ),
    )
    return ReconsolidationIntent(record=record, derived_trace=derived)


class MemoryRecallOrchestrator:
    """Owner-scoped recall: retrieve → evidence → reconstruct → optional plan."""

    __slots__ = ("_reconstructor",)

    def __init__(self, reconstructor: MemoryReconstructor | None = None) -> None:
        self._reconstructor: MemoryReconstructor = (
            DeterministicMemoryReconstructor()
            if reconstructor is None
            else reconstructor
        )

    async def recall(
        self,
        service: MemoryService,
        request: MemoryRecallRequest,
    ) -> MemoryRecallResult:
        if type(request) is not MemoryRecallRequest:
            _LOG.error(
                "memory_recall_invalid",
                extra={
                    "operation": "recall",
                    "reason_code": "invalid_request",
                },
            )
            raise TypeError("MemoryRecallOrchestrator.recall: invalid_request")

        scope = service.scope
        dynamics_version = (
            None
            if request.dynamics_policy is None
            else request.dynamics_policy.version
        )
        _LOG.debug(
            "memory_recall_start",
            extra={
                "operation": "recall",
                "run_id": scope.run_id.value,
                "owner_id": scope.owner_id.value,
                "tick": request.retrieve.current_tick,
                "policy_version": request.reconstruction_policy.version,
                "dynamics_policy_version": dynamics_version,
                "reconstruction_id": request.reconstruction_id.value,
            },
        )

        retrieve_result = await service.retrieve(request.retrieve)
        try:
            evidence = build_recall_evidence(
                owner_id=scope.owner_id,
                hits=retrieve_result.hits,
                request=request,
            )
        except ValueError as exc:
            reason = str(exc).rsplit(":", maxsplit=1)[-1].strip()
            _LOG.warning(
                "memory_recall_evidence_rejected",
                extra={
                    "operation": "recall",
                    "run_id": scope.run_id.value,
                    "owner_id": scope.owner_id.value,
                    "reason_code": reason,
                },
            )
            raise

        if not evidence.sources:
            _LOG.debug(
                "memory_recall_empty_sources",
                extra={
                    "operation": "recall",
                    "run_id": scope.run_id.value,
                    "owner_id": scope.owner_id.value,
                    "reason_code": "empty_sources",
                    "candidate_count": retrieve_result.candidate_count,
                },
            )
            return MemoryRecallResult(
                reconstructions=(),
                pending_accesses=retrieve_result.pending_accesses,
                evidence=evidence,
                reconsolidation=None,
                audits=(),
                pending_semanticization=None,
            )

        audits: tuple = ()
        if request.dynamics_policy is not None:
            access_counts = {
                hit.trace.memory_id.value: hit.trace.access_count
                for hit in retrieve_result.hits
            }
            _LOG.debug(
                "memory_recall_v2_start",
                extra={
                    "operation": "recall",
                    "run_id": scope.run_id.value,
                    "owner_id": scope.owner_id.value,
                    "tick": request.retrieve.current_tick,
                    "dynamics_policy_version": request.dynamics_policy.version,
                    "source_count": len(evidence.sources),
                    "reconstruction_id": request.reconstruction_id.value,
                },
            )
            try:
                dynamics_result = reconstruct_v2(
                    evidence,
                    policy=request.dynamics_policy,
                    access_counts=access_counts,
                )
            except (TypeError, ValueError) as exc:
                reason = str(exc).rsplit(":", maxsplit=1)[-1].strip()
                _LOG.error(
                    "memory_recall_v2_failed",
                    extra={
                        "operation": "recall",
                        "run_id": scope.run_id.value,
                        "owner_id": scope.owner_id.value,
                        "reason_code": reason,
                        "dynamics_policy_version": request.dynamics_policy.version,
                    },
                )
                raise
            reconstructed = dynamics_result.reconstructed
            audits = (dynamics_result.audit,)
            pending_semanticization: PendingSemanticizationIntent | None = None
            hint = dynamics_result.semanticization
            if hint is not None and hint.should_revise:
                pending_semanticization = PendingSemanticizationIntent(
                    owner_id=evidence.owner_id,
                    tick=evidence.current_tick,
                    source_memory_ids=hint.source_memory_ids,
                    gist_concepts=hint.gist_concepts,
                )
            code_counts: dict[str, int] = {}
            for code in dynamics_result.audit.distortion_codes:
                code_counts[code.value] = code_counts.get(code.value, 0) + 1
            _LOG.debug(
                "memory_recall_v2_complete",
                extra={
                    "operation": "recall",
                    "run_id": scope.run_id.value,
                    "owner_id": scope.owner_id.value,
                    "dynamics_policy_version": request.dynamics_policy.version,
                    "source_count": len(evidence.sources),
                    "selected_count": len(dynamics_result.audit.selected_ids),
                    "competitor_count": len(dynamics_result.audit.competitor_ids),
                    "distortion_code_counts": code_counts,
                    "pending_reconsolidation": bool(
                        request.reconstruction_policy.reconsolidate
                    ),
                    "semanticization_pending": pending_semanticization is not None,
                },
            )
        else:
            reconstructed = await self._reconstructor.reconstruct(evidence)
            reconstructed = validate_reconstructed_memory(
                reconstructed, evidence=evidence
            )
            pending_semanticization = None

        reconsolidation: ReconsolidationIntent | None = None
        if request.reconstruction_policy.reconsolidate:
            source_map = {
                hit.trace.memory_id: hit.trace for hit in retrieve_result.hits
            }
            # Ensure all referenced sources are present even if limit trimmed.
            for source_id in reconstructed.source_memory_ids:
                if source_id not in source_map:
                    fetched = await service.get(source_id)
                    if fetched is None:
                        raise ValueError("MemoryRecallOrchestrator: missing_source")
                    source_map[source_id] = fetched
            reconsolidation = plan_reconsolidation(
                reconstructed=reconstructed,
                evidence=evidence,
                run_id=scope.run_id,
                source_traces=source_map,
            )
            _LOG.info(
                "memory_recall_reconsolidation_intent",
                extra={
                    "operation": "recall",
                    "run_id": scope.run_id.value,
                    "owner_id": scope.owner_id.value,
                    "reconstruction_id": request.reconstruction_id.value,
                    "reconsolidation_count": 1,
                    "generation": reconstructed.generation,
                },
            )

        _LOG.debug(
            "memory_recall_complete",
            extra={
                "operation": "recall",
                "run_id": scope.run_id.value,
                "owner_id": scope.owner_id.value,
                "tick": request.retrieve.current_tick,
                "policy_version": request.reconstruction_policy.version,
                "dynamics_policy_version": dynamics_version,
                "reconstruction_id": request.reconstruction_id.value,
                "source_count": len(evidence.sources),
                "belief_count": len(evidence.beliefs),
                "result_count": 1,
                "audit_count": len(audits),
                "fallback_used": reconstructed.fallback_used,
                "used_provider": reconstructed.used_provider,
                "generation": reconstructed.generation,
            },
        )
        return MemoryRecallResult(
            reconstructions=(reconstructed,),
            pending_accesses=retrieve_result.pending_accesses,
            evidence=evidence,
            reconsolidation=reconsolidation,
            audits=audits,
            pending_semanticization=pending_semanticization,
        )


def _merge_concepts(
    sources: Sequence[RecallSourceEvidence],
) -> tuple[ConceptMention, ...]:
    seen: set[str] = set()
    out: list[ConceptMention] = []
    for source in sources:
        for concept in source.concepts:
            if concept.mention_id.value in seen:
                continue
            seen.add(concept.mention_id.value)
            out.append(concept)
    return tuple(out)


def _merge_entities(
    sources: Sequence[RecallSourceEvidence],
) -> tuple[EntityMention, ...]:
    seen: set[str] = set()
    out: list[EntityMention] = []
    for source in sources:
        for entity in source.entities:
            if entity.mention_id.value in seen:
                continue
            seen.add(entity.mention_id.value)
            out.append(entity)
    return tuple(out)


def _merge_relations(
    sources: Sequence[RecallSourceEvidence],
    *,
    concepts: Sequence[ConceptMention],
    entities: Sequence[EntityMention],
) -> tuple[MemoryRelation, ...]:
    concept_ids = {item.mention_id.value for item in concepts}
    entity_ids = {item.mention_id.value for item in entities}
    seen: set[str] = set()
    out: list[MemoryRelation] = []
    for source in sources:
        for relation in source.relations:
            rid = relation.relation_id.value
            if rid in seen or rid in concept_ids or rid in entity_ids:
                continue
            subject_ok = (
                relation.subject.mention_id.value in concept_ids
                or relation.subject.mention_id.value in entity_ids
            )
            object_ok = (
                relation.object.mention_id.value in concept_ids
                or relation.object.mention_id.value in entity_ids
            )
            if not (subject_ok and object_ok):
                continue
            seen.add(rid)
            out.append(relation)
    return tuple(out)


def _merge_context(
    sources: Sequence[RecallSourceEvidence],
    *,
    recall_context: MemoryRecallContext,
) -> MemorySituationContext:
    location = recall_context.location_id
    tags: list[str] = []
    seen_tags: set[str] = set()
    if location is None:
        for source in sources:
            if source.context.location_id is not None:
                location = source.context.location_id
                break
    for tag in recall_context.tags:
        if tag not in seen_tags:
            seen_tags.add(tag)
            tags.append(tag)
    for source in sources:
        for tag in source.context.tags:
            if tag not in seen_tags:
                seen_tags.add(tag)
                tags.append(tag)
    return MemorySituationContext(location_id=location, tags=tuple(tags))


def _deterministic_narrative(sources: Sequence[RecallSourceEvidence]) -> str:
    """Stable structural narrative from concept labels only (no invention)."""
    parts: list[str] = []
    for source in sources:
        concepts = ",".join(item.concept for item in source.concepts) or "empty"
        parts.append(f"{source.memory_id.value}:{concepts}")
    return ";".join(parts)
