"""Unit tests for deterministic ``emotion.v1`` EmotionalStateEngine."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.emotion import (
    EMOTION_POLICY_VERSION,
    EmotionalStateEngine,
    PassthroughEmotionalStateAppraiser,
)
from agents.cognition.models import (
    DEFAULT_EMOTION_KINDS,
    AgentEmotionalState,
    CognitiveLoopInput,
    EmotionDriverCode,
    EmotionIntensity,
    EmotionKind,
    EmotionRegulationPolicy,
    GoalBoard,
    GoalTransitionIntent,
    GoalTransitionIntentReason,
    InternalAgentState,
    InterpretedPerception,
    PerceptionClaimCode,
    RetrievedMemoryContext,
    SelfModel,
    SituationClaimCode,
    SituationModel,
    SubjectiveSnapshot,
    default_emotion_regulation_policy,
    empty_emotional_state,
)
from agents.models import AgentId, GoalId, GoalStatus
from memory.models import (
    MemoryId,
    MemoryProvenance,
    MemoryRankedHit,
    MemoryScoreBreakdown,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    quantize_score,
)
from social.models import CommunicationEnvelope, EnvelopeId
from social.relationships import RelationshipDimension
from tests.cognition_helpers import build_relationship
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
_TICK = 5


def _self_body(
    *,
    hunger: float = 0.0,
    thirst: float = 0.0,
    fatigue: float = 0.0,
    health: float = 100.0,
    life_status: LifeStatus = LifeStatus.ALIVE,
) -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        health=Health(health),
        hunger=Hunger(hunger),
        thirst=Thirst(thirst),
        fatigue=Fatigue(fatigue),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=life_status,
        carry_capacity=CarryCapacity(10),
    )


def _observation(
    *,
    tick: int = _TICK,
    self_body: ObservedSelf | None = None,
) -> Observation:
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=tick,
        self_body=self_body,
    )


def _perception(*, tick: int = _TICK) -> InterpretedPerception:
    return InterpretedPerception(
        owner_id=_OWNER,
        observer_id=EntityId("body-1"),
        tick=tick,
        revision=WorldRevision(0),
        life_status=LifeStatus.ALIVE,
        location_id=EntityId("loc-1"),
        claim_codes=(
            PerceptionClaimCode.SELF_ALIVE,
            PerceptionClaimCode.HAS_LOCATION,
        ),
        counts={},
        confidence=1.0,
    )


def _situation(*claims: SituationClaimCode, tick: int = _TICK) -> SituationModel:
    return SituationModel(
        owner_id=_OWNER,
        tick=tick,
        claim_codes=claims or (SituationClaimCode.LOCAL_SCENE,),
        confidence=1.0,
    )


def _memory() -> RetrievedMemoryContext:
    return RetrievedMemoryContext(
        owner_id=_OWNER,
        memory_ids=(),
        belief_ids=(),
        confidence=1.0,
    )


def _self_model() -> SelfModel:
    return SelfModel(
        owner_id=_OWNER,
        policy_id="self-model-projection",
        policy_version="1",
        life_status=LifeStatus.ALIVE,
        beliefs=(),
        goal_ids=(),
        confidence=1.0,
        candidate_count=0,
    )


def _board(
    *,
    tick: int = _TICK,
    intents: tuple[GoalTransitionIntent, ...] = (),
) -> GoalBoard:
    return GoalBoard(
        owner_id=_OWNER,
        tick=tick,
        goals=(),
        foci_ids=(),
        transition_intents=intents,
        confidence=1.0,
        policy_version="goals.v1",
    )


def _snapshot(
    *,
    relationships: tuple[object, ...] = (),
    inbox: tuple[CommunicationEnvelope, ...] = (),
) -> SubjectiveSnapshot:
    return SubjectiveSnapshot(
        owner_id=_OWNER,
        revision=0,
        memories=(),
        legacy_beliefs=(),
        semantic_beliefs=(),
        relationships=relationships,
        inbox=inbox,
    )


def _loop_input(
    *,
    tick: int = _TICK,
    self_body: ObservedSelf | None = None,
    snapshot: SubjectiveSnapshot | None = None,
) -> CognitiveLoopInput:
    return CognitiveLoopInput(
        agent_id=_OWNER,
        observation=_observation(tick=tick, self_body=self_body),
        internal_state=InternalAgentState(owner_id=_OWNER),
        snapshot=snapshot,
    )


def _salient_memory(*, salience: float = 0.8) -> RetrievedMemoryContext:
    trace = MemoryTrace(
        memory_id=MemoryId("m-salient"),
        owner_id=_OWNER,
        world_revision=WorldRevision(0),
        concepts=(),
        entities=(),
        relations=(),
        context=MemorySituationContext(tags=("threat_signal",)),
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
    hit = MemoryRankedHit(
        rank=1,
        trace=trace,
        score=0.5,
        breakdown=MemoryScoreBreakdown(),
        matched_concept_mention_ids=(),
        matched_entity_mention_ids=(),
        scoring_policy_id="test",
        scoring_policy_version="1",
        retrieval_tick=0,
    )
    return RetrievedMemoryContext(
        owner_id=_OWNER,
        memory_ids=(trace.memory_id,),
        belief_ids=(),
        confidence=1.0,
        ranked_hits=(hit,),
    )


def _policy(
    *,
    enabled_kinds: tuple[EmotionKind, ...] | None = None,
    gain_caps: dict[EmotionKind, float] | None = None,
    ceilings: dict[EmotionKind, float] | None = None,
) -> EmotionRegulationPolicy:
    base = default_emotion_regulation_policy(enabled_kinds=enabled_kinds)
    kinds = base.enabled_kinds
    return EmotionRegulationPolicy(
        policy_version=EMOTION_POLICY_VERSION,
        enabled_kinds=kinds,
        decay_rates=dict(base.decay_rates),
        gain_caps=gain_caps
        if gain_caps is not None
        else {kind: base.gain_caps[kind] for kind in kinds},
        floors={kind: base.floors[kind] for kind in kinds},
        ceilings=ceilings
        if ceilings is not None
        else {kind: base.ceilings[kind] for kind in kinds},
        baselines={kind: base.baselines[kind] for kind in kinds},
    )


@pytest.mark.asyncio
async def test_threat_raises_fear_and_anxiety() -> None:
    engine = EmotionalStateEngine()
    evaluation = await engine.appraise(
        _loop_input(),
        _perception(),
        _situation(SituationClaimCode.THREAT_SIGNAL),
        _memory(),
        _self_model(),
        _board(),
    )
    assert EmotionDriverCode.THREAT in evaluation.driver_codes
    assert evaluation.state.get(EmotionKind.FEAR) >= quantize_score(0.35)
    assert evaluation.state.get(EmotionKind.ANXIETY) >= quantize_score(0.25)
    assert "afraid" not in repr(evaluation).lower()


@pytest.mark.asyncio
async def test_goal_failure_intents_raise_sadness_and_anger() -> None:
    engine = EmotionalStateEngine()
    intent = GoalTransitionIntent(
        goal_id=GoalId("goal-1"),
        owner_id=_OWNER,
        from_status=GoalStatus.ACTIVE,
        to_status=GoalStatus.FAILED,
        reason_code=GoalTransitionIntentReason.FAILED,
        tick=_TICK,
    )
    evaluation = await engine.appraise(
        _loop_input(),
        _perception(),
        _situation(),
        _memory(),
        _self_model(),
        _board(intents=(intent,)),
    )
    assert EmotionDriverCode.GOAL_FAILURE in evaluation.driver_codes
    assert evaluation.state.get(EmotionKind.SADNESS) >= quantize_score(0.30)
    assert evaluation.state.get(EmotionKind.ANGER) >= quantize_score(0.20)


@pytest.mark.asyncio
async def test_goal_progress_raises_relief_and_confidence() -> None:
    engine = EmotionalStateEngine()
    intent = GoalTransitionIntent(
        goal_id=GoalId("goal-1"),
        owner_id=_OWNER,
        from_status=GoalStatus.ACTIVE,
        to_status=GoalStatus.ACTIVE,
        reason_code=GoalTransitionIntentReason.PROGRESS_UPDATED,
        tick=_TICK,
    )
    evaluation = await engine.appraise(
        _loop_input(),
        _perception(),
        _situation(),
        _memory(),
        _self_model(),
        _board(intents=(intent,)),
    )
    assert EmotionDriverCode.GOAL_PROGRESS in evaluation.driver_codes
    assert evaluation.state.get(EmotionKind.RELIEF) >= quantize_score(0.20)
    assert evaluation.state.get(EmotionKind.CONFIDENCE) >= quantize_score(0.25)


@pytest.mark.asyncio
async def test_decay_toward_baseline_over_ticks() -> None:
    engine = EmotionalStateEngine()
    prior = AgentEmotionalState(
        owner_id=_OWNER,
        tick=1,
        intensities=(EmotionIntensity(kind=EmotionKind.FEAR, intensity=0.8),),
        last_update_tick=1,
        policy_version=EMOTION_POLICY_VERSION,
    )
    evaluation = await engine.appraise(
        _loop_input(tick=4),
        _perception(tick=4),
        _situation(tick=4),
        _memory(),
        _self_model(),
        _board(tick=4),
        prior_state=prior,
    )
    assert EmotionDriverCode.DECAY in evaluation.driver_codes
    assert evaluation.state.get(EmotionKind.FEAR) < 0.8
    assert evaluation.state.get(EmotionKind.FEAR) > 0.0


@pytest.mark.asyncio
async def test_identical_inputs_are_deterministic() -> None:
    engine = EmotionalStateEngine()
    kwargs = dict(
        loop_input=_loop_input(),
        perception=_perception(),
        situation=_situation(SituationClaimCode.THREAT_SIGNAL),
        memory=_memory(),
        self_state=_self_model(),
        goal_board=_board(),
    )
    a = await engine.appraise(**kwargs)
    b = await engine.appraise(**kwargs)
    assert a == b


@pytest.mark.asyncio
async def test_passthrough_emits_prior_without_driver_deltas() -> None:
    appraiser = PassthroughEmotionalStateAppraiser()
    prior = AgentEmotionalState(
        owner_id=_OWNER,
        tick=1,
        intensities=(EmotionIntensity(kind=EmotionKind.FEAR, intensity=0.5),),
        last_update_tick=1,
        policy_version=EMOTION_POLICY_VERSION,
    )
    evaluation = await appraiser.appraise(
        _loop_input(),
        _perception(),
        _situation(SituationClaimCode.THREAT_SIGNAL),
        _memory(),
        _self_model(),
        _board(),
        prior_state=prior,
    )
    assert evaluation.driver_codes == (EmotionDriverCode.PASSTHROUGH,)
    assert evaluation.state.get(EmotionKind.FEAR) == 0.5


@pytest.mark.asyncio
async def test_ownership_fail_closed() -> None:
    engine = EmotionalStateEngine()
    with pytest.raises(ValueError, match="ownership"):
        await engine.appraise(
            _loop_input(),
            _perception(),
            _situation(),
            _memory(),
            _self_model(),
            _board(),
            prior_state=empty_emotional_state(AgentId("other"), tick=0),
        )


@pytest.mark.asyncio
async def test_relationship_fear_distinct_from_emotion_kind(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """RelationshipDimension.FEAR feeds emotion fear without type conflation."""
    assert EmotionKind.FEAR is not RelationshipDimension.FEAR
    engine = EmotionalStateEngine()
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.emotion"):
        evaluation = await engine.appraise(
            _loop_input(),
            _perception(),
            _situation(SituationClaimCode.THREAT_SIGNAL),
            _memory(),
            _self_model(),
            _board(),
        )
    assert EmotionKind.FEAR in {e.kind for e in evaluation.state.intensities}
    for record in caplog.records:
        extra = getattr(record, "cognition", None)
        if isinstance(extra, dict):
            assert "afraid" not in str(extra).lower()
            assert set(extra).issubset(
                {
                    "policy_version",
                    "owner_id",
                    "tick",
                    "mode",
                    "active_kind_count",
                    "max_intensity_band",
                    "driver_code_counts",
                    "decay_applied",
                    "status",
                    "reason_code",
                    "kind",
                }
            )


@pytest.mark.asyncio
async def test_observation_communications_raise_attachment() -> None:
    engine = EmotionalStateEngine()
    perception = InterpretedPerception(
        owner_id=_OWNER,
        observer_id=EntityId("body-1"),
        tick=_TICK,
        revision=WorldRevision(0),
        life_status=LifeStatus.ALIVE,
        location_id=EntityId("loc-1"),
        claim_codes=(
            PerceptionClaimCode.SELF_ALIVE,
            PerceptionClaimCode.HAS_LOCATION,
            PerceptionClaimCode.HAS_COMMUNICATIONS,
        ),
        counts={},
        confidence=1.0,
    )
    evaluation = await engine.appraise(
        _loop_input(),
        perception,
        _situation(),
        _memory(),
        _self_model(),
        _board(),
    )
    assert EmotionDriverCode.OBSERVATION in evaluation.driver_codes
    assert evaluation.state.get(EmotionKind.ATTACHMENT) >= quantize_score(0.10)


@pytest.mark.asyncio
async def test_memory_salience_raises_anxiety_and_fear() -> None:
    engine = EmotionalStateEngine()
    evaluation = await engine.appraise(
        _loop_input(),
        _perception(),
        _situation(),
        _salient_memory(salience=0.8),
        _self_model(),
        _board(),
    )
    assert EmotionDriverCode.MEMORY_SALIENCE in evaluation.driver_codes
    assert evaluation.state.get(EmotionKind.ANXIETY) > 0.0
    assert evaluation.state.get(EmotionKind.FEAR) > 0.0


@pytest.mark.asyncio
async def test_social_signal_raises_attachment() -> None:
    engine = EmotionalStateEngine()
    evaluation = await engine.appraise(
        _loop_input(),
        _perception(),
        _situation(SituationClaimCode.SOCIAL_SIGNAL),
        _memory(),
        _self_model(),
        _board(),
    )
    assert EmotionDriverCode.SOCIAL_INTERACTION in evaluation.driver_codes
    assert evaluation.state.get(EmotionKind.ATTACHMENT) >= quantize_score(0.15)


@pytest.mark.asyncio
async def test_inbox_social_interaction_raises_attachment() -> None:
    engine = EmotionalStateEngine()
    inbox = (
        CommunicationEnvelope(
            envelope_id=EnvelopeId("env-1"),
            sender_id=AgentId("agent-2"),
            recipient_id=_OWNER,
            payload={"text": "hello"},
        ),
    )
    evaluation = await engine.appraise(
        _loop_input(snapshot=_snapshot(inbox=inbox)),
        _perception(),
        _situation(),
        _memory(),
        _self_model(),
        _board(),
    )
    assert EmotionDriverCode.SOCIAL_INTERACTION in evaluation.driver_codes
    assert evaluation.state.get(EmotionKind.ATTACHMENT) > 0.0


@pytest.mark.asyncio
async def test_relationship_dimension_fear_drives_emotion_fear() -> None:
    assert EmotionKind.FEAR is not RelationshipDimension.FEAR
    engine = EmotionalStateEngine()
    profile = build_relationship(source="agent-1", target="agent-2", fear=0.8)
    evaluation = await engine.appraise(
        _loop_input(snapshot=_snapshot(relationships=(profile,))),
        _perception(),
        _situation(),
        _memory(),
        _self_model(),
        _board(),
    )
    assert EmotionDriverCode.RELATIONSHIP in evaluation.driver_codes
    assert evaluation.state.get(EmotionKind.FEAR) > 0.0
    assert evaluation.state.get(EmotionKind.ANXIETY) > 0.0


@pytest.mark.asyncio
async def test_relationship_affection_drives_attachment() -> None:
    engine = EmotionalStateEngine()
    profile = build_relationship(source="agent-1", target="agent-2", affection=0.9)
    evaluation = await engine.appraise(
        _loop_input(snapshot=_snapshot(relationships=(profile,))),
        _perception(),
        _situation(),
        _memory(),
        _self_model(),
        _board(),
    )
    assert EmotionDriverCode.RELATIONSHIP in evaluation.driver_codes
    assert evaluation.state.get(EmotionKind.ATTACHMENT) > 0.0


@pytest.mark.asyncio
async def test_physical_distress_raises_anxiety_and_fear() -> None:
    engine = EmotionalStateEngine()
    evaluation = await engine.appraise(
        _loop_input(self_body=_self_body(hunger=90.0, health=40.0)),
        _perception(),
        _situation(),
        _memory(),
        _self_model(),
        _board(),
    )
    assert EmotionDriverCode.PHYSICAL_CONDITION in evaluation.driver_codes
    assert evaluation.state.get(EmotionKind.ANXIETY) > 0.0
    assert evaluation.state.get(EmotionKind.FEAR) > 0.0


@pytest.mark.asyncio
async def test_gain_cap_clamps_driver_delta() -> None:
    policy = _policy(gain_caps={kind: 0.05 for kind in DEFAULT_EMOTION_KINDS})
    engine = EmotionalStateEngine(policy=policy)
    evaluation = await engine.appraise(
        _loop_input(),
        _perception(),
        _situation(SituationClaimCode.THREAT_SIGNAL),
        _memory(),
        _self_model(),
        _board(),
    )
    assert EmotionDriverCode.THREAT in evaluation.driver_codes
    assert evaluation.state.get(EmotionKind.FEAR) == quantize_score(0.05)
    assert evaluation.state.get(EmotionKind.ANXIETY) == quantize_score(0.05)


@pytest.mark.asyncio
async def test_ceiling_clamps_final_intensity() -> None:
    kinds = tuple(DEFAULT_EMOTION_KINDS)
    policy = _policy(
        ceilings={kind: 0.12 for kind in kinds},
        gain_caps={kind: 0.12 for kind in kinds},
    )
    engine = EmotionalStateEngine(policy=policy)
    prior = AgentEmotionalState(
        owner_id=_OWNER,
        tick=_TICK,
        intensities=(EmotionIntensity(kind=EmotionKind.FEAR, intensity=0.10),),
        last_update_tick=_TICK,
        policy_version=EMOTION_POLICY_VERSION,
    )
    evaluation = await engine.appraise(
        _loop_input(),
        _perception(),
        _situation(SituationClaimCode.THREAT_SIGNAL),
        _memory(),
        _self_model(),
        _board(),
        prior_state=prior,
    )
    assert evaluation.state.get(EmotionKind.FEAR) == quantize_score(0.12)


@pytest.mark.asyncio
async def test_disabled_kind_rejected_from_prior(
    caplog: pytest.LogCaptureFixture,
) -> None:
    enabled = tuple(k for k in DEFAULT_EMOTION_KINDS if k is not EmotionKind.FEAR)
    policy = _policy(enabled_kinds=enabled)
    engine = EmotionalStateEngine(policy=policy)
    prior = AgentEmotionalState(
        owner_id=_OWNER,
        tick=1,
        intensities=(EmotionIntensity(kind=EmotionKind.FEAR, intensity=0.9),),
        last_update_tick=1,
        policy_version=EMOTION_POLICY_VERSION,
    )
    with caplog.at_level(logging.WARNING, logger="agents.cognition.emotion"):
        evaluation = await engine.appraise(
            _loop_input(),
            _perception(),
            _situation(SituationClaimCode.THREAT_SIGNAL),
            _memory(),
            _self_model(),
            _board(),
            prior_state=prior,
        )
    assert EmotionKind.FEAR not in {e.kind for e in evaluation.state.intensities}
    assert any(
        record.message == "emotional_state_disabled_kind_rejected"
        for record in caplog.records
    )


@pytest.mark.parametrize(
    ("driver", "kwargs", "kind", "min_intensity"),
    [
        (
            EmotionDriverCode.THREAT,
            {"situation": lambda: _situation(SituationClaimCode.THREAT_SIGNAL)},
            EmotionKind.FEAR,
            0.35,
        ),
        (
            EmotionDriverCode.OBSERVATION,
            {
                "perception": lambda: InterpretedPerception(
                    owner_id=_OWNER,
                    observer_id=EntityId("body-1"),
                    tick=_TICK,
                    revision=WorldRevision(0),
                    life_status=LifeStatus.ALIVE,
                    location_id=EntityId("loc-1"),
                    claim_codes=(
                        PerceptionClaimCode.SELF_ALIVE,
                        PerceptionClaimCode.HAS_COMMUNICATIONS,
                    ),
                    counts={},
                    confidence=1.0,
                )
            },
            EmotionKind.ATTACHMENT,
            0.10,
        ),
        (
            EmotionDriverCode.MEMORY_SALIENCE,
            {"memory": lambda: _salient_memory(salience=1.0)},
            EmotionKind.ANXIETY,
            0.20,
        ),
        (
            EmotionDriverCode.SOCIAL_INTERACTION,
            {"situation": lambda: _situation(SituationClaimCode.SOCIAL_SIGNAL)},
            EmotionKind.ATTACHMENT,
            0.15,
        ),
        (
            EmotionDriverCode.RELATIONSHIP,
            {
                "loop_input": lambda: _loop_input(
                    snapshot=_snapshot(
                        relationships=(
                            build_relationship(
                                source="agent-1", target="agent-2", fear=1.0
                            ),
                        )
                    )
                )
            },
            EmotionKind.FEAR,
            0.25,
        ),
        (
            EmotionDriverCode.PHYSICAL_CONDITION,
            {"loop_input": lambda: _loop_input(self_body=_self_body(hunger=100.0))},
            EmotionKind.ANXIETY,
            0.20,
        ),
        (
            EmotionDriverCode.GOAL_FAILURE,
            {
                "goal_board": lambda: _board(
                    intents=(
                        GoalTransitionIntent(
                            goal_id=GoalId("goal-1"),
                            owner_id=_OWNER,
                            from_status=GoalStatus.ACTIVE,
                            to_status=GoalStatus.FAILED,
                            reason_code=GoalTransitionIntentReason.FAILED,
                            tick=_TICK,
                        ),
                    )
                )
            },
            EmotionKind.SADNESS,
            0.30,
        ),
        (
            EmotionDriverCode.GOAL_PROGRESS,
            {
                "goal_board": lambda: _board(
                    intents=(
                        GoalTransitionIntent(
                            goal_id=GoalId("goal-1"),
                            owner_id=_OWNER,
                            from_status=GoalStatus.ACTIVE,
                            to_status=GoalStatus.ACTIVE,
                            reason_code=GoalTransitionIntentReason.PROGRESS_UPDATED,
                            tick=_TICK,
                        ),
                    )
                )
            },
            EmotionKind.CONFIDENCE,
            0.25,
        ),
    ],
)
@pytest.mark.asyncio
async def test_driver_table_directional_deltas(
    driver: EmotionDriverCode,
    kwargs: dict[str, object],
    kind: EmotionKind,
    min_intensity: float,
) -> None:
    engine = EmotionalStateEngine()
    call = {
        "loop_input": _loop_input(),
        "perception": _perception(),
        "situation": _situation(),
        "memory": _memory(),
        "self_state": _self_model(),
        "goal_board": _board(),
    }
    for key, factory in kwargs.items():
        call[key] = factory()  # type: ignore[operator]
    evaluation = await engine.appraise(**call)  # type: ignore[arg-type]
    assert driver in evaluation.driver_codes
    assert evaluation.state.get(kind) >= quantize_score(min_intensity)


@pytest.mark.asyncio
async def test_regulation_code_when_no_drivers() -> None:
    engine = EmotionalStateEngine()
    evaluation = await engine.appraise(
        _loop_input(),
        _perception(),
        _situation(),
        _memory(),
        _self_model(),
        _board(),
    )
    assert evaluation.driver_codes == (EmotionDriverCode.REGULATION,)
    assert evaluation.state.max_intensity() == 0.0
