"""Mypy fixtures for V1 domain command and request contracts."""

from __future__ import annotations

from typing import assert_never

from world.actions import (
    ActionProposal,
    ActionRequest,
    AgentCommand,
    Ask,
    Attack,
    Build,
    Craft,
    Drink,
    Drop,
    Eat,
    Flee,
    Give,
    Harvest,
    Help,
    Move,
    Repair,
    Search,
    Sleep,
    Store,
    Take,
    Talk,
    Tell,
    Wait,
    require_agent_command,
)
from world.events import EventDetails, Waited
from world.identifiers import (
    EntityId,
    ProposalId,
    RequestId,
    WorldId,
    WorldRevision,
)


def _accepted_command() -> AgentCommand:
    return require_agent_command(Wait())


def _proposal_and_request() -> tuple[ActionProposal, ActionRequest]:
    command: AgentCommand = Move(EntityId("loc-1"))
    proposal = ActionProposal(proposal_id=ProposalId("p-1"), command=command)
    request = ActionRequest(
        request_id=RequestId("r-1"),
        proposal_id=proposal.proposal_id,
        world_id=WorldId("world-1"),
        actor_id=EntityId("body-1"),
        revision=WorldRevision(0),
        command=command,
    )
    return proposal, request


def _admission_uses_agent_command() -> AgentCommand:
    from agents.models import AgentId
    from simulation.actions import admit_agent_command
    from simulation.models import SimulationRunConfig

    class _Translator:
        def to_entity_id(self, agent_id: AgentId) -> EntityId:
            return EntityId(agent_id.value)

        def to_agent_id(self, entity_id: EntityId) -> AgentId:
            return AgentId(entity_id.value)

    _proposal, request = admit_agent_command(
        config=SimulationRunConfig(seed=1),
        agent_id=AgentId("agent-1"),
        command=Wait(),
        translator=_Translator(),
        world_id=WorldId("world-1"),
        revision=WorldRevision(0),
        keys=("k",),
    )
    return request.command


def _exhaust_agent_command(command: AgentCommand) -> str:
    match command:
        case Move():
            return "move"
        case Search():
            return "search"
        case Take():
            return "take"
        case Drop():
            return "drop"
        case Give():
            return "give"
        case Eat():
            return "eat"
        case Drink():
            return "drink"
        case Sleep():
            return "sleep"
        case Talk():
            return "talk"
        case Ask():
            return "ask"
        case Tell():
            return "tell"
        case Help():
            return "help"
        case Attack():
            return "attack"
        case Flee():
            return "flee"
        case Wait():
            return "wait"
        case Harvest():
            return "harvest"
        case Craft():
            return "craft"
        case Build():
            return "build"
        case Repair():
            return "repair"
        case Store():
            return "store"
        case _:
            assert_never(command)


def _observation_uses_redacted_projections() -> None:
    from world.models import LifeStatus
    from world.observations import (
        Observation,
        ObservedLocation,
        ObservedSelf,
        VisibleBody,
        VisibleExit,
    )
    from world.values import (
        CarryCapacity,
        Fatigue,
        Health,
        Hunger,
        TemperatureCelsius,
        Thirst,
    )

    self_body = ObservedSelf(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        health=Health(10),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        self_body=self_body,
        locations=(ObservedLocation(entity_id=EntityId("loc-1"), name="Camp"),),
        exits=(VisibleExit(destination_id=EntityId("loc-2"), name="Forest"),),
        visible_bodies=(),
    )
    assert isinstance(observation.locations[0], ObservedLocation)
    assert not hasattr(observation.locations[0], "body_capacity")
    _ = VisibleBody


def _event_detail_kind(details: EventDetails) -> str:
    if isinstance(details, Waited):
        return details.kind
    return details.kind


def _lifecycle_token_is_not_request_id() -> None:
    from simulation.clock import Tick
    from simulation.lifecycle import TickToken
    from world.identifiers import RequestId

    token = TickToken("tok-1", Tick(0))
    request_id = RequestId("r-1")
    assert token.value != request_id.value or True
