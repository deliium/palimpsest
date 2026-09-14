"""Authoritative world state and agent-facing contracts.

Public facade. ``world._state`` and ``world._transitions`` are private
authority modules and must not be re-exported.
"""

from world.actions import (
    ActionOutcome,
    ActionProposal,
    ActionRequest,
    OutcomeCategory,
    ProposalId,
    RequestId,
    WorldGateway,
    accept_action_request,
)
from world.events import EventId, WorldEvent
from world.identifiers import EntityId, WorldRevision
from world.observations import Observation, detached_mapping

__all__ = [
    "ActionOutcome",
    "ActionProposal",
    "ActionRequest",
    "EntityId",
    "EventId",
    "Observation",
    "OutcomeCategory",
    "ProposalId",
    "RequestId",
    "WorldEvent",
    "WorldGateway",
    "WorldRevision",
    "accept_action_request",
    "detached_mapping",
]
