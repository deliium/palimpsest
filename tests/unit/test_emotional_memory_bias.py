"""Unit tests for prior-emotion retrieval and situation-focus bias."""

from __future__ import annotations

import pytest

from agents.cognition.defaults import DirectSituationModeler
from agents.cognition.emotion_bias import (
    EMOTION_BIAS_POLICY_VERSION,
    apply_retrieval_emotion_bias,
    apply_situation_focus_bias,
    prior_emotion_bias_active,
)
from agents.cognition.models import (
    AgentEmotionalState,
    CognitiveLoopInput,
    EmotionIntensity,
    EmotionKind,
    InternalAgentState,
    InterpretedPerception,
    PerceptionClaimCode,
    RetrievedMemoryContext,
    SituationClaimCode,
    SubjectiveSnapshot,
    empty_emotional_state,
)
from agents.models import AgentId
from memory.models import (
    MemoryId,
    MemoryProvenance,
    MemoryRankedHit,
    MemoryScoreBreakdown,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import Observation, ObservedSelf
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)


def _trace(
    memory_id: str,
    *,
    salience: float,
    tags: tuple[str, ...] = (),
    score: float = 0.5,
) -> MemoryRankedHit:
    owner = AgentId("agent-1")
    trace = MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=owner,
        world_revision=WorldRevision(0),
        concepts=(),
        entities=(),
        relations=(),
        context=MemorySituationContext(tags=tags),
        emotional_salience=salience,
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
    return MemoryRankedHit(
        rank=1,
        trace=trace,
        score=score,
        breakdown=MemoryScoreBreakdown(),
        matched_concept_mention_ids=(),
        matched_entity_mention_ids=(),
        scoring_policy_id="test",
        scoring_policy_version="1",
        retrieval_tick=0,
    )


def _fear_prior(*, intensity: float = 0.8) -> AgentEmotionalState:
    return AgentEmotionalState(
        owner_id=AgentId("agent-1"),
        tick=1,
        intensities=(
            EmotionIntensity(kind=EmotionKind.FEAR, intensity=intensity),
        ),
        last_update_tick=1,
        policy_version="emotion.v1",
    )


def test_prior_emotion_bias_inactive_when_passthrough_or_neutral() -> None:
    prior = _fear_prior()
    assert prior_emotion_bias_active(prior, enabled=False) is False
    assert prior_emotion_bias_active(None, enabled=True) is False
    assert (
        prior_emotion_bias_active(
            empty_emotional_state(AgentId("agent-1"), tick=0),
            enabled=True,
        )
        is False
    )
    assert prior_emotion_bias_active(prior, enabled=True) is True


def test_retrieval_bias_promotes_salient_threat_under_fear() -> None:
    social = _trace("m-social", salience=0.1, tags=("social_signal",), score=0.7)
    threat = _trace(
        "m-threat",
        salience=0.9,
        tags=("threat_signal",),
        score=0.4,
    )
    # Fix ranks for ordered input.
    social = MemoryRankedHit(
        rank=1,
        trace=social.trace,
        score=social.score,
        breakdown=social.breakdown,
        matched_concept_mention_ids=(),
        matched_entity_mention_ids=(),
        scoring_policy_id="test",
        scoring_policy_version="1",
        retrieval_tick=0,
    )
    threat = MemoryRankedHit(
        rank=2,
        trace=threat.trace,
        score=threat.score,
        breakdown=threat.breakdown,
        matched_concept_mention_ids=(),
        matched_entity_mention_ids=(),
        scoring_policy_id="test",
        scoring_policy_version="1",
        retrieval_tick=0,
    )
    prior = _fear_prior()

    off, applied_off = apply_retrieval_emotion_bias(
        (social, threat), prior, enabled=False
    )
    assert applied_off is False
    assert off[0].trace.memory_id.value == "m-social"

    on, applied_on = apply_retrieval_emotion_bias(
        (social, threat), prior, enabled=True
    )
    assert applied_on is True
    assert on[0].trace.memory_id.value == "m-threat"
    assert on[0].rank == 1
    assert on[1].trace.memory_id.value == "m-social"


def test_situation_focus_bias_surfaces_threat_under_fear() -> None:
    claims = (
        SituationClaimCode.LOCAL_SCENE,
        SituationClaimCode.SOCIAL_SIGNAL,
        SituationClaimCode.THREAT_SIGNAL,
    )
    prior = _fear_prior()
    off, counts_off, applied_off = apply_situation_focus_bias(
        claims, prior, enabled=False
    )
    assert applied_off is False
    assert off == claims
    assert counts_off == {}

    on, counts_on, applied_on = apply_situation_focus_bias(
        claims, prior, enabled=True
    )
    assert applied_on is True
    assert on[0] is SituationClaimCode.THREAT_SIGNAL
    assert counts_on.get("threat_focus") == 1
    assert EMOTION_BIAS_POLICY_VERSION.startswith("emotion-bias")


@pytest.mark.asyncio
async def test_situation_modeler_applies_bias_only_when_enabled() -> None:
    owner = AgentId("agent-1")
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=2,
        self_body=ObservedSelf(
            entity_id=EntityId("body-1"),
            location_id=EntityId("loc-1"),
            health=Health(100),
            hunger=Hunger(0),
            thirst=Thirst(0),
            fatigue=Fatigue(0),
            temperature=TemperatureCelsius(36.5),
            inventory=(),
            life_status=LifeStatus.ALIVE,
            carry_capacity=CarryCapacity(10),
        ),
    )
    perception = InterpretedPerception(
        owner_id=owner,
        observer_id=EntityId("body-1"),
        tick=2,
        revision=WorldRevision(0),
        life_status=LifeStatus.ALIVE,
        location_id=EntityId("loc-1"),
        claim_codes=(
            PerceptionClaimCode.HAS_LOCATION,
            PerceptionClaimCode.HAS_COMMUNICATIONS,
            PerceptionClaimCode.HAS_VISIBLE_BODIES,
        ),
        counts={
            "communications": 1,
            "visible_bodies": 1,
        },
        confidence=1.0,
    )
    memory = RetrievedMemoryContext(
        owner_id=owner,
        memory_ids=(),
        belief_ids=(),
        confidence=1.0,
    )
    snapshot = SubjectiveSnapshot(
        owner_id=owner,
        revision=0,
        memories=(),
        legacy_beliefs=(),
        semantic_beliefs=(),
        emotional_state=_fear_prior(),
    )
    loop_input = CognitiveLoopInput(
        agent_id=owner,
        observation=observation,
        internal_state=InternalAgentState(owner_id=owner),
        snapshot=snapshot,
    )

    passthrough = DirectSituationModeler(emotion_bias=False)
    model_off = await passthrough.model(loop_input, perception, memory)
    assert model_off.claim_codes[0] is not SituationClaimCode.THREAT_SIGNAL or (
        SituationClaimCode.SOCIAL_SIGNAL in model_off.claim_codes
        and model_off.claim_codes.index(SituationClaimCode.SOCIAL_SIGNAL)
        < model_off.claim_codes.index(SituationClaimCode.THREAT_SIGNAL)
    )

    enabled = DirectSituationModeler(emotion_bias=True)
    model_on = await enabled.model(loop_input, perception, memory)
    assert model_on.claim_codes[0] is SituationClaimCode.THREAT_SIGNAL
    assert any(
        code.startswith("emotion_bias:")
        for code in model_on.decision_metadata.selection_codes
    )


@pytest.mark.asyncio
async def test_emotion_bias_does_not_rewrite_v2_audit_selected_ids() -> None:
    """Dynamics audits are pre-emotion; bias only reorders agent-visible views."""
    from agents.cognition.emotion_bias import apply_reconstruction_emotion_bias
    from memory.models import (
        ConceptMention,
        MemoryMutationBatch,
        MemoryProvenance,
        MemoryRecallRequest,
        MemoryReconstructionPolicy,
        MemoryRetrieveRequest,
        MemoryRunId,
        MemoryScope,
        MemoryScoreWeights,
        MemoryScoringPolicy,
        MemorySourceKind,
        MemoryTrace,
        MentionId,
        ReconstructionId,
        default_memory_dynamics_policy,
    )
    from memory.service import InMemoryMemoryService

    scope = MemoryScope(run_id=MemoryRunId("run-emo"), owner_id=AgentId("agent-1"))
    service = InMemoryMemoryService(scope)
    await service.apply(
        MemoryMutationBatch(
            writes=(
                MemoryTrace(
                    memory_id=MemoryId("m-threat"),
                    owner_id=AgentId("agent-1"),
                    world_revision=WorldRevision(0),
                    concepts=(
                        ConceptMention(
                            mention_id=MentionId("c-t"), concept="alarm"
                        ),
                    ),
                    entities=(),
                    relations=(),
                    context=MemorySituationContext(tags=("threat_signal",)),
                    emotional_salience=0.9,
                    confidence=0.9,
                    provenance=MemoryProvenance(
                        kind=MemorySourceKind.DIRECT_OBSERVATION,
                        source_tick=4,
                    ),
                    created_tick=4,
                    source_tick=4,
                    last_access_tick=4,
                    access_count=0,
                ),
                MemoryTrace(
                    memory_id=MemoryId("m-social"),
                    owner_id=AgentId("agent-1"),
                    world_revision=WorldRevision(0),
                    concepts=(
                        ConceptMention(
                            mention_id=MentionId("c-s"), concept="chat"
                        ),
                    ),
                    entities=(),
                    relations=(),
                    context=MemorySituationContext(tags=("social_signal",)),
                    emotional_salience=0.2,
                    confidence=0.9,
                    provenance=MemoryProvenance(
                        kind=MemorySourceKind.DIRECT_OBSERVATION,
                        source_tick=3,
                    ),
                    created_tick=3,
                    source_tick=3,
                    last_access_tick=3,
                    access_count=0,
                ),
            )
        )
    )
    result = await service.recall(
        MemoryRecallRequest(
            retrieve=MemoryRetrieveRequest(
                current_tick=10,
                limit=8,
                scoring_policy=MemoryScoringPolicy(
                    policy_id="score",
                    version="1",
                    weights=MemoryScoreWeights(recency=1.0),
                ),
            ),
            reconstruction_id=ReconstructionId("recon-emo"),
            reconstruction_policy=MemoryReconstructionPolicy(
                policy_id="recall", version="1"
            ),
            dynamics_policy=default_memory_dynamics_policy(),
        )
    )
    assert len(result.audits) == 1
    selected_before = result.audits[0].selected_ids
    _biased, applied = apply_reconstruction_emotion_bias(
        result.reconstructions,
        _fear_prior(),
        enabled=True,
    )
    assert result.audits[0].selected_ids == selected_before
    # Bias may or may not reorder a single reconstruction; audits stay frozen.
    assert applied in {True, False}

