"""Contracts for owner-scoped first-order mind hypotheses."""

from __future__ import annotations

import logging
import math

import pytest

from agents.cognition.configuration import (
    CognitionLoopConfig,
    CognitionTheoryOfMindMode,
)
from agents.cognition.models import _EFFECT_QUANTUM
from agents.cognition.theory_of_mind import (
    THEORY_OF_MIND_POLICY_VERSION,
    MindAspect,
    MindAtom,
    MindEvidenceChannel,
    MindHypothesis,
    MindSlot,
    MindUpdateReason,
    TheoryOfMind,
    TheoryOfMindPolicy,
    confidence_from_masses,
    cues_from_observation,
    default_theory_of_mind_policy,
    empty_theory_of_mind,
    mind_hypothesis_id_for,
    update_theory_of_mind,
)
from agents.models import AgentId
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    CoarseHealth,
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
    ObservedOccurrence,
    ObservedSelf,
    VisibleBody,
)
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)

_OWNER = AgentId("agent-alice")
_SUBJECT = EntityId("body-bob")
_LOGGER = "agents.cognition.theory_of_mind"


def _atom(slot: MindSlot, value: str) -> MindAtom:
    return MindAtom(slot=slot, value=value)


def _hunger() -> MindHypothesis:
    return MindHypothesis(
        owner_id=_OWNER,
        subject_id=_SUBJECT,
        aspect=MindAspect.NEED,
        atoms=(_atom(MindSlot.NEED_KIND, "hunger"),),
        support=4.0,
        counter=0.0,
        evidence_ids=("prov-eat",),
        counter_evidence_ids=(),
        channel=MindEvidenceChannel.OBSERVED_BEHAVIOR,
    )


def test_policy_defaults_keep_provider_off() -> None:
    policy = default_theory_of_mind_policy()
    assert policy.version == THEORY_OF_MIND_POLICY_VERSION
    assert policy.prior == 1.0
    assert policy.behavior_weight == 4.0
    assert policy.testimony_weight == 2.0
    assert policy.trust_high_multiplier == 2.0
    assert policy.trust_low_multiplier == 0.5
    assert policy.emotion_multiplier == 2.0
    assert policy.future_discount == 0.5
    assert policy.action_threshold == 0.55
    assert policy.max_hypotheses == 64
    assert policy.max_history == 32
    assert policy.allow_provider is False
    assert default_theory_of_mind_policy(allow_provider=True).allow_provider is True


def test_behavior_mass_stays_above_threshold_after_two_counters() -> None:
    one = confidence_from_masses(4.0, 0.0, prior=1.0)
    two = confidence_from_masses(4.0, 2.0, prior=1.0)
    three = confidence_from_masses(4.0, 3.0, prior=1.0)
    assert one == pytest.approx(0.8)
    assert abs(two - (4.0 / 7.0)) < _EFFECT_QUANTUM
    assert two > 0.55
    assert three == pytest.approx(0.5)
    assert three < 0.55
    hypothesis = _hunger()
    assert hypothesis.confidence == pytest.approx(0.8)


def test_hypothesis_id_is_stable_sha256_without_builtin_hash() -> None:
    left = mind_hypothesis_id_for(
        owner_id=_OWNER,
        subject_id=_SUBJECT,
        aspect=MindAspect.NEED,
        atoms=(_atom(MindSlot.NEED_KIND, "hunger"),),
    )
    right = _hunger().hypothesis_id
    assert left == right
    assert left.startswith("mh-")
    assert len(left) == 3 + 48
    assert "hunger" not in left


def test_constructors_reject_invalid_hypotheses(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR, logger=_LOGGER)
    with pytest.raises(ValueError, match="empty_atoms"):
        MindHypothesis(
            owner_id=_OWNER,
            subject_id=_SUBJECT,
            aspect=MindAspect.NEED,
            atoms=(),
            support=1.0,
            counter=0.0,
            evidence_ids=(),
            counter_evidence_ids=(),
            channel=MindEvidenceChannel.OBSERVED_BEHAVIOR,
        )
    with pytest.raises(ValueError, match="duplicate_slot"):
        MindHypothesis(
            owner_id=_OWNER,
            subject_id=_SUBJECT,
            aspect=MindAspect.NEED,
            atoms=(
                _atom(MindSlot.NEED_KIND, "hunger"),
                _atom(MindSlot.NEED_KIND, "thirst"),
            ),
            support=1.0,
            counter=0.0,
            evidence_ids=(),
            counter_evidence_ids=(),
            channel=MindEvidenceChannel.OBSERVED_BEHAVIOR,
        )
    with pytest.raises(ValueError, match="not_finite"):
        MindHypothesis(
            owner_id=_OWNER,
            subject_id=_SUBJECT,
            aspect=MindAspect.NEED,
            atoms=(_atom(MindSlot.NEED_KIND, "hunger"),),
            support=math.nan,
            counter=0.0,
            evidence_ids=(),
            counter_evidence_ids=(),
            channel=MindEvidenceChannel.OBSERVED_BEHAVIOR,
        )
    with pytest.raises(ValueError, match="self_subject"):
        MindHypothesis(
            owner_id=AgentId("body-alice"),
            subject_id=EntityId("body-alice"),
            aspect=MindAspect.NEED,
            atoms=(_atom(MindSlot.NEED_KIND, "hunger"),),
            support=1.0,
            counter=0.0,
            evidence_ids=(),
            counter_evidence_ids=(),
            channel=MindEvidenceChannel.OBSERVED_BEHAVIOR,
        )
    with pytest.raises(ValueError, match="nested_mind_rejected"):
        MindHypothesis(
            owner_id=_OWNER,
            subject_id=_SUBJECT,
            aspect=MindAspect.BELIEF,
            atoms=(_atom(MindSlot.CLAIM_PREDICATE, "wants"),),
            support=1.0,
            counter=0.0,
            evidence_ids=(),
            counter_evidence_ids=(),
            channel=MindEvidenceChannel.COMMUNICATION,
        )
    with pytest.raises(ValueError, match="unknown_enum"):
        MindAtom(slot=MindSlot.NEED_KIND, value="curious")
    with pytest.raises(ValueError, match="owner_mismatch"):
        TheoryOfMind(
            owner_id=_OWNER,
            hypotheses=(
                MindHypothesis(
                    owner_id=AgentId("agent-other"),
                    subject_id=_SUBJECT,
                    aspect=MindAspect.NEED,
                    atoms=(_atom(MindSlot.NEED_KIND, "hunger"),),
                    support=1.0,
                    counter=0.0,
                    evidence_ids=(),
                    counter_evidence_ids=(),
                    channel=MindEvidenceChannel.OBSERVED_BEHAVIOR,
                ),
            ),
        )
    assert "theory_of_mind_validation_failed" in caplog.text
    assert "reason_code=empty_atoms" in caplog.text
    assert "hunger" not in caplog.text


def test_construction_logs_owner_policy_and_count(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    model = TheoryOfMind(owner_id=_OWNER, hypotheses=(_hunger(),))
    assert model.cue_cursor == ()
    assert model.last_tick is None
    assert "theory_of_mind_constructed" in caplog.text
    assert "owner_id=agent-alice" in caplog.text
    assert f"policy_version={THEORY_OF_MIND_POLICY_VERSION}" in caplog.text
    assert "hypothesis_count=1" in caplog.text
    assert "hunger" not in caplog.text


def test_empty_model_and_enabled_config_build_default_policy() -> None:
    empty = empty_theory_of_mind(_OWNER)
    assert empty.hypotheses == ()
    passthrough = CognitionLoopConfig()
    assert passthrough.theory_of_mind_mode is CognitionTheoryOfMindMode.PASSTHROUGH
    assert passthrough.theory_of_mind_policy is None
    enabled = CognitionLoopConfig(theory_of_mind_mode=CognitionTheoryOfMindMode.ENABLED)
    assert enabled.theory_of_mind_policy == default_theory_of_mind_policy()
    assert enabled.theory_of_mind_policy is not None
    assert enabled.theory_of_mind_policy.allow_provider is False
    custom = TheoryOfMindPolicy(allow_provider=True)
    configured = CognitionLoopConfig(
        theory_of_mind_mode=CognitionTheoryOfMindMode.ENABLED,
        theory_of_mind_policy=custom,
    )
    assert configured.theory_of_mind_policy.allow_provider is True


def test_drop_record_may_carry_zero_deltas() -> None:
    from agents.cognition.theory_of_mind import MindUpdateRecord

    record = MindUpdateRecord(
        tick=1,
        hypothesis_id="mh-drop",
        support_delta=0.0,
        counter_delta=0.0,
        channel=MindEvidenceChannel.COMMUNICATION,
        reason=MindUpdateReason.DROP,
    )
    assert record.reason is MindUpdateReason.DROP
    with pytest.raises(ValueError, match="empty_delta"):
        MindUpdateRecord(
            tick=1,
            hypothesis_id="mh-drop",
            support_delta=0.0,
            counter_delta=0.0,
            channel=MindEvidenceChannel.COMMUNICATION,
            reason=MindUpdateReason.SUPPORT,
        )


def _observed_self() -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId("body-alice"),
        location_id=EntityId("loc-camp"),
        health=Health(80.0),
        hunger=Hunger(0.0),
        thirst=Thirst(0.0),
        fatigue=Fatigue(0.0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(5),
    )


def _body(entity_id: str, *, health: CoarseHealth = CoarseHealth.STABLE) -> VisibleBody:
    return VisibleBody(
        entity_id=EntityId(entity_id),
        life_status=LifeStatus.ALIVE,
        coarse_health=health,
    )


def _occurrence(
    kind: str,
    *,
    tick: int,
    actor: str,
    other: str | None = None,
    destination: str | None = None,
    event: str,
    role: ObservationAudienceRole = ObservationAudienceRole.WITNESS,
) -> ObservedOccurrence:
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=max(tick - 1, 0),
            source_event_id=EventId(event),
        ),
        kind=kind,
        audience_role=role,
        actor_id=EntityId(actor),
        other_entity_id=None if other is None else EntityId(other),
        destination_id=None if destination is None else EntityId(destination),
        success=True,
    )


def _watch(
    *,
    tick: int,
    occurrences: tuple[ObservedOccurrence, ...] = (),
    bodies: tuple[str, ...] = ("body-bob",),
    communications: tuple[ObservedCommunication, ...] = (),
) -> Observation:
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-alice"),
        revision=WorldRevision(tick),
        tick=tick,
        self_body=_observed_self(),
        visible_bodies=tuple(_body(item) for item in sorted(bodies)),
        occurrences=occurrences,
        communications=communications,
    )


def _help_bias(
    model: TheoryOfMind,
) -> tuple[tuple[tuple[str, float], ...], str, str]:
    from agents.cognition.theory_of_mind import mind_direction_deltas

    deltas, status, direction, _confidence, _hypothesis_id, _aspect = (
        mind_direction_deltas(
            model,
            candidates=(("help-bob", "help", "body-bob"), ("wait", "wait", None)),
            visible_destinations=frozenset(),
            visible_entities=frozenset({"body-bob"}),
        )
    )
    return deltas, status, direction


def _need(model: TheoryOfMind, kind: str) -> MindHypothesis:
    matches = [
        item
        for item in model.hypotheses
        if item.aspect is MindAspect.NEED
        and any(
            atom.slot is MindSlot.NEED_KIND and atom.value == kind
            for atom in item.atoms
        )
    ]
    assert len(matches) == 1
    return matches[0]


def test_witnessed_eat_persists_through_two_mild_counters(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    policy = default_theory_of_mind_policy()
    owner = AgentId("agent-alice")
    model = empty_theory_of_mind(owner)
    eaten = _watch(
        tick=1,
        occurrences=(_occurrence("eat", tick=1, actor="body-bob", event="evt-eat"),),
    )
    model = update_theory_of_mind(
        model,
        cues_from_observation(eaten, owner_id=owner, model=model, policy=policy),
        policy,
    )
    hunger = _need(model, "hunger")
    assert hunger.confidence == pytest.approx(0.8)
    assert hunger.subject_id == EntityId("body-bob")
    for tick, event in ((2, "evt-wait-2"), (3, "evt-wait-3")):
        watched = _watch(
            tick=tick,
            occurrences=(
                _occurrence("wait", tick=tick, actor="body-bob", event=event),
            ),
        )
        model = update_theory_of_mind(
            model,
            cues_from_observation(watched, owner_id=owner, model=model, policy=policy),
            policy,
        )
    hunger = _need(model, "hunger")
    assert hunger.confidence == pytest.approx(4.0 / 7.0, abs=_EFFECT_QUANTUM)
    assert hunger.confidence > policy.action_threshold
    stayed, stayed_status, stayed_direction = _help_bias(model)
    assert stayed_status == "applied"
    assert stayed_direction == "help"
    assert dict(stayed)["help-bob"] == pytest.approx(hunger.confidence)
    third = _watch(
        tick=4,
        occurrences=(
            _occurrence("wait", tick=4, actor="body-bob", event="evt-wait-4"),
        ),
    )
    model = update_theory_of_mind(
        model,
        cues_from_observation(third, owner_id=owner, model=model, policy=policy),
        policy,
    )
    assert _need(model, "hunger").confidence == pytest.approx(0.5)
    stopped, stopped_status, stopped_direction = _help_bias(model)
    assert stopped == ()
    assert stopped_status == "none"
    assert stopped_direction == ""
    assert "aspect=need" in caplog.text
    assert "reason_code=support" in caplog.text
    assert "resulting_hunger" not in caplog.text


def test_testimony_weight_follows_trust_and_drops_multi_hop() -> None:
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
    from world.communications import origin_utterance, retell_utterance

    policy = default_theory_of_mind_policy()
    owner = AgentId("agent-alice")
    speaker = EntityId("body-bob")

    def told(event: str, utterance: object) -> Observation:
        return _watch(
            tick=1,
            communications=(
                ObservedCommunication(
                    provenance=ObservationProvenance(
                        source_kind=ObservationSourceKind.COMMUNICATION,
                        source_tick=0,
                        source_event_id=EventId(event),
                    ),
                    speaker_id=speaker,
                    listener_id=EntityId("body-alice"),
                    utterance=utterance,  # type: ignore[arg-type]
                    action_kind="tell",
                ),
            ),
        )

    food = origin_utterance(text="note", speaker_id=speaker, concepts=("food",))
    stranger = update_theory_of_mind(
        empty_theory_of_mind(owner),
        cues_from_observation(told("evt-food", food), owner_id=owner, policy=policy),
        policy,
    )
    assert _need(stranger, "hunger").confidence == pytest.approx(2.0 / 3.0)

    def profile(trust: float) -> DirectedRelationshipProfile:
        policy_ref = RelationshipPolicyRef(policy_id="rel-v1", version="1")
        return DirectedRelationshipProfile(
            relationship_id=RelationshipId("rel-bob"),
            source_id=owner,
            target_id=AgentId("body-bob"),
            dimensions=(
                RelationshipDimensionState(
                    dimension=RelationshipDimension.TRUST,
                    value=trust,
                    confidence=RelationshipConfidence(
                        confidence=0.9,
                        support_mass=0.9,
                        contradiction_mass=0.0,
                    ),
                    evidence=(),
                    logical_tick=1,
                    policy=policy_ref,
                ),
            ),
            activation_state=RelationshipActivationState.ACTIVE,
            current_revision_id=RelationshipRevisionId("rrev-1"),
            revision_ordinal=1,
            created_tick=1,
            updated_tick=1,
            policy=policy_ref,
        )

    trusted = update_theory_of_mind(
        empty_theory_of_mind(owner),
        cues_from_observation(
            told("evt-food-trust", food),
            owner_id=owner,
            profiles=(profile(0.8),),
            policy=policy,
        ),
        policy,
    )
    assert _need(trusted, "hunger").confidence == pytest.approx(0.8)
    distrusted = update_theory_of_mind(
        empty_theory_of_mind(owner),
        cues_from_observation(
            told("evt-food-low", food),
            owner_id=owner,
            profiles=(profile(-0.2),),
            policy=policy,
        ),
        policy,
    )
    assert _need(distrusted, "hunger").confidence == pytest.approx(0.5)
    retold = retell_utterance(
        prior=retell_utterance(
            prior=food,
            speaker_id=EntityId("body-carol"),
            communication_id="comm-hop-1",
        ),
        speaker_id=EntityId("body-dave"),
        communication_id="comm-hop-2",
    )
    hop_watch = _watch(
        tick=1,
        bodies=("body-bob", "body-dave"),
        communications=(
            ObservedCommunication(
                provenance=ObservationProvenance(
                    source_kind=ObservationSourceKind.COMMUNICATION,
                    source_tick=0,
                    source_event_id=EventId("evt-hop"),
                ),
                speaker_id=EntityId("body-dave"),
                listener_id=EntityId("body-alice"),
                utterance=retold,
                action_kind="tell",
            ),
        ),
    )
    dropped = update_theory_of_mind(
        empty_theory_of_mind(owner),
        cues_from_observation(hop_watch, owner_id=owner, policy=policy),
        policy,
    )
    assert dropped.hypotheses == ()


def test_bystander_attack_does_not_invent_a_target() -> None:
    policy = default_theory_of_mind_policy()
    owner = AgentId("agent-alice")
    watched = _watch(
        tick=1,
        bodies=("body-bob",),
        occurrences=(
            _occurrence(
                "attack",
                tick=1,
                actor="body-bob",
                event="evt-attack",
                role=ObservationAudienceRole.BYSTANDER,
            ),
        ),
    )
    model = update_theory_of_mind(
        empty_theory_of_mind(owner),
        cues_from_observation(watched, owner_id=owner, policy=policy),
        policy,
    )
    relationships = [
        item for item in model.hypotheses if item.aspect is MindAspect.RELATIONSHIP
    ]
    assert relationships == []
    assert all(
        all(atom.value != "body-carol" for atom in item.atoms)
        for item in model.hypotheses
    )


def test_non_observation_is_rejected() -> None:
    from world._state import WorldState
    from world.models import AgentBody

    with pytest.raises(TypeError):
        cues_from_observation(
            object.__new__(WorldState),
            owner_id=AgentId("agent-alice"),
        )
    with pytest.raises(TypeError):
        cues_from_observation(
            object.__new__(AgentBody),
            owner_id=AgentId("agent-alice"),
        )


def test_updater_source_excludes_private_authority_types() -> None:
    from pathlib import Path

    text = Path("src/agents/cognition/theory_of_mind.py").read_text(encoding="utf-8")
    for forbidden in (
        "WorldState",
        "AgentBody",
        "GoalBoard",
        "AgentEmotionalState",
        "PhysicalRules",
    ):
        assert forbidden not in text


def test_false_hunger_does_not_read_the_body() -> None:
    from dataclasses import replace

    from tests.simulation_helpers import alive_body
    from world.values import Hunger

    body = replace(alive_body("body-bob", location_id="loc-camp"), hunger=Hunger(12))
    before = body.hunger
    owner = AgentId("agent-alice")
    policy = default_theory_of_mind_policy()
    watched = _watch(
        tick=1,
        occurrences=(_occurrence("eat", tick=1, actor="body-bob", event="evt-eat"),),
    )
    model = update_theory_of_mind(
        empty_theory_of_mind(owner),
        cues_from_observation(watched, owner_id=owner, policy=policy),
        policy,
    )
    hunger = _need(model, "hunger")
    assert body.hunger == before
    assert body.hunger.value == 12
    assert "Hunger" not in repr(hunger)
    assert "Goal" not in repr(hunger)
    assert all(atom.value != "12" for atom in hunger.atoms)
    assert all(
        atom.value not in {"weather", "rain"} for atom in hunger.atoms
    )
    assert not hasattr(model, "empirical_action")


def test_food_ask_is_unreferenced_and_distrust_does_not_steer() -> None:
    from agents.cognition.communication import DeterministicSocialMessagePolicy
    from agents.cognition.models import DecisionMetadata, RetrievedMemoryContext
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
    from world.actions import Ask
    from world.communications import CommunicationSourceBasis, origin_utterance

    policy = default_theory_of_mind_policy()
    owner = AgentId("agent-alice")
    speaker = EntityId("body-bob")
    food = origin_utterance(text="note", speaker_id=speaker, concepts=("food",))
    watched = _watch(
        tick=1,
        bodies=("body-ann", "body-bob"),
        communications=(
            ObservedCommunication(
                provenance=ObservationProvenance(
                    source_kind=ObservationSourceKind.COMMUNICATION,
                    source_tick=0,
                    source_event_id=EventId("evt-food"),
                ),
                speaker_id=speaker,
                listener_id=EntityId("body-alice"),
                utterance=food,
                action_kind="tell",
            ),
        ),
    )
    model = update_theory_of_mind(
        empty_theory_of_mind(owner),
        cues_from_observation(watched, owner_id=owner, policy=policy),
        policy,
    )
    assert _need(model, "hunger").confidence == pytest.approx(2.0 / 3.0)
    assert "note" not in repr(model)
    memory = RetrievedMemoryContext(
        owner_id=owner,
        memory_ids=(),
        belief_ids=(),
        confidence=1.0,
        decision_metadata=DecisionMetadata(candidate_count=0),
    )
    messages = DeterministicSocialMessagePolicy()
    decision = messages.select(
        owner_id=owner,
        speaker_id=EntityId("body-alice"),
        observation=watched,
        memory=memory,
        mind=model,
    )
    assert decision is not None
    assert type(decision.command) is Ask
    assert decision.command.recipient_id == EntityId("body-bob")
    assert decision.command.utterance.content.concepts == ("food",)
    assert (
        decision.command.utterance.declared.source_basis
        is CommunicationSourceBasis.UNREFERENCED
    )
    assert decision.sender_confidence == pytest.approx(
        _need(model, "hunger").confidence
    )
    kept = messages.select(
        owner_id=owner,
        speaker_id=EntityId("body-alice"),
        observation=watched,
        memory=memory,
        preferred_recipient_id=EntityId("body-ann"),
        mind=model,
    )
    assert kept is not None
    assert kept.command.recipient_id == EntityId("body-ann")
    policy_ref = RelationshipPolicyRef(policy_id="rel-v1", version="1")
    low_trust = DirectedRelationshipProfile(
        relationship_id=RelationshipId("rel-bob"),
        source_id=owner,
        target_id=AgentId("body-bob"),
        dimensions=(
            RelationshipDimensionState(
                dimension=RelationshipDimension.TRUST,
                value=-0.2,
                confidence=RelationshipConfidence(
                    confidence=0.9,
                    support_mass=0.9,
                    contradiction_mass=0.0,
                ),
                evidence=(),
                logical_tick=1,
                policy=policy_ref,
            ),
        ),
        activation_state=RelationshipActivationState.ACTIVE,
        current_revision_id=RelationshipRevisionId("rrev-1"),
        revision_ordinal=1,
        created_tick=1,
        updated_tick=1,
        policy=policy_ref,
    )
    distrusted = update_theory_of_mind(
        empty_theory_of_mind(owner),
        cues_from_observation(
            watched, owner_id=owner, profiles=(low_trust,), policy=policy
        ),
        policy,
    )
    assert _need(distrusted, "hunger").confidence == pytest.approx(0.5)
    baseline = messages.select(
        owner_id=owner,
        speaker_id=EntityId("body-alice"),
        observation=watched,
        memory=memory,
    )
    unchanged = messages.select(
        owner_id=owner,
        speaker_id=EntityId("body-alice"),
        observation=watched,
        memory=memory,
        mind=distrusted,
    )
    assert baseline is not None and unchanged is not None
    assert unchanged.command == baseline.command


def test_move_exit_and_false_attack_choose_direction() -> None:
    from agents.cognition.theory_of_mind import mind_direction_deltas
    from world.communications import CommunicationRelation, origin_utterance

    policy = default_theory_of_mind_policy()
    owner = AgentId("agent-alice")
    moved = _watch(
        tick=1,
        occurrences=(
            _occurrence(
                "move",
                tick=1,
                actor="body-bob",
                destination="loc-north",
                event="evt-move",
            ),
        ),
    )
    model = update_theory_of_mind(
        empty_theory_of_mind(owner),
        cues_from_observation(moved, owner_id=owner, policy=policy),
        policy,
        owner_entity_id=moved.observer_id,
    )
    goal = next(item for item in model.hypotheses if item.aspect is MindAspect.GOAL)
    assert any(atom.value == "reach_place" for atom in goal.atoms)
    candidates = (
        ("move-north", "move", "loc-north"),
        ("help-bob", "help", "body-bob"),
    )
    _with_exit, status, direction, *_rest = mind_direction_deltas(
        model,
        candidates=candidates,
        visible_destinations=frozenset({"loc-north"}),
        visible_entities=frozenset({"body-bob"}),
    )
    assert status == "applied"
    assert direction == "move"
    _without_exit, closed_status, closed_direction, *_rest = mind_direction_deltas(
        model,
        candidates=candidates,
        visible_destinations=frozenset(),
        visible_entities=frozenset({"body-bob"}),
    )
    assert closed_status == "applied"
    assert closed_direction == "help"
    attacked = _watch(
        tick=1,
        occurrences=(
            _occurrence(
                "attack",
                tick=1,
                actor="body-bob",
                other="body-alice",
                event="evt-attack",
            ),
        ),
    )
    threatened = update_theory_of_mind(
        empty_theory_of_mind(owner),
        cues_from_observation(attacked, owner_id=owner, policy=policy),
        policy,
        owner_entity_id=attacked.observer_id,
    )
    future = next(
        item
        for item in threatened.hypotheses
        if item.aspect is MindAspect.FUTURE_ACTION
    )
    stored = future.confidence
    deltas, flee_status, flee_direction, *_rest = mind_direction_deltas(
        threatened,
        candidates=(
            ("flee", "flee", "body-bob"),
            ("attack", "attack", "body-bob"),
            ("wait", "wait", None),
        ),
        visible_destinations=frozenset(),
        visible_entities=frozenset({"body-bob", "body-alice"}),
    )
    assert flee_status == "applied"
    assert flee_direction == "flee"
    assert dict(deltas)["attack"] < 0
    assert future.confidence == stored
    assert not hasattr(threatened, "empirical_action")
    lie = origin_utterance(
        text="note",
        speaker_id=EntityId("body-bob"),
        relations=(
            CommunicationRelation(
                subject="body-bob",
                predicate="distrusts",
                object="body-carol",
            ),
        ),
    )
    told = _watch(
        tick=1,
        bodies=("body-bob", "body-carol"),
        communications=(
            ObservedCommunication(
                provenance=ObservationProvenance(
                    source_kind=ObservationSourceKind.COMMUNICATION,
                    source_tick=0,
                    source_event_id=EventId("evt-carol"),
                ),
                speaker_id=EntityId("body-bob"),
                listener_id=EntityId("body-alice"),
                utterance=lie,
                action_kind="tell",
            ),
        ),
    )
    social = update_theory_of_mind(
        empty_theory_of_mind(owner),
        cues_from_observation(told, owner_id=owner, policy=policy),
        policy,
    )
    relationship = next(
        item for item in social.hypotheses if item.aspect is MindAspect.RELATIONSHIP
    )
    assert any(atom.value == "negative" for atom in relationship.atoms)
    assert any(atom.value == "body-carol" for atom in relationship.atoms)
    from agents.cognition.communication import DeterministicSocialMessagePolicy
    from agents.cognition.models import DecisionMetadata, RetrievedMemoryContext

    decision = DeterministicSocialMessagePolicy().select(
        owner_id=owner,
        speaker_id=EntityId("body-alice"),
        observation=told,
        memory=RetrievedMemoryContext(
            owner_id=owner,
            memory_ids=(),
            belief_ids=(),
            confidence=1.0,
            decision_metadata=DecisionMetadata(candidate_count=0),
        ),
        mind=social,
    )
    assert decision is not None
    assert decision.command.recipient_id != EntityId("body-carol")
    nested = origin_utterance(
        text="note",
        speaker_id=EntityId("body-bob"),
        relations=(
            CommunicationRelation(
                subject="body-bob",
                predicate="believes",
                object="hungry",
            ),
        ),
    )
    nested_watch = _watch(
        tick=1,
        communications=(
            ObservedCommunication(
                provenance=ObservationProvenance(
                    source_kind=ObservationSourceKind.COMMUNICATION,
                    source_tick=0,
                    source_event_id=EventId("evt-nested"),
                ),
                speaker_id=EntityId("body-bob"),
                listener_id=EntityId("body-alice"),
                utterance=nested,
                action_kind="tell",
            ),
        ),
    )
    rejected = cues_from_observation(nested_watch, owner_id=owner, policy=policy)
    assert any(cue.drop_code == "nested_mind_rejected" for cue in rejected)
    stored_nested = update_theory_of_mind(
        empty_theory_of_mind(owner), rejected, policy
    )
    assert stored_nested.hypotheses == ()
    with pytest.raises(ValueError, match="nested_mind_rejected"):
        MindHypothesis(
            owner_id=owner,
            subject_id=EntityId("body-bob"),
            aspect=MindAspect.BELIEF,
            atoms=(_atom(MindSlot.CLAIM_PREDICATE, "wants"),),
            support=1.0,
            counter=0.0,
            evidence_ids=("prov-1",),
            counter_evidence_ids=(),
            channel=MindEvidenceChannel.COMMUNICATION,
        )
