"""Schema-v5 physical event payloads, causes, and compatibility matrix."""

from __future__ import annotations

import pytest

from world._transitions import TransitionResult, require_transition_events
from world.actions import TransitionOutcome
from world.communications import origin_utterance
from world.effects import (
    ActionCause,
    DeathCause,
    ResolvedActionEffects,
    ResolvedAttackEffect,
    ResolvedSearchEffect,
    SystemCause,
    SystemEffectFamily,
)
from world.events import (
    EVENT_SCHEMA_AUDIT_V1,
    EVENT_SCHEMA_REPLAY_V1,
    EVENT_SCHEMA_REPLAY_V2,
    EVENT_SCHEMA_REPLAY_V5,
    Attacked,
    Died,
    EventValidationCode,
    Moved,
    OccurrenceContext,
    Waited,
    WeatherChanged,
    WorldEvent,
    build_occurrence_context,
    make_physical_replayable_event,
    make_replayable_event,
    normalize_events,
    normalize_ordered_events,
)
from world.identifiers import (
    EntityId,
    EventId,
    RequestId,
    WorldId,
    WorldRevision,
)
from world.values import WeatherCondition


def _occurrence(details: object, *, origin: str = "loc-1") -> OccurrenceContext:
    return build_occurrence_context(
        details,  # type: ignore[arg-type]
        origin_location_id=EntityId(origin),
    )


def _physical_event(
    *,
    event_id: str,
    cause: ActionCause | SystemCause,
    details: object,
    tick: int = 0,
    sequence: int = 0,
    revision: int = 1,
    origin: str = "loc-1",
) -> WorldEvent:
    return make_physical_replayable_event(
        event_id=EventId(event_id),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=tick,
        sequence=sequence,
        cause=cause,
        resulting_revision=WorldRevision(revision),
        details=details,  # type: ignore[arg-type]
        occurrence=_occurrence(details, origin=origin),
    )


def test_event_details_are_closed_and_correlated() -> None:
    event = make_replayable_event(
        event_id=EventId("evt-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=0,
        sequence=0,
        request_id=RequestId("r-1"),
        resulting_revision=WorldRevision(2),
        details=Moved(EntityId("loc-1")),
        actor_id=EntityId("body-1"),
    )
    assert event.details.kind == "move"
    assert event.schema_version == EVENT_SCHEMA_REPLAY_V2
    assert event.schema_version == EVENT_SCHEMA_REPLAY_V1
    assert normalize_events([event]) == (event,)
    with pytest.raises(ValueError, match="duplicate event_id"):
        normalize_events([event, event])


def test_transition_result_rejects_mismatched_events() -> None:
    from world._state import WorldState

    event = make_replayable_event(
        event_id=EventId("evt-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=0,
        sequence=0,
        request_id=RequestId("r-1"),
        resulting_revision=WorldRevision(2),
        details=Waited(),
        actor_id=EntityId("body-1"),
    )
    result = TransitionResult(
        base_revision=WorldRevision(1),
        resulting_revision=WorldRevision(2),
        outcome=TransitionOutcome.APPLIED,
        events=(event,),
        resulting_state=WorldState(WorldRevision(2)),
    )
    assert result.events[0].details == Waited()
    with pytest.raises(ValueError, match="request_id mismatch"):
        require_transition_events(
            world_id=WorldId("world-1"),
            request_id=RequestId("other"),
            resulting_revision=WorldRevision(2),
            events=(event,),
        )


def test_physical_replay_v4_requires_cause_and_effect_facts() -> None:
    cause = ActionCause(RequestId("r-1"), EntityId("body-1"))
    sparse = Moved(EntityId("loc-1"))
    with pytest.raises(
        ValueError, match=EventValidationCode.MISSING_EFFECT_FACTS.value
    ):
        make_physical_replayable_event(
            event_id=EventId("evt-1"),
            run_id="run-1",
            world_id=WorldId("world-1"),
            tick=0,
            sequence=0,
            cause=cause,
            resulting_revision=WorldRevision(1),
            details=sparse,
            occurrence=_occurrence(sparse),
        )
    complete = Moved(
        EntityId("loc-1"),
        resulting_location_id=EntityId("loc-1"),
        fatigue_delta=5.0,
        resulting_fatigue=5.0,
    )
    event = _physical_event(event_id="evt-1", cause=cause, details=complete)
    assert event.schema_version == EVENT_SCHEMA_REPLAY_V5
    assert event.cause == cause
    assert event.request_id == cause.request_id
    assert event.occurrence is not None
    assert event.occurrence.origin_location_id == EntityId("loc-1")
    assert event.occurrence.destination_location_id == EntityId("loc-1")


def test_died_and_system_cause_are_closed() -> None:
    system = SystemCause(
        RequestId("sys-1"),
        SystemEffectFamily.COMBINED_NEEDS,
        EntityId("body-1"),
        0,
    )
    event = _physical_event(
        event_id="evt-died",
        cause=system,
        details=Died(EntityId("body-1"), DeathCause.COMBINED_NEEDS),
        tick=3,
        revision=4,
    )
    assert event.actor_id is None
    assert event.target_id == EntityId("body-1")
    died_details = event.details
    assert type(died_details) is Died
    assert died_details.death_cause is DeathCause.COMBINED_NEEDS
    assert event.occurrence is not None
    assert event.occurrence.affected_entity_ids == (EntityId("body-1"),)


def test_attack_miss_and_weather_payloads() -> None:
    cause = ActionCause(RequestId("r-2"), EntityId("body-1"))
    miss = _physical_event(
        event_id="evt-a",
        cause=cause,
        details=Attacked(EntityId("body-2"), hit=False),
        tick=1,
    )
    miss_details = miss.details
    assert type(miss_details) is Attacked
    assert miss_details.hit is False
    weather_cause = SystemCause(
        RequestId("sys-w"),
        SystemEffectFamily.WEATHER,
        EntityId("loc-1"),
        0,
    )
    weather = _physical_event(
        event_id="evt-w",
        cause=weather_cause,
        details=WeatherChanged(EntityId("loc-1"), WeatherCondition.RAIN),
        tick=5,
        revision=2,
    )
    weather_details = weather.details
    assert type(weather_details) is WeatherChanged
    assert weather_details.condition is WeatherCondition.RAIN
    assert weather.occurrence is not None
    assert weather.occurrence.origin_location_id == EntityId("loc-1")


def test_normalize_ordered_events_rejects_mixed_replay_schemas() -> None:
    v2 = make_replayable_event(
        event_id=EventId("evt-v2"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=0,
        sequence=0,
        request_id=RequestId("r-1"),
        resulting_revision=WorldRevision(1),
        details=Waited(),
        actor_id=EntityId("body-1"),
    )
    v4 = _physical_event(
        event_id="evt-v4",
        cause=ActionCause(RequestId("r-2"), EntityId("body-1")),
        details=Waited(),
        sequence=1,
    )
    with pytest.raises(ValueError, match=EventValidationCode.MIXED_REPLAY_SCHEMA.value):
        normalize_ordered_events((v2, v4))


def test_communication_occurrence_marks_private_recipient() -> None:
    from world.events import Talked

    cause = ActionCause(RequestId("r-talk"), EntityId("body-1"))
    details = Talked(
        EntityId("body-2"),
        origin_utterance(text="hello", speaker_id=EntityId("body-1")),
    )
    event = _physical_event(event_id="evt-talk", cause=cause, details=details)
    assert event.occurrence is not None
    assert event.occurrence.private_recipient_ids == (EntityId("body-2"),)
    assert event.target_id == EntityId("body-2")
    assert event.occurrence.origin_location_id == EntityId("loc-1")
    assert event.schema_version == EVENT_SCHEMA_REPLAY_V5


def test_audit_schema_is_non_replayable() -> None:
    event = WorldEvent(
        event_id=EventId("evt-audit"),
        run_id="legacy-audit",
        world_id=WorldId("world-1"),
        tick=0,
        sequence=0,
        request_id=RequestId("r-1"),
        resulting_revision=WorldRevision(0),
        schema_version=EVENT_SCHEMA_AUDIT_V1,
        details=Waited(),
        actor_id=None,
        target_id=None,
    )
    assert event.schema_version == EVENT_SCHEMA_AUDIT_V1
    with pytest.raises(ValueError, match=EventValidationCode.NON_REPLAYABLE.value):
        from world.events import require_replayable_event

        require_replayable_event(event)


def test_resolved_action_effects_validate_alignment() -> None:
    request = RequestId("r-1")
    effect = ResolvedSearchEffect(
        request_id=request,
        success=True,
        resource_id=EntityId("res-1"),
        created_item_id=EntityId("item-1"),
    )
    bundle = ResolvedActionEffects({request: effect})
    assert bundle.require(request, ResolvedSearchEffect) is effect
    with pytest.raises(ValueError, match="key must equal"):
        ResolvedActionEffects(
            {
                RequestId("other"): effect,
            }
        )
    with pytest.raises(TypeError, match="ResolvedAttackEffect"):
        bundle.require(request, ResolvedAttackEffect)
