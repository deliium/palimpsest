"""Declarative advice and competence uptake stay off the objective ledger."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.competence import (
    CompetenceDomain,
    empty_competence_model,
)
from agents.cognition.configuration import (
    CognitionSkillLearningMode,
    CognitionTeachingInteractionMode,
)
from agents.cognition.emotion import PassthroughEmotionalStateAppraiser
from agents.cognition.goal_manager import PassthroughGoalManager
from agents.cognition.loop import CognitiveLoop
from agents.cognition.models import (
    CognitiveLoopInput,
    CounterpartBinding,
    InternalAgentState,
    OwnerSafeSocialIdentity,
    SubjectiveSnapshot,
)
from agents.cognition.teaching import (
    AdviceAct,
    AdviceBand,
    AdviceDomain,
    AdviceStore,
    DeclarativeAdvice,
    TeachingClaimPolicy,
    apply_teaching_belief,
    band_for_belief,
    empty_advice_store,
    record_teaching,
)
from agents.models import AgentId
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
from world._skills import ObjectiveSkillLedger, SkillDomain
from world.communications import CommunicationRelation, origin_utterance
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.observations import (
    Observation,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
)

pytestmark = pytest.mark.unit

_LEARNER = AgentId("learner")
_TEACHER = AgentId("teacher")


def _quantize(value: float) -> float:
    return round(value / 1e-6) * 1e-6


def _identity() -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(
        owner_id=_LEARNER,
        owner_entity_id=EntityId("body-2"),
        counterparts=(
            CounterpartBinding(
                agent_id=_TEACHER,
                entity_id=EntityId("body-1"),
            ),
        ),
    )


def _profile(trust: float) -> DirectedRelationshipProfile:
    policy = RelationshipPolicyRef(policy_id="rel-v1", version="1")
    confidence = RelationshipConfidence(
        confidence=1.0, support_mass=1.0, contradiction_mass=0.0
    )
    return DirectedRelationshipProfile(
        relationship_id=RelationshipId("rel-1"),
        source_id=_LEARNER,
        target_id=_TEACHER,
        dimensions=(
            RelationshipDimensionState(
                dimension=RelationshipDimension.TRUST,
                value=trust,
                confidence=confidence,
                evidence=(),
                logical_tick=1,
                policy=policy,
            ),
        ),
        activation_state=RelationshipActivationState.ACTIVE,
        current_revision_id=RelationshipRevisionId("rrev-1"),
        revision_ordinal=1,
        created_tick=1,
        updated_tick=1,
        policy=policy,
    )


def _heard(predicate: str, obj: str, *, event: str = "evt-1") -> Observation:
    utterance = origin_utterance(
        text="a public act",
        speaker_id=EntityId("body-1"),
        communication_id="comm-1",
        relations=(
            CommunicationRelation(subject="skill", predicate=predicate, object=obj),
        ),
    )
    return Observation(
        observer_id=EntityId("body-2"),
        world_id=WorldId("world-1"),
        revision=WorldRevision(1),
        tick=2,
        communications=(
            ObservedCommunication(
                provenance=ObservationProvenance(
                    source_kind=ObservationSourceKind.COMMUNICATION,
                    source_tick=1,
                    source_event_id=EventId(event),
                ),
                speaker_id=EntityId("body-1"),
                listener_id=EntityId("body-2"),
                utterance=utterance,
                action_kind="tell",
            ),
        ),
    )


def _fresh() -> tuple[AdviceStore, object, TeachingClaimPolicy]:
    return (
        empty_advice_store(_LEARNER),
        empty_competence_model(_LEARNER),
        TeachingClaimPolicy(),
    )


def test_false_high_band_moves_belief_and_leaves_objective_skill(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.teaching")
    advice, model, policy = _fresh()
    ledger = ObjectiveSkillLedger.bootstrap((EntityId("body-1"),))
    assert ledger.level(EntityId("body-1"), SkillDomain.FORAGING) == 0.0
    assert band_for_belief(1.0, policy) is AdviceBand.HIGH
    assert ledger.level(EntityId("body-1"), SkillDomain.FORAGING) == 0.0
    stored = record_teaching(
        advice,
        _heard("explain", "foraging:high"),
        (_profile(1.0),),
        policy,
        _identity(),
    )
    row = stored.rows[0]
    assert row.act is AdviceAct.EXPLAIN
    assert row.domain is AdviceDomain.FORAGING
    assert row.band is AdviceBand.HIGH
    assert row.source_agent_id == _TEACHER
    updated = apply_teaching_belief(model, stored, policy, (_profile(1.0),))
    belief = updated.belief_for(CompetenceDomain.FORAGING)
    assert belief.support_mass == 0.08
    assert belief.counter_mass == 0.0
    assert belief.believed_level == _quantize(0.08 / 1.08)
    assert "teaching_advice owner_id=learner" in caplog.text
    assert "act=explain" in caplog.text
    assert "domain=foraging" in caplog.text
    assert "band=high" in caplog.text
    assert "teaching_belief owner_id=learner" in caplog.text
    assert f"believed={_quantize(0.08 / 1.08)}" in caplog.text


def test_low_uncertain_missing_trust_and_request() -> None:
    advice, model, policy = _fresh()
    low = record_teaching(
        advice,
        _heard("explain", "foraging:low"),
        (_profile(1.0),),
        policy,
        _identity(),
    )
    lowered = apply_teaching_belief(model, low, policy, (_profile(1.0),))
    belief = lowered.belief_for(CompetenceDomain.FORAGING)
    assert belief.support_mass == 0.0
    assert belief.counter_mass == 0.08
    assert belief.believed_level == 0.0

    uncertain = record_teaching(
        advice,
        _heard("explain", "foraging:uncertain", event="evt-mid"),
        (),
        policy,
        _identity(),
    )
    held = apply_teaching_belief(model, uncertain, policy, ())
    same = held.belief_for(CompetenceDomain.FORAGING)
    assert same.support_mass == 0.0
    assert same.counter_mass == 0.0

    cautious = record_teaching(
        advice,
        _heard("explain", "foraging:high", event="evt-half"),
        (),
        policy,
        _identity(),
    )
    half = apply_teaching_belief(model, cautious, policy, ())
    expected = half.belief_for(CompetenceDomain.FORAGING)
    assert expected.support_mass == 0.04
    assert expected.believed_level == _quantize(0.04 / 1.04)

    requested = record_teaching(
        advice,
        _heard("request_instruction", "healing", event="evt-ask"),
        (),
        policy,
        _identity(),
    )
    assert requested.rows[0].band is AdviceBand.UNSPECIFIED
    untouched = apply_teaching_belief(model, requested, policy, ())
    masses = untouched.belief_for(CompetenceDomain.HEALING)
    assert masses.support_mass == 0.0
    assert masses.counter_mass == 0.0


def test_unknown_speaker_and_foreign_inputs_fail(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR, logger="agents.cognition.teaching")
    advice, model, policy = _fresh()
    record_teaching(advice, _heard("explain", "foraging:high"), (), policy, None)
    assert "reason_code=unknown_speaker" in caplog.text
    ledger = ObjectiveSkillLedger.bootstrap((EntityId("body-1"),))
    with pytest.raises(TypeError):
        record_teaching(advice, ledger, (), policy, None)
    world = type("WorldState", (), {})()
    with pytest.raises(TypeError):
        apply_teaching_belief(model, world, policy)
    other = empty_competence_model(AgentId("other"))
    with pytest.raises(TypeError):
        apply_teaching_belief(model, other, policy)
    foreign = AdviceStore(
        owner_id=AgentId("other"),
        rows=(
            DeclarativeAdvice(
                occurrence_id="evt-x",
                source_agent_id=_TEACHER,
                act=AdviceAct.EXPLAIN,
                domain=AdviceDomain.FORAGING,
                band=AdviceBand.HIGH,
                delivery_tick=1,
            ),
        ),
    )
    caplog.clear()
    with pytest.raises(ValueError, match="owner_mismatch"):
        apply_teaching_belief(model, foreign, policy)
    assert "reason_code=owner_mismatch" in caplog.text


def test_prepare_applies_the_prior_utterance_and_not_a_repeat(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.teaching")
    loop = CognitiveLoop(
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
        skill_learning_mode=CognitionSkillLearningMode.DETERMINISTIC,
        teaching_interaction_mode=CognitionTeachingInteractionMode.DETERMINISTIC,
    )
    observation = _heard("explain", "foraging:high")
    snapshot = SubjectiveSnapshot(
        owner_id=_LEARNER,
        revision=0,
        memories=(),
        legacy_beliefs=(),
        semantic_beliefs=(),
        relationships=(_profile(1.0),),
        social_identity=_identity(),
    )
    loop_input = CognitiveLoopInput(
        agent_id=_LEARNER,
        observation=observation,
        internal_state=InternalAgentState(owner_id=_LEARNER),
        snapshot=snapshot,
    )
    model, advice = loop._prepare_teaching(loop_input, empty_competence_model(_LEARNER))
    assert advice is not None
    belief = model.belief_for(CompetenceDomain.FORAGING)
    assert belief.believed_level == _quantize(0.08 / 1.08)
    repeated = CognitiveLoopInput(
        agent_id=_LEARNER,
        observation=Observation(
            observer_id=EntityId("body-2"),
            world_id=WorldId("world-1"),
            revision=WorldRevision(1),
            tick=3,
        ),
        internal_state=InternalAgentState(owner_id=_LEARNER),
        snapshot=SubjectiveSnapshot(
            owner_id=_LEARNER,
            revision=1,
            memories=(),
            legacy_beliefs=(),
            semantic_beliefs=(),
            relationships=(_profile(1.0),),
            social_identity=_identity(),
            competence_model=model,
            declarative_advice=advice,
        ),
    )
    again, store = loop._prepare_teaching(repeated, model)
    assert again.belief_for(CompetenceDomain.FORAGING) == belief
    assert store.rows == advice.rows
    disabled = CognitiveLoop(
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
    )
    _kept, nothing = disabled._prepare_teaching(loop_input, None)
    assert nothing is None
