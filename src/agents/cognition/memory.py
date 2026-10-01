"""Owner-scoped cognition reconstructive memory adapter.

Observational only: maps a bound ``MemoryService.recall`` result into
``RetrievedMemoryContext`` and never mutates stores. Access receipts and
optional reconsolidation intents remain pending until ``AgentRuntime`` applies
them after successful cognition.
"""

from __future__ import annotations

import logging
from typing import Final

from agents.cognition.configuration import MEMORY_POLICY_VERSION
from agents.cognition.models import (
    ActionPlan,
    CognitiveLoopInput,
    DecisionMetadata,
    InterpretedPerception,
    MemoryUpdateIntent,
    MemoryUpdateKind,
    ReferenceEpisode,
    RetrievedMemoryContext,
    SelectedIntention,
)
from agents.models import AgentId
from memory.beliefs import SemanticBelief
from memory.contracts import BeliefReader, MemoryService
from memory.models import (
    Belief,
    BeliefId,
    ConceptMention,
    EntityMention,
    MemoryDynamicsPolicy,
    MemoryId,
    MemoryLineage,
    MemoryProvenance,
    MemoryQueryContext,
    MemoryQueryFilters,
    MemoryRecallContext,
    MemoryRecallRequest,
    MemoryReconstructionPolicy,
    MemoryRelation,
    MemoryRetrieveRequest,
    MemoryScoringPolicy,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
    RecallAuditRecord,
    ReconstructionId,
    RelationEndpoint,
    RelationEndpointKind,
)
from world.identifiers import EntityId, EventId, WorldRevision
from world.observations import Observation, ObservedOccurrence

__all__ = [
    "DIRECT_OBSERVATION_MEMORY_POLICY_VERSION",
    "DirectObservationMemoryUpdateHook",
    "ReferenceMemoryRetriever",
    "ScopedMemoryRetriever",
    "build_direct_observation_memory_trace",
    "with_violation_relation",
]

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.memory")
_DEFAULT_LIMIT: Final[int] = 8
DIRECT_OBSERVATION_MEMORY_POLICY_VERSION: Final[str] = "direct-observation-memory.v1"


class ScopedMemoryRetriever:
    """Production ``MemoryRetriever`` bound to one owner-scoped ``MemoryService``."""

    __slots__ = (
        "_audits",
        "_belief_reader",
        "_dynamics_policy",
        "_emotion_bias",
        "_limit",
        "_reconstruction_policy",
        "_scoring_policy",
        "_service",
    )

    def __init__(
        self,
        memory_service: MemoryService,
        *,
        scoring_policy: MemoryScoringPolicy,
        reconstruction_policy: MemoryReconstructionPolicy | None = None,
        belief_reader: BeliefReader | None = None,
        limit: int = _DEFAULT_LIMIT,
        emotion_bias: bool = False,
        dynamics_policy: MemoryDynamicsPolicy | None = None,
    ) -> None:
        if type(scoring_policy) is not MemoryScoringPolicy:
            raise TypeError("scoring_policy must be MemoryScoringPolicy")
        if scoring_policy.weights.semantic_relevance > 0.0:
            raise ValueError(
                "ScopedMemoryRetriever V1 requires non-semantic scoring_policy"
            )
        if reconstruction_policy is None:
            reconstruction_policy = MemoryReconstructionPolicy(
                policy_id="cognition-recall",
                version="1",
                allow_provider=False,
            )
        elif type(reconstruction_policy) is not MemoryReconstructionPolicy:
            raise TypeError("reconstruction_policy must be MemoryReconstructionPolicy")
        if limit < 1:
            raise ValueError("limit must be positive")
        if type(emotion_bias) is not bool:
            raise TypeError("emotion_bias must be bool")
        if dynamics_policy is not None and type(dynamics_policy) is not (
            MemoryDynamicsPolicy
        ):
            raise TypeError("dynamics_policy must be MemoryDynamicsPolicy | None")
        self._service = memory_service
        self._scoring_policy = scoring_policy
        self._reconstruction_policy = reconstruction_policy
        self._belief_reader = belief_reader
        self._limit = limit
        self._emotion_bias = emotion_bias
        self._dynamics_policy = dynamics_policy
        self._audits: list[RecallAuditRecord] = []

    def export_audits(self) -> tuple[RecallAuditRecord, ...]:
        """Return accumulated V2 recall audits (scientific sink; never agent-facing)."""
        return tuple(self._audits)

    async def retrieve(
        self,
        loop_input: CognitiveLoopInput,
        perception: InterpretedPerception,
    ) -> RetrievedMemoryContext:
        if type(loop_input) is not CognitiveLoopInput:
            raise TypeError("loop_input must be CognitiveLoopInput")
        if type(perception) is not InterpretedPerception:
            raise TypeError("perception must be InterpretedPerception")
        if loop_input.agent_id != perception.owner_id:
            raise ValueError("perception owner must match loop agent")
        if self._service.scope.owner_id != loop_input.agent_id:
            raise ValueError("memory service scope owner mismatch")

        tags = tuple(code.value for code in perception.claim_codes[:16])
        beliefs: tuple[Belief, ...] = ()
        belief_ids: tuple[BeliefId, ...] = ()
        semantic_beliefs: tuple[SemanticBelief, ...] = ()
        if loop_input.snapshot is not None:
            semantic_beliefs = loop_input.snapshot.semantic_beliefs
            for semantic_belief in semantic_beliefs:
                if semantic_belief.owner_id != loop_input.agent_id:
                    raise ValueError("foreign-owner semantic belief snapshot rejected")
        if self._belief_reader is not None:
            beliefs = self._belief_reader.snapshot()
            for belief in beliefs:
                if belief.owner_id != loop_input.agent_id:
                    raise ValueError("foreign-owner belief snapshot rejected")
            belief_ids = tuple(belief.belief_id for belief in beliefs)
        elif semantic_beliefs:
            belief_ids = tuple(
                semantic_belief.belief_id for semantic_belief in semantic_beliefs
            )

        retrieve = MemoryRetrieveRequest(
            current_tick=perception.tick,
            limit=self._limit,
            scoring_policy=self._scoring_policy,
            filters=MemoryQueryFilters(
                location_id=perception.location_id,
                require_active=True,
            ),
            context=MemoryQueryContext(
                location_id=perception.location_id,
                tags=tags,
            ),
            operation_id=(
                f"cog:{loop_input.agent_id.value}:t{perception.tick}:"
                f"{self._scoring_policy.version}"
            ),
        )
        policy = self._reconstruction_policy
        reconstruction_id = ReconstructionId(
            f"recon-{loop_input.agent_id.value}-t{perception.tick}-{policy.version}"
        )
        derived_id: MemoryId | None = None
        if policy.reconsolidate:
            derived_id = MemoryId(
                f"derived-{loop_input.agent_id.value}-t{perception.tick}-"
                f"{policy.version}"
            )
        recall_request = MemoryRecallRequest(
            retrieve=retrieve,
            reconstruction_id=reconstruction_id,
            reconstruction_policy=policy,
            beliefs=beliefs,
            recall_context=MemoryRecallContext(
                location_id=perception.location_id,
                tags=tags,
            ),
            derived_memory_id=derived_id,
            dynamics_policy=self._dynamics_policy,
        )
        # Service recall (incl. V2 dynamics + audits) completes before any
        # emotion re-ranking below. Audit selected_ids are pre-emotion.
        result = await self._service.recall(recall_request)
        if result.audits:
            self._audits.extend(result.audits)

        # Scientific ranked evidence: rebuild hits from evidence sources only as
        # ID metadata. Full ranked_hits require a retrieve; recall already ran
        # retrieve once, so re-rank from evidence without a second service call
        # by mapping source ranks. Downstream keeps traces out of "remembered".
        from memory.models import (
            MemoryRankedHit,
            MemoryScoreBreakdown,
        )

        ranked_hits: list[MemoryRankedHit] = []
        # Prefer loading traces for scientific metadata via get (no access bump).
        for source in result.evidence.sources:
            trace = await self._service.get(source.memory_id)
            if trace is None:
                continue
            if trace.owner_id != loop_input.agent_id:
                _LOG.error(
                    "memory_recall_foreign_owner",
                    extra={
                        "cognition": {
                            "owner_id": loop_input.agent_id.value,
                            "tick": perception.tick,
                            "reason_code": "ownership",
                        }
                    },
                )
                raise ValueError("foreign-owner memory result rejected")
            ranked_hits.append(
                MemoryRankedHit(
                    rank=source.rank,
                    trace=trace,
                    score=source.score,
                    breakdown=MemoryScoreBreakdown(),
                    matched_concept_mention_ids=(),
                    matched_entity_mention_ids=(),
                    scoring_policy_id=self._scoring_policy.policy_id,
                    scoring_policy_version=self._scoring_policy.version,
                    retrieval_tick=perception.tick,
                )
            )

        for reconstructed in result.reconstructions:
            if reconstructed.owner_id != loop_input.agent_id:
                raise ValueError("foreign-owner reconstruction rejected")

        prior = (
            None if loop_input.snapshot is None else loop_input.snapshot.emotional_state
        )
        from agents.cognition.emotion_bias import (
            EMOTION_BIAS_POLICY_VERSION,
            apply_reconstruction_emotion_bias,
            apply_retrieval_emotion_bias,
        )

        ranked_hits_tuple, retrieval_bias = apply_retrieval_emotion_bias(
            ranked_hits,
            prior,
            enabled=self._emotion_bias,
        )
        reconstructions, reconstruction_bias = apply_reconstruction_emotion_bias(
            result.reconstructions,
            prior,
            enabled=self._emotion_bias,
        )
        # Audits stay on MemoryRecallResult only — never on agent context.
        emotion_bias_applied = retrieval_bias or reconstruction_bias
        dynamics_version = (
            None if self._dynamics_policy is None else self._dynamics_policy.version
        )
        memory_ids = tuple(hit.trace.memory_id for hit in ranked_hits_tuple)
        generation = reconstructions[0].generation if reconstructions else 0
        _LOG.debug(
            "memory_recall_mapped",
            extra={
                "cognition": {
                    "owner_id": loop_input.agent_id.value,
                    "tick": perception.tick,
                    "policy_version": self._scoring_policy.version,
                    "reconstruction_policy_version": policy.version,
                    "dynamics_policy_version": dynamics_version,
                    "emotion_bias_policy_version": EMOTION_BIAS_POLICY_VERSION,
                    "emotion_bias_applied": emotion_bias_applied,
                    "audit_count": len(result.audits),
                    "enabled_components": list(
                        self._scoring_policy.weights.enabled_components()
                    ),
                    "candidate_count": result.evidence.policy.max_source_traces,
                    "source_count": len(result.evidence.sources),
                    "result_count": len(ranked_hits_tuple),
                    "reconstruction_count": len(reconstructions),
                    "pending_write_count": 1 if result.reconsolidation else 0,
                    "semanticization_pending": (
                        result.pending_semanticization is not None
                    ),
                    "generation": generation,
                    "used_provider": (
                        reconstructions[0].used_provider if reconstructions else False
                    ),
                    "fallback_used": (
                        reconstructions[0].fallback_used if reconstructions else False
                    ),
                }
            },
        )
        return RetrievedMemoryContext(
            owner_id=loop_input.agent_id,
            memory_ids=memory_ids,
            belief_ids=belief_ids,
            confidence=(reconstructions[0].confidence if reconstructions else 1.0),
            decision_metadata=DecisionMetadata(
                candidate_count=len(result.evidence.sources),
                selection_codes=tuple(
                    f"recon:{item.reconstruction_id.value}" for item in reconstructions
                )
                or tuple(f"rank:{hit.rank}" for hit in ranked_hits_tuple),
            ),
            ranked_hits=ranked_hits_tuple,
            pending_accesses=result.pending_accesses,
            candidate_count=len(result.evidence.sources),
            retrieval_tick=perception.tick,
            scoring_policy_version=self._scoring_policy.version,
            reconstructions=reconstructions,
            reconsolidation=result.reconsolidation,
            reconstruction_policy_version=policy.version,
            semantic_beliefs=semantic_beliefs,
            pending_semanticization=_belief_revision_from_semanticization(
                result.pending_semanticization,
                owner_id=loop_input.agent_id,
            ),
        )


class ReferenceMemoryRetriever:
    """Exact/reference memory: lossless owner-scoped projection of stored traces.

    Uses ``MemoryService.retrieve`` (not reconstructive recall) and maps each
    ranked hit into a ``ReferenceEpisode`` on the same episodic channel
    consumers read via ``episode_facts``.
    """

    __slots__ = (
        "_belief_reader",
        "_emotion_bias",
        "_limit",
        "_scoring_policy",
        "_service",
    )

    def __init__(
        self,
        memory_service: MemoryService,
        *,
        scoring_policy: MemoryScoringPolicy,
        belief_reader: BeliefReader | None = None,
        limit: int = _DEFAULT_LIMIT,
        emotion_bias: bool = False,
    ) -> None:
        if type(scoring_policy) is not MemoryScoringPolicy:
            raise TypeError("scoring_policy must be MemoryScoringPolicy")
        if scoring_policy.weights.semantic_relevance > 0.0:
            raise ValueError(
                "ReferenceMemoryRetriever V1 requires non-semantic scoring_policy"
            )
        if limit < 1:
            raise ValueError("limit must be positive")
        if type(emotion_bias) is not bool:
            raise TypeError("emotion_bias must be bool")
        self._service = memory_service
        self._scoring_policy = scoring_policy
        self._belief_reader = belief_reader
        self._limit = limit
        self._emotion_bias = emotion_bias

    async def retrieve(
        self,
        loop_input: CognitiveLoopInput,
        perception: InterpretedPerception,
    ) -> RetrievedMemoryContext:
        if type(loop_input) is not CognitiveLoopInput:
            raise TypeError("loop_input must be CognitiveLoopInput")
        if type(perception) is not InterpretedPerception:
            raise TypeError("perception must be InterpretedPerception")
        if loop_input.agent_id != perception.owner_id:
            raise ValueError("perception owner must match loop agent")
        if self._service.scope.owner_id != loop_input.agent_id:
            raise ValueError("memory service scope owner mismatch")

        tags = tuple(code.value for code in perception.claim_codes[:16])
        belief_ids: tuple[BeliefId, ...] = ()
        semantic_beliefs: tuple[SemanticBelief, ...] = ()
        if loop_input.snapshot is not None:
            semantic_beliefs = loop_input.snapshot.semantic_beliefs
            for semantic_belief in semantic_beliefs:
                if semantic_belief.owner_id != loop_input.agent_id:
                    raise ValueError("foreign-owner semantic belief snapshot rejected")
            belief_ids = tuple(item.belief_id for item in semantic_beliefs)
        if self._belief_reader is not None:
            beliefs = self._belief_reader.snapshot()
            for belief in beliefs:
                if belief.owner_id != loop_input.agent_id:
                    raise ValueError("foreign-owner belief snapshot rejected")
            belief_ids = tuple(belief.belief_id for belief in beliefs)

        retrieve = MemoryRetrieveRequest(
            current_tick=perception.tick,
            limit=self._limit,
            scoring_policy=self._scoring_policy,
            filters=MemoryQueryFilters(
                location_id=perception.location_id,
                require_active=True,
            ),
            context=MemoryQueryContext(
                location_id=perception.location_id,
                tags=tags,
            ),
            operation_id=(
                f"ref:{loop_input.agent_id.value}:t{perception.tick}:"
                f"{self._scoring_policy.version}"
            ),
        )
        result = await self._service.retrieve(retrieve)
        prior = (
            None if loop_input.snapshot is None else loop_input.snapshot.emotional_state
        )
        from agents.cognition.emotion_bias import (
            EMOTION_BIAS_POLICY_VERSION,
            apply_retrieval_emotion_bias,
        )

        biased_hits, retrieval_bias = apply_retrieval_emotion_bias(
            result.hits,
            prior,
            enabled=self._emotion_bias,
        )
        reference_episodes: list[ReferenceEpisode] = []
        for hit in biased_hits:
            if hit.trace.owner_id != loop_input.agent_id:
                _LOG.error(
                    "memory_reference_foreign_owner",
                    extra={
                        "cognition": {
                            "owner_id": loop_input.agent_id.value,
                            "tick": perception.tick,
                            "reason_code": "ownership",
                        }
                    },
                )
                raise ValueError("foreign-owner memory result rejected")
            reference_episodes.append(
                ReferenceEpisode.from_trace(
                    hit.trace,
                    policy_id="cognition-reference",
                    policy_version=MEMORY_POLICY_VERSION,
                )
            )
        memory_ids = tuple(hit.trace.memory_id for hit in biased_hits)
        confidence = reference_episodes[0].confidence if reference_episodes else 1.0
        _LOG.debug(
            "memory_reference_mapped",
            extra={
                "cognition": {
                    "owner_id": loop_input.agent_id.value,
                    "tick": perception.tick,
                    "policy_version": MEMORY_POLICY_VERSION,
                    "emotion_bias_policy_version": EMOTION_BIAS_POLICY_VERSION,
                    "emotion_bias_applied": retrieval_bias,
                    "mode": "reference",
                    "candidate_count": result.candidate_count,
                    "result_count": len(reference_episodes),
                    "status": "complete",
                }
            },
        )
        return RetrievedMemoryContext(
            owner_id=loop_input.agent_id,
            memory_ids=memory_ids,
            belief_ids=belief_ids,
            confidence=confidence,
            decision_metadata=DecisionMetadata(
                candidate_count=result.candidate_count,
                selection_codes=tuple(
                    f"ref:{item.episode_id}" for item in reference_episodes
                )
                or tuple(f"rank:{hit.rank}" for hit in biased_hits),
            ),
            ranked_hits=biased_hits,
            pending_accesses=result.pending_accesses,
            candidate_count=result.candidate_count,
            retrieval_tick=perception.tick,
            scoring_policy_version=self._scoring_policy.version,
            reference_episodes=tuple(reference_episodes),
            semantic_beliefs=semantic_beliefs,
        )


def _memory_id_for_occurrence(
    *,
    owner_id: AgentId,
    source_event_id: EventId | None,
    kind: str,
    tick: int,
) -> MemoryId:
    event_token = "none" if source_event_id is None else source_event_id.value
    raw = f"do-{owner_id.value}-{event_token}-{kind}-t{tick}"
    if len(raw) > 128:
        raw = raw[:128]
    return MemoryId(raw)


def _memory_id_for_scene(*, owner_id: AgentId, tick: int, revision: int) -> MemoryId:
    raw = f"do-scene-{owner_id.value}-t{tick}-r{revision}"
    if len(raw) > 128:
        raw = raw[:128]
    return MemoryId(raw)


def build_direct_observation_memory_trace(
    *,
    owner_id: AgentId,
    observation_tick: int,
    observation_revision: WorldRevision,
    occurrence: ObservedOccurrence,
    location_id: EntityId | None,
) -> MemoryTrace:
    """Build a fresh direct-observation trace from one owned occurrence.

    Uses only redacted observation fields and an opaque ``EventId`` correlation.
    Never accepts or dereferences ``WorldEvent`` payloads.
    """
    if type(occurrence) is not ObservedOccurrence:
        raise TypeError("occurrence must be ObservedOccurrence")
    if type(observation_revision) is not WorldRevision:
        raise TypeError("observation_revision must be WorldRevision")
    source_tick = occurrence.provenance.source_tick
    concepts: list[ConceptMention] = [
        ConceptMention(mention_id=MentionId("c-kind"), concept=occurrence.kind)
    ]
    entities: list[EntityMention] = []
    if occurrence.actor_id is not None:
        entities.append(
            EntityMention(
                mention_id=MentionId("e-actor"),
                label="actor",
                entity_id=occurrence.actor_id,
            )
        )
    if occurrence.other_entity_id is not None:
        entities.append(
            EntityMention(
                mention_id=MentionId("e-other"),
                label="other",
                entity_id=occurrence.other_entity_id,
            )
        )
    if occurrence.destination_id is not None:
        entities.append(
            EntityMention(
                mention_id=MentionId("e-dest"),
                label="destination",
                entity_id=occurrence.destination_id,
            )
        )
    relations: list[MemoryRelation] = []
    if occurrence.actor_id is not None and occurrence.other_entity_id is not None:
        relations.append(
            MemoryRelation(
                relation_id=MentionId("r-occ"),
                subject=RelationEndpoint(
                    kind=RelationEndpointKind.ENTITY,
                    mention_id=MentionId("e-actor"),
                ),
                predicate=occurrence.kind,
                object=RelationEndpoint(
                    kind=RelationEndpointKind.ENTITY,
                    mention_id=MentionId("e-other"),
                ),
            )
        )
    tags = ("direct", "occurrence", occurrence.kind, occurrence.audience_role.value)
    confidence = (
        0.9
        if occurrence.success is True
        else (0.7 if occurrence.success is False else 0.8)
    )
    return MemoryTrace(
        memory_id=_memory_id_for_occurrence(
            owner_id=owner_id,
            source_event_id=occurrence.provenance.source_event_id,
            kind=occurrence.kind,
            tick=observation_tick,
        ),
        owner_id=owner_id,
        world_revision=observation_revision,
        concepts=tuple(concepts),
        entities=tuple(entities),
        relations=tuple(relations),
        context=MemorySituationContext(location_id=location_id, tags=tags),
        emotional_salience=0.4 if occurrence.success is False else 0.3,
        confidence=confidence,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=source_tick,
            observed_source_id=occurrence.provenance.source_event_id,
        ),
        created_tick=observation_tick,
        source_tick=source_tick,
        last_access_tick=observation_tick,
        access_count=0,
        lineage=MemoryLineage(),
    )


def with_violation_relation(
    trace: MemoryTrace,
    *,
    subject_entity_id: EntityId,
    object_entity_id: EntityId,
) -> MemoryTrace:
    """Return a copy whose relations include predicate ``violated``.

    ``build_direct_observation_memory_trace`` is unchanged. Disabled claim
    mode does not call this helper.
    """
    if type(trace) is not MemoryTrace:
        raise TypeError("trace must be MemoryTrace")
    if type(subject_entity_id) is not EntityId or type(object_entity_id) is not (
        EntityId
    ):
        raise TypeError("violation endpoints must be EntityId")
    entities = list(trace.entities)

    def mention_for(entity_id: EntityId, preferred: str, label: str) -> MentionId:
        for item in entities:
            if item.entity_id == entity_id:
                return item.mention_id
        mention_id = MentionId(preferred)
        entities.append(
            EntityMention(
                mention_id=mention_id,
                label=label,
                entity_id=entity_id,
            )
        )
        return mention_id

    subject = mention_for(subject_entity_id, "e-subject", "actor")
    obj = mention_for(object_entity_id, "e-claim", "other")
    for relation in trace.relations:
        if (
            relation.predicate == "violated"
            and relation.subject.mention_id == subject
            and relation.object.mention_id == obj
        ):
            return trace
    relation_id = MentionId("r-violated")
    taken = {item.relation_id.value for item in trace.relations}
    suffix = 2
    while relation_id.value in taken:
        relation_id = MentionId(f"r-violated-{suffix}")
        suffix += 1
    relation = MemoryRelation(
        relation_id=relation_id,
        predicate="violated",
        subject=RelationEndpoint(
            kind=RelationEndpointKind.ENTITY,
            mention_id=subject,
        ),
        object=RelationEndpoint(
            kind=RelationEndpointKind.ENTITY,
            mention_id=obj,
        ),
    )
    return MemoryTrace(
        memory_id=trace.memory_id,
        owner_id=trace.owner_id,
        world_revision=trace.world_revision,
        concepts=trace.concepts,
        entities=tuple(entities),
        relations=(*trace.relations, relation),
        context=trace.context,
        emotional_salience=trace.emotional_salience,
        confidence=trace.confidence,
        provenance=trace.provenance,
        created_tick=trace.created_tick,
        source_tick=trace.source_tick,
        last_access_tick=trace.last_access_tick,
        access_count=trace.access_count,
        expires_at_tick=trace.expires_at_tick,
        forgotten_at_tick=trace.forgotten_at_tick,
        lineage=trace.lineage,
        embedding=trace.embedding,
    )


def build_direct_scene_memory_trace(
    *,
    owner_id: AgentId,
    observation: Observation,
    location_id: EntityId | None,
) -> MemoryTrace | None:
    """Build one scene-level direct trace from visible observation fields."""
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    concepts: list[ConceptMention] = []
    entities: list[EntityMention] = []
    index = 0
    for resource in observation.resources:
        concepts.append(
            ConceptMention(
                mention_id=MentionId(f"c-res-{index}"),
                concept=f"resource:{resource.kind.value}",
            )
        )
        entities.append(
            EntityMention(
                mention_id=MentionId(f"e-res-{index}"),
                label="resource",
                entity_id=resource.entity_id,
            )
        )
        index += 1
    for body in observation.visible_bodies:
        if body.entity_id == observation.observer_id:
            continue
        entities.append(
            EntityMention(
                mention_id=MentionId(f"e-body-{index}"),
                label="body",
                entity_id=body.entity_id,
            )
        )
        concepts.append(
            ConceptMention(
                mention_id=MentionId(f"c-body-{index}"),
                concept="visible_body",
            )
        )
        index += 1
    for item in observation.items:
        concepts.append(
            ConceptMention(
                mention_id=MentionId(f"c-item-{index}"),
                concept=f"item:{item.kind.value}",
            )
        )
        entities.append(
            EntityMention(
                mention_id=MentionId(f"e-item-{index}"),
                label="item",
                entity_id=item.entity_id,
            )
        )
        index += 1
    if not concepts and not entities:
        return None
    tags = ("direct", "scene")
    return MemoryTrace(
        memory_id=_memory_id_for_scene(
            owner_id=owner_id,
            tick=observation.tick,
            revision=observation.revision.value,
        ),
        owner_id=owner_id,
        world_revision=observation.revision,
        concepts=tuple(concepts[:32]),
        entities=tuple(entities[:32]),
        relations=(),
        context=MemorySituationContext(location_id=location_id, tags=tags),
        emotional_salience=0.2,
        confidence=0.85,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=observation.tick,
            observed_source_id=None,
        ),
        created_tick=observation.tick,
        source_tick=observation.tick,
        last_access_tick=observation.tick,
        access_count=0,
        lineage=MemoryLineage(),
    )


class DirectObservationMemoryUpdateHook:
    """Propose WRITE_MEMORY intents from owner-visible observation evidence."""

    __slots__ = ()

    async def propose_updates(
        self,
        loop_input: CognitiveLoopInput,
        plan: ActionPlan,
        perception: InterpretedPerception,
        memory: RetrievedMemoryContext,
        intention: SelectedIntention,
        self_state: object | None = None,
    ) -> tuple[MemoryUpdateIntent, ...]:
        _ = plan, intention, memory, self_state
        owner = loop_input.agent_id
        observation = loop_input.observation
        tick = observation.tick
        seen_ids: set[str] = set()
        if loop_input.snapshot is not None:
            for trace in loop_input.snapshot.memories:
                if trace.owner_id != owner:
                    continue
                if trace.provenance.kind is not MemorySourceKind.DIRECT_OBSERVATION:
                    continue
                seen_ids.add(trace.memory_id.value)
                if trace.provenance.observed_source_id is not None:
                    seen_ids.add(f"evt:{trace.provenance.observed_source_id.value}")

        intents: list[MemoryUpdateIntent] = []
        proposed = 0
        deduped = 0
        for occurrence in observation.occurrences:
            if type(occurrence) is not ObservedOccurrence:
                _LOG.error(
                    "direct_observation_memory_rejected",
                    extra={
                        "cognition": {
                            "owner_id": owner.value,
                            "tick": tick,
                            "reason_code": "invalid_occurrence_type",
                        }
                    },
                )
                continue
            event_key = (
                None
                if occurrence.provenance.source_event_id is None
                else f"evt:{occurrence.provenance.source_event_id.value}"
            )
            try:
                trace = build_direct_observation_memory_trace(
                    owner_id=owner,
                    observation_tick=tick,
                    observation_revision=observation.revision,
                    occurrence=occurrence,
                    location_id=perception.location_id,
                )
            except (TypeError, ValueError) as exc:
                _LOG.error(
                    "direct_observation_memory_rejected",
                    extra={
                        "cognition": {
                            "owner_id": owner.value,
                            "tick": tick,
                            "reason_code": "trace_build_failed",
                            "detail": type(exc).__name__,
                        }
                    },
                )
                continue
            if trace.memory_id.value in seen_ids or (
                event_key is not None and event_key in seen_ids
            ):
                deduped += 1
                _LOG.debug(
                    "direct_observation_memory_deduped",
                    extra={
                        "cognition": {
                            "owner_id": owner.value,
                            "tick": tick,
                            "event_id": (
                                None
                                if occurrence.provenance.source_event_id is None
                                else occurrence.provenance.source_event_id.value
                            ),
                            "deduplication_result": "duplicate",
                            "policy_version": DIRECT_OBSERVATION_MEMORY_POLICY_VERSION,
                        }
                    },
                )
                continue
            seen_ids.add(trace.memory_id.value)
            if event_key is not None:
                seen_ids.add(event_key)
            proposed += 1
            intents.append(
                MemoryUpdateIntent(
                    owner_id=owner,
                    kind=MemoryUpdateKind.WRITE_MEMORY,
                    memory=trace,
                )
            )
            _LOG.debug(
                "direct_observation_memory_proposed",
                extra={
                    "cognition": {
                        "owner_id": owner.value,
                        "tick": tick,
                        "event_id": (
                            None
                            if occurrence.provenance.source_event_id is None
                            else occurrence.provenance.source_event_id.value
                        ),
                        "audience_role": occurrence.audience_role.value,
                        "deduplication_result": "new",
                        "policy_version": DIRECT_OBSERVATION_MEMORY_POLICY_VERSION,
                    }
                },
            )

        scene = build_direct_scene_memory_trace(
            owner_id=owner,
            observation=observation,
            location_id=perception.location_id,
        )
        if scene is not None and scene.memory_id.value not in seen_ids:
            proposed += 1
            intents.append(
                MemoryUpdateIntent(
                    owner_id=owner,
                    kind=MemoryUpdateKind.WRITE_MEMORY,
                    memory=scene,
                )
            )
            _LOG.debug(
                "direct_observation_scene_proposed",
                extra={
                    "cognition": {
                        "owner_id": owner.value,
                        "tick": tick,
                        "concept_count": len(scene.concepts),
                        "entity_count": len(scene.entities),
                        "policy_version": DIRECT_OBSERVATION_MEMORY_POLICY_VERSION,
                    }
                },
            )

        _LOG.debug(
            "direct_observation_memory_batch",
            extra={
                "cognition": {
                    "owner_id": owner.value,
                    "tick": tick,
                    "proposed_count": proposed,
                    "deduped_count": deduped,
                    "applied_candidate_count": len(intents),
                    "policy_version": DIRECT_OBSERVATION_MEMORY_POLICY_VERSION,
                }
            },
        )
        return tuple(intents)


def _belief_revision_from_semanticization(
    pending: object | None,
    *,
    owner_id: AgentId,
) -> object | None:
    """Map V2 pending semanticization into one ownership-checked belief revision."""
    from memory.belief_formation import (
        DEFAULT_BELIEF_FORMATION_POLICY,
        BeliefEvidenceCandidate,
        belief_id_for_claim,
        bundle_from_candidates,
    )
    from memory.beliefs import (
        BeliefRevisionRequest,
        BeliefValueKind,
        ClaimSubject,
        ClaimSubjectKind,
        ClaimValue,
        EvidenceStance,
        SemanticClaim,
    )
    from memory.models import (
        MemorySourceKind,
        PendingSemanticizationIntent,
    )

    if pending is None:
        return None
    if type(pending) is not PendingSemanticizationIntent:
        raise TypeError("pending_semanticization must be PendingSemanticizationIntent")
    if pending.owner_id != owner_id:
        _LOG.error(
            "semanticization_owner_mismatch",
            extra={
                "cognition": {
                    "owner_id": owner_id.value,
                    "tick": pending.tick,
                    "reason_code": "ownership",
                    "semanticization_pending": True,
                    "belief_id_present": False,
                }
            },
        )
        raise ValueError("pending semanticization owner mismatch")

    gist = pending.gist_concepts[0]
    claim = SemanticClaim(
        subject=ClaimSubject(kind=ClaimSubjectKind.AGENT, agent_id=owner_id),
        predicate="experienced_concept",
        value=ClaimValue(kind=BeliefValueKind.TEXT, text_value=gist),
    )
    candidates: list[BeliefEvidenceCandidate] = []
    for memory_id in pending.source_memory_ids:
        candidates.append(
            BeliefEvidenceCandidate(
                memory_id=memory_id,
                claim=claim,
                stance=EvidenceStance.SUPPORTING,
                contribution=DEFAULT_BELIEF_FORMATION_POLICY.base_contribution,
                lineage_root_id=memory_id,
                source_tick=pending.tick,
                provenance_kind=MemorySourceKind.DIRECT_OBSERVATION,
            )
        )
    evidence = bundle_from_candidates(candidates, target_claim=claim)
    belief_id = belief_id_for_claim(owner_id=owner_id, claim=claim)
    revision = BeliefRevisionRequest(
        owner_id=owner_id,
        operation_id=(f"sem:{owner_id.value}:t{pending.tick}:{belief_id.value}"),
        logical_tick=pending.tick,
        claim=claim,
        evidence=evidence,
        policy=DEFAULT_BELIEF_FORMATION_POLICY.as_ref(),
        belief_id=belief_id,
    )
    _LOG.debug(
        "semanticization_mapped",
        extra={
            "cognition": {
                "owner_id": owner_id.value,
                "tick": pending.tick,
                "semanticization_pending": True,
                "belief_id_present": True,
                "source_count": len(pending.source_memory_ids),
                "gist_concept_count": len(pending.gist_concepts),
            }
        },
    )
    return revision
