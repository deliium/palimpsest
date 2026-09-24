"""Controlled divergence: identical objective situation, different prior emotion."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.configuration import (
    CognitionEmotionalStateMode,
    CognitionLoopConfig,
    build_cognitive_loop,
)
from agents.cognition.emotion_bias import apply_retrieval_emotion_bias
from agents.cognition.models import (
    AgentEmotionalState,
    CognitiveLoopInput,
    EmotionIntensity,
    EmotionKind,
    InternalAgentState,
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

_OWNER = AgentId("agent-1")


def _observation(*, tick: int = 0) -> Observation:
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=tick,
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


def _hit(
    memory_id: str,
    *,
    salience: float,
    tags: tuple[str, ...],
    score: float,
) -> MemoryRankedHit:
    trace = MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=_OWNER,
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


def _prior(kind: EmotionKind, intensity: float) -> AgentEmotionalState:
    return AgentEmotionalState(
        owner_id=_OWNER,
        tick=1,
        intensities=(EmotionIntensity(kind=kind, intensity=intensity),),
        last_update_tick=1,
        policy_version="emotion.v1",
    )


def test_identical_hits_diverge_under_fear_prior() -> None:
    social = _hit("m-social", salience=0.1, tags=("social_signal",), score=0.7)
    threat = _hit("m-threat", salience=0.9, tags=("threat_signal",), score=0.45)
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
    hits = (social, threat)
    fear = _prior(EmotionKind.FEAR, 0.8)
    attachment = _prior(EmotionKind.ATTACHMENT, 0.8)

    fear_ranked, fear_applied = apply_retrieval_emotion_bias(hits, fear, enabled=True)
    attach_ranked, attach_applied = apply_retrieval_emotion_bias(
        hits, attachment, enabled=True
    )
    off_a, off_applied_a = apply_retrieval_emotion_bias(hits, fear, enabled=False)
    off_b, off_applied_b = apply_retrieval_emotion_bias(hits, attachment, enabled=False)

    assert fear_applied and attach_applied
    assert fear_ranked[0].trace.memory_id.value == "m-threat"
    assert attach_ranked[0].trace.memory_id.value == "m-social"
    assert off_applied_a is False and off_applied_b is False
    assert off_a[0].trace.memory_id == off_b[0].trace.memory_id


@pytest.mark.asyncio
async def test_passthrough_mode_collapses_priors_to_identical_commands(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """PASSTHROUGH ignores prior emotion for bias; commands stay identical."""
    caplog.set_level(logging.DEBUG)

    async def _run(prior: AgentEmotionalState | None) -> object:
        config = CognitionLoopConfig(
            emotional_state_mode=CognitionEmotionalStateMode.PASSTHROUGH
        )
        loop = build_cognitive_loop(config)
        snapshot = SubjectiveSnapshot(
            owner_id=_OWNER,
            revision=0,
            memories=(),
            legacy_beliefs=(),
            semantic_beliefs=(),
            emotional_state=prior,
        )
        loop_input = CognitiveLoopInput(
            agent_id=_OWNER,
            observation=_observation(tick=2),
            internal_state=InternalAgentState(owner_id=_OWNER),
            snapshot=snapshot,
        )
        result = await loop.run(loop_input, invocation_id="inv-1")
        return type(result.command).__name__

    fear = _prior(EmotionKind.FEAR, 0.9)
    attach = _prior(EmotionKind.ATTACHMENT, 0.9)
    empty = empty_emotional_state(_OWNER, tick=1)
    assert await _run(fear) == await _run(attach)
    assert await _run(attach) == await _run(empty)
    # PASSTHROUGH must not emit retrieval emotion-bias apply logs as true.
    for record in caplog.records:
        if record.name == "agents.cognition.emotion_bias":
            extra = getattr(record, "cognition", None)
            if isinstance(extra, dict) and "bias_applied" in extra:
                assert extra["bias_applied"] is False
