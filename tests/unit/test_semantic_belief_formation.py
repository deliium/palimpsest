"""Unit tests for semantic belief extraction and revision."""

from __future__ import annotations

from agents.models import AgentId
from memory.belief_formation import (
    BeliefFormationPolicy,
    belief_id_for_claim,
    extract_evidence_candidates,
    lineage_root_for_trace,
    merge_revision,
    provenance_weight,
)
from memory.beliefs import (
    BeliefActivationState,
    BeliefEvidenceBundle,
    BeliefEvidenceContribution,
    BeliefValueKind,
    ClaimSubject,
    ClaimSubjectKind,
    ClaimValue,
    EvidenceStance,
    SemanticClaim,
    canonical_claim_identity,
)
from memory.models import (
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
    RelationEndpoint,
    RelationEndpointKind,
    WorldRevision,
)
from world.identifiers import EntityId


def _trace(
    memory_id: str,
    *,
    tick: int = 0,
    concept: str | None = "food",
    entity_label: str | None = None,
    entity_id: str | None = None,
    relation: tuple[str, str, str] | None = None,
    kind: MemorySourceKind = MemorySourceKind.DIRECT_OBSERVATION,
    speaker_id: EntityId | None = None,
    lineage: MemoryLineage | None = None,
    confidence: float = 1.0,
) -> MemoryTrace:
    concepts: tuple[ConceptMention, ...] = ()
    entities: tuple[EntityMention, ...] = ()
    relations: tuple[MemoryRelation, ...] = ()
    if concept is not None:
        concepts = (ConceptMention(mention_id=MentionId("c-1"), concept=concept),)
    if entity_label is not None:
        entities = (
            EntityMention(
                mention_id=MentionId("e-1"),
                label=entity_label,
                entity_id=EntityId(entity_id) if entity_id else None,
            ),
        )
    if relation is not None:
        subj, pred, obj = relation
        concepts = (
            ConceptMention(mention_id=MentionId("c-s"), concept=subj),
            ConceptMention(mention_id=MentionId("c-o"), concept=obj),
        )
        relations = (
            MemoryRelation(
                relation_id=MentionId("r-1"),
                predicate=pred,
                subject=RelationEndpoint(
                    kind=RelationEndpointKind.CONCEPT, mention_id=MentionId("c-s")
                ),
                object=RelationEndpoint(
                    kind=RelationEndpointKind.CONCEPT, mention_id=MentionId("c-o")
                ),
            ),
        )
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(0),
        concepts=concepts,
        entities=entities,
        relations=relations,
        context=MemorySituationContext(),
        emotional_salience=0.0,
        confidence=confidence,
        provenance=MemoryProvenance(
            kind=kind,
            source_tick=tick,
            speaker_id=speaker_id,
        ),
        created_tick=tick,
        source_tick=tick,
        last_access_tick=tick,
        access_count=0,
        lineage=lineage or MemoryLineage(),
    )


def _policy(**kwargs: object) -> BeliefFormationPolicy:
    base = dict(
        policy_id="test-formation",
        version="1",
        min_independent_observations=2,
        decay_half_life_ticks=100,
    )
    base.update(kwargs)
    return BeliefFormationPolicy(**base)  # type: ignore[arg-type]


def test_extract_candidates_from_concepts_entities_relations() -> None:
    trace = _trace(
        "m-1",
        concept="shelter",
        entity_label="gate",
        entity_id="ent-gate",
        relation=("alice", "protects", "bob"),
    )
    # relation path replaces concepts; rebuild with all
    concepts = (
        ConceptMention(mention_id=MentionId("c-1"), concept="shelter"),
        ConceptMention(mention_id=MentionId("c-s"), concept="alice"),
        ConceptMention(mention_id=MentionId("c-o"), concept="bob"),
    )
    entities = (
        EntityMention(
            mention_id=MentionId("e-1"),
            label="gate",
            entity_id=EntityId("ent-gate"),
        ),
    )
    relations = (
        MemoryRelation(
            relation_id=MentionId("r-1"),
            predicate="protects",
            subject=RelationEndpoint(
                kind=RelationEndpointKind.CONCEPT, mention_id=MentionId("c-s")
            ),
            object=RelationEndpoint(
                kind=RelationEndpointKind.CONCEPT, mention_id=MentionId("c-o")
            ),
        ),
    )
    trace = MemoryTrace(
        memory_id=MemoryId("m-1"),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(0),
        concepts=concepts,
        entities=entities,
        relations=relations,
        context=MemorySituationContext(),
        emotional_salience=0.0,
        confidence=1.0,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION, source_tick=0
        ),
        created_tick=0,
        source_tick=0,
        last_access_tick=0,
        access_count=0,
    )
    policy = _policy()
    candidates = extract_evidence_candidates(
        (trace,), owner_id=AgentId("agent-1"), policy=policy
    )
    assert len(candidates) >= 3
    predicates = {item.claim.predicate for item in candidates}
    assert "experienced_concept" in predicates
    assert "observed" in predicates
    assert "protects" in predicates


def test_provenance_weights_differ_for_communicated() -> None:
    policy = _policy(direct_weight=1.0, communicated_weight=0.5)
    assert provenance_weight(MemorySourceKind.DIRECT_OBSERVATION, policy=policy) == 1.0
    assert provenance_weight(MemorySourceKind.COMMUNICATED, policy=policy) == 0.5


def test_lineage_root_dedup_for_reconstructed_descendant() -> None:
    root = _trace("m-root", tick=1, concept="food")
    derived = _trace(
        "m-derived",
        tick=2,
        concept="food",
        lineage=MemoryLineage(
            supersedes_memory_id=MemoryId("m-root"),
            generation=1,
            source_memory_ids=(MemoryId("m-root"),),
        ),
    )
    index = {root.memory_id: root, derived.memory_id: derived}
    assert lineage_root_for_trace(derived, index) == MemoryId("m-root")


def test_permutation_invariant_belief_ids_and_candidate_order() -> None:
    t1 = _trace("m-a", tick=1, concept="alpha")
    t2 = _trace("m-b", tick=2, concept="beta")
    policy = _policy()
    owner = AgentId("agent-1")
    forward = extract_evidence_candidates((t1, t2), owner_id=owner, policy=policy)
    reverse = extract_evidence_candidates((t2, t1), owner_id=owner, policy=policy)
    assert [c.memory_id.value for c in forward] == [c.memory_id.value for c in reverse]
    claim = SemanticClaim(
        subject=ClaimSubject(kind=ClaimSubjectKind.AGENT, agent_id=owner),
        predicate="experienced_concept",
        value=ClaimValue(kind=BeliefValueKind.TEXT, text_value="alpha"),
    )
    assert belief_id_for_claim(owner_id=owner, claim=claim) == belief_id_for_claim(
        owner_id=owner, claim=claim
    )


def test_repeated_support_raises_confidence_and_activates() -> None:
    policy = _policy(min_independent_observations=2, activate_confidence_threshold=0.3)
    owner = AgentId("agent-1")
    claim = SemanticClaim(
        subject=ClaimSubject(kind=ClaimSubjectKind.AGENT, agent_id=owner),
        predicate="experienced_concept",
        value=ClaimValue(kind=BeliefValueKind.TEXT, text_value="food"),
    )

    def evidence(memory_id: str, ordinal: int) -> BeliefEvidenceBundle:
        return BeliefEvidenceBundle(
            supporting=(
                BeliefEvidenceContribution(
                    memory_id=MemoryId(memory_id),
                    stance=EvidenceStance.SUPPORTING,
                    contribution=0.4,
                    ordinal=ordinal,
                    lineage_root_id=MemoryId(memory_id),
                ),
            ),
            contradicting=(),
        )

    history, created, _, _ = merge_revision(
        owner_id=owner,
        claim=claim,
        new_evidence=evidence("m-1", 0),
        prior=None,
        logical_tick=1,
        operation_id="op-1",
        policy=policy,
    )
    assert created
    assert history.belief.activation_state is BeliefActivationState.CANDIDATE

    history2, _, _, changed = merge_revision(
        owner_id=owner,
        claim=claim,
        new_evidence=evidence("m-2", 0),
        prior=history,
        logical_tick=2,
        operation_id="op-2",
        policy=policy,
    )
    assert changed
    assert history2.belief.confidence.confidence > history.belief.confidence.confidence
    assert history2.belief.activation_state is BeliefActivationState.ACTIVE


def test_competing_value_counts_as_contradiction() -> None:
    policy = _policy(min_independent_observations=1, activate_confidence_threshold=0.2)
    owner = AgentId("agent-1")
    claim_a = SemanticClaim(
        subject=ClaimSubject(kind=ClaimSubjectKind.ENTITY, entity_id=EntityId("ent-1")),
        predicate="location",
        value=ClaimValue(kind=BeliefValueKind.TEXT, text_value="north"),
    )
    claim_b = SemanticClaim(
        subject=ClaimSubject(kind=ClaimSubjectKind.ENTITY, entity_id=EntityId("ent-1")),
        predicate="location",
        value=ClaimValue(kind=BeliefValueKind.TEXT, text_value="south"),
    )
    first, _, _, _ = merge_revision(
        owner_id=owner,
        claim=claim_a,
        new_evidence=BeliefEvidenceBundle(
            supporting=(
                BeliefEvidenceContribution(
                    memory_id=MemoryId("m-1"),
                    stance=EvidenceStance.SUPPORTING,
                    contribution=0.5,
                    ordinal=0,
                    lineage_root_id=MemoryId("m-1"),
                ),
            ),
            contradicting=(),
        ),
        prior=None,
        logical_tick=1,
        operation_id="op-1",
        policy=policy,
    )
    second, _, _, _ = merge_revision(
        owner_id=owner,
        claim=claim_b,
        new_evidence=BeliefEvidenceBundle(
            supporting=(
                BeliefEvidenceContribution(
                    memory_id=MemoryId("m-2"),
                    stance=EvidenceStance.SUPPORTING,
                    contribution=0.5,
                    ordinal=0,
                    lineage_root_id=MemoryId("m-2"),
                ),
            ),
            contradicting=(),
        ),
        prior=first,
        logical_tick=2,
        operation_id="op-2",
        policy=policy,
    )
    assert canonical_claim_identity(second.belief.claim) == canonical_claim_identity(
        claim_a
    )
    assert second.belief.confidence.confidence < first.belief.confidence.confidence
    assert second.belief.evidence_contradiction_count >= 1
