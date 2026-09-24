"""Shared deterministic builders for subjective cognition risk tests.

Factories only — helpers themselves carry no secrets, and ``repr`` of constructed
domain objects remains metadata-safe by production model contracts.
"""

from __future__ import annotations

from collections.abc import Sequence

from agents.cognition.contracts import MemoryRetriever
from agents.cognition.defaults import (
    DirectSelfStateProjector,
    DirectSituationModeler,
    EmptyMemoryUpdateHook,
    LiteralPerceptionInterpreter,
    PassthroughGoalManager,
)
from agents.cognition.deliberation import (
    CommandPlanner,
    MultiCriteriaIntentionSelector,
)
from agents.cognition.emotion import PassthroughEmotionalStateAppraiser
from agents.cognition.imagination import ImaginationEngine
from agents.cognition.loop import CognitiveLoop
from agents.cognition.models import (
    ActionPlan,
    CognitiveLoopInput,
    CounterpartBinding,
    InternalAgentState,
    InterpretedPerception,
    MotivationEvaluation,
    OwnerSafeSocialIdentity,
    PossibleFutures,
    RetrievedMemoryContext,
    SelectedIntention,
    SelfModel,
    SituationClaimCode,
    SituationModel,
    SubjectiveSnapshot,
)
from agents.cognition.motivation import MotivationAppraisal
from agents.models import (
    REQUIRED_DRIVE_KINDS,
    AgentId,
    DriveDisposition,
    DriveKind,
    DriveProfile,
    Goal,
    GoalId,
    GoalOutcome,
    GoalOutcomeKind,
    GoalProgress,
    GoalStatus,
    default_drive_profile,
)
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
from social.relationships import (
    DirectedRelationshipProfile,
    RelationshipActivationState,
    RelationshipConfidence,
    RelationshipDimension,
    RelationshipDimensionState,
    RelationshipId,
    RelationshipPolicyRef,
    RelationshipRevisionId,
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

__all__ = [
    "FixedMemoryRetriever",
    "build_belief",
    "build_drive_profile",
    "build_goal",
    "build_loop_input",
    "build_observation",
    "build_reconstruction",
    "build_relationship",
    "build_self_model",
    "build_situation",
    "build_snapshot",
    "empty_memory",
    "memory_context",
    "production_cognitive_loop",
    "run_deliberation",
    "subjective_self",
]


class FixedMemoryRetriever:
    """Deterministic MemoryRetriever returning fixed beliefs/reconstructions."""

    def __init__(
        self,
        *,
        beliefs: Sequence[SemanticBelief] = (),
        reconstructions: Sequence[ReconstructedMemory] = (),
    ) -> None:
        self._beliefs = tuple(beliefs)
        self._reconstructions = tuple(reconstructions)

    async def retrieve(
        self,
        loop_input: CognitiveLoopInput,
        perception: InterpretedPerception,
    ) -> RetrievedMemoryContext:
        _ = perception
        owner = loop_input.agent_id
        beliefs = tuple(b for b in self._beliefs if b.owner_id == owner)
        reconstructions = tuple(r for r in self._reconstructions if r.owner_id == owner)
        # Fall back to snapshot beliefs when none were injected.
        if not beliefs and loop_input.snapshot is not None:
            beliefs = loop_input.snapshot.semantic_beliefs
        return RetrievedMemoryContext(
            owner_id=owner,
            memory_ids=tuple(
                mid for recon in reconstructions for mid in recon.source_memory_ids
            ),
            belief_ids=tuple(item.belief_id for item in beliefs),
            confidence=1.0,
            reconstructions=reconstructions,
            semantic_beliefs=beliefs,
        )


def production_cognitive_loop(
    *,
    memory: MemoryRetriever | None = None,
) -> CognitiveLoop:
    """Build the production cognition stack with an optional memory override."""
    return CognitiveLoop(
        perception=LiteralPerceptionInterpreter(),
        memory=memory if memory is not None else FixedMemoryRetriever(),
        situation=DirectSituationModeler(),
        self_state=DirectSelfStateProjector(),
        goal_manager=PassthroughGoalManager(),
        emotional_state=PassthroughEmotionalStateAppraiser(),
        futures=ImaginationEngine(),
        motivation=MotivationAppraisal(),
        intention=MultiCriteriaIntentionSelector(),
        planner=CommandPlanner(),
        memory_updates=EmptyMemoryUpdateHook(),
    )


def subjective_self(
    *,
    entity_id: str = "body-1",
    location_id: str = "loc-1",
    hunger: float = 0.0,
    thirst: float = 0.0,
    fatigue: float = 0.0,
    health: float = 100.0,
) -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId(entity_id),
        location_id=EntityId(location_id),
        health=Health(health),
        hunger=Hunger(hunger),
        thirst=Thirst(thirst),
        fatigue=Fatigue(fatigue),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def build_observation(
    *,
    tick: int = 3,
    revision: int = 0,
    hunger: float = 0.0,
    thirst: float = 0.0,
    fatigue: float = 0.0,
    health: float = 100.0,
    with_water: bool = False,
    with_exit: bool = False,
    with_threat: bool = False,
    water_id: str = "water-1",
    exit_id: str = "loc-2",
    threat_id: str = "body-2",
) -> Observation:
    resources = ()
    if with_water:
        resources = (
            ObservedResource(
                entity_id=EntityId(water_id),
                name="spring",
                kind=ResourceKind.WATER,
                quantity=5.0,
                unit="L",
            ),
        )
    exits = ()
    if with_exit:
        exits = (VisibleExit(destination_id=EntityId(exit_id), name="path"),)
    bodies = ()
    if with_threat:
        bodies = (
            VisibleBody(
                entity_id=EntityId(threat_id),
                life_status=LifeStatus.ALIVE,
                coarse_health=CoarseHealth.INJURED,
            ),
        )
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(revision),
        tick=tick,
        self_body=subjective_self(
            hunger=hunger, thirst=thirst, fatigue=fatigue, health=health
        ),
        resources=resources,
        exits=exits,
        visible_bodies=bodies,
    )


def build_belief(
    *,
    predicate: str,
    confidence: float,
    belief_id: str = "belief-1",
    owner: str = "agent-1",
    bool_value: bool = True,
    activation: BeliefActivationState = BeliefActivationState.ACTIVE,
    subject_entity: str = "place-1",
) -> SemanticBelief:
    return SemanticBelief(
        belief_id=BeliefId(belief_id),
        owner_id=AgentId(owner),
        claim=SemanticClaim(
            subject=ClaimSubject(
                kind=ClaimSubjectKind.ENTITY, entity_id=EntityId(subject_entity)
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


def build_reconstruction(
    *,
    concepts: tuple[str, ...],
    confidence: float = 0.8,
    reconstruction_id: str = "recon-1",
    owner: str = "agent-1",
    narrative: str = "subjective-episode",
    memory_id: str = "mem-1",
    salience: float = 0.7,
) -> ReconstructedMemory:
    return ReconstructedMemory(
        reconstruction_id=ReconstructionId(reconstruction_id),
        owner_id=AgentId(owner),
        narrative=narrative,
        concepts=tuple(
            ConceptMention(mention_id=MentionId(f"c-{index}"), concept=concept)
            for index, concept in enumerate(concepts)
        ),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        confidence=confidence,
        emotional_salience=salience,
        source_memory_ids=(MemoryId(memory_id),),
        generation=1,
        reconstructed_at_tick=2,
        policy_id="recall",
        policy_version="1",
        used_provider=False,
        fallback_used=False,
    )


def build_goal(
    *,
    goal_id: str = "goal-1",
    owner: str = "agent-1",
    description: str = "secret-goal",
    priority: float = 0.8,
    status: GoalStatus = GoalStatus.ACTIVE,
    outcome: GoalOutcome | None = None,
    progress: float = 0.1,
) -> Goal:
    return Goal(
        goal_id=GoalId(goal_id),
        owner_id=AgentId(owner),
        description=description,
        priority=priority,
        status=status,
        outcome=outcome
        if outcome is not None
        else GoalOutcome(kind=GoalOutcomeKind.PRESERVE_LIFE),
        progress=GoalProgress(estimate=progress, confidence=0.9),
    )


def build_relationship(
    *,
    relationship_id: str = "rel-1",
    source: str = "agent-1",
    target: str = "agent-2",
    dependency: float = 0.0,
    affection: float = 0.0,
    fear: float = 0.0,
) -> DirectedRelationshipProfile:
    policy = RelationshipPolicyRef(policy_id="rel-v1", version="1")
    confidence = RelationshipConfidence(
        confidence=0.9, support_mass=0.9, contradiction_mass=0.0
    )
    dimensions: list[RelationshipDimensionState] = []
    for dimension, value in (
        (RelationshipDimension.DEPENDENCY, dependency),
        (RelationshipDimension.AFFECTION, affection),
        (RelationshipDimension.FEAR, fear),
    ):
        if value == 0.0 and dimension is not RelationshipDimension.DEPENDENCY:
            # Keep at least dependency for a valid non-empty profile when others unset.
            continue
        dimensions.append(
            RelationshipDimensionState(
                dimension=dimension,
                value=value,
                confidence=confidence,
                evidence=(),
                logical_tick=1,
                policy=policy,
            )
        )
    if not dimensions:
        dimensions.append(
            RelationshipDimensionState(
                dimension=RelationshipDimension.DEPENDENCY,
                value=0.0,
                confidence=confidence,
                evidence=(),
                logical_tick=1,
                policy=policy,
            )
        )
    return DirectedRelationshipProfile(
        relationship_id=RelationshipId(relationship_id),
        source_id=AgentId(source),
        target_id=AgentId(target),
        dimensions=tuple(dimensions),
        activation_state=RelationshipActivationState.ACTIVE,
        current_revision_id=RelationshipRevisionId("rrev-1"),
        revision_ordinal=1,
        created_tick=1,
        updated_tick=1,
        policy=policy,
    )


def build_drive_profile(
    owner: str = "agent-1",
    *,
    boosts: dict[DriveKind, tuple[float, float]] | None = None,
) -> DriveProfile:
    """Build a drive profile; ``boosts`` maps kind → (baseline, sensitivity)."""
    owner_id = AgentId(owner)
    boosts = boosts or {}
    dispositions = tuple(
        DriveDisposition(
            kind=kind,
            baseline=boosts.get(kind, (0.5, 0.5))[0],
            sensitivity=boosts.get(kind, (0.5, 0.5))[1],
        )
        for kind in REQUIRED_DRIVE_KINDS
    )
    return DriveProfile(owner_id=owner_id, dispositions=dispositions)


def build_snapshot(
    *,
    owner: str = "agent-1",
    revision: int = 1,
    beliefs: Sequence[SemanticBelief] = (),
    goals: Sequence[Goal] = (),
    relationships: Sequence[DirectedRelationshipProfile] = (),
    drives: DriveProfile | None = None,
    counterpart_agent: str | None = None,
    counterpart_entity: str = "body-2",
) -> SubjectiveSnapshot:
    owner_id = AgentId(owner)
    social = None
    if counterpart_agent is not None:
        social = OwnerSafeSocialIdentity(
            owner_id=owner_id,
            owner_entity_id=EntityId("body-1"),
            counterparts=(
                CounterpartBinding(
                    agent_id=AgentId(counterpart_agent),
                    entity_id=EntityId(counterpart_entity),
                ),
            ),
        )
    return SubjectiveSnapshot(
        owner_id=owner_id,
        revision=revision,
        memories=(),
        legacy_beliefs=(),
        semantic_beliefs=tuple(beliefs),
        relationships=tuple(relationships),
        goals=tuple(goals),
        drives=drives if drives is not None else default_drive_profile(owner_id),
        social_identity=social,
    )


def build_loop_input(
    observation: Observation | None = None,
    *,
    owner: str = "agent-1",
    snapshot: SubjectiveSnapshot | None = None,
    beliefs: Sequence[SemanticBelief] = (),
    goals: Sequence[Goal] = (),
    relationships: Sequence[DirectedRelationshipProfile] = (),
    drives: DriveProfile | None = None,
    counterpart_agent: str | None = None,
) -> CognitiveLoopInput:
    agent = AgentId(owner)
    if snapshot is None:
        snapshot = build_snapshot(
            owner=owner,
            beliefs=beliefs,
            goals=goals,
            relationships=relationships,
            drives=drives,
            counterpart_agent=counterpart_agent,
        )
    return CognitiveLoopInput(
        agent_id=agent,
        observation=observation or build_observation(),
        internal_state=InternalAgentState(owner_id=agent),
        snapshot=snapshot,
    )


def build_situation(
    *claims: SituationClaimCode,
    owner: str = "agent-1",
    tick: int = 3,
) -> SituationModel:
    return SituationModel(
        owner_id=AgentId(owner),
        tick=tick,
        claim_codes=claims or (SituationClaimCode.LOCAL_SCENE,),
        confidence=1.0,
    )


def build_self_model(*, owner: str = "agent-1") -> SelfModel:
    return SelfModel(
        owner_id=AgentId(owner),
        policy_id="self-model-projection",
        policy_version="1",
        life_status=LifeStatus.ALIVE,
        beliefs=(),
        goal_ids=(),
        confidence=1.0,
        candidate_count=0,
    )


def empty_memory(*, owner: str = "agent-1") -> RetrievedMemoryContext:
    return RetrievedMemoryContext(
        owner_id=AgentId(owner),
        memory_ids=(),
        belief_ids=(),
        confidence=1.0,
    )


def memory_context(
    *,
    owner: str = "agent-1",
    beliefs: Sequence[SemanticBelief] = (),
    reconstructions: Sequence[ReconstructedMemory] = (),
) -> RetrievedMemoryContext:
    belief_tuple = tuple(beliefs)
    recon_tuple = tuple(reconstructions)
    return RetrievedMemoryContext(
        owner_id=AgentId(owner),
        memory_ids=tuple(
            mid for recon in recon_tuple for mid in recon.source_memory_ids
        ),
        belief_ids=tuple(item.belief_id for item in belief_tuple),
        confidence=1.0,
        reconstructions=recon_tuple,
        semantic_beliefs=belief_tuple,
    )


async def run_deliberation(
    loop_input: CognitiveLoopInput,
    *,
    memory: RetrievedMemoryContext | None = None,
    situation: SituationModel | None = None,
    self_model: SelfModel | None = None,
) -> tuple[PossibleFutures, MotivationEvaluation, SelectedIntention, ActionPlan]:
    """Run imagination → motivation → intention → planning with production policies."""
    mem = memory
    if mem is None:
        beliefs = ()
        if loop_input.snapshot is not None:
            beliefs = loop_input.snapshot.semantic_beliefs
        mem = memory_context(owner=loop_input.agent_id.value, beliefs=beliefs)
    if situation is None:
        claims: list[SituationClaimCode] = [SituationClaimCode.LOCAL_SCENE]
        obs = loop_input.observation
        if obs.resources:
            claims.append(SituationClaimCode.RESOURCE_PRESENT)
        if obs.visible_bodies:
            claims.append(SituationClaimCode.THREAT_SIGNAL)
        if obs.communications:
            claims.append(SituationClaimCode.SOCIAL_SIGNAL)
        sit = build_situation(*claims, owner=loop_input.agent_id.value, tick=obs.tick)
    else:
        sit = situation
    self_state = self_model or build_self_model(owner=loop_input.agent_id.value)
    futures = await ImaginationEngine().imagine(loop_input, sit, self_state, mem)
    motivation = await MotivationAppraisal().evaluate(
        loop_input, sit, self_state, futures
    )
    intention = await MultiCriteriaIntentionSelector().select(
        loop_input, motivation, futures
    )
    plan = await CommandPlanner().plan(loop_input, intention, futures)
    return futures, motivation, intention, plan
