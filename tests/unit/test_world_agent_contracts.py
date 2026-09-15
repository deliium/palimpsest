"""Unit tests for world and agent contract surfaces."""

from __future__ import annotations

from types import MappingProxyType

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
    OutcomeCategory,
    accept_action_request,
)
from world.events import WorldEvent
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


def test_world_event_is_detached_from_source_mapping() -> None:
    payload = {"actors": [{"id": "e-1"}]}
    event = WorldEvent(
        event_id=EventId("event-1"),
        revision=WorldRevision(3),
        kind="spawned",
        payload=payload,
    )
    payload["actors"][0]["id"] = "mutated"
    assert event.payload["actors"] == ({"id": "e-1"},)
    assert isinstance(event.payload, MappingProxyType)


def test_gateway_rejects_proposal_and_raw_mapping() -> None:
    proposal = ActionProposal(
        proposal_id=ProposalId("p-1"),
        actor_id=EntityId("actor-1"),
        kind="speak",
        payload={"text": "hello"},
    )
    mapping = {
        "request_id": "r-1",
        "actor_id": "actor-1",
        "kind": "speak",
        "revision": 1,
        "payload": {},
    }
    with pytest.raises(TypeError, match="ActionProposal"):
        accept_action_request(proposal)
    with pytest.raises(TypeError, match="raw mappings"):
        accept_action_request(mapping)

    request = ActionRequest(
        request_id=RequestId("r-1"),
        actor_id=EntityId("actor-1"),
        kind="speak",
        revision=WorldRevision(1),
        payload={"text": "hello"},
    )
    assert accept_action_request(request) is request


def test_trusted_transition_rejects_proposals() -> None:
    class _Transition:
        def apply(self, state: WorldState, request: ActionRequest) -> ActionOutcome:
            return ActionOutcome(
                request_id=request.request_id,
                category=OutcomeCategory.ACCEPTED,
                revision=state.revision,
            )

    proposal = ActionProposal(
        proposal_id=ProposalId("p-1"),
        actor_id=EntityId("actor-1"),
        kind="speak",
        payload={},
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


def test_outcome_category_is_explicit() -> None:
    assert OutcomeCategory.ACCEPTED.value == "accepted"
    assert set(OutcomeCategory) == {
        OutcomeCategory.ACCEPTED,
        OutcomeCategory.REJECTED,
        OutcomeCategory.INVALID,
    }
