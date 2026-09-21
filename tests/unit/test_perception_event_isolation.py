"""Event audience, communication, routing, and authority isolation proofs."""

from __future__ import annotations

from world.communications import origin_utterance

import logging

import pytest

from agents.models import AgentId
from simulation.bootstrap import (
    AgentRegistration,
    WorldBootstrap,
    registration_translator,
)
from simulation.engine import WorldEngine
from simulation.lifecycle import (
    ActionResolutionStatus,
    ActionSubmission,
    EngineDiagnosticCode,
)
from simulation.models import SimulationRunConfig
from simulation.perception import PerspectiveOwnershipError, build_perspective
from tests.simulation_helpers import (
    connected_locations,
    make_item,
    make_resource,
    make_weather,
)
from world._perception import PerceptionService
from world._state import WorldState, rebuild_world_state
from world.actions import Attack, Help, Move, Take, Talk, Wait
from world.effects import (
    ActionCause,
    DeathCause,
    SystemCause,
    SystemEffectFamily,
)
from world.events import (
    Attacked,
    Died,
    Helped,
    Moved,
    NeedsApplied,
    Taken,
    Talked,
    WeatherChanged,
    build_occurrence_context,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.models import AgentBody, LifeStatus, copy_weather
from world.observations import (
    Observation,
    ObservationAudienceRole,
    ObservationContext,
    ObservationSourceKind,
)
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
    WeatherCondition,
)

_WORLD = WorldId("world-1")
_SERVICE = PerceptionService()


def _body(
    entity_id: str,
    location_id: str,
    *,
    dead: bool = False,
) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId(location_id),
        health=Health(0 if dead else 100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.DEAD if dead else LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _state() -> WorldState:
    return WorldState(
        WorldRevision(1),
        locations=connected_locations(("loc-1", "Camp"), ("loc-2", "Forest")),
        items=(make_item("item-1", name="Rock", location_id="loc-1"),),
        resources=(
            make_resource("res-1", name="Spring", location_id="loc-1", quantity=2.0),
        ),
        bodies=(
            _body("body-1", "loc-1"),
            _body("body-2", "loc-1"),
            _body("body-3", "loc-2"),
            _body("body-dead", "loc-1", dead=True),
        ),
        weather=(
            make_weather("loc-1", condition=WeatherCondition.CLEAR),
            make_weather("loc-2", condition=WeatherCondition.CLEAR),
        ),
    )


def _action_event(
    *,
    event_id: str,
    sequence: int,
    details: object,
    actor: str,
    origin: str = "loc-1",
    destination: str | None = None,
) -> object:
    return make_physical_replayable_event(
        event_id=EventId(event_id),
        run_id="run-1",
        world_id=_WORLD,
        tick=0,
        sequence=sequence,
        cause=ActionCause(RequestId(f"req-{event_id}"), EntityId(actor)),
        resulting_revision=WorldRevision(1),
        details=details,  # type: ignore[arg-type]
        occurrence=build_occurrence_context(
            details,  # type: ignore[arg-type]
            origin_location_id=EntityId(origin),
            destination_location_id=(
                None if destination is None else EntityId(destination)
            ),
        ),
    )


def _project(
    prior_events: tuple[object, ...],
    *,
    tick: int = 1,
    state: WorldState | None = None,
) -> tuple[Observation, ...]:
    return _SERVICE.project(
        world_id=_WORLD,
        state=_state() if state is None else state,
        observer_ids=(
            EntityId("body-1"),
            EntityId("body-2"),
            EntityId("body-3"),
            EntityId("body-dead"),
        ),
        context=ObservationContext(tick=tick),
        prior_events=prior_events,  # type: ignore[arg-type]
    )


def test_move_audiences_actor_witness_remote() -> None:
    move = _action_event(
        event_id="evt-move",
        sequence=0,
        details=Moved(
            EntityId("loc-2"),
            resulting_location_id=EntityId("loc-2"),
            fatigue_delta=5.0,
            resulting_fatigue=5.0,
        ),
        actor="body-1",
        origin="loc-1",
        destination="loc-2",
    )
    actor, local, remote, _dead = _project((move,))
    assert actor.occurrences[0].audience_role is ObservationAudienceRole.ACTOR
    assert local.occurrences[0].audience_role is ObservationAudienceRole.WITNESS
    assert remote.occurrences[0].audience_role is ObservationAudienceRole.WITNESS


def test_attack_help_and_death_audiences() -> None:
    attack = _action_event(
        event_id="evt-attack",
        sequence=0,
        details=Attacked(
            EntityId("body-2"),
            hit=True,
            damage=12,
            resulting_target_health=88.0,
        ),
        actor="body-1",
    )
    help_event = _action_event(
        event_id="evt-help",
        sequence=1,
        details=Helped(
            EntityId("body-2"),
            health_delta=10.0,
            resulting_target_health=98.0,
            helper_fatigue_delta=5.0,
            resulting_helper_fatigue=5.0,
        ),
        actor="body-1",
    )
    died = make_physical_replayable_event(
        event_id=EventId("evt-died"),
        run_id="run-1",
        world_id=_WORLD,
        tick=0,
        sequence=2,
        cause=ActionCause(RequestId("req-attack"), EntityId("body-1")),
        resulting_revision=WorldRevision(1),
        details=Died(EntityId("body-2"), DeathCause.ATTACK),
        occurrence=build_occurrence_context(
            Died(EntityId("body-2"), DeathCause.ATTACK),
            origin_location_id=EntityId("loc-1"),
        ),
    )
    actor, target, remote, _ = _project((attack, help_event, died))
    assert actor.occurrences[0].audience_role is ObservationAudienceRole.ACTOR
    assert target.occurrences[0].audience_role is ObservationAudienceRole.TARGET
    assert remote.occurrences == ()
    assert actor.occurrences[0].success is True
    kinds = {item.kind for item in actor.occurrences}
    assert {"attack", "help", "died"} <= kinds


def test_transfer_and_system_events_are_location_scoped() -> None:
    taken = _action_event(
        event_id="evt-take",
        sequence=0,
        details=Taken(EntityId("item-1"), resulting_holder_id=EntityId("body-1")),
        actor="body-1",
    )
    needs = make_physical_replayable_event(
        event_id=EventId("evt-needs"),
        run_id="run-1",
        world_id=_WORLD,
        tick=0,
        sequence=1,
        cause=SystemCause(
            cause_id=RequestId("sys-needs"),
            effect_family=SystemEffectFamily.COMBINED_NEEDS,
            entity_id=EntityId("body-1"),
            family_ordinal=0,
        ),
        resulting_revision=WorldRevision(1),
        details=NeedsApplied(
            EntityId("body-1"),
            resulting_hunger=2.0,
            resulting_thirst=3.0,
            resulting_fatigue=1.0,
            health_delta=0.0,
            resulting_health=100.0,
        ),
        occurrence=build_occurrence_context(
            NeedsApplied(
                EntityId("body-1"),
                resulting_hunger=2.0,
                resulting_thirst=3.0,
                resulting_fatigue=1.0,
                health_delta=0.0,
                resulting_health=100.0,
            ),
            origin_location_id=EntityId("loc-1"),
        ),
    )
    weather = make_physical_replayable_event(
        event_id=EventId("evt-weather"),
        run_id="run-1",
        world_id=_WORLD,
        tick=0,
        sequence=2,
        cause=SystemCause(
            cause_id=RequestId("sys-weather"),
            effect_family=SystemEffectFamily.WEATHER,
            entity_id=EntityId("loc-2"),
            family_ordinal=0,
        ),
        resulting_revision=WorldRevision(1),
        details=WeatherChanged(EntityId("loc-2"), WeatherCondition.RAIN),
        occurrence=build_occurrence_context(
            WeatherChanged(EntityId("loc-2"), WeatherCondition.RAIN),
            origin_location_id=EntityId("loc-2"),
        ),
    )
    actor, local, remote, _ = _project((taken, needs, weather))
    assert any(item.kind == "take" for item in actor.occurrences)
    assert any(item.kind == "needs_applied" for item in actor.occurrences)
    assert all(item.kind != "weather_changed" for item in actor.occurrences)
    assert any(item.kind == "weather_changed" for item in remote.occurrences)
    assert all(item.kind != "take" for item in remote.occurrences)
    assert any(item.kind == "take" for item in local.occurrences)


def test_communication_is_claim_only_and_private() -> None:
    talk = _action_event(
        event_id="evt-talk",
        sequence=0,
        details=Talked(EntityId("body-2"), origin_utterance(text="secret-claim", speaker_id=EntityId("body-1"))),
        actor="body-1",
    )
    speaker, listener, remote, dead = _project((talk,))
    assert speaker.communications[0].utterance.content.text == "secret-claim"
    assert listener.communications[0].utterance.content.text == "secret-claim"
    assert remote.communications == ()
    assert dead.communications == ()
    assert speaker.communications[0].provenance.source_kind is (
        ObservationSourceKind.COMMUNICATION
    )
    assert not hasattr(speaker.communications[0], "is_true")
    assert speaker.occurrences == ()


def test_low_visibility_hides_bystander_non_movement_events() -> None:
    taken = _action_event(
        event_id="evt-take",
        sequence=0,
        details=Taken(EntityId("item-1"), resulting_holder_id=EntityId("body-1")),
        actor="body-1",
    )
    state = _state()
    weather = dict(state.weather)
    weather[EntityId("loc-1")] = copy_weather(
        weather[EntityId("loc-1")], condition=WeatherCondition.STORM
    )
    dark = rebuild_world_state(state, weather=weather)
    actor, bystander, remote, _ = _project((taken,), tick=1, state=dark)
    assert actor.visibility is not None and actor.visibility < 0.5
    assert actor.occurrences
    assert bystander.occurrences == ()
    assert remote.occurrences == ()


def _engine() -> WorldEngine:
    locations = connected_locations(("loc-1", "Camp"), ("loc-2", "Forest"))
    return WorldEngine(
        config=SimulationRunConfig(seed=11),
        bootstrap=WorldBootstrap(
            world_id=_WORLD,
            revision=WorldRevision(0),
            locations=locations,
            items=(make_item("item-1", name="Rock", location_id="loc-1"),),
            bodies=(_body("body-1", "loc-1"), _body("body-2", "loc-1")),
            weather=(make_weather("loc-1"), make_weather("loc-2")),
            registrations=(
                AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
                AgentRegistration(AgentId("agent-2"), EntityId("body-2")),
            ),
        ),
    )


def test_rejected_and_duplicate_actions_do_not_appear_as_occurrences() -> None:
    engine = _engine()
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(batch.token, AgentId("agent-1"), Take(EntityId("item-1"))),
            ActionSubmission(batch.token, AgentId("agent-1"), Take(EntityId("item-1"))),
            ActionSubmission(
                batch.token, AgentId("agent-2"), Take(EntityId("missing-item"))
            ),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    assert result.resolutions[1].status is ActionResolutionStatus.DUPLICATE
    assert result.resolutions[2].status is ActionResolutionStatus.REJECTED
    next_batch = engine.observe()
    kinds = {
        occurrence.kind
        for observation in next_batch.observations
        for occurrence in observation.occurrences
    }
    assert "take" in kinds
    take_events = [
        record.event for record in result.events if record.event.event_type == "take"
    ]
    assert len(take_events) == 1


def test_eventless_window_and_idempotent_observe() -> None:
    engine = _engine()
    first = engine.observe()
    second = engine.observe()
    assert first == second
    assert all(observation.occurrences == () for observation in first.observations)
    engine.resolve_tick(())
    after = engine.observe()
    again = engine.observe()
    assert after == again


def test_observation_for_rejects_cross_agent_batch_handoff(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _engine()
    engine.observe()
    caplog.set_level(logging.DEBUG, logger="simulation.engine")
    own = engine.observation_for(AgentId("agent-1"))
    other = engine.observation_for(AgentId("agent-2"))
    assert own.observer_id == EntityId("body-1")
    assert other.observer_id == EntityId("body-2")
    assert own != other
    translator = registration_translator(engine._bootstrap)
    perspective = build_perspective(
        agent_id=AgentId("agent-1"),
        observation=own,
        translator=translator,
    )
    with pytest.raises(PerspectiveOwnershipError):
        build_perspective(
            agent_id=AgentId("agent-1"),
            observation=other,
            translator=translator,
        )
    assert perspective.observation is own
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert EngineDiagnosticCode.OBSERVATION_ROUTED.value in messages
    assert "Rock" not in messages


def test_next_tick_delivers_prior_talk_only() -> None:
    engine = _engine()
    batch = engine.observe()
    engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-1"),
                Talk(EntityId("body-2"), origin_utterance(text="next-tick-only", speaker_id=EntityId("body-1"))),
            ),
        )
    )
    engine.observe()
    listener = engine.observation_for(AgentId("agent-2"))
    assert listener.communications
    assert listener.communications[0].utterance.content.text == "next-tick-only"
    batch2 = engine.observe()
    engine.resolve_tick((ActionSubmission(batch2.token, AgentId("agent-2"), Wait()),))
    engine.observe()
    later = engine.observation_for(AgentId("agent-2"))
    assert all(
        communication.utterance.content.text != "next-tick-only" for communication in later.communications
    )


def test_move_help_attack_engine_path_audiences() -> None:
    engine = _engine()
    batch = engine.observe()
    engine.resolve_tick(
        (
            ActionSubmission(batch.token, AgentId("agent-1"), Help(EntityId("body-2"))),
            ActionSubmission(
                batch.token, AgentId("agent-2"), Attack(EntityId("body-1"))
            ),
        )
    )
    next_obs = engine.observe()
    by_agent = {
        observation.observer_id: observation for observation in next_obs.observations
    }
    helper = by_agent[EntityId("body-1")]
    target = by_agent[EntityId("body-2")]
    assert any(item.kind == "help" for item in helper.occurrences)
    assert any(item.kind == "attack" for item in target.occurrences)
    batch2 = engine.observe()
    engine.resolve_tick(
        (ActionSubmission(batch2.token, AgentId("agent-1"), Move(EntityId("loc-2"))),)
    )
    engine.observe()
    moved = engine.observation_for(AgentId("agent-1"))
    assert any(item.kind == "move" for item in moved.occurrences)
