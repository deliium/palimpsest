"""Identity revisions are pending until a successful finalize."""

from __future__ import annotations

import logging

import pytest

from agents.cognition import build_identity_claim, project_identity_state
from agents.cognition.configuration import (
    CognitionIdentityMode,
    CognitionLoopConfig,
    build_cognitive_loop,
)
from agents.cognition.consolidation import OfflineConsolidationPlan
from agents.cognition.emotion import PassthroughEmotionalStateAppraiser
from agents.cognition.goal_manager import PassthroughGoalManager
from agents.cognition.identity import without_overlapping_identity_requests
from agents.cognition.loop import CognitiveLoop
from agents.cognition.models import (
    CognitiveLoopInput,
    InternalAgentState,
    SubjectiveSnapshot,
)
from agents.models import AgentId
from memory.belief_formation import DEFAULT_BELIEF_FORMATION_POLICY, belief_id_for_claim
from memory.belief_service import InMemorySemanticBeliefService
from memory.beliefs import (
    BeliefEvidenceBundle,
    BeliefRevisionRequest,
    BeliefValueKind,
    ClaimValue,
)
from memory.models import (
    OFFLINE_CONSOLIDATION_POLICY_VERSION,
    BeliefId,
    BeliefStore,
    ConceptMention,
    MemoryId,
    MemoryProvenance,
    MemoryRunId,
    MemoryScope,
    MemorySituationContext,
    MemorySourceKind,
    MemoryStore,
    MemoryTrace,
    MentionId,
    OfflineConsolidationAudit,
    OfflineConsolidationSelection,
)
from memory.service import InMemoryMemoryService
from simulation.agent_runtime import AgentRuntime
from simulation.bootstrap import registration_translator
from simulation.subjective_state import InMemorySubjectiveStateService
from social.service import InMemoryRelationshipService
from tests.typecheck.cognitive_loop import (
    ScriptedFutureImagination,
    ScriptedIntentionSelector,
    ScriptedMemoryRetriever,
    ScriptedMemoryUpdateHook,
    ScriptedMotivationEvaluator,
    ScriptedPerceptionInterpreter,
    ScriptedPlanner,
    ScriptedSelfStateProjector,
    ScriptedSituationModeler,
)
from tests.unit.test_agent_runtime import _agent, _body, _bootstrap, _token
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.observations import (
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
    ObservedSelf,
)


def _memory(owner: AgentId) -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId("mem-move"),
        owner_id=owner,
        world_revision=WorldRevision(0),
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept="trail"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=0.0,
        confidence=1.0,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION, source_tick=3
        ),
        created_tick=3,
        source_tick=3,
        last_access_tick=3,
        access_count=0,
    )


def _occurrence() -> ObservedOccurrence:
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=3,
            source_event_id=EventId("event-move-3"),
        ),
        kind="move",
        audience_role=ObservationAudienceRole.ACTOR,
        actor_id=EntityId("body-1"),
        success=True,
    )


def _observation() -> Observation:
    body = _body("body-1")
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=4,
        self_body=ObservedSelf(
            entity_id=body.entity_id,
            location_id=body.location_id,
            health=body.health,
            hunger=body.hunger,
            thirst=body.thirst,
            fatigue=body.fatigue,
            temperature=body.temperature,
            inventory=body.inventory,
            life_status=body.life_status,
            carry_capacity=body.carry_capacity,
        ),
        occurrences=(_occurrence(),),
    )


def _scripted_loop(*, enabled: bool) -> CognitiveLoop:
    mode = (
        CognitionIdentityMode.ENABLED
        if enabled
        else CognitionIdentityMode.PASSTHROUGH
    )
    return CognitiveLoop(
        perception=ScriptedPerceptionInterpreter(),
        memory=ScriptedMemoryRetriever(),
        situation=ScriptedSituationModeler(),
        self_state=ScriptedSelfStateProjector(),
        goal_manager=PassthroughGoalManager(),
        emotional_state=PassthroughEmotionalStateAppraiser(),
        futures=ScriptedFutureImagination(),
        motivation=ScriptedMotivationEvaluator(),
        intention=ScriptedIntentionSelector(),
        planner=ScriptedPlanner(),
        memory_updates=ScriptedMemoryUpdateHook(),
        identity_mode=mode,
    )


def _loop_input(owner: AgentId) -> CognitiveLoopInput:
    return CognitiveLoopInput(
        agent_id=owner,
        observation=_observation(),
        internal_state=InternalAgentState(owner_id=owner),
        snapshot=SubjectiveSnapshot(
            owner_id=owner,
            revision=0,
            memories=(_memory(owner),),
            legacy_beliefs=(),
            semantic_beliefs=(),
        ),
    )


class _BeliefReader:
    def __init__(self, service: InMemorySemanticBeliefService) -> None:
        self._service = service

    def snapshot(self) -> tuple[object, ...]:
        return self._service._store.snapshot()

    def history(self, belief_id: BeliefId) -> object | None:
        return self._service.history_sync(belief_id)


@pytest.mark.asyncio
async def test_passthrough_emits_no_identity_requests(
    caplog: pytest.LogCaptureFixture,
) -> None:
    owner = AgentId("agent-1")
    loop = _scripted_loop(enabled=False)
    proposal = await loop.prepare(_loop_input(owner), invocation_id="inv-off")
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.loop"):
        result = await loop.complete(
            proposal, effective_command=proposal.proposed_command
        )
    assert result.identity_revisions == ()
    assert "identity_pending" not in caplog.text


@pytest.mark.asyncio
async def test_enabled_complete_emits_bool_requests(
    caplog: pytest.LogCaptureFixture,
) -> None:
    owner = AgentId("agent-1")
    loop = _scripted_loop(enabled=True)
    proposal = await loop.prepare(_loop_input(owner), invocation_id="inv-on")
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.loop"):
        result = await loop.complete(
            proposal, effective_command=proposal.proposed_command
        )
    assert result.identity_revisions
    assert all(
        item.claim.value.bool_value is True for item in result.identity_revisions
    )
    pending = [
        record for record in caplog.records if record.message == "identity_pending"
    ]
    assert pending
    payload = str(getattr(pending[-1], "aspect_counts", ""))
    assert "ability" in payload
    assert "move" not in payload
    assert "identity." not in payload


def test_overlap_drops_belief_already_revised() -> None:
    owner = AgentId("agent-1")
    claim = build_identity_claim(
        owner,
        "identity.ability.observed_outcome.move",
        ClaimValue(kind=BeliefValueKind.BOOL, bool_value=True),
    )
    request = BeliefRevisionRequest(
        owner_id=owner,
        operation_id="identity-ability-overlap",
        logical_tick=4,
        claim=claim,
        evidence=BeliefEvidenceBundle(supporting=(), contradicting=()),
        policy=DEFAULT_BELIEF_FORMATION_POLICY.as_ref(),
        belief_id=belief_id_for_claim(owner_id=owner, claim=claim),
    )
    plan = OfflineConsolidationPlan(
        selection=OfflineConsolidationSelection(
            owner_id=owner,
            tick=4,
            policy_version=OFFLINE_CONSOLIDATION_POLICY_VERSION,
        ),
        audit=OfflineConsolidationAudit(owner_id=owner, tick=4, mode="deterministic"),
        belief_revisions=(request,),
        relationship_revisions=(),
        goal_intents=(),
        self_model_belief_ids=(),
    )
    kept = without_overlapping_identity_requests(
        (request,), consolidation=plan, reflection=None
    )
    assert kept == ()


def _runtime() -> tuple[AgentRuntime, _BeliefReader]:
    owner = AgentId("agent-1")
    memories = MemoryStore(owner)
    memories.write(_memory(owner))
    scope = MemoryScope(run_id=MemoryRunId("run-identity"), owner_id=owner)
    beliefs = InMemorySemanticBeliefService(scope)
    subjective = InMemorySubjectiveStateService(
        scope,
        memory_service=InMemoryMemoryService(scope),
        belief_service=beliefs,
        relationship_service=InMemoryRelationshipService(owner),
    )
    reader = _BeliefReader(beliefs)
    runtime = AgentRuntime(
        agent=_agent(),
        translator=registration_translator(_bootstrap()),
        cognitive_loop=build_cognitive_loop(
            CognitionLoopConfig(identity_mode=CognitionIdentityMode.ENABLED)
        ),
        memory_reader=memories,
        memory_writer=memories,
        belief_reader=BeliefStore(owner),
        belief_writer=BeliefStore(owner),
        subjective_state=subjective,
        semantic_belief_reader=reader,  # type: ignore[arg-type]
    )
    runtime.start()
    return runtime, reader


@pytest.mark.asyncio
async def test_finalize_applies_identity_and_bind_does_not(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runtime, reader = _runtime()
    prepared = await runtime.prepare_observation(_observation(), token=_token(4))
    pending = await runtime.bind_effective_command(prepared)
    assert reader.snapshot() == ()
    with caplog.at_level(logging.DEBUG, logger="simulation.agent_runtime"):
        await runtime.finalize_pending(pending)
    heads = reader.snapshot()
    assert heads
    histories = tuple(reader.history(item.belief_id) for item in heads)  # type: ignore[attr-defined]
    state = project_identity_state(owner_id=AgentId("agent-1"), histories=histories)
    assert state.views
    assert all(view.claim.value.bool_value is True for view in state.views)
    applied = [
        record for record in caplog.records if record.message == "identity_applied"
    ]
    assert applied
    assert getattr(applied[-1], "created_count", 0) >= 1
    rendered = str(applied[-1].__dict__)
    assert "identity.ability" not in rendered
    assert "move" not in rendered
