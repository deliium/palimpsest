"""Owner-only destination traces, bounded recall, and generic belief evidence."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition.memory import (
    DirectObservationMemoryUpdateHook,
    ScopedMemoryRetriever,
)
from agents.cognition.models import (
    ActionPlan,
    CognitiveLoopInput,
    DecisionMetadata,
    IntentionCode,
    InternalAgentState,
    InterpretedPerception,
    RetrievedMemoryContext,
    SelectedIntention,
)
from agents.cognition.regional_migration import (
    destination_lane_id,
    destination_memory_trace,
    known_destination_ids,
)
from agents.models import AgentId
from memory.belief_formation import (
    BeliefFormationPolicy,
    bundle_from_candidates,
    extract_evidence_candidates,
)
from memory.beliefs import (
    BeliefValueKind,
    ClaimSubject,
    ClaimSubjectKind,
    ClaimValue,
    SemanticClaim,
)
from memory.models import (
    ConceptMention,
    EntityMention,
    MemoryId,
    MemoryLineage,
    MemoryMutationBatch,
    MemoryProvenance,
    MemoryReconstructionPolicy,
    MemoryRelation,
    MemoryRetrieveRequest,
    MemoryRunId,
    MemoryScope,
    MemoryScoreWeights,
    MemoryScoringPolicy,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
    RelationEndpoint,
    RelationEndpointKind,
)
from memory.service import InMemoryMemoryService
from tests.simulation_helpers import alive_body
from world.actions import Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    Observation,
    ObservedRegionalContext,
    ObservedSelf,
    VisibleExit,
)


def _observation(
    *,
    owner_body: str = "body-1",
    tick: int = 10,
    location: str = "loc-1",
    exits: tuple[VisibleExit, ...] | None = None,
) -> Observation:
    body = alive_body(owner_body, location_id=location)
    regional_exits = (
        (
            VisibleExit(
                destination_id=EntityId("loc-2"),
                name="Near",
                travel_duration_ticks=2,
                fatigue_cost=3,
                destination_region_id="south",
            ),
        )
        if exits is None
        else exits
    )
    return Observation(
        world_id=WorldId("world-destination-memory"),
        observer_id=body.entity_id,
        revision=WorldRevision(4),
        tick=tick,
        self_body=ObservedSelf(
            entity_id=body.entity_id,
            location_id=body.location_id,
            health=body.health,
            hunger=body.hunger,
            thirst=body.thirst,
            fatigue=body.fatigue,
            temperature=body.temperature,
            inventory=body.inventory,
            life_status=LifeStatus.ALIVE,
            carry_capacity=body.carry_capacity,
        ),
        exits=regional_exits,
        regional_context=ObservedRegionalContext("north", "North"),
    )


def _lane_trace(
    memory_id: str,
    *,
    owner: AgentId,
    context_location: str,
    destination: str,
    concept: str,
    source_kind: MemorySourceKind = MemorySourceKind.DIRECT_OBSERVATION,
    source_tick: int = 2,
) -> MemoryTrace:
    provenance = MemoryProvenance(
        kind=source_kind,
        source_tick=source_tick,
        speaker_id=(
            EntityId("speaker")
            if source_kind is MemorySourceKind.COMMUNICATED
            else None
        ),
    )
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=owner,
        world_revision=WorldRevision(1),
        concepts=(ConceptMention(MentionId(f"{memory_id}-concept"), concept),),
        entities=(
            EntityMention(
                MentionId(f"{memory_id}-origin"),
                "origin",
                EntityId(context_location),
            ),
            EntityMention(
                MentionId(f"{memory_id}-destination"),
                "destination",
                EntityId(destination),
            ),
        ),
        relations=(
            MemoryRelation(
                relation_id=MentionId(f"{memory_id}-relation"),
                subject=RelationEndpoint(
                    RelationEndpointKind.ENTITY,
                    MentionId(f"{memory_id}-origin"),
                ),
                predicate="destination_accessible",
                object=RelationEndpoint(
                    RelationEndpointKind.ENTITY,
                    MentionId(f"{memory_id}-destination"),
                ),
            ),
        ),
        context=MemorySituationContext(
            location_id=EntityId(context_location),
            tags=("destination", "route"),
        ),
        emotional_salience=0.2,
        confidence=0.7,
        provenance=provenance,
        created_tick=source_tick,
        source_tick=source_tick,
        last_access_tick=source_tick,
        access_count=0,
        lineage=MemoryLineage(),
    )


def _loop_parts(observation: Observation, owner: AgentId):
    loop_input = CognitiveLoopInput(
        agent_id=owner,
        observation=observation,
        internal_state=InternalAgentState(owner_id=owner),
    )
    perception = InterpretedPerception(
        owner_id=owner,
        observer_id=observation.observer_id,
        tick=observation.tick,
        revision=observation.revision,
        life_status=LifeStatus.ALIVE,
        location_id=observation.self_body.location_id,
        claim_codes=(),
        counts={},
        confidence=1.0,
    )
    plan = ActionPlan(
        owner_id=owner,
        command=Wait(),
        confidence=1,
        decision_metadata=DecisionMetadata(),
    )
    intention = SelectedIntention(
        owner_id=owner,
        intention=IntentionCode.WAIT,
        source_motive=None,
        confidence=1,
        decision_metadata=DecisionMetadata(),
    )
    memory = RetrievedMemoryContext(
        owner_id=owner,
        memory_ids=(),
        belief_ids=(),
        confidence=1,
        decision_metadata=DecisionMetadata(),
    )
    return loop_input, perception, plan, intention, memory


class _SpyMemoryService(InMemoryMemoryService):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.retrieve_requests: list[MemoryRetrieveRequest] = []
        self.recall_requests = []

    async def retrieve(self, request):
        self.retrieve_requests.append(request)
        return await super().retrieve(request)

    async def recall(self, request):
        self.recall_requests.append(request)
        return await super().recall(request)


@pytest.mark.asyncio
async def test_direct_exit_observation_forms_owner_destination_relation() -> None:
    owner = AgentId("agent-1")
    observation = _observation()
    trace = destination_memory_trace(
        owner_id=owner,
        observer_body_id=observation.observer_id,
        observation=observation,
        exit_view=observation.exits[0],
    )
    assert trace.owner_id == owner
    assert trace.context.location_id == EntityId("loc-1")
    assert trace.provenance.kind is MemorySourceKind.DIRECT_OBSERVATION
    assert trace.relations[0].predicate == "destination_accessible"
    candidates = extract_evidence_candidates(
        (trace,),
        owner_id=owner,
        policy=BeliefFormationPolicy(
            policy_id="regional-beliefs", version="1", min_independent_observations=1
        ),
    )
    assert any(
        candidate.claim.predicate == "destination_accessible"
        and candidate.claim.value.entity_id == EntityId("loc-2")
        for candidate in candidates
    )

    loop_parts = _loop_parts(observation, owner)
    loop_input, perception, plan, intention, memory = loop_parts
    intents = await DirectObservationMemoryUpdateHook().propose_updates(
        loop_input, plan, perception, memory, intention
    )
    destination_intents = [
        intent
        for intent in intents
        if intent.memory is not None and "destination" in intent.memory.context.tags
    ]
    assert len(destination_intents) == 1
    assert destination_intents[0].memory == trace


def test_known_destination_graph_is_bounded_and_owner_scoped() -> None:
    owner = AgentId("agent-1")
    observation = _observation()
    second_hop = _lane_trace(
        "visited-loc-3",
        owner=owner,
        context_location="loc-2",
        destination="loc-3",
        concept="visited_destination",
    )
    assert known_destination_ids(
        owner_id=owner,
        observation=observation,
        memories=(second_hop,),
        hop_limit=1,
    ) == (EntityId("loc-2"),)
    assert known_destination_ids(
        owner_id=owner,
        observation=observation,
        memories=(second_hop,),
        hop_limit=2,
    ) == (EntityId("loc-2"), EntityId("loc-3"))
    with pytest.raises(ValueError, match="foreign-owner"):
        known_destination_ids(
            owner_id=owner,
            observation=observation,
            memories=(replace(second_hop, owner_id=AgentId("other")),),
            hop_limit=2,
        )
    absent = _observation(exits=())
    assert (
        known_destination_ids(
            owner_id=owner, observation=absent, memories=(), hop_limit=2
        )
        == ()
    )


def test_destination_reports_can_be_stale_wrong_and_contradictory() -> None:
    owner = AgentId("agent-1")

    def report(memory_id: str, value: str, tick: int) -> MemoryTrace:
        base = _lane_trace(
            memory_id,
            owner=owner,
            context_location="loc-2",
            destination="loc-3",
            concept=f"water_report:{value}",
            source_kind=MemorySourceKind.COMMUNICATED,
            source_tick=tick,
        )
        mention_id = MentionId(f"{memory_id}-water")
        return replace(
            base,
            concepts=(*base.concepts, ConceptMention(mention_id, value)),
            relations=(
                *base.relations,
                MemoryRelation(
                    relation_id=MentionId(f"{memory_id}-water-relation"),
                    subject=RelationEndpoint(
                        RelationEndpointKind.ENTITY,
                        MentionId(f"{memory_id}-destination"),
                    ),
                    predicate="destination_resource_water",
                    object=RelationEndpoint(RelationEndpointKind.CONCEPT, mention_id),
                ),
            ),
        )

    stale_report = report("stale-water-report", "absent", tick=1)
    newer_report = report("new-water-report", "present", tick=9)
    candidates = extract_evidence_candidates(
        (stale_report, newer_report),
        owner_id=owner,
        policy=BeliefFormationPolicy(
            policy_id="regional-beliefs", version="1", min_independent_observations=1
        ),
    )
    target = SemanticClaim(
        subject=ClaimSubject(kind=ClaimSubjectKind.ENTITY, entity_id=EntityId("loc-3")),
        predicate="destination_resource_water",
        value=ClaimValue(kind=BeliefValueKind.TEXT, text_value="present"),
    )
    bundle = bundle_from_candidates(candidates, target_claim=target)
    assert {row.memory_id for row in bundle.supporting} == {newer_report.memory_id}
    assert {row.memory_id for row in bundle.contradicting} == {stale_report.memory_id}
    assert stale_report.source_tick == 1


@pytest.mark.asyncio
async def test_scoped_retriever_uses_bounded_destination_lane_and_unique_ids() -> None:
    owner = AgentId("agent-1")
    service = _SpyMemoryService(
        MemoryScope(run_id=MemoryRunId("run-1"), owner_id=owner)
    )
    observation = _observation()
    local = _lane_trace(
        "local-memory",
        owner=owner,
        context_location="loc-1",
        destination="loc-1",
        concept="at_local_place",
    )
    visited = _lane_trace(
        "visited-memory",
        owner=owner,
        context_location="loc-2",
        destination="loc-3",
        concept="reported_water_absent",
        source_kind=MemorySourceKind.COMMUNICATED,
    )
    overlap = destination_memory_trace(
        owner_id=owner,
        observer_body_id=observation.observer_id,
        observation=observation,
        exit_view=observation.exits[0],
    )
    await service.apply(MemoryMutationBatch(writes=(local, visited, overlap)))
    retriever = ScopedMemoryRetriever(
        service,
        scoring_policy=MemoryScoringPolicy(
            policy_id="destination-score",
            version="1",
            weights=MemoryScoreWeights(recency=1.0),
        ),
        reconstruction_policy=MemoryReconstructionPolicy(
            policy_id="destination-recall",
            version="1",
            max_source_traces=4,
        ),
        limit=4,
        destination_memory_limit=2,
        destination_hop_limit=2,
    )
    loop_input, perception, _, _, _ = _loop_parts(observation, owner)
    result = await retriever.retrieve(loop_input, perception)
    assert len(service.retrieve_requests) == 2
    assert service.retrieve_requests[0].operation_id == "cog:agent-1:t10:1"
    assert service.retrieve_requests[1].filters.location_id is None
    assert service.retrieve_requests[1].limit == 2
    assert service.retrieve_requests[1].operation_id.startswith(
        "destination-operation-"
    )
    assert len(service.recall_requests) == 2
    local_recall, destination_recall = service.recall_requests
    assert local_recall.reconstruction_id.value == "recon-agent-1-t10-1"
    assert local_recall.retrieve.operation_id == "cog:agent-1:t10:1"
    assert destination_recall.reconstruction_id != local_recall.reconstruction_id
    assert destination_recall.pre_retrieved is not None
    assert destination_recall.derived_memory_id is None
    assert destination_recall.reconstruction_policy.max_source_traces == 1
    assert len(result.memory_ids) == len(set(result.memory_ids))
    assert {item.value for item in result.memory_ids} == {
        "local-memory",
        "visited-memory",
        overlap.memory_id.value,
    }
    assert len(result.pending_accesses) == 3
    stale_hit = next(
        hit
        for hit in result.ranked_hits
        if hit.trace.memory_id.value == "visited-memory"
    )
    assert stale_hit.trace.source_tick == 2
    assert any(
        "reported_water_absent" in reconstruction.narrative
        for reconstruction in result.reconstructions
    )
    assert (
        destination_lane_id(
            namespace="operation",
            owner_id=owner,
            tick=10,
            policy_version="1",
        )
        == service.retrieve_requests[1].operation_id
    )


@pytest.mark.asyncio
async def test_destination_lane_skips_zero_remaining_selection_budget() -> None:
    owner = AgentId("agent-1")
    service = _SpyMemoryService(
        MemoryScope(run_id=MemoryRunId("run-1"), owner_id=owner)
    )
    observation = _observation()
    traces = tuple(
        _lane_trace(
            f"local-{index}",
            owner=owner,
            context_location="loc-1",
            destination=f"loc-{index}",
            concept=f"local_fact_{index}",
        )
        for index in range(2)
    )
    await service.apply(MemoryMutationBatch(writes=traces))
    retriever = ScopedMemoryRetriever(
        service,
        scoring_policy=MemoryScoringPolicy(
            policy_id="destination-score",
            version="1",
            weights=MemoryScoreWeights(recency=1.0),
        ),
        reconstruction_policy=MemoryReconstructionPolicy(
            policy_id="destination-recall", version="1", max_source_traces=2
        ),
        limit=2,
        destination_memory_limit=2,
        destination_hop_limit=1,
    )
    loop_input, perception, _, _, _ = _loop_parts(observation, owner)
    await retriever.retrieve(loop_input, perception)
    assert len(service.retrieve_requests) == 1
    assert len(service.recall_requests) == 1


@pytest.mark.asyncio
async def test_destination_reconsolidation_uses_lane_specific_lineage_ids() -> None:
    owner = AgentId("agent-1")
    service = _SpyMemoryService(
        MemoryScope(run_id=MemoryRunId("run-1"), owner_id=owner)
    )
    observation = _observation()
    visited = _lane_trace(
        "stale-destination-report",
        owner=owner,
        context_location="loc-2",
        destination="loc-2",
        concept="reported_water_absent",
        source_kind=MemorySourceKind.COMMUNICATED,
        source_tick=2,
    )
    await service.apply(MemoryMutationBatch(writes=(visited,)))
    retriever = ScopedMemoryRetriever(
        service,
        scoring_policy=MemoryScoringPolicy(
            policy_id="destination-score",
            version="2",
            weights=MemoryScoreWeights(recency=1.0),
        ),
        reconstruction_policy=MemoryReconstructionPolicy(
            policy_id="destination-recall",
            version="2",
            reconsolidate=True,
            max_source_traces=4,
        ),
        limit=4,
        destination_memory_limit=2,
        destination_hop_limit=1,
    )
    loop_input, perception, _, _, _ = _loop_parts(observation, owner)
    context = await retriever.retrieve(loop_input, perception)
    assert len(service.recall_requests) == 2
    local_request, destination_request = service.recall_requests
    assert local_request.reconstruction_id.value == "recon-agent-1-t10-2"
    assert destination_request.reconstruction_id != local_request.reconstruction_id
    assert destination_request.derived_memory_id is not None
    assert destination_request.derived_memory_id.value.startswith(
        "destination-derived-memory-"
    )
    assert context.reconsolidation is not None
    assert (
        context.reconsolidation.derived_trace.memory_id
        == destination_request.derived_memory_id
    )
    assert context.reconsolidation.derived_trace.source_tick == 2
