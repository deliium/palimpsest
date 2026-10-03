"""World authority and objective names stay free of naming predicates."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.cognition.semantic_naming import (
    NamingReferentKind,
    apply_naming_update,
    stable8_digest,
)
from agents.models import AgentId
from tests.unit.test_world_rules import _accept, _state
from world._operations import OperationAccepted, validate_action_request
from world._rules import RuleDisposition, apply_operation
from world.actions import ActionRequest, Talk, Wait, require_agent_command
from world.communications import CommunicationRelation, origin_utterance
from world.identifiers import EntityId, ProposalId, RequestId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import Observation, ObservedSelf
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)


def _admitted(application: object) -> None:
    disposition = application.result.disposition  # type: ignore[attr-defined]
    assert disposition in {RuleDisposition.MUTATE, RuleDisposition.EVENT_ONLY}
    assert application.result.emits_event is True  # type: ignore[attr-defined]


def test_wait_and_call_talk_still_admit_without_naming_checks() -> None:
    state = _state()
    waited = apply_operation(state, _accept(Wait()))
    _admitted(waited)
    outcome = validate_action_request(
        world_id=WorldId("world-1"),
        state=waited.next_state,
        request=ActionRequest(
            request_id=RequestId("r-talk"),
            proposal_id=ProposalId("p-1"),
            world_id=WorldId("world-1"),
            actor_id=EntityId("body-1"),
            revision=WorldRevision(1),
            command=require_agent_command(
                Talk(
                    recipient_id=EntityId("body-2"),
                    utterance=origin_utterance(
                        text="call",
                        speaker_id=EntityId("body-1"),
                        relations=(
                            CommunicationRelation(
                                subject="place_deadbeef",
                                predicate="call",
                                object="location",
                            ),
                        ),
                    ),
                )
            ),
        ),
    )
    assert isinstance(outcome, OperationAccepted)
    talked = apply_operation(waited.next_state, outcome.operation)
    _admitted(talked)


def test_location_bootstrap_names_unchanged_by_labeling() -> None:
    state = _state()
    before = {
        entity_id.value: location.name
        for entity_id, location in state.locations.items()
    }
    identity = OwnerSafeSocialIdentity(
        owner_id=AgentId("ada"),
        owner_entity_id=EntityId("body-1"),
        counterparts=(
            CounterpartBinding(
                agent_id=AgentId("ben"), entity_id=EntityId("body-2")
            ),
        ),
    )
    location_id = next(iter(before))
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(1),
        tick=1,
        self_body=ObservedSelf(
            entity_id=EntityId("body-1"),
            location_id=EntityId(location_id),
            health=Health(100),
            hunger=Hunger(0),
            thirst=Thirst(0),
            fatigue=Fatigue(0),
            temperature=TemperatureCelsius(36.5),
            inventory=(),
            life_status=LifeStatus.ALIVE,
            carry_capacity=CarryCapacity(10),
        ),
        occurrences=(),
        visible_bodies=(),
    )
    ledger = apply_naming_update(observation, identity, None)
    assert ledger.bindings
    after = {
        entity_id.value: location.name
        for entity_id, location in state.locations.items()
    }
    assert before == after
    assert all(not token.startswith("place_") for token in after.values())


def test_two_owners_mint_different_place_seeds_for_same_location() -> None:
    location_id = "clearing"
    alice = stable8_digest(
        AgentId("alice"), NamingReferentKind.LOCATION, location_id
    )
    bob = stable8_digest(AgentId("bob"), NamingReferentKind.LOCATION, location_id)
    assert alice != bob
    assert f"place_{alice}" != f"place_{bob}"


def test_world_info_logs_omit_naming_tokens(caplog: pytest.LogCaptureFixture) -> None:
    state = _state()
    caplog.set_level(logging.INFO, logger="world")
    apply_operation(state, _accept(Wait()))
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "place_" not in messages
    assert "dead_" not in messages
    assert "semantic_naming" not in messages
