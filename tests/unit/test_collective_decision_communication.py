"""Six collective-decision acts over existing recipient-scoped speech."""

from __future__ import annotations

import pytest

from agents.cognition.collective_decision_communication import (
    COLLECTIVE_DECISION_PREDICATES,
    ParsedCollectiveRelation,
    collective_decision_communicate_utterance,
    encode_collective_decision_relation,
    parse_collective_decision_relation,
    policy_marker_relation,
)
from agents.cognition.collective_decisions import (
    CollectiveAct,
    CollectiveTopic,
    apply_collective_decision_update,
    collective_context_key,
    collective_proposal_ref,
    empty_collective_decision_ledger,
)
from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.models import AgentId
from world.actions import Talk, Wait
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    Observation,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
    ObservedSelf,
)
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)

_OWNER = AgentId("ada")
_BEN = AgentId("ben")
_REF = "c" * 64
_CONTEXT = "a" * 16


def _identity(owner: AgentId = _OWNER) -> OwnerSafeSocialIdentity:
    other = _BEN if owner == _OWNER else _OWNER
    other_body = "body-ben" if other == _BEN else "body-ada"
    owner_body = "body-ada" if owner == _OWNER else "body-ben"
    return OwnerSafeSocialIdentity(
        owner_id=owner,
        owner_entity_id=EntityId(owner_body),
        counterparts=(
            CounterpartBinding(agent_id=other, entity_id=EntityId(other_body)),
        ),
    )


def _self() -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId("body-ada"),
        location_id=EntityId("clearing"),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _observation(
    *,
    tick: int,
    communications: tuple[ObservedCommunication, ...] = (),
) -> Observation:
    return Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId("body-ada"),
        revision=WorldRevision(1),
        tick=tick,
        self_body=_self(),
        occurrences=(),
        communications=communications,
    )


def _talk(relations: tuple[CommunicationRelation, ...]) -> Talk:
    return Talk(
        recipient_id=EntityId("body-ben"),
        utterance=origin_utterance(
            text="hello",
            speaker_id=EntityId("body-ada"),
            communication_id="talk-1",
            relations=relations,
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )


def _message(
    *,
    tick: int,
    speaker: str,
    root: str,
    relations: tuple[CommunicationRelation, ...],
) -> ObservedCommunication:
    utterance = origin_utterance(
        text="collective",
        speaker_id=EntityId(speaker),
        communication_id=root,
        relations=relations,
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    return ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=max(tick - 1, 0),
            source_event_id=EventId(f"event-{root}"),
        ),
        speaker_id=EntityId(speaker),
        listener_id=EntityId("body-ada"),
        utterance=utterance,
        action_kind="talk",
    )


def _ledger_with_proposal() -> object:
    context = collective_context_key(_observation(tick=1))
    ref = collective_proposal_ref(
        _OWNER,
        originator_id=_BEN,
        topic=CollectiveTopic.COLLECTIVE_PROJECT,
        context_key=context,
        inception_tick=1,
        inception_lineage="proposal",
    )
    relation = encode_collective_decision_relation(
        act=CollectiveAct.PROPOSE,
        topic=CollectiveTopic.COLLECTIVE_PROJECT,
        proposal_ref=ref,
        revision=0,
        action_token="start_project",
        target_token="field",
        terms=("dig_channel",),
        window_first_tick=1,
        window_last_tick=9,
        context_key=context,
    )
    return apply_collective_decision_update(
        _observation(
            tick=1,
            communications=(
                _message(
                    tick=1,
                    speaker="body-ben",
                    root="proposal-root",
                    relations=(relation,),
                ),
            ),
        ),
        _identity(),
        empty_collective_decision_ledger(_OWNER),
    )


def test_all_six_acts_round_trip() -> None:
    relations = (
        encode_collective_decision_relation(
            act=CollectiveAct.PROPOSE,
            topic=CollectiveTopic.MIGRATION,
            proposal_ref=_REF,
            revision=2,
            action_token="move",
            target_token="north",
            terms=("together",),
            window_first_tick=4,
            window_last_tick=9,
            context_key=_CONTEXT,
        ),
        encode_collective_decision_relation(
            act=CollectiveAct.SUPPORT,
            topic=CollectiveTopic.MIGRATION,
            proposal_ref=_REF,
            revision=2,
        ),
        encode_collective_decision_relation(
            act=CollectiveAct.OPPOSE,
            topic=CollectiveTopic.MIGRATION,
            proposal_ref=_REF,
            revision=2,
        ),
        encode_collective_decision_relation(
            act=CollectiveAct.DELEGATE,
            topic=CollectiveTopic.MIGRATION,
            proposal_ref=_REF,
            revision=2,
            delegate_entity=EntityId("body-ben"),
        ),
        encode_collective_decision_relation(
            act=CollectiveAct.WITHDRAW_SUPPORT,
            topic=CollectiveTopic.MIGRATION,
            proposal_ref=_REF,
            revision=2,
            retract_kind="position",
            retract_id="d" * 64,
        ),
        encode_collective_decision_relation(
            act=CollectiveAct.COORDINATE,
            topic=CollectiveTopic.MIGRATION,
            proposal_ref=_REF,
            revision=2,
            action_token="move",
            target_token="north",
        ),
    )
    parsed = [parse_collective_decision_relation(item) for item in relations]
    assert [item.act for item in parsed if item is not None] == list(CollectiveAct)
    propose = parsed[0]
    assert propose is not None
    assert propose.terms == ("together",)
    assert propose.window_first_tick == 4
    assert propose.window_last_tick == 9
    delegate = parsed[3]
    assert delegate is not None
    assert delegate.delegate_entity == EntityId("body-ben")
    withdraw = parsed[4]
    assert withdraw is not None
    assert withdraw.retract_kind == "position"


def test_ordinary_conversation_and_marker_are_unaffected() -> None:
    assert (
        parse_collective_decision_relation(
            CommunicationRelation(subject="weather", predicate="talk", object="rain")
        )
        is None
    )
    marker = policy_marker_relation()
    from agents.cognition.collective_decisions import (
        COLLECTIVE_DECISION_POLICY_VERSION,
    )

    assert marker.object == COLLECTIVE_DECISION_POLICY_VERSION
    assert parse_collective_decision_relation(marker) is None


def test_malformed_relations_are_rejected_without_raising() -> None:
    for relation in (
        CommunicationRelation(
            subject="migration", predicate="collective_support", object="x|0|-"
        ),
        CommunicationRelation(
            subject="migration",
            predicate="collective_propose",
            object=f"{_REF}|0|move",
        ),
        CommunicationRelation(
            subject="not_a_topic",
            predicate="collective_support",
            object=f"{_REF}|0|-",
        ),
        CommunicationRelation(
            subject="migration",
            predicate="collective_delegate",
            object=f"{_REF}|0|",
        ),
        CommunicationRelation(
            subject="migration",
            predicate="collective_withdraw",
            object=f"{_REF}|0|vote|{'d' * 64}",
        ),
    ):
        assert parse_collective_decision_relation(relation) is None
    with pytest.raises(TypeError):
        parse_collective_decision_relation(object())  # type: ignore[arg-type]


def test_policy_marker_and_relation_cap() -> None:
    ledger = _ledger_with_proposal()
    command = _talk((policy_marker_relation(),))
    stamped = collective_decision_communicate_utterance(
        command,
        owner_id=_OWNER,
        tick=2,
        observation=_observation(tick=2),
        identity=_identity(),
        ledger=ledger,
        mode=_Mode.DETERMINISTIC,
    )
    assert isinstance(stamped, Talk)
    relations = stamped.utterance.content.relations
    assert len(relations) <= 32
    parsed = [parse_collective_decision_relation(item) for item in relations]
    assert any(
        item is not None and item.act is CollectiveAct.SUPPORT for item in parsed
    )


class _Mode:
    DETERMINISTIC = type("Mode", (), {"value": "deterministic"})()
    DISABLED = type("Mode", (), {"value": "disabled"})()


def test_disabled_mode_is_a_strict_passthrough() -> None:
    command = _talk(())
    ledger = _ledger_with_proposal()
    result = collective_decision_communicate_utterance(
        command,
        owner_id=_OWNER,
        tick=2,
        observation=_observation(tick=2),
        identity=_identity(),
        ledger=ledger,
        mode=_Mode.DISABLED,
    )
    assert result is command


def test_stamped_speech_produces_fresh_receiver_evidence() -> None:
    owner_ledger = _ledger_with_proposal()
    proposal = owner_ledger.proposals[0]
    command = _talk(())
    stamped = collective_decision_communicate_utterance(
        command,
        owner_id=_OWNER,
        tick=2,
        observation=_observation(tick=2),
        identity=_identity(),
        ledger=owner_ledger,
        mode=_Mode.DETERMINISTIC,
    )
    assert isinstance(stamped, Talk)
    delivered = _message(
        tick=3,
        speaker="body-ada",
        root="delivered-support",
        relations=stamped.utterance.content.relations,
    )
    receiver_ledger = apply_collective_decision_update(
        _observation(tick=3, communications=(delivered,)),
        _identity(_BEN),
        empty_collective_decision_ledger(_BEN),
    )
    assert receiver_ledger.positions == ()
    assert "unknown_proposal" in receiver_ledger.notices
    owner_seen_own = apply_collective_decision_update(
        _observation(tick=3, communications=(delivered,)),
        _identity(_OWNER),
        owner_ledger,
    )
    assert len(owner_seen_own.positions) == 1
    assert owner_seen_own.positions[0].proposal_ref == proposal.proposal_ref


def test_attempt_without_delivery_observation_is_not_confirmed() -> None:
    ledger = _ledger_with_proposal()
    command = _talk(())
    stamped = collective_decision_communicate_utterance(
        command,
        owner_id=_OWNER,
        tick=2,
        observation=_observation(tick=2),
        identity=_identity(),
        ledger=ledger,
        mode=_Mode.DETERMINISTIC,
    )
    assert isinstance(stamped, Talk)
    assert ledger.positions == ()
    assert "collective_policy" in {
        item.predicate for item in stamped.utterance.content.relations
    }


def test_non_communication_command_is_untouched() -> None:
    ledger = _ledger_with_proposal()
    command = Wait()
    stamped = collective_decision_communicate_utterance(
        command,
        owner_id=_OWNER,
        tick=2,
        observation=_observation(tick=2),
        identity=_identity(),
        ledger=ledger,
        mode=_Mode.DETERMINISTIC,
    )
    assert stamped is command


def test_actor_is_verified_speaker_not_declared_payload() -> None:
    ledger = _ledger_with_proposal()
    relation = encode_collective_decision_relation(
        act=CollectiveAct.SUPPORT,
        topic=CollectiveTopic.COLLECTIVE_PROJECT,
        proposal_ref=ledger.proposals[0].proposal_ref,
        revision=0,
    )
    observed = _message(
        tick=2,
        speaker="body-ben",
        root="forged",
        relations=(relation,),
    )
    updated = apply_collective_decision_update(
        _observation(tick=2, communications=(observed,)),
        _identity(),
        ledger,
    )
    assert updated.positions[0].actor_id == _BEN


def test_predicates_are_namespaced_and_complete() -> None:
    assert set(COLLECTIVE_DECISION_PREDICATES) == set(CollectiveAct)
    assert all(
        predicate.startswith("collective_")
        for predicate in COLLECTIVE_DECISION_PREDICATES.values()
    )


def test_parsed_relation_type_is_exported() -> None:
    assert ParsedCollectiveRelation.__name__ == "ParsedCollectiveRelation"
