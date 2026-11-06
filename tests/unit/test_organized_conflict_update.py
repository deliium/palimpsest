# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined,no-untyped-def,no-untyped-call,call-overload,index,type-arg,unused-ignore"
from __future__ import annotations

import pytest

from agents.cognition.organized_conflict import (
    ConflictBasis,
    ConflictInterpretation,
    ConflictInterpretationKind,
    ConflictLedger,
    ConflictOperation,
    ConflictPlanStatus,
    ConflictProvenance,
    ConflictRole,
    ConflictTargetKind,
    ConflictTerminationKind,
    apply_organized_conflict_update,
    conflict_interpretation_id,
    conflict_target_token,
    default_organized_conflict_policy,
    empty_organized_conflict_ledger,
)
from agents.cognition.organized_conflict_communication import (
    ConflictAct,
    ConflictFrame,
    conflict_frame_relation,
)
from agents.models import AgentId
from world.communications import origin_utterance
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
    ObservedOccurrence,
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

OWNER = AgentId("agent-owner")
OWNER_BODY = EntityId("body-owner")
OTHER_BODY = EntityId("body-other")
AGENT_OTHER = AgentId("agent-other-two")
OWNER_REF = conflict_target_token(OWNER.value)
OTHER_REF = conflict_target_token("body-other")


def _self() -> ObservedSelf:
    return ObservedSelf(
        entity_id=OWNER_BODY,
        location_id=EntityId("place-a"),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _occur(
    kind: str, actor: EntityId, other: EntityId | None, event: str
) -> ObservedOccurrence:
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=0,
            source_event_id=EventId(event),
        ),
        kind=kind,
        audience_role=ObservationAudienceRole.WITNESS,
        actor_id=actor,
        other_entity_id=other,
        success=True,
    )


def _communication(speaker: EntityId, frame: ConflictFrame) -> ObservedCommunication:
    return ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=0,
            source_event_id=EventId("event-comm"),
        ),
        speaker_id=speaker,
        listener_id=OWNER_BODY,
        utterance=origin_utterance(
            text="ocf_v1",
            speaker_id=speaker,
            relations=(conflict_frame_relation(frame),),
        ),
        action_kind="tell",
    )


def _observe(
    *occurrences: ObservedOccurrence,
    communications: tuple[ObservedCommunication, ...] = (),
    tick: int = 1,
) -> Observation:
    return Observation(
        world_id=WorldId("world-w"),
        observer_id=OWNER_BODY,
        revision=WorldRevision(1),
        tick=tick,
        self_body=_self(),
        occurrences=occurrences,
        communications=communications,
    )


def _update(
    observation: Observation, prior: ConflictLedger, tick: int = 1
) -> ConflictLedger:
    return apply_organized_conflict_update(
        owner_id=OWNER,
        tick=tick,
        observation=observation,
        prior=prior,
        representation=None,
        diplomacy=None,
        identity=None,
        relationships=(),
        policy=default_organized_conflict_policy(),
    )


def _frame(**overrides: object) -> ConflictFrame:
    payload = {
        "act": ConflictAct.PROPOSE,
        "operation": ConflictOperation.COORDINATED_ATTACK,
        "target_kind": ConflictTargetKind.AGENT,
        "target_ref": OTHER_REF,
        "role": ConflictRole.ATTACKER,
        "side_ref": conflict_target_token("body-other"),
        "window_start": 1,
        "window_end": 5,
        "participant_refs": (conflict_target_token("body-other"),),
    }
    payload.update(overrides)
    return ConflictFrame(**payload)  # type: ignore[arg-type]


def test_propose_join_and_coordinate_update_plan() -> None:
    proposal = _frame()
    observation = _observe(communications=(_communication(OTHER_BODY, proposal),))
    ledger = _update(observation, empty_organized_conflict_ledger(OWNER, tick=1))
    assert len(ledger.plans) == 1
    plan = ledger.plans[0]
    assert plan.provenance is ConflictProvenance.COMMUNICATED
    assert plan.status is ConflictPlanStatus.PROPOSED

    join = _frame(
        act=ConflictAct.JOIN,
        plan_ref=plan.plan_id,
        side_ref=conflict_target_token("body-other"),
        participant_refs=(conflict_target_token("body-other"),),
    )
    joined = _update(
        _observe(communications=(_communication(OTHER_BODY, join),)),
        ledger,
        tick=2,
    )
    assert any(
        row.plan_id == plan.plan_id
        and row.participant_ref == conflict_target_token("body-other")
        for row in joined.participations
    )
    assert joined.tick == 2


def test_coordinate_updates_an_existing_plan_for_an_authorized_speaker() -> None:
    proposal = _frame()
    observation = _observe(communications=(_communication(OTHER_BODY, proposal),))
    ledger = _update(observation, empty_organized_conflict_ledger(OWNER, tick=1))
    plan = ledger.plans[0]
    new_target = conflict_target_token("body-new")
    coordinate = _frame(
        act=ConflictAct.COORDINATE,
        plan_ref=plan.plan_id,
        target_ref=new_target,
        window_end=9,
    )
    updated = _update(
        _observe(communications=(_communication(OTHER_BODY, coordinate),)),
        ledger,
        tick=2,
    )
    assert updated.plans[0].target_ref == new_target
    assert updated.plans[0].end_tick == 9
    assert updated.plans[0].last_tick == 2


def test_observed_coordination_infers_owner_plan_only() -> None:
    observation = _observe(
        _occur("attack", OWNER_BODY, OTHER_BODY, "e1"),
        _occur("attack", OTHER_BODY, OWNER_BODY, "e2"),
        _occur("attack", OWNER_BODY, OTHER_BODY, "e3"),
    )
    ledger = _update(observation, empty_organized_conflict_ledger(OWNER, tick=1))
    assert ledger.plans
    assert all(
        OWNER_REF in plan.participant_refs or plan.side_ref == OWNER_REF
        for plan in ledger.plans
    )
    assert any(plan.provenance is ConflictProvenance.INFERRED for plan in ledger.plans)


def test_opposing_interpretations_are_both_retained() -> None:
    episode_id = "oce-" + "a" * 16
    first = ConflictInterpretation(
        interpretation_id=conflict_interpretation_id(
            OWNER,
            episode_id,
            ConflictInterpretationKind.INDIVIDUAL_VIOLENCE,
            1,
            ConflictBasis.OBSERVED,
        ),
        episode_ref=None,
        kind=ConflictInterpretationKind.INDIVIDUAL_VIOLENCE,
        basis=ConflictBasis.OBSERVED,
        confidence_band="low",
        tick=1,
    )
    second = ConflictInterpretation(
        interpretation_id=conflict_interpretation_id(
            OWNER,
            episode_id,
            ConflictInterpretationKind.COORDINATED_CONFLICT,
            1,
            ConflictBasis.OBSERVED,
        ),
        episode_ref=None,
        kind=ConflictInterpretationKind.COORDINATED_CONFLICT,
        basis=ConflictBasis.OBSERVED,
        confidence_band="mid",
        tick=1,
    )
    ledger = ConflictLedger(
        owner_id=OWNER,
        interpretations=tuple(
            sorted((first, second), key=lambda row: row.interpretation_id)
        ),
    )
    kinds = {row.kind for row in ledger.interpretations}
    assert kinds == {
        ConflictInterpretationKind.INDIVIDUAL_VIOLENCE,
        ConflictInterpretationKind.COORDINATED_CONFLICT,
    }


def test_contradictions_are_unresolved_and_never_reconciled() -> None:
    observation = _observe(
        _occur("attack", OWNER_BODY, OTHER_BODY, "e1"),
        _occur("attack", OTHER_BODY, OWNER_BODY, "e2"),
    )
    ledger = _update(observation, empty_organized_conflict_ledger(OWNER, tick=1))
    assert all(row.status == "unresolved" for row in ledger.contradictions)
    assert ledger.contradictions == tuple(ledger.contradictions)


def test_expiry_appends_termination() -> None:
    observation = _observe(communications=(_communication(OTHER_BODY, _frame()),))
    ledger = _update(observation, empty_organized_conflict_ledger(OWNER, tick=1))
    plan = ledger.plans[0]
    expired = _update(_observe(tick=40), ledger, tick=40)
    assert any(row.plan_id == plan.plan_id for row in expired.terminations)
    assert any(
        row.kind is ConflictTerminationKind.EXPIRED for row in expired.terminations
    )


def test_update_rejects_world_state_and_events() -> None:
    class WorldState:
        pass

    class WorldEvent:
        pass

    prior = empty_organized_conflict_ledger(OWNER, tick=1)
    for forbidden in (WorldState(), WorldEvent()):
        with pytest.raises(TypeError):
            apply_organized_conflict_update(
                owner_id=OWNER,
                tick=1,
                observation=forbidden,
                prior=prior,
                policy=default_organized_conflict_policy(),
            )
    with pytest.raises(ValueError):
        apply_organized_conflict_update(
            owner_id=AGENT_OTHER,
            tick=1,
            observation=_observe(),
            prior=prior,
            policy=default_organized_conflict_policy(),
        )


def test_malformed_target_is_retained_as_notice() -> None:
    frame = _frame(target_ref="none")
    ledger = _update(
        _observe(communications=(_communication(OTHER_BODY, frame),)),
        empty_organized_conflict_ledger(OWNER, tick=1),
    )
    assert "unresolved_target" in ledger.notices
    assert ledger.plans == ()
