"""Detached participant identity bindings, independent of world materialization."""

from dataclasses import dataclass

from agents.models import AgentId
from world.identifiers import EntityId

__all__ = ["AgentRegistration"]


@dataclass(frozen=True, slots=True)
class AgentRegistration:
    """Ordered AgentId to body EntityId binding for one participant."""

    agent_id: AgentId
    entity_id: EntityId

    def __post_init__(self) -> None:
        if type(self.agent_id) is not AgentId:
            raise TypeError("AgentRegistration.agent_id must be AgentId")
        if type(self.entity_id) is not EntityId:
            raise TypeError("AgentRegistration.entity_id must be EntityId")
