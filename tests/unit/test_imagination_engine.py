"""Unit tests for ImaginationEngine subjective candidate generation."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.imagination import POLICY_VERSION, ImaginationEngine
from agents.cognition.models import (
    ActionDirection,
    CognitiveLoopInput,
    InternalAgentState,
    RetrievedMemoryContext,
    SelfModel,
    SituationClaimCode,
    SituationModel,
    SubjectiveSnapshot,
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
from memory.models import (
    BeliefId,
    ConceptMention,
    MemoryId,
    MemorySituationContext,
    MentionId,
    ReconstructedMemory,
    ReconstructionId,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    CoarseHealth,
    Observation,
    ObservedResource,
    ObservedSelf,
    VisibleBody,
    VisibleExit,
)
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    ResourceKind,
    TemperatureCelsius,
    Thirst,
)


def _self(
    *,
    hunger: float = 0.0,
    thirst: float = 0.0,
    fatigue: float = 0.0,
    health: float = 100.0,
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
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _observation(**kwargs: object) -> Observation:
    defaults: dict[str, object] = {
        "world_id": WorldId("world-1"),
        "observer_id": EntityId("body-1"),
        "revision": WorldRevision(0),
        "tick": 3,
        "self_body": _self(),
    }
    defaults.update(kwargs)
    return Observation(**defaults)  # type: ignore[arg-type]


def _loop_input(
    observation: Observation | None = None,
    *,
    snapshot: SubjectiveSnapshot | None = None,
) -> CognitiveLoopInput:
    agent = AgentId("agent-1")
    return CognitiveLoopInput(
        agent_id=agent,
        observation=observation or _observation(),
        internal_state=InternalAgentState(owner_id=agent),
        snapshot=snapshot,
    )


def _situation(*claims: SituationClaimCode) -> SituationModel:
    return SituationModel(
        owner_id=AgentId("agent-1"),
        tick=3,
        claim_codes=claims or (SituationClaimCode.LOCAL_SCENE,),
        confidence=1.0,
    )


def _self_model() -> SelfModel:
    return SelfModel(
        owner_id=AgentId("agent-1"),
        policy_id="self-model-projection",
        policy_version="1",
        life_status=LifeStatus.ALIVE,
        beliefs=(),
        goal_ids=(),
        confidence=1.0,
        candidate_count=0,
    )


def _belief(
    *,
    predicate: str,
    confidence: float,
    activation: BeliefActivationState = BeliefActivationState.ACTIVE,
    owner: str = "agent-1",
    belief_id: str = "belief-1",
    bool_value: bool = True,
) -> SemanticBelief:
    return SemanticBelief(
        belief_id=BeliefId(belief_id),
        owner_id=AgentId(owner),
        claim=SemanticClaim(
            subject=ClaimSubject(
                kind=ClaimSubjectKind.ENTITY, entity_id=EntityId("place-1")
            ),
            predicate=predicate,
            value=ClaimValue(kind=BeliefValueKind.BOOL, bool_value=bool_value),
        ),
        confidence=BeliefConfidenceState(
            confidence=confidence, support_mass=confidence, contradiction_mass=0.0
        ),
        activation_state=activation,
        current_revision_id=BeliefRevisionId("rev-1"),
        revision_ordinal=1,
        created_tick=1,
        updated_tick=2,
        policy=BeliefPolicyRef(policy_id="semantic-v1", version="1"),
        evidence_support_count=1,
        evidence_contradiction_count=0,
    )


def _reconstruction(
    *, concepts: tuple[str, ...], confidence: float = 0.8
) -> ReconstructedMemory:
    return ReconstructedMemory(
        reconstruction_id=ReconstructionId("recon-1"),
        owner_id=AgentId("agent-1"),
        narrative="subjective-episode",
        concepts=tuple(
            ConceptMention(mention_id=MentionId(f"c-{index}"), concept=concept)
            for index, concept in enumerate(concepts)
        ),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        confidence=confidence,
        emotional_salience=0.7,
        source_memory_ids=(MemoryId("mem-1"),),
        generation=1,
        reconstructed_at_tick=2,
        policy_id="recall",
        policy_version="1",
        used_provider=False,
        fallback_used=False,
    )


@pytest.mark.asyncio
async def test_imagination_generates_bounded_affordance_candidates() -> None:
    observation = _observation(
        resources=(
            ObservedResource(
                entity_id=EntityId("water-1"),
                name="spring",
                kind=ResourceKind.WATER,
                quantity=5.0,
                unit="L",
            ),
        ),
        exits=(VisibleExit(destination_id=EntityId("loc-2"), name="path"),),
        visible_bodies=(
            VisibleBody(
                entity_id=EntityId("body-2"),
                life_status=LifeStatus.ALIVE,
                coarse_health=CoarseHealth.STABLE,
            ),
        ),
        self_body=_self(fatigue=40.0),
    )
    memory = RetrievedMemoryContext(
        owner_id=AgentId("agent-1"),
        memory_ids=(),
        belief_ids=(),
        confidence=1.0,
    )
    result = await ImaginationEngine().imagine(
        _loop_input(observation),
        _situation(
            SituationClaimCode.LOCAL_SCENE,
            SituationClaimCode.RESOURCE_PRESENT,
            SituationClaimCode.THREAT_SIGNAL,
        ),
        _self_model(),
        memory,
    )
    directions = {future.direction for future in result.futures}
    assert ActionDirection.WAIT in directions
    assert ActionDirection.DRINK in directions
    assert ActionDirection.MOVE in directions
    assert ActionDirection.FLEE in directions
    assert ActionDirection.SLEEP in directions
    assert len(result.futures) <= 16
    assert len({future.future_id for future in result.futures}) == len(result.futures)


@pytest.mark.asyncio
async def test_danger_belief_changes_subjective_probs() -> None:
    observation = _observation(
        visible_bodies=(
            VisibleBody(
                entity_id=EntityId("body-2"),
                life_status=LifeStatus.ALIVE,
                coarse_health=CoarseHealth.INJURED,
            ),
        )
    )
    safe_belief = _belief(predicate="is_safe", confidence=0.9, belief_id="belief-safe")
    danger_belief = _belief(
        predicate="is_dangerous", confidence=0.9, belief_id="belief-danger"
    )
    engine = ImaginationEngine()
    situation = _situation(
        SituationClaimCode.LOCAL_SCENE, SituationClaimCode.THREAT_SIGNAL
    )
    safe = await engine.imagine(
        _loop_input(observation),
        situation,
        _self_model(),
        RetrievedMemoryContext(
            owner_id=AgentId("agent-1"),
            memory_ids=(),
            belief_ids=(safe_belief.belief_id,),
            confidence=1.0,
            semantic_beliefs=(safe_belief,),
        ),
    )
    danger = await engine.imagine(
        _loop_input(observation),
        situation,
        _self_model(),
        RetrievedMemoryContext(
            owner_id=AgentId("agent-1"),
            memory_ids=(),
            belief_ids=(danger_belief.belief_id,),
            confidence=1.0,
            semantic_beliefs=(danger_belief,),
        ),
    )
    safe_wait = next(f for f in safe.futures if f.direction is ActionDirection.WAIT)
    danger_wait = next(f for f in danger.futures if f.direction is ActionDirection.WAIT)
    assert danger_wait.subjective_probability != safe_wait.subjective_probability
    assert danger_wait.confidence != safe_wait.confidence
    # Belief confidence is not copied as outcome probability.
    assert danger_wait.subjective_probability != 0.9
    assert danger_belief.belief_id.value in danger_wait.source_refs.belief_ids


@pytest.mark.asyncio
async def test_reconstructed_danger_memory_raises_risk_vs_safety_memory() -> None:
    observation = _observation()
    danger_mem = _reconstruction(concepts=("danger", "threat"))
    safety_mem = _reconstruction(concepts=("safety", "shelter"))
    engine = ImaginationEngine()
    situation = _situation(SituationClaimCode.LOCAL_SCENE)
    danger = await engine.imagine(
        _loop_input(observation),
        situation,
        _self_model(),
        RetrievedMemoryContext(
            owner_id=AgentId("agent-1"),
            memory_ids=(MemoryId("mem-1"),),
            belief_ids=(),
            confidence=1.0,
            reconstructions=(danger_mem,),
        ),
    )
    safety = await engine.imagine(
        _loop_input(observation),
        situation,
        _self_model(),
        RetrievedMemoryContext(
            owner_id=AgentId("agent-1"),
            memory_ids=(MemoryId("mem-1"),),
            belief_ids=(),
            confidence=1.0,
            reconstructions=(safety_mem,),
        ),
    )
    danger_wait = next(f for f in danger.futures if f.direction is ActionDirection.WAIT)
    safety_wait = next(f for f in safety.futures if f.direction is ActionDirection.WAIT)
    danger_harm = sum(
        r.likelihood for r in danger_wait.risks if r.kind.value == "physical_harm"
    )
    safety_harm = sum(
        r.likelihood for r in safety_wait.risks if r.kind.value == "physical_harm"
    )
    assert danger_harm > safety_harm


@pytest.mark.asyncio
async def test_inactive_and_low_confidence_beliefs_ignored() -> None:
    observation = _observation()
    inactive = _belief(
        predicate="is_dangerous",
        confidence=0.9,
        activation=BeliefActivationState.RETIRED,
        belief_id="belief-inactive",
    )
    low = _belief(
        predicate="is_dangerous",
        confidence=0.05,
        belief_id="belief-low",
    )
    result = await ImaginationEngine().imagine(
        _loop_input(observation),
        _situation(SituationClaimCode.LOCAL_SCENE),
        _self_model(),
        RetrievedMemoryContext(
            owner_id=AgentId("agent-1"),
            memory_ids=(),
            belief_ids=(),
            confidence=1.0,
            semantic_beliefs=(inactive, low),
        ),
    )
    wait = next(f for f in result.futures if f.direction is ActionDirection.WAIT)
    assert wait.source_refs.belief_ids == ()


@pytest.mark.asyncio
async def test_terminal_situation_returns_wait_fallback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.imagination")
    result = await ImaginationEngine().imagine(
        _loop_input(),
        _situation(SituationClaimCode.TERMINAL_SELF),
        _self_model(),
        RetrievedMemoryContext(
            owner_id=AgentId("agent-1"),
            memory_ids=(),
            belief_ids=(),
            confidence=1.0,
        ),
    )
    assert len(result.futures) == 1
    assert result.futures[0].direction is ActionDirection.WAIT
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "imagination_complete" in messages
    assert POLICY_VERSION in str(caplog.records[-1].__dict__)
    assert "is_dangerous" not in messages
    assert "subjective-episode" not in messages


@pytest.mark.asyncio
async def test_imagination_is_deterministic() -> None:
    observation = _observation(
        exits=(VisibleExit(destination_id=EntityId("loc-2"), name="path"),)
    )
    memory = RetrievedMemoryContext(
        owner_id=AgentId("agent-1"),
        memory_ids=(),
        belief_ids=(),
        confidence=1.0,
        semantic_beliefs=(
            _belief(predicate="is_dangerous", confidence=0.7, belief_id="belief-1"),
        ),
    )
    engine = ImaginationEngine()
    first = await engine.imagine(
        _loop_input(observation),
        _situation(SituationClaimCode.LOCAL_SCENE),
        _self_model(),
        memory,
    )
    second = await engine.imagine(
        _loop_input(observation),
        _situation(SituationClaimCode.LOCAL_SCENE),
        _self_model(),
        memory,
    )
    assert [f.future_id for f in first.futures] == [f.future_id for f in second.futures]
    assert [f.direction for f in first.futures] == [f.direction for f in second.futures]
    assert [f.confidence for f in first.futures] == [
        f.confidence for f in second.futures
    ]
