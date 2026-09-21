"""Unit tests for world and agent contract surfaces."""

from __future__ import annotations

from world.communications import origin_utterance

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agents.models import Agent, AgentId
from simulation.lifecycle import require_action_submission
from world.actions import (
    ActionProposal,
    ActionRequest,
    TransitionOutcome,
    Wait,
)
from world.events import Waited, make_replayable_event
from world.identifiers import (
    EntityId,
    EventId,
    ProposalId,
    RequestId,
    WorldId,
    WorldRevision,
)
from world.models import LifeStatus
from world.observations import (
    PERCEPTION_FIELD_ACCESS,
    Observation,
    ObservationAudienceRole,
    ObservationFieldAccess,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
    ObservedItem,
    ObservedItemPlacement,
    ObservedLocation,
    ObservedOccurrence,
    ObservedSelf,
    observed_self_from_body,
)
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    ItemKind,
    ItemLoad,
    TemperatureCelsius,
    Thirst,
)

_ID_TEXT = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=24,
)


def _self(entity_id: str, location_id: str) -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId(entity_id),
        location_id=EntityId(location_id),
        health=Health(10),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
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
    locations = [ObservedLocation(entity_id=EntityId("loc-1"), name=location_name)]
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId(observer),
        revision=WorldRevision(revision),
        locations=locations,
    )
    locations.clear()
    assert observation.locations == (
        ObservedLocation(entity_id=EntityId("loc-1"), name=location_name),
    )


def test_observation_is_typed_partial_and_immutable() -> None:
    body = _self("observer-1", "loc-1")
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("observer-1"),
        revision=WorldRevision(1),
        self_body=body,
        locations=(ObservedLocation(entity_id=EntityId("loc-1"), name="Camp"),),
    )
    assert observation.self_body == body
    assert observation.items == ()
    assert observation.occurrences == ()
    assert observation.communications == ()
    with pytest.raises(AttributeError):
        observation.observer_id = EntityId("other")  # type: ignore[misc]
    with pytest.raises(ValueError, match="must match observer_id"):
        Observation(
            world_id=WorldId("world-1"),
            observer_id=EntityId("observer-1"),
            revision=WorldRevision(1),
            self_body=_self("other", "loc-1"),
        )


def test_observation_rejects_objective_policy_fields_on_redacted_dtos() -> None:
    location = ObservedLocation(entity_id=EntityId("loc-1"), name="Camp")
    assert not hasattr(location, "body_capacity")
    assert not hasattr(location, "item_capacity")
    assert not hasattr(location, "shelter_factor")
    resource_fields = ObservedItem.__dataclass_fields__
    assert "location_id" not in resource_fields
    assert "holder_id" not in resource_fields
    assert "maximum_quantity" not in ObservedItem.__dataclass_fields__
    from world.observations import ObservedResource

    assert "maximum_quantity" not in ObservedResource.__dataclass_fields__
    assert "regeneration_per_tick" not in ObservedResource.__dataclass_fields__


def test_perception_field_access_matrix_is_closed() -> None:
    assert PERCEPTION_FIELD_ACCESS["self"] is ObservationFieldAccess.ALWAYS_SELF
    assert (
        PERCEPTION_FIELD_ACCESS["ground_items"]
        is ObservationFieldAccess.VISIBILITY_GATED
    )
    assert (
        PERCEPTION_FIELD_ACCESS["communications"]
        is ObservationFieldAccess.RECIPIENT_ONLY
    )
    assert PERCEPTION_FIELD_ACCESS["other_inventory"] is ObservationFieldAccess.OMITTED
    assert PERCEPTION_FIELD_ACCESS["request_ids"] is ObservationFieldAccess.OMITTED
    assert set(ObservationFieldAccess) == {
        ObservationFieldAccess.ALWAYS_SELF,
        ObservationFieldAccess.VISIBILITY_GATED,
        ObservationFieldAccess.PARTICIPANT_ONLY,
        ObservationFieldAccess.RECIPIENT_ONLY,
        ObservationFieldAccess.OMITTED,
    }


def test_visible_body_omits_inventory_and_exact_physiology_fields() -> None:
    from world.observations import VisibleBody

    fields = set(VisibleBody.__dataclass_fields__)
    assert fields == {"entity_id", "life_status", "coarse_health"}
    for forbidden in (
        "inventory",
        "hunger",
        "thirst",
        "fatigue",
        "temperature",
        "health",
        "carry_capacity",
    ):
        assert forbidden not in fields


def test_occurrence_and_communication_require_prior_tick_and_unique_sources() -> None:
    provenance = ObservationProvenance(
        source_kind=ObservationSourceKind.OCCURRENCE,
        source_tick=0,
        source_event_id=EventId("event-1"),
    )
    occurrence = ObservedOccurrence(
        provenance=provenance,
        kind="wait",
        audience_role=ObservationAudienceRole.ACTOR,
        actor_id=EntityId("observer-1"),
    )
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("observer-1"),
        revision=WorldRevision(1),
        tick=1,
        occurrences=(occurrence,),
    )
    assert observation.occurrences[0].kind == "wait"
    with pytest.raises(ValueError, match="prior committed tick"):
        Observation(
            world_id=WorldId("world-1"),
            observer_id=EntityId("observer-1"),
            revision=WorldRevision(1),
            tick=0,
            occurrences=(occurrence,),
        )
    duplicate = ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=0,
            source_event_id=EventId("event-1"),
        ),
        kind="move",
        audience_role=ObservationAudienceRole.BYSTANDER,
    )
    with pytest.raises(ValueError, match="unique"):
        Observation(
            world_id=WorldId("world-1"),
            observer_id=EntityId("observer-1"),
            revision=WorldRevision(1),
            tick=1,
            occurrences=(occurrence, duplicate),
        )
    communication = ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=0,
            source_event_id=EventId("event-2"),
        ),
        speaker_id=EntityId("speaker-1"),
        listener_id=EntityId("observer-1"),
        utterance=origin_utterance(text="hello", speaker_id=EntityId("speaker-1")),
        action_kind="talk",
    )
    assert ObservedCommunication.__doc__ is not None
    assert "does not assert that the content is true" in ObservedCommunication.__doc__
    bundled = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("observer-1"),
        revision=WorldRevision(1),
        tick=1,
        occurrences=(occurrence,),
        communications=(communication,),
    )
    assert bundled.communications[0].utterance.content.text == "hello"


def test_held_item_must_match_self_inventory() -> None:
    body = ObservedSelf(
        entity_id=EntityId("observer-1"),
        location_id=EntityId("loc-1"),
        health=Health(10),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(EntityId("item-1"),),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )
    item = ObservedItem(
        entity_id=EntityId("item-1"),
        name="Cup",
        kind=ItemKind.GENERIC,
        load=ItemLoad(1),
        placement=ObservedItemPlacement.HELD_BY_SELF,
    )
    assert (
        Observation(
            world_id=WorldId("world-1"),
            observer_id=EntityId("observer-1"),
            revision=WorldRevision(1),
            self_body=body,
            items=(item,),
        )
        .items[0]
        .placement
        is ObservedItemPlacement.HELD_BY_SELF
    )
    with pytest.raises(ValueError, match=r"ObservedSelf\.inventory"):
        Observation(
            world_id=WorldId("world-1"),
            observer_id=EntityId("observer-1"),
            revision=WorldRevision(1),
            self_body=_self("observer-1", "loc-1"),
            items=(item,),
        )


def test_observed_self_from_body_preserves_physiology() -> None:
    from world.models import AgentBody

    body = AgentBody(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        health=Health(80),
        hunger=Hunger(1),
        thirst=Thirst(2),
        fatigue=Fatigue(3),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )
    projected = observed_self_from_body(body)
    assert projected.health == body.health
    assert projected.entity_id == body.entity_id


def test_world_event_is_immutable_occurrence() -> None:
    event = make_replayable_event(
        event_id=EventId("event-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=0,
        sequence=0,
        request_id=RequestId("r-1"),
        resulting_revision=WorldRevision(3),
        details=Waited(),
        actor_id=None,
    )
    assert event.details == Waited()
    with pytest.raises(AttributeError):
        event.resulting_revision = WorldRevision(4)  # type: ignore[misc]


def test_submissions_reject_proposal_and_raw_mapping() -> None:
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
    with pytest.raises(TypeError, match="ActionSubmission"):
        require_action_submission(proposal)
    with pytest.raises(TypeError, match=r"action submission|mappings"):
        require_action_submission(mapping)

    request = ActionRequest(
        request_id=RequestId("r-1"),
        proposal_id=ProposalId("p-1"),
        world_id=WorldId("world-1"),
        actor_id=EntityId("actor-1"),
        revision=WorldRevision(1),
        command=Wait(),
    )
    with pytest.raises(TypeError, match="ActionSubmission"):
        require_action_submission(request)


def test_public_facade_hides_legacy_gateway_symbols() -> None:
    import world

    assert "WorldGateway" not in world.__all__
    assert "accept_action_request" not in world.__all__
    assert "ActionOutcome" not in world.__all__
    assert "TransitionOutcome" not in world.__all__
    assert "ObservedLocation" in world.__all__
    assert "ObservationProvenance" in world.__all__


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
