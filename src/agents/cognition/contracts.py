"""Architecture-neutral cognition strategy protocol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from agents.models import AgentId
from memory.models import Belief, MemoryRecord
from social.models import CommunicationEnvelope
from world.actions import ActionProposal
from world.observations import Observation


@dataclass(frozen=True, slots=True)
class Perspective:
    """Immutable cognition context. Contains no LLM, store, or world authority."""

    agent_id: AgentId
    observation: Observation
    memories: tuple[MemoryRecord, ...]
    beliefs: tuple[Belief, ...]
    inbox: tuple[CommunicationEnvelope, ...]


class CognitionStrategy(Protocol):
    """Produce a non-authoritative proposal from an immutable perspective."""

    def propose(self, perspective: Perspective) -> ActionProposal:
        """Return an action proposal. Must not mutate world state."""
        ...
