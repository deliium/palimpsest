# mypy: ignore-errors

"""Bounded medical-belief testimony and receiver uptake."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition.medical_beliefs import (
    MB_RELATION_PREDICATE,
    MB_RELATION_SUBJECT,
    MedicalCause,
    MedicalOutlook,
    MedicalPractice,
    advance,
    relay_anchor,
    relay_anchor_hop,
)
from agents.cognition.medical_beliefs_communication import (
    MB_RELATION_MAX,
    MedicalBeliefMessage,
    attach_medical_belief_message,
    build_medical_belief_talk,
    encode_medical_belief_message,
    select_medical_belief_message,
    select_medical_recipient,
)
from tests.unit.test_medical_beliefs_ledger import (
    _delivery,
    _ledger,
    _observation,
    _root,
)
from world.actions import Talk
from world.communications import CommunicationRelation, origin_utterance
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

_MESSAGE = MedicalBeliefMessage(
    cause=MedicalCause.CONTACT,
    practice=MedicalPractice.LEAVE,
    outlook=MedicalOutlook.TENTATIVELY_HELPED,
    root=_root(50),
    hop=0,
)


def _talk(relations: tuple[CommunicationRelation, ...] = ()) -> Talk:
    return Talk(
        recipient_id=EntityId("body-b"),
        utterance=origin_utterance(
            text="hello",
            speaker_id=EntityId("body-a"),
            communication_id="comm-1",
            relations=relations,
        ),
    )


def test_attach_adds_one_reserved_relation() -> None:
    attached = attach_medical_belief_message(_talk(), _MESSAGE)
    assert type(attached) is Talk
    rows = attached.utterance.content.relations
    assert len(rows) == 1
    assert rows[0].subject == MB_RELATION_SUBJECT
    assert rows[0].predicate == MB_RELATION_PREDICATE
    assert rows[0].object == (
        f"contact|leave|tentatively_helped|{_MESSAGE.root}|0"
    )


def test_attach_skips_duplicate_reserved_or_full_relations() -> None:
    duplicate = _talk((encode_medical_belief_message(_MESSAGE),))
    assert attach_medical_belief_message(duplicate, _MESSAGE) is duplicate
    filler = tuple(
        CommunicationRelation(subject="x", predicate="y", object="z")
        for _ in range(MB_RELATION_MAX)
    )
    full = _talk(filler)
    assert attach_medical_belief_message(full, _MESSAGE) is full


def test_attach_rejects_non_speech_objects() -> None:
    with pytest.raises(TypeError):
        attach_medical_belief_message(object(), _MESSAGE)


def test_selection_prefers_anchor_and_increments_hop() -> None:
    root = _root(51)
    ledger = advance(
        _ledger(),
        _observation(
            1,
            cue=False,
            communications=(
                _delivery(
                    tick=0,
                    event="a",
                    object_value=f"contact|leave|uncertain|{root}|0",
                ),
            ),
        ),
    )
    assert relay_anchor(ledger, MedicalCause.CONTACT, MedicalPractice.LEAVE) == root
    assert relay_anchor_hop(ledger, MedicalCause.CONTACT, MedicalPractice.LEAVE) == 0
    message = select_medical_belief_message(ledger, tick=2)
    assert message is not None
    assert message.root == root
    assert message.hop == 1


def test_cue_free_receiver_retains_and_can_relay_before_own_cue() -> None:
    root = _root(52)
    ledger = advance(
        _ledger(),
        _observation(
            1,
            cue=False,
            communications=(
                _delivery(
                    tick=0,
                    event="a",
                    object_value=f"food|rest|uncertain|{root}|0",
                ),
            ),
        ),
    )
    message = select_medical_belief_message(ledger, tick=2)
    assert message is not None
    assert message.cause is MedicalCause.FOOD
    assert message.root == root
    assert message.hop == 1
    # No local observation of food, so no new root may be minted.
    ledger_without_anchor = replace(
        ledger, relay_anchors=()
    )
    assert select_medical_belief_message(ledger_without_anchor, tick=2) is None


def test_hop_four_anchor_cannot_be_relayed() -> None:
    root = _root(53)
    ledger = advance(
        _ledger(),
        _observation(
            1,
            cue=False,
            communications=(
                _delivery(
                    tick=0,
                    event="a",
                    object_value=f"weather|rest|uncertain|{root}|4",
                ),
            ),
        ),
    )
    assert relay_anchor_hop(ledger, MedicalCause.WEATHER, MedicalPractice.REST) == 4
    assert select_medical_belief_message(ledger, tick=2) is None


def test_local_belief_mints_digest_root_without_testimony() -> None:
    ledger = advance(_ledger(), _observation(0, cue=False, peer=True))
    ledger = advance(ledger, _observation(1, cue=True))
    message = select_medical_belief_message(ledger, tick=2)
    assert message is not None
    assert message.root == message.root.lower()
    assert len(message.root) == 32
    assert message.hop == 0
    assert message.outlook is MedicalOutlook.UNCERTAIN


def test_synthesize_talk_keeps_one_bounded_relation_and_recipient() -> None:
    ledger = advance(_ledger(), _observation(0, cue=False, peer=True))
    ledger = advance(ledger, _observation(1, cue=True))
    observation = _observation(2, cue=True, peer=True)
    recipient = select_medical_recipient(observation)
    assert recipient is not None
    message = select_medical_belief_message(ledger, tick=2)
    assert message is not None
    talk = build_medical_belief_talk(
        observation,
        ledger,
        tick=2,
        recipient_id=recipient,
        message=message,
    )
    assert talk is not None
    assert talk.recipient_id == EntityId("body-b")
    assert len(talk.utterance.content.relations) == 1
    assert talk.utterance.declared.hop_count == 0


def test_tied_causes_follow_declared_enum_order_like_intervention() -> None:
    from agents.cognition.medical_beliefs import (
        MedicalBeliefLedger,
        MedicalBeliefRow,
        active_cause,
    )

    base = _ledger()
    owner = base.owner_id
    ledger = replace(
        base,
        cause_scores=(
            (MedicalCause.CONTACT, 0),
            (MedicalCause.FOOD, 2),
            (MedicalCause.WEATHER, 2),
            (MedicalCause.LOCATION, 0),
            (MedicalCause.CULTURAL, 0),
        ),
        practice_scores=(
            (MedicalCause.FOOD, MedicalPractice.REST, 2),
            (MedicalCause.WEATHER, MedicalPractice.REST, 2),
        ),
        rows=(
            MedicalBeliefRow(
                row_id="mb-food",
                owner_id=owner,
                tick=1,
                cause=MedicalCause.FOOD,
                score=2,
            ),
            MedicalBeliefRow(
                row_id="mb-weather",
                owner_id=owner,
                tick=1,
                cause=MedicalCause.WEATHER,
                score=2,
            ),
        ),
        last_processed_tick=1,
    )
    assert type(ledger) is MedicalBeliefLedger
    assert active_cause(ledger) is MedicalCause.FOOD
    message = select_medical_belief_message(ledger, tick=2)
    assert message is not None
    assert message.cause is MedicalCause.FOOD
    assert message.practice is MedicalPractice.REST
