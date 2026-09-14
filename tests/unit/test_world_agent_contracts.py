"""Unit tests for world and agent contract surfaces."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agents.models import AgentId, AgentState
from world._state import WorldState
from world._transitions import apply_trusted
from world.actions import (
    ActionOutcome,
    ActionProposal,
    ActionRequest,
    OutcomeCategory,
    ProposalId,
    RequestId,
    accept_action_request,
)
from world.events import EventId, WorldEvent
from world.identifiers import EntityId, WorldRevision
from world.observations import Observation

_ID_TEXT = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=24,
)
_PAYLOADS = st.dictionaries(
    keys=st.text(min_size=1, max_size=12),
    values=st.one_of(
        st.booleans(),
        st.integers(min_value=-1000, max_value=1000),
        st.text(max_size=24),
    ),
    max_size=4,
)


@given(
    observer=_ID_TEXT,
    revision=st.integers(min_value=0, max_value=10_000),
    payload=_PAYLOADS,
)
@settings(max_examples=30, deadline=None)
def test_property_observation_payload_is_detached(
    observer: str, revision: int, payload: dict[str, Any]
) -> None:
    source = dict(payload)
    observation = Observation(
        observer_id=EntityId(observer),
        revision=WorldRevision(revision),
        payload=source,
    )
    source.clear()
    assert dict(observation.payload) == payload
    with pytest.raises(TypeError):
        observation.payload["__mut__"] = True  # type: ignore[index]


def test_observation_is_deeply_immutable_and_detached() -> None:
    source: dict[str, Any] = {"nested": {"flag": True}, "items": ["a", "b"]}
    observation = Observation(
        observer_id=EntityId("observer-1"),
        revision=WorldRevision(1),
        payload=source,
    )
    source["nested"]["flag"] = False
    source["items"].append("c")
    nested = observation.payload["nested"]
    assert isinstance(nested, Mapping)
    assert nested["flag"] is True
    assert observation.payload["items"] == ("a", "b")
    with pytest.raises(TypeError):
        observation.payload["extra"] = "no"  # type: ignore[index]
    with pytest.raises(AttributeError):
        observation.observer_id = EntityId("other")  # type: ignore[misc]


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


def test_agent_state_hides_owned_collections() -> None:
    state = AgentState(AgentId("agent-1"))
    assert state.agent_id == AgentId("agent-1")
    assert "beliefs" not in dir(state)
    assert not hasattr(state, "beliefs")
    assert not hasattr(state, "on_change")


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
