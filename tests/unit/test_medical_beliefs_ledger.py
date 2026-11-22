# mypy: ignore-errors

"""Owner-local medical belief ledger reducer invariants."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition.medical_beliefs import (
    MAX_HISTORY_ROWS,
    MAX_SEEN_ROOTS,
    MB_RELATION_PREDICATE,
    MB_RELATION_SUBJECT,
    MedicalAttemptRow,
    MedicalBeliefLedger,
    MedicalBeliefRow,
    MedicalCause,
    MedicalInterpretationRow,
    MedicalOutcomeKind,
    MedicalOutcomeRow,
    MedicalOutlook,
    MedicalPractice,
    MedicalTransmissionStatus,
    active_cause,
    advance,
    begin_attempt,
    latest_outlook,
    practice_support,
    relay_anchor,
    root_for_belief,
)
from agents.models import AgentId
from tests.simulation_helpers import alive_body
from world.artifacts import ArtifactContent, ArtifactKind
from world.communications import CommunicationRelation, origin_utterance
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import Health, LifeStatus
from world.observations import (
    CoarseHealth,
    Observation,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedArtifact,
    ObservedCommunication,
    ObservedItem,
    ObservedItemPlacement,
    VisibleBody,
    observed_self_from_body,
)
from world.values import ItemKind, ItemLoad, WeatherCondition

pytestmark = pytest.mark.unit

_OWNER = AgentId("agent-a")
_ENTITY = EntityId("body-a")
_PEER = EntityId("body-b")
_WORLD = WorldId("world-medical-beliefs")
_LOC_A = EntityId("loc-a")
_LOC_B = EntityId("loc-b")


def _ledger() -> MedicalBeliefLedger:
    return MedicalBeliefLedger(owner_id=_OWNER, observer_entity_id=_ENTITY)


def _item(name: str = "berry") -> ObservedItem:
    return ObservedItem(
        entity_id=EntityId(f"item-{name}"),
        name=name,
        kind=ItemKind.FOOD,
        load=ItemLoad(1),
        placement=ObservedItemPlacement.HELD_BY_SELF,
    )


def _observation(
    tick: int,
    *,
    cue: bool,
    location_id: EntityId = _LOC_A,
    weather: WeatherCondition | None = WeatherCondition.CLEAR,
    peer: bool = False,
    food: bool = False,
    artifact: bool = False,
    communications: tuple[ObservedCommunication, ...] = (),
    alive: bool = True,
) -> Observation:
    body = alive_body(
        "body-a",
        location_id=location_id.value,
        inventory=(EntityId("item-berry"),) if food else (),
    )
    if not alive:
        body = replace(body, life_status=LifeStatus.DEAD, health=Health(0.0))
    self_body = observed_self_from_body(
        body, symptom_cue="unwell" if (alive and cue) else None
    )
    visible = (
        (
            VisibleBody(
                entity_id=_PEER,
                life_status=LifeStatus.ALIVE,
                coarse_health=CoarseHealth.STABLE,
            ),
        )
        if peer
        else ()
    )
    return Observation(
        world_id=_WORLD,
        observer_id=_ENTITY,
        revision=WorldRevision(tick),
        tick=tick,
        self_body=self_body,
        visible_bodies=visible,
        items=(_item(),) if food else (),
        artifacts=(_artifact(),) if artifact else (),
        weather_condition=weather,
        communications=communications,
    )


def _artifact():
    return ObservedArtifact(
        entity_id=EntityId("artifact-1"),
        kind=ArtifactKind.MARK,
        author_id=_PEER,
        created_tick=0,
        content=ArtifactContent(marks=("mark",)),
        content_revision=0,
        placement=ObservedItemPlacement.GROUND_HERE,
    )


def _delivery(
    *,
    tick: int,
    event: str,
    object_value: str,
    speaker: EntityId = _PEER,
    listener: EntityId = _ENTITY,
) -> ObservedCommunication:
    utterance = origin_utterance(
        text="belief",
        speaker_id=speaker,
        communication_id=f"comm-{event}",
        relations=(
            CommunicationRelation(
                subject=MB_RELATION_SUBJECT,
                predicate=MB_RELATION_PREDICATE,
                object=object_value,
            ),
        ),
    )
    return ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=tick,
            source_event_id=EventId(f"event-{event}"),
        ),
        speaker_id=speaker,
        listener_id=listener,
        utterance=utterance,
        action_kind="tell",
    )


def _root(index: int) -> str:
    return f"{index:032x}"


def test_first_observation_is_baseline_and_absent_is_not_negative() -> None:
    ledger = advance(_ledger(), _observation(0, cue=False, peer=True))
    assert ledger.frame is not None
    assert ledger.cause_scores == tuple((cause, 0) for cause in MedicalCause)
    assert ledger.rows == ()
    ledger = advance(ledger, _observation(1, cue=False, peer=True, alive=False))
    assert ledger.frame is None
    ledger = advance(ledger, _observation(2, cue=True, peer=True))
    assert dict(ledger.cause_scores)[MedicalCause.CONTACT] == 0


def test_consecutive_onset_associations_are_independent() -> None:
    ledger = advance(_ledger(), _observation(0, cue=False, peer=True, food=True))
    ledger = advance(
        ledger,
        _observation(
            1,
            cue=True,
            location_id=_LOC_B,
            weather=WeatherCondition.RAIN,
            artifact=True,
        ),
    )
    scores = dict(ledger.cause_scores)
    assert scores[MedicalCause.CONTACT] == 2
    assert scores[MedicalCause.FOOD] == 2
    assert scores[MedicalCause.WEATHER] == 2
    assert scores[MedicalCause.LOCATION] == 2
    assert scores[MedicalCause.CULTURAL] == 2
    assert active_cause(ledger) is MedicalCause.CONTACT


def test_gap_or_absent_cue_establishes_baseline_only() -> None:
    ledger = advance(_ledger(), _observation(0, cue=False, peer=True))
    ledger = advance(ledger, _observation(2, cue=True, peer=True))
    assert dict(ledger.cause_scores)[MedicalCause.CONTACT] == 0
    ledger = advance(ledger, _observation(3, cue=True, peer=True))
    ledger = advance(ledger, _observation(4, cue=True, peer=True))
    assert dict(ledger.cause_scores)[MedicalCause.CONTACT] == 0


def test_wrong_owner_repeat_and_rewind_fail_closed() -> None:
    ledger = advance(_ledger(), _observation(1, cue=False))
    assert advance(ledger, _observation(1, cue=True)) is ledger
    with pytest.raises(ValueError, match="medical_beliefs_tick_rewind"):
        advance(ledger, _observation(0, cue=True))
    foreign = _observation(2, cue=True)
    object.__setattr__(foreign, "observer_id", EntityId("body-z"))
    with pytest.raises(ValueError, match="medical_beliefs_wrong_owner"):
        advance(ledger, foreign)


def test_attempt_outcomes_and_unknown_follow_up() -> None:
    ledger = advance(_ledger(), _observation(0, cue=True, peer=True))
    ledger = begin_attempt(
        ledger, tick=0, cause=MedicalCause.CONTACT, practice=MedicalPractice.LEAVE
    )
    assert ledger.open_attempt_id is not None
    ledger = advance(ledger, _observation(1, cue=False))
    assert practice_support(ledger, MedicalCause.CONTACT, MedicalPractice.LEAVE) == 1
    assert latest_outlook(
        ledger, MedicalCause.CONTACT, MedicalPractice.LEAVE
    ) is MedicalOutlook.TENTATIVELY_HELPED

    ledger = advance(ledger, _observation(2, cue=True, peer=True))
    ledger = begin_attempt(
        ledger, tick=2, cause=MedicalCause.CONTACT, practice=MedicalPractice.LEAVE
    )
    ledger = advance(ledger, _observation(3, cue=True))
    assert practice_support(ledger, MedicalCause.CONTACT, MedicalPractice.LEAVE) == 0
    assert latest_outlook(
        ledger, MedicalCause.CONTACT, MedicalPractice.LEAVE
    ) is MedicalOutlook.NOT_OBVIOUSLY_HELPED

    ledger = advance(ledger, _observation(4, cue=True, peer=True))
    ledger = begin_attempt(
        ledger, tick=4, cause=MedicalCause.CONTACT, practice=MedicalPractice.REST
    )
    ledger = advance(ledger, _observation(6, cue=False))
    outcomes = [row.outcome for row in ledger.rows if row.kind == "outcome"]
    assert outcomes[-1] is MedicalOutcomeKind.UNKNOWN
    assert practice_support(ledger, MedicalCause.CONTACT, MedicalPractice.REST) == 0
    assert latest_outlook(
        ledger, MedicalCause.CONTACT, MedicalPractice.LEAVE
    ) is MedicalOutlook.NOT_OBVIOUSLY_HELPED


def test_testimony_first_root_repeat_and_conflict() -> None:
    root = _root(1)
    first = _delivery(
        tick=0,
        event="1",
        object_value=f"contact|leave|tentatively_helped|{root}|0",
    )
    ledger = advance(_ledger(), _observation(1, cue=False, communications=(first,)))
    assert dict(ledger.cause_scores)[MedicalCause.CONTACT] == 2
    assert practice_support(ledger, MedicalCause.CONTACT, MedicalPractice.LEAVE) == 2
    assert relay_anchor(ledger, MedicalCause.CONTACT, MedicalPractice.LEAVE) == root

    repeat = _delivery(
        tick=1,
        event="2",
        object_value=f"contact|leave|not_obviously_helped|{root}|0",
    )
    ledger = advance(ledger, _observation(2, cue=False, communications=(repeat,)))
    assert dict(ledger.cause_scores)[MedicalCause.CONTACT] == 2
    assert practice_support(ledger, MedicalCause.CONTACT, MedicalPractice.LEAVE) == 2
    assert latest_outlook(
        ledger, MedicalCause.CONTACT, MedicalPractice.LEAVE
    ) is MedicalOutlook.NOT_OBVIOUSLY_HELPED
    assert ledger.rows[-1].status is MedicalTransmissionStatus.REPEAT


def test_delivery_rejects_nonrecipient_and_self_and_malformed() -> None:
    root = _root(3)
    value = f"food|rest|uncertain|{root}|1"
    cases = (
        _delivery(tick=0, event="a", object_value=value, listener=EntityId("body-x")),
        _delivery(tick=0, event="b", object_value=value, speaker=_ENTITY),
        _delivery(tick=0, event="c", object_value="food|rest|bogus"),
        _delivery(tick=0, event="d", object_value="food|rest|uncertain|UPPER|1"),
    )
    ledger = advance(_ledger(), _observation(1, cue=False, communications=cases))
    assert ledger.seen_roots == ()
    assert ledger.practice_scores == tuple(
        (cause, practice, 0)
        for cause in MedicalCause
        for practice in MedicalPractice
    )


def test_hop_and_capacity_bounds_block_unseen_roots() -> None:
    ledger = _ledger()
    communications = []
    for index in range(MAX_SEEN_ROOTS):
        cause = MedicalCause.CONTACT if index % 2 == 0 else MedicalCause.FOOD
        communications.append(
            _delivery(
                tick=0,
                event=f"e{index}",
                object_value=(
                    f"{cause.value}|leave|uncertain|{_root(index)}|0"
                ),
            )
        )
    ledger = advance(
        _ledger(), _observation(1, cue=False, communications=tuple(communications))
    )
    assert len(ledger.seen_roots) == MAX_SEEN_ROOTS
    blocked = _delivery(
        tick=1,
        event="blocked",
        object_value=f"weather|rest|uncertain|{_root(999)}|0",
    )
    ledger = advance(ledger, _observation(2, cue=False, communications=(blocked,)))
    assert dict(ledger.cause_scores)[MedicalCause.WEATHER] == 0
    assert practice_support(ledger, MedicalCause.WEATHER, MedicalPractice.REST) == 0
    assert relay_anchor(ledger, MedicalCause.WEATHER, MedicalPractice.REST) is None
    assert ledger.rows[-1].status is MedicalTransmissionStatus.CAPACITY_IGNORED
    assert len(ledger.rows) == MAX_HISTORY_ROWS
    assert ledger.history_truncated is True


def test_negative_outlook_survives_row_eviction() -> None:
    ledger = advance(_ledger(), _observation(0, cue=True))
    ledger = begin_attempt(
        ledger, tick=0, cause=MedicalCause.CONTACT, practice=MedicalPractice.REST
    )
    ledger = advance(ledger, _observation(1, cue=True))
    negative = latest_outlook(
        ledger, MedicalCause.CONTACT, MedicalPractice.REST
    )
    assert negative is MedicalOutlook.NOT_OBVIOUSLY_HELPED
    for tick in range(2, 200):
        ledger = advance(
            ledger,
            _observation(
                tick,
                cue=False,
                communications=(
                    _delivery(
                        tick=tick - 1,
                        event=f"r{tick}",
                        object_value=(
                            f"weather|leave|uncertain|{_root(1000 + tick)}|0"
                        ),
                    ),
                ),
            ),
        )
    assert ledger.history_truncated is True
    assert latest_outlook(
        ledger, MedicalCause.CONTACT, MedicalPractice.REST
    ) is negative


def test_scores_clamp_and_stay_bounded() -> None:
    ledger = advance(_ledger(), _observation(0, cue=False, peer=True))
    tick = 1
    for _ in range(10):
        ledger = advance(ledger, _observation(tick, cue=True, peer=True))
        assert -8 <= dict(ledger.cause_scores)[MedicalCause.CONTACT] <= 8
        tick += 1
        ledger = advance(ledger, _observation(tick, cue=False, peer=True))
        tick += 1
    assert dict(ledger.cause_scores)[MedicalCause.CONTACT] == 8


def test_deterministic_row_order_for_shuffled_deliveries() -> None:
    one = _delivery(
        tick=0,
        event="x",
        object_value=f"contact|leave|uncertain|{_root(7)}|0",
    )
    two = _delivery(
        tick=0,
        event="y",
        object_value=f"food|rest|uncertain|{_root(8)}|0",
    )
    left = advance(_ledger(), _observation(1, cue=False, communications=(one, two)))
    right = advance(_ledger(), _observation(1, cue=False, communications=(two, one)))
    assert left == right
    assert left.rows == right.rows


@pytest.mark.parametrize("seed", (1, 2, 3, 4, 5))
def test_hypothesis_shuffled_deliveries_are_deterministic(seed: int) -> None:
    import random

    entries = [
        (MedicalCause.CONTACT, _root(11)),
        (MedicalCause.FOOD, _root(12)),
        (MedicalCause.WEATHER, _root(13)),
        (MedicalCause.LOCATION, _root(14)),
        (MedicalCause.CULTURAL, _root(15)),
    ]
    rng = random.Random(seed)
    rng.shuffle(entries)
    communications = tuple(
        _delivery(
            tick=0,
            event=f"s{index}",
            object_value=f"{cause.value}|rest|uncertain|{root}|0",
        )
        for index, (cause, root) in enumerate(entries)
    )
    ledger = advance(
        _ledger(), _observation(1, cue=False, communications=communications)
    )
    assert len(ledger.seen_roots) == len(entries)
    assert ledger.rows == tuple(
        sorted(ledger.rows, key=lambda row: (row.tick, row.row_id))
    )


def test_root_derivation_is_stable_and_declared() -> None:
    ledger = _ledger()
    root = root_for_belief(
        ledger, tick=4, cause=MedicalCause.WEATHER, practice=MedicalPractice.REST
    )
    assert root == root_for_belief(
        _ledger(), tick=4, cause=MedicalCause.WEATHER, practice=MedicalPractice.REST
    )
    assert len(root) == 32 and root.lower() == root


def test_duplicate_row_ids_are_rejected() -> None:
    row = MedicalBeliefRow(
        row_id="mb-duplicate",
        owner_id=_OWNER,
        tick=1,
        cause=MedicalCause.FOOD,
        score=2,
    )
    with pytest.raises(ValueError, match="duplicate id"):
        MedicalBeliefLedger(
            owner_id=_OWNER,
            observer_entity_id=_ENTITY,
            rows=(row, row),
        )


def test_orphan_outcome_and_interpretation_are_rejected() -> None:
    outcome = MedicalOutcomeRow(
        row_id="mbo-orphan",
        attempt_id="mba-missing",
        owner_id=_OWNER,
        tick=1,
        outcome=MedicalOutcomeKind.UNKNOWN,
    )
    with pytest.raises(ValueError, match="orphan attempt reference"):
        MedicalBeliefLedger(
            owner_id=_OWNER,
            observer_entity_id=_ENTITY,
            rows=(outcome,),
        )
    interpretation = MedicalInterpretationRow(
        row_id="mbi-orphan",
        attempt_id="mba-missing",
        owner_id=_OWNER,
        tick=1,
        outlook=None,
    )
    with pytest.raises(ValueError, match="orphan attempt reference"):
        MedicalBeliefLedger(
            owner_id=_OWNER,
            observer_entity_id=_ENTITY,
            rows=(interpretation,),
        )


def test_attempt_tick_and_open_reference_are_validated() -> None:
    first = MedicalAttemptRow(
        attempt_id="mba-one",
        owner_id=_OWNER,
        tick=2,
        cause=MedicalCause.CONTACT,
        practice=MedicalPractice.LEAVE,
    )
    second = MedicalAttemptRow(
        attempt_id="mba-two",
        owner_id=_OWNER,
        tick=2,
        cause=MedicalCause.FOOD,
        practice=MedicalPractice.REST,
    )
    with pytest.raises(ValueError, match="duplicate attempt tick"):
        MedicalBeliefLedger(
            owner_id=_OWNER,
            observer_entity_id=_ENTITY,
            rows=(first, second),
        )
    with pytest.raises(ValueError, match="open_attempt_id missing"):
        MedicalBeliefLedger(
            owner_id=_OWNER,
            observer_entity_id=_ENTITY,
            rows=(first,),
            open_attempt_id="mba-missing",
        )


def test_duplicate_seen_roots_are_rejected() -> None:
    root = root_for_belief(
        _ledger(), tick=1, cause=MedicalCause.CONTACT, practice=MedicalPractice.LEAVE
    )
    entry = (MedicalCause.CONTACT, MedicalPractice.LEAVE, root)
    with pytest.raises(ValueError, match="seen_roots duplicate"):
        MedicalBeliefLedger(
            owner_id=_OWNER,
            observer_entity_id=_ENTITY,
            seen_roots=(entry, entry),
        )


def test_duplicate_relations_are_ignored_not_fatal() -> None:
    root = _root(77)
    delivery = _delivery(
        tick=0,
        event="dup",
        object_value=f"contact|leave|uncertain|{root}|0",
    )
    content = delivery.utterance.content
    relation = content.relations[0]
    duplicated = replace(
        delivery,
        utterance=replace(
            delivery.utterance,
            content=replace(content, relations=(relation, relation)),
        ),
    )
    ledger = advance(
        _ledger(),
        _observation(1, cue=False, communications=(duplicated,)),
    )
    transmissions = [
        row for row in ledger.rows if row.kind == "transmission"
    ]
    assert len(transmissions) == 1
    assert dict(ledger.cause_scores)[MedicalCause.CONTACT] == 2
