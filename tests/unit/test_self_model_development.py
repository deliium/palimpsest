"""Emergent self-model projection from semantic beliefs."""

from __future__ import annotations

from agents.cognition.models import (
    SelfModelProjectionPolicy,
    project_legacy_self_belief_state,
    project_self_model,
)
from agents.models import AgentId
from memory.beliefs import (
    BeliefActivationState,
    BeliefConfidenceState,
    BeliefPolicyRef,
    BeliefRevisionId,
    BeliefValueKind,
    ClaimSubject,
    ClaimSubjectKind,
    ClaimValue,
    SemanticBelief,
    SemanticClaim,
)
from memory.models import BeliefId
from world.models import LifeStatus


def _belief(
    *,
    belief_id: str,
    predicate: str,
    text: str,
    confidence: float,
    activation: BeliefActivationState = BeliefActivationState.ACTIVE,
    owner: str = "agent-1",
    subject_owner: bool = True,
) -> SemanticBelief:
    owner_id = AgentId(owner)
    if subject_owner:
        subject = ClaimSubject(kind=ClaimSubjectKind.AGENT, agent_id=owner_id)
        value = ClaimValue(kind=BeliefValueKind.TEXT, text_value=text)
    else:
        subject = ClaimSubject(kind=ClaimSubjectKind.CONCEPT, concept="other-topic")
        value = ClaimValue(kind=BeliefValueKind.TEXT, text_value=text)
    return SemanticBelief(
        belief_id=BeliefId(belief_id),
        owner_id=owner_id,
        claim=SemanticClaim(subject=subject, predicate=predicate, value=value),
        confidence=BeliefConfidenceState(
            confidence=confidence,
            support_mass=confidence,
            contradiction_mass=0.0,
        ),
        activation_state=activation,
        current_revision_id=BeliefRevisionId(f"rev-{belief_id}"),
        revision_ordinal=0,
        created_tick=0,
        updated_tick=0,
        policy=BeliefPolicyRef(policy_id="semantic-v1", version="1"),
        evidence_support_count=2,
        evidence_contradiction_count=0,
    )


def test_self_model_selects_owner_relevant_active_beliefs() -> None:
    owner = AgentId("agent-1")
    beliefs = (
        _belief(
            belief_id="b-food",
            predicate="experienced_concept",
            text="food",
            confidence=0.8,
        ),
        _belief(
            belief_id="b-protect",
            predicate="protects",
            text="others",
            confidence=0.7,
        ),
        _belief(
            belief_id="b-weak",
            predicate="experienced_concept",
            text="noise",
            confidence=0.05,
        ),
        _belief(
            belief_id="b-retired",
            predicate="experienced_concept",
            text="old",
            confidence=0.9,
            activation=BeliefActivationState.RETIRED,
        ),
        _belief(
            belief_id="b-foreign",
            predicate="experienced_concept",
            text="x",
            confidence=0.9,
            owner="agent-2",
        ),
        _belief(
            belief_id="b-unrelated",
            predicate="observed",
            text="gate",
            confidence=0.9,
            subject_owner=False,
        ),
    )
    model = project_self_model(
        owner_id=owner,
        life_status=LifeStatus.ALIVE,
        beliefs=beliefs,
        policy=SelfModelProjectionPolicy(
            policy_id="self-model-projection",
            version="1",
            min_confidence=0.2,
        ),
    )
    selected_ids = {item.belief_id.value for item in model.beliefs}
    assert selected_ids == {"b-food", "b-protect"}
    assert model.candidate_count == 2
    assert model.beliefs[0].belief_id.value == "b-food"
    assert "food" not in repr(model)
    legacy = project_legacy_self_belief_state(model)
    assert legacy.belief_ids == model.belief_ids


def test_identical_snapshots_yield_identical_self_models() -> None:
    beliefs = (
        _belief(
            belief_id="b-1",
            predicate="experienced_concept",
            text="food",
            confidence=0.6,
        ),
        _belief(
            belief_id="b-2",
            predicate="experienced_concept",
            text="water",
            confidence=0.5,
        ),
    )
    left = project_self_model(
        owner_id=AgentId("agent-1"),
        life_status=LifeStatus.ALIVE,
        beliefs=beliefs,
    )
    right = project_self_model(
        owner_id=AgentId("agent-1"),
        life_status=LifeStatus.ALIVE,
        beliefs=tuple(reversed(beliefs)),
    )
    assert left == right


def test_others_trust_me_style_value_reference() -> None:
    owner = AgentId("agent-1")
    claim = SemanticClaim(
        subject=ClaimSubject(kind=ClaimSubjectKind.AGENT, agent_id=AgentId("agent-2")),
        predicate="trusts",
        value=ClaimValue(kind=BeliefValueKind.AGENT, agent_id=owner),
    )
    belief = SemanticBelief(
        belief_id=BeliefId("b-trust"),
        owner_id=owner,
        claim=claim,
        confidence=BeliefConfidenceState(
            confidence=0.75, support_mass=0.75, contradiction_mass=0.0
        ),
        activation_state=BeliefActivationState.ACTIVE,
        current_revision_id=BeliefRevisionId("rev-trust"),
        revision_ordinal=0,
        created_tick=0,
        updated_tick=0,
        policy=BeliefPolicyRef(policy_id="semantic-v1", version="1"),
        evidence_support_count=3,
        evidence_contradiction_count=0,
    )
    model = project_self_model(
        owner_id=owner, life_status=LifeStatus.ALIVE, beliefs=(belief,)
    )
    assert len(model.beliefs) == 1
    assert model.beliefs[0].claim.predicate == "trusts"
