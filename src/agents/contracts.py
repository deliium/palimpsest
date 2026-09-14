"""Orchestration-boundary identity translation.

``AgentId`` and world ``EntityId`` remain distinct types. Only simulation
may implement this protocol.
"""

from __future__ import annotations

from typing import Protocol

from agents.models import AgentId
from world.identifiers import EntityId


class IdentityTranslator(Protocol):
    """Explicit mapping between agent identity and world entity identity."""

    def to_entity_id(self, agent_id: AgentId) -> EntityId:
        """Translate an agent id into the corresponding world entity id."""
        ...

    def to_agent_id(self, entity_id: EntityId) -> AgentId:
        """Translate a world entity id into the corresponding agent id."""
        ...
