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
from world.actions import Move, Take, Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, Item, LifeStatus, Location
from world.values import Fatigue, Health, Hunger, TemperatureCelsius, Thirst

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
    )


def _bootstrap() -> WorldBootstrap:
    return WorldBootstrap(
        world_id=WorldId("world-1"),
        revision=WorldRevision(0),
        locations=(Location(entity_id=EntityId("loc-1"), name="Camp"),),
        items=(
            Item(
                entity_id=EntityId("item-1"),
                name="Rock",
                location_id=EntityId("loc-1"),
            ),
        ),
        bodies=(_alive("body-1"), _alive("body-2")),
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
    engine.resolve_tick(
        (ActionSubmission(batch2.token, AgentId("agent-2"), Wait()),)
    )


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
            ActionSubmission(batch.token, AgentId("agent-2"), Move(EntityId("loc-1"))),
            ActionSubmission(batch.token, AgentId("agent-1"), Wait()),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    assert result.resolutions[1].status is ActionResolutionStatus.DEFERRED_POLICY
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
        EngineDiagnosticCode.RESOLUTION_DEFERRED,
        EngineDiagnosticCode.RESOLUTION_DUPLICATE,
    ):
        assert code.value in debug_text

    stale = batch.token
    next_batch = engine.observe()
    with pytest.raises(ValueError, match=r"stale|mismatch"):
        engine.resolve_tick(
            (ActionSubmission(stale, AgentId("agent-1"), Wait()),)
        )
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
    engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId("agent-1"), Wait()),)
    )
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
