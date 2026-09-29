"""Hidden communication-intent audits stay off agent-facing channels."""

from __future__ import annotations

import inspect
import logging
from dataclasses import fields
from types import SimpleNamespace

import pytest

from agents.cognition.communication_strategy import (
    CommunicationDivergence,
    CommunicationFactor,
    CommunicationIntentAudit,
    CommunicationStrategy,
    SpeakerStance,
    communication_intent,
)
from agents.models import AgentId
from memory.belief_formation import evaluate_communicated_testimony
from memory.models import MemoryTrace
from simulation.runner_models import SimulationRunnerResultDocument
from simulation.subjective_serialization import SUBJECTIVE_SCHEMA_VERSION
from social.models import CommunicationEnvelope
from world.communications import (
    CommunicationSourceBasis,
    DeclaredTransmission,
    StructuredUtterance,
)
from world.observations import ObservedCommunication

_FORBIDDEN = {
    "strategy",
    "stance",
    "memory_error",
    "uncertain_inference",
    "deliberate_deception",
}


def test_receiver_records_do_not_carry_strategy_labels() -> None:
    for model in (
        StructuredUtterance,
        DeclaredTransmission,
        ObservedCommunication,
        CommunicationEnvelope,
        MemoryTrace,
    ):
        names = {item.name for item in fields(model)}
        assert names.isdisjoint(_FORBIDDEN)
    parameters = inspect.signature(evaluate_communicated_testimony).parameters
    assert "strategy" not in parameters
    assert "category" not in parameters


def test_result_document_and_subjective_schema_omit_the_audit() -> None:
    document_names = {item.name for item in fields(SimulationRunnerResultDocument)}
    assert "communication_intent_audits" not in document_names
    assert SUBJECTIVE_SCHEMA_VERSION == "subjective-v1"


def test_trace_projection_does_not_name_strategy_fields() -> None:
    from pathlib import Path

    source = Path("src/agents/cognition/trace.py").read_text(encoding="utf-8")
    assert "communication_intent" not in source
    assert "deliberate_deception" not in source


@pytest.mark.asyncio
async def test_disabled_finalize_and_abort_append_no_audit(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from tests.unit.test_agent_runtime import _runtime, _self, _token

    runtime, _memories, _beliefs = _runtime()
    runtime.start()
    prepared = await runtime.prepare_observation(_self(tick=0), token=_token(0))
    pending = await runtime.bind_effective_command(prepared)
    runtime.abort_pending(pending)
    assert runtime.export_communication_intent_audits() == ()

    prepared_again = await runtime.prepare_observation(_self(tick=0), token=_token(0))
    finalized = await runtime.bind_effective_command(prepared_again)
    with caplog.at_level(logging.DEBUG, logger="simulation.agent_runtime"):
        await runtime.finalize_pending(finalized)
    assert runtime.export_communication_intent_audits() == ()
    skipped = [
        record.getMessage()
        for record in caplog.records
        if "communication_intent_audit_skipped" in record.getMessage()
    ]
    assert skipped
    assert "audit_present=False" in skipped[-1]


def test_commit_keeps_strategy_and_stance_out_of_atom_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from tests.unit.test_agent_runtime import _runtime

    owner = AgentId("agent-1")
    intent = communication_intent(
        owner_id=owner,
        recipient_id=AgentId("agent-2"),
        tick=4,
        strategy=CommunicationStrategy.TRUTHFUL,
        stance=SpeakerStance.ASSERT_MATCH,
        divergence=CommunicationDivergence.NONE,
        source_basis=CommunicationSourceBasis.BELIEF,
        source_confidence=0.8,
        source_atom_tokens=("food",),
        cited_event_id=None,
        factor_codes=(CommunicationFactor.NORMS_UNAVAILABLE,),
        delivered=True,
    )
    audit = CommunicationIntentAudit(
        intent_id=intent.intent_id,
        owner_id=intent.owner_id,
        recipient_id=intent.recipient_id,
        tick=intent.tick,
        strategy=intent.strategy,
        stance=intent.stance,
        divergence=intent.divergence,
        source_basis=intent.source_basis,
        source_confidence=intent.source_confidence,
        source_atom_tokens=intent.source_atom_tokens,
        cited_event_id=intent.cited_event_id,
        factor_codes=intent.factor_codes,
        delivered=intent.delivered,
        fallback_used=False,
    )
    runtime, _memories, _beliefs = _runtime()
    with caplog.at_level(logging.DEBUG, logger="simulation.agent_runtime"):
        runtime._commit_communication_intent(
            SimpleNamespace(
                communication_intent=intent,
                communication_intent_audit=audit,
            ),
            4,
        )
    exported = runtime.export_communication_intent_audits()
    assert exported == (audit,)
    message = next(
        record.getMessage()
        for record in caplog.records
        if "communication_intent_audit_committed" in record.getMessage()
    )
    assert "strategy=truthful" in message
    assert "stance=assert_match" in message
    assert "food" not in message


def _pair(**overrides: object):
    from agents.cognition.communication_strategy import apply_communication_strategy
    from world.identifiers import EntityId

    payload: dict[str, object] = {
        "owner_id": AgentId("agent-1"),
        "recipient_id": AgentId("agent-2"),
        "recipient_entity_id": EntityId("body-2"),
        "speaker_id": EntityId("body-1"),
        "tick": 4,
        "source_basis": CommunicationSourceBasis.BELIEF,
        "source_confidence": 0.9,
        "source_atom_tokens": ("camp",),
        "action_kind": "tell",
        "risks": (),
    }
    payload.update(overrides)
    return apply_communication_strategy(**payload)  # type: ignore[arg-type]


def _seen_event():
    from world.events import (
        EVENT_SCHEMA_REPLAY_V5,
        ActionCause,
        OccurrenceContext,
        Searched,
        WorldEvent,
    )
    from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision

    request = RequestId("r-seen")
    return WorldEvent(
        event_id=EventId("seen-1"),
        run_id="run-metric",
        world_id=WorldId("world-1"),
        tick=4,
        sequence=1,
        request_id=request,
        resulting_revision=WorldRevision(1),
        schema_version=EVENT_SCHEMA_REPLAY_V5,
        details=Searched(success=False),
        actor_id=EntityId("body-1"),
        cause=ActionCause(request, EntityId("body-1")),
        occurrence=OccurrenceContext(
            destination_location_id=EntityId("loc-other")
        ),
    )


def test_categories_stay_distinct_from_the_strategy() -> None:
    from agents.cognition.epistemic import EpistemicJudgment
    from agents.cognition.models import GoalBoard
    from agents.models import (
        Goal,
        GoalHorizon,
        GoalId,
        GoalOutcome,
        GoalOutcomeKind,
        GoalStatus,
    )
    from analysis.communication_strategy_metrics import (
        compute_communication_strategy_metrics,
    )

    event = _seen_event()
    _truth_command, truthful, truth_audit = _pair(
        source_basis=CommunicationSourceBasis.RECONSTRUCTED_MEMORY,
        cited_event_id="seen-1",
    )
    _none_command, unmatched, _unmatched_audit = _pair(
        source_basis=CommunicationSourceBasis.RECONSTRUCTED_MEMORY,
        cited_event_id=None,
    )
    ask, uncertain, _uncertain_audit = _pair(source_confidence=0.4)
    life = Goal(
        goal_id=GoalId("stay-alive"),
        owner_id=AgentId("agent-1"),
        description="remain alive",
        priority=1.0,
        status=GoalStatus.ACTIVE,
        horizon=GoalHorizon.CURRENT_INTENTION,
        outcome=GoalOutcome(kind=GoalOutcomeKind.PRESERVE_LIFE),
        created_tick=1,
    )
    board = GoalBoard(
        owner_id=AgentId("agent-1"),
        tick=4,
        goals=(life,),
        foci_ids=(life.goal_id,),
        transition_intents=(),
        confidence=1.0,
        policy_version="goals.v1",
    )
    refusal_command, refusal, _refusal_audit = _pair(
        goal_board=board,
        epistemic_judgment=EpistemicJudgment.SECRET,
    )
    labeled = compute_communication_strategy_metrics(
        (truth_audit, unmatched, uncertain, refusal),
        (event,),
        run_id="run-metric",
        input_revision="rev-1",
    )
    assert truthful.strategy is CommunicationStrategy.TRUTHFUL
    assert truthful.stance is SpeakerStance.ASSERT_MATCH
    assert ask is not None and ask.kind == "ask"
    assert refusal_command is not None
    assert refusal_command.utterance.content.relations[0].predicate == "decline"
    assert refusal_command.utterance.content.concepts == ()
    assert labeled.categories == (
        "memory_error",
        "unmatched",
        "uncertain_inference",
        "not_asserted",
    )
    covered = compute_communication_strategy_metrics(
        (uncertain,),
        (event,),
        run_id="run-metric",
        input_revision="rev-1",
    )
    assert covered.categories == ("uncertain_inference",)
    assert {item.name for item in fields(MemoryTrace)}.isdisjoint(_FORBIDDEN)


def test_false_statement_does_not_move_trust_until_contradiction() -> None:
    from agents.cognition.communication_strategy import apply_communication_strategy
    from analysis.communication_strategy_metrics import (
        compute_communication_strategy_metrics,
    )
    from memory.belief_formation import (
        DEFAULT_BELIEF_FORMATION_POLICY,
        CommunicatedEvidenceDecision,
    )
    from social.relationships import RelationshipDimension
    from tests.unit.test_communication_strategy import (
        _LISTENER,
        _OWNER,
        _RECIPIENT,
        _SPEAKER,
        _profile,
    )

    profile = _profile(trust=0.7, fear=0.5)
    before = next(
        item.value
        for item in profile.dimensions
        if item.dimension is RelationshipDimension.TRUST
    )
    command, intent, audit = apply_communication_strategy(
        owner_id=_OWNER,
        recipient_id=_RECIPIENT,
        recipient_entity_id=_LISTENER,
        speaker_id=_SPEAKER,
        tick=4,
        source_basis=CommunicationSourceBasis.BELIEF,
        source_confidence=0.9,
        source_atom_tokens=("loc-true",),
        action_kind="tell",
        relationships=(profile,),
        observation=_false_view(),
        risks=(),
    )
    assert intent.strategy is CommunicationStrategy.DELIBERATE_FALSE_STATEMENT
    assert command is not None
    assert command.utterance.content.concepts == ("loc-other",)
    assert command.utterance.content.text == "loc-other"
    assert not hasattr(command.utterance, "strategy")
    policy = DEFAULT_BELIEF_FORMATION_POLICY
    accepted = evaluate_communicated_testimony(
        sender_confidence=command.utterance.declared.sender_confidence,
        receiver_confidence=0.8,
        trust=before,
        trust_confidence=0.8,
        hop_count=0,
        context_relevance=0.8,
        base_contribution=0.5,
        policy=policy,
    )
    after = next(
        item.value
        for item in profile.dimensions
        if item.dimension is RelationshipDimension.TRUST
    )
    assert after == before
    assert accepted.decision is CommunicatedEvidenceDecision.ACCEPT
    contradicted = evaluate_communicated_testimony(
        sender_confidence=command.utterance.declared.sender_confidence,
        receiver_confidence=0.8,
        trust=0.1,
        trust_confidence=0.8,
        hop_count=0,
        context_relevance=0.8,
        base_contribution=0.5,
        policy=policy,
    )
    assert contradicted.decision is CommunicatedEvidenceDecision.CONTRADICT
    labeled = compute_communication_strategy_metrics(
        (audit,),
        (_seen_event(),),
        run_id="run-metric",
        input_revision="rev-1",
    )
    assert labeled.categories == ("deliberate_deception",)


def _false_view():
    from world.identifiers import EntityId, WorldId, WorldRevision
    from world.observations import Observation, ObservedLocation

    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-speaker"),
        revision=WorldRevision(0),
        locations=(
            ObservedLocation(entity_id=EntityId("loc-other"), name="other"),
        ),
    )


@pytest.mark.asyncio
async def test_omission_planner_emits_wait_without_a_social_command() -> None:
    from agents.cognition.communication import SocialMessageSelection
    from agents.cognition.deliberation import CommandPlanner
    from agents.cognition.epistemic import EpistemicJudgment
    from agents.cognition.models import (
        ActionDirection,
        ImaginedFuture,
        IntentionCode,
        MotivationCode,
        PossibleFutures,
        SelectedIntention,
        SituationClaimCode,
    )
    from tests.unit.test_action_planner import _loop_input
    from world.actions import Ask, Talk, Tell, Wait
    from world.identifiers import EntityId
    from world.models import LifeStatus
    from world.observations import CoarseHealth, VisibleBody

    class _OmissionPolicy:
        def select(self, **_kwargs: object) -> SocialMessageSelection:
            command, intent, audit = _pair(
                epistemic_judgment=EpistemicJudgment.SECRET,
                source_atom_tokens=("camp",),
            )
            assert command is None
            assert intent.delivered is False
            return SocialMessageSelection(
                command=None,
                intent=intent,
                action_kind="wait",
                source_basis=CommunicationSourceBasis.BELIEF,
                hop_count=0,
                sender_confidence=0.9,
                fallback=False,
                audit=audit,
            )

    plan = await CommandPlanner(social_messages=_OmissionPolicy()).plan(
        _loop_input(
            visible_bodies=(
                VisibleBody(
                    entity_id=EntityId("body-2"),
                    life_status=LifeStatus.ALIVE,
                    coarse_health=CoarseHealth.STABLE,
                ),
            )
        ),
        SelectedIntention(
            owner_id=AgentId("agent-1"),
            intention=IntentionCode.COMMUNICATE,
            source_motive=MotivationCode.WAIT,
            confidence=0.8,
            selected_future_id="talk-0",
            direction=ActionDirection.COMMUNICATE,
            appraisal_future_ids=("talk-0",),
        ),
        PossibleFutures(
            owner_id=AgentId("agent-1"),
            futures=(
                ImaginedFuture(
                    future_id="talk-0",
                    claim_codes=(SituationClaimCode.SOCIAL_SIGNAL,),
                    confidence=0.8,
                    direction=ActionDirection.COMMUNICATE,
                    target_entity_id="body-2",
                ),
            ),
            confidence=1.0,
        ),
    )
    assert type(plan.command) is Wait
    assert plan.communication_intent is not None
    assert plan.communication_intent.delivered is False
    assert type(plan.command) not in {Talk, Ask, Tell}


def test_hop_above_one_is_still_dropped() -> None:
    from agents.cognition.epistemic import _apply_testimony, default_epistemic_policy
    from world.communications import origin_utterance, retell_utterance
    from world.identifiers import EntityId, EventId, WorldId, WorldRevision
    from world.observations import (
        Observation,
        ObservationProvenance,
        ObservationSourceKind,
        ObservedCommunication,
    )

    origin = origin_utterance(
        text="camp",
        speaker_id=EntityId("body-a"),
        communication_id="comm-origin",
        sender_confidence=0.8,
        source_basis=CommunicationSourceBasis.BELIEF,
        concepts=("camp",),
    )
    once = retell_utterance(
        prior=origin,
        speaker_id=EntityId("body-b"),
        communication_id="comm-hop-1",
        sender_confidence=0.8,
    )
    twice = retell_utterance(
        prior=once,
        speaker_id=EntityId("body-c"),
        communication_id="comm-hop-2",
        sender_confidence=0.8,
    )
    assert twice.declared.hop_count > 1
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(1),
        tick=3,
        communications=(
            ObservedCommunication(
                provenance=ObservationProvenance(
                    source_kind=ObservationSourceKind.COMMUNICATION,
                    source_tick=2,
                    source_event_id=EventId("evt-hop"),
                ),
                speaker_id=EntityId("body-c"),
                listener_id=EntityId("body-1"),
                utterance=twice,
                action_kind="tell",
            ),
        ),
    )
    _created, dropped = _apply_testimony(
        [],
        observation=observation,
        policy=default_epistemic_policy(),
        owner=AgentId("agent-1"),
    )
    assert dropped == 1
