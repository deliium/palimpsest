"""Optional structured LLM reconstruction adapter for cognition.

Maps bounded ``RecallEvidence`` into an ``LLMRequest``, calls an injected
``LLMProvider``, and translates an exact ``StructuredOutput`` candidate into
project-owned ``ReconstructedMemory`` values only after semantic validation.
Falls back to the deterministic reconstructor on configured provider or
validation failures. Propagates ``CancelledError``. Never logs evidence,
beliefs, narratives, prompts, schemas, or provider payloads.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import replace
from typing import Final

from llm import (
    LLMProvider,
    LLMRequest,
    LLMRequestContext,
    LLMRequestOptions,
    StructuredOutput,
    render_prompt,
)
from llm.errors import LLMError
from memory.models import (
    ConceptMention,
    EntityMention,
    MemoryId,
    MemoryRelation,
    MemorySituationContext,
    MentionId,
    RecallEvidence,
    ReconstructedMemory,
    ReconstructionFallbackMode,
    RelationEndpoint,
    RelationEndpointKind,
    validate_reconstructed_memory,
)
from memory.reconstruction import DeterministicMemoryReconstructor
from world.identifiers import EntityId

__all__ = [
    "LLMMemoryReconstructor",
    "ReconstructedMemoryCandidate",
]

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.reconstruction")
_PROMPT_NAME: Final[str] = "reconstructive_memory"
_PROMPT_VERSION: Final[str] = "v1"
_SCHEMA_VERSION: Final[str] = "reconstructive_memory.candidate.v1"
_MAX_EVIDENCE_JSON_CHARS: Final[int] = 50_000


class ReconstructedMemoryCandidate(StructuredOutput):
    """Exact structured LLM candidate for reconstructive recall.

    Structural validity does not establish truth, ownership, or authority.
    """

    narrative: str
    concepts: tuple[str, ...]
    entity_labels: tuple[str, ...]
    entity_ids: tuple[str | None, ...]
    relation_predicates: tuple[str, ...]
    relation_subject_indexes: tuple[int, ...]
    relation_object_indexes: tuple[int, ...]
    relation_subject_kinds: tuple[str, ...]
    relation_object_kinds: tuple[str, ...]
    context_tags: tuple[str, ...]
    location_id: str | None = None
    confidence: float
    emotional_salience: float
    source_memory_ids: tuple[str, ...]


class LLMMemoryReconstructor:
    """Cognition-side LLM reconstructor with fail-closed deterministic fallback."""

    __slots__ = (
        "_fallback",
        "_options",
        "_provider",
        "_request_id_prefix",
    )

    def __init__(
        self,
        provider: LLMProvider,
        *,
        options: LLMRequestOptions | None = None,
        request_id_prefix: str = "recall",
    ) -> None:
        self._provider = provider
        self._options = options
        self._request_id_prefix = request_id_prefix
        self._fallback = DeterministicMemoryReconstructor()

    async def reconstruct(self, evidence: RecallEvidence) -> ReconstructedMemory:
        if type(evidence) is not RecallEvidence:
            raise TypeError("LLMMemoryReconstructor: invalid_evidence")
        if not evidence.policy.allow_provider:
            _LOG.info(
                "memory_llm_reconstruction_skipped",
                extra={
                    "operation": "llm_reconstruct",
                    "reconstruction_id": evidence.reconstruction_id.value,
                    "tick": evidence.current_tick,
                    "policy_version": evidence.policy.version,
                    "fallback_used": True,
                    "used_provider": False,
                },
            )
            return await self._fallback.reconstruct(evidence)

        attempt = 1
        _LOG.debug(
            "memory_llm_reconstruction_start",
            extra={
                "operation": "llm_reconstruct",
                "reconstruction_id": evidence.reconstruction_id.value,
                "tick": evidence.current_tick,
                "policy_version": evidence.policy.version,
                "prompt_version": _PROMPT_VERSION,
                "schema_version": _SCHEMA_VERSION,
                "source_count": len(evidence.sources),
                "attempt_count": attempt,
            },
        )
        try:
            candidate = await self._generate_candidate(evidence)
            reconstructed = _translate_candidate(candidate, evidence=evidence)
            validated = validate_reconstructed_memory(reconstructed, evidence=evidence)
            _LOG.info(
                "memory_llm_reconstruction_complete",
                extra={
                    "operation": "llm_reconstruct",
                    "reconstruction_id": evidence.reconstruction_id.value,
                    "tick": evidence.current_tick,
                    "policy_version": evidence.policy.version,
                    "prompt_version": _PROMPT_VERSION,
                    "fallback_used": False,
                    "used_provider": True,
                    "generation": validated.generation,
                },
            )
            return validated
        except asyncio.CancelledError:
            _LOG.error(
                "memory_llm_reconstruction_cancelled",
                extra={
                    "operation": "llm_reconstruct",
                    "reconstruction_id": evidence.reconstruction_id.value,
                    "reason_code": "cancelled",
                },
            )
            raise
        except Exception as exc:
            reason = _safe_reason(exc)
            _LOG.warning(
                "memory_llm_reconstruction_rejected",
                extra={
                    "operation": "llm_reconstruct",
                    "reconstruction_id": evidence.reconstruction_id.value,
                    "tick": evidence.current_tick,
                    "reason_code": reason,
                    "attempt_count": attempt,
                },
            )
            if evidence.policy.fallback_mode is ReconstructionFallbackMode.REJECT:
                _LOG.error(
                    "memory_llm_reconstruction_terminal",
                    extra={
                        "operation": "llm_reconstruct",
                        "reconstruction_id": evidence.reconstruction_id.value,
                        "reason_code": reason,
                    },
                )
                raise ValueError(f"LLMMemoryReconstructor: {reason}") from None
            fallback = await self._fallback.reconstruct(evidence)
            marked = replace(fallback, fallback_used=True, used_provider=False)
            _LOG.info(
                "memory_llm_reconstruction_fallback",
                extra={
                    "operation": "llm_reconstruct",
                    "reconstruction_id": evidence.reconstruction_id.value,
                    "tick": evidence.current_tick,
                    "policy_version": evidence.policy.version,
                    "fallback_used": True,
                    "used_provider": False,
                    "reason_code": reason,
                },
            )
            return marked

    async def _generate_candidate(
        self, evidence: RecallEvidence
    ) -> ReconstructedMemoryCandidate:
        evidence_json = _canonical_evidence_json(evidence)
        if len(evidence_json) > _MAX_EVIDENCE_JSON_CHARS:
            raise ValueError("evidence_json_exceeds_max")
        schema_json = json.dumps(
            ReconstructedMemoryCandidate.model_json_schema(),
            sort_keys=True,
            separators=(",", ":"),
        )
        rendered = render_prompt(
            _PROMPT_NAME,
            _PROMPT_VERSION,
            {
                "schema_name": ReconstructedMemoryCandidate.__name__,
                "schema_json": schema_json,
                "evidence_json": evidence_json,
            },
        )
        request = LLMRequest.create(
            messages=rendered.messages,
            response_model=ReconstructedMemoryCandidate,
            context=LLMRequestContext(
                run_id="recall-run",
                agent_id=evidence.owner_id.value,
                tick=evidence.current_tick,
                llm_request_id=(
                    f"{self._request_id_prefix}-{evidence.reconstruction_id.value}"
                ),
            ),
            prompt=rendered.reference,
            options=self._options,
        )
        result = await self._provider.generate(request)
        if type(result.output) is not ReconstructedMemoryCandidate:
            raise TypeError("response_model_mismatch")
        return result.output


def _canonical_evidence_json(evidence: RecallEvidence) -> str:
    payload = {
        "owner_id": evidence.owner_id.value,
        "current_tick": evidence.current_tick,
        "reconstruction_id": evidence.reconstruction_id.value,
        "policy_id": evidence.policy.policy_id,
        "policy_version": evidence.policy.version,
        "sources": [
            {
                "memory_id": source.memory_id.value,
                "rank": source.rank,
                "score": source.score,
                "concepts": [item.concept for item in source.concepts],
                "entities": [
                    {
                        "label": item.label,
                        "entity_id": None
                        if item.entity_id is None
                        else item.entity_id.value,
                    }
                    for item in source.entities
                ],
                "relations": [
                    {
                        "predicate": item.predicate,
                        "subject_kind": item.subject.kind.value,
                        "subject_mention_id": item.subject.mention_id.value,
                        "object_kind": item.object.kind.value,
                        "object_mention_id": item.object.mention_id.value,
                    }
                    for item in source.relations
                ],
                "context_tags": list(source.context.tags),
                "location_id": None
                if source.context.location_id is None
                else source.context.location_id.value,
                "emotional_salience": source.emotional_salience,
                "confidence": source.confidence,
                "source_confidence": source.source_confidence,
                "episode_age_ticks": source.episode_age_ticks,
                "storage_age_ticks": source.storage_age_ticks,
                "generation": source.generation,
            }
            for source in evidence.sources
        ],
        "beliefs": [
            {
                "belief_id": belief.belief_id.value,
                "confidence": belief.confidence,
            }
            for belief in evidence.beliefs
        ],
        "recall_context": {
            "tags": list(evidence.recall_context.tags),
            "location_id": None
            if evidence.recall_context.location_id is None
            else evidence.recall_context.location_id.value,
            "emotional_significance": evidence.recall_context.emotional_significance,
            "social_significance": evidence.recall_context.social_significance,
        },
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _translate_candidate(
    candidate: ReconstructedMemoryCandidate,
    *,
    evidence: RecallEvidence,
) -> ReconstructedMemory:
    allowed_sources = {item.memory_id.value for item in evidence.sources}
    source_ids: list[MemoryId] = []
    seen: set[str] = set()
    for raw in candidate.source_memory_ids:
        if raw not in allowed_sources:
            raise ValueError("unknown_source")
        if raw in seen:
            raise ValueError("duplicate_source")
        seen.add(raw)
        source_ids.append(MemoryId(raw))
    if not source_ids:
        raise ValueError("empty_sources")

    concepts = tuple(
        ConceptMention(mention_id=MentionId(f"c-{index}"), concept=concept)
        for index, concept in enumerate(candidate.concepts, start=1)
    )
    if len(candidate.entity_labels) != len(candidate.entity_ids):
        raise ValueError("entity_length_mismatch")
    entities: list[EntityMention] = []
    for index, (label, entity_raw) in enumerate(
        zip(candidate.entity_labels, candidate.entity_ids, strict=True), start=1
    ):
        entity_id = None if entity_raw is None else EntityId(entity_raw)
        entities.append(
            EntityMention(
                mention_id=MentionId(f"e-{index}"),
                label=label,
                entity_id=entity_id,
            )
        )
    entities_t = tuple(entities)

    n_concepts = len(concepts)
    n_entities = len(entities_t)
    predicates = candidate.relation_predicates
    subj_idx = candidate.relation_subject_indexes
    obj_idx = candidate.relation_object_indexes
    subj_kinds = candidate.relation_subject_kinds
    obj_kinds = candidate.relation_object_kinds
    lengths = {
        len(predicates),
        len(subj_idx),
        len(obj_idx),
        len(subj_kinds),
        len(obj_kinds),
    }
    if len(lengths) != 1:
        raise ValueError("relation_length_mismatch")

    relations: list[MemoryRelation] = []
    for index, predicate in enumerate(predicates):
        subject = _endpoint(
            kind_raw=subj_kinds[index],
            endpoint_index=subj_idx[index],
            n_concepts=n_concepts,
            n_entities=n_entities,
        )
        obj = _endpoint(
            kind_raw=obj_kinds[index],
            endpoint_index=obj_idx[index],
            n_concepts=n_concepts,
            n_entities=n_entities,
        )
        relations.append(
            MemoryRelation(
                relation_id=MentionId(f"r-{index + 1}"),
                predicate=predicate,
                subject=subject,
                object=obj,
            )
        )

    location_id = None
    if candidate.location_id is not None:
        location_id = EntityId(candidate.location_id)
    context = MemorySituationContext(
        location_id=location_id,
        tags=candidate.context_tags,
    )
    generation = 1 + max(item.generation for item in evidence.sources)
    return ReconstructedMemory(
        reconstruction_id=evidence.reconstruction_id,
        owner_id=evidence.owner_id,
        narrative=candidate.narrative,
        concepts=concepts,
        entities=entities_t,
        relations=tuple(relations),
        context=context,
        confidence=candidate.confidence,
        emotional_salience=candidate.emotional_salience,
        source_memory_ids=tuple(source_ids),
        generation=generation,
        reconstructed_at_tick=evidence.current_tick,
        policy_id=evidence.policy.policy_id,
        policy_version=evidence.policy.version,
        used_provider=True,
        fallback_used=False,
        prompt_version=_PROMPT_VERSION,
        schema_version=_SCHEMA_VERSION,
    )


def _endpoint(
    *,
    kind_raw: str,
    endpoint_index: int,
    n_concepts: int,
    n_entities: int,
) -> RelationEndpoint:
    if kind_raw == RelationEndpointKind.CONCEPT.value:
        if endpoint_index < 0 or endpoint_index >= n_concepts:
            raise ValueError("invalid_relation_endpoint")
        return RelationEndpoint(
            kind=RelationEndpointKind.CONCEPT,
            mention_id=MentionId(f"c-{endpoint_index + 1}"),
        )
    if kind_raw == RelationEndpointKind.ENTITY.value:
        if endpoint_index < 0 or endpoint_index >= n_entities:
            raise ValueError("invalid_relation_endpoint")
        return RelationEndpoint(
            kind=RelationEndpointKind.ENTITY,
            mention_id=MentionId(f"e-{endpoint_index + 1}"),
        )
    raise ValueError("unsupported_endpoint_kind")


def _safe_reason(exc: BaseException) -> str:
    if isinstance(exc, asyncio.CancelledError):
        return "cancelled"
    if isinstance(exc, LLMError):
        return exc.code.value
    if isinstance(exc, ValueError):
        text = str(exc)
        if ":" in text:
            return text.rsplit(":", maxsplit=1)[-1].strip() or "validation_rejected"
        return text or "validation_rejected"
    if isinstance(exc, TypeError):
        return "type_error"
    return "provider_failure"
