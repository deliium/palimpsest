"""Closed offline-consolidation modes, policy knobs, and episodic audits."""

from __future__ import annotations

import math

import pytest

from agents.cognition.configuration import CognitionConsolidationMode
from agents.models import AgentId, GoalId
from memory.models import (
    OFFLINE_CONSOLIDATION_POLICY_VERSION,
    ConceptMention,
    MemoryId,
    MemoryProvenance,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
    OfflineConsolidationAudit,
    OfflineConsolidationCandidateSet,
    OfflineConsolidationPolicy,
    OfflineConsolidationReasonCode,
    OfflineConsolidationSelection,
    default_offline_consolidation_policy,
    quantize_score,
)
from simulation.runner_models import ConsolidationMode
from world.identifiers import WorldRevision


def _trace(
    *, memory_id: str, owner: str = "agent-1", concept: str = "gate"
) -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId(owner),
        world_revision=WorldRevision(0),
        concepts=(
            ConceptMention(mention_id=MentionId(f"c-{memory_id}"), concept=concept),
        ),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=0.5,
        confidence=0.9,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=0,
        ),
        created_tick=0,
        source_tick=0,
        last_access_tick=0,
        access_count=0,
    )


def test_consolidation_mode_default_is_disabled_and_lockstep() -> None:
    assert ConsolidationMode.DISABLED.value == "disabled"
    assert tuple(mode.value for mode in ConsolidationMode) == tuple(
        mode.value for mode in CognitionConsolidationMode
    )
    assert CognitionConsolidationMode.DISABLED.value == ConsolidationMode.DISABLED.value


def test_policy_defaults_are_quantized_and_provider_is_off() -> None:
    policy = default_offline_consolidation_policy()
    assert policy.version == OFFLINE_CONSOLIDATION_POLICY_VERSION
    assert policy.allow_provider is False
    assert policy.cluster_similarity == quantize_score(0.5)
    assert policy.strengthen_retention_floor == quantize_score(0.4)
    assert policy.soft_forget_threshold == quantize_score(0.15)
    assert "proposition" not in repr(policy)


def test_policy_rejects_non_finite_and_overlapping_thresholds() -> None:
    with pytest.raises(ValueError, match="finite float"):
        OfflineConsolidationPolicy(cluster_similarity=math.nan)
    with pytest.raises(ValueError, match="finite float"):
        OfflineConsolidationPolicy(strengthen_retention_floor=1.5)
    with pytest.raises(ValueError, match="forget_above_strengthen"):
        OfflineConsolidationPolicy(
            strengthen_retention_floor=0.2,
            soft_forget_threshold=0.2,
        )
    with pytest.raises(ValueError, match="unsupported"):
        OfflineConsolidationPolicy(version="offline-consolidation-v0")
    with pytest.raises(TypeError, match="invalid_type"):
        OfflineConsolidationPolicy(allow_provider=1)  # type: ignore[arg-type]


def test_candidate_set_rejects_foreign_owner() -> None:
    owner = AgentId("agent-1")
    policy = default_offline_consolidation_policy()
    foreign = _trace(memory_id="m-2", owner="agent-2")
    with pytest.raises(ValueError, match="owner_mismatch"):
        OfflineConsolidationCandidateSet(
            owner_id=owner,
            tick=1,
            policy=policy,
            traces=(_trace(memory_id="m-1"), foreign),
        )


def test_selection_and_audit_repr_omit_propositions() -> None:
    owner = AgentId("agent-1")
    left = _trace(memory_id="m-1", concept="shared-gate-secret")
    right = _trace(memory_id="m-2", concept="shared-gate-secret")
    derived = _trace(memory_id="m-derived", concept="shared-gate-secret")
    selection = OfflineConsolidationSelection(
        owner_id=owner,
        tick=3,
        policy_version=OFFLINE_CONSOLIDATION_POLICY_VERSION,
        merge_groups=((left.memory_id, right.memory_id),),
        strengthen_ids=(left.memory_id,),
        belief_source_ids=(left.memory_id, right.memory_id),
        derived_traces=(derived,),
        reason_codes=(
            OfflineConsolidationReasonCode.MERGED,
            OfflineConsolidationReasonCode.BELIEF_CANDIDATE,
        ),
    )
    rendered = repr(selection)
    assert "shared-gate-secret" not in rendered
    assert "proposition" not in rendered
    assert selection.merge_groups[0][0].value == "m-1"

    audit = OfflineConsolidationAudit(
        owner_id=owner,
        tick=3,
        mode=ConsolidationMode.DETERMINISTIC.value,
        memory_ids=(left.memory_id, right.memory_id),
        strengthen_ids=(left.memory_id,),
        merge_groups=((left.memory_id, right.memory_id),),
        relationship_ids=("rel-1",),
        goal_ids=(GoalId("goal-1"),),
        reason_codes=(OfflineConsolidationReasonCode.MERGED,),
    )
    audit_repr = repr(audit)
    assert "shared-gate-secret" not in audit_repr
    assert "narrative" not in audit_repr
    assert audit.merge_count == 1
    assert audit.relationship_count == 1
    assert audit.goal_count == 1
    assert audit.belief_count == 0


def test_audit_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="invalid_mode"):
        OfflineConsolidationAudit(
            owner_id=AgentId("agent-1"),
            tick=0,
            mode="scripted",
        )
