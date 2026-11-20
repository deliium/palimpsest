# mypy: ignore-errors

"""Attributed theory speech, support, and teaching in the owner tick."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition.competing_theories import (
    TheoryAccount,
    TheoryCitation,
    TheoryCitationKind,
    TheoryCitationPolarity,
    TheoryClaim,
    TheoryContext,
    TheorySpeechAct,
    TheoryStanceAction,
    TheoryStanceRequest,
    TheoryTargetKind,
    apply_theory_updates,
    empty_competing_theory_ledger,
    theory_claim_id,
)
from agents.cognition.competing_theory_communication import (
    TheoryMessage,
    attach_theory_message,
    decode_theory_message,
    encode_theory_message,
    message_from_claim,
)
from agents.cognition.competing_theory_policy import (
    advance_competing_theories,
    record_theory_outbound,
    select_theory_speech,
)
from world.actions import Talk, Tell
from world.communications import (
    CommunicationRelation,
    StructuredUtterance,
    origin_utterance,
    retell_utterance,
)
from world.environment import Season
from world.identifiers import AgentId, EntityId, EventId, WorldId, WorldRevision
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

pytestmark = pytest.mark.unit

_OWNER = AgentId("body-ada")
_SPEAKER = EntityId("body-ben")
_OTHER = EntityId("body-cara")
_WORLD = WorldId("world-1")


def _context() -> TheoryContext:
    return TheoryContext(TheoryTargetKind.SEASON, "clearing", "spring")


def _message(act: TheorySpeechAct = TheorySpeechAct.SUPPORT) -> TheoryMessage:
    return TheoryMessage(
        act=act,
        context=_context(),
        account=TheoryAccount.RECURRENCE,
        predicted_category="summer",
        cited_root="root-1" if act is TheorySpeechAct.TEACH else "",
        cited_polarity=(
            TheoryCitationPolarity.SUPPORTS if act is TheorySpeechAct.TEACH else None
        ),
    )


def _self() -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId(_OWNER.value),
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


def _speech(
    *,
    speaker: EntityId,
    listener: EntityId,
    message: TheoryMessage,
    event: str,
    tick: int,
    prior: StructuredUtterance | None = None,
    action_kind: str = "talk",
) -> ObservedCommunication:
    claim, context = encode_theory_message(message)
    if prior is None:
        utterance = origin_utterance(
            text="theory", speaker_id=speaker, communication_id=event
        )
    else:
        utterance = retell_utterance(
            prior=prior,
            speaker_id=speaker,
            communication_id=event,
        )
    utterance = StructuredUtterance(
        content=type(utterance.content)(
            text=utterance.content.text,
            relations=(claim, context),
        ),
        declared=utterance.declared,
    )
    return ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=tick,
            source_event_id=EventId(f"evt-{event}"),
        ),
        speaker_id=speaker,
        listener_id=listener,
        utterance=utterance,
        action_kind=action_kind,  # type: ignore[arg-type]
    )


def _observation(
    tick: int, communications: tuple[ObservedCommunication, ...]
) -> Observation:
    return Observation(
        world_id=_WORLD,
        observer_id=EntityId(_OWNER.value),
        revision=WorldRevision(tick),
        tick=tick,
        season=Season.SUMMER,
        self_body=_self(),
        communications=communications,
    )


def _known_ledger() -> object:
    ledger = empty_competing_theory_ledger(_OWNER)
    message = _message()
    claim = TheoryClaim(
        context=message.context,
        account=message.account,
        predicted_category=message.predicted_category,
        claim_id=message.claim_id,
        created_tick=1,
    )
    citation = TheoryCitation(
        claim_id=claim.claim_id,
        owner_tick=1,
        polarity=TheoryCitationPolarity.SUPPORTS,
        kind=TheoryCitationKind.OWN_SCORED_CASE,
        root_ref="root-1",
        provenance_ref="case-1",
    )
    return apply_theory_updates(ledger, tick=1, claims=(claim,), citations=(citation,))


def test_frame_round_trip_and_malformed_sibling() -> None:
    message = _message()
    claim, context = encode_theory_message(message)
    decoded = decode_theory_message(
        type(
            "U",
            (),
            {
                "utterance": type(
                    "E",
                    (),
                    {"content": type("C", (), {"relations": (claim, context)})()},
                )()
            },
        )()
    )
    assert decoded == message
    inverted = (context, claim)
    assert (
        decode_theory_message(
            type(
                "U",
                (),
                {
                    "utterance": type(
                        "E", (), {"content": type("C", (), {"relations": inverted})()}
                    )()
                },
            )()
        )
        is None
    )


def test_two_origin_speakers_are_not_repeated_retellings() -> None:
    first = _speech(
        speaker=_SPEAKER,
        listener=EntityId(_OWNER.value),
        message=_message(),
        event="e1",
        tick=2,
    )
    retold = _speech(
        speaker=_OTHER,
        listener=EntityId(_OWNER.value),
        message=_message(),
        event="e2",
        tick=3,
        prior=first.utterance,
    )
    ledger = advance_competing_theories(
        _known_ledger(),
        _observation(10, (retold, first)),
        previous_scientific_models=None,
        scientific_models=None,
    )
    assert len(ledger.receipts) == 2
    assert sum(row.origin for row in ledger.receipts) == 1
    assert ledger.stances == ()


def test_two_distinct_origin_speakers_create_support() -> None:
    second = EntityId("body-dan")
    first = _speech(
        speaker=_SPEAKER,
        listener=EntityId(_OWNER.value),
        message=_message(),
        event="e1",
        tick=2,
    )
    other = _speech(
        speaker=second,
        listener=EntityId(_OWNER.value),
        message=_message(),
        event="e2",
        tick=3,
    )
    ledger = advance_competing_theories(
        _known_ledger(),
        _observation(10, (first, other)),
        previous_scientific_models=None,
        scientific_models=None,
    )
    assert len([row for row in ledger.receipts if row.origin]) == 2
    assert ledger.stances[-1].claim_id == _message().claim_id


def _dual_claim_ledger(owner: AgentId):
    context = _context()
    continuity = TheoryClaim(
        context=context,
        account=TheoryAccount.CONTINUITY,
        predicted_category=context.continuity_category,
        claim_id=theory_claim_id(
            context, TheoryAccount.CONTINUITY, context.continuity_category
        ),
        created_tick=0,
    )
    recurrence = TheoryClaim(
        context=context,
        account=TheoryAccount.RECURRENCE,
        predicted_category="summer",
        claim_id=theory_claim_id(context, TheoryAccount.RECURRENCE, "summer"),
        created_tick=0,
    )
    return apply_theory_updates(
        empty_competing_theory_ledger(owner),
        tick=0,
        claims=(continuity, recurrence),
    )


def _support_message(account: TheoryAccount, category: str) -> TheoryMessage:
    return TheoryMessage(
        act=TheorySpeechAct.SUPPORT,
        context=_context(),
        account=account,
        predicted_category=category,
        cited_root="",
        cited_polarity=None,
    )


def _owner_observation(
    owner: AgentId, tick: int, communications: tuple[ObservedCommunication, ...]
) -> Observation:
    base = _observation(tick, communications)
    return replace(
        base,
        observer_id=EntityId(owner.value),
        self_body=replace(base.self_body, entity_id=EntityId(owner.value)),
    )


def test_disjoint_recipient_cohorts_converge_on_different_rivals() -> None:
    context = _context()
    continuity = _support_message(
        TheoryAccount.CONTINUITY, context.continuity_category
    )
    recurrence = _support_message(TheoryAccount.RECURRENCE, "summer")
    cohort_a = (
        _speech(
            speaker=EntityId("body-a1"),
            listener=EntityId("body-a"),
            message=continuity,
            event="a1",
            tick=2,
        ),
        _speech(
            speaker=EntityId("body-a2"),
            listener=EntityId("body-a"),
            message=continuity,
            event="a2",
            tick=3,
        ),
    )
    cohort_b = (
        _speech(
            speaker=EntityId("body-b1"),
            listener=EntityId("body-b"),
            message=recurrence,
            event="b1",
            tick=2,
        ),
        _speech(
            speaker=EntityId("body-b2"),
            listener=EntityId("body-b"),
            message=recurrence,
            event="b2",
            tick=3,
        ),
    )
    owner_a = AgentId("body-a")
    owner_b = AgentId("body-b")
    ledger_a = advance_competing_theories(
        _dual_claim_ledger(owner_a),
        _owner_observation(owner_a, 10, cohort_a),
        previous_scientific_models=None,
        scientific_models=None,
    )
    ledger_b = advance_competing_theories(
        _dual_claim_ledger(owner_b),
        _owner_observation(owner_b, 10, cohort_b),
        previous_scientific_models=None,
        scientific_models=None,
    )
    assert ledger_a.stances[-1].claim_id == continuity.claim_id
    assert ledger_b.stances[-1].claim_id == recurrence.claim_id
    assert ledger_a.receipts and ledger_b.receipts
    assert {row.speaker_id.value for row in ledger_a.receipts} == {
        "body-a1",
        "body-a2",
    }
    assert {row.speaker_id.value for row in ledger_b.receipts} == {
        "body-b1",
        "body-b2",
    }


def test_private_bystander_and_ask_are_not_uptake() -> None:
    private = _speech(
        speaker=_SPEAKER, listener=_OTHER, message=_message(), event="e1", tick=2
    )
    asked = _speech(
        speaker=_SPEAKER,
        listener=EntityId(_OWNER.value),
        message=_message(),
        event="e2",
        tick=3,
        action_kind="ask",
    )
    ledger = advance_competing_theories(
        _known_ledger(),
        _observation(10, (private, asked)),
        previous_scientific_models=None,
        scientific_models=None,
    )
    assert ledger.receipts == ()


def test_teaching_receipt_is_distinct_from_support() -> None:
    taught = _speech(
        speaker=_SPEAKER,
        listener=EntityId(_OWNER.value),
        message=_message(TheorySpeechAct.TEACH),
        event="e1",
        tick=2,
    )
    ledger = advance_competing_theories(
        _known_ledger(),
        _observation(10, (taught,)),
        previous_scientific_models=None,
        scientific_models=None,
    )
    assert ledger.receipts[0].kind.value == "taught"
    assert ledger.receipts[0].act is TheorySpeechAct.TEACH
    assert ledger.stances == ()


def test_sender_echo_matches_outbound_and_adds_no_support() -> None:
    ledger = _known_ledger()
    claim = next(row for row in ledger.claims)
    ledger = apply_theory_updates(
        ledger,
        tick=2,
        stances=(
            TheoryStanceRequest(
                claim.context, TheoryStanceAction.SUPPORT, claim.claim_id
            ),
        ),
    )
    stance = ledger.stances[0]
    ledger = record_theory_outbound(
        ledger,
        recipient_entity_id=_SPEAKER.value,
        stance=stance,
        act=TheorySpeechAct.SUPPORT,
        frame_digest=_message().frame_digest,
        send_tick=2,
    )
    echo = _speech(
        speaker=EntityId(_OWNER.value),
        listener=_SPEAKER,
        message=_message(),
        event="e1",
        tick=3,
    )
    updated = advance_competing_theories(
        ledger,
        _observation(4, (echo,)),
        previous_scientific_models=None,
        scientific_models=None,
    )
    assert len(updated.echoes) == 1
    assert updated.receipts == ()
    assert updated.outbound == ()


def test_full_relation_budget_keeps_normal_speech_unchanged() -> None:
    message = _message()
    base = origin_utterance(
        text="hello", speaker_id=EntityId(_OWNER.value), communication_id="c1"
    )
    relations = tuple(
        CommunicationRelation("other", "part", f"value-{index}") for index in range(31)
    )
    utterance = StructuredUtterance(
        content=type(base.content)(text=base.content.text, relations=relations),
        declared=base.declared,
    )
    command = Tell(recipient_id=_SPEAKER, utterance=utterance)
    assert attach_theory_message(command, message) is command


def test_selection_announces_only_committed_stance_and_teaches_after_support() -> None:
    ledger = _known_ledger()
    claim = next(row for row in ledger.claims)
    ledger = apply_theory_updates(
        ledger,
        tick=2,
        stances=(
            TheoryStanceRequest(
                claim.context, TheoryStanceAction.SUPPORT, claim.claim_id
            ),
        ),
    )
    command = Talk(
        recipient_id=_SPEAKER,
        utterance=origin_utterance(text="hi", speaker_id=EntityId(_OWNER.value)),
    )
    selected = select_theory_speech(ledger, command, recipient_entity_id=_SPEAKER.value)
    assert selected is not None
    assert selected[0].act is TheorySpeechAct.SUPPORT
    message, _stance = selected
    claim_relation, context_relation = encode_theory_message(message)
    attached = attach_theory_message(command, message)
    assert attached.utterance.content.relations[-2:] == (
        claim_relation,
        context_relation,
    )
    assert encode_theory_message(message) == (claim_relation, context_relation)


def test_replaced_or_unaddressed_commands_carry_no_theory_delivery() -> None:
    from world.actions import Wait

    ledger = _known_ledger()
    claim = next(row for row in ledger.claims)
    ledger = apply_theory_updates(
        ledger,
        tick=2,
        stances=(
            TheoryStanceRequest(
                claim.context, TheoryStanceAction.SUPPORT, claim.claim_id
            ),
        ),
    )
    message = message_from_claim(claim, TheorySpeechAct.SUPPORT)
    wait = Wait()
    assert (
        select_theory_speech(ledger, wait, recipient_entity_id=_SPEAKER.value)
        is None
    )
    with pytest.raises(TypeError, match="requires Talk or Tell"):
        attach_theory_message(wait, message)
    talk = Talk(
        recipient_id=_SPEAKER,
        utterance=origin_utterance(text="hi", speaker_id=EntityId(_OWNER.value)),
    )
    assert select_theory_speech(ledger, talk, recipient_entity_id=None) is None
    assert ledger.outbound == ()
    assert ledger.receipts == ()


def test_social_switch_preserves_scored_failure_history() -> None:
    from agents.cognition.competing_theory_forecasts import (
        issue_theory_case,
        settle_theory_case,
    )
    from tests.unit.test_competing_theories_forecasts import (
        _forecast_case,
        _outcome,
        _seeded_ledger,
    )

    owner = AgentId("agent-1")
    ledger = _seeded_ledger()
    recurrence = next(
        row for row in ledger.claims if row.account is TheoryAccount.RECURRENCE
    )
    ledger = apply_theory_updates(
        ledger,
        tick=3,
        stances=(
            TheoryStanceRequest(
                recurrence.context,
                TheoryStanceAction.SUPPORT,
                recurrence.claim_id,
            ),
        ),
    )
    base = _forecast_case(tick=4)
    ledger = issue_theory_case(ledger, base)
    ledger = settle_theory_case(ledger, _outcome(base, "spring"))
    failed = tuple(ledger.cases)
    assert any(
        outcome.hit is False for case in ledger.cases for outcome in case.outcomes
    )
    continuity = next(
        row for row in ledger.claims if row.account is TheoryAccount.CONTINUITY
    )
    message = message_from_claim(continuity, TheorySpeechAct.SUPPORT)
    cohort = (
        _speech(
            speaker=EntityId("body-1"),
            listener=EntityId(owner.value),
            message=message,
            event="s1",
            tick=5,
        ),
        _speech(
            speaker=EntityId("body-2"),
            listener=EntityId(owner.value),
            message=message,
            event="s2",
            tick=6,
        ),
    )
    switched = advance_competing_theories(
        ledger,
        _owner_observation(owner, 10, cohort),
        previous_scientific_models=None,
        scientific_models=None,
    )
    assert switched.stances[-1].claim_id == continuity.claim_id
    assert tuple(switched.cases) == failed
    assert any(
        outcome.hit is False for case in switched.cases for outcome in case.outcomes
    )
