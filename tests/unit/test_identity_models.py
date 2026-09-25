"""Identity vocabulary, claim grammar, and derived stability."""

from __future__ import annotations

import pytest

from agents.cognition import (
    IDENTITY_POLICY_ID,
    IDENTITY_POLICY_VERSION,
    IdentityAspect,
    IdentityBeliefView,
    IdentityConflictCode,
    IdentityPolicy,
    IdentityProvenanceKind,
    IdentityRevisionPoint,
    IdentityRevisionSummary,
    IdentityState,
    aggregate_identity_confidence,
    assemble_identity_belief_view,
    build_identity_claim,
    default_identity_policy,
    derive_identity_rate,
    derive_identity_stability,
)
from agents.models import AgentId
from memory.beliefs import BeliefActivationState, BeliefValueKind, ClaimValue
from memory.models import BeliefId, MemoryId


def _claim(owner: AgentId, predicate: str) -> object:
    return build_identity_claim(
        owner,
        predicate,
        ClaimValue(kind=BeliefValueKind.BOOL, bool_value=True),
    )


def _point(
    ordinal: int,
    tick: int,
    confidence: float,
    *,
    contradicted: bool = False,
) -> IdentityRevisionPoint:
    return IdentityRevisionPoint(
        ordinal=ordinal,
        tick=tick,
        confidence=confidence,
        contradicted=contradicted,
    )


def _summary(
    ordinal: int,
    tick: int,
    activation: BeliefActivationState = BeliefActivationState.CANDIDATE,
) -> IdentityRevisionSummary:
    return IdentityRevisionSummary(ordinal=ordinal, tick=tick, activation=activation)


def test_closed_aspects_and_provenance_are_topics() -> None:
    assert len(IdentityAspect) == 11
    assert len(IdentityProvenanceKind) == 5
    assert {item.value for item in IdentityConflictCode} == {
        "commitment_command",
        "inferred_value_command",
        "risk_above_tolerance",
    }
    policy = default_identity_policy()
    assert policy.policy_id == IDENTITY_POLICY_ID
    assert policy.version == IDENTITY_POLICY_VERSION
    assert policy.social_scale_floor == pytest.approx(0.85)
    assert policy.social_scale_ceiling == pytest.approx(1.15)
    with pytest.raises(ValueError, match="unsupported"):
        IdentityPolicy(version="0")


def test_claim_builder_accepts_only_bool_true() -> None:
    owner = AgentId("agent-1")
    predicate = "identity.ability.observed_outcome.move_north"
    claim = build_identity_claim(
        owner,
        predicate,
        ClaimValue(kind=BeliefValueKind.BOOL, bool_value=True),
    )
    assert claim.predicate == predicate
    assert claim.value.bool_value is True
    assert claim.subject.agent_id == owner
    with pytest.raises(ValueError, match="text_value_rejected"):
        build_identity_claim(
            owner,
            predicate,
            ClaimValue(kind=BeliefValueKind.TEXT, text_value="warrior"),
        )
    with pytest.raises(ValueError, match="number_value_rejected"):
        build_identity_claim(
            owner,
            predicate,
            ClaimValue(kind=BeliefValueKind.NUMBER, number_value=0.5),
        )
    with pytest.raises(ValueError, match="agent_value_rejected"):
        build_identity_claim(
            owner,
            predicate,
            ClaimValue(kind=BeliefValueKind.AGENT, agent_id=AgentId("agent-2")),
        )
    with pytest.raises(ValueError, match="bool_not_true"):
        build_identity_claim(
            owner,
            predicate,
            ClaimValue(kind=BeliefValueKind.BOOL, bool_value=False),
        )
    with pytest.raises(ValueError, match="unknown_aspect"):
        build_identity_claim(
            owner,
            "identity.warrior.observed_outcome.move_north",
            ClaimValue(kind=BeliefValueKind.BOOL, bool_value=True),
        )
    with pytest.raises(ValueError, match="unknown_provenance"):
        build_identity_claim(
            owner,
            "identity.ability.scripted.move_north",
            ClaimValue(kind=BeliefValueKind.BOOL, bool_value=True),
        )
    with pytest.raises(ValueError, match="forbidden_identity_token"):
        build_identity_claim(
            owner,
            "identity.social_role.social_feedback.Leader",
            ClaimValue(kind=BeliefValueKind.BOOL, bool_value=True),
        )


def test_rate_tracks_counts_and_claim_stays_true() -> None:
    low = derive_identity_rate(support_count=1, contradiction_count=3)
    high = derive_identity_rate(support_count=3, contradiction_count=1)
    assert high > low
    assert derive_identity_rate(support_count=2, contradiction_count=0) == 1.0
    owner = AgentId("agent-1")
    claim = _claim(owner, "identity.reliability.observed_outcome.same_token")
    assert claim.value.bool_value is True
    with pytest.raises(ValueError, match="empty_evidence"):
        derive_identity_rate(support_count=0, contradiction_count=0)


def test_first_revision_is_less_stable_than_a_long_uncontradicted_chain() -> None:
    first = (_point(0, 1, 0.4),)
    long_chain = tuple(
        _point(index, index * 2, 0.4) for index in range(8)
    )
    first_stability = derive_identity_stability(first)
    long_stability = derive_identity_stability(long_chain)
    assert derive_identity_stability(first) == first_stability
    assert long_stability > first_stability
    contradicted = (
        *long_chain[:-1],
        _point(7, 14, 0.2, contradicted=True),
    )
    assert derive_identity_stability(contradicted) < long_stability
    with pytest.raises(ValueError, match="empty_history"):
        derive_identity_stability(())


def test_same_chain_yields_the_same_view_and_repr_hides_claim_text() -> None:
    owner = AgentId("agent-1")
    predicate = "identity.ability.observed_outcome.move_north"
    claim = _claim(owner, predicate)
    points = (_point(0, 2, 0.3), _point(1, 6, 0.45))
    summaries = (
        _summary(0, 2),
        _summary(1, 6, BeliefActivationState.ACTIVE),
    )
    kwargs = {
        "belief_id": BeliefId("belief-ability-1"),
        "claim": claim,
        "confidence": 0.45,
        "supporting_memory_ids": (MemoryId("mem-a"), MemoryId("mem-b")),
        "contradicting_memory_ids": (MemoryId("mem-c"),),
        "activation": BeliefActivationState.ACTIVE,
        "revision_points": points,
        "revision_summaries": summaries,
    }
    first = assemble_identity_belief_view(**kwargs)
    second = assemble_identity_belief_view(**kwargs)
    assert first == second
    assert first.derived_rate < 1.0
    assert first.claim.value.bool_value is True
    rendered = repr(first)
    assert predicate not in rendered
    assert "move_north" not in rendered
    assert "True" not in rendered
    assert "ability" in rendered
    assert "support_count=2" in rendered
    assert "contradiction_count=1" in rendered
    assert str(first.derived_rate) in rendered
    assert str(first.derived_stability) in rendered
    state = IdentityState(
        owner_id=owner,
        policy_id=IDENTITY_POLICY_ID,
        policy_version=IDENTITY_POLICY_VERSION,
        views=(first,),
        aggregate_confidence=aggregate_identity_confidence((first,)),
    )
    state_repr = repr(state)
    assert predicate not in state_repr
    assert "view_count=1" in state_repr
    assert "dissonance_count=0" in state_repr
    with pytest.raises(ValueError, match="retired"):
        IdentityBeliefView(
            belief_id=BeliefId("belief-retired"),
            aspect=IdentityAspect.ABILITY,
            provenance=IdentityProvenanceKind.OBSERVED_OUTCOME,
            evidence_token="move_north",
            claim=claim,
            confidence=0.45,
            derived_rate=0.5,
            supporting_memory_ids=(MemoryId("mem-a"),),
            contradicting_memory_ids=(),
            derived_stability=0.1,
            activation=BeliefActivationState.RETIRED,
            revisions=(_summary(0, 2),),
        )
