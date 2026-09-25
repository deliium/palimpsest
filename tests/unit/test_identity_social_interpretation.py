"""Relationship and reliability views scale trust inside a closed band."""

from __future__ import annotations

import pytest

from agents.cognition.communication import (
    identity_social_scale_factor,
    scale_trust_for_identity,
)
from agents.cognition.identity import (
    IDENTITY_POLICY_ID,
    IDENTITY_POLICY_VERSION,
    IdentityAspect,
    IdentityPolicy,
    IdentityProvenanceKind,
    IdentityRevisionPoint,
    IdentityRevisionSummary,
    IdentityState,
    aggregate_identity_confidence,
    assemble_identity_belief_view,
    build_identity_claim,
    identity_predicate,
)
from agents.models import AgentId
from memory.beliefs import BeliefActivationState, BeliefValueKind, ClaimValue
from memory.models import BeliefId, MemoryId, quantize_score

_OWNER = AgentId("agent-1")
_OTHER = "agent-2"


def _view(
    *,
    aspect: IdentityAspect,
    provenance: IdentityProvenanceKind,
    token: str,
    belief_id: str,
    supporting: tuple[str, ...],
    contradicting: tuple[str, ...] = (),
) -> object:
    claim = build_identity_claim(
        _OWNER,
        identity_predicate(aspect, provenance, token),
        ClaimValue(kind=BeliefValueKind.BOOL, bool_value=True),
    )
    point = IdentityRevisionPoint(
        ordinal=0, tick=1, confidence=0.8, contradicted=False
    )
    summary = IdentityRevisionSummary(
        ordinal=0, tick=1, activation=BeliefActivationState.ACTIVE
    )
    return assemble_identity_belief_view(
        belief_id=BeliefId(belief_id),
        claim=claim,
        confidence=0.8,
        supporting_memory_ids=tuple(MemoryId(item) for item in supporting),
        contradicting_memory_ids=tuple(MemoryId(item) for item in contradicting),
        activation=BeliefActivationState.ACTIVE,
        revision_points=(point,),
        revision_summaries=(summary,),
    )


def _state(*views: object) -> IdentityState:
    typed = tuple(views)
    return IdentityState(
        owner_id=_OWNER,
        policy_id=IDENTITY_POLICY_ID,
        policy_version=IDENTITY_POLICY_VERSION,
        views=typed,  # type: ignore[arg-type]
        aggregate_confidence=aggregate_identity_confidence(typed),  # type: ignore[arg-type]
    )


def test_missing_views_leave_trust_unchanged() -> None:
    trust, factor = scale_trust_for_identity(
        0.4, identity=None, counterpart_id=_OTHER
    )
    assert trust == 0.4
    assert factor == 1.0
    empty = _state()
    scaled, scaled_factor = scale_trust_for_identity(
        0.4, identity=empty, counterpart_id=_OTHER
    )
    assert scaled == pytest.approx(0.4)
    assert scaled_factor == 1.0


def test_full_support_raises_trust_inside_the_ceiling() -> None:
    policy = IdentityPolicy()
    identity = _state(
        _view(
            aspect=IdentityAspect.RELATIONSHIP,
            provenance=IdentityProvenanceKind.RELATIONSHIP_EVIDENCE,
            token=_OTHER,
            belief_id="belief-rel",
            supporting=("mem-1",),
        ),
        _view(
            aspect=IdentityAspect.RELIABILITY,
            provenance=IdentityProvenanceKind.OBSERVED_OUTCOME,
            token="search",
            belief_id="belief-reliable",
            supporting=("mem-2",),
        ),
    )
    factor = identity_social_scale_factor(identity, _OTHER)
    assert factor == pytest.approx(policy.social_scale_ceiling)
    scaled, _ = scale_trust_for_identity(0.5, identity=identity, counterpart_id=_OTHER)
    assert scaled == pytest.approx(quantize_score(0.5 * policy.social_scale_ceiling))
    clamped, _ = scale_trust_for_identity(
        1.0, identity=identity, counterpart_id=_OTHER
    )
    assert clamped == 1.0


def test_contradiction_lowers_trust_to_the_floor() -> None:
    policy = IdentityPolicy()
    identity = _state(
        _view(
            aspect=IdentityAspect.RELATIONSHIP,
            provenance=IdentityProvenanceKind.RELATIONSHIP_EVIDENCE,
            token=_OTHER,
            belief_id="belief-rel",
            supporting=(),
            contradicting=("mem-1",),
        )
    )
    factor = identity_social_scale_factor(identity, _OTHER)
    assert factor == pytest.approx(policy.social_scale_floor)
    scaled, _ = scale_trust_for_identity(0.5, identity=identity, counterpart_id=_OTHER)
    assert scaled == pytest.approx(quantize_score(0.5 * policy.social_scale_floor))


def test_unrelated_counterpart_uses_reliability_only() -> None:
    identity = _state(
        _view(
            aspect=IdentityAspect.RELATIONSHIP,
            provenance=IdentityProvenanceKind.RELATIONSHIP_EVIDENCE,
            token="agent-9",
            belief_id="belief-other",
            supporting=(),
            contradicting=("mem-1",),
        ),
        _view(
            aspect=IdentityAspect.RELIABILITY,
            provenance=IdentityProvenanceKind.OBSERVED_OUTCOME,
            token="search",
            belief_id="belief-reliable",
            supporting=("mem-2",),
        ),
    )
    factor = identity_social_scale_factor(identity, _OTHER)
    assert factor == pytest.approx(IdentityPolicy().social_scale_ceiling)
