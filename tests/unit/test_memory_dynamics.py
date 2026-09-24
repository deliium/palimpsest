"""Unit tests for pure V2 reconstructive memory dynamics."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from memory.dynamics import (
    DynamicsCandidate,
    apply_interference,
    compete_traces,
    confidence_degradation,
    cue_overlap,
    deterministic_unit,
    effective_confidence,
    reconstruct_v2,
    retrieval_strength,
    semanticization_trigger,
    source_confusion_attribution,
    trace_similarity,
)
from memory.dynamics import (
    testing_effect_deltas as compute_testing_effect_deltas,
)
from memory.models import (
    ConceptMention,
    MemoryDistortionCode,
    MemoryDynamicsPolicy,
    MemoryId,
    MemoryRecallContext,
    MemoryReconstructionPolicy,
    MemorySituationContext,
    MemorySourceKind,
    MentionId,
    RecallEvidence,
    RecallSourceEvidence,
    ReconstructionId,
    default_memory_dynamics_policy,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit


def _source(
    *,
    memory_id: str,
    concepts: tuple[str, ...],
    rank: int = 1,
    confidence: float = 0.9,
    salience: float = 0.4,
    age: int = 2,
    tags: tuple[str, ...] = (),
    entity_id: str | None = None,
) -> RecallSourceEvidence:
    concept_mentions = tuple(
        ConceptMention(
            mention_id=MentionId(f"{memory_id}-c-{index}"),
            concept=label,
        )
        for index, label in enumerate(concepts)
    )
    entities = ()
    if entity_id is not None:
        from memory.models import EntityMention

        entities = (
            EntityMention(
                mention_id=MentionId(f"{memory_id}-e-0"),
                entity_id=EntityId(entity_id),
                label=entity_id,
            ),
        )
    return RecallSourceEvidence(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId("agent-1"),
        rank=rank,
        score=0.8,
        concepts=concept_mentions,
        entities=entities,
        relations=(),
        context=MemorySituationContext(tags=tags),
        emotional_salience=salience,
        confidence=confidence,
        source_confidence=confidence,
        episode_age_ticks=age,
        storage_age_ticks=age,
        generation=0,
        provenance_kind=MemorySourceKind.DIRECT_OBSERVATION,
    )


def _evidence(
    sources: tuple[RecallSourceEvidence, ...],
    *,
    tags: tuple[str, ...] = (),
    related: tuple[EntityId, ...] = (),
) -> RecallEvidence:
    return RecallEvidence(
        reconstruction_id=ReconstructionId("recon-1"),
        owner_id=AgentId("agent-1"),
        current_tick=10,
        sources=sources,
        beliefs=(),
        recall_context=MemoryRecallContext(tags=tags, related_entity_ids=related),
        policy=MemoryReconstructionPolicy(policy_id="recall", version="1"),
    )


def test_deterministic_unit_stable() -> None:
    assert deterministic_unit("a", "b") == deterministic_unit("a", "b")
    assert deterministic_unit("a", "b") != deterministic_unit("a", "c")


def test_temporal_decay_and_salience_resistance() -> None:
    policy = default_memory_dynamics_policy()
    young = effective_confidence(0.9, age_ticks=1, salience=0.1, policy=policy)
    old = effective_confidence(0.9, age_ticks=40, salience=0.1, policy=policy)
    resistant = effective_confidence(0.9, age_ticks=40, salience=0.95, policy=policy)
    assert old < young
    assert resistant > old
    assert resistant >= policy.confidence_floor


def test_retrieval_strength_increases_with_access() -> None:
    policy = default_memory_dynamics_policy()
    low = retrieval_strength(
        age_ticks=5,
        access_count=0,
        salience=0.5,
        confidence=0.8,
        policy=policy,
    )
    high = retrieval_strength(
        age_ticks=5,
        access_count=8,
        salience=0.5,
        confidence=0.8,
        policy=policy,
    )
    assert high > low


def test_trace_similarity_and_interference() -> None:
    left = _source(memory_id="m-1", concepts=("gate", "guard"), tags=("camp",))
    right = _source(memory_id="m-2", concepts=("gate", "wall"), tags=("camp",))
    other = _source(memory_id="m-3", concepts=("river",), tags=("forest",))
    assert trace_similarity(left, right) > trace_similarity(left, other)
    policy = MemoryDynamicsPolicy(interference_strength=0.8)
    strengths = {"m-1": 0.9, "m-2": 0.85, "m-3": 0.4}
    sims = {
        ("m-1", "m-2"): trace_similarity(left, right),
        ("m-1", "m-3"): trace_similarity(left, other),
        ("m-2", "m-3"): trace_similarity(right, other),
    }
    interfered = apply_interference(strengths, sims, policy=policy)
    assert interfered["m-1"] < strengths["m-1"]
    assert interfered["m-2"] < strengths["m-2"]


def test_cue_dependent_competition_flips_winner() -> None:
    camp = _source(
        memory_id="m-camp",
        concepts=("tent",),
        tags=("camp",),
        rank=1,
        salience=0.5,
    )
    river = _source(
        memory_id="m-river",
        concepts=("boat",),
        tags=("river",),
        rank=2,
        salience=0.5,
    )
    policy = default_memory_dynamics_policy()
    candidates = (
        DynamicsCandidate(source=camp, access_count=1, strength=0.7),
        DynamicsCandidate(source=river, access_count=1, strength=0.7),
    )
    selected_camp, _ = compete_traces(
        candidates,
        cue=MemoryRecallContext(tags=("camp",)),
        policy=policy,
        max_selected=1,
    )
    selected_river, _ = compete_traces(
        candidates,
        cue=MemoryRecallContext(tags=("river",)),
        policy=policy,
        max_selected=1,
    )
    assert selected_camp[0].source.memory_id.value == "m-camp"
    assert selected_river[0].source.memory_id.value == "m-river"


def test_confidence_degradation_not_above_source() -> None:
    policy = default_memory_dynamics_policy()
    degraded = confidence_degradation(
        0.9,
        age_ticks=20,
        blend_count=3,
        competition_mass=0.5,
        policy=policy,
    )
    assert degraded <= 0.9
    assert degraded >= policy.confidence_floor


def test_source_confusion_audit_differs_when_triggered() -> None:
    policy = MemoryDynamicsPolicy(source_confusion_mass=1.0)
    true_ids = (MemoryId("m-1"),)
    competitors = (MemoryId("m-2"), MemoryId("m-3"))
    selected, confused = source_confusion_attribution(
        true_source_ids=true_ids,
        competitor_ids=competitors,
        reconstruction_id="recon-1",
        tick=10,
        policy=policy,
    )
    assert confused
    assert selected != true_ids
    assert selected[-1] in competitors


def test_testing_effect_deltas_signed() -> None:
    policy = default_memory_dynamics_policy()
    deltas = compute_testing_effect_deltas(
        selected_ids=(MemoryId("m-1"),),
        competitor_ids=(MemoryId("m-2"),),
        policy=policy,
    )
    by_id = {item.memory_id.value: item.delta for item in deltas}
    assert by_id["m-1"] > 0.0
    assert by_id["m-2"] < 0.0


def test_semanticization_requires_similarity_and_repeats() -> None:
    policy = MemoryDynamicsPolicy(
        semanticization_similarity_threshold=0.5,
        semanticization_repeat_threshold=2,
    )
    a = _source(memory_id="m-1", concepts=("gate", "guard"))
    b = _source(memory_id="m-2", concepts=("gate", "guard"))
    cold = semanticization_trigger((a, b), policy=policy, access_counts={})
    assert not cold.should_revise
    hot = semanticization_trigger(
        (a, b),
        policy=policy,
        access_counts={"m-1": 5, "m-2": 5},
    )
    assert hot.should_revise
    assert "gate" in hot.gist_concepts


def test_reconstruct_v2_deterministic_and_emits_audit() -> None:
    sources = (
        _source(memory_id="m-1", concepts=("gate",), tags=("camp",), rank=1),
        _source(memory_id="m-2", concepts=("gate", "wall"), tags=("camp",), rank=2),
        _source(memory_id="m-3", concepts=("river",), tags=("river",), rank=3),
    )
    evidence = _evidence(sources, tags=("camp",))
    policy = default_memory_dynamics_policy()
    first = reconstruct_v2(evidence, policy=policy)
    second = reconstruct_v2(evidence, policy=policy)
    assert first.reconstructed == second.reconstructed
    assert first.audit == second.audit
    assert first.audit.source_memory_ids
    assert MemoryDistortionCode.COMPETITION in first.audit.distortion_codes
    # Agent attribution may differ under confusion; audit keeps true sources.
    assert set(first.audit.source_memory_ids).issubset(
        {MemoryId("m-1"), MemoryId("m-2"), MemoryId("m-3")}
    )


def test_cue_overlap_empty_cue_is_neutral() -> None:
    source = _source(memory_id="m-1", concepts=("x",))
    assert cue_overlap(source, MemoryRecallContext()) == pytest.approx(0.5)


def test_combined_interference_changes_ranking() -> None:
    strong_similar_a = _source(
        memory_id="m-a",
        concepts=("shared", "alpha"),
        tags=("zone",),
        rank=1,
        salience=0.6,
    )
    strong_similar_b = _source(
        memory_id="m-b",
        concepts=("shared", "beta"),
        tags=("zone",),
        rank=2,
        salience=0.6,
    )
    distinct = _source(
        memory_id="m-c",
        concepts=("unique",),
        tags=("zone",),
        rank=3,
        salience=0.55,
    )
    policy = MemoryDynamicsPolicy(interference_strength=0.9, competition_blend=0.1)
    candidates = (
        DynamicsCandidate(source=strong_similar_a, access_count=2, strength=0.9),
        DynamicsCandidate(source=strong_similar_b, access_count=2, strength=0.88),
        DynamicsCandidate(source=distinct, access_count=2, strength=0.7),
    )
    selected, competitors = compete_traces(
        candidates,
        cue=MemoryRecallContext(tags=("zone",)),
        policy=policy,
        max_selected=2,
    )
    selected_ids = {item.source.memory_id.value for item in selected}
    assert len(selected_ids) == 2
    assert len(competitors) == 1
