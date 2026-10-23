"""Complete owner-service fork state: export, restore, and isolation."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from memory.belief_formation import DEFAULT_BELIEF_FORMATION_POLICY
from memory.belief_service import InMemorySemanticBeliefService
from memory.beliefs import (
    BeliefActivationState,
    BeliefConfidenceState,
    BeliefEvidenceBundle,
    BeliefEvidenceContribution,
    BeliefPolicyRef,
    BeliefRevisionRequest,
    BeliefValueKind,
    ClaimSubject,
    ClaimSubjectKind,
    ClaimValue,
    EvidenceStance,
    SemanticClaim,
)
from memory.errors import BeliefServiceError
from memory.fork_state import (
    BeliefForkState,
    LegacyBeliefForkState,
    MemoryForkState,
    MemoryForkStateError,
)
from memory.models import (
    Belief,
    BeliefId,
    BeliefStore,
    ConceptMention,
    MemoryAccessReceipt,
    MemoryApplyResult,
    MemoryId,
    MemoryLineage,
    MemoryMutationBatch,
    MemoryProvenance,
    MemoryRunId,
    MemoryScope,
    MemorySituationContext,
    MemorySourceKind,
    MemoryStore,
    MemoryTrace,
    MentionId,
    ReconstructedMemory,
    ReconstructionId,
    ReconstructionRecord,
)
from memory.service import InMemoryMemoryService
from simulation.subjective_state import (
    InMemorySubjectiveOwnerBundle,
    SubjectiveMutationBatch,
    SubjectiveOwnerForkState,
    SubjectiveStateError,
    SubjectiveStateErrorCode,
)
from social.fork_state import RelationshipForkState, RelationshipForkStateError
from social.relationships import (
    RelationshipDimension,
    RelationshipInteractionSignal,
    RelationshipPolicyRef,
    RelationshipRevisionRequest,
    RelationshipSignalKind,
)
from social.service import InMemoryRelationshipService, RelationshipServiceError
from world.identifiers import EntityId, WorldRevision

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-a")
OTHER = AgentId("agent-b")
TARGET = AgentId("agent-b")
PARENT_RUN = MemoryRunId("parent-run")
CHILD_RUN = MemoryRunId("child-run")
PARENT_SCOPE = MemoryScope(run_id=PARENT_RUN, owner_id=OWNER)
CHILD_SCOPE = MemoryScope(run_id=CHILD_RUN, owner_id=OWNER)


def _trace(
    memory_id: str,
    *,
    owner: AgentId = OWNER,
    tick: int = 1,
    lineage: object | None = None,
) -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=owner,
        world_revision=WorldRevision(0),
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept="camp"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(location_id=EntityId("loc-1")),
        emotional_salience=0.2,
        confidence=1.0,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=tick,
        ),
        created_tick=tick,
        source_tick=tick,
        last_access_tick=tick,
        access_count=0,
        lineage=MemoryLineage() if lineage is None else lineage,  # type: ignore[arg-type]
    )


def _reconstruction(tick: int = 2) -> ReconstructionRecord:
    reconstructed = ReconstructedMemory(
        reconstruction_id=ReconstructionId("rec-1"),
        owner_id=OWNER,
        narrative="remembered camp",
        concepts=(),
        entities=(),
        relations=(),
        context=MemorySituationContext(location_id=EntityId("loc-1")),
        confidence=0.8,
        emotional_salience=0.3,
        source_memory_ids=(MemoryId("mem-1"),),
        generation=1,
        reconstructed_at_tick=tick,
        policy_id="reconstruction-v1",
        policy_version="1",
        used_provider=False,
        fallback_used=False,
    )
    return ReconstructionRecord(
        reconstruction_id=ReconstructionId("rec-1"),
        run_id=PARENT_RUN,
        owner_id=OWNER,
        source_memory_ids=(MemoryId("mem-1"),),
        reconstructed=reconstructed,
        created_tick=tick,
        policy_id="reconstruction-v1",
        policy_version="1",
        used_provider=False,
        fallback_used=False,
    )


def _belief_request(operation_id: str = "belief-op") -> BeliefRevisionRequest:
    return BeliefRevisionRequest(
        owner_id=OWNER,
        operation_id=operation_id,
        logical_tick=2,
        claim=SemanticClaim(
            subject=ClaimSubject(
                kind=ClaimSubjectKind.ENTITY, entity_id=EntityId("place-1")
            ),
            predicate="at_location",
            value=ClaimValue(kind=BeliefValueKind.BOOL, bool_value=True),
        ),
        evidence=BeliefEvidenceBundle(
            supporting=(
                BeliefEvidenceContribution(
                    memory_id=MemoryId("mem-1"),
                    stance=EvidenceStance.SUPPORTING,
                    contribution=0.8,
                    ordinal=0,
                    lineage_root_id=MemoryId("mem-1"),
                ),
            ),
            contradicting=(),
        ),
        policy=BeliefPolicyRef(policy_id="semantic-v1", version="1"),
        activation_state=BeliefActivationState.ACTIVE,
        confidence=BeliefConfidenceState(
            confidence=0.8, support_mass=0.8, contradiction_mass=0.0
        ),
    )


def _relationship_request(operation_id: str = "rel-op") -> RelationshipRevisionRequest:
    return RelationshipRevisionRequest(
        source_id=OWNER,
        target_id=TARGET,
        operation_id=operation_id,
        logical_tick=2,
        signals=(
            RelationshipInteractionSignal(
                counterpart_id=TARGET,
                kind=RelationshipSignalKind.HELP_RECEIVED,
                strength=0.6,
                memory_ref="mem-1",
                lineage_root_ref="mem-1",
                source_tick=2,
            ),
        ),
        policy=RelationshipPolicyRef(policy_id="relationship-v1", version="1"),
    )


async def _populated_bundle(
    scope: MemoryScope = PARENT_SCOPE,
) -> InMemorySubjectiveOwnerBundle:
    memory = InMemoryMemoryService(scope)
    belief = InMemorySemanticBeliefService(scope)
    relationship = InMemoryRelationshipService(scope.owner_id)
    bundle = InMemorySubjectiveOwnerBundle(
        scope,
        memory_service=memory,  # type: ignore[arg-type]
        belief_service=belief,  # type: ignore[arg-type]
        relationship_service=relationship,  # type: ignore[arg-type]
    )
    await memory.apply(
        MemoryMutationBatch(
            writes=(_trace("mem-1"),),
            operation_id="memory-write-1",
        )
    )
    record = _reconstruction()
    derived = _trace(
        "mem-2",
        tick=2,
        lineage=MemoryLineage(
            supersedes_memory_id=MemoryId("mem-1"),
            generation=1,
            source_memory_ids=(MemoryId("mem-1"),),
            reconstruction_id=ReconstructionId("rec-1"),
        ),
    )
    await memory.apply(
        MemoryMutationBatch(
            reconstructions=(record,),
            writes=(derived,),
            accesses=(
                MemoryAccessReceipt(
                    memory_id=MemoryId("mem-1"),
                    access_tick=2,
                    operation_id="access-1",
                ),
            ),
            operation_id="memory-reconstruct-1",
        )
    )
    await belief.revise(_belief_request())
    await relationship.revise(_relationship_request())
    await bundle.commit(
        SubjectiveMutationBatch(
            operation_id="subjective-op-1",
            logical_tick=3,
            memory_accesses=(),
        )
    )
    return bundle


@pytest.mark.asyncio
async def test_owner_fork_state_round_trip_preserves_history_and_rebases_run() -> None:
    parent = await _populated_bundle()
    state = await parent.export_fork_state()
    assert isinstance(state, SubjectiveOwnerForkState)
    assert len(state.memory.traces) == 2
    assert len(state.memory.reconstructions) == 1
    assert len(state.memory.derivation_edges) == 1
    assert state.memory.access_operations == (("access-1", "mem-1"),)
    assert len(state.belief.beliefs) == 1
    assert len(state.relationship.profiles) == 1
    assert state.commit.revision == 1

    # Build a genuinely fresh destination rather than reusing seeded state.
    child_memory = InMemoryMemoryService(CHILD_SCOPE)
    child_belief = InMemorySemanticBeliefService(CHILD_SCOPE)
    child_relationship = InMemoryRelationshipService(OWNER)
    child = InMemorySubjectiveOwnerBundle(
        CHILD_SCOPE,
        memory_service=child_memory,  # type: ignore[arg-type]
        belief_service=child_belief,  # type: ignore[arg-type]
        relationship_service=child_relationship,  # type: ignore[arg-type]
    )
    await child.restore_fork_state(state, parent_scope=PARENT_SCOPE)

    child_state = await child.export_fork_state()
    assert child_state.scope == CHILD_SCOPE
    assert child_state.memory.reconstructions[0].run_id == CHILD_RUN
    assert child_state.memory.traces == state.memory.traces
    assert child_state.memory.derivation_edges == state.memory.derivation_edges
    assert child_state.memory.access_operations == state.memory.access_operations
    assert child_state.belief.beliefs == state.belief.beliefs
    assert child_state.belief.histories == state.belief.histories
    assert child_state.relationship.profiles == state.relationship.profiles
    assert child_state.commit.revision == state.commit.revision

    snapshot = await child.snapshot()
    assert {trace.memory_id.value for trace in snapshot.memories} == {
        "mem-1",
        "mem-2",
    }
    assert len(snapshot.semantic_beliefs) == 1
    assert len(snapshot.relationships) == 1

    # Access receipt replay remains idempotent and belief/relationship ops reject
    # a conflicting replay rather than silently re-applying.
    result = await child_memory.apply(
        MemoryMutationBatch(
            accesses=(
                MemoryAccessReceipt(
                    memory_id=MemoryId("mem-1"),
                    access_tick=2,
                    operation_id="access-1",
                ),
            )
        )
    )
    assert result.access_idempotent_count == 1
    with pytest.raises(BeliefServiceError):
        await child_belief.revise(
            replace(_belief_request("belief-op"), logical_tick=4)
        )
    with pytest.raises(RelationshipServiceError):
        await child_relationship.revise(
            replace(_relationship_request("rel-op"), logical_tick=4)
        )

    # Parent remains untouched and child mutations stay isolated.
    parent_after = await parent.export_fork_state()
    assert parent_after == state
    await child_memory.apply(
        MemoryMutationBatch(writes=(_trace("mem-child", tick=4),))
    )
    assert len((await parent.export_fork_state()).memory.traces) == 2
    assert len((await child.export_fork_state()).memory.traces) == 3


@pytest.mark.asyncio
async def test_owner_fork_state_rejects_owner_mismatch_and_second_import() -> None:
    parent = await _populated_bundle()
    state = await parent.export_fork_state()

    other_scope = MemoryScope(run_id=CHILD_RUN, owner_id=OTHER)
    other = InMemorySubjectiveOwnerBundle(
        other_scope,
        memory_service=InMemoryMemoryService(other_scope),  # type: ignore[arg-type]
        belief_service=InMemorySemanticBeliefService(other_scope),  # type: ignore[arg-type]
        relationship_service=InMemoryRelationshipService(OTHER),  # type: ignore[arg-type]
    )
    with pytest.raises(SubjectiveStateError) as exc:
        await other.restore_fork_state(state, parent_scope=PARENT_SCOPE)
    assert exc.value.code is SubjectiveStateErrorCode.FORK_OWNER_MISMATCH

    child = InMemorySubjectiveOwnerBundle(
        CHILD_SCOPE,
        memory_service=InMemoryMemoryService(CHILD_SCOPE),  # type: ignore[arg-type]
        belief_service=InMemorySemanticBeliefService(CHILD_SCOPE),  # type: ignore[arg-type]
        relationship_service=InMemoryRelationshipService(OWNER),  # type: ignore[arg-type]
    )
    await child.restore_fork_state(state, parent_scope=PARENT_SCOPE)
    with pytest.raises(SubjectiveStateError) as exc:
        await child.restore_fork_state(state, parent_scope=PARENT_SCOPE)
    assert exc.value.code is SubjectiveStateErrorCode.FORK_DESTINATION_NOT_EMPTY


@pytest.mark.asyncio
async def test_owner_fork_state_rolls_back_on_partial_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = await _populated_bundle()
    state = await parent.export_fork_state()
    child_memory = InMemoryMemoryService(CHILD_SCOPE)
    child_belief = InMemorySemanticBeliefService(CHILD_SCOPE)
    child_relationship = InMemoryRelationshipService(OWNER)
    child = InMemorySubjectiveOwnerBundle(
        CHILD_SCOPE,
        memory_service=child_memory,  # type: ignore[arg-type]
        belief_service=child_belief,  # type: ignore[arg-type]
        relationship_service=child_relationship,  # type: ignore[arg-type]
    )

    def _fail(_self: object, _state: object) -> None:
        raise RelationshipForkStateError("fork_state_invalid", "forced")

    monkeypatch.setattr(
        type(child_relationship), "restore_fork_state", _fail
    )
    with pytest.raises(SubjectiveStateError) as exc:
        await child.restore_fork_state(state, parent_scope=PARENT_SCOPE)
    assert exc.value.code is SubjectiveStateErrorCode.FORK_STATE_INVALID
    assert child_memory.export_fork_state().traces == ()
    assert child_belief.export_fork_state().beliefs == ()
    assert child.commit_service.revision == 0


@pytest.mark.asyncio
async def test_non_fork_capable_service_fails_preflight() -> None:
    class _BareService:
        def __init__(self) -> None:
            self.scope = CHILD_SCOPE
            self.source_id = OWNER

    child = InMemorySubjectiveOwnerBundle(
        CHILD_SCOPE,
        memory_service=_BareService(),  # type: ignore[arg-type]
        belief_service=_BareService(),  # type: ignore[arg-type]
        relationship_service=_BareService(),  # type: ignore[arg-type]
    )
    with pytest.raises(SubjectiveStateError) as exc:
        await child.export_fork_state()
    assert exc.value.code is SubjectiveStateErrorCode.FORK_STATE_UNSUPPORTED


def test_legacy_stores_export_and_restore_detached_owner_checked_rows() -> None:
    trace = _trace("legacy-mem")
    store = MemoryStore(OWNER)
    store.write(trace)
    state = store.export_fork_state()
    assert state == (trace,)
    restored = MemoryStore(OWNER)
    restored.restore_fork_state(state)
    assert restored.export_fork_state() == state

    with pytest.raises(MemoryForkStateError) as exc:
        MemoryStore(OTHER).restore_fork_state(state)
    assert exc.value.code == "fork_owner_mismatch"

    with pytest.raises(MemoryForkStateError) as exc:
        restored.restore_fork_state(state)
    assert exc.value.code == "fork_destination_not_empty"

    belief = Belief(
        belief_id=BeliefId("legacy-belief"),
        owner_id=OWNER,
        proposition="camp is north",
        confidence=0.7,
        evidence_memory_ids=(MemoryId("legacy-mem"),),
    )
    belief_store = BeliefStore(OWNER)
    belief_store.write(belief)
    legacy_state = belief_store.export_fork_state()
    assert legacy_state == (belief,)
    restored_beliefs = BeliefStore(OWNER)
    restored_beliefs.restore_fork_state(legacy_state)
    assert restored_beliefs.export_fork_state() == (belief,)

    with pytest.raises(MemoryForkStateError) as exc:
        BeliefStore(OTHER).restore_fork_state(legacy_state)
    assert exc.value.code == "fork_owner_mismatch"


@pytest.mark.asyncio
async def test_fork_state_versions_and_references_fail_closed() -> None:
    trace = _trace("mem-1")
    with pytest.raises(MemoryForkStateError, match="fork_state_unsupported"):
        MemoryForkState(
            scope=PARENT_SCOPE,
            traces=(trace,),
            reconstructions=(),
            derivation_edges=(),
            access_operations=(),
            state_format_version="future-version",
        )
    with pytest.raises(MemoryForkStateError, match="fork_state_invalid"):
        MemoryForkState(
            scope=PARENT_SCOPE,
            traces=(_trace("dup"), _trace("dup")),
            reconstructions=(),
            derivation_edges=(),
            access_operations=(),
        )
    parent = await _populated_bundle()
    belief_state = (await parent.export_fork_state()).belief
    with pytest.raises(MemoryForkStateError, match="fork_state_invalid"):
        BeliefForkState(
            scope=PARENT_SCOPE,
            policy=DEFAULT_BELIEF_FORMATION_POLICY,
            beliefs=belief_state.beliefs,
            histories=(),
            operations=(),
        )
    with pytest.raises(RelationshipForkStateError, match="fork_state_unsupported"):
        RelationshipForkState(
            owner_id=OWNER,
            policy=__import__(
                "social.relationships", fromlist=["DEFAULT_RELATIONSHIP_POLICY"]
            ).DEFAULT_RELATIONSHIP_POLICY,
            profiles=(),
            histories=(),
            operations=(),
            state_format_version="future-version",
        )


def test_legacy_belief_state_is_separate_from_semantic_belief_state() -> None:
    legacy = LegacyBeliefForkState(
        owner_id=OWNER,
        beliefs=(
            Belief(
                belief_id=BeliefId("legacy-1"),
                owner_id=OWNER,
                proposition="legacy proposition",
                confidence=0.4,
                evidence_memory_ids=(),
            ),
        ),
    )
    assert legacy.beliefs[0].belief_id == BeliefId("legacy-1")
    assert not hasattr(legacy.beliefs[0], "claim")
    _ = (MemoryApplyResult, RelationshipDimension, MemoryForkState)
