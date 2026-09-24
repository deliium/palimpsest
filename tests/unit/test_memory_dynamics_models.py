"""Unit tests for V2 memory dynamics contracts and carriers."""

from __future__ import annotations

import math

import pytest

from agents.models import AgentId
from memory.models import (
    MEMORY_DYNAMICS_POLICY_VERSION,
    ConceptMention,
    MemoryDistortionCode,
    MemoryDynamicsPolicy,
    MemoryId,
    MemoryRecallContext,
    MemoryRecallRequest,
    MemoryRecallResult,
    MemoryReconstructionPolicy,
    MemoryRetrieveRequest,
    MemoryScoreWeights,
    MemoryScoringPolicy,
    MemorySituationContext,
    MemorySourceKind,
    MentionId,
    RecallAuditRecord,
    RecallEvidence,
    RecallSourceEvidence,
    ReconstructedMemory,
    ReconstructionId,
    StrengthDeltaSummary,
    default_memory_dynamics_policy,
)

pytestmark = pytest.mark.unit


def _retrieve() -> MemoryRetrieveRequest:
    return MemoryRetrieveRequest(
        current_tick=5,
        limit=3,
        scoring_policy=MemoryScoringPolicy(
            policy_id="score",
            version="1",
            weights=MemoryScoreWeights(recency=1.0),
        ),
    )


def _evidence() -> RecallEvidence:
    source = RecallSourceEvidence(
        memory_id=MemoryId("m-1"),
        owner_id=AgentId("agent-1"),
        rank=1,
        score=0.8,
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept="gate"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=0.4,
        confidence=0.9,
        source_confidence=0.9,
        episode_age_ticks=2,
        storage_age_ticks=3,
        generation=0,
        provenance_kind=MemorySourceKind.DIRECT_OBSERVATION,
    )
    return RecallEvidence(
        reconstruction_id=ReconstructionId("recon-1"),
        owner_id=AgentId("agent-1"),
        current_tick=5,
        sources=(source,),
        beliefs=(),
        recall_context=MemoryRecallContext(),
        policy=MemoryReconstructionPolicy(policy_id="recall", version="1"),
    )


def _reconstructed() -> ReconstructedMemory:
    evidence = _evidence()
    return ReconstructedMemory(
        reconstruction_id=ReconstructionId("recon-1"),
        owner_id=AgentId("agent-1"),
        narrative="merged",
        concepts=evidence.sources[0].concepts,
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        confidence=0.9,
        emotional_salience=0.4,
        source_memory_ids=(MemoryId("m-1"),),
        generation=1,
        reconstructed_at_tick=5,
        policy_id="recall",
        policy_version="1",
        used_provider=False,
        fallback_used=False,
    )


def test_default_dynamics_policy_version_stable() -> None:
    policy = default_memory_dynamics_policy()
    assert policy.version == MEMORY_DYNAMICS_POLICY_VERSION
    assert policy.version == "memory-dynamics-v1"
    assert policy.decay_rate == pytest.approx(0.02)
    assert policy.semanticization_repeat_threshold == 3


def test_dynamics_policy_rejects_unsupported_version() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        MemoryDynamicsPolicy(version="memory-dynamics-v0")


def test_dynamics_policy_rejects_non_unit_knobs() -> None:
    with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
        MemoryDynamicsPolicy(decay_rate=1.5)
    with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
        MemoryDynamicsPolicy(interference_strength=float("nan"))
    with pytest.raises(ValueError, match="out_of_range"):
        MemoryDynamicsPolicy(semanticization_repeat_threshold=0)


def test_dynamics_policy_quantizes_knobs() -> None:
    policy = MemoryDynamicsPolicy(decay_rate=0.02 + 1e-9)
    assert math.isclose(policy.decay_rate, 0.02, abs_tol=1e-6)


def test_recall_request_defaults_dynamics_none() -> None:
    request = MemoryRecallRequest(
        retrieve=_retrieve(),
        reconstruction_id=ReconstructionId("recon-1"),
        reconstruction_policy=MemoryReconstructionPolicy(
            policy_id="recall", version="1"
        ),
    )
    assert request.dynamics_policy is None
    assert "dynamics_policy_version=None" in repr(request)


def test_recall_request_accepts_dynamics_policy() -> None:
    policy = default_memory_dynamics_policy()
    request = MemoryRecallRequest(
        retrieve=_retrieve(),
        reconstruction_id=ReconstructionId("recon-1"),
        reconstruction_policy=MemoryReconstructionPolicy(
            policy_id="recall", version="1"
        ),
        dynamics_policy=policy,
    )
    assert request.dynamics_policy is policy
    assert "memory-dynamics-v1" in repr(request)


def test_recall_request_rejects_invalid_dynamics_type() -> None:
    with pytest.raises(TypeError, match="dynamics_policy"):
        MemoryRecallRequest(
            retrieve=_retrieve(),
            reconstruction_id=ReconstructionId("recon-1"),
            reconstruction_policy=MemoryReconstructionPolicy(
                policy_id="recall", version="1"
            ),
            dynamics_policy="memory-dynamics-v1",  # type: ignore[arg-type]
        )


def test_strength_delta_and_audit_safe_repr() -> None:
    delta = StrengthDeltaSummary(memory_id=MemoryId("m-1"), delta=-0.04)
    assert delta.delta == pytest.approx(-0.04)
    audit = RecallAuditRecord(
        reconstruction_id=ReconstructionId("recon-1"),
        owner_id=AgentId("agent-1"),
        tick=5,
        source_memory_ids=(MemoryId("m-1"),),
        competitor_ids=(MemoryId("m-2"),),
        selected_ids=(MemoryId("m-1"),),
        distortion_codes=(
            MemoryDistortionCode.INTERFERENCE,
            MemoryDistortionCode.SOURCE_CONFUSION,
        ),
        confidence_before=0.9,
        confidence_after=0.7,
        strength_deltas=(delta,),
    )
    text = repr(audit)
    assert "agent-1" in text
    assert "source_count=1" in text
    assert "competitor_count=1" in text
    assert "gate" not in text
    assert "narrative" not in text


def test_recall_result_defaults_empty_audits() -> None:
    result = MemoryRecallResult(
        reconstructions=(_reconstructed(),),
        pending_accesses=(),
        evidence=_evidence(),
    )
    assert result.audits == ()
    assert "audit_count=0" in repr(result)


def test_recall_result_rejects_audit_owner_mismatch() -> None:
    audit = RecallAuditRecord(
        reconstruction_id=ReconstructionId("recon-1"),
        owner_id=AgentId("other"),
        tick=5,
        source_memory_ids=(MemoryId("m-1"),),
        competitor_ids=(),
        selected_ids=(MemoryId("m-1"),),
        distortion_codes=(),
        confidence_before=0.9,
        confidence_after=0.9,
    )
    with pytest.raises(ValueError, match="owner_mismatch"):
        MemoryRecallResult(
            reconstructions=(_reconstructed(),),
            pending_accesses=(),
            evidence=_evidence(),
            audits=(audit,),
        )


def test_closed_distortion_codes() -> None:
    assert set(MemoryDistortionCode) == {
        MemoryDistortionCode.TEMPORAL_DECAY,
        MemoryDistortionCode.INTERFERENCE,
        MemoryDistortionCode.COMPETITION,
        MemoryDistortionCode.SALIENCE_BIAS,
        MemoryDistortionCode.CONFIDENCE_DEGRADATION,
        MemoryDistortionCode.SOURCE_CONFUSION,
        MemoryDistortionCode.TESTING_EFFECT,
        MemoryDistortionCode.SEMANTICIZATION,
    }
