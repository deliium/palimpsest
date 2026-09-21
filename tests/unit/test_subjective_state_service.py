"""Atomic SubjectiveStateService commit boundary tests."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from memory.belief_formation import BeliefFormationPolicy
from memory.belief_service import InMemorySemanticBeliefService
from memory.beliefs import (
    BeliefEvidenceBundle,
    BeliefEvidenceContribution,
    BeliefRevisionRequest,
    BeliefValueKind,
    ClaimSubject,
    ClaimSubjectKind,
    ClaimValue,
    EvidenceStance,
    SemanticClaim,
)
from memory.models import (
    ConceptMention,
    MemoryId,
    MemoryProvenance,
    MemoryRunId,
    MemoryScope,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
)
from memory.service import InMemoryMemoryService
from simulation.subjective_state import (
    InMemorySubjectiveStateService,
    SubjectiveMutationBatch,
    SubjectiveStateError,
    SubjectiveStateErrorCode,
)
from social.relationships import (
    RelationshipFormationPolicy,
    RelationshipInteractionSignal,
    RelationshipRevisionRequest,
    RelationshipSignalKind,
)
from social.service import InMemoryRelationshipService
from world.identifiers import EntityId, WorldRevision


def _scope() -> MemoryScope:
    return MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))


def _trace(memory_id: str, *, tick: int = 0) -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(tick),
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept="food"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(location_id=EntityId("loc-1")),
        emotional_salience=0.1,
        confidence=1.0,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION, source_tick=tick
        ),
        created_tick=tick,
        source_tick=tick,
        last_access_tick=tick,
        access_count=0,
    )


def _belief_request(*, tick: int, memory_id: str, op: str) -> BeliefRevisionRequest:
    from memory.belief_formation import (
        DEFAULT_BELIEF_FORMATION_POLICY,
        belief_id_for_claim,
    )

    claim = SemanticClaim(
        subject=ClaimSubject(kind=ClaimSubjectKind.AGENT, agent_id=AgentId("agent-1")),
        predicate="experienced_concept",
        value=ClaimValue(kind=BeliefValueKind.TEXT, text_value="food"),
    )
    evidence = BeliefEvidenceBundle(
        supporting=(
            BeliefEvidenceContribution(
                memory_id=MemoryId(memory_id),
                stance=EvidenceStance.SUPPORTING,
                contribution=0.5,
                ordinal=0,
                lineage_root_id=MemoryId(memory_id),
            ),
        ),
        contradicting=(),
    )
    return BeliefRevisionRequest(
        owner_id=AgentId("agent-1"),
        operation_id=op,
        logical_tick=tick,
        claim=claim,
        evidence=evidence,
        policy=DEFAULT_BELIEF_FORMATION_POLICY.as_ref(),
        belief_id=belief_id_for_claim(owner_id=AgentId("agent-1"), claim=claim),
    )


def _rel_request(*, tick: int, memory_id: str, op: str) -> RelationshipRevisionRequest:
    return RelationshipRevisionRequest(
        source_id=AgentId("agent-1"),
        target_id=AgentId("agent-2"),
        operation_id=op,
        logical_tick=tick,
        signals=(
            RelationshipInteractionSignal(
                counterpart_id=AgentId("agent-2"),
                kind=RelationshipSignalKind.PROXIMITY,
                strength=0.4,
                memory_ref=memory_id,
                lineage_root_ref=memory_id,
                source_tick=tick,
            ),
        ),
        policy=RelationshipFormationPolicy(
            policy_id="relationship-formation", version="1"
        ).as_ref(),
    )


def _service() -> tuple[
    InMemorySubjectiveStateService,
    InMemoryMemoryService,
    InMemorySemanticBeliefService,
    InMemoryRelationshipService,
]:
    scope = _scope()
    memory = InMemoryMemoryService(scope)
    beliefs = InMemorySemanticBeliefService(
        scope,
        policy=BeliefFormationPolicy(
            policy_id="test", version="1", min_independent_observations=1
        ),
    )
    relationships = InMemoryRelationshipService(AgentId("agent-1"))
    service = InMemorySubjectiveStateService(
        scope,
        memory_service=memory,
        belief_service=beliefs,
        relationship_service=relationships,
    )
    return service, memory, beliefs, relationships


@pytest.mark.asyncio
async def test_commit_applies_memory_belief_and_relationship() -> None:
    service, memory, beliefs, relationships = _service()
    batch = SubjectiveMutationBatch(
        operation_id="op-1",
        logical_tick=0,
        memory_writes=(_trace("m-1", tick=0),),
        belief_revisions=(_belief_request(tick=0, memory_id="m-1", op="b-1"),),
        relationship_revisions=(_rel_request(tick=0, memory_id="m-1", op="r-1"),),
        expected_revision=0,
    )
    receipt = await service.commit(batch)
    assert receipt.revision == 1
    assert receipt.memory_written_count == 1
    assert receipt.belief_revision_count == 1
    assert receipt.relationship_revision_count == 1
    assert await memory.get(MemoryId("m-1")) is not None
    assert len(await beliefs.snapshot()) == 1
    assert len(await relationships.snapshot()) == 1
    assert "food" not in repr(receipt)


@pytest.mark.asyncio
async def test_commit_is_idempotent_for_same_operation() -> None:
    service, *_ = _service()
    batch = SubjectiveMutationBatch(
        operation_id="op-1",
        logical_tick=0,
        memory_writes=(_trace("m-1", tick=0),),
        belief_revisions=(_belief_request(tick=0, memory_id="m-1", op="b-1"),),
        expected_revision=0,
    )
    first = await service.commit(batch)
    second = await service.commit(batch)
    assert first.revision == second.revision == 1
    assert service.revision == 1


@pytest.mark.asyncio
async def test_commit_rejects_idempotency_conflict() -> None:
    service, *_ = _service()
    first = SubjectiveMutationBatch(
        operation_id="op-1",
        logical_tick=0,
        memory_writes=(_trace("m-1", tick=0),),
        expected_revision=0,
    )
    await service.commit(first)
    conflict = SubjectiveMutationBatch(
        operation_id="op-1",
        logical_tick=0,
        memory_writes=(_trace("m-2", tick=0),),
        expected_revision=1,
    )
    with pytest.raises(SubjectiveStateError) as exc:
        await service.commit(conflict)
    assert exc.value.code is SubjectiveStateErrorCode.IDEMPOTENCY_CONFLICT


@pytest.mark.asyncio
async def test_commit_rejects_expected_revision_conflict() -> None:
    service, *_ = _service()
    await service.commit(
        SubjectiveMutationBatch(
            operation_id="op-1",
            logical_tick=0,
            memory_writes=(_trace("m-1", tick=0),),
            expected_revision=0,
        )
    )
    with pytest.raises(SubjectiveStateError) as exc:
        await service.commit(
            SubjectiveMutationBatch(
                operation_id="op-2",
                logical_tick=0,
                memory_writes=(_trace("m-2", tick=0),),
                expected_revision=0,
            )
        )
    assert exc.value.code is SubjectiveStateErrorCode.CONFLICT


@pytest.mark.asyncio
async def test_commit_rolls_back_on_adapter_failure() -> None:
    service, memory, beliefs, relationships = _service()
    # Seed a later-tick belief so the batch revision fails chronology after
    # the memory write, forcing copy-then-swap rollback.
    await beliefs.revise(_belief_request(tick=5, memory_id="m-seed", op="seed"))
    with pytest.raises(SubjectiveStateError) as exc:
        await service.commit(
            SubjectiveMutationBatch(
                operation_id="op-fail",
                logical_tick=0,
                memory_writes=(_trace("m-1", tick=0),),
                belief_revisions=(
                    _belief_request(tick=0, memory_id="m-1", op="b-bad"),
                ),
                expected_revision=0,
            )
        )
    assert exc.value.code is SubjectiveStateErrorCode.ADAPTER_FAILED
    assert await memory.get(MemoryId("m-1")) is None
    assert len(await beliefs.snapshot()) == 1
    assert await relationships.snapshot() == ()
    assert service.revision == 0


@pytest.mark.asyncio
async def test_commit_logs_are_metadata_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    service, *_ = _service()
    secret_concept = "secret-belief-claim-payload"
    with caplog.at_level(logging.DEBUG, logger="simulation.subjective_state"):
        await service.commit(
            SubjectiveMutationBatch(
                operation_id="op-log",
                logical_tick=0,
                memory_writes=(
                    MemoryTrace(
                        memory_id=MemoryId("m-log"),
                        owner_id=AgentId("agent-1"),
                        world_revision=WorldRevision(0),
                        concepts=(
                            ConceptMention(
                                mention_id=MentionId("c-1"),
                                concept=secret_concept,
                            ),
                        ),
                        entities=(),
                        relations=(),
                        context=MemorySituationContext(tags=()),
                        emotional_salience=0.1,
                        confidence=0.5,
                        provenance=MemoryProvenance(
                            kind=MemorySourceKind.DIRECT_OBSERVATION,
                            source_tick=0,
                        ),
                        created_tick=0,
                        source_tick=0,
                        last_access_tick=0,
                        access_count=0,
                    ),
                ),
                belief_revisions=(
                    _belief_request(tick=0, memory_id="m-log", op="b-log"),
                ),
                expected_revision=0,
            )
        )
    joined = " ".join(
        f"{record.getMessage()} {record.__dict__}" for record in caplog.records
    )
    assert secret_concept not in joined
    assert "experienced_concept" not in joined
    assert "food" not in joined
