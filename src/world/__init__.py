"""Authoritative world state and agent-facing contracts.

Public facade. ``world._state`` and ``world._transitions`` are private
authority modules and must not be re-exported.
"""

from world.actions import (
    ActionOutcome,
    ActionProposal,
    ActionRequest,
    OutcomeCategory,
    WorldGateway,
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
from world.models import AgentBody, Item, LifeStatus, Location, Resource, Weather
from world.observations import Observation, detached_mapping
from world.values import (
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)

__all__ = [
    "ActionOutcome",
    "ActionProposal",
    "ActionRequest",
    "AgentBody",
    "EntityId",
    "EventId",
    "Fatigue",
    "Health",
    "Hunger",
    "Item",
    "LifeStatus",
    "Location",
    "Observation",
    "OutcomeCategory",
    "ProposalId",
    "RequestId",
    "Resource",
    "TemperatureCelsius",
    "Thirst",
    "Weather",
    "WorldEvent",
    "WorldGateway",
    "WorldId",
    "WorldRevision",
    "accept_action_request",
    "detached_mapping",
]
