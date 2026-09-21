"""Unit tests for structured semantic belief domain contracts."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from memory.beliefs import (
    BeliefActivationState,
    BeliefConfidenceState,
    BeliefEvidenceBundle,
    BeliefEvidenceContribution,
    BeliefPolicyRef,
    BeliefRevision,
    BeliefRevisionId,
    BeliefRevisionRequest,
    BeliefRevisionResult,
    BeliefValueKind,
    ClaimSubject,
    ClaimSubjectKind,
    ClaimValue,
    EvidenceStance,
    SemanticBelief,
    SemanticBeliefHistory,
    SemanticBeliefStore,
    SemanticClaim,
    canonical_claim_identity,
    canonical_subject_predicate_key,
    project_legacy_belief,
)
from memory.errors import BeliefServiceError, BeliefServiceErrorCode
from memory.models import BeliefId, MemoryId, OwnershipError
from world.identifiers import EntityId


def _claim(
    *,
    predicate: str = "finds_food",
    text: str = "effectively",
    subject_agent: str = "agent-1",
) -> SemanticClaim:
    return SemanticClaim(
        subject=ClaimSubject(
            kind=ClaimSubjectKind.AGENT,
            agent_id=AgentId(subject_agent),
        ),
        predicate=predicate,
        value=ClaimValue(kind=BeliefValueKind.TEXT, text_value=text),
    )


def _evidence(
    *pairs: tuple[str, EvidenceStance],
) -> BeliefEvidenceBundle:
    supporting: list[BeliefEvidenceContribution] = []
    contradicting: list[BeliefEvidenceContribution] = []
    for ordinal, (memory_id, stance) in enumerate(pairs):
        item = BeliefEvidenceContribution(
            memory_id=MemoryId(memory_id),
            stance=stance,
            contribution=0.5,
            ordinal=ordinal,
            lineage_root_id=MemoryId(memory_id),
        )
        if stance is EvidenceStance.SUPPORTING:
            supporting.append(item)
        else:
            contradicting.append(item)
    return BeliefEvidenceBundle(
        supporting=tuple(supporting),
        contradicting=tuple(contradicting),
    )


def _policy() -> BeliefPolicyRef:
    return BeliefPolicyRef(policy_id="semantic-v1", version="1")


def _confidence(*, confidence: float = 0.6) -> BeliefConfidenceState:
    return BeliefConfidenceState(
        confidence=confidence,
        support_mass=0.6,
        contradiction_mass=0.1,
    )


def _revision(
    *,
    ordinal: int = 0,
    tick: int = 3,
    previous: BeliefRevisionId | None = None,
    claim: SemanticClaim | None = None,
) -> BeliefRevision:
    return BeliefRevision(
        revision_id=BeliefRevisionId(f"rev-{ordinal}"),
        belief_id=BeliefId("belief-1"),
        owner_id=AgentId("agent-1"),
        ordinal=ordinal,
        logical_tick=tick,
        claim=claim or _claim(),
        confidence=_confidence(),
        evidence=_evidence(("m-1", EvidenceStance.SUPPORTING)),
        activation_state=BeliefActivationState.ACTIVE,
        policy=_policy(),
        previous_revision_id=previous,
    )


def _belief(*, ordinal: int = 0, tick: int = 3) -> SemanticBelief:
    return SemanticBelief(
        belief_id=BeliefId("belief-1"),
        owner_id=AgentId("agent-1"),
        claim=_claim(),
        confidence=_confidence(),
        activation_state=BeliefActivationState.ACTIVE,
        current_revision_id=BeliefRevisionId(f"rev-{ordinal}"),
        revision_ordinal=ordinal,
        created_tick=1,
        updated_tick=tick,
        policy=_policy(),
        evidence_support_count=1,
        evidence_contradiction_count=0,
    )


def test_claim_identity_is_deterministic_and_value_sensitive() -> None:
    a = _claim(text="effectively")
    b = _claim(text="effectively")
    c = _claim(text="poorly")
    assert canonical_claim_identity(a) == canonical_claim_identity(b)
    assert canonical_subject_predicate_key(a) == canonical_subject_predicate_key(c)
    assert canonical_claim_identity(a) != canonical_claim_identity(c)


def test_claim_subject_kinds_and_entity_value() -> None:
    subject = ClaimSubject(kind=ClaimSubjectKind.ENTITY, entity_id=EntityId("ent-1"))
    value = ClaimValue(kind=BeliefValueKind.BOOL, bool_value=True)
    claim = SemanticClaim(subject=subject, predicate="is_reachable", value=value)
    assert "entity=ent-1" in canonical_claim_identity(claim)
    assert "bool=1" in canonical_claim_identity(claim)


def test_evidence_rejects_duplicate_and_overlapping_stances() -> None:
    with pytest.raises(ValueError, match="duplicate_memory_id"):
        BeliefEvidenceBundle(
            supporting=(
                BeliefEvidenceContribution(
                    memory_id=MemoryId("m-1"),
                    stance=EvidenceStance.SUPPORTING,
                    contribution=0.2,
                    ordinal=0,
                    lineage_root_id=MemoryId("m-1"),
                ),
            ),
            contradicting=(
                BeliefEvidenceContribution(
                    memory_id=MemoryId("m-1"),
                    stance=EvidenceStance.CONTRADICTING,
                    contribution=0.2,
                    ordinal=1,
                    lineage_root_id=MemoryId("m-1"),
                ),
            ),
        )
    with pytest.raises(ValueError, match="stance_mismatch"):
        BeliefEvidenceBundle(
            supporting=(
                BeliefEvidenceContribution(
                    memory_id=MemoryId("m-1"),
                    stance=EvidenceStance.CONTRADICTING,
                    contribution=0.2,
                    ordinal=0,
                    lineage_root_id=MemoryId("m-1"),
                ),
            ),
            contradicting=(),
        )


def test_evidence_allows_interleaved_ordinals() -> None:
    bundle = BeliefEvidenceBundle(
        supporting=(
            BeliefEvidenceContribution(
                memory_id=MemoryId("m-0"),
                stance=EvidenceStance.SUPPORTING,
                contribution=0.4,
                ordinal=0,
                lineage_root_id=MemoryId("m-0"),
            ),
            BeliefEvidenceContribution(
                memory_id=MemoryId("m-2"),
                stance=EvidenceStance.SUPPORTING,
                contribution=0.4,
                ordinal=2,
                lineage_root_id=MemoryId("m-2"),
            ),
        ),
        contradicting=(
            BeliefEvidenceContribution(
                memory_id=MemoryId("m-1"),
                stance=EvidenceStance.CONTRADICTING,
                contribution=0.3,
                ordinal=1,
                lineage_root_id=MemoryId("m-1"),
            ),
        ),
    )
    assert bundle.total_count == 3


def test_confidence_and_ticks_are_bounded_and_monotonic() -> None:
    with pytest.raises(ValueError, match="not_unit_interval"):
        BeliefConfidenceState(confidence=1.5, support_mass=0.0, contradiction_mass=0.0)
    with pytest.raises(ValueError, match="before_created"):
        SemanticBelief(
            belief_id=BeliefId("belief-1"),
            owner_id=AgentId("agent-1"),
            claim=_claim(),
            confidence=_confidence(),
            activation_state=BeliefActivationState.CANDIDATE,
            current_revision_id=BeliefRevisionId("rev-0"),
            revision_ordinal=0,
            created_tick=5,
            updated_tick=4,
            policy=_policy(),
            evidence_support_count=0,
            evidence_contradiction_count=0,
        )


def test_revision_history_enforces_monotonic_chain() -> None:
    rev0 = _revision(ordinal=0, tick=1)
    rev1 = _revision(
        ordinal=1,
        tick=2,
        previous=BeliefRevisionId("rev-0"),
    )
    history = SemanticBeliefHistory(
        belief=_belief(ordinal=1, tick=2),
        revisions=(rev0, rev1),
    )
    assert len(history.revisions) == 2
    with pytest.raises(ValueError, match="tick_regression"):
        SemanticBeliefHistory(
            belief=_belief(ordinal=1, tick=1),
            revisions=(
                _revision(ordinal=0, tick=2),
                _revision(ordinal=1, tick=1, previous=BeliefRevisionId("rev-0")),
            ),
        )


def test_repr_and_errors_omit_payload_content() -> None:
    secret_predicate = "knows-secret-gate-code"
    secret_value = "hunter2-passphrase"
    claim = _claim(predicate=secret_predicate, text=secret_value)
    belief = SemanticBelief(
        belief_id=BeliefId("belief-1"),
        owner_id=AgentId("agent-1"),
        claim=claim,
        confidence=_confidence(),
        activation_state=BeliefActivationState.ACTIVE,
        current_revision_id=BeliefRevisionId("rev-0"),
        revision_ordinal=0,
        created_tick=1,
        updated_tick=1,
        policy=_policy(),
        evidence_support_count=1,
        evidence_contradiction_count=0,
    )
    revision = BeliefRevision(
        revision_id=BeliefRevisionId("rev-0"),
        belief_id=BeliefId("belief-1"),
        owner_id=AgentId("agent-1"),
        ordinal=0,
        logical_tick=1,
        claim=claim,
        confidence=_confidence(),
        evidence=_evidence(("m-secret", EvidenceStance.SUPPORTING)),
        activation_state=BeliefActivationState.ACTIVE,
        policy=_policy(),
    )
    request = BeliefRevisionRequest(
        owner_id=AgentId("agent-1"),
        operation_id="op-1",
        logical_tick=1,
        claim=claim,
        evidence=_evidence(("m-secret", EvidenceStance.SUPPORTING)),
        policy=_policy(),
    )
    result = BeliefRevisionResult(
        belief_id=BeliefId("belief-1"),
        revision_id=BeliefRevisionId("rev-0"),
        revision_ordinal=0,
        activation_state=BeliefActivationState.ACTIVE,
        idempotent=False,
        created=True,
        retired=False,
        materially_changed=True,
        support_count=1,
        contradiction_count=0,
    )
    rendered = " ".join(
        [
            repr(claim),
            repr(claim.subject),
            repr(claim.value),
            repr(belief),
            repr(revision),
            repr(request),
            repr(result),
            repr(revision.evidence),
            repr(revision.evidence.supporting[0]),
        ]
    )
    assert secret_predicate not in rendered
    assert secret_value not in rendered
    assert "hunter2" not in rendered
    assert "m-secret" in rendered  # IDs are allowed

    err = BeliefServiceError(BeliefServiceErrorCode.OWNERSHIP)
    assert str(err) == "ownership"
    assert secret_predicate not in str(err)
    assert secret_value not in repr(err)


def test_legacy_belief_repr_omits_proposition() -> None:
    from memory.models import Belief

    belief = Belief(
        belief_id=BeliefId("b-1"),
        owner_id=AgentId("agent-1"),
        proposition="the gate is open",
        confidence=0.5,
        evidence_memory_ids=(MemoryId("m-1"),),
    )
    rendered = repr(belief)
    assert "the gate is open" not in rendered
    assert "evidence_count=1" in rendered


def test_project_legacy_belief_uses_opaque_claim_key() -> None:
    semantic = _belief()
    legacy = project_legacy_belief(semantic)
    assert legacy.belief_id == semantic.belief_id
    assert legacy.owner_id == semantic.owner_id
    assert legacy.proposition == canonical_subject_predicate_key(semantic.claim)
    assert "effectively" not in legacy.proposition


def test_semantic_belief_store_owner_validation() -> None:
    store = SemanticBeliefStore(AgentId("agent-1"))
    rev = _revision()
    history = SemanticBeliefHistory(belief=_belief(), revisions=(rev,))
    store.write(history)
    assert len(store.snapshot()) == 1
    assert store.history(BeliefId("belief-1")) is not None

    foreign = SemanticBeliefHistory(
        belief=SemanticBelief(
            belief_id=BeliefId("belief-2"),
            owner_id=AgentId("agent-2"),
            claim=_claim(subject_agent="agent-2"),
            confidence=_confidence(),
            activation_state=BeliefActivationState.CANDIDATE,
            current_revision_id=BeliefRevisionId("rev-x"),
            revision_ordinal=0,
            created_tick=0,
            updated_tick=0,
            policy=_policy(),
            evidence_support_count=0,
            evidence_contradiction_count=0,
        ),
        revisions=(
            BeliefRevision(
                revision_id=BeliefRevisionId("rev-x"),
                belief_id=BeliefId("belief-2"),
                owner_id=AgentId("agent-2"),
                ordinal=0,
                logical_tick=0,
                claim=_claim(subject_agent="agent-2"),
                confidence=_confidence(confidence=0.1),
                evidence=BeliefEvidenceBundle(supporting=(), contradicting=()),
                activation_state=BeliefActivationState.CANDIDATE,
                policy=_policy(),
            ),
        ),
    )
    with pytest.raises(OwnershipError, match="ownership"):
        store.write(foreign)


def test_number_value_rejects_non_finite() -> None:
    with pytest.raises(ValueError, match="not_finite_number"):
        ClaimValue(kind=BeliefValueKind.NUMBER, number_value=float("nan"))
    with pytest.raises(ValueError, match="out_of_bounds"):
        ClaimValue(kind=BeliefValueKind.NUMBER, number_value=1.0e9)
