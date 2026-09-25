"""Identity projection stays off the V1 self-model path."""

from __future__ import annotations

import pytest

from agents.cognition import project_self_model
from agents.cognition.models import SelfModelProjectionPolicy
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


def _belief(*, belief_id: str, confidence: float) -> SemanticBelief:
    owner = AgentId("agent-1")
    return SemanticBelief(
        belief_id=BeliefId(belief_id),
        owner_id=owner,
        claim=SemanticClaim(
            subject=ClaimSubject(kind=ClaimSubjectKind.AGENT, agent_id=owner),
            predicate="experienced_concept",
            value=ClaimValue(kind=BeliefValueKind.TEXT, text_value="food"),
        ),
        confidence=BeliefConfidenceState(
            confidence=confidence,
            support_mass=confidence,
            contradiction_mass=0.0,
        ),
        activation_state=BeliefActivationState.ACTIVE,
        current_revision_id=BeliefRevisionId(f"rev-{belief_id}"),
        revision_ordinal=0,
        created_tick=0,
        updated_tick=0,
        policy=BeliefPolicyRef(policy_id="semantic-belief-formation", version="1"),
        evidence_support_count=2,
        evidence_contradiction_count=0,
    )


def test_v1_projection_keeps_selection_and_leaves_identity_empty() -> None:
    owner = AgentId("agent-1")
    model = project_self_model(
        owner_id=owner,
        life_status=LifeStatus.ALIVE,
        beliefs=(
            _belief(belief_id="b-high", confidence=0.8),
            _belief(belief_id="b-low", confidence=0.05),
        ),
        policy=SelfModelProjectionPolicy(
            policy_id="self-model-projection",
            version="1",
            min_confidence=0.2,
        ),
    )
    assert [item.belief_id.value for item in model.beliefs] == ["b-high"]
    assert model.confidence == pytest.approx(0.8)
    assert model.identity is None
    assert "food" not in repr(model)
