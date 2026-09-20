"""Cognition perspective ownership and strategy protocol tests."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.contracts import Perspective
from agents.models import AgentId
from llm.models import LLMResponse
from simulation.bootstrap import (
    AgentRegistration,
    WorldBootstrap,
    registration_translator,
)
from simulation.engine import WorldEngine
from simulation.models import SimulationRunConfig
from simulation.perception import (
    PerspectiveOwnershipCode,
    PerspectiveOwnershipError,
    build_perspective,
)
from social.models import CommunicationEnvelope, EnvelopeId
from tests.simulation_helpers import make_location, weather_for_locations
from tests.typecheck.cognition_strategies import (
    ScriptedCognitionStrategy,
    StubLLMBackedStrategy,
)
from world.actions import Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, LifeStatus
from world.observations import Observation
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)


class _Client:
    def complete(self, prompt: str) -> LLMResponse:
        return LLMResponse(provider="stub", model="echo", text=prompt, token_count=1)


def _alive(entity_id: str) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId("loc-1"),
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
        bodies=(_alive("body-1"), _alive("body-2")),
        weather=weather_for_locations(locations),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            AgentRegistration(AgentId("agent-2"), EntityId("body-2")),
        ),
    )


def test_scripted_and_stub_llm_strategies_share_propose_signature() -> None:
    agent_id = AgentId("agent-1")
    perspective = Perspective(
        agent_id=agent_id,
        observation=Observation(
            world_id=WorldId("world-1"),
            observer_id=EntityId("ent-1"),
            revision=WorldRevision(0),
        ),
        memories=(),
        beliefs=(),
        inbox=(),
    )
    scripted = ScriptedCognitionStrategy().propose(perspective)
    stub = StubLLMBackedStrategy(_Client()).propose(perspective)
    assert scripted == Wait()
    assert stub == Wait()
    assert type(scripted) is Wait
    assert type(stub) is Wait


def test_build_perspective_pairs_agent_with_own_observation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = WorldEngine(config=SimulationRunConfig(seed=1), bootstrap=_bootstrap())
    engine.observe()
    translator = registration_translator(engine._bootstrap)
    observation = engine.observation_for(AgentId("agent-1"))
    caplog.set_level(logging.DEBUG, logger="simulation.perception")
    perspective = build_perspective(
        agent_id=AgentId("agent-1"),
        observation=observation,
        translator=translator,
    )
    assert perspective.agent_id == AgentId("agent-1")
    assert perspective.observation is observation
    assert perspective.inbox == ()
    assert ScriptedCognitionStrategy().propose(perspective) == Wait()
    assert "perspective_built" in " ".join(
        record.getMessage() for record in caplog.records
    )
    assert "Camp" not in " ".join(record.getMessage() for record in caplog.records)


def test_build_perspective_rejects_cross_agent_observation() -> None:
    engine = WorldEngine(config=SimulationRunConfig(seed=2), bootstrap=_bootstrap())
    engine.observe()
    translator = registration_translator(engine._bootstrap)
    foreign = engine.observation_for(AgentId("agent-2"))
    with pytest.raises(PerspectiveOwnershipError) as exc_info:
        build_perspective(
            agent_id=AgentId("agent-1"),
            observation=foreign,
            translator=translator,
        )
    assert exc_info.value.code is PerspectiveOwnershipCode.CROSS_AGENT_OBSERVATION


def test_perspective_and_factory_reject_misaddressed_inbox() -> None:
    agent_id = AgentId("agent-1")
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
    )
    misaddressed = CommunicationEnvelope(
        envelope_id=EnvelopeId("e-1"),
        sender_id=AgentId("agent-2"),
        recipient_id=AgentId("agent-2"),
        payload={"text": "secret"},
    )
    with pytest.raises(ValueError, match="recipient_id"):
        Perspective(
            agent_id=agent_id,
            observation=observation,
            memories=(),
            beliefs=(),
            inbox=(misaddressed,),
        )
    translator = registration_translator(_bootstrap())
    with pytest.raises(PerspectiveOwnershipError) as exc_info:
        build_perspective(
            agent_id=agent_id,
            observation=observation,
            translator=translator,
            inbox=(misaddressed,),
        )
    assert exc_info.value.code is PerspectiveOwnershipCode.MISADDRESSED_INBOX


def test_inbox_is_out_of_band_not_derived_from_communications() -> None:
    from simulation.lifecycle import ActionSubmission
    from world.actions import Talk

    engine = WorldEngine(config=SimulationRunConfig(seed=3), bootstrap=_bootstrap())
    batch = engine.observe()
    engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-1"),
                Talk(EntityId("body-2"), "claim-only"),
            ),
        )
    )
    engine.observe()
    translator = registration_translator(engine._bootstrap)
    observation = engine.observation_for(AgentId("agent-2"))
    assert observation.communications
    perspective = build_perspective(
        agent_id=AgentId("agent-2"),
        observation=observation,
        translator=translator,
        inbox=(),
    )
    assert perspective.inbox == ()
    assert perspective.observation.communications[0].text == "claim-only"
