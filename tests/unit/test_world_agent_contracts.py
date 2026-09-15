"""Unit tests for world and agent contract surfaces."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agents.models import Agent, AgentId
from world._state import WorldState
from world._transitions import apply_trusted
from world.actions import (
    ActionOutcome,
    ActionProposal,
    ActionRequest,
    TransitionOutcome,
    Wait,
    accept_action_request,
)
from world.events import Waited, WorldEvent
from world.identifiers import (
    EntityId,
    EventId,
    ProposalId,
    RequestId,
    WorldId,
    WorldRevision,
)
from world.models import AgentBody, LifeStatus, Location
from world.observations import Observation
from world.values import Fatigue, Health, Hunger, TemperatureCelsius, Thirst

_ID_TEXT = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=24,
)


def _body(entity_id: str, location_id: str) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId(location_id),
        health=Health(10),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
    )


@given(
    observer=_ID_TEXT,
    revision=st.integers(min_value=0, max_value=10_000),
    location_name=_ID_TEXT,
)
@settings(max_examples=30, deadline=None)
def test_property_observation_projections_are_detached(
    observer: str, revision: int, location_name: str
) -> None:
    locations = [Location(entity_id=EntityId("loc-1"), name=location_name)]
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId(observer),
        revision=WorldRevision(revision),
        locations=locations,
    )
    locations.clear()
    assert observation.locations == (
        Location(entity_id=EntityId("loc-1"), name=location_name),
    )


def test_observation_is_typed_partial_and_immutable() -> None:
    body = _body("observer-1", "loc-1")
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("observer-1"),
        revision=WorldRevision(1),
        self_body=body,
        locations=(Location(entity_id=EntityId("loc-1"), name="Camp"),),
    )
    assert observation.self_body == body
    assert observation.items == ()
    with pytest.raises(AttributeError):
        observation.observer_id = EntityId("other")  # type: ignore[misc]
    with pytest.raises(ValueError, match="must match observer_id"):
        Observation(
            world_id=WorldId("world-1"),
            observer_id=EntityId("observer-1"),
            revision=WorldRevision(1),
            self_body=_body("other", "loc-1"),
        )


def test_world_event_is_immutable_occurrence() -> None:
    event = WorldEvent(
        event_id=EventId("event-1"),
        request_id=RequestId("r-1"),
        world_id=WorldId("world-1"),
        revision=WorldRevision(3),
        details=Waited(),
    )
    assert event.details == Waited()
    with pytest.raises(AttributeError):
        event.revision = WorldRevision(4)  # type: ignore[misc]


def test_gateway_rejects_proposal_and_raw_mapping() -> None:
    proposal = ActionProposal(
        proposal_id=ProposalId("p-1"),
        command=Wait(),
    )
    mapping = {
        "request_id": "r-1",
        "actor_id": "actor-1",
        "kind": "wait",
        "revision": 1,
    }
    with pytest.raises(TypeError, match="ActionProposal"):
        accept_action_request(proposal)
    with pytest.raises(TypeError, match="raw mappings"):
        accept_action_request(mapping)

    request = ActionRequest(
        request_id=RequestId("r-1"),
        proposal_id=ProposalId("p-1"),
        world_id=WorldId("world-1"),
        actor_id=EntityId("actor-1"),
        revision=WorldRevision(1),
        command=Wait(),
    )
    assert accept_action_request(request) is request


def test_trusted_transition_rejects_proposals() -> None:
    class _Transition:
        def apply(self, state: WorldState, request: ActionRequest) -> ActionOutcome:
            return ActionOutcome(
                request_id=request.request_id,
                outcome=TransitionOutcome.APPLIED,
                revision=state.revision,
            )

    proposal = ActionProposal(
        proposal_id=ProposalId("p-1"),
        command=Wait(),
    )
    with pytest.raises(TypeError, match="ActionProposal"):
        apply_trusted(_Transition(), WorldState(WorldRevision(0)), proposal)


def test_agent_id_is_not_an_entity_id() -> None:
    agent_id = AgentId("agent-1")
    entity_id = EntityId("agent-1")
    assert not isinstance(agent_id, EntityId)
    assert not isinstance(entity_id, AgentId)
    assert agent_id.value == entity_id.value


def test_agent_exposes_identity_without_memory_collections() -> None:
    agent = Agent(agent_id=AgentId("agent-1"), name="Ada", goals=())
    assert agent.agent_id == AgentId("agent-1")
    assert agent.goals == ()
    assert not hasattr(agent, "beliefs")
    assert not hasattr(agent, "on_change")


def test_booleans_are_rejected_as_revisions() -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        WorldRevision(True)


def test_empty_identifiers_are_rejected() -> None:
    with pytest.raises(ValueError):
        EntityId("")
    with pytest.raises(ValueError):
        AgentId("")
    with pytest.raises(ValueError):
        ProposalId("")


def test_transition_outcome_is_closed() -> None:
    assert TransitionOutcome.APPLIED.value == "applied"
    assert set(TransitionOutcome) == {
        TransitionOutcome.APPLIED,
        TransitionOutcome.NOT_APPLIED,
    }
