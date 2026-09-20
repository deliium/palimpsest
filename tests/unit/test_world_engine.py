"""WorldEngine observation and resolution lifecycle."""

from __future__ import annotations

import io
import logging
from collections.abc import Iterator

import pytest

from agents.models import AgentId
from infrastructure.logging import configure_logging, reset_logging_for_tests
from infrastructure.settings import AppEnvironment, LogLevel, load_settings
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import EnginePhase, WorldEngine
from simulation.lifecycle import (
    ActionResolutionStatus,
    ActionSubmission,
    EngineDiagnosticCode,
)
from simulation.models import SimulationRunConfig
from tests.simulation_helpers import make_item, make_location, weather_for_locations
from world.actions import Sleep, Take, Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, LifeStatus
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)

_ENGINE_LOGGER = "simulation.engine"
_FORBIDDEN_LOG_FRAGMENTS = (
    "Rock",
    "Camp",
    "self_body",
    "inventory",
    "AgentBody",
    "WorldState",
    "Talk(",
    "Hello",
)


def _alive(entity_id: str, location_id: str = "loc-1") -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId(location_id),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _bootstrap() -> WorldBootstrap:
    locations = (make_location("loc-1", name="Camp"),)
    return WorldBootstrap(
        world_id=WorldId("world-1"),
        revision=WorldRevision(0),
        locations=locations,
        items=(make_item("item-1", name="Rock", location_id="loc-1"),),
        bodies=(_alive("body-1"), _alive("body-2")),
        weather=weather_for_locations(locations),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            AgentRegistration(AgentId("agent-2"), EntityId("body-2")),
        ),
    )


def _messages(caplog: pytest.LogCaptureFixture) -> str:
    return " ".join(record.getMessage() for record in caplog.records)


def _assert_no_sensitive_payload(text: str) -> None:
    for fragment in _FORBIDDEN_LOG_FRAGMENTS:
        assert fragment not in text


@pytest.fixture
def logging_sandbox() -> Iterator[None]:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    try:
        yield
    finally:
        reset_logging_for_tests(original_handlers, original_level)


def test_observe_is_idempotent_within_open_tick() -> None:
    engine = WorldEngine(config=SimulationRunConfig(seed=1), bootstrap=_bootstrap())
    assert engine.phase is EnginePhase.AWAITING_OBSERVATION
    first = engine.observe()
    second = engine.observe()
    assert first == second
    assert engine.phase.value == EnginePhase.AWAITING_SUBMISSIONS.value
    assert first.token.tick.value == 0


def test_observation_for_routes_registered_agent_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = WorldEngine(config=SimulationRunConfig(seed=7), bootstrap=_bootstrap())
    with pytest.raises(RuntimeError, match="open observation batch"):
        engine.observation_for(AgentId("agent-1"))
    batch = engine.observe()
    caplog.set_level(logging.DEBUG, logger=_ENGINE_LOGGER)
    first = engine.observation_for(AgentId("agent-1"))
    second = engine.observation_for(AgentId("agent-1"))
    other = engine.observation_for(AgentId("agent-2"))
    assert first == second
    assert first.observer_id == EntityId("body-1")
    assert other.observer_id == EntityId("body-2")
    assert first == batch.for_observer(EntityId("body-1"))
    assert first != other
    with pytest.raises(KeyError, match="unknown agent_id"):
        engine.observation_for(AgentId("missing"))
    messages = _messages(caplog)
    assert EngineDiagnosticCode.OBSERVATION_ROUTED.value in messages
    _assert_no_sensitive_payload(messages)


def test_prior_tick_events_appear_only_on_next_observe() -> None:
    from world.actions import Talk

    engine = WorldEngine(config=SimulationRunConfig(seed=8), bootstrap=_bootstrap())
    batch0 = engine.observe()
    assert all(observation.occurrences == () for observation in batch0.observations)
    assert all(observation.communications == () for observation in batch0.observations)
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch0.token,
                AgentId("agent-1"),
                Talk(EntityId("body-2"), "hello-agent"),
            ),
        )
    )
    assert result.events
    assert all(record.event.tick == 0 for record in result.events)
    batch1 = engine.observe()
    speaker = engine.observation_for(AgentId("agent-1"))
    listener = engine.observation_for(AgentId("agent-2"))
    assert speaker.communications
    assert listener.communications
    assert speaker.communications[0].text == "hello-agent"
    assert listener.communications[0].text == "hello-agent"
    assert all(
        occurrence.provenance.source_tick == 0
        for occurrence in (*speaker.occurrences, *listener.occurrences)
    )
    # Open tick has not committed yet; outcomes stay out of the observation.
    assert batch1.tick.value == 1
    assert engine._snapshot.prior_event_window
    assert all(event.tick == 0 for event in engine._snapshot.prior_event_window)


def test_eventless_tick_carries_empty_prior_window() -> None:
    locations = (make_location("loc-1", name="Camp"),)
    dead = AgentBody(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        health=Health(0),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.DEAD,
        carry_capacity=CarryCapacity(10),
    )
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-1"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=(dead,),
        weather=weather_for_locations(locations),
        registrations=(AgentRegistration(AgentId("agent-1"), EntityId("body-1")),),
    )
    engine = WorldEngine(config=SimulationRunConfig(seed=9), bootstrap=bootstrap)
    engine.observe()
    result = engine.resolve_tick(())
    assert result.events == ()
    engine.observe()
    assert engine._snapshot.prior_event_window == ()
    observation = engine.observation_for(AgentId("agent-1"))
    assert observation.occurrences == ()
    assert observation.communications == ()


def test_resolve_wait_and_take_advances_tick_and_revision(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = WorldEngine(config=SimulationRunConfig(seed=2), bootstrap=_bootstrap())
    batch = engine.observe()
    caplog.set_level(logging.DEBUG, logger=_ENGINE_LOGGER)
    result = engine.resolve_tick(
        (
            ActionSubmission(batch.token, AgentId("agent-1"), Take(EntityId("item-1"))),
            ActionSubmission(batch.token, AgentId("agent-2"), Wait()),
        )
    )
    assert result.tick.value == 0
    assert result.resulting_tick.value == 1
    assert result.base_revision == WorldRevision(0)
    assert result.resulting_revision == WorldRevision(1)
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    assert result.resolutions[1].status is ActionResolutionStatus.APPLIED
    assert engine.tick.value == 1
    assert engine.revision == WorldRevision(1)
    assert engine.phase is EnginePhase.AWAITING_OBSERVATION
    messages = _messages(caplog)
    assert EngineDiagnosticCode.TICK_COMMITTED.value in messages
    _assert_no_sensitive_payload(messages)


def test_duplicate_submission_and_stale_token() -> None:
    engine = WorldEngine(config=SimulationRunConfig(seed=3), bootstrap=_bootstrap())
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(batch.token, AgentId("agent-1"), Wait()),
            ActionSubmission(batch.token, AgentId("agent-1"), Wait()),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    assert result.resolutions[1].status is ActionResolutionStatus.DUPLICATE

    batch2 = engine.observe()
    with pytest.raises(ValueError, match=r"stale|mismatch"):
        engine.resolve_tick(
            (ActionSubmission(batch.token, AgentId("agent-1"), Wait()),)
        )
    # Engine remains usable after failed resolve with prior snapshot preserved.
    engine.resolve_tick((ActionSubmission(batch2.token, AgentId("agent-2"), Wait()),))


def test_engine_logs_debug_info_warn_error_without_payloads(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Task 11: assert DEBUG outcomes, one INFO commit, WARN misuse, ERROR abort."""
    caplog.set_level(logging.DEBUG, logger=_ENGINE_LOGGER)
    engine = WorldEngine(config=SimulationRunConfig(seed=11), bootstrap=_bootstrap())

    with pytest.raises(RuntimeError, match="open observation token"):
        engine.resolve_tick(())
    assert any(
        record.levelno == logging.WARNING
        and EngineDiagnosticCode.LIFECYCLE_MISUSE.value in record.getMessage()
        for record in caplog.records
    )

    batch = engine.observe()
    assert any(
        record.levelno == logging.DEBUG
        and EngineDiagnosticCode.OBSERVATIONS_ISSUED.value in record.getMessage()
        for record in caplog.records
    )
    engine.observe()  # idempotent replay path

    result = engine.resolve_tick(
        (
            ActionSubmission(batch.token, AgentId("agent-1"), Take(EntityId("item-1"))),
            ActionSubmission(batch.token, AgentId("agent-2"), Sleep()),
            ActionSubmission(batch.token, AgentId("agent-1"), Wait()),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    assert result.resolutions[1].status is ActionResolutionStatus.APPLIED
    assert result.resolutions[2].status is ActionResolutionStatus.DUPLICATE

    info_commits = [
        record
        for record in caplog.records
        if record.levelno == logging.INFO
        and EngineDiagnosticCode.TICK_COMMITTED.value in record.getMessage()
    ]
    assert len(info_commits) == 1

    debug_text = _messages(caplog)
    for code in (
        EngineDiagnosticCode.SUBMISSION_ADMITTED,
        EngineDiagnosticCode.RESOLUTION_APPLIED,
        EngineDiagnosticCode.RESOLUTION_DUPLICATE,
    ):
        assert code.value in debug_text

    stale = batch.token
    next_batch = engine.observe()
    with pytest.raises(ValueError, match=r"stale|mismatch"):
        engine.resolve_tick((ActionSubmission(stale, AgentId("agent-1"), Wait()),))
    assert any(
        record.levelno == logging.WARNING
        and EngineDiagnosticCode.TOKEN_STALE.value in record.getMessage()
        for record in caplog.records
    )

    # Stale-token failure is caught inside the candidate try and aborts.
    assert any(
        record.levelno == logging.ERROR
        and EngineDiagnosticCode.CANDIDATE_ABORTED.value in record.getMessage()
        for record in caplog.records
    )
    assert engine.tick.value == next_batch.tick.value

    # Successful retry after abort still usable with current token.
    engine.resolve_tick(
        (ActionSubmission(next_batch.token, AgentId("agent-2"), Wait()),)
    )
    final = _messages(caplog)
    _assert_no_sensitive_payload(final)
    assert "observation=" not in final
    assert "AgentRegistration" not in final
    assert "bodies=" not in final


def test_engine_respects_palimpsest_log_level(
    logging_sandbox: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Engine diagnostics honor PALIMPSEST_LOG_LEVEL via configured root logging."""
    monkeypatch.setenv("PALIMPSEST_LOG_LEVEL", "WARNING")
    stream = io.StringIO()
    settings = load_settings(
        env_file=False,
        environment=AppEnvironment.LOCAL,
        log_level=LogLevel.WARNING,
    )
    assert settings.log_level is LogLevel.WARNING
    configure_logging(settings, stream=stream)

    engine = WorldEngine(config=SimulationRunConfig(seed=17), bootstrap=_bootstrap())
    with pytest.raises(RuntimeError, match="open observation token"):
        engine.resolve_tick(())
    batch = engine.observe()
    engine.resolve_tick((ActionSubmission(batch.token, AgentId("agent-1"), Wait()),))
    next_batch = engine.observe()
    with pytest.raises(ValueError, match=r"stale|mismatch"):
        engine.resolve_tick(
            (ActionSubmission(batch.token, AgentId("agent-1"), Wait()),)
        )
    assert next_batch.tick.value == engine.tick.value

    output = stream.getvalue()
    assert EngineDiagnosticCode.LIFECYCLE_MISUSE.value in output
    assert EngineDiagnosticCode.TOKEN_STALE.value in output
    assert EngineDiagnosticCode.CANDIDATE_ABORTED.value in output
    assert EngineDiagnosticCode.OBSERVATIONS_ISSUED.value not in output
    assert EngineDiagnosticCode.RESOLUTION_APPLIED.value not in output
    assert EngineDiagnosticCode.TICK_COMMITTED.value not in output
    _assert_no_sensitive_payload(output)


def test_autonomous_only_tick_applies_physiology_without_submissions(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = WorldEngine(config=SimulationRunConfig(seed=21), bootstrap=_bootstrap())
    engine.observe()
    caplog.set_level(logging.DEBUG, logger=_ENGINE_LOGGER)
    result = engine.resolve_tick(())
    assert result.resolutions == ()
    # Two living bodies → NeedsApplied + ExposureApplied each.
    assert len(result.events) == 4
    assert result.resulting_revision == WorldRevision(1)
    assert engine.revision == WorldRevision(1)
    body = engine._snapshot.world.state.bodies[EntityId("body-1")]
    assert body.hunger.value == 2.0
    assert body.thirst.value == 3.0
    assert body.fatigue.value == 1.0
    messages = _messages(caplog)
    assert "family_combined_needs=2" in messages
    assert "family_exposure=2" in messages
    assert EngineDiagnosticCode.TICK_COMMITTED.value in messages
    assert "deaths=0" in messages
    _assert_no_sensitive_payload(messages)


def test_wait_then_autonomous_merges_into_one_revision() -> None:
    engine = WorldEngine(config=SimulationRunConfig(seed=22), bootstrap=_bootstrap())
    batch = engine.observe()
    result = engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId("agent-1"), Wait()),)
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    assert result.resulting_revision == WorldRevision(1)
    # Wait + 2 needs + 2 exposure
    assert len(result.events) == 5
    assert result.events[0].event.details.kind == "wait"
    assert all(
        record.event.resulting_revision == WorldRevision(1) for record in result.events
    )


def test_all_dead_autonomous_tick_is_noop() -> None:
    locations = (make_location("loc-1", name="Camp"),)
    dead = AgentBody(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        health=Health(0),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.DEAD,
        carry_capacity=CarryCapacity(10),
    )
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-1"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=(dead,),
        weather=weather_for_locations(locations),
        registrations=(AgentRegistration(AgentId("agent-1"), EntityId("body-1")),),
    )
    engine = WorldEngine(config=SimulationRunConfig(seed=23), bootstrap=bootstrap)
    engine.observe()
    result = engine.resolve_tick(())
    assert result.events == ()
    assert result.resulting_revision == WorldRevision(0)
    assert engine.tick.value == 1
